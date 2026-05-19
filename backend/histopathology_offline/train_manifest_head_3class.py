"""
Entrenamiento y evaluación del clasificador de 3 clases sobre embeddings CONCH.

Remapeo de etiquetas a partir del manifest:
  label=1                                    → clase 1  (metastasico)
  label=0 + hard_negative_type en STROMA_TYPES → clase 2  (estroma)
  label=0 + cualquier otro tipo              → clase 0  (no_metastasico)

Los embeddings no necesitan re-extraerse: se usan los archivos .pt existentes
junto con el manifest CSV para reconstruir el remapeo de etiquetas.
"""

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

from app.histopathology.ml.classifier_head import TriClassifierHead, TriMLPClassifierHead
from histopathology_offline.manifest_dataset import PatchManifestRow, read_manifest

STROMA_TYPES: frozenset[str] = frozenset({"stroma", "stroma_low_cellularity"})

CLASS_NAMES = {0: "no_metastasico", 1: "metastasico", 2: "estroma"}
NUM_CLASSES = 3


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Entrena un clasificador de 3 clases (no_metastasico / metastasico / estroma) "
            "sobre embeddings CONCH pre-extraídos de un manifest."
        )
    )
    parser.add_argument("--manifest", required=True, help="Manifest CSV con hard_negative_type por fila.")
    parser.add_argument(
        "--embeddings-dir",
        default="artifacts/histopathology/embeddings-hard-negative",
        help="Directorio con archivos manifest_{split}_embeddings.pt.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/histopathology/checkpoints/tri_head_manifest.pt",
        help="Ruta para guardar el checkpoint.",
    )
    parser.add_argument(
        "--report",
        default="artifacts/histopathology/reports/tri_head_metrics.json",
        help="Ruta para guardar el reporte JSON de métricas.",
    )
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--head-type", default="mlp", choices=["linear", "mlp"])
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.25)
    parser.add_argument(
        "--selection-metric",
        default="tumor_recall_minus_stroma_fp",
        choices=["val_loss", "macro_f1", "tumor_f1", "tumor_recall_minus_stroma_fp"],
        help=(
            "Criterio para escoger el mejor epoch. tumor_recall_minus_stroma_fp "
            "maximiza recall tumoral y minimiza falsos positivos de estroma."
        ),
    )
    parser.add_argument(
        "--class-weights",
        action="store_true",
        default=True,
        help="Aplicar pesos inversamente proporcionales a la frecuencia de clase.",
    )
    parser.add_argument(
        "--class-weight-power",
        type=float,
        default=0.75,
        help=(
            "Suaviza los pesos de clase. "
            "1.0 usa pesos inversos completos; 0.5 usa raiz cuadrada; 0.0 equivale a pesos uniformes."
        ),
    )
    parser.add_argument(
        "--label-smoothing",
        type=float,
        default=0.05,
        help="Suavizado de etiquetas en CrossEntropyLoss (0.0 = sin suavizado, 0.1 es un buen valor).",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=8,
        help="Early stopping: detiene el entrenamiento si el score de seleccion no mejora tras N epochs.",
    )
    parser.add_argument(
        "--lr-scheduler",
        default="cosine",
        choices=["none", "cosine", "step"],
        help="Scheduler de learning rate. cosine aplica CosineAnnealingLR; step baja lr x0.5 cada 10 epochs.",
    )
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
        )
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise SystemExit(
            "PyTorch y scikit-learn son requeridos. "
            "Instala backend/requirements-histopathology.txt primero."
        ) from exc

    metrics = {
        "accuracy_score": accuracy_score,
        "confusion_matrix": confusion_matrix,
        "f1_score": f1_score,
        "precision_score": precision_score,
        "recall_score": recall_score,
    }
    return torch, nn, DataLoader, TensorDataset, metrics


