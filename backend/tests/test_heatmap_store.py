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
        self.assertIn("history_path", artifacts)
        self.assertTrue(Path(artifacts["trace_path"]).exists())
        self.assertTrue(Path(artifacts["latest_path"]).exists())
        self.assertTrue(Path(artifacts["history_path"]).exists())

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

    def test_history_lists_newest_first_for_image(self):
        heatmap_store.save_heatmap_result(self._make_result(image_id=9, trace_id="trace-old"))
        heatmap_store.save_heatmap_result(self._make_result(image_id=9, trace_id="trace-new"))
        history = heatmap_store.load_heatmap_history_for_image(9)
        self.assertEqual([item["trace_id"] for item in history], ["trace-new", "trace-old"])

    def test_history_is_scoped_by_image(self):
        heatmap_store.save_heatmap_result(self._make_result(image_id=10, trace_id="trace-a"))
        heatmap_store.save_heatmap_result(self._make_result(image_id=11, trace_id="trace-b"))
        history = heatmap_store.load_heatmap_history_for_image(10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["trace_id"], "trace-a")

    def test_history_limit_is_applied(self):
        for n in range(5):
            heatmap_store.save_heatmap_result(self._make_result(image_id=12, trace_id=f"trace-{n}"))
        history = heatmap_store.load_heatmap_history_for_image(12, limit=3)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["trace_id"], "trace-4")

    def test_history_falls_back_to_legacy_latest(self):
        result = self._make_result(image_id=14, trace_id="trace-legacy-latest")
        artifacts = heatmap_store.save_heatmap_result(result)
        Path(artifacts["history_path"]).unlink()
        history = heatmap_store.load_heatmap_history_for_image(14)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["trace_id"], "trace-legacy-latest")

    def test_history_replaces_duplicate_trace(self):
        result_a = self._make_result(image_id=13, trace_id="trace-dup")
        result_a["tile_count"] = 4
        result_b = self._make_result(image_id=13, trace_id="trace-dup")
        result_b["tile_count"] = 8
        heatmap_store.save_heatmap_result(result_a)
        heatmap_store.save_heatmap_result(result_b)
        history = heatmap_store.load_heatmap_history_for_image(13)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["tile_count"], 8)

    def test_history_compacts_best_tile(self):
        result = self._make_result(image_id=15, trace_id="trace-compact")
        result["summary"]["best_tile"] = {
            "index": 2,
            "roi": {"x": 10, "y": 20, "width": 512, "height": 512},
            "class": "metastasico",
            "tumor_score": 0.91,
            "probabilities": {"metastasico": 0.91},
            "roi_quality": {"large": "payload"},
        }
        heatmap_store.save_heatmap_result(result)
        best_tile = heatmap_store.load_heatmap_history_for_image(15)[0]["summary"]["best_tile"]
        self.assertEqual(best_tile["class"], "metastasico")
        self.assertNotIn("probabilities", best_tile)
        self.assertNotIn("roi_quality", best_tile)

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
        history = heatmap_store.load_heatmap_history_for_image(100)
        self.assertEqual(len(history), 6)


if __name__ == "__main__":
    unittest.main()
