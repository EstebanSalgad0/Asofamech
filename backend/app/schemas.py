from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class CaseOut(BaseModel):
    id: int
    title: str
    description: str
    body: str
    clinical_context: Optional[str] = None
    learning_objectives: Optional[str] = None
    difficulty: Optional[str] = None
    topic: Optional[str] = None
    image_id: Optional[int] = None
    sct_test_id: Optional[int] = None
    created_by: Optional[int] = None
    status: str = "draft"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        orm_mode = True

class CaseCreate(BaseModel):
    title: str
    description: str
    body: str
    clinical_context: Optional[str] = None
    learning_objectives: Optional[str] = None
    difficulty: Optional[str] = None
    topic: Optional[str] = None
    image_id: Optional[int] = None
    sct_test_id: Optional[int] = None
    status: str = "draft"

class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    body: Optional[str] = None
    clinical_context: Optional[str] = None
    learning_objectives: Optional[str] = None
    difficulty: Optional[str] = None
    topic: Optional[str] = None
    image_id: Optional[int] = None
    sct_test_id: Optional[int] = None

class CaseStatusUpdate(BaseModel):
    status: str

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
    status: str = "published"  # draft | published | archived

class SCTTestOut(BaseModel):
    id: int
    name: str
    difficulty: str
    focus: str
    num_items: int
    created_at: str
    status: str = "published"
    created_by: Optional[int] = None

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
    status: str = "published"

    class Config:
        orm_mode = True

class SCTTestUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None   # draft | published | archived
    focus: Optional[str] = None


class SCTAnswerItem(BaseModel):
    item_id: int
    selected_answer: int


class SCTAttemptCreate(BaseModel):
    answers: List[SCTAnswerItem]
    started_at: Optional[str] = None


class SCTAttemptOut(BaseModel):
    id: int
    test_id: int
    user_id: int
    score: float
    correct_count: int
    total_items: int
    completed_at: str

    class Config:
        orm_mode = True


class SCTAttemptWithTest(SCTAttemptOut):
    """SCTAttemptOut enriquecido con metadatos del test para vistas de historial."""
    test_name: str = ""
    test_focus: str = ""
    test_difficulty: str = ""


class SCTAttemptDetail(SCTAttemptOut):
    answers_json: List[dict]
    test_name: str
    test_focus: str
    test_difficulty: str


class SCTAttemptAdminOut(SCTAttemptWithTest):
    """Para docente/admin: incluye identidad del estudiante."""
    user_email: str = ""
    user_name: str = ""


# ========== Usability Feedback Schemas ==========

class FeedbackCreate(BaseModel):
    nav_clarity: int          # 1-5
    viewer_ease: int          # 1-5
    roi_ease: int             # 1-5
    ai_clarity: int           # 1-5
    chatbot_utility: int      # 1-5
    sct_utility: int          # 1-5
    observations: Optional[str] = None
    display_name: Optional[str] = None

class FeedbackOut(BaseModel):
    id: int
    role_at_submission: str
    nav_clarity: int
    viewer_ease: int
    roi_ease: int
    ai_clarity: int
    chatbot_utility: int
    sct_utility: int
    observations: Optional[str] = None
    display_name: Optional[str] = None
    submitted_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        orm_mode = True

class DimensionAverage(BaseModel):
    nav_clarity: float
    viewer_ease: float
    roi_ease: float
    ai_clarity: float
    chatbot_utility: float
    sct_utility: float

class RoleBreakdown(BaseModel):
    count: int
    averages: DimensionAverage

class FeedbackSummary(BaseModel):
    total_responses: int
    averages: DimensionAverage
    by_role: dict
    recent_observations: List[str]

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class FeedbackResponseItem(BaseModel):
    role: str
    display_name: Optional[str] = None
    nav_clarity: int
    viewer_ease: int
    roi_ease: int
    ai_clarity: int
    chatbot_utility: int
    sct_utility: int
    observations: Optional[str] = None
    submitted_at: Optional[str] = None
