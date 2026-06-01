import json
import logging
import os
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from .models import User


logger = logging.getLogger(__name__)

_STATUS_META: dict[str, dict] = {
    "account_approved":  {"accent": "#16a34a", "badge": "&#10003; Cuenta Habilitada",    "cta": True},
    "account_rejected":  {"accent": "#dc2626", "badge": "&#10007; Solicitud No Aprobada", "cta": False},
    "account_suspended": {"accent": "#d97706", "badge": "&#9888; Cuenta Suspendida",      "cta": False},
    "account_pending":   {"accent": "#2563eb", "badge": "&#8987; Solicitud Recibida",     "cta": False},
}

_DEFAULT_TEMPLATES: dict[str, dict] = {
    "account_approved": {
        "subject": "Tu cuenta ASOFAMECH ha sido habilitada",
        "body": (
            "Hola {nombre},\n\n"
            "Tu cuenta fue revisada y habilitada por el administrador.\n"
            "Ya puedes ingresar a la plataforma desde:\n{url_plataforma}\n\n"
            "Este es un correo automatico del prototipo educativo ASOFAMECH."
        ),
    },
    "account_rejected": {
        "subject": "Tu solicitud de cuenta ASOFAMECH no fue aprobada",
        "body": (
            "Hola {nombre},\n\n"
            "Lamentablemente tu solicitud de acceso a la plataforma ASOFAMECH no fue aprobada.\n"
            "Si crees que esto es un error, contacta al administrador.\n\n"
            "Este es un correo automatico del prototipo educativo ASOFAMECH."
        ),
    },
    "account_suspended": {
        "subject": "Tu cuenta ASOFAMECH ha sido suspendida",
        "body": (
            "Hola {nombre},\n\n"
            "Tu cuenta en la plataforma ASOFAMECH ha sido suspendida temporalmente.\n"
            "Contacta al administrador para mas informacion.\n\n"
            "Este es un correo automatico del prototipo educativo ASOFAMECH."
        ),
    },
    "account_pending": {
        "subject": "Solicitud de cuenta ASOFAMECH recibida",
        "body": (
            "Hola {nombre},\n\n"
            "Hemos recibido tu solicitud de acceso a la plataforma ASOFAMECH.\n"
            "Un administrador revisara tu cuenta en breve y te notificaremos por este medio.\n\n"
            "Este es un correo automatico del prototipo educativo ASOFAMECH."
        ),
    },
}


def _smtp_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "on"}


def _outbox_path() -> Path:
    return Path(os.getenv("ASOFAMECH_EMAIL_OUTBOX_PATH", "artifacts/email_outbox.jsonl"))


def _log_email_outbox(to_email: str, subject: str, body: str, reason: str) -> None:
    path = _outbox_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "to": to_email,
        "subject": subject,
        "body": body,
        "reason": reason,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _resolve_smtp(override: dict | None = None) -> dict:
    cfg = override or {}
    return {
        "host": cfg.get("email_smtp_host") or os.getenv("SMTP_HOST", ""),
        "port": int(cfg.get("email_smtp_port") or os.getenv("SMTP_PORT", "587") or 587),
        "user": cfg.get("email_smtp_user") or os.getenv("SMTP_USER", ""),
        "password": cfg.get("email_smtp_password") or os.getenv("SMTP_PASSWORD", ""),
        "from_addr": (
            cfg.get("email_smtp_from") or os.getenv("SMTP_FROM", "")
            or cfg.get("email_smtp_user") or os.getenv("SMTP_USER", "")
        ),
        "tls": _smtp_bool(cfg.get("email_smtp_tls") or os.getenv("SMTP_TLS"), True),
    }


def _body_to_html_content(body: str) -> str:
    """Convierte texto plano a párrafos HTML; omite el último si es solo el aviso automático."""
    paragraphs = [p.strip() for p in body.strip().split("\n\n") if p.strip()]
    if paragraphs and "correo automatico" in paragraphs[-1].lower():
        paragraphs = paragraphs[:-1]
    parts = []
    for p in paragraphs:
        inner = p.replace("\n", "<br>")
        parts.append(
            f'<p style="margin:0 0 20px;color:#334155;font-size:15px;line-height:1.8;">{inner}</p>'
        )
    return "".join(parts)


