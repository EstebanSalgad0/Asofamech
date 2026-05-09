import argparse
import json
import math
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PIL import Image

from app.histopathology.ml.classifier_head import BinaryClassifierHead
from app.histopathology.roi_quality import QualityThresholds, evaluate_roi_quality
from histopathology_offline.manifest_dataset import PatchManifestRow, read_manifest


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Pipeline completo: manifest → QC → modelo binario. "
            "Las ROI bloqueadas por QC se cuentan como roi_no_evaluable; "
            "las métricas del modelo se calculan solo sobre las ROI que pasan el filtro."
        )
    )
    parser.add_argument("--manifest", required=True, help="Manifest CSV de parches.")
    parser.add_argument(
        "--embeddings",
        default="artifacts/histopathology/embeddings-hard-negative/manifest_test_embeddings.pt",
        help="Embeddings CONCH pre-extraídos alineados con las filas del manifest.",
    )
    parser.add_argument(
        "--checkpoint",
        default="artifacts/histopathology/checkpoints/binary_head_hard_negative.pt",
        help="Checkpoint del clasificador binario entrenado.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/histopathology/reports/model_qc_eval.json",
        help="Ruta del reporte JSON de salida.",
    )
    parser.add_argument(
        "--root-dir",
        default=".",
        help="Directorio base para resolver rutas relativas de parches.",
    )
    parser.add_argument(
        "--splits",
        default="test",
        help="Splits a evaluar, separados por coma, o 'all'. Por defecto: test.",
    )
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    # Umbrales QC
    parser.add_argument("--max-white-fraction", type=float, default=0.45)
    parser.add_argument("--min-tissue-fraction", type=float, default=0.40)
    parser.add_argument("--min-nuclear-fraction", type=float, default=0.035)
    parser.add_argument("--max-dominant-stroma-fraction", type=float, default=0.55)
    parser.add_argument("--max-stroma-fraction-when-low-nuclear", type=float, default=0.65)
    parser.add_argument("--low-nuclear-for-stroma-fraction", type=float, default=0.12)
    parser.add_argument(
        "--include-records",
        action="store_true",
        help="Incluir resultado por parche en el reporte JSON.",
    )
    return parser.parse_args()


