import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

import {
  chooseCompatibleTask,
  isTaskCompatibleWithMode,
} from "../lib/annotation-edit-session";

const tasks = [
  { id: "image-1", modal: "image" as const },
  { id: "text-1", modal: "text" as const },
];

test("switching modality never keeps an incompatible task selected", () => {
  assert.equal(isTaskCompatibleWithMode(tasks[0], "text"), false);
  assert.equal(chooseCompatibleTask(tasks, "text", "image-1"), "");
  assert.equal(chooseCompatibleTask(tasks, "text", "text-1"), "text-1");
  assert.equal(chooseCompatibleTask(tasks, "pro", "image-1"), "image-1");
});

test("annotation page uses edit lease and exposes explicit takeover", () => {
  const source = readFileSync(
    path.resolve(process.cwd(), "app/(workspace)/annotation/page.tsx"),
    "utf8",
  );
  assert.match(source, /acquireAnnotationEditLease/);
  assert.match(source, /接管编辑/);
  assert.match(source, /chooseCompatibleTask/);
  assert.match(source, /readOnly=\{!editAccess\.editable\}/);
});
