import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

test("home task context and student summary share one profile-keyed request", () => {
  const api = readFileSync(path.resolve(process.cwd(), "lib/student-dashboard-api.ts"), "utf8");
  const taskContext = readFileSync(path.resolve(process.cwd(), "components/current-task/CurrentLearningTaskContext.tsx"), "utf8");
  const summary = readFileSync(path.resolve(process.cwd(), "components/student-shell/StudentHomeSummary.tsx"), "utf8");

  assert.match(api, /const homeRequests = new Map<string/);
  assert.match(api, /getStudentHomeDashboard\(profileId/);
  assert.match(taskContext, /getStudentHomeDashboard\(active\.id/);
  assert.match(summary, /getStudentHomeDashboard\(active\.id/);
});

test("growth core is aggregated while heavy analysis remains user-triggered", () => {
  const progress = readFileSync(path.resolve(process.cwd(), "app/(workspace)/progress/page.tsx"), "utf8");
  assert.match(progress, /getStudentGrowthDashboard\(profileId/);
  assert.match(progress, /async function loadOverviewDetails/);
  assert.match(progress, /onClick=\{\(\) => void loadOverviewDetails\(\)\}/);
});
