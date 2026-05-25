const { test, expect } = require('@playwright/test');

const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8001';
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin.e2e@asofamech.local';
const ADMIN_PASS = process.env.E2E_ADMIN_PASS || 'Admin12345';

test.describe('Autenticación', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any existing session before each auth test
    await page.goto('/auth', { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => localStorage.clear());
  });

  test('carga la página de login correctamente', async ({ page }) => {
    await page.goto('/auth');
    await expect(page).toHaveTitle(/ASOFAMECH/i);
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Iniciar sesión' })).toBeVisible();
  });

  test('muestra error con credenciales incorrectas', async ({ page }) => {
    await page.goto('/auth');
    await page.fill('#email', 'noexiste@test.com');
    await page.fill('#password', 'wrongpassword1');
    await page.getByRole('button', { name: 'Iniciar sesión' }).click();
    // Wait for error message to appear
    const errorEl = page.locator('.auth-error');
    await expect(errorEl).toBeVisible({ timeout: 10_000 });
    const errorText = await errorEl.textContent();
    expect(errorText.length).toBeGreaterThan(0);
  });

  test('login exitoso redirige al dashboard', async ({ page }) => {
    // This test requires valid credentials. It runs only if global-setup
    // successfully created/found the test admin user.
    const { loadAuthState } = require('./helpers/inject-auth');
    const state = loadAuthState('admin');
    test.skip(!state.auth_token, 'Admin E2E no configurado — provee credenciales válidas via E2E_ADMIN_EMAIL / E2E_ADMIN_PASS');

    await page.goto('/auth');
    await page.fill('#name', 'Admin E2E');
    await page.fill('#email', ADMIN_EMAIL);
    await page.fill('#password', ADMIN_PASS);
    await page.getByRole('button', { name: 'Iniciar sesión' }).click();

    // Should navigate to dashboard on success
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
  });

  test('link a registro cambia modo del formulario', async ({ page }) => {
    await page.goto('/auth');
    await page.getByRole('link', { name: 'Regístrate aquí' }).click();
    await expect(page).toHaveURL(/register=true/);
    await expect(page.getByRole('button', { name: 'Registrarse' })).toBeVisible();
  });

  test('página de registro muestra campos correctos', async ({ page }) => {
    await page.goto('/auth?register=true');
    await expect(page.locator('#name')).toBeVisible();
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Registrarse' })).toBeVisible();
  });
});
