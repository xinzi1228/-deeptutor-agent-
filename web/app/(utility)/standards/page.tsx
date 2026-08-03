"use client";

import { useEffect, useState } from "react";
import { BookOpen, ChevronRight } from "lucide-react";
import { getStandards, type StandardDoc } from "@/lib/standards-api";

export default function StandardsPage() {
  const [docs, setDocs] = useState<StandardDoc[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getStandards()
      .then((r) => { if (!cancelled) setDocs(r.standards); })
      .catch(() => { if (!cancelled) { setDocs([]); setError(true); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="h-full overflow-y-auto [scrollbar-gutter:stable]">
        <div className="mx-auto max-w-3xl px-6 py-10 text-sm text-[var(--muted-foreground)]">加载中...</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto [scrollbar-gutter:stable]">
      <div className="mx-auto max-w-3xl space-y-4 px-6 py-8">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-blue-500" />
          <div>
            <h1 className="text-lg font-bold">标注规范库</h1>
            <p className="text-sm text-[var(--muted-foreground)]">数据标注行业标准与操作规范</p>
          </div>
        </div>
        {error ? (
          <p className="text-sm text-[var(--muted-foreground)]">加载失败</p>
        ) : docs.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">暂无规范文档</p>
        ) : null}
        {docs.map((doc) => (
          <div key={doc.id} className="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
            <button
              type="button"
              onClick={() => setOpenId(openId === doc.id ? null : doc.id)}
              aria-expanded={openId === doc.id}
              className="flex w-full items-center gap-2 px-4 py-3 text-left"
            >
              <ChevronRight className={`h-4 w-4 transition-transform ${openId === doc.id ? "rotate-90" : ""}`} />
              <span className="text-sm font-semibold">{doc.title}</span>
              <span className="ml-auto text-xs text-[var(--muted-foreground)]">{doc.sections.length} 章节</span>
            </button>
            {openId === doc.id && (
              <div className="border-t border-[var(--border)] px-4 py-3">
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {doc.sections.map((s, i) => (
                    <span key={`${doc.id}-${i}`} className="rounded bg-[var(--muted)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">{s}</span>
                  ))}
                </div>
                <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap font-mono text-xs leading-5 text-[var(--foreground)]">
                  {doc.content}
                </pre>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
