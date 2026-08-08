export type RoleKey = "student" | "teacher" | "admin";

export const apiBase = process.env.E2E_API_BASE || "http://localhost:8001";

export const testUsers = {
  student: {
    id: 101,
    name: "Estudiante E2E",
    email: process.env.E2E_STUDENT_EMAIL || "student.e2e@asofamech.local",
    password: process.env.E2E_STUDENT_PASS || "Student12345",
    role: "estudiante",
    roleLabel: "Estudiante",
  },
  teacher: {
    id: 102,
    name: "Docente E2E",
    email: process.env.E2E_TEACHER_EMAIL || "teacher.e2e@asofamech.local",
    password: process.env.E2E_TEACHER_PASS || "Teacher12345",
    role: "docente",
    roleLabel: "Profesor",
  },
  admin: {
    id: 103,
    name: "Admin E2E",
    email: process.env.E2E_ADMIN_EMAIL || "admin.e2e@asofamech.local",
    password: process.env.E2E_ADMIN_PASS || "Admin12345",
    role: "administrador",
    roleLabel: "Administrador",
  },
} as const;

export const dziImage = {
  id: 501,
  filename: "e2e-ganglio-dzi.png",
  title: "Lamina DZI E2E - ganglio linfatico",
  description: "Imagen DZI controlada para pruebas end-to-end.",
  pathology_type: "Histopatologia",
  file_type: "png",
  file_size: 1_048_576,
  has_dzi: true,
  created_at: "2026-05-24T10:00:00.000Z",
  uploader_name: "Docente E2E",
};

export const dziManifest = `<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008" TileSize="256" Overlap="0" Format="png">
  <Size Width="1024" Height="1024"/>
</Image>`;

export const pngTileBase64 =
  "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAWElEQVR4nO3PQQ0AIBDAMMC/5+ONAvZoFSzZnY0zQJU9gFgCwBJYAsASWALAEliCwBJYAsASWALAEliCwBJYAsASWALAEliCwBJYAsASWALAEliCwBJYAsASWALAEliCwBJYAsASWALAEliCwBJYAsASWALAEv4CZnkAwR62x4IAAAAASUVORK5CYII=";

export const heatmapFixture = {
  trace_id: "e2e-heatmap-trace",
  image_id: dziImage.id,
  tile_size: 512,
  tile_count: 4,
  persisted: true,
  analyzed_at: "2026-05-24T10:10:00.000Z",
  educational: {
    label: "Mapa docente E2E",
    type: "tumoral",
    note: "Heatmap preparado para validar la visualizacion.",
  },
  summary: {
    classified_metastatic_tiles: 1,
    max_tumor_score: 0.94,
    roi_decision: {
      status: "metastasis_probable",
      label: "Metastasis probable",
      summary: "Tile focal con alta probabilidad tumoral.",
      recommendation: "Usar el tile de mayor score como ROI 2.",
    },
    best_tile: {
      index: 1,
      tumor_score: 0.94,
      roi: { x: 256, y: 256, width: 256, height: 256 },
    },
  },
  tiles: [
    {
      index: 1,
      roi: { x: 256, y: 256, width: 256, height: 256 },
      tumor_score: 0.94,
      class: "metastasico",
      status: "completed",
    },
    {
      index: 2,
      roi: { x: 512, y: 256, width: 256, height: 256 },
      tumor_score: 0.18,
      class: "no_metastasico",
      status: "completed",
    },
  ],
};

export const roiSessionFixture = {
  id: 701,
  image_id: dziImage.id,
  image_title: dziImage.title,
  image_filename: dziImage.filename,
  trace_id: "e2e-roi-session",
  roi_1: { x: 120, y: 120, width: 720, height: 720 },
  roi_2: { x: 280, y: 280, width: 220, height: 220 },
  clase: "metastasico",
  status: "completed",
  confidence: 0.93,
  probabilities: {
    metastasico: 0.93,
    no_metastasico: 0.05,
    estroma: 0.02,
  },
  reason: "Clasificacion educativa E2E.",
  recommendation: "Correlacionar con morfologia y contexto docente.",
  analyzed_at: "2026-05-24T10:12:00.000Z",
};

export const aiPredictionFixture = {
  trace_id: "e2e-ai-prediction",
  status: "clasificado",
  clase: "metastasico",
  confidence: 0.93,
  probabilities: {
    metastasico: 0.93,
    no_metastasico: 0.05,
    estroma: 0.02,
  },
  prediction: {
    predicted_class: "metastasico",
    confidence: 0.93,
    probabilities: {
      metastasico: 0.93,
      no_metastasico: 0.05,
      estroma: 0.02,
    },
  },
  patch_metadata: { extracted_width: 220, extracted_height: 220 },
  slide_dimensions: { width: 1024, height: 1024 },
  warning: "Resultado educativo, no diagnostico.",
  analyzed_at: "2026-05-24T10:15:00.000Z",
};

