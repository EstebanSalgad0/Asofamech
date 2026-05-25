const fs = require('fs');
const path = require('path');

const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8001';
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin.e2e@asofamech.local';
const ADMIN_PASS = process.env.E2E_ADMIN_PASS || 'Admin12345';
const STUDENT_EMAIL = process.env.E2E_STUDENT_EMAIL || 'student.e2e@asofamech.local';
const STUDENT_PASS = process.env.E2E_STUDENT_PASS || 'Student12345';

const AUTH_DIR = path.join(__dirname, '.auth');

async function apiPost(endpoint, body, token = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => null);
    return { ok: res.ok, status: res.status, data };
  } catch (err) {
    return { ok: false, status: 0, data: null, error: err.message };
  }
}

async function apiGet(endpoint, token) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    const data = await res.json().catch(() => null);
    return { ok: res.ok, data };
  } catch {
    return { ok: false, data: null };
  }
}

async function tryLogin(email, password) {
  const { ok, data } = await apiPost('/api/auth/login', { email, password });
  return ok && data?.access_token ? data : null;
}

async function tryRegister(name, email, password, role = 'estudiante') {
  const { ok, data } = await apiPost('/api/auth/register', { name, email, password, role });
  return ok ? data : null;
}

async function findAndApproveUser(adminToken, email) {
  const { ok, data } = await apiGet(`/api/admin/users?q=${encodeURIComponent(email)}`, adminToken);
  if (!ok || !data) return false;
  // Endpoint returns either an array or { users: [...] }
  const list = Array.isArray(data) ? data : (Array.isArray(data.users) ? data.users : []);
  const user = list.find(u => u.email === email);
  if (!user) return false;
  const { ok: approved } = await apiPost(`/api/admin/users/${user.id}/approve`, {}, adminToken);
  return approved;
}

function saveState(filename, token, userJson, role) {
  fs.writeFileSync(
    path.join(AUTH_DIR, filename),
    JSON.stringify({ auth_token: token, user: userJson, role }),
  );
}

function saveEmptyState(filename) {
  fs.writeFileSync(
    path.join(AUTH_DIR, filename),
    JSON.stringify({ auth_token: null, user: null, role: null }),
  );
}

module.exports = async function globalSetup() {
  fs.mkdirSync(AUTH_DIR, { recursive: true });

  // ── Check backend is reachable ──────────────────────────────────────────
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`Backend health check failed: ${res.status}`);
  } catch (err) {
    console.warn(`\n[E2E] WARNING: Backend not reachable at ${API_BASE}.`);
    console.warn('[E2E] Start the backend before running E2E tests.');
    console.warn('[E2E] Auth state files will be empty — tests requiring auth will skip.\n');
    saveEmptyState('admin.json');
    saveEmptyState('student.json');
    return;
  }

  // ── Admin user ───────────────────────────────────────────────────────────
  let adminSession = await tryLogin(ADMIN_EMAIL, ADMIN_PASS);

  if (!adminSession) {
    console.log('[E2E] Admin not found — attempting registration...');
    const regData = await tryRegister('Admin E2E', ADMIN_EMAIL, ADMIN_PASS, 'administrador');
    if (regData?.access_token) {
      adminSession = regData;
      console.log('[E2E] Admin auto-approved as first user');
    } else {
      console.warn('[E2E] Could not create admin. Provide existing credentials via env vars:');
      console.warn(`[E2E]   E2E_ADMIN_EMAIL / E2E_ADMIN_PASS (current: ${ADMIN_EMAIL})`);
      saveEmptyState('admin.json');
      saveEmptyState('student.json');
      return;
    }
  }

  const adminUserObj = adminSession.user || { email: ADMIN_EMAIL, name: 'Admin E2E' };
  saveState('admin.json', adminSession.access_token, JSON.stringify(adminUserObj), 'Administrador');
  console.log('[E2E] Admin auth state saved');

  // ── Student user ─────────────────────────────────────────────────────────
  let studentSession = await tryLogin(STUDENT_EMAIL, STUDENT_PASS);

  if (!studentSession) {
    console.log('[E2E] Student not found — attempting registration...');
    const regData = await tryRegister('Student E2E', STUDENT_EMAIL, STUDENT_PASS, 'estudiante');
    if (regData?.access_token) {
      studentSession = regData;
    } else {
      // Pending account — approve it as admin
      console.log('[E2E] Student pending approval — approving via admin...');
      const approved = await findAndApproveUser(adminSession.access_token, STUDENT_EMAIL);
      if (approved) {
        studentSession = await tryLogin(STUDENT_EMAIL, STUDENT_PASS);
      }
    }
  }

  if (studentSession) {
    const studentUserObj = studentSession.user || { email: STUDENT_EMAIL, name: 'Student E2E' };
    saveState('student.json', studentSession.access_token, JSON.stringify(studentUserObj), 'Estudiante');
    console.log('[E2E] Student auth state saved');
  } else {
    console.warn('[E2E] Could not set up student user — student-specific tests will skip');
    saveEmptyState('student.json');
  }
};
