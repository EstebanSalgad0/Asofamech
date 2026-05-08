import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..histopathology.audit_log import append_audit_event, get_audit_log_path
from ..histopathology.ml.conch_feature_extractor import ModelUnavailableError
from ..histopathology.ml.inference_service import get_inference_service
from ..histopathology.patch_extractor import OpenSlidePatchExtractor, PatchExtractionError
from ..histopathology.roi import validate_roi_pair
from ..histopathology.schemas import HistopathologyAnalyzeRequest
from ..models import MedicalImage
from .medical_images import get_current_user


router = APIRouter(prefix="/api/histopathology", tags=["histopathology"])

EDUCATIONAL_WARNING = (
    "Modulo educativo no diagnostico. La prediccion esta limitada a la tarea binaria "
    "PCam: metastasico vs no metastasico en patches de ganglio linfatico."
)


def _dump_schema(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
            "task": "binary_pcam_metastatic_vs_non_metastatic",
            "backbone": "CONCH frozen",
            "classifier": "binary linear head over CONCH embeddings",
            "checkpoint_configured": checkpoint_configured,
            "classifier_checkpoint": checkpoint_path,
            "checkpoint_ref": inference_service.checkpoint_ref,
            "device": inference_service.device,
            "feature_dim": inference_service.feature_dim,
            "labels": inference_service.labels,
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

    try:
        inference_service = get_inference_service()
        prediction = inference_service.predict_patch(patch_rgb)
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
                "error_type": "model_unavailable",
                "detail": str(exc),
            }
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    patch_metadata = {
        "extracted_width": patch_rgb.width,
        "extracted_height": patch_rgb.height,
        "roi_2_width": request.roi_2.width,
        "roi_2_height": request.roi_2.height,
        "model_input": "CONCH preprocess target, typically 224x224",
        "color_mode": "RGB",
    }
    model_metadata = {
        "task": "binary_pcam_metastatic_vs_non_metastatic",
        "backbone": "CONCH frozen",
        "classifier": "binary linear head over CONCH embeddings",
        "checkpoint_ref": inference_service.checkpoint_ref,
        "classifier_checkpoint": inference_service.classifier_path,
        "device": inference_service.device,
        "feature_dim": inference_service.feature_dim,
        "training_mode": inference_service.training_mode,
        "validation": inference_service.validation,
    }
    slide_dimensions = {
        "width": slide_width,
        "height": slide_height,
    }

    response_payload = {
        "trace_id": trace_id,
        "analyzed_at": analyzed_at,
        "image_id": request.image_id,
        "roi_1": roi_1_payload,
        "roi_2": roi_2_payload,
        "prediction": prediction,
        "patch_size": {
            **patch_metadata,
        },
        "patch_metadata": patch_metadata,
        "slide_dimensions": slide_dimensions,
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
            "roi_1": roi_1_payload,
            "roi_2": roi_2_payload,
            "patch_metadata": patch_metadata,
            "slide_dimensions": slide_dimensions,
            "prediction": prediction,
            "model": model_metadata,
            "warning": EDUCATIONAL_WARNING,
        }
    )

    return response_payload
