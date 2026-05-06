import argparse
import json
from pathlib import Path

import torch
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, TensorDataset

from app.histopathology.ml.classifier_head import BinaryClassifierHead


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate the PCam binary classifier head.")
    parser.add_argument("--embeddings", default="artifacts/histopathology/embeddings/pcam_test_embeddings.pt")
    parser.add_argument("--checkpoint", default="artifacts/histopathology/checkpoints/binary_head_pcam.pt")
    parser.add_argument("--output", default="artifacts/histopathology/reports/metrics_test.json")
    parser.add_argument("--batch-size", type=int, default=256)
    return parser.parse_args()


@torch.inference_mode()
def predict(head, loader, device):
    head.eval()
    y_true = []
    y_pred = []

    for features, labels in loader:
        features = features.to(device)
        logits = head(features)
        preds = torch.argmax(logits, dim=1).cpu()
        y_true.extend(labels.tolist())
        y_pred.extend(preds.tolist())

    return y_true, y_pred


def main():
    args = parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    embeddings = torch.load(args.embeddings, map_location="cpu")
    x = embeddings["x"].float()
    y = embeddings["y"].long()

    checkpoint = torch.load(args.checkpoint, map_location=device)
    head = BinaryClassifierHead(int(checkpoint["feature_dim"])).to(device)
    head.load_state_dict(checkpoint["state_dict"])

    loader = DataLoader(TensorDataset(x, y), batch_size=args.batch_size, shuffle=False)
    y_true, y_pred = predict(head, loader, device)

    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, pos_label=1),
        "recall": recall_score(y_true, y_pred, pos_label=1),
        "f1_score": f1_score(y_true, y_pred, pos_label=1),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "labels": checkpoint.get("labels", {"0": "no_metastasico", "1": "metastasico"}),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