def resolve_device(torch, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA solicitado pero torch.cuda.is_available() es False.")
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


def remap_label(orig_label: int, hard_negative_type: str) -> int:
    """Convierte etiqueta binaria + tipo de negativo a clase 0/1/2."""
    if int(orig_label) == 1:
        return 1  # metastasico
    if (hard_negative_type or "") in STROMA_TYPES:
        return 2  # estroma
    return 0  # no_metastasico


def load_split(torch, manifest_rows: list[PatchManifestRow], embeddings_dir: Path, split: str):
    """
    Carga embeddings de un split y reconstruye etiquetas de 3 clases usando el manifest.

    Los embeddings están alineados con las filas del manifest en el mismo orden
    en que fueron extraídos (ManifestPatchDataset filtra por split, preservando orden).
    """
    path = embeddings_dir / f"manifest_{split}_embeddings.pt"
    if not path.exists():
        raise FileNotFoundError(f"Archivo de embeddings no encontrado: {path}")

    payload = torch.load(path, map_location="cpu")
    x = payload["x"].float()

    split_rows = [r for r in manifest_rows if r.split == split]
    if len(x) != len(split_rows):
        raise SystemExit(
            f"Desalineación en split '{split}': "
            f"{len(x)} embeddings vs {len(split_rows)} filas del manifest. "
            "Re-extrae los embeddings con extract_manifest_embeddings.py."
        )

    y_remapped = torch.tensor(
        [remap_label(r.label, r.hard_negative_type) for r in split_rows],
        dtype=torch.long,
    )
    return x, y_remapped, split_rows, path


def load_optional_split(torch, manifest_rows, embeddings_dir, split):
    path = embeddings_dir / f"manifest_{split}_embeddings.pt"
    if not path.exists():
        return None
    try:
        return load_split(torch, manifest_rows, embeddings_dir, split)
    except SystemExit:
        return None


def compute_class_weights(torch, labels, power: float = 1.0):
    counts = torch.bincount(labels, minlength=NUM_CLASSES).float()
    counts = torch.clamp(counts, min=1.0)
    total = counts.sum()
    weights = total / (NUM_CLASSES * counts)
    if power == 1.0:
        return weights
    return torch.pow(weights, power)


def build_head(head_type: str, feature_dim: int, hidden_dim: int, dropout: float):
    if head_type == "mlp":
        return TriMLPClassifierHead(feature_dim, hidden_dim=hidden_dim, dropout=dropout)
    return TriClassifierHead(feature_dim)


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
    y_true, y_pred, y_score_tumor = [], [], []
    with torch.inference_mode():
        for features, labels in loader:
            logits = head(features.to(device))
            probabilities = torch.softmax(logits, dim=1)
            preds = torch.argmax(probabilities, dim=1).cpu()
            y_true.extend(labels.tolist())
            y_pred.extend(preds.tolist())
            y_score_tumor.extend(probabilities[:, 1].cpu().tolist())
    return y_true, y_pred, y_score_tumor


def per_class_metrics(metrics_api, y_true, y_pred) -> dict:
    """Precision, recall y F1 por clase (0, 1, 2)."""
    labels = list(range(NUM_CLASSES))
    precision = metrics_api["precision_score"](y_true, y_pred, labels=labels, average=None, zero_division=0)
    recall = metrics_api["recall_score"](y_true, y_pred, labels=labels, average=None, zero_division=0)
    f1 = metrics_api["f1_score"](y_true, y_pred, labels=labels, average=None, zero_division=0)
    result = {}
    for i, name in CLASS_NAMES.items():
        result[name] = {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
        }
    return result


def stroma_tumor_confusion(metrics_api, y_true, y_pred) -> dict:
    """
    Cuantifica cuánto estroma se confunde con tumor.
    Pregunta clave: ¿Stage 3-class reduce FP de estroma→tumor?
    """
    matrix = metrics_api["confusion_matrix"](y_true, y_pred, labels=[0, 1, 2])
    total_stroma = int(matrix[2].sum())
    stroma_as_tumor = int(matrix[2][1])
    stroma_as_negative = int(matrix[2][0])
    stroma_correct = int(matrix[2][2])
    return {
        "total_stroma_samples": total_stroma,
        "stroma_predicted_as_tumor": stroma_as_tumor,
        "stroma_predicted_as_negative": stroma_as_negative,
        "stroma_predicted_correctly": stroma_correct,
        "stroma_as_tumor_rate": stroma_as_tumor / max(1, total_stroma),
    }


def tumor_threshold_sweep(y_true, y_score_tumor) -> list[dict]:
    """
    Evalua el detector tumor-vs-rest usando distintos umbrales de probabilidad.

    Esto ayuda a decidir si el modelo 3-class sirve como compuerta practica:
    por ejemplo, emitir "metastasico" solo si P(tumor) supera cierto umbral y
    dejar el resto como no_metastasico/estroma/incierto.
    """
    rows = []
    for threshold in [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
        tp = fp = tn = fn = 0
        stroma_as_tumor = 0
        total_stroma = 0
        for true_label, tumor_score in zip(y_true, y_score_tumor):
            predicted_tumor = tumor_score >= threshold
            actual_tumor = int(true_label) == 1
            if int(true_label) == 2:
                total_stroma += 1
                if predicted_tumor:
                    stroma_as_tumor += 1
            if predicted_tumor and actual_tumor:
                tp += 1
            elif predicted_tumor and not actual_tumor:
                fp += 1
            elif not predicted_tumor and actual_tumor:
                fn += 1
            else:
                tn += 1

        precision = tp / max(1, tp + fp)
        sensitivity = tp / max(1, tp + fn)
        specificity = tn / max(1, tn + fp)
        rows.append(
            {
                "threshold": threshold,
                "tumor_precision": precision,
                "tumor_sensitivity": sensitivity,
                "tumor_specificity": specificity,
                "tumor_tp": tp,
                "tumor_fp": fp,
                "tumor_fn": fn,
                "tumor_tn": tn,
                "stroma_predicted_as_tumor": stroma_as_tumor,
                "total_stroma_samples": total_stroma,
                "stroma_as_tumor_rate": stroma_as_tumor / max(1, total_stroma),
            }
        )
    return rows


def summarize_metrics(metrics_api, y_true, y_pred, y_score_tumor) -> dict:
    macro_f1 = float(
        metrics_api["f1_score"](y_true, y_pred, average="macro", zero_division=0)
    )
    accuracy = float(metrics_api["accuracy_score"](y_true, y_pred))
    matrix = metrics_api["confusion_matrix"](y_true, y_pred, labels=[0, 1, 2]).tolist()
    per_class = per_class_metrics(metrics_api, y_true, y_pred)
    stroma_conf = stroma_tumor_confusion(metrics_api, y_true, y_pred)

    # ROC-AUC solo para clase 1 (tumor) en modo OVR
    roc_auc_tumor = None
    try:
        from sklearn.metrics import roc_auc_score
        binary_true = [1 if t == 1 else 0 for t in y_true]
        val = float(roc_auc_score(binary_true, y_score_tumor))
        if math.isfinite(val):
            roc_auc_tumor = val
    except (ValueError, ImportError):
        pass

    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "roc_auc_tumor_ovr": roc_auc_tumor,
        "per_class": per_class,
        "stroma_tumor_confusion": stroma_conf,
        "tumor_threshold_sweep": tumor_threshold_sweep(y_true, y_score_tumor),
        "confusion_matrix_3x3": matrix,
        "confusion_matrix_labels": list(CLASS_NAMES.values()),
        "sample_count": len(y_true),
    }


def selection_score(metrics: dict | None, val_loss: float, selection_metric: str) -> float:
    if selection_metric == "val_loss":
        return -float(val_loss)
    if not metrics:
        return float("-inf")
    if selection_metric == "macro_f1":
        return float(metrics["macro_f1"])
    if selection_metric == "tumor_f1":
        return float(metrics["per_class"]["metastasico"]["f1"])
    if selection_metric == "tumor_recall_minus_stroma_fp":
        tumor_recall = float(metrics["per_class"]["metastasico"]["recall"])
        stroma_fp = float(metrics["stroma_tumor_confusion"]["stroma_as_tumor_rate"])
        return tumor_recall - stroma_fp
    return -float(val_loss)


def class_distribution(rows: list[PatchManifestRow]) -> dict:
    dist: dict = {name: 0 for name in CLASS_NAMES.values()}
    for row in rows:
        label = remap_label(row.label, row.hard_negative_type)
        dist[CLASS_NAMES[label]] += 1
    return dist


def main():
    args = parse_args()
    if args.epochs < 1:
        raise SystemExit("--epochs debe ser mayor a cero.")
    if args.hidden_dim < 1:
        raise SystemExit("--hidden-dim debe ser mayor a cero.")
    if not 0.0 <= args.dropout < 1.0:
        raise SystemExit("--dropout debe estar en el rango [0, 1).")
    if args.class_weight_power < 0:
        raise SystemExit("--class-weight-power debe ser mayor o igual a cero.")
    if not 0.0 <= args.label_smoothing < 0.5:
        raise SystemExit("--label-smoothing debe estar en [0, 0.5).")
    if args.patience < 1:
        raise SystemExit("--patience debe ser mayor a cero.")

    torch, nn, DataLoader, TensorDataset, metrics_api = load_runtime_dependencies()
    set_seed(torch, args.seed)
    device = resolve_device(torch, args.device)

    manifest_path = Path(args.manifest)
    embeddings_dir = Path(args.embeddings_dir)
    all_rows = read_manifest(manifest_path)

    print(f"[histopathology-3class] manifest={manifest_path} total_rows={len(all_rows)}")

    train_x, train_y, train_rows, train_path = load_split(torch, all_rows, embeddings_dir, "train")
    val_x, val_y, val_rows, val_path = load_split(torch, all_rows, embeddings_dir, "val")
    test_split = load_optional_split(torch, all_rows, embeddings_dir, "test")

    print(f"[histopathology-3class] train distribución: {class_distribution(train_rows)}")
    print(f"[histopathology-3class] val distribución:   {class_distribution(val_rows)}")
    if test_split:
        print(f"[histopathology-3class] test distribución:  {class_distribution(test_split[2])}")

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
    test_rows = []
    test_path = None
    if test_split is not None:
        test_x, test_y, test_rows, test_path = test_split
        test_loader = DataLoader(TensorDataset(test_x, test_y), batch_size=args.batch_size, shuffle=False)

    head = build_head(args.head_type, train_x.shape[1], args.hidden_dim, args.dropout).to(device)
    weight = (
        compute_class_weights(torch, train_y, args.class_weight_power).to(device)
        if args.class_weights
        else None
    )
    criterion = nn.CrossEntropyLoss(weight=weight, label_smoothing=args.label_smoothing)
    optimizer = torch.optim.AdamW(head.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    if args.lr_scheduler == "cosine":
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.lr * 0.01)
    elif args.lr_scheduler == "step":
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)
    else:
        scheduler = None

    best_state = None
    best_val_loss = float("inf")
    best_selection_score = float("-inf")
    best_epoch = None
    epochs_without_improvement = 0
    history = []

    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(head, train_loader, optimizer, criterion, device)
        val_loss = validation_loss(torch, head, val_loader, criterion, device)

        if scheduler is not None:
            scheduler.step()

        val_metrics_for_selection = None
        if args.selection_metric != "val_loss":
            val_true_epoch, val_pred_epoch, val_score_epoch = predict(torch, head, val_loader, device)
            val_metrics_for_selection = summarize_metrics(
                metrics_api,
                val_true_epoch,
                val_pred_epoch,
                val_score_epoch,
            )
        score = selection_score(val_metrics_for_selection, val_loss, args.selection_metric)
        current_lr = optimizer.param_groups[0]["lr"]
        history_row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "lr": current_lr,
            "selection_metric": args.selection_metric,
            "selection_score": score,
        }
        if val_metrics_for_selection:
            history_row["val_accuracy"] = val_metrics_for_selection["accuracy"]
            history_row["val_macro_f1"] = val_metrics_for_selection["macro_f1"]
            history_row["val_tumor_recall"] = val_metrics_for_selection["per_class"]["metastasico"]["recall"]
            history_row["val_stroma_as_tumor_rate"] = val_metrics_for_selection["stroma_tumor_confusion"][
                "stroma_as_tumor_rate"
            ]
        history.append(history_row)
        print(
            f"[histopathology-3class] epoch={epoch}/{args.epochs} "
            f"train_loss={train_loss:.4f} val_loss={val_loss:.4f} "
            f"lr={current_lr:.2e} selection_score={score:.4f}"
        )
        if score > best_selection_score:
            best_selection_score = score
            best_val_loss = val_loss
            best_epoch = epoch
            best_state = {k: v.cpu() for k, v in head.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= args.patience:
                print(
                    f"[histopathology-3class] early stopping en epoch {epoch} "
                    f"(sin mejora durante {args.patience} epochs)"
                )
                break

    head.load_state_dict(best_state)
    val_true, val_pred, val_score = predict(torch, head, val_loader, device)
    val_metrics = summarize_metrics(metrics_api, val_true, val_pred, val_score)

    test_metrics = None
    if test_loader is not None:
        y_true, y_pred, y_score = predict(torch, head, test_loader, device)
        test_metrics = summarize_metrics(metrics_api, y_true, y_pred, y_score)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_payload = {
        "state_dict": best_state,
        "feature_dim": int(train_x.shape[1]),
        "num_classes": NUM_CLASSES,
        "class_names": CLASS_NAMES,
        "head_type": args.head_type,
        "head_hidden_dim": args.hidden_dim if args.head_type == "mlp" else None,
        "head_dropout": args.dropout if args.head_type == "mlp" else None,
        "stroma_types_used": sorted(STROMA_TYPES),
        "training_mode": f"frozen_conch_{args.head_type}_probe_3class",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "validation": {
            "best_epoch": best_epoch,
            "best_val_loss": best_val_loss,
            "selection_metric": args.selection_metric,
            "best_selection_score": best_selection_score,
        },
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "seed": args.seed,
            "device": device,
            "head_type": args.head_type,
            "hidden_dim": args.hidden_dim if args.head_type == "mlp" else None,
            "dropout": args.dropout if args.head_type == "mlp" else None,
            "selection_metric": args.selection_metric,
            "class_weights": args.class_weights,
            "class_weight_power": args.class_weight_power,
            "label_smoothing": args.label_smoothing,
            "lr_scheduler": args.lr_scheduler,
            "patience": args.patience,
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
        "selection_metric": args.selection_metric,
        "best_selection_score": best_selection_score,
        "val": val_metrics,
        "test": test_metrics,
        "checkpoint": str(output),
        "manifest": str(manifest_path),
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n--- Val ---")
    print(json.dumps(val_metrics, indent=2))
    if test_metrics:
        print("\n--- Test ---")
        print(json.dumps(test_metrics, indent=2))

    print(f"\n[histopathology-3class] checkpoint guardado: {output}")
    print(f"[histopathology-3class] reporte guardado:    {report_path}")


if __name__ == "__main__":
    main()
