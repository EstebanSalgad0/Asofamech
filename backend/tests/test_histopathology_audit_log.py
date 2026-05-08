import json
import unittest
import uuid
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.histopathology.audit_log import append_audit_event


class HistopathologyAuditLogTestCase(unittest.TestCase):
    def test_append_audit_event_writes_json_line(self):
        audit_path = Path("artifacts") / "histopathology-test" / f"audit-{uuid.uuid4()}.jsonl"

        written_path = append_audit_event(
            {
                "event": "histopathology_analyze_succeeded",
                "trace_id": "trace-1",
                "image_id": 12,
                "prediction": {"predicted_class": "metastasico"},
            },
            path=audit_path,
        )

        self.assertEqual(written_path, audit_path)
        lines = audit_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["trace_id"], "trace-1")
        self.assertEqual(payload["image_id"], 12)
        self.assertEqual(payload["prediction"]["predicted_class"], "metastasico")


if __name__ == "__main__":
    unittest.main()
