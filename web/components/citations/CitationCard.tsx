"use client";

import { useState } from "react";
import { BookOpen, ChevronDown, ShieldCheck } from "lucide-react";
import type { KnowledgeCitation } from "@/lib/knowledge-api";

const TRUST_LABELS: Record<KnowledgeCitation["trust_level"], string> = {
  authoritative: "权威来源",
  high: "高可信",
  medium: "课程资料",
  limited: "参考资料",
};

const TRUST_STYLES: Record<KnowledgeCitation["trust_level"], string> = {
  authoritative: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  high: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
  medium: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
  limited: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
};

function locator(citation: KnowledgeCitation): string {
  return [citation.chapter, citation.page ? `第 ${citation.page} 页` : ""]
    .filter(Boolean)
    .join(" · ");
}

export function CitationCard({ citation }: { citation: KnowledgeCitation }) {
  const [expanded, setExpanded] = useState(false);
  const location = locator(citation);
  const admin = citation.admin_details;
  return (
    <article className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className="flex w-full items-start gap-3 px-3 py-2.5 text-left transition hover:bg-[var(--muted)]/30"
      >
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--primary)]/10 text-[var(--primary)]">
          <BookOpen className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12.5px] font-medium text-[var(--foreground)]">
            {citation.title}
          </span>
          <span className="mt-1 flex flex-wrap items-center gap-1.5 text-[10.5px] text-[var(--muted-foreground)]">
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 ${TRUST_STYLES[citation.trust_level]}`}
            >
              <ShieldCheck className="h-3 w-3" />
              {TRUST_LABELS[citation.trust_level]}
            </span>
            {location ? <span>{location}</span> : null}
          </span>
        </span>
        <ChevronDown
          className={`mt-1 h-4 w-4 shrink-0 text-[var(--muted-foreground)] transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      {expanded ? (
        <div className="border-t border-[var(--border)] px-3 py-2.5">
          {citation.excerpt ? (
            <p className="text-[12px] leading-5 text-[var(--muted-foreground)]">
              {citation.excerpt}
            </p>
          ) : (
            <p className="text-[12px] text-[var(--muted-foreground)]">
              该来源没有提供可展示的原文摘要。
            </p>
          )}
          {admin ? (
            <dl className="mt-2 grid gap-1 rounded-lg bg-[var(--muted)]/30 p-2 font-mono text-[10px] text-[var(--muted-foreground)]">
              <div>版本：{admin.version || "未记录"}</div>
              <div>审核：{admin.review_status || "未记录"}</div>
              <div className="break-all">哈希：{admin.content_hash || "未记录"}</div>
              {admin.source_path ? (
                <div className="break-all">路径：{admin.source_path}</div>
              ) : null}
              {admin.review_record_id ? (
                <div>审核记录：{admin.review_record_id}</div>
              ) : null}
            </dl>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

export function CitationList({ citations }: { citations: KnowledgeCitation[] }) {
  if (!citations.length) return null;
  return (
    <section className="mt-3 w-full max-w-[min(620px,95%)]" aria-label="回答引用">
      <div className="mb-1.5 flex items-center gap-2 text-[11px] font-medium text-[var(--muted-foreground)]">
        <BookOpen className="h-3.5 w-3.5" />
        回答依据 · {citations.length} 条
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {citations.map((citation) => (
          <CitationCard key={citation.id} citation={citation} />
        ))}
      </div>
    </section>
  );
}

export { TRUST_LABELS };
