import React from "react";

/**
 * Editor de una rubrica: criterios con sus niveles y bandas de interpretacion.
 *
 * El puntaje maximo no se escribe: se deduce sumando el nivel mas alto de cada
 * criterio. Asi la rubrica no puede quedar diciendo "de 21 puntos" mientras sus
 * criterios suman 18.
 */

export function rubricMaxScore(criteria) {
  return (criteria || []).reduce((total, criterion) => {
    const scores = (criterion.levels || [])
      .map((level) => Number(level.score))
      .filter((score) => !Number.isNaN(score));
    return total + (scores.length > 0 ? Math.max(...scores) : 0);
  }, 0);
}

/** ISO completo (con segundos/zona) -> "YYYY-MM-DDTHH:mm" en hora local, lo que espera <input type="datetime-local">. */
function toLocalInputValue(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

const blankLevel = () => ({ label: "", score: "", descriptor: "" });
const blankCriterion = () => ({
  name: "",
  description: "",
  levels: [
    { label: "Adecuado", score: 3, descriptor: "" },
    { label: "Parcial", score: 2, descriptor: "" },
    { label: "Insuficiente", score: 1, descriptor: "" },
  ],
});

export function RubricEditor({ value, onChange }) {
  const criteria = value.criteria || [];
  const bands = value.bands || [];

  const patch = (changes) => onChange({ ...value, ...changes });

  const updateCriterion = (index, changes) =>
    patch({
      criteria: criteria.map((criterion, i) => (i === index ? { ...criterion, ...changes } : criterion)),
    });

  const updateLevel = (criterionIndex, levelIndex, changes) =>
    updateCriterion(criterionIndex, {
      levels: (criteria[criterionIndex].levels || []).map((level, i) =>
        i === levelIndex ? { ...level, ...changes } : level
      ),
    });

  const maxScore = rubricMaxScore(criteria);

  return (
    <div className="rbe" data-testid="rubric-editor">
      <div className="rbe-field">
        <label>Título *</label>
        <input
          type="text"
          value={value.title || ""}
          placeholder="Script de evaluación para informe clínico de alumno"
          onChange={(e) => patch({ title: e.target.value })}
        />
      </div>

      <div className="rbe-field">
        <label>Objetivo de la evaluación</label>
        <textarea
          rows={2}
          value={value.description || ""}
          onChange={(e) => patch({ description: e.target.value })}
        />
      </div>

      <div className="rbe-field">
        <label>Indicaciones para el revisor</label>
        <p className="rbe-hint">
          Contexto que se le entrega al modelo junto a la rúbrica: qué se espera del
          informe, términos esperables, criterios de exigencia.
        </p>
        <textarea
          rows={3}
          value={value.guidance || ""}
          onChange={(e) => patch({ guidance: e.target.value })}
        />
      </div>

      <div className="rbe-field">
        <label>Fecha de entrega (opcional)</label>
        <p className="rbe-hint">
          Pasada esta fecha, la rúbrica deja de aceptar entregas nuevas de estudiantes.
          Sin fecha, queda abierta indefinidamente. Tú puedes seguir probándola después.
        </p>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="datetime-local"
            value={toLocalInputValue(value.due_at)}
            onChange={(e) =>
              patch({ due_at: e.target.value ? new Date(e.target.value).toISOString() : null })
            }
          />
          {value.due_at && (
            <button type="button" className="rbe-remove" onClick={() => patch({ due_at: null })}>
              Quitar fecha
            </button>
          )}
        </div>
      </div>

      <div className="rbe-summary">
        <span>Puntaje máximo</span>
        <strong>{maxScore || 0} puntos</strong>
        <span className="rbe-summary-note">
          {criteria.length} criterio{criteria.length === 1 ? "" : "s"} · calculado desde los niveles
        </span>
      </div>

      <div className="rbe-criteria">
        {criteria.map((criterion, criterionIndex) => (
          <div key={criterionIndex} className="rbe-criterion">
            <div className="rbe-criterion-head">
              <input
                type="text"
                value={criterion.name || ""}
                placeholder={`Criterio ${criterionIndex + 1}`}
                onChange={(e) => updateCriterion(criterionIndex, { name: e.target.value })}
              />
              <button
                type="button"
                className="rbe-remove"
                onClick={() => patch({ criteria: criteria.filter((_, i) => i !== criterionIndex) })}
              >
                Quitar criterio
              </button>
            </div>

            <textarea
              rows={2}
              placeholder="Qué se observa en este criterio"
              value={criterion.description || ""}
              onChange={(e) => updateCriterion(criterionIndex, { description: e.target.value })}
            />

            <div className="rbe-levels">
              {(criterion.levels || []).map((level, levelIndex) => (
                <div key={levelIndex} className="rbe-level">
                  <input
                    type="text"
                    className="rbe-level-label"
                    placeholder="Nivel"
                    value={level.label || ""}
                    onChange={(e) => updateLevel(criterionIndex, levelIndex, { label: e.target.value })}
                  />
                  <input
                    type="number"
                    className="rbe-level-score"
                    step="0.5"
                    placeholder="Pts"
                    value={level.score === null || level.score === undefined ? "" : level.score}
                    onChange={(e) =>
                      updateLevel(criterionIndex, levelIndex, {
                        score: e.target.value === "" ? "" : Number(e.target.value),
                      })
                    }
                  />
                  <input
                    type="text"
                    className="rbe-level-descriptor"
                    placeholder="Descripción del desempeño"
                    value={level.descriptor || ""}
                    onChange={(e) =>
                      updateLevel(criterionIndex, levelIndex, { descriptor: e.target.value })
                    }
                  />
                  <button
                    type="button"
                    className="rbe-remove"
                    onClick={() =>
                      updateCriterion(criterionIndex, {
                        levels: criterion.levels.filter((_, i) => i !== levelIndex),
                      })
                    }
                    aria-label="Quitar nivel"
                  >
                    ×
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="rbe-add"
                onClick={() =>
                  updateCriterion(criterionIndex, { levels: [...(criterion.levels || []), blankLevel()] })
                }
              >
                + Agregar nivel
              </button>
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        className="rbe-add"
        onClick={() => patch({ criteria: [...criteria, blankCriterion()] })}
      >
        + Agregar criterio
      </button>

      <div className="rbe-field">
        <label>Bandas de interpretación</label>
        <p className="rbe-hint">
          Traducen el puntaje total a un dictamen (Adecuado, Parcial, Insuficiente).
        </p>
        <div className="rbe-bands">
          {bands.map((band, index) => (
            <div key={index} className="rbe-band">
              <input
                type="text"
                placeholder="Etiqueta"
                value={band.label || ""}
                onChange={(e) =>
                  patch({
                    bands: bands.map((b, i) => (i === index ? { ...b, label: e.target.value } : b)),
                  })
                }
              />
              <input
                type="number"
                step="0.5"
                placeholder="Desde"
                value={band.min === null || band.min === undefined ? "" : band.min}
                onChange={(e) =>
                  patch({
                    bands: bands.map((b, i) =>
                      i === index ? { ...b, min: e.target.value === "" ? "" : Number(e.target.value) } : b
                    ),
                  })
                }
              />
              <input
                type="number"
                step="0.5"
                placeholder="Hasta"
                value={band.max === null || band.max === undefined ? "" : band.max}
                onChange={(e) =>
                  patch({
                    bands: bands.map((b, i) =>
                      i === index ? { ...b, max: e.target.value === "" ? "" : Number(e.target.value) } : b
                    ),
                  })
                }
              />
              <button
                type="button"
                className="rbe-remove"
                onClick={() => patch({ bands: bands.filter((_, i) => i !== index) })}
                aria-label="Quitar banda"
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="rbe-add"
          onClick={() => patch({ bands: [...bands, { label: "", min: "", max: "" }] })}
        >
          + Agregar banda
        </button>
      </div>
    </div>
  );
}

/** Prepara la rúbrica para el backend: descarta niveles sin puntaje. */
export function serializeRubric(draft) {
  const criteria = (draft.criteria || [])
    .map((criterion) => ({
      name: (criterion.name || "").trim(),
      description: (criterion.description || "").trim() || null,
      levels: (criterion.levels || [])
        .filter((level) => level.score !== "" && level.score !== null && level.score !== undefined)
        .map((level) => ({
          label: (level.label || "").trim() || `${level.score} puntos`,
          score: Number(level.score),
          descriptor: (level.descriptor || "").trim() || null,
        })),
    }))
    .filter((criterion) => criterion.name && criterion.levels.length > 0);

  if (criteria.length === 0) {
    return { error: "La rúbrica necesita al menos un criterio con niveles puntuados." };
  }
  if (!(draft.title || "").trim()) {
    return { error: "La rúbrica necesita un título." };
  }

  const bands = (draft.bands || [])
    .filter((band) => (band.label || "").trim() && band.min !== "" && band.max !== "")
    .map((band) => ({
      label: band.label.trim(),
      min: Number(band.min),
      max: Number(band.max),
    }));

  return {
    payload: {
      title: draft.title.trim(),
      description: (draft.description || "").trim() || null,
      guidance: (draft.guidance || "").trim() || null,
      criteria,
      bands,
      case_id: draft.case_id ?? null,
      source_filename: draft.source_filename || null,
      due_at: draft.due_at || null,
      status: draft.status || "draft",
    },
  };
}

export default RubricEditor;