def _build_html(body: str, key: str | None = None, platform_url: str = "") -> str:
    meta = _STATUS_META.get(key or "", {})
    accent = meta.get("accent", "#1e3a5f")
    badge = meta.get("badge", "")
    show_cta = meta.get("cta", False) and bool(platform_url)

    content_html = _body_to_html_content(body)

    badge_row = ""
    if badge:
        badge_row = f"""\
        <tr>
          <td style="background:{accent};padding:11px 44px;text-align:center;">
            <span style="color:#ffffff;font-size:13px;font-weight:700;letter-spacing:0.6px;">{badge}</span>
          </td>
        </tr>"""

    cta_html = ""
    if show_cta:
        cta_html = f"""\
        <div style="text-align:center;margin:30px 0 8px;">
          <a href="{platform_url}"
             style="display:inline-block;background:{accent};color:#ffffff;padding:14px 44px;
                    border-radius:8px;text-decoration:none;font-size:15px;font-weight:700;
                    letter-spacing:0.3px;">
            Ingresar a la Plataforma
          </a>
        </div>"""

    year = datetime.now(UTC).year

    return f"""\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASOFAMECH</title>
</head>
<body style="margin:0;padding:0;background:#eef2f7;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f7;padding:48px 16px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="max-width:560px;width:100%;border-radius:14px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,0.10);">

        <!-- ── Header ── -->
        <tr>
          <td style="background:#1e3a5f;padding:32px 44px;text-align:center;">
            <div style="color:#ffffff;font-size:26px;font-weight:800;letter-spacing:5px;
                        text-transform:uppercase;">ASOFAMECH</div>
            <div style="color:rgba(255,255,255,0.55);font-size:11px;margin-top:6px;
                        letter-spacing:2px;text-transform:uppercase;">
              Plataforma Educativa &middot; Histopatolog&iacute;a
            </div>
          </td>
        </tr>

        <!-- ── Status badge ── -->
        {badge_row}

        <!-- ── Body ── -->
        <tr>
          <td style="background:#ffffff;padding:42px 44px 36px;">
            {content_html}
            {cta_html}
          </td>
        </tr>

        <!-- ── Divider ── -->
        <tr>
          <td style="background:#ffffff;padding:0 44px;">
            <div style="border-top:1px solid #e2e8f0;"></div>
          </td>
        </tr>

        <!-- ── Footer ── -->
        <tr>
          <td style="background:#f8fafc;padding:22px 44px;text-align:center;
                     border-top:3px solid {accent};">
            <p style="margin:0 0 6px;color:#64748b;font-size:12px;font-weight:600;
                      text-transform:uppercase;letter-spacing:0.8px;">
              ASOFAMECH &mdash; Sistema Educativo
            </p>
            <p style="margin:0;color:#94a3b8;font-size:11px;line-height:1.7;">
              Este es un correo autom&aacute;tico. Por favor no respondas este mensaje.<br>
              Para consultas, contacta al administrador de la plataforma.
            </p>
            <p style="margin:14px 0 0;color:#cbd5e1;font-size:10px;">
              &copy; {year} ASOFAMECH &mdash; Prototipo Educativo
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _send_smtp(to_email: str, subject: str, body: str, smtp: dict, html: str | None = None) -> dict:
    if not smtp["host"] or not smtp["from_addr"]:
        _log_email_outbox(to_email, subject, body, "smtp_not_configured")
        return {
            "sent": False,
            "reason": "smtp_not_configured",
            "message": "SMTP no configurado; correo registrado en outbox local.",
        }
    msg = EmailMessage()
    msg["From"] = smtp["from_addr"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(smtp["host"], smtp["port"], timeout=10) as conn:
            if smtp["tls"]:
                conn.starttls()
            if smtp["user"] and smtp["password"]:
                conn.login(smtp["user"], smtp["password"])
            conn.send_message(msg)
        return {"sent": True, "reason": "sent", "message": "Correo enviado."}
    except Exception as exc:
        logger.warning("Error SMTP enviando a %s: %s", to_email, exc)
        _log_email_outbox(to_email, subject, body, f"smtp_error:{exc}")
        return {
            "sent": False,
            "reason": "smtp_error",
            "message": f"Error SMTP: {exc}; correo registrado en outbox local.",
        }


def _smtp_cfg_from_db(db) -> dict:
    from .models import AIConfiguration
    keys = {"email_smtp_host", "email_smtp_port", "email_smtp_user",
            "email_smtp_password", "email_smtp_from", "email_smtp_tls"}
    return {r.key: r.value for r in db.query(AIConfiguration).filter(AIConfiguration.key.in_(keys)).all()}


def _get_template(db, key: str) -> tuple[str, str]:
    from .models import EmailTemplate
    t = db.query(EmailTemplate).filter(EmailTemplate.key == key).first()
    defaults = _DEFAULT_TEMPLATES.get(key, {"subject": "", "body": ""})
    return (t.subject if t else defaults["subject"], t.body if t else defaults["body"])


def _render(body: str, user: User) -> str:
    url = os.getenv("ASOFAMECH_PLATFORM_URL", "http://localhost:3000/auth")
    return body.replace("{nombre}", user.name or "").replace("{url_plataforma}", url)


def send_template_email(user: User, key: str, db, smtp_config: dict | None = None) -> dict:
    """Envía el correo correspondiente a la clave de plantilla indicada."""
    smtp = smtp_config if smtp_config is not None else _smtp_cfg_from_db(db)
    subject, body = _get_template(db, key)
    rendered_body = _render(body, user)
    platform_url = os.getenv("ASOFAMECH_PLATFORM_URL", "http://localhost:3000/auth")
    html = _build_html(rendered_body, key=key, platform_url=platform_url)
    return _send_smtp(user.email, subject, rendered_body, _resolve_smtp(smtp), html=html)


# Compat: mantiene la firma original para no romper llamadas existentes
def send_account_approved_email(user: User, smtp_config: dict | None = None, db=None) -> dict:
    if db is not None:
        return send_template_email(user, "account_approved", db, smtp_config)
    subject = _DEFAULT_TEMPLATES["account_approved"]["subject"]
    body = _DEFAULT_TEMPLATES["account_approved"]["body"]
    rendered_body = _render(body, user)
    html = _build_html(rendered_body, key="account_approved")
    return _send_smtp(user.email, subject, rendered_body, _resolve_smtp(smtp_config), html=html)


def send_password_reset_email(user: User, reset_url: str, db) -> dict:
    """Envía correo con enlace único para restablecer contraseña (válido 1 hora)."""
    smtp = _smtp_cfg_from_db(db)
    subject = "Recuperación de contraseña – ASOFAMECH"
    body = (
        f"Hola {user.name},\n\n"
        "Recibimos una solicitud para restablecer la contraseña de tu cuenta ASOFAMECH.\n\n"
        "Haz clic en el botón de abajo para crear una nueva contraseña.\n"
        "El enlace es válido por 1 hora y solo puede usarse una vez.\n\n"
        f"{reset_url}\n\n"
        "Si no solicitaste este cambio, ignora este correo. Tu contraseña no cambiará.\n\n"
        "Este es un correo automatico del prototipo educativo ASOFAMECH."
    )
    meta_key = "_password_reset"
    accent = "#2563eb"
    content_html = _body_to_html_content(body)
    cta_html = f"""\
        <div style="text-align:center;margin:30px 0 8px;">
          <a href="{reset_url}"
             style="display:inline-block;background:{accent};color:#ffffff;padding:14px 44px;
                    border-radius:8px;text-decoration:none;font-size:15px;font-weight:700;
                    letter-spacing:0.3px;">
            Restablecer contraseña
          </a>
        </div>
        <p style="text-align:center;color:#94a3b8;font-size:12px;margin-top:18px;">
          O copia este enlace en tu navegador:<br>
          <span style="color:#2563eb;word-break:break-all;">{reset_url}</span>
        </p>"""
    year = datetime.now(UTC).year
    html = f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASOFAMECH – Recuperación de contraseña</title></head>
<body style="margin:0;padding:0;background:#eef2f7;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f7;padding:48px 16px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="max-width:560px;width:100%;border-radius:14px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,0.10);">
        <tr>
          <td style="background:#1e3a5f;padding:32px 44px;text-align:center;">
            <div style="color:#ffffff;font-size:26px;font-weight:800;letter-spacing:5px;text-transform:uppercase;">ASOFAMECH</div>
            <div style="color:rgba(255,255,255,0.55);font-size:11px;margin-top:6px;letter-spacing:2px;text-transform:uppercase;">
              Plataforma Educativa &middot; Histopatolog&iacute;a
            </div>
          </td>
        </tr>
        <tr>
          <td style="background:{accent};padding:11px 44px;text-align:center;">
            <span style="color:#ffffff;font-size:13px;font-weight:700;letter-spacing:0.6px;">&#128274; Recuperación de Contraseña</span>
          </td>
        </tr>
        <tr>
          <td style="background:#ffffff;padding:42px 44px 36px;">
            {content_html}
            {cta_html}
          </td>
        </tr>
        <tr><td style="background:#ffffff;padding:0 44px;"><div style="border-top:1px solid #e2e8f0;"></div></td></tr>
        <tr>
          <td style="background:#f8fafc;padding:22px 44px;text-align:center;border-top:3px solid {accent};">
            <p style="margin:0 0 6px;color:#64748b;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;">
              ASOFAMECH &mdash; Sistema Educativo
            </p>
            <p style="margin:0;color:#94a3b8;font-size:11px;line-height:1.7;">
              Este es un correo autom&aacute;tico. Por favor no respondas este mensaje.
            </p>
            <p style="margin:14px 0 0;color:#cbd5e1;font-size:10px;">&copy; {year} ASOFAMECH</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return _send_smtp(user.email, subject, body, _resolve_smtp(smtp), html=html)


def send_test_email(user: User, smtp_config: dict | None = None) -> dict:
    subject = "Correo de prueba – ASOFAMECH"
    body = (
        f"Hola {user.name},\n\n"
        "Este es un correo de prueba enviado desde el panel de administracion de ASOFAMECH.\n"
        "Si lo recibes, la configuracion SMTP es correcta.\n\n"
        f"Enviado el: {datetime.now(UTC).strftime('%d/%m/%Y %H:%M UTC')}"
    )
    html = _build_html(body, key=None)
    return _send_smtp(user.email, subject, body, _resolve_smtp(smtp_config), html=html)
