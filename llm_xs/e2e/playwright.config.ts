import { defineConfig } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:8001";
const apiKey = process.env.E2E_API_KEY || "";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL,
    extraHTTPHeaders: apiKey
      ? { Authorization: `Bearer ${apiKey}`, "X-API-Key": apiKey }
      : {},
  },
  projects: [
    { name: "api", testMatch: /api-smoke\.spec\.ts|flows-api\.spec\.ts/ },
    {
      name: "ui",
      testMatch: /ui-smoke\.spec\.ts|flows-ui\.spec\.ts/,
      use: { baseURL: process.env.E2E_UI_URL || "http://127.0.0.1:5173" },
    },
  ],
});
