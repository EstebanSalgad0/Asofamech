import { expect, test } from "@playwright/test";
import { signInAs } from "./helpers/auth";
import { mockAllApis } from "./helpers/network";

test.describe("Control de tamaño de texto", () => {
  test("reduce y aumenta de forma perceptible la interfaz", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "student", "/dashboard");

    const control = page.locator(".fontsize-control-sidebar");
    const label = control.locator(".fontsize-label");
    await expect(control).toBeVisible();
    await expect(control.locator(".fontsize-sep")).toHaveText("Normal");

    const normalHeight = (await label.boundingBox())?.height ?? 0;

    await control.getByRole("button", { name: "Aumentar tamaño de texto" }).click();
    await control.getByRole("button", { name: "Aumentar tamaño de texto" }).click();
    await expect(control.locator(".fontsize-sep")).toHaveText("Máx");
    await expect(page.locator("html")).toHaveAttribute("data-fontsize", "xl");
    const maximumHeight = (await label.boundingBox())?.height ?? 0;

    expect(maximumHeight).toBeGreaterThan(normalHeight * 1.18);

    await control.getByRole("button", { name: "Reducir tamaño de texto" }).click();
    await control.getByRole("button", { name: "Reducir tamaño de texto" }).click();
    await control.getByRole("button", { name: "Reducir tamaño de texto" }).click();
    await expect(control.locator(".fontsize-sep")).toHaveText("Pequeño");
    await expect(page.locator("html")).toHaveAttribute("data-fontsize", "small");
    const smallHeight = (await label.boundingBox())?.height ?? 0;

    expect(smallHeight).toBeLessThan(normalHeight * 0.95);
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem("asofamech-fontsize")))
      .toBe("small");
  });
});
