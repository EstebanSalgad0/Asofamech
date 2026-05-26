import os
import unittest
from unittest.mock import patch

from app.histopathology import heatmap_access


class HeatmapAccessTestCase(unittest.TestCase):
    def setUp(self):
        heatmap_access.reset_heatmap_rate_limits()

    def tearDown(self):
        heatmap_access.reset_heatmap_rate_limits()

    def test_normalize_role_aliases(self):
        self.assertEqual(heatmap_access.normalize_role("Administrador"), "administrador")
        self.assertEqual(heatmap_access.normalize_role("Docente"), "profesor")
        self.assertEqual(heatmap_access.normalize_role("student"), "estudiante")
        self.assertEqual(heatmap_access.normalize_role(None), "estudiante")

    def test_privileged_roles(self):
        self.assertTrue(heatmap_access.is_privileged_role("Profesor"))
        self.assertTrue(heatmap_access.is_privileged_role("administrador"))
        self.assertFalse(heatmap_access.is_privileged_role("Estudiante"))

    def test_student_limits_are_lower_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(heatmap_access.max_tiles_for_role("Estudiante"), 16)
            self.assertEqual(heatmap_access.max_tile_size_for_role("Estudiante"), 1024)
            self.assertGreaterEqual(heatmap_access.max_tiles_for_role("Administrador"), 64)

    def test_limits_can_be_configured(self):
        with patch.dict(os.environ, {"HISTO_STUDENT_MAX_HEATMAP_TILES": "8"}):
            self.assertEqual(heatmap_access.max_tiles_for_role("Estudiante"), 8)

    def test_rate_limit_allows_until_limit(self):
        with patch.dict(os.environ, {"HISTO_STUDENT_HEATMAP_JOBS_PER_WINDOW": "2"}):
            key = heatmap_access.heatmap_rate_limit_key(user_id=1, role="Estudiante", client_id="abc")
            allowed_1 = heatmap_access.check_heatmap_rate_limit(key, "Estudiante", now=100.0)
            allowed_2 = heatmap_access.check_heatmap_rate_limit(key, "Estudiante", now=101.0)
            blocked = heatmap_access.check_heatmap_rate_limit(key, "Estudiante", now=102.0)
            self.assertTrue(allowed_1[0])
            self.assertTrue(allowed_2[0])
            self.assertFalse(blocked[0])
            self.assertGreater(blocked[1], 0)

    def test_rate_limit_expires_after_window(self):
        with patch.dict(
            os.environ,
            {
                "HISTO_STUDENT_HEATMAP_JOBS_PER_WINDOW": "1",
                "HISTO_HEATMAP_RATE_LIMIT_WINDOW_SECONDS": "10",
            },
        ):
            key = heatmap_access.heatmap_rate_limit_key(user_id=1, role="Estudiante", client_id="abc")
            self.assertTrue(heatmap_access.check_heatmap_rate_limit(key, "Estudiante", now=100.0)[0])
            self.assertFalse(heatmap_access.check_heatmap_rate_limit(key, "Estudiante", now=105.0)[0])
            self.assertTrue(heatmap_access.check_heatmap_rate_limit(key, "Estudiante", now=111.0)[0])


if __name__ == "__main__":
    unittest.main()
