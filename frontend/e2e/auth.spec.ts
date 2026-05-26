import { expect, test } from "@playwright/test";
import { testUsers } from "./fixtures/e2e-data";
import { mockAuthApi, mockCommonApi } from "./helpers/network";

test.describe("Autenticacion", () => {
  test.beforeEach(async ({ page }) => {
    await mockCommonApi(page);
    await mockAuthApi(page);
  });

  test("E2E-01 Login y acceso al dashboard", async ({ page }) => {
    await page.goto("/auth");

    await page.getByTestId("auth-email").fill(testUsers.student.email);
    await page.getByTestId("auth-password").fill(testUsers.student.password);
    await page.getByTestId("auth-submit").click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByTestId("dashboard-page")).toBeVisible();
    await expect(page.getByTestId("app-user-card")).toContainText(testUsers.student.name);
  });

  test("E2E-02 Bloqueo de acceso sin autenticacion", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });

    await expect(page).toHaveURL(/\/auth$/);
    await expect(page.getByTestId("auth-form")).toBeVisible();
  });

  test("muestra error de credenciales invalidas", async ({ page }) => {
    await page.goto("/auth");

    await page.getByTestId("auth-email").fill("noexiste@asofamech.local");
    await page.getByTestId("auth-password").fill("Wrong12345");
    await page.getByTestId("auth-submit").click();

    await expect(page.getByTestId("auth-error")).toContainText(/credenciales/i);
  });
});
