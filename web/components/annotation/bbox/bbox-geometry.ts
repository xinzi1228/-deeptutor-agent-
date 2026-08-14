export type Bbox = {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
};

export type ImageBounds = { width: number; height: number };
export type ResizeHandle = "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw";
export type BboxIssueCode = "out-of-bounds" | "zero-area" | "too-small" | "duplicate";
export type BboxIssue = { boxId: string; code: BboxIssueCode; message: string };

const finite = (value: number, fallback = 0) => Number.isFinite(value) ? value : fallback;
const within = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function clampBox(box: Bbox, bounds: ImageBounds): Bbox {
  const width = Math.max(1, finite(bounds.width, 1));
  const height = Math.max(1, finite(bounds.height, 1));
  const x = within(finite(box.x), 0, width);
  const y = within(finite(box.y), 0, height);
  const w = within(finite(box.w), 0, width - x);
  const h = within(finite(box.h), 0, height - y);
  return { ...box, x, y, w, h };
}

export function moveBox(box: Bbox, dx: number, dy: number, bounds: ImageBounds): Bbox {
  return {
    ...box,
    x: within(box.x + finite(dx), 0, Math.max(0, bounds.width - box.w)),
    y: within(box.y + finite(dy), 0, Math.max(0, bounds.height - box.h)),
  };
}

export function resizeBox(
  box: Bbox,
  handle: ResizeHandle,
  dx: number,
  dy: number,
  bounds: ImageBounds,
  minimum = 4,
): Bbox {
  const min = Math.max(1, minimum);
  let left = box.x;
  let top = box.y;
  let right = box.x + box.w;
  let bottom = box.y + box.h;
  if (handle.includes("w")) left = within(left + dx, 0, right - min);
  if (handle.includes("e")) right = within(right + dx, left + min, bounds.width);
  if (handle.includes("n")) top = within(top + dy, 0, bottom - min);
  if (handle.includes("s")) bottom = within(bottom + dy, top + min, bounds.height);
  return clampBox({ ...box, x: left, y: top, w: right - left, h: bottom - top }, bounds);
}

export function boxIou(first: Bbox, second: Bbox): number {
  const left = Math.max(first.x, second.x);
  const top = Math.max(first.y, second.y);
  const right = Math.min(first.x + first.w, second.x + second.w);
  const bottom = Math.min(first.y + first.h, second.y + second.h);
  const intersection = Math.max(0, right - left) * Math.max(0, bottom - top);
  const union = first.w * first.h + second.w * second.h - intersection;
  return union > 0 ? intersection / union : 0;
}

export function validateBoxes(
  boxes: Bbox[],
  bounds: ImageBounds,
  minimum = 4,
): BboxIssue[] {
  const issues: BboxIssue[] = [];
  boxes.forEach((box, index) => {
    if (box.w <= 0 || box.h <= 0) {
      issues.push({ boxId: box.id, code: "zero-area", message: `对象 ${index + 1} 没有有效面积` });
    } else if (box.w < minimum || box.h < minimum) {
      issues.push({ boxId: box.id, code: "too-small", message: `对象 ${index + 1} 小于最小尺寸 ${minimum}px` });
    }
    if (box.x < 0 || box.y < 0 || box.x + box.w > bounds.width || box.y + box.h > bounds.height) {
      issues.push({ boxId: box.id, code: "out-of-bounds", message: `对象 ${index + 1} 超出图片边界` });
    }
    const duplicate = boxes.slice(0, index).find(
      (candidate) => candidate.label === box.label && boxIou(candidate, box) >= 0.95,
    );
    if (duplicate) {
      issues.push({ boxId: box.id, code: "duplicate", message: `对象 ${index + 1} 与同类框几乎重复` });
    }
  });
  return issues;
}

export function toBbox(value: Record<string, unknown>, index: number): Bbox {
  return {
    id: String(value.id || `box-${index}`),
    x: Number(value.x || 0),
    y: Number(value.y || 0),
    w: Number(value.w || 0),
    h: Number(value.h || 0),
    label: String(value.label || "object"),
  };
}
