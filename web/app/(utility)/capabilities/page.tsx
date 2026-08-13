"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, Bot, CheckCircle2, Database, Download, HeartPulse, Puzzle, RefreshCw, Settings2, Sparkles, Wrench } from "lucide-react";
import { apiFetch, apiUrl } from "@/lib/api";
import { QuickKnowledgeImport } from "@/components/capabilities/QuickKnowledgeImport";

type State = "normal" | "limited" | "fault";
type Card = { key: string; title: string; status: State; summary: string; impact: string; repair_href: string; details: Record<string, unknown> };
type Overview = { overall: State; cards: Card[]; is_admin: boolean; active_learning_profile: boolean; onboarding: { step: number; completed: number[]; skipped: number[]; dismissed: boolean } | null; privacy: string; generated_at: string };

const ICONS = { models: Bot, knowledge: Database, extensions: Puzzle, annotation: Wrench, system: HeartPulse };
const LABELS: Record<State, string> = { normal: "正常", limited: "受限", fault: "故障" };
const STYLES: Record<State, string> = { normal: "border-emerald-500/25 bg-emerald-500/5 text-emerald-600", limited: "border-amber-500/25 bg-amber-500/5 text-amber-600", fault: "border-rose-500/25 bg-rose-500/5 text-rose-600" };

export default function CapabilityCenterPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true); setError("");
    try {
      const response = await apiFetch(apiUrl("/api/v1/capability-center/overview"), { cache: "no-store" });
      if (!response.ok) throw new Error("能力状态读取失败");
      setData(await response.json());
    } catch (reason) { setError(reason instanceof Error ? reason.message : "能力状态读取失败"); }
    finally { setLoading(false); }
  };
  useEffect(() => {
    // Initial fetch synchronizes this page with the backend capability state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, []);
  const download = async () => {
    const response = await apiFetch(apiUrl("/api/v1/capability-center/diagnostics"));
    if (!response.ok) return;
    const blob = new Blob([JSON.stringify(await response.json(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "标注星图-脱敏体检报告.json"; link.click(); URL.revokeObjectURL(url);
  };
  return <div className="h-full overflow-y-auto bg-[var(--background)]"><div className="mx-auto max-w-6xl px-6 py-8">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-violet-500/10 px-2.5 py-1 text-[11px] font-medium text-violet-600"><Sparkles className="h-3.5 w-3.5" />新手配置入口</div><h1 className="font-serif text-3xl font-semibold tracking-tight">能力中心</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted-foreground)]">不用先懂 API、MCP 或向量数据库。这里会告诉你系统现在能做什么、缺少什么，以及点哪里修复；技术参数仍保留在高级设置中。</p></div><div className="flex gap-2"><button type="button" onClick={() => void download()} className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border)] px-3 py-2 text-xs"><Download className="h-4 w-4" />下载脱敏报告</button><button type="button" onClick={() => void load()} className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--foreground)] px-3 py-2 text-xs text-[var(--background)]"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />重新检测</button></div></header>
    {error && <div className="mt-6 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-600">{error}</div>}
    {data?.is_admin && data.onboarding && !data.onboarding.dismissed && <Onboarding data={data.onboarding} onSaved={load} />}
    <QuickKnowledgeImport onImported={load} />
    <div className="mt-7 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{data?.cards.map((card) => <CapabilityCard key={card.key} card={card} />)}</div>
    {!data && loading && <div className="mt-10 grid gap-4 md:grid-cols-3">{[1,2,3,4,5].map((item) => <div key={item} className="h-44 animate-pulse rounded-2xl bg-[var(--muted)]" />)}</div>}
    {data && <div className="mt-6 flex items-start gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-xs text-[var(--muted-foreground)]"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" /><span>{data.privacy}</span></div>}
    <div className="mt-6 flex justify-end"><Link href="/settings" className="inline-flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><Settings2 className="h-4 w-4" />进入高级设置</Link></div>
  </div></div>;
}

function CapabilityCard({ card }: { card: Card }) {
  const Icon = ICONS[card.key as keyof typeof ICONS] || BookOpen;
  return <article className="flex min-h-48 flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm"><div className="flex items-start justify-between"><div className="rounded-xl bg-[var(--muted)] p-2.5"><Icon className="h-5 w-5" /></div><span className={`rounded-full border px-2 py-1 text-[10px] font-medium ${STYLES[card.status]}`}>{LABELS[card.status]}</span></div><h2 className="mt-4 text-base font-semibold">{card.title}</h2><p className="mt-1.5 text-sm leading-5">{card.summary}</p><p className="mt-2 flex-1 text-xs leading-5 text-[var(--muted-foreground)]">{card.impact}</p><Link href={card.repair_href} className="mt-4 inline-flex items-center gap-1 self-start text-xs font-medium text-[var(--primary)]">{card.status === "normal" ? "查看与管理" : "去修复"}<span aria-hidden>→</span></Link></article>;
}

const STEPS = ["检测运行环境", "配置主对话模型", "配置可选模型", "导入第一份资料", "启用审核扩展", "创建学生档案", "运行完整体检"];
function Onboarding({ data, onSaved }: { data: NonNullable<Overview["onboarding"]>; onSaved: () => void }) {
  const save = async (step: number, action: "done" | "skip" | "dismiss") => {
    const completed = action === "done" ? Array.from(new Set([...data.completed, step])) : data.completed;
    const skipped = action === "skip" ? Array.from(new Set([...data.skipped, step])) : data.skipped;
    await apiFetch(apiUrl("/api/v1/capability-center/onboarding"), { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ step: Math.min(step + 1, 7), completed, skipped, dismissed: action === "dismiss" }) });
    onSaved();
  };
  const current = Math.min(Math.max(data.step, 1), 7);
  return <section className="mt-7 rounded-2xl border border-violet-500/20 bg-gradient-to-br from-violet-500/10 to-blue-500/5 p-5"><div className="flex items-center justify-between gap-3"><div><h2 className="text-base font-semibold">首次初始化 · 第 {current}/7 步</h2><p className="mt-1 text-xs text-[var(--muted-foreground)]">{STEPS[current - 1]}</p></div><button type="button" onClick={() => void save(current, "dismiss")} className="text-xs text-[var(--muted-foreground)]">暂时隐藏</button></div><div className="mt-4 grid grid-cols-7 gap-1.5">{STEPS.map((label, index) => { const number=index+1; const finished=data.completed.includes(number); return <div key={label} title={label} className={`h-1.5 rounded-full ${finished ? "bg-emerald-500" : number === current ? "bg-violet-500" : "bg-[var(--border)]"}`} />; })}</div><div className="mt-4 flex gap-2"><button type="button" onClick={() => void save(current, "done")} className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-medium text-white">这一步已完成</button>{[3,5].includes(current) && <button type="button" onClick={() => void save(current, "skip")} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs">稍后再配置（核心仍可用）</button>}</div></section>;
}
