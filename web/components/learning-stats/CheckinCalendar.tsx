"use client";

import { useEffect, useState } from "react";

import { apiFetch, apiUrl } from "@/lib/api";

interface CheckinData {
  dates: string[];
  total_days: number;
  streak: number;
  today_checked: boolean;
}

const WEEKS = 12;

function isoDate(offsetDays: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

/** GitHub-contribution-style check-in heatmap (last ~12 weeks) + streak. */
export function CheckinCalendar() {
  const [data, setData] = useState<CheckinData | null>(null);

  useEffect(() => {
    apiFetch(apiUrl("/api/v1/achievements"))
      .then((r) => (r.ok ? r.json() : null))
      .then((payload) => setData(payload?.checkin ?? null))
      .catch(() => setData(null));
  }, []);

  if (!data) return null;

  const checked = new Set(data.dates);
  const todayIso = isoDate(0);
  const cols: string[][] = [];
  for (let w = 0; w < WEEKS; w++) {
    const col: string[] = [];
    for (let d = 0; d < 7; d++) {
      col.push(isoDate(-(w * 7 + d)));
    }
    cols.push(col);
  }

  return (
    <div className="rounded-lg border border-[var(--border)]/60 p-4">
      <div className="mb-2 flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-[15px] font-medium">打卡日历</h3>
        <div className="text-[13px] text-[var(--muted-foreground)]">
          🔥 连续打卡 {data.streak} 天 · 累计 {data.total_days} 天
          {data.today_checked ? " · ✅ 今日已打卡" : ""}
        </div>
      </div>
      <div className="flex gap-1 overflow-x-auto pb-1">
        {cols.map((col, ci) => (
          <div key={ci} className="flex flex-col gap-1">
            {col.map((date) => (
              <div
                key={date}
                title={date}
                className={`h-3 w-3 rounded-[3px] ${
                  date === todayIso
                    ? "bg-[var(--primary)] ring-1 ring-[var(--primary)]"
                    : checked.has(date)
                      ? "bg-[var(--primary)]/60"
                      : "bg-[var(--muted)]/40"
                }`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
