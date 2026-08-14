import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

import {
  clearBrowserAnnotationDraft,
  readBrowserAnnotationDraft,
  saveBrowserAnnotationDraft,
} from "../lib/learning-api";

test("browser drafts are isolated by profile and task", () => {
  const values = new Map<string, string>();
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      sessionStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
    },
  });
  saveBrowserAnnotationDraft({ profileId: "profile-a", taskId: "task-1", predictions: [{ label: "车" }], updatedAt: 1 });
  assert.equal(readBrowserAnnotationDraft("profile-a", "task-1")?.predictions[0].label, "车");
  assert.equal(readBrowserAnnotationDraft("profile-b", "task-1"), null);
  clearBrowserAnnotationDraft("profile-a", "task-1");
  assert.equal(readBrowserAnnotationDraft("profile-a", "task-1"), null);
  Reflect.deleteProperty(globalThis, "window");
});

test("unsynced local checks are never rendered as formal grades", () => {
  const source = readFileSync(
    path.resolve(process.cwd(), "components/annotation/UnifiedAnnotationWorkbench.tsx"),
    "utf8",
  );
  assert.match(source, /if \(!data\.finalized\)/);
  assert.match(source, /本地检查（非正式）/);
  assert.match(source, /retryPendingAnnotationRevisions/);
});
