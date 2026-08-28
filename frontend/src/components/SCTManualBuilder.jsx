import React, { useState } from "react";
import { saveSCTTest } from "../api";
import { SCT_SCALE, SCT_SCALE_LABELS } from "./caseStructure";

/**
 * Constructor manual de un test SCT (Script Concordance Test): el docente
 * escribe cada item a mano -viñeta, hipótesis, nuevo dato, respuesta correcta
 * y explicación- en vez de generarlos con IA. Se usa tanto en el módulo SCT
 * como embebido en la sección "Practical Script" del editor de casos, por eso
 * no asume dónde vive ni qué pasa después de guardar (lo decide `onSaved`).
 */

const DIFFICULTIES = [
  { value: "pregrado", label: "Pregrado" },
  { value: "internado", label: "Internado" },
  { value: "residente", label: "Residente" },
];

function emptyItem(id) {
  return { id, vignette: "", hypothesis: "", new_info: "", correct_answer: 0, explanation: "" };
}

export function SCTManualBuilder({
  defaultName = "",
  defaultDifficulty = "pregrado",
  defaultFocus = "",
  onSaved,
  onCancel,
}) {
  const [name, setName] = useState(defaultName);
  const [difficulty, setDifficulty] = useState(defaultDifficulty);
  const [focus, setFocus] = useState(defaultFocus);
  const [items, setItems] = useState([emptyItem(1)]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const updateItem = (index, patch) =>
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));

  const addItem = () =>
    setItems((prev) => [...prev, emptyItem((prev[prev.length - 1]?.id || 0) + 1)]);

  const removeItem = (index) =>
    setItems((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev));

  const isValid =
    name.trim().length > 0 &&
    focus.trim().length > 0 &&
    items.every((item) => item.vignette.trim() && item.hypothesis.trim() && item.new_info.trim());

  const handleSave = async () => {
    if (!isValid || saving) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await saveSCTTest(
        name.trim(),
        difficulty,
        focus.trim(),
        items.length,
        items.map((item, i) => ({ ...item, id: i + 1 })),
      );
      onSaved?.(saved);
    } catch (err) {
      setError(err?.message || "No se pudo guardar el test SCT.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="cse-panel sctmb-panel">
      <div className="cse-field">
        <label className="cse-label">Nombre del test</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ej: SCT Tuberculosis pulmonar"
        />
      </div>

      <div className="cse-grid-2">
        <div className="cse-field">
          <label className="cse-label">Dificultad</label>
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            {DIFFICULTIES.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </div>
        <div className="cse-field">
          <label className="cse-label">Enfoque / tema</label>
          <input
            type="text"
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="Ej: Tuberculosis pulmonar"
          />
        </div>
      </div>

      <div className="cse-rows">
        {items.map((item, index) => (
          <div key={item.id} className="cse-row sctmb-item">
            <div className="cse-row-fields">
              <div className="cse-row-field cse-row-field-area">
                <label className="cse-row-label">Viñeta clínica {index + 1}</label>
                <textarea
                  rows={2}
                  value={item.vignette}
                  onChange={(e) => updateItem(index, { vignette: e.target.value })}
                />
              </div>
              <div className="cse-row-field">
                <label className="cse-row-label">Hipótesis</label>
                <input
                  type="text"
                  value={item.hypothesis}
                  onChange={(e) => updateItem(index, { hypothesis: e.target.value })}
                />
              </div>
              <div className="cse-row-field">
                <label className="cse-row-label">Nueva información</label>
                <input
                  type="text"
                  value={item.new_info}
                  onChange={(e) => updateItem(index, { new_info: e.target.value })}
                />
              </div>
              <div className="cse-row-field">
                <label className="cse-row-label">Respuesta correcta</label>
                <select
                  value={item.correct_answer}
                  onChange={(e) => updateItem(index, { correct_answer: Number(e.target.value) })}
                >
                  {SCT_SCALE.map((v) => (
                    <option key={v} value={v}>
                      {v > 0 ? `+${v}` : v} · {SCT_SCALE_LABELS[v]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="cse-row-field cse-row-field-area">
                <label className="cse-row-label">Explicación</label>
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
                title="Quitar ítem"
              >
                ✕
              </button>
            )}
          </div>
        ))}
      </div>

      <button type="button" className="cse-add-btn" onClick={addItem}>
        + Agregar ítem
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
          {saving ? "Guardando…" : "Guardar test SCT"}
        </button>
      </div>
    </div>
  );
}
