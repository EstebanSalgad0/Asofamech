import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.histopathology.ml.classifier_head import BinaryClassifierHead


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate the PCam binary classifier head.")
    parser.add_argument("--embeddings", default="artifacts/histopathology/embeddings/pcam_test_embeddings.pt")
    parser.add_argument("--checkpoint", default="artifacts/histopathology/checkpoints/binary_head_pcam.pt")
    parser.add_argument("--output", default="artifacts/histopathology/reports/metrics_test.json")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    return parser.parse_args()


def load_runtime_dependencies():
    try:
        import torch
        from sklearn.metrics import (
            accuracy_score,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise SystemExit(
            "PyTorch and scikit-learn are required. "
            "Install backend/requirements-histopathology.txt first."
        ) from exc

    metrics = {
        "accuracy_score": accuracy_score,
        "confusion_matrix": confusion_matrix,
        "f1_score": f1_score,
        "precision_score": precision_score,
        "recall_score": recall_score,
        "roc_auc_score": roc_auc_score,
    }
    return torch, DataLoader, TensorDataset, metrics


def resolve_device(torch, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA was requested but torch.cuda.is_available() is false")
    return requested


def predict(torch, head, loader, device):
    head.eval()
    y_true = []
    y_pred = []
    y_score = []

    with torch.inference_mode():
        for features, labels in loader:
            features = features.to(device)
            logits = head(features)
            probabilities = torch.softmax(logits, dim=1)
            preds = torch.argmax(probabilities, dim=1).cpu()
            y_true.extend(labels.tolist())
            y_pred.extend(preds.tolist())
            y_score.extend(probabilities[:, 1].cpu().tolist())

    return y_true, y_pred, y_score


def main():
    args = parse_args()
    torch, DataLoader, TensorDataset, metrics_api = load_runtime_dependencies()
    device = resolve_device(torch, args.device)

    embeddings = torch.load(args.embeddings, map_location="cpu")
    x = embeddings["x"].float()
    y = embeddings["y"].long()

    checkpoint = torch.load(args.checkpoint, map_location=device)
    head = BinaryClassifierHead(int(checkpoint["feature_dim"])).to(device)
    head.load_state_dict(checkpoint["state_dict"])

    loader = DataLoader(TensorDataset(x, y), batch_size=args.batch_size, shuffle=False)
    y_true, y_pred, y_score = predict(torch, head, loader, device)

    roc_auc = None
    try:
        roc_auc = float(metrics_api["roc_auc_score"](y_true, y_score))
    except ValueError:
        pass

    metrics = {
        "accuracy": float(metrics_api["accuracy_score"](y_true, y_pred)),
        "precision": float(metrics_api["precision_score"](y_true, y_pred, pos_label=1, zero_division=0)),
        "recall": float(metrics_api["recall_score"](y_true, y_pred, pos_label=1, zero_division=0)),
        "f1_score": float(metrics_api["f1_score"](y_true, y_pred, pos_label=1, zero_division=0)),
        "roc_auc": roc_auc,
        "confusion_matrix": metrics_api["confusion_matrix"](y_true, y_pred).tolist(),
        "labels": checkpoint.get("labels", {"0": "no_metastasico", "1": "metastasico"}),
        "sample_count": len(y_true),
        "checkpoint": str(args.checkpoint),
        "embeddings": str(args.embeddings),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
