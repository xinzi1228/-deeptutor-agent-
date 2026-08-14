"use client";

import { Hand, Maximize2, MousePointer2, Redo2, Square, Trash2, Undo2, ZoomIn, ZoomOut } from "lucide-react";

export type BboxTool = "select" | "draw" | "pan";

type Props = {
  tool: BboxTool;
  onToolChange: (tool: BboxTool) => void;
  activeLabel: string;
  labels: string[];
  onActiveLabelChange: (label: string) => void;
  zoom: number;
  onZoomChange: (zoom: number) => void;
  onFit: () => void;
  canUndo: boolean;
  canRedo: boolean;
  hasSelection: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onDelete: () => void;
};

const toolClass = (active: boolean) => `inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs ${active ? "bg-violet-600 text-white" : "border border-[var(--border)] bg-[var(--card)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"}`;

export default function BboxToolbar(props: Props) {
  return <div className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--background)] p-2">
    <div className="flex gap-1">
      <button type="button" className={toolClass(props.tool === "select")} onClick={() => props.onToolChange("select")} title="选择、移动和缩放"><MousePointer2 className="h-3.5 w-3.5" />选择</button>
      <button type="button" className={toolClass(props.tool === "draw")} onClick={() => props.onToolChange("draw")} title="按当前类别绘制矩形框"><Square className="h-3.5 w-3.5" />画框</button>
      <button type="button" className={toolClass(props.tool === "pan")} onClick={() => props.onToolChange("pan")} title="拖动画布"><Hand className="h-3.5 w-3.5" />平移</button>
    </div>
    <label className="ml-1 flex items-center gap-2 text-xs text-[var(--muted-foreground)]">当前类别
      <select value={props.activeLabel} onChange={(event) => props.onActiveLabelChange(event.target.value)} className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1.5 text-[var(--foreground)]">
        {props.labels.map((label) => <option key={label} value={label}>{label}</option>)}
      </select>
    </label>
    <div className="ml-auto flex items-center gap-1">
      <button type="button" className={toolClass(false)} disabled={!props.canUndo} onClick={props.onUndo} title="撤销（Ctrl+Z）"><Undo2 className="h-3.5 w-3.5" /></button>
      <button type="button" className={toolClass(false)} disabled={!props.canRedo} onClick={props.onRedo} title="重做（Ctrl+Y）"><Redo2 className="h-3.5 w-3.5" /></button>
      <button type="button" className={toolClass(false)} disabled={!props.hasSelection} onClick={props.onDelete} title="删除选中框（Delete）"><Trash2 className="h-3.5 w-3.5" /></button>
      <button type="button" className={toolClass(false)} onClick={() => props.onZoomChange(props.zoom - 0.25)} title="缩小"><ZoomOut className="h-3.5 w-3.5" /></button>
      <span className="min-w-11 text-center text-[10px] text-[var(--muted-foreground)]">{Math.round(props.zoom * 100)}%</span>
      <button type="button" className={toolClass(false)} onClick={() => props.onZoomChange(props.zoom + 0.25)} title="放大"><ZoomIn className="h-3.5 w-3.5" /></button>
      <button type="button" className={toolClass(false)} onClick={props.onFit} title="适配画布"><Maximize2 className="h-3.5 w-3.5" /></button>
    </div>
  </div>;
}
