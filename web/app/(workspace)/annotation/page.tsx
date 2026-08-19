"use client";

import dynamic from "next/dynamic";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslation } from "react-i18next";
import { Tag, PenLine, Wrench, Mic, Video, FileText } from "lucide-react";
import AnnotationProgress from "@/components/annotation/AnnotationProgress";
import AnnotationResultCard from "@/components/annotation/AnnotationResultCard";
import { apiFetch, apiUrl } from "@/lib/api";
import type { AnnotationScoreRecord } from "@/lib/learning-api";
import { emitPerformanceMetric } from "@/lib/performance-metrics";
import type { AnnotationTask } from "@/components/annotation/UnifiedAnnotationWorkbench";
import { useCurrentLearningTask } from "@/components/current-task/CurrentLearningTaskContext";
import { useLearningProfile } from "@/components/learning-profiles/LearningProfileContext";
import { readLastModeFor, readLastTaskFor, writeLastModeFor, writeLastTaskFor, type AnnotationModeKey } from "@/lib/annotation-mode-memory";
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

function AnnotationPageInner() {
  const { t } = useTranslation();
  const { openTask } = useCurrentLearningTask();
  const { active } = useLearningProfile();
  const searchParams = useSearchParams();
  const queryTask = searchParams.get("task");
  const queryMode = searchParams.get("mode");
  const [mode, setMode] = useState<"image" | "text" | "audio" | "video" | "pro">(() => {
    const m = queryMode;
    if (m === "professional") return "pro";
    if (m && ["image", "text", "audio", "video"].includes(m)) return m as "image" | "text" | "audio" | "video";
    return readLastModeFor(active?.id || "") ?? "image";
  });
  const modeInitializedRef = useRef(false);
  const [tasks, setTasks] = useState<Array<{ id: string; title: string; type: string; modal: "image" | "text" | "audio" | "video"; difficulty: string }>>([]);
  const [professionalTasks, setProfessionalTasks] = useState<typeof tasks>([]);
  const [selectedTask, setSelectedTask] = useState("");
  const [selectedTaskData, setSelectedTaskData] = useState<AnnotationTask | null>(null);
  const [labelStudio, setLabelStudio] = useState<{ available: boolean; configured?: boolean; management_url?: string | null; detail?: string; ready?: boolean; prepared_count?: number; ready_count?: number; task_urls?: Record<string, string> } | null>(null);
  const [professionalUrl, setProfessionalUrl] = useState("");
  const [professionalLoading, setProfessionalLoading] = useState(false);
  const [professionalSyncing, setProfessionalSyncing] = useState(false);
  const [professionalResult, setProfessionalResult] = useState<{ metrics: Record<string, number>; report: string; scoreRecord?: AnnotationScoreRecord | null } | null>(null);
  const [preloadSrc, setPreloadSrc] = useState("");
  const [preloadStage, setPreloadStage] = useState("正在准备 Label Studio 项目…");
  const [preloadTimedOut, setPreloadTimedOut] = useState(false);
  const [browserSessionId, setBrowserSessionId] = useState("");
  const [editAccess, setEditAccess] = useState<EditAccess>({ editable: false, lease: null, message: "请选择任务" });
  const draftSaverRef = useRef<(() => Promise<{ draftVersion: number; lease: AnnotationEditLease }>) | null>(null);
  const taskRequestVersion = useRef(0);
  const professionalRequestVersion = useRef(0);
  const restoredTaskRef = useRef(false);
  const profileId = active?.id;
  const lastTaskKey = profileId ? `deeptutor_last_annotation_task.${profileId}` : "deeptutor_last_annotation_task";

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

  const chooseTask = useCallback(async (taskId: string) => {
    if (!taskId) return;
    const requestVersion = ++taskRequestVersion.current;
    professionalRequestVersion.current += 1;
    setProfessionalLoading(false);
    setPreloadTimedOut(false);
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
      try {
        writeLastTaskFor(profileId || "", task.modal as AnnotationModeKey, taskId);
      } catch { /* ignore */ }
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
  }, [acquireForTask, browserSessionId, editAccess.editable, editAccess.lease, openTask, profileId, saveOwnedCheckpoint, selectedTask]);

  const switchMode = useCallback(async (nextMode: "image" | "text" | "audio" | "video" | "pro") => {
    if (nextMode === mode) return;
    const startedAt = performance.now();
    taskRequestVersion.current += 1;
    professionalRequestVersion.current += 1;
    setProfessionalLoading(false);
    setPreloadTimedOut(false);
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
    writeLastModeFor(profileId || "", nextMode);
    // 每种模态拥有独立任务上下文。专业模式也必须重新从本人任务中进入。
    if (!compatibleTask || nextMode === "pro" || mode === "pro") {
      setSelectedTask("");
      setSelectedTaskData(null);
      setProfessionalUrl("");
      setEditAccess({ editable: false, lease: null, message: "请选择任务" });
    }
    // 切换到教学模态时，按该模态的本地记忆自动恢复上次任务（覆盖空态清空）
    if (nextMode !== "pro") {
      const saved = readLastTaskFor(profileId || "", nextMode);
      if (saved && tasks.some((task) => task.id === saved && task.modal === nextMode)) {
        void chooseTask(saved);
      }
    }
    requestAnimationFrame(() => emitPerformanceMetric({
      name: "annotation_mode_switch",
      route: "/annotation",
      duration_ms: performance.now() - startedAt,
      stage: nextMode,
    }));
  }, [browserSessionId, chooseTask, mode, profileId, saveOwnedCheckpoint, selectedTask, tasks]);

  useEffect(() => {
    fetch("/api/v1/annotation/tasks?practice_only=true").then((res) => res.ok ? res.json() : Promise.reject()).then((data) => {
      setTasks(data.tasks || []);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    // 档案解锁后自动后台准备专业任务（幂等，失败重试一次）
    if (!profileId) return;
    let cancelled = false;
    const controller = new AbortController();
    const run = (attempt: number) => {
      apiFetch(apiUrl("/api/v1/label-studio/preload"), {
        method: "POST",
        signal: controller.signal,
      })
        .then((res) => {
          if (cancelled) return null;
          if (!res.ok) throw new Error("preload failed");
          return res.json();
        })
        .then((data) => {
          if (cancelled || !data) return;
          setLabelStudio((current) => ({
            ...(current || {}),
            available: current?.available ?? false,
            ready: Boolean(data.ready),
            prepared_count: Number(data.prepared || 0),
            task_urls: data.task_urls || {},
          }));
        })
        .catch(() => {
          if (attempt < 1 && !cancelled) {
            setTimeout(() => run(attempt + 1), 2000);
          }
        });
    };
    run(0);
    return () => { cancelled = true; controller.abort(); };
  }, [profileId]);

  useEffect(() => {
    // 进入专业模式时刷新状态；档案解锁后也可在非 pro 模式提前拉取，用于隐藏 iframe 预载
    if (mode !== "pro" && !profileId) return;
    let cancelled = false;
    Promise.all([
      fetch("/api/v1/label-studio/status", { cache: "no-store" }).then(async (res) => {
        if (res.status === 423) throw Object.assign(new Error("unlocked"), { code: 423 });
        if (!res.ok) throw new Error("status failed");
        return res.json();
      }),
      fetch("/api/v1/label-studio/professional/tasks", { cache: "no-store" }).then((res) => res.ok ? res.json() : { tasks: [] }),
    ])
      .then(([status, assigned]) => {
        if (cancelled) return;
        setLabelStudio(status);
        setProfessionalTasks(assigned.tasks || []);
        // /status 的 prepared_tasks 无 URL；mapping.public_dict() 含 project_id，用它预载项目数据页
        const projectId = status?.mapping?.project_id;
        setPreloadSrc(projectId ? `/api/v1/label-studio/proxy/projects/${projectId}/data` : "");
      })
      .catch((err) => {
        if (cancelled) return;
        if (err?.code === 423) setLabelStudio({ available: false, detail: "unlocked" });
        else setLabelStudio({ available: false, detail: "无法连接本地服务" });
      });
    return () => { cancelled = true; };
  }, [profileId, mode]);

  useEffect(() => {
    // profileId 异步就绪后，用该档案的最后模态修正初始模式（queryMode 时已由 URL 决定，不再覆盖）
    if (!profileId || modeInitializedRef.current || queryMode) return;
    modeInitializedRef.current = true;
    const lastMode = readLastModeFor(profileId);
    if (lastMode && lastMode !== mode) setMode(lastMode);
  }, [profileId, mode, queryMode]);

  useEffect(() => {
    // 关闭/刷新页面前强制落盘草稿与编辑检查点
    const onUnload = () => {
      void saveOwnedCheckpoint();
    };
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, [saveOwnedCheckpoint]);

  useEffect(() => {
    // 深链优先：URL 指定了任务时，不执行 localStorage 恢复
    if (queryTask) return;
    if (tasks.length === 0 || restoredTaskRef.current || !profileId) return;
    restoredTaskRef.current = true;
    let saved: string | null = null;
    try {
      // 模态记忆优先，旧键（无模态后缀）作为兼容回退
      saved = mode !== "pro"
        ? readLastTaskFor(profileId, mode) ?? window.localStorage.getItem(lastTaskKey)
        : window.localStorage.getItem(lastTaskKey);
    } catch { /* ignore */ }
    if (!saved) return;
    const exists = tasks.some((task) => task.id === saved);
    if (exists) void chooseTask(saved);
  }, [tasks, chooseTask, lastTaskKey, profileId, mode]);

  const chooseProfessionalTask = async (taskId: string) => {
    const requestVersion = ++professionalRequestVersion.current;
    const startedAt = performance.now();
    setProfessionalLoading(true);
    setProfessionalUrl("");
    setProfessionalResult(null);
    setPreloadStage("正在准备 Label Studio 项目…");
    setPreloadTimedOut(false);
    const timeoutTimer = window.setTimeout(() => setPreloadTimedOut(true), 15000);
    const stopTimeout = () => window.clearTimeout(timeoutTimer);
    try {
      if (selectedTask && selectedTask !== taskId && editAccess.editable && editAccess.lease) {
        setPreloadStage("正在保存并释放上一任务编辑权…");
        const checkpointed = await saveOwnedCheckpoint();
        if (checkpointed) await releaseAnnotationEditLease(selectedTask, browserSessionId, checkpointed);
      }
      setSelectedTask(taskId);
      setPreloadStage("正在同步编辑权限…");
      await acquireForTask(taskId, "professional");
      setPreloadStage("正在生成专业标注工作台…");
      const response = await apiFetch(apiUrl(`/api/v1/label-studio/prepare/${encodeURIComponent(taskId)}`), { method: "POST" });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "专业任务准备失败");
      }
      const data = await response.json();
      if (requestVersion !== professionalRequestVersion.current) return;
      setProfessionalUrl(data.workbench_url);
      setLabelStudio((current) => ({ ...(current || {}), available: true }));
      writeLastTaskFor(profileId || "", "pro", taskId);
      writeLastModeFor(profileId || "", "pro");
      await openTask({ courseId: "annotation-professional", taskId, mode: "professional_annotation" });
      emitPerformanceMetric({
        name: "annotation_task_visible",
        route: "/annotation",
        duration_ms: performance.now() - startedAt,
        stage: "professional",
      });
    } catch (error) {
      if (requestVersion !== professionalRequestVersion.current) return;
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
      stopTimeout();
      if (requestVersion === professionalRequestVersion.current) {
        setProfessionalLoading(false);
      }
    }
  };

  const queryHandledRef = useRef(false);
  useEffect(() => {
    if (queryHandledRef.current) return;
    if (!queryTask) {
      queryHandledRef.current = true;
      return;
    }
    const inTeaching = tasks.some((task) => task.id === queryTask);
    const inProfessional = professionalTasks.some((task) => task.id === queryTask);
    if (inTeaching || inProfessional) {
      queryHandledRef.current = true;
      if (queryMode === "professional" && inProfessional) {
        void chooseProfessionalTask(queryTask);
      } else {
        void chooseTask(queryTask);
      }
      window.history.replaceState({}, "", "/annotation");
    } else if (tasks.length > 0 && professionalTasks.length > 0) {
      queryHandledRef.current = true;
      window.history.replaceState({}, "", "/annotation");
    }
    // 仅在 tasks/professionalTasks 加载完成后触发一次；chooseTask/chooseProfessionalTask 不应进入依赖
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryTask, queryMode, tasks, professionalTasks]);

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

  const syncProfessionalResult = useCallback(async () => {
    if (!selectedTask || professionalSyncing) return;
    setProfessionalSyncing(true);
    try {
      const response = await apiFetch(apiUrl(`/api/v1/label-studio/sync/${encodeURIComponent(selectedTask)}`), { method: "POST" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data?.detail || "同步失败");
      if (!data.synced) throw new Error(data?.detail || "请先在专业模式中保存标注");
      setProfessionalResult({
        metrics: data.attempt?.metrics || {},
        report: data.attempt?.report || "专业模式标注已同步",
        scoreRecord: data.score_record,
      });
      reportLiveState({ task_id: selectedTask, mode: "professional", stage: "submitted", metrics: data.attempt?.metrics || {} });
    } catch (reason) {
      setEditAccess((current) => ({ ...current, message: reason instanceof Error ? reason.message : "同步失败" }));
    } finally {
      setProfessionalSyncing(false);
    }
  }, [professionalSyncing, reportLiveState, selectedTask]);

  useEffect(() => {
    // 隐藏预载 iframe 同样会被注入桥接脚本；只有专业模式才接收并上报这些事件
    if (mode !== "pro") return;
    const onProfessionalEvent = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.data?.type !== "label_studio_workbench_event") return;
      const allowedStages = new Set(["bridge_ready", "draft_changed", "selection_changed", "tool_changed", "label_changed", "undo", "save", "task_changed"]);
      const rawStage = String(event.data.event || "editing");
      reportLiveState({
        task_id: selectedTask,
        mode: "professional",
        stage: allowedStages.has(rawStage) ? rawStage : "editing",
        annotation_count: Math.max(0, Math.min(10_000, Number(event.data.annotationCount || 0))),
        current_label: String(event.data.label || "").slice(0, 80),
        selected_object_id: String(event.data.selectedObjectId || "").slice(0, 120),
        tool: String(event.data.tool || "").slice(0, 40),
        realtime_bridge: true,
      });
    };
    window.addEventListener("message", onProfessionalEvent);
    return () => window.removeEventListener("message", onProfessionalEvent);
  }, [mode, reportLiveState, selectedTask]);

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
      <header className="flex min-w-0 flex-col gap-3 border-b border-[var(--border)] px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
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
        <div className="flex max-w-full shrink-0 overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--card)] p-1">
          <button
            onClick={() => void switchMode("image")}
            className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
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
            className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
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
            className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
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
            className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
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
            className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
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

      <div className="flex min-w-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-4 py-2 sm:px-6">
          <label className="text-xs text-[var(--muted-foreground)]" htmlFor="task-bank">{mode === "pro" ? "本人专业任务" : "任务库"}</label>
          <select id="task-bank" value={selectedTask} onChange={(event) => void (mode === "pro" ? chooseProfessionalTask(event.target.value) : chooseTask(event.target.value))} className="min-w-0 max-w-md flex-1 rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs">
            <option value="">{mode === "pro" ? "选择后直接进入 Label Studio 题目" : "选择任务后加载到当前标注台"}</option>
            {filteredTasks.map((task) => <option key={task.id} value={task.id}>{task.id} · {task.title}{task.difficulty ? `（${task.difficulty}）` : ""}</option>)}
          </select>
          {mode === "pro" && professionalUrl && <button disabled={professionalSyncing} className="rounded border border-[var(--border)] px-2 py-1 text-xs text-[var(--primary)] disabled:opacity-50" onClick={() => void syncProfessionalResult()}>{professionalSyncing ? "正在评分…" : "同步并评分"}</button>}
        </div>
      {mode === "pro" && professionalResult ? <div className="border-b border-[var(--border)] bg-[var(--card)] px-4 py-3 sm:px-6"><AnnotationResultCard metrics={professionalResult.metrics} report={professionalResult.report} formal revisionNumber={professionalResult.scoreRecord?.revision_number} metricDelta={professionalResult.scoreRecord?.metric_delta} ruleVersion={professionalResult.scoreRecord?.rule_version} referenceVersion={professionalResult.scoreRecord?.reference_version} /></div> : null}
      <div className="flex-1">
        {mode !== "pro" ? selectedTaskData ? <UnifiedAnnotationWorkbench key={selectedTask} task={selectedTaskData} previousTaskId={selectedIndex > 0 ? filteredTasks[selectedIndex - 1]?.id : undefined} nextTaskId={selectedIndex >= 0 ? filteredTasks[selectedIndex + 1]?.id : undefined} onSelectTask={(taskId) => void chooseTask(taskId)} onLiveState={reportLiveState} readOnly={!editAccess.editable} browserSessionId={browserSessionId} leaseVersion={editAccess.lease?.version} onLeaseChange={handleLeaseChange} onLeaseLost={handleLeaseLost} registerDraftSaver={registerDraftSaver} /> : <div className="flex h-full items-center justify-center p-8"><div className="max-w-md rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 text-center"><h2 className="font-semibold">选择一项任务开始练习</h2><p className="mt-2 text-xs leading-5 text-[var(--muted-foreground)]">统一 React 标注台会自动保存草稿到当前学习档案，并把实时进度提供给标注教练。</p></div></div> : labelStudio?.available && professionalUrl ? (
          <div className="relative h-full"><iframe src={professionalUrl} className={`h-full w-full border-0 ${editAccess.editable ? "" : "pointer-events-none opacity-70"}`} title="Label Studio 专业标注台" />{!editAccess.editable && <div className="absolute inset-x-4 top-4 rounded-xl border border-amber-500/35 bg-[var(--card)]/95 p-3 text-center text-xs text-amber-700 shadow-sm">专业标注台当前只读，请先在上方接管编辑。</div>}</div>
        ) : professionalLoading ? (
          <div className="flex h-full items-center justify-center p-6"><div className="max-w-lg rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 text-sm"><h2 className="font-semibold">正在准备你的专业任务…</h2><p className="mt-2 text-[var(--muted-foreground)]">{preloadStage}</p>{preloadTimedOut && <div className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3"><p className="text-amber-800">准备超时。请检查 Label Studio 服务与凭证后重试。</p><button type="button" className="mt-2 rounded-lg bg-amber-600 px-3 py-1.5 font-medium text-white" onClick={() => { if (selectedTask) void chooseProfessionalTask(selectedTask); }}>重试</button></div>}</div></div>
        ) : labelStudio?.available && (labelStudio.ready_count ?? 0) > 0 ? (
          <div className="flex h-full items-center justify-center p-6"><div className="max-w-lg rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 text-sm"><h2 className="font-semibold">专业模式已就绪</h2><p className="mt-2 text-[var(--muted-foreground)]">已准备好 {labelStudio.ready_count ?? 0} 个专业任务，选择后直接进入。</p></div></div>
        ) : labelStudio?.detail === "unlocked" ? (
          <div className="flex h-full items-center justify-center p-6"><div className="max-w-lg rounded-xl border border-amber-500/40 bg-amber-500/10 p-5 text-sm"><h2 className="font-semibold">学习档案未解锁</h2><p className="mt-2 text-[var(--muted-foreground)]">请先在左侧解锁学习档案，专业模式需要档案已解锁后才能使用。</p></div></div>
        ) : <div className="flex h-full items-center justify-center p-6"><div className="max-w-lg rounded-xl border border-amber-500/40 bg-amber-500/10 p-5 text-sm"><h2 className="font-semibold">{labelStudio?.available ? "请选择一项专业任务" : "Label Studio 专业模式尚未就绪"}</h2><p className="mt-2 text-[var(--muted-foreground)]">{labelStudio?.available ? "系统会为当前学习档案准备独立项目，并通过同源网关直接打开，不需要再次登录。" : "请启动本机 8080 服务，并在系统环境中配置 LABEL_STUDIO_API_TOKEN 与 LABEL_STUDIO_BRIDGE_SECRET。教学模式仍可正常使用。"}</p><p className="mt-2 text-xs text-[var(--muted-foreground)]">检测信息：{labelStudio?.detail || (labelStudio?.configured === false ? "服务已连接，但尚未配置 API Token" : "正在检测服务…")}</p>{labelStudio?.management_url && <a className="mt-3 inline-block text-xs text-[var(--primary)] underline" href={labelStudio.management_url} target="_blank" rel="noreferrer">管理员打开 Label Studio 管理台</a>}</div></div>}
      </div>

      {mode !== "pro" && labelStudio?.available && profileId && preloadSrc && (
        <iframe src={preloadSrc} className="pointer-events-none fixed -left-[10000px] top-0 h-[600px] w-[1200px] border-0 opacity-0" aria-hidden tabIndex={-1} title="Label Studio 预加载" />
      )}

      <AnnotationCoach />
    </div>
  );
}

export default function AnnotationPage() {
  return (
    <Suspense fallback={null}>
      <AnnotationPageInner />
    </Suspense>
  );
}
