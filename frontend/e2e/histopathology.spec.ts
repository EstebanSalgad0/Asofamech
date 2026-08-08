import { expect, test } from "@playwright/test";
import { apiBase, dziImage } from "./fixtures/e2e-data";
import { drawOnOverlay, expectRectStartsAtOverlayPoint } from "./helpers/histopathology";
import { signInAs } from "./helpers/auth";
import { mockAllApis } from "./helpers/network";

async function openViewer(page, options: { fontSize?: "large" | "xl" } = {}) {
  await mockAllApis(page);
  await signInAs(page, "student", "/dashboard/images");
  if (options.fontSize) {
    await page.evaluate((fontSize) => {
      localStorage.setItem("asofamech-fontsize", fontSize);
      document.documentElement.setAttribute("data-fontsize", fontSize);
    }, options.fontSize);
  }
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
  test("estudiante solo puede seleccionar imagenes de la biblioteca", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "student", "/dashboard/images");

    await expect(page.getByTestId("disease-add-images")).toHaveCount(0);
    await expect(page.getByTestId("histopathology-empty-viewer")).toContainText(
      /selecciona una imagen disponible de la biblioteca/i,
    );
  });

  test("el selector de enfermedades despliega las laminas de cada patologia", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "teacher", "/dashboard/images");

    const selector = page.getByTestId("disease-selector");
    await expect(selector).toBeVisible();
    // Mas de una enfermedad analizable, no solo cancer.
    await expect(selector.getByRole("button", { expanded: false })).not.toHaveCount(0);
    await expect(selector).toContainText(/Cáncer de mama/i);
    await expect(selector).toContainText(/Necrosis y muerte celular/i);

    // La enfermedad con laminas queda desplegada y muestra sus imagenes.
    await expect(page.getByTestId(`image-library-item-${dziImage.id}`)).toBeVisible();

    // Colapsar la enfermedad oculta sus laminas.
    const openHead = selector.getByRole("button", { expanded: true }).first();
    await openHead.click();
    await expect(page.getByTestId(`image-library-item-${dziImage.id}`)).toHaveCount(0);

    // Docente puede saltar a Configuracion para cargar mas enfermedades.
    await expect(page.getByTestId("disease-add-images")).toBeVisible();
  });

  test("E2E-04 Apertura de imagen DZI y carga del visor", async ({ page }) => {
    await openViewer(page);

    await expect(page.getByTestId("osd-canvas")).toBeVisible();
    await expect(page.getByTestId("heatmap-toggle")).toBeChecked();
  });

  test("E2E-05 Seleccion de ROI 1 y ROI 2", async ({ page }) => {
    await openViewer(page, { fontSize: "large" });
    await selectRois(page);
    await expectRectStartsAtOverlayPoint(page, "osd-overlay", "roi-1-overlay", { x: 120, y: 120 });
    await expectRectStartsAtOverlayPoint(page, "osd-overlay", "roi-2-overlay", { x: 180, y: 180 });
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

    await expect(page.getByTestId("heatmap-summary")).toContainText(/Mapa de probabilidades por tiles/i);
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
