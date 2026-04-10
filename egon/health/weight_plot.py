"""
Weight (BodyMass) report plot, with optional LeanBodyMass subplot.
"""

from datetime import date as date_type
from pathlib import Path
from statistics import mean

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.plot_style import apply_style


def plot_weight(
    data: list[tuple[date_type, float]],
    output_path: Path | None,
    title: str = "Weight",
    unit: str = "kg",
    lean_data: list[tuple[date_type, float]] | None = None,
    target_body_mass: float | None = None,
    target_lean_body_mass: float | None = None,
) -> "plt.Figure | None":
    """
    Plot daily mean body weight over time and save to *output_path*.

    When *lean_data* is provided the figure has two stacked subplots —
    body mass (top) and lean body mass (bottom) — each with their own
    average and optional goal line.  Without lean data a single panel is
    used.
    """
    if not data:
        raise ValueError("No weight data found — nothing to plot.")

    apply_style()
    dates, values = zip(*data)
    avg = mean(values)

    if lean_data:
        fig, (ax, ax_lean) = plt.subplots(2, 1, figsize=(14, 7), sharex=True, layout="constrained")
    else:
        fig, ax = plt.subplots(figsize=(14, 4))

    # --- Body mass ---
    ax.plot(dates, values, color="#4C72B0", linewidth=1.5, alpha=0.9)
    ax.scatter(dates, values, color="#4C72B0", s=18, zorder=3, alpha=0.7)
    ax.axhline(
        avg,
        color="#4C72B0",
        linewidth=0.9,
        linestyle="--",
        alpha=0.5,
        label=f"avg {avg:.1f} {unit}",
    )
    if target_body_mass is not None:
        ax.axhline(
            target_body_mass,
            color="#4C72B0",
            linewidth=0.9,
            linestyle=":",
            alpha=0.7,
            label=f"goal {target_body_mass:.1f} {unit}",
        )
    ax.set_ylabel(f"body mass ({unit})")
    ax.set_title(title)
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # --- Lean body mass (when available) ---
    if lean_data:
        lean_dates, lean_values = zip(*lean_data)
        lean_avg = mean(lean_values)
        ax_lean.plot(lean_dates, lean_values, color="#DD8452", linewidth=1.5, alpha=0.9)
        ax_lean.scatter(lean_dates, lean_values, color="#DD8452", s=18, zorder=3, alpha=0.7)
        ax_lean.axhline(
            lean_avg,
            color="#DD8452",
            linewidth=0.9,
            linestyle="--",
            alpha=0.5,
            label=f"avg {lean_avg:.1f} {unit}",
        )
        if target_lean_body_mass is not None:
            ax_lean.axhline(
                target_lean_body_mass,
                color="#DD8452",
                linewidth=0.9,
                linestyle=":",
                alpha=0.7,
                label=f"goal {target_lean_body_mass:.1f} {unit}",
            )
        ax_lean.set_ylabel(f"lean body mass ({unit})")
        ax_lean.legend(frameon=False)
        ax_lean.spines["top"].set_visible(False)
        ax_lean.spines["right"].set_visible(False)

        locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
        formatter = mdates.ConciseDateFormatter(locator)
        ax_lean.xaxis.set_major_locator(locator)
        ax_lean.xaxis.set_major_formatter(formatter)
        fig.autofmt_xdate(rotation=30)
    else:
        locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        fig.autofmt_xdate(rotation=30)
        fig.tight_layout()

    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
    return None
