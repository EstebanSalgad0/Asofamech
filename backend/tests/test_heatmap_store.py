import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app.histopathology import heatmap_store


class HeatmapStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env_patcher = patch.dict(os.environ, {"HISTO_HEATMAP_DIR": self.tmp})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_result(self, image_id=1, trace_id="test-trace-001"):
        return {
            "image_id": image_id,
            "trace_id": trace_id,
            "tile_count": 4,
            "tiles": [],
            "summary": {"max_tumor_score": 0.85, "classified_metastatic_tiles": 1},
        }

    def test_save_and_load_by_trace(self):
        result = self._make_result()
        heatmap_store.save_heatmap_result(result)
        loaded = heatmap_store.load_heatmap_by_trace("test-trace-001")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["trace_id"], "test-trace-001")
        self.assertEqual(loaded["tile_count"], 4)
        self.assertTrue(loaded.get("persisted"))

    def test_save_and_load_latest_for_image(self):
        result = self._make_result(image_id=42, trace_id="trace-latest")
        heatmap_store.save_heatmap_result(result)
        loaded = heatmap_store.load_latest_heatmap_for_image(42)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["image_id"], 42)
        self.assertEqual(loaded["trace_id"], "trace-latest")

    def test_load_missing_trace_returns_none(self):
        result = heatmap_store.load_heatmap_by_trace("does-not-exist")
        self.assertIsNone(result)

    def test_load_missing_image_returns_none(self):
        result = heatmap_store.load_latest_heatmap_for_image(9999)
        self.assertIsNone(result)

    def test_save_creates_both_artifact_files(self):
        result = self._make_result(image_id=5, trace_id="trace-both")
        artifacts = heatmap_store.save_heatmap_result(result)
        self.assertIn("trace_path", artifacts)
        self.assertIn("latest_path", artifacts)
        self.assertTrue(Path(artifacts["trace_path"]).exists())
        self.assertTrue(Path(artifacts["latest_path"]).exists())

    def test_save_marks_persisted_flag(self):
        result = self._make_result(image_id=3, trace_id="trace-flag")
        heatmap_store.save_heatmap_result(result)
        loaded = heatmap_store.load_heatmap_by_trace("trace-flag")
        self.assertTrue(loaded.get("persisted") is True)

    def test_latest_overwritten_by_newer_result(self):
        result_a = self._make_result(image_id=7, trace_id="trace-a")
        result_a["tile_count"] = 10
        result_b = self._make_result(image_id=7, trace_id="trace-b")
        result_b["tile_count"] = 20
        heatmap_store.save_heatmap_result(result_a)
        heatmap_store.save_heatmap_result(result_b)
        loaded = heatmap_store.load_latest_heatmap_for_image(7)
        self.assertEqual(loaded["tile_count"], 20)
        self.assertEqual(loaded["trace_id"], "trace-b")

    def test_previous_trace_still_readable_after_overwrite(self):
        heatmap_store.save_heatmap_result(self._make_result(image_id=8, trace_id="trace-old"))
        heatmap_store.save_heatmap_result(self._make_result(image_id=8, trace_id="trace-new"))
        old = heatmap_store.load_heatmap_by_trace("trace-old")
        self.assertIsNotNone(old)
        self.assertEqual(old["trace_id"], "trace-old")

    def test_concurrent_saves_do_not_corrupt(self):
        errors = []

        def save_one(n):
            try:
                r = {
                    "image_id": 100,
                    "trace_id": f"concurrent-{n}",
                    "tile_count": n,
                    "tiles": [],
                    "summary": {},
                }
                heatmap_store.save_heatmap_result(r)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=save_one, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errores en escritura concurrente: {errors}")
        loaded = heatmap_store.load_latest_heatmap_for_image(100)
        self.assertIsNotNone(loaded)


if __name__ == "__main__":
    unittest.main()
