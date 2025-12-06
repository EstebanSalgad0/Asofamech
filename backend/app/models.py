from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from datetime import datetime
from .db import Base

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
