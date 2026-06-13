/**
 * ASOFAMECH - AI endpoints load test
 *
 * Mide tiempos reales de Ollama (chat) e inferencia ML (histopatología)
 * bajo distintos niveles de concurrencia.
 *
 * Perfiles via env ASO_AI_PROFILE:
 *   chat_solo       – 1 VU, 4 iteraciones  (baseline chat)
 *   chat_concurrent – 4 VUs, 12 iteraciones (chat simultáneo)
 *   histo_solo      – 1 VU, 4 iteraciones  (baseline histopatología)
 *   histo_concurrent– 4 VUs, 12 iteraciones (histo simultáneo)
 *   combined        – 2 VUs chat + 2 VUs histo a la vez
 */
import http from "k6/http";
import { check, group, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const BASE_URL = (__ENV.ASO_BASE_URL || "http://localhost:8001").replace(/\/$/, "");
const EMAIL    = __ENV.ASO_EMAIL    || "";
const PASSWORD = __ENV.ASO_PASSWORD || "";
const PROFILE  = (__ENV.ASO_AI_PROFILE || "chat_solo").toLowerCase();
const CHAT_TEXT = __ENV.ASO_CHAT_TEXT || "¿Qué es una biopsia? Responde en máximo 2 oraciones.";

// ── Métricas personalizadas ──────────────────────────────────────────────────
const chatDuration  = new Trend("ai_chat_duration",  true);
const histoDuration = new Trend("ai_histo_duration", true);
const aiErrorRate   = new Rate("ai_errors");

// ── Configuración de escenarios ──────────────────────────────────────────────
const SCENARIOS = {
  chat_solo: {
    scenarios: {
      chat: { executor: "shared-iterations", vus: 1, iterations: 4, maxDuration: "15m" },
    },
    thresholds: { ai_errors: ["rate<0.10"] },
    mode: "chat",
  },
  chat_concurrent: {
    scenarios: {
      chat: { executor: "shared-iterations", vus: 4, iterations: 12, maxDuration: "20m" },
    },
    thresholds: { ai_errors: ["rate<0.20"] },
    mode: "chat",
  },
  histo_solo: {
    scenarios: {
      histo: { executor: "shared-iterations", vus: 1, iterations: 4, maxDuration: "10m" },
    },
    thresholds: { ai_errors: ["rate<0.10"] },
    mode: "histo",
  },
  histo_concurrent: {
    scenarios: {
      histo: { executor: "shared-iterations", vus: 4, iterations: 12, maxDuration: "15m" },
    },
    thresholds: { ai_errors: ["rate<0.20"] },
    mode: "histo",
  },
  combined: {
    scenarios: {
      chat:  { executor: "shared-iterations", vus: 2, iterations: 6, maxDuration: "20m" },
      histo: { executor: "shared-iterations", vus: 2, iterations: 6, maxDuration: "15m" },
    },
    thresholds: { ai_errors: ["rate<0.20"] },
    mode: "combined",
  },
};

const selected = SCENARIOS[PROFILE] || SCENARIOS.chat_solo;
export const options = {
  scenarios: selected.scenarios,
  thresholds: selected.thresholds,
};

// ── Setup ────────────────────────────────────────────────────────────────────
export function setup() {
  if (!EMAIL || !PASSWORD) throw new Error("Define ASO_EMAIL y ASO_PASSWORD.");

  const login = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(login, { "login ok": (r) => r.status === 200 });
  const token = login.json("access_token");

  // Obtener imagen disponible para histopatología
  const imgList = http.get(`${BASE_URL}/api/medical-images/list`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  let imageId = null;
  if (imgList.status === 200) {
    const imgs = imgList.json();
    if (Array.isArray(imgs) && imgs.length > 0) {
      imageId = imgs[0].id;
    }
  }

  return { token, imageId };
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function headers(token) {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

function runChat(token) {
  group("chat_ia", () => {
    const start = Date.now();
    const r = http.post(
      `${BASE_URL}/api/chat`,
      JSON.stringify({ text: CHAT_TEXT }),
      { headers: headers(token), timeout: "180s", tags: { type: "ai_chat" } }
    );
    const elapsed = Date.now() - start;
    chatDuration.add(elapsed);
    const ok = check(r, {
      "chat 2xx":          (res) => res.status >= 200 && res.status < 300,
      "chat tiene answer": (res) => {
        try { return Boolean(res.json("answer") || res.json("response") || res.json("text")); }
        catch { return res.body && res.body.length > 10; }
      },
    });
    aiErrorRate.add(!ok);
    console.log(`[chat] ${r.status} | ${elapsed}ms`);
  });
}

function runHisto(token, imageId) {
  if (!imageId) {
    console.warn("[histo] Sin imagen disponible — omitiendo iteración.");
    aiErrorRate.add(1);
    return;
  }
  group("histo_ia", () => {
    const body = JSON.stringify({
      image_id: imageId,
      roi_1: { x: 0,   y: 0,   width: 512, height: 512 },
      roi_2: { x: 256, y: 256, width: 256, height: 256 },
    });
    const start = Date.now();
    const r = http.post(
      `${BASE_URL}/api/histopathology/analyze-roi`,
      body,
      { headers: headers(token), timeout: "120s", tags: { type: "ai_histo" } }
    );
    const elapsed = Date.now() - start;
    histoDuration.add(elapsed);
    const ok = check(r, {
      "histo 2xx":          (res) => res.status >= 200 && res.status < 300,
      "histo tiene clase":  (res) => {
        try { return Boolean(res.json("clase") || res.json("result") || res.json("classification")); }
        catch { return res.body && res.body.length > 5; }
      },
    });
    aiErrorRate.add(!ok);
    console.log(`[histo] ${r.status} | ${elapsed}ms`);
  });
}

// ── Escenario principal ──────────────────────────────────────────────────────
export default function (data) {
  const { token, imageId } = data;
  const scenarioName = __ENV.K6_SCENARIO_NAME || "";

  if (selected.mode === "chat") {
    runChat(token);
  } else if (selected.mode === "histo") {
    runHisto(token, imageId);
  } else {
    // combined: cada escenario nombrado decide qué corre
    if (scenarioName === "histo") {
      runHisto(token, imageId);
    } else {
      runChat(token);
    }
  }

  sleep(0.5);
}
