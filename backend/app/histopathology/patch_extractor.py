from pathlib import Path
from typing import Tuple

from PIL import Image

from .schemas import ROIBox


class PatchExtractionError(RuntimeError):
    pass


class OpenSlidePatchExtractor:
    """Reads slide dimensions and extracts ROI 2 patches in level-0 coordinates."""

    def get_slide_dimensions(self, slide_path: str) -> Tuple[int, int]:
        path = Path(slide_path)
        if not path.exists():
            raise PatchExtractionError(f"Slide file does not exist: {slide_path}")

        openslide_error = None
        try:
            import openslide

            with openslide.OpenSlide(str(path)) as slide:
                return slide.dimensions
        except Exception as exc:
            openslide_error = exc

        try:
            with Image.open(path) as image:
                return image.size
        except Exception as exc:
            raise PatchExtractionError(
                f"Could not read image dimensions. OpenSlide error: {openslide_error}. PIL error: {exc}"
            ) from exc

    def extract_roi2(self, slide_path: str, roi_2: ROIBox) -> Image.Image:
        path = Path(slide_path)
        if not path.exists():
            raise PatchExtractionError(f"Slide file does not exist: {slide_path}")

        openslide_error = None
        try:
            import openslide

            with openslide.OpenSlide(str(path)) as slide:
                patch = slide.read_region(
                    location=(roi_2.x, roi_2.y),
                    level=0,
                    size=(roi_2.width, roi_2.height),
                )
                return patch.convert("RGB")
        except Exception as exc:
            openslide_error = exc

        try:
            with Image.open(path) as image:
                image = image.convert("RGB")
                box = (roi_2.x, roi_2.y, roi_2.x + roi_2.width, roi_2.y + roi_2.height)
                return image.crop(box)
        except Exception as exc:
            raise PatchExtractionError(
                f"Could not extract ROI 2. OpenSlide error: {openslide_error}. PIL error: {exc}"
            ) from exc

