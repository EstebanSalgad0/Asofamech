import { authFetch, authHeaders } from "./authClient";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8001";

export async function sendChatMessage(text) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    throw new Error(`Error API: ${res.status}`);
  }

  return res.json(); // { messages: [...] } desde FastAPI → Ollama
}

async function parseJsonResponse(res, fallback) {
  const payload = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(payload?.detail || fallback || `Error API: ${res.status}`);
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

export async function generateSCT(numItems = 5, difficulty = "pregrado", focus = "tuberculosis pulmonar") {
  const res = await fetch(`${API_BASE}/api/sct/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ 
      num_items: numItems,
      difficulty: difficulty,
      focus: focus
    }),
  });

  if (!res.ok) {
    throw new Error(`Error API SCT: ${res.status}`);
  }

  return res.json();
}

export async function getExampleSCT() {
  const res = await fetch(`${API_BASE}/api/sct/example`);
  
  if (!res.ok) {
    throw new Error(`Error API SCT Example: ${res.status}`);
  }

  return res.json();
}

export async function saveSCTTest(name, difficulty, focus, numItems, items) {
  const res = await fetch(`${API_BASE}/api/sct/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      difficulty,
      focus,
      num_items: numItems,
      items
    }),
  });

  if (!res.ok) {
    throw new Error(`Error API SCT Save: ${res.status}`);
  }

  return res.json();
}

export async function listSCTTests() {
  const res = await fetch(`${API_BASE}/api/sct/list`);
  
  if (!res.ok) {
    throw new Error(`Error API SCT List: ${res.status}`);
  }

  return res.json();
}

export async function getSCTTest(testId) {
  const res = await fetch(`${API_BASE}/api/sct/${testId}`);
  
  if (!res.ok) {
    throw new Error(`Error API SCT Get: ${res.status}`);
  }

  return res.json();
}

export async function deleteSCTTest(testId) {
  const res = await fetch(`${API_BASE}/api/sct/${testId}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    throw new Error(`Error API SCT Delete: ${res.status}`);
  }

  return res.json();
}
