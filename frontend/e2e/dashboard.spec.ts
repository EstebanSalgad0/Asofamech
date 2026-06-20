import { expect, test } from "@playwright/test";
import { testUsers } from "./fixtures/e2e-data";
import { signInAs } from "./helpers/auth";
import { mockAllApis } from "./helpers/network";

const chatStorageKey = `asofamech_chat_history:user_${testUsers.student.id}`;

async function openDashboardWithLocalChat(page, conversations: unknown[]) {
  await mockAllApis(page);
  await signInAs(page, "student", "/dashboard");
  await page.evaluate(
    ({ key, value }) => localStorage.setItem(key, JSON.stringify(value)),
    { key: chatStorageKey, value: conversations },
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("dashboard-page")).toBeVisible();
}

test.describe("Dashboard history", () => {
  test("prefiere conversaciones locales del chat sobre el historial del backend", async ({ page }) => {
    await openDashboardWithLocalChat(page, [
      {
        id: 9001,
        title: "Consulta nueva visible en dashboard",
        createdAt: "2026-06-19T21:55:00.000Z",
        updatedAt: "2026-06-19T21:56:00.000Z",
        messages: [
          { sender: "bot", text: "Hola" },
          { sender: "user", text: "Consulta nueva visible en dashboard" },
          { sender: "bot", text: "Respuesta", usedRag: true },
        ],
      },
    ]);

    const history = page.getByTestId("dashboard-history");
    await expect(history).toContainText("Consulta nueva visible en dashboard");
    await expect(history).not.toContainText("fiebre persistente con sospecha infecciosa");
  });

  test("una lista local sin mensajes no vuelve a mostrar conversaciones borradas del backend", async ({ page }) => {
    await openDashboardWithLocalChat(page, [
      {
        id: 9002,
        title: "Nueva conversación",
        createdAt: "2026-06-19T21:57:00.000Z",
        updatedAt: "2026-06-19T21:57:00.000Z",
        messages: [{ sender: "bot", text: "Hola" }],
      },
    ]);

    const history = page.getByTestId("dashboard-history");
    await expect(history).toContainText("Sin conversaciones guardadas");
    await expect(history).not.toContainText("fiebre persistente con sospecha infecciosa");
  });
});
