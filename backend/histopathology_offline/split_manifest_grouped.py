import argparse
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from histopathology_offline.balance_patch_manifest import CLASS_ORDER, class_name_for_row
from histopathology_offline.manifest_dataset import PatchManifestRow, read_manifest, write_manifest


SPLIT_ORDER = ("train", "val", "test")
PATIENT_PATTERN = re.compile(r"(patient[_-]?\d+)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a reproducible train/validation/test manifest without patient or "
            "slide overlap. Patient grouping is preferred and slide grouping is the fallback."
        )
    )
    parser.add_argument("--manifest", required=True, help="Source manifest CSV.")
    parser.add_argument("--output", required=True, help="Output manifest CSV.")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--summary-csv", required=True)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=20260607)
    parser.add_argument(
        "--search-trials",
        type=int,
        default=20000,
        help="Deterministic random assignments evaluated for class balance.",
    )
    return parser.parse_args()


def patient_id_for_row(row: PatchManifestRow) -> str | None:
    for value in (row.slide_id, row.patch_id, row.path):
        match = PATIENT_PATTERN.search(value or "")
        if match:
            digits = re.search(r"\d+", match.group(1))
            if digits:
                return f"patient_{int(digits.group(0)):03d}"
    return None


def group_id_for_row(row: PatchManifestRow) -> tuple[str, str]:
    patient_id = patient_id_for_row(row)
    if patient_id:
        return "patient", patient_id
    return "slide", row.slide_id


def _split_group_counts(group_count: int, train_ratio: float, val_ratio: float) -> dict[str, int]:
    if group_count < 3:
        raise ValueError("At least three independent patient/slide groups are required.")
    train_count = max(1, round(group_count * train_ratio))
    val_count = max(1, round(group_count * val_ratio))
    if train_count + val_count >= group_count:
        train_count = max(1, group_count - 2)
        val_count = 1
    return {
        "train": train_count,
        "val": val_count,
        "test": group_count - train_count - val_count,
    }


def _assignment_score(
    assignment: dict[str, set[tuple[str, str]]],
    group_rows: dict[tuple[str, str], list[PatchManifestRow]],
    ratios: dict[str, float],
) -> float:
    total_rows = sum(len(rows) for rows in group_rows.values())
    global_classes = Counter(class_name_for_row(row) for rows in group_rows.values() for row in rows)
    score = 0.0
    for split in SPLIT_ORDER:
        rows = [row for group in assignment[split] for row in group_rows[group]]
        class_counts = Counter(class_name_for_row(row) for row in rows)
        target_rows = max(1.0, total_rows * ratios[split])
        score += abs(len(rows) - target_rows) / target_rows
        for class_name in CLASS_ORDER:
            target_class = max(1.0, global_classes[class_name] * ratios[split])
            score += 2.0 * abs(class_counts[class_name] - target_class) / target_class
            if global_classes[class_name] and not class_counts[class_name]:
                score += 100.0
    return score


def assign_groups(
    rows: list[PatchManifestRow],
    *,
    train_ratio: float,
    val_ratio: float,
    seed: int,
    search_trials: int,
) -> dict[tuple[str, str], str]:
    test_ratio = 1.0 - train_ratio - val_ratio
    if min(train_ratio, val_ratio, test_ratio) <= 0:
        raise ValueError("Ratios must be positive and leave a non-empty test split.")

    group_rows: dict[tuple[str, str], list[PatchManifestRow]] = defaultdict(list)
    for row in rows:
        group_rows[group_id_for_row(row)].append(row)

    groups = sorted(group_rows)
    counts = _split_group_counts(len(groups), train_ratio, val_ratio)
    ratios = {"train": train_ratio, "val": val_ratio, "test": test_ratio}
    rng = random.Random(seed)
    best_score = float("inf")
    best_assignment = None

    for _ in range(max(1, search_trials)):
        candidate = list(groups)
        rng.shuffle(candidate)
        train_end = counts["train"]
        val_end = train_end + counts["val"]
        assignment = {
            "train": set(candidate[:train_end]),
            "val": set(candidate[train_end:val_end]),
            "test": set(candidate[val_end:]),
        }
        score = _assignment_score(assignment, group_rows, ratios)
        if score < best_score:
            best_score = score
            best_assignment = assignment

    if best_assignment is None:
        raise RuntimeError("No valid group assignment was generated.")
    return {
        group: split
        for split, split_groups in best_assignment.items()
        for group in split_groups
    }


