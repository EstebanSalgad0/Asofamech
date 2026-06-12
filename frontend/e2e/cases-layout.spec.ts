import { expect, test } from "@playwright/test";
import { signInAs } from "./helpers/auth";
import { mockAllApis } from "./helpers/network";

test.describe("Formulario de casos clinicos", () => {
  test("el selector SCT permanece dentro del modal", async ({ page }) => {
    await page.setViewportSize({ width: 763, height: 1024 });
    await mockAllApis(page);
    await signInAs(page, "teacher", "/dashboard/cases");

    await page.getByRole("button", { name: /nuevo caso/i }).click();

    const modal = page.getByTestId("case-form-modal");
    const sctSelect = page.getByTestId("case-sct-select");
    await expect(modal).toBeVisible();
    await expect(sctSelect).toBeVisible();

    const layout = await modal.evaluate((element) => {
      const modalRect = element.getBoundingClientRect();
      const select = element.querySelector('[data-testid="case-sct-select"]');
      const selectRect = select?.getBoundingClientRect();

      return {
        modalLeft: modalRect.left,
        modalRight: modalRect.right,
        modalClientWidth: element.clientWidth,
        modalScrollWidth: element.scrollWidth,
        selectLeft: selectRect?.left ?? -1,
        selectRight: selectRect?.right ?? -1,
        viewportWidth: window.innerWidth,
      };
    });

    expect(layout.modalLeft).toBeGreaterThanOrEqual(0);
    expect(layout.modalRight).toBeLessThanOrEqual(layout.viewportWidth);
    expect(layout.modalScrollWidth).toBeLessThanOrEqual(layout.modalClientWidth);
    expect(layout.selectLeft).toBeGreaterThanOrEqual(layout.modalLeft);
    expect(layout.selectRight).toBeLessThanOrEqual(layout.modalRight);
  });
});
