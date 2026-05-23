import { authErrorMessage, authFetch } from "./authClient";

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
  return parseJsonResponse(res, "No se pudo cargar la configuracion IA");
}

export async function updateAIConfig(items) {
  const res = await authFetch("/api/admin/ai-config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  return parseJsonResponse(res, "No se pudo guardar la configuracion IA");
}

export async function getIntegrationStatus() {
  const res = await authFetch("/api/admin/integrations/status");
  return parseJsonResponse(res, "No se pudo verificar la integracion IA");
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
