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

  test("muestra los recursos externos como enlaces seguros en pestana nueva", async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "student", "/dashboard/cases");

    await page.getByTestId(`case-card-${clinicalCaseFixture.id}`).click();
    await expect(page.getByTestId("case-resources")).toBeVisible();

    const [wooclap, bibliografia] = clinicalCaseFixture.links;

    // La actividad interactiva acompana al SCT y a la lamina en el bloque de
    // retroalimentacion; la bibliografia queda en material de consulta.
    const wooclapLink = page.getByTestId(`case-link-${wooclap.id}`);
    await expect(wooclapLink).toHaveAttribute("href", wooclap.url);
    await expect(wooclapLink).toHaveAttribute("target", "_blank");
    await expect(wooclapLink).toHaveAttribute("rel", /noopener/);
    await expect(wooclapLink).toContainText(wooclap.label);

    const bookLink = page.getByTestId(`case-link-${bibliografia.id}`);
    await expect(bookLink).toHaveAttribute("href", bibliografia.url);
    await expect(bookLink).toContainText("biblioteca.example.cl");
  });

  test("descarta enlaces con esquema no navegable en vez de renderizarlos", async ({ page }) => {
    await mockAllApis(page);
    await page.route("**/api/cases**", async (route) => {
      // Un caso guardado antes de la validacion de esquemas podria conservar
      // un javascript:. Nunca debe llegar a un href del estudiante.
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            ...clinicalCaseFixture,
            links: [
              { id: 9101, case_id: 601, kind: "otro", label: "Enlace heredado", url: "javascript:alert(1)", position: 0 },
              ...clinicalCaseFixture.links,
            ],
          },
        ]),
      });
    });
    await signInAs(page, "student", "/dashboard/cases");

    await page.getByTestId(`case-card-${clinicalCaseFixture.id}`).click();
    await expect(page.getByTestId("case-resources")).toBeVisible();
    await expect(page.getByTestId("case-link-9101")).toHaveCount(0);
    await expect(page.getByTestId(`case-link-${clinicalCaseFixture.links[0].id}`)).toBeVisible();
  });
});
