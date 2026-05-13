import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
JWT_ALGORITHM = "HS256"


class TokenError(ValueError):
    pass


def jwt_secret() -> str:
    return os.getenv("ASOFAMECH_JWT_SECRET", "dev-only-change-this-asofamech-secret")


def access_token_expire_seconds() -> int:
    raw = os.getenv("ASOFAMECH_ACCESS_TOKEN_EXPIRE_MINUTES", "720")
    try:
        minutes = int(raw)
    except ValueError:
        minutes = 720
    return max(5, minutes) * 60


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def normalize_role_for_storage(role: str | None) -> str:
    value = (role or "").strip().lower()
    if value in {"administrador", "admin", "administrator"}:
        return "administrador"
    if value in {"docente", "profesor", "profesora", "teacher"}:
        return "docente"
    return "estudiante"


def display_role(role: str | None) -> str:
    normalized = normalize_role_for_storage(role)
    if normalized == "administrador":
        return "Administrador"
    if normalized == "docente":
        return "Profesor"
    return "Estudiante"


def hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(24)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        algorithm, iterations_raw, salt, expected_hex = stored_hash.split("$", 3)
        iterations = int(iterations_raw)
    except (ValueError, AttributeError):
        return False
    if algorithm != PASSWORD_ALGORITHM or iterations <= 0:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(actual, expected_hex)


def is_legacy_placeholder_hash(stored_hash: str | None) -> bool:
    return stored_hash in {"hashed_password", "mock_password", "password"}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _sign(unsigned_token: str) -> str:
    signature = hmac.new(
        jwt_secret().encode("utf-8"),
        unsigned_token.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(signature)


def create_access_token(payload: Dict[str, Any]) -> str:
    now = int(time.time())
    claims = {
        **payload,
        "iat": now,
        "exp": now + access_token_expire_seconds(),
    }
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    unsigned = f"{encoded_header}.{encoded_payload}"
    return f"{unsigned}.{_sign(unsigned)}"


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        encoded_header, encoded_payload, signature = token.split(".", 2)
    except ValueError as exc:
        raise TokenError("Token invalido") from exc

    unsigned = f"{encoded_header}.{encoded_payload}"
    if not hmac.compare_digest(_sign(unsigned), signature):
        raise TokenError("Firma de token invalida")

    try:
        header = json.loads(_b64url_decode(encoded_header).decode("utf-8"))
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise TokenError("Token invalido") from exc

    if header.get("alg") != JWT_ALGORITHM or header.get("typ") != "JWT":
        raise TokenError("Algoritmo de token no soportado")

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        raise TokenError("Token expirado")

    if "sub" not in payload:
        raise TokenError("Token sin sujeto")

    return payload
