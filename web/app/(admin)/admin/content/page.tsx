"use client";

import Link from "next/link";
import { FileText, Inbox } from "lucide-react";

import AdminCenterShell from "@/components/admin/AdminCenterShell";
import AdminTaskCenter from "@/components/admin/AdminTaskCenter";
import { QuickKnowledgeImport } from "@/components/capabilities/QuickKnowledgeImport";
import { ADMIN_CENTERS } from "@/lib/capability-routes";

const center = ADMIN_CENTERS.find((c) => c.key === "content")!;

export default function AdminContentPage() {
  return (
    <AdminCenterShell
      center={center}
      availability="知识库与文档解析引擎可用；教材转换任务在统一任务中心跟踪。"
      pending="待人工审核的内容修订与导入失败任务见下方任务中心。"
      next="先在高级设置中确认文档解析引擎，再导入教材并人工审核候选内容。"
    >
      <section className="mt-8">
        <QuickKnowledgeImport onImported={() => undefined} />
      </section>

      <div className="mt-8">
        <AdminTaskCenter />
      </div>

      <section className="mt-8 grid gap-3 sm:grid-cols-2">
        <QuickLink
          href="/settings/document-parsing"
          title="文档解析引擎"
          description="选择文本 / Docling / MarkItDown / MinerU 等解析器，管理解析任务与模型下载。"
          icon={<FileText className="h-4 w-4" />}
        />
        <QuickLink
          href="/admin/content"
          title="内容来源与审核"
          description="查看来源目录、待审修订与标准冲突；AI 只能写入候选修订。"
          icon={<Inbox className="h-4 w-4" />}
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
      className="group flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:border-[var(--foreground)]/20"
    >
      <span className="mt-0.5 rounded-lg bg-[var(--muted)] p-2">{icon}</span>
      <span className="min-w-0">
        <span className="block text-[14px] font-medium text-[var(--foreground)]">
          {title}
        </span>
        <span className="mt-0.5 block text-xs leading-5 text-[var(--muted-foreground)]">
          {description}
        </span>
      </span>
    </Link>
  );
}
