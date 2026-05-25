from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from .routers import admin, auth, chat, cases, dashboard, feedback, history, rag, sct, medical_images, histopathology

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


@app.on_event("startup")
def on_startup():
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
app.include_router(feedback.router)

# Las imágenes médicas y tiles DZI se sirven exclusivamente a través de los
# endpoints autenticados de /api/medical-images/. No se expone el directorio
# uploads/ como archivos estáticos para evitar acceso sin autenticación.
