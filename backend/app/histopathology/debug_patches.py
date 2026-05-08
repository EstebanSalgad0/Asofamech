import os
from pathlib import Path
from typing import Dict, Optional

from PIL import Image


DEFAULT_DEBUG_PATCH_DIR = "artifacts/histopathology/debug_patches"


def _env_enabled(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def debug_patches_enabled() -> bool:
    return _env_enabled("HISTO_SAVE_DEBUG_PATCHES", True)


def get_debug_patch_dir() -> Path:
    return Path(os.getenv("HISTO_DEBUG_PATCH_DIR", DEFAULT_DEBUG_PATCH_DIR))


def save_patch_debug_images(
    trace_id: str,
    original_patch: Image.Image,
    preprocessed_patch: Optional[Image.Image] = None,
    preprocessed_tensor: Optional[object] = None,
) -> Dict[str, object]:
    if not debug_patches_enabled():
        return {"enabled": False}

    trace_dir = get_debug_patch_dir() / trace_id
    try:
        trace_dir.mkdir(parents=True, exist_ok=True)

        artifacts: Dict[str, object] = {"enabled": True, "directory": str(trace_dir)}

        original_path = trace_dir / "debug_patch_original.png"
        original_patch.convert("RGB").save(original_path)
        artifacts["original_patch"] = str(original_path)

        if preprocessed_patch is not None:
            preprocessed_path = trace_dir / "debug_patch_preprocessed.png"
            preprocessed_patch.convert("RGB").save(preprocessed_path)
            artifacts["preprocessed_patch"] = str(preprocessed_path)

        if preprocessed_tensor is not None:
            tensor_path = trace_dir / "debug_patch_preprocessed.pt"
            try:
                import torch

                torch.save(preprocessed_tensor, tensor_path)
                artifacts["preprocessed_tensor"] = str(tensor_path)
            except Exception as exc:
                artifacts["preprocessed_tensor_error"] = str(exc)

        return artifacts
    except OSError as exc:
        return {"enabled": True, "error": str(exc), "directory": str(trace_dir)}
