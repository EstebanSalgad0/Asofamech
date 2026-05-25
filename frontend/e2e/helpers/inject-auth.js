const fs = require('fs');
const path = require('path');

function loadAuthState(role = 'admin') {
  const file = path.join(__dirname, '..', '.auth', `${role}.json`);
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return { auth_token: null, user: null, role: null };
  }
}

/** Inject localStorage auth state and navigate to a URL.
 *  Returns false (and skips) if no valid token is available. */
async function injectAuthAndGo(page, test, url, role = 'admin') {
  const state = loadAuthState(role);
  if (!state.auth_token) {
    test.skip(true, `Auth state for "${role}" not available. Run global-setup first.`);
    return false;
  }
  // Navigate to a blank page on the same origin first so localStorage is writable
  await page.goto('/auth', { waitUntil: 'domcontentloaded' });
  await page.evaluate((s) => {
    localStorage.setItem('auth_token', s.auth_token);
    localStorage.setItem('user', s.user);
    localStorage.setItem('role', s.role);
  }, state);
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  return true;
}

module.exports = { loadAuthState, injectAuthAndGo };
