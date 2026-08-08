import asyncio

import httpx
import pytest
from fastapi import HTTPException

from app.llm_service import (
    GROQ_BASE_URL,
    PROVIDER_GROQ,
    PROVIDER_OLLAMA,
    SECRET_PLACEHOLDER,
    build_llm_settings,
    chat_completion,
    normalize_provider,
    probe_provider,
)


MESSAGES = [{"role": "user", "content": "Explica la neumonia adquirida en la comunidad"}]


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ── resolucion de configuracion ──────────────────────────────────────────────

def test_provider_falls_back_to_ollama_when_unknown():
    assert normalize_provider("gemini") == PROVIDER_OLLAMA
    assert normalize_provider(None) == PROVIDER_OLLAMA
    assert normalize_provider(" GROQ ") == PROVIDER_GROQ


def test_ollama_settings_use_ollama_url_and_local_model():
    settings = build_llm_settings({
        "llm_provider": "ollama",
        "llm_model": "llama3.1:8b",
        "ollama_url": "http://ollama:11434/",
        "llm_api_model": "llama-3.3-70b-versatile",
    })

    assert settings.provider == PROVIDER_OLLAMA
    assert settings.model == "llama3.1:8b"
    assert settings.base_url == "http://ollama:11434"
    assert settings.is_openai_style is False


def test_groq_settings_use_api_fields_and_default_base_url():
    settings = build_llm_settings({
        "llm_provider": "groq",
        "llm_api_base_url": "",
        "llm_api_key": "gsk_demo",
        "llm_api_model": "llama-3.3-70b-versatile",
    })

    assert settings.base_url == GROQ_BASE_URL
    assert settings.model == "llama-3.3-70b-versatile"
    assert settings.is_openai_style is True


def test_timeout_is_clamped_to_a_sane_range():
    assert build_llm_settings({"llm_request_timeout": "0"}).timeout == 5.0
    assert build_llm_settings({"llm_request_timeout": "99999"}).timeout == 600.0
    assert build_llm_settings({"llm_request_timeout": "no-numerico"}).timeout == 120.0


# ── transporte por proveedor ─────────────────────────────────────────────────

def test_ollama_request_uses_native_endpoint_and_options():
    import json as _json

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = _json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"message": {"content": "respuesta local"}})

    settings = build_llm_settings({"llm_provider": "ollama", "ollama_url": "http://ollama:11434"})

    async def run():
        async with _client(handler) as client:
            return await chat_completion(client, settings, MESSAGES, max_tokens=256, num_ctx=2048)

    text = asyncio.run(run())

    assert text == "respuesta local"
    assert captured["url"] == "http://ollama:11434/api/chat"
    assert captured["json"]["options"]["num_predict"] == 256
    assert captured["json"]["options"]["num_ctx"] == 2048
    assert captured["auth"] is None


def test_openai_style_request_sends_bearer_and_max_tokens():
    import json as _json

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = _json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "respuesta remota"}}]},
        )

    settings = build_llm_settings({
        "llm_provider": "groq",
        "llm_api_key": "gsk_demo",
        "llm_api_model": "llama-3.3-70b-versatile",
    })

    async def run():
        async with _client(handler) as client:
            return await chat_completion(client, settings, MESSAGES, max_tokens=256, json_mode=True)

    text = asyncio.run(run())

    assert text == "respuesta remota"
    assert captured["url"] == f"{GROQ_BASE_URL}/chat/completions"
    assert captured["auth"] == "Bearer gsk_demo"
    assert captured["json"]["max_tokens"] == 256
    assert captured["json"]["response_format"] == {"type": "json_object"}
    # num_ctx no existe en el dialecto OpenAI: enviarlo provocaria un 400.
    assert "options" not in captured["json"]
    assert "num_ctx" not in captured["json"]


def test_missing_api_key_fails_before_any_network_call():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no debe salir trafico sin credencial")

    settings = build_llm_settings({"llm_provider": "groq", "llm_api_key": ""})

    async def run():
        async with _client(handler) as client:
            await chat_completion(client, settings, MESSAGES)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(run())

    assert exc.value.status_code == 503
    assert "API key" in exc.value.detail


def test_invalid_credentials_produce_actionable_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API Key"}})

    settings = build_llm_settings({"llm_provider": "groq", "llm_api_key": "gsk_malo"})

    async def run():
        async with _client(handler) as client:
            await chat_completion(client, settings, MESSAGES)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(run())

    assert exc.value.status_code == 502
    assert "credenciales" in exc.value.detail
    # El detalle nunca puede arrastrar la clave hacia la respuesta HTTP.
    assert "gsk_malo" not in exc.value.detail


def test_probe_reports_unconfigured_provider_without_network():
    settings = build_llm_settings({"llm_provider": "groq", "llm_api_key": ""})
    status = asyncio.run(probe_provider(settings))

    assert status["configured"] is False
    assert status["reachable"] is False
    assert status["api_key_set"] is False


def test_secret_placeholder_is_not_a_plausible_key():
    assert SECRET_PLACEHOLDER
    assert not SECRET_PLACEHOLDER.startswith("gsk_")
