"use client";

import { usePathname } from "next/navigation";
import { ShieldAlert } from "lucide-react";
import Link from "next/link";

import { roleAreaForPath } from "@/lib/capability-routes";
import { useAuthStatus } from "@/hooks/useAuthStatus";
import { useViewIdentity } from "@/lib/view-identity";

/**
 * Route-level role gate for the admin workspace shell.
 *
 * The backend is the final authority for every API call (REST, WebSocket,
 * tools, Store). This component only mirrors that policy for navigation and
 * direct-URL access:
 *   • `/admin/*` — admin role required, otherwise an explicit 403 page.
 *   • `/teacher` — authenticated staff view required; student identity
 *     (view-identity) is rejected with an explicit 403 page.
 *
 * It never redirects to a seemingly-empty config page: unauthorized access
 * gets a clear "拒绝访问" screen instead.
 */
export default function RoleRouteGate({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const auth = useAuthStatus();
  const area = roleAreaForPath(pathname);
  const { studentMode } = useViewIdentity({
    authEnabled: auth.enabled,
    isAdmin: auth.isAdmin,
  });

  if (auth.loading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--muted-foreground)]">
        …
      </div>
    );
  }

  if (area === "admin" && (!auth.authenticated || !auth.isAdmin)) {
    return <ForbiddenScreen />;
  }
  if (area === "teacher" && (!auth.authenticated || studentMode)) {
    return <ForbiddenScreen />;
  }

  return children;
}

function ForbiddenScreen() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 bg-[var(--background)] px-6 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-500">
        <ShieldAlert size={26} strokeWidth={1.6} />
      </span>
      <h1 className="text-lg font-semibold text-[var(--foreground)]">
        拒绝访问
      </h1>
      <p className="max-w-sm text-sm leading-6 text-[var(--muted-foreground)]">
        当前账号没有访问该工作区的权限。教师与管理员权限由系统统一策略控制；
        若你确认需要访问，请联系管理员在账号管理中授权。
      </p>
      <Link
        href="/home"
        className="mt-2 rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
      >
        返回学习空间
      </Link>
    </div>
  );
}
