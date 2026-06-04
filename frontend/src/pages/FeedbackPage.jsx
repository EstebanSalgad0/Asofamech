import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { submitFeedback, getMyFeedback, getFeedbackSummary, getFeedbackResponses, downloadFeedbackCsv } from "../api";
import { AppSidebar } from "../components/AppSidebar";
import { clearAuthSession, getStoredRole, getStoredUser, canManageEducationalContent } from "../authClient";

const DIMENSIONS = [
  { key: "nav_clarity",     label: "Claridad de navegación",      hint: "¿Es fácil encontrar las secciones del sistema?" },
  { key: "viewer_ease",     label: "Facilidad del visor de imágenes", hint: "¿El visor histopatológico es intuitivo?" },
  { key: "roi_ease",        label: "Selección de ROI",            hint: "¿Es sencillo marcar las regiones de interés?" },
  { key: "ai_clarity",      label: "Claridad de resultados IA",   hint: "¿Los resultados del análisis se entienden?" },
  { key: "chatbot_utility", label: "Utilidad del chatbot",        hint: "¿El asistente responde de forma útil?" },
  { key: "sct_utility",     label: "Utilidad del Test SCT",       hint: "¿Los tests de razonamiento clínico son valiosos?" },
];

const SCALE_LABELS = { 1: "Muy malo", 2: "Malo", 3: "Regular", 4: "Bueno", 5: "Excelente" };

const EMPTY_RATINGS = Object.fromEntries(DIMENSIONS.map((d) => [d.key, 0]));

function RatingRow({ label, hint, dimKey, value, onChange }) {
  return (
    <div className="fb-dim-row">
      <div className="fb-dim-info">
        <span className="fb-dim-label">{label}</span>
        <span className="fb-dim-hint">{hint}</span>
      </div>
      <div className="fb-scale">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            className={`fb-scale-btn${value === n ? " selected" : ""}`}
            onClick={() => onChange(dimKey, n)}
            title={SCALE_LABELS[n]}
            aria-label={`${label}: ${n}`}
            data-testid={`feedback-rating-${dimKey}-${n}`}
          >
            {n}
          </button>
        ))}
        {value > 0 && (
          <span className="fb-scale-label">{SCALE_LABELS[value]}</span>
        )}
      </div>
    </div>
  );
}

