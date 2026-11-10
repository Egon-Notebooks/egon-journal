"""
LLM-generated Apple Health summaries via Ollama.

Inspired by krumjahn/applehealth: rather than sending raw records to the
model, we compute compact descriptive statistics per metric — mean / min /
max, a first-vs-last-bucket trend, and a weekly (or, for long periods,
monthly) breakdown — and ask a local model to narrate them.  Small local
models (3b–7b) handle this far more reliably than long raw series.

Two kinds of output:
  - an overall narrative summary of all health metrics for the period
    (``generate_health_summary``), and
  - a short per-metric commentary paragraph for use beneath a report
    figure (``generate_metric_commentary``).

All inference runs locally via Ollama; no data leaves the device.

Requires the optional dependency group:
    uv sync --extra local-llm
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from statistics import mean

from egon.health.apple_health import (
    daily_mean,
    daily_sum,
    filter_by_date,
    infer_unit,
)
from egon.health.sleep import filter_sleep_by_date, load_sleep_records
from egon.local_llm import chat

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_SUMMARY_SYSTEM: str = (
    (_PROMPTS_DIR / "health_summary_system.txt").read_text(encoding="utf-8").strip()
)
_COMMENTARY_SYSTEM: str = (
    (_PROMPTS_DIR / "health_commentary_system.txt").read_text(encoding="utf-8").strip()
)

# Periods longer than this many days are bucketed by month instead of by
# ISO week, to keep the stats block compact for the model.
_WEEKLY_BUCKET_MAX_DAYS = 112

# Quantity metrics included in the stats block.
# (record key, figure/commentary key, display name, daily aggregation)
_QUANTITY_METRICS: list[tuple[str, str, str, str]] = [
    ("BodyMass", "weight", "Weight", "mean"),
    ("RestingHeartRate", "resting-heart-rate", "Resting heart rate", "mean"),
    ("HeartRateVariabilitySDNN", "hrv", "Heart rate variability (SDNN)", "mean"),
    ("StepCount", "step-count", "Steps", "sum"),
    ("AppleExerciseTime", "exercise", "Exercise time", "sum"),
    ("VO2Max", "vo2max", "VO₂ max", "mean"),
]


@dataclass
class MetricStats:
    """Descriptive statistics for one health metric over a period."""

    key: str  # figure key, e.g. "resting-heart-rate"
    name: str  # display name, e.g. "Resting heart rate"
    unit: str
    n_days: int
    mean: float
    min_value: float
    min_date: date_type
    max_value: float
    max_date: date_type
    # (bucket label, mean of daily values) — weekly or monthly, full buckets only
    buckets: list[tuple[str, float]] = field(default_factory=list)

    def format(self) -> str:
        """Render this metric's statistics as a compact text block."""
        unit_str = f" {self.unit}" if self.unit else ""
        lines = [
            f"### {self.name}",
            f"- days with data: {self.n_days}",
            f"- mean: {_fmt(self.mean)}{unit_str} | "
            f"min: {_fmt(self.min_value)} ({self.min_date.isoformat()}) | "
            f"max: {_fmt(self.max_value)} ({self.max_date.isoformat()})",
        ]
        if reading := _READING.get(self.key):
            lines.append(f"- reading: {reading}")
        if len(self.buckets) >= 2:
            first_label, first_val = self.buckets[0]
            last_label, last_val = self.buckets[-1]
            lines.append(
                f"- trend: {_fmt(first_val)} ({first_label}) → {_fmt(last_val)} ({last_label})"
            )
            breakdown = ", ".join(f"{label}: {_fmt(v)}" for label, v in self.buckets)
            lines.append(f"- breakdown (mean per day): {breakdown}")
        return "\n".join(lines)


# How to read the direction of each metric, so the model frames changes correctly.
_READING: dict[str, str] = {
    "resting-heart-rate": "lower usually means better recovery and fitness; a fall is an improvement",
    "hrv": "higher usually means better recovery and lower stress; a rise is an improvement",
    "vo2max": "higher means fitter; it changes slowly",
    "step-count": "more steps are generally better for mood",
    "exercise": "more is generally better; the WHO suggests about 30 minutes a day",
    "sleep": "7–9 hours a night is the usual recommendation for adults",
    "weight": "neither direction is good or bad in itself; sudden changes are worth noticing",
}

# An edge bucket (first or last week/month) only counts if the period covers enough
# of it; a one-day "week" at the end of a quarter would otherwise look like a big change.
_MIN_EDGE_DAYS = {True: 4, False: 15}  # weekly: 4 of 7 days, monthly: 15 days


