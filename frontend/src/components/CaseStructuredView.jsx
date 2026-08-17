import React from "react";
import { CaseImageFigure } from "./CaseImageGallery";
import { SCT_SCALE_LABELS } from "./caseStructure";
import { safeExternalUrl } from "./CaseResources";

/**
 * Presentacion de lectura de un caso en formato PA-ASO-001.
 *
 * Se renderiza desde el objeto y no desde el markdown generado porque cada
 * seccion tiene su propia forma —tablas de laboratorio, matriz del Practical
 * Script, cronologia— y aplanarlas a texto perderia esa lectura.
 *
 * El backend ya recorta la clave de correccion para el estudiante, asi que
 * aqui basta con no dibujar las secciones que llegan vacias.
 */

function Section({ title, children }) {
  return (
    <section className="csv-section">
      <h3 className="csv-section-title">{title}</h3>
      {children}
    </section>
  );
}

function Paragraphs({ text }) {
  if (!text) return null;
  return (
    <>
      {String(text)
        .split(/\n{2,}/)
        .map((block, index) => (
          <p key={index} className="csv-paragraph">
            {block.split("\n").map((line, lineIndex, lines) => (
              <React.Fragment key={lineIndex}>
                {line}
                {lineIndex < lines.length - 1 && <br />}
              </React.Fragment>
            ))}
          </p>
        ))}
    </>
  );
}

