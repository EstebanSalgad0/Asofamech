import React, { useState } from "react";
import {
  SCT_SCALE,
  SCT_SCALE_LABELS,
  getAtPath,
  linesToList,
  listToLines,
  setAtPath,
} from "./caseStructure";

/**
 * Editor del caso clinico en el formato PA-ASO-001.
 *
 * Doce secciones plegables, la primera abierta. Se pliegan porque el formato
 * completo es largo y un docente rara vez trabaja mas de una seccion a la vez;
 * mostrarlo todo desplegado convertiria el formulario en un muro de campos.
 *
 * El estado vive arriba (CasesPage): aqui solo se emite `onChange` con la
 * estructura completa ya modificada.
 */

const SECTIONS = [
  { id: "identification", label: "1. Identificación del caso" },
  { id: "narratives", label: "2. Relatos" },
  { id: "semantics", label: "3. Análisis semántico" },
  { id: "clinical", label: "4. Información clínica" },
  { id: "physical_exam", label: "5. Examen físico" },
  { id: "workup", label: "6. Laboratorio e imagenología" },
  { id: "course", label: "7. Evolución y tratamiento" },
  { id: "diagnoses", label: "8. Diagnósticos y razonamiento" },
  { id: "practical_script", label: "9. Practical Script (SCT)" },
  { id: "pathology", label: "10. Anatomía patológica" },
  { id: "pedagogy", label: "11. Metadatos pedagógicos" },
  { id: "assessment", label: "12. Banco de evaluación" },
];

// Secciones que contienen la clave de correccion. Se marcan en la interfaz para
// que el docente sepa que el estudiante no las vera mientras el caso siga
// cerrado (pedagogy.reveal_key en false).
const ANSWER_KEY_SECTIONS = new Set([
  "practical_script",
  "assessment",
]);

const VITAL_FIELDS = [
  ["blood_pressure", "Presión arterial"],
  ["heart_rate", "Frecuencia cardíaca"],
  ["respiratory_rate", "Frecuencia respiratoria"],
  ["temperature", "Temperatura"],
  ["oxygen_saturation", "Saturación O₂"],
  ["weight", "Peso"],
  ["height", "Talla"],
  ["bmi", "IMC"],
];

const QUALIFIER_FIELDS = [
  ["temporality", "Temporalidad", "hace 3 meses\núltimas semanas\ndiaria"],
  ["evolution", "Evolución", "progresiva\nempeoramiento\ninicialmente… luego…"],
  ["intensity", "Intensidad / cantidad", "10 kg\nmarcada\nprofusa"],
  ["features", "Características", "involuntaria\nseca\nproductiva\nen reposo"],
];

function Field({ label, hint, children }) {
  return (
    <div className="cse-field">
      <label className="cse-label">{label}</label>
      {hint && <p className="cse-hint">{hint}</p>}
      {children}
    </div>
  );
}

function ListArea({ label, hint, value, onChange, rows = 4, placeholder }) {
  return (
    <Field label={label} hint={hint || "Una línea por elemento."}>
      <textarea
        rows={rows}
        placeholder={placeholder}
        value={listToLines(value)}
        onChange={(e) => onChange(linesToList(e.target.value))}
      />
    </Field>
  );
}

/**
 * Lista editable de filas homogéneas (sistemas del examen, cronología, etc.).
 * `columns` describe cada campo: { key, label, type: "text" | "area" | "score" }.
 */
