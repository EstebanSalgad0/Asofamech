from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.histopathology.ml.classifier_head import TriClassifierHead, TriMLPClassifierHead
from histopathology_offline.build_camelyon17_official_manifest import (
    TumorPolygon,
    bbox_intersects,
    load_polygons,
    load_targets_csv,
    point_in_polygon,
)
from histopathology_offline.manifest_dataset import PatchManifestRow


OUTCOMES = ("true_positive", "false_positive", "false_negative", "true_negative", "unknown")


@dataclass(frozen=True)
class OfficialTruth:
    label: int | None
    source: str
    xml_tumor_match: bool
    target: int | None = None


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a trained histopathology head against CAMELYON17 ASAP XML "
            "annotations using manifest coordinates and precomputed CONCH embeddings."
        )
    )
    parser.add_argument("--manifest", required=True, help="Patch manifest used to extract embeddings.")
    parser.add_argument("--embeddings-dir", required=True, help="Directory with manifest_{split}_embeddings.pt files.")
    parser.add_argument("--checkpoint", required=True, help="Trained classifier checkpoint.")
    parser.add_argument("--annotations-dir", default="data/camelyon17/annotations")
    parser.add_argument("--targets-csv", default="data/camelyon17/stages.csv")
    parser.add_argument("--output-dir", default="artifacts/histopathology/evaluation/camelyon17_xml")
    parser.add_argument("--splits", default="test", help="Comma-separated splits to evaluate.")
    parser.add_argument(
        "--truth-mode",
        default="center",
        choices=("center", "intersects"),
        help=(
            "center: a patch is tumor if its center is inside an XML polygon. "
            "intersects: a patch is tumor if its rectangle intersects an XML polygon."
        ),
    )
    parser.add_argument(
        "--tumor-threshold",
        type=float,
        default=0.90,
        help="Classify a patch as predicted tumor when P(metastasico) reaches this threshold.",
    )
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    return parser.parse_args()


def parse_splits(value: str) -> list[str]:
    splits = [item.strip() for item in value.split(",") if item.strip()]
    if not splits:
        raise SystemExit("At least one split is required.")
    return splits


def load_runtime_dependencies():
    try:
        import torch
    except ImportError as exc:
        raise SystemExit("PyTorch is required to evaluate checkpoint predictions.") from exc
    return torch


def resolve_device(torch, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA requested but torch.cuda.is_available() is False.")
    return requested


def normalize_labels(raw: dict[str, Any], num_classes: int) -> dict[str, str]:
    default = {"0": "no_metastasico", "1": "metastasico", "2": "estroma"}
    labels = raw.get("labels") or raw.get("class_names") or {}
    normalized = {**default, **{str(key): str(value) for key, value in labels.items()}}
    return {str(index): normalized[str(index)] for index in range(num_classes)}


def build_head_from_checkpoint(torch, checkpoint: dict[str, Any], device: str):
    state_dict = checkpoint["state_dict"]
    feature_dim = int(checkpoint["feature_dim"])
    num_classes = int(checkpoint.get("num_classes") or state_dict["classifier.weight"].shape[0])
    if num_classes != 3:
        raise SystemExit(f"Only 3-class checkpoints are supported by this evaluator, got {num_classes}.")

    head_type = checkpoint.get("head_type", "linear")
    if head_type == "mlp":
        hyperparameters = checkpoint.get("hyperparameters") or {}
        hidden_dim = int(checkpoint.get("head_hidden_dim") or hyperparameters.get("hidden_dim") or 128)
        dropout = float(checkpoint.get("head_dropout") or hyperparameters.get("dropout") or 0.20)
        head = TriMLPClassifierHead(feature_dim, hidden_dim=hidden_dim, dropout=dropout)
    else:
        head = TriClassifierHead(feature_dim)

    head.load_state_dict(state_dict)
    head.to(device)
    head.eval()
    return head, normalize_labels(checkpoint, num_classes)


def point_inside_rect(point: tuple[float, float], rect: tuple[int, int, int, int]) -> bool:
    x, y = point
    x1, y1, x2, y2 = rect
    return x1 <= x <= x2 and y1 <= y <= y2


def orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
    return (
        min(a[0], c[0]) <= b[0] <= max(a[0], c[0])
        and min(a[1], c[1]) <= b[1] <= max(a[1], c[1])
    )


def segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)

    if o1 == 0 and on_segment(a, c, b):
        return True
    if o2 == 0 and on_segment(a, d, b):
        return True
    if o3 == 0 and on_segment(c, a, d):
        return True
    if o4 == 0 and on_segment(c, b, d):
        return True
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def rect_intersects_polygon(x: int, y: int, width: int, height: int, polygon: TumorPolygon) -> bool:
    rect = (x, y, x + width, y + height)
    if not bbox_intersects(rect, polygon.bbox):
        return False

    rect_points = [
        (float(rect[0]), float(rect[1])),
        (float(rect[2]), float(rect[1])),
        (float(rect[2]), float(rect[3])),
        (float(rect[0]), float(rect[3])),
    ]
    if any(point_in_polygon(px, py, polygon.points) for px, py in rect_points):
        return True
    if any(point_inside_rect(point, rect) for point in polygon.points):
        return True

    rect_edges = list(zip(rect_points, rect_points[1:] + rect_points[:1]))
    polygon_points = list(polygon.points)
    polygon_edges = list(zip(polygon_points, polygon_points[1:] + polygon_points[:1]))
    return any(
        segments_intersect(edge_a[0], edge_a[1], edge_b[0], edge_b[1])
        for edge_a in rect_edges
        for edge_b in polygon_edges
    )


