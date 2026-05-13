import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { generateSCT, saveSCTTest, listSCTTests, getSCTTest } from "../api";
import { startSession, flushSession, trackTestCompleted, pushActivity } from "../tracker";
import { AppSidebar } from "../components/AppSidebar";
import { clearAuthSession } from "../authClient";

export function SCTPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [numItems, setNumItems] = useState(5);
  const [difficulty, setDifficulty] = useState("Pregrado");
  const [medicalFocus, setMedicalFocus] = useState("");
  const [savedTests, setSavedTests] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTest, setCurrentTest] = useState(null);
  const [viewMode, setViewMode] = useState('config');
  const [answers, setAnswers] = useState({});
  const [testResults, setTestResults] = useState(null);

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
    loadSavedTests();
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
    } catch (error) {
      console.error("Error cargando tests guardados:", error);
      setSavedTests([]);
    }
  };

  const handleGenerateTest = async () => {
    if (!medicalFocus.trim()) {
      alert("Por favor ingresa un enfoque médico para generar el test");
      return;
    }
    setIsGenerating(true);
    setProgress(0);
    try {
      const progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) { clearInterval(progressInterval); return 90; }
          return prev + 15;
        });
      }, 800);
      const response = await generateSCT(parseInt(numItems), difficulty.toLowerCase(), medicalFocus);
      clearInterval(progressInterval);
      setProgress(100);
      setTimeout(() => {
        setIsGenerating(false);
        setProgress(0);
        if (response && response.items && response.items.length > 0) {
          const formattedTest = {
            id: Date.now(),
            title: `Test SCT - ${medicalFocus}`,
            items: response.items.map((item, index) => ({
              id: index + 1,
              scenario: item.vignette || item.scenario || item.caso_clinico || '',
              hypothesis: item.hypothesis || item.hipotesis || '',
              newInfo: item.new_info || item.nueva_informacion || '',
              question: item.question || item.pregunta || "Si usted estaba pensando en esta hipótesis y encuentra esta nueva información, esta hipótesis se vuelve:",
              correctAnswer: item.correct_answer || 0,
              explanation: item.explanation || item.explicacion || ''
            })),
            difficulty: difficulty,
            focus: medicalFocus,
            date: new Date().toLocaleDateString('es-ES')
          };
          setCurrentTest(formattedTest);
          setViewMode('test');
          setAnswers({});
        } else {
          alert("Error: No se pudieron generar los casos. Intenta nuevamente.");
        }
      }, 500);
    } catch (error) {
      console.error("Error generando test:", error);
      setIsGenerating(false);
      setProgress(0);
      alert("Error al generar el test. Por favor verifica que el backend esté funcionando.");
    }
  };

  const handleAnswer = (itemId, value) => {
    setAnswers(prev => ({ ...prev, [itemId]: value }));
  };

  const handleSubmitTest = () => {
    const answeredCount = Object.keys(answers).length;
    const totalItems = currentTest.items.length;
    if (answeredCount < totalItems) {
      alert(`Has respondido ${answeredCount} de ${totalItems} preguntas. Por favor completa todas.`);
      return;
    }
    let correctCount = 0;
    const results = currentTest.items.map(item => {
      const userAnswer = answers[item.id];
      const isCorrect = Math.abs(userAnswer - (item.correctAnswer || 0)) <= 1;
      if (isCorrect) correctCount++;
      return { itemId: item.id, userAnswer, correctAnswer: item.correctAnswer || 0, isCorrect, scenario: item.scenario, hypothesis: item.hypothesis, newInfo: item.newInfo, explanation: item.explanation };
    });
    const score = Math.round((correctCount / totalItems) * 100);
    setTestResults({ score, correctCount, totalItems, results });
    setViewMode('results');
    const passed = score >= 60;
    trackTestCompleted(passed);
    pushActivity("sct", `${currentTest.title} — ${score}%`);
  };

  const handleBackToConfig = () => {
    if (window.confirm('¿Estás seguro? Se perderá el progreso actual del test.')) {
      setViewMode('config'); setCurrentTest(null); setAnswers({}); setTestResults(null);
    }
  };

  const handleNewTest = () => {
    setViewMode('config'); setCurrentTest(null); setAnswers({}); setTestResults(null);
  };

  const handleSaveTest = async () => {
    if (!currentTest) { alert("No hay test para guardar"); return; }
    const testName = prompt("Ingresa un nombre para este test:", `Test SCT - ${currentTest.focus}`);
    if (!testName) return;
    try {
      const itemsToSave = currentTest.items.map(item => ({
        id: item.id, vignette: item.scenario, hypothesis: item.hypothesis,
        new_info: item.newInfo,
        scale_options: ["−2: Descarta completamente", "−1: Menos probable", "0: Sin cambio", "+1: Más probable", "+2: Apoya fuertemente"],
        correct_answer: item.correctAnswer, explanation: item.explanation
      }));
      await saveSCTTest(testName, currentTest.difficulty.toLowerCase(), currentTest.focus, currentTest.items.length, itemsToSave);
      alert("Test guardado exitosamente");
      await loadSavedTests();
    } catch (error) {
      console.error("Error guardando test:", error);
      alert("Error al guardar el test. Por favor intenta nuevamente.");
    }
  };

  const handleLoadTest = async (testId) => {
    try {
      const testData = await getSCTTest(testId);
      if (testData && testData.items && testData.items.length > 0) {
        const formattedTest = {
          id: testData.id, title: testData.name,
          items: testData.items.map((item, index) => ({
            id: item.id || index + 1,
            scenario: item.vignette || "", hypothesis: item.hypothesis || "",
            newInfo: item.new_info || "",
            question: "Si usted estaba pensando en esta hipótesis y encuentra esta nueva información, esta hipótesis se vuelve:",
            correctAnswer: item.correct_answer || 0, explanation: item.explanation || ""
          })),
          difficulty: testData.difficulty, focus: testData.focus,
          date: new Date(testData.created_at).toLocaleDateString('es-ES')
        };
        setCurrentTest(formattedTest); setViewMode('test'); setAnswers({});
      } else {
        alert("Error: No se pudo cargar el test.");
      }
    } catch (error) {
      console.error("Error cargando test:", error);
      alert("Error al cargar el test.");
    }
  };

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

  const answeredCount = Object.keys(answers).length;
  const totalItems = currentTest?.items?.length || 0;
  const progressPct = totalItems > 0 ? Math.round((answeredCount / totalItems) * 100) : 0;

  return (
    <>
      <AppSidebar
        user={user}
        role={role}
        activeRoute="sct"
        onRoleChange={handleRoleChange}
        onLogout={handleLogout}
      />

      <div className="page-scroll">
        {viewMode === 'config' && (
          <>
            {/* Hero */}
            <div className="sct-v2-hero">
              <div className="sct-v2-hero-tag">Test SCT</div>
              <h1 className="sct-v2-hero-title">
                Concordancia de{" "}
                <span className="serif-it">Scripts</span>
              </h1>
              <p className="sct-v2-hero-sub">
                Evalúa tu razonamiento clínico resolviendo casos médicos. El SCT mide cómo ajustas tus hipótesis diagnósticas ante nueva información.
              </p>
            </div>

            <div className="sct-v2-body">
              {/* Config grid */}
              <div className="sct-v2-grid">
                <div className="sct-v2-config-card">
                  <div className="sct-v2-config-title">Configurar Test</div>

                  <div className="sct-v2-field">
                    <label className="sct-v2-label">Número de ítems</label>
                    <input
                      type="number"
                      className="sct-v2-input"
                      value={numItems}
                      onChange={(e) => setNumItems(e.target.value)}
                      min="1" max="20"
                    />
                  </div>

                  <div className="sct-v2-field">
                    <label className="sct-v2-label">Dificultad</label>
                    <select
                      className="sct-v2-select"
                      value={difficulty}
                      onChange={(e) => setDifficulty(e.target.value)}
                    >
                      <option value="Pregrado">Pregrado</option>
                      <option value="Internado">Internado</option>
                      <option value="Residente">Residente</option>
                    </select>
                  </div>

                  <div className="sct-v2-field">
                    <label className="sct-v2-label">Enfoque médico</label>
                    <input
                      type="text"
                      className="sct-v2-input"
                      placeholder="Ej: VIH/SIDA, diabetes mellitus, insuficiencia cardíaca…"
                      value={medicalFocus}
                      onChange={(e) => setMedicalFocus(e.target.value)}
                    />
                  </div>

                  <button className="sct-v2-generate-btn" onClick={handleGenerateTest}>
                    ✨ Generar Test con IA
                  </button>
                </div>

                <div className="sct-v2-info-card">
                  <div className="sct-v2-info-title">¿Qué es el SCT?</div>
                  <div className="sct-v2-info-text">
                    El Script Concordance Test evalúa cómo los estudiantes modifican sus hipótesis clínicas cuando reciben nueva información, simulando el razonamiento de expertos. Cada ítem presenta un escenario clínico, una hipótesis y nueva información.
                  </div>
                  <div>
                    <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.35)', fontFamily: 'JetBrains Mono', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                      Escala de respuesta
                    </div>
                    <div className="sct-v2-scale-demo">
                      {[-2, -1, 0, 1, 2].map(v => (
                        <div key={v} className={`sct-v2-scale-opt ${v === 1 ? "sel" : ""}`}>
                          {v > 0 ? `+${v}` : v}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Saved tests */}
              <div className="sct-v2-saved-section">
                <div className="sct-v2-saved-head">
                  <div className="sct-v2-saved-title">Mis Tests Guardados</div>
                  {savedTests.length > 0 && (
                    <span style={{ fontSize: '11px', color: 'var(--muted)', fontFamily: 'JetBrains Mono' }}>
                      {savedTests.length} test{savedTests.length !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>

                {savedTests.length === 0 ? (
                  <div className="sct-v2-empty">
                    <span className="sct-v2-empty-icon">📄</span>
                    <div className="sct-v2-empty-title">No tienes tests guardados</div>
                    <div className="sct-v2-empty-desc">Genera tu primer test SCT y guárdalo para revisar más tarde</div>
                  </div>
                ) : (
                  <div className="sct-v2-saved-grid">
                    {savedTests.map(test => (
                      <div key={test.id} className="sct-v2-saved-card">
                        <div className="sct-v2-saved-name">{test.name}</div>
                        <div className="sct-v2-saved-tags">
                          <span className="sct-v2-saved-tag">{test.num_items} ítems</span>
                          <span className="sct-v2-saved-tag">{test.difficulty}</span>
                          <span className="sct-v2-saved-tag">{new Date(test.created_at).toLocaleDateString('es-ES')}</span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '14px', lineHeight: '1.4' }}>
                          {test.focus}
                        </div>
                        <button className="sct-v2-open-btn" onClick={() => handleLoadTest(test.id)}>
                          Abrir Test →
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {viewMode === 'test' && currentTest && (
          <>
            {/* Sticky top bar */}
            <div className="sct-v2-test-topbar">
              <button onClick={handleBackToConfig} className="sct-v2-back-btn">
                ← Volver
              </button>
              <div className="sct-v2-progress-info">
                <span className="sct-v2-progress-text">{answeredCount} / {totalItems}</span>
                <div className="sct-v2-progress-track">
                  <div className="sct-v2-progress-fill" style={{ width: `${progressPct}%` }} />
                </div>
              </div>
            </div>

            <div className="sct-v2-test-body">
              {/* Meta */}
              <div className="sct-v2-test-meta">
                <span className="sct-v2-meta-chip">{currentTest.title}</span>
                <span className="sct-v2-meta-chip">{currentTest.difficulty}</span>
                <span className="sct-v2-meta-chip">{currentTest.date}</span>
                <span className="sct-v2-meta-chip">{totalItems} ítems</span>
              </div>

              {/* Instructions */}
              <div className="sct-v2-instructions">
                <div className="sct-v2-instr-title">Instrucciones</div>
                <div className="sct-v2-instr-text">
                  Para cada escenario clínico, evalúa cómo la nueva información afecta la hipótesis diagnóstica. Selecciona una opción en la escala:
                </div>
                <div className="sct-v2-scale-legend">
                  {[{v:"-2",l:"Descarta"},{v:"-1",l:"Disminuye"},{v:"0",l:"No afecta"},{v:"+1",l:"Aumenta"},{v:"+2",l:"Confirma"}].map(s => (
                    <div key={s.v} className="sct-v2-legend-item">
                      <strong>{s.v}</strong>{s.l}
                    </div>
                  ))}
                </div>
              </div>

              {/* Items */}
              {currentTest.items.map((item, index) => (
                <div key={item.id} className="sct-v2-item">
                  <div className="sct-v2-item-num">Caso {index + 1}</div>

                  <div className="sct-v2-section">
                    <div className="sct-v2-section-label lbl-scenario">Escenario Clínico</div>
                    <div className="sct-v2-section-text">{item.scenario}</div>
                  </div>

                  <div className="sct-v2-section">
                    <div className="sct-v2-section-label lbl-hypothesis">Hipótesis Diagnóstica</div>
                    <div className="sct-v2-section-text txt-hypothesis">{item.hypothesis}</div>
                  </div>

                  <div className="sct-v2-section">
                    <div className="sct-v2-section-label lbl-newinfo">Nueva Información</div>
                    <div className="sct-v2-section-text txt-newinfo">{item.newInfo}</div>
                  </div>

                  <div className="sct-v2-answer-section">
                    <div className="sct-v2-answer-label">{item.question}</div>
                    <div className="sct-v2-answer-row">
                      {[-2, -1, 0, 1, 2].map(value => (
                        <label key={value} className="sct-v2-answer-opt">
                          <input
                            type="radio"
                            name={`item-${item.id}`}
                            value={value}
                            checked={answers[item.id] === value}
                            onChange={() => handleAnswer(item.id, value)}
                          />
                          <div className="sct-v2-answer-face">
                            <div className="sct-v2-ans-val">{value > 0 ? `+${value}` : value}</div>
                            <div className="sct-v2-ans-lbl">
                              {value === -2 && 'Descarta'}
                              {value === -1 && 'Disminuye'}
                              {value === 0 && 'No afecta'}
                              {value === 1 && 'Aumenta'}
                              {value === 2 && 'Confirma'}
                            </div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              ))}

              <div className="sct-v2-submit-section">
                <button onClick={handleSubmitTest} className="sct-v2-submit-btn">
                  ✓ Enviar para Evaluación
                </button>
                <div className="sct-v2-submit-note">
                  Asegúrate de responder todas las preguntas antes de enviar
                </div>
              </div>
            </div>
          </>
        )}

        {viewMode === 'results' && testResults && (
          <>
            {/* Results hero */}
            <div className="sct-v2-results-hero">
              <div className="sct-v2-score-ring">
                <svg width="160" height="160" viewBox="0 0 160 160">
                  <circle cx="80" cy="80" r="68" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10"/>
                  <circle
                    cx="80" cy="80" r="68" fill="none"
                    stroke={testResults.score >= 70 ? "var(--accent)" : testResults.score >= 50 ? "var(--indigo)" : "var(--coral)"}
                    strokeWidth="10"
                    strokeDasharray={`${(testResults.score / 100) * 427} 427`}
                    transform="rotate(-90 80 80)"
                    strokeLinecap="round"
                  />
                </svg>
                <div className="sct-v2-score-center">
                  <div className="sct-v2-score-num">{testResults.score}%</div>
                  <div className="sct-v2-score-lbl">Puntuación</div>
                </div>
              </div>

              <div className="sct-v2-results-info">
                <div className="sct-v2-results-title">¡Test Completado!</div>
                <div className="sct-v2-results-summary">
                  {testResults.correctCount} de {testResults.totalItems} respuestas correctas
                </div>
                <div>
                  {testResults.score >= 80 && <span className="sct-v2-perf-badge excellent">🌟 Excelente</span>}
                  {testResults.score >= 60 && testResults.score < 80 && <span className="sct-v2-perf-badge good">👍 Bien</span>}
                  {testResults.score >= 40 && testResults.score < 60 && <span className="sct-v2-perf-badge average">📚 Regular</span>}
                  {testResults.score < 40 && <span className="sct-v2-perf-badge poor">💪 Sigue practicando</span>}
                </div>
              </div>
            </div>

            <div className="sct-v2-results-body">
              <div className="sct-v2-feedback-title">Retroalimentación Detallada</div>

              {testResults.results.map((result, index) => (
                <div key={result.itemId} className={`sct-v2-feedback-card ${result.isCorrect ? "correct" : "incorrect"}`}>
                  <div className="sct-v2-feedback-top">
                    <span className="sct-v2-feedback-num">Caso {index + 1}</span>
                    <span className={`sct-v2-feedback-status ${result.isCorrect ? "correct" : "incorrect"}`}>
                      {result.isCorrect ? "✓ Correcto" : "✗ Incorrecto"}
                    </span>
                  </div>

                  <div className="sct-v2-feedback-field">
                    <strong>Escenario</strong>{result.scenario}
                  </div>
                  <div className="sct-v2-feedback-field">
                    <strong>Hipótesis</strong>{result.hypothesis}
                  </div>
                  <div className="sct-v2-feedback-field">
                    <strong>Nueva información</strong>{result.newInfo}
                  </div>

                  <div className="sct-v2-answers-row">
                    <div className="sct-v2-ans-pill">
                      <div className="sct-v2-ans-pill-label">Tu respuesta</div>
                      <div className="sct-v2-ans-pill-val">
                        {result.userAnswer > 0 ? `+${result.userAnswer}` : result.userAnswer}
                      </div>
                    </div>
                    <div className="sct-v2-ans-pill">
                      <div className="sct-v2-ans-pill-label">Respuesta esperada</div>
                      <div className="sct-v2-ans-pill-val">
                        {result.correctAnswer > 0 ? `+${result.correctAnswer}` : result.correctAnswer}
                      </div>
                    </div>
                  </div>

                  {result.explanation && (
                    <div className="sct-v2-expl">
                      <strong>💡 </strong>{result.explanation}
                    </div>
                  )}
                </div>
              ))}

              <div className="sct-v2-results-actions">
                <button onClick={handleSaveTest} className="sct-v2-res-btn primary">
                  💾 Guardar Test
                </button>
                <button onClick={handleNewTest} className="sct-v2-res-btn secondary">
                  🔄 Nuevo Test
                </button>
                <button onClick={() => setViewMode('config')} className="sct-v2-res-btn secondary">
                  ← Configuración
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Loading Modal */}
      {isGenerating && (
        <div className="v2-loading-overlay">
          <div className="v2-loading-modal">
            <div className="v2-loading-spinner" />
            <div className="v2-loading-title">Generando test con IA…</div>
            <div className="v2-loading-sub">Creando {numItems} ítems de nivel {difficulty}</div>
            <div className="v2-progress-track">
              <div className="v2-progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <div className="v2-loading-steps">
              {[
                { label: "Analizando enfoque médico", threshold: 25 },
                { label: "Generando escenarios clínicos", threshold: 50 },
                { label: "Creando hipótesis diagnósticas", threshold: 75 },
                { label: "Finalizando test", threshold: 100 },
              ].map((step, i) => (
                <div key={i} className={`v2-loading-step ${progress >= step.threshold ? "done" : ""}`}>
                  <div className="v2-loading-step-icon">
                    {progress >= step.threshold ? "✓" : "○"}
                  </div>
                  <span>{step.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
