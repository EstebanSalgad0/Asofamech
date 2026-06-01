from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditLog, User


def record_audit_log(
    db: Session,
    *,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: int | str | None = None,
    summary: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        actor_role=actor.role if actor else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        summary=summary,
        details=details or {},
        created_at=datetime.utcnow(),
    )
    db.add(log)
    return log


def audit_log_to_payload(log: AuditLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "actor_user_id": log.actor_user_id,
        "actor_email": log.actor_email,
        "actor_role": log.actor_role,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "summary": log.summary,
        "details": log.details or {},
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }
