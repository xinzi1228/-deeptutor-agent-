"use client";
import { labelColorFor, labelHotkeyFor } from "./label-style";

export default function BboxLabelPanel({
  labels,
  activeLabel,
  selectedIds,
  onActiveLabelChange,
  onApplyToSelection,
}: {
  labels: string[];
  activeLabel: string;
  selectedIds: string[];
  onActiveLabelChange: (label: string) => void;
  onApplyToSelection: (label: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted-foreground)]">标签</div>
      {labels.map((label, index) => {
        const active = label === activeLabel;
        const color = labelColorFor(label);
        const hotkey = labelHotkeyFor(index);
        return (
          <button
            key={label}
            type="button"
            onClick={() => selectedIds.length ? onApplyToSelection(label) : onActiveLabelChange(label)}
            className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${active ? "border-transparent text-white" : "border-[var(--border)] hover:bg-[var(--muted)]"}`}
            style={{ backgroundColor: active ? color : "transparent" }}
          >
            <span className="h-3 w-3 rounded-sm border border-black/10" style={{ backgroundColor: color }} />
            <span className="flex-1 text-left">{label}</span>
            {hotkey && <kbd className="rounded bg-black/10 px-1 text-[10px]">{hotkey}</kbd>}
          </button>
        );
      })}
    </div>
  );
}
