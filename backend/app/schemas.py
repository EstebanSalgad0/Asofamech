from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

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
    case_code: Optional[str] = None
    # Estructura PA-ASO-001. Al estudiante se le entrega sin las secciones
    # docentes (Practical Script, justificacion, banco de evaluacion).
    structured: Optional[dict] = None
    clinical_context: Optional[str] = None
    learning_objectives: Optional[str] = None
    difficulty: Optional[str] = None
    topic: Optional[str] = None
    image_id: Optional[int] = None
    sct_test_id: Optional[int] = None
    mcq_test_id: Optional[int] = None
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
    # Si se envia `structured`, el cuerpo se regenera desde ella y este campo
    # pasa a ser opcional.
    body: Optional[str] = None
    case_code: Optional[str] = None
    structured: Optional[dict] = None
    clinical_context: Optional[str] = None
    learning_objectives: Optional[str] = None
    difficulty: Optional[str] = None
    topic: Optional[str] = None
    image_id: Optional[int] = None
    sct_test_id: Optional[int] = None
    mcq_test_id: Optional[int] = None
    links: Optional[List[CaseLinkIn]] = None
    status: str = "draft"

class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    body: Optional[str] = None
    case_code: Optional[str] = None
    structured: Optional[dict] = None
    clinical_context: Optional[str] = None
    learning_objectives: Optional[str] = None
    difficulty: Optional[str] = None
    topic: Optional[str] = None
    image_id: Optional[int] = None
    sct_test_id: Optional[int] = None
    mcq_test_id: Optional[int] = None
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


class WordFrequency(BaseModel):
    text: str
    count: int          # veces que aparece el termino en total
    responses: int      # respuestas distintas donde aparece


class WordCloudOut(BaseModel):
    item_id: int
    item_text: str
    section: str
    total_answers: int
    words: List[WordFrequency] = []


# ========== Revisor de informes por rúbrica ==========

class RubricLevelIn(BaseModel):
    label: str
    score: float
    descriptor: Optional[str] = None


class RubricCriterionIn(BaseModel):
    name: str
    description: Optional[str] = None
    levels: List[RubricLevelIn] = []


class RubricBandIn(BaseModel):
    label: str
    min: float
    max: float


class RubricCreate(BaseModel):
    title: str
    description: Optional[str] = None
    criteria: List[RubricCriterionIn] = []
    bands: List[RubricBandIn] = []
    guidance: Optional[str] = None
    case_id: Optional[int] = None
    source_filename: Optional[str] = None
    # Pasada esta fecha la rubrica deja de aceptar entregas nuevas. Sin fecha,
    # queda abierta indefinidamente.
    due_at: Optional[datetime] = None
    status: str = "draft"


class RubricUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    criteria: Optional[List[RubricCriterionIn]] = None
    bands: Optional[List[RubricBandIn]] = None
    guidance: Optional[str] = None
    case_id: Optional[int] = None
    due_at: Optional[datetime] = None
    status: Optional[str] = None


class RubricStatusUpdate(BaseModel):
    status: str


class RubricOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    criteria: List[dict] = []
    bands: List[dict] = []
    guidance: Optional[str] = None
    max_score: float = 0.0
    case_id: Optional[int] = None
    source_filename: Optional[str] = None
    due_at: Optional[str] = None
    status: str = "draft"
    created_by: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RubricStudentProgress(BaseModel):
    """Cuanto de sus 3 intentos gasto un estudiante en esta rubrica, y su ultima nota."""
    user_id: int
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    attempts: int
    attempts_max: int
    latest_submission_id: Optional[int] = None
    latest_status: Optional[str] = None
    # Puntaje del intento mas reciente, en la escala propia de la rubrica
    # (ej. 18 de 21) — no convertido a otra escala.
    latest_score: Optional[float] = None
    latest_max_score: Optional[float] = None
    latest_released: bool = False


class RubricDraftOut(BaseModel):
    """Propuesta extraída de un documento; el docente la revisa antes de guardar."""
    title: str
    description: Optional[str] = None
    criteria: List[dict] = []
    bands: List[dict] = []
    max_score: float = 0.0
    source_filename: Optional[str] = None


class EvaluationRelease(BaseModel):
    released: bool
    teacher_note: Optional[str] = None
    teacher_score: Optional[float] = None


class ReportEvaluationOut(BaseModel):
    total_score: float
    max_score: float
    band: Optional[str] = None
    criteria: List[dict] = []
    summary: Optional[str] = None
    strengths: List[str] = []
    improvements: List[str] = []
    provider: Optional[str] = None
    model: Optional[str] = None
    evaluated_at: Optional[str] = None
    released: bool = False
    released_at: Optional[str] = None
    teacher_note: Optional[str] = None
    teacher_score: Optional[float] = None
    # Puntaje que corresponde mostrar: el del docente si corrigió, si no el del modelo.
    effective_score: float = 0.0


