import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { API_BASE, saveAuthSession } from "../authClient";
import { requestPasswordReset } from "../api";

export function AuthPage() {
  const [searchParams] = useSearchParams();
  const isRegister = searchParams.get("register") === "true";
  const navigate = useNavigate();

  const [view, setView] = useState("auth"); // "auth" | "forgot"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [role] = useState("estudiante");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const fallbackName = () => {
    if (name.trim()) return name.trim();
    if (!email) return "Usuario";
    const emailName = email.split("@")[0] || "usuario";
    return emailName.charAt(0).toUpperCase() + emailName.slice(1);
  };

  const handleForgotSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);
    try {
      const result = await requestPasswordReset(email);
      setSuccess(result.message || "Si el correo está registrado, recibirás las instrucciones.");
    } catch (err) {
      setSuccess("Si el correo está registrado, recibirás las instrucciones.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    try {
      const endpoint = isRegister ? "/api/auth/register" : "/api/auth/login";
      const body = isRegister
        ? { name: fallbackName(), email, password, role }
        : { email, password };

      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(payload?.detail || `Error HTTP ${response.status}`);
      }

      if (isRegister && !payload?.access_token) {
        setSuccess(payload?.message || "Solicitud recibida. Un administrador debe aprobar tu cuenta antes de ingresar.");
        setPassword("");
        return;
      }

      saveAuthSession(payload);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message || "No se pudo iniciar sesión");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-form-side">
          <Link to="/" className="auth-back-link">
            Volver al inicio
          </Link>

          <div className="auth-logo">
            <div className="logo-mark">A</div>
            <span>ASOFAMECH</span>
          </div>

          <div className="auth-form-content">

            {/* ── Vista: recuperar contraseña ─────────────────────── */}
            {view === "forgot" && (
              <>
                <h1 className="auth-title">Recuperar contraseña</h1>
                <p className="auth-subtitle">
                  Ingresa tu correo y te enviaremos un enlace para crear una nueva contraseña.
                </p>
                <form onSubmit={handleForgotSubmit} className="auth-form">
                  <div className="form-group">
                    <label htmlFor="forgot-email" className="form-label">Correo electrónico</label>
                    <input
                      type="email"
                      id="forgot-email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="tu@correo.com"
                      className="form-input"
                      required
                    />
                  </div>
                  {error && <div className="auth-error" role="alert">{error}</div>}
                  {success && <div className="auth-info-note">{success}</div>}
                  <button type="submit" className="btn-auth-submit" disabled={loading}>
                    {loading ? "Enviando..." : "Enviar enlace de recuperación"}
                  </button>
                </form>
                <p className="auth-switch">
                  <button
                    type="button"
                    className="auth-switch-link"
                    style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
                    onClick={() => { setView("auth"); setError(""); setSuccess(""); }}
                  >
                    Volver al inicio de sesión
                  </button>
                </p>
              </>
            )}

            {/* ── Vista: login / registro ─────────────────────────── */}
            {view === "auth" && (
              <>
                <h1 className="auth-title">
                  {isRegister ? "Crear cuenta" : "Bienvenido de vuelta"}
                </h1>
                <p className="auth-subtitle">
                  Accede con una cuenta real para proteger las acciones docentes y administrativas.
                </p>

                <form onSubmit={handleSubmit} className="auth-form" data-testid="auth-form">
                  <div className="form-group">
                    <label htmlFor="name" className="form-label">
                      Nombre completo {!isRegister && <span style={{ opacity: 0.6, fontSize: "0.85em" }}>(opcional)</span>}
                    </label>
                    <input
                      type="text"
                      id="name"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      placeholder={isRegister ? "Nombre y apellido" : "Tu nombre"}
                      className="form-input"
                      required={isRegister}
                      data-testid="auth-name"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="email" className="form-label">Correo electrónico</label>
                    <input
                      type="email"
                      id="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="tu@correo.com"
                      className="form-input"
                      required
                      data-testid="auth-email"
                    />
                  </div>

                  {isRegister && (
                    <div className="auth-info-note">
                      Tu cuenta quedara pendiente hasta que un administrador la revise y autorice.
                    </div>
                  )}

                  <div className="form-group">
                    <div className="form-label-row">
                      <label htmlFor="password" className="form-label">Contraseña</label>
                      {!isRegister && (
                        <button
                          type="button"
                          className="auth-forgot-link"
                          onClick={() => { setView("forgot"); setError(""); setSuccess(""); }}
                        >
                          ¿Olvidaste tu contraseña?
                        </button>
                      )}
                    </div>
                    <div className="password-input-wrapper">
                      <input
                        type={showPassword ? "text" : "password"}
                        id="password"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        placeholder="Mínimo 8 caracteres, con letras y números"
                        className="form-input"
                        minLength={8}
                        required
                        data-testid="auth-password"
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowPassword((value) => !value)}
                        aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                      >
                        {showPassword ? "Ocultar" : "Ver"}
                      </button>
                    </div>
                  </div>

                  {error && <div className="auth-error" role="alert" data-testid="auth-error">{error}</div>}
                  {success && <div className="auth-info-note" data-testid="auth-success">{success}</div>}

                  <button type="submit" className="btn-auth-submit" disabled={loading} data-testid="auth-submit">
                    {loading ? "Validando..." : isRegister ? "Registrarse" : "Iniciar sesión"}
                  </button>
                </form>

                <p className="auth-switch">
                  {isRegister ? "¿Ya tienes cuenta? " : "¿No tienes cuenta? "}
                  <Link
                    to={isRegister ? "/auth" : "/auth?register=true"}
                    className="auth-switch-link"
                  >
                    {isRegister ? "Inicia sesión aquí" : "Regístrate aquí"}
                  </Link>
                </p>
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

            <ul className="auth-info-features">
              <li><span className="feature-check">OK</span> Asistente médico educativo</li>
              <li><span className="feature-check">OK</span> Tests SCT personalizados</li>
              <li><span className="feature-check">OK</span> Módulo histopatológico protegido por rol</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
