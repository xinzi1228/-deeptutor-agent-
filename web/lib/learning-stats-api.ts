const API_BASE = "/api/v1/profile";

export interface ProfileOverview {
  total_tasks_completed: number;
  tasks_passed: number;
  pass_rate: number;
  total_theory_mastered: number;
  latest_f1: number | null;
  latest_precision: number | null;
  latest_recall: number | null;
  teaching_mode: string | null;
  mission: string | null;
  goal_type: string | null;
}

export interface RadarDimension {
  name: string;
  english: string;
  score: number;
  max: number;
}

export interface F1Point {
  task_id: string;
  f1: number;
  precision: number;
  recall: number;
  difficulty: string;
  date: string;
}

export interface SkillTreeNode {
  name: string;
  id: string;
  level: number;
  mastered?: boolean;
  mastered_count?: number;
  total_leaves?: number;
  children?: SkillTreeNode[];
}

export interface DecisionLog {
  kind: string;
  target: string;
  rationale: string;
  evidence?: unknown;
  timestamp?: string;
}

export interface CoursePlanModule {
  name: string;
  concepts: string[];
  tasks: string[];
  target: string;
}

export interface CoursePlan {
  plan_id: string;
  teaching_mode: string;
  goal_type: string;
  modules: CoursePlanModule[];
  dag: Record<string, string[]>;
}

export interface TeachingEvaluation {
  plan: string;
  student_profile?: string;
  evaluation: string;
  timestamp?: string;
}

export interface Episode {
  date: string;
  count: number;
  records: Record<string, any>[];
}

export interface ForesightStats {
  total: number;
  verified: number;
  hits: number;
  hit_rate: number | null;
  open: number;
}

export interface CoachMetrics {
  f1_growth: number | null;
  latest_f1: number | null;
  pattern_confirmation_rate: number | null;
  foresight_hit_rate: number | null;
  teaching_improvements: number;
  decision_audit_entries: number;
  tasks_completed: number;
}

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${url} returned ${res.status}`);
  return res.json();
}

export function getLearningOverview(): Promise<{ overview: ProfileOverview }> {
  return fetchJSON(API_BASE);
}

export function getRadarDimensions(): Promise<{ dimensions: RadarDimension[] }> {
  return fetchJSON(`${API_BASE}/radar`);
}

export function getF1Trend(): Promise<{ points: F1Point[] }> {
  return fetchJSON(`${API_BASE}/f1-trend`);
}

export function getSkillTree(): Promise<{ tree: SkillTreeNode }> {
  return fetchJSON(`${API_BASE}/skill-tree`);
}

export function getDecisions(): Promise<{ decisions: DecisionLog[] }> {
  return fetchJSON(`${API_BASE}/decisions`);
}

export function getEvaluations(): Promise<{ evaluations: TeachingEvaluation[] }> {
  return fetchJSON(`${API_BASE}/evaluations`);
}

export function getCoursePlan(): Promise<{ plan: CoursePlan }> {
  return fetchJSON(`${API_BASE}/course-plan`);
}

export function getCoursePlanDocx(): Promise<{ docx: { url: string | null; path: string } }> {
  return fetchJSON(`${API_BASE}/course-plan/docx`);
}

export function getEpisodes(): Promise<{ episodes: Episode[] }> {
  return fetchJSON(`${API_BASE}/episodes`);
}

export function getForesightStats(): Promise<ForesightStats> {
  return fetchJSON(`${API_BASE}/foresights`);
}

export function getCoachMetrics(): Promise<CoachMetrics> {
  return fetchJSON(`${API_BASE}/coach-metrics`);
}

export async function reflectMemory(): Promise<{ reflect: { clusters_merged: number; records_archived: number; active_records: number } }> {
  const res = await fetch(`${API_BASE}/reflect`, { method: "POST" });
  if (!res.ok) throw new Error(`API reflect returned ${res.status}`);
  return res.json();
}
