import assert from "node:assert/strict";
import { test } from "node:test";
import { labelColorFor, labelHotkeyFor } from "../components/annotation/bbox/label-style";

test("labelColorFor 对同一标签稳定", () => {
  assert.equal(labelColorFor("car"), labelColorFor("car"));
  assert.notEqual(labelColorFor("car"), labelColorFor("person"));
});

test("labelHotkeyFor 前 9 个标签分配 1-9", () => {
  assert.equal(labelHotkeyFor(0), "1");
  assert.equal(labelHotkeyFor(8), "9");
  assert.equal(labelHotkeyFor(9), null);
});
