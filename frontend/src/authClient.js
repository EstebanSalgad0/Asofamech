// En Docker el entrypoint inyecta window.__ASOFAMECH_CONFIG__ en runtime.
// En dev local se usa VITE_API_BASE de .env.local como fallback.
const runtimeApiBase =
  typeof window !== "undefined" && window.__ASOFAMECH_CONFIG__
    ? window.__ASOFAMECH_CONFIG__.API_BASE
    : undefined;

export const API_BASE =
  runtimeApiBase !== undefined
    ? runtimeApiBase
    : import.meta.env.VITE_API_BASE || "http://localhost:8001";

const TOKEN_KEY = "auth_token";
const USER_KEY = "user";
const ROLE_KEY = "role";

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

const _ROLE_DISPLAY = { administrador: "Administrador", docente: "Profesor", estudiante: "Estudiante" };
const _ROLE_NORMALIZED = { administrador: "administrador", admin: "administrador", administrator: "administrador", profesor: "docente", profesora: "docente", docente: "docente", teacher: "docente", estudiante: "estudiante", student: "estudiante" };

function _getRoleFromToken() {
  const token = getAuthToken();
  if (!token) return null;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    return _ROLE_DISPLAY[payload.role] || null;
  } catch {
    return null;
  }
}

export function getStoredRole() {
  return _getRoleFromToken() || getStoredUser()?.role_label || localStorage.getItem(ROLE_KEY) || "Estudiante";
}

export function normalizeRole(role) {
  const value = String(role || "").trim().toLowerCase();
  return _ROLE_NORMALIZED[value] || "estudiante";
}

export function hasAnyRole(role, allowedRoles) {
  const normalized = normalizeRole(role);
  return allowedRoles.map(normalizeRole).includes(normalized);
}

export function canManageEducationalContent(role = getStoredRole()) {
  return hasAnyRole(role, ["docente", "administrador"]);
}

export function canManageAdminSettings(role = getStoredRole()) {
  return hasAnyRole(role, ["administrador"]);
}

export function authErrorMessage(status, fallback = "No se pudo completar la accion") {
  if (status === 401) return "Sesion expirada o no autenticada. Vuelve a iniciar sesion.";
  if (status === 403) return "No tienes permisos para realizar esta accion.";
  return fallback;
}

export function getUserStorageScope(user = getStoredUser()) {
  if (user?.id) return `user_${user.id}`;
  if (user?.email) return `email_${String(user.email).trim().toLowerCase().replace(/[^a-z0-9._-]/g, "_")}`;
  return "anonymous";
}

export function userStorageKey(baseKey) {
  return `${baseKey}:${getUserStorageScope()}`;
}

export function saveAuthSession(payload) {
  const user = payload?.user;
  if (!payload?.access_token || !user) {
    throw new Error("Respuesta de autenticacion incompleta");
  }
  localStorage.setItem(TOKEN_KEY, payload.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  localStorage.setItem(ROLE_KEY, user.role_label || "Estudiante");
}

export function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function authHeaders(extra = {}) {
  const token = getAuthToken();
  return {
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function authFetch(pathOrUrl, options = {}) {
  const url = pathOrUrl.startsWith("http") ? pathOrUrl : `${API_BASE}${pathOrUrl}`;
  const res = await fetch(url, {
    ...options,
    headers: authHeaders(options.headers || {}),
  });
  if (res.status === 401) {
    clearAuthSession();
    window.location.href = "/auth";
  }
  return res;
}