class ReportSubmissionOut(BaseModel):
    id: int
    # Agrupa las filas que nacieron del mismo archivo subido contra varias
    # rubricas a la vez: mismo batch_id = mismo informe, distintos resultados.
    batch_id: str
    rubric_id: int
    rubric_title: Optional[str] = None
    case_id: Optional[int] = None
    case_title: Optional[str] = None
    user_id: Optional[int] = None
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    original_filename: str
    file_type: str
    file_size: Optional[int] = None
    status: str
    error: Optional[str] = None
    created_at: Optional[str] = None
    # Ausente mientras la evaluación no esté liberada al estudiante.
    evaluation: Optional[ReportEvaluationOut] = None
    # Para el estudiante: hay resultado, pero el docente aún no lo publica.
    evaluation_pending_release: bool = False


# ========== Anotaciones docentes sobre imagenes ==========
# Independientes del clasificador: un rectangulo con texto sobre una region de
# la imagen, sin relacion con HistopathologySession ni con CONCH/CAMELYON.

class AnnotationRoi(BaseModel):
    """Rectangulo en coordenadas de imagen nivel-0 (los mismos pixeles absolutos
    que ROIBox), pero definido aqui de forma independiente: una anotacion no
    debe depender del modulo de histopatologia ni de su pipeline de IA."""
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    width: int = Field(..., gt=0, le=100000)
    height: int = Field(..., gt=0, le=100000)


class ImageAnnotationCreate(BaseModel):
    roi: AnnotationRoi
    # El ovalo es el inscrito en `roi`, no un esquema de coordenadas distinto.
    shape: str = "rect"  # rect | ellipse
    label: str = Field(..., min_length=1, max_length=200)
    note: Optional[str] = Field(None, max_length=2000)


class ImageAnnotationUpdate(BaseModel):
    roi: Optional[AnnotationRoi] = None
    shape: Optional[str] = None
    label: Optional[str] = Field(None, min_length=1, max_length=200)
    note: Optional[str] = Field(None, max_length=2000)


class ImageAnnotationOut(BaseModel):
    id: int
    image_id: int
    roi: dict
    shape: str = "rect"
    label: str
    note: Optional[str] = None
    created_by: Optional[int] = None
    creator_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DiseaseCategoryCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=60)
    label: str = Field(..., min_length=1, max_length=100)
    icon: str = Field("🧫", min_length=1, max_length=16)
    description: Optional[str] = Field(None, max_length=300)
    keywords: List[str] = Field(default_factory=list)
    sort_order: int = 0


class DiseaseCategoryUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    icon: Optional[str] = Field(None, min_length=1, max_length=16)
    description: Optional[str] = Field(None, max_length=300)
    keywords: Optional[List[str]] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class MCQItem(BaseModel):
    id: int
    question: str
    options: List[str] = Field(..., min_length=2, max_length=8)
    correct_index: int
    explanation: str = ""


class MCQImportResponse(BaseModel):
    items: List[MCQItem]
    total: int
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class MCQSaveRequest(BaseModel):
    name: str
    topic: str
    difficulty: Optional[str] = None
    num_items: int
    items: List[MCQItem]
    status: str = "published"


class MCQTestOut(BaseModel):
    id: int
    name: str
    topic: str
    difficulty: Optional[str] = None
    num_items: int
    created_at: str
    status: str = "published"
    created_by: Optional[int] = None

    class Config:
        orm_mode = True


class MCQTestDetail(BaseModel):
    id: int
    name: str
    topic: str
    difficulty: Optional[str] = None
    num_items: int
    items: List[MCQItem]
    created_at: str
    status: str = "published"

    class Config:
        orm_mode = True


class MCQTestUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    topic: Optional[str] = None


class MCQAnswerItem(BaseModel):
    item_id: int
    selected_index: int


class MCQAttemptCreate(BaseModel):
    answers: List[MCQAnswerItem]
    started_at: Optional[str] = None


class MCQAttemptOut(BaseModel):
    id: int
    test_id: int
    user_id: int
    score: float
    correct_count: int
    total_items: int
    completed_at: str

    class Config:
        orm_mode = True


class MCQAttemptWithTest(MCQAttemptOut):
    test_name: str = ""
    test_topic: str = ""
    test_difficulty: str = ""


class MCQAttemptDetail(MCQAttemptOut):
    answers_json: List[dict]
    test_name: str
    test_topic: str
    test_difficulty: str


class MCQAttemptAdminOut(MCQAttemptWithTest):
    user_email: str = ""
    user_name: str = ""


class DiseaseCategoryOut(BaseModel):
    id: int
    key: str
    label: str
    icon: str
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    sort_order: int = 0
    is_active: bool = True
    created_at: Optional[str] = None

    class Config:
        orm_mode = True
