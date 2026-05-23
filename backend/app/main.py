from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import time
import os

from .routers import admin, auth, chat, cases, dashboard, history, rag, sct, medical_images, histopathology
from .db import Base, engine

app = FastAPI(title="Backend ASOFAMECH Educativo")

# --- CORS ---
_cors_env = os.getenv("CORS_ORIGINS", "").strip()
origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],          # GET, POST, etc.
    allow_headers=["*"],          # Authorization, Content-Type, etc.
)


def create_tables_with_retry(max_retries: int = 3, delay_seconds: int = 2) -> None:
    """
    Intenta crear las tablas varias veces hasta que la base de datos
    esté lista para aceptar conexiones.
    """
    attempt = 1
    while attempt <= max_retries:
        try:
            print(f"[backend] Intentando crear tablas en la BD (intento {attempt}/{max_retries})...")
            Base.metadata.create_all(bind=engine)
            apply_compatibility_migrations()
            print("[backend] Tablas creadas (o ya existían).")
            return
        except (OperationalError, UnicodeDecodeError, SQLAlchemyError) as e:
            print(f"[backend] Error de conexión a la BD: {e}")
            print(f"[backend] Reintentando en {delay_seconds} segundos...")
            time.sleep(delay_seconds)
            attempt += 1

    print("[backend] No fue posible conectar con la BD despues de varios intentos; el servicio continuara sin inicializar tablas.")


def apply_compatibility_migrations() -> None:
    """
    Compatibilidad ligera para prototipo sin Alembic: agrega columnas nuevas
    a tablas existentes y conserva aprobadas las cuentas previas.
    """
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "users" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("users")}
        default_true = "true" if conn.dialect.name == "postgresql" else "1"
        if "is_active" not in columns:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT {default_true} NOT NULL"))
        if "account_status" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN account_status VARCHAR(30) DEFAULT 'approved' NOT NULL"))
        if "approved_at" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN approved_at TIMESTAMP NULL"))
        if "approved_by" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN approved_by INTEGER NULL"))
        conn.execute(text("UPDATE users SET account_status = 'approved' WHERE account_status IS NULL OR account_status = ''"))
        conn.execute(text("UPDATE users SET is_active = true WHERE is_active IS NULL"))
        conn.execute(text("UPDATE users SET approved_at = COALESCE(approved_at, created_at) WHERE account_status = 'approved'"))

        table_names = set(inspector.get_table_names())
        if "documents" in table_names:
            document_columns = {column["name"] for column in inspector.get_columns("documents")}
            if "source" not in document_columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN source VARCHAR(500) NULL"))
            if "document_type" not in document_columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN document_type VARCHAR(50) DEFAULT 'text' NOT NULL"))
            if "uploaded_at" not in document_columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL"))
            if "created_by" not in document_columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN created_by INTEGER NULL"))
            if "indexing_status" not in document_columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN indexing_status VARCHAR(30) DEFAULT 'indexed' NOT NULL"))
            if "indexing_error" not in document_columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN indexing_error TEXT NULL"))
            if "chunk_size" not in document_columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN chunk_size INTEGER DEFAULT 180 NOT NULL"))
            if "chunk_overlap" not in document_columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN chunk_overlap INTEGER DEFAULT 40 NOT NULL"))

        if "document_chunks" in table_names:
            chunk_columns = {column["name"] for column in inspector.get_columns("document_chunks")}
            if "embedding_provider" not in chunk_columns:
                conn.execute(text("ALTER TABLE document_chunks ADD COLUMN embedding_provider VARCHAR(160) DEFAULT 'local-hashing' NOT NULL"))

        if "chat_logs" in table_names:
            chat_log_columns = {column["name"] for column in inspector.get_columns("chat_logs")}
            if "rag_sources" not in chat_log_columns:
                conn.execute(text("ALTER TABLE chat_logs ADD COLUMN rag_sources JSON NULL"))

        if "heatmap_jobs" in table_names:
            heatmap_job_columns = {column["name"] for column in inspector.get_columns("heatmap_jobs")}
            if "user_id" not in heatmap_job_columns:
                conn.execute(text("ALTER TABLE heatmap_jobs ADD COLUMN user_id INTEGER NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_heatmap_jobs_user_id ON heatmap_jobs (user_id)"))


@app.on_event("startup")
def on_startup():
    create_tables_with_retry()
    if not os.getenv("ASOFAMECH_JWT_SECRET"):
        print(
            "[backend] ADVERTENCIA: ASOFAMECH_JWT_SECRET no configurado. "
            "Se usa el secreto de desarrollo — NO apto para producción."
        )
    print("[backend] Servicio FastAPI iniciado correctamente.")


@app.get("/health")
def health():
    return {"status": "ok"}


# Incluir los routers (endpoints /api/chat, /api/cases y /api/sct)
app.include_router(chat.router)
app.include_router(cases.router)
app.include_router(dashboard.router)
app.include_router(rag.router)
app.include_router(history.router)
app.include_router(admin.router)
app.include_router(sct.router)
app.include_router(auth.router)
app.include_router(medical_images.router)
app.include_router(histopathology.router)

# Servir archivos estáticos para imágenes
from fastapi.staticfiles import StaticFiles
import os

# Crear directorio de uploads si no existe
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
