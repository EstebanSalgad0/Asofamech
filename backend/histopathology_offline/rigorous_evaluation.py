import math
from pathlib import Path


CLASS_NAMES = ("no_metastasico", "metastasico", "estroma")


def softmax_with_temperature(logits, temperature: float):
    import numpy as np

    values = np.asarray(logits, dtype=float) / max(float(temperature), 1e-6)
    values -= values.max(axis=1, keepdims=True)
    exp_values = np.exp(values)
    return exp_values / exp_values.sum(axis=1, keepdims=True)


def fit_temperature(logits, labels) -> float:
    import torch

    logits_tensor = torch.as_tensor(logits, dtype=torch.float32)
    labels_tensor = torch.as_tensor(labels, dtype=torch.long)
    log_temperature = torch.zeros(1, requires_grad=True)
    optimizer = torch.optim.LBFGS([log_temperature], lr=0.05, max_iter=100)
    criterion = torch.nn.CrossEntropyLoss()

    def closure():
        optimizer.zero_grad()
        temperature = torch.exp(log_temperature).clamp(0.05, 10.0)
        loss = criterion(logits_tensor / temperature, labels_tensor)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(torch.exp(log_temperature.detach()).clamp(0.05, 10.0).item())


def expected_calibration_error(labels, probabilities, bins: int = 10) -> float:
    import numpy as np

    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    confidence = probabilities.max(axis=1)
    predictions = probabilities.argmax(axis=1)
    correctness = predictions == labels
    edges = np.linspace(0.0, 1.0, bins + 1)
    value = 0.0
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        selected = (confidence > lower) & (confidence <= upper)
        if selected.any():
            value += selected.mean() * abs(correctness[selected].mean() - confidence[selected].mean())
    return float(value)


def reliability_bins(labels, probabilities, bins: int = 10) -> list[dict]:
    import numpy as np

    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    confidence = probabilities.max(axis=1)
    predictions = probabilities.argmax(axis=1)
    correctness = predictions == labels
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows = []
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        selected = (confidence > lower) & (confidence <= upper)
        rows.append(
            {
                "lower": float(lower),
                "upper": float(upper),
                "count": int(selected.sum()),
                "mean_confidence": float(confidence[selected].mean()) if selected.any() else None,
                "accuracy": float(correctness[selected].mean()) if selected.any() else None,
            }
        )
    return rows


def calibration_metrics(labels, probabilities, bins: int = 10) -> dict:
    import numpy as np
    from sklearn.metrics import log_loss

    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    one_hot = np.eye(probabilities.shape[1])[labels]
    tumor_true = (labels == 1).astype(float)
    return {
        "multiclass_brier": float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1))),
        "tumor_ovr_brier": float(np.mean((probabilities[:, 1] - tumor_true) ** 2)),
        "expected_calibration_error": expected_calibration_error(labels, probabilities, bins=bins),
        "negative_log_likelihood": float(log_loss(labels, probabilities, labels=list(range(probabilities.shape[1])))),
        "reliability_bins": reliability_bins(labels, probabilities, bins=bins),
    }


def threshold_sweep(labels, probabilities, thresholds=None) -> list[dict]:
    import numpy as np

    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    tumor_true = labels == 1
    confidence = probabilities.max(axis=1)
    thresholds = thresholds or [round(value * 0.05, 2) for value in range(1, 20)]
    rows = []
    for threshold in thresholds:
        tumor_pred = probabilities[:, 1] >= threshold
        tp = int((tumor_pred & tumor_true).sum())
        fp = int((tumor_pred & ~tumor_true).sum())
        fn = int((~tumor_pred & tumor_true).sum())
        tn = int((~tumor_pred & ~tumor_true).sum())
        precision = tp / max(1, tp + fp)
        sensitivity = tp / max(1, tp + fn)
        specificity = tn / max(1, tn + fp)
        f1 = 2 * precision * sensitivity / max(1e-12, precision + sensitivity)
        rows.append(
            {
                "threshold": float(threshold),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "sensitivity": sensitivity,
                "specificity": specificity,
                "f1": f1,
                "balanced_accuracy": (sensitivity + specificity) / 2.0,
                "abstention_rate": float((confidence < threshold).mean()),
            }
        )
    return rows


