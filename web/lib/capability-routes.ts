/**
 * Model capability a feature depends on. As of the multi-user release, the only
 * per-user-grantable model capability is the LLM — embedding/search are shared
 * admin infrastructure and are never gated per user.
 */
export type Capability = "llm";

/**
 * Single source of truth mapping a workspace feature route to the model
 * capability it needs in order to function. Features absent from this list
 * require no per-user model and are always available (Knowledge, Space,
 * Memory, Notebook, Settings, …).
 *
 * Both the sidebar (to lock nav items) and the route-level CapabilityGate
 * (to lock the page itself) read from here, so a new gated feature only has
 * to be declared once.
 */
export const ROUTE_CAPABILITIES: ReadonlyArray<{
  prefix: string;
  capability: Capability;
}> = [
  { prefix: "/home", capability: "llm" },
  { prefix: "/partners", capability: "llm" },
  { prefix: "/co-writer", capability: "llm" },
  { prefix: "/book", capability: "llm" },
  { prefix: "/space/learning", capability: "llm" }, // Mastery Path
  { prefix: "/playground", capability: "llm" },
];

/**
 * Returns the capability required for a pathname, or null if none is needed.
 * Matches on a path-segment boundary (exact, or prefix followed by "/") so a
 * sibling route like "/booket" can never be swallowed by the "/book" prefix.
 */
export function capabilityForPath(pathname: string): Capability | null {
  const match = ROUTE_CAPABILITIES.find(
    (r) => pathname === r.prefix || pathname.startsWith(`${r.prefix}/`),
  );
  return match ? match.capability : null;
}

/**
 * Human-facing phrase for a capability, used in the "ask your admin" copy.
 * Kept as plain English keys so react-i18next can translate them later.
 */
export const CAPABILITY_LABEL: Record<Capability, string> = {
  llm: "an LLM model",
};

/**
 * The five admin workspaces (管理员五中心). Single source of truth for the
 * center routes surfaced in the admin nav, the admin dashboard cards and the
 * route gate. Kept dependency-free so it can be unit-tested under `node:test`.
 */
export type AdminCenterKey =
  | "content"
  | "teaching"
  | "ai"
  | "integrations"
  | "operations";

export interface AdminCenterInfo {
  key: AdminCenterKey;
  href: string;
  label: string;
  en: string;
  blurb: string;
}

export const ADMIN_CENTERS: readonly AdminCenterInfo[] = [
  {
    key: "content",
    href: "/admin/content",
    label: "内容治理",
    en: "Content",
    blurb: "教材导入、转换任务、知识条目、题库、引用、版本、审核与发布",
  },
  {
    key: "teaching",
    href: "/admin/teaching",
    label: "教学配置",
    en: "Teaching",
    blurb: "课程、场景、能力图谱、任务分配、评分规则和教师授权",
  },
  {
    key: "ai",
    href: "/admin/ai",
    label: "AI 能力",
    en: "AI",
    blurb: "对话、Embedding、生图模型，连接测试、用量与评测",
  },
  {
    key: "integrations",
    href: "/admin/integrations",
    label: "扩展与集成",
    en: "Integrations",
    blurb: "Skill、MCP、学习插件、Label Studio、权限与健康状态",
  },
  {
    key: "operations",
    href: "/admin/operations",
    label: "系统运维",
    en: "Operations",
    blurb: "账号角色、备份、审计、体检、失败任务、性能和脱敏诊断",
  },
];

export function adminCenterForPath(pathname: string): AdminCenterInfo | null {
  return ADMIN_CENTERS.find(
    (c) => pathname === c.href || pathname.startsWith(`${c.href}/`),
  ) ?? null;
}

/**
 * Role area a route belongs to for the frontend gate. `/admin/*` is admin-only
 * (the backend enforces the same policy); `/teacher` is the teacher workspace
 * and only requires an authenticated session. Anything else is not an
 * admin/teacher area — students and the workspace shell handle their own gates.
 */
export type RoleArea = "admin" | "teacher" | "public";

export function roleAreaForPath(pathname: string): RoleArea {
  if (pathname === "/admin" || pathname.startsWith("/admin/")) return "admin";
  if (pathname === "/teacher" || pathname.startsWith("/teacher/"))
    return "teacher";
  return "public";
}

/**
 * Legacy admin URLs that must keep working after the workspace reorganisation.
 * Visiting one redirects to the new location (admin area). Keys are matched on
 * a segment boundary.
 */
export const LEGACY_ADMIN_REDIRECTS: Readonly<Record<string, string>> = {
  "/capabilities": "/admin",
  "/settings/status": "/admin",
};

export function legacyAdminRedirectFor(pathname: string): string | null {
  for (const [legacy, target] of Object.entries(LEGACY_ADMIN_REDIRECTS)) {
    if (pathname === legacy || pathname.startsWith(`${legacy}/`)) return target;
  }
  return null;
}

/**
 * Maps the admin-only settings categories to the admin center that owns them,
 * so "设置内容按五中心重新归类" has a single machine-readable source. The
 * frontend nav and center pages read from here instead of duplicating labels.
 */
export const SETTINGS_CENTER_ASSIGNMENT: Readonly<
  Record<string, AdminCenterKey>
> = {
  network: "operations",
  models: "ai",
  knowledge: "content",
  chat: "integrations",
  agents: "ai",
  memory: "ai",
};

export function settingsCenterFor(
  categoryKey: string,
): AdminCenterKey | null {
  return SETTINGS_CENTER_ASSIGNMENT[categoryKey] ?? null;
}
