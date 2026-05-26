import { expect, test } from "@playwright/test";
import { mockAllApis } from "./helpers/network";
import { signInAs } from "./helpers/auth";

test.describe("Chatbot educativo y RAG", () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApis(page);
    await signInAs(page, "student", "/dashboard/chat");
    await expect(page.getByTestId("chat-input")).toBeVisible();
  });

  test("E2E-08 Consulta al chatbot educativo", async ({ page }) => {
    await page.getByTestId("chat-input").fill("Como evaluar fiebre persistente en un estudiante?");
    await page.getByTestId("chat-send").click();

    await expect(page.getByTestId("chat-message-user").last()).toContainText(/fiebre persistente/i);
    await expect(page.getByTestId("chat-message-bot").last()).toContainText(/fiebre persistente/i);
  });

  test("E2E-09 Consulta con RAG y verificacion de fuente/contexto", async ({ page }) => {
    await page.getByTestId("chat-input").fill("Explica fiebre persistente usando fuentes de la plataforma");
    await page.getByTestId("chat-send").click();

    await expect(page.getByTestId("chat-message-bot").last()).toContainText(/documentos de la plataforma/i);
    await expect(page.getByTestId("chat-cited-sources")).toContainText(/Documento RAG fiebre E2E/i);
    await expect(page.getByTestId("chat-rag-card")).toContainText(/Documento RAG fiebre E2E/i);
  });
});
