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
