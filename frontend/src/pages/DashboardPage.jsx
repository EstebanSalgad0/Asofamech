import React, { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  startSession,
  flushSession,
  getMetrics,
  getRecentActivity,
  timeAgo,
} from "../tracker";
import { AppSidebar } from "../components/AppSidebar";
import { clearAuthSession, getStoredRole } from "../authClient";
import { getDashboardStats, getDashboardRanking, getMyHistory } from "../api";

const NEW_CHAT_FLAG = "asofamech_new_chat_requested";

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Buenos dias";
  if (h < 19) return "Buenas tardes";
  return "Buenas noches";
}

function getSessionLabel() {
  const date = new Date();
  return new Intl.DateTimeFormat("es-CL", { day: "2-digit", month: "long" }).format(date);
}

function activityRoute(type) {
  if (type === "chat") return "/dashboard/chat";
  if (type === "sct") return "/dashboard/sct";
  if (type === "images") return "/dashboard/images";
  return "/dashboard";
}

function activityIcon(type) {
  if (type === "chat") return "chat";
  if (type === "sct") return "sct";
  if (type === "images") return "histo";
  return "dot";
}

function activitySubtitle(item) {
  if (!item?.title) return "Actividad registrada";
  const parts = item.title.split(" - ");
  if (parts.length > 1) return parts.slice(1).join(" - ");
  if (item.type === "chat") return "conversación guardada";
  if (item.type === "sct") return "caso de razonamiento clínico";
  if (item.type === "images") return "visualización histopatológica";
  return "registro local";
}

function activityTitle(item) {
  if (!item?.title) return "Actividad";
  return item.title.split(" - ")[0];
}

