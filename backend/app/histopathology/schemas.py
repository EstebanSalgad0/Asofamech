from typing import Dict, Optional

from pydantic import BaseModel, Field


class ROIBox(BaseModel):
    """Rectangle expressed in level-0 image coordinates."""

    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)


class HistopathologyAnalyzeRequest(BaseModel):
    image_id: int
    roi_1: ROIBox
    roi_2: ROIBox


class HistopathologyPrediction(BaseModel):
    predicted_class: str
    confidence: float
    probabilities: Dict[str, float]


class HistopathologyAnalyzeResponse(BaseModel):
    image_id: int
    roi_1: ROIBox
    roi_2: ROIBox
    prediction: HistopathologyPrediction
    patch_size: Dict[str, int]
    model: Dict[str, str]
    warning: str
    slide_dimensions: Optional[Dict[str, int]] = None

