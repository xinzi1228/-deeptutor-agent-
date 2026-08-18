"use client";

import { useEffect, useState } from "react";
import { Target, Trophy } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";

import ContinueLearningCard from "@/components/student-shell/ContinueLearningCard";
import { useCurrentLearningTask } from "@/components/current-task/CurrentLearningTaskContext";
import type { LearningReport, ProfileOverview } from "@/lib/learning-stats-api";
import { getStudentHomeDashboard } from "@/lib/student-dashboard-api";
import { useLearningProfile } from "@/components/learning-profiles/LearningProfileContext";

export default function StudentHomeSummary({ onStartChat }: { onStartChat: () => void }) {
  const router = useRouter();
  const { t } = useTranslation();
  const { task, loading } = useCurrentLearningTask();
  const { active } = useLearningProfile();
  const activeProfileId = active?.id;
  const [overview, setOverview] = useState<ProfileOverview | null>(null);
  const [report, setReport] = useState<LearningReport | null>(null);

  useEffect(() => {
    if (!activeProfileId) return;
    let cancelled = false;
    const controller = new AbortController();
    void getStudentHomeDashboard(activeProfileId, controller.signal)
      .then((result) => {
        if (cancelled) return;
        setOverview(result.overview);
        setReport(result.report);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [activeProfileId]);

  const continueLearning = () => {
    if (task?.mode === "teaching_annotation" && task.task_id) {
      router.push(`/annotation?task=${encodeURIComponent(task.task_id)}&mode=teaching`);
      return;
    }
    if (task?.mode === "professional_annotation" && task.task_id) {
      router.push(`/annotation?task=${encodeURIComponent(task.task_id)}&mode=professional`);
      return;
    }
    onStartChat();
  };

  const latestResult = overview?.latest_f1 == null
    ? overview?.total_tasks_completed
      ? `已完成 ${overview.total_tasks_completed} 项任务`
      : "完成首个任务后生成"
    : `最近 F1 ${(overview.latest_f1 * 100).toFixed(1)}%`;

  return (
    <div className="w-full max-w-[820px] space-y-4">
      <div>
        <p className="text-sm text-[var(--muted-foreground)]">{t("今天只看最重要的下一步")}</p>
        <h1 className="mt-1 font-serif text-3xl font-semibold tracking-tight text-[var(--foreground)]">{t("开始今天的学习")}</h1>
      </div>
      <ContinueLearningCard task={task} loading={loading} onContinue={continueLearning} />
      <div className="grid gap-3 sm:grid-cols-2">
        <article className="rounded-2xl border border-[var(--border)]/70 bg-[var(--card)] p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-[var(--foreground)]"><Target size={16} className="text-amber-500" />{t("当前薄弱点")}</div>
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--muted-foreground)]">{report?.summary.priority_gap || t("暂无明确薄弱点，完成一次诊断后会自动更新。")}</p>
        </article>
        <article className="rounded-2xl border border-[var(--border)]/70 bg-[var(--card)] p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-[var(--foreground)]"><Trophy size={16} className="text-emerald-500" />{t("最近结果")}</div>
          <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">{latestResult}</p>
        </article>
      </div>
    </div>
  );
}
