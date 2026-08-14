import test from "node:test";
import assert from "node:assert/strict";

import { buildResponseProgress } from "../lib/response-progress";

test("uses real teaching events as the response progress source", () => {
  const progress = buildResponseProgress(
    [
      {
        type: "progress",
        content: "已接收问题",
        metadata: { teaching_event: "run.accepted" },
      },
      {
        type: "progress",
        content: "正在读取当前学习任务",
        metadata: { teaching_event: "context.loaded" },
      },
      {
        type: "progress",
        content: "正在检索已审核资料",
        metadata: { teaching_event: "retrieval.started" },
      },
    ],
    true,
  );

  assert.equal(progress.visible, true);
  assert.equal(progress.status, "running");
  assert.equal(progress.currentEvent, "retrieval.started");
  assert.equal(progress.label, "正在检索已审核资料");
  assert.equal(progress.completedSteps, 3);
});

test("completed and failed events expose honest terminal state", () => {
  const completed = buildResponseProgress(
    [
      {
        type: "progress",
        content: "回答完成",
        metadata: { teaching_event: "run.completed" },
      },
    ],
    false,
  );
  assert.equal(completed.status, "completed");

  const failed = buildResponseProgress(
    [
      {
        type: "error",
        content: "模型超时，可重试",
        metadata: { teaching_event: "run.failed", retryable: true },
      },
    ],
    false,
  );
  assert.equal(failed.status, "failed");
  assert.equal(failed.canRetry, true);
  assert.equal(failed.label, "模型超时，可重试");
});

test("does not invent progress when the backend emitted no teaching event", () => {
  const progress = buildResponseProgress(
    [{ type: "thinking", content: "内部思考", metadata: {} }],
    true,
  );

  assert.equal(progress.visible, false);
});
