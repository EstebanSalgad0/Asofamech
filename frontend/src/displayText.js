const ACRONYMS = new Set([
  "AI",
  "CAMELYON17",
  "DZI",
  "IA",
  "JPG",
  "JPEG",
  "MB",
  "PNG",
  "ROI",
  "SCT",
  "HD",
  "SLN",
  "SVS",
  "TIF",
  "TIFF",
  "WSI",
]);

const WORD_LABELS = {
  cancer: "Cáncer",
  camelyon17: "CAMELYON17",
  cardiologia: "Cardiología",
  clasificacion: "Clasificación",
  diagnostico: "Diagnóstico",
  histologia: "Histología",
  histologico: "Histológico",
  histopatologia: "Histopatología",
  histopatologico: "Histopatológico",
  imagenes: "Imágenes",
  mama: "Mama",
  metastasis: "Metástasis",
  metastasico: "Metastásico",
  micro: "Micro",
  negativo: "Negativo",
  node: "Node",
  patient: "Patient",
  positivo: "Positivo",
  test: "Test",
  testeo: "Testeo",
};

function normalizeWhitespace(value) {
  return String(value || "")
    .replace(/\.[a-z0-9]{2,5}$/i, "")
    .replace(/([a-záéíóúñ])(\d)/gi, "$1 $2")
    .replace(/(\d)([a-záéíóúñ])/gi, "$1 $2")
    .replace(/camelyon\s*17/gi, " CAMELYON17 ")
    .replace(/(metastasis|cancer|camelyon17|patient|node|negativo|positivo|macro|micro|mama|hd)/gi, " $1 ")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function formatWord(word, index) {
  if (!word) return "";
  const clean = word.trim();
  const upper = clean.toUpperCase();
  const lower = clean.toLowerCase();
  if (ACRONYMS.has(upper)) return upper;
  if (/^\d+$/.test(clean)) return clean;
  if (WORD_LABELS[lower]) return WORD_LABELS[lower];
  if (index > 0 && clean.length <= 2) return lower;
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

export function formatDisplayTitle(value, fallback = "Sin título") {
  const normalized = normalizeWhitespace(value);
  if (!normalized) return fallback;
  return normalized
    .split(" ")
    .map(formatWord)
    .filter(Boolean)
    .join(" ");
}

export function formatDisplayTag(value) {
  return formatDisplayTitle(value, "");
}

export function formatImageDisplayName(image) {
  return formatDisplayTitle(image?.title || image?.original_filename || image?.filename, "Imagen sin título");
}

export function formatFileType(value) {
  return String(value || "").replace(/^\./, "").toUpperCase();
}

export function formatFileSizeMB(bytes) {
  const size = Number(bytes);
  if (!Number.isFinite(size) || size <= 0) return "";
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}
