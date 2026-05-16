from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from histopathology_offline.manifest_dataset import PatchManifestRow, write_manifest


DEFAULT_OUTCOMES = ("false_positive", "false_negative")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Build a Stage 9 candidate manifest from CAMELYON17 XML evaluation "
            "errors. False positives become hard negatives; false negatives become "
            "difficult official positives."
        )
    )
    parser.add_argument("--evaluation-csv", required=True, help="all_predictions.csv from XML evaluation.")
    parser.add_argument("--output", required=True, help="Output manifest CSV.")
    parser.add_argument("--summary", default="", help="Optional summary JSON path.")
    parser.add_argument(
        "--include-outcomes",
        default=",".join(DEFAULT_OUTCOMES),
        help="Comma-separated outcomes to export.",
    )
    parser.add_argument(
        "--force-split",
        default="",
        help="Optional split override. Leave empty to preserve train/val split from evaluation.",
    )
    parser.add_argument(
        "--cap",
        action="append",
        default=[],
        help="Optional cap in outcome=count format. Example: --cap false_negative=120",
    )
    return parser.parse_args()


def parse_outcomes(value: str) -> set[str]:
    outcomes = {item.strip() for item in value.split(",") if item.strip()}
    if not outcomes:
        raise SystemExit("At least one outcome is required.")
    return outcomes


def parse_caps(values: list[str]) -> dict[str, int]:
    caps: dict[str, int] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid cap '{value}'. Expected outcome=count.")
        outcome, raw_count = value.split("=", 1)
        outcome = outcome.strip()
        if not outcome:
            raise SystemExit(f"Invalid cap '{value}'. Outcome is empty.")
        try:
            count = int(raw_count)
        except ValueError as exc:
            raise SystemExit(f"Invalid cap count in '{value}'.") from exc
        if count < 0:
            raise SystemExit(f"Invalid cap '{value}'. Count must be >= 0.")
        caps[outcome] = count
    return caps


def read_evaluation_rows(path: str | Path) -> list[dict]:
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def stable_key(row: dict) -> tuple:
    return (
        row.get("slide_id", ""),
        int(float(row.get("x") or 0)),
        int(float(row.get("y") or 0)),
        int(float(row.get("width") or 0)),
        int(float(row.get("height") or 0)),
        row.get("outcome", ""),
    )


def row_to_manifest_row(row: dict, force_split: str = "") -> PatchManifestRow:
    outcome = row["outcome"]
    if outcome == "false_positive":
        label = 0
        hard_negative_type = "xml_false_positive_hard_negative"
        label_source = "xml_evaluation_false_positive"
    elif outcome == "false_negative":
        label = 1
        hard_negative_type = "xml_false_negative_tumor"
        label_source = "xml_evaluation_false_negative"
    elif outcome == "true_positive":
        label = 1
        hard_negative_type = "xml_true_positive_tumor"
        label_source = "xml_evaluation_true_positive"
    elif outcome == "true_negative":
        label = 0
        hard_negative_type = "xml_true_negative"
        label_source = "xml_evaluation_true_negative"
    else:
        raise ValueError(f"Unsupported outcome for manifest export: {outcome}")

    slide_id = row["slide_id"]
    x = int(float(row["x"]))
    y = int(float(row["y"]))
    width = int(float(row["width"]))
    height = int(float(row["height"]))
    split = force_split or row.get("split") or "train"
    patch_id = f"stage9_{outcome}:{slide_id}:{x}:{y}:{width}:{height}"

    return PatchManifestRow(
        patch_id=patch_id,
        source="camelyon17_xml_evaluation",
        slide_id=slide_id,
        path=row.get("path", ""),
        label=label,
        hard_negative_type=hard_negative_type,
        x=x,
        y=y,
        width=width,
        height=height,
        split=split,
        qc_status="",
        qc_tissue_fraction="",
        qc_nuclear_fraction="",
        qc_white_fraction="",
        qc_stroma_fraction="",
        annotation_status=row.get("truth_source", ""),
        label_source=label_source,
    )


def select_rows(rows: list[dict], outcomes: set[str], caps: dict[str, int]) -> list[dict]:
    selected: list[dict] = []
    seen = set()
    counts: Counter[str] = Counter()
    for row in rows:
        outcome = row.get("outcome", "")
        if outcome not in outcomes:
            continue
        if outcome == "unknown":
            continue
        cap = caps.get(outcome)
        if cap is not None and counts[outcome] >= cap:
            continue
        key = stable_key(row)
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
        counts[outcome] += 1
    return selected


def summarize(rows: list[PatchManifestRow], source_rows: list[dict]) -> dict:
    by_outcome = Counter(row.get("outcome", "") for row in source_rows)
    by_manifest_class = Counter("metastasico" if row.label == 1 else "no_metastasico" for row in rows)
    by_split: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        class_name = "metastasico" if row.label == 1 else "no_metastasico"
        by_split[row.split][class_name] += 1
    return {
        "rows": len(rows),
        "source_outcomes": dict(by_outcome),
        "manifest_classes": dict(by_manifest_class),
        "by_split": {split: dict(counter) for split, counter in sorted(by_split.items())},
        "label_sources": dict(Counter(row.label_source for row in rows)),
        "hard_negative_types": dict(Counter(row.hard_negative_type for row in rows)),
    }


def main():
    args = parse_args()
    outcomes = parse_outcomes(args.include_outcomes)
    caps = parse_caps(args.cap)
    evaluation_rows = read_evaluation_rows(args.evaluation_csv)
    selected_source_rows = select_rows(evaluation_rows, outcomes, caps)
    manifest_rows = [row_to_manifest_row(row, force_split=args.force_split) for row in selected_source_rows]
    write_manifest(args.output, manifest_rows)

    summary = {
        "evaluation_csv": args.evaluation_csv,
        "output": args.output,
        "include_outcomes": sorted(outcomes),
        "force_split": args.force_split or None,
        "caps": caps,
        **summarize(manifest_rows, selected_source_rows),
    }
    summary_path = Path(args.summary) if args.summary else Path(args.output).with_suffix(".summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
