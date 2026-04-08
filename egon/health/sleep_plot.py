"""
Sleep report plot — time asleep per night with optional sleep onset subplot.

Sleep onset regularity is a strong predictor of mental health: irregular
bedtimes are associated with depression, anxiety, and poor mood.
"""
from datetime import date as date_type
from pathlib import Path
from statistics import mean, stdev

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

from egon.plot_style import apply_style

_ONSET_REF_HOUR = 18  # must match sleep.py


def _onset_label(hours_after_6pm: float, _pos=None) -> str:
    """Convert hours-after-18:00 back to a HH:MM clock string."""
    total_minutes = round((hours_after_6pm + _ONSET_REF_HOUR) * 60) % (24 * 60)
    h, m = divmod(total_minutes, 60)
    return f"{h:02d}:{m:02d}"


def _fmt_std(std_hours: float) -> str:
    """Format a std dev in hours as 'Xh Ym' or 'Ym' for display."""
    total_minutes = round(std_hours * 60)
    h, m = divmod(total_minutes, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def plot_sleep(
    data: list[tuple[date_type, float]],
    output_path: Path,
    title: str = "Sleep",
    onset_data: list[tuple[date_type, float]] | None = None,
) -> None:
    """
    Plot nightly hours asleep as a bar chart and save to *output_path*.

    If *onset_data* is provided (list of (date, hours_after_18:00) tuples),
    a second subplot is added below showing:
      - individual onset times (scatter + line)
      - a dashed average onset line
      - a ±1σ shaded band showing onset variability
      - a σ annotation in the corner (sleep onset rhythmicity indicator)
    """
    if not data:
        raise ValueError("No sleep data found — nothing to plot.")

    apply_style()
    dates, hours = zip(*data)

    n_rows = 2 if onset_data else 1
    fig, axes = plt.subplots(
        n_rows, 1,
        figsize=(14, 4 * n_rows),
        sharex=True,
        layout="constrained",
    )
    if n_rows == 1:
        axes = [axes]

    # --- Top panel: hours asleep ---
    ax_sleep = axes[0]
    ax_sleep.bar(dates, hours, width=0.8, color="#8172B3", alpha=0.85)
    ax_sleep.axhline(7, color="grey", linewidth=0.8, linestyle="--", alpha=0.5)
    ax_sleep.axhline(9, color="grey", linewidth=0.8, linestyle="--", alpha=0.5)
    ax_sleep.set_ylabel("hours asleep")
    ax_sleep.set_title(title)
    ax_sleep.spines["top"].set_visible(False)
    ax_sleep.spines["right"].set_visible(False)

    # --- Bottom panel: sleep onset ---
    if onset_data:
        onset_dates, onset_values = zip(*onset_data)
        avg = mean(onset_values)
        std = stdev(onset_values) if len(onset_values) > 1 else 0.0

        ax_onset = axes[1]
        ax_onset.scatter(onset_dates, onset_values, color="#C44E52", s=22,
                         zorder=3, alpha=0.8)
        ax_onset.plot(onset_dates, onset_values, color="#C44E52", linewidth=1.0,
                      alpha=0.4)

        # Average onset line
        ax_onset.axhline(avg, color="#C44E52", linewidth=1.0, linestyle="--",
                         alpha=0.7, label=f"avg {_onset_label(avg)}")

        # ±1σ shaded band — rhythmicity window
        ax_onset.axhspan(avg - std, avg + std, color="#C44E52", alpha=0.08,
                         label=f"±1σ  ({_fmt_std(std)})")

        ax_onset.legend(frameon=False, loc="upper right")
        ax_onset.yaxis.set_major_formatter(mticker.FuncFormatter(_onset_label))
        ax_onset.invert_yaxis()  # earlier = higher on the chart (healthier)
        ax_onset.set_ylabel("sleep onset")
        ax_onset.set_title("Sleep onset time")
        ax_onset.spines["top"].set_visible(False)
        ax_onset.spines["right"].set_visible(False)

    # Shared x-axis formatting (applied to the bottom-most axes)
    ax_bottom = axes[-1]
    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax_bottom.xaxis.set_major_locator(locator)
    ax_bottom.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
