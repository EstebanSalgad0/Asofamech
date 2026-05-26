import { expect, test } from "@playwright/test";
import { mockAllApis } from "./helpers/network";
import { signInAs } from "./helpers/auth";

const dimensions = [
  "nav_clarity",
  "viewer_ease",
  "roi_ease",
  "ai_clarity",
  "chatbot_utility",
  "sct_utility",
];

test.describe("Feedback de usabilidad", () => {
  test("E2E-13 Usuario completa formulario y recibe confirmacion", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "student", "/dashboard/feedback");

    await expect(page.getByTestId("feedback-form")).toBeVisible();
    for (const dimension of dimensions) {
      await page.getByTestId(`feedback-rating-${dimension}-5`).click();
    }
    await page.getByTestId("feedback-observations").fill("Flujo validado por E2E con datos controlados.");
    await page.getByTestId("feedback-submit").click();

    await expect(page.getByTestId("feedback-confirmation")).toContainText(/Gracias/i);
    await expect(page.getByTestId("feedback-confirmation")).toContainText(/registrada/i);
  });
});
