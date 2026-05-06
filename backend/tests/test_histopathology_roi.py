import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.histopathology.roi import roi_contains, validate_roi_pair
from app.histopathology.schemas import ROIBox


class HistopathologyROITestCase(unittest.TestCase):
    def test_roi2_inside_roi1_is_valid(self):
        roi_1 = ROIBox(x=100, y=100, width=500, height=500)
        roi_2 = ROIBox(x=200, y=220, width=128, height=128)

        validate_roi_pair(roi_1, roi_2, slide_width=1000, slide_height=1000)

        self.assertTrue(roi_contains(roi_1, roi_2))

    def test_roi2_outside_roi1_is_invalid(self):
        roi_1 = ROIBox(x=100, y=100, width=300, height=300)
        roi_2 = ROIBox(x=350, y=350, width=128, height=128)

        with self.assertRaises(ValueError):
            validate_roi_pair(roi_1, roi_2, slide_width=1000, slide_height=1000)

    def test_roi2_outside_slide_is_invalid(self):
        roi_1 = ROIBox(x=0, y=0, width=900, height=900)
        roi_2 = ROIBox(x=850, y=850, width=128, height=128)

        with self.assertRaises(ValueError):
            validate_roi_pair(roi_1, roi_2, slide_width=900, slide_height=900)


if __name__ == "__main__":
    unittest.main()
