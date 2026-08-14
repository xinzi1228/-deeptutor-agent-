import test from "node:test";
import assert from "node:assert/strict";

import {
  clampBox,
  moveBox,
  resizeBox,
  validateBoxes,
  type Bbox,
} from "../components/annotation/bbox/bbox-geometry";
import {
  createBboxState,
  reduceBboxState,
} from "../components/annotation/bbox/bbox-reducer";

const bounds = { width: 100, height: 80 };
const box: Bbox = { id: "a", x: 10, y: 10, w: 20, h: 20, label: "车辆" };

test("move and resize stay inside the source image", () => {
  assert.deepEqual(moveBox(box, 500, 500, bounds), { ...box, x: 80, y: 60 });
  assert.deepEqual(resizeBox(box, "nw", -20, -20, bounds), {
    ...box,
    x: 0,
    y: 0,
    w: 30,
    h: 30,
  });
  assert.deepEqual(clampBox({ ...box, x: -4, y: 70, w: 200, h: 30 }, bounds), {
    ...box,
    x: 0,
    y: 70,
    w: 100,
    h: 10,
  });
});

test("eight-way resize keeps a minimum visible box", () => {
  const resized = resizeBox(box, "se", -100, -100, bounds, 4);
  assert.equal(resized.w, 4);
  assert.equal(resized.h, 4);
  assert.equal(resized.x, box.x);
  assert.equal(resized.y, box.y);
});

test("local validation reports invalid and duplicate boxes", () => {
  const issues = validateBoxes([
    box,
    { ...box, id: "duplicate" },
    { id: "tiny", x: 1, y: 1, w: 1, h: 1, label: "行人" },
  ], bounds, 4);
  assert.ok(issues.some((issue) => issue.code === "duplicate"));
  assert.ok(issues.some((issue) => issue.code === "too-small"));
});

test("bbox reducer supports selection, label change, delete, undo and redo", () => {
  let state = createBboxState([box], "车辆");
  state = reduceBboxState(state, { type: "select", id: "a" });
  state = reduceBboxState(state, { type: "set-selected-label", label: "行人" });
  assert.equal(state.boxes[0].label, "行人");
  state = reduceBboxState(state, { type: "delete-selected" });
  assert.equal(state.boxes.length, 0);
  state = reduceBboxState(state, { type: "undo" });
  assert.equal(state.boxes.length, 1);
  state = reduceBboxState(state, { type: "redo" });
  assert.equal(state.boxes.length, 0);
});
