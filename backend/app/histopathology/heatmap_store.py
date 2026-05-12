import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_HEATMAP_DIR = "artifacts/histopathology/heatmaps"
_WRITE_LOCK = threading.Lock()


def get_heatmap_dir() -> Path:
    return Path(os.getenv("HISTO_HEATMAP_DIR", DEFAULT_HEATMAP_DIR))


def _image_index_path(image_id: int) -> Path:
    return get_heatmap_dir() / "images" / str(image_id) / "latest.json"


def _trace_path(trace_id: str) -> Path:
    return get_heatmap_dir() / "traces" / f"{trace_id}.json"


def save_heatmap_result(result: Dict[str, Any]) -> Dict[str, str]:
    trace_id = str(result["trace_id"])
    image_id = int(result["image_id"])
    trace_path = _trace_path(trace_id)
    latest_path = _image_index_path(image_id)
    artifacts = {
        "trace_path": str(trace_path),
        "latest_path": str(latest_path),
    }
    stored_result = {
        **result,
        "persisted": True,
        "artifacts": artifacts,
    }

    trace_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.parent.mkdir(parents=True, exist_ok=True)

    with _WRITE_LOCK:
        payload = json.dumps(stored_result, ensure_ascii=True, sort_keys=True, indent=2)
        trace_path.write_text(payload, encoding="utf-8")
        latest_path.write_text(payload, encoding="utf-8")

    return artifacts


def load_heatmap_by_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    path = _trace_path(trace_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_latest_heatmap_for_image(image_id: int) -> Optional[Dict[str, Any]]:
    path = _image_index_path(image_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
