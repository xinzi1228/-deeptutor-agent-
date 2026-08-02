"""Chart card contract builders + scorecard PNG rendering.

Tools emit deterministic chart data via ``ToolResult.metadata.chart``. The
frontend ``ChatChartCard`` renders it (Chart.js / cytoscape / <img>). The
scorecard uses matplotlib so the grade card is a portable PNG the student can
screenshot into a report.
"""

from __future__ import annotations

from pathlib import Path


def radar_chart(labels: list[str], values: list[float]) -> dict:
    """Five-dimension ability radar contract."""
    return {"type": "radar", "data": {"labels": list(labels), "values": [float(v) for v in values]}}


def progress_chart(*, completed: int, total: int, modules: list[dict] | None = None) -> dict:
    """Learning progress / plan-vs-actual contract."""
    return {
        "type": "progress",
        "data": {
            "completed": int(completed),
            "total": int(total),
            "modules": modules or [],
        },
    }


def build_scorecard_chart(*, f1: float, precision: float, recall: float, passed: bool) -> dict:
    """Exercise scorecard contract (rendered as matplotlib PNG, not Chart.js)."""
    return {
        "type": "scorecard",
        "data": {
            "f1": float(f1),
            "precision": float(precision),
            "recall": float(recall),
            "passed": bool(passed),
        },
    }


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


async def render_scorecard_png(
    *,
    f1: float,
    precision: float,
    recall: float,
    passed: bool,
    feedback: list[str],
    out_dir: Path,
) -> Path:
    """Render a scorecard as a PNG via matplotlib. Never raises on chart errors."""
    import asyncio

    def _draw() -> Path:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(7, 3), dpi=120)
        color = "#22c55e" if passed else "#ef4444"
        rgb = _hex_to_rgb(color)

        ax.barh([0], [f1], color=color, alpha=0.85, height=0.55)
        ax.barh([0], [1], color="#e5e7eb", height=0.55)
        ax.text(
            f1 / 2,
            0,
            f"F1 = {f1:.2f}",
            ha="center",
            va="center",
            color="white",
            fontsize=13,
            fontweight="bold",
        )
        ax.set_yticks([])
        ax.set_xlim(0, 1)

        labels = ["Precision", "Recall"]
        vals = [precision, recall]
        bars = ax.barh([1, 2], vals, color="#3b82f6", alpha=0.85, height=0.5)
        for b, v in zip(bars, vals):
            ax.text(
                b.get_width() + 0.02,
                b.get_y() + b.get_height() / 2,
                f"{v:.2f}",
                va="center",
                fontsize=10,
            )
        ax.set_yticks([1, 2])
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlim(0, 1.15)

        ax.text(0, -0.8, " · ".join(feedback[:3]), fontsize=7, color="#6b7280")

        ax.set_title(
            "练习成绩单" + (" ✓ 达标" if passed else " ✗ 待加强"), fontsize=12, color=color
        )
        ax.spines[["top", "right"]].set_visible(False)

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "scorecard.png"
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return path

    return await asyncio.to_thread(_draw)


__all__ = ["build_scorecard_chart", "progress_chart", "radar_chart", "render_scorecard_png"]
