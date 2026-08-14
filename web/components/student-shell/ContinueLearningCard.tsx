"use client";

import { ArrowRight, BookOpen, Tag } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { CurrentLearningTask } from "@/lib/current-learning-task-api";

const PHASE_LABEL: Record<CurrentLearningTask["phase"], string> = {
  assigned: "待开始",
  diagnosing: "入门诊断",
  theory: "理论学习",
  practice: "标注练习",
  review: "复盘巩固",
  paused: "已暂停",
  completed: "已完成",
};

export default function ContinueLearningCard({
  task,
  loading,
  onContinue,
}: {
  task: CurrentLearningTask | null;
  loading: boolean;
  onContinue: () => void;
}) {
  const { t } = useTranslation();
  const practice = task?.mode === "teaching_annotation" || task?.mode === "professional_annotation";
  const Icon = practice ? Tag : BookOpen;

  return (
    <section className="rounded-3xl border border-blue-500/15 bg-gradient-to-br from-blue-500/[0.09] via-[var(--card)] to-violet-500/[0.06] p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-600 dark:text-blue-300">
            <Icon size={20} />
          </span>
          <div className="min-w-0">
            <p className="text-xs font-medium text-blue-600 dark:text-blue-300">{t("继续上次学习")}</p>
            <h2 className="mt-1 truncate text-lg font-semibold text-[var(--foreground)]">
              {loading ? t("正在读取学习进度…") : task ? task.task_id : t("开始第一次学习")}
            </h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              {task ? `${PHASE_LABEL[task.phase]} · ${practice ? t("数据标注实训") : t("理论学习")}` : t("先告诉标注教练你想学习什么，我们会为你安排下一步。")}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onContinue}
          disabled={loading}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-[var(--primary)] px-3.5 py-2 text-sm font-medium text-[var(--primary-foreground)] transition hover:opacity-90 disabled:opacity-50"
        >
          {task ? t("继续") : t("开始")}
          <ArrowRight size={15} />
        </button>
      </div>
    </section>
  );
}
