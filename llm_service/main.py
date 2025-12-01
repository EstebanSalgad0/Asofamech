from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
import os

app = FastAPI(title="LLaMA3 Educational Service")

# Variables de entorno configuradas en docker-compose.yml
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3:8b")


class LLMRequest(BaseModel):
    system_prompt: Optional[str] = None
    user_question: str
    intent: Optional[str] = None
    context_scope: Optional[str] = None


class LLMResponse(BaseModel):
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate", response_model=LLMResponse)
async def generate(req: LLMRequest):
    """
    Endpoint que Rasa (action_consultar_llm_medico) va a llamar.
    Internamente llama a Ollama /api/chat con el modelo configurado (Llama 3, etc.).
    """

    # Prompt base de seguridad / educativo
    base_system_prompt = (
        "Eres un asistente educativo para estudiantes del área de la salud. "
        "Explicas conceptos de medicina (especialmente tuberculosis y patologías respiratorias) "
        "solo con fines formativos. No das diagnósticos ni indicaciones de tratamiento "
        "para pacientes reales y siempre recuerdas que se debe consultar a "
        "profesionales de la salud."
    )

    # Si viene un system_prompt adicional desde Rasa, lo concatenamos
    system_prompt = base_system_prompt
    if req.system_prompt:
        system_prompt += "\n\nInstrucciones adicionales:\n" + req.system_prompt

    # Añadimos info del intent y del contexto, si está disponible
    if req.intent:
        system_prompt += f"\n\nContexto técnico: la intención detectada es '{req.intent}'."
    if req.context_scope:
        system_prompt += f"\n\nAlcance del contexto: {req.context_scope}."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.user_question},
    ]

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": LLM_MODEL,
                    "messages": messages,
                    "stream": False,
                },
            )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al llamar al modelo LLM en Ollama: {e}",
        )

    data = resp.json()
    # Formato típico de /api/chat en Ollama: {"message": {"role": "...", "content": "texto"}}
    answer = data.get("message", {}).get("content", "")

    if not answer:
        answer = (
            "En este momento no he podido generar una respuesta. "
            "Intenta reformular tu pregunta o consúltalo con un profesional de la salud."
        )

    return LLMResponse(answer=answer)
