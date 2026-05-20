export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8001";

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
  return fetch(url, {
    ...options,
    headers: authHeaders(options.headers || {}),
  });
}
