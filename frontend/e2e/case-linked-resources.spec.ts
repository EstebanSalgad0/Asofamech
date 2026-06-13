import { expect, test } from "@playwright/test";
import { clinicalCaseFixture, dziImage, publishedSct } from "./fixtures/e2e-data";
import { signInAs } from "./helpers/auth";
import { mockAllApis } from "./helpers/network";

test.describe("Recursos asociados a casos clinicos", () => {
  test("abre directamente la imagen histopatologica asociada", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "student", "/dashboard/cases");

    await page.getByTestId(`case-card-${clinicalCaseFixture.id}`).click();
    await page.getByTestId("case-linked-image").click();

    await expect(page).toHaveURL(new RegExp(`/dashboard/images\\?image=${dziImage.id}$`));
    await expect(page.getByTestId(`image-library-item-${dziImage.id}`)).toHaveClass(/selected/);
    await expect(page.getByTestId("osd-viewer-root")).toBeVisible();
  });

  test("abre directamente el test SCT asociado", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "student", "/dashboard/cases");

    await page.getByTestId(`case-card-${clinicalCaseFixture.id}`).click();
    await page.getByTestId("case-linked-sct").click();

    await expect(page).toHaveURL(new RegExp(`/dashboard/sct\\?test=${publishedSct.id}$`));
    await expect(page.getByTestId("sct-test-page")).toBeVisible();
    await expect(page.locator(".sct-test-name")).toContainText(publishedSct.name);
  });
});
