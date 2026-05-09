import argparse
import random
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from histopathology_offline.manifest_dataset import read_manifest, write_manifest


def parse_args():
    parser = argparse.ArgumentParser(description="Merge patch manifests with optional per-source caps.")
    parser.add_argument("--base-manifest", required=True)
    parser.add_argument("--extra-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-extra-per-split", type=int, default=0)
    parser.add_argument("--seed", type=int, default=13)
    return parser.parse_args()


def cap_rows_by_split(rows, max_per_split: int, seed: int):
    if max_per_split <= 0:
        return rows

    rng = random.Random(seed)
    grouped = {}
    for row in rows:
        grouped.setdefault(row.split, []).append(row)

    selected = []
    for split, split_rows in grouped.items():
        rng.shuffle(split_rows)
        selected.extend(split_rows[:max_per_split])
    return selected


def main():
    args = parse_args()
    base_rows = read_manifest(args.base_manifest)
    extra_rows = read_manifest(args.extra_manifest)
    selected_extra_rows = cap_rows_by_split(extra_rows, args.max_extra_per_split, args.seed)
    write_manifest(args.output, [*base_rows, *selected_extra_rows])
    print(
        "[histopathology] "
        f"base={len(base_rows)} extra={len(extra_rows)} selected_extra={len(selected_extra_rows)} "
        f"total={len(base_rows) + len(selected_extra_rows)} -> {args.output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
