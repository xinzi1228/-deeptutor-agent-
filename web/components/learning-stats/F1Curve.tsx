"use client";

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from "chart.js";
import { Line } from "react-chartjs-2";
import type { F1Point } from "@/lib/learning-stats-api";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

interface F1CurveProps {
  points: F1Point[];
}

export function F1Curve({ points }: F1CurveProps) {
  if (!points.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
        <p className="text-sm text-[var(--muted-foreground)]">暂无数据 — 完成标注任务后出现</p>
      </div>
    );
  }

  const labels = points.map((p) => `${p.task_id}\n${p.difficulty}`);

  const data = {
    labels,
    datasets: [
      {
        label: "F1",
        data: points.map((p) => p.f1),
        borderColor: "rgba(59, 130, 246, 1)",
        backgroundColor: "rgba(59, 130, 246, 0.1)",
        tension: 0.3,
        pointRadius: 5,
        pointBackgroundColor: points.map((p) =>
          p.f1 >= 85 ? "rgba(34,197,94,1)" : "rgba(59,130,246,1)"
        ),
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        ticks: { callback: (v: any) => `${v}%` },
        grid: { color: "rgba(128,128,128,0.1)" },
      },
      x: {
        grid: { display: false },
      },
    },
  };

  return (
    <div className="h-72 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <Line data={data} options={options} />
    </div>
  );
}
