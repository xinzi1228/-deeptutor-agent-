"use client";

import { useMemo, useRef, useState } from "react";
import {
  clampBox,
  moveBox,
  resizeBox,
  type Bbox,
  type ImageBounds,
  type ResizeHandle,
} from "./bbox-geometry";
import type { BboxTool } from "./BboxToolbar";

type Props = {
  imageUrl?: string;
  imageAlt: string;
  boxes: Bbox[];
  selectedId: string | null;
  activeLabel: string;
  tool: BboxTool;
  zoom: number;
  onSelect: (id: string | null) => void;
  onCommit: (boxes: Bbox[], selectedId: string | null) => void;
  onImageSizeChange: (bounds: ImageBounds) => void;
};

type Interaction =
  | { kind: "draw"; start: { x: number; y: number } }
  | { kind: "move"; start: { x: number; y: number }; box: Bbox }
  | { kind: "resize"; start: { x: number; y: number }; box: Bbox; handle: ResizeHandle }
  | { kind: "pan"; clientX: number; clientY: number; scrollLeft: number; scrollTop: number };

const handles: Array<{ name: ResizeHandle; className: string; cursor: string }> = [
  { name: "nw", className: "-left-1.5 -top-1.5", cursor: "nwse-resize" },
  { name: "n", className: "left-1/2 -top-1.5 -translate-x-1/2", cursor: "ns-resize" },
  { name: "ne", className: "-right-1.5 -top-1.5", cursor: "nesw-resize" },
  { name: "e", className: "-right-1.5 top-1/2 -translate-y-1/2", cursor: "ew-resize" },
  { name: "se", className: "-bottom-1.5 -right-1.5", cursor: "nwse-resize" },
  { name: "s", className: "-bottom-1.5 left-1/2 -translate-x-1/2", cursor: "ns-resize" },
  { name: "sw", className: "-bottom-1.5 -left-1.5", cursor: "nesw-resize" },
  { name: "w", className: "-left-1.5 top-1/2 -translate-y-1/2", cursor: "ew-resize" },
];

const newId = () => globalThis.crypto?.randomUUID?.() || `box-${Date.now()}-${Math.random()}`;

