import test from "node:test";
import assert from "node:assert/strict";

import { normalizePerformanceMetric } from "../lib/performance-metrics";

test("normalizePerformanceMetric keeps only the privacy whitelist", () => {
  const metric = normalizePerformanceMetric({
    name: "route_visible",
    route: "/progress?student=secret",
    duration_ms: 321.456,
    outcome: "success",
    stage: "rendered",
    tool_calls: 2,
    error_type: "",
    build_version: "build-1",
    conversation: "private",
  } as never);

  assert.deepEqual(metric, {
    name: "route_visible",
    route: "/progress",
    duration_ms: 321.46,
    outcome: "success",
    stage: "rendered",
    tool_calls: 2,
    error_type: "",
    build_version: "build-1",
  });
  assert.equal("conversation" in metric, false);
});

test("normalizePerformanceMetric rejects invalid routes and durations", () => {
  assert.throws(() =>
    normalizePerformanceMetric({
      name: "route_visible",
      route: "https://example.com/private",
      duration_ms: 1,
    }),
  );
  assert.throws(() =>
    normalizePerformanceMetric({
      name: "route_visible",
      route: "/home",
      duration_ms: -1,
    }),
  );
});
