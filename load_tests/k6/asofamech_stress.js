/**
 * ASOFAMECH - Stress / Load test
 *
 * Perfiles disponibles via env ASO_PROFILE:
 *   smoke   – 3 VUs, 1 min  (verificacion rapida)
 *   load    – rampa hasta 20 VUs durante 4 min (carga normal)
 *   stress  – rampa hasta 40 VUs durante 7 min (limite de la plataforma)
 *   spike   – pico abrupto de 50 VUs, 30 s     (resistencia a picos)
 */
import http from "k6/http";
import { check, group, sleep } from "k6";
import { Trend, Rate, Counter } from "k6/metrics";

const BASE_URL = (__ENV.ASO_BASE_URL || "http://localhost:8001").replace(/\/$/, "");
const EMAIL    = __ENV.ASO_EMAIL    || "";
const PASSWORD = __ENV.ASO_PASSWORD || "";
const PROFILE  = (__ENV.ASO_PROFILE || "load").toLowerCase();

// ── Métricas personalizadas ──────────────────────────────────────────────────
const dashboardDuration = new Trend("dashboard_req_duration", true);
const contentDuration   = new Trend("content_req_duration",   true);
const historyDuration   = new Trend("history_req_duration",   true);
const errorRate         = new Rate("errors");
const requestsTotal     = new Counter("requests_total");

// ── Perfiles de carga ────────────────────────────────────────────────────────
const PROFILES = {
  smoke: {
    vus: 3,
    duration: "1m",
    thresholds: {
      "http_req_duration{type:api}":    ["p(95)<2000"],
      "http_req_duration{type:auth}":   ["p(95)<1500"],
      "http_req_duration{type:health}": ["p(95)<500"],
      http_req_failed: ["rate<0.05"],
      errors:          ["rate<0.05"],
    },
  },
  load: {
    stages: [
      { duration: "30s", target: 5  },
      { duration: "1m",  target: 10 },
      { duration: "1m",  target: 20 },
      { duration: "1m",  target: 20 },
      { duration: "30s", target: 0  },
    ],
    thresholds: {
      "http_req_duration{type:api}":    ["p(95)<2500", "p(99)<5000"],
      "http_req_duration{type:auth}":   ["p(95)<1500"],
      "http_req_duration{type:health}": ["p(95)<600"],
      http_req_failed: ["rate<0.05"],
      errors:          ["rate<0.05"],
      dashboard_req_duration: ["p(95)<2500"],
      content_req_duration:   ["p(95)<2000"],
      history_req_duration:   ["p(95)<2000"],
    },
  },
  stress: {
    stages: [
      { duration: "30s", target: 10 },
      { duration: "1m",  target: 20 },
      { duration: "1m",  target: 30 },
      { duration: "2m",  target: 40 },
      { duration: "1m",  target: 40 },
      { duration: "1m",  target: 0  },
    ],
    thresholds: {
      "http_req_duration{type:api}":    ["p(95)<5000"],
      "http_req_duration{type:health}": ["p(95)<1000"],
      http_req_failed: ["rate<0.10"],
      errors:          ["rate<0.10"],
    },
  },
  spike: {
    stages: [
      { duration: "10s", target: 5  },
      { duration: "30s", target: 50 },
      { duration: "1m",  target: 50 },
      { duration: "30s", target: 5  },
      { duration: "10s", target: 0  },
    ],
    thresholds: {
      "http_req_duration{type:health}": ["p(95)<1000"],
      http_req_failed: ["rate<0.15"],
    },
  },
};

const selected = PROFILES[PROFILE] || PROFILES.load;
export const options = {
  ...(selected.stages ? { stages: selected.stages } : { vus: selected.vus, duration: selected.duration }),
  thresholds: selected.thresholds,
};

// ── Setup: login una vez, token compartido ───────────────────────────────────
export function setup() {
  const health = http.get(`${BASE_URL}/health`, { tags: { type: "health" } });
  check(health, { "health ok": (r) => r.status === 200 });

  if (!EMAIL || !PASSWORD) {
    throw new Error("Define ASO_EMAIL y ASO_PASSWORD.");
  }

  const login = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" }, tags: { type: "auth" } }
  );
  check(login, { "login ok": (r) => r.status === 200 });
  return { token: login.json("access_token") };
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function headers(token) {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

function get(url, tag, token) {
  requestsTotal.add(1);
  const r = http.get(`${BASE_URL}${url}`, { headers: headers(token), tags: { type: "api", endpoint: tag } });
  const ok = check(r, { [`${tag} 2xx`]: (res) => res.status >= 200 && res.status < 300 });
  errorRate.add(!ok);
  return r;
}

// ── Escenario principal ──────────────────────────────────────────────────────
export default function (data) {
  const token = data.token;

  // 1. Dashboard (métricas del usuario actual)
  group("dashboard", () => {
    const t0 = Date.now();
    get("/api/auth/me",            "auth_me",           token);
    get("/api/dashboard/stats",    "dashboard_stats",   token);
    get("/api/dashboard/ranking",  "dashboard_ranking", token);
    dashboardDuration.add(Date.now() - t0);
  });

  sleep(0.5);

  // 2. Contenido (listas que devuelven paginación)
  group("content", () => {
    const t0 = Date.now();
    get("/api/sct/list",              "sct_list",          token);
    get("/api/cases",                 "cases_list",        token);
    get("/api/medical-images/list",   "images_list",       token);
    contentDuration.add(Date.now() - t0);
  });

  sleep(0.5);

  // 3. Historial personal
  group("history", () => {
    const t0 = Date.now();
    get("/api/history/me?limit=10",       "history_me",       token);
    get("/api/history/sct-attempts",       "history_sct",      token);
    get("/api/history/conversations",      "history_chat",     token);
    historyDuration.add(Date.now() - t0);
  });

  sleep(1);
}
