"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Tag, PenLine, Wrench } from "lucide-react";

export default function AnnotationPage() {
  const { t } = useTranslation();
  const [mode, setMode] = useState<"basic" | "pro">("basic");

  return (
    <div className="flex h-full flex-col bg-[var(--background)]">
      <header className="flex items-center justify-between border-b border-[var(--border)] px-6 py-3">
        <div className="flex items-center gap-3">
          <Tag className="h-5 w-5 text-[var(--muted-foreground)]" />
          <div>
            <h1 className="text-[15px] font-semibold text-[var(--foreground)]">
              {t("annotation.title")}
            </h1>
            <p className="text-[11px] text-[var(--muted-foreground)]">
              {t("annotation.subtitle")}
            </p>
          </div>
        </div>
        <div className="flex rounded-lg border border-[var(--border)] bg-[var(--card)] p-1">
          <button
            onClick={() => setMode("basic")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === "basic"
                ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <PenLine className="h-3.5 w-3.5" />
            {t("annotation.basicMode")}
          </button>
          <button
            onClick={() => setMode("pro")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === "pro"
                ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <Wrench className="h-3.5 w-3.5" />
            {t("annotation.proMode")}
          </button>
        </div>
      </header>

      <div className="flex-1">
        {mode === "basic" ? (
          <iframe
            src="/annotation_tool.html"
            className="h-full w-full border-0"
            title="Basic Annotation Tool"
            sandbox="allow-scripts allow-same-origin allow-top-navigation allow-popups"
          />
        ) : (
          <iframe
            src="http://localhost:8080"
            className="h-full w-full border-0"
            title="Label Studio"
          />
        )}
      </div>
    </div>
  );
}