function MiniBar({ value, max }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  const color = value >= 4 ? "#D4A017" : value >= 3 ? "#f59e0b" : "#ff6b5c";
  return (
    <div className="fb-mini-bar-wrap">
      <div className="fb-mini-bar" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function ScoreDot({ value }) {
  const color = value >= 4 ? "#D4A017" : value >= 3 ? "#f59e0b" : "#ff6b5c";
  return <span className="fb-score-dot" style={{ background: color }}>{value.toFixed(1)}</span>;
}

export function FeedbackPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [canManage, setCanManage] = useState(false);

  const [tab, setTab] = useState("form");   // "form" | "summary"
  const [ratings, setRatings] = useState(EMPTY_RATINGS);
  const [observations, setObservations] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [existingFeedback, setExistingFeedback] = useState(null);
  const [loadingMy, setLoadingMy] = useState(true);

  const [summary, setSummary] = useState(null);
  const [responses, setResponses] = useState([]);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);
  const [roleFilter, setRoleFilter] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const storedUser = getStoredUser();
    const storedRole = getStoredRole();
    if (!storedUser) { navigate("/auth"); return; }
    setUser(storedUser);
    setRole(storedRole);
    const manage = canManageEducationalContent(storedRole);
    setCanManage(manage);

    getMyFeedback()
      .then((fb) => {
        if (fb) {
          setExistingFeedback(fb);
          setRatings({
            nav_clarity: fb.nav_clarity,
            viewer_ease: fb.viewer_ease,
            roi_ease: fb.roi_ease,
            ai_clarity: fb.ai_clarity,
            chatbot_utility: fb.chatbot_utility,
            sct_utility: fb.sct_utility,
          });
          setObservations(fb.observations || "");
          setDisplayName(fb.display_name || "");
        }
      })
      .catch(() => {})
      .finally(() => setLoadingMy(false));
  }, [navigate]);

  useEffect(() => {
    if (tab !== "summary" || !canManage) return;
    setSummaryLoading(true);
    setSummaryError(null);
    Promise.all([getFeedbackSummary(), getFeedbackResponses(roleFilter)])
      .then(([sum, resp]) => { setSummary(sum); setResponses(resp); })
      .catch((err) => setSummaryError(err.message))
      .finally(() => setSummaryLoading(false));
  }, [tab, canManage, roleFilter]);

  function handleLogout() {
    clearAuthSession();
    navigate("/auth");
  }

  function handleRatingChange(key, value) {
    setRatings((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const missing = DIMENSIONS.filter((d) => ratings[d.key] === 0);
    if (missing.length > 0) {
      setSaveError(`Por favor evalúa todas las dimensiones (falta: ${missing.map((d) => d.label).join(", ")})`);
      return;
    }
    setSaveError(null);
    setSaving(true);
    try {
      const result = await submitFeedback({
        ...ratings,
        observations: observations.trim() || null,
        display_name: displayName.trim() || null,
      });
      setExistingFeedback(result);
      setSubmitted(true);
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function handleEdit() {
    setSubmitted(false);
  }

  return (
    <div className="dashboard-layout">
      <AppSidebar user={user} role={role} activeRoute="feedback" onLogout={handleLogout} />

      <main className="dashboard-main">
        <div className="fb-page" data-testid="feedback-page">

          <div className="fb-header">
            <div>
              <h1 className="fb-title">Evaluación de Usabilidad</h1>
              <p className="fb-subtitle">
                Tu opinión ayuda a mejorar el sistema para futuras versiones.
                Las respuestas son confidenciales.
              </p>
            </div>
            {canManage && (
              <div className="fb-tabs">
                <button className={`fb-tab${tab === "form" ? " active" : ""}`} onClick={() => setTab("form")}>
                  Mi evaluación
                </button>
                <button className={`fb-tab${tab === "summary" ? " active" : ""}`} onClick={() => setTab("summary")}>
                  Resumen general
                </button>
              </div>
            )}
          </div>

          {/* ── FORMULARIO ─────────────────────────────────────────── */}
          {tab === "form" && (
            <>
              {loadingMy && <p className="fb-loading">Cargando...</p>}

              {!loadingMy && submitted && (
                <div className="fb-thankyou" data-testid="feedback-confirmation">
                  <div className="fb-thankyou-icon">✓</div>
                  <h2>¡Gracias por tu evaluación!</h2>
                  <p>Tu retroalimentación ha sido registrada correctamente.</p>
                  <button className="fb-btn-secondary" onClick={handleEdit}>
                    Modificar respuestas
                  </button>
                </div>
              )}

              {!loadingMy && !submitted && (
                <form className="fb-form" onSubmit={handleSubmit} data-testid="feedback-form">
                  {existingFeedback && (
                    <div className="fb-notice">
                      Ya enviaste una evaluación. Puedes modificarla y guardar de nuevo.
                    </div>
                  )}

                  <div className="fb-scale-header">
                    <span />
                    <div className="fb-scale-legend">
                      {[1, 2, 3, 4, 5].map((n) => (
                        <span key={n} className="fb-legend-item">
                          <b>{n}</b>
                          <small>{SCALE_LABELS[n]}</small>
                        </span>
                      ))}
                    </div>
                  </div>

                  {DIMENSIONS.map((dim) => (
                    <RatingRow
                      key={dim.key}
                      label={dim.label}
                      hint={dim.hint}
                      dimKey={dim.key}
                      value={ratings[dim.key]}
                      onChange={handleRatingChange}
                    />
                  ))}

                  <div className="fb-obs-row">
                    <label className="fb-obs-label">
                      Tu nombre <span className="fb-optional">(opcional)</span>
                    </label>
                    <input
                      className="fb-name-input"
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="Escribe tu nombre si deseas identificar tu evaluación"
                      maxLength={100}
                      data-testid="feedback-display-name"
                    />
                  </div>

                  <div className="fb-obs-row">
                    <label className="fb-obs-label">
                      Observaciones adicionales <span className="fb-optional">(opcional)</span>
                    </label>
                    <textarea
                      className="fb-obs-textarea"
                      value={observations}
                      onChange={(e) => setObservations(e.target.value)}
                      placeholder="¿Hay algo específico que quieras destacar o mejorar?"
                      rows={4}
                      maxLength={1000}
                      data-testid="feedback-observations"
                    />
                    <span className="fb-char-count">{observations.length}/1000</span>
                  </div>

                  {saveError && <p className="fb-error">{saveError}</p>}

                  <div className="fb-form-actions">
                    <button type="submit" className="fb-btn-submit" disabled={saving} data-testid="feedback-submit">
                      {saving ? "Guardando..." : existingFeedback ? "Actualizar evaluación" : "Enviar evaluación"}
                    </button>
                  </div>
                </form>
              )}
            </>
          )}

          {/* ── RESUMEN (docente/admin) ─────────────────────────────── */}
          {tab === "summary" && canManage && (
            <div className="fb-summary">
              {summaryLoading && <p className="fb-loading">Cargando resumen...</p>}
              {summaryError && <p className="fb-error">{summaryError}</p>}

              {!summaryLoading && summary && (
                <>
                  <div className="fb-summary-meta">
                    <span className="fb-summary-count">
                      {summary.total_responses} {summary.total_responses === 1 ? "respuesta" : "respuestas"}
                    </span>
                    {Object.entries(summary.by_role).map(([r, info]) => (
                      <span key={r} className="fb-summary-role-chip">
                        {r}: {info.count}{info.anonymized ? " (datos insuficientes)" : ""}
                      </span>
                    ))}
                    <button
                      className="fb-btn-export"
                      onClick={async () => {
                        setExporting(true);
                        try { await downloadFeedbackCsv(); }
                        catch (e) { alert(e.message); }
                        finally { setExporting(false); }
                      }}
                      disabled={exporting || summary.total_responses === 0}
                    >
                      {exporting ? "Exportando..." : "Exportar CSV"}
                    </button>
                  </div>

                  <div className="fb-summary-grid">
                    {DIMENSIONS.map((dim) => {
                      const avg = summary.averages[dim.key] ?? 0;
                      return (
                        <div key={dim.key} className="fb-summary-card">
                          <div className="fb-summary-card-top">
                            <span className="fb-summary-dim-label">{dim.label}</span>
                            <ScoreDot value={avg} />
                          </div>
                          <MiniBar value={avg} max={5} />
                          <div className="fb-summary-role-breakdown">
                            {Object.entries(summary.by_role).map(([r, info]) =>
                              info.anonymized ? (
                                <span key={r} className="fb-breakdown-item fb-breakdown-anon" title="Menos de 3 respuestas para este rol">
                                  {r}: —
                                </span>
                              ) : (
                                <span key={r} className="fb-breakdown-item">
                                  {r}: {(info.averages[dim.key] ?? 0).toFixed(1)}
                                </span>
                              )
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {summary.recent_observations.length > 0 && (
                    <div className="fb-observations-panel">
                      <h3 className="fb-obs-title">Observaciones recientes</h3>
                      <ul className="fb-obs-list">
                        {summary.recent_observations.map((obs, i) => (
                          <li key={i} className="fb-obs-item">{obs}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="fb-responses-section">
                    <div className="fb-responses-header">
                      <h3 className="fb-obs-title">Respuestas individuales</h3>
                      <select
                        className="fb-role-filter"
                        value={roleFilter}
                        onChange={(e) => setRoleFilter(e.target.value)}
                      >
                        <option value="">Todos los roles</option>
                        <option value="estudiante">Estudiante</option>
                        <option value="docente">Docente</option>
                        <option value="administrador">Administrador</option>
                      </select>
                    </div>
                    {responses.length === 0 ? (
                      <p className="fb-empty">No hay respuestas para este filtro.</p>
                    ) : (
                      <div className="fb-responses-table-wrap">
                        <table className="fb-responses-table">
                          <thead>
                            <tr>
                              <th>Nombre</th>
                              <th>Rol</th>
                              {DIMENSIONS.map((d) => (
                                <th key={d.key} title={d.label}>{d.label.split(" ")[0]}</th>
                              ))}
                              <th>Observaciones</th>
                              <th>Fecha</th>
                            </tr>
                          </thead>
                          <tbody>
                            {responses.map((r, i) => (
                              <tr key={i}>
                                <td className="fb-cell-name">{r.display_name || <span className="fb-anon">—</span>}</td>
                                <td><span className="fb-role-tag">{r.role}</span></td>
                                {DIMENSIONS.map((d) => (
                                  <td key={d.key} className="fb-cell-rating">
                                    <span
                                      className="fb-rating-pill"
                                      style={{
                                        background: r[d.key] >= 4 ? "rgba(212,160,23,0.12)" :
                                                    r[d.key] >= 3 ? "rgba(245,158,11,0.12)" :
                                                    "rgba(255,107,92,0.12)",
                                        color: r[d.key] >= 4 ? "#7A4F00" :
                                               r[d.key] >= 3 ? "#b45309" : "#c0392b",
                                      }}
                                    >
                                      {r[d.key]}
                                    </span>
                                  </td>
                                ))}
                                <td className="fb-cell-obs">{r.observations || "—"}</td>
                                <td className="fb-cell-date">
                                  {r.submitted_at ? new Date(r.submitted_at).toLocaleDateString("es-ES") : "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
