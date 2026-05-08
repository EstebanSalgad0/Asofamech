import json
import os
import threading
from pathlib import Path
from typing import Any, Dict


DEFAULT_AUDIT_LOG_PATH = "artifacts/histopathology/audit_log.jsonl"
_WRITE_LOCK = threading.Lock()


def get_audit_log_path() -> Path:
    return Path(os.getenv("HISTO_AUDIT_LOG_PATH", DEFAULT_AUDIT_LOG_PATH))


def append_audit_event(event: Dict[str, Any], path: Path | None = None) -> Path:
    audit_path = path or get_audit_log_path()
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    with _WRITE_LOCK:
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True))
            handle.write("\n")

    return audit_path
