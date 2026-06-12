#!/usr/bin/env python3
"""
Reporte de evaluación de modelos para tesis — ASOFAMECH Histopatología.

Lee todos los reportes JSON generados durante el entrenamiento y produce:
  - Curvas ROC con AUC (val + test)
  - Curvas Precisión-Recall (val + test)
  - Matrices de confusión 3×3 (heatmap)
  - Métricas por clase (barras agrupadas)
  - Análisis de umbral operativo
  - Curvas de entrenamiento (loss + métricas)
  - Evolución de métricas entre stages
  - Tabla comparativa de todos los modelos
  - Figura combinada (póster) para el jurado

Uso:
    cd backend/
    python histopathology_offline/generate_thesis_report.py
    python histopathology_offline/generate_thesis_report.py --best-stage 16 --output-dir artifacts/histopathology/thesis_report
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Verificar dependencias antes de importar matplotlib
# ---------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.colors import LinearSegmentedColormap
    import numpy as np
except ImportError as exc:
    print(
        f"[ERROR] Falta una dependencia: {exc}\n"
        "Instala con: pip install matplotlib numpy\n"
        "(o: pip install -r requirements-histopathology.txt)"
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paleta de colores y estilo
# ---------------------------------------------------------------------------
C_VAL       = "#1976D2"   # azul  — validación
C_TEST      = "#D32F2F"   # rojo  — test
C_TUMOR     = "#E65100"   # naranja — metastásico
C_NEG       = "#2E7D32"   # verde  — no metastásico
C_STROMA    = "#6A1B9A"   # violeta — estroma
C_GRID      = "#E0E0E0"
C_BG        = "#FAFAFA"

CMAP_CONF = LinearSegmentedColormap.from_list(
    "conf", ["#FFFFFF", "#1565C0"], N=256
)

plt.rcParams.update({
    "figure.facecolor": C_BG,
    "axes.facecolor":   C_BG,
    "axes.grid":        True,
    "grid.color":       C_GRID,
    "grid.linewidth":   0.6,
    "font.family":      "DejaVu Sans",
    "font.size":        10,
    "axes.titlesize":   11,
    "axes.labelsize":   10,
    "xtick.labelsize":  9,
    "ytick.labelsize":  9,
    "legend.fontsize":  9,
    "figure.dpi":       150,
    "savefig.dpi":      300,
    "savefig.bbox":     "tight",
})

CLASS_LABELS_ES = {
    "no_metastasico": "No metastásico",
    "metastasico":    "Metastásico",
    "estroma":        "Estroma",
}

# ---------------------------------------------------------------------------
# Utilidades de carga
# ---------------------------------------------------------------------------

DEFAULT_REPORTS_DIR  = Path("artifacts/histopathology/reports")
DEFAULT_OUTPUT_DIR   = Path("artifacts/histopathology/thesis_report")


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _stage_key(name: str) -> tuple[int, str]:
    """Clave de ordenamiento basada en el número de stage del nombre."""
    m = re.search(r"stage(\d+)", name)
    return (int(m.group(1)) if m else 0, name)


def load_tri_head_reports(reports_dir: Path) -> list[dict]:
    """
    Carga todos los reportes de modelos de 3 clases (tri_head) ordenados por stage.
    """
    paths = sorted(reports_dir.glob("tri_head_*_metrics.json"), key=lambda p: _stage_key(p.stem))
    records = []
    for p in paths:
        data = _load_json(p)
        if "val" not in data or "per_class" not in data.get("val", {}):
            continue  # ignorar reportes sin métricas 3-class
        m = re.search(r"stage(\d+)", p.stem)
        stage = int(m.group(1)) if m else 0
        label = _short_label(p.stem)
        records.append({"path": p, "stage": stage, "label": label, "data": data})
    return records


def load_binary_reports(reports_dir: Path) -> list[dict]:
    """Carga reportes de modelos binarios (stages 1-5)."""
    paths = sorted(reports_dir.glob("camelyon17_stage*_metrics.json"), key=lambda p: _stage_key(p.stem))
    records = []
    for p in paths:
        data = _load_json(p)
        if "val" not in data or "per_class" in data.get("val", {}):
            continue  # saltar si es 3-class
        m = re.search(r"stage(\d+)", p.stem)
        stage = int(m.group(1)) if m else 0
        records.append({"path": p, "stage": stage, "label": f"Binario S{stage}", "data": data})
    return records


def _short_label(stem: str) -> str:
    """Etiqueta compacta para gráficos de evolución."""
    m = re.search(r"stage(\d+)", stem)
    n = m.group(1) if m else "?"
    if "stage16" in stem:
        return f"S{n} (final)"
    if "weighted" in stem:
        return f"S{n}w"
    if "weight050" in stem:
        return f"S{n}w½"
    if "unweighted" in stem:
        return f"S{n}u"
    return f"S{n}"


# ---------------------------------------------------------------------------
# Construcción de puntos para curvas ROC / PR desde threshold_sweep
# ---------------------------------------------------------------------------

def _roc_points_from_sweep(sweep: list[dict]) -> tuple[list, list]:
    """Retorna (fpr_list, tpr_list) incluyendo los extremos (0,0) y (1,1)."""
    # Ordenar de mayor a menor umbral para trazar izquierda→derecha
    pts = sorted(sweep, key=lambda d: d["threshold"], reverse=True)
    fpr = [0.0] + [1 - p["tumor_specificity"] for p in pts] + [1.0]
    tpr = [0.0] + [p["tumor_sensitivity"]       for p in pts] + [1.0]
    return fpr, tpr


def _pr_points_from_sweep(sweep: list[dict]) -> tuple[list, list]:
    """Retorna (recall_list, precision_list) ordenados por recall creciente."""
    pts = sorted(sweep, key=lambda d: d["tumor_sensitivity"])
    recall    = [p["tumor_sensitivity"] for p in pts]
    precision = [p["tumor_precision"]   for p in pts]
    return recall, precision


def _trapz_auc(x: list, y: list) -> float:
    fn = getattr(np, "trapezoid", None) or getattr(np, "trapz", None)
    return float(fn(y, x))


# ---------------------------------------------------------------------------
# Figura 1 — Curvas ROC (modelo final, val + test)
# ---------------------------------------------------------------------------

def fig_roc_curve(report: dict, out_dir: Path) -> None:
    val_sweep  = report["data"].get("val",  {}).get("tumor_threshold_sweep", [])
    test_sweep = report["data"].get("test", {}).get("tumor_threshold_sweep", [])

    val_auc  = report["data"].get("val",  {}).get("roc_auc_tumor_ovr", None)
    test_auc = report["data"].get("test", {}).get("roc_auc_tumor_ovr", None)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.set_facecolor(C_BG)
    ax.plot([0, 1], [0, 1], "--", color="#9E9E9E", linewidth=1, label="Clasificador aleatorio")

    if val_sweep:
        fpr, tpr = _roc_points_from_sweep(val_sweep)
        auc_approx = val_auc if val_auc else _trapz_auc(fpr, tpr)
        ax.plot(fpr, tpr, color=C_VAL, linewidth=2.2,
                label=f"Validación (AUC = {auc_approx:.4f})")
        ax.scatter([1 - p["tumor_specificity"] for p in val_sweep],
                   [p["tumor_sensitivity"]     for p in val_sweep],
                   color=C_VAL, s=25, zorder=5)

    if test_sweep:
        fpr, tpr = _roc_points_from_sweep(test_sweep)
        auc_approx = test_auc if test_auc else _trapz_auc(fpr, tpr)
        ax.plot(fpr, tpr, color=C_TEST, linewidth=2.2,
                label=f"Test (AUC = {auc_approx:.4f})")
        ax.scatter([1 - p["tumor_specificity"] for p in test_sweep],
                   [p["tumor_sensitivity"]     for p in test_sweep],
                   color=C_TEST, s=25, zorder=5)

    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Tasa de Falsos Positivos (1 − Especificidad)")
    ax.set_ylabel("Sensibilidad (Recall de Tumor)")
    ax.set_title("Curva ROC — Detección de metástasis\n(Modelo final, umbral tumor OvR)")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_dir / "fig1_curva_roc.png")
    plt.close(fig)
    print("  [OK] fig1_curva_roc.png")


# ---------------------------------------------------------------------------
# Figura 2 — Curvas Precisión-Recall
# ---------------------------------------------------------------------------

def fig_pr_curve(report: dict, out_dir: Path) -> None:
    val_sweep  = report["data"].get("val",  {}).get("tumor_threshold_sweep", [])
    test_sweep = report["data"].get("test", {}).get("tumor_threshold_sweep", [])

    fig, ax = plt.subplots(figsize=(6, 5))

    if val_sweep:
        recall, precision = _pr_points_from_sweep(val_sweep)
        ap = _trapz_auc(recall, precision)
        ax.plot(recall, precision, color=C_VAL, linewidth=2.2,
                label=f"Validación (AP ≈ {ap:.4f})")
        ax.scatter(recall, precision, color=C_VAL, s=25, zorder=5)

    if test_sweep:
        recall, precision = _pr_points_from_sweep(test_sweep)
        ap = _trapz_auc(recall, precision)
        ax.plot(recall, precision, color=C_TEST, linewidth=2.2,
                label=f"Test (AP ≈ {ap:.4f})")
        ax.scatter(recall, precision, color=C_TEST, s=25, zorder=5)

    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(0.0,  1.05)
    ax.set_xlabel("Recall (Sensibilidad)")
    ax.set_ylabel("Precisión")
    ax.set_title("Curva Precisión-Recall — Clase Metastásico\n(Modelo final, umbral tumor OvR)")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(out_dir / "fig2_curva_precision_recall.png")
    plt.close(fig)
    print("  [OK]fig2_curva_precision_recall.png")


# ---------------------------------------------------------------------------
# Figura 3 — Matriz de Confusión 3×3
# ---------------------------------------------------------------------------

def fig_confusion_matrix(report: dict, out_dir: Path, split: str = "test") -> None:
    split_data = report["data"].get(split, {})
    matrix = split_data.get("confusion_matrix_3x3")
    labels = split_data.get("confusion_matrix_labels",
                            ["no_metastasico", "metastasico", "estroma"])
    if not matrix:
        print(f"  ! No hay confusion_matrix_3x3 en split '{split}', se omite.")
        return

    cm = np.array(matrix, dtype=float)
    total = cm.sum(axis=1, keepdims=True)
    cm_norm = np.where(total > 0, cm / np.where(total > 0, total, 1), 0.0)

    labels_es = [CLASS_LABELS_ES.get(l, l) for l in labels]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    for ax_idx, (data_cm, title_suffix) in enumerate([
        (cm,      " (conteos)"),
        (cm_norm, " (normalizada por fila)"),
    ]):
        ax = axes[ax_idx]
        im = ax.imshow(data_cm, cmap=CMAP_CONF,
                       vmin=0, vmax=(data_cm.max() if ax_idx == 0 else 1))
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        ax.set_xticks(range(len(labels_es)))
        ax.set_yticks(range(len(labels_es)))
        ax.set_xticklabels(labels_es, rotation=30, ha="right")
        ax.set_yticklabels(labels_es)
        ax.set_xlabel("Predicción")
        ax.set_ylabel("Real")
        ax.set_title(f"Matriz de Confusión{title_suffix}\nSplit: {split.capitalize()}")

        for i in range(len(labels)):
            for j in range(len(labels)):
                val = data_cm[i, j]
                txt = f"{val:.0f}" if ax_idx == 0 else f"{val:.2f}"
                color = "white" if val > (data_cm.max() * 0.55) else "black"
                ax.text(j, i, txt, ha="center", va="center",
                        color=color, fontsize=10, fontweight="bold")

    fig.suptitle(
        f"Modelo final (Stage 16) — {split.capitalize()}\n"
        f"Accuracy: {split_data.get('accuracy', 0):.3f} | "
        f"Macro-F1: {split_data.get('macro_f1', 0):.3f} | "
        f"ROC-AUC tumor: {split_data.get('roc_auc_tumor_ovr', 0):.3f}",
        fontsize=11, y=1.02
    )
    fig.tight_layout()
    fname = f"fig3_confusion_matrix_{split}.png"
    fig.savefig(out_dir / fname)
    plt.close(fig)
    print(f"  [OK] {fname}")


# ---------------------------------------------------------------------------
# Figura 4 — Métricas por clase (barras agrupadas)
# ---------------------------------------------------------------------------

def fig_per_class_metrics(report: dict, out_dir: Path) -> None:
    colors_cls = [C_NEG, C_TUMOR, C_STROMA]
    metric_keys = ["precision", "recall", "f1"]
    metric_labels = ["Precisión", "Recall", "F1-Score"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=False)

    for ax_i, (split, ax) in enumerate([("val", axes[0]), ("test", axes[1])]):
        per_class = report["data"].get(split, {}).get("per_class", {})
        if not per_class:
            ax.set_visible(False)
            continue

        class_names = list(per_class.keys())
        x = np.arange(len(metric_keys))
        width = 0.22
        n_classes = len(class_names)

        for ci, cls_name in enumerate(class_names):
            vals = [per_class[cls_name].get(k, 0) for k in metric_keys]
            offset = (ci - n_classes / 2 + 0.5) * width
            bars = ax.bar(x + offset, vals, width, label=CLASS_LABELS_ES.get(cls_name, cls_name),
                          color=colors_cls[ci % len(colors_cls)], alpha=0.85)
            for bar, v in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                        f"{v:.2f}", ha="center", va="bottom", fontsize=8)

        ax.set_xticks(x)
        ax.set_xticklabels(metric_labels)
        ax.set_ylim(0, 1.12)
        ax.set_ylabel("Valor")
        ax.set_title(f"Métricas por Clase — {split.capitalize()}")
        ax.legend(loc="upper right")

    fig.suptitle("Precisión, Recall y F1-Score por Clase (Modelo final Stage 16)", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_dir / "fig4_metricas_por_clase.png")
    plt.close(fig)
    print("  [OK]fig4_metricas_por_clase.png")


# ---------------------------------------------------------------------------
# Figura 5 — Análisis de umbral operativo
# ---------------------------------------------------------------------------

def fig_threshold_analysis(report: dict, out_dir: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    for split, ax in [("val", axes[0]), ("test", axes[1])]:
        sweep = report["data"].get(split, {}).get("tumor_threshold_sweep", [])
        if not sweep:
            ax.set_visible(False)
            continue

        thresholds   = [p["threshold"]           for p in sweep]
        sensitivity  = [p["tumor_sensitivity"]   for p in sweep]
        precision    = [p["tumor_precision"]      for p in sweep]
        stroma_fp    = [p["stroma_as_tumor_rate"] for p in sweep]

        ax.plot(thresholds, sensitivity, "o-", color=C_TUMOR,   linewidth=2, label="Sensibilidad (tumor)")
        ax.plot(thresholds, precision,   "s-", color=C_VAL,     linewidth=2, label="Precisión (tumor)")
        ax.plot(thresholds, stroma_fp,   "^-", color=C_STROMA,  linewidth=2, label="Tasa FP estroma")

        ax.set_xlabel("Umbral de decisión P(tumor)")
        ax.set_ylabel("Proporción")
        ax.set_ylim(-0.02, 1.1)
        ax.set_xlim(0.05, 0.95)
        ax.set_xticks([p / 10 for p in range(1, 10)])
        ax.set_title(f"Análisis de Umbral Operativo — {split.capitalize()}")
        ax.legend()
        ax.axvline(x=0.5, color="#9E9E9E", linestyle="--", linewidth=1, alpha=0.7, label="Umbral 0.5")

    fig.suptitle(
        "Impacto del Umbral de Decisión sobre Sensibilidad, Precisión y Falsos Positivos de Estroma",
        fontsize=11
    )
    fig.tight_layout()
    fig.savefig(out_dir / "fig5_analisis_umbral.png")
    plt.close(fig)
    print("  [OK]fig5_analisis_umbral.png")


# ---------------------------------------------------------------------------
# Figura 6 — Curvas de entrenamiento
# ---------------------------------------------------------------------------

def fig_training_history(report: dict, out_dir: Path) -> None:
    history = report["data"].get("history", [])
    if not history:
        print("  ! Sin historial de entrenamiento, se omite fig6.")
        return

    epochs      = [h["epoch"]       for h in history]
    train_loss  = [h["train_loss"]  for h in history]
    val_loss    = [h["val_loss"]    for h in history]

    has_extra = "val_macro_f1" in history[0]
    n_plots = 3 if has_extra else 1
    fig, axes = plt.subplots(1, n_plots, figsize=(5 * n_plots, 4))
    if n_plots == 1:
        axes = [axes]

    # Loss
    axes[0].plot(epochs, train_loss, "-",  color=C_VAL,  linewidth=2, label="Train loss")
    axes[0].plot(epochs, val_loss,   "--", color=C_TEST, linewidth=2, label="Val loss")
    best_epoch = report["data"].get("best_epoch")
    if best_epoch:
        best_val = history[best_epoch - 1]["val_loss"] if best_epoch <= len(history) else None
        if best_val:
            axes[0].axvline(x=best_epoch, color="#FF9800", linewidth=1.5,
                            linestyle=":", label=f"Mejor epoch ({best_epoch})")
    axes[0].set_xlabel("Época")
    axes[0].set_ylabel("Cross-entropy loss")
    axes[0].set_title("Curva de entrenamiento (Loss)")
    axes[0].legend()

    if has_extra:
        # Macro F1 + tumor recall
        macro_f1      = [h.get("val_macro_f1",       0) for h in history]
        tumor_recall  = [h.get("val_tumor_recall",    0) for h in history]
        axes[1].plot(epochs, macro_f1,     "-",  color=C_VAL,   linewidth=2, label="Macro-F1")
        axes[1].plot(epochs, tumor_recall, "--", color=C_TUMOR, linewidth=2, label="Recall tumor")
        axes[1].set_xlabel("Época")
        axes[1].set_ylabel("Score")
        axes[1].set_title("Métricas de validación")
        axes[1].legend()

        # Stroma FP rate
        stroma_fp = [h.get("val_stroma_as_tumor_rate", 0) for h in history]
        axes[2].plot(epochs, stroma_fp, "-", color=C_STROMA, linewidth=2, label="Estroma → tumor (FP)")
        axes[2].set_xlabel("Época")
        axes[2].set_ylabel("Tasa FP estroma")
        axes[2].set_title("Falsos positivos de estroma en validación")
        axes[2].legend()

    fig.suptitle(f"Historial de entrenamiento — Stage 16 (best epoch: {best_epoch})", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_dir / "fig6_curvas_entrenamiento.png")
    plt.close(fig)
    print("  [OK]fig6_curvas_entrenamiento.png")


# ---------------------------------------------------------------------------
# Figura 7 — Evolución de métricas entre stages (tri-head)
# ---------------------------------------------------------------------------

def fig_metrics_evolution(tri_reports: list[dict], out_dir: Path) -> None:
    labels     = []
    test_acc   = []
    test_f1    = []
    test_auc   = []
    test_tumor_f1 = []

    for r in tri_reports:
        test_data = r["data"].get("test", {})
        if not test_data:
            continue
        labels.append(r["label"])
        test_acc.append(test_data.get("accuracy", 0))
        test_f1.append(test_data.get("macro_f1", 0))
        test_auc.append(test_data.get("roc_auc_tumor_ovr", 0))
        pc = test_data.get("per_class", {})
        test_tumor_f1.append(pc.get("metastasico", {}).get("f1", 0))

    if not labels:
        print("  ! Sin datos de evolución, se omite fig7.")
        return

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 0.7), 5))

    ax.plot(x, test_acc,      "o-", color="#607D8B", linewidth=2, label="Accuracy")
    ax.plot(x, test_f1,       "s-", color=C_VAL,    linewidth=2, label="Macro-F1")
    ax.plot(x, test_auc,      "^-", color=C_TEST,   linewidth=2, label="ROC-AUC tumor")
    ax.plot(x, test_tumor_f1, "D-", color=C_TUMOR,  linewidth=2, label="F1 Metastásico")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylim(0.3, 1.05)
    ax.set_ylabel("Score (split test)")
    ax.set_title("Evolución de métricas en test — modelos 3 clases por stage de entrenamiento")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_dir / "fig7_evolucion_stages.png")
    plt.close(fig)
    print("  [OK]fig7_evolucion_stages.png")


# ---------------------------------------------------------------------------
# Figura 8 — Tabla comparativa de todos los modelos 3-class
# ---------------------------------------------------------------------------

def fig_model_comparison_table(tri_reports: list[dict], out_dir: Path) -> None:
    rows = []
    for r in tri_reports:
        test = r["data"].get("test", {})
        if not test:
            continue
        pc = test.get("per_class", {})
        stc = test.get("stroma_tumor_confusion", {})
        rows.append([
            r["label"],
            f"{test.get('accuracy',         0) or 0:.3f}",
            f"{test.get('macro_f1',         0) or 0:.3f}",
            f"{test.get('roc_auc_tumor_ovr',0) or 0:.3f}",
            f"{pc.get('metastasico',{}).get('precision',0) or 0:.3f}",
            f"{pc.get('metastasico',{}).get('recall',   0) or 0:.3f}",
            f"{pc.get('metastasico',{}).get('f1',       0) or 0:.3f}",
            f"{stc.get('stroma_as_tumor_rate', 0) or 0:.3f}",
        ])

    if not rows:
        print("  ! Sin filas para tabla, se omite fig8.")
        return

    cols = [
        "Modelo", "Accuracy", "Macro-F1", "AUC Tumor",
        "P Tumor", "R Tumor", "F1 Tumor", "FP Estroma"
    ]

    fig_h = max(3.5, len(rows) * 0.38 + 1.5)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    ax.axis("off")

    row_colors = [["#FFFFFF"] * len(cols)] * len(rows)
    for ri, row in enumerate(rows):
        # Resaltar el modelo final
        if "final" in row[0] or "stage16" in row[0].lower() or "S16" in row[0]:
            row_colors[ri] = ["#E3F2FD"] * len(cols)

    table = ax.table(
        cellText=rows,
        colLabels=cols,
        cellLoc="center",
        loc="center",
        cellColours=row_colors,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)

    # Encabezado
    for ci in range(len(cols)):
        table[0, ci].set_facecolor("#1565C0")
        table[0, ci].set_text_props(color="white", fontweight="bold")

    ax.set_title(
        "Comparativa de modelos 3-clases (split test)\n"
        "Ordenados cronológicamente por stage de entrenamiento",
        fontsize=11, pad=12
    )
    fig.tight_layout()
    fig.savefig(out_dir / "fig8_tabla_comparativa.png")
    plt.close(fig)
    print("  [OK]fig8_tabla_comparativa.png")


# ---------------------------------------------------------------------------
# Figura 9 — Panel combinado (póster para jurado)
# ---------------------------------------------------------------------------

def fig_poster(report: dict, out_dir: Path) -> None:
    """
    Panel 2×3 con las figuras más relevantes para la presentación:
    ROC | PR | Confusión
    Métricas/clase | Umbral | Entrenamiento
    """
    fig = plt.figure(figsize=(18, 11))
    gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.35)

    split_data_test = report["data"].get("test", {})
    split_data_val  = report["data"].get("val",  {})

    # ── ROC ──────────────────────────────────────────────────────────────
    ax0 = fig.add_subplot(gs[0, 0])
    ax0.plot([0, 1], [0, 1], "--", color="#9E9E9E", linewidth=1)
    for split, col, data in [("val", C_VAL, split_data_val), ("test", C_TEST, split_data_test)]:
        sweep = data.get("tumor_threshold_sweep", [])
        if sweep:
            fpr, tpr = _roc_points_from_sweep(sweep)
            auc = data.get("roc_auc_tumor_ovr") or _trapz_auc(fpr, tpr)
            ax0.plot(fpr, tpr, color=col, linewidth=2, label=f"{split} AUC={auc:.3f}")
    ax0.set_xlim(-0.02, 1.02); ax0.set_ylim(-0.02, 1.02)
    ax0.set_xlabel("FPR"); ax0.set_ylabel("TPR")
    ax0.set_title("Curva ROC")
    ax0.legend(fontsize=8)

    # ── PR ───────────────────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 1])
    for split, col, data in [("val", C_VAL, split_data_val), ("test", C_TEST, split_data_test)]:
        sweep = data.get("tumor_threshold_sweep", [])
        if sweep:
            rec, prec = _pr_points_from_sweep(sweep)
            ap = _trapz_auc(rec, prec)
            ax1.plot(rec, prec, color=col, linewidth=2, label=f"{split} AP={ap:.3f}")
    ax1.set_xlim(-0.02, 1.02); ax1.set_ylim(0, 1.08)
    ax1.set_xlabel("Recall"); ax1.set_ylabel("Precisión")
    ax1.set_title("Curva Precisión-Recall")
    ax1.legend(fontsize=8)

    # ── Confusión ─────────────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 2])
    matrix = split_data_test.get("confusion_matrix_3x3")
    labels = split_data_test.get("confusion_matrix_labels",
                                 ["no_metastasico", "metastasico", "estroma"])
    if matrix:
        cm = np.array(matrix, dtype=float)
        total = cm.sum(axis=1, keepdims=True)
        cm_n  = np.where(total > 0, cm / np.where(total > 0, total, 1), 0.0)
        im = ax2.imshow(cm_n, cmap=CMAP_CONF, vmin=0, vmax=1)
        fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
        lbls = [CLASS_LABELS_ES.get(l, l) for l in labels]
        ax2.set_xticks(range(3)); ax2.set_yticks(range(3))
        ax2.set_xticklabels(lbls, rotation=20, ha="right", fontsize=8)
        ax2.set_yticklabels(lbls, fontsize=8)
        for i in range(3):
            for j in range(3):
                col_txt = "white" if cm_n[i, j] > 0.5 else "black"
                ax2.text(j, i, f"{cm_n[i,j]:.2f}\n({int(cm[i,j])})",
                         ha="center", va="center", color=col_txt, fontsize=8)
    ax2.set_title("Matriz de Confusión (test, normalizada)")
    ax2.set_xlabel("Predicción"); ax2.set_ylabel("Real")

    # ── Métricas por clase ────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    pc   = split_data_test.get("per_class", {})
    cls_keys  = list(pc.keys())
    met_keys  = ["precision", "recall", "f1"]
    met_lbls  = ["Prec.", "Recall", "F1"]
    colors_c  = [C_NEG, C_TUMOR, C_STROMA]
    x = np.arange(len(met_keys)); w = 0.22
    for ci, cls in enumerate(cls_keys):
        vals = [pc[cls].get(k, 0) for k in met_keys]
        off  = (ci - len(cls_keys) / 2 + 0.5) * w
        ax3.bar(x + off, vals, w, label=CLASS_LABELS_ES.get(cls, cls),
                color=colors_c[ci % 3], alpha=0.85)
    ax3.set_xticks(x); ax3.set_xticklabels(met_lbls)
    ax3.set_ylim(0, 1.12); ax3.set_ylabel("Score")
    ax3.set_title("Métricas por clase (test)")
    ax3.legend(fontsize=8)

    # ── Umbral ────────────────────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    sweep = split_data_test.get("tumor_threshold_sweep", [])
    if sweep:
        thr = [p["threshold"]           for p in sweep]
        ax4.plot(thr, [p["tumor_sensitivity"]   for p in sweep], "o-", color=C_TUMOR,  linewidth=2, label="Sensibilidad")
        ax4.plot(thr, [p["tumor_precision"]     for p in sweep], "s-", color=C_VAL,    linewidth=2, label="Precisión")
        ax4.plot(thr, [p["stroma_as_tumor_rate"]for p in sweep], "^-", color=C_STROMA, linewidth=2, label="FP estroma")
        ax4.axvline(x=0.5, color="#9E9E9E", linestyle="--", linewidth=1)
    ax4.set_xlabel("Umbral P(tumor)"); ax4.set_ylabel("Proporción")
    ax4.set_title("Análisis de umbral operativo (test)")
    ax4.legend(fontsize=8)

    # ── Entrenamiento ─────────────────────────────────────────────────────
    ax5 = fig.add_subplot(gs[1, 2])
    history = report["data"].get("history", [])
    if history:
        eps = [h["epoch"]      for h in history]
        ax5.plot(eps, [h["train_loss"] for h in history], "-",  color=C_VAL,  linewidth=2, label="Train loss")
        ax5.plot(eps, [h["val_loss"]   for h in history], "--", color=C_TEST, linewidth=2, label="Val loss")
        be = report["data"].get("best_epoch")
        if be:
            ax5.axvline(x=be, color="#FF9800", linewidth=1.5, linestyle=":", label=f"Mejor epoch {be}")
    ax5.set_xlabel("Época"); ax5.set_ylabel("Loss")
    ax5.set_title("Curva de entrenamiento")
    ax5.legend(fontsize=8)

    # ── Título global ─────────────────────────────────────────────────────
    acc  = split_data_test.get("accuracy",         0)
    mf1  = split_data_test.get("macro_f1",         0)
    auc  = split_data_test.get("roc_auc_tumor_ovr",0)
    fig.suptitle(
        f"Evaluación completa — Modelo final (Stage 16, 3 clases)\n"
        f"Test: Accuracy={acc:.3f} | Macro-F1={mf1:.3f} | AUC Tumor={auc:.3f}",
        fontsize=13, fontweight="bold", y=1.01
    )
    fig.savefig(out_dir / "fig0_poster_jurado.png")
    plt.close(fig)
    print("  [OK] fig0_poster_jurado.png  <-- FIGURA PRINCIPAL PARA EL JURADO")


# ---------------------------------------------------------------------------
# Resumen JSON + CSV
# ---------------------------------------------------------------------------

def save_summary(tri_reports: list[dict], out_dir: Path) -> None:
    rows = []
    for r in tri_reports:
        entry = {"model": r["label"], "stage": r["stage"]}
        for split in ("val", "test"):
            sd = r["data"].get(split, {})
            if not sd:
                continue
            pc  = sd.get("per_class", {})
            stc = sd.get("stroma_tumor_confusion", {})
            entry[f"{split}_accuracy"]         = round(sd.get("accuracy",         0) or 0, 4)
            entry[f"{split}_macro_f1"]         = round(sd.get("macro_f1",         0) or 0, 4)
            entry[f"{split}_roc_auc_tumor"]    = round(sd.get("roc_auc_tumor_ovr",0) or 0, 4)
            entry[f"{split}_tumor_precision"]  = round(pc.get("metastasico",{}).get("precision",0) or 0, 4)
            entry[f"{split}_tumor_recall"]     = round(pc.get("metastasico",{}).get("recall",   0) or 0, 4)
            entry[f"{split}_tumor_f1"]         = round(pc.get("metastasico",{}).get("f1",       0) or 0, 4)
            entry[f"{split}_stroma_fp_rate"]   = round(stc.get("stroma_as_tumor_rate", 0) or 0, 4)
        rows.append(entry)

    # JSON
    json_path = out_dir / "metrics_summary.json"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [OK] metrics_summary.json ({len(rows)} modelos)")

    # CSV
    if rows:
        import csv
        csv_path = out_dir / "metrics_summary.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print("  [OK] metrics_summary.csv")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR,
        help="Directorio con los reportes JSON (default: %(default)s)",
    )
    p.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="Directorio de salida para figuras y resumen (default: %(default)s)",
    )
    p.add_argument(
        "--best-stage", type=str, default="stage16",
        help="Nombre parcial del stage del mejor modelo para figuras principales (default: %(default)s)",
    )
    return p.parse_args()


def find_best_report(tri_reports: list[dict], best_stage: str) -> dict | None:
    for r in reversed(tri_reports):
        if best_stage.lower() in r["data"].get("checkpoint", "").lower():
            return r
        if best_stage.lower() in r["path"].stem.lower():
            return r
    return tri_reports[-1] if tri_reports else None


def main() -> None:
    args = parse_args()

    reports_dir: Path = args.reports_dir
    output_dir:  Path = args.output_dir

    if not reports_dir.exists():
        print(f"[ERROR] No existe el directorio de reportes: {reports_dir}")
        print("  Asegúrate de ejecutar el script desde la raíz del directorio backend/")
        sys.exit(1)

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print("  Reporte de evaluación para tesis — ASOFAMECH Histopatología")
    print(f"{'='*60}")
    print(f"  Reportes: {reports_dir}")
    print(f"  Salida:   {figures_dir}\n")

    # ── Cargar datos ──────────────────────────────────────────────────────
    tri_reports = load_tri_head_reports(reports_dir)
    print(f"Modelos 3-clases cargados: {len(tri_reports)}")

    best = find_best_report(tri_reports, args.best_stage)
    if not best:
        print("[ERROR] No se encontró ningún reporte de modelo 3-clases.")
        sys.exit(1)
    print(f"Modelo principal para figuras: {best['path'].name}\n")

    # ── Generar figuras ───────────────────────────────────────────────────
    print("Generando figuras:")
    fig_roc_curve(best, figures_dir)
    fig_pr_curve(best, figures_dir)
    fig_confusion_matrix(best, figures_dir, split="test")
    fig_confusion_matrix(best, figures_dir, split="val")
    fig_per_class_metrics(best, figures_dir)
    fig_threshold_analysis(best, figures_dir)
    fig_training_history(best, figures_dir)
    fig_metrics_evolution(tri_reports, figures_dir)
    fig_model_comparison_table(tri_reports, figures_dir)
    fig_poster(best, figures_dir)

    # ── Resumen ──────────────────────────────────────────────────────────
    print("\nGenerando resumen de métricas:")
    save_summary(tri_reports, output_dir)

    print(f"\n{'='*60}")
    print(f"  Reporte generado en: {output_dir.resolve()}")
    print(f"  Figuras:             {figures_dir.resolve()}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
