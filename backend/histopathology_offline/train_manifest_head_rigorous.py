import argparse
import csv
import datetime as dt
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.histopathology.ml.classifier_head import TriMLPClassifierHead
from histopathology_offline.rigorous_evaluation import (
    calibration_metrics,
    classification_metrics,
    fit_temperature,
    recommend_threshold,
    save_confusion_matrix,
    save_reliability_diagram,
    softmax_with_temperature,
    threshold_metrics_at,
    threshold_sweep,
)


CLASS_NAMES = {0: "no_metastasico", 1: "metastasico", 2: "estroma"}
STROMA_TYPES = {"stroma", "stroma_low_cellularity"}
NUM_CLASSES = 3


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train a reproducible frozen-CONCH MLP head without using test for model selection."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--embeddings-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--figures-dir", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=20260607)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.25)
    parser.add_argument("--label-smoothing", type=float, default=0.05)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument(
        "--balance-strategy",
        default="none",
        choices=["none", "class_weights", "oversample", "focal"],
    )
    parser.add_argument("--class-weight-power", type=float, default=0.75)
    parser.add_argument("--focal-gamma", type=float, default=2.0)
    parser.add_argument("--minimum-tumor-precision", type=float, default=0.85)
    return parser.parse_args()


def remap_record(record: dict) -> int:
    if int(record.get("label", 0)) == 1:
        return 1
    if (record.get("hard_negative_type") or "") in STROMA_TYPES:
        return 2
    return 0


def load_split(torch, embeddings_dir: Path, split: str):
    path = embeddings_dir / f"manifest_{split}_embeddings.pt"
    if not path.exists():
        raise FileNotFoundError(path)
    payload = torch.load(path, map_location="cpu")
    features = payload["x"].float()
    records = payload.get("records") or []
    if len(features) != len(records):
        raise SystemExit(f"{path}: {len(features)} embeddings vs {len(records)} records.")
    labels = torch.tensor([remap_record(record) for record in records], dtype=torch.long)
    return features, labels, records, path, payload.get("metadata") or {}


def set_seed(torch, seed: int):
    import numpy as np

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def class_weights(torch, labels, power: float):
    counts = torch.bincount(labels, minlength=NUM_CLASSES).float().clamp(min=1)
    inverse = counts.sum() / (NUM_CLASSES * counts)
    return inverse.pow(power)


def distribution(labels) -> dict:
    counts = Counter(int(value) for value in labels.tolist())
    return {CLASS_NAMES[index]: counts.get(index, 0) for index in range(NUM_CLASSES)}


class FocalLoss:
    def __init__(self, torch, weight, gamma: float, label_smoothing: float):
        self.torch = torch
        self.weight = weight
        self.gamma = gamma
        self.label_smoothing = label_smoothing

    def __call__(self, logits, labels):
        losses = self.torch.nn.functional.cross_entropy(
            logits,
            labels,
            weight=self.weight,
            label_smoothing=self.label_smoothing,
            reduction="none",
        )
        probability = self.torch.exp(-losses)
        return (((1.0 - probability) ** self.gamma) * losses).mean()


def predict(torch, head, loader, device):
    head.eval()
    labels = []
    logits = []
    with torch.inference_mode():
        for features, batch_labels in loader:
            batch_logits = head(features.to(device))
            labels.extend(batch_labels.tolist())
            logits.extend(batch_logits.cpu().tolist())
    return labels, logits


def selection_score(metrics: dict) -> float:
    tumor_recall = metrics["per_class"]["metastasico"]["recall"]
    matrix = metrics["confusion_matrix_3x3"]
    stroma_total = max(1, sum(matrix[2]))
    stroma_as_tumor = matrix[2][1] / stroma_total
    return float(tumor_recall - stroma_as_tumor)


def save_loss_plot(history: list[dict], output_path: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.plot([row["epoch"] for row in history], [row["train_loss"] for row in history], label="train")
    axis.plot([row["epoch"] for row in history], [row["val_loss"] for row in history], label="validation")
    axis.set(xlabel="Epoch", ylabel="Loss", title="Curvas de pérdida")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def write_predictions(path: Path, records, labels, probabilities):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "patch_id",
                "slide_id",
                "x",
                "y",
                "true_class",
                "predicted_class",
                "p_no_metastasico",
                "p_metastasico",
                "p_estroma",
            ],
        )
        writer.writeheader()
        for record, label, probability in zip(records, labels, probabilities):
            predicted = int(probability.argmax())
            writer.writerow(
                {
                    "patch_id": record.get("patch_id"),
                    "slide_id": record.get("slide_id"),
                    "x": record.get("x"),
                    "y": record.get("y"),
                    "true_class": CLASS_NAMES[int(label)],
                    "predicted_class": CLASS_NAMES[predicted],
                    "p_no_metastasico": float(probability[0]),
                    "p_metastasico": float(probability[1]),
                    "p_estroma": float(probability[2]),
                }
            )


