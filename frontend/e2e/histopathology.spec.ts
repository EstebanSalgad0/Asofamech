import { expect, test } from "@playwright/test";
import { apiBase, dziImage } from "./fixtures/e2e-data";
import { drawOnOverlay } from "./helpers/histopathology";
import { signInAs } from "./helpers/auth";
import { mockAllApis } from "./helpers/network";

async function openViewer(page) {
  await mockAllApis(page);
  await signInAs(page, "student", "/dashboard/images");
  await page.getByTestId(`image-library-item-${dziImage.id}`).click();
  await expect(page.getByTestId("osd-viewer-root")).toBeVisible();
  await expect(page.getByTestId("osd-overlay")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("model-status")).toContainText(/Modelo listo/i);
}

async function selectRois(page) {
  await page.getByTestId("osd-mode-roi1").click();
  await drawOnOverlay(page, "osd-overlay", { x: 120, y: 120, width: 360, height: 320 });
  await expect(page.getByTestId("roi-1-overlay")).toBeVisible();
  await expect(page.getByTestId("roi1-status")).not.toContainText(/Sin definir/i);

  await page.getByTestId("osd-mode-roi2").click();
  await drawOnOverlay(page, "osd-overlay", { x: 180, y: 180, width: 120, height: 120 });
  await expect(page.getByTestId("roi-2-overlay")).toBeVisible();
  await expect(page.getByTestId("roi2-status")).toContainText(/px/i);
}

test.describe("Visor histopatologico", () => {
  test("E2E-04 Apertura de imagen DZI y carga del visor", async ({ page }) => {
    await openViewer(page);

    await expect(page.getByTestId("osd-canvas")).toBeVisible();
    await expect(page.getByTestId("heatmap-toggle")).toBeChecked();
  });

  test("E2E-05 Seleccion de ROI 1 y ROI 2", async ({ page }) => {
    await openViewer(page);
    await selectRois(page);
  });

  test("E2E-06 Analisis IA sobre ROI y resultado formativo", async ({ page }) => {
    await openViewer(page);
    await selectRois(page);

    await expect(page.getByTestId("analyze-roi-button")).toBeEnabled();
    await page.getByTestId("analyze-roi-button").click();

    await expect(page.getByTestId("ai-result-card")).toBeVisible();
    await expect(page.getByTestId("ai-result-card")).toContainText(/Resultado educativo/i);
    await expect(page.getByTestId("ai-feedback-button")).toBeVisible();

    await page.getByTestId("ai-feedback-button").click();
    await expect(page.getByTestId("ai-feedback-panel")).toContainText(/ROI muestra/i);
  });

  test("E2E-07 Visualizacion de heatmap disponible", async ({ page }) => {
    await openViewer(page);
    await page.getByTestId("osd-mode-roi1").click();

    await expect(page.getByTestId("heatmap-summary")).toContainText(/Mapa ROI 1/i);
    await expect(page.getByTestId("heatmap-tile").first()).toBeVisible();
  });

  test("E2E-11 Consulta de historial o persistencia del analisis", async ({ page }) => {
    await openViewer(page);

    await page.getByTestId("roi-history-toggle").click();
    await expect(page.getByTestId("roi-history-session-701")).toContainText(/Metastasico/i);
  });

  test("demo real local: GET /api/histopathology/status", async ({ request }) => {
    test.skip(process.env.E2E_REAL_BACKEND !== "1", "Opt-in: ejecutar con E2E_REAL_BACKEND=1 y backend real activo.");

    const response = await request.get(`${apiBase}/api/histopathology/status`);
    expect(response.ok()).toBeTruthy();
    const payload = await response.json();
    expect(payload).toHaveProperty("model_ready");
  });
});
