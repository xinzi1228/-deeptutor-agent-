"use client";

import { useCallback, useEffect, useState } from "react";
import { Eye, FolderPlus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { apiFetch, apiUrl } from "@/lib/api";

interface Bucket {
  name: string;
}

interface BucketsResponse {
  buckets: Bucket[];
}

interface BucketContentResponse {
  name: string;
  content: string;
}

export default function MemoryBuckets() {
  const { t } = useTranslation();
  const [buckets, setBuckets] = useState<Bucket[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [contents, setContents] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const res = await apiFetch(apiUrl("/api/v1/memory/buckets"));
      if (!res.ok) return;
      const data = (await res.json()) as BucketsResponse;
      setBuckets(data.buckets ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const canCreate = newName.trim().length > 0 && !creating;

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name || creating) return;
    setCreating(true);
    setError(null);
    try {
      const res = await apiFetch(apiUrl("/api/v1/memory/buckets"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (res.status === 409) {
        setError(t("已存在同名的记忆区"));
        return;
      }
      if (!res.ok) {
        setError(t("创建失败，请检查记忆区名称"));
        return;
      }
      setNewName("");
      await load();
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = async (name: string) => {
    if (expanded === name) {
      setExpanded(null);
      return;
    }
    setExpanded(name);
    if (contents[name] === undefined) {
      try {
        const res = await apiFetch(
          apiUrl(`/api/v1/memory/buckets/${encodeURIComponent(name)}`),
        );
        if (!res.ok) return;
        const data = (await res.json()) as BucketContentResponse;
        setContents((prev) => ({ ...prev, [name]: data.content }));
      } catch {
        setContents((prev) => ({ ...prev, [name]: t("读取失败") }));
      }
    }
  };

  const handleDelete = async (name: string) => {
    if (!window.confirm(t("确定删除记忆区 {{name}}？此操作不可撤销。", { name }))) {
      return;
    }
    try {
      const res = await apiFetch(
        apiUrl(`/api/v1/memory/buckets/${encodeURIComponent(name)}`),
        { method: "DELETE" },
      );
      if (res.ok) {
        setContents((prev) => {
          const next = { ...prev };
          delete next[name];
          return next;
        });
        if (expanded === name) setExpanded(null);
        await load();
      }
    } catch {
      setError(t("删除失败"));
    }
  };

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-lg bg-[var(--primary)]/10 text-[var(--primary)]">
          <FolderPlus className="h-4 w-4" />
        </span>
        <div>
          <h2 className="text-[15px] font-semibold text-[var(--foreground)]">
            {t("记忆区（Buckets）")}
          </h2>
          <p className="text-[12px] text-[var(--muted-foreground)]">
            {t("将不同主题的记忆分区隔离，互不干扰。")}
          </p>
        </div>
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void handleCreate();
          }}
          placeholder={t("记忆区名称（如：标注学习）")}
          className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-[13px] text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:border-[var(--primary)] focus:outline-none"
        />
        <button
          type="button"
          onClick={() => void handleCreate()}
          disabled={!canCreate}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-[13px] font-medium text-[var(--foreground)] transition hover:bg-[var(--muted)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <FolderPlus className="h-3.5 w-3.5" />
          {t("新建记忆区")}
        </button>
      </div>

      {error && <p className="text-[12px] text-red-500">{error}</p>}

      {loading ? (
        <p className="text-[13px] text-[var(--muted-foreground)]">{t("加载中…")}</p>
      ) : buckets.length === 0 ? (
        <p className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] p-4 text-[13px] text-[var(--muted-foreground)]">
          {t("暂无记忆区，创建后可分区隔离不同主题的记忆（如标注学习 / Python 学习）。")}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {buckets.map((bucket) => (
            <div
              key={bucket.name}
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-[13px] font-medium text-[var(--foreground)]">
                  {bucket.name}
                </span>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => void handleToggle(bucket.name)}
                    className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-[12px] text-[var(--muted-foreground)] transition hover:bg-[var(--muted)]"
                  >
                    <Eye className="h-3 w-3" />
                    {expanded === bucket.name ? t("收起") : t("查看")}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDelete(bucket.name)}
                    className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-[12px] text-red-500 transition hover:bg-[var(--muted)]"
                  >
                    <Trash2 className="h-3 w-3" />
                    {t("删除")}
                  </button>
                </div>
              </div>
              {expanded === bucket.name && (
                <pre className="mt-3 max-h-60 overflow-auto whitespace-pre-wrap rounded-md border border-[var(--border)] bg-[var(--background)] p-3 text-[12px] leading-relaxed text-[var(--muted-foreground)]">
                  {contents[bucket.name] ?? t("加载中…")}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
