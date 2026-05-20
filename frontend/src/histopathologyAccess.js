import { authHeaders, getStoredRole } from "./authClient";

const CLIENT_ID_KEY = "asofamech_histopathology_client_id";

export const PRIVILEGED_HEATMAP_MAX_TILES = 128;
export const STUDENT_HEATMAP_MAX_TILES = 128;

export function normalizeRole(role) {
  const value = (role || "").trim().toLowerCase();
  if (["administrador", "admin", "administrator"].includes(value)) return "administrador";
  if (["profesor", "profesora", "docente", "teacher"].includes(value)) return "profesor";
  return "estudiante";
}

export function currentRole() {
  return getStoredRole();
}

export function isPrivilegedRole(role = currentRole()) {
  return ["administrador", "profesor"].includes(normalizeRole(role));
}

export function heatmapMaxTilesForCurrentRole() {
  return isPrivilegedRole() ? PRIVILEGED_HEATMAP_MAX_TILES : STUDENT_HEATMAP_MAX_TILES;
}

export function histopathologyClientId() {
  let clientId = localStorage.getItem(CLIENT_ID_KEY);
  if (!clientId) {
    clientId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(CLIENT_ID_KEY, clientId);
  }
  return clientId;
}

export function histopathologyHeaders(extra = {}) {
  return authHeaders({
    ...extra,
    "X-Asofamech-Role": currentRole(),
    "X-Asofamech-Client-Id": histopathologyClientId(),
  });
}
