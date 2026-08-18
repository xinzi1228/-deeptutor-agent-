import assert from "node:assert/strict";
import { test } from "node:test";
import { createBboxState, reduceBboxState } from "../components/annotation/bbox/bbox-reducer";
import type { Bbox } from "../components/annotation/bbox/bbox-geometry";

const box = (id: string, label = "car"): Bbox => ({ id, x: 10, y: 10, w: 30, h: 30, label });

test("增量 add/update/delete 产生可撤销历史", () => {
  let s = createBboxState([], "car");
  s = reduceBboxState(s, { type: "add", box: box("a") });
  s = reduceBboxState(s, { type: "add", box: box("b") });
  assert.equal(s.boxes.length, 2);
  assert.equal(s.past.length, 2);
  s = reduceBboxState(s, { type: "undo" });
  assert.equal(s.boxes.length, 1);
  s = reduceBboxState(s, { type: "redo" });
  assert.equal(s.boxes.length, 2);
});

test("undo 后 selectedIds 为空", () => {
  let s = createBboxState([], "car");
  s = reduceBboxState(s, { type: "add", box: box("a") });
  s = reduceBboxState(s, { type: "select", ids: ["a"] });
  assert.deepEqual(s.selectedIds, ["a"]);
  s = reduceBboxState(s, { type: "undo" });
  assert.deepEqual(s.selectedIds, []);
});

test("replace-external 只清历史当外部变化", () => {
  let s = createBboxState([box("a")], "car");
  s = reduceBboxState(s, { type: "add", box: box("b") });
  assert.equal(s.past.length, 1);
  s = reduceBboxState(s, { type: "replace-external", boxes: [box("a"), box("b"), box("c")] });
  assert.equal(s.past.length, 0);
});

test("多选 + 批量删除", () => {
  let s = createBboxState([], "car");
  s = reduceBboxState(s, { type: "add", box: box("a") });
  s = reduceBboxState(s, { type: "add", box: box("b") });
  s = reduceBboxState(s, { type: "select", ids: ["a", "b"] });
  assert.deepEqual(s.selectedIds, ["a", "b"]);
  s = reduceBboxState(s, { type: "delete-selected" });
  assert.equal(s.boxes.length, 0);
  assert.deepEqual(s.selectedIds, []);
});

test("select-toggle 加选/减选", () => {
  let s = createBboxState([], "car");
  s = reduceBboxState(s, { type: "add", box: box("a") });
  s = reduceBboxState(s, { type: "add", box: box("b") });
  s = reduceBboxState(s, { type: "clear-selection" });
  s = reduceBboxState(s, { type: "select-toggle", id: "a" });
  s = reduceBboxState(s, { type: "select-toggle", id: "b" });
  assert.deepEqual(s.selectedIds, ["a", "b"]);
  s = reduceBboxState(s, { type: "select-toggle", id: "a" });
  assert.deepEqual(s.selectedIds, ["b"]);
});

test("批量改标签", () => {
  let s = createBboxState([], "car");
  s = reduceBboxState(s, { type: "add", box: box("a", "car") });
  s = reduceBboxState(s, { type: "add", box: box("b", "car") });
  s = reduceBboxState(s, { type: "select", ids: ["a", "b"] });
  s = reduceBboxState(s, { type: "set-selected-label", label: "person" });
  assert.ok(s.boxes.every((b) => b.label === "person"));
});
