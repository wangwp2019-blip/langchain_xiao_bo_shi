/** E2E 用 mock JWT（前端仅校验 exp，不验签；后端开放模式或 API Key 模式均可联调） */
export function mockJwt(sub = "e2e-kid", expireSec = 3600): string {
  const enc = (obj: object) =>
    Buffer.from(JSON.stringify(obj))
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  const header = enc({ alg: "HS256", typ: "JWT" });
  const payload = enc({ sub, exp: Math.floor(Date.now() / 1000) + expireSec });
  return `${header}.${payload}.e2e-mock-signature`;
}

export function injectAuth(page: import("@playwright/test").Page, sub = "e2e-kid") {
  const token = mockJwt(sub);
  return page.addInitScript(
    ({ t, u }) => {
      localStorage.setItem("kid_access_token", t);
      localStorage.setItem("kid_user", JSON.stringify({ id: u, display_name: "E2E 小朋友" }));
    },
    { t: token, u: sub },
  );
}
