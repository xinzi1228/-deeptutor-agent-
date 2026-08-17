import assert from "node:assert/strict";
import { test, beforeEach, afterEach } from "node:test";
import { getViewIdentity, setViewIdentity, isStudentView, type ViewIdentity } from "../lib/view-identity";

const KEY = "deeptutor_view_identity";

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

test("默认身份为学生（AUTH 关闭场景）", () => {
  assert.equal(getViewIdentity(), "student");
});

test("setViewIdentity 持久化", () => {
  setViewIdentity("staff");
  assert.equal(localStorage.getItem(KEY), "staff");
  assert.equal(getViewIdentity(), "staff");
});

test("isStudentView 正确判断", () => {
  assert.equal(isStudentView("student"), true);
  assert.equal(isStudentView("staff"), false);
});

test("非法值回退到学生", () => {
  localStorage.setItem(KEY, "banana");
  assert.equal(getViewIdentity(), "student");
});
