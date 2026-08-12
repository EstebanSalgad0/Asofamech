from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class CaseLinkIn(BaseModel):
    """Recurso externo del caso: bibliografia, guia, articulo, video o Wooclap."""
    kind: str = "otro"
    label: str
    url: str
    description: Optional[str] = None


class CaseLinkOut(CaseLinkIn):
    id: int
    case_id: int
    position: int = 0
    created_at: Optional[str] = None


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
    # Imagenes ilustrativas del caso (radiografia, TAC...), distintas de la
    # lamina histopatologica referenciada por image_id.
    images: List[dict] = []
    # Recursos externos: material complementario y actividades interactivas.
    links: List[dict] = []
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
    links: Optional[List[CaseLinkIn]] = None
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
    # Omitirlo deja los enlaces intactos; enviarlo reemplaza el conjunto completo.
    links: Optional[List[CaseLinkIn]] = None

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


class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ========== Encuestas de percepción ==========

class SurveyItemOut(BaseModel):
    id: int
    section: str
    section_order: int
    item_order: int
    text: str
    item_type: str            # "likert_1_5" | "open_text"
    required: bool

    class Config:
        orm_mode = True


class SurveyOut(BaseModel):
    id: int
    code: str
    title: str
    description: Optional[str] = None
    status: str               # "open" | "archived"
    created_at: Optional[str] = None

    class Config:
        orm_mode = True


class SurveyDetailOut(SurveyOut):
    items: List[SurveyItemOut] = []
    already_answered: bool = False


class SurveyStatusUpdate(BaseModel):
    status: str               # "open" | "archived"


class SurveyAnswerIn(BaseModel):
    item_id: int
    value_int: Optional[int] = None    # 1..5 para Likert
    value_text: Optional[str] = None   # respuesta libre


class SurveyResponseCreate(BaseModel):
    answers: List[SurveyAnswerIn]


class ItemStat(BaseModel):
    item_id: int
    section: str
    text: str
    item_type: str
    average: Optional[float] = None
    n: int
    distribution: dict = {}    # {"1": x, "2": y, ...}


class SectionStat(BaseModel):
    section: str
    average: Optional[float] = None
    n_items: int


class SurveySummary(BaseModel):
    survey_code: str
    survey_title: str
    total_responses: int
    global_average: Optional[float] = None
    section_averages: List[SectionStat] = []
    item_stats: List[ItemStat] = []


class OpenAnswerOut(BaseModel):
    item_id: int
    item_text: str
    section: str
    answers: List[str] = []
