import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, user_can_access_platform, user_to_public_payload
from ..auth_security import (
    create_access_token,
    hash_password,
    is_legacy_placeholder_hash,
    normalize_email,
    normalize_role_for_storage,
    verify_password,
)
from ..db import get_db
from ..email_service import send_password_reset_email, send_template_email
from ..models import PasswordResetToken, User


router = APIRouter(prefix="/api/auth", tags=["auth"])

# --- Rate limiting: login por IP+email ---
FAILED_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
LOGIN_WINDOW_SECONDS = 10 * 60   # ventana de 10 minutos
LOGIN_MAX_ATTEMPTS = 6            # 6 fallos por IP+email

# --- Rate limiting: login por IP (previene enumeración masiva de cuentas) ---
IP_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
IP_LOGIN_WINDOW_SECONDS = 60 * 60  # ventana de 1 hora
IP_LOGIN_MAX_ATTEMPTS = 30         # 30 intentos fallidos por IP en total

# --- Rate limiting: registro por IP ---
IP_REGISTER_ATTEMPTS: dict[str, list[float]] = {}
REGISTER_WINDOW_SECONDS = 60 * 60  # ventana de 1 hora
REGISTER_MAX_ATTEMPTS = 5          # 5 registros por IP por hora

# --- Rate limiting: forgot-password por IP ---
IP_RESET_ATTEMPTS: dict[str, list[float]] = {}
RESET_WINDOW_SECONDS = 60 * 60    # ventana de 1 hora
RESET_MAX_ATTEMPTS = 5             # 5 solicitudes por IP por hora

TOKEN_EXPIRY_HOURS = 1


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


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


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _attempt_key(request: Request, email: str) -> str:
    return f"{_client_ip(request)}:{email}"


def _prune(store: dict, key: str, window: float, now: float) -> list[float]:
    pruned = [t for t in store.get(key, []) if now - t <= window]
    store[key] = pruned
    return pruned


# ── Login por IP+email ────────────────────────────────────────────────────

def _assert_login_not_limited(request: Request, email: str) -> None:
    now = time.time()
    ip = _client_ip(request)

    ip_attempts = _prune(IP_LOGIN_ATTEMPTS, ip, IP_LOGIN_WINDOW_SECONDS, now)
    if len(ip_attempts) >= IP_LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos desde esta direccion. Intenta nuevamente mas tarde.",
        )

    key = _attempt_key(request, email)
    attempts = _prune(FAILED_LOGIN_ATTEMPTS, key, LOGIN_WINDOW_SECONDS, now)
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Intenta nuevamente en unos minutos.",
        )


def _record_failed_login(request: Request, email: str) -> None:
    now = time.time()
    ip = _client_ip(request)
    ip_attempts = _prune(IP_LOGIN_ATTEMPTS, ip, IP_LOGIN_WINDOW_SECONDS, now)
    ip_attempts.append(now)
    IP_LOGIN_ATTEMPTS[ip] = ip_attempts

    key = _attempt_key(request, email)
    attempts = _prune(FAILED_LOGIN_ATTEMPTS, key, LOGIN_WINDOW_SECONDS, now)
    attempts.append(now)
    FAILED_LOGIN_ATTEMPTS[key] = attempts


def _clear_failed_login(request: Request, email: str) -> None:
    FAILED_LOGIN_ATTEMPTS.pop(_attempt_key(request, email), None)


# ── Registro por IP ───────────────────────────────────────────────────────

def _assert_register_not_limited(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    attempts = _prune(IP_REGISTER_ATTEMPTS, ip, REGISTER_WINDOW_SECONDS, now)
    if len(attempts) >= REGISTER_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes de registro desde esta direccion. Intenta mas tarde.",
        )


def _record_register_attempt(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    attempts = _prune(IP_REGISTER_ATTEMPTS, ip, REGISTER_WINDOW_SECONDS, now)
    attempts.append(now)
    IP_REGISTER_ATTEMPTS[ip] = attempts


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
def register(payload: AuthRegisterRequest, request: Request, db: Session = Depends(get_db)):
    _assert_register_not_limited(request)
    email = _validate_email(payload.email)
    _validate_password_strength(payload.password)
    existing = db.query(User).filter(User.email == email).first()
    role = normalize_role_for_storage(payload.role)
    admin_exists = db.query(User).filter(User.role == "administrador").first() is not None
    user_count = db.query(User).count()
    bootstrap_first_user = user_count == 0
    if role in {"docente", "administrador"} and admin_exists:
        role = "estudiante"
    if bootstrap_first_user:
        role = "administrador"

    if existing and not is_legacy_placeholder_hash(existing.password_hash):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo")

    is_approved = bootstrap_first_user
    if existing:
        existing.name = payload.name.strip()
        existing.password_hash = hash_password(payload.password)
        existing.role = role
        existing.is_active = is_approved
        existing.account_status = "approved" if is_approved else "pending"
        existing.approved_at = datetime.utcnow() if is_approved else None
        existing.approved_by = existing.id if is_approved else None
        user = existing
    else:
        user = User(
            email=email,
            name=payload.name.strip(),
            password_hash=hash_password(payload.password),
            role=role,
            is_active=is_approved,
            account_status="approved" if is_approved else "pending",
            approved_at=datetime.utcnow() if is_approved else None,
        )
        db.add(user)

    _record_register_attempt(request)
    db.commit()
    db.refresh(user)
    if bootstrap_first_user:
        user.approved_by = user.id
        db.commit()
        db.refresh(user)
        return _issue_session(user)
    try:
        send_template_email(user, "account_pending", db)
    except Exception:
        pass
    return {
        "ok": True,
        "approval_required": True,
        "message": "Solicitud de cuenta recibida. Un administrador debe revisar y autorizar el acceso.",
        "user": user_to_public_payload(user),
    }


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
    if not user_can_access_platform(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta aun no esta autorizada. Espera la aprobacion del administrador.",
        )
    _clear_failed_login(request, email)
    return _issue_session(user)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Solicita recuperación de contraseña. Siempre responde igual para no enumerar cuentas."""
    _GENERIC_OK = {"ok": True, "message": "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."}

    ip = _client_ip(request)
    now = time.time()
    attempts = _prune(IP_RESET_ATTEMPTS, ip, RESET_WINDOW_SECONDS, now)
    if len(attempts) >= RESET_MAX_ATTEMPTS:
        return _GENERIC_OK

    attempts.append(now)
    IP_RESET_ATTEMPTS[ip] = attempts

    try:
        email = normalize_email(payload.email)
    except Exception:
        return _GENERIC_OK

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return _GENERIC_OK

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).delete(synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)

    db_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_at=datetime.utcnow(),
    )
    db.add(db_token)
    db.commit()

    platform_url = os.getenv("ASOFAMECH_PLATFORM_URL", "http://localhost:3000")
    reset_url = f"{platform_url}/auth/reset-password?token={raw_token}"
    try:
        send_password_reset_email(user, reset_url, db)
    except Exception:
        pass

    return _GENERIC_OK


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Establece una nueva contraseña usando el token de recuperación."""
    _validate_password_strength(payload.new_password)

    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    now = datetime.utcnow()

    db_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > now,
    ).first()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de recuperación no es válido o ha expirado. Solicita uno nuevo.",
        )

    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario no encontrado.")

    user.password_hash = hash_password(payload.new_password)
    db_token.used_at = now
    db.commit()

    return {"ok": True, "message": "Contraseña actualizada correctamente. Ya puedes iniciar sesión."}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return user_to_public_payload(current_user)
