from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from .routers import (
    admin, auth, chat, cases, dashboard, history, image_annotations, rag,
    reports, sct, medical_images, histopathology, surveys,
)

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

    try:
        from .histopathology.heatmap_jobs import recover_stale_heatmap_jobs
        recovered = recover_stale_heatmap_jobs()
        if recovered:
            print(f"[backend] Heatmap jobs recuperados al inicio: {recovered} job(s) marcados como fallidos.")
    except Exception as exc:
        print(f"[backend] ADVERTENCIA: No se pudo recuperar jobs de heatmap atascados: {exc}")

    try:
        from .db import SessionLocal
        from .seeds.cases_loader import seed_cases
        from .seeds.rubrics_loader import seed_rubrics
        from .seeds.surveys_loader import seed_surveys
        db = SessionLocal()
        try:
            seed_surveys(db)
            seed_cases(db)
            seed_rubrics(db)
        finally:
            db.close()
    except Exception as exc:
        print(f"[backend] ADVERTENCIA: No se pudieron sembrar los datos iniciales: {exc}")

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
app.include_router(image_annotations.router)
app.include_router(histopathology.router)
app.include_router(surveys.router)
app.include_router(reports.router)

# Las imágenes médicas y tiles DZI se sirven exclusivamente a través de los
# endpoints autenticados de /api/medical-images/. No se expone el directorio
# uploads/ como archivos estáticos para evitar acceso sin autenticación.
