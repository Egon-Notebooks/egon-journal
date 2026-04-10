"""
Word count by day — analytics and plot.
"""
import math
import re
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.analytics.loader import JournalEntry
from egon.plot_style import apply_style

# HTML/Markdown comment pattern (<!-- ... -->)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def count_words(text: str) -> int:
    """
    Count whitespace-delimited words in *text*.
    Strips Markdown/HTML comments before counting.
    """
    text = _COMMENT_RE.sub("", text)
    return len(text.split())


def word_counts_by_day(entries: list[JournalEntry]) -> list[tuple[date_type, int]]:
    """Return a list of (date, word_count) tuples sorted by date."""
    return [(e.date, count_words(e.body)) for e in entries]


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def period_bounds(period: str, ref: date_type) -> tuple[date_type, date_type]:
    """
    Return (start, end) inclusive date bounds for *period* relative to *ref*.

    period values: "week", "month", "quarter", "year", "all-time"
    For "all-time" returns (date.min, date.max).
    """
    match period:
        case "week":
            start = ref - timedelta(days=ref.weekday())
            return start, start + timedelta(days=6)
        case "month":
            start = ref.replace(day=1)
            # First day of next month minus one day
            if ref.month == 12:
                end = date_type(ref.year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date_type(ref.year, ref.month + 1, 1) - timedelta(days=1)
            return start, end
        case "quarter":
            q_start_month = ((ref.month - 1) // 3) * 3 + 1
            start = date_type(ref.year, q_start_month, 1)
            end_month = q_start_month + 2
            if end_month == 12:
                end = date_type(ref.year, 12, 31)
            else:
                end = date_type(ref.year, end_month + 1, 1) - timedelta(days=1)
            return start, end
        case "year":
            return date_type(ref.year, 1, 1), date_type(ref.year, 12, 31)
        case "all-time":
            return date_type.min, date_type.max
        case _:
            raise ValueError(
                f"Unknown period '{period}'. Use: week, month, quarter, year, all-time"
            )


def period_label(period: str, ref: date_type) -> str:
    """Return a short label for the period, used in titles and filenames."""
    match period:
        case "week":
            year, week, _ = ref.isocalendar()
            return f"{year}-W{week:02d}"
        case "month":
            return ref.strftime("%Y-%m")
        case "quarter":
            q = math.ceil(ref.month / 3)
            return f"{ref.year}-Q{q}"
        case "year":
            return str(ref.year)
        case "all-time":
            return "all-time"
        case _:
            raise ValueError(f"Unknown period '{period}'")


_YEAR_RE    = re.compile(r"^(\d{4})$")
_MONTH_RE   = re.compile(r"^(\d{4})-(\d{2})$")
_WEEK_RE    = re.compile(r"^(\d{4})-W(\d{2})$")
_QUARTER_RE = re.compile(r"^(\d{4})-Q([1-4])$")


def parse_period_value(value: str) -> tuple[date_type, date_type, str]:
    """
    Parse a specific period value string into (start, end, label).

    Accepted formats:
      "2025"      → full year 2025
      "2026-02"   → February 2026
      "2026-W14"  → ISO week 14 of 2026
      "2026-Q2"   → second quarter of 2026
    """
    if m := _YEAR_RE.match(value):
        year = int(m.group(1))
        return date_type(year, 1, 1), date_type(year, 12, 31), str(year)

    if m := _MONTH_RE.match(value):
        year, month = int(m.group(1)), int(m.group(2))
        start = date_type(year, month, 1)
        if month == 12:
            end = date_type(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date_type(year, month + 1, 1) - timedelta(days=1)
        return start, end, value

    if m := _WEEK_RE.match(value):
        year, week = int(m.group(1)), int(m.group(2))
        # ISO week: Monday of week N
        start = date_type.fromisocalendar(year, week, 1)
        return start, start + timedelta(days=6), value

    if m := _QUARTER_RE.match(value):
        year, q = int(m.group(1)), int(m.group(2))
        q_start_month = (q - 1) * 3 + 1
        start = date_type(year, q_start_month, 1)
        end_month = q_start_month + 2
        if end_month == 12:
            end = date_type(year, 12, 31)
        else:
            end = date_type(year, end_month + 1, 1) - timedelta(days=1)
        return start, end, value

    raise ValueError(
        f"Cannot parse period value '{value}'. "
        "Expected: YYYY, YYYY-MM, YYYY-WNN, or YYYY-QN"
    )


def filter_entries(
    entries: list[JournalEntry], start: date_type, end: date_type
) -> list[JournalEntry]:
    """Return entries whose date falls within [start, end] inclusive."""
    return [e for e in entries if start <= e.date <= end]


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def plot_word_count(
    entries: list[JournalEntry],
    output_path: Path | None,
    title: str = "Journal word count by day",
) -> "plt.Figure | None":
    """
    Generate a word-count-by-day bar chart and save it to *output_path*.

    The file format is inferred from the extension (.pdf, .png, .svg, …).
    """
    apply_style()
    data = word_counts_by_day(entries)
    if not data:
        raise ValueError("No journal entries found — nothing to plot.")

    dates, counts = zip(*data)

    fig, ax = plt.subplots(figsize=(14, 4))

    ax.bar(dates, counts, width=0.8, color="#4C72B0", alpha=0.85)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    ax.set_ylabel("word count")
    ax.set_title(title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
    return None
