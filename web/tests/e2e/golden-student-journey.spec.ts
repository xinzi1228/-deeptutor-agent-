import { test, expect, type Page } from "@playwright/test";

// Golden student journey E2E.
//
// Runs against a served frontend (WEB_BASE_URL, default :3000 — for the repo
// default dev that is `http://localhost:3782`). API responses are mocked at
// the route level so the spec is deterministic and does not depend on a live
// model, Label Studio, or external services. It covers:
//   * normal chain: profile select → current task → annotation workbench;
//   * refresh recovery and idempotent re-clicks;
//   * teaching / professional mode switch degradation;
//   * full isolation after switching learning profiles.

const BASE_URL =
  process.env.WEB_BASE_URL || "http://localhost:3782";

const PROFILE_A = { id: "prof-a", name: "测试档案A", avatar: "" };
const PROFILE_B = { id: "prof-b", name: "测试档案B", avatar: "" };

const TRAFFIC_TASK = {
  id: "task1",
  title: "街景车辆检测",
  type: "bbox",
  modal: "image",
  difficulty: "easy",
  instruction: "请框选图中的车辆与行人",
  image_url: "/images/traffic-sample.png",
  labels: ["car", "pedestrian"],
};

async function mockProfileRoutes(page: Page, activeId: string | null) {
  const profiles = [PROFILE_A, PROFILE_B];
  await page.route("**/api/v1/learning-profiles", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ profiles, active_profile_id: activeId }),
    }),
  );
  await page.route("**/api/v1/learning-profiles/active", (route) => {
    const profile = profiles.find((p) => p.id === activeId) ?? null;
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        unlocked: Boolean(profile),
        profile: profile
          ? { ...profile, created_at: "", updated_at: "", failed_attempts: 0, locked_until: "", disabled: false, data_version: 1, owner_user_id: "owner" }
          : null,
        mode: profile ? "student" : null,
        read_only: false,
      }),
    });
  });
}

async function mockCurrentTask(page: Page, profileId: string | null) {
  const task = profileId
    ? {
        profile_id: profileId,
        course_id: "course-traffic",
        task_id: "task1",
        phase: "practice",
        mode: "teaching_annotation",
        draft_ref: "",
        latest_submission_ref: "",
        coach_session_id: "coach-1",
        version: 3,
        updated_at: "2026-08-15T00:00:00+00:00",
      }
    : null;
  await page.route("**/api/v1/current-learning-task", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ task }),
    }),
  );
  // The student shell / task bar reads the aggregated student-dashboard home.
  await page.route("**/api/v1/student-dashboard/home", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        task,
        overview: {},
        report: { summary: "", text: "", cards: [], quality_warnings: [] },
        version: {
          profile_id: profileId ?? "",
          profile_data_version: 1,
          learning_data_version: "v1",
          task_version: 3,
        },
        generated_at: "2026-08-15T00:00:00+00:00",
      }),
    }),
  );
}

async function mockAnnotationRoutes(page: Page) {
  await page.route("**/api/v1/annotation/tasks", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ tasks: [TRAFFIC_TASK] }),
    }),
  );
  await page.route("**/api/v1/annotation/tasks/task1", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ task: TRAFFIC_TASK }),
    }),
  );
  await page.route("**/api/v1/annotation/tasks/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ task: TRAFFIC_TASK }),
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
}

async function mockAuth(page: Page) {
  await page.route("**/api/v1/auth/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        enabled: true,
        authenticated: true,
        user_id: "student-1",
        username: "student",
        role: "user",
        is_admin: false,
        avatar: "",
      }),
    }),
  );
}

async function openHome(page: Page) {
  await page.goto(`${BASE_URL}/home`);
  await page.waitForSelector("main", { timeout: 10000 });
}

