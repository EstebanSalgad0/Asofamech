import React, { useState, useEffect } from "react";
import { listSCTTests, getSCTTest } from "../api";

export default function SCTTestSelector({ onSelect, onClose }) {
  const [tests, setTests] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadTests();
  }, []);

  const loadTests = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const data = await listSCTTests();
      setTests(data);
    } catch (err) {
      console.error("Error al cargar tests:", err);
      setError("No se pudieron cargar los tests guardados");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectTest = async (testId) => {
    try {
      const testData = await getSCTTest(testId);
      onSelect(testData);
      onClose();
    } catch (err) {
      console.error("Error al cargar test:", err);
      alert("Error al cargar el test seleccionado");
    }
  };

  // Agrupar tests por enfoque
  const groupedTests = tests.reduce((acc, test) => {
    const category = test.focus || "Otros";
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(test);
    return acc;
  }, {});

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>📚 Seleccionar Test Guardado</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {isLoading ? (
            <div className="modal-loading">
              <div className="loading-spinner"></div>
              <p>Cargando tests guardados...</p>
            </div>
          ) : error ? (
            <div className="modal-error">
              <p>{error}</p>
              <button className="btn btn-outline" onClick={loadTests}>
                Reintentar
              </button>
            </div>
          ) : tests.length === 0 ? (
            <div className="modal-empty">
              <p>📭 No hay tests guardados aún</p>
              <p className="modal-empty-hint">
                Genera un test y guárdalo para verlo aquí
              </p>
            </div>
          ) : (
            <div className="test-selector-list">
              {Object.entries(groupedTests).map(([category, categoryTests]) => (
                <div key={category} className="test-category">
                  <h4 className="test-category-title">
                    {category.charAt(0).toUpperCase() + category.slice(1)}
                  </h4>
                  <div className="test-category-items">
                    {categoryTests.map((test) => (
                      <div
                        key={test.id}
                        className="test-card"
                        onClick={() => handleSelectTest(test.id)}
                      >
                        <div className="test-card-header">
                          <h5>{test.name}</h5>
                          <span className="test-card-badge">{test.difficulty}</span>
                        </div>
                        <div className="test-card-info">
                          <span className="test-card-meta">
                            📋 {test.num_items} ítem{test.num_items !== 1 ? 's' : ''}
                          </span>
                          <span className="test-card-meta">
                            📅 {new Date(test.created_at).toLocaleDateString('es-ES')}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
