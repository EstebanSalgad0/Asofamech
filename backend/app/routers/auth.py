from fastapi import APIRouter, Depends, HTTPException, status
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


class AuthLoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)


class AuthRegisterRequest(AuthLoginRequest):
    name: str = Field(min_length=2)
    role: str = "estudiante"


def _validate_email(email: str) -> str:
    normalized = normalize_email(email)
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Correo electronico invalido")
    return normalized


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
    existing = db.query(User).filter(User.email == email).first()
    role = normalize_role_for_storage(payload.role)

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
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)):
    email = _validate_email(payload.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contrasena incorrectos",
        )
    return _issue_session(user)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return user_to_public_payload(current_user)