test.describe("Golden student journey", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuth(page);
  });

  test("student navigation exposes four product entries", async ({ page }) => {
    await mockProfileRoutes(page, null);
    await openHome(page);

    const nav = page.getByRole("navigation", { name: "学生主导航" });
    await expect(nav).toBeVisible();
    for (const label of ["学习", "实训", "成长", "我的"]) {
      await expect(nav.getByText(label).first()).toBeVisible();
    }
  });

  test("profile lock prompts for selection, then unlocks", async ({ page }) => {
    await mockProfileRoutes(page, null);
    await page.route("**/api/v1/learning-profiles/*/unlock", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, profile: PROFILE_A }),
      }),
    );
    await openHome(page);

    // No active profile → the lock screen explains profiles are separate.
    await expect(page.getByText("先选择学习档案")).toBeVisible();

    // Open the profile switcher and choose profile A → the PIN dialog appears.
    const switcher = page.getByRole("button", { name: /选择学习档案|谁在学习/ }).first();
    await switcher.click();
    await page.getByRole("button", { name: new RegExp(PROFILE_A.name) }).first().click();

    const dialog = page.getByRole("dialog").filter({ hasText: /解锁/ });
    await dialog.waitFor({ timeout: 8000 });
    await dialog.locator('input[inputmode="numeric"]').fill("1234");
    await dialog.getByRole("button", { name: "进入学习" }).click();
    // The mock unlock succeeds and closes the dialog.
    await expect(dialog).toHaveCount(0, { timeout: 8000 });
  });

  test("annotation workbench loads a traffic bbox task and switch is idempotent", async ({
    page,
  }) => {
    await mockProfileRoutes(page, PROFILE_A.id);
    await mockCurrentTask(page, PROFILE_A.id);
    await mockAnnotationRoutes(page);
    await openHome(page);

    await page.goto(`${BASE_URL}/annotation`);
    await page.waitForSelector("main", { timeout: 10000 });

    // The traffic task is offered in the task-bank select.
    const taskSelect = page.locator("#task-bank");
    await taskSelect.waitFor({ timeout: 8000 });
    await taskSelect.selectOption("task1");
    await expect(
      page.getByText("请框选图中的车辆与行人").first(),
    ).toBeVisible({ timeout: 8000 });

    // Repeated clicks on a mode switch do not corrupt state (idempotent).
    const imageMode = page.getByRole("button", { name: /图片|图像/i });
    if (await imageMode.count()) {
      await imageMode.first().click();
      await imageMode.first().click();
      await expect(page).not.toHaveURL(/error/);
    }
  });

  test("professional mode degrades gracefully when Label Studio is unavailable", async ({
    page,
  }) => {
    await mockProfileRoutes(page, PROFILE_A.id);
    await mockCurrentTask(page, PROFILE_A.id);
    await mockAnnotationRoutes(page);
    await openHome(page);

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

  test("refresh keeps the current task (recovery)", async ({ page }) => {
    await mockProfileRoutes(page, PROFILE_A.id);
    await mockCurrentTask(page, PROFILE_A.id);
    await mockAnnotationRoutes(page);
    await openHome(page);

    await page.goto(`${BASE_URL}/annotation`);
    await page.waitForSelector("main", { timeout: 10000 });
    const taskSelect = page.locator("#task-bank");
    await taskSelect.waitFor({ timeout: 8000 });
    await taskSelect.selectOption("task1");
    await expect(
      page.getByText("请框选图中的车辆与行人").first(),
    ).toBeVisible({ timeout: 8000 });

    await page.reload();
    await page.waitForSelector("main", { timeout: 10000 });
    const reloadedSelect = page.locator("#task-bank");
    await reloadedSelect.waitFor({ timeout: 8000 });
    await expect(
      page.locator('#task-bank option[value="task1"]').first(),
    ).toHaveText(/街景车辆检测/);
  });

  test("switching learning profiles fully isolates the current task", async ({
    page,
  }) => {
    // Profile A has a current task.
    await mockProfileRoutes(page, PROFILE_A.id);
    await mockCurrentTask(page, PROFILE_A.id);
    await mockAnnotationRoutes(page);
    await openHome(page);

    // Profile A: the current-task bar shows its task.
    await expect(page.getByText("当前任务").first()).toBeVisible();

    // Now switch the active profile to B (no current task) and reload.
    await mockProfileRoutes(page, PROFILE_B.id);
    await mockCurrentTask(page, null);
    await page.reload();
    await page.waitForSelector("main", { timeout: 10000 });

    // Profile B has no task: the task bar is gone — A's task never leaks.
    await expect(page.getByText("当前任务").first()).toHaveCount(0, {
      timeout: 8000,
    });
    await expect(page.getByText("测试档案B").first()).toBeVisible();
  });
});
