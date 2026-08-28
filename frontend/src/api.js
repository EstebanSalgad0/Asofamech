import { API_BASE, authErrorMessage, authFetch } from "./authClient";

export async function sendChatMessage(text) {
  const res = await authFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    throw new Error(authErrorMessage(res.status, `Error API: ${res.status}`));
  }

  return res.json(); // { messages: [...] } desde FastAPI → Ollama
}

async function parseJsonResponse(res, fallback) {
  const payload = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(payload?.detail || authErrorMessage(res.status, fallback || `Error API: ${res.status}`));
  }
  return payload;
}

export async function listRagDocuments() {
  const res = await authFetch("/api/rag/documents");
  return parseJsonResponse(res, "No se pudieron cargar los documentos RAG");
}

export async function createRagDocument(document) {
  const res = await authFetch("/api/rag/documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(document),
  });
  return parseJsonResponse(res, "No se pudo crear el documento RAG");
}

export async function uploadRagDocument(formData) {
  const res = await authFetch("/api/rag/documents/upload", {
    method: "POST",
    body: formData,
  });
  return parseJsonResponse(res, "No se pudo cargar el archivo RAG");
}

export async function updateRagDocument(documentId, document) {
  const res = await authFetch(`/api/rag/documents/${documentId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(document),
  });
  return parseJsonResponse(res, "No se pudo actualizar el documento RAG");
}

export async function deleteRagDocument(documentId) {
  const res = await authFetch(`/api/rag/documents/${documentId}`, { method: "DELETE" });
  return parseJsonResponse(res, "No se pudo eliminar el documento RAG");
}

export async function reindexRagDocument(documentId) {
  const res = await authFetch(`/api/rag/documents/${documentId}/reindex`, { method: "POST" });
  return parseJsonResponse(res, "No se pudo reindexar el documento RAG");
}

export async function reindexAllRagDocuments() {
  const res = await authFetch("/api/rag/reindex", { method: "POST" });
  return parseJsonResponse(res, "No se pudo reindexar el corpus RAG");
}

export async function searchRagDocuments(query, limit = 4) {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  const res = await authFetch(`/api/rag/search?${params.toString()}`);
  return parseJsonResponse(res, "No se pudo buscar en el corpus RAG");
}

export async function getAIConfig() {
  const res = await authFetch("/api/admin/ai-config");
  return parseJsonResponse(res, "No se pudo cargar la configuración IA");
}

export async function updateAIConfig(items) {
  const res = await authFetch("/api/admin/ai-config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  return parseJsonResponse(res, "No se pudo guardar la configuración IA");
}

/** Genera una respuesta minima con el proveedor guardado para validar credencial y modelo. */
export async function testLLMProvider() {
  const res = await authFetch("/api/admin/llm/test", { method: "POST" });
  return parseJsonResponse(res, "No se pudo probar el proveedor de IA");
}

export async function getIntegrationStatus({ refresh = false } = {}) {
  const qs = refresh ? "?refresh=true" : "";
  const res = await authFetch(`/api/admin/integrations/status${qs}`);
  return parseJsonResponse(res, "No se pudo verificar la integracion IA");
}

export async function getLlmUsageSummary(window = "30d") {
  const res = await authFetch(`/api/admin/llm/usage/summary?window=${encodeURIComponent(window)}`);
  return parseJsonResponse(res, "No se pudo cargar el consumo del LLM");
}

export async function getLlmUsageRecent(limit = 50) {
  const res = await authFetch(`/api/admin/llm/usage/recent?limit=${limit}`);
  return parseJsonResponse(res, "No se pudieron cargar las últimas llamadas");
}

export async function downloadLlmUsageCsv(window = "30d") {
  const res = await authFetch(`/api/admin/llm/usage/export.csv?window=${encodeURIComponent(window)}`);
  if (!res.ok) throw new Error(`Error al exportar CSV (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `llm_usage_${window}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function listAdminUsers(filters = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.role) params.set("role", filters.role);
  if (filters.q) params.set("q", filters.q);
  const query = params.toString();
  const res = await authFetch(`/api/admin/users${query ? `?${query}` : ""}`);
  return parseJsonResponse(res, "No se pudieron cargar los usuarios");
}

export async function createAdminUser(payload) {
  const res = await authFetch("/api/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo crear el usuario");
}

export async function updateAdminUser(userId, payload) {
  const res = await authFetch(`/api/admin/users/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo actualizar el usuario");
}

export async function approveAdminUser(userId, payload = {}) {
  const res = await authFetch(`/api/admin/users/${userId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo aprobar el usuario");
}

export async function rejectAdminUser(userId) {
  const res = await authFetch(`/api/admin/users/${userId}/reject`, { method: "POST" });
  return parseJsonResponse(res, "No se pudo rechazar el usuario");
}

export async function deleteAdminUser(userId) {
  const res = await authFetch(`/api/admin/users/${userId}`, { method: "DELETE" });
  return parseJsonResponse(res, "No se pudo eliminar el usuario");
}

export async function listAuditLogs(filters = {}) {
  const params = new URLSearchParams();
  if (filters.actor_id) params.set("actor_id", String(filters.actor_id));
  if (filters.action) params.set("action", filters.action);
  if (filters.target_type) params.set("target_type", filters.target_type);
  if (filters.target_id) params.set("target_id", String(filters.target_id));
  if (filters.limit) params.set("limit", String(filters.limit));
  const query = params.toString();
  const res = await authFetch(`/api/admin/audit-logs${query ? `?${query}` : ""}`);
  return parseJsonResponse(res, "No se pudo cargar la auditoria");
}

export async function getDashboardStats() {
  const res = await authFetch("/api/dashboard/stats");
  return parseJsonResponse(res, "No se pudieron cargar las estadísticas");
}

export async function getDashboardRanking() {
  const res = await authFetch("/api/dashboard/ranking");
  return parseJsonResponse(res, "No se pudo cargar el ranking");
}

export async function getMyHistory(limit = 10) {
  const params = new URLSearchParams({ limit: String(limit) });
  const res = await authFetch(`/api/history/me?${params.toString()}`);
  return parseJsonResponse(res, "No se pudo cargar el historial");
}

export async function generateSCT(numItems = 5, difficulty = "pregrado", focus = "tuberculosis pulmonar") {
  const res = await authFetch("/api/sct/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ num_items: numItems, difficulty, focus }),
  });
  return parseJsonResponse(res, "Error al generar el test SCT");
}

export async function getExampleSCT() {
  const res = await authFetch("/api/sct/example");
  return parseJsonResponse(res, "Error al cargar el test de ejemplo");
}

export async function saveSCTTest(name, difficulty, focus, numItems, items) {
  const res = await authFetch("/api/sct/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, difficulty, focus, num_items: numItems, items }),
  });
  return parseJsonResponse(res, "No se pudo guardar el test SCT");
}

export async function listSCTTests() {
  const res = await authFetch("/api/sct/list");
  return parseJsonResponse(res, "No se pudieron cargar los tests SCT");
}

export async function getSCTTest(testId) {
  const res = await authFetch(`/api/sct/${testId}`);
  return parseJsonResponse(res, "No se pudo cargar el test SCT");
}

export async function deleteSCTTest(testId) {
  const res = await authFetch(`/api/sct/${testId}`, { method: "DELETE" });
  return parseJsonResponse(res, "No se pudo eliminar el test SCT");
}

export async function submitSCTAttempt(testId, answers, startedAt = null) {
  const res = await authFetch(`/api/sct/${testId}/attempt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers, started_at: startedAt }),
  });
  if (!res.ok) throw new Error(`Error SCT Attempt: ${res.status}`);
  return res.json();
}

