import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.auth import user_can_access_platform, user_to_public_payload
from app.email_service import send_account_approved_email
from app.models import User
from app.routers.admin import _safe_status, _validate_admin_email, _validate_admin_password


class UserApprovalTestCase(unittest.TestCase):
    def test_pending_user_cannot_access_platform(self):
        user = User(
            email="estudiante@example.com",
            name="Estudiante",
            password_hash="hash",
            role="estudiante",
            is_active=False,
            account_status="pending",
        )

        self.assertFalse(user_can_access_platform(user))

    def test_approved_active_user_can_access_platform(self):
        user = User(
            email="estudiante@example.com",
            name="Estudiante",
            password_hash="hash",
            role="estudiante",
            is_active=True,
            account_status="approved",
        )

        self.assertTrue(user_can_access_platform(user))

    def test_public_payload_exposes_account_state_without_password(self):
        user = User(
            id=10,
            email="docente@example.com",
            name="Docente",
            password_hash="secret",
            role="docente",
            is_active=True,
            account_status="approved",
        )

        payload = user_to_public_payload(user)

        self.assertEqual(payload["account_status"], "approved")
        self.assertTrue(payload["is_active"])
        self.assertNotIn("password_hash", payload)

    def test_safe_status_rejects_unknown_values(self):
        self.assertEqual(_safe_status("approved"), "approved")
        with self.assertRaises(Exception):
            _safe_status("root")

    def test_admin_create_user_validators(self):
        self.assertEqual(_validate_admin_email(" Nuevo@Example.COM "), "nuevo@example.com")
        self.assertIsNone(_validate_admin_password("clave123"))
        with self.assertRaises(Exception):
            _validate_admin_email("correo-local")
        with self.assertRaises(Exception):
            _validate_admin_password("sololetras")

    def test_approval_email_falls_back_to_outbox_when_smtp_is_missing(self):
        user = User(email="nuevo@example.com", name="Nuevo", password_hash="hash", role="estudiante")
        with tempfile.TemporaryDirectory() as tmpdir:
            outbox = Path(tmpdir) / "outbox.jsonl"
            with patch.dict("os.environ", {"ASOFAMECH_EMAIL_OUTBOX_PATH": str(outbox)}, clear=True):
                result = send_account_approved_email(user)

            self.assertFalse(result["sent"])
            self.assertEqual(result["reason"], "smtp_not_configured")
            self.assertTrue(outbox.exists())
            self.assertIn("nuevo@example.com", outbox.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
