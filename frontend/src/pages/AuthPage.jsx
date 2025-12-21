import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

export function AuthPage() {
  const [searchParams] = useSearchParams();
  const isRegister = searchParams.get("register") === "true";
  const navigate = useNavigate();
  
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    // Aquí iría la lógica de autenticación
    // Por ahora simulamos login exitoso
    localStorage.setItem("user", JSON.stringify({ 
      name: name || "Dr. María García",
      email: email,
      role: "Estudiante"
    }));
    navigate("/dashboard");
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        {/* Left Side - Form */}
        <div className="auth-form-side">
          <Link to="/" className="auth-back-link">
            ← Volver al inicio
          </Link>
          
          <div className="auth-logo">
            <div className="logo-icon">A</div>
            <span>ASOFAMECH</span>
          </div>
          
          <div className="auth-form-content">
            <h1 className="auth-title">
              {isRegister ? "Bienvenido" : "Bienvenido de vuelta"}
            </h1>
            <p className="auth-subtitle">
              {isRegister 
                ? "Ingresa tus credenciales para acceder a la plataforma"
                : "Ingresa tus credenciales para acceder a la plataforma"
              }
            </p>
            
            <form onSubmit={handleSubmit} className="auth-form">
              {isRegister && (
                <div className="form-group">
                  <label htmlFor="name" className="form-label">Nombre completo</label>
                  <input
                    type="text"
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Dr. Juan Pérez"
                    className="form-input"
                    required={isRegister}
                  />
                </div>
              )}
              
              <div className="form-group">
                <label htmlFor="email" className="form-label">Correo electrónico</label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@correo.com"
                  className="form-input"
                  required
                />
              </div>
              
              <div className="form-group">
                <div className="form-label-row">
                  <label htmlFor="password" className="form-label">Contraseña</label>
                  {!isRegister && (
                    <a href="#" className="form-link">¿Olvidaste tu contraseña?</a>
                  )}
                </div>
                <div className="password-input-wrapper">
                  <input
                    type="password"
                    id="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="form-input"
                    required
                  />
                  <button type="button" className="password-toggle">
                    👁️
                  </button>
                </div>
              </div>
              
              <button type="submit" className="btn-auth-submit">
                {isRegister ? "Registrarse" : "Iniciar Sesión"}
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
          </div>
        </div>
        
        {/* Right Side - Info */}
        <div className="auth-info-side">
          <div className="auth-info-content">
            <h2 className="auth-info-title">
              Educación médica<br />del futuro
            </h2>
            <p className="auth-info-subtitle">
              Accede a herramientas impulsadas por IA para potenciar tu aprendizaje y razonamiento clínico.
            </p>
            
            <ul className="auth-info-features">
              <li>
                <span className="feature-check">✓</span>
                Chatbot médico educativo 24/7
              </li>
              <li>
                <span className="feature-check">✓</span>
                Generador de casos SCT personalizados
              </li>
              <li>
                <span className="feature-check">✓</span>
                Contenido verificado por especialistas
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