export async function listMyAttempts() {
  const res = await authFetch("/api/sct/my-attempts");
  return parseJsonResponse(res, "No se pudo cargar el historial de intentos");
}

export async function listAllAttempts() {
  const res = await authFetch("/api/sct/admin/attempts");
  return parseJsonResponse(res, "No se pudo cargar los intentos de estudiantes");
}

export async function updateSCTTest(testId, updates) {
  const res = await authFetch(`/api/sct/${testId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  return parseJsonResponse(res, "No se pudo actualizar el test");
}

export async function importMCQFile(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await authFetch("/api/mcq/import", { method: "POST", body: form });
  return parseJsonResponse(res, "No se pudo importar el archivo de preguntas");
}

export async function saveMCQTest(name, topic, difficulty, numItems, items, status = "published") {
  const res = await authFetch("/api/mcq/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, topic, difficulty, num_items: numItems, items, status }),
  });
  return parseJsonResponse(res, "No se pudo guardar el test de alternativas");
}

export async function listMCQTests() {
  const res = await authFetch("/api/mcq/list");
  return parseJsonResponse(res, "No se pudieron cargar los tests de alternativas");
}

export async function getMCQTest(testId) {
  const res = await authFetch(`/api/mcq/${testId}`);
  return parseJsonResponse(res, "No se pudo cargar el test de alternativas");
}

export async function deleteMCQTest(testId) {
  const res = await authFetch(`/api/mcq/${testId}`, { method: "DELETE" });
  return parseJsonResponse(res, "No se pudo eliminar el test de alternativas");
}

export async function submitMCQAttempt(testId, answers, startedAt = null) {
  const res = await authFetch(`/api/mcq/${testId}/attempt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers, started_at: startedAt }),
  });
  if (!res.ok) throw new Error(`Error MCQ Attempt: ${res.status}`);
  return res.json();
}

