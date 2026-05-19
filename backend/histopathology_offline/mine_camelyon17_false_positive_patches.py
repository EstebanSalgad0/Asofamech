from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.histopathology.ml.inference_service import get_inference_service
from app.histopathology.roi_quality import evaluate_roi_quality
from histopathology_offline.build_camelyon17_official_manifest import (
    IMAGE_EXTENSIONS,
    SlideReader,
    TumorPolygon,
    bbox_intersects,
    load_polygons,
    split_for_slide,
)
from histopathology_offline.manifest_dataset import PatchManifestRow, write_manifest
from histopathology_offline.sample_hard_negative_patches import classify_negative_type, format_metric


DEFAULT_STAGE10_CHECKPOINT = (
    "artifacts/histopathology/checkpoints/"
    "tri_head_camelyon17_stage10_balanced_v1_weighted.pt"
)


@dataclass(frozen=True)
class MiningSlide:
    slide_id: str
    path: Path
    truth_source: str


@dataclass(frozen=True)
class MinedCandidate:
    slide_id: str
    x: int
    y: int
    width: int
    height: int
    split: str
    truth_source: str
    tumor_score: float
    predicted_class: str
    confidence: float
    qc: dict[str, Any]


def parse_id_set(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def expanded_bbox(bbox: tuple[float, float, float, float], margin: int) -> tuple[float, float, float, float]:
    left, top, right, bottom = bbox
    return left - margin, top - margin, right + margin, bottom + margin


def patch_is_outside_tumor(
    x: int,
    y: int,
    patch_size: int,
    polygons: list[TumorPolygon],
    tumor_margin: int = 0,
) -> bool:
    patch_bbox = (x, y, x + patch_size, y + patch_size)
    for polygon in polygons:
        if bbox_intersects(patch_bbox, expanded_bbox(polygon.bbox, tumor_margin)):
            return False
    return True


def sample_outside_tumor_xy(
    dimensions: tuple[int, int],
    polygons: list[TumorPolygon],
    patch_size: int,
    rng: random.Random,
    max_attempts: int,
    tumor_margin: int,
) -> tuple[int, int] | None:
    slide_width, slide_height = dimensions
    if slide_width < patch_size or slide_height < patch_size:
        return None

    for _ in range(max_attempts):
        x = rng.randint(0, slide_width - patch_size)
        y = rng.randint(0, slide_height - patch_size)
        if patch_is_outside_tumor(x, y, patch_size, polygons, tumor_margin):
            return x, y
    return None


def load_mining_slides(
    images_dir: Path,
    polygons_by_slide: dict[str, list[TumorPolygon]],
    requested_slide_ids: set[str],
    negative_slide_ids: set[str],
) -> list[MiningSlide]:
    slides: list[MiningSlide] = []
    for image_path in sorted(images_dir.iterdir()):
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        slide_id = image_path.name
        if requested_slide_ids and slide_id not in requested_slide_ids:
            continue
        if slide_id in polygons_by_slide:
            slides.append(
                MiningSlide(
                    slide_id=slide_id,
                    path=image_path,
                    truth_source="outside_xml_tumor_polygon",
                )
            )
        elif slide_id in negative_slide_ids:
            slides.append(
                MiningSlide(
                    slide_id=slide_id,
                    path=image_path,
                    truth_source="negative_slide",
                )
            )
    return slides


def should_keep_candidate(
    *,
    tumor_score: float,
    predicted_class: str,
    min_tumor_score: float,
) -> bool:
    return tumor_score >= min_tumor_score or predicted_class == "metastasico"


def select_top_candidates(candidates: list[MinedCandidate], limit: int) -> list[MinedCandidate]:
    return sorted(candidates, key=lambda item: item.tumor_score, reverse=True)[:limit]


def mined_hard_negative_type(qc: dict[str, Any]) -> str:
    negative_type = classify_negative_type(qc)
    if negative_type in {"stroma", "stroma_low_cellularity"}:
        return negative_type
    return negative_type or "lymphoid_or_mixed_negative"


def candidate_to_manifest_row(
    candidate: MinedCandidate,
    patch_path: Path,
    row_index: int,
    source: str,
) -> PatchManifestRow:
    metrics = candidate.qc["metrics"]
    patch_id = (
        f"stage13_{Path(candidate.slide_id).stem}_{candidate.x}_{candidate.y}_"
        f"{candidate.width}x{candidate.height}_{row_index:06d}"
    )
    return PatchManifestRow(
        patch_id=patch_id,
        source=source,
        slide_id=candidate.slide_id,
        path=str(patch_path),
        label=0,
        hard_negative_type=mined_hard_negative_type(candidate.qc),
        x=candidate.x,
        y=candidate.y,
        width=candidate.width,
        height=candidate.height,
        split=candidate.split,
        qc_status=candidate.qc["status"],
        qc_tissue_fraction=format_metric(metrics["tissue_fraction"]),
        qc_nuclear_fraction=format_metric(metrics["nuclear_fraction"]),
        qc_white_fraction=format_metric(metrics["white_fraction"]),
        qc_stroma_fraction=format_metric(metrics["stroma_fraction"]),
        annotation_status=candidate.truth_source,
        label_source="xml_mined_false_positive",
    )


def write_candidates_csv(path: Path, rows: list[tuple[MinedCandidate, PatchManifestRow]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "patch_id",
                "slide_id",
                "split",
                "truth_source",
                "x",
                "y",
                "width",
                "height",
                "tumor_score",
                "predicted_class",
                "confidence",
                "hard_negative_type",
                "qc_status",
                "qc_tissue_fraction",
                "qc_nuclear_fraction",
                "qc_white_fraction",
                "qc_stroma_fraction",
                "path",
            ],
        )
        writer.writeheader()
        for candidate, manifest_row in rows:
            writer.writerow(
                {
                    "patch_id": manifest_row.patch_id,
                    "slide_id": candidate.slide_id,
                    "split": candidate.split,
                    "truth_source": candidate.truth_source,
                    "x": candidate.x,
                    "y": candidate.y,
                    "width": candidate.width,
                    "height": candidate.height,
                    "tumor_score": f"{candidate.tumor_score:.6f}",
                    "predicted_class": candidate.predicted_class,
                    "confidence": f"{candidate.confidence:.6f}",
                    "hard_negative_type": manifest_row.hard_negative_type,
                    "qc_status": manifest_row.qc_status,
                    "qc_tissue_fraction": manifest_row.qc_tissue_fraction,
                    "qc_nuclear_fraction": manifest_row.qc_nuclear_fraction,
                    "qc_white_fraction": manifest_row.qc_white_fraction,
                    "qc_stroma_fraction": manifest_row.qc_stroma_fraction,
                    "path": manifest_row.path,
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Mine CAMELYON17 hard negatives by sampling official non-tumor tissue "
            "and keeping patches the active model scores as suspicious/metastatic."
        )
    )
    parser.add_argument("--images-dir", default="data/camelyon17/images")
    parser.add_argument("--annotations-dir", default="data/camelyon17/annotations")
    parser.add_argument("--output-dir", default="artifacts/histopathology/camelyon17_patches_stage13_mined")
    parser.add_argument(
        "--manifest",
        default="artifacts/histopathology/manifests/camelyon17_manifest_stage13_mined_hard_negatives.csv",
    )
    parser.add_argument(
        "--candidates-csv",
        default="artifacts/histopathology/reports/camelyon17_stage13_mined_candidates.csv",
    )
    parser.add_argument(
        "--report",
        default="artifacts/histopathology/reports/camelyon17_stage13_mined_summary.json",
    )
    parser.add_argument("--source", default="camelyon17_xml_mined")
    parser.add_argument("--classifier-checkpoint", default=DEFAULT_STAGE10_CHECKPOINT)
    parser.add_argument("--conch-checkpoint-ref", default="")
    parser.add_argument("--slide-ids", default="", help="Comma-separated slide filenames to process.")
    parser.add_argument(
        "--negative-slide-ids",
        default="",
        help="Comma-separated slide filenames that are known negative despite having no XML.",
    )
    parser.add_argument("--patch-size", type=int, default=256)
    parser.add_argument("--sampled-patches-per-slide", type=int, default=96)
    parser.add_argument("--hard-negatives-per-slide", type=int, default=24)
    parser.add_argument("--max-attempts-per-sample", type=int, default=80)
    parser.add_argument("--tumor-margin", type=int, default=512)
    parser.add_argument("--min-tumor-score", type=float, default=0.50)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=37)
    parser.add_argument(
        "--allow-non-evaluable",
        action="store_true",
        help="Keep non-evaluable suspicious patches. Default skips them.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.patch_size < 1:
        raise SystemExit("--patch-size must be greater than zero")
    if args.sampled_patches_per_slide < 1:
        raise SystemExit("--sampled-patches-per-slide must be greater than zero")
    if args.hard_negatives_per_slide < 1:
        raise SystemExit("--hard-negatives-per-slide must be greater than zero")
    if args.max_attempts_per_sample < 1:
        raise SystemExit("--max-attempts-per-sample must be greater than zero")
    if args.tumor_margin < 0:
        raise SystemExit("--tumor-margin must be zero or greater")
    if args.min_tumor_score < 0.0 or args.min_tumor_score > 1.0:
        raise SystemExit("--min-tumor-score must be between 0 and 1")
    if args.train_ratio <= 0 or args.val_ratio < 0 or args.train_ratio + args.val_ratio >= 1:
        raise SystemExit("Ratios must leave a non-empty test split")


def main() -> None:
    args = parse_args()
    validate_args(args)

    classifier_checkpoint = Path(args.classifier_checkpoint)
    if not classifier_checkpoint.exists():
        raise SystemExit(f"Classifier checkpoint not found: {classifier_checkpoint}")
    os.environ["HISTO_CLASSIFIER_CHECKPOINT"] = str(classifier_checkpoint)
    if args.conch_checkpoint_ref:
        os.environ["HISTO_CONCH_CHECKPOINT_REF"] = args.conch_checkpoint_ref

    images_dir = Path(args.images_dir)
    annotations_dir = Path(args.annotations_dir)
    output_dir = Path(args.output_dir)
    polygons_by_slide = load_polygons(annotations_dir)
    requested_slide_ids = parse_id_set(args.slide_ids)
    negative_slide_ids = parse_id_set(args.negative_slide_ids)
    slides = load_mining_slides(images_dir, polygons_by_slide, requested_slide_ids, negative_slide_ids)
    if not slides:
        raise SystemExit("No eligible slides found. Use XML-positive slides or explicit --negative-slide-ids.")

    rng = random.Random(args.seed)
    inference_service = get_inference_service()
    manifest_rows: list[PatchManifestRow] = []
    selected_pairs: list[tuple[MinedCandidate, PatchManifestRow]] = []
    per_slide: dict[str, dict[str, Any]] = {}

    for slide in slides:
        polygons = polygons_by_slide.get(slide.slide_id, [])
        split = split_for_slide(slide.slide_id, args.train_ratio, args.val_ratio, args.seed)
        candidates: list[MinedCandidate] = []
        sampled = 0
        skipped_qc = 0
        attempted_positions = 0
        max_sampling_attempts = args.sampled_patches_per_slide * args.max_attempts_per_sample
        reader = SlideReader(slide.path)
        try:
            while sampled < args.sampled_patches_per_slide and attempted_positions < max_sampling_attempts:
                attempted_positions += 1
                xy = sample_outside_tumor_xy(
                    dimensions=reader.dimensions,
                    polygons=polygons,
                    patch_size=args.patch_size,
                    rng=rng,
                    max_attempts=1,
                    tumor_margin=args.tumor_margin,
                )
                if xy is None:
                    continue

                x, y = xy
                patch = reader.read_patch(x, y, args.patch_size, args.patch_size)
                qc = evaluate_roi_quality(patch)
                if qc["status"] != "evaluable" and not args.allow_non_evaluable:
                    skipped_qc += 1
                    continue

                sampled += 1
                prediction = inference_service.predict_patch(patch)
                tumor_score = float(prediction["probabilities"].get("metastasico", 0.0))
                predicted_class = str(prediction["predicted_class"])
                if not should_keep_candidate(
                    tumor_score=tumor_score,
                    predicted_class=predicted_class,
                    min_tumor_score=args.min_tumor_score,
                ):
                    continue

                candidates.append(
                    MinedCandidate(
                        slide_id=slide.slide_id,
                        x=x,
                        y=y,
                        width=args.patch_size,
                        height=args.patch_size,
                        split=split,
                        truth_source=slide.truth_source,
                        tumor_score=tumor_score,
                        predicted_class=predicted_class,
                        confidence=float(prediction["confidence"]),
                        qc=qc,
                    )
                )

            selected = select_top_candidates(candidates, args.hard_negatives_per_slide)
            for candidate in selected:
                row_index = len(manifest_rows)
                patch_id = (
                    f"stage13_{Path(candidate.slide_id).stem}_{candidate.x}_{candidate.y}_"
                    f"{candidate.width}x{candidate.height}_{row_index:06d}"
                )
                patch_path = output_dir / candidate.split / "0" / f"{patch_id}.png"
                patch_path.parent.mkdir(parents=True, exist_ok=True)
                patch = reader.read_patch(candidate.x, candidate.y, candidate.width, candidate.height)
                patch.save(patch_path)
                row = candidate_to_manifest_row(candidate, patch_path, row_index, args.source)
                manifest_rows.append(row)
                selected_pairs.append((candidate, row))

            per_slide[slide.slide_id] = {
                "truth_source": slide.truth_source,
                "split": split,
                "attempted_positions": attempted_positions,
                "sampled_evaluable": sampled,
                "skipped_qc": skipped_qc,
                "suspicious_candidates": len(candidates),
                "selected": len(selected),
                "max_tumor_score": max((candidate.tumor_score for candidate in candidates), default=0.0),
            }
            print(
                "[histopathology-stage13] "
                f"slide={slide.slide_id} attempts={attempted_positions} sampled={sampled} suspicious={len(candidates)} "
                f"selected={len(selected)} max_score={per_slide[slide.slide_id]['max_tumor_score']:.3f}",
                flush=True,
            )
        finally:
            reader.close()

    write_manifest(args.manifest, manifest_rows)
    write_candidates_csv(Path(args.candidates_csv), selected_pairs)

    summary = {
        "manifest": args.manifest,
        "candidates_csv": args.candidates_csv,
        "output_dir": args.output_dir,
        "classifier_checkpoint": str(classifier_checkpoint),
        "num_slides": len(slides),
        "rows": len(manifest_rows),
        "patch_size": args.patch_size,
        "sampled_patches_per_slide": args.sampled_patches_per_slide,
        "hard_negatives_per_slide": args.hard_negatives_per_slide,
        "min_tumor_score": args.min_tumor_score,
        "tumor_margin": args.tumor_margin,
        "by_split": dict(Counter(row.split for row in manifest_rows)),
        "by_hard_negative_type": dict(Counter(row.hard_negative_type for row in manifest_rows)),
        "by_annotation_status": dict(Counter(row.annotation_status for row in manifest_rows)),
        "per_slide": per_slide,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[histopathology-stage13] manifest rows={len(manifest_rows)} -> {args.manifest}", flush=True)
    print(f"[histopathology-stage13] report -> {report_path}", flush=True)


if __name__ == "__main__":
    main()
