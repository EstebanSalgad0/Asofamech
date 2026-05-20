from typing import Any, Dict, List, Optional

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
    educational_label: Optional[str] = Field(None, max_length=120)
    educational_note: Optional[str] = Field(None, max_length=600)
    educational_type: Optional[str] = Field(None, max_length=40)


class HeatmapEducationalMetadataUpdate(BaseModel):
    educational_label: Optional[str] = Field(None, max_length=120)
    educational_note: Optional[str] = Field(None, max_length=600)
    educational_type: Optional[str] = Field(None, max_length=40)


class HistopathologyPrediction(BaseModel):
    predicted_class: str
    confidence: float
    probabilities: Dict[str, float]
    predicted_index: Optional[int] = None
    model_predicted_class: Optional[str] = None
    class_mapping: Optional[Dict[str, str]] = None
    decision_threshold: Optional[float] = None


DOCENTE_LABEL_CHOICES = [
    "correcto",
    "falso_positivo",
    "falso_negativo",
    "estroma_no_evaluable",
    "zona_tumoral_confirmada",
    "zona_sana_confirmada",
]

DOCENTE_LABEL_DISPLAY = {
    "correcto": "Correcto",
    "falso_positivo": "Falso positivo",
    "falso_negativo": "Falso negativo",
    "estroma_no_evaluable": "Estroma / No evaluable",
    "zona_tumoral_confirmada": "Zona tumoral confirmada",
    "zona_sana_confirmada": "Zona sana confirmada",
}


class CorrectionCreateRequest(BaseModel):
    docente_label: str = Field(..., description="Una de: " + ", ".join(DOCENTE_LABEL_CHOICES))
    docente_note: Optional[str] = Field(None, max_length=600)
    include_in_dataset: bool = False


class HistopathologySessionSummary(BaseModel):
    id: int
    trace_id: str
    analyzed_at: str
    status: str
    clase: Optional[str] = None
    confidence: Optional[float] = None
    roi_1: Dict[str, int]
    roi_2: Dict[str, int]

    class Config:
        orm_mode = True


class HistopathologySessionDetail(HistopathologySessionSummary):
    probabilities: Optional[Dict[str, float]] = None
    reason: Optional[str] = None
    recommendation: Optional[str] = None
    roi_quality_metrics: Optional[Dict[str, Any]] = None
    warning: Optional[str] = None
    educational_feedback: Optional[str] = None


class HistopathologySessionListResponse(BaseModel):
    image_id: Optional[int] = None
    count: int
    items: List[HistopathologySessionSummary]


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
    educational_feedback: Optional[str] = None
