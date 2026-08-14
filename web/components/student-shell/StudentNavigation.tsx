"use client";

import Link from "next/link";
import { BookOpen, Settings, Tag, TrendingUp, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import { STUDENT_NAVIGATION } from "@/lib/student-experience";
import { Tooltip } from "@/components/ui/Tooltip";

const ICONS: Record<(typeof STUDENT_NAVIGATION)[number]["label"], LucideIcon> = {
  学习: BookOpen,
  实训: Tag,
  成长: TrendingUp,
  我的: Settings,
};

export default function StudentNavigation({
  collapsed,
  pathname,
  onLearningClick,
}: {
  collapsed: boolean;
  pathname: string;
  onLearningClick?: (event: React.MouseEvent) => void;
}) {
  const { t } = useTranslation();
  if (collapsed) {
    return (
      <nav aria-label={t("学生主导航")} className="mt-1 flex w-full flex-col items-center gap-1 px-1.5">
        {STUDENT_NAVIGATION.map((item) => {
          const Icon = ICONS[item.label];
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Tooltip key={item.href} label={item.label} side="right">
              <Link
                href={item.href}
                onClick={item.href === "/home" ? onLearningClick : undefined}
                aria-label={item.label}
                className={`relative flex h-9 w-9 items-center justify-center rounded-xl transition-all duration-150 ${
                  active
                    ? "bg-[var(--accent)] text-[var(--foreground)] shadow-sm"
                    : "text-[var(--foreground)]/85 hover:bg-[var(--background)]/60"
                }`}
              >
                <Icon size={18} strokeWidth={active ? 2 : 1.6} />
              </Link>
            </Tooltip>
          );
        })}
      </nav>
    );
  }

  return (
    <nav aria-label={t("学生主导航")} className="px-2 pt-1">
      <div className="space-y-px">
        {STUDENT_NAVIGATION.map((item) => {
          const Icon = ICONS[item.label];
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={item.href === "/home" ? onLearningClick : undefined}
              className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] transition-colors ${
                active
                  ? "bg-[var(--accent)] font-medium text-[var(--foreground)]"
                  : "text-[var(--foreground)]/85 hover:bg-[var(--background)]/60"
              }`}
            >
              <Icon size={16} strokeWidth={active ? 1.9 : 1.5} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
