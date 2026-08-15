"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslation } from "react-i18next";
import {
  BookOpenText,
  Bot,
  LayoutDashboard,
  Puzzle,
  ServerCog,
  SlidersHorizontal,
  Users,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import { ADMIN_CENTERS, roleAreaForPath } from "@/lib/capability-routes";
import { useAuthStatus } from "@/hooks/useAuthStatus";

const CENTER_ICONS: Record<string, LucideIcon> = {
  content: BookOpenText,
  teaching: SlidersHorizontal,
  ai: Bot,
  integrations: Puzzle,
  operations: ServerCog,
};

/**
 * Navigation for the admin workspace shell. Shows the five admin centers, the
 * user-management page and the workspace maintenance page to admins, and the
 * teacher workspace to any authenticated user. `roleAreaForPath` decides which
 * group is highlighted, so the same rail serves `/admin/*` and `/teacher`.
 */
export default function AdminNav() {
  const { t } = useTranslation();
  const pathname = usePathname() ?? "";
  const auth = useAuthStatus();
  const isAdmin = !auth.loading && auth.enabled && auth.isAdmin;
  const area = roleAreaForPath(pathname);

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-[var(--border)]/70 bg-[var(--card)]/40">
      <div className="flex items-center gap-2.5 px-5 py-4">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]/10 text-[var(--primary)]">
          <LayoutDashboard size={16} strokeWidth={1.7} />
        </span>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold tracking-tight text-[var(--foreground)]">
            {t("管理员工作台")}
          </p>
          <p className="truncate text-[10.5px] text-[var(--muted-foreground)]">
            {t("Admin Workspace")}
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
        {isAdmin && (
          <>
            <NavItem
              href="/admin"
              label={t("工作台首页")}
              active={pathname === "/admin"}
              icon={LayoutDashboard}
            />
            {ADMIN_CENTERS.map((center) => (
              <NavItem
                key={center.key}
                href={center.href}
                label={center.label}
                active={area === "admin" && adminCenterActive(pathname, center.href)}
                icon={CENTER_ICONS[center.key] ?? Wrench}
              />
            ))}
            <div className="mx-3 my-2 border-t border-[var(--border)]/60" />
            <NavItem
              href="/admin/users"
              label={t("账号管理")}
              active={pathname === "/admin/users"}
              icon={Users}
            />
            <NavItem
              href="/admin/learning-workspace"
              label={t("学习工作区维护")}
              active={pathname === "/admin/learning-workspace"}
              icon={Wrench}
            />
          </>
        )}
        <NavItem
          href="/teacher"
          label={t("教师工作台")}
          active={area === "teacher"}
          icon={Users}
        />
      </nav>

      <div className="border-t border-[var(--border)]/60 p-3">
        <NavItem href="/home" label={t("返回学习空间")} icon={LayoutDashboard} />
      </div>
    </aside>
  );
}

function adminCenterActive(pathname: string, centerHref: string): boolean {
  return pathname === centerHref || pathname.startsWith(`${centerHref}/`);
}

function NavItem({
  href,
  label,
  active,
  icon: Icon,
}: {
  href: string;
  label: string;
  active?: boolean;
  icon: LucideIcon;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors ${
        active
          ? "bg-[var(--primary)]/10 font-medium text-[var(--primary)]"
          : "text-[var(--muted-foreground)] hover:bg-[var(--background)]/60 hover:text-[var(--foreground)]"
      }`}
    >
      <Icon size={15} strokeWidth={1.7} />
      <span className="truncate">{label}</span>
    </Link>
  );
}
