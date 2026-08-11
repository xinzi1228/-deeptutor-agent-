"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiUrl } from "@/lib/api";

export default function LearningWorkspaceAdminPage() {
  const [data, setData] = useState<any>(null);
  const [message, setMessage] = useState("");
  const load = async () => {
    const [workspace, views] = await Promise.all([
      apiFetch(apiUrl("/api/v1/profile/workspace")).then((r) => r.json()),
      apiFetch(apiUrl("/api/v1/profile/workspace/views")).then((r) => r.json()),
    ]);
    setData({ workspace, views });
  };
  useEffect(() => { void load().catch(() => setMessage("无法读取学习工作区状态")); }, []);
  const rebuild = async (rebuildCourse: boolean) => {
    if (rebuildCourse && !window.confirm("将根据诊断重新生成课程计划，继续吗？")) return;
    const res = await apiFetch(apiUrl("/api/v1/profile/workspace/rebuild"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rebuild_course: rebuildCourse, confirmed: rebuildCourse }),
    });
    const body = await res.json();
    setMessage(res.ok ? `完成：${JSON.stringify(body.result)}` : body.detail || "重建失败");
    if (res.ok) await load();
  };
  return <main className="mx-auto max-w-4xl space-y-6 p-8">
    <div><h1 className="text-xl font-bold">学习工作区维护</h1><p className="mt-1 text-sm text-[var(--muted-foreground)]">仅管理员可见；不会修改学生原始学习记录。</p></div>
    <section className="rounded-xl border p-5"><h2 className="font-semibold">数据状态</h2><pre className="mt-3 overflow-auto text-xs">{JSON.stringify(data?.workspace?.manifest ?? {}, null, 2)}</pre></section>
    <section className="rounded-xl border p-5"><h2 className="font-semibold">教学资产版本</h2><pre className="mt-3 overflow-auto text-xs">{JSON.stringify(data?.views?.assets ?? {}, null, 2)}</pre></section>
    <div className="flex gap-3"><button className="rounded bg-blue-600 px-4 py-2 text-sm text-white" onClick={() => void rebuild(false)}>修复学习展示</button><button className="rounded border px-4 py-2 text-sm" onClick={() => void rebuild(true)}>重建课程计划</button></div>
    {message && <p className="text-sm">{message}</p>}
  </main>;
}
