import test from "node:test";
import assert from "node:assert/strict";

import { isStudentRouteAllowed, STUDENT_NAVIGATION } from "../lib/student-experience";
import { categoriesForRole } from "../lib/settings-nav";

test("student navigation exposes exactly four product-language entries", () => {
  assert.deepEqual(STUDENT_NAVIGATION.map(({ href, label }) => ({ href, label })), [
    { href: "/home", label: "学习" },
    { href: "/annotation", label: "实训" },
    { href: "/progress", label: "成长" },
    { href: "/settings", label: "我的" },
  ]);
});

test("student route allow-list blocks infrastructure pages even by direct URL", () => {
  for (const path of ["/home/session-1", "/annotation", "/progress", "/settings", "/settings/appearance"]) assert.equal(isStudentRouteAllowed(path), true, path);
  for (const path of ["/capabilities", "/memory", "/standards", "/tasks", "/settings/models", "/settings/mcp", "/settings/agents/codex"]) assert.equal(isStudentRouteAllowed(path), false, path);
});

test("student settings only exposes personal appearance while admin keeps infrastructure", () => {
  assert.deepEqual(categoriesForRole("student").map((item) => item.key), ["appearance"]);
  assert.ok(categoriesForRole("admin").some((item) => item.key === "models"));
  assert.ok(categoriesForRole("admin").some((item) => item.key === "agents"));
});

