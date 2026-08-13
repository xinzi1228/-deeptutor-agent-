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

export interface LearningReportSummary {
  completed_count: number;
  average_f1: number | null;
  latest_f1: number | null;
  trend: "up" | "down" | "steady" | "unknown";
  strength: string | null;
  priority_gap: string | null;
  next_action: string;
  data_status: "sufficient" | "partial" | "empty";
  latest_task_id: string | null;
}

export interface LearningReport {
  summary: LearningReportSummary;
  text: string;
  quality_warnings: string[];
  presentation: "plain" | "cards";
  cards: { title: string; content: string }[];
}

export interface WorkspaceViews {
  inbox: { id: string; raw_text: string; source: string }[];
  mastered: { knowledge_point: string; evidence: string }[];
  confirmed_errors: string[];
  next_tasks: string[];
}

export interface LearningExtension {
  id: string;
  name: string;
  version: string;
  kind: "visualization" | "skill";
  description: string;
  permissions: string[];
  tools: string[];
  approved: boolean;
  installed: boolean;
  enabled: boolean;
}

export interface LearningPathDiagram {
  title: string;
  nodes: { id: string; label: string; status: "current" | "done" | "next" | "attention" | "goal" }[];
  edges: { from: string; to: string }[];
  notice: string;
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

export interface TraceItem {
  timestamp: string;
  date?: string | null;
  type: string;
  task_id?: string | null;
  knowledge_point?: string | null;
  f1?: number | null;
  precision?: number | null;
  recall?: number | null;
  readiness?: string | null;
  knowledge_points?: string[] | null;
  foresight_verified?: boolean;
  foresight_hit?: boolean;
  intervention?: {
    kind: string;
    target?: string;
    rationale?: string;
    timestamp?: string;
  } | null;
  decision?: {
    kind: string;
    target?: string;
    rationale?: string;
  } | null;
}

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${url} returned ${res.status}`);
  return res.json();
}

export function getLearningOverview(): Promise<{ overview: ProfileOverview }> {
  return fetchJSON(API_BASE);
}

export function getLearningReport(): Promise<LearningReport> {
  return fetchJSON(`${API_BASE}/report-summary`);
}

export function getWorkspaceViews(): Promise<{ views: WorkspaceViews }> {
  return fetchJSON(`${API_BASE}/workspace/views`);
}

export function getExtensionCatalog(): Promise<{ extensions: LearningExtension[] }> {
  return fetchJSON(`${API_BASE}/extensions/catalog`);
}

export async function installExtension(id: string): Promise<{ extension: LearningExtension }> {
  const res = await fetch(`${API_BASE}/extensions/${encodeURIComponent(id)}/install`, { method: "POST" });
  if (!res.ok) throw new Error(`安装扩展失败：${res.status}`);
  return res.json();
}

export async function setExtensionEnabled(id: string, enabled: boolean): Promise<{ extension: LearningExtension }> {
  const res = await fetch(`${API_BASE}/extensions/${encodeURIComponent(id)}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error(`更新扩展失败：${res.status}`);
  return res.json();
}

export async function getLearningPathDiagram(): Promise<{ diagram: LearningPathDiagram }> {
  return fetchJSON(`${API_BASE}/extensions/learning-path`);
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

export interface RiskNode {
  id: string;
  name: string;
}

export interface RiskChain {
  target: string;
  name: string;
  missing_prereqs: RiskNode[];
  affected_downstream: RiskNode[];
  confidence: string;
}

export interface KnowledgeGraphData {
  graph: { nodes: number; edges: number } | null;
  mastery: { mastered: RiskNode[]; struggling: RiskNode[] };
  risk_chains: RiskChain[];
}

export function getKnowledgeGraph(): Promise<KnowledgeGraphData> {
  return fetchJSON(`${API_BASE}/knowledge-graph`);
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

export async function getTraceLog(limit = 30): Promise<{ traces: TraceItem[] }> {
  const res = await fetch(`${API_BASE}/trace-log?limit=${limit}`, { credentials: "include" });
  if (!res.ok) throw new Error(`Failed to load trace log: ${res.status}`);
  return res.json();
}

export type TeachingFlowStep = {
  status: string;
  ts?: string | null;
  f1?: number | null;
  readiness?: string | null;
};

export type TeachingFlowState = {
  has_flow: boolean;
  task_id?: string | null;
  current_step?: string | null;
  expert?: string | null;
  blocked?: {
    step: string;
    reason: string;
    next_action: string;
  } | null;
  steps?: Record<string, TeachingFlowStep>;
};

export async function getTeachingFlow(): Promise<TeachingFlowState> {
  const res = await fetch(`${API_BASE}/teaching-flow`, { credentials: "include" });
  if (!res.ok) throw new Error(`Failed to load teaching flow: ${res.status}`);
  return res.json();
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
