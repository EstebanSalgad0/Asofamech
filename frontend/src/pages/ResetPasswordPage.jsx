import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { confirmPasswordReset } from "../api";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setLoading(true);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
    } catch (err) {
      setError(err.message || "No se pudo restablecer la contraseña.");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="auth-page">
        <div className="auth-container">
          <div className="auth-form-side">
            <div className="auth-logo">
              <div className="logo-mark">A</div>
              <span>ASOFAMECH</span>
            </div>
            <div className="auth-form-content">
              <h1 className="auth-title">Enlace inválido</h1>
              <p className="auth-subtitle">
                Este enlace de recuperación no es válido. Solicita uno nuevo desde el inicio de sesión.
              </p>
              <Link to="/auth" className="btn-auth-submit" style={{ display: "block", textAlign: "center", textDecoration: "none" }}>
                Ir al inicio de sesión
              </Link>
            </div>
          </div>
          <div className="auth-info-side">
            <div className="auth-info-content">
              <h2 className="auth-info-title">Educación médica<br />del futuro</h2>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-form-side">
          <Link to="/auth" className="auth-back-link">Volver al inicio de sesión</Link>

          <div className="auth-logo">
            <div className="logo-mark">A</div>
            <span>ASOFAMECH</span>
          </div>

          <div className="auth-form-content">
            <h1 className="auth-title">Nueva contraseña</h1>

            {done ? (
              <>
                <div className="auth-info-note" style={{ marginBottom: "24px" }}>
                  Tu contraseña fue actualizada correctamente. Ya puedes iniciar sesión con tu nueva contraseña.
                </div>
                <button
                  type="button"
                  className="btn-auth-submit"
                  onClick={() => navigate("/auth")}
                >
                  Ir al inicio de sesión
                </button>
              </>
            ) : (
              <>
                <p className="auth-subtitle">
                  Elige una contraseña segura de al menos 8 caracteres con letras y números.
                </p>
                <form onSubmit={handleSubmit} className="auth-form">
                  <div className="form-group">
                    <div className="form-label-row">
                      <label htmlFor="new-password" className="form-label">Nueva contraseña</label>
                    </div>
                    <div className="password-input-wrapper">
                      <input
                        type={showPassword ? "text" : "password"}
                        id="new-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Mínimo 8 caracteres, con letras y números"
                        className="form-input"
                        minLength={8}
                        required
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowPassword((v) => !v)}
                        aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                      >
                        {showPassword ? "Ocultar" : "Ver"}
                      </button>
                    </div>
                  </div>

                  <div className="form-group">
                    <label htmlFor="confirm-password" className="form-label">Confirmar contraseña</label>
                    <input
                      type={showPassword ? "text" : "password"}
                      id="confirm-password"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      placeholder="Repite la contraseña"
                      className="form-input"
                      minLength={8}
                      required
                    />
                  </div>

                  {error && <div className="auth-error" role="alert">{error}</div>}

                  <button type="submit" className="btn-auth-submit" disabled={loading}>
                    {loading ? "Guardando..." : "Establecer nueva contraseña"}
                  </button>
                </form>
              </>
            )}
          </div>
        </div>

        <div className="auth-info-side">
          <div className="auth-info-content">
            <h2 className="auth-info-title">
              Educación médica<br />del futuro
            </h2>
            <p className="auth-info-subtitle">
              Usa herramientas educativas con IA para reforzar aprendizaje, casos y revisión histopatológica.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
