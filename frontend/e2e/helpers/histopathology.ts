import { expect, type Page } from "@playwright/test";

export async function drawOnOverlay(
  page: Page,
  testId: string,
  rect: { x: number; y: number; width: number; height: number },
) {
  const overlay = page.getByTestId(testId);
  await expect(overlay).toBeVisible();
  const box = await overlay.boundingBox();
  if (!box) throw new Error(`No bounding box for ${testId}`);

  await page.mouse.move(box.x + rect.x, box.y + rect.y);
  await page.mouse.down();
  await page.mouse.move(box.x + rect.x + rect.width, box.y + rect.y + rect.height, { steps: 8 });
  await page.mouse.up();
}
