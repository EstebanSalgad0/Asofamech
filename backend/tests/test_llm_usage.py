"""Tests del tracking de consumo del LLM.

Verifica:
  - Extraccion correcta de tokens por proveedor (Groq/OpenAI vs Ollama).
  - Fallback estimated=True cuando el proveedor no reporta.
  - Persistencia en llm_usage_log con db pasada.
  - No persistencia cuando db=None (backwards compat).
"""
import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.llm_service import (
    LLMSettings,
    PROVIDER_GROQ,
    PROVIDER_OLLAMA,
    _extract_usage,
    chat_completion,
)
from app.models import AIConfiguration, LlmUsageLog, User
from app.routers import admin


MESSAGES = [{"role": "user", "content": "test"}]


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _openai_settings() -> LLMSettings:
    return LLMSettings(
        provider=PROVIDER_GROQ,
        model="llama-3.1-8b-instant",
        base_url="https://api.example.com/v1",
        api_key="k",
    )


def _ollama_settings() -> LLMSettings:
    return LLMSettings(
        provider=PROVIDER_OLLAMA,
        model="llama3.1:8b",
        base_url="http://ollama:11434",
    )


# ── extraccion de usage ─────────────────────────────────────────────────────

def test_extract_usage_openai_returns_authoritative_tokens():
    data = {"usage": {"prompt_tokens": 137, "completion_tokens": 82}}
    prompt, completion, estimated = _extract_usage(_openai_settings(), data, "algo")
    assert prompt == 137
    assert completion == 82
    assert estimated is False


def test_extract_usage_ollama_returns_authoritative_tokens():
    data = {"prompt_eval_count": 42, "eval_count": 91}
    prompt, completion, estimated = _extract_usage(_ollama_settings(), data, "algo")
    assert prompt == 42
    assert completion == 91
    assert estimated is False


def test_extract_usage_falls_back_when_provider_omits_usage():
    prompt, completion, estimated = _extract_usage(_openai_settings(), {"choices": []}, "hola")
    assert estimated is True
    assert prompt == 0
    assert completion > 0   # estimacion sobre el texto


# ── persistencia end-to-end ─────────────────────────────────────────────────

@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_chat_completion_persists_usage_row_when_db_is_passed(db_session):
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "listo"}}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 4},
        })

    settings = _openai_settings()

    async def run():
        async with _client(handler) as client:
            return await chat_completion(
                client, settings, MESSAGES,
                db=db_session, feature="unit_test",
            )

    text = asyncio.run(run())
    assert text == "listo"

    rows = db_session.query(LlmUsageLog).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.provider == "groq"
    assert row.model == "llama-3.1-8b-instant"
    assert row.feature == "unit_test"
    assert row.prompt_tokens == 15
    assert row.completion_tokens == 4
    assert row.total_tokens == 19
    assert row.success is True
    assert row.estimated is False
    assert row.latency_ms is not None and row.latency_ms >= 0


def test_chat_completion_does_not_persist_when_db_is_none(db_session):
    """Backwards compat: si nadie pasa db, no se toca la tabla."""
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "x"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })

    settings = _openai_settings()

    async def run():
        async with _client(handler) as client:
            return await chat_completion(client, settings, MESSAGES)

    asyncio.run(run())
    assert db_session.query(LlmUsageLog).count() == 0


def test_chat_completion_records_failure_row_on_http_error(db_session):
    def handler(request):
        return httpx.Response(429, json={"error": "rate limit"})

    settings = _openai_settings()

    async def run():
        async with _client(handler) as client:
            await chat_completion(client, settings, MESSAGES, db=db_session, feature="chat")

    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        asyncio.run(run())

    rows = db_session.query(LlmUsageLog).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.success is False
    assert row.error_kind == "http_rate_limit"
    assert row.total_tokens == 0


# ── endpoint /api/admin/llm/usage/summary ────────────────────────────────────

def _make_admin(user_id: int = 1) -> User:
    return User(
        id=user_id, email="a@a.a", name="Admin", password_hash="x",
        role="administrador", is_active=True, account_status="approved",
    )


@pytest.fixture
def admin_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add(_make_admin())
        # Precios del panel
        db.add(AIConfiguration(key="llm_price_input_per_million", value="0.10"))
        db.add(AIConfiguration(key="llm_price_output_per_million", value="0.20"))
        # 2 llamadas ok + 1 fallida, distintos features/modelos
        db.add(LlmUsageLog(provider="groq", model="llama-3.1-8b-instant", feature="chat",
                           prompt_tokens=1000, completion_tokens=500, total_tokens=1500,
                           latency_ms=300, success=True, estimated=False))
        db.add(LlmUsageLog(provider="groq", model="llama-3.1-8b-instant", feature="sct",
                           prompt_tokens=2000, completion_tokens=1000, total_tokens=3000,
                           latency_ms=800, success=True, estimated=False))
        db.add(LlmUsageLog(provider="groq", model="llama-3.1-8b-instant", feature="chat",
                           prompt_tokens=0, completion_tokens=0, total_tokens=0,
                           latency_ms=120, success=False, error_kind="http_rate_limit"))
        db.commit()

    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[get_db] = lambda: (yield from _yield_db(SessionLocal))
    app.dependency_overrides[get_current_user] = lambda: _make_admin()

    with TestClient(app) as client:
        yield client

    Base.metadata.drop_all(bind=engine)


def _yield_db(SessionLocal):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_usage_summary_returns_totals_and_breakdowns(admin_client):
    resp = admin_client.get("/api/admin/llm/usage/summary?window=30d")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["totals"]["prompt_tokens"] == 3000
    assert data["totals"]["completion_tokens"] == 1500
    assert data["totals"]["total_tokens"] == 4500
    assert data["totals"]["calls"] == 3
    assert data["totals"]["successful_calls"] == 2
    assert data["totals"]["failed_calls"] == 1

    # Costo: 3000 * 0.10/1M + 1500 * 0.20/1M = 0.0003 + 0.0003 = 0.0006
    assert data["totals"]["cost_usd"] == pytest.approx(0.0006, abs=1e-6)

    # Breakdown por feature
    features = {r["key"]: r for r in data["by_feature"]}
    assert features["chat"]["total_tokens"] == 1500     # llamada fallida suma 0
    assert features["sct"]["total_tokens"] == 3000

    assert data["pricing"]["input_per_million_usd"] == 0.10
    assert data["pricing"]["output_per_million_usd"] == 0.20


def test_usage_recent_lists_calls_without_user_id(admin_client):
    resp = admin_client.get("/api/admin/llm/usage/recent?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert all("user_id" not in item for item in data["items"])
    assert all("cost_usd" in item for item in data["items"])


def test_usage_export_csv_excludes_user_id(admin_client):
    resp = admin_client.get("/api/admin/llm/usage/export.csv?window=30d")
    assert resp.status_code == 200
    body = resp.text
    header = body.splitlines()[0].lower()
    assert "user_id" not in header
    assert "prompt_tokens" in header
    assert "cost_usd" in header
