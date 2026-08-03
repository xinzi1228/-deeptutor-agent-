import test from "node:test";
import assert from "node:assert/strict";
import {
  containsStandardMarker,
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

test("parseStandardHref decodes percent-encoded § and CJK (coach output path)", () => {
  const href = `${STANDARD_HREF_PREFIX}bbox-guide%C2%A7%E9%81%AE%E6%8C%A1%E7%9B%AE%E6%A0%87%E5%A4%84%E7%90%86`;
  assert.deepEqual(parseStandardHref(href), {
    docId: "bbox-guide",
    section: "遮挡目标处理",
  });
});

test("parseStandardHref tolerates invalid percent-encoding without crashing", () => {
  // decodeURIComponent throws on %ZZ; the function must not crash and should
  // fall back to the raw href. Whether the section parses depends on the raw
  // bytes — the important guarantee is "no throw".
  const href = `${STANDARD_HREF_PREFIX}bbox-guide%C2%A7%ZZ`;
  const result = parseStandardHref(href);
  assert.ok(result);
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

test("containsStandardMarker detects a marker-only message", () => {
  assert.equal(containsStandardMarker("〔规范: bbox-guide§边界框绘制〕"), true);
  assert.equal(containsStandardMarker("〔规范: bbox-guide〕"), true);
});

test("containsStandardMarker detects the marker inside surrounding prose", () => {
  assert.equal(
    containsStandardMarker("请参照〔规范: bbox-guide〕完成标注。"),
    true,
  );
});

test("containsStandardMarker is monotonic on a partial streaming marker", () => {
  assert.equal(containsStandardMarker("请参照〔规范:"), true);
  assert.equal(containsStandardMarker("〔规范: bbox-guide§边"), true);
});

test("containsStandardMarker rejects plain text and ascii lookalikes", () => {
  assert.equal(containsStandardMarker("普通文本"), false);
  assert.equal(containsStandardMarker("[规范: bbox-guide]"), false);
  assert.equal(containsStandardMarker(""), false);
});
