import { test, expect } from "@playwright/test";

test.describe("API 冒烟", () => {
  test("health / ready", async ({ request }) => {
    const health = await request.get("/api/health");
    expect(health.ok()).toBeTruthy();
    const h = await health.json();
    expect(h.status).toBe("ok");

    const ready = await request.get("/api/ready");
    expect(ready.ok()).toBeTruthy();
    expect((await ready.json()).ready).toBe(true);
  });

  test("quiz → grade 闭环", async ({ request }) => {
    const quiz = await request.post("/api/quiz", {
      data: { grade: "三年级", subject: "数学", count: 3, seed: 42 },
    });
    expect(quiz.ok()).toBeTruthy();
    const body = await quiz.json();
    expect(body.session_id).toBeTruthy();
    expect(body.public?.questions?.length).toBe(3);
    expect(JSON.stringify(body)).not.toContain('"answer"');

    const answers: Record<string, string> = {};
    for (let i = 1; i <= 3; i++) answers[String(i)] = "0";

    const grade = await request.post("/api/grade", {
      data: { session_id: body.session_id, answers },
    });
    expect(grade.ok()).toBeTruthy();
    const g = await grade.json();
    expect(g.total).toBe(3);
    expect(g.score).toBeGreaterThanOrEqual(0);
    expect(g.score).toBeLessThanOrEqual(100);
    expect(g.items?.length).toBe(3);
  });

  test("离线算式 chat", async ({ request }) => {
    const chat = await request.post("/api/chat", {
      data: { question: "12 + 34 = ?", user_id: "e2e-kid", thread_id: "e2e" },
    });
    expect(chat.ok()).toBeTruthy();
    const c = await chat.json();
    expect(c.answer).toMatch(/46/);
  });
});
