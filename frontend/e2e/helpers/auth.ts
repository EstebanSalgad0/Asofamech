import type { Page } from "@playwright/test";
import { type RoleKey, testUsers } from "../fixtures/e2e-data";

function base64Url(payload: unknown) {
  return Buffer.from(JSON.stringify(payload)).toString("base64url");
}

export function sessionFor(role: RoleKey) {
  const user = testUsers[role];
  const token = [
    base64Url({ alg: "HS256", typ: "JWT" }),
    base64Url({
      sub: String(user.id),
      email: user.email,
      name: user.name,
      role: user.role,
      exp: Math.floor(Date.now() / 1000) + 60 * 60,
    }),
    "e2e-signature",
  ].join(".");

  return {
    auth_token: token,
    role: user.roleLabel,
    user: {
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
      role_label: user.roleLabel,
      is_active: true,
      account_status: "approved",
    },
  };
}

export async function signInAs(page: Page, role: RoleKey = "student", path = "/dashboard") {
  const session = sessionFor(role);

  await page.goto("/auth", { waitUntil: "domcontentloaded" });
  await page.evaluate((state) => {
    localStorage.clear();
    sessionStorage.clear();
    localStorage.setItem("auth_token", state.auth_token);
    localStorage.setItem("user", JSON.stringify(state.user));
    localStorage.setItem("role", state.role);
  }, session);
  await page.goto(path, { waitUntil: "domcontentloaded" });
}

export async function clearSession(page: Page) {
  await page.goto("/auth", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
}