function formatHistoryDate(value) {
  if (!value) return "fecha no registrada";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "fecha no registrada";
  return new Intl.DateTimeFormat("es-CL", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatSctScore(item) {
  if (!item || item.total_items === 0) return "sin puntaje";
  return `${item.correct_count}/${item.total_items} correctas`;
}

function makeHistoryGroups(historyData) {
  const analyses = historyData?.analyses || [];
  const sctAttempts = historyData?.sct_attempts || [];
  const conversations = historyData?.conversations || [];
  const heatmaps = historyData?.heatmaps || [];
  return [
    {
      id: "analyses",
      title: "Análisis ROI",
      route: "/dashboard/images",
      accent: "histo",
      empty: "Sin análisis registrados",
      items: analyses.slice(0, 3).map((item) => ({
        id: `analysis-${item.id}`,
        title: item.image_title || "Lámina histopatológica",
        meta: `${item.clase || item.status || "registrado"} - ${formatHistoryDate(item.analyzed_at)}`,
      })),
    },
    {
      id: "sct",
      title: "Intentos SCT",
      route: "/dashboard/sct",
      accent: "sct",
      empty: "Sin intentos SCT",
      items: sctAttempts.slice(0, 3).map((item) => ({
        id: `sct-${item.id}`,
        title: item.test_name || item.test_focus || "Test SCT",
        meta: `${formatSctScore(item)} - ${formatHistoryDate(item.completed_at)}`,
      })),
    },
    {
      id: "chat",
      title: "Conversaciones",
      route: "/dashboard/chat",
      accent: "chat",
      empty: "Sin conversaciones guardadas",
      items: conversations.slice(0, 3).map((item) => ({
        id: `chat-${item.id}`,
        title: item.question || "Consulta educativa",
        meta: `${item.used_rag ? "con fuentes RAG" : "respuesta general"} - ${formatHistoryDate(item.created_at)}`,
      })),
    },
    {
      id: "heatmaps",
      title: "Heatmaps",
      route: "/dashboard/images",
      accent: "histo",
      empty: "Sin heatmaps registrados",
      items: heatmaps.slice(0, 3).map((item) => ({
        id: `heatmap-${item.trace_id || item.job_id}`,
        title: item.roi_label || item.educational_label || item.status || "Heatmap",
        meta: `${item.tile_count || item.total_tiles || 0} tiles - ${formatHistoryDate(item.analyzed_at || item.created_at)}`,
      })),
    },
  ];
}

function ActivityGlyph({ type }) {
  if (type === "chat") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M21 14a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v7Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (type === "sct") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M8 4h8M9 2h6a1 1 0 0 1 1 1v2H8V3a1 1 0 0 1 1-1Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M7 5H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M8 12h8M8 16h5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M9 3h6v4l2 2v9a3 3 0 0 1-3 3h-4a3 3 0 0 1-3-3V9l2-2V3Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8 13h8M10 17h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function Sparkline({ data, color }) {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data, 1);
  const W = 80, H = 36, P = 3;
  const pts = data.map((v, i) => [
    P + (i / (data.length - 1)) * (W - P * 2),
    H - P - (v / max) * (H - P * 2),
  ]);
  const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${pts[0][0].toFixed(1)},${H} ` + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ") + ` ${pts[pts.length - 1][0].toFixed(1)},${H}`;
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} fill="none" aria-hidden="true">
      <polygon points={area} fill={color} opacity="0.13" />
      <polyline points={line} stroke={color} strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lx.toFixed(1)} cy={ly.toFixed(1)} r="2.8" fill={color} />
    </svg>
  );
}

function formatStudyTime(ms) {
  if (!ms || ms === 0) return "0 min";
  const totalMin = Math.round(ms / 60000);
  if (totalMin < 60) return `${totalMin} min`;
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [metrics, setMetrics] = useState({ consultations: 0, studyMs: 0, testsTotal: 0, testsPassed: 0 });
  const [activity, setActivity] = useState([]);
  const [activityFilter, setActivityFilter] = useState("all");
  const [dashStats, setDashStats] = useState(null);
  const [rankingData, setRankingData] = useState(null);
  const [historyData, setHistoryData] = useState(null);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    const token = localStorage.getItem("auth_token");
    if (!userData || !token) {
      clearAuthSession();
      navigate("/auth");
      return;
    }
    setUser(JSON.parse(userData));
    setRole(getStoredRole());

    startSession();
    setMetrics(getMetrics());
    setActivity(getRecentActivity(10));

    getDashboardStats().then(setDashStats).catch(() => {});
    getDashboardRanking().then(setRankingData).catch(() => {});
    getMyHistory(10).then(setHistoryData).catch(() => {});

    const handleUnload = () => flushSession();
    window.addEventListener("beforeunload", handleUnload);
    return () => {
      flushSession();
      window.removeEventListener("beforeunload", handleUnload);
    };
  }, [navigate]);

  useEffect(() => {
    const refresh = () => {
      setMetrics(getMetrics());
      setActivity(getRecentActivity(10));
    };
    const handleVisibility = () => { if (document.visibilityState === "visible") refresh(); };
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("focus", refresh);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("focus", refresh);
    };
  }, []);

  const handleLogout = () => { flushSession(); clearAuthSession(); navigate("/"); };
  const handleRoleChange = () => setRole(getStoredRole());
  const openNewChat = () => { sessionStorage.setItem(NEW_CHAT_FLAG, "1"); navigate("/dashboard/chat"); };

  const filteredActivity = useMemo(() => {
    if (activityFilter === "all") return activity.slice(0, 5);
    return activity.filter((item) => item.type === activityFilter).slice(0, 5);
  }, [activity, activityFilter]);

  if (!user) return null;

  const firstName = (user.name || "Estudiante").split(" ")[0];

  // Real data from backend (fallback to local tracker)
  const chatCount   = dashStats?.chat?.total  ?? metrics.consultations;
  const chatWeek    = dashStats?.chat?.week   ?? 0;
  const chatDaily   = dashStats?.chat?.daily  ?? [];
  const histoCount  = dashStats?.histo?.total ?? activity.filter(i => i.type === "images").length;
  const histoWeek   = dashStats?.histo?.week  ?? 0;
  const histoDaily  = dashStats?.histo?.daily ?? [];
  const localSctCount = metrics.testsTotal || activity.filter(i => i.type === "sct").length;
  const sctCount    = dashStats?.sct?.total ?? localSctCount;
  const sctWeek     = dashStats?.sct?.week  ?? 0;
  const sctDaily    = dashStats?.sct?.daily ?? [];
  const latestSctScore = dashStats?.sct?.latest?.total_items
    ? Math.round((dashStats.sct.latest.correct_count / dashStats.sct.latest.total_items) * 100)
    : null;
  const studyMsTotal = dashStats?.study?.total_ms ?? metrics.studyMs;
  const studyMsWeek  = dashStats?.study?.week_ms  ?? 0;
  const studyLabel   = formatStudyTime(studyMsTotal);
  const testsPassedPct = latestSctScore ?? (metrics.testsTotal > 0 ? Math.round((metrics.testsPassed / metrics.testsTotal) * 100) : null);

  const latestChat  = activity.find(i => i.type === "chat");
  const latestSct   = activity.find(i => i.type === "sct");
  const latestHisto = activity.find(i => i.type === "images");
  const pendingSct  = sctCount === 0 ? 1 : 0;
  const newConversations = Math.min(2, Math.max(0, activity.filter(i => i.type === "chat").length));
  const notificationCount = Math.min(9, Math.max(1, pendingSct + newConversations));

  const statCards = [
    {
      id: "chat",
      label: "CONSULTAS IA",
      value: chatCount,
      sub: chatWeek > 0 ? `+${chatWeek} esta semana` : "sin consultas esta semana",
      color: "#C41E3A",
      daily: chatDaily,
    },
    {
      id: "study",
      label: "TIEMPO DE ESTUDIO",
      value: studyLabel,
      sub: studyMsWeek >= 60_000 ? `+${formatStudyTime(studyMsWeek)} esta semana` : "sesión activa",
      color: "#D4A017",
      daily: null,
    },
    {
      id: "sct",
      label: "TESTS SCT",
      value: sctCount,
      sub: testsPassedPct !== null ? `último: ${testsPassedPct}%` : (sctWeek > 0 ? `+${sctWeek} esta semana` : "sin tests completados"),
      color: "#8B1520",
      daily: sctDaily,
    },
    {
      id: "histo",
      label: "LÁMINAS VISTAS",
      value: histoCount,
      sub: histoWeek > 0 ? `${histoWeek} nuevas` : "sin láminas esta semana",
      color: "#C41E3A",
      daily: histoDaily,
    },
  ];

  const moduleCards = [
    {
      id: "chat", eyebrow: "01 - Módulo", title: "Asistente Médico IA",
      description: "Consulta educativa 24/7 sobre temas médicos, diagnósticos y tratamientos.",
      stat: `${chatCount} consultas`,
      detail: latestChat ? `Última: ${activityTitle(latestChat)}` : "Inicia una conversación clínica",
      route: "/dashboard/chat", className: "home-v3-card-dark", glyph: "chat",
    },
    {
      id: "sct", eyebrow: "02 - Módulo", title: "Test SCT",
      description: "Evalúa tu razonamiento clínico con casos médicos generados por IA.",
      stat: `${sctCount} tests completados`,
      detail: latestSct ? `Último: ${activityTitle(latestSct)}` : "Practica con casos cortos",
      route: "/dashboard/sct", className: "home-v3-card-coral", glyph: "sct",
    },
    {
      id: "images", eyebrow: "03 - Módulo", title: "Análisis Histopatológico",
      description: "Visualiza y analiza imágenes histológicas de alta resolución.",
      stat: `${histoCount} visualizaciones`,
      detail: latestHisto ? `Última: ${activityTitle(latestHisto)}` : "Explora láminas educativas",
      route: "/dashboard/images", className: "home-v3-card-mint", glyph: "histo",
    },
  ];

  const ranking = rankingData?.ranking ?? [];
  const yourPosition = rankingData?.your_position;
  const percentile   = rankingData?.percentile;
  const historyGroups = makeHistoryGroups(historyData);

  return (
    <>
      <AppSidebar user={user} role={role} activeRoute="dashboard" onRoleChange={handleRoleChange} onLogout={handleLogout} />

      <main className="home-v3-shell" data-testid="dashboard-page">
        <header className="home-v3-hero">
          <div>
            <div className="home-v3-pill">
              <span />
              Plataforma activa · Sesión {getSessionLabel()}
            </div>
            <h1>{getGreeting()}, <em>{firstName}.</em></h1>
            <p>
              Continúa tu entrenamiento clínico donde lo dejaste.
              {pendingSct > 0 ? ` Tienes ${pendingSct} caso SCT pendiente` : ""}
              {newConversations > 0 ? `${pendingSct > 0 ? " y" : " Tienes"} ${newConversations} conversaciones nuevas.` : "."}
            </p>
          </div>
          <div className="home-v3-actions">
            <button className="home-v3-primary-btn" type="button" onClick={openNewChat}>
              <span>+</span> Nueva sesión
            </button>
          </div>
        </header>

        {/* ── Stats row ─────────────────────────────────── */}
        <section className="home-v3-stats-row">
          {statCards.map((card) => (
            <div key={card.id} className="home-v3-stat-card">
              <div className="home-v3-stat-left">
                <span className="home-v3-stat-label">{card.label}</span>
                <span className="home-v3-stat-value">{card.value}</span>
                <span className="home-v3-stat-sub" style={{ color: card.color }}>{card.sub}</span>
              </div>
              <div className="home-v3-stat-right">
                {card.daily && card.daily.some(v => v > 0)
                  ? <Sparkline data={card.daily} color={card.color} />
                  : <div className="home-v3-stat-nodata" style={{ borderColor: card.color }} />
                }
              </div>
            </div>
          ))}
        </section>

        {/* ── Modules ───────────────────────────────────── */}
        <section className="home-v3-section home-v3-modules-section">
          <div className="home-v3-section-head">
            <div>
              <div className="home-v3-kicker">/ 01 - Modulos</div>
              <h2>Tus tres herramientas</h2>
            </div>
            <span>Clic para abrir cualquiera.</span>
          </div>
          <div className="home-v3-modules-grid">
            {moduleCards.map((card) => (
              <button key={card.id} type="button" className={`home-v3-module-card ${card.className}`} onClick={() => navigate(card.route)} data-testid={`dashboard-module-${card.id}`}>
                <span className="home-v3-module-eyebrow">{card.eyebrow}</span>
                <span className="home-v3-module-glyph"><ActivityGlyph type={card.glyph} /></span>
                <span className="home-v3-module-title">{card.title}</span>
                <span className="home-v3-module-desc">{card.description}</span>
                <span className="home-v3-module-foot">
                  <strong>{card.stat}</strong>
                  <small>{card.detail}</small>
                  <b>Abrir</b>
                </span>
              </button>
            ))}
          </div>
        </section>

        {/* ── Lower grid ────────────────────────────────── */}
        <section className="home-v3-section home-v3-history-section" data-testid="dashboard-history">
          <div className="home-v3-section-head">
            <div>
              <div className="home-v3-kicker">/ 02 - Historial</div>
              <h2>Tu trazabilidad reciente</h2>
            </div>
            <span>Registros asociados a tu cuenta.</span>
          </div>
          <div className="home-v3-history-grid">
            {historyGroups.map((group) => (
              <div key={group.id} className="home-v3-history-card">
                <div className="home-v3-history-card-head">
                  <span className={`home-v3-activity-icon type-${group.accent}`}>
                    <ActivityGlyph type={group.accent} />
                  </span>
                  <strong>{group.title}</strong>
                </div>
                <div className="home-v3-history-list">
                  {group.items.length === 0 ? (
                    <div className="home-v3-history-empty">{group.empty}</div>
                  ) : (
                    group.items.map((item) => (
                      <button key={item.id} type="button" onClick={() => navigate(group.route)}>
                        <span>{item.title}</span>
                        <small>{item.meta}</small>
                      </button>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="home-v3-lower-grid">
          <div className="home-v3-activity-card">
            <div className="home-v3-card-head">
              <div>
                <h3>Actividad reciente</h3>
                <p>{activity.length} eventos registrados en tu historial local</p>
              </div>
              <div className="home-v3-filter-tabs">
                {[["all", "Todo"], ["chat", "IA"], ["sct", "SCT"], ["images", "Histo"]].map(([value, label]) => (
                  <button key={value} type="button" className={activityFilter === value ? "active" : ""} onClick={() => setActivityFilter(value)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="home-v3-activity-list">
              {filteredActivity.length === 0 ? (
                <div className="home-v3-empty-activity">
                  <strong>Sin actividad para este filtro</strong>
                  <span>Usa un módulo para generar nuevos registros.</span>
                </div>
              ) : (
                filteredActivity.map((item, index) => (
                  <button key={`${item.timestamp}-${index}`} type="button" className="home-v3-activity-row" onClick={() => navigate(activityRoute(item.type))}>
                    <span className={`home-v3-activity-icon type-${activityIcon(item.type)}`}>
                      <ActivityGlyph type={activityIcon(item.type)} />
                    </span>
                    <span className="home-v3-activity-copy">
                      <strong>{activityTitle(item)}</strong>
                      <small>{activitySubtitle(item)}</small>
                    </span>
                    <span className="home-v3-activity-time">{timeAgo(item.timestamp)}</span>
                  </button>
                ))
              )}
            </div>
            <div className="home-v3-activity-foot">
              <span>Mostrando {filteredActivity.length} de {activity.length}</span>
              <button type="button" onClick={() => setActivityFilter("all")}>Ver toda la actividad</button>
            </div>
          </div>

          <aside className="home-v3-side-stack">
            <div className="home-v3-suggestion-card">
              <span className="home-v3-suggest-label">Sugerido</span>
              <h3>Repasa <em>histopatologia</em> hoy.</h3>
              <p>Analiza una nueva lámina o genera 5 ítems SCT para reforzar tu razonamiento clínico.</p>
              <button type="button" onClick={() => navigate("/dashboard/sct")}>
                Empezar caso <span>{"->"}</span>
              </button>
            </div>

            <div className="home-v3-ranking-card">
              <div className="home-v3-ranking-head">
                <strong>Ranking semanal</strong>
                {percentile != null && <span>Top {percentile}%</span>}
              </div>
              {ranking.length === 0 ? (
                <div className="home-v3-ranking-empty">Sin datos suficientes esta semana</div>
              ) : (
                <div className="home-v3-ranking-list">
                  {ranking.map((item, index) => (
                    <div key={`${item.name}-${index}`} className={item.is_you ? "is-you" : ""}>
                      <span>#{index + 1}</span>
                      <strong>{item.is_you ? `${item.name} (tu)` : item.name}</strong>
                      <b>{item.score}%</b>
                    </div>
                  ))}
                </div>
              )}
              {yourPosition != null && (
                <div className="home-v3-ranking-foot">
                  Posición #{yourPosition} de {rankingData?.total_users} usuarios activos
                </div>
              )}
            </div>
          </aside>
        </section>
      </main>
    </>
  );
}
