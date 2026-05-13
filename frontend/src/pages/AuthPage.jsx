import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { API_BASE, saveAuthSession } from "../authClient";

export function AuthPage() {
  const [searchParams] = useSearchParams();
  const isRegister = searchParams.get("register") === "true";
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("estudiante");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fallbackName = () => {
    if (name.trim()) return name.trim();
    if (!email) return "Usuario";
    const emailName = email.split("@")[0] || "usuario";
    return emailName.charAt(0).toUpperCase() + emailName.slice(1);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
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

      saveAuthSession(payload);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message || "No se pudo iniciar sesion");
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
            <h1 className="auth-title">
              {isRegister ? "Crear cuenta" : "Bienvenido de vuelta"}
            </h1>
            <p className="auth-subtitle">
              Accede con una cuenta real para proteger las acciones docentes y administrativas.
            </p>

            <form onSubmit={handleSubmit} className="auth-form">
              <div className="form-group">
                <label htmlFor="name" className="form-label">
                  Nombre completo {!isRegister && <span style={{ opacity: 0.6, fontSize: "0.85em" }}>(opcional)</span>}
                </label>
                <input
                  type="text"
                  id="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder={isRegister ? "Dr. Juan Perez" : "Tu nombre"}
                  className="form-input"
                  required={isRegister}
                />
              </div>

              <div className="form-group">
                <label htmlFor="email" className="form-label">Correo electronico</label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="tu@correo.com"
                  className="form-input"
                  required
                />
              </div>

              {isRegister && (
                <div className="form-group">
                  <label htmlFor="role" className="form-label">Rol educativo</label>
                  <select
                    id="role"
                    value={role}
                    onChange={(event) => setRole(event.target.value)}
                    className="form-input"
                  >
                    <option value="estudiante">Estudiante</option>
                    <option value="docente">Profesor</option>
                    <option value="administrador">Administrador</option>
                  </select>
                </div>
              )}

              <div className="form-group">
                <div className="form-label-row">
                  <label htmlFor="password" className="form-label">Contrasena</label>
                </div>
                <div className="password-input-wrapper">
                  <input
                    type={showPassword ? "text" : "password"}
                    id="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Minimo 6 caracteres"
                    className="form-input"
                    minLength={6}
                    required
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowPassword((value) => !value)}
                    aria-label={showPassword ? "Ocultar contrasena" : "Mostrar contrasena"}
                  >
                    {showPassword ? "Ocultar" : "Ver"}
                  </button>
                </div>
              </div>

              {error && <div className="auth-error">{error}</div>}

              <button type="submit" className="btn-auth-submit" disabled={loading}>
                {loading ? "Validando..." : isRegister ? "Registrarse" : "Iniciar sesion"}
              </button>
            </form>

            <p className="auth-switch">
              {isRegister ? "Ya tienes cuenta? " : "No tienes cuenta? "}
              <Link
                to={isRegister ? "/auth" : "/auth?register=true"}
                className="auth-switch-link"
              >
                {isRegister ? "Inicia sesion aqui" : "Registrate aqui"}
              </Link>
            </p>
          </div>
        </div>

        <div className="auth-info-side">
          <div className="auth-info-content">
            <h2 className="auth-info-title">
              Educacion medica<br />del futuro
            </h2>
            <p className="auth-info-subtitle">
              Usa herramientas educativas con IA para reforzar aprendizaje, casos y revision histopatologica.
            </p>

            <ul className="auth-info-features">
              <li><span className="feature-check">OK</span> Asistente medico educativo</li>
              <li><span className="feature-check">OK</span> Tests SCT personalizados</li>
              <li><span className="feature-check">OK</span> Modulo histopatologico protegido por rol</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
