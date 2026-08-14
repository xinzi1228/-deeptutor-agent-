"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useSettings } from "@/components/settings/SettingsContext";
import { statusDotClass } from "@/components/settings/shared";
import { apiFetch, apiUrl } from "@/lib/api";

type SecretSecurityStatus = {
  backend: string;
  plaintext_count: number;
  reference_count: number;
  configured_count: number;
  migration_required: boolean;
};

/**
 * Resident status module on the settings hub — the old `/settings/status` page
 * demoted to an always-visible strip. Reads the runtime `/system/status`
 * snapshot (available to every user, unlike the editable catalog), so it
 * reflects what is actually running rather than the draft.
 *
 * Compact, left-aligned, hairline-separated items — no stretched grid or
 * uppercase eyebrow (CJK reads badly with letter-spacing).
 */
export default function SettingsStatusPanel() {
  const { t } = useTranslation();
  const { status, catalogEditable } = useSettings();
  const [secretStatus, setSecretStatus] = useState<SecretSecurityStatus | null>(
    null,
  );
  const [migrating, setMigrating] = useState(false);

  useEffect(() => {
    if (!catalogEditable) return;
    let active = true;
    void apiFetch(apiUrl("/api/v1/settings/catalog/security"))
      .then(async (response) =>
        response.ok
          ? ((await response.json()) as SecretSecurityStatus)
          : null,
      )
      .then((payload) => {
        if (active && payload) setSecretStatus(payload);
      });
    return () => {
      active = false;
    };
  }, [catalogEditable]);

  const migrateSecrets = useCallback(async () => {
    setMigrating(true);
    try {
      const response = await apiFetch(
        apiUrl("/api/v1/settings/catalog/security/migrate"),
        { method: "POST" },
      );
      if (response.ok) {
        setSecretStatus((await response.json()) as SecretSecurityStatus);
      }
    } finally {
      setMigrating(false);
    }
  }, []);

  const items = [
    {
      key: "backend",
      name: t("Backend"),
      configured: status?.backend.status === "online",
      hasError: false,
      value: status
        ? status.backend.status === "online"
          ? t("Online")
          : t("Checking")
        : t("Checking"),
    },
    {
      key: "llm",
      name: t("LLM"),
      configured: Boolean(status?.llm.model),
      hasError: Boolean(status?.llm.error),
      value: status?.llm.model || t("Not set"),
    },
    {
      key: "embedding",
      name: t("Embedding"),
      configured: Boolean(status?.embeddings.model),
      hasError: Boolean(status?.embeddings.error),
      value: status?.embeddings.model || t("Not set"),
    },
    {
      key: "search",
      name: t("Search"),
      configured: Boolean(status?.search.provider),
      hasError: Boolean(status?.search.error),
      value: status?.search.provider || t("Not set"),
    },
  ];

  return (
    <section
      data-tour="tour-status"
      className="flex flex-wrap items-center gap-x-5 gap-y-2.5 rounded-2xl border border-[var(--border)]/70 bg-[var(--card)]/50 px-5 py-3.5"
    >
      {items.map((item, i) => (
        <Fragment key={item.key}>
          {i > 0 && (
            <span
              aria-hidden
              className="hidden h-7 w-px shrink-0 bg-[var(--border)]/70 sm:block"
            />
          )}
          <div className="flex items-center gap-2.5">
            <span
              className={`h-2 w-2 shrink-0 rounded-full ${statusDotClass(
                item.configured,
                item.hasError,
              )}`}
            />
            <div className="flex items-baseline gap-2">
              <span className="text-[13px] font-medium leading-none tracking-tight text-[var(--foreground)]">
                {item.name}
              </span>
              <span
                className="max-w-[220px] truncate text-[12px] leading-none text-[var(--muted-foreground)]"
                title={item.value}
              >
                {item.value}
              </span>
            </div>
          </div>
        </Fragment>
      ))}
      {catalogEditable && secretStatus && (
        <>
          <span
            aria-hidden
            className="hidden h-7 w-px shrink-0 bg-[var(--border)]/70 sm:block"
          />
          <div className="flex items-center gap-2.5">
            <span
              className={`h-2 w-2 shrink-0 rounded-full ${
                secretStatus.migration_required ? "bg-amber-500" : "bg-emerald-500"
              }`}
            />
            <div className="flex items-center gap-2 text-[12px]">
              <span className="font-medium text-[var(--foreground)]">
                {t("密钥安全")}
              </span>
              <span className="text-[var(--muted-foreground)]">
                {secretStatus.migration_required
                  ? t("发现 {{count}} 个旧版明文密钥", {
                      count: secretStatus.plaintext_count,
                    })
                  : t("已安全存储")}
              </span>
              {secretStatus.migration_required && (
                <button
                  type="button"
                  disabled={migrating}
                  onClick={() => void migrateSecrets()}
                  className="rounded-md border border-amber-500/40 px-2 py-1 text-amber-700 transition-colors hover:bg-amber-500/10 disabled:opacity-50 dark:text-amber-300"
                >
                  {migrating ? t("迁移中…") : t("立即迁移")}
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
