"""Tests for egon.health.apple_health, weight_plot, and step_count_plot."""
from datetime import date
from pathlib import Path

import pytest

from egon.health.apple_health import (
    daily_mean,
    daily_sum,
    filter_by_date,
    infer_unit,
    load_records,
)
from egon.health.hrv_plot import plot_hrv
from egon.health.resting_heart_rate_plot import plot_resting_heart_rate
from egon.health.step_count_plot import plot_step_count
from egon.health.vo2max_plot import plot_vo2max
from egon.health.weight_plot import plot_weight

# ---------------------------------------------------------------------------
# Minimal Apple Health XML fixture
# ---------------------------------------------------------------------------

def _make_export_xml(records: list[dict]) -> str:
    """Build a minimal export.xml string from a list of record attribute dicts."""
    record_lines = "\n".join(
        f'  <Record type="{r["type"]}" value="{r["value"]}" unit="{r.get("unit", "")}" '
        f'startDate="{r["date"]} 08:00:00 +0100" endDate="{r["date"]} 08:00:00 +0100" '
        f'creationDate="{r["date"]} 09:00:00 +0100" />'
        for r in records
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<HealthData locale=\"en_GB\">\n"
        f"{record_lines}\n"
        "</HealthData>\n"
    )


_BM = "HKQuantityTypeIdentifierBodyMass"
_RHR = "HKQuantityTypeIdentifierRestingHeartRate"
WEIGHT_RECORDS = [
    {"type": _BM, "value": "80.5", "unit": "kg", "date": "2026-04-01"},
    {"type": _BM, "value": "80.2", "unit": "kg", "date": "2026-04-01"},  # second reading
    {"type": _BM, "value": "79.8", "unit": "kg", "date": "2026-04-02"},
    {"type": _BM, "value": "79.5", "unit": "kg", "date": "2026-04-03"},
    {"type": _RHR, "value": "58", "unit": "count/min", "date": "2026-04-01"},
]


