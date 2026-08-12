"""Capa unica de acceso al modelo generativo.

Todo el sistema (chatbot, generacion SCT y retroalimentacion de histopatologia)
pasa por aqui en vez de hablar con Ollama directamente. Eso permite cambiar de
proveedor desde la configuracion sin tocar los prompts ni la logica educativa.

Proveedores soportados:

- ``ollama``: servidor local, endpoint nativo ``/api/chat``.
- ``groq`` / ``openai_compatible``: cualquier API con ``/chat/completions`` al
  estilo OpenAI (Groq, OpenRouter, Together, vLLM, LM Studio...). Groq es el
  caso previsto: sirve Llama 3.x con latencias muy por debajo de una GPU local.

El RAG *no* pasa por esta capa. Los embeddings se siguen calculando en el
backend (sentence-transformers + pgvector), de modo que cambiar el proveedor
generativo no obliga a reindexar el corpus ni traslada los documentos a un
tercero: al proveedor externo solo viaja el prompt de cada consulta, con los
fragmentos ya seleccionados localmente.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

PROVIDER_OLLAMA = "ollama"
PROVIDER_GROQ = "groq"
PROVIDER_OPENAI_COMPATIBLE = "openai_compatible"

#: Proveedores que hablan el dialecto ``/chat/completions`` de OpenAI.
OPENAI_STYLE_PROVIDERS = {PROVIDER_GROQ, PROVIDER_OPENAI_COMPATIBLE}
VALID_PROVIDERS = {PROVIDER_OLLAMA} | OPENAI_STYLE_PROVIDERS

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", os.getenv("OLLAMA_HOST", "http://ollama:11434"))
DEFAULT_OLLAMA_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
DEFAULT_API_MODEL = os.getenv("LLM_API_MODEL", "llama-3.3-70b-versatile")
DEFAULT_TIMEOUT = 120.0

#: Valor que se devuelve en lugar de un secreto ya almacenado. El formulario lo
#: reenvia tal cual al guardar, y el backend lo interpreta como "no cambiar".
SECRET_PLACEHOLDER = "********"


class LLMConfigurationError(HTTPException):
    """Falta configuracion imprescindible para hablar con el proveedor."""

    def __init__(self, detail: str):
        super().__init__(status_code=503, detail=detail)


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    base_url: str
    api_key: str = ""
    timeout: float = DEFAULT_TIMEOUT

    @property
    def is_openai_style(self) -> bool:
        return self.provider in OPENAI_STYLE_PROVIDERS

    @property
    def label(self) -> str:
        return {
            PROVIDER_OLLAMA: "Ollama (local)",
            PROVIDER_GROQ: "Groq",
            PROVIDER_OPENAI_COMPATIBLE: "API compatible con OpenAI",
        }.get(self.provider, self.provider)


def _clean(value: object, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def normalize_provider(value: object) -> str:
    provider = _clean(value, PROVIDER_OLLAMA).lower()
    return provider if provider in VALID_PROVIDERS else PROVIDER_OLLAMA


def _default_base_url(provider: str) -> str:
    return GROQ_BASE_URL if provider == PROVIDER_GROQ else ""


def build_llm_settings(config: dict[str, str]) -> LLMSettings:
    """Traduce el mapa de configuracion IA a los parametros del proveedor."""
    provider = normalize_provider(config.get("llm_provider"))

    try:
        timeout = float(_clean(config.get("llm_request_timeout"), str(DEFAULT_TIMEOUT)))
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    timeout = min(max(timeout, 5.0), 600.0)

    if provider == PROVIDER_OLLAMA:
        return LLMSettings(
            provider=provider,
            model=_clean(config.get("llm_model"), DEFAULT_OLLAMA_MODEL),
            base_url=_clean(config.get("ollama_url"), DEFAULT_OLLAMA_URL).rstrip("/"),
            timeout=timeout,
        )

    base_url = _clean(config.get("llm_api_base_url"), _default_base_url(provider)).rstrip("/")
    return LLMSettings(
        provider=provider,
        model=_clean(config.get("llm_api_model"), DEFAULT_API_MODEL),
        base_url=base_url,
        api_key=_clean(config.get("llm_api_key")),
        timeout=timeout,
    )


def resolve_llm_settings(db: Session) -> LLMSettings:
    """Lee la configuracion vigente en base de datos y arma los parametros."""
    from .routers.admin import get_ai_config_map  # import diferido: evita ciclo

    return build_llm_settings(get_ai_config_map(db))


def _require_usable(settings: LLMSettings) -> None:
    if not settings.base_url:
        raise LLMConfigurationError(
            "El proveedor de IA externo no tiene URL base configurada. "
            "Revisa Configuracion → IA."
        )
    if settings.is_openai_style and not settings.api_key:
        raise LLMConfigurationError(
            "El proveedor de IA externo no tiene API key configurada. "
            "Revisa Configuracion → IA."
        )
    if not settings.model:
        raise LLMConfigurationError(
            "No hay modelo generativo seleccionado. Revisa Configuracion → IA."
        )


def _ollama_request(
    settings: LLMSettings,
    messages: list[dict],
    *,
    temperature: float,
    top_p: float,
    max_tokens: int,
    num_ctx: int,
    json_mode: bool,
) -> tuple[str, dict, dict]:
    payload: dict = {
        "model": settings.model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_ctx": num_ctx,
            "num_predict": max_tokens,
        },
    }
    if json_mode:
        payload["format"] = "json"
    return f"{settings.base_url}/api/chat", payload, {}


def _openai_request(
    settings: LLMSettings,
    messages: list[dict],
    *,
    temperature: float,
    top_p: float,
    max_tokens: int,
    num_ctx: int,
    json_mode: bool,
) -> tuple[str, dict, dict]:
    # num_ctx no tiene equivalente: la ventana de contexto la fija el proveedor
    # segun el modelo, no el cliente.
    payload: dict = {
        "model": settings.model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {settings.api_key}"}
    return f"{settings.base_url}/chat/completions", payload, headers


def _extract_content(settings: LLMSettings, data: dict) -> str:
    if settings.is_openai_style:
        choices = data.get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message") or {}).get("content") or ""
    return (data.get("message") or {}).get("content") or ""


def _extract_usage(settings: LLMSettings, data: dict, content: str) -> tuple[int, int, bool]:
    """Devuelve (prompt_tokens, completion_tokens, estimated).

    Cada proveedor reporta consumo distinto:
      - OpenAI-style (Groq, OpenAI): data["usage"]["prompt_tokens" | "completion_tokens"].
      - Ollama:                       data["prompt_eval_count"] + data["eval_count"].

    Si el campo esperado falta (raro), se estima como len(text)//4 y se marca
    `estimated=True` para no contaminar los agregados como si fueran oficiales.
    """
    if settings.is_openai_style:
        usage = data.get("usage") or {}
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        if isinstance(prompt, int) and isinstance(completion, int):
            return prompt, completion, False
    else:
        prompt = data.get("prompt_eval_count")
        completion = data.get("eval_count")
        if isinstance(prompt, int) and isinstance(completion, int):
            return prompt, completion, False

    # Fallback: estimacion muy gruesa. Marcamos como estimated para que el
    # panel pueda distinguir tokens autoritativos vs aproximados.
    est_out = max(1, len(content) // 4) if content else 0
    return 0, est_out, True


def _http_error_kind(status_code: int) -> str:
    if status_code == 401 or status_code == 403:
        return "http_auth"
    if status_code == 404:
        return "http_not_found"
    if status_code == 429:
        return "http_rate_limit"
    if status_code >= 500:
        return "http_server"
    return f"http_{status_code}"


def _record_usage(
    db: Session | None,
    settings: LLMSettings,
    *,
    feature: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    success: bool,
    error_kind: str | None,
    estimated: bool,
) -> None:
    """Persiste una fila en llm_usage_log. Falla silenciosa: si no se puede
    grabar (ej. tests sin la tabla, DB caida), se logea pero no revienta la
    consulta del usuario."""
    if db is None:
        return
    try:
        from .models import LlmUsageLog

        db.add(
            LlmUsageLog(
                provider=settings.provider,
                model=settings.model or "",
                feature=(feature or None),
                prompt_tokens=int(prompt_tokens or 0),
                completion_tokens=int(completion_tokens or 0),
                total_tokens=int(prompt_tokens or 0) + int(completion_tokens or 0),
                latency_ms=latency_ms,
                success=success,
                error_kind=error_kind,
                estimated=estimated,
            )
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[llm_usage] no se pudo registrar consumo: %s", exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


def _error_detail(settings: LLMSettings, response: httpx.Response) -> str:
    """Mensaje accionable sin filtrar credenciales ni el cuerpo completo."""
    if response.status_code in (401, 403):
        return (
            f"{settings.label} rechazo las credenciales (HTTP {response.status_code}). "
            "Revisa la API key en Configuracion → IA."
        )
    if response.status_code == 404:
        return (
            f"{settings.label} no reconoce el modelo '{settings.model}' "
            "o la URL base configurada."
        )
    if response.status_code == 429:
        return f"{settings.label} aplico limite de uso (HTTP 429). Reintenta en unos segundos."
    return f"{settings.label} no pudo procesar la solicitud educativa (HTTP {response.status_code})."


async def chat_completion(
    client: httpx.AsyncClient,
    settings: LLMSettings,
    messages: list[dict],
    *,
    temperature: float = 0.4,
    top_p: float = 0.9,
    max_tokens: int = 800,
    num_ctx: int = 4096,
    json_mode: bool = False,
    purpose: str = "respuesta",
    db: Session | None = None,
    feature: str | None = None,
) -> str:
    """Envia una conversacion al proveedor activo y devuelve el texto generado.

    Si se pasa ``db``, cada llamada (exitosa o fallida) queda registrada en
    ``llm_usage_log`` con los tokens autoritativos que devolvio el proveedor.
    ``feature`` etiqueta la fuente (chat, sct, cases, ...) para desglose
    en el panel de consumo; si no viene, se usa ``purpose``.
    """
    _require_usable(settings)

    builder = _openai_request if settings.is_openai_style else _ollama_request
    url, payload, headers = builder(
        settings,
        messages,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        num_ctx=num_ctx,
        json_mode=json_mode,
    )

    logger.info("Enviando %s a %s (%s)", purpose, settings.label, settings.model)
    started = time.monotonic()
    feature_tag = feature or purpose

    try:
        response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        _record_usage(
            db, settings,
            feature=feature_tag,
            prompt_tokens=0, completion_tokens=0,
            latency_ms=latency_ms,
            success=False,
            error_kind="network",
            estimated=False,
        )
        raise HTTPException(status_code=502, detail=f"{settings.label} no respondio.") from exc

    latency_ms = int((time.monotonic() - started) * 1000)

    if response.status_code != 200:
        logger.warning(
            "%s respondio %s para %s", settings.label, response.status_code, purpose
        )
        _record_usage(
            db, settings,
            feature=feature_tag,
            prompt_tokens=0, completion_tokens=0,
            latency_ms=latency_ms,
            success=False,
            error_kind=_http_error_kind(response.status_code),
            estimated=False,
        )
        raise HTTPException(status_code=502, detail=_error_detail(settings, response))

    try:
        data = response.json()
    except ValueError as exc:
        _record_usage(
            db, settings,
            feature=feature_tag,
            prompt_tokens=0, completion_tokens=0,
            latency_ms=latency_ms,
            success=False,
            error_kind="invalid_json",
            estimated=False,
        )
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo interpretar la respuesta de {settings.label}.",
        ) from exc

    content = _extract_content(settings, data).strip()
    prompt_tokens, completion_tokens, estimated = _extract_usage(settings, data, content)
    _record_usage(
        db, settings,
        feature=feature_tag,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        success=True,
        error_kind=None,
        estimated=estimated,
    )
    return content


async def probe_provider(settings: LLMSettings, timeout: float = 4.0) -> dict:
    """Comprueba disponibilidad del proveedor para el panel de integracion."""
    result = {
        "provider": settings.provider,
        "label": settings.label,
        "model": settings.model,
        "base_url": settings.base_url,
        "configured": bool(settings.base_url and settings.model)
        and (not settings.is_openai_style or bool(settings.api_key)),
        "api_key_set": bool(settings.api_key),
        "reachable": False,
        "models": [],
    }
    if not result["configured"]:
        return result

    if settings.is_openai_style:
        url = f"{settings.base_url}/models"
        headers = {"Authorization": f"Bearer {settings.api_key}"}
    else:
        url = f"{settings.base_url}/api/tags"
        headers = {}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
        if response.status_code != 200:
            return result
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return result

    if settings.is_openai_style:
        models = [m.get("id") for m in data.get("data", []) if m.get("id")]
    else:
        models = [m.get("name") for m in data.get("models", []) if m.get("name")]

    result["reachable"] = True
    result["models"] = sorted(models)
    return result
