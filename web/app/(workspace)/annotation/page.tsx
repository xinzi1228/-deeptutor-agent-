"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Tag, PenLine, Wrench, Mic, Video, FileText } from "lucide-react";
import AnnotationProgress from "@/components/annotation/AnnotationProgress";
import { apiFetch, apiUrl } from "@/lib/api";
import { emitPerformanceMetric } from "@/lib/performance-metrics";
import type { AnnotationTask } from "@/components/annotation/UnifiedAnnotationWorkbench";
import { useCurrentLearningTask } from "@/components/current-task/CurrentLearningTaskContext";
import {
  acquireAnnotationEditLease,
  checkpointProfessionalEditLease,
  chooseCompatibleTask,
  getAnnotationBrowserSessionId,
  releaseAnnotationEditLease,
  takeoverAnnotationEditLease,
  type AnnotationEditLease,
  type AnnotationEditorMode,
} from "@/lib/annotation-edit-session";

type EditAccess = {
  editable: boolean;
  lease: AnnotationEditLease | null;
  message: string;
};

const AnnotationCoach = dynamic(
  () => import("@/components/annotation/AnnotationCoach"),
  { ssr: false, loading: () => null },
);

const UnifiedAnnotationWorkbench = dynamic(
  () => import("@/components/annotation/UnifiedAnnotationWorkbench"),
  { ssr: false, loading: () => <div className="flex h-full items-center justify-center text-sm text-[var(--muted-foreground)]">正在加载统一标注台…</div> },
);

