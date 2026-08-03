import test from "node:test";
import assert from "node:assert/strict";
import {
  parseStandardHref,
  parseStandardRef,
  STANDARD_HREF_PREFIX,
} from "../lib/standards-markdown";
import {
  markdownUrlTransform,
  normalizeMarkdownForDisplay,
} from "../lib/markdown-display";

test("parseStandardRef matches docId + section", () => {
  assert.deepEqual(parseStandardRef("〔规范: bbox-guide§边界框绘制〕"), {
    docId: "bbox-guide",
    section: "边界框绘制",
  });
});

test("parseStandardRef matches docId without section", () => {
  assert.deepEqual(parseStandardRef("〔规范: bbox-guide〕"), {
    docId: "bbox-guide",
  });
});

test("parseStandardRef trims spaces around colon and section separator", () => {
  assert.deepEqual(parseStandardRef("〔规范: bbox-guide § 边界框绘制 〕"), {
    docId: "bbox-guide",
    section: "边界框绘制",
  });
});

test("parseStandardRef returns null for non-standard text", () => {
  assert.equal(parseStandardRef("普通文本"), null);
  assert.equal(parseStandardRef("〔规范:〕"), null);
});

test("parseStandardRef finds the first ref inside a paragraph", () => {
  assert.deepEqual(
    parseStandardRef("请参照〔规范: bbox-guide§边界框绘制〕来完成标注。"),
    { docId: "bbox-guide", section: "边界框绘制" },
  );
});

test("parseStandardRef does not match ascii bracket lookalikes", () => {
  assert.equal(parseStandardRef("[规范: bbox-guide]"), null);
});

test("parseStandardHref round-trips docId + section", () => {
  const href = `${STANDARD_HREF_PREFIX}bbox-guide§边界框绘制`;
  assert.deepEqual(parseStandardHref(href), {
    docId: "bbox-guide",
    section: "边界框绘制",
  });
});

test("parseStandardHref round-trips docId only", () => {
  const href = `${STANDARD_HREF_PREFIX}bbox-guide`;
  assert.deepEqual(parseStandardHref(href), { docId: "bbox-guide" });
});

test("parseStandardHref returns null for non-standard hrefs", () => {
  assert.equal(parseStandardHref("#references"), null);
  assert.equal(parseStandardHref("attachment:foo.pdf"), null);
  assert.equal(parseStandardHref("https://example.com"), null);
  assert.equal(parseStandardHref(undefined), null);
});

test("markdownUrlTransform keeps standard: scheme hrefs", () => {
  const href = `${STANDARD_HREF_PREFIX}bbox-guide§边界框绘制`;
  assert.equal(
    markdownUrlTransform(href, "href", { tagName: "a" }),
    href,
  );
});

test("normalizeMarkdownForDisplay passes 〔规范: ...〕 markers through untouched", () => {
  const input = "请参照〔规范: bbox-guide§边界框绘制〕完成标注。";
  assert.equal(normalizeMarkdownForDisplay(input), input);
});
