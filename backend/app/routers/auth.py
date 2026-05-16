import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, user_to_public_payload
from ..auth_security import (
    create_access_token,
    hash_password,
    is_legacy_placeholder_hash,
    normalize_email,
    normalize_role_for_storage,
    verify_password,
)
from ..db import get_db
from ..models import User


router = APIRouter(prefix="/api/auth", tags=["auth"])
FAILED_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
LOGIN_WINDOW_SECONDS = 10 * 60
LOGIN_MAX_ATTEMPTS = 6


class AuthLoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class AuthRegisterRequest(AuthLoginRequest):
    name: str = Field(min_length=2)
    role: str = "estudiante"


def _validate_email(email: str) -> str:
    normalized = normalize_email(email)
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Correo electronico invalido")
    return normalized


def _validate_password_strength(password: str) -> None:
    if len(password or "") < 8:
        raise HTTPException(status_code=422, detail="La contrasena debe tener al menos 8 caracteres")
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise HTTPException(
            status_code=422,
            detail="La contrasena debe incluir letras y numeros",
        )


def _attempt_key(request: Request, email: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}:{email}"


def _prune_attempts(key: str, now: float) -> list[float]:
    attempts = [
        timestamp
        for timestamp in FAILED_LOGIN_ATTEMPTS.get(key, [])
        if now - timestamp <= LOGIN_WINDOW_SECONDS
    ]
    FAILED_LOGIN_ATTEMPTS[key] = attempts
    return attempts


def _assert_login_not_limited(request: Request, email: str) -> None:
    key = _attempt_key(request, email)
    attempts = _prune_attempts(key, time.time())
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Intenta nuevamente en unos minutos.",
        )


def _record_failed_login(request: Request, email: str) -> None:
    key = _attempt_key(request, email)
    attempts = _prune_attempts(key, time.time())
    attempts.append(time.time())
    FAILED_LOGIN_ATTEMPTS[key] = attempts


def _clear_failed_login(request: Request, email: str) -> None:
    FAILED_LOGIN_ATTEMPTS.pop(_attempt_key(request, email), None)


def _issue_session(user: User) -> dict:
    public_user = user_to_public_payload(user)
    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
        }
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": public_user,
    }


@router.post("/register")
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)):
    email = _validate_email(payload.email)
    _validate_password_strength(payload.password)
    existing = db.query(User).filter(User.email == email).first()
    role = normalize_role_for_storage(payload.role)
    admin_exists = db.query(User).filter(User.role == "administrador").first() is not None
    if role in {"docente", "administrador"} and admin_exists:
        role = "estudiante"

    if existing and not is_legacy_placeholder_hash(existing.password_hash):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo")

    if existing:
        existing.name = payload.name.strip()
        existing.password_hash = hash_password(payload.password)
        existing.role = role
        user = existing
    else:
        user = User(
            email=email,
            name=payload.name.strip(),
            password_hash=hash_password(payload.password),
            role=role,
        )
        db.add(user)

    db.commit()
    db.refresh(user)
    return _issue_session(user)


@router.post("/login")
def login(payload: AuthLoginRequest, request: Request, db: Session = Depends(get_db)):
    email = _validate_email(payload.email)
    _assert_login_not_limited(request, email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        _record_failed_login(request, email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contrasena incorrectos",
        )
    _clear_failed_login(request, email)
    return _issue_session(user)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return user_to_public_payload(current_user)
