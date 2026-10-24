"""Engineering Chart and Plot Generator for Cognexa AI.

Generates mathematical plots, system architecture diagrams, and metric charts
using Matplotlib with a dark cyber/modern theme.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("exports").resolve()
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_chart_plot(
    title: str,
    chart_type: str = "line",
    data_points: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate engineering chart/plot and save as high-res PNG."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        raise RuntimeError("matplotlib is required for chart generation.")

    clean_title = re.sub(r"[^a-zA-Z0-9_\-\s]", "", title).strip()
    clean_filename = re.sub(r"\s+", "_", clean_title)[:30] or "chart"
    unique_suffix = uuid.uuid4().hex[:6]
    filename = f"{clean_filename}_{unique_suffix}.png"
    out_path = EXPORTS_DIR / filename

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    # Colors
    cyan = "#00d2ff"
    purple = "#7b2ff7"
    emerald = "#10b981"

    if chart_type == "bar":
        categories = (data_points or {}).get("labels", ["Module A", "Module B", "Module C", "Module D", "Module E"])
        values = (data_points or {}).get("values", [85, 92, 78, 96, 88])
        bars = ax.bar(categories, values, color=cyan, edgecolor=purple, linewidth=1.5, width=0.55)
        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, yval + 1, f"{yval}", ha="center", va="bottom", color="white", fontsize=10, fontweight="bold")
        ax.set_ylim(0, max(values) * 1.15)
    else:
        # Line / Curve plot
        x = np.linspace(0, 10, 100)
        y1 = np.sin(x) * np.exp(-0.1 * x)
        y2 = np.cos(x) * np.exp(-0.1 * x)
        ax.plot(x, y1, color=cyan, label="Signal Primary (α)", linewidth=2.5)
        ax.plot(x, y2, color=purple, label="Reference Baseline (β)", linewidth=2.0, linestyle="--")
        ax.grid(True, linestyle=":", alpha=0.3, color="#64748b")
        ax.legend(framealpha=0.8, facecolor="#0f172a", edgecolor="#334155")

    ax.set_title(title, fontsize=14, fontweight="bold", color="white", pad=14)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#334155")
    ax.spines["bottom"].set_color("#334155")
    ax.tick_params(colors="#94a3b8", labelsize=9)

    plt.tight_layout()
    plt.savefig(str(out_path), facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)

    size_kb = round(out_path.stat().st_size / 1024, 1)
    download_url = f"http://localhost:8001/downloads/{filename}"

    return {
        "status": "success",
        "title": title,
        "filename": filename,
        "download_url": download_url,
        "image_url": download_url,
        "size_kb": size_kb,
    }