function RowList({ label, hint, rows, columns, onChange, addLabel = "+ Agregar fila" }) {
  const list = Array.isArray(rows) ? rows : [];

  const blankRow = () =>
    columns.reduce((acc, column) => ({ ...acc, [column.key]: column.type === "score" ? null : "" }), {});

  const update = (index, key, value) =>
    onChange(list.map((row, i) => (i === index ? { ...row, [key]: value } : row)));

  return (
    <Field label={label} hint={hint}>
      <div className="cse-rows">
        {list.map((row, index) => (
          <div key={index} className="cse-row">
            <div className="cse-row-fields">
              {columns.map((column) => (
                <div key={column.key} className={`cse-row-field cse-row-field-${column.type || "text"}`}>
                  <span className="cse-row-label">{column.label}</span>
                  {column.type === "area" ? (
                    <textarea
                      rows={column.rows || 3}
                      value={row[column.key] || ""}
                      placeholder={column.placeholder}
                      onChange={(e) => update(index, column.key, e.target.value)}
                    />
                  ) : column.type === "score" ? (
                    <select
                      value={row[column.key] === null || row[column.key] === undefined ? "" : String(row[column.key])}
                      onChange={(e) =>
                        update(index, column.key, e.target.value === "" ? null : parseInt(e.target.value, 10))
                      }
                    >
                      <option value="">—</option>
                      {SCT_SCALE.map((score) => (
                        <option key={score} value={String(score)}>
                          {score > 0 ? `+${score}` : score} · {SCT_SCALE_LABELS[score]}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={row[column.key] || ""}
                      placeholder={column.placeholder}
                      onChange={(e) => update(index, column.key, e.target.value)}
                    />
                  )}
                </div>
              ))}
            </div>
            <button
              type="button"
              className="cse-row-remove"
              onClick={() => onChange(list.filter((_, i) => i !== index))}
              aria-label={`Quitar fila ${index + 1}`}
            >
              Quitar
            </button>
          </div>
        ))}
      </div>
      <button type="button" className="cse-add-btn" onClick={() => onChange([...list, blankRow()])}>
        {addLabel}
      </button>
    </Field>
  );
}

/** Panel de laboratorio: cabecera, filas parámetro/resultado/referencia y comentario. */
function LabPanels({ panels, onChange }) {
  const list = Array.isArray(panels) ? panels : [];

  const updatePanel = (index, patch) =>
    onChange(list.map((panel, i) => (i === index ? { ...panel, ...patch } : panel)));

  return (
    <Field
      label="Paneles de laboratorio"
      hint="Cada panel agrupa los parámetros de un mismo examen (hemograma, perfil bioquímico…)."
    >
      <div className="cse-panels">
        {list.map((panel, index) => (
          <div key={index} className="cse-panel">
            <div className="cse-panel-head">
              <input
                type="text"
                value={panel.name || ""}
                placeholder="Nombre del panel (ej: Hemograma con VHS)"
                onChange={(e) => updatePanel(index, { name: e.target.value })}
              />
              <button
                type="button"
                className="cse-row-remove"
                onClick={() => onChange(list.filter((_, i) => i !== index))}
              >
                Quitar panel
              </button>
            </div>
            <RowList
              label="Parámetros"
              rows={panel.rows}
              onChange={(rows) => updatePanel(index, { rows })}
              addLabel="+ Agregar parámetro"
              columns={[
                { key: "parameter", label: "Parámetro", placeholder: "Hemoglobina (Hb)" },
                { key: "result", label: "Resultado", placeholder: "10,2 g/dL" },
                { key: "reference", label: "Referencia", placeholder: "13,5 – 17,5 g/dL" },
                { key: "interpretation", label: "Interpretación", placeholder: "Anemia moderada" },
              ]}
            />
            <Field label="Comentario interpretativo">
              <textarea
                rows={3}
                value={panel.comment || ""}
                onChange={(e) => updatePanel(index, { comment: e.target.value })}
              />
            </Field>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="cse-add-btn"
        onClick={() => onChange([...list, { name: "", rows: [], comment: "" }])}
      >
        + Agregar panel
      </button>
    </Field>
  );
}

/**
 * Practical Script: matriz hallazgo × diagnóstico.
 *
 * Las columnas son los diagnósticos y se sugieren desde la sección 8, para que
 * el docente no tenga que reescribirlos ni arriesgar que dejen de coincidir.
 */
function PracticalScript({ script, suggestedColumns, onChange }) {
  const columns = script.columns || [];
  const rows = script.rows || [];

  const setColumns = (next) => {
    // Al cambiar las columnas, cada fila se recorta o rellena para que el
    // numero de celdas siga coincidiendo con el de diagnosticos.
    const resized = rows.map((row) => {
      const ratings = [...(row.ratings || [])];
      while (ratings.length < next.length) ratings.push({ value: null, rationale: "" });
      return { ...row, ratings: ratings.slice(0, next.length) };
    });
    onChange({ ...script, columns: next, rows: resized });
  };

  const updateCell = (rowIndex, cellIndex, patch) =>
    onChange({
      ...script,
      rows: rows.map((row, i) =>
        i === rowIndex
          ? {
              ...row,
              ratings: (row.ratings || []).map((cell, j) =>
                j === cellIndex ? { ...cell, ...patch } : cell
              ),
            }
          : row
      ),
    });

  const addRow = () =>
    onChange({
      ...script,
      rows: [
        ...rows,
        { finding: "", ratings: columns.map(() => ({ value: null, rationale: "" })) },
      ],
    });

  const canSyncColumns =
    suggestedColumns.length > 0 && suggestedColumns.join("|") !== columns.join("|");

  return (
    <>
      <Field label="Instrucciones para el estudiante">
        <textarea
          rows={2}
          value={script.instructions || ""}
          placeholder="Para cada nuevo dato, indique cómo cambia la probabilidad de cada diagnóstico…"
          onChange={(e) => onChange({ ...script, instructions: e.target.value })}
        />
      </Field>

      <Field
        label="Diagnósticos evaluados (columnas)"
        hint="Una línea por diagnóstico, en el mismo orden en que aparecerán las columnas."
      >
        <textarea
          rows={3}
          value={listToLines(columns)}
          onChange={(e) => setColumns(linesToList(e.target.value))}
        />
        {canSyncColumns && (
          <button type="button" className="cse-add-btn" onClick={() => setColumns(suggestedColumns)}>
            Usar los diagnósticos de la sección 8
          </button>
        )}
      </Field>

      {columns.length === 0 ? (
        <p className="cse-hint">Define primero los diagnósticos para poder cargar los hallazgos.</p>
      ) : (
        <div className="cse-rows">
          {rows.map((row, rowIndex) => (
            <div key={rowIndex} className="cse-script-row">
              <div className="cse-script-head">
                <input
                  type="text"
                  value={row.finding || ""}
                  placeholder="Nuevo dato clínico (ej: 3. Tos productiva hemoptoica)"
                  onChange={(e) =>
                    onChange({
                      ...script,
                      rows: rows.map((r, i) => (i === rowIndex ? { ...r, finding: e.target.value } : r)),
                    })
                  }
                />
                <button
                  type="button"
                  className="cse-row-remove"
                  onClick={() =>
                    onChange({ ...script, rows: rows.filter((_, i) => i !== rowIndex) })
                  }
                >
                  Quitar
                </button>
              </div>
              <div className="cse-script-cells">
                {columns.map((column, cellIndex) => {
                  const cell = (row.ratings || [])[cellIndex] || { value: null, rationale: "" };
                  return (
                    <div key={cellIndex} className="cse-script-cell">
                      <span className="cse-row-label">{column}</span>
                      <select
                        value={cell.value === null || cell.value === undefined ? "" : String(cell.value)}
                        onChange={(e) =>
                          updateCell(rowIndex, cellIndex, {
                            value: e.target.value === "" ? null : parseInt(e.target.value, 10),
                          })
                        }
                      >
                        <option value="">—</option>
                        {SCT_SCALE.map((score) => (
                          <option key={score} value={String(score)}>
                            {score > 0 ? `+${score}` : score}
                          </option>
                        ))}
                      </select>
                      <input
                        type="text"
                        value={cell.rationale || ""}
                        placeholder="Justificación breve"
                        onChange={(e) => updateCell(rowIndex, cellIndex, { rationale: e.target.value })}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
          <button type="button" className="cse-add-btn" onClick={addRow}>
            + Agregar hallazgo
          </button>
        </div>
      )}
    </>
  );
}

export function CaseStructureEditor({ value, onChange }) {
  const [openSection, setOpenSection] = useState("identification");
  const structure = value;

  const set = (path, next) => onChange(setAtPath(structure, path, next));
  const get = (path) => getAtPath(structure, path);

  const bindText = (path) => ({
    value: get(path) || "",
    onChange: (e) => set(path, e.target.value),
  });

  const suggestedColumns = [
    structure.diagnoses?.primary?.name,
    ...(structure.diagnoses?.differentials || []).map((d) => d.name),
  ].filter(Boolean);

  const renderSection = (id) => {
    switch (id) {
      case "identification":
        return (
          <>
            <Field label="Código del caso" hint="Identificador editorial, ej: PAC-ASO-002.">
              <input type="text" placeholder="PAC-ASO-002" {...bindText("identification.case_code")} />
            </Field>
            <Field label="Resumen">
              <textarea rows={2} {...bindText("identification.summary")} />
            </Field>
            <ListArea
              label="Palabras clave"
              value={get("identification.keywords")}
              onChange={(next) => set("identification.keywords", next)}
              placeholder={"Tuberculosis miliar\nVIH positivo\nInmunodepresión"}
            />
          </>
        );

      case "narratives":
        return (
          <>
            <Field
              label="Relato del paciente en primera persona"
              hint="Cómo cuenta el paciente su historia, con lenguaje coloquial."
            >
              <textarea rows={8} {...bindText("narratives.patient_first_person")} />
            </Field>
            <Field
              label="Relato para presentación clínica"
              hint="La misma historia traducida a lenguaje médico. Es el modelo contra el que se contrasta el informe del estudiante."
            >
              <textarea rows={6} {...bindText("narratives.clinical_presentation")} />
            </Field>
          </>
        );

      case "semantics":
        return (
          <>
            <Field label="Síntoma pivote" hint="El síntoma central que organiza el caso.">
              <input type="text" placeholder="Tos con hemoptisis" {...bindText("semantics.pivot_symptom")} />
            </Field>
            <ListArea
              label="Términos médicos más importantes"
              value={get("semantics.key_terms")}
              onChange={(next) => set("semantics.key_terms", next)}
              rows={6}
            />
            {QUALIFIER_FIELDS.map(([key, label, placeholder]) => (
              <ListArea
                key={key}
                label={`Calificadores · ${label}`}
                value={get(`semantics.qualifiers.${key}`)}
                onChange={(next) => set(`semantics.qualifiers.${key}`, next)}
                rows={3}
                placeholder={placeholder}
              />
            ))}
          </>
        );

      case "clinical":
        return (
          <>
            <div className="cse-grid-2">
              <Field label="Edad">
                <input type="text" placeholder="34 años" {...bindText("clinical.patient_profile.age")} />
              </Field>
              <Field label="Sexo">
                <input type="text" placeholder="Masculino" {...bindText("clinical.patient_profile.sex")} />
              </Field>
            </div>
            <Field label="Antecedentes del perfil">
              <textarea rows={3} {...bindText("clinical.patient_profile.background")} />
            </Field>
            <Field label="Motivo de consulta">
              <textarea rows={2} {...bindText("clinical.chief_complaint")} />
            </Field>
            <Field label="Anamnesis y evolución">
              <textarea rows={6} {...bindText("clinical.anamnesis")} />
            </Field>
            <ListArea
              label="Fármacos"
              value={get("clinical.medications")}
              onChange={(next) => set("clinical.medications", next)}
              rows={3}
            />
            <Field label="Hábitos">
              <textarea rows={3} {...bindText("clinical.habits")} />
            </Field>
            <Field label="Ocupación">
              <input type="text" {...bindText("clinical.occupation")} />
            </Field>
          </>
        );

      case "physical_exam":
        return (
          <>
            <Field label="Signos vitales">
              <div className="cse-grid-2">
                {VITAL_FIELDS.map(([key, label]) => (
                  <div key={key} className="cse-vital">
                    <span className="cse-row-label">{label}</span>
                    <input type="text" {...bindText(`physical_exam.vital_signs.${key}`)} />
                  </div>
                ))}
              </div>
            </Field>
            <Field label="Estado general">
              <textarea rows={3} {...bindText("physical_exam.general_state")} />
            </Field>
            <RowList
              label="Examen por sistemas"
              rows={get("physical_exam.systems")}
              onChange={(next) => set("physical_exam.systems", next)}
              addLabel="+ Agregar sistema"
              columns={[
                { key: "name", label: "Sistema", placeholder: "Tórax y aparato respiratorio" },
                { key: "findings", label: "Hallazgos", type: "area", rows: 4 },
              ]}
            />
          </>
        );

      case "workup":
        return (
          <>
            <LabPanels
              panels={get("workup.lab_panels")}
              onChange={(next) => set("workup.lab_panels", next)}
            />
            <RowList
              label="Microbiología y pruebas específicas"
              rows={get("workup.microbiology")}
              onChange={(next) => set("workup.microbiology", next)}
              addLabel="+ Agregar examen"
              columns={[
                { key: "test", label: "Examen", placeholder: "Baciloscopia (3 muestras)" },
                { key: "result", label: "Resultado", placeholder: "Negativa" },
                { key: "note", label: "Observación", type: "area", rows: 2 },
              ]}
            />
            <RowList
              label="Estudios de imagen"
              hint="La fuente puede ser un enlace externo (Radiopaedia, repositorio institucional)."
              rows={get("workup.imaging")}
              onChange={(next) => set("workup.imaging", next)}
              addLabel="+ Agregar estudio"
              columns={[
                { key: "study", label: "Estudio", placeholder: "Radiografía de tórax PA y lateral" },
                { key: "source", label: "Fuente", placeholder: "https://radiopaedia.org/cases/…" },
                { key: "report", label: "Informe", type: "area", rows: 3 },
              ]}
            />
          </>
        );

      case "course":
        return (
          <>
            <RowList
              label="Línea de tiempo"
              hint="Cuándo ocurre cada hecho: síntomas, exámenes que llegan, cambios de tratamiento."
              rows={get("course.timeline")}
              onChange={(next) => set("course.timeline", next)}
              addLabel="+ Agregar hito"
              columns={[
                { key: "moment", label: "Momento", placeholder: "Día 15" },
                { key: "event", label: "Hecho clínico", type: "area", rows: 3 },
              ]}
            />
            <Field label="Plan de tratamiento">
              <textarea rows={4} {...bindText("course.treatment_plan")} />
            </Field>
          </>
        );

      case "diagnoses":
        return (
          <>
            <div className="cse-grid-2">
              <Field label="Diagnóstico principal">
                <input type="text" placeholder="Tuberculosis miliar" {...bindText("diagnoses.primary.name")} />
              </Field>
              <Field label="SNOMED CT ID">
                <input type="text" placeholder="47604008" {...bindText("diagnoses.primary.sctid")} />
              </Field>
            </div>
            <RowList
              label="Diagnósticos diferenciales"
              rows={get("diagnoses.differentials")}
              onChange={(next) => set("diagnoses.differentials", next)}
              addLabel="+ Agregar diferencial"
              columns={[
                { key: "name", label: "Diagnóstico", placeholder: "Neumonía por Pneumocystis jirovecii" },
                { key: "sctid", label: "SNOMED CT ID", placeholder: "415125002" },
              ]}
            />
            <Field
              label="Justificación diagnóstica"
              hint="Parte de la clave de corrección: el estudiante no la ve mientras el caso siga cerrado."
            >
              <textarea rows={8} {...bindText("diagnoses.justification")} />
            </Field>
          </>
        );

      case "practical_script":
        return (
          <PracticalScript
            script={get("practical_script") || {}}
            suggestedColumns={suggestedColumns}
            onChange={(next) => set("practical_script", next)}
          />
        );

      case "pathology":
        return (
          <>
            <Field label="Muestra recibida">
              <input type="text" placeholder="Ganglio linfático, biopsia escisional" {...bindText("pathology.specimen")} />
            </Field>
            <Field label="Descripción macroscópica">
              <textarea rows={4} {...bindText("pathology.macroscopic")} />
            </Field>
            <Field label="Descripción microscópica">
              <textarea rows={6} {...bindText("pathology.microscopic")} />
            </Field>
            <Field label="Diagnóstico anatomopatológico">
              <textarea rows={3} {...bindText("pathology.diagnosis")} />
            </Field>
            <Field label="Codificación (ICD / SNOMED CT)">
              <input type="text" placeholder="SNOMED CT 47604008" {...bindText("pathology.coding")} />
            </Field>
            <RowList
              label="Test de concordancia con la histopatología"
              hint="Cómo cambia cada diagnóstico al conocer el informe. Parte de la clave de corrección."
              rows={get("pathology.concordance")}
              onChange={(next) => set("pathology.concordance", next)}
              addLabel="+ Agregar fila"
              columns={[
                { key: "diagnosis", label: "Diagnóstico inicial" },
                { key: "new_data", label: "Nuevo dato", type: "area", rows: 2 },
                { key: "shift", label: "Se vuelve…", type: "score" },
                { key: "rationale", label: "Justificación", type: "area", rows: 2 },
              ]}
            />
          </>
        );

      case "pedagogy":
        return (
          <>
            <RowList
              label="Objetivos de aprendizaje"
              rows={get("pedagogy.objectives")}
              onChange={(next) => set("pedagogy.objectives", next)}
              addLabel="+ Agregar objetivo"
              columns={[
                { key: "area", label: "Asignatura", placeholder: "Razonamiento clínico" },
                { key: "text", label: "Objetivo", type: "area", rows: 3 },
              ]}
            />
            <div className="cse-grid-2">
              <Field label="Nivel de dificultad">
                <input type="text" placeholder="Pregrado" {...bindText("pedagogy.level")} />
              </Field>
              <Field label="Prerrequisitos">
                <input type="text" {...bindText("pedagogy.prerequisites")} />
              </Field>
            </div>
            <Field label="Ubicación curricular">
              <textarea rows={2} {...bindText("pedagogy.curricular_placement")} />
            </Field>
            <label className="cse-check">
              <input
                type="checkbox"
                checked={Boolean(get("pedagogy.reveal_key"))}
                onChange={(e) => set("pedagogy.reveal_key", e.target.checked)}
              />
              <span>
                Liberar la clave de corrección al estudiante
                <em>
                  Mientras esté desmarcado, el estudiante no ve el Practical Script, la
                  justificación diagnóstica, el test de concordancia ni el banco de evaluación.
                </em>
              </span>
            </label>
          </>
        );

      case "assessment":
        return (
          <>
            <MultipleChoice
              questions={get("assessment.multiple_choice")}
              onChange={(next) => set("assessment.multiple_choice", next)}
            />
            <RowList
              label="Preguntas abiertas con rúbrica"
              rows={get("assessment.open_questions")}
              onChange={(next) => set("assessment.open_questions", next)}
              addLabel="+ Agregar pregunta abierta"
              columns={[
                { key: "question", label: "Pregunta", type: "area", rows: 2 },
                { key: "rubric", label: "Criterios de corrección", type: "area", rows: 3 },
              ]}
            />
          </>
        );

      default:
        return null;
    }
  };

  return (
    <div className="cse" data-testid="case-structure-editor">
      {SECTIONS.map((section) => {
        const isOpen = openSection === section.id;
        return (
          <section key={section.id} className={`cse-section ${isOpen ? "open" : ""}`}>
            <button
              type="button"
              className="cse-section-head"
              aria-expanded={isOpen}
              onClick={() => setOpenSection(isOpen ? null : section.id)}
            >
              <span>{section.label}</span>
              {ANSWER_KEY_SECTIONS.has(section.id) && (
                <span className="cse-badge-key">Clave</span>
              )}
              <span className="cse-caret">{isOpen ? "−" : "+"}</span>
            </button>
            {isOpen && <div className="cse-section-body">{renderSection(section.id)}</div>}
          </section>
        );
      })}
    </div>
  );
}

/** Preguntas de opción múltiple con alternativa correcta y justificación. */
function MultipleChoice({ questions, onChange }) {
  const list = Array.isArray(questions) ? questions : [];

  const update = (index, patch) =>
    onChange(list.map((q, i) => (i === index ? { ...q, ...patch } : q)));

  return (
    <Field label="Preguntas de opción múltiple">
      <div className="cse-rows">
        {list.map((question, index) => (
          <div key={index} className="cse-row cse-mcq">
            <div className="cse-row-fields">
              <div className="cse-row-field cse-row-field-area">
                <span className="cse-row-label">Enunciado</span>
                <textarea
                  rows={2}
                  value={question.question || ""}
                  onChange={(e) => update(index, { question: e.target.value })}
                />
              </div>
              <div className="cse-row-field cse-row-field-area">
                <span className="cse-row-label">Alternativas (una por línea)</span>
                <textarea
                  rows={4}
                  value={listToLines(question.options)}
                  onChange={(e) => update(index, { options: linesToList(e.target.value) })}
                />
              </div>
              <div className="cse-row-field">
                <span className="cse-row-label">Alternativa correcta</span>
                <select
                  value={
                    question.correct_index === null || question.correct_index === undefined
                      ? ""
                      : String(question.correct_index)
                  }
                  onChange={(e) =>
                    update(index, {
                      correct_index: e.target.value === "" ? null : parseInt(e.target.value, 10),
                    })
                  }
                >
                  <option value="">—</option>
                  {(question.options || []).map((option, optionIndex) => (
                    <option key={optionIndex} value={String(optionIndex)}>
                      {String.fromCharCode(65 + optionIndex)}. {option}
                    </option>
                  ))}
                </select>
              </div>
              <div className="cse-row-field cse-row-field-area">
                <span className="cse-row-label">Justificación</span>
                <textarea
                  rows={2}
                  value={question.rationale || ""}
                  onChange={(e) => update(index, { rationale: e.target.value })}
                />
              </div>
            </div>
            <button
              type="button"
              className="cse-row-remove"
              onClick={() => onChange(list.filter((_, i) => i !== index))}
            >
              Quitar
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="cse-add-btn"
        onClick={() =>
          onChange([...list, { question: "", options: [], correct_index: null, rationale: "" }])
        }
      >
        + Agregar pregunta
      </button>
    </Field>
  );
}

export default CaseStructureEditor;
