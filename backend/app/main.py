from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError
import time
import os

from .routers import chat, cases, sct, medical_images
from .db import Base, engine

app = FastAPI(title="Backend TB Educativa")

# --- CORS ---
# Si quieres permitir todo en desarrollo, puedes cambiar a allow_origins=["*"]
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],          # GET, POST, etc.
    allow_headers=["*"],          # Authorization, Content-Type, etc.
)


def create_tables_with_retry(max_retries: int = 10, delay_seconds: int = 2) -> None:
    """
    Intenta crear las tablas varias veces hasta que la base de datos
    esté lista para aceptar conexiones.
    """
    attempt = 1
    while attempt <= max_retries:
        try:
            print(f"[backend] Intentando crear tablas en la BD (intento {attempt}/{max_retries})...")
            Base.metadata.create_all(bind=engine)
            print("[backend] Tablas creadas (o ya existían).")
            return
        except OperationalError as e:
            print(f"[backend] Error de conexión a la BD: {e}")
            print(f"[backend] Reintentando en {delay_seconds} segundos...")
            time.sleep(delay_seconds)
            attempt += 1

    print("[backend] No fue posible conectar con la BD después de varios intentos.")


@app.on_event("startup")
def on_startup():
    # Crear tablas al arrancar, con reintentos
    create_tables_with_retry()
    print("[backend] Servicio FastAPI iniciado correctamente.")


@app.get("/health")
def health():
    return {"status": "ok"}


# Incluir los routers (endpoints /api/chat, /api/cases y /api/sct)
app.include_router(chat.router)
app.include_router(cases.router)
app.include_router(sct.router)
app.include_router(medical_images.router)

# Servir archivos estáticos para imágenes
from fastapi.staticfiles import StaticFiles
import os

# Crear directorio de uploads si no existe
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
