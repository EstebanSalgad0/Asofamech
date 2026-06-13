import { expect, test } from "@playwright/test";
import { mockAllApis } from "./helpers/network";
import { signInAs } from "./helpers/auth";

test.describe("Test SCT", () => {
  test("permite seleccionar Oncologia como area clinica", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "teacher", "/dashboard/sct");

    await page.getByRole("button", { name: "Paso 2 Foco médico" }).click();
    const oncology = page.getByRole("button", { name: "Oncología" });

    await expect(oncology).toBeVisible();
    await oncology.click();
    await expect(oncology).toContainText("✓");

    await page.getByRole("button", { name: /Siguiente.*Revisar/i }).click();
    await expect(page.locator(".sct3-review-areas")).toContainText("Oncología");
  });

  test("E2E-10 Resolucion de actividad SCT y retroalimentacion", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "student", "/dashboard/sct");

    await expect(page.getByTestId("sct-library-card-801")).toContainText(/PUBLICADO/i);
    await page.getByTestId("sct-open-801").click();

    await expect(page.getByTestId("sct-test-page")).toBeVisible();
    await page.getByTestId("sct-answer-1-2").click();
    await page.getByTestId("sct-answer-2--1").click();
    await page.getByTestId("sct-submit").click();

    await expect(page.getByTestId("sct-results")).toContainText(/100/);
    await expect(page.getByTestId("sct-results")).toContainText(/Test Completado/i);
    await expect(page.getByTestId("sct-feedback-card-1")).toContainText(/baciloscopia/i);
    await expect(page.getByTestId("sct-feedback-card-2")).toContainText(/viral/i);
  });
});