export async function listMyMCQAttempts() {
  const res = await authFetch("/api/mcq/my-attempts");
  return parseJsonResponse(res, "No se pudo cargar el historial de intentos");
}

export async function listAllMCQAttempts() {
  const res = await authFetch("/api/mcq/admin/attempts");
  return parseJsonResponse(res, "No se pudieron cargar los intentos de estudiantes");
}

export async function updateMCQTest(testId, updates) {
  const res = await authFetch(`/api/mcq/${testId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  return parseJsonResponse(res, "No se pudo actualizar el test");
}

export async function listMyRoiSessions(limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) });
  const res = await authFetch(`/api/history/roi-sessions?${params.toString()}`);
  return parseJsonResponse(res, "No se pudo cargar el historial de sesiones ROI");
}

export async function getRoiSession(sessionId) {
  const res = await authFetch(`/api/histopathology/sessions/${sessionId}`);
  return parseJsonResponse(res, "No se pudo cargar la sesión ROI");
}

export async function listMedicalImages() {
  const res = await authFetch("/api/medical-images/list");
  return parseJsonResponse(res, "No se pudieron cargar las imágenes médicas");
}

export async function listDiseaseCategories() {
  const res = await authFetch("/api/disease-categories");
  return parseJsonResponse(res, "No se pudieron cargar las categorías de enfermedades");
}

export async function createDiseaseCategory(payload) {
  const res = await authFetch("/api/disease-categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo crear la categoría");
}

export async function updateDiseaseCategory(categoryId, updates) {
  const res = await authFetch(`/api/disease-categories/${categoryId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  return parseJsonResponse(res, "No se pudo actualizar la categoría");
}

export async function deleteDiseaseCategory(categoryId) {
  const res = await authFetch(`/api/disease-categories/${categoryId}`, { method: "DELETE" });
  return parseJsonResponse(res, "No se pudo eliminar la categoría");
}

export async function listCases(filters = {}) {
  const params = new URLSearchParams();
  if (filters.topic) params.set("topic", filters.topic);
  if (filters.difficulty) params.set("difficulty", filters.difficulty);
  if (filters.status) params.set("status", filters.status);
  const query = params.toString();
  const res = await authFetch(`/api/cases${query ? `?${query}` : ""}`);
  return parseJsonResponse(res, "No se pudieron cargar los casos clínicos");
}

export async function searchCases(q, filters = {}) {
  const params = new URLSearchParams({ q: q || "" });
  if (filters.topic) params.set("topic", filters.topic);
  if (filters.difficulty) params.set("difficulty", filters.difficulty);
  const res = await authFetch(`/api/cases/search?${params.toString()}`);
  return parseJsonResponse(res, "No se pudo buscar casos clínicos");
}

export async function getCase(caseId) {
  const res = await authFetch(`/api/cases/${caseId}`);
  return parseJsonResponse(res, "No se pudo cargar el caso clínico");
}

export async function createCase(payload) {
  const res = await authFetch("/api/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo crear el caso clínico");
}

export async function updateCase(caseId, payload) {
  const res = await authFetch(`/api/cases/${caseId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo actualizar el caso clínico");
}

export async function updateCaseStatus(caseId, status) {
  const res = await authFetch(`/api/cases/${caseId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return parseJsonResponse(res, "No se pudo cambiar el estado del caso");
}

export async function deleteCase(caseId) {
  const res = await authFetch(`/api/cases/${caseId}`, { method: "DELETE" });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || `Error al eliminar el caso (${res.status})`);
  }
}

/**
 * Sube un documento y devuelve la propuesta de caso clínico. No guarda nada:
 * el docente revisa la estructura en el editor antes de crear el caso.
 */
export async function importCaseFromFile(formData) {
  const res = await authFetch("/api/cases/import", {
    method: "POST",
    body: formData,
  });
  return parseJsonResponse(res, "No se pudo interpretar el documento del caso clínico");
}

export async function listCaseImages(caseId) {
  const res = await authFetch(`/api/cases/${caseId}/images`);
  return parseJsonResponse(res, "No se pudieron cargar las imagenes del caso");
}

export async function uploadCaseImages(caseId, formData) {
  const res = await authFetch(`/api/cases/${caseId}/images`, {
    method: "POST",
    body: formData,
  });
  return parseJsonResponse(res, "No se pudieron subir las imagenes del caso");
}

export async function deleteCaseImage(imageId) {
  const res = await authFetch(`/api/cases/images/${imageId}`, { method: "DELETE" });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || `Error al eliminar la imagen (${res.status})`);
  }
}

