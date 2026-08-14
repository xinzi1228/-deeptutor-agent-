"use client";

import { useTranslation } from "react-i18next";

import { useCurrentLearningTask } from "@/components/current-task/CurrentLearningTaskContext";

const PHASE_LABEL = {
  assigned: "待开始",
  diagnosing: "诊断中",
  theory: "理论学习",
  practice: "实训中",
  review: "待复核",
  paused: "已暂停",
  completed: "已完成",
} as const;

export default function CurrentTaskBar() {
  const { t } = useTranslation();
  const { task, loading } = useCurrentLearningTask();
  if (!task && !loading) return null;
  return (
    <div className="flex min-h-11 items-center gap-3 border-b border-[var(--border)]/70 bg-[var(--card)]/80 px-4 text-sm backdrop-blur">
      <span className="font-medium text-[var(--foreground)]">{t("当前任务")}</span>
      {loading && !task ? (
        <span className="text-[var(--muted-foreground)]">{t("正在读取…")}</span>
      ) : task ? (
        <>
          <span className="max-w-[320px] truncate text-[var(--muted-foreground)]">{task.task_id}</span>
          <span className="rounded-full bg-[var(--primary)]/10 px-2 py-0.5 text-xs text-[var(--primary)]">
            {t(PHASE_LABEL[task.phase])}
          </span>
          {task.draft_ref && <span className="text-xs text-emerald-600">{t("草稿已保存")}</span>}
        </>
      ) : null}
    </div>
  );
}
