"use client";

import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";
import { Radar } from "react-chartjs-2";
import type { RadarDimension } from "@/lib/learning-stats-api";

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

interface RadarChartProps {
  dimensions: RadarDimension[];
}

export function RadarChart({ dimensions }: RadarChartProps) {
  if (!dimensions.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
        <p className="text-sm text-[var(--muted-foreground)]">暂无数据 — 完成标注练习后出现</p>
      </div>
    );
  }

  const data = {
    labels: dimensions.map((d) => d.name),
    datasets: [
      {
        label: "当前水平",
        data: dimensions.map((d) => d.score),
        backgroundColor: "rgba(59, 130, 246, 0.15)",
        borderColor: "rgba(59, 130, 246, 0.8)",
        borderWidth: 2,
        pointBackgroundColor: "rgba(59, 130, 246, 1)",
        pointBorderColor: "#fff",
        pointHoverRadius: 6,
      },
      {
        label: "五级标准 (≥85%)",
        data: dimensions.map(() => 85),
        backgroundColor: "rgba(34, 197, 94, 0.05)",
        borderColor: "rgba(34, 197, 94, 0.3)",
        borderWidth: 1.5,
        borderDash: [6, 4],
        pointRadius: 0,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        beginAtZero: true,
        max: 100,
        ticks: { stepSize: 20, backdropColor: "transparent" },
        grid: { color: "rgba(128,128,128,0.15)" },
        angleLines: { color: "rgba(128,128,128,0.15)" },
        pointLabels: { font: { size: 12 } },
      },
    },
    plugins: {
      legend: { position: "bottom" as const },
    },
  };

  return (
    <div className="flex h-80 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <Radar data={data} options={options} />
    </div>
  );
}
