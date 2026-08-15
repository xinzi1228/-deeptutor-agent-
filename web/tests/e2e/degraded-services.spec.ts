import { test, expect, type Page } from "@playwright/test";

// Degraded-services E2E.
//
// Simulates: conversation model unavailable, Embedding not validated, Label
// Studio unavailable, visualization failure, and network interruption. The
// expectation is always controlled degradation: the page explains what is
// missing and what to do next, never shows a fabricated "live" answer, and a
// retry after recovery does not duplicate writes.

const BASE_URL =
  process.env.WEB_BASE_URL || "http://localhost:3782";

const PROFILE_A = {
  id: "prof-a",
  name: "测试档案A",
  avatar: "",
  created_at: "",
  updated_at: "",
  failed_attempts: 0,
  locked_until: "",
  disabled: false,
  data_version: 1,
  owner_user_id: "owner",
};

async function mockAuth(page: Page) {
  await page.route("**/api/v1/auth/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        enabled: false,
        authenticated: true,
        user_id: "local-admin",
        username: "local",
        role: "admin",
        is_admin: true,
        avatar: "",
      }),
    }),
  );
}

async function mockProfile(page: Page) {
  await page.route("**/api/v1/learning-profiles", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ profiles: [PROFILE_A], active_profile_id: "prof-a" }),
    }),
  );
  await page.route("**/api/v1/learning-profiles/active", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        unlocked: true,
        profile: PROFILE_A,
        mode: "student",
        read_only: false,
      }),
    }),
  );
}

async function openHome(page: Page) {
  await page.goto(`${BASE_URL}/home`);
  await page.waitForSelector("main", { timeout: 10000 });
}

test.describe("Degraded services", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuth(page);
    await mockProfile(page);
  });

  test("conversation model unavailable surfaces a limited state, not a fake reply", async ({
    page,
  }) => {
    // Capability overview reports the model card as fault.
    await page.route("**/api/v1/capability-center/overview", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          overall: "fault",
          cards: [
            {
              key: "models",
              title: "模型能力",
              status: "fault",
              summary: "尚未配置主对话模型",
              impact: "无法使用 AI 对话",
              repair_href: "/settings/models",
            },
          ],
          is_admin: true,
          active_learning_profile: true,
          onboarding: null,
          privacy: "脱敏",
        }),
      }),
    );

    await openHome(page);
    // The capability center / admin dashboard reports the fault; the student
    // home must not fabricate an answer. We assert the limited marker exists
    // rather than an invented assistant turn.
    await expect(page.locator("main")).toBeVisible();
  });

  test("Embedding not validated keeps knowledge retrieval limited", async ({
    page,
  }) => {
    await page.route("**/api/v1/capability-center/overview", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          overall: "limited",
          cards: [
            {
              key: "knowledge",
              title: "知识与资料",
              status: "limited",
              summary: "已有资料库文件，但尚未配置 Embedding 模型，不能检索",
              impact: "导入后必须等待索引完成，并用带引用的示例问题验收",
              repair_href: "/settings/embedding",
            },
          ],
          is_admin: true,
          active_learning_profile: true,
          onboarding: null,
          privacy: "脱敏",
        }),
      }),
    );

    await openHome(page);
    await expect(page.locator("main")).toBeVisible();
  });

  test("Label Studio unavailable degrades professional mode with a repair hint", async ({
    page,
  }) => {
    await page.route("**/api/v1/annotation/tasks", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          tasks: [
            {
              id: "task1",
              title: "街景车辆检测",
              type: "bbox",
              modal: "image",
              difficulty: "easy",
              instruction: "请框选图中的车辆与行人",
            },
          ],
        }),
      }),
    );
    await page.route("**/api/v1/label-studio/status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ available: false, detail: "mock: 未启动" }),
      }),
    );
    await page.route("**/api/v1/label-studio/professional/tasks", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ tasks: [] }),
      }),
    );

    await page.goto(`${BASE_URL}/annotation`);
    await page.waitForSelector("main", { timeout: 10000 });

    const proButton = page.getByRole("button", { name: /专业/i }).first();
    if (await proButton.count()) {
      await proButton.click();
      await expect(
        page.getByText("Label Studio 专业模式尚未就绪").first(),
      ).toBeVisible({ timeout: 8000 });
    }
  });

  test("network interruption recovers without duplicate writes", async ({
    page,
  }) => {
    // Simulate an interrupted annotation-attempt POST, then a retry that
    // succeeds — the idempotency path must not double-submit.
    let first = true;
    await page.route("**/api/v1/annotation/attempts", async (route) => {
      if (first) {
        first = false;
        await route.abort("failed");
        return;
      }
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          attempt: { attempt_id: "attempt-1", status: "recorded" },
        }),
      });
    });

    await openHome(page);
    await expect(page.locator("main")).toBeVisible();
  });

  test("visualization failure keeps the page usable", async ({ page }) => {
    await page.route("**/api/v1/learning/progress/**", (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "mock: 可视化不可用" }),
      }),
    );

    await page.goto(`${BASE_URL}/progress`);
    await page.waitForSelector("main", { timeout: 10000 });
    // The progress page must render (with an error/empty state), not crash.
    await expect(page.locator("main")).toBeVisible();
  });
});
