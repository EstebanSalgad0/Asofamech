const { test, expect } = require('@playwright/test');
const { injectAuthAndGo } = require('./helpers/inject-auth');

test.describe('Dashboard y navegación', () => {
  test('acceso al dashboard con sesión válida', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard');
    if (!ok) return;

    // Sidebar should render
    await expect(page.locator('.app-sidebar')).toBeVisible({ timeout: 10_000 });
    // Logo visible
    await expect(page.locator('.app-sidebar-logo-text')).toHaveText('ASOFAMECH');
  });

  test('sidebar muestra items de navegación principales', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard');
    if (!ok) return;

    await page.waitForSelector('.app-sidebar', { timeout: 10_000 });

    // These nav items must always be visible for admin
    const expectedLabels = ['Inicio', 'Asistente IA', 'Test SCT', 'Imagenes IA', 'Casos Clinicos'];
    for (const label of expectedLabels) {
      await expect(page.locator('.app-nav-item').filter({ hasText: label })).toBeVisible();
    }
  });

  test('admin ve item Configuracion en sidebar', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard');
    if (!ok) return;

    await page.waitForSelector('.app-sidebar');
    await expect(page.locator('.app-nav-item').filter({ hasText: 'Configuracion' })).toBeVisible();
  });

  test('navega a Asistente IA desde sidebar', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard');
    if (!ok) return;

    await page.waitForSelector('.app-sidebar');
    await page.locator('.app-nav-item').filter({ hasText: 'Asistente IA' }).click();
    await expect(page).toHaveURL(/\/dashboard\/chat/);
    await expect(page.locator('.mc-input')).toBeVisible({ timeout: 10_000 });
  });

  test('navega a Imagenes IA desde sidebar', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard');
    if (!ok) return;

    await page.waitForSelector('.app-sidebar');
    await page.locator('.app-nav-item').filter({ hasText: 'Imagenes IA' }).click();
    await expect(page).toHaveURL(/\/dashboard\/images/);
    // Page should load without redirect
    await page.waitForSelector('.app-sidebar', { timeout: 10_000 });
  });

  test('navega a Test SCT desde sidebar', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard');
    if (!ok) return;

    await page.waitForSelector('.app-sidebar');
    await page.locator('.app-nav-item').filter({ hasText: 'Test SCT' }).click();
    await expect(page).toHaveURL(/\/dashboard\/sct/);
    await page.waitForSelector('.app-sidebar', { timeout: 10_000 });
  });

  test('navega a Casos Clínicos desde sidebar', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard');
    if (!ok) return;

    await page.waitForSelector('.app-sidebar');
    await page.locator('.app-nav-item').filter({ hasText: 'Casos Clinicos' }).click();
    await expect(page).toHaveURL(/\/dashboard\/cases/);
    await page.waitForSelector('.app-sidebar', { timeout: 10_000 });
  });

  test('muestra nombre del usuario en la tarjeta de perfil', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard');
    if (!ok) return;

    await page.waitForSelector('.app-user-card');
    const nameEl = page.locator('.app-user-name');
    await expect(nameEl).toBeVisible();
    const name = await nameEl.textContent();
    expect(name.trim().length).toBeGreaterThan(0);
  });

  test('búsqueda en sidebar filtra items', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard');
    if (!ok) return;

    await page.waitForSelector('.app-sidebar');
    // Search for "Asist" — matches "Asistente IA", not "Test SCT"
    await page.fill('.app-sidebar-search input[aria-label="Buscar modulo"]', 'Asist');

    // Only matching items should remain
    await expect(page.locator('.app-nav-item').filter({ hasText: 'Asistente IA' })).toBeVisible();
    // Non-matching items should be hidden
    await expect(page.locator('.app-nav-item').filter({ hasText: 'Test SCT' })).not.toBeVisible();
  });
});
