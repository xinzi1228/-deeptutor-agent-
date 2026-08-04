"use client";

import { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";

type SharedMessage = { role: string; content?: string };

export default function SharePage({ params }: { params: { token: string } }) {
  const [session, setSession] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/v1/share/${params.token}`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        if (data.error) setError(data.error);
        else setSession(data.session);
      })
      .catch(() => {
        if (!cancelled) setError("加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [params.token]);

  if (loading)
    return (
      <div className="mx-auto max-w-3xl px-6 py-10 text-sm text-[var(--muted-foreground)]">
        加载中...
      </div>
    );
  if (error)
    return (
      <div className="mx-auto max-w-3xl px-6 py-20 text-center text-sm text-red-500">
        {error}
      </div>
    );

  const messages: SharedMessage[] = session?.messages ?? [];

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-6 flex items-center gap-2">
        <BookOpen className="h-5 w-5 text-blue-500" />
        <div>
          <h1 className="text-lg font-bold">{session?.title || "分享的学习会话"}</h1>
          <p className="text-sm text-[var(--muted-foreground)]">只读分享 · 标注星图</p>
        </div>
      </div>
      {messages.length === 0 && (
        <p className="text-sm text-[var(--muted-foreground)]">暂无消息</p>
      )}
      <div className="space-y-4">
        {messages
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map((m, i) => (
            <div
              key={i}
              className={`rounded-2xl border border-[var(--border)] p-4 ${
                m.role === "assistant" ? "bg-[var(--card)]" : "bg-[var(--muted)]/40"
              }`}
            >
              <div className="mb-1 text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
                {m.role === "assistant" ? "教练" : "学生"}
              </div>
              <div className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--foreground)]">
                {m.content || ""}
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}
