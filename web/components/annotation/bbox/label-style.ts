const PALETTE = ["#6366F1", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#F97316", "#EC4899", "#84CC16", "#0EA5E9", "#A855F7", "#14B8A6"];

export function labelColorFor(label: string): string {
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

export function labelHotkeyFor(index: number): string | null {
  return index < 9 ? String(index + 1) : null;
}
