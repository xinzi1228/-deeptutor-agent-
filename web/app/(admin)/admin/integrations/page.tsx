"use client";

import Link from "next/link";
import { Boxes, Plug, Puzzle, Settings2, Wrench } from "lucide-react";

import AdminCenterShell from "@/components/admin/AdminCenterShell";
import { ADMIN_CENTERS } from "@/lib/capability-routes";

const center = ADMIN_CENTERS.find((c) => c.key === "integrations")!;

export default function AdminIntegrationsPage() {
  return (
    <AdminCenterShell
      center={center}
      availability="扩展采用白名单市场：Skill、MCP 与学习插件只能由管理员安装并分配给课程。"
      pending="未审核扩展默认禁用；启用高风险扩展需要二次确认并保留版本与回滚记录。"
      next="在 MCP 服务器、工具与伙伴和智能体设置中完成接入，再为课程分配白名单。"
    >
      <section className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <QuickLink
          href="/settings/mcp"
          title="MCP 服务器"
          description="管理部署共享的外部 MCP 服务器；密钥与凭据不回显。"
          icon={<Plug className="h-4 w-4" />}
        />
        <QuickLink
          href="/settings/tools"
          title="工具"
          description="对话智能体可调用的内置工具启停。"
          icon={<Wrench className="h-4 w-4" />}
        />
        <QuickLink
          href="/settings/agents"
          title="伙伴和智能体"
          description="配置对话中可调用的子智能体。"
          icon={<Puzzle className="h-4 w-4" />}
        />
        <QuickLink
          href="/settings/attachments"
          title="附件预算"
          description="聊天附件的大小上限与文本提取预算。"
          icon={<Boxes className="h-4 w-4" />}
        />
        <QuickLink
          href="/admin/integrations"
          title="Label Studio 专业模式"
          description="专业标注经同源网关连接；学生不接触 Label Studio 账号。"
          icon={<Settings2 className="h-4 w-4" />}
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
