import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from app.histopathology import heatmap_tile_cache


class HeatmapTileCacheTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env_patcher = patch.dict(
            os.environ,
            {"HISTO_HEATMAP_TILE_CACHE_DIR": self.tmp},
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _roi(self):
        return {"x": 10, "y": 20, "width": 512, "height": 512}

    def test_build_key_is_stable_for_same_payload(self):
        key_a = heatmap_tile_cache.build_tile_cache_key(
            image_id=1,
            roi=self._roi(),
            model_signature="model-a",
        )
        key_b = heatmap_tile_cache.build_tile_cache_key(
            image_id=1,
            roi=self._roi(),
            model_signature="model-a",
        )
        self.assertEqual(key_a, key_b)

    def test_build_key_changes_with_model_signature(self):
        key_a = heatmap_tile_cache.build_tile_cache_key(
            image_id=1,
            roi=self._roi(),
            model_signature="model-a",
        )
        key_b = heatmap_tile_cache.build_tile_cache_key(
            image_id=1,
            roi=self._roi(),
            model_signature="model-b",
        )
        self.assertNotEqual(key_a, key_b)

    def test_load_missing_tile_returns_none(self):
        self.assertIsNone(heatmap_tile_cache.load_cached_tile("missing-key"))

    def test_save_and_load_cached_tile(self):
        cache_key = heatmap_tile_cache.build_tile_cache_key(
            image_id=5,
            roi=self._roi(),
            model_signature="model-a",
        )
        tile = {
            "roi": self._roi(),
            "status": "clasificado",
            "class": "metastasico",
            "tumor_score": 0.95,
        }
        heatmap_tile_cache.save_cached_tile(cache_key, tile)
        loaded = heatmap_tile_cache.load_cached_tile(cache_key)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["class"], "metastasico")
        self.assertAlmostEqual(loaded["tumor_score"], 0.95)


if __name__ == "__main__":
    unittest.main()
