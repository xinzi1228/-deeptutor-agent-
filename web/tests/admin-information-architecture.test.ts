import test from "node:test";
import assert from "node:assert/strict";

import {
  ADMIN_CENTERS,
  adminCenterForPath,
  legacyAdminRedirectFor,
  roleAreaForPath,
  settingsCenterFor,
} from "../lib/capability-routes";
import {
  SETTINGS_CATEGORIES,
  categoriesForCenter,
  categoriesForRole,
} from "../lib/settings-nav";

// ── Admin five centers ───────────────────────────────────────────────────

test("admin workspaces expose exactly five centers with unique hrefs", () => {
  assert.equal(ADMIN_CENTERS.length, 5);
  const keys = new Set(ADMIN_CENTERS.map((c) => c.key));
  assert.equal(keys.size, 5, "center keys must be unique");
  const hrefs = new Set(ADMIN_CENTERS.map((c) => c.href));
  assert.equal(hrefs.size, 5, "center hrefs must be unique");
  for (const center of ADMIN_CENTERS) {
    assert.ok(center.href.startsWith("/admin/"), center.href);
    assert.ok(center.label.length > 0);
    assert.ok(center.blurb.length > 0);
  }
});

test("the five centers match the competition design order", () => {
  assert.deepEqual(
    ADMIN_CENTERS.map((c) => c.key),
    ["content", "teaching", "ai", "integrations", "operations"],
  );
});

test("adminCenterForPath maps each center route", () => {
  for (const center of ADMIN_CENTERS) {
    assert.equal(adminCenterForPath(center.href)?.key, center.key);
    assert.equal(adminCenterForPath(`${center.href}/sub`)?.key, center.key);
  }
  assert.equal(adminCenterForPath("/admin"), null);
  assert.equal(adminCenterForPath("/admin/users"), null);
  assert.equal(adminCenterForPath("/home"), null);
});

// ── Role area gate ───────────────────────────────────────────────────────

test("roleAreaForPath separates admin, teacher and public areas", () => {
  assert.equal(roleAreaForPath("/admin"), "admin");
  assert.equal(roleAreaForPath("/admin/content"), "admin");
  assert.equal(roleAreaForPath("/admin/users"), "admin");
  assert.equal(roleAreaForPath("/teacher"), "teacher");
  assert.equal(roleAreaForPath("/teacher/anything"), "teacher");
  assert.equal(roleAreaForPath("/home"), "public");
  assert.equal(roleAreaForPath("/settings"), "public");
  // Segment-boundary safety: a sibling route is never swallowed.
  assert.equal(roleAreaForPath("/administrator"), "public");
  assert.equal(roleAreaForPath("/teachers"), "public");
});

// ── Legacy redirects ─────────────────────────────────────────────────────

test("legacy admin URLs keep working via compatible redirects", () => {
  assert.equal(legacyAdminRedirectFor("/capabilities"), "/admin");
  assert.equal(legacyAdminRedirectFor("/capabilities/"), "/admin");
  assert.equal(legacyAdminRedirectFor("/settings/status"), "/admin");
  assert.equal(legacyAdminRedirectFor("/settings/llm"), null);
  assert.equal(legacyAdminRedirectFor("/home"), null);
});

// ── Settings re-grouped into the five centers ────────────────────────────

test("every admin-only settings category belongs to exactly one center", () => {
  const adminCategories = categoriesForRole("admin");
  for (const category of adminCategories) {
    if (category.adminOnly) {
      const center = settingsCenterFor(category.key);
      assert.ok(center, `admin-only category "${category.key}" must map to a center`);
      assert.ok(
        ADMIN_CENTERS.some((c) => c.key === center),
        `center "${center}" must be a known admin center`,
      );
    }
  }
});

test("student-facing settings stay out of the centers", () => {
  assert.equal(settingsCenterFor("appearance"), null);
});

test("settingsCategoriesForCenter groups categories under the owning center", () => {
  const ai = categoriesForCenter("ai");
  assert.ok(ai.some((c) => c.key === "models"));
  assert.ok(ai.some((c) => c.key === "memory"));
  assert.ok(ai.some((c) => c.key === "agents"));
  const integrations = categoriesForCenter("integrations");
  assert.ok(integrations.some((c) => c.key === "chat"));
  const content = categoriesForCenter("content");
  assert.ok(content.some((c) => c.key === "knowledge"));
  const operations = categoriesForCenter("operations");
  assert.ok(operations.some((c) => c.key === "network"));
});

test("centers never include the student appearance category", () => {
  const centered = SETTINGS_CATEGORIES.filter((c) => c.center !== undefined);
  assert.ok(centered.every((c) => c.key !== "appearance"));
});
