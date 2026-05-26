import { expect, test } from "@playwright/test";
import { signInAs } from "./helpers/auth";
import { mockAllApis } from "./helpers/network";

test.describe("Control de roles", () => {
  test("E2E-12 Estudiante no puede acceder a administracion/configuracion", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "student", "/dashboard");

    await expect(page.getByTestId("nav-config")).toHaveCount(0);

    await page.goto("/dashboard/config", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByTestId("config-page")).toHaveCount(0);
  });

  test("administrador ve y abre configuracion", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "admin", "/dashboard");

    await expect(page.getByTestId("nav-config")).toBeVisible();
    await page.getByTestId("nav-config").click();
    await expect(page).toHaveURL(/\/dashboard\/config$/);
    await expect(page.getByTestId("config-page")).toBeVisible();
  });
});
