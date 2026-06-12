import { expect, test } from "@playwright/test";
import { signInAs } from "./helpers/auth";
import { mockAllApis } from "./helpers/network";

const routes = [
  { path: "/dashboard", role: "student", root: "[data-testid='dashboard-page']" },
  { path: "/dashboard/chat", role: "student", root: "[data-testid='chatbot-page']" },
  { path: "/dashboard/sct", role: "student", root: "[data-testid='sct-page']" },
  { path: "/dashboard/images", role: "student", root: "[data-testid='histopathology-page']" },
  { path: "/dashboard/cases", role: "teacher", root: "[data-testid='cases-page']" },
  { path: "/dashboard/feedback", role: "admin", root: "[data-testid='feedback-page']" },
  { path: "/dashboard/config", role: "admin", root: "[data-testid='config-page']" },
] as const;

const scenarios = [
  { width: 1366, height: 768, fontSize: "large" },
  { width: 1366, height: 768, fontSize: "xl" },
  { width: 1024, height: 768, fontSize: "xl" },
  { width: 768, height: 1024, fontSize: "xl" },
  { width: 1920, height: 1080, fontSize: "xl" },
] as const;

test.describe("Navegacion responsiva con tamaño de texto", () => {
  for (const scenario of scenarios) {
    test(`${scenario.width}x${scenario.height} con texto ${scenario.fontSize}`, async ({ page }) => {
      await page.setViewportSize({ width: scenario.width, height: scenario.height });
      await mockAllApis(page);

      for (const route of routes) {
        await signInAs(page, route.role, route.path);
        await page.evaluate((fontSize) => {
          localStorage.setItem("asofamech-fontsize", fontSize);
        }, scenario.fontSize);
        await page.reload({ waitUntil: "domcontentloaded" });

        const root = page.locator(route.root);
        await expect(root, `${route.path} debe renderizar`).toBeVisible();

        const layout = await page.evaluate((rootSelector) => {
          const rootElement = document.querySelector(rootSelector);
          const sidebar = document.querySelector(".app-sidebar");
          const fontControl = document.querySelector(".fontsize-control-sidebar");
          const rootRect = rootElement?.getBoundingClientRect();
          const sidebarRect = sidebar?.getBoundingClientRect();
          const controlRect = fontControl?.getBoundingClientRect();
          const sidebarVisible = Boolean(
            sidebarRect
            && getComputedStyle(sidebar as Element).display !== "none"
            && sidebarRect.width > 0,
          );
          const clippedControls = rootElement
            ? Array.from(rootElement.querySelectorAll("button, input, select, textarea, a"))
              .filter((element) => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return (
                  rect.width > 0
                  && rect.height > 0
                  && style.display !== "none"
                  && style.visibility !== "hidden"
                  && (rect.left < (rootRect?.left ?? 0) - 1 || rect.right > window.innerWidth + 1)
                );
              })
              .slice(0, 5)
              .map((element) => ({
                tag: element.tagName.toLowerCase(),
                className: element.className,
                text: element.textContent?.trim().slice(0, 60) ?? "",
              }))
            : [];

          return {
            rootLeft: rootRect?.left ?? -1,
            rootRight: rootRect?.right ?? -1,
            sidebarRight: sidebarVisible ? sidebarRect?.right ?? 0 : 0,
            controlTop: controlRect?.top ?? -1,
            controlBottom: controlRect?.bottom ?? -1,
            bodyScrollWidth: document.body.scrollWidth,
            documentScrollWidth: document.documentElement.scrollWidth,
            viewportWidth: window.innerWidth,
            viewportHeight: window.innerHeight,
            sidebarVisible,
            clippedControls,
          };
        }, route.root);

        expect(
          layout.rootLeft,
          `${route.path}: el contenido no debe quedar bajo la barra lateral`,
        ).toBeGreaterThanOrEqual(layout.sidebarRight - 1);
        expect(
          layout.rootRight,
          `${route.path}: el contenido no debe salir del viewport`,
        ).toBeLessThanOrEqual(layout.viewportWidth + 1);
        expect(
          Math.max(layout.bodyScrollWidth, layout.documentScrollWidth),
          `${route.path}: no debe existir overflow horizontal global`,
        ).toBeLessThanOrEqual(layout.viewportWidth + 1);
        expect(
          layout.clippedControls,
          `${route.path}: los controles interactivos deben permanecer dentro de la vista`,
        ).toEqual([]);
        if (layout.sidebarVisible) {
          expect(
            layout.controlTop,
            `${route.path}: el control tipografico debe seguir visible`,
          ).toBeGreaterThanOrEqual(0);
          expect(
            layout.controlBottom,
            `${route.path}: el control tipografico debe caber verticalmente`,
          ).toBeLessThanOrEqual(layout.viewportHeight + 1);
        }
      }
    });
  }
});
