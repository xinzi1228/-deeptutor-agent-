"use client";

import { Gavel, AlertTriangle, CheckCircle2 } from "lucide-react";
import type { TeachingEvaluation } from "@/lib/learning-stats-api";

function splitSections(text: string): { challenges: string[]; suggestions: string[]; conclusion: string } {
  const lines = text.split("\n");
  const challenges: string[] = [];
  const suggestions: string[] = [];
  let conclusion = "";
  let section: "challenges" | "suggestions" | "conclusion" | null = null;
  for (const raw of lines) {
    const line = raw.trim();
    if (/^##\s*质疑点|^##\s*挑战|^##\s*Critic/i.test(line)) { section = "challenges"; continue; }
    if (/^##\s*修正建议|^##\s*建议|^##\s*Fix/i.test(line)) { section = "suggestions"; continue; }
    if (/^##\s*结论|^##\s*Conclusion/i.test(line)) { section = "conclusion"; continue; }
    if (!line) continue;
    if (section === "challenges" && line.startsWith("-")) challenges.push(line.replace(/^-\s*/, ""));
    else if (section === "suggestions" && (line.startsWith("-") || /^\d+[.、]/.test(line))) suggestions.push(line.replace(/^[-\d.、\s]+/, ""));
    else if (section === "conclusion") conclusion = line;
  }
  return { challenges, suggestions, conclusion };
}

export function EvaluationPanel({ evaluations }: { evaluations: TeachingEvaluation[] }) {
  if (!evaluations.length) {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="mb-2 flex items-center gap-1.5">
          <Gavel className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
          <h3 className="text-sm font-semibold">教学方案评估</h3>
        </div>
        <p className="text-xs text-[var(--muted-foreground)]">
          暂无记录 — 教练设计跨概念模块时会请独立评估员对抗性审查
        </p>
      </div>
    );
  }

  const ev = evaluations[evaluations.length - 1];
  const { challenges, suggestions, conclusion } = splitSections(ev.evaluation);

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center gap-1.5">
        <Gavel className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        <h3 className="text-sm font-semibold">教学方案评估</h3>
        <span className="text-[10px] text-[var(--muted-foreground)]">(独立评估员视角)</span>
      </div>

      <div className="mb-3 rounded-lg bg-[var(--border)]/50 p-2">
        <p className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">审查的方案</p>
        <p className="mt-1 line-clamp-2 text-xs text-[var(--muted-foreground)]">{ev.plan}</p>
      </div>

      {challenges.length > 0 && (
        <div className="mb-3">
          <div className="mb-1.5 flex items-center gap-1 text-xs font-semibold text-red-500">
            <AlertTriangle className="h-3 w-3" /> 质疑点 ({challenges.length})
          </div>
          <ul className="space-y-1.5">
            {challenges.slice(0, 4).map((c, i) => (
              <li key={i} className="text-xs text-[var(--muted-foreground)]">· {c}</li>
            ))}
            {challenges.length > 4 && (
              <li className="text-[10px] text-[var(--muted-foreground)]">… 共 {challenges.length} 条</li>
            )}
          </ul>
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="mb-3">
          <div className="mb-1.5 flex items-center gap-1 text-xs font-semibold text-green-500">
            <CheckCircle2 className="h-3 w-3" /> 修正建议
          </div>
          <ul className="space-y-1.5">
            {suggestions.slice(0, 3).map((s, i) => (
              <li key={i} className="text-xs text-[var(--muted-foreground)]">· {s}</li>
            ))}
          </ul>
        </div>
      )}

      {conclusion && (
        <div className="rounded-lg border border-[var(--border)] p-2 text-xs">{conclusion}</div>
      )}
    </div>
  );
}
