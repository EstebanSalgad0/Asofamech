import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_HEATMAP_DIR = "artifacts/histopathology/heatmaps"
_WRITE_LOCK = threading.Lock()


def get_heatmap_dir() -> Path:
    return Path(os.getenv("HISTO_HEATMAP_DIR", DEFAULT_HEATMAP_DIR))


def _image_index_path(image_id: int) -> Path:
    return get_heatmap_dir() / "images" / str(image_id) / "latest.json"


def _image_history_path(image_id: int) -> Path:
    return get_heatmap_dir() / "images" / str(image_id) / "history.json"


def _trace_path(trace_id: str) -> Path:
    return get_heatmap_dir() / "traces" / f"{trace_id}.json"


def _compact_best_tile(best_tile: Any) -> Any:
    if not isinstance(best_tile, dict):
        return best_tile
    return {
        "index": best_tile.get("index"),
        "roi": best_tile.get("roi"),
        "status": best_tile.get("status"),
        "class": best_tile.get("class"),
        "tumor_score": best_tile.get("tumor_score"),
        "confidence": best_tile.get("confidence"),
        "reason": best_tile.get("reason"),
    }


def _history_item(result: Dict[str, Any], artifacts: Dict[str, str]) -> Dict[str, Any]:
    summary = result.get("summary") or {}
    return {
        "trace_id": result.get("trace_id"),
        "image_id": result.get("image_id"),
        "analyzed_at": result.get("analyzed_at"),
        "roi": result.get("roi"),
        "tile_size": result.get("tile_size"),
        "stride": result.get("stride"),
        "requested_max_tiles": result.get("requested_max_tiles"),
        "tile_count": result.get("tile_count"),
        "summary": {
            "classified_metastatic_tiles": summary.get("classified_metastatic_tiles", 0),
            "uncertain_high_tumor_tiles": summary.get("uncertain_high_tumor_tiles", 0),
            "max_tumor_score": summary.get("max_tumor_score", 0.0),
            "cache_hits": summary.get("cache_hits", 0),
            "cache_misses": summary.get("cache_misses", 0),
            "cache_hit_rate": summary.get("cache_hit_rate", 0.0),
            "best_tile": _compact_best_tile(summary.get("best_tile")),
        },
        "artifacts": artifacts,
    }


def _load_history_unlocked(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return []


def save_heatmap_result(result: Dict[str, Any]) -> Dict[str, str]:
    trace_id = str(result["trace_id"])
    image_id = int(result["image_id"])
    trace_path = _trace_path(trace_id)
    latest_path = _image_index_path(image_id)
    history_path = _image_history_path(image_id)
    artifacts = {
        "trace_path": str(trace_path),
        "latest_path": str(latest_path),
        "history_path": str(history_path),
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
        history = [
            item for item in _load_history_unlocked(history_path)
            if item.get("trace_id") != trace_id
        ]
        history.insert(0, _history_item(stored_result, artifacts))
        history_path.write_text(
            json.dumps(history[:100], ensure_ascii=True, sort_keys=True, indent=2),
            encoding="utf-8",
        )

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


def load_heatmap_history_for_image(image_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    path = _image_history_path(image_id)
    if not path.exists():
        latest = load_latest_heatmap_for_image(image_id)
        if not latest:
            return []
        return [_history_item(latest, latest.get("artifacts", {}))][:limit]
    history = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(history, list):
        return []
    safe_limit = max(1, min(int(limit), 100))
    return history[:safe_limit]
