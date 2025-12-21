import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";

export function DashboardPage() {
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
          <Link to="/dashboard" className="nav-item active">
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
          <Link to="/dashboard/images" className="nav-item">
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
      <main className="dashboard-main">
        <div className="dashboard-header">
          <h1 className="dashboard-welcome">Bienvenido de vuelta</h1>
          <p className="dashboard-subtitle">
            Continúa tu aprendizaje médico con nuestras herramientas de IA
          </p>
        </div>

        {/* Stats Cards */}
        <div className="dashboard-stats">
          <div className="stat-card">
            <div className="stat-icon">📈</div>
            <div className="stat-content">
              <div className="stat-label">Consultas este mes</div>
              <div className="stat-value">128</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">⏱️</div>
            <div className="stat-content">
              <div className="stat-label">Tiempo de estudio</div>
              <div className="stat-value">12.5h</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">⭐</div>
            <div className="stat-content">
              <div className="stat-label">Tests aprobados</div>
              <div className="stat-value">89%</div>
            </div>
          </div>
        </div>

        {/* Modules Section */}
        <section className="dashboard-section">
          <h2 className="section-title">Módulos</h2>
          
          <div className="modules-grid">
            <Link to="/dashboard/chat" className="module-card">
              <div className="module-icon blue">💬</div>
              <h3 className="module-title">Chatbot Médico IA</h3>
              <p className="module-description">
                Consulta educativa 24/7 sobre temas de salud
              </p>
              <div className="module-stats">1.234 consultas</div>
            </Link>
            
            <Link to="/dashboard/sct" className="module-card">
              <div className="module-icon green">📋</div>
              <h3 className="module-title">Test SCT</h3>
              <p className="module-description">
                Evalúa tu razonamiento clínico
              </p>
              <div className="module-stats">45 tests completados</div>
            </Link>
            
            <div className="module-card disabled">
              <div className="module-icon cyan">🖼️</div>
              <h3 className="module-title">Análisis de Imágenes</h3>
              <p className="module-description">
                Próximamente disponible
              </p>
              <div className="module-stats">Próximamente</div>
            </div>
          </div>
        </section>

        {/* Recent Activity */}
        <section className="dashboard-section">
          <h2 className="section-title">Actividad Reciente</h2>
          
          <div className="activity-list">
            <div className="activity-item">
              <div className="activity-icon">💬</div>
              <div className="activity-content">
                <div className="activity-title">Consulta sobre diabetes mellitus tipo 2</div>
                <div className="activity-time">Hace 2 horas</div>
              </div>
            </div>
            
            <div className="activity-item">
              <div className="activity-icon">📋</div>
              <div className="activity-content">
                <div className="activity-title">Test SCT - Cardiología</div>
                <div className="activity-time">Ayer</div>
              </div>
            </div>
            
            <div className="activity-item">
              <div className="activity-icon">💬</div>
              <div className="activity-content">
                <div className="activity-title">Síntomas de hipertensión arterial</div>
                <div className="activity-time">Hace 2 días</div>
              </div>
            </div>
          </div>
        </section>

        {/* Disclaimer */}
        <div className="dashboard-disclaimer">
          <p>
            <strong>Recordatorio:</strong> Esta plataforma es exclusivamente educativa. La información no reemplaza la consulta con un profesional de la salud.
          </p>
        </div>
      </main>
    </div>
  );
}