export default function BboxCanvas(props: Props) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const interaction = useRef<Interaction | null>(null);
  const draftBoxRef = useRef<Bbox | null>(null);
  const [bounds, setBounds] = useState<ImageBounds>({ width: 1000, height: 1000 });
  const [draftBox, setDraftBox] = useState<Bbox | null>(null);
  const renderedBoxes = useMemo(() => draftBox ? props.boxes.map((box) => box.id === draftBox.id ? draftBox : box) : props.boxes, [draftBox, props.boxes]);
  const updateDraft = (box: Bbox | null) => { draftBoxRef.current = box; setDraftBox(box); };

  const point = (event: React.PointerEvent) => {
    const rect = stageRef.current!.getBoundingClientRect();
    return {
      x: Math.min(bounds.width, Math.max(0, ((event.clientX - rect.left) / rect.width) * bounds.width)),
      y: Math.min(bounds.height, Math.max(0, ((event.clientY - rect.top) / rect.height) * bounds.height)),
    };
  };

  const beginStage = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    if (props.tool === "select") { props.onSelect(null); return; }
    event.currentTarget.setPointerCapture(event.pointerId);
    if (props.tool === "pan") {
      const viewport = viewportRef.current!;
      interaction.current = { kind: "pan", clientX: event.clientX, clientY: event.clientY, scrollLeft: viewport.scrollLeft, scrollTop: viewport.scrollTop };
      return;
    }
    const start = point(event);
    interaction.current = { kind: "draw", start };
    updateDraft({ id: "__draft__", x: start.x, y: start.y, w: 0, h: 0, label: props.activeLabel });
  };

  const movePointer = (event: React.PointerEvent<HTMLDivElement>) => {
    const active = interaction.current;
    if (!active) return;
    if (active.kind === "pan") {
      const viewport = viewportRef.current!;
      viewport.scrollLeft = active.scrollLeft - (event.clientX - active.clientX);
      viewport.scrollTop = active.scrollTop - (event.clientY - active.clientY);
      return;
    }
    const current = point(event);
    const dx = current.x - active.start.x;
    const dy = current.y - active.start.y;
    if (active.kind === "draw") {
      updateDraft(clampBox({ id: "__draft__", x: Math.min(active.start.x, current.x), y: Math.min(active.start.y, current.y), w: Math.abs(dx), h: Math.abs(dy), label: props.activeLabel }, bounds));
    } else if (active.kind === "move") {
      updateDraft(moveBox(active.box, dx, dy, bounds));
    } else {
      updateDraft(resizeBox(active.box, active.handle, dx, dy, bounds));
    }
  };

  const endPointer = () => {
    const active = interaction.current;
    interaction.current = null;
    const finished = draftBoxRef.current;
    if (!active || active.kind === "pan") { updateDraft(null); return; }
    if (!finished || finished.w < 4 || finished.h < 4) { updateDraft(null); return; }
    if (active.kind === "draw") {
      const created = { ...finished, id: newId() };
      props.onCommit([...props.boxes, created], created.id);
    } else {
      props.onCommit(props.boxes.map((box) => box.id === finished.id ? finished : box), finished.id);
    }
    updateDraft(null);
  };

  const beginBox = (event: React.PointerEvent, box: Bbox) => {
    if (props.tool !== "select") return;
    event.stopPropagation();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    props.onSelect(box.id);
    interaction.current = { kind: "move", start: point(event), box: { ...box } };
  };

  const beginResize = (event: React.PointerEvent, box: Bbox, handle: ResizeHandle) => {
    event.stopPropagation();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    interaction.current = { kind: "resize", start: point(event), box: { ...box }, handle };
  };

  const fitWidth = Math.min(900, Math.max(280, (bounds.width / Math.max(1, bounds.height)) * 560));
  const stageWidth = Math.max(160, Math.round(fitWidth * props.zoom));
  return <div ref={viewportRef} className={`max-h-[600px] overflow-auto rounded-xl bg-slate-950/95 p-3 ${props.tool === "pan" ? "cursor-grab" : props.tool === "draw" ? "cursor-crosshair" : "cursor-default"}`}>
    <div ref={stageRef} className="relative mx-auto touch-none select-none overflow-visible bg-slate-900 shadow-2xl" style={{ width: stageWidth, aspectRatio: `${bounds.width} / ${bounds.height}` }} onPointerDown={beginStage} onPointerMove={movePointer} onPointerUp={endPointer} onPointerCancel={endPointer}>
      {props.imageUrl ? <img src={props.imageUrl} alt={props.imageAlt} draggable={false} onLoad={(event) => { const next = { width: event.currentTarget.naturalWidth || 1000, height: event.currentTarget.naturalHeight || 1000 }; setBounds(next); props.onImageSizeChange(next); }} className="pointer-events-none absolute inset-0 h-full w-full object-contain" /> : <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">任务图片暂不可用</div>}
      {renderedBoxes.map((box, index) => {
        const selected = props.selectedId === box.id;
        return <div key={box.id} role="button" tabIndex={0} aria-label={`对象 ${index + 1}：${box.label}`} onPointerDown={(event) => beginBox(event, box)} className={`absolute border-2 ${selected ? "z-20 border-violet-400 bg-violet-400/15" : "z-10 border-cyan-400 bg-cyan-400/10"}`} style={{ left: `${(box.x / bounds.width) * 100}%`, top: `${(box.y / bounds.height) * 100}%`, width: `${(box.w / bounds.width) * 100}%`, height: `${(box.h / bounds.height) * 100}%`, cursor: props.tool === "select" ? "move" : undefined }}>
          <span className={`pointer-events-none absolute -top-5 left-[-2px] whitespace-nowrap px-1 text-[9px] text-white ${selected ? "bg-violet-500" : "bg-cyan-500"}`}>{index + 1} · {box.label}</span>
          {selected && props.tool === "select" && handles.map((handle) => <span key={handle.name} role="button" aria-label={`${handle.name} 缩放手柄`} onPointerDown={(event) => beginResize(event, box, handle.name)} className={`absolute h-3 w-3 rounded-sm border border-white bg-violet-500 ${handle.className}`} style={{ cursor: handle.cursor }} />)}
        </div>;
      })}
      {draftBox?.id === "__draft__" && <div className="pointer-events-none absolute z-20 border-2 border-violet-400 bg-violet-400/15" style={{ left: `${(draftBox.x / bounds.width) * 100}%`, top: `${(draftBox.y / bounds.height) * 100}%`, width: `${(draftBox.w / bounds.width) * 100}%`, height: `${(draftBox.h / bounds.height) * 100}%` }} />}
    </div>
  </div>;
}
