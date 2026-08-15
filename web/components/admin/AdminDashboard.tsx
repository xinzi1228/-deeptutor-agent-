"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  BookOpenText,
  Bot,
  Download,
  Puzzle,
  RefreshCw,
  ServerCog,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { apiFetch, apiUrl } from "@/lib/api";
import { ADMIN_CENTERS } from "@/lib/capability-routes";
import AdminTaskCenter from "@/components/admin/AdminTaskCenter";

type State = "normal" | "limited" | "fault";
type Card = {
  key: string;
  title: string;
  status: State;
  summary: string;
  impact: string;
  repair_href: string;
};
type Overview = {
  overall: State;
  cards: Card[];
  is_admin: boolean;
  onboarding: {
    step: number;
    completed: number[];
    skipped: number[];
    dismissed: boolean;
  } | null;
  privacy: string;
  generated_at: string;
};

const CARD_ICONS: Record<string, LucideIcon> = {
  models: Bot,
  knowledge: BookOpenText,
  extensions: Puzzle,
  annotation: SlidersHorizontal,
  system: ServerCog,
};

const STATUS_LABEL: Record<State, string> = {
  normal: "正常",
  limited: "受限",
  fault: "故障",
};
const STATUS_STYLE: Record<State, string> = {
  normal: "bg-emerald-500/10 text-emerald-600",
  limited: "bg-amber-500/10 text-amber-600",
  fault: "bg-rose-500/10 text-rose-600",
};

/**
 * 管理员工作台首页 — the landing page of `/admin`. Prioritises what an admin
 * needs to act on (pending reviews, failed tasks, system health, onboarding
 * progress, high-risk alerts) instead of stacking configuration forms. The
 * five admin centers are reachable from the cards below; detailed config lives
 * in each center.
 */
export default function AdminDashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(apiUrl("/api/v1/capability-center/overview"), {
        cache: "no-store",
      });
      if (!res.ok) throw new Error("健康状态读取失败");
      setOverview((await res.json()) as Overview);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "健康状态读取失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch synchronizes the admin home with the capability state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, []);

  const downloadDiagnostics = async () => {
    const res = await apiFetch(apiUrl("/api/v1/capability-center/diagnostics"));
    if (!res.ok) return;
    const blob = new Blob([JSON.stringify(await res.json(), null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "标注星图-脱敏体检报告.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  const onboarded = overview?.onboarding
    ? overview.onboarding.completed.length
    : 0;
  const onboardingTotal = overview?.onboarding ? 7 : 0;
  const hasRisk =
    overview?.cards.some((card) => card.status === "fault") ?? false;

  return (
    <div className="min-h-full bg-[var(--background)] px-6 py-8 [scrollbar-gutter:stable]">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-violet-500/10 px-2.5 py-1 text-[11px] font-medium text-violet-600">
              <Sparkles className="h-3.5 w-3.5" />
              管理员工作台
            </div>
            <h1 className="font-serif text-3xl font-semibold tracking-tight">
              标注星图 · 运维总览
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted-foreground)]">
              先看系统现在能做什么、缺什么、哪里需要处理；具体配置在五个中心内完成。
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void downloadDiagnostics()}
              className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border)] px-3 py-2 text-xs"
            >
              <Download className="h-4 w-4" />
              下载脱敏报告
            </button>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--foreground)] px-3 py-2 text-xs text-[var(--background)]"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              重新检测
            </button>
          </div>
        </header>

        {error && (
          <div className="mt-6 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-600">
            {error}
          </div>
        )}

        {overview && (
          <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryCard
              label="系统健康"
              value={STATUS_LABEL[overview.overall]}
              tone={
                overview.overall === "fault"
                  ? "rose"
                  : overview.overall === "limited"
                    ? "amber"
                    : "emerald"
              }
              icon={<Activity className="h-5 w-5" />}
            />
            <SummaryCard
              label="初始化进度"
              value={`${onboarded}/${onboardingTotal}`}
              tone={onboarded >= onboardingTotal && onboardingTotal > 0 ? "emerald" : "violet"}
              icon={<Sparkles className="h-5 w-5" />}
              href="/admin"
            />
            <SummaryCard
              label="高风险管理"
              value={hasRisk ? "存在故障项" : "无"}
              tone={hasRisk ? "rose" : "emerald"}
              icon={<AlertTriangle className="h-5 w-5" />}
            />
            <SummaryCard
              label="脱敏与安全"
              value="严格白名单"
              tone="emerald"
              icon={<ShieldCheck className="h-5 w-5" />}
            />
          </section>
        )}

        {overview?.onboarding && !overview.onboarding.dismissed && (
          <Onboarding
            data={overview.onboarding}
            onSaved={() => void load()}
          />
        )}

        {!overview && loading && (
          <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-24 animate-pulse rounded-2xl bg-[var(--muted)]" />
            ))}
          </div>
        )}

        <div className="mt-6">
          <AdminTaskCenter />
        </div>

        <section className="mt-7">
          <h2 className="text-base font-semibold">五大管理中心</h2>
          <div className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {ADMIN_CENTERS.map((center) => {
              const Icon = CARD_ICONS[center.key] ?? ServerCog;
              const card = overview?.cards.find((c) =>
                centerOwnsCard(center.key, c.key),
              );
              return (
                <Link
                  key={center.key}
                  href={center.href}
                  className="group flex min-h-44 flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-[var(--foreground)]/20"
                >
                  <div className="flex items-start justify-between">
                    <span className="rounded-xl bg-[var(--muted)] p-2.5">
                      <Icon className="h-5 w-5" />
                    </span>
                    {card && (
                      <span className={`rounded-full border px-2 py-1 text-[10px] font-medium ${STATUS_STYLE[card.status]}`}>
                        {STATUS_LABEL[card.status]}
                      </span>
                    )}
                  </div>
                  <h3 className="mt-4 text-base font-semibold">{center.label}</h3>
                  <p className="mt-1.5 flex-1 text-xs leading-5 text-[var(--muted-foreground)]">
                    {center.blurb}
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-[var(--primary)]">
                    {card && card.status !== "normal" ? "去处理" : "进入"}
                    <span aria-hidden>→</span>
                  </span>
                </Link>
              );
            })}
          </div>
        </section>

        {overview?.privacy && (
          <div className="mt-7 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-xs text-[var(--muted-foreground)]">
            {overview.privacy}
          </div>
        )}
      </div>
    </div>
  );
}