export default function AnnotationPage() {
  const { t } = useTranslation();
  const { openTask } = useCurrentLearningTask();
  const [mode, setMode] = useState<"image" | "text" | "audio" | "video" | "pro">("image");
  const [tasks, setTasks] = useState<Array<{ id: string; title: string; type: string; modal: "image" | "text" | "audio" | "video"; difficulty: string }>>([]);
  const [professionalTasks, setProfessionalTasks] = useState<typeof tasks>([]);
  const [selectedTask, setSelectedTask] = useState("");
  const [selectedTaskData, setSelectedTaskData] = useState<AnnotationTask | null>(null);
  const [labelStudio, setLabelStudio] = useState<{ available: boolean; configured?: boolean; management_url?: string | null; detail?: string } | null>(null);
  const [professionalUrl, setProfessionalUrl] = useState("");
  const [professionalLoading, setProfessionalLoading] = useState(false);
  const [browserSessionId, setBrowserSessionId] = useState("");
  const [editAccess, setEditAccess] = useState<EditAccess>({ editable: false, lease: null, message: "请选择任务" });
  const draftSaverRef = useRef<(() => Promise<{ draftVersion: number; lease: AnnotationEditLease }>) | null>(null);
  const taskRequestVersion = useRef(0);

  useEffect(() => { setBrowserSessionId(getAnnotationBrowserSessionId()); }, []);

  const acquireForTask = useCallback(async (taskId: string, editorMode: AnnotationEditorMode) => {
    if (!browserSessionId) return null;
    try {
      const lease = await acquireAnnotationEditLease(taskId, editorMode, browserSessionId);
      setEditAccess({ editable: true, lease, message: "" });
      return lease;
    } catch (reason) {
      const error = reason as Error & { lease?: AnnotationEditLease };
      setEditAccess({ editable: false, lease: error.lease || null, message: error.message });
      return null;
    }
  }, [browserSessionId]);

  const saveOwnedCheckpoint = useCallback(async () => {
    const current = editAccess.lease;
    if (!selectedTask || !current || !editAccess.editable) return current;
    if (current.mode === "teaching") {
      const saved = await draftSaverRef.current?.();
      if (!saved) throw new Error("教学模式草稿尚未准备好，请稍后重试");
      setEditAccess({ editable: true, lease: saved.lease, message: "" });
      return saved.lease;
    }
    await apiFetch(apiUrl(`/api/v1/label-studio/sync/${encodeURIComponent(selectedTask)}`), { method: "POST" });
    const lease = await checkpointProfessionalEditLease(selectedTask, browserSessionId, current);
    setEditAccess({ editable: true, lease, message: "" });
    return lease;
  }, [browserSessionId, editAccess, selectedTask]);

  const switchMode = useCallback(async (nextMode: "image" | "text" | "audio" | "video" | "pro") => {
    if (nextMode === mode) return;
    const startedAt = performance.now();
    taskRequestVersion.current += 1;
    const previousTask = selectedTask;
    const compatibleTask = chooseCompatibleTask(tasks, nextMode, previousTask);
    try {
      const checkpointed = await saveOwnedCheckpoint();
      if (previousTask && checkpointed && browserSessionId) {
        await releaseAnnotationEditLease(previousTask, browserSessionId, checkpointed);
      }
    } catch (reason) {
      setEditAccess((current) => ({ ...current, message: reason instanceof Error ? reason.message : "切换前保存失败" }));
      return;
    }
    setMode(nextMode);
    // 每种模态拥有独立任务上下文。专业模式也必须重新从本人任务中进入。
    if (!compatibleTask || nextMode === "pro" || mode === "pro") {
      setSelectedTask("");
      setSelectedTaskData(null);
      setProfessionalUrl("");
      setEditAccess({ editable: false, lease: null, message: "请选择任务" });
    }
    requestAnimationFrame(() => emitPerformanceMetric({
      name: "annotation_mode_switch",
      route: "/annotation",
      duration_ms: performance.now() - startedAt,
      stage: nextMode,
    }));
  }, [browserSessionId, mode, saveOwnedCheckpoint, selectedTask, tasks]);

  useEffect(() => {
    fetch("/api/v1/annotation/tasks").then((res) => res.ok ? res.json() : Promise.reject()).then((data) => {
      setTasks(data.tasks || []);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (mode !== "pro") return;
    Promise.all([
      fetch("/api/v1/label-studio/status", { cache: "no-store" }).then((res) => res.ok ? res.json() : Promise.reject()),
      fetch("/api/v1/label-studio/professional/tasks", { cache: "no-store" }).then((res) => res.ok ? res.json() : { tasks: [] }),
    ])
      .then(([status, assigned]) => { setLabelStudio(status); setProfessionalTasks(assigned.tasks || []); })
      .catch(() => setLabelStudio({ available: false, detail: "无法连接本地服务，或学习档案尚未解锁" }));
  }, [mode]);

  const chooseTask = useCallback(async (taskId: string) => {
    if (!taskId) return;
    const requestVersion = ++taskRequestVersion.current;
    const startedAt = performance.now();
    try {
      if (selectedTask && selectedTask !== taskId && editAccess.editable && editAccess.lease) {
        const checkpointed = await saveOwnedCheckpoint();
        if (checkpointed) await releaseAnnotationEditLease(selectedTask, browserSessionId, checkpointed);
      }
      setSelectedTask(taskId);
      const res = await fetch(`/api/v1/annotation/tasks/${encodeURIComponent(taskId)}`);
      if (!res.ok) throw new Error("任务加载失败");
      const { task } = await res.json();
      if (requestVersion !== taskRequestVersion.current) return;
      await acquireForTask(taskId, "teaching");
      if (requestVersion !== taskRequestVersion.current) return;
      setSelectedTaskData(task);
      setMode(task.modal);
      await openTask({ courseId: "annotation-foundations", taskId, mode: "teaching_annotation" });
      emitPerformanceMetric({
        name: "annotation_task_visible",
        route: "/annotation",
        duration_ms: performance.now() - startedAt,
        stage: "teaching",
      });
      void apiFetch(apiUrl("/api/v1/annotation/activity"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: taskId, mode: "teaching", stage: "selected", summary: { title: task.title, modal: task.modal, task_type: task.type } }),
      }).catch(() => undefined);
    } catch {
      emitPerformanceMetric({
        name: "annotation_task_visible",
        route: "/annotation",
        duration_ms: performance.now() - startedAt,
        outcome: "error",
        stage: "teaching",
        error_type: "server",
      });
      // 保持当前工作台；选择器仍可重试
    }
  }, [acquireForTask, browserSessionId, editAccess.editable, editAccess.lease, openTask, saveOwnedCheckpoint, selectedTask]);

  const chooseProfessionalTask = async (taskId: string) => {
    const requestVersion = ++taskRequestVersion.current;
    const startedAt = performance.now();
    setProfessionalLoading(true);
    setProfessionalUrl("");
    try {
      if (selectedTask && selectedTask !== taskId && editAccess.editable && editAccess.lease) {
        const checkpointed = await saveOwnedCheckpoint();
        if (checkpointed) await releaseAnnotationEditLease(selectedTask, browserSessionId, checkpointed);
      }
      setSelectedTask(taskId);
      await acquireForTask(taskId, "professional");
      const response = await apiFetch(apiUrl(`/api/v1/label-studio/prepare/${encodeURIComponent(taskId)}`), { method: "POST" });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "专业任务准备失败");
      }
      const data = await response.json();
      if (requestVersion !== taskRequestVersion.current) return;
      setProfessionalUrl(data.workbench_url);
      await openTask({ courseId: "annotation-professional", taskId, mode: "professional_annotation" });
      emitPerformanceMetric({
        name: "annotation_task_visible",
        route: "/annotation",
        duration_ms: performance.now() - startedAt,
        stage: "professional",
      });
    } catch (error) {
      emitPerformanceMetric({
        name: "annotation_task_visible",
        route: "/annotation",
        duration_ms: performance.now() - startedAt,
        outcome: "error",
        stage: "professional",
        error_type: "server",
      });
      setLabelStudio((current) => ({ available: false, configured: current?.configured, management_url: current?.management_url, detail: error instanceof Error ? error.message : "专业任务准备失败" }));
    } finally {
      setProfessionalLoading(false);
    }
  };

  const takeOverEditing = useCallback(async () => {
    if (!selectedTask || !editAccess.lease || !browserSessionId) return;
    try {
      const desiredMode: AnnotationEditorMode = mode === "pro" ? "professional" : "teaching";
      const lease = await takeoverAnnotationEditLease(
        selectedTask,
        desiredMode,
        browserSessionId,
        editAccess.lease,
      );
      setEditAccess({ editable: true, lease, message: "" });
    } catch (reason) {
      setEditAccess((current) => ({ ...current, message: reason instanceof Error ? reason.message : "接管失败" }));
    }
  }, [browserSessionId, editAccess.lease, mode, selectedTask]);

  useEffect(() => {
    if (!selectedTask || !editAccess.editable || !editAccess.lease || !browserSessionId) return;
    const timer = window.setInterval(() => {
      void acquireAnnotationEditLease(selectedTask, editAccess.lease!.mode, browserSessionId)
        .then((lease) => setEditAccess({ editable: true, lease, message: "" }))
        .catch(() => setEditAccess((current) => ({ ...current, editable: false, message: "编辑权已过期，请重新接管" })));
    }, 45_000);
    return () => window.clearInterval(timer);
  }, [browserSessionId, editAccess.editable, editAccess.lease, selectedTask]);

  const filteredTasks = mode === "pro" ? professionalTasks : tasks.filter((task) => task.modal === mode);
  const selectedIndex = filteredTasks.findIndex((task) => task.id === selectedTask);
  const reportLiveState = useCallback((state: Record<string, unknown>) => {
    const taskId = String(state.task_id || selectedTask);
    if (!taskId) return;
    void apiFetch(apiUrl("/api/v1/annotation/activity"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, mode: String(state.mode || "teaching"), stage: String(state.stage || "editing"), summary: state }),
    }).catch(() => undefined);
  }, [selectedTask]);

  useEffect(() => {
    const onProfessionalEvent = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.data?.type !== "label_studio_workbench_event") return;
      reportLiveState({
        task_id: selectedTask,
        mode: "professional",
        stage: String(event.data.event || "editing"),
        annotation_count: Number(event.data.annotationCount || 0),
        current_label: String(event.data.label || "").slice(0, 80),
        realtime_bridge: true,
      });
    };
    window.addEventListener("message", onProfessionalEvent);
    return () => window.removeEventListener("message", onProfessionalEvent);
  }, [reportLiveState, selectedTask]);

  const handleLeaseChange = useCallback((lease: AnnotationEditLease) => {
    setEditAccess({ editable: true, lease, message: "" });
  }, []);

  const handleLeaseLost = useCallback(() => {
    setEditAccess((current) => ({
      ...current,
      editable: false,
      message: "编辑权已变化，当前标注台已转为只读",
    }));
  }, []);

  const registerDraftSaver = useCallback((saver: (() => Promise<{ draftVersion: number; lease: AnnotationEditLease }>) | null) => {
    draftSaverRef.current = saver;
  }, []);

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
            onClick={() => void switchMode("image")}
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
            onClick={() => void switchMode("text")}
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
            onClick={() => void switchMode("audio")}
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
            onClick={() => void switchMode("video")}
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
            onClick={() => void switchMode("pro")}
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

      {selectedTask && !editAccess.editable && <div className="flex items-center justify-between gap-3 border-b border-amber-500/30 bg-amber-500/10 px-6 py-2 text-xs text-amber-800"><span>{editAccess.message || "该任务当前为只读状态"}</span><button type="button" onClick={() => void takeOverEditing()} disabled={!editAccess.lease?.checkpoint_version} className="rounded-lg bg-amber-600 px-3 py-1.5 font-medium text-white disabled:cursor-not-allowed disabled:opacity-45">接管编辑</button></div>}

      <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-2">
          <label className="text-xs text-[var(--muted-foreground)]" htmlFor="task-bank">{mode === "pro" ? "本人专业任务" : "任务库"}</label>
          <select id="task-bank" value={selectedTask} onChange={(event) => void (mode === "pro" ? chooseProfessionalTask(event.target.value) : chooseTask(event.target.value))} className="max-w-md rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs">
            <option value="">{mode === "pro" ? "选择后直接进入 Label Studio 题目" : "选择任务后加载到当前标注台"}</option>
            {filteredTasks.map((task) => <option key={task.id} value={task.id}>{task.id} · {task.title}{task.difficulty ? `（${task.difficulty}）` : ""}</option>)}
          </select>
          {mode === "pro" && professionalUrl && <button className="rounded border border-[var(--border)] px-2 py-1 text-xs text-[var(--primary)]" onClick={() => void apiFetch(apiUrl(`/api/v1/label-studio/sync/${encodeURIComponent(selectedTask)}`), { method: "POST" })}>同步已保存标注</button>}
        </div>
      <div className="flex-1">
        {mode !== "pro" ? selectedTaskData ? <UnifiedAnnotationWorkbench key={selectedTask} task={selectedTaskData} previousTaskId={selectedIndex > 0 ? filteredTasks[selectedIndex - 1]?.id : undefined} nextTaskId={selectedIndex >= 0 ? filteredTasks[selectedIndex + 1]?.id : undefined} onSelectTask={(taskId) => void chooseTask(taskId)} onLiveState={reportLiveState} readOnly={!editAccess.editable} browserSessionId={browserSessionId} leaseVersion={editAccess.lease?.version} onLeaseChange={handleLeaseChange} onLeaseLost={handleLeaseLost} registerDraftSaver={registerDraftSaver} /> : <div className="flex h-full items-center justify-center p-8"><div className="max-w-md rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 text-center"><h2 className="font-semibold">选择一项任务开始练习</h2><p className="mt-2 text-xs leading-5 text-[var(--muted-foreground)]">统一 React 标注台会自动保存草稿到当前学习档案，并把实时进度提供给标注教练。</p></div></div> : labelStudio?.available && professionalUrl ? (
          <div className="relative h-full"><iframe src={professionalUrl} className={`h-full w-full border-0 ${editAccess.editable ? "" : "pointer-events-none opacity-70"}`} title="Label Studio 专业标注台" />{!editAccess.editable && <div className="absolute inset-x-4 top-4 rounded-xl border border-amber-500/35 bg-[var(--card)]/95 p-3 text-center text-xs text-amber-700 shadow-sm">专业标注台当前只读，请先在上方接管编辑。</div>}</div>
        ) : <div className="flex h-full items-center justify-center p-6"><div className="max-w-lg rounded-xl border border-amber-500/40 bg-amber-500/10 p-5 text-sm"><h2 className="font-semibold">{professionalLoading ? "正在准备你的专业任务…" : labelStudio?.available ? "请选择一项专业任务" : "Label Studio 专业模式尚未就绪"}</h2><p className="mt-2 text-[var(--muted-foreground)]">{labelStudio?.available ? "系统会为当前学习档案准备独立项目，并通过同源网关直接打开，不需要再次登录。" : "请启动本机 8080 服务，并在系统环境中配置 LABEL_STUDIO_API_TOKEN 与 LABEL_STUDIO_BRIDGE_SECRET。教学模式仍可正常使用。"}</p><p className="mt-2 text-xs text-[var(--muted-foreground)]">检测信息：{labelStudio?.detail || (labelStudio?.configured === false ? "服务已连接，但尚未配置 API Token" : "正在检测服务…")}</p>{labelStudio?.management_url && <a className="mt-3 inline-block text-xs text-[var(--primary)] underline" href={labelStudio.management_url} target="_blank" rel="noreferrer">管理员打开 Label Studio 管理台</a>}</div></div>}
      </div>

      <AnnotationCoach />
    </div>
  );
}
