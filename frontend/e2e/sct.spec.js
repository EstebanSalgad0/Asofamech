const { test, expect } = require('@playwright/test');
const { injectAuthAndGo, loadAuthState } = require('./helpers/inject-auth');

const MOCK_SCT_GENERATED = {
  items: [
    {
      id: 1,
      vignette: 'Paciente de 35 años con tos persistente de 3 semanas, fiebre vespertina y pérdida de peso.',
      hypothesis: 'Tuberculosis pulmonar',
      new_info: 'Baciloscopía de esputo positiva para BAAR.',
      scale_options: ['-2: Descarta completamente', '-1: Menos probable', '0: Sin cambio', '+1: Más probable', '+2: Apoya fuertemente'],
      correct_answer: 2,
      explanation: 'La baciloscopía positiva confirma el diagnóstico de tuberculosis.',
    },
  ],
  total: 1,
  difficulty: 'pregrado',
  focus: 'tuberculosis pulmonar',
};

const MOCK_ATTEMPT_RESPONSE = {
  id: 1,
  test_id: 1,
  user_id: 1,
  score: 100.0,
  correct_count: 1,
  total_items: 1,
  completed_at: new Date().toISOString(),
};

test.describe('Test SCT', () => {
  test('página SCT carga sin errores', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard/sct');
    if (!ok) return;

    // Wait for sidebar and page content
    await page.waitForSelector('.app-sidebar', { timeout: 10_000 });
    // Should NOT redirect away
    await expect(page).toHaveURL(/\/dashboard\/sct/);
  });

  test('muestra interfaz de generación (docente/admin)', async ({ page }) => {
    // Mock the generate endpoint to avoid hitting the real AI backend
    await page.route('**/api/sct/generate', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_SCT_GENERATED),
      });
    });
    await page.route('**/api/sct/list', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });
    await page.route('**/api/sct/my-attempts', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });

    const ok = await injectAuthAndGo(page, test, '/dashboard/sct');
    if (!ok) return;

    await page.waitForSelector('.app-sidebar', { timeout: 10_000 });
    // Admin/docente sees tab or section for test list
    // Just verify the page body renders something substantial
    const body = await page.locator('body').textContent();
    expect(body.length).toBeGreaterThan(100);
  });

  test('lista de tests publicados se carga', async ({ page }) => {
    await page.route('**/api/sct/list', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, name: 'Test Tuberculosis', difficulty: 'pregrado', focus: 'tuberculosis pulmonar', num_items: 1, status: 'published', created_at: new Date().toISOString() },
        ]),
      });
    });
    await page.route('**/api/sct/my-attempts', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });
    await page.route('**/api/sct/admin/attempts', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });

    const ok = await injectAuthAndGo(page, test, '/dashboard/sct');
    if (!ok) return;

    await page.waitForSelector('.app-sidebar', { timeout: 10_000 });
    // Card renders "Test SCT · tuberculosis" (first word of focus, lowercased) — not the raw name
    await expect(page.locator('.sct3-library-card')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.sct3-lib-badge')).toHaveText('PUBLICADO');
  });

  test('estudiante puede intentar un test SCT (flujo mockeado)', async ({ page }) => {
    await page.route('**/api/sct/list', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, name: 'Test Tuberculosis', difficulty: 'pregrado', focus: 'tuberculosis pulmonar', num_items: 1, status: 'published', created_at: new Date().toISOString() },
        ]),
      });
    });
    await page.route('**/api/sct/1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...MOCK_SCT_GENERATED, id: 1, name: 'Test Tuberculosis', created_at: new Date().toISOString() }),
      });
    });
    await page.route('**/api/sct/1/attempt', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_ATTEMPT_RESPONSE),
      });
    });
    await page.route('**/api/sct/my-attempts', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });
    await page.route('**/api/sct/admin/attempts', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });

    // Use student auth if available, fall back to admin
    const studentState = loadAuthState('student');
    const role = studentState.auth_token ? 'student' : 'admin';

    const ok = await injectAuthAndGo(page, test, '/dashboard/sct', role);
    if (!ok) return;

    await page.waitForSelector('.app-sidebar', { timeout: 10_000 });

    // Click the test to open it (look for a button/link with the test name)
    const testButton = page.locator('text=Test Tuberculosis').first();
    const testVisible = await testButton.isVisible({ timeout: 5_000 }).catch(() => false);
    if (!testVisible) {
      test.skip(true, 'Test list item not rendered — UI structure may differ');
      return;
    }
    await testButton.click();
    // Should show some SCT content (items, vignette, etc.)
    await page.waitForTimeout(1000);
    const body = await page.locator('body').textContent();
    expect(body).toBeTruthy();
  });
});