def recommend_threshold(rows: list[dict], minimum_precision: float = 0.85) -> dict:
    eligible = [row for row in rows if row["precision"] >= minimum_precision]
    candidates = eligible or rows
    selected = max(
        candidates,
        key=lambda row: (row["f1"], row["balanced_accuracy"], row["sensitivity"], -row["threshold"]),
    )
    return {
        **selected,
        "selection_set": "precision_constraint" if eligible else "all_thresholds",
        "minimum_precision": minimum_precision,
        "selected_on": "validation",
    }


def classification_metrics(labels, probabilities) -> dict:
    import numpy as np
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
        roc_auc_score,
    )

    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    predictions = probabilities.argmax(axis=1)
    report = classification_report(
        labels,
        predictions,
        labels=[0, 1, 2],
        target_names=list(CLASS_NAMES),
        output_dict=True,
        zero_division=0,
    )
    tumor_true = (labels == 1).astype(int)
    tumor_auc = None
    if len(set(tumor_true.tolist())) == 2:
        tumor_auc = float(roc_auc_score(tumor_true, probabilities[:, 1]))
    multiclass_auc = None
    try:
        multiclass_auc = float(roc_auc_score(labels, probabilities, multi_class="ovr", average="macro"))
    except ValueError:
        pass
    return {
        "sample_count": int(len(labels)),
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro_f1": float(f1_score(labels, predictions, average="macro", zero_division=0)),
        "roc_auc_tumor_ovr": tumor_auc,
        "roc_auc_macro_ovr": multiclass_auc,
        "confusion_matrix_3x3": confusion_matrix(labels, predictions, labels=[0, 1, 2]).tolist(),
        "confusion_matrix_labels": list(CLASS_NAMES),
        "per_class": {
            name: {
                "precision": float(report[name]["precision"]),
                "recall": float(report[name]["recall"]),
                "f1": float(report[name]["f1-score"]),
                "support": int(report[name]["support"]),
            }
            for name in CLASS_NAMES
        },
    }


def threshold_metrics_at(labels, probabilities, threshold: float) -> dict:
    rows = threshold_sweep(labels, probabilities, thresholds=[threshold])
    return rows[0]


def save_reliability_diagram(before: dict, after: dict, output_path: str | Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(6, 6))
    axis.plot([0, 1], [0, 1], linestyle="--", color="black", label="Calibración ideal")
    for label, payload, color in (
        ("Antes", before, "#dc2626"),
        ("Temperature scaling", after, "#2563eb"),
    ):
        points = [
            row
            for row in payload["reliability_bins"]
            if row["mean_confidence"] is not None
        ]
        axis.plot(
            [row["mean_confidence"] for row in points],
            [row["accuracy"] for row in points],
            marker="o",
            color=color,
            label=label,
        )
    axis.set(xlabel="Confianza media", ylabel="Exactitud observada", xlim=(0, 1), ylim=(0, 1))
    axis.set_title("Diagrama de confiabilidad (validación)")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def save_confusion_matrix(matrix, labels, output_path: str | Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    matrix = np.asarray(matrix)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(6, 5))
    image = axis.imshow(matrix, cmap="Blues")
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(column, row, str(matrix[row, column]), ha="center", va="center")
    axis.set_xticks(range(len(labels)), labels, rotation=25, ha="right")
    axis.set_yticks(range(len(labels)), labels)
    axis.set(xlabel="Predicción", ylabel="Etiqueta", title=title)
    figure.colorbar(image, ax=axis)
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def finite_or_none(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None