def main():
    args = parse_args()
    import numpy as np
    import torch
    from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

    set_seed(torch, args.seed)
    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    if device == "auto":
        device = "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA requested but unavailable.")

    embeddings_dir = Path(args.embeddings_dir)
    train_x, train_y, train_records, train_path, train_metadata = load_split(torch, embeddings_dir, "train")
    val_x, val_y, val_records, val_path, val_metadata = load_split(torch, embeddings_dir, "val")
    test_x, test_y, test_records, test_path, test_metadata = load_split(torch, embeddings_dir, "test")

    generator = torch.Generator().manual_seed(args.seed)
    sampler = None
    shuffle = True
    weights = class_weights(torch, train_y, args.class_weight_power)
    if args.balance_strategy == "oversample":
        sample_weights = weights[train_y]
        sampler = WeightedRandomSampler(
            sample_weights,
            num_samples=len(sample_weights),
            replacement=True,
            generator=generator,
        )
        shuffle = False

    train_loader = DataLoader(
        TensorDataset(train_x, train_y),
        batch_size=args.batch_size,
        shuffle=shuffle,
        sampler=sampler,
        generator=generator if shuffle else None,
    )
    val_loader = DataLoader(TensorDataset(val_x, val_y), batch_size=args.batch_size)
    test_loader = DataLoader(TensorDataset(test_x, test_y), batch_size=args.batch_size)

    head = TriMLPClassifierHead(
        int(train_x.shape[1]),
        hidden_dim=args.hidden_dim,
        dropout=args.dropout,
    ).to(device)
    loss_weights = weights.to(device) if args.balance_strategy in {"class_weights", "focal"} else None
    if args.balance_strategy == "focal":
        criterion = FocalLoss(
            torch,
            weight=loss_weights,
            gamma=args.focal_gamma,
            label_smoothing=args.label_smoothing,
        )
    else:
        criterion = torch.nn.CrossEntropyLoss(
            weight=loss_weights,
            label_smoothing=args.label_smoothing,
        )

    optimizer = torch.optim.AdamW(head.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=args.epochs,
        eta_min=args.lr * 0.01,
    )
    history = []
    best_state = None
    best_epoch = 0
    best_score = float("-inf")
    best_val_loss = float("inf")
    stale_epochs = 0

    for epoch in range(1, args.epochs + 1):
        head.train()
        train_total = 0.0
        for features, labels in train_loader:
            features = features.to(device)
            labels = labels.to(device)
            optimizer.zero_grad()
            loss = criterion(head(features), labels)
            loss.backward()
            optimizer.step()
            train_total += float(loss.item()) * len(labels)

        head.eval()
        val_total = 0.0
        with torch.inference_mode():
            for features, labels in val_loader:
                features = features.to(device)
                labels = labels.to(device)
                val_total += float(criterion(head(features), labels).item()) * len(labels)
        scheduler.step()

        val_labels_epoch, val_logits_epoch = predict(torch, head, val_loader, device)
        val_probabilities_epoch = softmax_with_temperature(val_logits_epoch, 1.0)
        val_metrics_epoch = classification_metrics(val_labels_epoch, val_probabilities_epoch)
        score = selection_score(val_metrics_epoch)
        train_loss = train_total / len(train_y)
        val_loss = val_total / len(val_y)
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "selection_score": score,
                "val_macro_f1": val_metrics_epoch["macro_f1"],
                "val_tumor_recall": val_metrics_epoch["per_class"]["metastasico"]["recall"],
                "lr": optimizer.param_groups[0]["lr"],
            }
        )
        print(
            f"[rigorous:{args.variant}] epoch={epoch} train_loss={train_loss:.4f} "
            f"val_loss={val_loss:.4f} score={score:.4f}",
            flush=True,
        )
        if score > best_score:
            best_score = score
            best_epoch = epoch
            best_val_loss = val_loss
            best_state = {key: value.detach().cpu() for key, value in head.state_dict().items()}
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= args.patience:
                break

    head.load_state_dict(best_state)
    val_labels, val_logits = predict(torch, head, val_loader, device)
    test_labels, test_logits = predict(torch, head, test_loader, device)
    temperature = fit_temperature(val_logits, val_labels)
    val_before = softmax_with_temperature(val_logits, 1.0)
    val_after = softmax_with_temperature(val_logits, temperature)
    test_before = softmax_with_temperature(test_logits, 1.0)
    test_after = softmax_with_temperature(test_logits, temperature)

    val_sweep = threshold_sweep(val_labels, val_after)
    operating_threshold = recommend_threshold(
        val_sweep,
        minimum_precision=args.minimum_tumor_precision,
    )
    locked_threshold = operating_threshold["threshold"]
    figures_dir = Path(args.figures_dir)
    val_metrics = classification_metrics(val_labels, val_after)
    test_metrics = classification_metrics(test_labels, test_after)
    val_calibration_before = calibration_metrics(val_labels, val_before)
    val_calibration_after = calibration_metrics(val_labels, val_after)
    test_calibration_before = calibration_metrics(test_labels, test_before)
    test_calibration_after = calibration_metrics(test_labels, test_after)

    save_loss_plot(history, figures_dir / "loss_curves.png")
    save_reliability_diagram(
        val_calibration_before,
        val_calibration_after,
        figures_dir / "reliability_validation.png",
    )
    save_confusion_matrix(
        val_metrics["confusion_matrix_3x3"],
        val_metrics["confusion_matrix_labels"],
        figures_dir / "confusion_validation.png",
        "Matriz de confusión - validación",
    )
    save_confusion_matrix(
        test_metrics["confusion_matrix_3x3"],
        test_metrics["confusion_matrix_labels"],
        figures_dir / "confusion_test.png",
        "Matriz de confusión - test independiente",
    )
    write_predictions(figures_dir / "predictions_validation.csv", val_records, val_labels, val_after)
    write_predictions(figures_dir / "predictions_test.csv", test_records, test_labels, test_after)

    created_at = dt.datetime.now(dt.timezone.utc).isoformat()
    checkpoint = {
        "state_dict": best_state,
        "feature_dim": int(train_x.shape[1]),
        "num_classes": NUM_CLASSES,
        "class_names": CLASS_NAMES,
        "head_type": "mlp",
        "head_hidden_dim": args.hidden_dim,
        "head_dropout": args.dropout,
        "stroma_types_used": sorted(STROMA_TYPES),
        "training_mode": "frozen_conch_mlp_probe_3class_rigorous",
        "created_at": created_at,
        "variant": args.variant,
        "calibration": {
            "method": "temperature_scaling",
            "temperature": temperature,
            "fit_split": "validation",
        },
        "operating_threshold": {
            **operating_threshold,
            "locked_test_metrics": threshold_metrics_at(test_labels, test_after, locked_threshold),
        },
        "validation": {
            "best_epoch": best_epoch,
            "best_val_loss": best_val_loss,
            "selection_metric": "tumor_recall_minus_stroma_as_tumor",
            "best_selection_score": best_score,
        },
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "seed": args.seed,
            "device": device,
            "hidden_dim": args.hidden_dim,
            "dropout": args.dropout,
            "label_smoothing": args.label_smoothing,
            "patience": args.patience,
            "balance_strategy": args.balance_strategy,
            "class_weight_power": args.class_weight_power,
            "focal_gamma": args.focal_gamma,
        },
        "embedding_files": {
            "train": str(train_path),
            "val": str(val_path),
            "test": str(test_path),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, output)

    report = {
        "variant": args.variant,
        "created_at": created_at,
        "manifest": args.manifest,
        "checkpoint": str(output),
        "data_distribution": {
            "train": distribution(train_y),
            "validation": distribution(val_y),
            "test": distribution(test_y),
        },
        "embedding_metadata": {
            "train": train_metadata,
            "validation": val_metadata,
            "test": test_metadata,
        },
        "balance_strategy": args.balance_strategy,
        "class_weights": weights.tolist(),
        "history": history,
        "best_epoch": best_epoch,
        "temperature": temperature,
        "operating_threshold_selected_on_validation": operating_threshold,
        "validation": {
            "classification": val_metrics,
            "calibration_before": val_calibration_before,
            "calibration_after": val_calibration_after,
            "threshold_sweep": val_sweep,
        },
        "test": {
            "classification": test_metrics,
            "calibration_before": test_calibration_before,
            "calibration_after": test_calibration_after,
            "locked_threshold_metrics": threshold_metrics_at(test_labels, test_after, locked_threshold),
            "threshold_sweep_for_reporting_only": threshold_sweep(test_labels, test_after),
        },
        "methodological_scope": (
            "Internal technical evaluation on a patient-grouped split. "
            "Not clinical, diagnostic, prospective, external, or regulatory validation."
        ),
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"test": test_metrics, "threshold": operating_threshold, "temperature": temperature}, indent=2))


if __name__ == "__main__":
    main()
