"use client";

import { useEffect, useState } from "react";

import { apiFetch, apiUrl } from "@/lib/api";

interface Badge {
  id: string;
  name: string;
  description: string;
  unlocked: boolean;
  unlocked_at: string | null;
}

/** 6-badge achievement wall — unlocked badges lit, locked greyed. */
export function BadgeWall() {
  const [badges, setBadges] = useState<Badge[] | null>(null);

  useEffect(() => {
    apiFetch(apiUrl("/api/v1/achievements"))
      .then((r) => (r.ok ? r.json() : null))
      .then((payload) => setBadges(payload?.badges ?? null))
      .catch(() => setBadges(null));
  }, []);

  if (!badges) return null;

  return (
    <div className="rounded-lg border border-[var(--border)]/60 p-4">
      <h3 className="mb-3 text-[15px] font-medium">成就徽章</h3>
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
        {badges.map((b) => (
          <div
            key={b.id}
            title={b.unlocked ? `${b.name} · ${b.unlocked_at ?? ""}` : b.description}
            className={`flex flex-col items-center gap-1 rounded-lg border p-2 text-center ${
              b.unlocked
                ? "border-[var(--primary)]/40 bg-[var(--primary)]/[0.06]"
                : "border-[var(--border)]/40 opacity-45"
            }`}
          >
            <span className="text-2xl">{b.unlocked ? "🏆" : "🔒"}</span>
            <span className="text-[12px] leading-tight">{b.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