// ============ Encuestas de percepción ============

export async function listSurveys() {
  const res = await authFetch("/api/surveys");
  return parseJsonResponse(res, "No se pudieron cargar las encuestas");
}

export async function listAllSurveysAdmin() {
  const res = await authFetch("/api/surveys/admin/all");
  return parseJsonResponse(res, "No se pudieron cargar las encuestas");
}

export async function getSurvey(code) {
  const res = await authFetch(`/api/surveys/${encodeURIComponent(code)}`);
  return parseJsonResponse(res, "No se pudo cargar la encuesta");
}

export async function submitSurveyResponse(code, answers) {
  const res = await authFetch(`/api/surveys/${encodeURIComponent(code)}/responses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  return parseJsonResponse(res, "No se pudo enviar la encuesta");
}

export async function updateSurveyStatus(code, status) {
  const res = await authFetch(`/api/surveys/${encodeURIComponent(code)}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return parseJsonResponse(res, "No se pudo actualizar el estado");
}

export async function getSurveySummary(code) {
  const res = await authFetch(`/api/surveys/${encodeURIComponent(code)}/summary`);
  return parseJsonResponse(res, "No se pudo cargar el resumen");
}

export async function getSurveyOpenAnswers(code) {
  const res = await authFetch(`/api/surveys/${encodeURIComponent(code)}/open-answers`);
  return parseJsonResponse(res, "No se pudieron cargar las respuestas abiertas");
}

export async function getSurveyWordCloud(code) {
  const res = await authFetch(`/api/surveys/${encodeURIComponent(code)}/word-cloud`);
  return parseJsonResponse(res, "No se pudo cargar la nube de palabras");
}

export async function downloadSurveyCsv(code) {
  const res = await authFetch(`/api/surveys/${encodeURIComponent(code)}/export.csv`);
  if (!res.ok) throw new Error(`Error al exportar CSV (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `encuesta_${code}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function requestPasswordReset(email) {
  const res = await fetch(`${API_BASE}/api/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  const payload = await res.json().catch(() => null);
  if (!res.ok) throw new Error(payload?.detail || "Error al procesar la solicitud");
  return payload;
}

export async function confirmPasswordReset(token, newPassword) {
  const res = await fetch(`${API_BASE}/api/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  const payload = await res.json().catch(() => null);
  if (!res.ok) throw new Error(payload?.detail || "Error al restablecer la contraseña");
  return payload;
}

// ============ Revisor de informes por rúbrica ============

export async function listRubrics(filters = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.caseId) params.set("case_id", filters.caseId);
  const query = params.toString();
  const res = await authFetch(`/api/reports/rubrics${query ? `?${query}` : ""}`);
  return parseJsonResponse(res, "No se pudieron cargar las rúbricas");
}

export async function getRubric(rubricId) {
  const res = await authFetch(`/api/reports/rubrics/${rubricId}`);
  return parseJsonResponse(res, "No se pudo cargar la rúbrica");
}

/** Por estudiante: intentos usados de esta rúbrica y su nota más reciente (0-100). */
export async function getRubricProgress(rubricId) {
  const res = await authFetch(`/api/reports/rubrics/${rubricId}/progress`);
  return parseJsonResponse(res, "No se pudo cargar el progreso de la rúbrica");
}

/** Sube el documento de la rúbrica y devuelve la propuesta extraída por la IA. */
export async function extractRubricFromFile(formData) {
  const res = await authFetch("/api/reports/rubrics/extract", {
    method: "POST",
    body: formData,
  });
  return parseJsonResponse(res, "No se pudo interpretar el documento de la rúbrica");
}

export async function createRubric(payload) {
  const res = await authFetch("/api/reports/rubrics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo crear la rúbrica");
}

export async function updateRubric(rubricId, payload) {
  const res = await authFetch(`/api/reports/rubrics/${rubricId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo actualizar la rúbrica");
}

export async function updateRubricStatus(rubricId, status) {
  const res = await authFetch(`/api/reports/rubrics/${rubricId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return parseJsonResponse(res, "No se pudo cambiar el estado de la rúbrica");
}

export async function deleteRubric(rubricId) {
  const res = await authFetch(`/api/reports/rubrics/${rubricId}`, { method: "DELETE" });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || `Error al eliminar la rúbrica (${res.status})`);
  }
}

export async function submitReport(formData) {
  const res = await authFetch("/api/reports/submissions", {
    method: "POST",
    body: formData,
  });
  return parseJsonResponse(res, "No se pudo enviar el informe");
}

export async function listMyReportSubmissions() {
  const res = await authFetch("/api/reports/submissions/mine");
  return parseJsonResponse(res, "No se pudieron cargar tus entregas");
}

export async function listReportSubmissions(filters = {}) {
  const params = new URLSearchParams();
  if (filters.rubricId) params.set("rubric_id", filters.rubricId);
  if (filters.caseId) params.set("case_id", filters.caseId);
  if (filters.status) params.set("status", filters.status);
  const query = params.toString();
  const res = await authFetch(`/api/reports/submissions${query ? `?${query}` : ""}`);
  return parseJsonResponse(res, "No se pudieron cargar las entregas");
}

export async function reevaluateReport(submissionId) {
  const res = await authFetch(`/api/reports/submissions/${submissionId}/evaluate`, {
    method: "POST",
  });
  return parseJsonResponse(res, "No se pudo reevaluar el informe");
}

export async function releaseReportEvaluation(submissionId, payload) {
  const res = await authFetch(`/api/reports/submissions/${submissionId}/release`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo actualizar la visibilidad de la evaluación");
}

export async function deleteReportSubmission(submissionId) {
  const res = await authFetch(`/api/reports/submissions/${submissionId}`, { method: "DELETE" });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || `Error al eliminar la entrega (${res.status})`);
  }
}

export async function downloadReportFile(submissionId, filename) {
  const res = await authFetch(`/api/reports/submissions/${submissionId}/file`);
  if (!res.ok) throw new Error(`Error al descargar el informe (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `informe_${submissionId}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ============ Anotaciones docentes sobre imágenes ============
// Independientes del clasificador: un rectángulo con texto sobre una región de
// la imagen. Nunca disparan ni requieren el pipeline de IA.

export async function listImageAnnotations(imageId) {
  const res = await authFetch(`/api/medical-images/${imageId}/annotations`);
  return parseJsonResponse(res, "No se pudieron cargar las anotaciones");
}

export async function createImageAnnotation(imageId, payload) {
  const res = await authFetch(`/api/medical-images/${imageId}/annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo crear la anotación");
}

export async function updateImageAnnotation(annotationId, payload) {
  const res = await authFetch(`/api/medical-images/annotations/${annotationId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(res, "No se pudo actualizar la anotación");
}

export async function deleteImageAnnotation(annotationId) {
  const res = await authFetch(`/api/medical-images/annotations/${annotationId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.detail || `Error al eliminar la anotación (${res.status})`);
  }
}
