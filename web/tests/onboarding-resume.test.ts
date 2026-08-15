import test from "node:test";
import assert from "node:assert/strict";

import {
  ALL_STEPS,
  CORE_STEPS,
  OPTIONAL_STEPS,
  applyAction,
  completedSteps,
  currentStep,
  isTerminal,
  legacyIntToKey,
  markStale,
  skippedSteps,
  type OnboardingState,
} from "../lib/onboarding-resume";

function freshState(): OnboardingState {
  return {
    version: 2,
    dismissed: false,
    steps: Object.fromEntries(
      ALL_STEPS.map((key) => [key, { status: "not_started" as const }]),
    ),
  };
}

test("fixed wizard order matches the competition design", () => {
  assert.deepEqual(CORE_STEPS, [
    "account_security",
    "llm",
    "embedding",
    "knowledge_base",
    "label_studio",
    "health_check",
  ]);
  assert.deepEqual(OPTIONAL_STEPS, ["imagegen", "mcp", "skill"]);
});

test("default state resumes at the first core step", () => {
  const state = freshState();
  assert.equal(currentStep(state), "account_security");
});

test("done advances the resume point through the fixed order", () => {
  let state = freshState();
  state = applyAction(state, "account_security", "done");
  assert.equal(currentStep(state), "llm");
  state = applyAction(state, "llm", "done");
  state = applyAction(state, "embedding", "done");
  assert.equal(currentStep(state), "knowledge_base");
});

test("skip is terminal and preserves ordering", () => {
  const state = applyAction(freshState(), "account_security", "skip");
  assert.equal(isTerminal("skipped"), true);
  assert.equal(currentStep(state), "llm");
});

test("retest moves a passed step back to running", () => {
  let state = freshState();
  state = applyAction(state, "account_security", "done", { fingerprint: "abc" });
  state = applyAction(state, "account_security", "retest");
  assert.equal(state.steps["account_security"].status, "running");
  assert.equal(state.steps["account_security"].fingerprint, "");
  assert.equal(currentStep(state), "account_security");
});

test("resume marks the step running", () => {
  const state = applyAction(freshState(), "knowledge_base", "resume");
  assert.equal(state.steps["knowledge_base"].status, "running");
});

test("dismiss hides the wizard", () => {
  const state = applyAction(freshState(), "account_security", "dismiss");
  assert.equal(state.dismissed, true);
});

test("unknown step or action is rejected", () => {
  const state = freshState();
  assert.throws(() => applyAction(state, "nope", "done"));
  assert.throws(() => applyAction(state, "llm", "explode" as never));
});

test("a passed step degrades to stale when its dependency changes", () => {
  let state = freshState();
  state = applyAction(state, "account_security", "done", { fingerprint: "sec-1" });
  state = applyAction(state, "llm", "done", { fingerprint: "model-A" });
  state = applyAction(state, "embedding", "done", { fingerprint: "emb-1" });
  const stale = markStale(state, { llm: "model-B", embedding: "emb-1" });
  assert.equal(stale.steps["llm"].status, "stale");
  assert.equal(stale.steps["embedding"].status, "passed");
  assert.equal(currentStep(stale), "llm");
});

test("completed/skipped lists track terminal statuses", () => {
  let state = freshState();
  state = applyAction(state, "account_security", "done");
  state = applyAction(state, "llm", "skip");
  assert.deepEqual(completedSteps(state), ["account_security"]);
  assert.deepEqual(skippedSteps(state), ["llm"]);
});

test("legacy integer mapping covers core steps and clamps", () => {
  assert.equal(legacyIntToKey(1), "account_security");
  assert.equal(legacyIntToKey(6), "health_check");
  assert.equal(legacyIntToKey(99), "health_check");
  assert.equal(legacyIntToKey(0), "account_security");
});

test("immutable transitions leave the source state untouched", () => {
  const state = freshState();
  const next = applyAction(state, "account_security", "done");
  assert.equal(state.steps["account_security"].status, "not_started");
  assert.equal(next.steps["account_security"].status, "passed");
});
