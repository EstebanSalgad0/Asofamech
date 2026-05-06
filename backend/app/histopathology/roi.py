from .schemas import ROIBox


MIN_ROI2_SIZE = 32
MAX_ROI2_SIZE = 4096


def roi_contains(parent: ROIBox, child: ROIBox) -> bool:
    return (
        child.x >= parent.x
        and child.y >= parent.y
        and child.x + child.width <= parent.x + parent.width
        and child.y + child.height <= parent.y + parent.height
    )


def validate_roi_bounds(roi: ROIBox, slide_width: int, slide_height: int) -> None:
    if roi.x + roi.width > slide_width:
        raise ValueError("ROI exceeds slide width")

    if roi.y + roi.height > slide_height:
        raise ValueError("ROI exceeds slide height")


def validate_roi2_size(roi: ROIBox) -> None:
    if roi.width < MIN_ROI2_SIZE or roi.height < MIN_ROI2_SIZE:
        raise ValueError(f"ROI 2 must be at least {MIN_ROI2_SIZE}x{MIN_ROI2_SIZE} pixels")

    if roi.width > MAX_ROI2_SIZE or roi.height > MAX_ROI2_SIZE:
        raise ValueError(f"ROI 2 must be at most {MAX_ROI2_SIZE}x{MAX_ROI2_SIZE} pixels")


def validate_roi_pair(roi_1: ROIBox, roi_2: ROIBox, slide_width: int, slide_height: int) -> None:
    validate_roi_bounds(roi_1, slide_width, slide_height)
    validate_roi_bounds(roi_2, slide_width, slide_height)
    validate_roi2_size(roi_2)

    if not roi_contains(roi_1, roi_2):
        raise ValueError("ROI 2 must be contained inside ROI 1")

