"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Cloud,
  CloudOff,
  Redo2,
  RotateCcw,
  Send,
  Undo2,
} from "lucide-react";
import { apiFetch, apiUrl } from "@/lib/api";
import { invalidateStudentDashboard } from "@/lib/student-dashboard-api";
import { useLearningProfile } from "@/components/learning-profiles/LearningProfileContext";
import type { AnnotationEditLease } from "@/lib/annotation-edit-session";
import BboxCanvas from "@/components/annotation/bbox/BboxCanvas";
import BboxObjectList from "@/components/annotation/bbox/BboxObjectList";
import BboxToolbar, { type BboxTool } from "@/components/annotation/bbox/BboxToolbar";
import { toBbox, validateBoxes, type Bbox, type ImageBounds } from "@/components/annotation/bbox/bbox-geometry";
import { createBboxState, reduceBboxState } from "@/components/annotation/bbox/bbox-reducer";
import {
  clearBrowserAnnotationDraft,
  readBrowserAnnotationDraft,
  retryPendingAnnotationRevisions,
  saveBrowserAnnotationDraft,
  submitAnnotationRevision,
} from "@/lib/learning-api";

export type AnnotationTask = {
  id: string;
  title: string;
  type: string;
  modal: "image" | "text" | "audio" | "video";
  difficulty?: string;
  instruction?: string;
  image_url?: string;
  media_url?: string;
  text?: string;
  labels?: string[];
  items?: Array<{ id: string | number; text: string }>;
  pre_annotation?: Array<Record<string, unknown>>;
};

type Props = {
  task: AnnotationTask;
  previousTaskId?: string;
  nextTaskId?: string;
  onSelectTask: (taskId: string) => void;
  onLiveState?: (state: Record<string, unknown>) => void;
  readOnly?: boolean;
  browserSessionId: string;
  leaseVersion?: number;
  onLeaseChange?: (lease: AnnotationEditLease) => void;
  onLeaseLost?: () => void;
  registerDraftSaver?: (
    saver: (() => Promise<{ draftVersion: number; lease: AnnotationEditLease }>) | null,
  ) => void;
};

type SaveState = "idle" | "saving" | "backend_saved" | "local_pending" | "synced";

function emptyPredictions(task: AnnotationTask): Array<Record<string, unknown>> {
  if (task.type === "classification") return [{ id: 0, label: "" }];
  if (task.type === "judgment") return (task.items || []).map((item) => ({ id: item.id, label: "" }));
  if (task.type === "error_case") return (task.items || []).map((item) => ({ id: item.id, flagged: false }));
  if (task.type === "audio_transcription") return (task.items || []).map((item) => ({ id: item.id, text: "" }));
  if (task.type === "video_tracking") return [{ frame: 0, boxes: [] }];
  return [];
}

function clone(value: Array<Record<string, unknown>>) {
  return JSON.parse(JSON.stringify(value)) as Array<Record<string, unknown>>;
}

function scoreLabel(metrics: Record<string, unknown>) {
  const raw = metrics.f1 ?? metrics.accuracy ?? metrics.compliance_rate;
  if (typeof raw !== "number") return "已评分";
  return `${Math.round(raw * 100)} 分`;
}

