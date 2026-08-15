"use client";

import Link from "next/link";
import { GraduationCap, ScrollText, Users } from "lucide-react";

import AdminCenterShell from "@/components/admin/AdminCenterShell";
import { ADMIN_CENTERS } from "@/lib/capability-routes";

const center = ADMIN_CENTERS.find((c) => c.key === "teaching")!;

export default function AdminTeachingPage() {
  return (
    <AdminCenterShell
      center={center}
      availability="课程、场景与能力图谱按当前学习档案结构展示；教学标注与评分规则已启用。"
      pending="任务分配与教师授权需要为具体学生档案配置，并保留 30 分钟代管审计。"
      next="进入账号管理为学生分配任务与教师授权；评分规则与参考答案以审核发布版本为准。"
    >
      <section className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <QuickLink
          href="/admin/users"
          title="任务分配与教师授权"
          description="为学生账号分配学习任务，并为教师授予只读视角与限时代管权限。"
          icon={<Users className="h-4 w-4" />}
        />
        <QuickLink
          href="/admin/learning-workspace"
          title="学习工作区维护"
          description="查看学习展示与教学资产版本；修复展示或按诊断重建课程计划。"
          icon={<GraduationCap className="h-4 w-4" />}
        />
        <QuickLink
          href="/settings"
          title="课程与场景配置"
          description="基础设置与高级设置分层维护；密钥输入与原始 JSON 默认折叠。"
          icon={<ScrollText className="h-4 w-4" />}
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
