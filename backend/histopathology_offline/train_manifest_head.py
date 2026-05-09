import argparse
import datetime as dt
import json
import math
import random
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.histopathology.ml.classifier_head import BinaryClassifierHead


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train and evaluate a binary head over manifest-derived CONCH embeddings."
    )
    parser.add_argument("--embeddings-dir", default="artifacts/histopathology/embeddings-hard-negative")
    parser.add_argument("--output", default="artifacts/histopathology/checkpoints/binary_head_hard_negative.pt")
    parser.add_argument("--report", default="artifacts/histopathology/reports/hard_negative_metrics.json")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--class-weights", action="store_true")
    return parser.parse_args()


def load_runtime_dependencies():
    try:
        import torch
        import torch.nn as nn
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
    return torch, nn, DataLoader, TensorDataset, metrics


def resolve_device(torch, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA was requested but torch.cuda.is_available() is false")
    return requested


def set_seed(torch, seed: int) -> None:
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_embedding_split(torch, embeddings_dir: Path, split: str):
    path = embeddings_dir / f"manifest_{split}_embeddings.pt"
    if not path.exists():
        raise FileNotFoundError(f"Embeddings file not found: {path}")
    payload = torch.load(path, map_location="cpu")
    return payload["x"].float(), payload["y"].long(), payload.get("records", []), path


def load_optional_embedding_split(torch, embeddings_dir: Path, split: str):
    path = embeddings_dir / f"manifest_{split}_embeddings.pt"
    if not path.exists():
        return None
    payload = torch.load(path, map_location="cpu")
    return payload["x"].float(), payload["y"].long(), payload.get("records", []), path


def compute_class_weights(torch, labels):
    counts = torch.bincount(labels, minlength=2).float()
    counts = torch.clamp(counts, min=1.0)
    total = counts.sum()
    return total / (2.0 * counts)


def run_epoch(head, loader, optimizer, criterion, device):
    head.train()
    total_loss = 0.0
    for features, labels in loader:
        features = features.to(device)
        labels = labels.to(device)
        logits = head(features)
        loss = criterion(logits, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * features.size(0)
    return total_loss / len(loader.dataset)


def validation_loss(torch, head, loader, criterion, device):
    head.eval()
    total_loss = 0.0
    with torch.inference_mode():
        for features, labels in loader:
            features = features.to(device)
            labels = labels.to(device)
            logits = head(features)
            loss = criterion(logits, labels)
            total_loss += loss.item() * features.size(0)
    return total_loss / len(loader.dataset)


def predict(torch, head, loader, device):
    head.eval()
    y_true = []
    y_pred = []
    y_score = []
    with torch.inference_mode():
        for features, labels in loader:
            logits = head(features.to(device))
            probabilities = torch.softmax(logits, dim=1)
            preds = torch.argmax(probabilities, dim=1).cpu()
            y_true.extend(labels.tolist())
            y_pred.extend(preds.tolist())
            y_score.extend(probabilities[:, 1].cpu().tolist())
    return y_true, y_pred, y_score


def summarize_metrics(metrics_api, y_true, y_pred, y_score):
    roc_auc = None
    try:
        parsed_auc = float(metrics_api["roc_auc_score"](y_true, y_score))
        if math.isfinite(parsed_auc):
            roc_auc = parsed_auc
    except ValueError:
        pass

    return {
        "accuracy": float(metrics_api["accuracy_score"](y_true, y_pred)),
        "precision": float(metrics_api["precision_score"](y_true, y_pred, pos_label=1, zero_division=0)),
        "sensitivity_recall": float(metrics_api["recall_score"](y_true, y_pred, pos_label=1, zero_division=0)),
        "specificity": specificity(metrics_api, y_true, y_pred),
        "f1_score": float(metrics_api["f1_score"](y_true, y_pred, pos_label=1, zero_division=0)),
        "roc_auc": roc_auc,
        "confusion_matrix": metrics_api["confusion_matrix"](y_true, y_pred, labels=[0, 1]).tolist(),
        "sample_count": len(y_true),
    }


def specificity(metrics_api, y_true, y_pred) -> float:
    matrix = metrics_api["confusion_matrix"](y_true, y_pred, labels=[0, 1])
    tn = matrix[0][0]
    fp = matrix[0][1]
    denominator = tn + fp
    if denominator == 0:
        return 0.0
    return float(tn / denominator)


def hard_negative_breakdown(records, y_true, y_pred):
    buckets = {}
    for record, true_label, predicted_label in zip(records, y_true, y_pred):
        if int(true_label) != 0:
            continue
        key = record.get("hard_negative_type") or "negative_unspecified"
        bucket = buckets.setdefault(key, {"count": 0, "false_positives": 0})
        bucket["count"] += 1
        if int(predicted_label) == 1:
            bucket["false_positives"] += 1

    for bucket in buckets.values():
        count = max(bucket["count"], 1)
        bucket["false_positive_rate"] = bucket["false_positives"] / count
    return buckets


def main():
    args = parse_args()
    if args.epochs < 1:
        raise SystemExit("--epochs must be greater than zero")

    torch, nn, DataLoader, TensorDataset, metrics_api = load_runtime_dependencies()
    set_seed(torch, args.seed)
    device = resolve_device(torch, args.device)
    embeddings_dir = Path(args.embeddings_dir)

    train_x, train_y, _, train_path = load_embedding_split(torch, embeddings_dir, "train")
    val_x, val_y, _, val_path = load_embedding_split(torch, embeddings_dir, "val")
    test_split = load_optional_embedding_split(torch, embeddings_dir, "test")

    generator = torch.Generator()
    generator.manual_seed(args.seed)
    train_loader = DataLoader(
        TensorDataset(train_x, train_y),
        batch_size=args.batch_size,
        shuffle=True,
        generator=generator,
    )
    val_loader = DataLoader(TensorDataset(val_x, val_y), batch_size=args.batch_size, shuffle=False)
    test_loader = None
    test_records = []
    test_path = None
    if test_split is not None:
        test_x, test_y, test_records, test_path = test_split
        test_loader = DataLoader(TensorDataset(test_x, test_y), batch_size=args.batch_size, shuffle=False)

    head = BinaryClassifierHead(train_x.shape[1]).to(device)
    weight = compute_class_weights(torch, train_y).to(device) if args.class_weights else None
    criterion = nn.CrossEntropyLoss(weight=weight)
    optimizer = torch.optim.AdamW(head.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    best_state = None
    best_val_loss = float("inf")
    best_epoch = None
    history = []

    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(head, train_loader, optimizer, criterion, device)
        val_loss = validation_loss(torch, head, val_loader, criterion, device)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        print(f"[histopathology] epoch={epoch} train_loss={train_loss:.4f} val_loss={val_loss:.4f}")
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            best_state = {key: value.cpu() for key, value in head.state_dict().items()}

    head.load_state_dict(best_state)
    val_eval_true, val_eval_pred, val_eval_score = predict(torch, head, val_loader, device)
    val_metrics = summarize_metrics(metrics_api, val_eval_true, val_eval_pred, val_eval_score)

    test_metrics = None
    if test_loader is not None:
        y_true, y_pred, y_score = predict(torch, head, test_loader, device)
        test_metrics = summarize_metrics(metrics_api, y_true, y_pred, y_score)
        test_metrics["hard_negative_breakdown"] = hard_negative_breakdown(test_records, y_true, y_pred)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_payload = {
        "state_dict": best_state,
        "feature_dim": int(train_x.shape[1]),
        "labels": {"0": "no_metastasico", "1": "metastasico"},
        "training_mode": "frozen_conch_linear_probe_hard_negative",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "validation": {
            "best_epoch": best_epoch,
            "best_val_loss": best_val_loss,
        },
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "seed": args.seed,
            "device": device,
            "class_weights": args.class_weights,
        },
        "embedding_files": {
            "train": str(train_path),
            "val": str(val_path),
            "test": str(test_path) if test_path is not None else None,
        },
    }
    torch.save(checkpoint_payload, output)

    report = {
        "history": history,
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
        "val": val_metrics,
        "test": test_metrics,
        "checkpoint": str(output),
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"val": val_metrics, "test": test_metrics}, indent=2))
    print(f"[histopathology] saved checkpoint: {output}")
    print(f"[histopathology] saved report: {report_path}")


if __name__ == "__main__":
    main()
