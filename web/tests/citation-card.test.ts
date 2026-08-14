import test from "node:test";
import assert from "node:assert/strict";

import { extractKnowledgeCitations } from "../lib/knowledge-api";

test("citation events become deduplicated source cards", () => {
  const events = [
    {
      type: "sources",
      metadata: {
        sources: [
          {
            id: "citation:a",
            title: "数据标注规程",
            excerpt: "边界框应贴合目标。",
            page: "12",
            trust_level: "authoritative",
          },
          {
            id: "citation:a",
            title: "重复来源",
            page: "12",
          },
        ],
      },
    },
  ];

  const citations = extractKnowledgeCitations(events);

  assert.equal(citations.length, 1);
  assert.equal(citations[0].title, "数据标注规程");
  assert.equal(citations[0].page, "12");
  assert.equal(citations[0].trust_level, "authoritative");
});

test("query-only fallback is not presented as a real citation", () => {
  const citations = extractKnowledgeCitations([
    {
      type: "sources",
      metadata: {
        sources: [{ type: "rag", query: "边界框", kb_name: "demo" }],
      },
    },
  ]);

  assert.deepEqual(citations, []);
});

test("admin provenance details remain available when backend supplies them", () => {
  const [citation] = extractKnowledgeCitations([
    {
      type: "sources",
      metadata: {
        sources: [
          {
            id: "citation:b",
            title: "课程教材",
            trust_level: "high",
            admin_details: {
              version: "v3",
              content_hash: "sha256:abc",
              review_status: "approved",
            },
          },
        ],
      },
    },
  ]);

  assert.equal(citation.admin_details?.version, "v3");
  assert.equal(citation.admin_details?.content_hash, "sha256:abc");
});
