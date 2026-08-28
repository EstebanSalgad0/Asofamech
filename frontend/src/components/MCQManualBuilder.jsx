import React, { useRef, useState } from "react";
import { importMCQFile, saveMCQTest } from "../api";

/**
 * Constructor de un test de alternativas (pregunta + opciones + correcta):
 * el docente puede escribir las preguntas a mano o importar un documento
 * (PDF/DOCX/TXT) con el formato clásico -pregunta, alternativas a/b/c/d,
 * correcta y explicación- y la IA las convierte en ítems editables antes de
 * guardar. Se usa tanto en el módulo de Test de alternativas como embebido
 * en la sección "Banco de evaluación" del editor de casos.
 */

const DIFFICULTIES = [
  { value: "pregrado", label: "Pregrado" },
  { value: "internado", label: "Internado" },
  { value: "residente", label: "Residente" },
];

function emptyItem(id) {
  return { id, question: "", options: ["", ""], correct_index: 0, explanation: "" };
}

export function MCQManualBuilder({
  defaultName = "",
  defaultTopic = "",
  defaultDifficulty = "pregrado",
  onSaved,
  onCancel,
}) {
  const [name, setName] = useState(defaultName);
  const [topic, setTopic] = useState(defaultTopic);
  const [difficulty, setDifficulty] = useState(defaultDifficulty);
  const [items, setItems] = useState([emptyItem(1)]);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importProgress, setImportProgress] = useState(0);
  const [importFileName, setImportFileName] = useState("");
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const updateItem = (index, patch) =>
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));

  const updateOption = (index, optIndex, value) =>
    setItems((prev) =>
      prev.map((item, i) =>
        i === index
          ? { ...item, options: item.options.map((opt, oi) => (oi === optIndex ? value : opt)) }
          : item,
      ),
    );

  const addOption = (index) =>
    setItems((prev) =>
      prev.map((item, i) =>
        i === index && item.options.length < 6 ? { ...item, options: [...item.options, ""] } : item,
      ),
    );

  const removeOption = (index, optIndex) =>
    setItems((prev) =>
      prev.map((item, i) => {
        if (i !== index || item.options.length <= 2) return item;
        const options = item.options.filter((_, oi) => oi !== optIndex);
        const correct_index =
          item.correct_index === optIndex
            ? 0
            : item.correct_index > optIndex
              ? item.correct_index - 1
              : item.correct_index;
        return { ...item, options, correct_index };
      }),
    );

  const addItem = () =>
    setItems((prev) => [...prev, emptyItem((prev[prev.length - 1]?.id || 0) + 1)]);

  const removeItem = (index) =>
    setItems((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev));

  const handleImportClick = () => fileInputRef.current?.click();

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setImportProgress(0);
    setImportFileName(file.name);
    setError(null);
    const interval = setInterval(() => {
      setImportProgress((p) => {
        if (p >= 90) { clearInterval(interval); return 90; }
        return p + 12;
      });
    }, 600);
    try {
      const result = await importMCQFile(file);
      clearInterval(interval);
      setImportProgress(100);
      if (result?.items?.length) {
        setItems(
          result.items.map((item, i) => ({
            id: i + 1,
            question: item.question,
            options: item.options,
            correct_index: item.correct_index,
            explanation: item.explanation || "",
          })),
        );
        if (result.topic && !topic.trim()) setTopic(result.topic);
        if (result.difficulty) setDifficulty(result.difficulty);
        if (!name.trim()) setName(file.name.replace(/\.[^.]+$/, ""));
        if (result.warnings?.length) setError(result.warnings.join(" "));
      }
      await new Promise((resolve) => setTimeout(resolve, 400));
    } catch (err) {
      clearInterval(interval);
      setError(err?.message || "No se pudo importar el archivo.");
    } finally {
      setImporting(false);
      setImportProgress(0);
    }
  };

  const isValid =
    name.trim().length > 0 &&
    topic.trim().length > 0 &&
    items.every(
      (item) => item.question.trim() && item.options.length >= 2 && item.options.every((opt) => opt.trim()),
    );

  const handleSave = async () => {
    if (!isValid || saving) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await saveMCQTest(
        name.trim(),
        topic.trim(),
        difficulty,
        items.length,
        items.map((item, i) => ({ ...item, id: i + 1 })),
      );
      onSaved?.(saved);
    } catch (err) {
      setError(err?.message || "No se pudo guardar el test de alternativas.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="cse-panel mcqb-panel">
      <div className="mcqb-import-row">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />
        <button type="button" className="mcqb-import-btn" onClick={handleImportClick} disabled={importing}>
          {importing ? "Leyendo documento…" : "📄 Importar preguntas desde archivo"}
        </button>
        <span className="cse-hint">
          PDF, DOCX o TXT con preguntas y alternativas. La IA las extrae automáticamente; revísalas antes de guardar.
        </span>
      </div>

      {importing && (
        <div className="mcqb-import-progress" role="status" aria-live="polite">
          <div className="mcqb-import-progress-head">
            <span className="mcqb-import-progress-spinner" />
            <span className="mcqb-import-progress-title">Leyendo "{importFileName}"…</span>
            <span className="mcqb-import-progress-pct">{importProgress}%</span>
          </div>
          <div className="mcqb-import-progress-track">
            <div className="mcqb-import-progress-fill" style={{ width: `${importProgress}%` }} />
          </div>
          <div className="mcqb-import-progress-step">
            {importProgress < 35
              ? "Extrayendo el texto del documento…"
              : importProgress < 80
                ? "La IA está identificando preguntas y alternativas…"
                : "Verificando las respuestas correctas…"}
            {" "}Puede tardar entre 30 segundos y un par de minutos según el largo del archivo.
          </div>
        </div>
      )}

      <div className="cse-field">
        <label className="cse-label">Nombre del test</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ej: Patogénesis de la tuberculosis"
        />
      </div>

      <div className="cse-grid-2">
        <div className="cse-field">
          <label className="cse-label">Tema</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Ej: Tuberculosis"
          />
        </div>
        <div className="cse-field">
          <label className="cse-label">Dificultad</label>
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            {DIFFICULTIES.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="cse-rows">
        {items.map((item, index) => (
          <div key={item.id} className="cse-row mcqb-item">
            <div className="cse-row-fields">
              <div className="cse-row-field cse-row-field-area">
                <label className="cse-row-label">Pregunta {index + 1}</label>
                <textarea
                  rows={2}
                  value={item.question}
                  onChange={(e) => updateItem(index, { question: e.target.value })}
                />
              </div>
              <div className="cse-row-field cse-row-field-area">
                <label className="cse-row-label">Alternativas (marca la correcta)</label>
                <div className="mcqb-options">
                  {item.options.map((option, optIndex) => (
                    <div key={optIndex} className="mcqb-option-row">
                      <input
                        type="radio"
                        name={`correct-${item.id}`}
                        checked={item.correct_index === optIndex}
                        onChange={() => updateItem(index, { correct_index: optIndex })}
                        title="Marcar como correcta"
                      />
                      <input
                        type="text"
                        value={option}
                        onChange={(e) => updateOption(index, optIndex, e.target.value)}
                        placeholder={`Alternativa ${String.fromCharCode(97 + optIndex)}`}
                      />
                      {item.options.length > 2 && (
                        <button
                          type="button"
                          className="mcqb-option-remove"
                          onClick={() => removeOption(index, optIndex)}
                          title="Quitar alternativa"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  ))}
                  {item.options.length < 6 && (
                    <button type="button" className="cse-add-btn" onClick={() => addOption(index)}>
                      + Agregar alternativa
                    </button>
                  )}
                </div>
              </div>
              <div className="cse-row-field cse-row-field-area">
                <label className="cse-row-label">Explicación (opcional)</label>
                <textarea
                  rows={2}
                  value={item.explanation}
                  onChange={(e) => updateItem(index, { explanation: e.target.value })}
                />
              </div>
            </div>
            {items.length > 1 && (
              <button
                type="button"
                className="cse-row-remove"
                onClick={() => removeItem(index)}
                title="Quitar pregunta"
              >
                ✕
              </button>
            )}
          </div>
        ))}
      </div>

      <button type="button" className="cse-add-btn" onClick={addItem}>
        + Agregar pregunta
      </button>

      {error && <p className="cse-hint sctmb-error">{error}</p>}

      <div className="sctmb-actions">
        {onCancel && (
          <button type="button" className="sctmb-cancel-btn" onClick={onCancel} disabled={saving}>
            Cancelar
          </button>
        )}
        <button
          type="button"
          className="sctmb-save-btn"
          disabled={!isValid || saving}
          onClick={handleSave}
        >
          {saving ? "Guardando…" : "Guardar test de alternativas"}
        </button>
      </div>
    </div>
  );
}
