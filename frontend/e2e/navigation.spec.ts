import { expect, test } from "@playwright/test";
import { mockAllApis } from "./helpers/network";
import { signInAs } from "./helpers/auth";

test.describe("Navegacion principal", () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "student", "/dashboard");
  });

  test("E2E-03 Navegacion entre modulos principales", async ({ page }) => {
    await expect(page.getByTestId("dashboard-page")).toBeVisible();

    await page.getByTestId("nav-chat").click();
    await expect(page).toHaveURL(/\/dashboard\/chat$/);
    await expect(page.getByTestId("chat-input")).toBeVisible();

    await page.getByTestId("nav-sct").click();
    await expect(page).toHaveURL(/\/dashboard\/sct$/);
    await expect(page.getByTestId("sct-page")).toBeVisible();

    await page.getByTestId("nav-images").click();
    await expect(page).toHaveURL(/\/dashboard\/images$/);
    await expect(page.getByTestId("histopathology-page")).toBeVisible();

    await page.getByTestId("nav-cases").click();
    await expect(page).toHaveURL(/\/dashboard\/cases$/);
    await expect(page.getByTestId("cases-page")).toBeVisible();

    await page.getByTestId("nav-surveys").click();
    await expect(page).toHaveURL(/\/dashboard\/surveys$/);
    await expect(page.getByTestId("surveys-page")).toBeVisible();
  });
});
