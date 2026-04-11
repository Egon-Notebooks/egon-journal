"""
Cross-signal correlation analysis.

Computes pairwise Pearson correlations across all available daily time series
(journal text metrics, personality scores, physiological measures) and renders:

  1. plot_correlation_matrix  — full n×n heatmap of all available signals.
  2. plot_highlighted_correlations — 2×2 scatter grid for pairs with known
     mental-health interpretations.

Both functions accept a ``signals`` dict mapping short display names to
``list[tuple[date, float]]`` time series.  Only signals with at least
``min_overlap`` days of data are included.
"""

from datetime import date as date_type
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import pearsonr

from egon.plot_style import apply_style

# ---------------------------------------------------------------------------
# Highlighted pairs — (signal_a, signal_b, panel title)
# Only rendered when both signals are present with sufficient overlap.
# ---------------------------------------------------------------------------
MENTAL_HEALTH_PAIRS: list[tuple[str, str, str]] = [
    ("sleep (h)", "sentiment", "Sleep quality & next-day mood"),
    ("HRV", "B5-N", "HRV & neuroticism"),
    ("steps", "B5-E", "Physical activity & extraversion"),
    ("resting HR", "B5-N", "Resting heart rate & neuroticism"),
]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _align_pairwise(
    a: list[tuple[date_type, float]],
    b: list[tuple[date_type, float]],
) -> tuple[list[float], list[float]]:
    """Return (xs, ys) restricted to dates present in both series."""
    b_dict = dict(b)
    xs, ys = [], []
    for d, v in a:
        if d in b_dict:
            xs.append(v)
            ys.append(b_dict[d])
    return xs, ys


def _build_matrix(
    signals: dict[str, list[tuple[date_type, float]]],
    min_overlap: int,
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """
    Return (names, r_matrix, p_matrix).
    Names are sorted alphabetically; cells with too few overlapping days are NaN.
    """
    names = sorted(k for k, v in signals.items() if len(v) >= min_overlap)
    n = len(names)
    r_mat = np.full((n, n), np.nan)
    p_mat = np.full((n, n), np.nan)

    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if i == j:
                r_mat[i, j] = 1.0
                p_mat[i, j] = 0.0
                continue
            xs, ys = _align_pairwise(signals[a], signals[b])
            if len(xs) < min_overlap:
                continue
            r, p = pearsonr(xs, ys)
            r_mat[i, j] = float(r)
            p_mat[i, j] = float(p)

    return names, r_mat, p_mat


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plot_correlation_matrix(
    signals: dict[str, list[tuple[date_type, float]]],
    output_path: Path | None,
    title: str = "Cross-signal correlation matrix",
    min_overlap: int = 10,
) -> "plt.Figure | None":
    """
    Heatmap of all pairwise Pearson correlations.

    * Diverging red–blue colormap, range −1 to +1.
    * Lower triangle only (upper triangle is blank).
    * Cell text is bold when p < 0.05; faded when p ≥ 0.05.
    * Cells with fewer than *min_overlap* shared days show "—".
    """
    if len(signals) < 2:
        raise ValueError("Need at least 2 signals to compute correlations.")

    names, r_mat, p_mat = _build_matrix(signals, min_overlap)
    n = len(names)
    if n < 2:
        raise ValueError("Insufficient overlapping data across signals.")

    apply_style()

    fig, ax = plt.subplots(figsize=(14, 12))

    # Only show lower triangle; upper goes white.
    r_display = np.where(np.triu(np.ones((n, n), dtype=bool), k=1), np.nan, r_mat)
    im = ax.imshow(r_display, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")

    for i in range(n):
        for j in range(i + 1):  # lower triangle including diagonal
            r = r_mat[i, j]
            if np.isnan(r):
                ax.text(j, i, "—", ha="center", va="center", fontsize=7, color="#aaaaaa")
                continue
            p = p_mat[i, j]
            sig = p < 0.05 or i == j
            txt_color = "white" if abs(r) > 0.55 else "#1a1a1a"
            label = "1.0" if i == j else f"{r:+.2f}"
            ax.text(
                j,
                i,
                label,
                ha="center",
                va="center",
                fontsize=7.5,
                color=txt_color,
                alpha=1.0 if sig else 0.38,
                fontweight="bold" if sig and i != j else "normal",
            )

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=8.5)
    ax.set_yticklabels(names, fontsize=8.5)
    ax.set_title(title, pad=12)

    cbar = fig.colorbar(im, ax=ax, fraction=0.030, pad=0.02)
    cbar.set_label("Pearson r", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    fig.text(
        0.5,
        0.005,
        "Bold: p < 0.05 · Faded: p \u2265 0.05 · \u2014: fewer than "
        f"{min_overlap} overlapping days",
        ha="center",
        va="bottom",
        fontsize=7.5,
        color="#6B7A8D",
        style="italic",
    )

    fig.tight_layout(rect=[0, 0.03, 1, 1])
    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return None


def plot_highlighted_correlations(
    signals: dict[str, list[tuple[date_type, float]]],
    output_path: Path | None,
    title: str = "Key cross-signal relationships",
    min_overlap: int = 10,
) -> "plt.Figure | None":
    """
    2×2 scatter grid for the four pairs with known mental-health interpretations.

    Each panel shows: data points, OLS regression line, and r / p annotation.
    Panels for unavailable signal pairs are hidden.
    """
    available = [(a, b, lbl) for a, b, lbl in MENTAL_HEALTH_PAIRS if a in signals and b in signals]
    if not available:
        raise ValueError("None of the highlighted signal pairs are available.")

    apply_style()

    ncols = 2
    nrows = (len(available) + 1) // 2
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 6 * nrows), layout="constrained")
    axes_flat = np.array(axes).flatten()

    _SCATTER_COLOR = "#4C72B0"
    _LINE_COLOR = "#C44E52"

    for idx, (a, b, lbl) in enumerate(available):
        ax = axes_flat[idx]
        xs, ys = _align_pairwise(signals[a], signals[b])

        if len(xs) < min_overlap:
            ax.axis("off")
            ax.text(
                0.5,
                0.5,
                f"Insufficient data\n({len(xs)} days overlap)",
                ha="center",
                va="center",
                transform=ax.transAxes,
                color="#aaaaaa",
                fontsize=10,
            )
            continue

        r, p = pearsonr(xs, ys)
        xs_arr = np.array(xs, dtype=float)
        ys_arr = np.array(ys, dtype=float)

        ax.scatter(xs_arr, ys_arr, alpha=0.55, s=22, color=_SCATTER_COLOR, zorder=3)

        m, c = np.polyfit(xs_arr, ys_arr, 1)
        x_line = np.linspace(xs_arr.min(), xs_arr.max(), 200)
        ax.plot(x_line, m * x_line + c, color=_LINE_COLOR, linewidth=1.5, alpha=0.85)

        p_str = "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
        ax.text(
            0.04,
            0.96,
            f"r = {r:+.2f},  {p_str}  (n = {len(xs)})",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9.5,
            color="#2D2D2D",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=3),
        )

        ax.set_xlabel(a, fontsize=10)
        ax.set_ylabel(b, fontsize=10)
        ax.set_title(lbl, fontsize=11)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    # Hide unused subplot slots
    for idx in range(len(available), len(axes_flat)):
        axes_flat[idx].axis("off")

    fig.suptitle(title, fontsize=13)

    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return None