def load_runtime_dependencies():
    try:
        import torch
        from sklearn.metrics import (
            accuracy_score,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise SystemExit(
            "PyTorch y scikit-learn son requeridos. "
            "Instala backend/requirements-histopathology.txt primero."
        ) from exc

    metrics = {
        "accuracy_score": accuracy_score,
        "confusion_matrix": confusion_matrix,
        "f1_score": f1_score,
        "precision_score": precision_score,
        "recall_score": recall_score,
        "roc_auc_score": roc_auc_score,
    }
    return torch, DataLoader, TensorDataset, metrics


def resolve_device(torch, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA solicitado pero torch.cuda.is_available() es False.")
    return requested


def selected_splits(raw: str) -> set[str] | None:
    if raw.strip().lower() == "all":
        return None
    return {s.strip() for s in raw.split(",") if s.strip()}


def resolve_patch_path(row: PatchManifestRow, root_dir: Path) -> Path:
    path = Path(row.path)
    if path.is_absolute():
        return path
    return root_dir / path


def apply_qc(
    rows: list[PatchManifestRow],
    root_dir: Path,
    thresholds: QualityThresholds,
) -> tuple[list[dict], list[int]]:
    """
    Evalúa el filtro QC para cada fila del manifest.

    Retorna:
      qc_results: lista de dicts con resultado QC por parche.
      evaluable_indices: índices (en `rows`) de los parches que pasaron QC.
    """
    qc_results = []
    evaluable_indices = []

    for i, row in enumerate(rows):
        patch_path = resolve_patch_path(row, root_dir)
        if not patch_path.exists():
            qc_results.append(
                {
                    "patch_id": row.patch_id,
                    "label": int(row.label),
                    "hard_negative_type": row.hard_negative_type or "",
                    "blocked": True,
                    "reason": "file_not_found",
                    "qc_metrics": None,
                    "qc_checks": None,
                }
            )
            continue

        with Image.open(patch_path) as img:
            quality = evaluate_roi_quality(img.convert("RGB"), thresholds=thresholds)

        is_evaluable = bool(quality["is_evaluable"])
        qc_results.append(
            {
                "patch_id": row.patch_id,
                "label": int(row.label),
                "hard_negative_type": row.hard_negative_type or "",
                "blocked": not is_evaluable,
                "reason": quality["reason"],
                "qc_metrics": quality["metrics"],
                "qc_checks": quality["checks"],
            }
        )
        if is_evaluable:
            evaluable_indices.append(i)

    return qc_results, evaluable_indices


def predict(torch, head, loader, device):
    head.eval()
    y_true, y_pred, y_score = [], [], []
    with torch.inference_mode():
        for features, labels in loader:
            logits = head(features.to(device))
            probabilities = torch.softmax(logits, dim=1)
            preds = torch.argmax(probabilities, dim=1).cpu()
            y_true.extend(labels.tolist())
            y_pred.extend(preds.tolist())
            y_score.extend(probabilities[:, 1].cpu().tolist())
    return y_true, y_pred, y_score


def _specificity(metrics_api, y_true, y_pred) -> float:
    matrix = metrics_api["confusion_matrix"](y_true, y_pred, labels=[0, 1])
    tn, fp = matrix[0][0], matrix[0][1]
    denominator = tn + fp
    return float(tn / denominator) if denominator > 0 else 0.0


def summarize_metrics(metrics_api, y_true, y_pred, y_score) -> dict:
    roc_auc = None
    try:
        val = float(metrics_api["roc_auc_score"](y_true, y_score))
        if math.isfinite(val):
            roc_auc = val
    except ValueError:
        pass

    return {
        "accuracy": float(metrics_api["accuracy_score"](y_true, y_pred)),
        "precision": float(metrics_api["precision_score"](y_true, y_pred, pos_label=1, zero_division=0)),
        "sensitivity_recall": float(metrics_api["recall_score"](y_true, y_pred, pos_label=1, zero_division=0)),
        "specificity": _specificity(metrics_api, y_true, y_pred),
        "f1_score": float(metrics_api["f1_score"](y_true, y_pred, pos_label=1, zero_division=0)),
        "roc_auc": roc_auc,
        "confusion_matrix": metrics_api["confusion_matrix"](y_true, y_pred, labels=[0, 1]).tolist(),
        "sample_count": len(y_true),
    }


def hard_negative_breakdown(eval_rows: list[PatchManifestRow], y_true, y_pred) -> dict:
    """
    Tasa de falsos positivos por tipo de hard negative, solo sobre ROI evaluables.
    Responde: ¿Stage 2 + QC reduce FP en stroma sin destruir sensibilidad tumoral?
    """
    buckets: dict = {}
    for row, true_label, pred_label in zip(eval_rows, y_true, y_pred):
        if int(true_label) != 0:
            continue
        key = row.hard_negative_type or "negative_unspecified"
        bucket = buckets.setdefault(key, {"count": 0, "false_positives": 0})
        bucket["count"] += 1
        if int(pred_label) == 1:
            bucket["false_positives"] += 1
    for bucket in buckets.values():
        count = max(bucket["count"], 1)
        bucket["false_positive_rate"] = bucket["false_positives"] / count
    return buckets


def compute_qc_summary(qc_results: list[dict]) -> dict:
    summary = {
        "total": len(qc_results),
        "evaluable": 0,
        "blocked": 0,
        "blocked_rate": 0.0,
        "by_label": {
            "positive": {"total": 0, "blocked": 0, "blocked_rate": 0.0},
            "negative": {"total": 0, "blocked": 0, "blocked_rate": 0.0},
        },
        "by_hard_negative_type": {},
        "blocked_reasons": {},
        "sensitivity_impact": {
            "true_positives_blocked": 0,
            "total_positives": 0,
            "fraction_positives_lost": 0.0,
        },
    }

    for r in qc_results:
        label_name = "positive" if r["label"] == 1 else "negative"
        summary["by_label"][label_name]["total"] += 1

        if r["blocked"]:
            summary["blocked"] += 1
            summary["by_label"][label_name]["blocked"] += 1
            reason = r["reason"] or "roi_no_evaluable"
            summary["blocked_reasons"][reason] = summary["blocked_reasons"].get(reason, 0) + 1
        else:
            summary["evaluable"] += 1

        if r["label"] == 0:
            hn_type = r["hard_negative_type"] or "negative_unspecified"
            hn_bucket = summary["by_hard_negative_type"].setdefault(
                hn_type, {"total": 0, "blocked": 0, "blocked_rate": 0.0}
            )
            hn_bucket["total"] += 1
            if r["blocked"]:
                hn_bucket["blocked"] += 1

    total = max(1, summary["total"])
    summary["blocked_rate"] = summary["blocked"] / total

    for label_bucket in summary["by_label"].values():
        t = max(1, label_bucket["total"])
        label_bucket["blocked_rate"] = label_bucket["blocked"] / t

    for hn_bucket in summary["by_hard_negative_type"].values():
        t = max(1, hn_bucket["total"])
        hn_bucket["blocked_rate"] = hn_bucket["blocked"] / t

    total_pos = summary["by_label"]["positive"]["total"]
    blocked_pos = summary["by_label"]["positive"]["blocked"]
    summary["sensitivity_impact"]["total_positives"] = total_pos
    summary["sensitivity_impact"]["true_positives_blocked"] = blocked_pos
    summary["sensitivity_impact"]["fraction_positives_lost"] = blocked_pos / max(1, total_pos)

    return summary


def main() -> None:
    args = parse_args()
    torch, DataLoader, TensorDataset, metrics_api = load_runtime_dependencies()
    device = resolve_device(torch, args.device)

    manifest_path = Path(args.manifest)
    root_dir = Path(args.root_dir)
    splits = selected_splits(args.splits)

    thresholds = QualityThresholds(
        max_white_fraction=args.max_white_fraction,
        min_tissue_fraction=args.min_tissue_fraction,
        min_nuclear_fraction=args.min_nuclear_fraction,
        max_dominant_stroma_fraction=args.max_dominant_stroma_fraction,
        max_stroma_fraction_when_low_nuclear=args.max_stroma_fraction_when_low_nuclear,
        low_nuclear_for_stroma_fraction=args.low_nuclear_for_stroma_fraction,
    )

    all_rows = read_manifest(manifest_path)
    rows = [r for r in all_rows if splits is None or r.split in splits]
    if not rows:
        raise SystemExit("Ninguna fila del manifest corresponde al split solicitado.")
    print(f"[histopathology] manifest_rows={len(rows)} splits={sorted(splits) if splits else 'all'}")

    # Cargar embeddings pre-extraídos alineados con el manifest
    embeddings_path = Path(args.embeddings)
    if not embeddings_path.exists():
        raise SystemExit(f"Archivo de embeddings no encontrado: {embeddings_path}")
    payload = torch.load(embeddings_path, map_location="cpu")
    x_all = payload["x"].float()
    y_all = payload["y"].long()
    if len(x_all) != len(rows):
        raise SystemExit(
            f"Desalineación: {len(x_all)} embeddings vs {len(rows)} filas del manifest. "
            "Re-extrae los embeddings para este split."
        )

    # Cargar checkpoint del modelo
    ckpt_path = Path(args.checkpoint)
    if not ckpt_path.exists():
        raise SystemExit(f"Checkpoint no encontrado: {ckpt_path}")
    checkpoint = torch.load(ckpt_path, map_location=device)
    head = BinaryClassifierHead(int(checkpoint["feature_dim"])).to(device)
    head.load_state_dict(checkpoint["state_dict"])
    print(f"[histopathology] checkpoint={ckpt_path.name} feature_dim={checkpoint['feature_dim']}")

    # ── Paso 1: QC ──────────────────────────────────────────────────────────
    print(f"[histopathology] aplicando QC a {len(rows)} parches...")
    qc_results, evaluable_indices = apply_qc(rows, root_dir, thresholds)
    qc_summary = compute_qc_summary(qc_results)
    print(
        f"[histopathology] qc total={qc_summary['total']} "
        f"evaluable={qc_summary['evaluable']} "
        f"blocked={qc_summary['blocked']} "
        f"blocked_rate={qc_summary['blocked_rate']:.3f} "
        f"positivos_perdidos={qc_summary['sensitivity_impact']['fraction_positives_lost']:.3f}"
    )

    # ── Paso 2: Inferencia sobre ROI evaluables ──────────────────────────────
    model_metrics = None
    hn_breakdown: dict = {}

    if evaluable_indices:
        eval_x = x_all[evaluable_indices]
        eval_y = y_all[evaluable_indices]
        eval_rows = [rows[i] for i in evaluable_indices]

        loader = DataLoader(
            TensorDataset(eval_x, eval_y), batch_size=args.batch_size, shuffle=False
        )
        y_true, y_pred, y_score = predict(torch, head, loader, device)
        model_metrics = summarize_metrics(metrics_api, y_true, y_pred, y_score)
        hn_breakdown = hard_negative_breakdown(eval_rows, y_true, y_pred)

        print(
            f"[histopathology] modelo evaluado={len(y_true)} "
            f"sensibilidad={model_metrics['sensitivity_recall']:.3f} "
            f"especificidad={model_metrics['specificity']:.3f} "
            f"f1={model_metrics['f1_score']:.3f} "
            f"roc_auc={model_metrics.get('roc_auc')}"
        )
        stroma_bucket = hn_breakdown.get("stroma") or hn_breakdown.get("stroma_low_cellularity")
        if stroma_bucket:
            print(
                f"[histopathology] FP en stroma (evaluable): "
                f"count={stroma_bucket['count']} "
                f"false_positives={stroma_bucket['false_positives']} "
                f"fp_rate={stroma_bucket['false_positive_rate']:.3f}"
            )
    else:
        print("[histopathology] advertencia: ningún parche evaluable después del QC — modelo no ejecutado.")

    # ── Reporte final ────────────────────────────────────────────────────────
    report = {
        "manifest": str(manifest_path),
        "embeddings": str(embeddings_path),
        "checkpoint": str(ckpt_path),
        "splits": "all" if splits is None else sorted(splits),
        "thresholds": thresholds.__dict__,
        "qc": qc_summary,
        "model": model_metrics,
        "hard_negative_breakdown_evaluable": hn_breakdown,
        "records": (
            [
                {
                    "patch_id": r["patch_id"],
                    "label": r["label"],
                    "hard_negative_type": r["hard_negative_type"],
                    "blocked": r["blocked"],
                    "reason": r["reason"],
                }
                for r in qc_results
            ]
            if args.include_records
            else None
        ),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[histopathology] reporte guardado: {output}")


if __name__ == "__main__":
    main()
