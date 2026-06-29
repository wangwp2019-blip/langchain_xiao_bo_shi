import { test, expect } from "@playwright/test";

test.describe("API 全流程", () => {
  test("consent → chat 闭环", async ({ request }) => {
    const sub = `e2e-consent-${Date.now()}`;

    const status0 = await request.get(`/api/privacy/consent?sub=${sub}`);
    expect(status0.ok()).toBeTruthy();
    const s0 = await status0.json();
    if (s0.required) {
      const consent = await request.post("/api/privacy/consent", {
        data: { sub, parent_name: "E2E 家长" },
      });
      expect(consent.ok()).toBeTruthy();
      const s1 = await request.get(`/api/privacy/consent?sub=${sub}`);
      expect((await s1.json()).valid).toBe(true);
    }

    const chat = await request.post("/api/chat", {
      data: { question: "5 + 6 = ?", user_id: sub, thread_id: "e2e-flow" },
    });
    expect(chat.ok()).toBeTruthy();
    expect((await chat.json()).answer).toMatch(/11/);
  });

  test("chat/stream SSE 含 done 事件", async ({ request }) => {
    const resp = await request.post("/api/chat/stream", {
      data: { question: "8 + 1 = ?", user_id: "e2e-stream", thread_id: "e2e-s" },
    });
    expect(resp.ok()).toBeTruthy();
    const body = await resp.text();
    expect(body).toContain("data:");
    expect(body).toContain("9");
    expect(body).toContain("event: done");
    expect(body).toContain("[DONE]");
  });
});
