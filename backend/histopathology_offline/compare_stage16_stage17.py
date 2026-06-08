import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.histopathology.ml.classifier_head import TriMLPClassifierHead
from histopathology_offline.manifest_dataset import read_manifest
from histopathology_offline.rigorous_evaluation import (
    classification_metrics,
    softmax_with_temperature,
    threshold_metrics_at,
)
from histopathology_offline.split_manifest_grouped import patient_id_for_row


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare Stage 16 and Stage 17 on the same patient-grouped test set."
    )
    parser.add_argument("--stage16-checkpoint", required=True)
    parser.add_argument("--stage17-checkpoint", required=True)
    parser.add_argument("--common-embeddings-dir", required=True)
    parser.add_argument("--stage16-manifest", required=True)
    parser.add_argument("--stage17-manifest", required=True)
    parser.add_argument("--stage17-split-summary", required=True)
    parser.add_argument("--stage16-report", required=True)
    parser.add_argument("--stage17-report", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def load_predictions(torch, checkpoint_path: Path, embeddings_path: Path, temperature: float):
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    payload = torch.load(embeddings_path, map_location="cpu")
    head = TriMLPClassifierHead(
        int(checkpoint["feature_dim"]),
        hidden_dim=int(checkpoint.get("head_hidden_dim") or 256),
        dropout=float(checkpoint.get("head_dropout") or 0.25),
    )
    head.load_state_dict(checkpoint["state_dict"])
    head.eval()
    with torch.inference_mode():
        logits = head(payload["x"].float()).numpy()
    labels = [
        1
        if int(record.get("label", 0)) == 1
        else 2
        if (record.get("hard_negative_type") or "") in {"stroma", "stroma_low_cellularity"}
        else 0
        for record in payload["records"]
    ]
    return labels, softmax_with_temperature(logits, temperature)


def false_positive_breakdown(labels, probabilities, threshold: float):
    import numpy as np

    labels = np.asarray(labels, dtype=int)
    tumor_predicted = probabilities[:, 1] >= threshold
    return {
        "no_metastasico_as_tumor": int((tumor_predicted & (labels == 0)).sum()),
        "estroma_as_tumor": int((tumor_predicted & (labels == 2)).sum()),
        "no_metastasico_count": int((labels == 0).sum()),
        "estroma_count": int((labels == 2).sum()),
        "no_metastasico_false_positive_rate": float(
            (tumor_predicted & (labels == 0)).sum() / max(1, (labels == 0).sum())
        ),
        "estroma_false_positive_rate": float(
            (tumor_predicted & (labels == 2)).sum() / max(1, (labels == 2).sum())
        ),
    }


def manifest_summary(path: Path):
    rows = read_manifest(path)
    summary = {}
    entities = {}
    for split in ("train", "val", "test"):
        selected = [row for row in rows if row.split == split]
        patients = {patient_id_for_row(row) for row in selected}
        patients.discard(None)
        summary[split] = {
            "patches": len(selected),
            "patients": len(patients),
            "slides": len({row.slide_id for row in selected}),
        }
        entities[split] = {
            "patients": patients,
            "slides": {row.slide_id for row in selected},
        }
    overlaps = {}
    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        overlaps[f"{left}_vs_{right}"] = {
            "patients": len(entities[left]["patients"] & entities[right]["patients"]),
            "slides": len(entities[left]["slides"] & entities[right]["slides"]),
        }
    return {"splits": summary, "overlaps": overlaps}


def common_test_stage16_provenance(stage16_manifest: Path, stage17_manifest: Path):
    stage16_rows = read_manifest(stage16_manifest)
    stage17_test = [row for row in read_manifest(stage17_manifest) if row.split == "test"]
    stage16_by_patch = {row.patch_id: row for row in stage16_rows}
    stage16_train = [row for row in stage16_rows if row.split == "train"]
    train_patients = {patient_id_for_row(row) for row in stage16_train}
    train_slides = {row.slide_id for row in stage16_train}
    test_patients = {patient_id_for_row(row) for row in stage17_test}
    test_slides = {row.slide_id for row in stage17_test}
    return {
        "rows_by_original_stage16_split": {
            split: sum(
                1
                for row in stage17_test
                if stage16_by_patch[row.patch_id].split == split
            )
            for split in ("train", "val", "test")
        },
        "test_patients": len(test_patients),
        "patients_seen_in_stage16_train": len(test_patients & train_patients),
        "test_slides": len(test_slides),
        "slides_seen_in_stage16_train": len(test_slides & train_slides),
    }


def evaluate_model(torch, checkpoint_path, embeddings_path, threshold, temperature):
    labels, probabilities = load_predictions(
        torch,
        checkpoint_path,
        embeddings_path,
        temperature,
    )
    return {
        "temperature": temperature,
        "classification": classification_metrics(labels, probabilities),
        "operating_threshold": {
            **threshold_metrics_at(labels, probabilities, threshold),
            "false_positive_breakdown": false_positive_breakdown(
                labels,
                probabilities,
                threshold,
            ),
        },
    }


def main():
    args = parse_args()
    import torch

    embeddings_dir = Path(args.common_embeddings_dir)
    test_embeddings = embeddings_dir / "manifest_test_embeddings.pt"
    stage17_checkpoint = torch.load(args.stage17_checkpoint, map_location="cpu")
    stage17_temperature = float(
        (stage17_checkpoint.get("calibration") or {}).get("temperature") or 1.0
    )

    stage16_common = evaluate_model(
        torch,
        Path(args.stage16_checkpoint),
        test_embeddings,
        threshold=0.90,
        temperature=1.0,
    )
    stage17_common_uncalibrated = evaluate_model(
        torch,
        Path(args.stage17_checkpoint),
        test_embeddings,
        threshold=0.35,
        temperature=1.0,
    )
    stage17_common_calibrated = evaluate_model(
        torch,
        Path(args.stage17_checkpoint),
        test_embeddings,
        threshold=0.35,
        temperature=stage17_temperature,
    )

    stage16_historical = json.loads(Path(args.stage16_report).read_text(encoding="utf-8"))
    stage17_generated = json.loads(Path(args.stage17_report).read_text(encoding="utf-8"))
    stage17_split = json.loads(Path(args.stage17_split_summary).read_text(encoding="utf-8"))
    output = {
        "scope": (
            "Internal technical comparison on identical images. The test is independent "
            "for Stage 17, but not for Stage 16 because the historical training split "
            "contains some of the same patients, slides, and patches."
        ),
        "stage16_historical_split": manifest_summary(Path(args.stage16_manifest)),
        "stage17_grouped_split": stage17_split,
        "common_test_stage16_provenance": common_test_stage16_provenance(
            Path(args.stage16_manifest),
            Path(args.stage17_manifest),
        ),
        "historical_reports": {
            "stage16": stage16_historical["test"],
            "stage17": stage17_generated["test"],
        },
        "same_grouped_test_comparison": {
            "test_samples": stage17_generated["test"]["classification"]["sample_count"],
            "stage16_threshold_0_90": stage16_common,
            "stage17_threshold_0_35_uncalibrated": stage17_common_uncalibrated,
            "stage17_threshold_0_35_temperature_scaled": stage17_common_calibrated,
        },
        "notes": [
            "Stage 16 historical metrics and its common-test reference are leakage-affected.",
            "Stage 17 threshold 0.35 was selected on validation with temperature scaling.",
            "The uncalibrated Stage 17 result is included because production calibration is opt-in.",
            "No result is a clinical, diagnostic, prospective, external, or regulatory validation.",
        ],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output["same_grouped_test_comparison"], indent=2))


if __name__ == "__main__":
    main()
