/**
 * Resumable onboarding state machine helpers (mirror of the backend in
 * deeptutor/services/onboarding). Pure functions — no React, no network — so
 * they are unit-testable under `node:test`.
 *
 * Step order is fixed: account_security → llm → embedding → knowledge_base →
 * label_studio → health_check, with optional imagegen / mcp / skill.
 * The wizard resumes at the first core step that is not passed/skipped.
 */

export type OnboardingStepStatus =
  | "not_started"
  | "running"
  | "passed"
  | "failed"
  | "skipped"
  | "stale";

export type OnboardingAction = "done" | "skip" | "resume" | "retest" | "dismiss";

export interface StepState {
  status: OnboardingStepStatus;
  updated_at?: string;
  detail?: string;
  fingerprint?: string;
}

export interface OnboardingState {
  version: number;
  dismissed: boolean;
  updated_at?: string;
  steps: Record<string, StepState>;
  current_step?: string;
  completed?: string[];
  skipped?: string[];
  optional?: string[];
}

/** Fixed order of the core wizard. Index order is meaningful. */
export const CORE_STEPS = [
  "account_security",
  "llm",
  "embedding",
  "knowledge_base",
  "label_studio",
  "health_check",
] as const;

export const OPTIONAL_STEPS = ["imagegen", "mcp", "skill"] as const;

export const ALL_STEPS: readonly string[] = [
  ...CORE_STEPS,
  ...OPTIONAL_STEPS,
];

const TERMINAL = new Set<string>(["passed", "skipped"]);

export function isTerminal(status: string): boolean {
  return TERMINAL.has(status);
}

/** First core step (in fixed order) that is not passed/skipped. */
export function currentStep(state: OnboardingState): string {
  for (const key of CORE_STEPS) {
    const status = state.steps?.[key]?.status ?? "not_started";
    if (!isTerminal(status)) return key;
  }
  return CORE_STEPS[CORE_STEPS.length - 1];
}

export function completedSteps(state: OnboardingState): string[] {
  return ALL_STEPS.filter((key) => state.steps?.[key]?.status === "passed");
}

export function skippedSteps(state: OnboardingState): string[] {
  return ALL_STEPS.filter((key) => state.steps?.[key]?.status === "skipped");
}

/**
 * Apply one wizard action to a step and return a new state (immutable).
 * `done` records the live config fingerprint for staleness detection.
 */
export function applyAction(
  state: OnboardingState,
  stepKey: string,
  action: OnboardingAction,
  options?: { detail?: string; fingerprint?: string },
): OnboardingState {
  if (!(stepKey in (state.steps ?? {}))) {
    throw new Error(`未知的初始化步骤：${stepKey}`);
  }
  const now = new Date().toISOString();
  const steps = { ...state.steps };
  const step: StepState = { ...steps[stepKey] };

  switch (action) {
    case "done":
      step.status = "passed";
      step.updated_at = now;
      step.detail = options?.detail ?? "";
      step.fingerprint = options?.fingerprint ?? "";
      break;
    case "skip":
      step.status = "skipped";
      step.updated_at = now;
      step.detail = options?.detail ?? "";
      break;
    case "resume":
      step.status = "running";
      step.updated_at = now;
      step.detail = options?.detail ?? "";
      break;
    case "retest":
      step.status = "running";
      step.updated_at = now;
      step.detail = options?.detail ?? "";
      step.fingerprint = "";
      break;
    case "dismiss":
      return { ...state, dismissed: true, updated_at: now };
    default:
      throw new Error(`未知的初始化动作：${action}`);
  }
  steps[stepKey] = step;
  return { ...state, steps, updated_at: now };
}

/**
 * Degrade passed steps whose dependency config changed to `stale`.
 * Only steps that recorded a fingerprint during `done` can be checked.
 */
export function markStale(
  state: OnboardingState,
  liveFingerprints: Record<string, string>,
): OnboardingState {
  const steps = { ...state.steps };
  let changed = false;
  for (const key of ALL_STEPS) {
    const stored = steps[key];
    if (!stored || stored.status !== "passed") continue;
    const recorded = stored.fingerprint ?? "";
    if (!recorded) continue;
    const live = liveFingerprints[key];
    if (live && live !== recorded) {
      steps[key] = {
        ...stored,
        status: "stale",
        detail: "依赖配置已变化，请重新验证",
      };
      changed = true;
    }
  }
  return changed
    ? { ...state, steps, updated_at: new Date().toISOString() }
    : state;
}

/** Map a legacy 1-based wizard step number to a new core step key. */
export function legacyIntToKey(index: number): string {
  const safe = Math.max(1, Math.min(CORE_STEPS.length, Math.round(index)));
  return CORE_STEPS[safe - 1];
}
