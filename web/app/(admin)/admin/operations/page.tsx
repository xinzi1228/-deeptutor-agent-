"use client";

import Link from "next/link";
import { Activity, ClipboardCheck, Network, ShieldCheck, Users } from "lucide-react";

import AdminCenterShell from "@/components/admin/AdminCenterShell";
import { ADMIN_CENTERS } from "@/lib/capability-routes";

const center = ADMIN_CENTERS.find((c) => c.key === "operations")!;

export default function AdminOperationsPage() {
  return (
    <AdminCenterShell
      center={center}
      availability="系统健康、初始化进度与脱敏报告可从工作台首页查看；账号角色统一由策略控制。"
      pending="失败任务与待审核项见工作台任务中心；审计仅保存请求与内容哈希。"
      next="核对账号角色与网络设置，定期下载脱敏体检报告并检查失败任务。"
    >
      <section className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <QuickLink
          href="/admin/users"
          title="账号角色"
          description="管理注册账号、角色升降级与档案授权；不能修改自己的角色。"
          icon={<Users className="h-4 w-4" />}
        />
        <QuickLink
          href="/settings/network"
          title="网络与运行"
          description="端口、浏览器 API 地址与 CORS 来源。"
          icon={<Network className="h-4 w-4" />}
        />
        <QuickLink
          href="/admin/operations"
          title="审计与安全"
          description="教师代管逐写审计仅记录请求与 SHA-256 内容哈希；密钥统一脱敏。"
          icon={<ShieldCheck className="h-4 w-4" />}
        />
        <QuickLink
          href="/admin/operations/usability"
          title="用户测试与竞赛证据"
          description="匿名参与者测试运行、确定性报告与证据包导出。"
          icon={<ClipboardCheck className="h-4 w-4" />}
        />
        <QuickLink
          href="/admin"
          title="系统健康"
          description="从工作台首页查看整体健康、初始化进度与高风险项。"
          icon={<Activity className="h-4 w-4" />}
        />
      </section>
    </AdminCenterShell>
  );
}

function QuickLink({
  href,
  title,
  description,
  icon,
}: {
  href: string;
  title: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="group flex flex-col rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:border-[var(--foreground)]/20"
    >
      <span className="rounded-lg bg-[var(--muted)] p-2.5">{icon}</span>
      <span className="mt-3 text-[14px] font-medium text-[var(--foreground)]">
        {title}
      </span>
      <span className="mt-1 text-xs leading-5 text-[var(--muted-foreground)]">
        {description}
      </span>
    </Link>
  );
}
