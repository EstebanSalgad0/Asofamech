import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listSurveys, getSurvey, submitSurveyResponse } from "../api";
import { AppSidebar } from "../components/AppSidebar";
import { clearAuthSession, getStoredRole, getStoredUser } from "../authClient";

const SCALE_LABELS = {
  1: "Totalmente en desacuerdo",
  2: "En desacuerdo",
  3: "Ni acuerdo ni desacuerdo",
  4: "De acuerdo",
  5: "Totalmente de acuerdo",
};

// Metadatos visuales por encuesta. Si aparece una nueva sin match, cae en "default".
const SURVEY_META = {
  razonamiento: { modifier: "razonamiento", icon: "🧠", chip: "Razonamiento clínico" },
  fpa:          { modifier: "fpa",          icon: "🔬", chip: "Fisiopatología" },
  pap:          { modifier: "pap",          icon: "🩺", chip: "Patología" },
};
const DEFAULT_META = { modifier: "default", icon: "📋", chip: "Encuesta" };

function metaFor(code) {
  return SURVEY_META[code] || DEFAULT_META;
}

function LikertRow({ item, value, onChange }) {
  const answered = typeof value === "number" && value >= 1 && value <= 5;
  return (
    <div className={`sv-item${answered ? " sv-item--answered" : ""}`}>
      <div className="sv-item-text">{item.text}</div>
      <div className="sv-likert" role="radiogroup" aria-label={item.text}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            className={`sv-lb${value === n ? " selected" : ""}`}
            data-value={n}
            onClick={() => onChange(item.id, n)}
            title={SCALE_LABELS[n]}
            data-testid={`survey-rating-${item.id}-${n}`}
          >
            {n}
          </button>
        ))}
        <span className="sv-scale-caption">{answered ? SCALE_LABELS[value] : "Elige una opción"}</span>
      </div>
    </div>
  );
}

function OpenRow({ item, value, onChange }) {
  return (
    <div className="sv-item sv-item--open">
      <div className="sv-item-text">
        {item.text}
        {!item.required && <span className="sv-item-optional">(opcional)</span>}
      </div>
      <textarea
        className="sv-textarea"
        value={value || ""}
        onChange={(e) => onChange(item.id, e.target.value)}
        rows={3}
        placeholder="Escribe tu respuesta..."
        data-testid={`survey-open-${item.id}`}
      />
    </div>
  );
}

function groupBySection(items) {
  const groups = [];
  const map = new Map();
  for (const it of items) {
    if (!map.has(it.section)) {
      map.set(it.section, { section: it.section, items: [] });
      groups.push(map.get(it.section));
    }
    map.get(it.section).items.push(it);
  }
  return groups;
}

// "I. Utilidad Percibida" → "I"
function sectionShortLabel(name) {
  const m = /^([IVX]+|\d+)/.exec(name || "");
  return m ? m[1] : "•";
}

