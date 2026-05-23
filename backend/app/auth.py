from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .auth_security import (
    decode_access_token,
    display_role,
    normalize_email,
    normalize_role_for_storage,
    TokenError,
)
from .db import get_db
from .models import User


bearer_scheme = HTTPBearer(auto_error=False)

ROLE_STUDENT = "estudiante"
ROLE_TEACHER = "docente"
ROLE_ADMIN = "administrador"

PERM_USE_PLATFORM = "use_platform"
PERM_USE_CHAT = "use_chat"
PERM_USE_HISTOPATHOLOGY = "use_histopathology"
PERM_SOLVE_SCT = "solve_sct"
PERM_VIEW_OWN_HISTORY = "view_own_history"
PERM_MANAGE_CASES = "manage_cases"
PERM_MANAGE_SCT = "manage_sct"
PERM_REVIEW_STUDENTS = "review_students"
PERM_MANAGE_EDUCATIONAL_CONTENT = "manage_educational_content"
PERM_MANAGE_USERS = "manage_users"
PERM_MANAGE_AI_CONFIG = "manage_ai_config"
PERM_MANAGE_RAG = "manage_rag"
PERM_MANAGE_IMAGES = "manage_images"
PERM_DELETE_SENSITIVE_RESOURCES = "delete_sensitive_resources"

ROLE_PERMISSIONS = {
    ROLE_STUDENT: {
        PERM_USE_PLATFORM,
        PERM_USE_CHAT,
        PERM_USE_HISTOPATHOLOGY,
        PERM_SOLVE_SCT,
        PERM_VIEW_OWN_HISTORY,
    },
    ROLE_TEACHER: {
        PERM_USE_PLATFORM,
        PERM_USE_CHAT,
        PERM_USE_HISTOPATHOLOGY,
        PERM_SOLVE_SCT,
        PERM_VIEW_OWN_HISTORY,
        PERM_MANAGE_CASES,
        PERM_MANAGE_SCT,
        PERM_REVIEW_STUDENTS,
        PERM_MANAGE_EDUCATIONAL_CONTENT,
        PERM_MANAGE_RAG,
        PERM_MANAGE_IMAGES,
    },
    ROLE_ADMIN: {
        PERM_USE_PLATFORM,
        PERM_USE_CHAT,
        PERM_USE_HISTOPATHOLOGY,
        PERM_SOLVE_SCT,
        PERM_VIEW_OWN_HISTORY,
        PERM_MANAGE_CASES,
        PERM_MANAGE_SCT,
        PERM_REVIEW_STUDENTS,
        PERM_MANAGE_EDUCATIONAL_CONTENT,
        PERM_MANAGE_USERS,
        PERM_MANAGE_AI_CONFIG,
        PERM_MANAGE_RAG,
        PERM_MANAGE_IMAGES,
        PERM_DELETE_SENSITIVE_RESOURCES,
    },
}


def user_to_public_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "role_label": display_role(user.role),
        "is_active": bool(user.is_active),
        "account_status": user.account_status or "pending",
    }


def user_can_access_platform(user: User) -> bool:
    return bool(user.is_active) and (user.account_status or "pending") == "approved"


def user_role(user_or_role: User | str | None) -> str:
    role = getattr(user_or_role, "role", user_or_role)
    return normalize_role_for_storage(role)


def user_has_role(user: User, *allowed_roles: str) -> bool:
    normalized_allowed = {normalize_role_for_storage(role) for role in allowed_roles}
    return user_role(user) in normalized_allowed


def user_has_permission(user: User, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(user_role(user), set())


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (TokenError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc) or "Token invalido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.query(User).filter(User.id == user_id).first()
    if not user or normalize_email(user.email) != normalize_email(payload.get("email", user.email)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user_can_access_platform(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta pendiente de aprobacion o deshabilitada",
        )
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return get_current_user(credentials, db)


def require_roles(*allowed_roles: str):
    normalized_allowed = {normalize_role_for_storage(role) for role in allowed_roles}

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if user_role(current_user) not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para realizar esta accion",
            )
        return current_user

    return _dependency


def require_permission(permission: str):
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if not user_has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para realizar esta accion",
            )
        return current_user

    return _dependency


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not user_has_role(current_user, ROLE_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden realizar esta accion",
        )
    return current_user
