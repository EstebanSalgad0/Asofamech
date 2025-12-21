import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";

export function ImagesPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");

  useEffect(() => {
    const userData = localStorage.getItem("user");
    if (!userData) {
      navigate("/auth");
    } else {
      setUser(JSON.parse(userData));
    }
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem("user");
    navigate("/");
  };

  if (!user) return null;

  return (
    <div className="dashboard-page">
      {/* Sidebar */}
      <aside className="dashboard-sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">A</div>
          <span>ASOFAMECH</span>
        </div>
        
        <nav className="sidebar-nav">
          <Link to="/dashboard" className="nav-item">
            <span className="nav-icon">🏠</span>
            <span>Inicio</span>
          </Link>
          <Link to="/dashboard/chat" className="nav-item">
            <span className="nav-icon">💬</span>
            <span>Chatbot IA</span>
          </Link>
          <Link to="/dashboard/sct" className="nav-item">
            <span className="nav-icon">📋</span>
            <span>Test SCT</span>
          </Link>
          <Link to="/dashboard/images" className="nav-item active">
            <span className="nav-icon">🖼️</span>
            <span>Imágenes IA</span>
            <span className="nav-badge">Próximamente</span>
          </Link>
        </nav>
        
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="user-avatar">
              {user.name.charAt(0)}
            </div>
            <div className="user-info">
              <div className="user-name">{user.name}</div>
              <div className="user-role">{role}</div>
            </div>
          </div>
          <select 
            className="sidebar-role-selector"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="Estudiante">Estudiante</option>
            <option value="Administrador">Administrador</option>
            <option value="Profesor">Profesor</option>
          </select>
          <button onClick={handleLogout} className="btn-logout">
            <span>↗</span> Cerrar Sesión
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="dashboard-main images-page">
        <div className="images-header">
          <div className="images-icon-large">🖼️</div>
          <h1 className="images-title">
            Análisis de <span className="gradient-text">Imágenes Médicas</span>
          </h1>
          <div className="badge-coming-soon">✨ Próximamente</div>
        </div>

        <div className="images-description">
          <p>
            Estamos desarrollando una herramienta educativa de análisis de imágenes médicas 
            impulsada por inteligencia artificial. Podrás aprender a interpretar radiografías, 
            tomografías y más con asistencia de IA.
          </p>
        </div>

        {/* Features Preview */}
        <div className="images-features">
          <div className="images-feature-card">
            <div className="feature-icon-large">📷</div>
            <h3 className="feature-title-large">Radiografías</h3>
            <p className="feature-description-large">Interpretación guiada</p>
          </div>

          <div className="images-feature-card">
            <div className="feature-icon-large">🔬</div>
            <h3 className="feature-title-large">Tomografías</h3>
            <p className="feature-description-large">Análisis educativo</p>
          </div>

          <div className="images-feature-card">
            <div className="feature-icon-large">💓</div>
            <h3 className="feature-title-large">ECG</h3>
            <p className="feature-description-large">Reconocimiento de patrones</p>
          </div>
        </div>

        <div className="images-info-box">
          <p>
            Esta herramienta será exclusivamente para fines educativos y no proporcionará 
            diagnósticos clínicos reales. No reemplaza la evaluación de un profesional médico.
          </p>
        </div>

        <div className="images-cta">
          <p className="images-cta-text">
            ¿Quieres ser notificado cuando esté disponible?
          </p>
          <button className="btn-notify">
            🔔 Notificarme
          </button>
        </div>
      </main>
    </div>
  );
}