export default function UnifiedAnnotationWorkbench({
  task,
  previousTaskId,
  nextTaskId,
  onSelectTask,
  onLiveState,
  readOnly = false,
  browserSessionId,
  leaseVersion,
  onLeaseChange,
  onLeaseLost,
  registerDraftSaver,
}: Props) {
  const { active } = useLearningProfile();
  const activeProfileId = active?.id;
  const [predictions, setPredictions] = useState<Array<Record<string, unknown>>>(() => emptyPredictions(task));
  const [history, setHistory] = useState<Array<Array<Record<string, unknown>>>>([]);
  const [future, setFuture] = useState<Array<Array<Record<string, unknown>>>>([]);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [result, setResult] = useState<{ metrics: Record<string, unknown>; report: string; formal: boolean } | null>(null);
  const [syncPending, setSyncPending] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const hydratedTask = useRef("");
  const predictionsRef = useRef(predictions);
  const leaseVersionRef = useRef(leaseVersion);
  const imageSizeRef = useRef("1000x1000");
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => { predictionsRef.current = predictions; }, [predictions]);
  useEffect(() => { leaseVersionRef.current = leaseVersion; }, [leaseVersion]);

  useEffect(() => {
    let cancelled = false;
    void apiFetch(apiUrl(`/api/v1/annotation/drafts/${encodeURIComponent(task.id)}`), { cache: "no-store" })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => {
        if (cancelled) return;
        const backendUpdatedAt = Date.parse(String(data?.draft?.updated_at || "")) || 0;
        const browserDraft = activeProfileId ? readBrowserAnnotationDraft(activeProfileId, task.id) : null;
        const restored = browserDraft && browserDraft.updatedAt > backendUpdatedAt
          ? browserDraft.predictions
          : data?.draft?.payload?.predictions;
        setPredictions(Array.isArray(restored) ? restored : emptyPredictions(task));
        setSyncPending(data?.draft?.sync_status === "retry_pending");
        if (data?.draft?.sync_status === "synced") setSaveState("synced");
        hydratedTask.current = task.id;
      })
      .catch(() => {
        if (!cancelled) {
          const browserDraft = activeProfileId ? readBrowserAnnotationDraft(activeProfileId, task.id) : null;
          setPredictions(browserDraft?.predictions || emptyPredictions(task));
          if (browserDraft) setSaveState("local_pending");
          hydratedTask.current = task.id;
        }
      });
    return () => { cancelled = true; };
  }, [activeProfileId, task]);

  const update = useCallback((next: Array<Record<string, unknown>>) => {
    if (readOnly) return;
    setPredictions((current) => {
      setHistory((rows) => [...rows.slice(-39), clone(current)]);
      setFuture([]);
      return next;
    });
    setResult(null);
  }, [readOnly]);

  const undo = useCallback(() => {
    setHistory((rows) => {
      const previous = rows.at(-1);
      if (!previous) return rows;
      setPredictions((current) => { setFuture((items) => [clone(current), ...items].slice(0, 40)); return clone(previous); });
      return rows.slice(0, -1);
    });
  }, []);

  const redo = useCallback(() => {
    setFuture((rows) => {
      const next = rows[0];
      if (!next) return rows;
      setPredictions((current) => { setHistory((items) => [...items.slice(-39), clone(current)]); return clone(next); });
      return rows.slice(1);
    });
  }, []);

  const saveDraftNow = useCallback(async () => {
    const operation = saveQueueRef.current.catch(() => undefined).then(async () => {
      const activeLeaseVersion = leaseVersionRef.current;
      if (readOnly || !activeLeaseVersion) throw new Error("当前页面没有编辑权");
      setSaveState("saving");
      try {
        const response = await apiFetch(apiUrl(`/api/v1/annotation/drafts/${encodeURIComponent(task.id)}`), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            task_id: task.id,
            mode: "teaching",
            payload: { predictions: predictionsRef.current, image_size: imageSizeRef.current },
            browser_session_id: browserSessionId,
            lease_version: activeLeaseVersion,
          }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          if (response.status === 409 || response.status === 412) onLeaseLost?.();
          throw new Error(data?.detail || "草稿保存失败");
        }
        const nextLease = data.lease as AnnotationEditLease;
        leaseVersionRef.current = nextLease.version;
        onLeaseChange?.(nextLease);
        setSaveState("backend_saved");
        return { draftVersion: Number(data?.draft?.version || 0), lease: nextLease };
      } catch (reason) {
        setSaveState("local_pending");
        throw reason;
      }
    });
    saveQueueRef.current = operation.then(() => undefined, () => undefined);
    return operation;
  }, [browserSessionId, onLeaseChange, onLeaseLost, readOnly, task.id]);

  useEffect(() => {
    registerDraftSaver?.(readOnly ? null : saveDraftNow);
    return () => registerDraftSaver?.(null);
  }, [readOnly, registerDraftSaver, saveDraftNow]);

  useEffect(() => {
    if (hydratedTask.current !== task.id) return;
    onLiveState?.({ task_id: task.id, mode: "teaching", stage: "editing", annotation_count: predictions.length, labels: predictions.map((item) => item.label).filter(Boolean) });
    if (activeProfileId) saveBrowserAnnotationDraft({ profileId: activeProfileId, taskId: task.id, predictions, updatedAt: Date.now() });
    if (readOnly || !leaseVersionRef.current) return;
    const timer = window.setTimeout(() => {
      void saveDraftNow().catch(() => undefined);
    }, 650);
    return () => window.clearTimeout(timer);
  }, [activeProfileId, onLiveState, predictions, readOnly, saveDraftNow, task.id]);

  const submit = useCallback(async () => {
    if (submitting || readOnly || !leaseVersionRef.current) return;
    setSubmitting(true); setError("");
    try {
      await saveDraftNow();
      const data = await submitAnnotationRevision({
        task_id: task.id,
        task_type: task.type,
        mode: "teaching",
        payload: { predictions, pre_annotation: task.pre_annotation || [], image_size: imageSizeRef.current },
        idempotency_key: `react:${task.id}:${Date.now()}`,
        grade: true,
        browser_session_id: browserSessionId,
        lease_version: leaseVersionRef.current,
      });
      if (!data.finalized) {
        const local = data.local_check || {};
        setSyncPending(true);
        setSaveState("local_pending");
        setResult({
          metrics: local.metrics || {},
          report: `${data.detail || "已暂存本机"}\n\n${local.report || ""}`,
          formal: false,
        });
        return;
      }
      if (activeProfileId) invalidateStudentDashboard(activeProfileId);
      if (activeProfileId) clearBrowserAnnotationDraft(activeProfileId, task.id);
      setSyncPending(false);
      setSaveState("synced");
      setResult({ metrics: data.grade?.metrics || data.attempt?.metrics || {}, report: data.grade?.report || data.attempt?.report || "提交成功", formal: true });
      onLiveState?.({ task_id: task.id, mode: "teaching", stage: "submitted", metrics: data.grade?.metrics || data.attempt?.metrics || {} });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提交失败");
    } finally { setSubmitting(false); }
  }, [activeProfileId, browserSessionId, onLiveState, predictions, readOnly, saveDraftNow, submitting, task]);

  useEffect(() => {
    if (!syncPending) return;
    const retry = () => {
      void retryPendingAnnotationRevisions().then((data) => {
        const completed = data.completed.find((item) => item.attempt?.task_id === task.id)?.attempt;
        if (!completed) return;
        setSyncPending(false);
        setSaveState("synced");
        setResult({ metrics: completed.metrics || {}, report: completed.report || "正式修订已同步", formal: true });
        if (activeProfileId) {
          clearBrowserAnnotationDraft(activeProfileId, task.id);
          invalidateStudentDashboard(activeProfileId);
        }
      }).catch(() => undefined);
    };
    const timer = window.setInterval(retry, 15_000);
    return () => window.clearInterval(timer);
  }, [activeProfileId, syncPending, task.id]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.tagName === "SELECT";
      if (readOnly) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); event.shiftKey ? redo() : undo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") { event.preventDefault(); redo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") { event.preventDefault(); void saveDraftNow().catch(() => undefined); }
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); void submit(); }
      if (!typing && event.key === "ArrowLeft" && previousTaskId) onSelectTask(previousTaskId);
      if (!typing && event.key === "ArrowRight" && nextTaskId) onSelectTask(nextTaskId);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [nextTaskId, onSelectTask, previousTaskId, readOnly, redo, saveDraftNow, submit, undo]);

  const saveText = saveState === "saving" ? "正在保存" : saveState === "backend_saved" ? "草稿已保存" : saveState === "local_pending" ? "暂存本机，等待正式同步" : saveState === "synced" ? "已生成正式修订" : "等待编辑";
  const SaveIcon = saveState === "local_pending" ? CloudOff : Cloud;

  return <div className="grid h-full min-h-0 grid-cols-1 bg-[var(--background)] lg:grid-cols-[minmax(190px,0.72fr)_minmax(380px,2.2fr)_minmax(210px,0.82fr)]">
    <aside className="hidden min-h-0 overflow-y-auto border-r border-[var(--border)] bg-[var(--card)] p-4 lg:block">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">当前任务</div>
      <h2 className="mt-2 text-base font-semibold leading-6">{task.title}</h2>
      <div className="mt-2 flex gap-2 text-[10px]"><span className="rounded-full bg-violet-500/10 px-2 py-1 text-violet-600">{task.modal}</span><span className="rounded-full bg-[var(--muted)] px-2 py-1">{task.type}</span></div>
      <p className="mt-4 text-xs leading-5 text-[var(--muted-foreground)]">{task.instruction || "按任务要求完成标注，提交后系统会给出评分与改进建议。"}</p>
      <div className="mt-5 rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 text-[11px] leading-5 text-[var(--muted-foreground)]"><strong className="text-[var(--foreground)]">快捷键</strong><br />Ctrl+Z 撤销 · Ctrl+Y 重做<br />Ctrl+Enter 提交<br />← / → 切换任务</div>
    </aside>

    <main className="min-h-0 overflow-y-auto p-4 sm:p-5">
      <details className="mb-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 lg:hidden"><summary className="cursor-pointer text-xs font-semibold">当前任务：{task.title}</summary><p className="mt-2 text-xs leading-5 text-[var(--muted-foreground)]">{task.instruction || "按任务要求完成标注，提交后系统会给出评分与改进建议。"}</p></details>
      {readOnly && <div className="mb-3 rounded-xl border border-amber-500/35 bg-amber-500/10 p-3 text-xs text-amber-700">该任务正在另一模式或窗口中编辑。这里保留只读查看，接管后才能修改。</div>}
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <ToolbarButton label="撤销" disabled={readOnly || !history.length} onClick={undo}><Undo2 className="h-4 w-4" /></ToolbarButton>
          <ToolbarButton label="重做" disabled={readOnly || !future.length} onClick={redo}><Redo2 className="h-4 w-4" /></ToolbarButton>
          <ToolbarButton label="重置" disabled={readOnly} onClick={() => update(emptyPredictions(task))}><RotateCcw className="h-4 w-4" /></ToolbarButton>
        </div>
        <span className="inline-flex items-center gap-1.5 text-[11px] text-[var(--muted-foreground)]"><SaveIcon className="h-3.5 w-3.5" />{saveText}</span>
      </div>
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
        <fieldset disabled={readOnly} className={readOnly ? "pointer-events-none opacity-70" : ""}><TaskEditor task={task} predictions={predictions} onChange={update} onUndo={undo} onRedo={redo} canUndo={Boolean(history.length)} canRedo={Boolean(future.length)} onImageSizeChange={(size) => { imageSizeRef.current = `${size.width}x${size.height}`; }} /></fieldset>
      </div>
      {error && <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-600">{error}</div>}
      {result && <section className={`mt-3 rounded-2xl border p-4 ${result.formal ? "border-emerald-500/25 bg-emerald-500/5" : "border-amber-500/35 bg-amber-500/10"}`}><div className={`flex items-center gap-2 font-semibold ${result.formal ? "text-emerald-600" : "text-amber-700"}`}><CheckCircle2 className="h-4 w-4" />{result.formal ? `正式成绩 · ${scoreLabel(result.metrics)}` : `本地检查（非正式）· ${scoreLabel(result.metrics)}`}</div><div className="mt-2 flex flex-wrap gap-2">{Object.entries(result.metrics).map(([key, value]) => <span key={key} className="rounded-lg bg-[var(--background)] px-2 py-1 text-[11px]">{key}: {String(value)}</span>)}</div><p className="mt-3 whitespace-pre-wrap text-xs leading-5 text-[var(--muted-foreground)]">{result.report}</p></section>}
      <details className="mt-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 lg:hidden" open><summary className="cursor-pointer text-xs font-semibold">提交与切换任务</summary><div className="mt-3 flex flex-wrap gap-2">{(task.labels || []).map((label) => <span key={label} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-[11px]">{label}</span>)}</div><button type="button" disabled={readOnly || submitting} onClick={() => void submit()} className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"><Send className="h-4 w-4" />{readOnly ? "只读模式" : submitting ? "正在评分…" : "提交并评分"}</button><div className="mt-2 grid grid-cols-2 gap-2"><button disabled={!previousTaskId} onClick={() => previousTaskId && onSelectTask(previousTaskId)} className="rounded-lg border border-[var(--border)] py-2 text-xs disabled:opacity-40">上一题</button><button disabled={!nextTaskId} onClick={() => nextTaskId && onSelectTask(nextTaskId)} className="rounded-lg border border-[var(--border)] py-2 text-xs disabled:opacity-40">下一题</button></div></details>
    </main>

    <aside className="hidden min-h-0 flex-col border-l border-[var(--border)] bg-[var(--card)] p-4 lg:flex">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">标签与提交</div>
      <div className="mt-3 flex flex-wrap gap-2">{(task.labels || []).map((label) => <span key={label} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-xs">{label}</span>)}</div>
      <div className="mt-auto space-y-2 pt-5"><button type="button" disabled={readOnly || submitting} onClick={() => void submit()} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-violet-500 disabled:opacity-50"><Send className="h-4 w-4" />{readOnly ? "只读模式" : submitting ? "正在评分…" : "提交并评分"}</button><div className="grid grid-cols-2 gap-2"><button disabled={!previousTaskId} onClick={() => previousTaskId && onSelectTask(previousTaskId)} className="inline-flex items-center justify-center gap-1 rounded-lg border border-[var(--border)] py-2 text-xs disabled:opacity-40"><ChevronLeft className="h-3.5 w-3.5" />上一题</button><button disabled={!nextTaskId} onClick={() => nextTaskId && onSelectTask(nextTaskId)} className="inline-flex items-center justify-center gap-1 rounded-lg border border-[var(--border)] py-2 text-xs disabled:opacity-40">下一题<ChevronRight className="h-3.5 w-3.5" /></button></div></div>
    </aside>
  </div>;
}

function ToolbarButton({ label, disabled, onClick, children }: { label: string; disabled?: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" title={label} aria-label={label} disabled={disabled} onClick={onClick} className="rounded-lg border border-transparent p-2 text-[var(--muted-foreground)] hover:border-[var(--border)] hover:bg-[var(--card)] hover:text-[var(--foreground)] disabled:opacity-35">{children}</button>;
}

function TaskEditor({ task, predictions, onChange, onUndo, onRedo, canUndo, canRedo, onImageSizeChange }: { task: AnnotationTask; predictions: Array<Record<string, unknown>>; onChange: (value: Array<Record<string, unknown>>) => void; onUndo: () => void; onRedo: () => void; canUndo: boolean; canRedo: boolean; onImageSizeChange: (size: ImageBounds) => void }) {
  if (task.type === "bbox") return <BBoxEditor task={task} predictions={predictions} onChange={onChange} onUndo={onUndo} onRedo={onRedo} canUndo={canUndo} canRedo={canRedo} onImageSizeChange={onImageSizeChange} />;
  if (task.type === "classification") return <ChoiceEditor task={task} value={String(predictions[0]?.label || "")} onChange={(label) => onChange([{ id: 0, label }])} />;
  if (task.type === "judgment") return <ItemChoiceEditor task={task} predictions={predictions} onChange={onChange} />;
  if (task.type === "error_case") return <ErrorCaseEditor task={task} predictions={predictions} onChange={onChange} />;
  if (task.type === "audio_transcription") return <TranscriptionEditor task={task} predictions={predictions} onChange={onChange} />;
  if (["audio_event", "video_event"].includes(task.type)) return <SegmentEditor task={task} predictions={predictions} onChange={onChange} />;
  if (task.type === "ner") return <NerEditor task={task} predictions={predictions} onChange={onChange} />;
  return <JsonEditor task={task} predictions={predictions} onChange={onChange} />;
}

function Media({ task }: { task: AnnotationTask }) {
  if (task.image_url) return <img src={task.image_url} alt={task.title} className="mx-auto max-h-[440px] max-w-full rounded-xl object-contain" />;
  if (task.modal === "audio" && task.media_url) return <audio controls src={task.media_url} className="w-full" />;
  if (task.modal === "video" && task.media_url) return <video controls src={task.media_url} className="max-h-[400px] w-full rounded-xl bg-black" />;
  if (task.text) return <div className="rounded-xl bg-[var(--muted)]/40 p-5 text-sm leading-7">{task.text}</div>;
  return null;
}

function ChoiceEditor({ task, value, onChange }: { task: AnnotationTask; value: string; onChange: (value: string) => void }) {
  return <div className="space-y-4"><Media task={task} /><div className="grid gap-2 sm:grid-cols-2">{(task.labels || []).map((label) => <button key={label} type="button" onClick={() => onChange(label)} className={`rounded-xl border px-4 py-3 text-left text-sm ${value === label ? "border-violet-500 bg-violet-500/10 text-violet-700" : "border-[var(--border)] hover:bg-[var(--muted)]"}`}>{label}</button>)}</div></div>;
}

function ItemChoiceEditor({ task, predictions, onChange }: { task: AnnotationTask; predictions: Array<Record<string, unknown>>; onChange: (value: Array<Record<string, unknown>>) => void }) {
  return <div className="space-y-3">{(task.items || []).map((item, index) => <div key={item.id} className="rounded-xl border border-[var(--border)] p-3"><p className="text-sm">{item.text}</p><div className="mt-2 flex gap-2">{["correct", "wrong"].map((label) => <button key={label} type="button" onClick={() => onChange(predictions.map((row, i) => i === index ? { ...row, label } : row))} className={`rounded-lg px-3 py-1.5 text-xs ${predictions[index]?.label === label ? "bg-violet-600 text-white" : "bg-[var(--muted)]"}`}>{label === "correct" ? "正确" : "错误"}</button>)}</div></div>)}</div>;
}

function ErrorCaseEditor({ task, predictions, onChange }: { task: AnnotationTask; predictions: Array<Record<string, unknown>>; onChange: (value: Array<Record<string, unknown>>) => void }) {
  return <div className="space-y-3">{(task.items || []).map((item, index) => <label key={item.id} className="flex cursor-pointer gap-3 rounded-xl border border-[var(--border)] p-3"><input type="checkbox" checked={Boolean(predictions[index]?.flagged)} onChange={(event) => onChange(predictions.map((row, i) => i === index ? { ...row, flagged: event.target.checked } : row))} /><span className="text-sm">{item.text}</span></label>)}</div>;
}

function TranscriptionEditor({ task, predictions, onChange }: { task: AnnotationTask; predictions: Array<Record<string, unknown>>; onChange: (value: Array<Record<string, unknown>>) => void }) {
  return <div className="space-y-4"><Media task={task} />{(task.items || []).map((item, index) => <label key={item.id} className="block text-xs text-[var(--muted-foreground)]">{item.text}<textarea value={String(predictions[index]?.text || "")} onChange={(event) => onChange(predictions.map((row, i) => i === index ? { ...row, text: event.target.value } : row))} className="mt-1.5 min-h-20 w-full rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 text-sm text-[var(--foreground)]" /></label>)}</div>;
}

function SegmentEditor({ task, predictions, onChange }: { task: AnnotationTask; predictions: Array<Record<string, unknown>>; onChange: (value: Array<Record<string, unknown>>) => void }) {
  const add = () => onChange([...predictions, { start_time: 0, end_time: 1, label: task.labels?.[0] || "" }]);
  return <div className="space-y-4"><Media task={task} /><button type="button" onClick={add} className="rounded-lg bg-violet-600 px-3 py-2 text-xs text-white">添加时间段</button>{predictions.map((row, index) => <div key={index} className="grid grid-cols-[1fr_1fr_1.5fr_auto] gap-2 rounded-xl border border-[var(--border)] p-3"><input aria-label="开始秒" type="number" step="0.1" value={Number(row.start_time || 0)} onChange={(e) => onChange(predictions.map((item, i) => i === index ? { ...item, start_time: Number(e.target.value) } : item))} className="rounded border border-[var(--border)] bg-transparent px-2" /><input aria-label="结束秒" type="number" step="0.1" value={Number(row.end_time || 0)} onChange={(e) => onChange(predictions.map((item, i) => i === index ? { ...item, end_time: Number(e.target.value) } : item))} className="rounded border border-[var(--border)] bg-transparent px-2" /><select value={String(row.label || "")} onChange={(e) => onChange(predictions.map((item, i) => i === index ? { ...item, label: e.target.value } : item))} className="rounded border border-[var(--border)] bg-[var(--background)] px-2">{(task.labels || []).map((label) => <option key={label}>{label}</option>)}</select><button onClick={() => onChange(predictions.filter((_, i) => i !== index))} className="text-xs text-rose-600">删除</button></div>)}</div>;
}

function NerEditor({ task, predictions, onChange }: { task: AnnotationTask; predictions: Array<Record<string, unknown>>; onChange: (value: Array<Record<string, unknown>>) => void }) {
  return <div className="space-y-4"><Media task={task} /><button type="button" onClick={() => onChange([...predictions, { start: 0, end: 1, label: task.labels?.[0] || "" }])} className="rounded-lg bg-violet-600 px-3 py-2 text-xs text-white">添加实体</button>{predictions.map((row, index) => <div key={index} className="grid grid-cols-[1fr_1fr_1.5fr_auto] gap-2"><input type="number" value={Number(row.start || 0)} onChange={(e) => onChange(predictions.map((item, i) => i === index ? { ...item, start: Number(e.target.value) } : item))} className="rounded border border-[var(--border)] bg-transparent px-2" /><input type="number" value={Number(row.end || 0)} onChange={(e) => onChange(predictions.map((item, i) => i === index ? { ...item, end: Number(e.target.value) } : item))} className="rounded border border-[var(--border)] bg-transparent px-2" /><select value={String(row.label || "")} onChange={(e) => onChange(predictions.map((item, i) => i === index ? { ...item, label: e.target.value } : item))} className="rounded border border-[var(--border)] bg-[var(--background)] px-2">{(task.labels || []).map((label) => <option key={label}>{label}</option>)}</select><button onClick={() => onChange(predictions.filter((_, i) => i !== index))} className="text-xs text-rose-600">删除</button></div>)}</div>;
}

function JsonEditor({ task, predictions, onChange }: { task: AnnotationTask; predictions: Array<Record<string, unknown>>; onChange: (value: Array<Record<string, unknown>>) => void }) {
  const serialized = JSON.stringify(predictions, null, 2);
  return <div className="space-y-4"><Media task={task} /><p className="text-xs text-[var(--muted-foreground)]">该任务使用结构化编辑器。视频跟踪格式为每帧一个对象，包含 frame 与 boxes。</p><textarea key={serialized} spellCheck={false} defaultValue={serialized} onChange={(event) => { try { const value = JSON.parse(event.target.value); if (Array.isArray(value)) onChange(value); } catch { /* keep editing until JSON is valid */ } }} className="min-h-72 w-full rounded-xl border border-[var(--border)] bg-slate-950 p-4 font-mono text-xs text-slate-100" /></div>;
}

function BBoxEditor({ task, predictions, onChange, onUndo, onRedo, canUndo, canRedo, onImageSizeChange }: { task: AnnotationTask; predictions: Array<Record<string, unknown>>; onChange: (value: Array<Record<string, unknown>>) => void; onUndo: () => void; onRedo: () => void; canUndo: boolean; canRedo: boolean; onImageSizeChange: (size: ImageBounds) => void }) {
  const labels = task.labels?.length ? task.labels : ["object"];
  const externalBoxes = useMemo(() => predictions.map(toBbox), [predictions]);
  const [state, dispatch] = useReducer(reduceBboxState, externalBoxes, (boxes) => createBboxState(boxes, labels[0]));
  const [tool, setTool] = useState<BboxTool>("draw");
  const [zoom, setZoom] = useState(1);
  const [bounds, setBounds] = useState<ImageBounds>({ width: 1000, height: 1000 });
  const externalSignature = JSON.stringify(externalBoxes);
  const localSignature = JSON.stringify(state.boxes);

  useEffect(() => {
    if (externalSignature !== localSignature) dispatch({ type: "replace-external", boxes: externalBoxes });
  }, [externalBoxes, externalSignature, localSignature]);

  const commit = useCallback((boxes: Bbox[], selectedId: string | null) => {
    dispatch({ type: "replace-external", boxes });
    dispatch({ type: "select", id: selectedId });
    onChange(boxes);
  }, [onChange]);

  const deleteBox = useCallback((id: string) => {
    commit(state.boxes.filter((box) => box.id !== id), state.selectedId === id ? null : state.selectedId);
  }, [commit, state.boxes, state.selectedId]);

  const changeLabel = useCallback((id: string, label: string) => {
    commit(state.boxes.map((box) => box.id === id ? { ...box, label } : box), id);
  }, [commit, state.boxes]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.tagName === "SELECT";
      if (typing) return;
      if ((event.key === "Delete" || event.key === "Backspace") && state.selectedId) { event.preventDefault(); deleteBox(state.selectedId); }
      if (event.key.toLowerCase() === "v") setTool("select");
      if (event.key.toLowerCase() === "b") setTool("draw");
      if (event.key === "Escape") dispatch({ type: "select", id: null });
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteBox, state.selectedId]);

  const issues = useMemo(() => validateBoxes(state.boxes, bounds), [bounds, state.boxes]);
  return <div className="space-y-3">
    <BboxToolbar tool={tool} onToolChange={setTool} activeLabel={state.activeLabel} labels={labels} onActiveLabelChange={(label) => dispatch({ type: "set-active-label", label })} zoom={zoom} onZoomChange={(value) => setZoom(Math.min(3, Math.max(0.5, value)))} onFit={() => setZoom(1)} canUndo={canUndo} canRedo={canRedo} hasSelection={Boolean(state.selectedId)} onUndo={onUndo} onRedo={onRedo} onDelete={() => state.selectedId && deleteBox(state.selectedId)} />
    <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_220px]">
      <BboxCanvas imageUrl={task.image_url} imageAlt={task.title} boxes={state.boxes} selectedId={state.selectedId} activeLabel={state.activeLabel} tool={tool} zoom={zoom} onSelect={(id) => dispatch({ type: "select", id })} onCommit={commit} onImageSizeChange={(size) => { setBounds(size); onImageSizeChange(size); }} />
      <aside className="hidden max-h-[600px] overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 xl:block"><div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted-foreground)]">对象列表 · {state.boxes.length}</div><BboxObjectList boxes={state.boxes} labels={labels} selectedId={state.selectedId} issues={issues} onSelect={(id) => dispatch({ type: "select", id })} onLabelChange={changeLabel} onDelete={deleteBox} /></aside>
    </div>
    <details className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 xl:hidden"><summary className="cursor-pointer text-xs font-medium">对象列表（{state.boxes.length}）</summary><div className="mt-3"><BboxObjectList boxes={state.boxes} labels={labels} selectedId={state.selectedId} issues={issues} onSelect={(id) => dispatch({ type: "select", id })} onLabelChange={changeLabel} onDelete={deleteBox} /></div></details>
    {issues.length > 0 && <div className="rounded-xl border border-amber-500/35 bg-amber-500/10 p-3 text-xs text-amber-700"><strong>本地质检发现 {issues.length} 项：</strong>{issues.slice(0, 3).map((issue) => <span key={`${issue.boxId}-${issue.code}`} className="ml-2">{issue.message}</span>)}</div>}
    <p className="text-center text-[11px] text-[var(--muted-foreground)]">先选类别再画框；V 选择 · B 画框 · Delete 删除 · Ctrl+S 保存草稿。</p>
  </div>;
}
