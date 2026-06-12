import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from histopathology_offline.rigorous_evaluation import recommend_threshold
from histopathology_offline.roi_aggregation import STRATEGIES, aggregate_tile_probabilities


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Compare tile aggregation strategies on deterministic slide-level tile bags. "
            "This is a proxy analysis, not evaluation on expert-annotated user ROIs."
        )
    )
    parser.add_argument("--validation-predictions", required=True)
    parser.add_argument("--test-predictions", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--bag-size", type=int, default=8)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--tile-threshold", type=float, default=0.5)
    parser.add_argument("--minimum-precision", type=float, default=0.85)
    return parser.parse_args()


def read_rows(path):
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["x"] = int(float(row["x"]))
        row["y"] = int(float(row["y"]))
    return rows


def build_bags(rows, bag_size: int):
    by_slide = defaultdict(list)
    for row in rows:
        by_slide[row["slide_id"]].append(row)
    bags = []
    for slide_id, slide_rows in sorted(by_slide.items()):
        ordered = sorted(slide_rows, key=lambda row: (row["y"], row["x"], row["patch_id"]))
        for offset in range(0, len(ordered), bag_size):
            bag_rows = ordered[offset : offset + bag_size]
            if not bag_rows:
                continue
            bags.append(
                {
                    "slide_id": slide_id,
                    "rows": bag_rows,
                    "tumor_true": any(row["true_class"] == "metastasico" for row in bag_rows),
                }
            )
    return bags


def score_bags(bags, strategy: str, top_k: int, tile_threshold: float):
    scored = []
    for bag in bags:
        probabilities = [
            {
                "no_metastasico": float(row["p_no_metastasico"]),
                "metastasico": float(row["p_metastasico"]),
                "estroma": float(row["p_estroma"]),
            }
            for row in bag["rows"]
        ]
        aggregation = aggregate_tile_probabilities(
            probabilities,
            strategy=strategy,
            top_k=top_k,
            tile_threshold=tile_threshold,
        )
        scored.append(
            {
                "slide_id": bag["slide_id"],
                "tumor_true": bag["tumor_true"],
                "tumor_score": aggregation["tumor_score"],
                "tile_count": aggregation["tile_count"],
            }
        )
    return scored


def threshold_rows(scored):
    rows = []
    for threshold in [round(value * 0.05, 2) for value in range(1, 20)]:
        tp = fp = fn = tn = 0
        for item in scored:
            predicted = item["tumor_score"] >= threshold
            actual = item["tumor_true"]
            if predicted and actual:
                tp += 1
            elif predicted:
                fp += 1
            elif actual:
                fn += 1
            else:
                tn += 1
        precision = tp / max(1, tp + fp)
        sensitivity = tp / max(1, tp + fn)
        specificity = tn / max(1, tn + fp)
        f1 = 2 * precision * sensitivity / max(1e-12, precision + sensitivity)
        rows.append(
            {
                "threshold": threshold,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "sensitivity": sensitivity,
                "specificity": specificity,
                "f1": f1,
                "balanced_accuracy": (sensitivity + specificity) / 2,
            }
        )
    return rows


def evaluate_locked(scored, threshold):
    return next(row for row in threshold_rows(scored) if row["threshold"] == threshold)


def main():
    args = parse_args()
    validation_bags = build_bags(read_rows(args.validation_predictions), args.bag_size)
    test_bags = build_bags(read_rows(args.test_predictions), args.bag_size)
    comparisons = {}
    for strategy in STRATEGIES:
        validation_scored = score_bags(
            validation_bags,
            strategy,
            args.top_k,
            args.tile_threshold,
        )
        test_scored = score_bags(test_bags, strategy, args.top_k, args.tile_threshold)
        selected = recommend_threshold(
            threshold_rows(validation_scored),
            minimum_precision=args.minimum_precision,
        )
        comparisons[strategy] = {
            "validation_selected_threshold": selected,
            "test_locked_threshold_metrics": evaluate_locked(
                test_scored,
                selected["threshold"],
            ),
        }
    payload = {
        "method": "deterministic slide-sorted tile bags",
        "bag_size": args.bag_size,
        "validation_bags": len(validation_bags),
        "test_bags": len(test_bags),
        "strategies": comparisons,
        "limitation": (
            "Proxy only: bags are built from sampled patches ordered within each slide. "
            "They are not contiguous user-selected ROIs and have no expert ROI-level labels."
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