export function SurveysPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");

  const [surveys, setSurveys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCode, setSelectedCode] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [answers, setAnswers] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [justSubmitted, setJustSubmitted] = useState(false);

  useEffect(() => {
    const storedUser = getStoredUser();
    if (!storedUser) {
      navigate("/auth");
      return;
    }
    setUser(storedUser);
    setRole(getStoredRole());
    loadSurveys();
  }, [navigate]);

  async function loadSurveys() {
    setLoading(true);
    try {
      const data = await listSurveys();
      setSurveys(data || []);
    } catch (e) {
      setError(e.message || "No se pudieron cargar las encuestas");
    } finally {
      setLoading(false);
    }
  }

  async function openSurvey(code) {
    setSelectedCode(code);
    setDetail(null);
    setAnswers({});
    setError(null);
    setJustSubmitted(false);
    setLoadingDetail(true);
    try {
      const d = await getSurvey(code);
      setDetail(d);
    } catch (e) {
      setError(e.message || "No se pudo cargar la encuesta");
    } finally {
      setLoadingDetail(false);
    }
  }

  function backToList() {
    setSelectedCode(null);
    setDetail(null);
    setAnswers({});
    setError(null);
    setJustSubmitted(false);
  }

  function setAnswer(itemId, value) {
    setAnswers((prev) => ({ ...prev, [itemId]: value }));
  }

  const requiredIds = useMemo(
    () => (detail ? detail.items.filter((i) => i.required).map((i) => i.id) : []),
    [detail],
  );

  function isAnswered(itemId, itemType) {
    const v = answers[itemId];
    if (itemType === "likert_1_5") return typeof v === "number" && v >= 1 && v <= 5;
    return !!(v && String(v).trim());
  }

  const answeredRequiredCount = useMemo(() => {
    if (!detail) return 0;
    return detail.items.filter((i) => i.required && isAnswered(i.id, i.item_type)).length;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answers, detail]);

  const progressPct = requiredIds.length === 0 ? 0 : Math.round((answeredRequiredCount / requiredIds.length) * 100);
  const isComplete = requiredIds.length > 0 && answeredRequiredCount === requiredIds.length;

  async function handleSubmit() {
    if (!detail) return;
    if (!isComplete) {
      setError("Debes responder todas las preguntas obligatorias.");
      return;
    }
    if (!window.confirm("Vas a enviar tu respuesta. Es anónima y NO podrás modificarla después. ¿Continuar?")) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = detail.items
        .filter((it) => answers[it.id] !== undefined && answers[it.id] !== "")
        .map((it) => ({
          item_id: it.id,
          value_int: it.item_type === "likert_1_5" ? answers[it.id] : null,
          value_text: it.item_type === "open_text" ? String(answers[it.id]) : null,
        }));
      await submitSurveyResponse(detail.code, payload);
      setJustSubmitted(true);
      await loadSurveys();
      const refreshed = await getSurvey(detail.code);
      setDetail(refreshed);
    } catch (e) {
      setError(e.message || "No se pudo enviar la encuesta");
    } finally {
      setSaving(false);
    }
  }

  function handleLogout() {
    clearAuthSession();
    navigate("/auth");
  }

  const sections = useMemo(() => (detail ? groupBySection(detail.items) : []), [detail]);
  const detailMeta = detail ? metaFor(detail.code) : DEFAULT_META;
  const activeRoute = "surveys";

  return (
    <div className="dashboard-layout">
      <AppSidebar user={user} role={role} activeRoute={activeRoute} onLogout={handleLogout} />

      <main className="dashboard-main">
        <div className="sv-page" data-testid="surveys-page">
          {/* ============ LISTA ============ */}
          {!selectedCode && (
            <>
              <section className="sv-hero">
                <div className="sv-hero-top">
                  <div>
                    <h1 className="sv-hero-title">Encuestas de percepción</h1>
                    <p className="sv-hero-sub">
                      Tu opinión ayuda a mejorar la plataforma. Las respuestas son <b>anónimas</b> y solo pueden enviarse una vez por encuesta.
                    </p>
                  </div>
                  <span className="sv-hero-badge">
                    {surveys.length} {surveys.length === 1 ? "disponible" : "disponibles"}
                  </span>
                </div>
              </section>

              {error && <div className="sv-error">{error}</div>}

              {loading && <div className="sv-empty">Cargando encuestas...</div>}

              {!loading && surveys.length === 0 && (
                <div className="sv-empty">
                  <div className="sv-empty-icon">📭</div>
                  No hay encuestas disponibles por ahora.
                </div>
              )}

              {!loading && surveys.length > 0 && (
                <div className="sv-list">
                  {surveys.map((s) => {
                    const meta = metaFor(s.code);
                    return (
                      <button
                        key={s.code}
                        type="button"
                        onClick={() => openSurvey(s.code)}
                        className={`sv-card sv-card--${meta.modifier}`}
                        data-testid={`survey-card-${s.code}`}
                      >
                        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                          <span className="sv-card-icon" aria-hidden="true">{meta.icon}</span>
                          <span className="sv-card-chip">{meta.chip}</span>
                        </div>
                        <h3 className="sv-card-title">{s.title}</h3>
                        {s.description && <p className="sv-card-desc">{s.description}</p>}
                        <div className="sv-card-foot">
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>Escala Likert 1–5</span>
                          <span className="sv-card-cta">Responder →</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </>
          )}

          {/* ============ FORMULARIO ============ */}
          {selectedCode && (
            <>
              <div className="sv-form-header">
                <div>
                  <h1 className="sv-hero-title" style={{ fontSize: 28, marginBottom: 2 }}>Encuestas de percepción</h1>
                  <p className="sv-hero-sub" style={{ fontSize: 13 }}>
                    Respuestas <b>anónimas</b> — envío único, sin edición posterior.
                  </p>
                </div>
                <button type="button" onClick={backToList} className="sv-back-btn">← Volver</button>
              </div>

              {error && <div className="sv-error">{error}</div>}

              {loadingDetail && <div className="sv-empty">Cargando encuesta...</div>}

              {detail && !loadingDetail && (
                <div className={`sv-card--${detailMeta.modifier}`} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                  <section className="sv-form-hero">
                    <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 10 }}>
                      <span className="sv-card-icon" aria-hidden="true">{detailMeta.icon}</span>
                      <span className="sv-card-chip">{detailMeta.chip}</span>
                    </div>
                    <h2 className="sv-form-hero-title">{detail.title}</h2>
                    {detail.description && <p className="sv-form-hero-sub">{detail.description}</p>}
                  </section>

                  {(detail.already_answered || justSubmitted) && (
                    <div className="sv-answered" data-testid="survey-already-answered">
                      <div className="sv-answered-icon">✓</div>
                      <div>
                        <h3 className="sv-answered-title">¡Gracias por tu participación!</h3>
                        <p className="sv-answered-body">
                          Ya respondiste esta encuesta. Las respuestas son anónimas y no pueden modificarse.
                        </p>
                      </div>
                    </div>
                  )}

                  {!(detail.already_answered || justSubmitted) && detail.status === "archived" && (
                    <div className="sv-archived">
                      Esta encuesta está archivada y ya no acepta nuevas respuestas.
                    </div>
                  )}

                  {!(detail.already_answered || justSubmitted) && detail.status === "open" && (
                    <>
                      <div className="sv-progress">
                        <div className="sv-progress-bar-wrap">
                          <div className="sv-progress-bar" style={{ width: `${progressPct}%` }} />
                        </div>
                        <span className="sv-progress-label">
                          <b>{answeredRequiredCount}</b> de {requiredIds.length} obligatorias
                        </span>
                      </div>

                      {sections.map((sec, idx) => (
                        <section key={sec.section} className="sv-section">
                          <header className="sv-section-header">
                            <span className="sv-section-num">{sectionShortLabel(sec.section)}</span>
                            <h3 className="sv-section-title">{sec.section.replace(/^([IVX]+|\d+)\.\s*/, "")}</h3>
                          </header>
                          <div className="sv-section-body">
                            {sec.items.map((it) =>
                              it.item_type === "likert_1_5" ? (
                                <LikertRow key={it.id} item={it} value={answers[it.id]} onChange={setAnswer} />
                              ) : (
                                <OpenRow key={it.id} item={it} value={answers[it.id]} onChange={setAnswer} />
                              ),
                            )}
                          </div>
                        </section>
                      ))}

                      <div className="sv-actions">
                        <span className="sv-actions-hint">
                          {isComplete
                            ? "Todo listo. Revisa tus respuestas antes de enviar — no podrás modificarlas."
                            : `Faltan ${requiredIds.length - answeredRequiredCount} pregunta(s) obligatoria(s).`}
                        </span>
                        <button
                          type="button"
                          onClick={handleSubmit}
                          disabled={saving || !isComplete}
                          className="sv-btn-primary"
                          data-testid="survey-submit"
                        >
                          {saving ? "Enviando..." : "Enviar respuestas"}
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
