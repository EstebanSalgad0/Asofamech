import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { startSession, flushSession, getMetrics, formatStudyTime, getRecentActivity, timeAgo } from "../tracker";

export function DashboardPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [metrics, setMetrics] = useState({ consultations: 0, studyMs: 0, testsTotal: 0, testsPassed: 0 });
  const [activity, setActivity] = useState([]);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    if (!userData) {
      navigate("/auth");
    } else {
      setUser(JSON.parse(userData));
      const savedRole = localStorage.getItem("role");
      if (savedRole) setRole(savedRole);
    }

    // Start session timer for study time
    startSession();

    // Load real metrics & activity
    setMetrics(getMetrics());
    setActivity(getRecentActivity(10));

    // Flush session time when leaving
    const handleUnload = () => flushSession();
    window.addEventListener("beforeunload", handleUnload);
    return () => {
      flushSession();
      window.removeEventListener("beforeunload", handleUnload);
    };
  }, [navigate]);

  // Refresh metrics when page becomes visible again (tab switch back)
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        setMetrics(getMetrics());
        setActivity(getRecentActivity(10));
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  const handleLogout = () => {
    flushSession();
    localStorage.removeItem("user");
    navigate("/");
  };

  if (!user) return null;

  const testsPassedPct = metrics.testsTotal > 0
    ? Math.round((metrics.testsPassed / metrics.testsTotal) * 100)
    : 0;

  const activityIcon = { chat: "💬", sct: "📋", images: "🖼️" };

  return (
    <div className="dashboard-page">
      {/* Sidebar */}
      <aside className="dashboard-sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark">A</div>
          <span>ASOFAMECH</span>
        </div>
        
        <nav className="sidebar-nav">
          <Link to="/dashboard" className="nav-item active">
            <span className="nav-icon">🏠</span>
            <span>Inicio</span>
          </Link>
          <Link to="/dashboard/chat" className="nav-item">
            <span className="nav-icon">💬</span>
            <span>Asistente IA</span>
          </Link>
          <Link to="/dashboard/sct" className="nav-item">
            <span className="nav-icon">📋</span>
            <span>Test SCT</span>
          </Link>
          <Link to="/dashboard/images" className="nav-item">
            <span className="nav-icon">🖼️</span>
            <span>Imágenes IA</span>
          </Link>
          {(role === "Administrador" || role === "Profesor") && (
            <Link to="/dashboard/config" className="nav-item">
              <span className="nav-icon">⚙️</span>
              <span>Configuración</span>
            </Link>
          )}
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
            onChange={(e) => {
              setRole(e.target.value);
              localStorage.setItem("role", e.target.value);
            }}
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
              <div className="stat-label">Consultas realizadas</div>
              <div className="stat-value">{metrics.consultations}</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">⏱️</div>
            <div className="stat-content">
              <div className="stat-label">Tiempo de estudio</div>
              <div className="stat-value">{formatStudyTime(metrics.studyMs)}</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">⭐</div>
            <div className="stat-content">
              <div className="stat-label">Tests aprobados</div>
              <div className="stat-value">
                {metrics.testsTotal > 0
                  ? `${testsPassedPct}%`
                  : "—"}
              </div>
              {metrics.testsTotal > 0 && (
                <div className="stat-detail">
                  {metrics.testsPassed}/{metrics.testsTotal} tests
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Modules Section */}
        <section className="dashboard-section">
          <h2 className="section-title">Módulos</h2>
          
          <div className="modules-grid">
            <Link to="/dashboard/chat" className="module-card">
              <div className="module-icon blue">💬</div>
              <h3 className="module-title">Asistente Médico IA</h3>
              <p className="module-description">
                Consulta educativa 24/7 sobre temas de salud
              </p>
              <div className="module-stats">
                {metrics.consultations > 0
                  ? `${metrics.consultations} consultas`
                  : "Empieza a consultar"}
              </div>
            </Link>
            
            <Link to="/dashboard/sct" className="module-card">
              <div className="module-icon green">📋</div>
              <h3 className="module-title">Test SCT</h3>
              <p className="module-description">
                Evalúa tu razonamiento clínico
              </p>
              <div className="module-stats">
                {metrics.testsTotal > 0
                  ? `${metrics.testsTotal} tests completados`
                  : "Realiza tu primer test"}
              </div>
            </Link>
            
            <Link to="/dashboard/images" className="module-card">
              <div className="module-icon cyan">🖼️</div>
              <h3 className="module-title">Análisis de Imágenes</h3>
              <p className="module-description">
                Visualiza imágenes histológicas de alta resolución
              </p>
              <div className="module-stats">
                {activity.filter(a => a.type === "images").length > 0
                  ? `${activity.filter(a => a.type === "images").length} visualizaciones`
                  : "Explora las imágenes"}
              </div>
            </Link>
          </div>
        </section>

        {/* Recent Activity */}
        <section className="dashboard-section">
          <h2 className="section-title">Actividad Reciente</h2>
          
          <div className="activity-list">
            {activity.length === 0 ? (
              <div className="activity-empty">
                <span className="activity-empty-icon">📭</span>
                <p>Aún no hay actividad registrada. Comienza usando el asistente o realizando un test SCT.</p>
              </div>
            ) : (
              activity.map((item, idx) => (
                <div key={idx} className="activity-item">
                  <div className="activity-icon">{activityIcon[item.type] || "📌"}</div>
                  <div className="activity-content">
                    <div className="activity-title">{item.title}</div>
                    <div className="activity-time">{timeAgo(item.timestamp)}</div>
                  </div>
                </div>
              ))
            )}
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
