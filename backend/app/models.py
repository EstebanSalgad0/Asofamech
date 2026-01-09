from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
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
    created_at = Column(DateTime, default=datetime.utcnow)
    
    uploaded_images = relationship("MedicalImage", back_populates="uploader")

class MedicalImage(Base):
    __tablename__ = "medical_images"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(200), unique=True, nullable=False)
    original_filename = Column(String(200), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    pathology_type = Column(String(200), nullable=True)  # Necrosis, Células de Langerhans, etc.
    file_type = Column(String(20), nullable=False)  # svs, jpg, png, etc.
    file_size = Column(Integer, nullable=True)  # tamaño en bytes
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

class ChatLog(Base):
    __tablename__ = "chat_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), nullable=True)  # o "anon"
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

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
