from typing import Iterable


STRATEGIES = ("mean", "max", "top_k_mean", "positive_fraction")


def aggregate_tile_probabilities(
    probabilities: Iterable[dict],
    *,
    strategy: str,
    top_k: int = 3,
    tile_threshold: float = 0.5,
) -> dict:
    import numpy as np

    if strategy not in STRATEGIES:
        raise ValueError(f"Unsupported aggregation strategy: {strategy}")
    rows = list(probabilities)
    if not rows:
        return {
            "strategy": strategy,
            "tumor_score": 0.0,
            "mean_probabilities": {},
            "positive_tile_fraction": 0.0,
            "tile_count": 0,
        }

    matrix = np.asarray(
        [
            [
                row["no_metastasico"],
                row["metastasico"],
                row["estroma"],
            ]
            for row in rows
        ],
        dtype=float,
    )
    tumor_scores = matrix[:, 1]
    positive_fraction = float((tumor_scores >= tile_threshold).mean())
    if strategy == "mean":
        tumor_score = float(tumor_scores.mean())
    elif strategy == "max":
        tumor_score = float(tumor_scores.max())
    elif strategy == "top_k_mean":
        count = min(max(1, top_k), len(tumor_scores))
        tumor_score = float(np.sort(tumor_scores)[-count:].mean())
    else:
        tumor_score = positive_fraction
    mean_values = matrix.mean(axis=0)
    return {
        "strategy": strategy,
        "tumor_score": tumor_score,
        "mean_probabilities": {
            "no_metastasico": float(mean_values[0]),
            "metastasico": float(mean_values[1]),
            "estroma": float(mean_values[2]),
        },
        "positive_tile_fraction": positive_fraction,
        "tile_count": len(rows),
    }


def classify_roi(
    aggregation: dict,
    *,
    tumor_threshold: float,
    uncertainty_margin: float = 0.05,
    stroma_threshold: float = 0.5,
) -> dict:
    tumor_score = float(aggregation["tumor_score"])
    mean_probabilities = aggregation.get("mean_probabilities") or {}
    stroma_score = float(mean_probabilities.get("estroma", 0.0))
    if aggregation.get("tile_count", 0) == 0:
        status = "no_evaluable"
        label = "estroma_no_evaluable"
    elif abs(tumor_score - tumor_threshold) <= uncertainty_margin:
        status = "incierto"
        label = "incierto"
    elif tumor_score >= tumor_threshold:
        status = "clasificado"
        label = "metastasico"
    elif stroma_score >= stroma_threshold:
        status = "no_evaluable"
        label = "estroma_no_evaluable"
    else:
        status = "baja_sospecha"
        label = "no_metastasico"
    return {
        **aggregation,
        "status": status,
        "label": label,
        "tumor_threshold": tumor_threshold,
        "uncertainty_margin": uncertainty_margin,
    }
