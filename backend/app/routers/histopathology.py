import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..histopathology.audit_log import append_audit_event, get_audit_log_path
from ..histopathology.debug_patches import save_patch_debug_images
from ..histopathology.heatmap_access import (
    check_heatmap_rate_limit,
    heatmap_rate_limit_key,
    max_tile_size_for_role,
    max_tiles_for_role,
    normalize_role,
)
from ..histopathology.heatmap_jobs import (
    acquire_heatmap_worker,
    create_heatmap_job,
    get_heatmap_job,
    release_heatmap_worker,
    update_heatmap_job,
    utc_now as job_utc_now,
)
from ..histopathology.heatmap_store import (
    load_heatmap_history_for_image,
    load_heatmap_by_trace,
    load_latest_heatmap_for_image,
    save_heatmap_result,
    update_heatmap_educational_metadata,
)
from ..histopathology.heatmap_tile_cache import (
    build_tile_cache_key,
    load_cached_tile,
    save_cached_tile,
)
from ..histopathology.ml.conch_feature_extractor import ModelUnavailableError
from ..histopathology.ml.inference_service import DEFAULT_LABELS, get_inference_service
from ..histopathology.patch_extractor import OpenSlidePatchExtractor, PatchExtractionError
from ..histopathology.roi_quality import evaluate_roi_quality, get_quality_thresholds
from ..histopathology.roi import validate_roi_pair
from ..histopathology.schemas import (
    CorrectionCreateRequest,
    DOCENTE_LABEL_CHOICES,
    HeatmapEducationalMetadataUpdate,
    HistopathologyAnalyzeRequest,
    HistopathologyScanRequest,
    ROIBox,
)
from ..models import HistopathologyCorrection, HistopathologySession, MedicalImage
from ..auth import get_current_user


router = APIRouter(prefix="/api/histopathology", tags=["histopathology"])

EDUCATIONAL_WARNING = (
    "Modulo educativo no diagnostico. La prediccion esta limitada a patches de "
    "ganglio linfatico tipo CAMELYON/PCam y puede abstenerse ante estroma."
)


