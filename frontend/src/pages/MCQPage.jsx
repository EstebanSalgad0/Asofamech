import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  deleteMCQTest,
  getMCQTest,
  listAllMCQAttempts,
  listMCQTests,
  listMyMCQAttempts,
  submitMCQAttempt,
  updateMCQTest,
} from "../api";
import { startSession, flushSession, trackTestCompleted, pushActivity } from "../tracker";
import { AppSidebar } from "../components/AppSidebar";
import { MCQManualBuilder } from "../components/MCQManualBuilder";
import { clearAuthSession, getStoredRole, canManageEducationalContent } from "../authClient";

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" });
}

function scorePercent(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return 0;
  return Math.round(value <= 1 ? value * 100 : value);
}

function shuffleArray(list) {
  const result = [...list];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

/** Baraja el orden de las preguntas y, dentro de cada una, el de sus
 * alternativas. `optionOrder[posicionMostrada] = índiceOriginal`, así el
 * puntaje siempre se calcula (y se envía al backend) contra los índices
 * originales sin importar cómo se vieron en pantalla. */
function buildShuffledItems(items) {
  return shuffleArray(items).map((item) => {
    const optionOrder = shuffleArray(item.options.map((_, i) => i));
    return {
      id: item.id,
      question: item.question,
      explanation: item.explanation,
      correctIndex: item.correct_index,
      displayOptions: optionOrder.map((originalIndex) => item.options[originalIndex]),
      optionOrder,
    };
  });
}

export function MCQPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedTestId = Number.parseInt(searchParams.get("test") || "", 10);
  const openedRequestedTestRef = useRef(null);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [canManage, setCanManage] = useState(false);
  const [savedTests, setSavedTests] = useState([]);
  const [currentTest, setCurrentTest] = useState(null);
  const [viewMode, setViewMode] = useState("config");
  const [answers, setAnswers] = useState({});
  const [testResults, setTestResults] = useState(null);
  const [toast, setToast] = useState(null);
  const [myDbAttempts, setMyDbAttempts] = useState([]);
  const [allAttempts, setAllAttempts] = useState([]);
  const [updatingStatusId, setUpdatingStatusId] = useState(null);
  const [testStartedAt, setTestStartedAt] = useState(null);
  const [showBuilder, setShowBuilder] = useState(false);

  const showToast = (message, type = "info") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => {
    const userData = localStorage.getItem("user");
    const token = localStorage.getItem("auth_token");
    if (!userData || !token) {
      clearAuthSession();
      navigate("/auth");
      return;
    }
    setUser(JSON.parse(userData));
    const storedRole = getStoredRole();
    setRole(storedRole);
    setCanManage(canManageEducationalContent(storedRole));
    startSession();
    loadSavedTests();
    loadMyAttempts();
    if (canManageEducationalContent(storedRole)) loadAllAttempts();
    const handleUnload = () => flushSession();
    window.addEventListener("beforeunload", handleUnload);
    return () => {
      flushSession();
      window.removeEventListener("beforeunload", handleUnload);
    };
  }, [navigate]);

  const loadSavedTests = async () => {
    try {
      setSavedTests((await listMCQTests()) || []);
    } catch {
      setSavedTests([]);
    }
  };

  const loadMyAttempts = async () => {
    try {
      setMyDbAttempts((await listMyMCQAttempts()) || []);
    } catch {
      setMyDbAttempts([]);
    }
  };

  const loadAllAttempts = async () => {
    try {
      setAllAttempts((await listAllMCQAttempts()) || []);
    } catch {
      setAllAttempts([]);
    }
  };

  const handleUpdateTestStatus = async (testId, status) => {
    setUpdatingStatusId(testId);
    try {
      await updateMCQTest(testId, { status });
      await loadSavedTests();
      showToast(`Estado actualizado a "${status}"`, "success");
    } catch {
      showToast("Error al actualizar el estado del test", "error");
    } finally {
      setUpdatingStatusId(null);
    }
  };

  const handleDeleteTest = async (testId) => {
    if (!confirm("¿Eliminar este test de alternativas?")) return;
    try {
      await deleteMCQTest(testId);
      await loadSavedTests();
      showToast("Test eliminado", "success");
    } catch {
      showToast("Error al eliminar el test", "error");
    }
  };

  const handleLoadTest = async (testId) => {
    try {
      const data = await getMCQTest(testId);
      if (data?.items?.length > 0) {
        setCurrentTest({
          id: data.id,
          title: data.name,
          topic: data.topic,
          difficulty: data.difficulty,
          date: formatDate(data.created_at),
          items: buildShuffledItems(data.items),
        });
        setViewMode("test");
        setAnswers({});
        setTestStartedAt(new Date().toISOString());
      } else {
        showToast("No se pudo cargar el test.", "error");
      }
    } catch {
      showToast("Error al cargar el test.", "error");
    }
  };

  useEffect(() => {
    if (
      !user
      || !Number.isInteger(requestedTestId)
      || requestedTestId <= 0
      || openedRequestedTestRef.current === requestedTestId
    ) {
      return;
    }
    openedRequestedTestRef.current = requestedTestId;
    handleLoadTest(requestedTestId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestedTestId, user]);

  const handleAnswer = (itemId, displayPosition) => {
    setAnswers((prev) => ({ ...prev, [itemId]: displayPosition }));
  };

  const handleSubmitTest = async () => {
    const answered = Object.keys(answers).length;
    const total = currentTest.items.length;
    if (answered < total) {
      showToast(`Faltan ${total - answered} respuestas. Completa todas antes de enviar.`, "warning");
      return;
    }
    let correct = 0;
    const results = currentTest.items.map((item) => {
      const displayPosition = answers[item.id];
      const selectedIndex = item.optionOrder[displayPosition];
      const isCorrect = selectedIndex === item.correctIndex;
      if (isCorrect) correct++;
      return {
        itemId: item.id,
        question: item.question,
        displayOptions: item.displayOptions,
        selectedPosition: displayPosition,
        correctPosition: item.optionOrder.indexOf(item.correctIndex),
        isCorrect,
        explanation: item.explanation,
      };
    });
    const score = Math.round((correct / total) * 100);
    setTestResults({ score, correctCount: correct, totalItems: total, results });
    setViewMode("results");
    trackTestCompleted(score >= 60);
    pushActivity("mcq", `${currentTest.title} — ${score}%`);

    try {
      const backendAnswers = currentTest.items.map((item) => ({
        item_id: item.id,
        selected_index: item.optionOrder[answers[item.id]],
      }));
      await submitMCQAttempt(currentTest.id, backendAnswers, testStartedAt);
      loadMyAttempts();
    } catch {
      // el resultado local ya se muestra igual
    }
  };

  const handleBackToConfig = () => {
    if (window.confirm("¿Estás seguro? Se perderá el progreso actual.")) {
      setViewMode("config");
      setCurrentTest(null);
      setAnswers({});
      setTestResults(null);
    }
  };

  const handleNewTest = () => {
    setViewMode("config");
    setCurrentTest(null);
    setAnswers({});
    setTestResults(null);
  };

  const handleLogout = () => { flushSession(); clearAuthSession(); navigate("/"); };
  const handleRoleChange = () => setRole(getStoredRole());

  if (!user) return null;

  const answeredCount = Object.keys(answers).length;
  const totalItems = currentTest?.items?.length || 0;
  const progressPct = totalItems > 0 ? Math.round((answeredCount / totalItems) * 100) : 0;
  const letterFor = (index) => String.fromCharCode(97 + index);

  /* ── TEST VIEW ── */
  if (viewMode === "test" && currentTest) {
    return (
      <>
        <AppSidebar user={user} role={role} activeRoute="mcq" onRoleChange={handleRoleChange} onLogout={handleLogout} />
        <div className="page-scroll" data-testid="mcq-test-page">
          <div className="sct-test-topbar">
            <button onClick={handleBackToConfig} className="sct-back-btn">← Volver</button>
            <div className="sct-test-info">
              <span className="sct-test-name">{currentTest.title}</span>
              {currentTest.difficulty && <span className="sct-test-chip">{currentTest.difficulty}</span>}
            </div>
            <div className="sct-progress-info">
              <span className="sct-progress-text">{answeredCount} / {totalItems}</span>
              <div className="sct-progress-track">
                <div className="sct-progress-fill" style={{ width: `${progressPct}%` }} />
              </div>
            </div>
          </div>

          <div className="sct-test-body">
            {currentTest.items.map((item, idx) => (
              <div key={item.id} className="sct-item-card" data-testid={`mcq-item-${item.id}`}>
                <div className="sct-item-num">Pregunta {idx + 1}</div>
                <div className="sct-item-section">
                  <div className="sct-item-section-txt">{item.question}</div>
                </div>
                <div className="sct-answer-section">
                  <div className="mcq-options-list">
                    {item.displayOptions.map((option, optIndex) => (
                      <label
                        key={optIndex}
                        className={`mcq-option ${answers[item.id] === optIndex ? "selected" : ""}`}
                        data-testid={`mcq-answer-${item.id}-${optIndex}`}
                      >
                        <input
                          type="radio"
                          name={`item-${item.id}`}
                          checked={answers[item.id] === optIndex}
                          onChange={() => handleAnswer(item.id, optIndex)}
                        />
                        <span className="mcq-option-letter">{letterFor(optIndex)}</span>
                        <span className="mcq-option-text">{option}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            ))}

            <div className="sct-submit-section">
              <button onClick={handleSubmitTest} className="sct-submit-btn" data-testid="mcq-submit">
                ✓ Enviar para Evaluación
              </button>
              <div className="sct-submit-note">Asegúrate de responder todas las preguntas antes de enviar</div>
            </div>
          </div>
        </div>
        {toast && (
          <div className={`v2-toast ${toast.type}`}>
            <span className="v2-toast-msg">{toast.message}</span>
            <button className="v2-toast-close" onClick={() => setToast(null)}>✕</button>
          </div>
        )}
      </>
    );
  }

  /* ── RESULTS VIEW ── */
  if (viewMode === "results" && testResults) {
    return (
      <>
        <AppSidebar user={user} role={role} activeRoute="mcq" onRoleChange={handleRoleChange} onLogout={handleLogout} />
        <div className="page-scroll" data-testid="mcq-results-page">
          <div className="sct-results-hero" data-testid="mcq-results">
            <div className="sct-score-ring">
              <svg width="140" height="140" viewBox="0 0 140 140">
                <circle cx="70" cy="70" r="58" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="9" />
                <circle
                  cx="70" cy="70" r="58" fill="none"
                  stroke={testResults.score >= 70 ? "var(--accent)" : testResults.score >= 50 ? "var(--indigo)" : "var(--coral)"}
                  strokeWidth="9"
                  strokeDasharray={`${(testResults.score / 100) * 364} 364`}
                  transform="rotate(-90 70 70)" strokeLinecap="round"
                />
              </svg>
              <div className="sct-score-center">
                <div className="sct-score-num">{testResults.score}<span>%</span></div>
                <div className="sct-score-lbl">Puntuación</div>
              </div>
            </div>
            <div className="sct-results-info">
              <div className="sct-results-title">¡Test Completado!</div>
              <div className="sct-results-summary">{testResults.correctCount} de {testResults.totalItems} correctas</div>
            </div>
          </div>

          <div className="sct-results-body">
            <div className="sct-feedback-title">Retroalimentación Detallada</div>
            {testResults.results.map((r, i) => (
              <div key={r.itemId} className={`sct-feedback-card ${r.isCorrect ? "correct" : "incorrect"}`} data-testid={`mcq-feedback-card-${r.itemId}`}>
                <div className="sct-feedback-top">
                  <span className="sct-feedback-num">Pregunta {i + 1}</span>
                  <span className={`sct-feedback-status ${r.isCorrect ? "correct" : "incorrect"}`}>
                    {r.isCorrect ? "✓ Correcto" : "✗ Incorrecto"}
                  </span>
                </div>
                <div className="sct-feedback-field">{r.question}</div>
                <div className="mcq-options-list">
                  {r.displayOptions.map((option, optIndex) => (
                    <div
                      key={optIndex}
                      className={`mcq-option review ${optIndex === r.correctPosition ? "correct" : ""} ${optIndex === r.selectedPosition && optIndex !== r.correctPosition ? "wrong" : ""}`}
                    >
                      <span className="mcq-option-letter">{letterFor(optIndex)}</span>
                      <span className="mcq-option-text">{option}</span>
                      {optIndex === r.selectedPosition && <span className="mcq-option-tag">Tu respuesta</span>}
                      {optIndex === r.correctPosition && <span className="mcq-option-tag correct">Correcta</span>}
                    </div>
                  ))}
                </div>
                {r.explanation && <div className="sct-expl"><strong>💡 </strong>{r.explanation}</div>}
              </div>
            ))}
            <div className="sct-results-actions">
              <button onClick={handleNewTest} className="sct-res-btn secondary">Volver al banco</button>
            </div>
          </div>
        </div>
        {toast && (
          <div className={`v2-toast ${toast.type}`}>
            <span className="v2-toast-msg">{toast.message}</span>
            <button className="v2-toast-close" onClick={() => setToast(null)}>✕</button>
          </div>
        )}
      </>
    );
  }

  /* ── CONFIG / BIBLIOTECA VIEW ── */
  return (
    <>
      <AppSidebar user={user} role={role} activeRoute="mcq" onRoleChange={handleRoleChange} onLogout={handleLogout} />
      <div className="page-scroll" data-testid="mcq-page">
        <div className="sct3-top-header">
          <div className="sct3-top-left">
            <div className="sct3-breadcrumb-pill">
              <span className="sct3-pill-dot" />
              Test de alternativas
            </div>
            <h1 className="sct3-page-title">
              Preguntas de <em>alternativas.</em>
            </h1>
            <p className="sct3-page-subtitle">
              Preguntas de opción múltiple clásicas: pregunta, alternativas y respuesta correcta. Créalas a
              mano o importa un documento y la IA las extrae por ti. El orden de preguntas y alternativas se
              baraja cada vez que un estudiante rinde el test.
            </p>
          </div>
        </div>

        <div className="sct3-body">
          {canManage && (
            <>
              <div className="sct3-section-head">
                <span className="sct3-section-num">/ 01 — Crear test</span>
              </div>
              <div className="sct3-section-title-row">
                <h2 className="sct3-section-title">Banco de preguntas</h2>
              </div>

              {!showBuilder ? (
                <button type="button" className="cse-add-btn" onClick={() => setShowBuilder(true)}>
                  + Crear nuevo test de alternativas
                </button>
              ) : (
                <MCQManualBuilder
                  onCancel={() => setShowBuilder(false)}
                  onSaved={async (saved) => {
                    showToast(`"${saved.name}" guardado correctamente`, "success");
                    setShowBuilder(false);
                    await loadSavedTests();
                  }}
                />
              )}
            </>
          )}

          <div className="sct3-section-head" style={{ marginTop: 48 }}>
            <span className="sct3-section-num">/ 02 — Biblioteca</span>
          </div>
          <div className="sct3-section-title-row">
            <h2 className="sct3-section-title">Tests disponibles</h2>
            {savedTests.length > 0 && (
              <span className="sct3-section-meta">{savedTests.length} test{savedTests.length !== 1 ? "s" : ""}</span>
            )}
          </div>

          {savedTests.length === 0 ? (
            <div className="sct3-library-empty">
              <span className="sct3-library-empty-icon">📄</span>
              <div className="sct3-library-empty-title">No hay tests disponibles</div>
              <div className="sct3-library-empty-desc">
                {canManage
                  ? "Crea tu primer test de alternativas manualmente o importando un archivo."
                  : "Los tests publicados por tu docente aparecerán aquí"}
              </div>
            </div>
          ) : (
            <div className="sct3-library-grid">
              {savedTests.map((test) => {
                const status = test.status || "published";
                const statusLabel = { draft: "BORRADOR", published: "PUBLICADO", archived: "ARCHIVADO" }[status] || status.toUpperCase();
                const statusCls = { draft: "draft", published: "result", archived: "archived" }[status] || "draft";
                const isUpdating = updatingStatusId === test.id;
                return (
                  <div key={test.id} className={`sct3-library-card${status === "archived" ? " sct3-card-archived" : ""}`} data-testid={`mcq-library-card-${test.id}`}>
                    <div className="sct3-library-card-top">
                      <div className="sct3-library-card-title">{test.name}</div>
                      <span className={`sct3-lib-badge ${statusCls}`}>{statusLabel}</span>
                    </div>
                    <div className="sct3-library-tags">
                      {test.topic && <span className="sct3-lib-tag">{test.topic}</span>}
                      {test.difficulty && <span className="sct3-lib-tag">{test.difficulty}</span>}
                      {test.num_items && <span className="sct3-lib-tag">{test.num_items} preguntas</span>}
                    </div>
                    <div className="sct3-library-date">{formatDate(test.created_at)}</div>
                    <div className="sct3-library-card-footer">
                      {status !== "archived" && (
                        <button className="sct3-open-btn" onClick={() => handleLoadTest(test.id)} data-testid={`mcq-open-${test.id}`}>
                          Abrir →
                        </button>
                      )}
                      {canManage && (
                        <div className="sct3-status-btns">
                          {status !== "published" && (
                            <button className="sct3-status-btn publish" disabled={isUpdating} onClick={() => handleUpdateTestStatus(test.id, "published")}>
                              Publicar
                            </button>
                          )}
                          {status !== "draft" && (
                            <button className="sct3-status-btn draft" disabled={isUpdating} onClick={() => handleUpdateTestStatus(test.id, "draft")}>
                              Borrador
                            </button>
                          )}
                          {status !== "archived" && (
                            <button className="sct3-status-btn archive" disabled={isUpdating} onClick={() => handleUpdateTestStatus(test.id, "archived")}>
                              Archivar
                            </button>
                          )}
                          <button className="sct3-status-btn archive" onClick={() => handleDeleteTest(test.id)}>
                            Eliminar
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="sct3-section-head" style={{ marginTop: 48 }}>
            <span className="sct3-section-num">/ 03 — Historial</span>
          </div>
          <div className="sct3-section-title-row">
            <h2 className="sct3-section-title">Mis intentos</h2>
            {myDbAttempts.length > 0 && (
              <span className="sct3-section-meta">{myDbAttempts.length} intento{myDbAttempts.length !== 1 ? "s" : ""}</span>
            )}
          </div>
          {myDbAttempts.length === 0 ? (
            <div className="sct3-library-empty">
              <span className="sct3-library-empty-icon">📊</span>
              <div className="sct3-library-empty-title">Sin intentos registrados</div>
              <div className="sct3-library-empty-desc">Completa un test publicado para ver tu historial aquí</div>
            </div>
          ) : (
            <div className="sct3-attempts-table" data-testid="mcq-attempts-table">
              <div className="sct3-attempts-head">
                <span>Test</span>
                <span>Tema</span>
                <span>Correctas</span>
                <span>Puntuación</span>
                <span>Fecha</span>
              </div>
              {myDbAttempts.map((a) => (
                <div key={a.id} className="sct3-attempts-row">
                  <span className="sct3-att-name">{a.test_name || `Test #${a.test_id}`}</span>
                  <span>{a.test_topic || "—"}</span>
                  <span>{a.correct_count}/{a.total_items}</span>
                  <span className={`sct3-att-score ${scorePercent(a.score) >= 70 ? "good" : scorePercent(a.score) >= 50 ? "avg" : "low"}`}>
                    {scorePercent(a.score)}%
                  </span>
                  <span>{formatDate(a.completed_at)}</span>
                </div>
              ))}
            </div>
          )}

          {canManage && (
            <>
              <div className="sct3-section-head" style={{ marginTop: 48 }}>
                <span className="sct3-section-num">/ 04 — Revisión</span>
              </div>
              <div className="sct3-section-title-row">
                <h2 className="sct3-section-title">Intentos de estudiantes</h2>
                {allAttempts.length > 0 && (
                  <span className="sct3-section-meta">{allAttempts.length} intento{allAttempts.length !== 1 ? "s" : ""}</span>
                )}
              </div>
              {allAttempts.length === 0 ? (
                <div className="sct3-library-empty" style={{ marginBottom: 48 }}>
                  <span className="sct3-library-empty-icon">📋</span>
                  <div className="sct3-library-empty-title">Sin intentos aún</div>
                  <div className="sct3-library-empty-desc">Los intentos de estudiantes aparecerán aquí una vez que completen tests publicados</div>
                </div>
              ) : (
                <div className="sct3-attempts-table" style={{ marginBottom: 48 }}>
                  <div className="sct3-attempts-head sct3-attempts-head-admin">
                    <span>Estudiante</span>
                    <span>Test</span>
                    <span>Tema</span>
                    <span>Correctas</span>
                    <span>Puntuación</span>
                    <span>Fecha</span>
                  </div>
                  {allAttempts.map((a) => (
                    <div key={a.id} className="sct3-attempts-row">
                      <span className="sct3-att-name">{a.user_name || a.user_email || `#${a.user_id}`}</span>
                      <span>{a.test_name || `Test #${a.test_id}`}</span>
                      <span>{a.test_topic || "—"}</span>
                      <span>{a.correct_count}/{a.total_items}</span>
                      <span className={`sct3-att-score ${scorePercent(a.score) >= 70 ? "good" : scorePercent(a.score) >= 50 ? "avg" : "low"}`}>
                        {scorePercent(a.score)}%
                      </span>
                      <span>{formatDate(a.completed_at)}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {toast && (
        <div className={`v2-toast ${toast.type}`}>
          <span className="v2-toast-msg">{toast.message}</span>
          <button className="v2-toast-close" onClick={() => setToast(null)}>✕</button>
        </div>
      )}
    </>
  );
}
