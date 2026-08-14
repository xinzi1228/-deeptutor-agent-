"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

type SaveState = "idle" | "saving" | "saved" | "offline";

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
  const [result, setResult] = useState<{ metrics: Record<string, unknown>; report: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const hydratedTask = useRef("");
  const predictionsRef = useRef(predictions);
  const leaseVersionRef = useRef(leaseVersion);

  useEffect(() => { predictionsRef.current = predictions; }, [predictions]);
  useEffect(() => { leaseVersionRef.current = leaseVersion; }, [leaseVersion]);

  useEffect(() => {
    let cancelled = false;
    void apiFetch(apiUrl(`/api/v1/annotation/drafts/${encodeURIComponent(task.id)}`), { cache: "no-store" })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => {
        if (cancelled) return;
        const restored = data?.draft?.payload?.predictions;
        setPredictions(Array.isArray(restored) ? restored : emptyPredictions(task));
        hydratedTask.current = task.id;
      })
      .catch(() => {
        if (!cancelled) {
          setPredictions(emptyPredictions(task));
          hydratedTask.current = task.id;
        }
      });
    return () => { cancelled = true; };
  }, [task]);

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
          payload: { predictions: predictionsRef.current },
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
      setSaveState("saved");
      return { draftVersion: Number(data?.draft?.version || 0), lease: nextLease };
    } catch (reason) {
      setSaveState("offline");
      throw reason;
    }
  }, [browserSessionId, onLeaseChange, onLeaseLost, readOnly, task.id]);

  useEffect(() => {
    registerDraftSaver?.(readOnly ? null : saveDraftNow);
    return () => registerDraftSaver?.(null);
  }, [readOnly, registerDraftSaver, saveDraftNow]);

  useEffect(() => {
    if (hydratedTask.current !== task.id) return;
    onLiveState?.({ task_id: task.id, mode: "teaching", stage: "editing", annotation_count: predictions.length, labels: predictions.map((item) => item.label).filter(Boolean) });
    if (readOnly || !leaseVersionRef.current) return;
    const timer = window.setTimeout(() => {
      void saveDraftNow().catch(() => undefined);
    }, 650);
    return () => window.clearTimeout(timer);
  }, [onLiveState, predictions, readOnly, saveDraftNow, task.id]);

  const submit = useCallback(async () => {
    if (submitting || readOnly || !leaseVersionRef.current) return;
    setSubmitting(true); setError("");
    try {
      const response = await apiFetch(apiUrl("/api/v1/annotation/attempts"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: task.id,
          task_type: task.type,
          mode: "teaching",
          payload: { predictions, pre_annotation: task.pre_annotation || [] },
          idempotency_key: `react:${task.id}:${Date.now()}`,
          grade: true,
          browser_session_id: browserSessionId,
          lease_version: leaseVersionRef.current,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "提交失败");
      if (activeProfileId) invalidateStudentDashboard(activeProfileId);
      setResult({ metrics: data.grade?.metrics || data.attempt?.metrics || {}, report: data.grade?.report || data.attempt?.report || "提交成功" });
      onLiveState?.({ task_id: task.id, mode: "teaching", stage: "submitted", metrics: data.grade?.metrics || data.attempt?.metrics || {} });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提交失败");
    } finally { setSubmitting(false); }
  }, [activeProfileId, browserSessionId, onLiveState, predictions, readOnly, submitting, task]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.tagName === "SELECT";
      if (readOnly) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); event.shiftKey ? redo() : undo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") { event.preventDefault(); redo(); }
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); void submit(); }
      if (!typing && event.key === "ArrowLeft" && previousTaskId) onSelectTask(previousTaskId);
      if (!typing && event.key === "ArrowRight" && nextTaskId) onSelectTask(nextTaskId);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [nextTaskId, onSelectTask, previousTaskId, readOnly, redo, submit, undo]);

  const saveText = saveState === "saving" ? "正在保存" : saveState === "saved" ? "已保存到当前档案" : saveState === "offline" ? "离线缓存待恢复" : "等待编辑";
  const SaveIcon = saveState === "offline" ? CloudOff : Cloud;

  return <div className="grid h-full min-h-0 grid-cols-[minmax(210px,0.72fr)_minmax(420px,2.2fr)_minmax(230px,0.82fr)] bg-[var(--background)]">
    <aside className="min-h-0 overflow-y-auto border-r border-[var(--border)] bg-[var(--card)] p-4">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">当前任务</div>
      <h2 className="mt-2 text-base font-semibold leading-6">{task.title}</h2>
      <div className="mt-2 flex gap-2 text-[10px]"><span className="rounded-full bg-violet-500/10 px-2 py-1 text-violet-600">{task.modal}</span><span className="rounded-full bg-[var(--muted)] px-2 py-1">{task.type}</span></div>
      <p className="mt-4 text-xs leading-5 text-[var(--muted-foreground)]">{task.instruction || "按任务要求完成标注，提交后系统会给出评分与改进建议。"}</p>
      <div className="mt-5 rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 text-[11px] leading-5 text-[var(--muted-foreground)]"><strong className="text-[var(--foreground)]">快捷键</strong><br />Ctrl+Z 撤销 · Ctrl+Y 重做<br />Ctrl+Enter 提交<br />← / → 切换任务</div>
    </aside>

    <main className="min-h-0 overflow-y-auto p-4 sm:p-5">
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
        <fieldset disabled={readOnly} className={readOnly ? "opacity-70" : ""}><TaskEditor task={task} predictions={predictions} onChange={update} /></fieldset>
      </div>
      {error && <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-600">{error}</div>}
      {result && <section className="mt-3 rounded-2xl border border-emerald-500/25 bg-emerald-500/5 p-4"><div className="flex items-center gap-2 font-semibold text-emerald-600"><CheckCircle2 className="h-4 w-4" />{scoreLabel(result.metrics)}</div><div className="mt-2 flex flex-wrap gap-2">{Object.entries(result.metrics).map(([key, value]) => <span key={key} className="rounded-lg bg-[var(--background)] px-2 py-1 text-[11px]">{key}: {String(value)}</span>)}</div><p className="mt-3 whitespace-pre-wrap text-xs leading-5 text-[var(--muted-foreground)]">{result.report}</p></section>}
    </main>

    <aside className="flex min-h-0 flex-col border-l border-[var(--border)] bg-[var(--card)] p-4">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">标签与提交</div>
      <div className="mt-3 flex flex-wrap gap-2">{(task.labels || []).map((label) => <span key={label} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-xs">{label}</span>)}</div>
      <div className="mt-auto space-y-2 pt-5"><button type="button" disabled={readOnly || submitting} onClick={() => void submit()} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-violet-500 disabled:opacity-50"><Send className="h-4 w-4" />{readOnly ? "只读模式" : submitting ? "正在评分…" : "提交并评分"}</button><div className="grid grid-cols-2 gap-2"><button disabled={!previousTaskId} onClick={() => previousTaskId && onSelectTask(previousTaskId)} className="inline-flex items-center justify-center gap-1 rounded-lg border border-[var(--border)] py-2 text-xs disabled:opacity-40"><ChevronLeft className="h-3.5 w-3.5" />上一题</button><button disabled={!nextTaskId} onClick={() => nextTaskId && onSelectTask(nextTaskId)} className="inline-flex items-center justify-center gap-1 rounded-lg border border-[var(--border)] py-2 text-xs disabled:opacity-40">下一题<ChevronRight className="h-3.5 w-3.5" /></button></div></div>
    </aside>
  </div>;
}

function ToolbarButton({ label, disabled, onClick, children }: { label: string; disabled?: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" title={label} aria-label={label} disabled={disabled} onClick={onClick} className="rounded-lg border border-transparent p-2 text-[var(--muted-foreground)] hover:border-[var(--border)] hover:bg-[var(--card)] hover:text-[var(--foreground)] disabled:opacity-35">{children}</button>;
}

function TaskEditor({ task, predictions, onChange }: { task: AnnotationTask; predictions: Array<Record<string, unknown>>; onChange: (value: Array<Record<string, unknown>>) => void }) {
  if (task.type === "bbox") return <BBoxEditor task={task} predictions={predictions} onChange={onChange} />;
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

function BBoxEditor({ task, predictions, onChange }: { task: AnnotationTask; predictions: Array<Record<string, unknown>>; onChange: (value: Array<Record<string, unknown>>) => void }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const [preview, setPreview] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [imageSize, setImageSize] = useState({ width: 1000, height: 1000 });
  const point = (event: React.PointerEvent) => { const rect = ref.current!.getBoundingClientRect(); return { x: Math.round(((event.clientX - rect.left) / rect.width) * imageSize.width), y: Math.round(((event.clientY - rect.top) / rect.height) * imageSize.height) }; };
  return <div className="space-y-3"><div ref={ref} className="relative mx-auto max-w-4xl touch-none overflow-hidden rounded-xl bg-slate-950" onPointerDown={(e) => { start.current = point(e); (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); }} onPointerMove={(e) => { if (!start.current) return; const end = point(e); setPreview({ x: Math.min(start.current.x, end.x), y: Math.min(start.current.y, end.y), w: Math.abs(end.x - start.current.x), h: Math.abs(end.y - start.current.y) }); }} onPointerUp={() => { if (preview && preview.w > 4 && preview.h > 4) onChange([...predictions, { ...preview, label: task.labels?.[0] || "object" }]); start.current = null; setPreview(null); }}><img src={task.image_url} alt={task.title} draggable={false} onLoad={(event) => setImageSize({ width: event.currentTarget.naturalWidth || 1000, height: event.currentTarget.naturalHeight || 1000 })} className="block max-h-[560px] w-full object-contain" />{predictions.map((box, index) => <button type="button" title="点击删除此框" key={index} onClick={() => onChange(predictions.filter((_, i) => i !== index))} className="absolute border-2 border-cyan-400 bg-cyan-400/10" style={{ left: `${(Number(box.x) / imageSize.width) * 100}%`, top: `${(Number(box.y) / imageSize.height) * 100}%`, width: `${(Number(box.w) / imageSize.width) * 100}%`, height: `${(Number(box.h) / imageSize.height) * 100}%` }}><span className="absolute -top-5 left-[-2px] bg-cyan-500 px-1 text-[9px] text-white">{String(box.label || "object")}</span></button>)}{preview && <div className="pointer-events-none absolute border-2 border-violet-400 bg-violet-400/10" style={{ left: `${(preview.x / imageSize.width) * 100}%`, top: `${(preview.y / imageSize.height) * 100}%`, width: `${(preview.w / imageSize.width) * 100}%`, height: `${(preview.h / imageSize.height) * 100}%` }} />}</div><p className="text-center text-[11px] text-[var(--muted-foreground)]">在图片上按住并拖动绘制矩形框；点击已有框可删除。</p></div>;
}