def validate_no_overlap(rows: list[PatchManifestRow]) -> dict:
    values_by_split = {
        split: {
            "patches": set(),
            "slides": set(),
            "patients": set(),
        }
        for split in SPLIT_ORDER
    }
    for row in rows:
        if row.split not in values_by_split:
            continue
        bucket = values_by_split[row.split]
        bucket["patches"].add(row.patch_id)
        bucket["slides"].add(row.slide_id)
        patient_id = patient_id_for_row(row)
        if patient_id:
            bucket["patients"].add(patient_id)

    overlaps = {}
    for left_index, left in enumerate(SPLIT_ORDER):
        for right in SPLIT_ORDER[left_index + 1 :]:
            key = f"{left}_vs_{right}"
            overlaps[key] = {
                entity: sorted(values_by_split[left][entity] & values_by_split[right][entity])
                for entity in ("patches", "slides", "patients")
            }

    valid = all(
        not values
        for pair in overlaps.values()
        for values in pair.values()
    )
    return {"valid": valid, "overlaps": overlaps}


def summarize(rows: list[PatchManifestRow], *, source_manifest: str, seed: int, ratios: dict) -> dict:
    validation = validate_no_overlap(rows)
    split_summary = {}
    for split in SPLIT_ORDER:
        selected = [row for row in rows if row.split == split]
        patients = {patient_id_for_row(row) for row in selected}
        patients.discard(None)
        split_summary[split] = {
            "patches": len(selected),
            "slides": len({row.slide_id for row in selected}),
            "patients": len(patients),
            "class_counts": dict(
                sorted(Counter(class_name_for_row(row) for row in selected).items())
            ),
        }
    return {
        "source_manifest": source_manifest,
        "seed": seed,
        "ratios": ratios,
        "grouping_priority": ["patient", "slide"],
        "fallback_slide_groups": sorted(
            {row.slide_id for row in rows if patient_id_for_row(row) is None}
        ),
        "splits": split_summary,
        "overlap_validation": validation,
        "limitations": (
            "This is an internal grouped split of the available CAMELYON17-derived patches. "
            "It is not an external, prospective, diagnostic, or clinical validation."
        ),
    }


def write_summary_csv(path: str | Path, summary: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "split",
                "patches",
                "slides",
                "patients",
                *CLASS_ORDER,
            ],
        )
        writer.writeheader()
        for split in SPLIT_ORDER:
            payload = summary["splits"][split]
            writer.writerow(
                {
                    "split": split,
                    "patches": payload["patches"],
                    "slides": payload["slides"],
                    "patients": payload["patients"],
                    **{
                        class_name: payload["class_counts"].get(class_name, 0)
                        for class_name in CLASS_ORDER
                    },
                }
            )


def main() -> None:
    args = parse_args()
    rows = read_manifest(args.manifest)
    assignment = assign_groups(
        rows,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        seed=args.seed,
        search_trials=args.search_trials,
    )
    split_rows = [
        replace(row, split=assignment[group_id_for_row(row)])
        for row in rows
    ]
    summary = summarize(
        split_rows,
        source_manifest=args.manifest,
        seed=args.seed,
        ratios={
            "train": args.train_ratio,
            "val": args.val_ratio,
            "test": 1.0 - args.train_ratio - args.val_ratio,
        },
    )
    if not summary["overlap_validation"]["valid"]:
        raise SystemExit("Grouped split failed overlap validation.")

    write_manifest(args.output, split_rows)
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_summary_csv(args.summary_csv, summary)
    print(json.dumps(summary["splits"], indent=2), flush=True)


if __name__ == "__main__":
    main()
