"use client";

import { ChevronRight, CheckCircle2, Circle } from "lucide-react";
import type { SkillTreeNode } from "@/lib/learning-stats-api";

interface SkillTreeProps {
  tree: SkillTreeNode | null;
}

function TreeNode({ node, depth = 0 }: { node: SkillTreeNode; depth?: number }) {
  const showChildren = node.children && node.children.length > 0;
  const isLeaf = node.level === 4;
  const colors: Record<number, string> = {
    1: "var(--foreground)",
    2: "var(--blue-500,#3b82f6)",
    3: "var(--purple-500,#a855f7)",
  };

  return (
    <div className="ml-0">
      <div
        className="flex items-center gap-1.5 py-0.5"
        style={{ paddingLeft: depth * 20 }}
      >
        {isLeaf ? (
          <span className="flex-shrink-0">
            {node.mastered ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <Circle className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
            )}
          </span>
        ) : showChildren ? (
          <ChevronRight className="h-3 w-3 text-[var(--muted-foreground)]" />
        ) : null}
        <span
          className="text-xs font-medium"
          style={{ color: colors[node.level] || "var(--muted-foreground)" }}
        >
          {node.name}
        </span>
        {node.mastered_count !== undefined && node.total_leaves !== undefined && (
          <span className="ml-1 text-[10px] text-[var(--muted-foreground)]">
            {node.mastered_count}/{node.total_leaves}
          </span>
        )}
      </div>
      {showChildren &&
        node.children!.map((child) => (
          <TreeNode key={child.id} node={child} depth={depth + 1} />
        ))}
    </div>
  );
}

export function SkillTree({ tree }: SkillTreeProps) {
  if (!tree) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
        <p className="text-sm text-[var(--muted-foreground)]">暂无数据</p>
      </div>
    );
  }

  const totalLeaves = tree.total_leaves || 1;
  const masteredCount = tree.mastered_count || 0;
  const pct = Math.round((masteredCount / totalLeaves) * 100);

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">能力图谱</h3>
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-[var(--border)]">
            <div
              className="h-full rounded-full bg-blue-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-xs text-[var(--muted-foreground)]">{pct}%</span>
        </div>
      </div>
      <TreeNode node={tree} />
    </div>
  );
}
