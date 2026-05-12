import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_TILE_CACHE_DIR = "artifacts/histopathology/heatmaps/tile_cache"
_WRITE_LOCK = threading.Lock()


def get_tile_cache_dir() -> Path:
    return Path(os.getenv("HISTO_HEATMAP_TILE_CACHE_DIR", DEFAULT_TILE_CACHE_DIR))


def build_tile_cache_key(
    *,
    image_id: int,
    roi: Dict[str, int],
    model_signature: str,
) -> str:
    payload = {
        "image_id": int(image_id),
        "roi": {
            "x": int(roi["x"]),
            "y": int(roi["y"]),
            "width": int(roi["width"]),
            "height": int(roi["height"]),
        },
        "model_signature": model_signature,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_path(cache_key: str) -> Path:
    return get_tile_cache_dir() / f"{cache_key}.json"


def load_cached_tile(cache_key: str) -> Optional[Dict[str, Any]]:
    path = _cache_path(cache_key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_cached_tile(cache_key: str, tile_result: Dict[str, Any]) -> None:
    path = _cache_path(cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK:
        path.write_text(
            json.dumps(tile_result, ensure_ascii=True, sort_keys=True, indent=2),
            encoding="utf-8",
        )
