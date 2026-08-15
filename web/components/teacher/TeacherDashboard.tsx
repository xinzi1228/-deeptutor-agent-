"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BookOpenCheck,
  ClipboardList,
  Eye,
  FileText,
  HelpCircle,
  Inbox,
  ShieldCheck,
  Users,
} from "lucide-react";

import { apiFetch, apiUrl } from "@/lib/api";
import {
  getActiveLearningProfile,
  type ActiveLearningProfile,
} from "@/lib/learning-profiles-api";
import { useAuthStatus } from "@/hooks/useAuthStatus";

/**
 * 教师工作台 — read-only workspace for teachers granted access to student
 * learning profiles (teacher_view / impersonate grants issued by an admin).
 *
 * It only shows: assigned student, current task, recent submissions, report,
 * questions and review suggestions — never technical configuration. When no
 * teacher grant is active, sections render as empty states with an explanation
 * instead of pretending there is data.
 */
export default function TeacherDashboard() {
  const auth = useAuthStatus();
  const [active, setActive] = useState<ActiveLearningProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [task, setTask] = useState<Record<string, unknown> | null>(null);
  const [attempts, setAttempts] = useState<unknown[]>([]);
  const [questions, setQuestions] = useState<unknown[]>([]);

  const isTeacherSession =
    active?.mode === "teacher_view" || active?.mode === "impersonate";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const profile = await getActiveLearningProfile();
      setActive(profile);

      const isTeacher =
        profile.mode === "teacher_view" || profile.mode === "impersonate";
      if (isTeacher && profile.unlocked && profile.profile) {
        const [taskRes, attemptsRes, questionsRes] = await Promise.all([
          apiFetch(apiUrl("/api/v1/current-learning-task")).then((res) =>
            res.ok ? res.json() : null,
          ),
          apiFetch(apiUrl("/api/v1/annotation/attempts?limit=10")).then(
            async (res) =>
              res.ok ? ((await res.json()) as { attempts: unknown[] }) : null,
          ),
          apiFetch(apiUrl("/api/v1/question-notebook/entries?limit=10")).then(
            async (res) =>
              res.ok ? ((await res.json()) as { entries?: unknown[] }) : null,
          ),
        ]);
        setTask(taskRes ?? null);
        setAttempts(attemptsRes?.attempts ?? []);
        setQuestions(questionsRes?.entries ?? []);
      } else {
        setTask(null);
        setAttempts([]);
        setQuestions([]);
      }
    } catch {
      setActive(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return (
    <div className="min-h-full bg-[var(--background)] px-6 py-8 [scrollbar-gutter:stable]">
      <div className="mx-auto max-w-5xl">
        <header>
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-600">
            <ShieldCheck className="h-3.5 w-3.5" />
            教师工作台 · 默认只读
          </div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight">
            学生与任务总览
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted-foreground)]">
            仅展示被授权学生的概览、任务、报告、问题、审核建议与测试记录；
            教师不能修改学生原始学习证据。
          </p>
        </header>

        {loading ? (
          <div className="mt-7 grid gap-4 md:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-32 animate-pulse rounded-2xl bg-[var(--muted)]" />
            ))}
          </div>
        ) : !isTeacherSession || !active?.profile ? (
          <EmptyTeacherState
            authenticated={Boolean(auth.authenticated)}
          />
        ) : (
          <>
            <StudentIdentityBanner profile={active} />

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <SectionCard
                title="当前任务"
                icon={<ClipboardList className="h-4 w-4" />}
                empty={!task}
                emptyText="该学生暂未分配当前任务。"
              >
                {task && (
                  <dl className="space-y-1.5 text-sm">
                    <Row label="阶段" value={String(task.stage ?? "—")} />
                    <Row label="模式" value={String(task.mode ?? "—")} />
                    <Row label="题目" value={String(task.task_id ?? "—")} />
                  </dl>
                )}
              </SectionCard>

              <SectionCard
                title="最近提交 · 测试记录"
                icon={<Inbox className="h-4 w-4" />}
                empty={attempts.length === 0}
                emptyText="暂无标注提交记录。"
              >
                <ul className="space-y-2">
                  {attempts.slice(0, 5).map((item, index) => {
                    const attempt = item as Record<string, unknown>;
                    return (
                      <li key={String(attempt.attempt_id ?? index)} className="text-xs">
                        <span className="font-medium text-[var(--foreground)]">
                          {String(attempt.task_id ?? "任务")}
                        </span>
                        <span className="ml-2 text-[var(--muted-foreground)]">
                          {String(attempt.status ?? "已提交")}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </SectionCard>

              <SectionCard
                title="问题"
                icon={<HelpCircle className="h-4 w-4" />}
                empty={questions.length === 0}
                emptyText="暂无错题或疑问记录。"
              >
                <ul className="space-y-2">
                  {questions.slice(0, 5).map((item, index) => {
                    const entry = item as Record<string, unknown>;
                    return (
                      <li key={String(entry.entry_id ?? index)} className="text-xs">
                        {String(entry.question ?? "题目")}
                      </li>
                    );
                  })}
                </ul>
              </SectionCard>

              <SectionCard
                title="审核建议"
                icon={<BookOpenCheck className="h-4 w-4" />}
                empty
                emptyText="评分与审核建议仅基于落盘事实；暂无待你复核的内容。"
              >
                <p className="text-xs text-[var(--muted-foreground)]">
                  单次错误视为 unconfirmed，重复且确认后才成为稳定薄弱点。
                </p>
              </SectionCard>
            </div>

            <SectionCard
              title="成长报告"
              icon={<FileText className="h-4 w-4" />}
              empty
              emptyText="报告仅引用落盘事实；可前往该学生的成长页查看完整报告。"
            >
              <p className="text-xs text-[var(--muted-foreground)]">
                报告与提醒使用可追溯的已确认记录生成。
              </p>
            </SectionCard>
          </>
        )}
      </div>
    </div>
  );
}

function EmptyTeacherState({ authenticated }: { authenticated: boolean }) {
  return (
    <div className="mt-7 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-8 text-center">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--muted)] text-[var(--muted-foreground)]">
        <Eye className="h-6 w-6" strokeWidth={1.6} />
      </span>
      <h2 className="mt-4 text-base font-semibold">当前没有可查看的学生</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--muted-foreground)]">
        {authenticated
          ? "教师需要由管理员在账号管理中为该档案发起教师只读或代管授权，授权后才能在这里看到该学生的任务、提交与报告。"
          : "请先登录后再查看教师工作台。"}
      </p>
    </div>
  );
}

function StudentIdentityBanner({ profile }: { profile: ActiveLearningProfile }) {
  const mode =
    profile.mode === "impersonate" ? "代管（可写受限）" : "教师只读视角";
  return (
    <section className="mt-6 flex flex-wrap items-center gap-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4">
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600">
        <Users className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-[var(--foreground)]">
          正在查看：{profile.profile?.name ?? "学习档案"}
        </p>
        <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
          {mode}
          {profile.read_only ? " · 只读" : ""} · 档案数据与其他学生完全隔离
        </p>
      </div>
    </section>
  );
}

function SectionCard({
  title,
  icon,
  empty,
  emptyText,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  empty?: boolean;
  emptyText: string;
  children?: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-[var(--foreground)]">
        <span className="rounded-lg bg-[var(--muted)] p-1.5">{icon}</span>
        {title}
      </div>
      <div className="mt-3">
        {empty ? (
          <p className="text-xs leading-5 text-[var(--muted-foreground)]">
            {emptyText}
          </p>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-3">
      <dt className="w-16 shrink-0 text-xs text-[var(--muted-foreground)]">
        {label}
      </dt>
      <dd className="truncate text-[13px] text-[var(--foreground)]">{value}</dd>
    </div>
  );
}
