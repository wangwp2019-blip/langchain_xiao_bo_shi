import { test, expect } from "@playwright/test";

/**
 * UI 冒烟：需设置 E2E_UI_URL。
 * 完整流程（mock JWT + 出题判分）见 flows-ui.spec.ts。
 */
test.describe("UI 冒烟", () => {
  test.skip(!process.env.E2E_UI_URL, "未设置 E2E_UI_URL 时跳过 UI 测试");

  test("首页可加载", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body")).toBeVisible({ timeout: 15_000 });
  });
});
