import React, { useState } from "react";
import { generateSCT, saveSCTTest } from "../api";
import SCTTestSelector from "./SCTTestSelector";

export default function SCTSection() {
  const [sctData, setSctData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [currentItemIndex, setCurrentItemIndex] = useState(0);
  const [userAnswers, setUserAnswers] = useState({});
  const [showResults, setShowResults] = useState(false);
  const [showTestSelector, setShowTestSelector] = useState(false);
  const [testName, setTestName] = useState("");
  const [savedTestId, setSavedTestId] = useState(null);
  
  // Configuración
  const [numItems, setNumItems] = useState(5);
  const [difficulty, setDifficulty] = useState("pregrado");
  const [focus, setFocus] = useState("");

  const handleGenerate = async () => {
    setIsLoading(true);
    setShowResults(false);
    setUserAnswers({});
    setCurrentItemIndex(0);
    setSavedTestId(null);
    
    try {
      const data = await generateSCT(numItems, difficulty, focus);
      setSctData(data);
      
      // Auto-generar nombre sugerido
      const date = new Date().toLocaleDateString('es-ES');
      setTestName(`SCT ${focus} - ${date}`);
    } catch (err) {
      console.error("Error al generar SCT:", err);
      alert("Error al generar el test. Asegúrate de que el backend y Ollama estén corriendo.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveTest = async () => {
    if (savedTestId) {
      alert("Este test ya está guardado.");
      return;
    }
    if (!testName.trim()) {
      alert("Por favor ingresa un nombre para el test");
      return;
    }
    
    try {
      const saved = await saveSCTTest(testName, difficulty, focus, sctData.items.length, sctData.items);
      setSavedTestId(saved?.id || true);
      alert(`✅ Test "${testName}" guardado exitosamente`);
    } catch (err) {
      console.error("Error al guardar test:", err);
      alert("Error al guardar el test");
    }
  };

  const handleLoadSaved = () => {
    setShowTestSelector(true);
  };

  const handleSelectTest = (testData) => {
    setSctData({
      items: testData.items,
      total: testData.num_items,
      difficulty: testData.difficulty,
      focus: testData.focus
    });
    setTestName(testData.name);
    setSavedTestId(testData.id || true);
    setDifficulty(testData.difficulty);
    setFocus(testData.focus);
    setNumItems(testData.num_items);
    setShowResults(false);
    setUserAnswers({});
    setCurrentItemIndex(0);
  };

  const handleAnswerSelect = (itemId, answer) => {
    setUserAnswers(prev => ({
      ...prev,
      [itemId]: answer
    }));
  };

  const handleNext = () => {
    if (currentItemIndex < sctData.items.length - 1) {
      setCurrentItemIndex(currentItemIndex + 1);
    }
  };

  const handlePrevious = () => {
    if (currentItemIndex > 0) {
      setCurrentItemIndex(currentItemIndex - 1);
    }
  };

  const handleSubmit = () => {
    setShowResults(true);
    setCurrentItemIndex(0);
  };

  const calculateScore = () => {
    if (!sctData) return { correct: 0, total: 0, percentage: 0 };
    
    let correct = 0;
    sctData.items.forEach(item => {
      if (userAnswers[item.id] === item.correct_answer) {
        correct++;
      }
    });
    
    const total = sctData.items.length;
    const percentage = total > 0 ? Math.round((correct / total) * 100) : 0;
    
    return { correct, total, percentage };
  };

  const scaleLabels = {
    "-2": "Descarta completamente",
    "-1": "Menos probable",
    "0": "Sin cambio",
    "1": "Más probable",
    "2": "Apoya fuertemente"
  };

  const currentItem = sctData?.items[currentItemIndex];
  const score = showResults ? calculateScore() : null;

  return (
    <section id="sct" className="sct-section">
      <div className="sct-inner">
        <div className="sct-header-text">
          <h2>
            Test de Concordancia de <span>Scripts (SCT)</span>
          </h2>
          <p>
            Evalúa tu razonamiento clínico resolviendo casos médicos de cualquier especialidad.
            El SCT mide cómo ajustas tus hipótesis diagnósticas ante nueva información.
          </p>
        </div>

        {!sctData ? (
          <div className="sct-config-card">
            <h3>Configurar Test SCT</h3>
            
            <div className="sct-config-form">
              <div className="form-group">
                <label htmlFor="numItems">Número de ítems:</label>
                <input
                  id="numItems"
                  type="number"
                  min="1"
                  max="10"
                  value={numItems}
                  onChange={(e) => setNumItems(parseInt(e.target.value))}
                  disabled={isLoading}
                />
              </div>

              <div className="form-group">
                <label htmlFor="difficulty">Dificultad:</label>
                <select
                  id="difficulty"
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  disabled={isLoading}
                >
                  <option value="pregrado">Pregrado</option>
                  <option value="internado">Internado</option>
                  <option value="residente">Residente</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="focus">Enfoque médico:</label>
                <input
                  id="focus"
                  type="text"
                  value={focus}
                  onChange={(e) => setFocus(e.target.value)}
                  disabled={isLoading}
                  placeholder="Ej: VIH/SIDA, diabetes mellitus, insuficiencia cardíaca, etc."
                />
              </div>
            </div>

            <div className="sct-config-actions">
              <button
                className="btn btn-primary"
                onClick={handleGenerate}
                disabled={isLoading}
              >
                {isLoading ? "Generando con IA..." : "🤖 Generar Test con LLaMA 3"}
              </button>
              
              <button
                className="btn btn-outline"
                onClick={handleLoadSaved}
                disabled={isLoading}
              >
                📚 Cargar Test Guardado
              </button>
            </div>

            <div className="sct-info">
              <p>
                💡 <strong>¿Qué es el SCT?</strong> El Script Concordance Test evalúa
                cómo los estudiantes modifican sus hipótesis clínicas cuando reciben
                nueva información, simulando el razonamiento de expertos.
              </p>
            </div>
          </div>
        ) : (
          <div className="sct-test-card">
            {!showResults ? (
              <>
                <div className="sct-test-header">
                  <div className="sct-test-name-group">
                    <label htmlFor="testName">Nombre del test:</label>
                    <input
                      id="testName"
                      type="text"
                      value={testName}
                      onChange={(e) => setTestName(e.target.value)}
                      placeholder="Ej: SCT VIH - Diciembre 2025"
                    />
                    {!savedTestId && (
                      <button
                        className="btn-save-test"
                        onClick={handleSaveTest}
                        title="Guardar test en base de datos"
                      >
                        💾 Guardar
                      </button>
                    )}
                  </div>
                </div>

                <div className="sct-progress">
                  <div className="sct-progress-info">
                    <span>Ítem {currentItemIndex + 1} de {sctData.items.length}</span>
                    <span className="sct-difficulty-badge">{sctData.difficulty}</span>
                  </div>
                  <div className="sct-progress-bar">
                    <div 
                      className="sct-progress-fill"
                      style={{ width: `${((currentItemIndex + 1) / sctData.items.length) * 100}%` }}
                    />
                  </div>
                </div>

                <div className="sct-item">
                  <div className="sct-vignette">
                    <h4>📋 Caso Clínico</h4>
                    <p>{currentItem.vignette}</p>
                  </div>

                  <div className="sct-hypothesis">
                    <h4>🔍 Hipótesis</h4>
                    <p>{currentItem.hypothesis}</p>
                  </div>

                  <div className="sct-new-info">
                    <h4>✨ Nueva Información</h4>
                    <p>{currentItem.new_info}</p>
                  </div>

                  <div className="sct-question">
                    <h4>❓ ¿Cómo afecta esta información a tu hipótesis?</h4>
                    <div className="sct-scale">
                      {[-2, -1, 0, 1, 2].map(value => (
                        <button
                          key={value}
                          className={`sct-scale-option ${userAnswers[currentItem.id] === value ? 'selected' : ''}`}
                          onClick={() => handleAnswerSelect(currentItem.id, value)}
                        >
                          <span className="sct-scale-value">{value > 0 ? `+${value}` : value}</span>
                          <span className="sct-scale-label">{scaleLabels[value.toString()]}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="sct-navigation">
                  <button
                    className="btn btn-outline"
                    onClick={handlePrevious}
                    disabled={currentItemIndex === 0}
                  >
                    ← Anterior
                  </button>

                  {currentItemIndex === sctData.items.length - 1 ? (
                    <button
                      className="btn btn-primary"
                      onClick={handleSubmit}
                      disabled={Object.keys(userAnswers).length !== sctData.items.length}
                    >
                      Ver Resultados
                    </button>
                  ) : (
                    <button
                      className="btn btn-primary"
                      onClick={handleNext}
                    >
                      Siguiente →
                    </button>
                  )}
                </div>
              </>
            ) : (
              <div className="sct-results">
                <div className="sct-score-header">
                  <h3>📊 Resultados del Test</h3>
                  <div className="sct-score-circle">
                    <span className="sct-percentage">{score.percentage}%</span>
                    <span className="sct-score-label">{score.correct}/{score.total} correctas</span>
                  </div>
                </div>

                <div className="sct-items-review">
                  {sctData.items.map((item, idx) => {
                    const userAnswer = userAnswers[item.id];
                    const isCorrect = userAnswer === item.correct_answer;
                    
                    return (
                      <div key={item.id} className={`sct-review-item ${isCorrect ? 'correct' : 'incorrect'}`}>
                        <div className="sct-review-header">
                          <h4>Ítem {idx + 1} {isCorrect ? '✅' : '❌'}</h4>
                        </div>
                        
                        <div className="sct-review-content">
                          <p><strong>Caso:</strong> {item.vignette}</p>
                          <p><strong>Hipótesis:</strong> {item.hypothesis}</p>
                          <p><strong>Nueva información:</strong> {item.new_info}</p>
                          
                          <div className="sct-review-answers">
                            <p>
                              <strong>Tu respuesta:</strong>{" "}
                              <span className={isCorrect ? "answer-correct" : "answer-incorrect"}>
                                {userAnswer > 0 ? `+${userAnswer}` : userAnswer} - {scaleLabels[userAnswer?.toString()]}
                              </span>
                            </p>
                            {!isCorrect && (
                              <p>
                                <strong>Respuesta correcta:</strong>{" "}
                                <span className="answer-correct">
                                  {item.correct_answer > 0 ? `+${item.correct_answer}` : item.correct_answer} - {scaleLabels[item.correct_answer.toString()]}
                                </span>
                              </p>
                            )}
                          </div>
                          
                          <div className="sct-explanation">
                            <strong>💡 Explicación:</strong>
                            <p>{item.explanation}</p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <button
                  className="btn btn-primary"
                  onClick={() => {
                    setSctData(null);
                    setUserAnswers({});
                    setShowResults(false);
                    setCurrentItemIndex(0);
                  }}
                >
                  🔄 Generar Nuevo Test
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {showTestSelector && (
        <SCTTestSelector
          onSelect={handleSelectTest}
          onClose={() => setShowTestSelector(false)}
        />
      )}
    </section>
  );
}

