import assert from "node:assert/strict";
import { test, beforeEach, afterEach } from "node:test";
import {
  lastTaskKeyFor,
  readLastTaskFor,
  writeLastTaskFor,
  type AnnotationModeKey,
} from "../lib/annotation-mode-memory";

const PROFILE = "lp_test123";

const storage = new Map<string, string>();
const mockStorage = {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => {
    storage.set(key, value);
  },
  removeItem: (key: string) => {
    storage.delete(key);
  },
  clear: () => {
    storage.clear();
  },
  key: (index: number) => Array.from(storage.keys())[index] ?? null,
  get length() {
    return storage.size;
  },
};

(globalThis as any).window = { localStorage: mockStorage };
(globalThis as any).localStorage = mockStorage;

beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

test("lastTaskKeyFor 含 modal 后缀", () => {
  assert.equal(lastTaskKeyFor(PROFILE, "image"), "deeptutor_last_annotation_task.lp_test123.image");
  assert.equal(lastTaskKeyFor(PROFILE, "video"), "deeptutor_last_annotation_task.lp_test123.video");
});

test("write/read roundtrip", () => {
  writeLastTaskFor(PROFILE, "text", "task5");
  assert.equal(readLastTaskFor(PROFILE, "text"), "task5");
});

test("不同 modal 独立", () => {
  writeLastTaskFor(PROFILE, "image", "task1");
  writeLastTaskFor(PROFILE, "video", "task15");
  assert.equal(readLastTaskFor(PROFILE, "image"), "task1");
  assert.equal(readLastTaskFor(PROFILE, "video"), "task15");
  assert.equal(readLastTaskFor(PROFILE, "audio"), null);
});

test("无 profile 退化全局键", () => {
  assert.equal(lastTaskKeyFor("", "image"), "deeptutor_last_annotation_task.image");
});