function centerOwnsCard(centerKey: string, cardKey: string): boolean {
  const map: Record<string, string[]> = {
    content: ["knowledge"],
    teaching: ["annotation"],
    ai: ["models"],
    integrations: ["extensions"],
    operations: ["system"],
  };
  return (map[centerKey] ?? []).includes(cardKey);
}

function SummaryCard({
  label,
  value,
  tone,
  icon,
  href,
}: {
  label: string;
  value: string;
  tone: "emerald" | "amber" | "rose" | "violet";
  icon: React.ReactNode;
  href?: string;
}) {
  const tones: Record<string, string> = {
    emerald: "bg-emerald-500/10 text-emerald-600",
    amber: "bg-amber-500/10 text-amber-600",
    rose: "bg-rose-500/10 text-rose-600",
    violet: "bg-violet-500/10 text-violet-600",
  };
  const body = (
    <div className="flex h-24 flex-col justify-between rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
      <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
        <span className={`rounded-lg p-1.5 ${tones[tone]}`}>{icon}</span>
        {label}
      </div>
      <span className="text-xl font-semibold tabular-nums text-[var(--foreground)]">
        {value}
      </span>
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

const ONBOARDING_STEPS = [
  "检测运行环境",
  "配置主对话模型",
  "配置可选模型",
  "导入第一份资料",
  "启用审核扩展",
  "创建学生档案",
  "运行完整体检",
];

function Onboarding({
  data,
  onSaved,
}: {
  data: NonNullable<Overview["onboarding"]>;
  onSaved: () => void;
}) {
  const save = async (
    step: number,
    action: "done" | "skip" | "dismiss",
  ) => {
    const completed =
      action === "done"
        ? Array.from(new Set([...data.completed, step]))
        : data.completed;
    const skipped =
      action === "skip"
        ? Array.from(new Set([...data.skipped, step]))
        : data.skipped;
    await apiFetch(apiUrl("/api/v1/capability-center/onboarding"), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        step: Math.min(step + 1, 7),
        completed,
        skipped,
        dismissed: action === "dismiss",
      }),
    });
    onSaved();
  };
  const current = Math.min(Math.max(data.step, 1), 7);
  return (
    <section className="mt-6 rounded-2xl border border-violet-500/20 bg-gradient-to-br from-violet-500/10 to-blue-500/5 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">
            首次初始化 · 第 {current}/7 步
          </h2>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            {ONBOARDING_STEPS[current - 1]}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void save(current, "dismiss")}
          className="text-xs text-[var(--muted-foreground)]"
        >
          暂时隐藏
        </button>
      </div>
      <div className="mt-4 grid grid-cols-7 gap-1.5">
        {ONBOARDING_STEPS.map((label, index) => {
          const number = index + 1;
          const finished = data.completed.includes(number);
          return (
            <div
              key={label}
              title={label}
              className={`h-1.5 rounded-full ${
                finished
                  ? "bg-emerald-500"
                  : number === current
                    ? "bg-violet-500"
                    : "bg-[var(--border)]"
              }`}
            />
          );
        })}
      </div>
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={() => void save(current, "done")}
          className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-medium text-white"
        >
          这一步已完成
        </button>
        {[3, 5].includes(current) && (
          <button
            type="button"
            onClick={() => void save(current, "skip")}
            className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs"
          >
            稍后再配置（核心仍可用）
          </button>
        )}
      </div>
    </section>
  );
}
