import type { Page, Route } from "@playwright/test";
import {
  aiPredictionFixture,
  chatRagResponse,
  clinicalCaseFixture,
  dashboardHistoryFixture,
  dashboardStatsFixture,
  diseaseCategoriesFixture,
  dziImage,
  dziManifest,
  heatmapFixture,
  surveyDemoFixture,
  pngTileBase64,
  publishedSct,
  publishedSctDetail,
  roiSessionFixture,
  sctAttemptFixture,
} from "../fixtures/e2e-data";

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function text(route: Route, body: string, contentType = "text/plain", status = 200) {
  await route.fulfill({ status, contentType, body });
}

export async function mockCommonApi(page: Page) {
  await page.route("**/health", (route) => json(route, { status: "ok", service: "asofamech-e2e" }));
  await page.route("**/api/dashboard/stats", (route) => json(route, dashboardStatsFixture));
  await page.route("**/api/dashboard/ranking", (route) =>
    json(route, {
      ranking: [{ name: "Estudiante E2E", score: 100, is_you: true }],
      your_position: 1,
      percentile: 1,
      total_users: 1,
    }),
  );
  await page.route("**/api/history/me?**", (route) => json(route, dashboardHistoryFixture));
  await page.route("**/api/cases", (route) => json(route, [clinicalCaseFixture]));
  await page.route("**/api/cases?**", (route) => json(route, [clinicalCaseFixture]));
  await page.route("**/api/cases/search?**", (route) => json(route, [clinicalCaseFixture]));
}

export async function mockAuthApi(page: Page) {
  await page.route("**/api/auth/login", async (route) => {
    const body = route.request().postDataJSON() as { email?: string; password?: string };
    const allUsers = Object.values((await import("../fixtures/e2e-data")).testUsers);
    const user = allUsers.find((item) => item.email === body.email && item.password === body.password);
    if (!user) {
      await json(route, { detail: "Credenciales invalidas" }, 401);
      return;
    }
    const { sessionFor } = await import("./auth");
    const role = user.role === "administrador" ? "admin" : user.role === "docente" ? "teacher" : "student";
    const session = sessionFor(role);
    await json(route, {
      access_token: session.auth_token,
      token_type: "bearer",
      user: session.user,
    });
  });
}

export async function mockHistopathologyApi(page: Page) {
  await page.route("**/api/medical-images/list", (route) => json(route, [dziImage]));
  await page.route("**/api/disease-categories", (route) => json(route, diseaseCategoriesFixture));
  await page.route("**/api/history/roi-sessions?**", (route) =>
    json(route, { count: 1, items: [roiSessionFixture] }),
  );
  await page.route("**/api/medical-images/dzi/501.dzi", (route) =>
    text(route, dziManifest, "application/xml"),
  );
  await page.route("**/api/medical-images/dzi/501_files/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/png",
      body: Buffer.from(pngTileBase64, "base64"),
    }),
  );
  await page.route("**/api/histopathology/status", (route) =>
    json(route, {
      model_ready: true,
      backbone: "CONCH mock",
      device: "cpu-e2e",
      feature_dim: 512,
      num_classes: 3,
      labels: ["metastasico", "no_metastasico", "estroma"],
      confidence_threshold: 0.9,
    }),
  );
  await page.route("**/api/histopathology/heatmaps/image/501/latest", (route) =>
    json(route, heatmapFixture),
  );
  await page.route("**/api/histopathology/heatmaps/image/501/history?**", (route) =>
    json(route, { count: 1, items: [heatmapFixture] }),
  );
  await page.route("**/api/histopathology/heatmaps/e2e-heatmap-trace", (route) =>
    json(route, heatmapFixture),
  );
  await page.route("**/api/histopathology/sessions?**", (route) =>
    json(route, { count: 1, items: [roiSessionFixture] }),
  );
  await page.route("**/api/histopathology/analyze-roi", (route) => json(route, aiPredictionFixture));
  await page.route("**/api/histopathology/feedback", (route) =>
    json(route, {
      educational_feedback:
        "La ROI muestra un patron compatible con foco metastasico en contexto educativo. Revisa arquitectura, celularidad y correlaciona con el mapa de calor.",
    }),
  );
}

export async function mockChatApi(page: Page) {
  await page.route("**/api/chat", (route) => json(route, chatRagResponse));
}

export async function mockSctApi(page: Page) {
  await page.route("**/api/sct/list", (route) => json(route, [publishedSct]));
  await page.route("**/api/sct/my-attempts", (route) => json(route, []));
  await page.route("**/api/sct/admin/attempts", (route) => json(route, []));
  await page.route("**/api/sct/801", (route) => json(route, publishedSctDetail));
  await page.route("**/api/sct/801/attempt", (route) => json(route, sctAttemptFixture));
}

export async function mockSurveysApi(page: Page) {
  await page.route("**/api/surveys", (route) => json(route, [surveyDemoFixture]));
  await page.route("**/api/surveys/admin/all", (route) => json(route, [surveyDemoFixture]));
  await page.route("**/api/surveys/demo", (route) =>
    json(route, { ...surveyDemoFixture, items: [], already_answered: false }),
  );
  await page.route("**/api/surveys/demo/summary", (route) =>
    json(route, {
      survey_code: "demo",
      survey_title: "Demo",
      total_responses: 0,
      global_average: null,
      section_averages: [],
      item_stats: [],
    }),
  );
  await page.route("**/api/surveys/demo/open-answers", (route) => json(route, []));
}

export async function mockAllApis(page: Page) {
  await mockCommonApi(page);
  await mockHistopathologyApi(page);
  await mockChatApi(page);
  await mockSctApi(page);
  await mockSurveysApi(page);
}