function Table({ headers, rows }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="csv-table-wrap">
      <table className="csv-table">
        <thead>
          <tr>
            {headers.map((header, index) => (
              <th key={index}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Chips({ items }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="csv-chips">
      {items.map((item, index) => (
        <span key={index} className="csv-chip">
          {item}
        </span>
      ))}
    </div>
  );
}

function scoreLabel(value) {
  if (value === null || value === undefined || value === "") return "—";
  const sign = value > 0 ? `+${value}` : String(value);
  return `${sign} ${SCT_SCALE_LABELS[String(value)] || ""}`.trim();
}

function scoreClass(value) {
  if (value === null || value === undefined || value === "") return "csv-score";
  if (value > 0) return "csv-score csv-score-pos";
  if (value < 0) return "csv-score csv-score-neg";
  return "csv-score csv-score-zero";
}

const VITAL_LABELS = [
  ["blood_pressure", "Presión arterial"],
  ["heart_rate", "Frecuencia cardíaca"],
  ["respiratory_rate", "Frecuencia respiratoria"],
  ["temperature", "Temperatura"],
  ["oxygen_saturation", "Saturación O₂"],
  ["weight", "Peso"],
  ["height", "Talla"],
  ["bmi", "IMC"],
];

const QUALIFIER_LABELS = [
  ["temporality", "Temporalidad"],
  ["evolution", "Evolución"],
  ["intensity", "Intensidad / cantidad"],
  ["features", "Características"],
];

export function CaseStructuredView({ structure, images = [], canManage = false }) {
  if (!structure) return null;

  const identification = structure.identification || {};
  const narratives = structure.narratives || {};
  const semantics = structure.semantics || {};
  const qualifiers = semantics.qualifiers || {};
  const clinical = structure.clinical || {};
  const profile = clinical.patient_profile || {};
  const exam = structure.physical_exam || {};
  const vitals = exam.vital_signs || {};
  const workup = structure.workup || {};
  const course = structure.course || {};
  const diagnoses = structure.diagnoses || {};
  const script = structure.practical_script || {};
  const pathology = structure.pathology || {};
  const assessment = structure.assessment || {};

  const vitalRows = VITAL_LABELS.filter(([key]) => vitals[key]).map(([key, label]) => [
    label,
    vitals[key],
  ]);
  const profileHeader = [profile.age, profile.sex].filter(Boolean).join(" · ");
  const hasQualifiers = QUALIFIER_LABELS.some(([key]) => (qualifiers[key] || []).length > 0);
  const scriptRows = script.rows || [];
  const answerKeyHidden =
    !canManage && !structure.pedagogy?.reveal_key && scriptRows.length === 0;

  return (
    <div className="csv" data-testid="case-structured-view">
      {identification.summary && <p className="csv-lead">{identification.summary}</p>}
      <Chips items={identification.keywords} />

      {narratives.patient_first_person && (
        <Section title="Relato del paciente">
          <blockquote className="csv-quote">
            <Paragraphs text={narratives.patient_first_person} />
          </blockquote>
        </Section>
      )}

      {narratives.clinical_presentation && (
        <Section title="Relato para presentación clínica">
          <Paragraphs text={narratives.clinical_presentation} />
        </Section>
      )}

      {(semantics.pivot_symptom || (semantics.key_terms || []).length > 0 || hasQualifiers) && (
        <Section title="Análisis semántico">
          {semantics.pivot_symptom && (
            <p className="csv-highlight">
              <span>Síntoma pivote</span>
              <strong>{semantics.pivot_symptom}</strong>
            </p>
          )}
          {(semantics.key_terms || []).length > 0 && (
            <>
              <h4 className="csv-sub">Términos médicos más importantes</h4>
              <Chips items={semantics.key_terms} />
            </>
          )}
          {hasQualifiers && (
            <>
              <h4 className="csv-sub">Calificadores semánticos</h4>
              <dl className="csv-deflist">
                {QUALIFIER_LABELS.filter(([key]) => (qualifiers[key] || []).length > 0).map(
                  ([key, label]) => (
                    <React.Fragment key={key}>
                      <dt>{label}</dt>
                      <dd>{qualifiers[key].join(" · ")}</dd>
                    </React.Fragment>
                  )
                )}
              </dl>
            </>
          )}
        </Section>
      )}

      {(profileHeader || profile.background || clinical.chief_complaint || clinical.anamnesis) && (
        <Section title="Información clínica estructurada">
          {(profileHeader || profile.background) && (
            <p className="csv-paragraph">
              <strong>Perfil del paciente: </strong>
              {[profileHeader, profile.background].filter(Boolean).join(" — ")}
            </p>
          )}
          {clinical.occupation && (
            <p className="csv-paragraph">
              <strong>Ocupación: </strong>
              {clinical.occupation}
            </p>
          )}
          {clinical.chief_complaint && (
            <>
              <h4 className="csv-sub">Motivo de consulta</h4>
              <Paragraphs text={clinical.chief_complaint} />
            </>
          )}
          {clinical.anamnesis && (
            <>
              <h4 className="csv-sub">Anamnesis y evolución</h4>
              <Paragraphs text={clinical.anamnesis} />
            </>
          )}
          {(clinical.medications || []).length > 0 && (
            <>
              <h4 className="csv-sub">Fármacos</h4>
              <ul className="csv-list">
                {clinical.medications.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </>
          )}
          {clinical.habits && (
            <>
              <h4 className="csv-sub">Hábitos</h4>
              <Paragraphs text={clinical.habits} />
            </>
          )}
        </Section>
      )}

      {(vitalRows.length > 0 || exam.general_state || (exam.systems || []).length > 0) && (
        <Section title="Examen físico">
          {vitalRows.length > 0 && (
            <div className="csv-vitals">
              {vitalRows.map(([label, value]) => (
                <div key={label} className="csv-vital">
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          )}
          {exam.general_state && (
            <>
              <h4 className="csv-sub">Estado general</h4>
              <Paragraphs text={exam.general_state} />
            </>
          )}
          {(exam.systems || []).map((system, index) => (
            <div key={index}>
              <h4 className="csv-sub">{system.name}</h4>
              <Paragraphs text={system.findings} />
            </div>
          ))}
        </Section>
      )}

      {((workup.lab_panels || []).length > 0 || (workup.microbiology || []).length > 0) && (
        <Section title="Laboratorio y pruebas complementarias">
          {(workup.lab_panels || []).map((panel, index) => (
            <div key={index}>
              {panel.name && <h4 className="csv-sub">{panel.name}</h4>}
              <Table
                headers={["Parámetro", "Resultado", "Valores de referencia", "Interpretación"]}
                rows={(panel.rows || []).map((row) => [
                  row.parameter,
                  row.result,
                  row.reference,
                  row.interpretation,
                ])}
              />
              {panel.comment && <p className="csv-note">{panel.comment}</p>}
            </div>
          ))}
          {(workup.microbiology || []).length > 0 && (
            <>
              <h4 className="csv-sub">Microbiología</h4>
              <Table
                headers={["Examen", "Resultado", "Observación"]}
                rows={workup.microbiology.map((row) => [row.test, row.result, row.note])}
              />
            </>
          )}
        </Section>
      )}

      {(workup.imaging || []).length > 0 && (
        <Section title="Estudios imagenológicos">
          {workup.imaging.map((study, index) => {
            const href = safeExternalUrl(study.source);
            return (
              <div key={index} className="csv-imaging">
                <h4 className="csv-sub">{study.study}</h4>
                {href ? (
                  <p className="csv-note">
                    Fuente:{" "}
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {href}
                    </a>
                  </p>
                ) : (
                  study.source && <p className="csv-note">Fuente: {study.source}</p>
                )}
                <Paragraphs text={study.report} />
              </div>
            );
          })}
        </Section>
      )}

      {((course.timeline || []).length > 0 || course.treatment_plan) && (
        <Section title="Evolución temporal">
          {(course.timeline || []).length > 0 && (
            <ol className="csv-timeline">
              {course.timeline.map((entry, index) => (
                <li key={index}>
                  <span className="csv-timeline-moment">{entry.moment}</span>
                  <span className="csv-timeline-event">{entry.event}</span>
                </li>
              ))}
            </ol>
          )}
          {course.treatment_plan && (
            <>
              <h4 className="csv-sub">Plan de tratamiento</h4>
              <Paragraphs text={course.treatment_plan} />
            </>
          )}
        </Section>
      )}

      {(diagnoses.primary?.name || (diagnoses.differentials || []).length > 0) && (
        <Section title="Diagnósticos">
          {diagnoses.primary?.name && (
            <p className="csv-highlight">
              <span>Diagnóstico principal</span>
              <strong>
                {diagnoses.primary.name}
                {diagnoses.primary.sctid && (
                  <em className="csv-sctid"> SCTID {diagnoses.primary.sctid}</em>
                )}
              </strong>
            </p>
          )}
          {(diagnoses.differentials || []).length > 0 && (
            <>
              <h4 className="csv-sub">Diagnósticos diferenciales</h4>
              <ul className="csv-list">
                {diagnoses.differentials.map((entry, index) => (
                  <li key={index}>
                    {entry.name}
                    {entry.sctid && <em className="csv-sctid"> SCTID {entry.sctid}</em>}
                  </li>
                ))}
              </ul>
            </>
          )}
          {diagnoses.justification && (
            <>
              <h4 className="csv-sub">Justificación</h4>
              <Paragraphs text={diagnoses.justification} />
            </>
          )}
        </Section>
      )}

      {scriptRows.length > 0 && (script.columns || []).length > 0 && (
        <Section title="Practical Script">
          {canManage && <p className="csv-key-note">Clave de corrección · visible solo para docentes.</p>}
          {script.instructions && <p className="csv-note">{script.instructions}</p>}
          <div className="csv-table-wrap">
            <table className="csv-table csv-table-script">
              <thead>
                <tr>
                  <th>Nuevo dato clínico</th>
                  {script.columns.map((column, index) => (
                    <th key={index}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scriptRows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    <th scope="row">{row.finding}</th>
                    {script.columns.map((_, cellIndex) => {
                      const cell = (row.ratings || [])[cellIndex] || {};
                      return (
                        <td key={cellIndex}>
                          <span className={scoreClass(cell.value)}>{scoreLabel(cell.value)}</span>
                          {cell.rationale && <span className="csv-cell-note">{cell.rationale}</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {(pathology.specimen || pathology.macroscopic || pathology.microscopic || pathology.diagnosis) && (
        <Section title="Informe anatomopatológico">
          {pathology.specimen && (
            <p className="csv-paragraph">
              <strong>Muestra recibida: </strong>
              {pathology.specimen}
            </p>
          )}
          {pathology.macroscopic && (
            <>
              <h4 className="csv-sub">Descripción macroscópica</h4>
              <Paragraphs text={pathology.macroscopic} />
            </>
          )}
          {pathology.microscopic && (
            <>
              <h4 className="csv-sub">Descripción microscópica</h4>
              <Paragraphs text={pathology.microscopic} />
            </>
          )}
          {pathology.diagnosis && (
            <>
              <h4 className="csv-sub">Diagnóstico</h4>
              <Paragraphs text={pathology.diagnosis} />
            </>
          )}
          {pathology.coding && <p className="csv-note">Codificación: {pathology.coding}</p>}
          {(pathology.concordance || []).length > 0 && (
            <>
              <h4 className="csv-sub">Test de concordancia clínica</h4>
              <Table
                headers={["Diagnóstico inicial", "Nuevo dato clínico", "Se vuelve…", "Justificación"]}
                rows={pathology.concordance.map((row) => [
                  row.diagnosis,
                  row.new_data,
                  <span key="s" className={scoreClass(row.shift)}>
                    {scoreLabel(row.shift)}
                  </span>,
                  row.rationale,
                ])}
              />
            </>
          )}
        </Section>
      )}

      {((assessment.multiple_choice || []).length > 0 ||
        (assessment.open_questions || []).length > 0) && (
        <Section title="Banco de evaluación">
          {canManage && <p className="csv-key-note">Clave de corrección · visible solo para docentes.</p>}
          {(assessment.multiple_choice || []).map((question, index) => (
            <div key={index} className="csv-mcq">
              <p className="csv-paragraph">
                <strong>{index + 1}. </strong>
                {question.question}
              </p>
              <ol className="csv-options">
                {(question.options || []).map((option, optionIndex) => (
                  <li
                    key={optionIndex}
                    className={optionIndex === question.correct_index ? "correct" : undefined}
                  >
                    {option}
                  </li>
                ))}
              </ol>
              {question.rationale && <p className="csv-note">{question.rationale}</p>}
            </div>
          ))}
          {(assessment.open_questions || []).map((question, index) => (
            <div key={`open-${index}`} className="csv-open-question">
              <p className="csv-paragraph">
                <strong>Pregunta abierta. </strong>
                {question.question}
              </p>
              {question.rubric && <p className="csv-note">Corrección: {question.rubric}</p>}
            </div>
          ))}
        </Section>
      )}

      {answerKeyHidden && (
        <p className="csv-note csv-hidden-note">
          El Practical Script, la justificación diagnóstica y el banco de evaluación se publicarán
          cuando el docente libere la clave del caso.
        </p>
      )}

      {images.length > 0 && (
        <Section title="Imágenes del caso">
          <div className="case-img-grid">
            {images.map((image) => (
              <CaseImageFigure key={image.id} image={image} variant="thumb" />
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

export default CaseStructuredView;
