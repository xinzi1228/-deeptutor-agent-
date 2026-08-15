"use client";

import Link from "next/link";
import { ArrowLeft, ChevronRight } from "lucide-react";

import {
  ADMIN_CENTERS,
  type AdminCenterInfo,
  adminCenterForPath,
} from "@/lib/capability-routes";
import {
  categoriesForCenter,
  type SettingsCategory,
} from "@/lib/settings-nav";
import { usePathname } from "next/navigation";

/**
 * Shared scaffold for the five admin centers. Every center opens with a
 * "现在是否可用 / 有什么待处理 / 下一步是什么" block, then lists the settings
 * categories that belong to that center (each linking to its settings page).
 * Center pages pass center-specific live data as children.
 */
export default function AdminCenterShell({
  center,
  availability,
  pending,
  next,
  children,
}: {
  center: AdminCenterInfo;
  availability: string;
  pending: string;
  next: string;
  children?: React.ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const current = adminCenterForPath(pathname) ?? center;
  const categories = categoriesForCenter(center.key);

  return (
    <div className="min-h-full bg-[var(--background)] px-6 py-8 [scrollbar-gutter:stable]">
      <div className="mx-auto max-w-5xl">
        <Link
          href="/admin"
          className="mb-5 inline-flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回工作台
        </Link>

        <header className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
              {current.label}
            </p>
            <h1 className="mt-1 font-serif text-3xl font-semibold tracking-tight">
              {center.label}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted-foreground)]">
              {center.blurb}
            </p>
          </div>
        </header>

        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <StatusLine label="现在是否可用" text={availability} tone="emerald" />
          <StatusLine label="有什么待处理" text={pending} tone="amber" />
          <StatusLine label="下一步是什么" text={next} tone="sky" />
        </div>

        {children}

        {categories.length > 0 && (
          <section className="mt-8">
            <h2 className="text-sm font-semibold text-[var(--muted-foreground)]">
              本中心相关设置
            </h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {categories.map((category) => (
                <CategoryCard key={category.key} category={category} />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

function StatusLine({
  label,
  text,
  tone,
}: {
  label: string;
  text: string;
  tone: "emerald" | "amber" | "sky";
}) {
  const tones: Record<string, string> = {
    emerald: "bg-emerald-500/10 text-emerald-600",
    amber: "bg-amber-500/10 text-amber-600",
    sky: "bg-sky-500/10 text-sky-600",
  };
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <span className={`inline-flex rounded-full px-2 py-0.5 text-[10.5px] font-medium ${tones[tone]}`}>
        {label}
      </span>
      <p className="mt-2 text-[13px] leading-5 text-[var(--muted-foreground)]">
        {text}
      </p>
    </div>
  );
}

function CategoryCard({ category }: { category: SettingsCategory }) {
  const Icon = category.icon;
  return (
    <Link
      href={category.href}
      className="group flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:border-[var(--foreground)]/20"
    >
      <span className="rounded-lg bg-[var(--muted)] p-2">
        <Icon className="h-4 w-4" strokeWidth={1.7} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[14px] font-medium text-[var(--foreground)]">
          {category.label.zh}
        </span>
        <span className="block truncate text-xs text-[var(--muted-foreground)]">
          {category.blurb.zh}
        </span>
      </span>
      <ChevronRight
        className="shrink-0 text-[var(--muted-foreground)]/40 transition-transform group-hover:translate-x-0.5"
        size={16}
      />
    </Link>
  );
}

export { ADMIN_CENTERS };