def _fmt(value: float) -> str:
    """Format a value compactly: integers for large numbers, one decimal otherwise."""
    if abs(value) >= 100:
        return f"{value:,.0f}"
    return f"{value:.1f}"


def _bucket_label(d: date_type, weekly: bool) -> str:
    if weekly:
        iso = d.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return f"{d.year}-{d.month:02d}"


def _bucket_means(
    data: list[tuple[date_type, float]],
    weekly: bool,
    start: date_type | None = None,
    end: date_type | None = None,
) -> list[tuple[str, float]]:
    """Group daily values into weekly or monthly buckets and average each.

    When the period [start, end] is given, a first or last bucket that the period
    only partly covers is dropped (see ``_MIN_EDGE_DAYS``).
    """
    buckets: dict[str, list[float]] = {}
    order: list[str] = []
    for d, v in data:
        label = _bucket_label(d, weekly)
        if label not in buckets:
            buckets[label] = []
            order.append(label)
        buckets[label].append(v)
    if start is not None and end is not None and len(order) > 2:
        covered: dict[str, int] = {}
        day = start
        while day <= end:
            label = _bucket_label(day, weekly)
            covered[label] = covered.get(label, 0) + 1
            day += timedelta(days=1)
        for edge in (order[0], order[-1]):
            if covered.get(edge, 0) < _MIN_EDGE_DAYS[weekly] and len(order) > 2:
                order.remove(edge)
    return [(label, mean(buckets[label])) for label in order]


def _stats_from_series(
    key: str,
    name: str,
    unit: str,
    data: list[tuple[date_type, float]],
    weekly: bool,
    start: date_type | None = None,
    end: date_type | None = None,
) -> MetricStats:
    values = [v for _, v in data]
    min_date, min_value = min(data, key=lambda x: x[1])
    max_date, max_value = max(data, key=lambda x: x[1])
    return MetricStats(
        key=key,
        name=name,
        unit=unit,
        n_days=len(data),
        mean=mean(values),
        min_value=min_value,
        min_date=min_date,
        max_value=max_value,
        max_date=max_date,
        buckets=_bucket_means(data, weekly, start, end),
    )


def build_health_stats(
    health_records: dict,
    xml_path: Path | None,
    start: date_type,
    end: date_type,
) -> list[MetricStats]:
    """
    Compute :class:`MetricStats` for every metric with data in [start, end].

    *health_records* is the dict returned by
    :func:`egon.health.apple_health.load_records`.  Sleep duration is parsed
    separately from *xml_path* (it is a category type, not a quantity type).
    """
    weekly = (end - start).days <= _WEEKLY_BUCKET_MAX_DAYS
    stats: list[MetricStats] = []

    for record_key, fig_key, name, agg in _QUANTITY_METRICS:
        records = health_records.get(record_key)
        if not records:
            continue
        aggregate = daily_mean if agg == "mean" else daily_sum
        data = filter_by_date(aggregate(records), start, end)
        if not data:
            continue
        stats.append(
            _stats_from_series(fig_key, name, infer_unit(records), data, weekly, start, end)
        )

    if xml_path and xml_path.is_file():
        try:
            sleep_data = filter_sleep_by_date(load_sleep_records(xml_path), start, end)
        except Exception:
            sleep_data = []
        if sleep_data:
            stats.append(
                _stats_from_series("sleep", "Sleep duration", "h", sleep_data, weekly, start, end)
            )

    return stats


def format_health_stats(
    stats: list[MetricStats],
    label: str,
    start: date_type,
    end: date_type,
) -> str:
    """Render all metric statistics as one Markdown block for the LLM (or for export)."""
    header = (
        f"## Apple Health statistics — {label}\nPeriod: {start.isoformat()} to {end.isoformat()}"
    )
    return "\n\n".join([header, *(s.format() for s in stats)])


def generate_health_summary(stats_text: str, model: str) -> str:
    """Ask the local Ollama *model* for an overall narrative summary of *stats_text*."""
    return chat(
        model,
        _SUMMARY_SYSTEM,
        f"Here are my Apple Health statistics:\n\n{stats_text}\n\nWrite the summary as instructed.",
    )


def generate_metric_commentary(stats: MetricStats, label: str, model: str) -> str:
    """Ask the local Ollama *model* for a short commentary paragraph on one metric."""
    return chat(
        model,
        _COMMENTARY_SYSTEM,
        f"Period: {label}\n\nStatistics for {stats.name}:\n\n{stats.format()}\n\n"
        "Write the commentary paragraph as instructed.",
    )
