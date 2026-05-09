import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PIL import Image

from app.histopathology.roi_quality import QualityThresholds, evaluate_roi_quality
from histopathology_offline.manifest_dataset import PatchManifestRow, read_manifest


def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate the ROI quality gate over a patch manifest."
    )
    parser.add_argument("--manifest", required=True, help="Patch manifest CSV to evaluate.")
    parser.add_argument("--output", required=True, help="JSON report output path.")
    parser.add_argument(
        "--root-dir",
        default=".",
        help="Base directory used for relative patch paths. Default: current directory.",
    )
    parser.add_argument(
        "--splits",
        default="test",
        help="Comma-separated splits to evaluate, or 'all'. Default: test.",
    )
    parser.add_argument("--max-white-fraction", type=float, default=0.45)
    parser.add_argument("--min-tissue-fraction", type=float, default=0.40)
    parser.add_argument("--min-nuclear-fraction", type=float, default=0.035)
    parser.add_argument("--max-dominant-stroma-fraction", type=float, default=0.55)
    parser.add_argument("--max-stroma-fraction-when-low-nuclear", type=float, default=0.65)
    parser.add_argument("--low-nuclear-for-stroma-fraction", type=float, default=0.12)
    parser.add_argument(
        "--include-records",
        action="store_true",
        help="Include one compact result per patch in the JSON report.",
    )
    return parser.parse_args()


def selected_splits(raw: str) -> set[str] | None:
    if raw.strip().lower() == "all":
        return None
    return {split.strip() for split in raw.split(",") if split.strip()}


def resolve_patch_path(row: PatchManifestRow, root_dir: Path) -> Path:
    path = Path(row.path)
    if path.is_absolute():
        return path
    return root_dir / path


def empty_bucket() -> dict:
    return {
        "total": 0,
        "evaluable": 0,
        "blocked": 0,
        "blocked_rate": 0.0,
    }


def update_bucket(bucket: dict, is_evaluable: bool) -> None:
    bucket["total"] += 1
    if is_evaluable:
        bucket["evaluable"] += 1
    else:
        bucket["blocked"] += 1


def finalize_rates(payload) -> None:
    if isinstance(payload, dict) and {"total", "blocked_rate"}.issubset(payload):
        total = max(1, payload["total"])
        payload["blocked_rate"] = payload["blocked"] / total
        return

    if isinstance(payload, dict):
        for value in payload.values():
            finalize_rates(value)


def evaluate_rows(
    rows: Iterable[PatchManifestRow],
    root_dir: Path,
    thresholds: QualityThresholds,
    include_records: bool,
) -> dict:
    summary = {
        "overall": empty_bucket(),
        "by_split": {},
        "by_label": {},
        "by_hard_negative_type": {},
        "blocked_reasons": {},
    }
    records = []
    missing_files = []

    for row in rows:
        patch_path = resolve_patch_path(row, root_dir)
        if not patch_path.exists():
            missing_files.append({"patch_id": row.patch_id, "path": str(patch_path)})
            continue

        with Image.open(patch_path) as image:
            quality = evaluate_roi_quality(image.convert("RGB"), thresholds=thresholds)

        is_evaluable = bool(quality["is_evaluable"])
        update_bucket(summary["overall"], is_evaluable)

        split_bucket = summary["by_split"].setdefault(row.split, empty_bucket())
        update_bucket(split_bucket, is_evaluable)

        label_name = "positive" if int(row.label) == 1 else "negative"
        label_bucket = summary["by_label"].setdefault(label_name, empty_bucket())
        update_bucket(label_bucket, is_evaluable)

        if int(row.label) == 0:
            hard_type = row.hard_negative_type or "negative_unspecified"
            hard_bucket = summary["by_hard_negative_type"].setdefault(hard_type, empty_bucket())
            update_bucket(hard_bucket, is_evaluable)

        if not is_evaluable:
            reason = quality["reason"] or "ROI no evaluable"
            summary["blocked_reasons"][reason] = summary["blocked_reasons"].get(reason, 0) + 1

        if include_records:
            records.append(
                {
                    "patch_id": row.patch_id,
                    "split": row.split,
                    "label": int(row.label),
                    "hard_negative_type": row.hard_negative_type,
                    "is_evaluable": is_evaluable,
                    "reason": quality["reason"],
                    "metrics": quality["metrics"],
                    "checks": quality["checks"],
                }
            )

    finalize_rates(summary)
    return {
        "summary": summary,
        "missing_files": missing_files,
        "records": records if include_records else None,
    }


def main() -> None:
    args = parse_args()
    manifest = Path(args.manifest)
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

    rows = read_manifest(manifest)
    selected_rows = [row for row in rows if splits is None or row.split in splits]
    if not selected_rows:
        raise SystemExit("No manifest rows matched the requested splits.")

    result = evaluate_rows(selected_rows, root_dir, thresholds, args.include_records)
    report = {
        "manifest": str(manifest),
        "root_dir": str(root_dir),
        "splits": "all" if splits is None else sorted(splits),
        "thresholds": thresholds.__dict__,
        **result,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["summary"]["overall"]
    print(
        "[histopathology] "
        f"evaluated={summary['total']} "
        f"evaluable={summary['evaluable']} "
        f"blocked={summary['blocked']} "
        f"blocked_rate={summary['blocked_rate']:.3f} "
        f"report={output}"
    )


if __name__ == "__main__":
    main()
