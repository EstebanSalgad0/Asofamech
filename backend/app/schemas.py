from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class CaseOut(BaseModel):
    id: int
    title: str
    description: str

    class Config:
        orm_mode = True

class CaseCreate(BaseModel):
    title: str
    description: str
    body: str

# ========== SCT Schemas ==========

class DifficultyLevel(str, Enum):
    pregrado = "pregrado"
    internado = "internado"
    residente = "residente"

class SCTGenerateRequest(BaseModel):
    num_items: int = 5
    difficulty: DifficultyLevel = DifficultyLevel.pregrado
    focus: str = "tuberculosis pulmonar"

class SCTItem(BaseModel):
    id: int
    vignette: str  # Viñeta clínica
    hypothesis: str  # Hipótesis clínica
    new_info: str  # Nueva información
    scale_options: List[str] = [
        "−2: Descarta completamente",
        "−1: Menos probable",
        "0: Sin cambio",
        "+1: Más probable",
        "+2: Apoya fuertemente"
    ]
    correct_answer: int  # Valor de -2 a +2
    explanation: str  # Explicación de la respuesta correcta

class SCTResponse(BaseModel):
    items: List[SCTItem]
    total: int
    difficulty: str
    focus: str

class SCTSaveRequest(BaseModel):
    name: str  # Nombre identificador del test
    difficulty: str
    focus: str
    num_items: int
    items: List[SCTItem]

class SCTTestOut(BaseModel):
    id: int
    name: str
    difficulty: str
    focus: str
    num_items: int
    created_at: str
    
    class Config:
        orm_mode = True

class SCTTestDetail(BaseModel):
    id: int
    name: str
    difficulty: str
    focus: str
    num_items: int
    items: List[SCTItem]
    created_at: str
    
    class Config:
        orm_mode = True
