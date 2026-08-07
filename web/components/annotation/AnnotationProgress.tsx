"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { MapPin } from "lucide-react";

interface FlowState {
  has_flow: boolean;
  task_id?: string;
  current_step?: string;
  steps?: Record<string, unknown>;
}

interface SkillTreeNode {
  id?: string;
  name?: string;
  level?: number;
  mastered?: boolean;
  mastered_count?: number;
  total_leaves?: number;
}

interface SkillTree {
  tree?: SkillTreeNode;
}

export default function AnnotationProgress() {
  const { t } = useTranslation();
  const [flow, setFlow] = useState<FlowState | null>(null);
  const [tree, setTree] = useState<SkillTreeNode | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [flowRes, skillRes] = await Promise.all([
          fetch("/api/v1/profile/teaching-flow"),
          fetch("/api/v1/profile/skill-tree"),
        ]);
        if (cancelled) return;
        if (flowRes.ok) setFlow((await flowRes.json()) as FlowState);
        if (skillRes.ok) {
          const data = (await skillRes.json()) as SkillTree;
          setTree(data.tree ?? null);
        }
      } catch {
        // 静默失败：教学进度展示为可选增强
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const masteredCount = tree?.mastered_count ?? 0;
  const totalLeaves = tree?.total_leaves ?? 1;
  const pct = Math.round((masteredCount / totalLeaves) * 100);

  if (!flow?.has_flow && !tree) return null;

  return (
    <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-2 text-xs">
      <MapPin className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
      <span className="text-[var(--muted-foreground)]">
        {t("annotation.currentTask", "当前任务在能力树位置")}
      </span>
      {tree?.name && (
        <span className="font-medium text-[var(--foreground)]">{tree.name}</span>
      )}
      {tree && (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-28 overflow-hidden rounded-full bg-[var(--border)]">
            <div
              className="h-full rounded-full bg-[var(--primary)]"
              style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
            />
          </div>
          <span className="text-[var(--muted-foreground)]">
            {masteredCount}/{totalLeaves}
          </span>
        </div>
      )}
      {flow?.current_step && (
        <span className="ml-auto rounded-full border border-[var(--border)] px-2 py-0.5 text-[var(--muted-foreground)]">
          {t("annotation.flowStep", "教学流程")}: {flow.current_step}
        </span>
      )}
    </div>
  );
}
