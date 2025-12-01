from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

RASA_URL = os.getenv("RASA_URL", "http://rasa:5005/webhooks/rest/webhook")


class ChatRequest(BaseModel):
    text: str


@router.post("/chat")
async def chat(req: ChatRequest):
    payload = {
        "sender": "usuario_demo",
        "message": req.text,
    }

    logger.info(f"Enviando a Rasa URL: {RASA_URL}")
    logger.info(f"Payload: {payload}")

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(RASA_URL, json=payload)
            logger.info(f"Rasa respondió con status: {resp.status_code}")
            logger.info(f"Respuesta: {resp.text[:200]}")
            
            if resp.status_code != 200:
                # Rasa devolvió error explícito
                raise HTTPException(
                    status_code=502,
                    detail=f"Rasa devolvió un error HTTP {resp.status_code}: {resp.text}",
                )

            try:
                rasa_messages = resp.json()  # lista de {text, ...}
            except ValueError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"No se pudo parsear la respuesta de Rasa como JSON: {e}",
                )

            # Normalizamos la respuesta para el frontend
            return {"messages": rasa_messages}
            
    except httpx.HTTPError as e:
        # Error al conectar con Rasa
        logger.error(f"Excepción al conectar con Rasa: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Error al contactar al servidor Rasa: {e}",
        )
    except HTTPException:
        # Re-lanzar excepciones HTTP que ya creamos
        raise
    except Exception as e:
        logger.error(f"Excepción inesperada: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Error inesperado: {e}",
        )
