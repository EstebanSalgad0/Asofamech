import math
import os
from collections import deque
from typing import Any, Dict, Iterable, List


POSITIVE_STATUS = "metastasis_probable"
SANE_STATUS = "sano_probable"
FOCAL_STATUS = "sospecha_focal"
MIXED_STATUS = "mixto_incierto"
NOT_EVALUABLE_STATUS = "roi_no_evaluable"


def _env_float(name: str, default: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value < minimum or value > maximum:
        return default
    return value


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _tile_rect(tile: Dict[str, Any]) -> Dict[str, int] | None:
    roi = tile.get("roi") or {}
    try:
        return {
            "x": int(roi["x"]),
            "y": int(roi["y"]),
            "width": int(roi["width"]),
            "height": int(roi["height"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _rects_touch_or_overlap(a: Dict[str, int], b: Dict[str, int], gap_tolerance: int) -> bool:
    ax2 = a["x"] + a["width"]
    ay2 = a["y"] + a["height"]
    bx2 = b["x"] + b["width"]
    by2 = b["y"] + b["height"]

    x_gap = max(0, max(a["x"], b["x"]) - min(ax2, bx2))
    y_gap = max(0, max(a["y"], b["y"]) - min(ay2, by2))
    return x_gap <= gap_tolerance and y_gap <= gap_tolerance


def _max_connected_cluster(tiles: List[Dict[str, Any]], gap_tolerance: int) -> int:
    rects = [_tile_rect(tile) for tile in tiles]
    indexed_rects = [(index, rect) for index, rect in enumerate(rects) if rect is not None]
    if not indexed_rects:
        return 0

    neighbors: dict[int, list[int]] = {index: [] for index, _ in indexed_rects}
    for pos, (left_index, left_rect) in enumerate(indexed_rects):
        for right_index, right_rect in indexed_rects[pos + 1:]:
            if _rects_touch_or_overlap(left_rect, right_rect, gap_tolerance):
                neighbors[left_index].append(right_index)
                neighbors[right_index].append(left_index)

    visited: set[int] = set()
    largest = 0
    for start in neighbors:
        if start in visited:
            continue
        size = 0
        queue = deque([start])
        visited.add(start)
        while queue:
            current = queue.popleft()
            size += 1
            for neighbor in neighbors[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        largest = max(largest, size)
    return largest


def _decision(
    *,
    status: str,
    label: str,
    summary: str,
    recommendation: str,
    metrics: Dict[str, Any],
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "status": status,
        "label": label,
        "summary": summary,
        "recommendation": recommendation,
        "metrics": metrics,
        "thresholds": thresholds,
    }


def aggregate_tile_probability_summary(tile_results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    evaluable = [
        tile
        for tile in tile_results
        if tile.get("status") not in {"error", NOT_EVALUABLE_STATUS}
        and isinstance(tile.get("probabilities"), dict)
        and tile.get("probabilities")
    ]
    tumor_scores = sorted(
        (_as_float(tile["probabilities"].get("metastasico")) for tile in evaluable),
        reverse=True,
    )
    tile_threshold = _env_float("HISTO_HEATMAP_ROI_AGGREGATION_TILE_THRESHOLD", 0.50)
    top_k = min(_env_int("HISTO_HEATMAP_ROI_AGGREGATION_TOP_K", 3), len(tumor_scores))
    if not tumor_scores:
        return {
            "tile_count": 0,
            "mean_tumor_probability": 0.0,
            "max_tumor_probability": 0.0,
            "top_k_mean_tumor_probability": 0.0,
            "positive_tile_fraction": 0.0,
            "top_k": 0,
            "tile_threshold": tile_threshold,
            "recommended_strategy": "top_k_mean",
            "interpretation": "No hay tiles evaluables para agregar.",
        }
    return {
        "tile_count": len(tumor_scores),
        "mean_tumor_probability": sum(tumor_scores) / len(tumor_scores),
        "max_tumor_probability": tumor_scores[0],
        "top_k_mean_tumor_probability": sum(tumor_scores[:top_k]) / top_k,
        "positive_tile_fraction": (
            sum(score >= tile_threshold for score in tumor_scores) / len(tumor_scores)
        ),
        "top_k": top_k,
        "tile_threshold": tile_threshold,
        "recommended_strategy": "top_k_mean",
        "interpretation": (
            "Resumen de probabilidades por tiles. No es Grad-CAM ni una explicacion causal."
        ),
    }


def aggregate_heatmap_roi_decision(tile_results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate already-computed heatmap tiles into an educational ROI decision.

    This function intentionally does not run inference. It only inspects tile-level
    classes, probabilities and coordinates that were already produced by the heatmap.
    """
    tiles = list(tile_results)
    total_tiles = len(tiles)
    # Thresholds ajustados para reducir falsos positivos en zonas sin metastasis:
    # - tumor_tile_threshold subido (0.90→0.92): exige mayor certeza para declarar tile tumoral
    # - sane_max_tumor_score subido (0.30→0.35): permite score tumoral levemente mas alto en zona sana
    # - sane_min_negative_fraction bajado (0.70→0.60): basta con 60 % de tiles negativos para sano probable
    tumor_tile_threshold = _env_float("HISTO_HEATMAP_ROI_TUMOR_TILE_THRESHOLD", 0.92)
    suspicious_tile_threshold = _env_float("HISTO_HEATMAP_ROI_SUSPICIOUS_TILE_THRESHOLD", 0.80)
    sane_max_tumor_score = _env_float("HISTO_HEATMAP_ROI_SANE_MAX_TUMOR_SCORE", 0.35)
    sane_min_negative_fraction = _env_float("HISTO_HEATMAP_ROI_SANE_MIN_NEGATIVE_FRACTION", 0.60)
    min_evaluable_fraction = _env_float("HISTO_HEATMAP_ROI_MIN_EVALUABLE_FRACTION", 0.35)
    configured_min_cluster = _env_int("HISTO_HEATMAP_ROI_MIN_TUMOR_CLUSTER", 2)

    error_tiles = [tile for tile in tiles if tile.get("status") == "error"]
    non_error_tiles = [tile for tile in tiles if tile.get("status") != "error"]
    not_evaluable_tiles = [
        tile for tile in non_error_tiles
        if tile.get("status") == NOT_EVALUABLE_STATUS or tile.get("class") == NOT_EVALUABLE_STATUS
    ]
    evaluable_tiles = [
        tile for tile in non_error_tiles
        if tile not in not_evaluable_tiles
    ]

    evaluable_count = len(evaluable_tiles)
    denominator = max(len(non_error_tiles), 1)
    evaluable_fraction = evaluable_count / denominator

    strong_tumor_tiles = [
        tile for tile in evaluable_tiles
        if tile.get("class") == "metastasico"
        and _as_float(tile.get("tumor_score")) >= tumor_tile_threshold
    ]
    suspicious_tiles = [
        tile for tile in evaluable_tiles
        if _as_float(tile.get("tumor_score")) >= suspicious_tile_threshold
    ]
    # "estroma" se incluye como soporte negativo: el modelo 3-class usa esta clase
    # para tejido conectivo que el modelo binario confundia con tumor (falsos positivos).
    negative_support_tiles = [
        tile for tile in evaluable_tiles
        if tile.get("class") in {"no_metastasico", "no_metastasico_probable", "estroma"}
    ]
    uncertain_tiles = [
        tile for tile in evaluable_tiles
        if tile.get("status") == "resultado_incierto"
    ]

    max_tumor_score = max((_as_float(tile.get("tumor_score")) for tile in evaluable_tiles), default=0.0)
    gap_tolerance = 1
    max_cluster = _max_connected_cluster(strong_tumor_tiles, gap_tolerance)
    cluster_required = 1 if evaluable_count <= 1 else configured_min_cluster
    negative_fraction = len(negative_support_tiles) / max(evaluable_count, 1)
    strong_fraction = len(strong_tumor_tiles) / max(evaluable_count, 1)
    suspicious_fraction = len(suspicious_tiles) / max(evaluable_count, 1)

    metrics = {
        "total_tiles": total_tiles,
        "evaluable_tiles": evaluable_count,
        "error_tiles": len(error_tiles),
        "non_evaluable_tiles": len(not_evaluable_tiles),
        "strong_tumor_tiles": len(strong_tumor_tiles),
        "suspicious_tiles": len(suspicious_tiles),
        "negative_support_tiles": len(negative_support_tiles),
        "uncertain_tiles": len(uncertain_tiles),
        "max_connected_tumor_cluster": max_cluster,
        "cluster_required": cluster_required,
        "max_tumor_score": max_tumor_score,
        "evaluable_fraction": evaluable_fraction,
        "negative_fraction": negative_fraction,
        "strong_tumor_fraction": strong_fraction,
        "suspicious_fraction": suspicious_fraction,
    }
    thresholds = {
        "tumor_tile": tumor_tile_threshold,
        "suspicious_tile": suspicious_tile_threshold,
        "sane_max_tumor_score": sane_max_tumor_score,
        "sane_min_negative_fraction": sane_min_negative_fraction,
        "min_evaluable_fraction": min_evaluable_fraction,
        "min_tumor_cluster": configured_min_cluster,
    }

    if total_tiles == 0 or evaluable_count == 0 or (total_tiles >= 4 and evaluable_fraction < min_evaluable_fraction):
        return _decision(
            status=NOT_EVALUABLE_STATUS,
            label="ROI no evaluable",
            summary="La ROI no tiene suficientes tiles evaluables para decidir tumor vs sano.",
            recommendation="Seleccione una ROI con mas tejido util y menos fondo, estroma o artefacto.",
            metrics=metrics,
            thresholds=thresholds,
        )

    if max_cluster >= cluster_required:
        return _decision(
            status=POSITIVE_STATUS,
            label="Patron compatible con metastasis",
            summary=(
                "Hay multiples tiles tumorales contiguos; la decision se apoya en "
                "patron espacial, no en un tile aislado."
            ),
            recommendation="Use el mejor tile o la zona agrupada como ROI 2 para revision educativa.",
            metrics=metrics,
            thresholds=thresholds,
        )

    minimum_distributed_tiles = max(cluster_required + 1, math.ceil(evaluable_count * 0.25))
    if len(strong_tumor_tiles) >= minimum_distributed_tiles:
        return _decision(
            status=POSITIVE_STATUS,
            label="Patron compatible con metastasis",
            summary="Hay varios tiles tumorales fuertes distribuidos en la ROI.",
            recommendation="Revise los tiles con mayor probabilidad metastasica antes de cerrar la interpretacion.",
            metrics=metrics,
            thresholds=thresholds,
        )

    if strong_tumor_tiles:
        return _decision(
            status=FOCAL_STATUS,
            label="Sospecha focal",
            summary="Existe un tile tumoral fuerte, pero no hay cluster suficiente para clasificar toda la ROI.",
            recommendation="Evite concluir metastasis por un tile aislado; amplie la ROI o analice la zona focal como ROI 2.",
            metrics=metrics,
            thresholds=thresholds,
        )

    if suspicious_tiles or uncertain_tiles:
        return _decision(
            status=MIXED_STATUS,
            label="ROI mixta o incierta",
            summary="Hay senales tumorales intermedias o tiles inciertos, sin patron tumoral agrupado.",
            recommendation="Seleccione una subregion mas representativa o compare con un mapa preparado por docente.",
            metrics=metrics,
            thresholds=thresholds,
        )

    if negative_fraction >= sane_min_negative_fraction and max_tumor_score <= sane_max_tumor_score:
        return _decision(
            status=SANE_STATUS,
            label="Sano probable",
            summary="La mayoria de tiles evaluables apoyan no metastasis y la probabilidad tumoral maxima es baja.",
            recommendation="Resultado educativo compatible con zona sin metastasis evidente en los tiles analizados.",
            metrics=metrics,
            thresholds=thresholds,
        )

    return _decision(
        status=MIXED_STATUS,
        label="ROI mixta o incierta",
        summary="La ROI no cumple criterios fuertes de metastasis ni de sano probable.",
        recommendation="Use una ROI mas pequena o revise visualmente los tiles con mayor probabilidad.",
        metrics=metrics,
        thresholds=thresholds,
    )
