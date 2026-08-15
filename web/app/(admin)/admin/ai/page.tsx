"use client";

import { useEffect, useState } from "react";
import { Bot, Cpu, Database, ImageIcon, Search, Sparkles, Volume2 } from "lucide-react";

import AdminCenterShell from "@/components/admin/AdminCenterShell";
import { ADMIN_CENTERS } from "@/lib/capability-routes";
import { apiFetch, apiUrl } from "@/lib/api";
import { SettingsProvider, useSettings } from "@/components/settings/SettingsContext";
import {
  serviceReadiness,
  type ServiceReadiness,
} from "@/components/settings/SettingsContext";
import Link from "next/link";

const center = ADMIN_CENTERS.find((c) => c.key === "ai")!;

type ServiceLeaf = {
  key: string;
  href: string;
  label: string;
  icon: typeof Bot;
  service: "llm" | "embedding" | "search" | "tts" | "stt" | "imagegen" | "videogen";
};

const SERVICES: ServiceLeaf[] = [
  { key: "llm", href: "/settings/llm", label: "对话模型", icon: Bot, service: "llm" },
  { key: "embedding", href: "/settings/embedding", label: "嵌入模型", icon: Database, service: "embedding" },
  { key: "imagegen", href: "/settings/image", label: "文生图", icon: ImageIcon, service: "imagegen" },
  { key: "search", href: "/settings/search", label: "联网搜索", icon: Search, service: "search" },
  { key: "tts", href: "/settings/tts", label: "语音合成", icon: Volume2, service: "tts" },
];

export default function AdminAIPage() {
  return (
    <SettingsProvider>
      <AdminAIContent />
    </SettingsProvider>
  );
}

function AdminAIContent() {
  const { catalog, catalogEditable, diagnosticsResults } = useSettings();
  const [embeddingReady, setEmbeddingReady] = useState(false);

  useEffect(() => {
    void apiFetch(apiUrl("/api/v1/capability-center/overview"))
      .then(async (res) => (res.ok ? await res.json() : null))
      .then((data) => {
        const knowledge = data?.cards?.find((c: { key: string }) => c.key === "knowledge");
        setEmbeddingReady(Boolean(knowledge && knowledge.status !== "fault"));
      })
      .catch(() => undefined);
  }, []);

  const readiness = (service: ServiceLeaf["service"]): ServiceReadiness =>
    catalogEditable === true
      ? serviceReadiness(catalog, service, diagnosticsResults)
      : "not_configured";

  return (
    <AdminCenterShell
      center={center}
      availability={
        catalogEditable === true
          ? "模型目录可编辑；各服务连接与测试状态见下方卡片。"
          : "当前环境不可编辑模型目录，请通过管理员配置。"
      }
      pending="Embedding 需通过五项验收后才可索引真实资料；生图可用性以真实生成测试为准。"
      next="逐项配置并连接测试对话、嵌入与生图模型；通过后再导入并索引学习资料。"
    >
      <section className="mt-8">
        <h2 className="text-sm font-semibold text-[var(--muted-foreground)]">
          模型服务状态
        </h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {SERVICES.map((service) => {
            const Icon = service.icon;
            const state = readiness(service.service);
            const tone =
              state === "passed"
                ? "bg-emerald-500/10 text-emerald-600"
                : state === "failed"
                  ? "bg-rose-500/10 text-rose-600"
                  : "bg-[var(--muted)] text-[var(--muted-foreground)]";
            const label =
              state === "passed"
                ? "通过"
                : state === "failed"
                  ? "失败"
                  : state === "untested"
                    ? "已配置"
                    : "未配置";
            return (
              <Link
                key={service.key}
                href={service.href}
                className="group flex flex-col rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:border-[var(--foreground)]/20"
              >
                <div className="flex items-start justify-between">
                  <span className="rounded-lg bg-[var(--muted)] p-2">
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${tone}`}>
                    {label}
                  </span>
                </div>
                <span className="mt-3 text-[13px] font-medium text-[var(--foreground)]">
                  {service.label}
                </span>
              </Link>
            );
          })}
        </div>
        <p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
          <Cpu className="h-3.5 w-3.5" />
          嵌入模型：{embeddingReady ? "知识库可索引" : "资料未索引 / 生图不可用，不伪造就绪状态"}
        </p>
      </section>

      <section className="mt-8 grid gap-3 sm:grid-cols-2">
        <QuickLink href="/settings/capabilities" title="能力与运行时旋钮" description="配置各能力的 LLM 参数与运行时预算。" icon={<Sparkles className="h-4 w-4" />} />
        <QuickLink href="/settings/memory" title="记忆与引用策略" description="分块、预算、去重与引用规则。" icon={<Database className="h-4 w-4" />} />
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