def patch_matches_xml_tumor(
    row: PatchManifestRow,
    polygons: list[TumorPolygon],
    truth_mode: str,
) -> bool:
    if not polygons:
        return False
    if truth_mode == "center":
        center_x = row.x + row.width / 2
        center_y = row.y + row.height / 2
        return any(point_in_polygon(center_x, center_y, polygon.points) for polygon in polygons)
    return any(rect_intersects_polygon(row.x, row.y, row.width, row.height, polygon) for polygon in polygons)


def official_truth_for_row(
    row: PatchManifestRow,
    polygons_by_slide: dict[str, list[TumorPolygon]],
    targets: dict[str, int],
    truth_mode: str,
) -> OfficialTruth:
    target = targets.get(row.slide_id)
    polygons = polygons_by_slide.get(row.slide_id, [])
    xml_match = patch_matches_xml_tumor(row, polygons, truth_mode)

    if xml_match:
        return OfficialTruth(label=1, source="xml_tumor_polygon", xml_tumor_match=True, target=target)
    if polygons:
        return OfficialTruth(label=0, source="outside_xml_tumor_polygon", xml_tumor_match=False, target=target)
    if target == 0:
        return OfficialTruth(label=0, source="negative_slide", xml_tumor_match=False, target=target)
    if target == 1:
        return OfficialTruth(label=None, source="positive_slide_without_xml", xml_tumor_match=False, target=target)
    return OfficialTruth(label=None, source="unknown_unannotated_slide", xml_tumor_match=False, target=target)


def outcome_for_truth_prediction(truth_label: int | None, predicted_tumor: bool) -> str:
    if truth_label is None:
        return "unknown"
    if truth_label == 1 and predicted_tumor:
        return "true_positive"
    if truth_label == 1 and not predicted_tumor:
        return "false_negative"
    if truth_label == 0 and predicted_tumor:
        return "false_positive"
    return "true_negative"


def records_to_rows(records: list[dict[str, Any]]) -> list[PatchManifestRow]:
    return [PatchManifestRow.from_dict(record) for record in records]


def probability_by_label(probabilities, labels: dict[str, str]) -> dict[str, float]:
    return {
        labels[str(index)]: float(probabilities[index].item())
        for index in range(len(labels))
    }


def evaluate_split(
    *,
    torch,
    head,
    labels: dict[str, str],
    embeddings_path: Path,
    polygons_by_slide: dict[str, list[TumorPolygon]],
    targets: dict[str, int],
    truth_mode: str,
    tumor_threshold: float,
    batch_size: int,
    device: str,
) -> list[dict[str, Any]]:
    payload = torch.load(embeddings_path, map_location="cpu")
    features = payload["x"]
    rows = records_to_rows(payload["records"])
    if len(features) != len(rows):
        raise SystemExit(f"{embeddings_path}: {len(features)} embeddings vs {len(rows)} records.")

    evaluated: list[dict[str, Any]] = []
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            end = min(start + batch_size, len(rows))
            batch_x = features[start:end].to(device)
            logits = head(batch_x)
            batch_probs = torch.softmax(logits, dim=1).cpu()
            batch_pred = torch.argmax(batch_probs, dim=1).cpu()

            for offset, row in enumerate(rows[start:end]):
                probabilities = probability_by_label(batch_probs[offset], labels)
                predicted_index = int(batch_pred[offset].item())
                predicted_class = labels[str(predicted_index)]
                p_tumor = float(probabilities.get("metastasico", 0.0))
                predicted_tumor = predicted_class == "metastasico" and p_tumor >= tumor_threshold
                truth = official_truth_for_row(row, polygons_by_slide, targets, truth_mode)
                outcome = outcome_for_truth_prediction(truth.label, predicted_tumor)
                confidence = float(batch_probs[offset][predicted_index].item())

                evaluated.append(
                    {
                        "patch_id": row.patch_id,
                        "split": row.split,
                        "slide_id": row.slide_id,
                        "x": row.x,
                        "y": row.y,
                        "width": row.width,
                        "height": row.height,
                        "truth_label": "" if truth.label is None else truth.label,
                        "truth_source": truth.source,
                        "xml_tumor_match": truth.xml_tumor_match,
                        "target": "" if truth.target is None else truth.target,
                        "predicted_tumor": predicted_tumor,
                        "predicted_index": predicted_index,
                        "predicted_class": predicted_class,
                        "confidence": confidence,
                        "p_no_metastasico": float(probabilities.get("no_metastasico", 0.0)),
                        "p_metastasico": p_tumor,
                        "p_estroma": float(probabilities.get("estroma", 0.0)),
                        "outcome": outcome,
                        "label_source": row.label_source,
                        "annotation_status": row.annotation_status,
                        "hard_negative_type": row.hard_negative_type,
                        "path": row.path,
                    }
                )
    return evaluated


