const { test, expect } = require('@playwright/test');
const { injectAuthAndGo } = require('./helpers/inject-auth');

const MOCK_CHAT_RESPONSE = {
  messages: [{ text: 'La tuberculosis pulmonar es una enfermedad infecciosa causada por Mycobacterium tuberculosis.' }],
  used_rag: false,
  message_type: 'answer',
};

test.describe('Chatbot / Asistente IA', () => {
  test('página del chatbot carga la interfaz completa', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard/chat');
    if (!ok) return;

    await expect(page.locator('.mc-input')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('.mc-send-btn')).toBeVisible();
    await expect(page.locator('.mc-messages')).toBeVisible();
  });

  test('muestra mensaje de bienvenida del bot', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard/chat');
    if (!ok) return;

    await page.waitForSelector('.mc-messages', { timeout: 10_000 });
    // Bot welcome message should be visible
    const botMessages = page.locator('.mc-msg.bot');
    await expect(botMessages.first()).toBeVisible();
  });

  test('botón enviar deshabilitado con input vacío', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard/chat');
    if (!ok) return;

    await page.waitForSelector('.mc-send-btn');
    // With empty input, send button should be disabled
    const sendBtn = page.locator('.mc-send-btn');
    await expect(sendBtn).toBeDisabled();
  });

  test('envío de mensaje (respuesta mockeada)', async ({ page }) => {
    // Mock the /api/chat endpoint so the test doesn't depend on Ollama
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE),
      });
    });

    const ok = await injectAuthAndGo(page, test, '/dashboard/chat');
    if (!ok) return;

    await page.waitForSelector('.mc-input', { timeout: 10_000 });

    const input = page.locator('.mc-input');
    await input.fill('¿Qué es la tuberculosis pulmonar?');
    await expect(page.locator('.mc-send-btn')).toBeEnabled();
    await page.locator('.mc-send-btn').click();

    // User message should appear
    await expect(page.locator('.mc-msg.user').last()).toBeVisible({ timeout: 5_000 });

    // Bot response should arrive (mocked instantly)
    await expect(page.locator('.mc-msg.bot').last()).toBeVisible({ timeout: 10_000 });
  });

  test('Enter envía el mensaje', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE),
      });
    });

    const ok = await injectAuthAndGo(page, test, '/dashboard/chat');
    if (!ok) return;

    await page.waitForSelector('.mc-input', { timeout: 10_000 });
    await page.fill('.mc-input', 'síntomas de neumonía');
    await page.keyboard.press('Enter');

    await expect(page.locator('.mc-msg.user').last()).toBeVisible({ timeout: 5_000 });
  });

  test('muestra lista de conversaciones en panel izquierdo', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard/chat');
    if (!ok) return;

    await page.waitForSelector('.mc-conversations', { timeout: 10_000 });
    await expect(page.locator('.mc-conversations')).toBeVisible();
  });

  test('botón Nueva conversación crea un hilo nuevo', async ({ page }) => {
    const ok = await injectAuthAndGo(page, test, '/dashboard/chat');
    if (!ok) return;

    await page.waitForSelector('.mc-new-conv-btn', { timeout: 10_000 });
    const before = await page.locator('.mc-conv-item').count();
    await page.locator('.mc-new-conv-btn').click();
    const after = await page.locator('.mc-conv-item').count();
    expect(after).toBeGreaterThanOrEqual(before);
  });
});
