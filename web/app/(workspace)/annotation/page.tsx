"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Tag, PenLine, Wrench, Mic, Video, FileText } from "lucide-react";
import AnnotationCoach from "@/components/annotation/AnnotationCoach";
import AnnotationProgress from "@/components/annotation/AnnotationProgress";

export default function AnnotationPage() {
  const { t } = useTranslation();
  const [mode, setMode] = useState<"image" | "text" | "audio" | "video" | "pro">("image");
  const [tasks, setTasks] = useState<Array<{ id: string; title: string; type: string; modal: "image" | "text" | "audio" | "video"; difficulty: string }>>([]);
  const [selectedTask, setSelectedTask] = useState("");
  const [selectedTaskData, setSelectedTaskData] = useState<Record<string, unknown> | null>(null);
  const [labelStudio, setLabelStudio] = useState<{ available: boolean; url: string; detail?: string } | null>(null);
  const workbenchRef = useRef<HTMLIFrameElement | null>(null);

  useEffect(() => {
    fetch("/api/v1/annotation/tasks").then((res) => res.ok ? res.json() : Promise.reject()).then((data) => {
      setTasks(data.tasks || []);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (mode !== "pro") return;
    fetch("/api/v1/annotation/label-studio-status", { cache: "no-store" })
      .then((res) => res.ok ? res.json() : Promise.reject())
      .then(setLabelStudio)
      .catch(() => setLabelStudio({ available: false, url: "http://127.0.0.1:8080", detail: "无法连接本地服务" }));
  }, [mode]);

  useEffect(() => {
    if (!selectedTaskData || mode === "pro") return;
    workbenchRef.current?.contentWindow?.postMessage(
      { type: "load_annotation_task", task: selectedTaskData },
      window.location.origin,
    );
  }, [selectedTaskData, mode]);

  const chooseTask = async (taskId: string) => {
    setSelectedTask(taskId);
    try {
      const res = await fetch(`/api/v1/annotation/tasks/${encodeURIComponent(taskId)}`);
      if (!res.ok) throw new Error("任务加载失败");
      const { task } = await res.json();
      setSelectedTaskData(task);
      setMode(task.modal);
    } catch {
      // 保持当前工作台；选择器仍可重试
    }
  };

  const toolSrc = mode === "image" ? "/annotation_tool.html" : mode === "text" ? "/annotation_tool_text.html" : mode === "audio" ? "/annotation_tool_audio.html" : "/annotation_tool_video.html";

  return (
    <div className="flex h-full flex-col bg-[var(--background)]">
      <header className="flex items-center justify-between border-b border-[var(--border)] px-6 py-3">
        <div className="flex items-center gap-3">
          <Tag className="h-5 w-5 text-[var(--muted-foreground)]" />
          <div>
            <h1 className="text-[15px] font-semibold text-[var(--foreground)]">
              {t("annotation.title")}
            </h1>
            <p className="text-[11px] text-[var(--muted-foreground)]">
              {t("annotation.subtitle")}
            </p>
          </div>
        </div>
        <div className="flex rounded-lg border border-[var(--border)] bg-[var(--card)] p-1">
          <button
            onClick={() => setMode("image")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === "image"
                ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <PenLine className="h-3.5 w-3.5" />
            图片标注
          </button>
          <button
            onClick={() => setMode("text")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === "text"
                ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            文本标注
          </button>
          <button
            onClick={() => setMode("audio")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === "audio"
                ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <Mic className="h-3.5 w-3.5" />
            音频标注
          </button>
          <button
            onClick={() => setMode("video")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === "video"
                ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <Video className="h-3.5 w-3.5" />
            视频标注
          </button>
          <button
            onClick={() => setMode("pro")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === "pro"
                ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <Wrench className="h-3.5 w-3.5" />
            {t("annotation.proMode")}
          </button>
        </div>
      </header>

      <AnnotationProgress />

      {mode !== "pro" && (
        <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-2">
          <label className="text-xs text-[var(--muted-foreground)]" htmlFor="task-bank">任务库</label>
          <select id="task-bank" value={selectedTask} onChange={(event) => void chooseTask(event.target.value)} className="max-w-md rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs">
            <option value="">选择任务后加载到当前标注台</option>
            {tasks.filter((task) => task.modal === mode).map((task) => <option key={task.id} value={task.id}>{task.id} · {task.title}{task.difficulty ? `（${task.difficulty}）` : ""}</option>)}
          </select>
        </div>
      )}

      <div className="flex-1">
        {mode !== "pro" ? <iframe ref={workbenchRef} src={toolSrc} onLoad={() => selectedTaskData && workbenchRef.current?.contentWindow?.postMessage({ type: "load_annotation_task", task: selectedTaskData }, window.location.origin)} className="h-full w-full border-0" title="Annotation Tool" sandbox="allow-scripts allow-same-origin allow-top-navigation allow-popups" /> : labelStudio?.available ? (
          <div className="h-full"><div className="flex justify-end border-b border-[var(--border)] px-4 py-2"><a className="text-xs text-[var(--primary)] underline" href={labelStudio.url} target="_blank" rel="noreferrer">在新窗口打开 Label Studio</a></div><iframe src={labelStudio.url} className="h-[calc(100%-37px)] w-full border-0" title="Label Studio" /></div>
        ) : <div className="flex h-full items-center justify-center p-6"><div className="max-w-md rounded-xl border border-amber-500/40 bg-amber-500/10 p-5 text-sm"><h2 className="font-semibold">Label Studio 尚未启动</h2><p className="mt-2 text-[var(--muted-foreground)]">专业模式需要本机 8080 服务。请运行项目根目录的 <code>start_label_studio.bat</code>，启动完成后重新点击“专业模式”。</p><p className="mt-2 text-xs text-[var(--muted-foreground)]">检测信息：{labelStudio?.detail || "正在检测服务…"}</p></div></div>}
      </div>

      <AnnotationCoach />
    </div>
  );
}