@pytest.fixture
def export_xml(tmp_path) -> Path:
    path = tmp_path / "export.xml"
    path.write_text(_make_export_xml(WEIGHT_RECORDS), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# load_records
# ---------------------------------------------------------------------------

class TestLoadRecords:
    def test_strips_prefix(self, export_xml):
        records = load_records(export_xml)
        assert "BodyMass" in records
        assert "RestingHeartRate" in records

    def test_parses_values(self, export_xml):
        records = load_records(export_xml)
        values = [r.value for r in records["BodyMass"]]
        assert 80.5 in values
        assert 79.8 in values

    def test_parses_dates(self, export_xml):
        records = load_records(export_xml)
        dates = {r.date for r in records["BodyMass"]}
        assert date(2026, 4, 1) in dates
        assert date(2026, 4, 2) in dates

    def test_captures_unit(self, export_xml):
        records = load_records(export_xml)
        units = {r.unit for r in records["BodyMass"]}
        assert "kg" in units

    def test_skips_non_numeric_values(self, tmp_path):
        xml = _make_export_xml([
            {"type": _BM, "value": "N/A", "unit": "kg", "date": "2026-04-01"},
        ])
        path = tmp_path / "export.xml"
        path.write_text(xml)
        records = load_records(path)
        assert records.get("BodyMass", []) == []


# ---------------------------------------------------------------------------
# daily_mean / daily_sum
# ---------------------------------------------------------------------------

class TestDailyAggregation:
    def test_daily_mean_averages_multiple_readings(self, export_xml):
        records = load_records(export_xml)
        data = daily_mean(records["BodyMass"])
        day1 = next(v for d, v in data if d == date(2026, 4, 1))
        assert abs(day1 - 80.35) < 0.01  # mean of 80.5 and 80.2

    def test_daily_mean_single_reading(self, export_xml):
        records = load_records(export_xml)
        data = daily_mean(records["BodyMass"])
        day2 = next(v for d, v in data if d == date(2026, 4, 2))
        assert abs(day2 - 79.8) < 0.01

    def test_sorted_by_date(self, export_xml):
        records = load_records(export_xml)
        data = daily_mean(records["BodyMass"])
        dates = [d for d, _ in data]
        assert dates == sorted(dates)

    def test_daily_sum(self, tmp_path):
        _SC = "HKQuantityTypeIdentifierStepCount"
        xml = _make_export_xml([
            {"type": _SC, "value": "3000", "unit": "count", "date": "2026-04-01"},
            {"type": _SC, "value": "2000", "unit": "count", "date": "2026-04-01"},
        ])
        path = tmp_path / "export.xml"
        path.write_text(xml)
        records = load_records(path)
        data = daily_sum(records["StepCount"])
        assert data[0] == (date(2026, 4, 1), 5000.0)


# ---------------------------------------------------------------------------
# filter_by_date
# ---------------------------------------------------------------------------

class TestFilterByDate:
    def test_inclusive_bounds(self):
        data = [(date(2026, 4, d), float(d)) for d in range(1, 8)]
        result = filter_by_date(data, date(2026, 4, 3), date(2026, 4, 5))
        assert [d for d, _ in result] == [date(2026, 4, 3), date(2026, 4, 4), date(2026, 4, 5)]

    def test_returns_empty_when_no_match(self):
        data = [(date(2026, 3, 1), 80.0)]
        assert filter_by_date(data, date(2026, 4, 1), date(2026, 4, 30)) == []


# ---------------------------------------------------------------------------
# infer_unit
# ---------------------------------------------------------------------------

class TestInferUnit:
    def test_returns_most_common_unit(self, export_xml):
        records = load_records(export_xml)
        assert infer_unit(records["BodyMass"]) == "kg"

    def test_empty_records_returns_empty_string(self):
        assert infer_unit([]) == ""


# ---------------------------------------------------------------------------
# plot_weight
# ---------------------------------------------------------------------------

class TestPlotHrv:
    DATA = [(date(2026, 4, d), 40.0 + d * 0.5) for d in range(1, 8)]

    def test_saves_pdf(self, tmp_path):
        out = tmp_path / "hrv.pdf"
        plot_hrv(self.DATA, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "hrv.pdf"
        plot_hrv(self.DATA, out)
        assert out.exists()

    def test_raises_on_empty_data(self, tmp_path):
        with pytest.raises(ValueError, match="No HRV data"):
            plot_hrv([], tmp_path / "out.pdf")


class TestPlotRestingHeartRate:
    DATA = [(date(2026, 4, d), 58.0 + d * 0.2) for d in range(1, 8)]

    def test_saves_pdf(self, tmp_path):
        out = tmp_path / "rhr.pdf"
        plot_resting_heart_rate(self.DATA, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "rhr.pdf"
        plot_resting_heart_rate(self.DATA, out)
        assert out.exists()

    def test_raises_on_empty_data(self, tmp_path):
        with pytest.raises(ValueError, match="No resting heart rate data"):
            plot_resting_heart_rate([], tmp_path / "out.pdf")


class TestPlotWeight:
    DATA = [(date(2026, 4, d), 80.0 - d * 0.1) for d in range(1, 8)]
    LEAN_DATA = [(date(2026, 4, d), 65.0 - d * 0.05) for d in range(1, 8)]

    def test_saves_pdf(self, tmp_path):
        out = tmp_path / "weight.pdf"
        plot_weight(self.DATA, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "weight.pdf"
        plot_weight(self.DATA, out)
        assert out.exists()

    def test_raises_on_empty_data(self, tmp_path):
        with pytest.raises(ValueError, match="No weight data"):
            plot_weight([], tmp_path / "out.pdf")

    def test_saves_pdf_with_lean_data(self, tmp_path):
        out = tmp_path / "weight_lean.pdf"
        plot_weight(self.DATA, out, lean_data=self.LEAN_DATA)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_lean_data_none_does_not_error(self, tmp_path):
        out = tmp_path / "weight_no_lean.pdf"
        plot_weight(self.DATA, out, lean_data=None)
        assert out.exists()

    def test_target_lines(self, tmp_path):
        out = tmp_path / "weight_targets.pdf"
        plot_weight(self.DATA, out, lean_data=self.LEAN_DATA,
                    target_body_mass=75.0, target_lean_body_mass=65.0)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_target_body_mass_only(self, tmp_path):
        out = tmp_path / "weight_target_bm.pdf"
        plot_weight(self.DATA, out, target_body_mass=75.0)
        assert out.exists()


class TestPlotStepCount:
    DATA = [(date(2026, 4, d), 8000.0 + d * 200) for d in range(1, 8)]

    def test_saves_pdf(self, tmp_path):
        out = tmp_path / "steps.pdf"
        plot_step_count(self.DATA, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "steps.pdf"
        plot_step_count(self.DATA, out)
        assert out.exists()

    def test_raises_on_empty_data(self, tmp_path):
        with pytest.raises(ValueError, match="No step count data"):
            plot_step_count([], tmp_path / "out.pdf")


class TestPlotVo2Max:
    DATA = [(date(2026, 4, d), 45.0 + d * 0.1) for d in range(1, 8)]

    def test_saves_pdf(self, tmp_path):
        out = tmp_path / "vo2max.pdf"
        plot_vo2max(self.DATA, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "vo2max.pdf"
        plot_vo2max(self.DATA, out)
        assert out.exists()

    def test_raises_on_empty_data(self, tmp_path):
        with pytest.raises(ValueError, match="No VO2 max data"):
            plot_vo2max([], tmp_path / "out.pdf")
