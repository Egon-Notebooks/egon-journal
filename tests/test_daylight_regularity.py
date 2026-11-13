"""Tests for time in daylight and sleep regularity in reports."""

from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from egon.cli import app
from egon.config import ReportConfig
from egon.full_report import build_full_report
from egon.health.sleep import rolling_sd_minutes
from egon.report import figures as F
from egon.report.data import HealthSeries, ReportData
from tests.test_cli import _make_export_xml

START = date(2026, 4, 1)
DAYS = [START + timedelta(days=i) for i in range(21)]


def test_rolling_sd_is_zero_for_a_steady_bedtime():
    steady = [(d, 5.0) for d in DAYS]
    assert all(v == 0 for _, v in rolling_sd_minutes(steady))


def test_rolling_sd_in_minutes_and_skips_thin_windows():
    alternating = [(d, 5.0 if i % 2 else 6.0) for i, d in enumerate(DAYS)]
    result = rolling_sd_minutes(alternating)
    assert result[0][0] == DAYS[3]  # needs 4 nights
    assert result[-1][1] == pytest.approx(30, abs=1)


def test_figures_have_every_part():
    series = [(d, 40.0 + i) for i, d in enumerate(DAYS)]
    for fig in (F.daylight_figure(series), F.sleep_regularity_figure(series, series)):
        assert fig.spec and fig.why and fig.how_to_read and fig.table.rows


def test_full_report_includes_daylight_and_regularity():
    onset = [(d, 5.0 + (i % 3) * 0.5) for i, d in enumerate(DAYS)]
    data = ReportData(
        label="2026-04",
        start=DAYS[0],
        end=DAYS[-1],
        health={"daylight": HealthSeries([(d, 45.0) for d in DAYS], "min")},
        sleep_hours=[(d, 7.0) for d in DAYS],
        sleep_onset=onset,
    )
    report = build_full_report(data, config=ReportConfig())
    keys = {f.key for s in report.sections for f in s.figures}
    assert {"daylight", "sleep-regularity"} <= keys
    stat_labels = {st.label for s in report.sections for st in s.stats}
    assert {"Daylight", "Bedtime spread"} <= stat_labels


def test_both_can_be_turned_off():
    data = ReportData(
        label="2026-04",
        start=DAYS[0],
        end=DAYS[-1],
        health={"daylight": HealthSeries([(d, 45.0) for d in DAYS], "min")},
        sleep_hours=[(d, 7.0) for d in DAYS],
        sleep_onset=[(d, 5.0) for d in DAYS],
    )
    config = ReportConfig(analyses={"daylight": False, "sleep_regularity": False})
    keys = {f.key for s in build_full_report(data, config=config).sections for f in s.figures}
    assert not {"daylight", "sleep-regularity"} & keys


def test_report_daylight_command(tmp_path):
    records = [
        {
            "type": "HKQuantityTypeIdentifierTimeInDaylight",
            "value": "15",
            "unit": "min",
            "date": d.isoformat(),
        }
        for d in DAYS[:7]
        for _ in range(2)
    ]
    xml = tmp_path / "export.xml"
    xml.write_text(_make_export_xml(records), encoding="utf-8")
    result = CliRunner().invoke(app, ["report", "daylight", "--xml", str(xml), "--for", "2026-04"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "reports" / "daylight" / "2026-04.html").exists()
