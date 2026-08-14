"use client";

import { useTranslation } from "react-i18next";
import { CheckCircle2, XCircle, AlertCircle } from "lucide-react";

interface CheckMetrics {
  precision?: number;
  recall?: number;
  f1?: number;
  accuracy?: number;
  correct?: number;
  total?: number;
  [key: string]: unknown;
}

interface AnnotationResultCardProps {
  metrics: CheckMetrics;
  report?: string;
  formal?: boolean;
  revisionNumber?: number;
  metricDelta?: Record<string, number>;
  ruleVersion?: string;
  referenceVersion?: string;
}

function pct(value?: number): string {
  if (typeof value !== "number") return "—";
  return `${Math.round(value * 100)}%`;
}

export default function AnnotationResultCard({
  metrics,
  report,
  formal = true,
  revisionNumber,
  metricDelta,
  ruleVersion,
  referenceVersion,
}: AnnotationResultCardProps) {
  const { t } = useTranslation();

  const f1 = typeof metrics.f1 === "number" ? metrics.f1 : null;
  const accuracy = typeof metrics.accuracy === "number" ? metrics.accuracy : null;
  const score = f1 ?? accuracy;

  let tone: "good" | "ok" | "bad" | "none" = "none";
  let Icon = AlertCircle;
  if (score !== null) {
    if (score >= 0.8) {
      tone = "good";
      Icon = CheckCircle2;
    } else if (score >= 0.6) {
      tone = "ok";
      Icon = AlertCircle;
    } else {
      tone = "bad";
      Icon = XCircle;
    }
  }

  const toneClass =
    tone === "good"
      ? "border-[var(--primary)]/40 text-[var(--primary)]"
      : tone === "bad"
        ? "border-[var(--destructive)]/40 text-[var(--destructive)]"
        : "border-[var(--border)] text-[var(--muted-foreground)]";

  return (
    <div className={`rounded-lg border p-3 text-xs ${toneClass}`}>
      <div className="mb-1 flex items-center gap-2 font-medium">
        <Icon className="h-4 w-4" />
        <span>{formal ? t("annotation.resultCard.title", "本次正式评分") : "本地检查（非正式）"}</span>
        {revisionNumber ? <span className="ml-auto rounded-full border border-current/20 px-2 py-0.5 text-[10px]">第 {revisionNumber} 次修订</span> : null}
      </div>
      {metricDelta && Object.keys(metricDelta).length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {Object.entries(metricDelta).map(([key, value]) => (
            <span key={key} className={`rounded-full px-2 py-0.5 text-[10px] ${value >= 0 ? "bg-emerald-500/10 text-emerald-700" : "bg-rose-500/10 text-rose-700"}`}>
              较上次 {key} {value >= 0 ? "+" : ""}{Math.round(value * 100)}%
            </span>
          ))}
        </div>
      ) : null}
      <div className="flex flex-wrap gap-4">
        {f1 !== null && (
          <span>{t("annotation.resultCard.f1", "F1")}: <b>{pct(f1)}</b></span>
        )}
        {metrics.precision !== undefined && (
          <span>{t("annotation.resultCard.precision", "精确率")}: <b>{pct(metrics.precision)}</b></span>
        )}
        {metrics.recall !== undefined && (
          <span>{t("annotation.resultCard.recall", "召回率")}: <b>{pct(metrics.recall)}</b></span>
        )}
        {accuracy !== null && (
          <span>{t("annotation.resultCard.accuracy", "准确率")}: <b>{pct(accuracy)}</b></span>
        )}
        {typeof metrics.correct === "number" && typeof metrics.total === "number" && (
          <span>
            {t("annotation.resultCard.correct", "正确")}: {metrics.correct}/{metrics.total}
          </span>
        )}
      </div>
      {report && (
        <div className="mt-2 max-h-28 overflow-auto border-t border-[var(--border)]/40 pt-2 text-[var(--muted-foreground)]">
          {report}
        </div>
      )}
      {(ruleVersion || referenceVersion) && (
        <details className="mt-2 border-t border-[var(--border)]/40 pt-2 text-[10px] text-[var(--muted-foreground)]">
          <summary className="cursor-pointer">查看评分依据</summary>
          {ruleVersion ? <div className="mt-1 break-all">规则版本：{ruleVersion}</div> : null}
          {referenceVersion ? <div className="mt-1 break-all">参考答案版本：{referenceVersion}</div> : null}
        </details>
      )}
    </div>
  );
}