export const publishedSct = {
  id: 801,
  name: "SCT E2E tuberculosis publicado",
  difficulty: "pregrado",
  focus: "tuberculosis pulmonar",
  num_items: 2,
  status: "published",
  created_at: "2026-05-24T09:00:00.000Z",
  created_by: testUsers.teacher.id,
};

export const publishedSctDetail = {
  ...publishedSct,
  items: [
    {
      id: 1,
      vignette: "Paciente de 35 anos con tos persistente, fiebre vespertina y perdida de peso.",
      hypothesis: "Tuberculosis pulmonar activa",
      new_info: "Baciloscopia de esputo positiva para BAAR.",
      scale_options: ["-2", "-1", "0", "+1", "+2"],
      correct_answer: 2,
      explanation: "La baciloscopia positiva apoya fuertemente tuberculosis activa.",
    },
    {
      id: 2,
      vignette: "Paciente con tos seca de 48 horas, sin fiebre ni baja de peso.",
      hypothesis: "Tuberculosis pulmonar activa",
      new_info: "PCR viral respiratoria positiva para influenza A.",
      scale_options: ["-2", "-1", "0", "+1", "+2"],
      correct_answer: -1,
      explanation: "Un diagnostico viral alternativo hace menos probable tuberculosis activa.",
    },
  ],
};

export const sctAttemptFixture = {
  id: 901,
  test_id: publishedSct.id,
  test_name: publishedSct.name,
  test_focus: publishedSct.focus,
  test_difficulty: publishedSct.difficulty,
  user_id: testUsers.student.id,
  score: 100,
  correct_count: 2,
  total_items: 2,
  completed_at: "2026-05-24T11:00:00.000Z",
};

export const ragDocumentFixture = {
  id: 301,
  document_id: 301,
  title: "Documento RAG fiebre E2E",
  source: "backend/data/rag/fiebre_documento_rag.md",
  document_type: "guia_docente",
  tags: ["fiebre", "infectologia"],
  score: 0.91,
  chunk_id: 12,
  chunk_index: 0,
  snippet: "La fiebre persistente debe contextualizarse con foco infeccioso, duracion y signos de alarma.",
};

export const chatRagResponse = {
  answer:
    "La fiebre persistente requiere evaluar duracion, foco probable y signos de alarma. En este caso se recomienda ordenar la informacion clinica y contrastarla con fuentes docentes.",
  messages: [
    {
      text:
        "La fiebre persistente requiere evaluar duracion, foco probable y signos de alarma. En este caso se recomienda ordenar la informacion clinica y contrastarla con fuentes docentes.",
    },
  ],
  message_type: "answer",
  used_rag: true,
  warning: "Contenido con finalidad educativa.",
  sources: [ragDocumentFixture],
  source_chunks: [ragDocumentFixture],
  rag_sources: [ragDocumentFixture],
};

export const dashboardStatsFixture = {
  chat: { total: 3, week: 1, daily: [0, 0, 1, 0, 1, 0, 1] },
  histo: { total: 2, week: 1, daily: [0, 0, 0, 1, 0, 0, 1] },
};

export const dashboardHistoryFixture = {
  user_id: testUsers.student.id,
  counts: { roi_sessions: 1, analyses: 1, sct_attempts: 1, conversations: 1, heatmaps: 1 },
  analyses: [roiSessionFixture],
  roi_sessions: [roiSessionFixture],
  sct_attempts: [sctAttemptFixture],
  conversations: [
    {
      id: 401,
      question: "fiebre persistente con sospecha infecciosa",
      used_rag: true,
      created_at: "2026-05-24T11:05:00.000Z",
    },
  ],
  heatmaps: [heatmapFixture],
};

export const clinicalCaseFixture = {
  id: 601,
  title: "Caso E2E: fiebre persistente",
  description: "Caso clinico publicado para navegacion.",
  body: "Paciente con fiebre persistente y estudio etiologico.",
  difficulty: "pregrado",
  topic: "infectologia",
  image_id: dziImage.id,
  sct_test_id: publishedSct.id,
  links: [
    {
      id: 9001,
      case_id: 601,
      kind: "wooclap",
      label: "Actividad interactiva del caso",
      url: "https://app.wooclap.com/EVENTOE2E",
      description: "Responde en vivo durante la clase",
      position: 0,
    },
    {
      id: 9002,
      case_id: 601,
      kind: "bibliografia",
      label: "Harrison, capitulo de fiebre de origen desconocido",
      url: "https://biblioteca.example.cl/harrison-fod",
      description: null,
      position: 1,
    },
  ],
  status: "published",
  created_at: "2026-05-24T08:00:00.000Z",
};

export const feedbackResponseFixture = {
  id: 1001,
  user_id: testUsers.student.id,
  role: "estudiante",
  nav_clarity: 5,
  viewer_ease: 4,
  roi_ease: 4,
  ai_clarity: 5,
  chatbot_utility: 5,
  sct_utility: 4,
  observations: "Flujo E2E claro y estable.",
  submitted_at: "2026-05-24T12:00:00.000Z",
};
