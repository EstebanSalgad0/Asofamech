import React from "react";

/**
 * Resultado de la revision automatica de un informe.
 *
 * Muestra siempre el puntaje efectivo —el del docente si corrigio, si no el del
 * modelo— y deja visible el del modelo cuando difieren, para que la correccion
 * quede trazable en lugar de sustituir silenciosamente al original.
 */

function bandTone(band) {
  const label = (band || "").toLowerCase();
  if (label.includes("adecuad")) return "ok";
  if (label.includes("parcial")) return "warn";
  if (label.includes("insuficiente")) return "bad";
  return "neutral";
}

function scoreTone(score, max) {
  if (!max) return "neutral";
  const ratio = score / max;
  if (ratio >= 0.8) return "ok";
  if (ratio >= 0.55) return "warn";
  return "bad";
}

export function EvaluationResult({ evaluation, showModelMeta = false }) {
  if (!evaluation) return null;

  const score = evaluation.effective_score ?? evaluation.total_score;
  const max = evaluation.max_score || 0;
  const corrected =
    evaluation.teacher_score !== null && evaluation.teacher_score !== undefined;

  return (
    <div className="evr" data-testid="evaluation-result">
      <div className="evr-head">
        <div className={`evr-score evr-${scoreTone(score, max)}`}>
          <strong>{score}</strong>
          <span>de {max} puntos</span>
        </div>
        {evaluation.band && (
          <span className={`evr-band evr-band-${bandTone(evaluation.band)}`}>{evaluation.band}</span>
        )}
        {corrected && (
          <span className="evr-corrected">
            Puntaje corregido por el docente · la revisión automática dio {evaluation.total_score}
          </span>
        )}
      </div>

      {evaluation.summary && <p className="evr-summary">{evaluation.summary}</p>}

      {evaluation.teacher_note && (
        <div className="evr-teacher-note">
          <span>Comentario del docente</span>
          <p>{evaluation.teacher_note}</p>
        </div>
      )}

      <div className="evr-criteria">
        {(evaluation.criteria || []).map((criterion, index) => (
          <div
            key={index}
            className={`evr-criterion ${criterion.evaluated === false ? "not-evaluated" : ""}`}
          >
            <div className="evr-criterion-head">
              <span className="evr-criterion-name">{criterion.criterion}</span>
              <span className={`evr-criterion-score evr-${scoreTone(criterion.score, criterion.max_score)}`}>
                {criterion.score} / {criterion.max_score}
              </span>
            </div>
            {criterion.level && <span className="evr-criterion-level">{criterion.level}</span>}
            {criterion.justification && <p className="evr-criterion-text">{criterion.justification}</p>}
            {criterion.evidence && (
              <blockquote className="evr-evidence">“{criterion.evidence}”</blockquote>
            )}
          </div>
        ))}
      </div>

      {(evaluation.strengths || []).length > 0 && (
        <div className="evr-lists">
          <div>
            <h4>Fortalezas</h4>
            <ul>
              {evaluation.strengths.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
          {(evaluation.improvements || []).length > 0 && (
            <div>
              <h4>Qué mejorar</h4>
              <ul>
                {evaluation.improvements.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {(evaluation.improvements || []).length > 0 && (evaluation.strengths || []).length === 0 && (
        <div className="evr-lists">
          <div>
            <h4>Qué mejorar</h4>
            <ul>
              {evaluation.improvements.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {showModelMeta && evaluation.model && (
        <p className="evr-meta">
          Revisión generada por {evaluation.provider} · {evaluation.model}
          {evaluation.evaluated_at && ` · ${new Date(evaluation.evaluated_at).toLocaleString("es-ES")}`}
        </p>
      )}
    </div>
  );
}

export default EvaluationResult;
