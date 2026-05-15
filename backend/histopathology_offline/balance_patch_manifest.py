import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from histopathology_offline.manifest_dataset import PatchManifestRow, read_manifest, write_manifest


STROMA_TYPES = {"stroma", "stroma_low_cellularity"}
CLASS_ORDER = ("no_metastasico", "metastasico", "estroma")
SPLIT_ORDER = ("train", "val", "test")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Balance one or more patch manifests by split and semantic class. "
            "Selection is stratified by hard_negative_type/label_source to preserve variety."
        )
    )
    parser.add_argument("--manifest", action="append", required=True, help="Input manifest CSV. Can be repeated.")
    parser.add_argument("--output", required=True, help="Balanced output manifest CSV.")
    parser.add_argument("--summary", default="", help="Optional JSON summary path.")
    parser.add_argument(
        "--cap",
        action="append",
        default=[],
        help="Cap in the form split:class=count, for example train:no_metastasico=700.",
    )
    parser.add_argument("--seed", type=int, default=29)
    parser.add_argument("--no-dedupe", action="store_true", help="Keep duplicate coordinate rows.")
    return parser.parse_args()


def class_name_for_row(row: PatchManifestRow) -> str:
    if int(row.label) == 1:
        return "metastasico"
    if (row.hard_negative_type or "") in STROMA_TYPES:
        return "estroma"
    return "no_metastasico"


def parse_cap(value: str) -> tuple[str, str, int]:
    try:
        left, count_text = value.split("=", 1)
        split, class_name = left.split(":", 1)
        count = int(count_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Cap must use the form split:class=count, for example train:no_metastasico=700."
        ) from exc
    split = split.strip()
    class_name = class_name.strip()
    if split not in SPLIT_ORDER:
        raise argparse.ArgumentTypeError(f"Unknown split '{split}'. Expected one of {', '.join(SPLIT_ORDER)}.")
    if class_name not in CLASS_ORDER:
        raise argparse.ArgumentTypeError(
            f"Unknown class '{class_name}'. Expected one of {', '.join(CLASS_ORDER)}."
        )
    if count < 0:
        raise argparse.ArgumentTypeError("Cap count must be zero or greater.")
    return split, class_name, count


def parse_caps(values: list[str]) -> dict[tuple[str, str], int]:
    caps = {}
    for value in values:
        split, class_name, count = parse_cap(value)
        caps[(split, class_name)] = count
    return caps


def dedupe_rows(rows: list[PatchManifestRow]) -> list[PatchManifestRow]:
    seen = set()
    unique = []
    for row in rows:
        key = (
            row.source,
            row.slide_id,
            int(row.x),
            int(row.y),
            int(row.width),
            int(row.height),
            int(row.label),
            row.hard_negative_type or "",
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def subgroup_key(row: PatchManifestRow) -> str:
    class_name = class_name_for_row(row)
    if class_name == "metastasico":
        return row.label_source or row.annotation_status or "legacy_positive"
    if class_name == "estroma":
        return row.hard_negative_type or "stroma"
    return row.hard_negative_type or row.label_source or row.annotation_status or "generic_negative"


def select_stratified(rows: list[PatchManifestRow], cap: int, rng: random.Random) -> list[PatchManifestRow]:
    if cap >= len(rows):
        return list(rows)
    if cap <= 0:
        return []

    grouped = defaultdict(list)
    for row in rows:
        grouped[subgroup_key(row)].append(row)
    for group_rows in grouped.values():
        rng.shuffle(group_rows)

    selected = []
    subgroup_names = sorted(grouped)
    while len(selected) < cap and subgroup_names:
        progressed = False
        for name in list(subgroup_names):
            group_rows = grouped[name]
            if not group_rows:
                subgroup_names.remove(name)
                continue
            selected.append(group_rows.pop())
            progressed = True
            if len(selected) >= cap:
                break
        if not progressed:
            break
    return selected


def balance_rows(rows: list[PatchManifestRow], caps: dict[tuple[str, str], int], seed: int) -> list[PatchManifestRow]:
    rng = random.Random(seed)
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row.split, class_name_for_row(row))].append(row)

    selected = []
    split_names = [*SPLIT_ORDER, *sorted({row.split for row in rows} - set(SPLIT_ORDER))]
    for split in split_names:
        for class_name in CLASS_ORDER:
            group_rows = grouped.get((split, class_name), [])
            cap = caps.get((split, class_name), len(group_rows))
            selected.extend(select_stratified(group_rows, cap, rng))
    return selected


def summarize(rows: list[PatchManifestRow]) -> dict:
    by_split_class = Counter()
    by_hard_negative_type = Counter()
    by_label_source = Counter()
    for row in rows:
        class_name = class_name_for_row(row)
        by_split_class[f"{row.split}:{class_name}"] += 1
        by_hard_negative_type[row.hard_negative_type or ""] += 1
        by_label_source[row.label_source or ""] += 1
    return {
        "total_rows": len(rows),
        "by_split_class": dict(sorted(by_split_class.items())),
        "by_hard_negative_type": dict(sorted(by_hard_negative_type.items())),
        "by_label_source": dict(sorted(by_label_source.items())),
    }


def main():
    args = parse_args()
    caps = parse_caps(args.cap)
    rows = []
    for manifest in args.manifest:
        rows.extend(read_manifest(manifest))
    input_count = len(rows)
    if not args.no_dedupe:
        rows = dedupe_rows(rows)

    balanced = balance_rows(rows, caps, args.seed)
    write_manifest(args.output, balanced)
    summary = {
        "inputs": args.manifest,
        "input_rows": input_count,
        "deduped_rows": len(rows),
        "caps": {f"{split}:{class_name}": count for (split, class_name), count in sorted(caps.items())},
        "output": args.output,
        **summarize(balanced),
    }
    if args.summary:
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        "[histopathology] "
        f"input={input_count} deduped={len(rows)} balanced={len(balanced)} -> {args.output}",
        flush=True,
    )
    print(json.dumps(summary["by_split_class"], indent=2), flush=True)


if __name__ == "__main__":
    main()
