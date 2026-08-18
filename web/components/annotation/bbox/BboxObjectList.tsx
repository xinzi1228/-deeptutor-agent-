"use client";

import { Trash2 } from "lucide-react";
import type { Bbox, BboxIssue } from "./bbox-geometry";

type Props = {
  boxes: Bbox[];
  labels: string[];
  selectedIds: string[];
  issues: BboxIssue[];
  onSelect: (ids: string[]) => void;
  onSelectToggle: (id: string) => void;
  onSelectRange: (id: string) => void;
  onLabelChange: (id: string, label: string) => void;
  onDelete: (ids: string[]) => void;
};

export default function BboxObjectList({ boxes, labels, selectedIds, issues, onSelect, onSelectToggle, onSelectRange, onLabelChange, onDelete }: Props) {
  if (!boxes.length) return <div className="rounded-xl border border-dashed border-[var(--border)] p-4 text-center text-xs text-[var(--muted-foreground)]">还没有标注对象。先选择类别，再在图片上拖动画框。</div>;
  return <div className="space-y-2">
    {boxes.map((box, index) => {
      const hasIssue = issues.some((issue) => issue.boxId === box.id);
      const selected = selectedIds.includes(box.id);
      const handleRowClick = (event: React.MouseEvent) => {
        if (event.shiftKey) { onSelectRange(box.id); return; }
        if (event.ctrlKey || event.metaKey) { onSelectToggle(box.id); return; }
        onSelect([box.id]);
      };
      return <div key={box.id} role="button" tabIndex={0} onClick={handleRowClick} onKeyDown={(event) => { if (event.key === "Enter") onSelect([box.id]); }} className={`rounded-xl border p-2.5 ${selected ? "border-violet-500 bg-violet-500/10" : hasIssue ? "border-amber-500/45 bg-amber-500/5" : "border-[var(--border)] bg-[var(--background)]"}`}>
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-violet-500/10 text-[10px] font-semibold text-violet-600">{index + 1}</span>
          <select aria-label={`对象 ${index + 1} 类别`} value={box.label} onClick={(event) => event.stopPropagation()} onChange={(event) => onLabelChange(box.id, event.target.value)} className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-xs">
            {labels.map((label) => <option key={label} value={label}>{label}</option>)}
          </select>
          <button type="button" aria-label={`删除对象 ${index + 1}`} onClick={(event) => { event.stopPropagation(); onDelete([box.id]); }} className="rounded-md p-1 text-[var(--muted-foreground)] hover:bg-rose-500/10 hover:text-rose-600"><Trash2 className="h-3.5 w-3.5" /></button>
        </div>
        <div className="mt-1.5 pl-8 font-mono text-[9px] text-[var(--muted-foreground)]">x {Math.round(box.x)} · y {Math.round(box.y)} · {Math.round(box.w)} × {Math.round(box.h)}</div>
      </div>;
    })}
  </div>;
}
