from typing import Any, Dict, Optional

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


class HistopathologyScanRequest(BaseModel):
    image_id: int
    roi: ROIBox
    tile_size: int = Field(512, ge=64, le=2048)
    stride: int = Field(512, ge=32, le=2048)
    max_tiles: int = Field(64, ge=1, le=256)


class HistopathologyPrediction(BaseModel):
    predicted_class: str
    confidence: float
    probabilities: Dict[str, float]
    predicted_index: Optional[int] = None
    model_predicted_class: Optional[str] = None
    class_mapping: Optional[Dict[str, str]] = None
    decision_threshold: Optional[float] = None


class HistopathologyAnalyzeResponse(BaseModel):
    trace_id: str
    analyzed_at: str
    image_id: int
    status: str = "clasificado"
    clase: Optional[str] = None
    confidence: Optional[float] = None
    probabilities: Optional[Dict[str, float]] = None
    reason: Optional[str] = None
    recommendation: Optional[str] = None
    roi_1: ROIBox
    roi_2: ROIBox
    prediction: HistopathologyPrediction
    patch_size: Dict[str, Any]
    patch_metadata: Dict[str, Any]
    roi_quality: Optional[Dict[str, Any]] = None
    debug_artifacts: Optional[Dict[str, Any]] = None
    model: Dict[str, Any]
    warning: str
    slide_dimensions: Optional[Dict[str, int]] = None
