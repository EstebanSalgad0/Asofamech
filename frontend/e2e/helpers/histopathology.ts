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

export async function expectRectStartsAtOverlayPoint(
  page: Page,
  overlayTestId: string,
  rectTestId: string,
  point: { x: number; y: number },
  tolerance = 6,
) {
  const overlay = page.getByTestId(overlayTestId);
  const rect = page.getByTestId(rectTestId);
  await expect(overlay).toBeVisible();
  await expect(rect).toBeVisible();

  const overlayBox = await overlay.boundingBox();
  const rectBox = await rect.boundingBox();
  if (!overlayBox || !rectBox) throw new Error(`No bounding box for ${overlayTestId} or ${rectTestId}`);

  expect(Math.abs(rectBox.x - (overlayBox.x + point.x))).toBeLessThanOrEqual(tolerance);
  expect(Math.abs(rectBox.y - (overlayBox.y + point.y))).toBeLessThanOrEqual(tolerance);
}
