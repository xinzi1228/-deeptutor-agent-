"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";

import { fetchAuthStatus } from "@/lib/auth";
import { legacyAdminRedirectFor } from "@/lib/capability-routes";

/**
 * Legacy 能力中心 entry. After the workspace reorganisation the capability
 * center became the admin workspace homepage (`/admin`). This page keeps the
 * old URL working by redirecting to the new location — admins land on the
 * dashboard, other authenticated users are sent back to the learning space.
 * A one-time migration hint is shown while the redirect happens.
 */
export default function CapabilityCenterLegacyPage() {
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    void fetchAuthStatus().then((status) => {
      if (cancelled) return;
      const target =
        status?.authenticated && status.role === "admin"
          ? legacyAdminRedirectFor("/capabilities") ?? "/admin"
          : "/home";
      router.replace(target);
    });
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 bg-[var(--background)] px-6 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-500/10 text-violet-600">
        <Sparkles size={26} strokeWidth={1.6} />
      </span>
      <h1 className="text-lg font-semibold text-[var(--foreground)]">
        能力中心已迁移
      </h1>
      <p className="max-w-sm text-sm leading-6 text-[var(--muted-foreground)]">
        能力中心已成为管理员工作台首页。正在为你跳转到新的工作台…
      </p>
    </div>
  );
}
