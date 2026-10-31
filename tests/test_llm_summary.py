"""
Tests for egon.health.llm_summary — stats building and prompt assembly.

LLM calls are mocked at the egon.local_llm.chat boundary; no Ollama
installation is required.
"""

from datetime import date
from unittest.mock import patch

from egon.health.apple_health import HealthRecord
from egon.health.llm_summary import (
    build_health_stats,
    format_health_stats,
    generate_health_summary,
    generate_metric_commentary,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _records(values: dict[date, float], unit: str) -> list[HealthRecord]:
    return [HealthRecord(date=d, value=v, unit=unit) for d, v in values.items()]


def _sleep_xml_text(days: int = 7) -> str:
    rows = "\n".join(
        f'  <Record type="HKCategoryTypeIdentifierSleepAnalysis" '
        f'value="HKCategoryValueSleepAnalysisAsleepCore" '
        f'startDate="2026-04-{i:02d} 23:00:00 +0100" '
        f'endDate="2026-04-{i + 1:02d} 06:30:00 +0100" />'
        for i in range(1, days + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<HealthData locale="en_GB">\n'
        f"{rows}\n"
        "</HealthData>\n"
    )


# ---------------------------------------------------------------------------
# build_health_stats
# ---------------------------------------------------------------------------


class TestBuildHealthStats:
    def test_mean_metric(self):
        records = {
            "BodyMass": _records({date(2026, 4, i): 80.0 - i * 0.1 for i in range(1, 15)}, "kg")
        }
        stats = build_health_stats(records, None, date(2026, 4, 1), date(2026, 4, 14))
        assert len(stats) == 1
        s = stats[0]
        assert s.key == "weight"
        assert s.unit == "kg"
        assert s.n_days == 14
        assert s.max_value == 79.9
        assert s.max_date == date(2026, 4, 1)
        assert s.min_value == 78.6
        assert s.min_date == date(2026, 4, 14)
        # 14 days spanning ISO weeks → at least two weekly buckets
        assert len(s.buckets) >= 2
        assert all(label.startswith("2026-W") for label, _ in s.buckets)

    def test_sum_metric_aggregates_within_day(self):
        records = {
            "StepCount": [
                HealthRecord(date=date(2026, 4, 1), value=4000.0, unit="count"),
                HealthRecord(date=date(2026, 4, 1), value=6000.0, unit="count"),
                HealthRecord(date=date(2026, 4, 2), value=8000.0, unit="count"),
            ]
        }
        stats = build_health_stats(records, None, date(2026, 4, 1), date(2026, 4, 30))
        s = stats[0]
        assert s.key == "step-count"
        assert s.max_value == 10000.0  # 4000 + 6000 summed on the same day
        assert s.n_days == 2

    def test_date_filtering_excludes_out_of_range(self):
        records = {
            "RestingHeartRate": _records(
                {date(2026, 3, 31): 60.0, date(2026, 4, 1): 55.0, date(2026, 5, 1): 70.0},
                "count/min",
            )
        }
        stats = build_health_stats(records, None, date(2026, 4, 1), date(2026, 4, 30))
        s = stats[0]
        assert s.n_days == 1
        assert s.mean == 55.0

    def test_metric_with_no_data_in_range_is_omitted(self):
        records = {"BodyMass": _records({date(2025, 1, 1): 80.0}, "kg")}
        stats = build_health_stats(records, None, date(2026, 4, 1), date(2026, 4, 30))
        assert stats == []

    def test_long_period_uses_monthly_buckets(self):
        records = {"BodyMass": _records({date(2026, m, 15): 80.0 - m for m in range(1, 7)}, "kg")}
        stats = build_health_stats(records, None, date(2026, 1, 1), date(2026, 6, 30))
        s = stats[0]
        assert [label for label, _ in s.buckets] == [f"2026-{m:02d}" for m in range(1, 7)]

    def test_sleep_from_xml(self, tmp_path):
        xml = tmp_path / "export.xml"
        xml.write_text(_sleep_xml_text(), encoding="utf-8")
        stats = build_health_stats({}, xml, date(2026, 4, 1), date(2026, 4, 30))
        assert len(stats) == 1
        s = stats[0]
        assert s.key == "sleep"
        assert s.unit == "h"
        assert abs(s.mean - 7.5) < 0.01  # 23:00 → 06:30


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


class TestFormatting:
    def test_format_health_stats_block(self):
        records = {
            "BodyMass": _records({date(2026, 4, i): 80.0 - i * 0.1 for i in range(1, 15)}, "kg")
        }
        stats = build_health_stats(records, None, date(2026, 4, 1), date(2026, 4, 14))
        text = format_health_stats(stats, "2026-04", date(2026, 4, 1), date(2026, 4, 14))
        assert "Apple Health statistics — 2026-04" in text
        assert "2026-04-01 to 2026-04-14" in text
        assert "### Weight" in text
        assert "- trend:" in text
        assert "- breakdown (mean per day):" in text

    def test_large_values_formatted_without_decimals(self):
        records = {
            "StepCount": _records({date(2026, 4, 1): 9500.0, date(2026, 4, 2): 10500.0}, "count")
        }
        stats = build_health_stats(records, None, date(2026, 4, 1), date(2026, 4, 30))
        assert "10,500" in stats[0].format()


# ---------------------------------------------------------------------------
# LLM call assembly (chat mocked)
# ---------------------------------------------------------------------------


class TestGeneration:
    def test_generate_health_summary_passes_stats(self):
        with patch("egon.health.llm_summary.chat", return_value="A summary.") as mock_chat:
            result = generate_health_summary("### Weight\n- mean: 79.0 kg", "llama3.2:3b")
        assert result == "A summary."
        args = mock_chat.call_args[0]
        assert args[0] == "llama3.2:3b"
        assert "### Weight" in args[2]

    def test_generate_metric_commentary_passes_metric_block(self):
        records = {"RestingHeartRate": _records({date(2026, 4, 1): 55.0}, "count/min")}
        stats = build_health_stats(records, None, date(2026, 4, 1), date(2026, 4, 30))
        with patch("egon.health.llm_summary.chat", return_value="A paragraph.") as mock_chat:
            result = generate_metric_commentary(stats[0], "2026-04", "llama3.2:3b")
        assert result == "A paragraph."
        user_msg = mock_chat.call_args[0][2]
        assert "Resting heart rate" in user_msg
        assert "2026-04" in user_msg
