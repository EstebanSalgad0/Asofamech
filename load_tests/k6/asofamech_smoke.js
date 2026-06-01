import http from "k6/http";
import { check, fail, group, sleep } from "k6";

const BASE_URL = (__ENV.ASO_BASE_URL || __ENV.K6_BASE_URL || "http://localhost:8001").replace(/\/$/, "");
const EMAIL = __ENV.ASO_EMAIL || __ENV.K6_EMAIL || "";
const PASSWORD = __ENV.ASO_PASSWORD || __ENV.K6_PASSWORD || "";
const INCLUDE_CHAT = String(__ENV.ASO_INCLUDE_CHAT || __ENV.K6_INCLUDE_CHAT || "false").toLowerCase() === "true";
const INCLUDE_ADMIN = String(__ENV.ASO_INCLUDE_ADMIN || __ENV.K6_INCLUDE_ADMIN || "false").toLowerCase() === "true";
const CHAT_TEXT = __ENV.ASO_CHAT_TEXT || __ENV.K6_CHAT_TEXT || "Explica brevemente que es una biopsia con fines educativos.";
const CHAT_P95_MS = Number(__ENV.ASO_CHAT_P95_MS || __ENV.K6_CHAT_P95_MS || 0);
const VUS = Number(__ENV.ASO_VUS || __ENV.K6_VUS || 5);
const DURATION = __ENV.ASO_DURATION || __ENV.K6_DURATION || "1m";
const ITERATIONS = Number(__ENV.ASO_ITERATIONS || __ENV.K6_ITERATIONS || 0);
const MAX_DURATION = __ENV.ASO_MAX_DURATION || __ENV.K6_MAX_DURATION || "10m";

const thresholds = {
  http_req_failed: ["rate<0.05"],
  "http_req_duration{type:health}": ["p(95)<500"],
  "http_req_duration{type:auth}": ["p(95)<1200"],
  "http_req_duration{type:api}": ["p(95)<1500"],
};

if (INCLUDE_CHAT && CHAT_P95_MS > 0) {
  thresholds["http_req_duration{type:chat}"] = [`p(95)<${CHAT_P95_MS}`];
}

function buildOptions() {
  const baseOptions = { thresholds };

  if (ITERATIONS > 0) {
    baseOptions.scenarios = {
      default: {
        executor: "shared-iterations",
        vus: VUS,
        iterations: ITERATIONS,
        maxDuration: MAX_DURATION,
      },
    };
    return baseOptions;
  }

  baseOptions.vus = VUS;
  baseOptions.duration = DURATION;
  return baseOptions;
}

export const options = buildOptions();

function jsonHeaders(token) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

function getApi(path, endpoint, token) {
  const response = http.get(`${BASE_URL}${path}`, {
    headers: jsonHeaders(token),
    tags: { endpoint, type: "api" },
  });
  check(response, {
    [`${endpoint} status 2xx`]: (r) => r.status >= 200 && r.status < 300,
  });
  return response;
}

export function setup() {
  const health = http.get(`${BASE_URL}/health`, {
    tags: { endpoint: "health", type: "health" },
  });
  check(health, { "health ok": (r) => r.status === 200 });

  if (!EMAIL || !PASSWORD) {
    fail("Define ASO_EMAIL y ASO_PASSWORD, o usa scripts/run_k6_smoke.ps1 -Email ... -Password ...");
  }

  const login = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    {
      headers: { "Content-Type": "application/json" },
      tags: { endpoint: "auth_login", type: "auth" },
    },
  );

  const loginOk = check(login, {
    "login ok": (r) => r.status === 200 && Boolean(r.json("access_token")),
  });

  if (!loginOk) {
    fail(`Login fallo: HTTP ${login.status} ${login.body}`);
  }

  return { token: login.json("access_token") };
}

export default function (data) {
  const token = data.token;

  group("dashboard", () => {
    getApi("/api/auth/me", "auth_me", token);
    getApi("/api/dashboard/stats", "dashboard_stats", token);
    getApi("/api/dashboard/ranking", "dashboard_ranking", token);
  });

  group("content", () => {
    getApi("/api/sct/list", "sct_list", token);
    getApi("/api/medical-images/list", "medical_images_list", token);
    getApi("/api/cases", "cases_list", token);
  });

  group("history", () => {
    getApi("/api/history/me?limit=5", "history_me", token);
  });

  if (INCLUDE_ADMIN) {
    group("admin", () => {
      getApi("/api/admin/audit-logs?limit=20", "admin_audit_logs", token);
      getApi("/api/admin/integrations/status", "admin_integrations_status", token);
    });
  }

  if (INCLUDE_CHAT) {
    group("chat_optional", () => {
      const response = http.post(
        `${BASE_URL}/api/chat`,
        JSON.stringify({ text: CHAT_TEXT }),
        {
          headers: jsonHeaders(token),
          tags: { endpoint: "chat", type: "chat" },
          timeout: "180s",
        },
      );
      check(response, {
        "chat status 2xx": (r) => r.status >= 200 && r.status < 300,
      });
    });
  }

  sleep(1);
}
