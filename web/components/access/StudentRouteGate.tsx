"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";

import { useAuthStatus } from "@/hooks/useAuthStatus";
import { isStudentRouteAllowed } from "@/lib/student-experience";

export default function StudentRouteGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const auth = useAuthStatus();
  const { t } = useTranslation();
  const blocked = !auth.loading && auth.enabled && !auth.isAdmin && !isStudentRouteAllowed(pathname);

  useEffect(() => {
    if (blocked) router.replace("/home");
  }, [blocked, router]);

  if (auth.loading || blocked) {
    return <div className="flex h-full items-center justify-center text-sm text-[var(--muted-foreground)]">{t("正在进入学习空间…")}</div>;
  }
  return children;
}
