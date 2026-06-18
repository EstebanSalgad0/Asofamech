import React, { useState, useEffect, useMemo, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { generateSCT, saveSCTTest, listSCTTests, getSCTTest, submitSCTAttempt, listMyAttempts, listAllAttempts, updateSCTTest } from "../api";
import { startSession, flushSession, trackTestCompleted, pushActivity } from "../tracker";
import { AppSidebar } from "../components/AppSidebar";
import { clearAuthSession, getStoredRole, userStorageKey, canManageEducationalContent } from "../authClient";
import { formatDisplayTitle } from "../displayText";

/* ── Persistent SCT result log (one entry per completed test) ── */
const SCT_RESULTS_KEY = "asofamech_sct_result_log";

const AREA_COLORS = {
  "Cardiología":     "#C41E3A",
  "Nefrología":      "#ff6b5c",
  "Endocrinología":  "#f59e0b",
  "Infectología":    "#5b6cf6",
  "Neurología":      "#a78bfa",
  "Gastroenterología":"#D4A017",
  "Hematología":     "#f472b6",
  "Oncología":       "#dc2626",
  "Neumología":      "#60a5fa",
};

function loadResultLog() {
  try {
    const raw = localStorage.getItem(userStorageKey(SCT_RESULTS_KEY));
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function appendResult(entry) {
  const log = loadResultLog();
  log.unshift(entry); // newest first
  if (log.length > 100) log.length = 100;
  localStorage.setItem(userStorageKey(SCT_RESULTS_KEY), JSON.stringify(log));
}

/** Extract primary area name from the effectiveFocus string. */
function primaryAreaFromFocus(focus = "") {
  const f = focus.toLowerCase();
  return MEDICAL_AREAS.find((a) => f.includes(a.toLowerCase())) || null;
}

const MEDICAL_AREAS = [
  "Cardiología", "Nefrología", "Endocrinología", "Infectología",
  "Neurología", "Gastroenterología", "Hematología", "Oncología", "Neumología",
];

const DIFFICULTY_OPTIONS = [
  { value: "Pregrado", label: "Pregrado", sub: "Casos típicos" },
  { value: "Internado", label: "Internado", sub: "Casos complejos" },
  { value: "Residente", label: "Residente", sub: "Diagnóstico diferencial" },
];

const ITEM_COUNTS = [3, 5, 10, 15];

const SCALE_OPTS = [
  { v: -2, label: "desc.", cls: "s-neg2" },
  { v: -1, label: "débil", cls: "s-neg1" },
  { v:  0, label: "sin",   cls: "s-zero" },
  { v:  1, label: "fuerte",cls: "s-pos1" },
  { v:  2, label: "conf.", cls: "s-pos2" },
];

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" });
}

function scorePercent(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return 0;
  return Math.round(value <= 1 ? value * 100 : value);
}

function attemptAreaLabel(attempt) {
  const raw = attempt?.test_focus ? attempt.test_focus.split(",")[0].trim() : "";
  return raw ? formatDisplayTitle(raw) : "Sin área";
}

// Progress chart: Y axis is score percentage, X axis is recent SCT attempts.
function Sparkline({ points = [], color = "#C41E3A" }) {
  const chartRef = useRef(null);
  const [chartWidth, setChartWidth] = useState(360);

  useEffect(() => {
    const node = chartRef.current;
    if (!node) return undefined;

    const updateWidth = () => {
      setChartWidth(Math.max(180, Math.round(node.clientWidth)));
    };
    updateWidth();

    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(updateWidth);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const w = chartWidth, h = 76, padX = 5, padY = 6;
  if (points.length < 2) return null;
  const safePoints = points.map((v) => Math.max(0, Math.min(100, Number(v) || 0)));
  const xs = points.map((_, i) => padX + (i / (points.length - 1)) * (w - padX * 2));
  const yFor = (value) => h - padY - (value / 100) * (h - padY * 2);
  const ys = safePoints.map(yFor);
  const chartPoints = xs.map((x, i) => ({ x, y: ys[i] }));
  const clampY = (value) => Math.max(padY, Math.min(h - padY, value));
  const curvePath = chartPoints.slice(0, -1).reduce((result, point, i) => {
    const previous = chartPoints[i - 1] || point;
    const next = chartPoints[i + 1];
    const following = chartPoints[i + 2] || next;
    const control1 = {
      x: point.x + (next.x - previous.x) / 6,
      y: clampY(point.y + (next.y - previous.y) / 6),
    };
    const control2 = {
      x: next.x - (following.x - point.x) / 6,
      y: clampY(next.y - (following.y - point.y) / 6),
    };
    return `${result} C${control1.x},${control1.y} ${control2.x},${control2.y} ${next.x},${next.y}`;
  }, `M${chartPoints[0].x},${chartPoints[0].y}`);
  const area = `${curvePath} L${chartPoints.at(-1).x},${h} L${chartPoints[0].x},${h} Z`;
  const ticks = [100, 50, 0];
  return (
    <div className="sct-sparkline-chart" role="img" aria-label="Tendencia SCT: eje Y puntaje porcentual y eje X tests recientes">
      <div className="sct-sparkline-y-title" aria-hidden="true">Puntaje</div>
      <div className="sct-sparkline-y" aria-hidden="true">
        {ticks.map((tick) => <span key={tick}>{tick}%</span>)}
      </div>
      <div className="sct-sparkline-main" ref={chartRef}>
        <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="sct-sparkline" aria-hidden="true">
          <defs>
            <linearGradient id="sp-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.3" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          {ticks.map((tick) => (
            <line key={tick} className="sct-sparkline-grid" x1="0" x2={w} y1={yFor(tick)} y2={yFor(tick)} />
          ))}
          <line className="sct-sparkline-axis" x1="0" x2="0" y1={padY} y2={h - padY} />
          <line className="sct-sparkline-axis" x1="0" x2={w} y1={h - padY} y2={h - padY} />
          <path d={area} fill="url(#sp-fill)" />
          <path d={curvePath} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          {chartPoints.map((point, index) => (
            <circle
              key={`${point.x}-${point.y}`}
              className={index === chartPoints.length - 1 ? "sct-sparkline-point latest" : "sct-sparkline-point"}
              cx={point.x}
              cy={point.y}
              r={index === chartPoints.length - 1 ? 3.5 : 3}
            />
          ))}
        </svg>
        <div className="sct-sparkline-x" aria-hidden="true">
          <span>Antiguo</span>
          <b>Tests recientes</b>
          <span>Reciente</span>
        </div>
      </div>
    </div>
  );
}

export function SCTPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedTestId = Number.parseInt(searchParams.get("test") || "", 10);
  const openedRequestedTestRef = useRef(null);
  const savedRef = useRef(null);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [savedTests, setSavedTests] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [genProgress, setGenProgress] = useState(0);
  const [currentTest, setCurrentTest] = useState(null);
  const [viewMode, setViewMode] = useState("config");
  const [answers, setAnswers] = useState({});
  const [testResults, setTestResults] = useState(null);
  const [toast, setToast] = useState(null);
  const [saveNameInput, setSaveNameInput] = useState("");
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [canManage, setCanManage] = useState(false);
  const [myDbAttempts, setMyDbAttempts] = useState([]);
  const [allAttempts, setAllAttempts] = useState([]);
  const [updatingStatusId, setUpdatingStatusId] = useState(null);

  // Config state
  const [configStep, setConfigStep] = useState(1);
  const [numItems, setNumItems] = useState(5);
  const [difficulty, setDifficulty] = useState("Pregrado");
  const [selectedAreas, setSelectedAreas] = useState([]);
  const [specificFocus, setSpecificFocus] = useState("");

  const [resultLog, setResultLog] = useState([]);
  const [testStartedAt, setTestStartedAt] = useState(null);

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
    const manage = canManageEducationalContent(storedRole);
    setCanManage(manage);
    startSession();
    setResultLog(loadResultLog());
    loadSavedTests();
    loadMyAttempts();
    if (manage) loadAllAttempts();
    const handleUnload = () => flushSession();
    window.addEventListener("beforeunload", handleUnload);
    return () => {
      flushSession();
      window.removeEventListener("beforeunload", handleUnload);
    };
  }, [navigate]);

  const loadSavedTests = async () => {
    try {
      const tests = await listSCTTests();
      setSavedTests(tests || []);
    } catch {
      setSavedTests([]);
    }
  };

  const loadMyAttempts = async () => {
    try {
      const data = await listMyAttempts();
      setMyDbAttempts(data || []);
    } catch {
      setMyDbAttempts([]);
    }
  };

  const loadAllAttempts = async () => {
    try {
      const data = await listAllAttempts();
      setAllAttempts(data || []);
    } catch {
      setAllAttempts([]);
    }
  };

  const handleUpdateTestStatus = async (testId, status) => {
    setUpdatingStatusId(testId);
    try {
      await updateSCTTest(testId, { status });
      await loadSavedTests();
      showToast(`Estado actualizado a "${status}"`, "success");
    } catch {
      showToast("Error al actualizar el estado del test", "error");
    } finally {
      setUpdatingStatusId(null);
    }
  };

  /* ── Real computed stats ── */

  // Global average from all completed tests
  const globalAverage = useMemo(() => {
    if (resultLog.length === 0) return null;
    return Math.round(resultLog.reduce((s, r) => s + r.score, 0) / resultLog.length);
  }, [resultLog]);

  // Per-area average scores
  const areaStats = useMemo(() => {
    const map = {};
    resultLog.forEach((r) => {
      if (!r.area) return;
      if (!map[r.area]) map[r.area] = [];
      map[r.area].push(r.score);
    });
    return Object.entries(map)
      .map(([area, scores]) => ({
        area,
        key: area.slice(0, 5).toUpperCase(),
        pct: Math.round(scores.reduce((a, b) => a + b, 0) / scores.length),
        color: AREA_COLORS[area] || "#9ca3af",
        count: scores.length,
      }))
      .sort((a, b) => a.area.localeCompare(b.area));
  }, [resultLog]);

  // Area with lowest average (only if we have per-area data)
  const weakArea = useMemo(() => {
    if (areaStats.length === 0) return null;
    return areaStats.reduce((a, b) => (a.pct < b.pct ? a : b));
  }, [areaStats]);

  // Sparkline: last 7 test scores, oldest→newest
  const sparkPoints = useMemo(() => {
    if (resultLog.length === 0) return [];
    return [...resultLog].reverse().slice(-7).map((r) => r.score);
  }, [resultLog]);

  // Personal history for ranking card (best scores per area, or last 4 tests)
  const historyRows = useMemo(() => {
    if (resultLog.length === 0) return [];
    return resultLog.slice(0, 4).map((r) => ({
      label: r.area || r.focus?.split(",")[0]?.trim() || "General",
      score: r.score,
      date: r.date,
    }));
  }, [resultLog]);

  // Preview data
  const previewTopic =
    selectedAreas.length > 0
      ? selectedAreas[0].toLowerCase()
      : specificFocus.split(" ")[0].toLowerCase() || "general";
  const previewDuration = `~${numItems * 2} min`;

  // Toggle area
  const toggleArea = (area) => {
    setSelectedAreas((prev) =>
      prev.includes(area) ? prev.filter((a) => a !== area) : [...prev, area]
    );
  };

  // Effective focus for API
  const effectiveFocus = useMemo(() => {
    const parts = [];
    if (selectedAreas.length > 0) parts.push(selectedAreas.join(", "));
    if (specificFocus.trim()) parts.push(specificFocus.trim());
    return parts.join(" — ") || "medicina general";
  }, [selectedAreas, specificFocus]);

  const handleGenerateTest = async () => {
    setIsGenerating(true);
    setGenProgress(0);
    try {
      const interval = setInterval(() => {
        setGenProgress((p) => {
          if (p >= 90) { clearInterval(interval); return 90; }
          return p + 15;
        });
      }, 700);
      const response = await generateSCT(parseInt(numItems), difficulty.toLowerCase(), effectiveFocus);
      clearInterval(interval);
      setGenProgress(100);
      setTimeout(() => {
        setIsGenerating(false);
        setGenProgress(0);
        if (response?.items?.length > 0) {
          const formatted = {
            id: Date.now(),
            db_id: null,
            title: `Test SCT · ${previewTopic}`,
            items: response.items.map((item, i) => ({
              id: i + 1,
              scenario: item.vignette || item.scenario || item.caso_clinico || "",
              hypothesis: item.hypothesis || item.hipotesis || "",
              newInfo: item.new_info || item.nueva_informacion || "",
              question: item.question || item.pregunta || "Si usted estaba pensando en esta hipótesis y encuentra esta nueva información, esta hipótesis se vuelve:",
              correctAnswer: item.correct_answer || 0,
              explanation: item.explanation || item.explicacion || "",
            })),
            difficulty,
            focus: effectiveFocus,
            date: new Date().toLocaleDateString("es-ES"),
          };
          setCurrentTest(formatted);
          setViewMode("test");
          setAnswers({});
          setTestStartedAt(new Date().toISOString());
        } else {
          showToast("No se generaron casos. Revisa el enfoque e intenta nuevamente.", "error");
        }
      }, 400);
    } catch (err) {
      setIsGenerating(false);
      setGenProgress(0);
      const is503 = String(err).includes("503") || String(err?.message).includes("503");
      showToast(
        is503
          ? "El servicio de IA no está disponible (503). Verifica que Ollama esté ejecutándose."
          : "Error al generar el test. Verifica la conexión con el backend.",
        "error"
      );
    }
  };

  const handleDemoTest = () => {
    setNumItems(5);
    setDifficulty("Pregrado");
    setSelectedAreas(["Cardiología"]);
    setSpecificFocus("");
    setConfigStep(3);
  };

  const handleAnswer = (itemId, value) => {
    setAnswers((prev) => ({ ...prev, [itemId]: value }));
  };

  const handleSubmitTest = () => {
    const answered = Object.keys(answers).length;
    const total = currentTest.items.length;
    if (answered < total) {
      showToast(`Faltan ${total - answered} respuestas. Completa todas antes de enviar.`, "warning");
      return;
    }
    let correct = 0;
    const results = currentTest.items.map((item) => {
      const ua = answers[item.id];
      const ok = ua === (item.correctAnswer || 0);
      if (ok) correct++;
      return { itemId: item.id, userAnswer: ua, correctAnswer: item.correctAnswer || 0, isCorrect: ok, ...item };
    });
    const score = Math.round((correct / total) * 100);
    setTestResults({ score, correctCount: correct, totalItems: total, results });
    setViewMode("results");
    trackTestCompleted(score >= 60);
    pushActivity("sct", `${currentTest.title} — ${score}%`);
    // Persist result for real stats
    const area = primaryAreaFromFocus(currentTest.focus);
    const entry = {
      score,
      area,
      focus: currentTest.focus,
      difficulty: currentTest.difficulty,
      items: total,
      date: new Date().toISOString(),
    };
    appendResult(entry);
    setResultLog(loadResultLog());

    // Enviar intento al backend (fire-and-forget, no bloquea la UI)
    const backendAnswers = currentTest.items.map((item) => ({
      item_id: item.id,
      selected_answer: answers[item.id],
    }));
    const submittedTestId = currentTest.id;
    (async () => {
      try {
        let dbId = currentTest.db_id;
        if (!dbId && canManage) {
          setCurrentTest((prev) => (prev?.id === submittedTestId ? { ...prev, isSavingToLibrary: true } : prev));
          // Solo docente/admin puede crear tests: auto-guardar para obtener db_id
          const saved = await saveSCTTest(
            currentTest.title,
            currentTest.difficulty.toLowerCase(),
            currentTest.focus,
            currentTest.items.length,
            currentTest.items.map((item) => ({
              id: item.id,
              vignette: item.scenario,
              hypothesis: item.hypothesis,
              new_info: item.newInfo,
              scale_options: ["−2", "−1", "0", "+1", "+2"],
              correct_answer: item.correctAnswer,
              explanation: item.explanation,
            }))
          );
          dbId = saved?.id;
          if (dbId) {
            setCurrentTest((prev) => (
              prev?.id === submittedTestId
                ? {
                    ...prev,
                    id: dbId,
                    db_id: dbId,
                    title: saved?.name || prev.title,
                    date: formatDate(saved?.created_at) || prev.date,
                    isSavingToLibrary: false,
                  }
                : prev
            ));
            loadSavedTests();
          } else {
            setCurrentTest((prev) => (prev?.id === submittedTestId ? { ...prev, isSavingToLibrary: false } : prev));
          }
        }
        if (dbId) {
          await submitSCTAttempt(dbId, backendAnswers, testStartedAt);
          loadMyAttempts();
        }
      } catch {
        setCurrentTest((prev) => (prev?.id === submittedTestId ? { ...prev, isSavingToLibrary: false } : prev));
        // fallo silencioso — el resultado local ya fue guardado
      }
    })();
  };

  const handleSaveTest = async (nameOverride) => {
    if (!currentTest) return;
    if (currentTest.db_id) {
      setShowSaveModal(false);
      showToast("Este test ya está guardado.", "info");
      return;
    }
    const testName = nameOverride || `Test SCT - ${currentTest.focus}`;
    const savingTestId = currentTest.id;
    try {
      const saved = await saveSCTTest(
        testName,
        currentTest.difficulty.toLowerCase(),
        currentTest.focus,
        currentTest.items.length,
        currentTest.items.map((item) => ({
          id: item.id,
          vignette: item.scenario,
          hypothesis: item.hypothesis,
          new_info: item.newInfo,
          scale_options: ["−2", "−1", "0", "+1", "+2"],
          correct_answer: item.correctAnswer,
          explanation: item.explanation,
        }))
      );
      if (saved?.id) {
        setCurrentTest((prev) => (
          prev?.id === savingTestId
            ? {
                ...prev,
                id: saved.id,
                db_id: saved.id,
                title: saved.name || prev.title,
                date: formatDate(saved.created_at) || prev.date,
              }
            : prev
        ));
      }
      await loadSavedTests();
      showToast(`"${testName}" guardado correctamente`, "success");
      setShowSaveModal(false);
    } catch {
      showToast("Error al guardar el test. Intenta nuevamente.", "error");
    }
  };

  const handleLoadTest = async (testId) => {
    try {
      const data = await getSCTTest(testId);
      if (data?.items?.length > 0) {
        setCurrentTest({
          id: data.id,
          db_id: data.id,
          title: data.name,
          items: data.items.map((item, i) => ({
            id: item.id || i + 1,
            scenario: item.vignette || "",
            hypothesis: item.hypothesis || "",
            newInfo: item.new_info || "",
            question: "Si usted estaba pensando en esta hipótesis y encuentra esta nueva información, esta hipótesis se vuelve:",
            correctAnswer: item.correct_answer || 0,
            explanation: item.explanation || "",
          })),
          difficulty: data.difficulty,
          focus: data.focus,
          date: formatDate(data.created_at),
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
  }, [requestedTestId, user]);

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
    setConfigStep(1);
  };

  const handleLogout = () => { flushSession(); clearAuthSession(); navigate("/"); };
  const handleRoleChange = () => setRole(getStoredRole());

  if (!user) return null;

  const answeredCount = Object.keys(answers).length;
  const totalItems = currentTest?.items?.length || 0;
  const progressPct = totalItems > 0 ? Math.round((answeredCount / totalItems) * 100) : 0;

  /* ── TEST VIEW ── */
  if (viewMode === "test" && currentTest) {
    return (
      <>
        <AppSidebar user={user} role={role} activeRoute="sct" onRoleChange={handleRoleChange} onLogout={handleLogout} />
        <div className="page-scroll" data-testid="sct-test-page">
          <div className="sct-test-topbar">
            <button onClick={handleBackToConfig} className="sct-back-btn">← Volver</button>
            <div className="sct-test-info">
              <span className="sct-test-name">{currentTest.title}</span>
              <span className="sct-test-chip">{currentTest.difficulty}</span>
            </div>
            <div className="sct-progress-info">
              <span className="sct-progress-text">{answeredCount} / {totalItems}</span>
              <div className="sct-progress-track">
                <div className="sct-progress-fill" style={{ width: `${progressPct}%` }} />
              </div>
            </div>
          </div>

          <div className="sct-test-body">
            <div className="sct-instructions">
              <div className="sct-instr-title">Instrucciones</div>
              <div className="sct-instr-text">
                Para cada escenario clínico, evalúa cómo la nueva información afecta la hipótesis diagnóstica.
              </div>
              <div className="sct-scale-legend">
                {SCALE_OPTS.map((s) => (
                  <div key={s.v} className="sct-legend-item">
                    <strong>{s.v > 0 ? `+${s.v}` : s.v}</strong>{" "}
                    {s.v === -2 && "Descarta"}{s.v === -1 && "Disminuye"}
                    {s.v ===  0 && "No afecta"}{s.v ===  1 && "Aumenta"}
                    {s.v ===  2 && "Confirma"}
                  </div>
                ))}
              </div>
            </div>

            {currentTest.items.map((item, idx) => (
              <div key={item.id} className="sct-item-card" data-testid={`sct-item-${item.id}`}>
                <div className="sct-item-num">Caso {idx + 1}</div>
                <div className="sct-item-section">
                  <div className="sct-item-section-lbl scenario">Escenario Clínico</div>
                  <div className="sct-item-section-txt">{item.scenario}</div>
                </div>
                <div className="sct-item-section">
                  <div className="sct-item-section-lbl hypothesis">Hipótesis Diagnóstica</div>
                  <div className="sct-item-section-txt hyp">{item.hypothesis}</div>
                </div>
                <div className="sct-item-section">
                  <div className="sct-item-section-lbl newinfo">Nueva Información</div>
                  <div className="sct-item-section-txt new">{item.newInfo}</div>
                </div>
                <div className="sct-answer-section">
                  <div className="sct-answer-label">{item.question}</div>
                  <div className="sct-answer-row">
                    {SCALE_OPTS.map((s) => (
                      <label key={s.v} className={`sct-answer-opt ${answers[item.id] === s.v ? "selected" : ""} ${s.cls}`} data-testid={`sct-answer-${item.id}-${s.v}`}>
                        <input type="radio" name={`item-${item.id}`} value={s.v} checked={answers[item.id] === s.v} onChange={() => handleAnswer(item.id, s.v)} aria-label={`Caso ${idx + 1} respuesta ${s.v}`} />
                        <div className="sct-answer-face">
                          <div className="sct-ans-val">{s.v > 0 ? `+${s.v}` : s.v}</div>
                          <div className="sct-ans-lbl">{s.label}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            ))}

            <div className="sct-submit-section">
              <button onClick={handleSubmitTest} className="sct-submit-btn" data-testid="sct-submit">
                ✓ Enviar para Evaluación
              </button>
              <div className="sct-submit-note">Asegúrate de responder todas las preguntas antes de enviar</div>
            </div>
          </div>
        </div>

        {toast && (
          <div className={`v2-toast ${toast.type}`}>
            <span className="v2-toast-icon">{toast.type === "success" ? "✓" : toast.type === "error" ? "✕" : "ℹ"}</span>
            <span className="v2-toast-msg">{toast.message}</span>
            <button className="v2-toast-close" onClick={() => setToast(null)}>✕</button>
          </div>
        )}
      </>
    );
  }

  /* ── RESULTS VIEW ── */
  if (viewMode === "results" && testResults) {
    const canSaveCurrentTest = canManage && currentTest && !currentTest.db_id && !currentTest.isSavingToLibrary;

    return (
      <>
        <AppSidebar user={user} role={role} activeRoute="sct" onRoleChange={handleRoleChange} onLogout={handleLogout} />
        <div className="page-scroll" data-testid="sct-results-page">
          <div className="sct-results-hero" data-testid="sct-results">
            <div className="sct-score-ring">
              <svg width="140" height="140" viewBox="0 0 140 140">
                <circle cx="70" cy="70" r="58" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="9"/>
                <circle cx="70" cy="70" r="58" fill="none"
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
              <div style={{ marginTop: 12 }}>
                {testResults.score >= 80 && <span className="sct-perf-badge excellent">🌟 Excelente</span>}
                {testResults.score >= 60 && testResults.score < 80 && <span className="sct-perf-badge good">👍 Bien</span>}
                {testResults.score >= 40 && testResults.score < 60 && <span className="sct-perf-badge avg">📚 Regular</span>}
                {testResults.score < 40 && <span className="sct-perf-badge poor">💪 Sigue practicando</span>}
              </div>
            </div>
          </div>

          <div className="sct-results-body">
            <div className="sct-feedback-title">Retroalimentación Detallada</div>
            {testResults.results.map((r, i) => (
              <div key={r.itemId} className={`sct-feedback-card ${r.isCorrect ? "correct" : "incorrect"}`} data-testid={`sct-feedback-card-${r.itemId}`}>
                <div className="sct-feedback-top">
                  <span className="sct-feedback-num">Caso {i + 1}</span>
                  <span className={`sct-feedback-status ${r.isCorrect ? "correct" : "incorrect"}`}>
                    {r.isCorrect ? "✓ Correcto" : "✗ Incorrecto"}
                  </span>
                </div>
                <div className="sct-feedback-field"><strong>Escenario: </strong>{r.scenario}</div>
                <div className="sct-feedback-field"><strong>Hipótesis: </strong>{r.hypothesis}</div>
                <div className="sct-feedback-field"><strong>Nueva info: </strong>{r.newInfo}</div>
                <div className="sct-answers-row">
                  <div className="sct-ans-pill">
                    <div className="sct-ans-pill-lbl">Tu respuesta</div>
                    <div className="sct-ans-pill-val">{r.userAnswer > 0 ? `+${r.userAnswer}` : r.userAnswer}</div>
                  </div>
                  <div className="sct-ans-pill expected">
                    <div className="sct-ans-pill-lbl">Esperada</div>
                    <div className="sct-ans-pill-val">{r.correctAnswer > 0 ? `+${r.correctAnswer}` : r.correctAnswer}</div>
                  </div>
                </div>
                {r.explanation && <div className="sct-expl"><strong>💡 </strong>{r.explanation}</div>}
              </div>
            ))}
            <div className="sct-results-actions">
              {canSaveCurrentTest && (
                <button onClick={() => { setSaveNameInput(`Test SCT - ${currentTest?.focus || "general"}`); setShowSaveModal(true); }} className="sct-res-btn primary">Guardar Test</button>
              )}
              <button onClick={handleNewTest} className="sct-res-btn secondary">Nuevo Test</button>
            </div>
          </div>
        </div>

        {toast && (
          <div className={`v2-toast ${toast.type}`}>
            <span className="v2-toast-icon">{toast.type === "success" ? "✓" : toast.type === "error" ? "✕" : "ℹ"}</span>
            <span className="v2-toast-msg">{toast.message}</span>
            <button className="v2-toast-close" onClick={() => setToast(null)}>✕</button>
          </div>
        )}

        {showSaveModal && (
          <div className="sct-modal-overlay" onClick={() => setShowSaveModal(false)}>
            <div className="sct-modal" onClick={(e) => e.stopPropagation()}>
              <div className="sct-modal-title">Guardar test</div>
              <input
                className="sct3-text-input"
                value={saveNameInput}
                onChange={(e) => setSaveNameInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSaveTest(saveNameInput)}
                autoFocus
              />
              <div className="sct-modal-actions">
                <button className="sct-modal-cancel" onClick={() => setShowSaveModal(false)}>Cancelar</button>
                <button className="sct-modal-confirm" onClick={() => handleSaveTest(saveNameInput)}>Guardar</button>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  /* ── CONFIG VIEW ── */
  const totalSavedItems = savedTests.reduce((s, t) => s + (t.num_items || 0), 0);

  return (
    <>
      <AppSidebar user={user} role={role} activeRoute="sct" onRoleChange={handleRoleChange} onLogout={handleLogout} />

      <div className="page-scroll" data-testid="sct-page">
        {/* ── Top header ── */}
        <div className="sct3-top-header">
          <div className="sct3-top-left">
            <div className="sct3-breadcrumb-pill">
              <span className="sct3-pill-dot" />
              Test SCT · Razonamiento clínico
            </div>
            <h1 className="sct3-page-title">
              Concordancia de <em>Scripts.</em>
            </h1>
            <p className="sct3-page-subtitle">
              El SCT mide cómo ajustas tus hipótesis diagnósticas ante nueva información. Genera tests con IA,
              compite con tu cohorte, recibe explicación detallada.
            </p>
          </div>
          <div className="sct3-top-actions">
            <button className="sct3-my-tests-btn" onClick={() => savedRef.current?.scrollIntoView({ behavior: "smooth" })}>
              <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M4 4h12v12H4V4Zm3 4h6M7 12h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              {canManage ? "Mis tests" : "Ver tests"}
            </button>
            {canManage && (
              <button className="sct3-demo-btn" onClick={handleDemoTest}>
                <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path d="M10 2l2.4 4.8 5.3.8-3.8 3.7.9 5.2L10 14l-4.8 2.5.9-5.2L2.3 7.6l5.3-.8L10 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                </svg>
                Empezar test demo
              </button>
            )}
          </div>
        </div>

        <div className="sct3-body">
          {/* ── 01 — Stats row ── */}
          <div className="sct3-stats-row">
            {/* Progress card */}
            <div className="sct3-progress-card">
              <div className="sct3-card-topbar">
                <span className="sct3-card-tag">✦ Tu progreso</span>
                <span className="sct3-card-meta">{resultLog.length} test{resultLog.length !== 1 ? "s" : ""} completados</span>
              </div>
              <div className="sct3-progress-label">Promedio global</div>
              {globalAverage === null ? (
                <div className="sct3-progress-empty">
                  <div className="sct3-progress-empty-num">—</div>
                  <div className="sct3-progress-empty-hint">Completa tu primer test para ver tu progreso</div>
                </div>
              ) : (
                <>
                  <div className="sct3-progress-big">
                    {globalAverage}<span className="sct3-pct-sign">%</span>
                  </div>
                  {sparkPoints.length >= 2 && <Sparkline points={sparkPoints} color="#C41E3A" />}
                  {resultLog.length >= 2 && (
                    <div className="sct3-vs-prev">
                      {(() => {
                        const prev = resultLog[1]?.score ?? globalAverage;
                        const diff = resultLog[0].score - prev;
                        return (
                          <span className={`sct3-vs-badge ${diff < 0 ? "neg" : ""}`}>
                            {diff >= 0 ? "+" : ""}{diff}% vs test anterior
                          </span>
                        );
                      })()}
                    </div>
                  )}
                  {areaStats.length > 0 && (
                    <div className="sct3-area-bars">
                      {areaStats.slice(0, 4).map((a) => (
                        <div key={a.area} className="sct3-area-bar-item">
                          <div className="sct3-area-bar-label">{a.key}</div>
                          <div className="sct3-area-bar-pct" style={{ color: a.color }}>{a.pct}%</div>
                          <div className="sct3-area-bar-track">
                            <div className="sct3-area-bar-fill" style={{ width: `${a.pct}%`, background: a.color }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* History card (replaces fake ranking) */}
            <div className="sct3-ranking-card">
              <div className="sct3-card-topbar">
                <span className="sct3-ranking-title">Tu historial</span>
                <span className="sct3-card-meta">últimos tests</span>
              </div>
              {historyRows.length === 0 ? (
                <div className="sct3-ranking-empty">
                  Completa tu primer test para ver tu historial de resultados aquí.
                </div>
              ) : (
                <div className="sct3-ranking-list">
                  {historyRows.map((row, i) => (
                    <div key={i} className="sct3-ranking-row me">
                      <span className="sct3-rank-num">#{i + 1}</span>
                      <span className="sct3-rank-name">{row.label}</span>
                      <span className="sct3-rank-score">{row.score}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Weak area card */}
            <div className="sct3-weak-card">
              <div className="sct3-weak-tag">Área Débil</div>
              {weakArea === null ? (
                <>
                  <div className="sct3-weak-title">Descubre tu <em>área débil</em></div>
                  <p className="sct3-weak-desc">
                    Completa tests en distintas áreas clínicas para identificar dónde reforzar tu razonamiento.
                  </p>
                </>
              ) : (
                <>
                  <div className="sct3-weak-title">
                    Refuerza <em>{weakArea.area}</em>
                  </div>
                  <p className="sct3-weak-desc">
                    Tu promedio en esta área es {weakArea.pct}%
                    {globalAverage !== null && weakArea.pct < globalAverage
                      ? `, ${globalAverage - weakArea.pct}% bajo tu media global`
                      : ""}.
                    Generamos un test de 5 ítems enfocado.
                  </p>
                  <button
                    className="sct3-weak-btn"
                    onClick={() => {
                      setSelectedAreas([weakArea.area]);
                      setNumItems(5);
                      setConfigStep(3);
                      window.scrollTo({ top: 400, behavior: "smooth" });
                    }}
                  >
                    Generar caso →
                  </button>
                </>
              )}
            </div>
          </div>

          {/* ── 02 — Config (solo docente/admin) ── */}
          {canManage && <>
          <div className="sct3-section-head">
            <span className="sct3-section-num">/ 02 — Generador IA</span>
          </div>
          <div className="sct3-section-title-row">
            <h2 className="sct3-section-title">Configura tu próximo test</h2>
            <span className="sct3-section-meta">3 pasos · ~30 segundos</span>
          </div>

          <div className="sct3-config-grid">
            {/* Left: Step wizard */}
            <div className="sct3-wizard">
              {/* Step tabs */}
              <div className="sct3-steps">
                {[
                  { n: 1, label: "Alcance" },
                  { n: 2, label: "Foco médico" },
                  { n: 3, label: "Revisar y generar" },
                ].map((s) => (
                  <button
                    key={s.n}
                    className={`sct3-step-tab ${configStep === s.n ? "active" : configStep > s.n ? "done" : ""}`}
                    onClick={() => setConfigStep(s.n)}
                  >
                    <span className="sct3-step-num">{configStep > s.n ? "✓" : s.n}</span>
                    <span className="sct3-step-sub">Paso {s.n}</span>
                    <span className="sct3-step-name">{s.label}</span>
                  </button>
                ))}
              </div>

              {/* Step 1: Alcance */}
              {configStep === 1 && (
                <div className="sct3-step-content">
                  <div className="sct3-field">
                    <label className="sct3-field-label">Número de ítems</label>
                    <div className="sct3-count-btns">
                      {ITEM_COUNTS.map((n) => (
                        <button
                          key={n}
                          className={`sct3-count-btn ${numItems === n ? "active" : ""}`}
                          onClick={() => setNumItems(n)}
                        >
                          {n}
                        </button>
                      ))}
                    </div>
                    <div className="sct3-field-hint">
                      Recomendado <strong>5</strong> para sesión corta, <strong>10</strong> para examen.
                    </div>
                  </div>

                  <div className="sct3-field">
                    <label className="sct3-field-label">Dificultad</label>
                    <div className="sct3-diff-btns">
                      {DIFFICULTY_OPTIONS.map((d) => (
                        <button
                          key={d.value}
                          className={`sct3-diff-btn ${difficulty === d.value ? "active" : ""}`}
                          onClick={() => setDifficulty(d.value)}
                        >
                          <div className="sct3-diff-name">{d.label}</div>
                          <div className="sct3-diff-sub">{d.sub}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="sct3-step-footer">
                    <button className="sct3-next-btn" onClick={() => setConfigStep(2)}>
                      Siguiente → Foco médico
                    </button>
                  </div>
                </div>
              )}

              {/* Step 2: Foco médico */}
              {configStep === 2 && (
                <div className="sct3-step-content">
                  <div className="sct3-field">
                    <label className="sct3-field-label">Áreas clínicas</label>
                    <div className="sct3-areas-grid">
                      {MEDICAL_AREAS.map((area) => (
                        <button
                          key={area}
                          className={`sct3-area-btn ${selectedAreas.includes(area) ? "active" : ""}`}
                          onClick={() => toggleArea(area)}
                        >
                          {selectedAreas.includes(area) && "✓ "}{area}
                        </button>
                      ))}
                    </div>
                    <div className="sct3-field-hint">
                      Marca las áreas que deben aparecer. Combínalas o usa solo una.
                    </div>
                  </div>

                  <div className="sct3-field">
                    <label className="sct3-field-label">
                      Enfoque específico <span className="sct3-optional">(Opcional)</span>
                    </label>
                    <input
                      type="text"
                      className="sct3-text-input"
                      placeholder="Ej. VIH/SIDA, diabetes mellitus, insuficiencia cardíaca..."
                      value={specificFocus}
                      onChange={(e) => setSpecificFocus(e.target.value)}
                    />
                    <div className="sct3-field-hint">
                      Restringe el tema. Ej: 'sepsis en geriátricos', 'tuberculosis ósea'.
                    </div>
                  </div>

                  <div className="sct3-step-footer">
                    <button className="sct3-back-step-btn" onClick={() => setConfigStep(1)}>← Atrás</button>
                    <button className="sct3-next-btn" onClick={() => setConfigStep(3)}>
                      Siguiente → Revisar
                    </button>
                  </div>
                </div>
              )}

              {/* Step 3: Revisar y generar */}
              {configStep === 3 && (
                <div className="sct3-step-content">
                  <div className="sct3-review-grid">
                    <div className="sct3-review-item">
                      <div className="sct3-review-label">Número de ítems</div>
                      <div className="sct3-review-val">{numItems}</div>
                    </div>
                    <div className="sct3-review-item">
                      <div className="sct3-review-label">Dificultad</div>
                      <div className="sct3-review-val">{difficulty}</div>
                    </div>
                    <div className="sct3-review-item">
                      <div className="sct3-review-label">Duración estimada</div>
                      <div className="sct3-review-val">{previewDuration}</div>
                    </div>
                    <div className="sct3-review-item">
                      <div className="sct3-review-label">Escala</div>
                      <div className="sct3-review-val">-2 a +2</div>
                    </div>
                  </div>

                  {selectedAreas.length > 0 && (
                    <div className="sct3-review-areas">
                      <div className="sct3-review-label">Áreas seleccionadas</div>
                      <div className="sct3-review-chips">
                        {selectedAreas.map((a) => (
                          <span key={a} className="sct3-review-chip">{a}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {specificFocus && (
                    <div className="sct3-review-focus">
                      <div className="sct3-review-label">Enfoque</div>
                      <div className="sct3-review-val">{specificFocus}</div>
                    </div>
                  )}

                  <div className="sct3-step-footer sct3-step-footer-generate">
                    <button className="sct3-back-step-btn" onClick={() => setConfigStep(2)}>← Atrás</button>
                    <button className="sct3-generate-btn" onClick={handleGenerateTest} disabled={isGenerating}>
                      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                        <path d="M10 2l2.4 4.8 5.3.8-3.8 3.7.9 5.2L10 14l-4.8 2.5.9-5.2L2.3 7.6l5.3-.8L10 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                      </svg>
                      Generar test con IA
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Right: Preview panel (summary only, no action button) */}
            <div className="sct3-preview-panel">
              <div className="sct3-preview-header">
                <span className="sct3-preview-label">Vista previa</span>
                <span className="sct3-preview-ai-badge">✦ IA</span>
              </div>
              <div className="sct3-preview-provisional">Configuración actual</div>
              <div className="sct3-preview-title">
                Test SCT · <em>{previewTopic}</em>
              </div>
              <div className="sct3-preview-mix">
                {selectedAreas.length > 1 ? "Mix áreas" : selectedAreas.length === 1 ? selectedAreas[0] : "Mix general"}
              </div>

              <div className="sct3-preview-stats">
                <div className="sct3-preview-stat">
                  <div className="sct3-preview-stat-label">Ítems</div>
                  <div className="sct3-preview-stat-val">{numItems}</div>
                </div>
                <div className="sct3-preview-stat">
                  <div className="sct3-preview-stat-label">Dificultad</div>
                  <div className="sct3-preview-stat-val">{difficulty}</div>
                </div>
                <div className="sct3-preview-stat">
                  <div className="sct3-preview-stat-label">Duración</div>
                  <div className="sct3-preview-stat-val">{previewDuration}</div>
                </div>
                <div className="sct3-preview-stat">
                  <div className="sct3-preview-stat-label">Escala</div>
                  <div className="sct3-preview-stat-val">-2 a +2</div>
                </div>
              </div>

              <div className="sct3-scale-section">
                <div className="sct3-scale-label">Escala de respuesta</div>
                <div className="sct3-scale-row">
                  {SCALE_OPTS.map((s) => (
                    <div key={s.v} className={`sct3-scale-opt ${s.cls}`}>
                      <div className="sct3-scale-val">{s.v > 0 ? `+${s.v}` : s.v}</div>
                      <div className="sct3-scale-lbl">{s.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              {configStep < 3 && (
                <div className="sct3-preview-hint">
                  Completa los pasos y genera tu test en el paso 3.
                </div>
              )}
            </div>
          </div>

          </>}

          {/* ── 03 — Saved tests ── */}
          <div ref={savedRef} className="sct3-section-head" style={{ marginTop: 48 }}>
            <span className="sct3-section-num">/ 03 — Biblioteca</span>
          </div>
          <div className="sct3-section-title-row">
            <h2 className="sct3-section-title">Mis tests guardados</h2>
            {savedTests.length > 0 && (
              <span className="sct3-section-meta">
                {savedTests.length} test{savedTests.length !== 1 ? "s" : ""} · {totalSavedItems} ítems totales
              </span>
            )}
          </div>

          {savedTests.length === 0 ? (
            <div className="sct3-library-empty">
              <span className="sct3-library-empty-icon">📄</span>
              <div className="sct3-library-empty-title">No hay tests disponibles</div>
              <div className="sct3-library-empty-desc">
                {canManage
                  ? "Genera tu primer test SCT con el generador IA y guárdalo para publicarlo"
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
                  <div key={test.id} className={`sct3-library-card${status === "archived" ? " sct3-card-archived" : ""}`} data-testid={`sct-library-card-${test.id}`}>
                    <div className="sct3-library-card-top">
                      <div className="sct3-library-card-title">
                        Test SCT · <em>{(test.focus || test.name || "").split(" ")[0].toLowerCase()}</em>
                      </div>
                      <span className={`sct3-lib-badge ${statusCls}`}>{statusLabel}</span>
                    </div>
                    <div className="sct3-library-tags">
                      {test.difficulty && <span className="sct3-lib-tag">{test.difficulty}</span>}
                      {test.focus && <span className="sct3-lib-tag">{test.focus.split(",")[0].trim().toLowerCase().slice(0, 12)}</span>}
                      {test.num_items && <span className="sct3-lib-tag">{test.num_items} ítems</span>}
                    </div>
                    <div className="sct3-library-date">{formatDate(test.created_at)}</div>
                    <div className="sct3-library-card-footer">
                      {status !== "archived" && (
                        <button className="sct3-open-btn" onClick={() => handleLoadTest(test.id)} data-testid={`sct-open-${test.id}`}>
                          Abrir →
                        </button>
                      )}
                      {canManage && (
                        <div className="sct3-status-btns">
                          {status !== "published" && (
                            <button
                              className="sct3-status-btn publish"
                              disabled={isUpdating}
                              onClick={() => handleUpdateTestStatus(test.id, "published")}
                            >
                              Publicar
                            </button>
                          )}
                          {status !== "draft" && (
                            <button
                              className="sct3-status-btn draft"
                              disabled={isUpdating}
                              onClick={() => handleUpdateTestStatus(test.id, "draft")}
                            >
                              Borrador
                            </button>
                          )}
                          {status !== "archived" && (
                            <button
                              className="sct3-status-btn archive"
                              disabled={isUpdating}
                              onClick={() => handleUpdateTestStatus(test.id, "archived")}
                            >
                              Archivar
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {/* ── 04 — Mis intentos (BD) ── */}
          <div className="sct3-section-head" style={{ marginTop: 48 }}>
            <span className="sct3-section-num">/ 04 — Historial</span>
          </div>
          <div className="sct3-section-title-row">
            <h2 className="sct3-section-title">Mis intentos</h2>
            {myDbAttempts.length > 0 && (
              <span className="sct3-section-meta">{myDbAttempts.length} intento{myDbAttempts.length !== 1 ? "s" : ""}</span>
            )}
          </div>
          <p className="sct3-section-desc">
            Registro de tus resoluciones SCT guardadas en la base de datos: test realizado, área evaluada, respuestas correctas, puntuación y fecha.
          </p>
          {myDbAttempts.length === 0 ? (
            <div className="sct3-library-empty">
              <span className="sct3-library-empty-icon">📊</span>
              <div className="sct3-library-empty-title">Sin intentos registrados</div>
              <div className="sct3-library-empty-desc">Completa un test publicado para ver tu historial aquí</div>
            </div>
          ) : (
            <div className="sct3-attempts-table" data-testid="sct-attempts-table">
              <div className="sct3-attempts-head">
                <span>Test</span>
                <span>Área</span>
                <span>Dificultad</span>
                <span>Correctas</span>
                <span>Puntuación</span>
                <span>Fecha</span>
              </div>
              {myDbAttempts.map((a) => (
                <div key={a.id} className="sct3-attempts-row">
                  <span className="sct3-att-name">{a.test_name || `Test #${a.test_id}`}</span>
                  <span>{attemptAreaLabel(a)}</span>
                  <span>{a.test_difficulty || "—"}</span>
                  <span>{a.correct_count}/{a.total_items}</span>
                  <span className={`sct3-att-score ${scorePercent(a.score) >= 70 ? "good" : scorePercent(a.score) >= 50 ? "avg" : "low"}`}>
                    {scorePercent(a.score)}%
                  </span>
                  <span>{formatDate(a.completed_at)}</span>
                </div>
              ))}
            </div>
          )}

          {/* ── 05 — Revisión docente ── */}
          {canManage && (
            <>
              <div className="sct3-section-head" style={{ marginTop: 48 }}>
                <span className="sct3-section-num">/ 05 — Revisión</span>
              </div>
              <div className="sct3-section-title-row">
                <h2 className="sct3-section-title">Intentos de estudiantes</h2>
                {allAttempts.length > 0 && (
                  <span className="sct3-section-meta">{allAttempts.length} intento{allAttempts.length !== 1 ? "s" : ""}</span>
                )}
              </div>
              <p className="sct3-section-desc">
                Vista docente basada en los intentos guardados por estudiantes. Sirve para ver participación y desempeño por test/área, no para diagnosticar al estudiante.
              </p>
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
                    <span>Área</span>
                    <span>Correctas</span>
                    <span>Puntuación</span>
                    <span>Fecha</span>
                  </div>
                  {allAttempts.map((a) => (
                    <div key={a.id} className="sct3-attempts-row">
                      <span className="sct3-att-name">{a.user_name || a.user_email || `#${a.user_id}`}</span>
                      <span>{a.test_name || `Test #${a.test_id}`}</span>
                      <span>{attemptAreaLabel(a)}</span>
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

      {/* Loading overlay */}
      {isGenerating && (
        <div className="v2-loading-overlay">
          <div className="v2-loading-modal">
            <div className="v2-loading-spinner" />
            <div className="v2-loading-title">Generando test con IA…</div>
            <div className="v2-loading-sub">Creando {numItems} ítems · {difficulty}</div>
            <div className="v2-progress-track">
              <div className="v2-progress-fill" style={{ width: `${genProgress}%` }} />
            </div>
            <div className="v2-loading-steps">
              {[
                { label: "Analizando enfoque médico", threshold: 25 },
                { label: "Generando escenarios clínicos", threshold: 50 },
                { label: "Creando hipótesis diagnósticas", threshold: 75 },
                { label: "Finalizando test", threshold: 100 },
              ].map((step, i) => (
                <div key={i} className={`v2-loading-step ${genProgress >= step.threshold ? "done" : ""}`}>
                  <div className="v2-loading-step-icon">{genProgress >= step.threshold ? "✓" : "○"}</div>
                  <span>{step.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div className={`v2-toast ${toast.type}`}>
          <span className="v2-toast-icon">
            {toast.type === "success" ? "✓" : toast.type === "error" ? "✕" : "ℹ"}
          </span>
          <span className="v2-toast-msg">{toast.message}</span>
          <button className="v2-toast-close" onClick={() => setToast(null)}>✕</button>
        </div>
      )}

      {/* Save modal */}
      {showSaveModal && (
        <div className="sct-modal-overlay" onClick={() => setShowSaveModal(false)}>
          <div className="sct-modal" onClick={(e) => e.stopPropagation()}>
            <div className="sct-modal-title">Guardar test</div>
            <input
              className="sct3-text-input"
              value={saveNameInput}
              onChange={(e) => setSaveNameInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSaveTest(saveNameInput)}
              autoFocus
            />
            <div className="sct-modal-actions">
              <button className="sct-modal-cancel" onClick={() => setShowSaveModal(false)}>Cancelar</button>
              <button className="sct-modal-confirm" onClick={() => handleSaveTest(saveNameInput)}>Guardar</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
