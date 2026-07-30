"use client";

import { useTranslation } from "react-i18next";
import { Tag } from "lucide-react";

export default function AnnotationPage() {
  const { t } = useTranslation();

  return (
    <div className="flex h-full flex-col bg-[var(--background)]">
      <header className="flex items-center gap-3 border-b border-[var(--border)] px-6 py-3">
        <Tag className="h-5 w-5 text-[var(--muted-foreground)]" />
        <div>
          <h1 className="text-[15px] font-semibold text-[var(--foreground)]">
            {t("annotation.title")}
          </h1>
          <p className="text-[11px] text-[var(--muted-foreground)]">
            Draw boxes on the image, copy JSON, paste into chat for scoring
          </p>
        </div>
      </header>
      <div className="flex-1">
        <iframe
          src="/annotation_tool.html"
          className="h-full w-full border-0"
          title="Annotation Tool"
          sandbox="allow-scripts allow-same-origin allow-top-navigation allow-popups"
        />
      </div>
    </div>
  );
}
