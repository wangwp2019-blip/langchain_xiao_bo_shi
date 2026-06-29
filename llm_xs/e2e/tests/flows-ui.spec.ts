import { test, expect } from "@playwright/test";
import { injectAuth } from "../helpers/mock-jwt";

test.describe("UI 全流程", () => {
  test.skip(!process.env.E2E_UI_URL, "未设置 E2E_UI_URL 时跳过 UI 测试");

  test("mock JWT → 出题判分", async ({ page }) => {
    await injectAuth(page, "e2e-ui-kid");
    await page.goto("/");
    await expect(page.getByText("小博士")).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /出题练习|Quiz/ }).click();
    await page.getByRole("button", { name: "出题" }).click();

    await expect(page.getByText(/第 1 题/)).toBeVisible({ timeout: 15_000 });

    const inputs = page.locator('input[placeholder*="答案"], input[placeholder*="Answer"]');
    const count = await inputs.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      await inputs.nth(i).fill("0");
    }

    await page.getByRole("button", { name: /提交判分|Submit/ }).click();
    await expect(page.getByText(/得分|Score/)).toBeVisible({ timeout: 15_000 });
  });
});
