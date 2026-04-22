import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { generateSCT, saveSCTTest, listSCTTests, getSCTTest } from "../api";
import { startSession, flushSession, trackTestCompleted, pushActivity } from "../tracker";

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
  const [viewMode, setViewMode] = useState('config'); // 'config', 'test' o 'results'
  const [answers, setAnswers] = useState({});
  const [testResults, setTestResults] = useState(null);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    if (!userData) {
      navigate("/auth");
    } else {
      setUser(JSON.parse(userData));
      const savedRole = localStorage.getItem("role");
      if (savedRole) setRole(savedRole);
    }
    
    // Start session timer
    startSession();

    // Cargar tests guardados
    loadSavedTests();

    // Flush session time on unload
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
      // Simular progreso mientras se genera
      const progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 15;
        });
      }, 800);

      // Llamar a la API real para generar el test
      const response = await generateSCT(
        parseInt(numItems), 
        difficulty.toLowerCase(), 
        medicalFocus
      );

      clearInterval(progressInterval);
      setProgress(100);

      setTimeout(() => {
        setIsGenerating(false);
        setProgress(0);
        
        if (response && response.items && response.items.length > 0) {
          // Convertir el formato de la API al formato del componente
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
      alert("Error al generar el test. Por favor verifica que el backend esté funcionando y que el modelo de IA esté disponible.");
    }
  };

  const handleAnswer = (itemId, value) => {
    setAnswers(prev => ({
      ...prev,
      [itemId]: value
    }));
  };

  const handleSubmitTest = () => {
    const answeredCount = Object.keys(answers).length;
    const totalItems = currentTest.items.length;
    
    if (answeredCount < totalItems) {
      alert(`Has respondido ${answeredCount} de ${totalItems} preguntas. Por favor completa todas antes de enviar.`);
      return;
    }
    
    // Calcular resultados
    let correctCount = 0;
    const results = currentTest.items.map(item => {
      const userAnswer = answers[item.id];
      const isCorrect = Math.abs(userAnswer - (item.correctAnswer || 0)) <= 1; // Tolerancia de ±1
      if (isCorrect) correctCount++;
      
      return {
        itemId: item.id,
        userAnswer: userAnswer,
        correctAnswer: item.correctAnswer || 0,
        isCorrect: isCorrect,
        scenario: item.scenario,
        hypothesis: item.hypothesis,
        newInfo: item.newInfo,
        explanation: item.explanation
      };
    });

    const score = Math.round((correctCount / totalItems) * 100);
    
    setTestResults({
      score: score,
      correctCount: correctCount,
      totalItems: totalItems,
      results: results
    });
    
    setViewMode('results');

    // Track test completion + activity
    const passed = score >= 60;
    trackTestCompleted(passed);
    pushActivity("sct", `${currentTest.title} — ${score}%`);
  };

  const handleBackToConfig = () => {
    if (window.confirm('¿Estás seguro? Se perderá el progreso actual del test.')) {
      setViewMode('config');
      setCurrentTest(null);
      setAnswers({});
      setTestResults(null);
    }
  };

  const handleNewTest = () => {
    setViewMode('config');
    setCurrentTest(null);
    setAnswers({});
    setTestResults(null);
  };

  const handleSaveTest = async () => {
    if (!currentTest) {
      alert("No hay test para guardar");
      return;
    }

    const testName = prompt("Ingresa un nombre para este test:", `Test SCT - ${currentTest.focus}`);
    
    if (!testName) {
      return; // Usuario canceló
    }

    try {
      // Preparar los ítems en el formato que espera el backend
      const itemsToSave = currentTest.items.map(item => ({
        id: item.id,
        vignette: item.scenario,
        hypothesis: item.hypothesis,
        new_info: item.newInfo,
        scale_options: [
          "−2: Descarta completamente",
          "−1: Menos probable",
          "0: Sin cambio",
          "+1: Más probable",
          "+2: Apoya fuertemente"
        ],
        correct_answer: item.correctAnswer,
        explanation: item.explanation
      }));

      await saveSCTTest(
        testName,
        currentTest.difficulty.toLowerCase(),
        currentTest.focus,
        currentTest.items.length,
        itemsToSave
      );

      alert("Test guardado exitosamente");
      // Recargar la lista de tests guardados
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
        // Convertir el formato del backend al formato del componente
        const formattedTest = {
          id: testData.id,
          title: testData.name,
          items: testData.items.map((item, index) => ({
            id: item.id || index + 1,
            scenario: item.vignette || "",
            hypothesis: item.hypothesis || "",
            newInfo: item.new_info || "",
            question: "Si usted estaba pensando en esta hipótesis y encuentra esta nueva información, esta hipótesis se vuelve:",
            correctAnswer: item.correct_answer || 0,
            explanation: item.explanation || ""
          })),
          difficulty: testData.difficulty,
          focus: testData.focus,
          date: new Date(testData.created_at).toLocaleDateString('es-ES')
        };
        
        setCurrentTest(formattedTest);
        setViewMode('test');
        setAnswers({});
      } else {
        alert("Error: No se pudo cargar el test.");
      }
    } catch (error) {
      console.error("Error cargando test:", error);
      alert("Error al cargar el test. Por favor intenta nuevamente.");
    }
  };

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
            <span>Asistente IA</span>
          </Link>
          <Link to="/dashboard/sct" className="nav-item active">
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
      <main className="dashboard-main sct-page">
        {viewMode === 'config' ? (
          <>
            <div className="sct-header">
              <h1 className="sct-title">
                Test de Concordancia de <span className="gradient-text">Scripts (SCT)</span>
              </h1>
              <p className="sct-description">
                Evalúa tu razonamiento clínico resolviendo casos médicos de cualquier especialidad. 
                El SCT mide cómo ajustas tus hipótesis diagnósticas ante nueva información.
              </p>
            </div>

            {/* Configuration Card */}
            <div className="sct-config-card">
          <h2 className="sct-config-title">Configurar Test SCT</h2>
          
          <div className="sct-form">
            <div className="form-group">
              <label htmlFor="numItems" className="form-label">Número de ítems</label>
              <input
                type="number"
                id="numItems"
                className="form-input"
                value={numItems}
                onChange={(e) => setNumItems(e.target.value)}
                min="1"
                max="20"
              />
            </div>

            <div className="form-group">
              <label htmlFor="difficulty" className="form-label">Dificultad</label>
              <select
                id="difficulty"
                className="form-select"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
              >
                <option value="Pregrado">Pregrado</option>
                <option value="Internado">Internado</option>
                <option value="Residente">Residente</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="medicalFocus" className="form-label">Enfoque médico</label>
              <input
                type="text"
                id="medicalFocus"
                className="form-input"
                placeholder="Ej: VIH/SIDA, diabetes mellitus, insuficiencia cardíaca, etc."
                value={medicalFocus}
                onChange={(e) => setMedicalFocus(e.target.value)}
              />
            </div>

            <div className="sct-buttons">
              <button 
                className="btn-generate-test"
                onClick={handleGenerateTest}
              >
                <span>✨</span> Generar Test con IA
              </button>
            </div>
          </div>
        </div>

        {/* What is SCT Section */}
        <div className="sct-info-card">
          <div className="sct-info-icon">❓</div>
          <div className="sct-info-content">
            <h3 className="sct-info-title">¿Qué es el SCT?</h3>
            <p className="sct-info-text">
              El Script Concordance Test evalúa cómo los estudiantes modifican sus hipótesis 
              clínicas cuando reciben nueva información, simulando el razonamiento de expertos. 
              Cada ítem presenta un escenario clínico, una hipótesis y nueva información que 
              puede fortalecer o debilitar dicha hipótesis.
            </p>
          </div>
        </div>

        {/* Saved Tests Section */}
        <section className="sct-saved-section">
          <h2 className="section-title">Mis Tests Guardados</h2>
          
          {savedTests.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📄</div>
              <h3 className="empty-title">No tienes tests guardados</h3>
              <p className="empty-description">
                Genera tu primer test SCT y guárdalo para revisar más tarde
              </p>
            </div>
          ) : (
            <div className="saved-tests-grid">
              {savedTests.map(test => (
                <div key={test.id} className="saved-test-card">
                  <div className="saved-test-header">
                    <h4>{test.name}</h4>
                    <span className="saved-test-date">{new Date(test.created_at).toLocaleDateString('es-ES')}</span>
                  </div>
                  <div className="saved-test-info">
                    <span>{test.num_items} ítems</span>
                    <span>•</span>
                    <span>{test.difficulty}</span>
                    <span>•</span>
                    <span>{test.focus}</span>
                  </div>
                  <button 
                    className="btn-open-test"
                    onClick={() => handleLoadTest(test.id)}
                  >
                    📖 Abrir Test
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
          </>
        ) : viewMode === 'test' ? (
          // Test View
          <div className="test-container">
            <div className="test-header-bar">
              <button onClick={handleBackToConfig} className="btn-back">
                ← Volver a configuración
              </button>
              <div className="test-progress-info">
                <span>{Object.keys(answers).length} / {currentTest.items.length} respondidas</span>
              </div>
            </div>

            <div className="test-title-section">
              <h2 className="test-main-title">{currentTest.title}</h2>
              <div className="test-meta">
                <span className="test-badge">{currentTest.difficulty}</span>
                <span className="test-date">{currentTest.date}</span>
                <span className="test-items">{currentTest.items.length} ítems</span>
              </div>
            </div>

            <div className="test-instructions">
              <h3>📋 Instrucciones</h3>
              <p>Para cada escenario clínico, evalúa cómo la nueva información afecta la hipótesis diagnóstica presentada. Selecciona una opción en la escala de -2 a +2:</p>
              <ul>
                <li><strong>-2:</strong> Descarta casi completamente la hipótesis</li>
                <li><strong>-1:</strong> Disminuye la probabilidad de la hipótesis</li>
                <li><strong>0:</strong> No afecta la hipótesis (ni la fortalece ni la debilita)</li>
                <li><strong>+1:</strong> Aumenta la probabilidad de la hipótesis</li>
                <li><strong>+2:</strong> Confirma casi completamente la hipótesis</li>
              </ul>
            </div>

            {currentTest.items.map((item, index) => (
              <div key={item.id} className="sct-item-card">
                <div className="item-number">Caso {index + 1}</div>
                
                <div className="item-section">
                  <h4 className="item-section-title">🏥 Escenario Clínico</h4>
                  <p className="item-text">{item.scenario}</p>
                </div>

                <div className="item-section">
                  <h4 className="item-section-title">💭 Hipótesis Diagnóstica</h4>
                  <p className="item-text hypothesis">{item.hypothesis}</p>
                </div>

                <div className="item-section">
                  <h4 className="item-section-title">🔍 Nueva Información</h4>
                  <p className="item-text new-info">{item.newInfo}</p>
                </div>

                <div className="item-section">
                  <h4 className="item-section-title">❓ Pregunta</h4>
                  <p className="item-question">{item.question}</p>
                </div>

                <div className="item-answers">
                  <div className="answer-scale">
                    {[-2, -1, 0, 1, 2].map(value => (
                      <label 
                        key={value} 
                        className={`answer-option ${answers[item.id] === value ? 'selected' : ''}`}
                      >
                        <input
                          type="radio"
                          name={`item-${item.id}`}
                          value={value}
                          checked={answers[item.id] === value}
                          onChange={() => handleAnswer(item.id, value)}
                        />
                        <span className="answer-value">{value > 0 ? `+${value}` : value}</span>
                        <span className="answer-label">
                          {value === -2 && 'Descarta'}
                          {value === -1 && 'Disminuye'}
                          {value === 0 && 'No afecta'}
                          {value === 1 && 'Aumenta'}
                          {value === 2 && 'Confirma'}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            ))}

            <div className="test-submit-section">
              <button 
                onClick={handleSubmitTest} 
                className="btn-submit-test"
              >
                ✓ Enviar Test para Evaluación
              </button>
              <p className="submit-note">
                Asegúrate de haber respondido todas las preguntas antes de enviar
              </p>
            </div>
          </div>
        ) : viewMode === 'results' ? (
          <div className="results-container">
            <div className="results-header">
              <div className="results-score-card">
                <div className="score-circle">
                  <svg width="200" height="200" viewBox="0 0 200 200">
                    <circle cx="100" cy="100" r="90" fill="none" stroke="#e5e7eb" strokeWidth="12"/>
                    <circle 
                      cx="100" 
                      cy="100" 
                      r="90" 
                      fill="none" 
                      stroke={testResults.score >= 70 ? "#10b981" : testResults.score >= 50 ? "#f59e0b" : "#ef4444"}
                      strokeWidth="12"
                      strokeDasharray={`${(testResults.score / 100) * 565} 565`}
                      transform="rotate(-90 100 100)"
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="score-text">
                    <div className="score-number">{testResults.score}%</div>
                    <div className="score-label">Puntuación</div>
                  </div>
                </div>
                <div className="score-details">
                  <h2 className="results-title">¡Test Completado!</h2>
                  <p className="results-summary">
                    {testResults.correctCount} de {testResults.totalItems} respuestas correctas
                  </p>
                  <div className="results-performance">
                    {testResults.score >= 80 && <span className="performance-badge excellent">🌟 Excelente</span>}
                    {testResults.score >= 60 && testResults.score < 80 && <span className="performance-badge good">👍 Bien</span>}
                    {testResults.score >= 40 && testResults.score < 60 && <span className="performance-badge average">📚 Regular</span>}
                    {testResults.score < 40 && <span className="performance-badge poor">💪 Sigue practicando</span>}
                  </div>
                </div>
              </div>
            </div>

            <div className="results-feedback-section">
              <h3 className="feedback-title">📊 Retroalimentación Detallada</h3>
              
              {testResults.results.map((result, index) => (
                <div key={result.itemId} className={`feedback-card ${result.isCorrect ? 'correct' : 'incorrect'}`}>
                  <div className="feedback-header">
                    <span className="feedback-number">Caso {index + 1}</span>
                    <span className={`feedback-status ${result.isCorrect ? 'correct' : 'incorrect'}`}>
                      {result.isCorrect ? '✓ Correcto' : '✗ Incorrecto'}
                    </span>
                  </div>

                  <div className="feedback-content">
                    <div className="feedback-scenario">
                      <strong>Escenario:</strong> {result.scenario}
                    </div>
                    <div className="feedback-hypothesis">
                      <strong>Hipótesis:</strong> {result.hypothesis}
                    </div>
                    <div className="feedback-newinfo">
                      <strong>Nueva información:</strong> {result.newInfo}
                    </div>
                  </div>

                  <div className="feedback-answers">
                    <div className="answer-comparison">
                      <div className="user-answer">
                        <span className="answer-label">Tu respuesta:</span>
                        <span className="answer-value">{result.userAnswer > 0 ? `+${result.userAnswer}` : result.userAnswer}</span>
                      </div>
                      <div className="correct-answer">
                        <span className="answer-label">Respuesta esperada:</span>
                        <span className="answer-value">{result.correctAnswer > 0 ? `+${result.correctAnswer}` : result.correctAnswer}</span>
                      </div>
                    </div>
                  </div>

                  {result.explanation && (
                    <div className="feedback-explanation">
                      <strong>💡 Explicación:</strong>
                      <p>{result.explanation}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="results-actions">
              <button onClick={handleSaveTest} className="btn-save-test">
                💾 Guardar Test
              </button>
              <button onClick={handleNewTest} className="btn-new-test">
                🔄 Generar Nuevo Test
              </button>
              <button onClick={() => setViewMode('config')} className="btn-back-config">
                ← Volver a Configuración
              </button>
            </div>
          </div>
        ) : null}
      </main>

      {/* Loading Modal */}
      {isGenerating && (
        <div className="loading-overlay">
          <div className="loading-modal">
            <div className="loading-icon">
              <div className="spinner"></div>
            </div>
            <h3 className="loading-title">Generando test con IA...</h3>
            <p className="loading-subtitle">Creando {numItems} ítems de nivel {difficulty}</p>
            
            <div className="progress-container">
              <div className="progress-bar">
                <div 
                  className="progress-fill" 
                  style={{ width: `${progress}%` }}
                >
                  <span className="progress-text">{progress}%</span>
                </div>
              </div>
            </div>
            
            <div className="loading-steps">
              <div className={`loading-step ${progress >= 25 ? 'active' : ''}`}>
                <span className="step-icon">{progress >= 25 ? '✓' : '⏳'}</span>
                <span className="step-text">Analizando enfoque médico</span>
              </div>
              <div className={`loading-step ${progress >= 50 ? 'active' : ''}`}>
                <span className="step-icon">{progress >= 50 ? '✓' : '⏳'}</span>
                <span className="step-text">Generando escenarios clínicos</span>
              </div>
              <div className={`loading-step ${progress >= 75 ? 'active' : ''}`}>
                <span className="step-icon">{progress >= 75 ? '✓' : '⏳'}</span>
                <span className="step-text">Creando hipótesis diagnósticas</span>
              </div>
              <div className={`loading-step ${progress >= 100 ? 'active' : ''}`}>
                <span className="step-icon">{progress >= 100 ? '✓' : '⏳'}</span>
                <span className="step-text">Finalizando test</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
