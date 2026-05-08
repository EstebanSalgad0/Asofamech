import os
from dataclasses import dataclass
from typing import Dict, Optional

from PIL import Image


@dataclass(frozen=True)
class QualityThresholds:
    max_white_fraction: float = 0.45
    min_tissue_fraction: float = 0.40
    min_nuclear_fraction: float = 0.035
    max_stroma_fraction_when_low_nuclear: float = 0.65
    low_nuclear_for_stroma_fraction: float = 0.12


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def get_quality_thresholds() -> QualityThresholds:
    return QualityThresholds(
        max_white_fraction=_float_env("HISTO_QC_MAX_WHITE_FRACTION", 0.45),
        min_tissue_fraction=_float_env("HISTO_QC_MIN_TISSUE_FRACTION", 0.40),
        min_nuclear_fraction=_float_env("HISTO_QC_MIN_NUCLEAR_FRACTION", 0.035),
        max_stroma_fraction_when_low_nuclear=_float_env(
            "HISTO_QC_MAX_STROMA_FRACTION_WHEN_LOW_NUCLEAR", 0.65
        ),
        low_nuclear_for_stroma_fraction=_float_env(
            "HISTO_QC_LOW_NUCLEAR_FOR_STROMA_FRACTION", 0.12
        ),
    )


def _analysis_image(image: Image.Image, max_side: int = 512) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    longest = max(width, height)
    if longest <= max_side:
        return rgb

    scale = max_side / longest
    resized = (max(1, int(width * scale)), max(1, int(height * scale)))
    return rgb.resize(resized, Image.Resampling.BILINEAR)


def evaluate_roi_quality(
    patch_rgb: Image.Image,
    thresholds: Optional[QualityThresholds] = None,
) -> Dict:
    """
    Estimate whether a ROI has enough tissue/cellularity for binary inference.

    This is a conservative heuristic guard, not a tissue classifier. It blocks
    obvious out-of-domain inputs such as mostly white background, adipose spaces,
    sparse tissue, or stroma-dominant low-cellularity regions.
    """
    thresholds = thresholds or get_quality_thresholds()
    image = _analysis_image(patch_rgb)
    if hasattr(image, "get_flattened_data"):
        pixels = list(image.get_flattened_data())
    else:
        pixels = list(image.getdata())
    total = max(1, len(pixels))

    white_pixels = 0
    tissue_pixels = 0
    nuclear_pixels = 0
    stroma_like_pixels = 0

    for r, g, b in pixels:
        max_channel = max(r, g, b)
        min_channel = min(r, g, b)
        intensity = (r + g + b) / 3.0
        saturation = max_channel - min_channel

        is_white = r >= 220 and g >= 220 and b >= 220 and saturation <= 30
        if is_white:
            white_pixels += 1
            continue

        tissue_pixels += 1

        # Dark purple/blue H&E nuclear material tends to have lower intensity
        # and enough color separation from the background.
        is_nuclear = intensity <= 145 and saturation >= 20 and b >= g * 0.75
        if is_nuclear:
            nuclear_pixels += 1

        # Pink collagen/stroma often has stronger red channel and mid/high
        # intensity. This helps flag stroma-dominant sparse ROIs.
        is_stroma_like = r >= g + 8 and r >= b + 12 and intensity >= 120 and saturation >= 15
        if is_stroma_like:
            stroma_like_pixels += 1

    white_fraction = white_pixels / total
    tissue_fraction = tissue_pixels / total
    nuclear_fraction = nuclear_pixels / total
    stroma_fraction = stroma_like_pixels / max(1, tissue_pixels)

    checks = {
        "white_fraction_ok": white_fraction <= thresholds.max_white_fraction,
        "tissue_fraction_ok": tissue_fraction >= thresholds.min_tissue_fraction,
        "nuclear_fraction_ok": nuclear_fraction >= thresholds.min_nuclear_fraction,
        "stroma_fraction_ok": not (
            stroma_fraction > thresholds.max_stroma_fraction_when_low_nuclear
            and nuclear_fraction < thresholds.low_nuclear_for_stroma_fraction
        ),
    }

    reasons = []
    if not checks["white_fraction_ok"]:
        reasons.append("exceso de fondo blanco o espacios adiposos")
    if not checks["tissue_fraction_ok"]:
        reasons.append("baja proporcion de tejido util")
    if not checks["nuclear_fraction_ok"]:
        reasons.append("baja densidad celular/nuclear")
    if not checks["stroma_fraction_ok"]:
        reasons.append("predominio de estroma con baja celularidad")

    is_evaluable = all(checks.values())
    reason = None
    recommendation = None
    if not is_evaluable:
        reason = "ROI no evaluable: " + ", ".join(reasons) + "."
        recommendation = (
            "Seleccione una ROI con mayor densidad celular, menor fondo blanco "
            "y menor predominio de tejido adiposo, estroma o artefactos."
        )

    return {
        "is_evaluable": is_evaluable,
        "status": "evaluable" if is_evaluable else "roi_no_evaluable",
        "reason": reason,
        "recommendation": recommendation,
        "metrics": {
            "white_fraction": white_fraction,
            "tissue_fraction": tissue_fraction,
            "nuclear_fraction": nuclear_fraction,
            "stroma_fraction": stroma_fraction,
            "analysis_width": image.width,
            "analysis_height": image.height,
        },
        "checks": checks,
        "thresholds": {
            "max_white_fraction": thresholds.max_white_fraction,
            "min_tissue_fraction": thresholds.min_tissue_fraction,
            "min_nuclear_fraction": thresholds.min_nuclear_fraction,
            "max_stroma_fraction_when_low_nuclear": thresholds.max_stroma_fraction_when_low_nuclear,
            "low_nuclear_for_stroma_fraction": thresholds.low_nuclear_for_stroma_fraction,
        },
    }
