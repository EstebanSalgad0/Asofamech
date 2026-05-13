import unittest
from unittest.mock import patch

from app import auth_security


class AuthSecurityTestCase(unittest.TestCase):
    def test_password_hash_round_trip(self):
        stored = auth_security.hash_password("clave-segura")
        self.assertTrue(auth_security.verify_password("clave-segura", stored))
        self.assertFalse(auth_security.verify_password("otra-clave", stored))

    def test_password_hash_uses_random_salt(self):
        first = auth_security.hash_password("clave-segura")
        second = auth_security.hash_password("clave-segura")
        self.assertNotEqual(first, second)
        self.assertTrue(auth_security.verify_password("clave-segura", first))
        self.assertTrue(auth_security.verify_password("clave-segura", second))

    def test_jwt_round_trip(self):
        with patch.dict("os.environ", {"ASOFAMECH_JWT_SECRET": "test-secret"}):
            token = auth_security.create_access_token(
                {"sub": "7", "email": "docente@example.com", "role": "docente"}
            )
            payload = auth_security.decode_access_token(token)
        self.assertEqual(payload["sub"], "7")
        self.assertEqual(payload["email"], "docente@example.com")
        self.assertEqual(payload["role"], "docente")

    def test_jwt_rejects_tampering(self):
        with patch.dict("os.environ", {"ASOFAMECH_JWT_SECRET": "test-secret"}):
            token = auth_security.create_access_token({"sub": "1", "email": "a@b.cl"})
            tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
            with self.assertRaises(auth_security.TokenError):
                auth_security.decode_access_token(tampered)

    def test_jwt_rejects_expired_token(self):
        with patch.dict(
            "os.environ",
            {
                "ASOFAMECH_JWT_SECRET": "test-secret",
                "ASOFAMECH_ACCESS_TOKEN_EXPIRE_MINUTES": "5",
            },
        ):
            with patch("app.auth_security.time.time", return_value=1000):
                token = auth_security.create_access_token({"sub": "1"})
            with patch("app.auth_security.time.time", return_value=1000 + 301):
                with self.assertRaises(auth_security.TokenError):
                    auth_security.decode_access_token(token)

    def test_role_display_mapping(self):
        self.assertEqual(auth_security.display_role("administrador"), "Administrador")
        self.assertEqual(auth_security.display_role("docente"), "Profesor")
        self.assertEqual(auth_security.display_role("profesor"), "Profesor")
        self.assertEqual(auth_security.display_role("student"), "Estudiante")


if __name__ == "__main__":
    unittest.main()