def _dump_schema(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _configured_confidence_threshold() -> float:
    value = os.getenv("HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD")
    if value is None:
        return 0.90
    try:
        parsed = float(value)
    except ValueError:
        return 0.90
    return parsed if 0.0 < parsed <= 1.0 else 0.90


def _require_heatmap_manager(current_user) -> None:
    if getattr(current_user, "role", None) not in {"docente", "administrador"}:
        raise HTTPException(
            status_code=403,
            detail="Solo docentes y administradores pueden modificar mapas educativos.",
        )


def _require_docente_or_admin(current_user) -> None:
    if getattr(current_user, "role", None) not in {"docente", "administrador"}:
        raise HTTPException(
            status_code=403,
            detail="Solo docentes y administradores pueden realizar esta accion.",
        )


def _save_histopathology_session(
    db: Session, user_id: int | None, image_id: int, payload: dict
) -> None:
    """Persiste un resultado de analisis ROI 2 en histopathology_sessions."""
    if user_id is None:
        return
    roi_quality = payload.get("roi_quality") or {}
    metrics = roi_quality.get("metrics") if isinstance(roi_quality, dict) else None
    analyzed_at_str = payload.get("analyzed_at") or _utc_now()
    try:
        analyzed_at_dt = datetime.fromisoformat(analyzed_at_str).replace(tzinfo=None)
    except Exception:
        analyzed_at_dt = datetime.now(timezone.utc).replace(tzinfo=None)

    existing = (
        db.query(HistopathologySession)
        .filter(HistopathologySession.trace_id == payload["trace_id"])
        .first()
    )
    if existing:
        return

    session = HistopathologySession(
        trace_id=payload["trace_id"],
        user_id=user_id,
        image_id=image_id,
        analyzed_at=analyzed_at_dt,
        roi_1=payload.get("roi_1"),
        roi_2=payload.get("roi_2"),
        status=payload.get("status", "clasificado"),
        clase=payload.get("clase"),
        confidence=payload.get("confidence"),
        probabilities=payload.get("probabilities"),
        reason=payload.get("reason"),
        recommendation=payload.get("recommendation"),
        roi_quality_metrics=metrics,
        warning=payload.get("warning"),
    )
    db.add(session)
    db.commit()


def _correction_to_out(c: HistopathologyCorrection) -> dict:
    return {
        "id": c.id,
        "session_id": c.session_id,
        "trace_id": c.trace_id,
        "docente_label": c.docente_label,
        "docente_note": c.docente_note,
        "include_in_dataset": c.include_in_dataset,
        "corrected_at": c.corrected_at.isoformat() if c.corrected_at else None,
        "docente_user_id": c.docente_user_id,
    }


def _session_to_summary(s: HistopathologySession) -> dict:
    return {
        "id": s.id,
        "trace_id": s.trace_id,
        "image_id": s.image_id,
        "analyzed_at": s.analyzed_at.isoformat() if s.analyzed_at else None,
        "status": s.status,
        "clase": s.clase,
        "confidence": s.confidence,
        "roi_1": s.roi_1,
        "roi_2": s.roi_2,
        "correction": _correction_to_out(s.correction) if s.correction else None,
    }


def _session_to_detail(s: HistopathologySession) -> dict:
    return {
        **_session_to_summary(s),
        "user_id": s.user_id,
        "probabilities": s.probabilities,
        "reason": s.reason,
        "recommendation": s.recommendation,
        "roi_quality_metrics": s.roi_quality_metrics,
        "warning": s.warning,
    }


def _validate_roi_bounds(roi: ROIBox, slide_width: int, slide_height: int) -> None:
    if roi.x + roi.width > slide_width or roi.y + roi.height > slide_height:
        raise ValueError("La ROI queda fuera de los limites de la lamina.")


def _model_metadata(inference_service) -> dict:
    return {
        "task": "camelyon_patch_classification_with_stroma_abstention",
        "backbone": "CONCH frozen",
        "classifier": f"{inference_service.num_classes}-class linear head over CONCH embeddings",
        "checkpoint_ref": inference_service.checkpoint_ref,
        "classifier_checkpoint": inference_service.classifier_path,
        "device": inference_service.device,
        "feature_dim": inference_service.feature_dim,
        "num_classes": inference_service.num_classes,
        "classifier_kind": inference_service.classifier_kind,
        "labels": inference_service.labels,
        "class_mapping": inference_service.class_mapping,
        "confidence_threshold": inference_service.confidence_threshold,
        "training_mode": inference_service.training_mode,
        "validation": inference_service.validation,
    }


def _heatmap_model_signature(inference_service) -> str:
    return "|".join(
        [
            str(inference_service.classifier_path),
            str(inference_service.checkpoint_ref),
            str(inference_service.num_classes),
            str(inference_service.confidence_threshold),
        ]
    )


def _axis_positions(start: int, length: int, tile_size: int, stride: int) -> list[int]:
    if length <= tile_size:
        return [start]

    end = start + length
    positions = list(range(start, end - tile_size + 1, stride))
    last = end - tile_size
    if not positions or positions[-1] != last:
        positions.append(last)
    return positions


def _tile_grid(roi: ROIBox, tile_size: int, stride: int, max_tiles: int) -> list[ROIBox]:
    tiles = []
    x_positions = _axis_positions(roi.x, roi.width, tile_size, stride)
    y_positions = _axis_positions(roi.y, roi.height, tile_size, stride)

    for y in y_positions:
        for x in x_positions:
            width = min(tile_size, roi.x + roi.width - x)
            height = min(tile_size, roi.y + roi.height - y)
            if width < 64 or height < 64:
                continue
            tiles.append(ROIBox(x=x, y=y, width=width, height=height))
            if len(tiles) >= max_tiles:
                return tiles
    return tiles


def _execute_heatmap_scan(
    *,
    request: HistopathologyScanRequest,
    image_payload: dict,
    user_id: int | None,
    trace_id: str | None = None,
    analyzed_at: str | None = None,
    progress_callback=None,
) -> dict:
    trace_id = trace_id or str(uuid4())
    analyzed_at = analyzed_at or _utc_now()
    roi_payload = _dump_schema(request.roi)
    extractor = OpenSlidePatchExtractor()

    slide_width, slide_height = extractor.get_slide_dimensions(image_payload["file_path"])
    _validate_roi_bounds(request.roi, slide_width, slide_height)
    tiles = _tile_grid(request.roi, request.tile_size, request.stride, request.max_tiles)
    total_tiles = len(tiles)
    if progress_callback:
        progress_callback(0, total_tiles)
    inference_service = get_inference_service()
    model_signature = _heatmap_model_signature(inference_service)
    cache_hits = 0
    cache_misses = 0

    tile_results = []
    for index, tile_roi in enumerate(tiles):
        tile_roi_payload = _dump_schema(tile_roi)
        cache_key = build_tile_cache_key(
            image_id=request.image_id,
            roi=tile_roi_payload,
            model_signature=model_signature,
        )
        cached_tile = load_cached_tile(cache_key)
        if cached_tile:
            cache_hits += 1
            tile_results.append(
                {
                    **cached_tile,
                    "index": index,
                    "cache": "hit",
                    "cache_key": cache_key,
                }
            )
            if progress_callback:
                progress_callback(index + 1, total_tiles)
            continue

        cache_misses += 1
        try:
            patch_rgb = extractor.extract_roi2(image_payload["file_path"], tile_roi)
        except PatchExtractionError as exc:
            tile_results.append(
                {
                    "index": index,
                    "roi": tile_roi_payload,
                    "status": "error",
                    "class": "error",
                    "confidence": 0.0,
                    "probabilities": {},
                    "tumor_score": 0.0,
                    "cache": "miss",
                    "cache_key": cache_key,
                    "reason": str(exc),
                }
            )
            if progress_callback:
                progress_callback(index + 1, total_tiles)
            continue

        roi_quality = evaluate_roi_quality(patch_rgb)
        if not roi_quality["is_evaluable"]:
            tile_result = {
                "index": index,
                "roi": tile_roi_payload,
                "status": "roi_no_evaluable",
                "class": "roi_no_evaluable",
                "confidence": 0.0,
                "probabilities": {},
                "tumor_score": 0.0,
                "roi_quality": roi_quality,
                "cache": "miss",
                "cache_key": cache_key,
                "reason": roi_quality["reason"],
            }
            tile_results.append(tile_result)
            try:
                save_cached_tile(cache_key, tile_result)
            except OSError:
                tile_result["cache_save_error"] = True
            if progress_callback:
                progress_callback(index + 1, total_tiles)
            continue

        raw_prediction = inference_service.predict_patch(patch_rgb)
        status = "clasificado"
        predicted_class = raw_prediction["predicted_class"]
        reason = None

        if predicted_class == "estroma":
            status = "roi_no_evaluable"
            predicted_class = "roi_no_evaluable"
            reason = "Tile marcado como estroma por la cabeza 3-class."
        elif raw_prediction["confidence"] < inference_service.confidence_threshold:
            status = "resultado_incierto"
            predicted_class = "incierto"
            reason = "Ninguna clase supera el umbral de confianza configurado."

        probabilities = raw_prediction["probabilities"]
        tile_result = {
            "index": index,
            "roi": tile_roi_payload,
            "status": status,
            "class": predicted_class,
            "model_predicted_class": raw_prediction["model_predicted_class"],
            "confidence": raw_prediction["confidence"],
            "probabilities": probabilities,
            "tumor_score": float(probabilities.get("metastasico", 0.0)),
            "roi_quality": roi_quality,
            "cache": "miss",
            "cache_key": cache_key,
            "reason": reason,
        }
        tile_results.append(tile_result)
        try:
            save_cached_tile(cache_key, tile_result)
        except OSError:
            tile_result["cache_save_error"] = True
        if progress_callback:
            progress_callback(index + 1, total_tiles)

    evaluable_tiles = [tile for tile in tile_results if tile["status"] != "error"]
    best_tile = max(evaluable_tiles, key=lambda item: item.get("tumor_score", 0.0), default=None)
    classified_tumor = [
        tile for tile in tile_results
        if tile.get("class") == "metastasico"
    ]
    uncertain_high = [
        tile for tile in tile_results
        if tile.get("status") == "resultado_incierto" and tile.get("tumor_score", 0.0) >= 0.50
    ]

    response_payload = {
        "trace_id": trace_id,
        "analyzed_at": analyzed_at,
        "image_id": request.image_id,
        "status": "completed",
        "roi": roi_payload,
        "tile_size": request.tile_size,
        "stride": request.stride,
        "requested_max_tiles": request.max_tiles,
        "tile_count": len(tile_results),
        "tiles": tile_results,
        "summary": {
            "classified_metastatic_tiles": len(classified_tumor),
            "uncertain_high_tumor_tiles": len(uncertain_high),
            "best_tile": best_tile,
            "max_tumor_score": best_tile.get("tumor_score", 0.0) if best_tile else 0.0,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": cache_hits / total_tiles if total_tiles else 0.0,
        },
        "slide_dimensions": {
            "width": slide_width,
            "height": slide_height,
        },
        "educational": {
            "label": request.educational_label or "",
            "note": request.educational_note or "",
            "type": request.educational_type or "referencia",
        },
        "model": _model_metadata(inference_service),
        "persisted": False,
        "warning": EDUCATIONAL_WARNING,
    }

    try:
        heatmap_artifacts = save_heatmap_result(response_payload)
        response_payload["persisted"] = True
        response_payload["artifacts"] = heatmap_artifacts
    except OSError as exc:
        response_payload["persisted"] = False
        response_payload["artifact_error"] = str(exc)

    append_audit_event(
        {
            "event": "histopathology_scan_succeeded",
            "trace_id": trace_id,
            "timestamp": analyzed_at,
            "image_id": request.image_id,
            "image_filename": image_payload.get("filename"),
            "user_id": user_id,
            "roi": roi_payload,
            "tile_size": request.tile_size,
            "stride": request.stride,
            "tile_count": len(tile_results),
            "summary": response_payload["summary"],
            "persisted": response_payload["persisted"],
            "artifacts": response_payload.get("artifacts"),
            "artifact_error": response_payload.get("artifact_error"),
            "model": response_payload["model"],
            "warning": EDUCATIONAL_WARNING,
        }
    )

    return response_payload


def _run_heatmap_job(
    *,
    job_id: str,
    request: HistopathologyScanRequest,
    image_payload: dict,
    user_id: int | None,
    trace_id: str,
):
    acquire_heatmap_worker()
    update_heatmap_job(
        job_id,
        status="running",
        started_at=job_utc_now(),
        progress=0.0,
    )

    def update_progress(processed: int, total: int):
        progress = processed / total if total else 1.0
        update_heatmap_job(
            job_id,
            processed_tiles=processed,
            total_tiles=total,
            progress=progress,
        )

    try:
        result = _execute_heatmap_scan(
            request=request,
            image_payload=image_payload,
            user_id=user_id,
            trace_id=trace_id,
            analyzed_at=_utc_now(),
            progress_callback=update_progress,
        )
        update_heatmap_job(
            job_id,
            status="completed",
            progress=1.0,
            processed_tiles=result["tile_count"],
            total_tiles=result["tile_count"],
            completed_at=job_utc_now(),
            result=result,
        )
    except Exception as exc:
        update_heatmap_job(
            job_id,
            status="failed",
            failed_at=job_utc_now(),
            error=str(exc),
        )
        append_audit_event(
            {
                "event": "histopathology_heatmap_job_failed",
                "trace_id": trace_id,
                "timestamp": _utc_now(),
                "image_id": request.image_id,
                "image_filename": image_payload.get("filename"),
                "user_id": user_id,
                "roi": _dump_schema(request.roi),
                "error_type": type(exc).__name__,
                "detail": str(exc),
            }
        )
    finally:
        release_heatmap_worker()


@router.get("/status")
async def histopathology_status():
    checkpoint_path = os.getenv("HISTO_CLASSIFIER_CHECKPOINT")
    checkpoint_configured = bool(checkpoint_path)

    try:
        inference_service = get_inference_service()
        checkpoint_path = inference_service.classifier_path
        checkpoint_configured = bool(checkpoint_path)
        return {
            "model_ready": True,
            "task": "camelyon_patch_classification_with_stroma_abstention",
            "backbone": "CONCH frozen",
            "classifier": f"{inference_service.num_classes}-class linear head over CONCH embeddings",
            "checkpoint_configured": checkpoint_configured,
            "classifier_checkpoint": checkpoint_path,
            "checkpoint_ref": inference_service.checkpoint_ref,
            "device": inference_service.device,
            "feature_dim": inference_service.feature_dim,
            "num_classes": inference_service.num_classes,
            "classifier_kind": inference_service.classifier_kind,
            "labels": inference_service.labels,
            "class_mapping": inference_service.class_mapping,
            "confidence_threshold": inference_service.confidence_threshold,
            "roi_quality_thresholds": get_quality_thresholds().__dict__,
            "training_mode": inference_service.training_mode,
            "validation": inference_service.validation,
            "created_at": inference_service.created_at,
            "audit_log_path": str(get_audit_log_path()),
            "model_input": "CONCH preprocess target, typically 224x224",
            "warning": EDUCATIONAL_WARNING,
        }
    except ModelUnavailableError as exc:
        return {
            "model_ready": False,
            "reason": str(exc),
            "checkpoint_configured": checkpoint_configured,
            "classifier_checkpoint": checkpoint_path,
            "audit_log_path": str(get_audit_log_path()),
            "class_mapping": DEFAULT_LABELS,
            "confidence_threshold": _configured_confidence_threshold(),
            "roi_quality_thresholds": get_quality_thresholds().__dict__,
            "required_env": [
                "HISTO_CLASSIFIER_CHECKPOINT",
                "HISTO_CONCH_CHECKPOINT_REF",
                "HF_TOKEN or HISTO_HF_TOKEN if the CONCH checkpoint requires authentication",
            ],
            "warning": EDUCATIONAL_WARNING,
        }
    except Exception as exc:
        return {
            "model_ready": False,
            "reason": f"Unexpected histopathology model status error: {exc}",
            "checkpoint_configured": checkpoint_configured,
            "classifier_checkpoint": checkpoint_path,
            "audit_log_path": str(get_audit_log_path()),
            "class_mapping": DEFAULT_LABELS,
            "confidence_threshold": _configured_confidence_threshold(),
            "roi_quality_thresholds": get_quality_thresholds().__dict__,
            "warning": EDUCATIONAL_WARNING,
        }


@router.post("/analyze-roi")
async def analyze_roi2(
    request: HistopathologyAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    trace_id = str(uuid4())
    analyzed_at = _utc_now()
    roi_1_payload = _dump_schema(request.roi_1)
    roi_2_payload = _dump_schema(request.roi_2)

    image = (
        db.query(MedicalImage)
        .filter(MedicalImage.id == request.image_id, MedicalImage.is_active == True)
        .first()
    )

    if not image:
        append_audit_event(
            {
                "event": "histopathology_analyze_failed",
                "trace_id": trace_id,
                "timestamp": analyzed_at,
                "image_id": request.image_id,
                "user_id": getattr(current_user, "id", None),
                "roi_1": roi_1_payload,
                "roi_2": roi_2_payload,
                "error_type": "image_not_found",
                "detail": "Imagen no encontrada",
            }
        )
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    extractor = OpenSlidePatchExtractor()

    try:
        slide_width, slide_height = extractor.get_slide_dimensions(image.file_path)
        validate_roi_pair(request.roi_1, request.roi_2, slide_width, slide_height)
        patch_rgb = extractor.extract_roi2(image.file_path, request.roi_2)
    except ValueError as exc:
        append_audit_event(
            {
                "event": "histopathology_analyze_failed",
                "trace_id": trace_id,
                "timestamp": analyzed_at,
                "image_id": request.image_id,
                "user_id": getattr(current_user, "id", None),
                "roi_1": roi_1_payload,
                "roi_2": roi_2_payload,
                "error_type": "roi_validation_error",
                "detail": str(exc),
            }
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PatchExtractionError as exc:
        append_audit_event(
            {
                "event": "histopathology_analyze_failed",
                "trace_id": trace_id,
                "timestamp": analyzed_at,
                "image_id": request.image_id,
                "user_id": getattr(current_user, "id", None),
                "roi_1": roi_1_payload,
                "roi_2": roi_2_payload,
                "error_type": "patch_extraction_error",
                "detail": str(exc),
            }
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    debug_artifacts = save_patch_debug_images(trace_id, patch_rgb)

    try:
        inference_service = get_inference_service()
    except ModelUnavailableError as exc:
        append_audit_event(
            {
                "event": "histopathology_analyze_failed",
                "trace_id": trace_id,
                "timestamp": analyzed_at,
                "image_id": request.image_id,
                "user_id": getattr(current_user, "id", None),
                "roi_1": roi_1_payload,
                "roi_2": roi_2_payload,
                "patch_size": {
                    "extracted_width": patch_rgb.width,
                    "extracted_height": patch_rgb.height,
                },
                "debug_artifacts": debug_artifacts,
                "error_type": "model_unavailable",
                "detail": str(exc),
            }
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        preprocessed_debug_patch = inference_service.preprocess_debug_image(patch_rgb)
        preprocessed_debug_tensor = inference_service.preprocess_debug_tensor(patch_rgb)
        debug_artifacts = save_patch_debug_images(
            trace_id,
            patch_rgb,
            preprocessed_patch=preprocessed_debug_patch,
            preprocessed_tensor=preprocessed_debug_tensor,
        )
    except Exception as exc:
        debug_artifacts = {
            **debug_artifacts,
            "preprocessed_patch_error": str(exc),
        }

    roi_quality = evaluate_roi_quality(patch_rgb)
    patch_metadata = {
        "extracted_width": patch_rgb.width,
        "extracted_height": patch_rgb.height,
        "roi_2_width": request.roi_2.width,
        "roi_2_height": request.roi_2.height,
        "model_input": "CONCH preprocess target, typically 224x224",
        "color_mode": "RGB",
        "debug_artifacts": debug_artifacts,
    }
    model_metadata = _model_metadata(inference_service)
    slide_dimensions = {
        "width": slide_width,
        "height": slide_height,
    }

    if not roi_quality["is_evaluable"]:
        prediction = {
            "predicted_index": None,
            "predicted_class": "roi_no_evaluable",
            "model_predicted_class": None,
            "confidence": 0.0,
            "probabilities": {},
            "class_mapping": inference_service.class_mapping,
            "decision_threshold": inference_service.confidence_threshold,
        }
        response_payload = {
            "trace_id": trace_id,
            "analyzed_at": analyzed_at,
            "image_id": request.image_id,
            "status": "roi_no_evaluable",
            "class": "roi_no_evaluable",
            "clase": "roi_no_evaluable",
            "confidence": 0.0,
            "probabilities": {},
            "reason": roi_quality["reason"],
            "recommendation": roi_quality["recommendation"],
            "roi_1": roi_1_payload,
            "roi_2": roi_2_payload,
            "prediction": prediction,
            "patch_size": {
                **patch_metadata,
            },
            "patch_metadata": patch_metadata,
            "slide_dimensions": slide_dimensions,
            "roi_quality": roi_quality,
            "debug_artifacts": debug_artifacts,
            "model": model_metadata,
            "warning": EDUCATIONAL_WARNING,
        }

        append_audit_event(
            {
                "event": "histopathology_analyze_roi_not_evaluable",
                "trace_id": trace_id,
                "timestamp": analyzed_at,
                "image_id": request.image_id,
                "image_filename": image.filename,
                "user_id": getattr(current_user, "id", None),
                "status": response_payload["status"],
                "reason": response_payload["reason"],
                "recommendation": response_payload["recommendation"],
                "roi_1": roi_1_payload,
                "roi_2": roi_2_payload,
                "patch_metadata": patch_metadata,
                "slide_dimensions": slide_dimensions,
                "roi_quality": roi_quality,
                "debug_artifacts": debug_artifacts,
                "prediction": prediction,
                "model": model_metadata,
                "warning": EDUCATIONAL_WARNING,
            }
        )

        try:
            _save_histopathology_session(db, getattr(current_user, "id", None), request.image_id, response_payload)
        except Exception:
            pass
        return response_payload

    raw_prediction = inference_service.predict_patch(patch_rgb)
    status = "clasificado"
    predicted_class = raw_prediction["predicted_class"]
    reason = None
    recommendation = None
    prediction = raw_prediction

    if raw_prediction["predicted_class"] == "estroma":
        status = "roi_no_evaluable"
        predicted_class = "roi_no_evaluable"
        reason = (
            "ROI no evaluable: el clasificador 3-class detecto predominio de "
            "patron estromal."
        )
        recommendation = (
            "Seleccione otra ROI con mayor celularidad tumoral o registre esta "
            "region como estroma/no evaluable."
        )
        prediction = {
            **raw_prediction,
            "predicted_class": "roi_no_evaluable",
            "model_predicted_class": raw_prediction["predicted_class"],
        }

    if status == "clasificado" and raw_prediction["confidence"] < inference_service.confidence_threshold:
        status = "resultado_incierto"
        predicted_class = "incierto"
        reason = (
            "Ninguna clase supera el umbral de confianza configurado "
            f"({inference_service.confidence_threshold:.2f})."
        )
        recommendation = (
            "Seleccione una ROI con mayor densidad celular y menos fondo, estroma "
            "o artefactos; si persiste, registre el resultado como incierto."
        )
        prediction = {
            **raw_prediction,
            "predicted_class": "incierto",
            "model_predicted_class": raw_prediction["predicted_class"],
        }

    response_payload = {
        "trace_id": trace_id,
        "analyzed_at": analyzed_at,
        "image_id": request.image_id,
        "status": status,
        "class": predicted_class,
        "clase": predicted_class,
        "confidence": raw_prediction["confidence"],
        "probabilities": raw_prediction["probabilities"],
        "reason": reason,
        "recommendation": recommendation,
        "roi_1": roi_1_payload,
        "roi_2": roi_2_payload,
        "prediction": prediction,
        "patch_size": {
            **patch_metadata,
        },
        "patch_metadata": patch_metadata,
        "slide_dimensions": slide_dimensions,
        "roi_quality": roi_quality,
        "debug_artifacts": debug_artifacts,
        "model": model_metadata,
        "warning": EDUCATIONAL_WARNING,
    }

    append_audit_event(
        {
            "event": "histopathology_analyze_succeeded",
            "trace_id": trace_id,
            "timestamp": analyzed_at,
            "image_id": request.image_id,
            "image_filename": image.filename,
            "user_id": getattr(current_user, "id", None),
            "status": status,
            "reason": reason,
            "recommendation": recommendation,
            "roi_1": roi_1_payload,
            "roi_2": roi_2_payload,
            "patch_metadata": patch_metadata,
            "slide_dimensions": slide_dimensions,
            "roi_quality": roi_quality,
            "debug_artifacts": debug_artifacts,
            "prediction": prediction,
            "model": model_metadata,
            "warning": EDUCATIONAL_WARNING,
        }
    )

    try:
        _save_histopathology_session(db, getattr(current_user, "id", None), request.image_id, response_payload)
    except Exception:
        pass
    return response_payload


@router.post("/scan-roi")
async def scan_roi_heatmap(
    request: HistopathologyScanRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    trace_id = str(uuid4())
    analyzed_at = _utc_now()
    roi_payload = _dump_schema(request.roi)
    image = (
        db.query(MedicalImage)
        .filter(MedicalImage.id == request.image_id, MedicalImage.is_active == True)
        .first()
    )

    if not image:
        append_audit_event(
            {
                "event": "histopathology_scan_failed",
                "trace_id": trace_id,
                "timestamp": analyzed_at,
                "image_id": request.image_id,
                "user_id": getattr(current_user, "id", None),
                "roi": roi_payload,
                "error_type": "image_not_found",
                "detail": "Imagen no encontrada",
            }
        )
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    image_payload = {
        "id": image.id,
        "filename": image.filename,
        "file_path": image.file_path,
    }

    try:
        return _execute_heatmap_scan(
            request=request,
            image_payload=image_payload,
            user_id=getattr(current_user, "id", None),
            trace_id=trace_id,
            analyzed_at=analyzed_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PatchExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelUnavailableError as exc:
        append_audit_event(
            {
                "event": "histopathology_scan_failed",
                "trace_id": trace_id,
                "timestamp": analyzed_at,
                "image_id": request.image_id,
                "user_id": getattr(current_user, "id", None),
                "roi": roi_payload,
                "error_type": "model_unavailable",
                "detail": str(exc),
            }
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/heatmaps/jobs")
async def create_heatmap_scan_job(
    scan_request: HistopathologyScanRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    effective_role = normalize_role(
        getattr(current_user, "role", None) or http_request.headers.get("x-asofamech-role")
    )
    max_allowed_tiles = max_tiles_for_role(effective_role)
    if scan_request.max_tiles > max_allowed_tiles:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Tu rol permite hasta {max_allowed_tiles} tiles por heatmap. "
                "Reduce el area ROI o pide a un docente preparar el mapa."
            ),
        )

    max_allowed_tile_size = max_tile_size_for_role(effective_role)
    if scan_request.tile_size > max_allowed_tile_size or scan_request.stride > max_allowed_tile_size:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Tu rol permite tile/stride de hasta {max_allowed_tile_size}px para heatmaps."
            ),
        )

    client_id = http_request.headers.get("x-asofamech-client-id")
    rate_key = heatmap_rate_limit_key(
        user_id=getattr(current_user, "id", None),
        role=effective_role,
        client_id=client_id,
    )
    allowed, retry_after, limit, window_seconds = check_heatmap_rate_limit(
        rate_key,
        effective_role,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Demasiadas solicitudes de heatmap. Limite: {limit} cada "
                f"{window_seconds} segundos."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    image = (
        db.query(MedicalImage)
        .filter(MedicalImage.id == scan_request.image_id, MedicalImage.is_active == True)
        .first()
    )
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    trace_id = str(uuid4())
    image_payload = {
        "id": image.id,
        "filename": image.filename,
        "file_path": image.file_path,
    }
    request_payload = {
        "image_id": scan_request.image_id,
        "roi": _dump_schema(scan_request.roi),
        "tile_size": scan_request.tile_size,
        "stride": scan_request.stride,
        "max_tiles": scan_request.max_tiles,
        "requested_by_role": effective_role,
        "client_id": client_id,
        "educational": {
            "label": scan_request.educational_label or "",
            "note": scan_request.educational_note or "",
            "type": scan_request.educational_type or "referencia",
        },
    }
    job = create_heatmap_job(
        {
            "trace_id": trace_id,
            "request": request_payload,
        }
    )
    background_tasks.add_task(
        _run_heatmap_job,
        job_id=job["job_id"],
        request=scan_request,
        image_payload=image_payload,
        user_id=getattr(current_user, "id", None),
        trace_id=trace_id,
    )

    return job


@router.get("/heatmaps/jobs/{job_id}")
async def get_heatmap_scan_job(
    job_id: str,
    current_user=Depends(get_current_user),
):
    job = get_heatmap_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job de heatmap no encontrado")
    return job


@router.get("/heatmaps/image/{image_id}/latest")
async def get_latest_heatmap(
    image_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    image = (
        db.query(MedicalImage)
        .filter(MedicalImage.id == image_id, MedicalImage.is_active == True)
        .first()
    )
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    heatmap = load_latest_heatmap_for_image(image_id)
    if not heatmap:
        raise HTTPException(status_code=404, detail="No hay heatmap guardado para esta imagen")

    return heatmap


@router.get("/heatmaps/image/{image_id}/history")
async def get_heatmap_history(
    image_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    image = (
        db.query(MedicalImage)
        .filter(MedicalImage.id == image_id, MedicalImage.is_active == True)
        .first()
    )
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    items = load_heatmap_history_for_image(image_id, limit=limit)
    return {
        "image_id": image_id,
        "count": len(items),
        "items": items,
    }


@router.get("/heatmaps/{trace_id}")
async def get_heatmap_by_trace(
    trace_id: str,
    current_user=Depends(get_current_user),
):
    heatmap = load_heatmap_by_trace(trace_id)
    if not heatmap:
        raise HTTPException(status_code=404, detail="Heatmap no encontrado")

    return heatmap


@router.get("/sessions")
async def list_sessions(
    image_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(HistopathologySession).filter(
        HistopathologySession.user_id == current_user.id,
        HistopathologySession.is_active == True,
    )
    if image_id is not None:
        query = query.filter(HistopathologySession.image_id == image_id)
    sessions = (
        query.order_by(HistopathologySession.analyzed_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "image_id": image_id,
        "count": len(sessions),
        "items": [_session_to_summary(s) for s in sessions],
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    session = (
        db.query(HistopathologySession)
        .filter(
            HistopathologySession.id == session_id,
            HistopathologySession.user_id == current_user.id,
            HistopathologySession.is_active == True,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    return _session_to_detail(session)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    session = (
        db.query(HistopathologySession)
        .filter(
            HistopathologySession.id == session_id,
            HistopathologySession.user_id == current_user.id,
            HistopathologySession.is_active == True,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    session.is_active = False
    db.commit()


@router.patch("/heatmaps/{trace_id}/educational")
async def update_heatmap_educational_metadata_endpoint(
    trace_id: str,
    metadata: HeatmapEducationalMetadataUpdate,
    current_user=Depends(get_current_user),
):
    _require_heatmap_manager(current_user)
    updated = update_heatmap_educational_metadata(
        trace_id,
        {
            "educational_label": metadata.educational_label,
            "educational_note": metadata.educational_note,
            "educational_type": metadata.educational_type,
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Heatmap no encontrado")

    return updated


@router.post("/sessions/{session_id}/correction")
async def upsert_session_correction(
    session_id: int,
    body: CorrectionCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_docente_or_admin(current_user)
    if body.docente_label not in DOCENTE_LABEL_CHOICES:
        raise HTTPException(
            status_code=422,
            detail=f"docente_label debe ser uno de: {', '.join(DOCENTE_LABEL_CHOICES)}",
        )
    session = (
        db.query(HistopathologySession)
        .filter(HistopathologySession.id == session_id, HistopathologySession.is_active == True)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")

    correction = (
        db.query(HistopathologyCorrection)
        .filter(HistopathologyCorrection.session_id == session_id)
        .first()
    )
    if correction:
        correction.docente_label = body.docente_label
        correction.docente_note = body.docente_note
        correction.include_in_dataset = body.include_in_dataset
        correction.corrected_at = datetime.now(timezone.utc).replace(tzinfo=None)
        correction.docente_user_id = current_user.id
    else:
        correction = HistopathologyCorrection(
            session_id=session_id,
            trace_id=session.trace_id,
            image_id=session.image_id,
            docente_user_id=current_user.id,
            docente_label=body.docente_label,
            docente_note=body.docente_note,
            include_in_dataset=body.include_in_dataset,
            corrected_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(correction)
    db.commit()
    db.refresh(correction)
    return _correction_to_out(correction)


@router.delete("/sessions/{session_id}/correction", status_code=204)
async def delete_session_correction(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_docente_or_admin(current_user)
    correction = (
        db.query(HistopathologyCorrection)
        .filter(HistopathologyCorrection.session_id == session_id)
        .first()
    )
    if not correction:
        raise HTTPException(status_code=404, detail="Correccion no encontrada")
    db.delete(correction)
    db.commit()


@router.get("/dataset/manifest")
async def get_dataset_manifest(
    image_id: int | None = Query(None),
    include_uncertain: bool = Query(False),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_docente_or_admin(current_user)
    query = (
        db.query(HistopathologyCorrection, HistopathologySession, MedicalImage)
        .join(HistopathologySession, HistopathologyCorrection.session_id == HistopathologySession.id)
        .join(MedicalImage, HistopathologySession.image_id == MedicalImage.id)
        .filter(
            HistopathologyCorrection.include_in_dataset == True,
            HistopathologySession.is_active == True,
        )
    )
    if image_id is not None:
        query = query.filter(HistopathologySession.image_id == image_id)
    if not include_uncertain:
        query = query.filter(HistopathologySession.clase != "incierto")

    rows = query.order_by(HistopathologyCorrection.corrected_at.desc()).all()
    items = [
        {
            "trace_id": correction.trace_id,
            "session_id": session.id,
            "image_id": image.id,
            "image_filename": image.filename,
            "roi_1": session.roi_1,
            "roi_2": session.roi_2,
            "model_clase": session.clase,
            "model_confidence": session.confidence,
            "model_probabilities": session.probabilities,
            "docente_label": correction.docente_label,
            "docente_note": correction.docente_note,
            "corrected_at": correction.corrected_at.isoformat() if correction.corrected_at else None,
            "analyzed_at": session.analyzed_at.isoformat() if session.analyzed_at else None,
        }
        for correction, session, image in rows
    ]
    return {
        "count": len(items),
        "generated_at": _utc_now(),
        "items": items,
    }


@router.get("/review/sessions")
async def review_sessions(
    image_id: int | None = Query(None),
    docente_label: str | None = Query(None),
    include_in_dataset: bool | None = Query(None),
    corrected: bool | None = Query(None),
    model_clase: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_docente_or_admin(current_user)
    query = (
        db.query(HistopathologySession)
        .outerjoin(HistopathologyCorrection, HistopathologyCorrection.session_id == HistopathologySession.id)
        .filter(HistopathologySession.is_active == True)
    )
    if image_id is not None:
        query = query.filter(HistopathologySession.image_id == image_id)
    if model_clase is not None:
        query = query.filter(HistopathologySession.clase == model_clase)
    if corrected is True:
        query = query.filter(HistopathologyCorrection.id.isnot(None))
    elif corrected is False:
        query = query.filter(HistopathologyCorrection.id.is_(None))
    if docente_label is not None:
        query = query.filter(HistopathologyCorrection.docente_label == docente_label)
    if include_in_dataset is not None:
        query = query.filter(HistopathologyCorrection.include_in_dataset == include_in_dataset)

    sessions = (
        query.order_by(HistopathologySession.analyzed_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(sessions),
        "items": [_session_to_detail(s) for s in sessions],
    }
