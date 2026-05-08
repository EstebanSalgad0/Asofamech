import unittest

from PIL import Image

from app.histopathology.roi_quality import QualityThresholds, evaluate_roi_quality


class HistopathologyROIQualityTestCase(unittest.TestCase):
    def test_rejects_mostly_white_background(self):
        patch = Image.new("RGB", (96, 96), (245, 245, 245))

        quality = evaluate_roi_quality(patch)

        self.assertFalse(quality["is_evaluable"])
        self.assertFalse(quality["checks"]["white_fraction_ok"])
        self.assertIn("fondo blanco", quality["reason"])

    def test_accepts_dense_cellular_he_patch(self):
        patch = Image.new("RGB", (96, 96), (92, 54, 128))

        quality = evaluate_roi_quality(patch)

        self.assertTrue(quality["is_evaluable"])
        self.assertGreater(quality["metrics"]["nuclear_fraction"], 0.9)

    def test_rejects_stroma_dominant_low_cellularity_patch(self):
        patch = Image.new("RGB", (96, 96), (221, 155, 179))
        thresholds = QualityThresholds(
            max_white_fraction=0.60,
            min_tissue_fraction=0.30,
            min_nuclear_fraction=0.035,
            max_stroma_fraction_when_low_nuclear=0.65,
            low_nuclear_for_stroma_fraction=0.08,
        )

        quality = evaluate_roi_quality(patch, thresholds=thresholds)

        self.assertFalse(quality["is_evaluable"])
        self.assertFalse(quality["checks"]["nuclear_fraction_ok"])
        self.assertFalse(quality["checks"]["stroma_fraction_ok"])
        self.assertIn("estroma", quality["reason"])


if __name__ == "__main__":
    unittest.main()
