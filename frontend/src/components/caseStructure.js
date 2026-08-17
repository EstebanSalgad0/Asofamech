/**
 * Forma canonica de un caso clinico en el formato PA-ASO-001.
 *
 * Espejo de `backend/app/case_structure.py`: el backend normaliza lo que llega
 * y devuelve siempre todas las claves, asi que aqui solo hace falta la plantilla
 * vacia (para inicializar el editor sin pedirla al servidor) y los helpers de
 * lectura/escritura por ruta que usan el editor y la vista.
 */

export const SCT_SCALE = [-2, -1, 0, 1, 2];

export const SCT_SCALE_LABELS = {
  "-2": "Mucho menos apropiada",
  "-1": "Menos apropiada",
  0: "Sin cambios",
  1: "Más apropiada",
  2: "Mucho más apropiada",
};

export const EMPTY_CASE_STRUCTURE = {
  version: 1,
  identification: { case_code: "", summary: "", keywords: [] },
  narratives: { patient_first_person: "", clinical_presentation: "" },
  semantics: {
    pivot_symptom: "",
    key_terms: [],
    qualifiers: { temporality: [], evolution: [], intensity: [], features: [] },
  },
  clinical: {
    patient_profile: { age: "", sex: "", background: "" },
    chief_complaint: "",
    anamnesis: "",
    medications: [],
    habits: "",
    occupation: "",
  },
  physical_exam: {
    vital_signs: {
      blood_pressure: "",
      heart_rate: "",
      respiratory_rate: "",
      temperature: "",
      oxygen_saturation: "",
      weight: "",
      height: "",
      bmi: "",
    },
    general_state: "",
    systems: [],
  },
  workup: { lab_panels: [], microbiology: [], imaging: [] },
  course: { timeline: [], treatment_plan: "" },
  diagnoses: { primary: { name: "", sctid: "" }, differentials: [], justification: "" },
  practical_script: { instructions: "", columns: [], rows: [] },
  pathology: {
    specimen: "",
    macroscopic: "",
    microscopic: "",
    diagnosis: "",
    coding: "",
    concordance: [],
  },
  pedagogy: {
    objectives: [],
    level: "",
    prerequisites: "",
    curricular_placement: "",
    reveal_key: false,
  },
  assessment: { multiple_choice: [], open_questions: [] },
};

/** Copia profunda de la plantilla: cada caso nuevo arranca con su propio objeto. */
export function emptyCaseStructure() {
  return JSON.parse(JSON.stringify(EMPTY_CASE_STRUCTURE));
}

/**
 * Rellena las claves que falten con las de la plantilla.
 *
 * Un caso guardado con una version anterior del formato no trae las secciones
 * nuevas; sin esto el editor intentaria leer `undefined.rows` al abrirlo.
 */
export function withDefaults(structure) {
  return mergeDefaults(EMPTY_CASE_STRUCTURE, structure);
}

function mergeDefaults(template, value) {
  if (Array.isArray(template)) return Array.isArray(value) ? value : [];
  if (template && typeof template === "object") {
    const source = value && typeof value === "object" ? value : {};
    const merged = {};
    for (const key of Object.keys(template)) {
      merged[key] = mergeDefaults(template[key], source[key]);
    }
    // Claves que el backend agrego y el frontend aun no conoce: se conservan
    // para no perderlas al reenviar el caso.
    for (const key of Object.keys(source)) {
      if (!(key in merged)) merged[key] = source[key];
    }
    return merged;
  }
  return value === undefined || value === null ? template : value;
}

export function getAtPath(object, path) {
  return path.split(".").reduce((acc, key) => (acc == null ? acc : acc[key]), object);
}

/** Devuelve una copia de `object` con `path` reemplazado. No muta el original. */
export function setAtPath(object, path, value) {
  const keys = path.split(".");
  const clone = Array.isArray(object) ? [...object] : { ...object };
  let cursor = clone;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i];
    const next = cursor[key];
    cursor[key] = Array.isArray(next) ? [...next] : { ...(next || {}) };
    cursor = cursor[key];
  }
  cursor[keys[keys.length - 1]] = value;
  return clone;
}

/** ¿Tiene la estructura algún contenido real, más allá de las claves vacías? */
export function isStructureEmpty(structure) {
  if (!structure) return true;
  return isBlank({ ...structure, version: undefined });
}

function isBlank(value) {
  if (Array.isArray(value)) return value.every(isBlank);
  if (value && typeof value === "object") return Object.values(value).every(isBlank);
  if (typeof value === "boolean") return value === false;
  return value === "" || value === null || value === undefined;
}

/** Texto multilínea ↔ lista de strings, para editar listas en un textarea. */
export const linesToList = (text) =>
  (text || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

export const listToLines = (list) => (Array.isArray(list) ? list.join("\n") : "");
