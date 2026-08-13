"use client";

import { useEffect, useMemo, useState } from "react";
import { FilePlus2, LoaderCircle, UploadCloud } from "lucide-react";

import {
  createKnowledgeBase,
  getKnowledgeUploadPolicy,
  listRagProviders,
  type KnowledgeUploadPolicy,
  type RagProviderSummary,
} from "@/lib/knowledge-api";

export function QuickKnowledgeImport({ onImported }: { onImported: () => void }) {
  const [name, setName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [providers, setProviders] = useState<RagProviderSummary[]>([]);
  const [provider, setProvider] = useState("llamaindex");
  const [policy, setPolicy] = useState<KnowledgeUploadPolicy | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void Promise.all([listRagProviders({ force: true }), getKnowledgeUploadPolicy()]).then(
      ([items, uploadPolicy]) => {
        setProviders(items);
        setPolicy(uploadPolicy);
        const ready = items.find((item) => item.configured !== false) ?? items[0];
        if (ready) setProvider(ready.id);
      },
    );
  }, []);

  const totalSize = useMemo(
    () => files.reduce((sum, file) => sum + file.size, 0),
    [files],
  );

  const submit = async () => {
    if (!name.trim() || files.length === 0) {
      setMessage("请填写资料库名称，并至少选择一个文件。");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      await createKnowledgeBase({ name: name.trim(), provider, files });
      setMessage("资料已接收，系统正在后台建立索引。完成后即可在对话中选择它。");
      setName("");
      setFiles([]);
      onImported();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "导入失败，请检查模型与解析配置。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section id="quick-knowledge" className="mt-7 scroll-mt-6 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded-xl bg-sky-500/10 p-2 text-sky-600"><FilePlus2 className="h-5 w-5" /></span>
            <div><h2 className="text-base font-semibold">资料快速导入</h2><p className="mt-0.5 text-xs text-[var(--muted-foreground)]">适合第一次使用；复杂切分和检索参数仍可在高级设置中调整。</p></div>
          </div>
        </div>
        <span className="rounded-full bg-[var(--muted)] px-2.5 py-1 text-[10px] text-[var(--muted-foreground)]">最多 {policy ? Math.round(policy.max_file_size_bytes / 1024 / 1024) : 200} MB / 文件</span>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-[1fr_180px_1.4fr_auto]">
        <label className="grid gap-1 text-xs"><span>资料库名称</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：数据标注实训手册" className="h-10 rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 outline-none focus:border-sky-500" /></label>
        <label className="grid gap-1 text-xs"><span>检索引擎</span><select value={provider} onChange={(event) => setProvider(event.target.value)} className="h-10 rounded-xl border border-[var(--border)] bg-[var(--background)] px-3">{providers.map((item) => <option key={item.id} value={item.id} disabled={item.configured === false}>{item.name}{item.configured === false ? "（未配置）" : ""}</option>)}</select></label>
        <label className="grid gap-1 text-xs"><span>选择课程资料</span><span className="flex h-10 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-[var(--border)] bg-[var(--background)] px-3"><UploadCloud className="h-4 w-4 text-sky-600" /><span className="min-w-0 flex-1 truncate text-[var(--muted-foreground)]">{files.length ? `${files.length} 个文件，共 ${(totalSize / 1024 / 1024).toFixed(1)} MB` : "PDF、Word、PPT、图片等"}</span><input type="file" multiple accept={policy?.accept} className="sr-only" onChange={(event) => setFiles(Array.from(event.target.files ?? []))} /></span></label>
        <button type="button" onClick={() => void submit()} disabled={busy} className="mt-auto inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-sky-600 px-4 text-xs font-medium text-white disabled:opacity-50">{busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}开始导入</button>
      </div>
      {message && <p className="mt-3 rounded-lg bg-[var(--muted)] px-3 py-2 text-xs text-[var(--muted-foreground)]">{message}</p>}
    </section>
  );
}
