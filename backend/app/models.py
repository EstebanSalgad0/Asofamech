from sqlalchemy import Column, Integer, BigInteger, Float, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(50), default="estudiante")  # estudiante, docente, administrador
    is_active = Column(Boolean, default=False, nullable=False)
    account_status = Column(String(30), default="pending", nullable=False)  # pending, approved, rejected, suspended
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    uploaded_images = relationship("MedicalImage", back_populates="uploader")
    approver = relationship("User", remote_side=[id])

class MedicalImage(Base):
    __tablename__ = "medical_images"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(200), unique=True, nullable=False)
    original_filename = Column(String(200), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    pathology_type = Column(String(200), nullable=True)  # Necrosis, Células de Langerhans, etc.
    file_type = Column(String(20), nullable=False)  # svs, jpg, png, etc.
    file_size = Column(BigInteger, nullable=True)  # tamaño en bytes
    file_path = Column(String(500), nullable=False)
    dzi_path = Column(String(500), nullable=True)  # ruta al DZI si fue procesado
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    uploader = relationship("User", back_populates="uploaded_images")

class Case(Base):
    __tablename__ = "cases"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)   # resumen del caso
    body = Column(Text, nullable=False)          # caso clínico completo
    is_active = Column(Boolean, default=True)

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)       # texto que luego se puede usar para RAG
    tags = Column(String(200), nullable=True)
    source = Column(String(500), nullable=True)
    document_type = Column(String(50), nullable=False, default="text")
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    indexing_status = Column(String(30), nullable=False, default="pending")  # pending, indexed, failed
    indexing_error = Column(Text, nullable=True)
    chunk_size = Column(Integer, nullable=False, default=180)
    chunk_overlap = Column(Integer, nullable=False, default=40)
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    creator = relationship("User")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False)
    embedding_provider = Column(String(160), nullable=False, default="local-hashing")
    token_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")

class ChatLog(Base):
    __tablename__ = "chat_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), nullable=True)  # o "anon"
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    rag_sources = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIConfiguration(Base):
    __tablename__ = "ai_configurations"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(120), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    value_type = Column(String(40), nullable=False, default="string")
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailTemplate(Base):
    __tablename__ = "email_templates"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    label = Column(String(200), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SCTTest(Base):
    __tablename__ = "sct_tests"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)          # Nombre identificador
    difficulty = Column(String(50), nullable=False)     # pregrado, internado, residente
    focus = Column(String(200), nullable=False)         # tuberculosis pulmonar, diabetes, etc.
    num_items = Column(Integer, nullable=False)         # Cantidad de ítems
    items_json = Column(JSON, nullable=False)           # Array de ítems SCT
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class HeatmapJob(Base):
    __tablename__ = "heatmap_jobs"
    job_id = Column(String(36), primary_key=True)
    trace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="queued")
    progress = Column(Float, nullable=False, default=0.0)
    processed_tiles = Column(Integer, nullable=False, default=0)
    total_tiles = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    request_json = Column(JSON, nullable=True)
    result_json = Column(JSON, nullable=True)
    worker_limit = Column(Integer, nullable=False, default=1)

    user = relationship("User")


class SCTAttempt(Base):
    __tablename__ = "sct_attempts"
    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("sct_tests.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    answers_json = Column(JSON, nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    correct_count = Column(Integer, nullable=False, default=0)
    total_items = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    test = relationship("SCTTest")
    user = relationship("User")


class HistopathologySession(Base):
    """Registro persistente de cada analisis ROI 2 realizado por un usuario."""
    __tablename__ = "histopathology_sessions"
    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(36), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    image_id = Column(Integer, ForeignKey("medical_images.id"), nullable=False, index=True)
    analyzed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    roi_1 = Column(JSON, nullable=False)
    roi_2 = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False)         # clasificado, roi_no_evaluable, resultado_incierto
    clase = Column(String(50), nullable=True)           # no_metastasico, metastasico, incierto, roi_no_evaluable
    confidence = Column(JSON, nullable=True)            # float almacenado como JSON (puede ser null)
    probabilities = Column(JSON, nullable=True)         # {clase: probabilidad}
    reason = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    roi_quality_metrics = Column(JSON, nullable=True)   # metricas compactas de QC
    warning = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("User")
    image = relationship("MedicalImage")
    correction = relationship("HistopathologyCorrection", back_populates="session", uselist=False)


class HistopathologyCorrection(Base):
    """Corrección docente sobre una sesión de análisis ROI 2."""
    __tablename__ = "histopathology_corrections"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("histopathology_sessions.id"), nullable=False, unique=True, index=True)
    trace_id = Column(String(36), nullable=False, index=True)    # denormalizado para lookup rápido
    image_id = Column(Integer, nullable=False, index=True)       # denormalizado para filtros
    docente_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # correcto | falso_positivo | falso_negativo | estroma_no_evaluable | zona_tumoral_confirmada | zona_sana_confirmada
    docente_label = Column(String(80), nullable=False)
    docente_note = Column(Text, nullable=True)
    include_in_dataset = Column(Boolean, default=False, nullable=False)
    corrected_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    session = relationship("HistopathologySession", back_populates="correction")
    docente = relationship("User")
