import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { startSession, flushSession, getMetrics, formatStudyTime, getRecentActivity, timeAgo } from "../tracker";
import { AppSidebar } from "../components/AppSidebar";
import { clearAuthSession } from "../authClient";

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Buenos días";
  if (h < 19) return "Buenas tardes";
  return "Buenas noches";
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [metrics, setMetrics] = useState({ consultations: 0, studyMs: 0, testsTotal: 0, testsPassed: 0 });
  const [activity, setActivity] = useState([]);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    const token = localStorage.getItem("auth_token");
    if (!userData || !token) {
      clearAuthSession();
      navigate("/auth");
      return;
    } else {
      setUser(JSON.parse(userData));
      const savedRole = localStorage.getItem("role");
      if (savedRole) setRole(savedRole);
    }
    startSession();
    setMetrics(getMetrics());
    setActivity(getRecentActivity(10));

    const handleUnload = () => flushSession();
    window.addEventListener("beforeunload", handleUnload);
    return () => {
      flushSession();
      window.removeEventListener("beforeunload", handleUnload);
    };
  }, [navigate]);

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
    clearAuthSession();
    navigate("/");
  };

  const handleRoleChange = (val) => {
    setRole(val);
    localStorage.setItem("role", val);
  };

  if (!user) return null;

  const testsPassedPct = metrics.testsTotal > 0
    ? Math.round((metrics.testsPassed / metrics.testsTotal) * 100)
    : null;

  const activityDotClass = { chat: "type-chat", sct: "type-sct", images: "type-images" };
  const activityEmoji = { chat: "💬", sct: "📋", images: "🔬" };

  return (
    <>
      <AppSidebar
        user={user}
        role={role}
        activeRoute="dashboard"
        onRoleChange={handleRoleChange}
        onLogout={handleLogout}
      />

      <div className="page-scroll">
        {/* Hero */}
        <div className="home-hero">
          <div className="home-hero-pill">
            <span className="home-hero-pill-dot" />
            Plataforma activa
          </div>
          <h1 className="home-hero-greeting">
            {getGreeting()},{" "}
            <span className="home-hero-name">{user.name.split(" ")[0]}</span>
          </h1>
          <p className="home-hero-sub">Continúa tu entrenamiento clínico donde lo dejaste.</p>

          <div className="home-stats-strip">
            <div className="home-stat">
              <div className="home-stat-label">Consultas realizadas</div>
              <div className={`home-stat-value${metrics.consultations > 0 ? " clr-accent" : ""}`}>
                {metrics.consultations}
              </div>
            </div>
            <div className="home-stat">
              <div className="home-stat-label">Tiempo de estudio</div>
              <div className="home-stat-value clr-indigo">
                {formatStudyTime(metrics.studyMs)}
              </div>
            </div>
            <div className="home-stat">
              <div className="home-stat-label">Tests aprobados</div>
              <div className={`home-stat-value${testsPassedPct !== null && testsPassedPct >= 60 ? " clr-accent" : testsPassedPct !== null ? " clr-coral" : ""}`}>
                {testsPassedPct !== null ? `${testsPassedPct}%` : "—"}
              </div>
              {metrics.testsTotal > 0 && (
                <div className="home-stat-detail">{metrics.testsPassed}/{metrics.testsTotal} tests</div>
              )}
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="home-body">
          {/* Modules */}
          <div className="home-section-head">
            <h2 className="home-section-title">Módulos</h2>
            <span className="home-section-meta">3 herramientas</span>
          </div>

          <div className="home-modules-grid">
            <a href="/dashboard/chat" className="home-module-card chat-card" onClick={e => { e.preventDefault(); navigate("/dashboard/chat"); }}>
              <div className="home-module-tag">01 — Asistente</div>
              <div className="home-module-icon">🤖</div>
              <h3 className="home-module-title">Asistente Médico IA</h3>
              <p className="home-module-desc">Consulta educativa 24/7 sobre temas de salud, diagnósticos y tratamientos.</p>
              <div className="home-module-stat">
                {metrics.consultations > 0 ? `${metrics.consultations} consultas` : "Empieza a consultar →"}
              </div>
            </a>

            <a href="/dashboard/sct" className="home-module-card sct-card" onClick={e => { e.preventDefault(); navigate("/dashboard/sct"); }}>
              <div className="home-module-tag">02 — Test</div>
              <div className="home-module-icon">📋</div>
              <h3 className="home-module-title">Test SCT</h3>
              <p className="home-module-desc">Evalúa tu razonamiento clínico con casos médicos generados por IA.</p>
              <div className="home-module-stat">
                {metrics.testsTotal > 0 ? `${metrics.testsTotal} tests completados` : "Realiza tu primer test →"}
              </div>
            </a>

            <a href="/dashboard/images" className="home-module-card images-card" onClick={e => { e.preventDefault(); navigate("/dashboard/images"); }}>
              <div className="home-module-tag">03 — Análisis</div>
              <div className="home-module-icon">🔬</div>
              <h3 className="home-module-title">Imágenes IA</h3>
              <p className="home-module-desc">Visualiza y analiza imágenes histológicas de alta resolución.</p>
              <div className="home-module-stat">
                {activity.filter(a => a.type === "images").length > 0
                  ? `${activity.filter(a => a.type === "images").length} visualizaciones`
                  : "Explora las imágenes →"}
              </div>
            </a>
          </div>

          {/* Activity */}
          <div className="home-section-head">
            <h2 className="home-section-title">Actividad Reciente</h2>
            {activity.length > 0 && (
              <span className="home-section-meta">{activity.length} registros</span>
            )}
          </div>

          <div className="home-activity-list">
            {activity.length === 0 ? (
              <div className="home-activity-empty">
                <span className="home-activity-empty-icon">📭</span>
                <p>Aún no hay actividad registrada. Comienza usando el asistente o realizando un test SCT.</p>
              </div>
            ) : (
              activity.map((item, idx) => (
                <div key={idx} className="home-activity-item">
                  <div className={`home-activity-dot ${activityDotClass[item.type] || "type-other"}`}>
                    {activityEmoji[item.type] || "📌"}
                  </div>
                  <div className="home-activity-text">
                    <div className="home-activity-title">{item.title}</div>
                    <div className="home-activity-time">{timeAgo(item.timestamp)}</div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="home-disclaimer">
            <strong>Recordatorio:</strong> Esta plataforma es exclusivamente educativa. La información no reemplaza la consulta con un profesional de la salud.
          </div>
        </div>
      </div>
    </>
  );
}