def safe_div(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(row["outcome"] for row in rows)
    by_split: dict[str, Counter] = defaultdict(Counter)
    by_truth_source: dict[str, Counter] = defaultdict(Counter)
    by_slide: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_split[row["split"]][row["outcome"]] += 1
        by_truth_source[row["truth_source"]][row["outcome"]] += 1
        by_slide[row["slide_id"]][row["outcome"]] += 1

    tp = counts["true_positive"]
    fp = counts["false_positive"]
    fn = counts["false_negative"]
    tn = counts["true_negative"]
    known = tp + fp + fn + tn

    return {
        "total_rows": len(rows),
        "known_truth_rows": known,
        "unknown_rows": counts["unknown"],
        "counts": {name: counts[name] for name in OUTCOMES},
        "metrics": {
            "accuracy": safe_div(tp + tn, known),
            "tumor_precision": safe_div(tp, tp + fp),
            "tumor_recall": safe_div(tp, tp + fn),
            "false_positive_rate": safe_div(fp, fp + tn),
            "false_negative_rate": safe_div(fn, fn + tp),
        },
        "by_split": {split: dict(counter) for split, counter in sorted(by_split.items())},
        "by_truth_source": {
            source: dict(counter) for source, counter in sorted(by_truth_source.items())
        },
        "by_slide": {slide: dict(counter) for slide, counter in sorted(by_slide.items())},
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "patch_id",
        "split",
        "slide_id",
        "x",
        "y",
        "width",
        "height",
        "truth_label",
        "truth_source",
        "xml_tumor_match",
        "target",
        "predicted_tumor",
        "predicted_index",
        "predicted_class",
        "confidence",
        "p_no_metastasico",
        "p_metastasico",
        "p_estroma",
        "outcome",
        "label_source",
        "annotation_status",
        "hard_negative_type",
        "path",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_outputs(output_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "all_predictions.csv", rows)
    for outcome in OUTCOMES:
        write_csv(output_dir / f"{outcome}.csv", [row for row in rows if row["outcome"] == outcome])
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be greater than zero.")
    if not 0.0 <= args.tumor_threshold <= 1.0:
        raise SystemExit("--tumor-threshold must be in [0, 1].")

    torch = load_runtime_dependencies()
    device = resolve_device(torch, args.device)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    head, labels = build_head_from_checkpoint(torch, checkpoint, device)
    polygons_by_slide = load_polygons(Path(args.annotations_dir))
    targets = load_targets_csv(Path(args.targets_csv)) if args.targets_csv else {}

    output_dir = Path(args.output_dir)
    all_rows: list[dict[str, Any]] = []
    for split in parse_splits(args.splits):
        embeddings_path = Path(args.embeddings_dir) / f"manifest_{split}_embeddings.pt"
        if not embeddings_path.exists():
            raise SystemExit(f"Missing embeddings file: {embeddings_path}")
        print(f"[histopathology-xml-eval] evaluating split={split} from {embeddings_path}", flush=True)
        all_rows.extend(
            evaluate_split(
                torch=torch,
                head=head,
                labels=labels,
                embeddings_path=embeddings_path,
                polygons_by_slide=polygons_by_slide,
                targets=targets,
                truth_mode=args.truth_mode,
                tumor_threshold=args.tumor_threshold,
                batch_size=args.batch_size,
                device=device,
            )
        )

    summary = {
        "manifest": args.manifest,
        "embeddings_dir": args.embeddings_dir,
        "checkpoint": args.checkpoint,
        "annotations_dir": args.annotations_dir,
        "targets_csv": args.targets_csv,
        "splits": parse_splits(args.splits),
        "truth_mode": args.truth_mode,
        "tumor_threshold": args.tumor_threshold,
        "labels": labels,
        **summarize_rows(all_rows),
    }
    write_outputs(output_dir, all_rows, summary)
    print(json.dumps(summary["counts"], indent=2), flush=True)
    print(f"[histopathology-xml-eval] outputs -> {output_dir}", flush=True)


if __name__ == "__main__":
    main()
