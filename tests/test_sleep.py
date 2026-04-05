"""Tests for egon.health.sleep and egon.health.sleep_plot."""
import pytest

from egon.health.sleep import filter_sleep_by_date, load_sleep_onset, load_sleep_records
from egon.health.sleep_plot import plot_sleep


def _make_sleep_xml(records: list[dict]) -> str:
    """
    Each record dict should have: value (int), start (str), end (str).
    start/end format: "YYYY-MM-DD HH:MM:SS"
    """
    lines = "\n".join(
        f'  <Record type="HKCategoryTypeIdentifierSleepAnalysis" '
        f'value="{r["value"]}" '
        f'startDate="{r["start"]} +0000" '
        f'endDate="{r["end"]} +0000" '
        f'creationDate="{r["end"]} +0000" />'
        for r in records
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<HealthData locale="en_GB">\n'
        f"{lines}\n"
        "</HealthData>\n"
    )


_ASLEEP = "HKCategoryValueSleepAnalysisAsleepUnspecified"
_INBED = "HKCategoryValueSleepAnalysisInBed"
_AWAKE = "HKCategoryValueSleepAnalysisAwake"
_CORE = "HKCategoryValueSleepAnalysisAsleepCore"
_DEEP = "HKCategoryValueSleepAnalysisAsleepDeep"
_REM = "HKCategoryValueSleepAnalysisAsleepREM"

# One night: 23:00 Apr 3 → 07:00 Apr 4 = 8h asleep
# Plus an InBed record that should be excluded
# Plus an Awake record that should be excluded
SIMPLE_NIGHT = [
    {"value": _ASLEEP, "start": "2026-04-03 23:00:00", "end": "2026-04-04 07:00:00"},
    {"value": _INBED,  "start": "2026-04-03 22:30:00", "end": "2026-04-04 07:15:00"},  # excluded
    {"value": _AWAKE,  "start": "2026-04-04 03:00:00", "end": "2026-04-04 03:30:00"},  # excluded
]

MULTI_STAGE_NIGHT = [
    {"value": _CORE, "start": "2026-04-04 23:00:00", "end": "2026-04-05 01:00:00"},  # 2h
    {"value": _DEEP, "start": "2026-04-05 01:00:00", "end": "2026-04-05 02:30:00"},  # 1.5h
    {"value": _REM,  "start": "2026-04-05 02:30:00", "end": "2026-04-05 07:00:00"},  # 4.5h
]  # total = 8h, attributed to 2026-04-05

# Overlapping records from two sources covering the same ~8h night.
# Apple Watch segments (total 8h) + AutoSleep single block (7.5h, fully overlapping).
# Merged union should still be 8h, not 15.5h.
OVERLAPPING_SOURCES_NIGHT = [
    {"value": _CORE,   "start": "2026-04-06 23:00:00", "end": "2026-04-07 01:00:00"},  # 2h
    {"value": _REM,    "start": "2026-04-07 01:00:00", "end": "2026-04-07 05:00:00"},  # 4h
    {"value": _DEEP,   "start": "2026-04-07 05:00:00", "end": "2026-04-07 07:00:00"},  # 2h
    {"value": _ASLEEP, "start": "2026-04-06 23:00:00", "end": "2026-04-07 06:30:00"},  # 7.5h overlap
]  # merged union: 23:00–07:00 = 8h


class TestLoadSleepRecords:
    def test_basic_asleep_duration(self, tmp_path):
        xml = _make_sleep_xml(SIMPLE_NIGHT)
        path = tmp_path / "export.xml"
        path.write_text(xml)
        data = load_sleep_records(path)
        assert len(data) == 1
        d, hours = data[0]
        assert d == date(2026, 4, 4)
        assert abs(hours - 8.0) < 0.01

    def test_excludes_inbed_and_awake(self, tmp_path):
        xml = _make_sleep_xml(SIMPLE_NIGHT)
        path = tmp_path / "export.xml"
        path.write_text(xml)
        data = load_sleep_records(path)
        _, hours = data[0]
        # Only the asleep record (8h) — not InBed (8.75h) or Awake (0.5h)
        assert abs(hours - 8.0) < 0.01

    def test_sums_multiple_stages(self, tmp_path):
        xml = _make_sleep_xml(MULTI_STAGE_NIGHT)
        path = tmp_path / "export.xml"
        path.write_text(xml)
        data = load_sleep_records(path)
        assert len(data) == 1
        d, hours = data[0]
        assert d == date(2026, 4, 5)
        assert abs(hours - 8.0) < 0.01

    def test_attributed_to_wake_date(self, tmp_path):
        # Sleep crosses midnight — should be attributed to the wake-up date
        xml = _make_sleep_xml([
            {"value": _ASLEEP, "start": "2026-04-10 22:00:00", "end": "2026-04-11 06:00:00"},
        ])
        path = tmp_path / "export.xml"
        path.write_text(xml)
        data = load_sleep_records(path)
        assert data[0][0] == date(2026, 4, 11)

    def test_returns_sorted_by_date(self, tmp_path):
        xml = _make_sleep_xml([
            {"value": _ASLEEP, "start": "2026-04-05 23:00:00", "end": "2026-04-06 07:00:00"},
            {"value": _ASLEEP, "start": "2026-04-03 23:00:00", "end": "2026-04-04 07:00:00"},
        ])
        path = tmp_path / "export.xml"
        path.write_text(xml)
        data = load_sleep_records(path)
        dates = [d for d, _ in data]
        assert dates == sorted(dates)

    def test_deduplicates_overlapping_sources(self, tmp_path):
        xml = _make_sleep_xml(OVERLAPPING_SOURCES_NIGHT)
        path = tmp_path / "export.xml"
        path.write_text(xml)
        data = load_sleep_records(path)
        assert len(data) == 1
        d, hours = data[0]
        assert d == date(2026, 4, 7)
        assert abs(hours - 8.0) < 0.01  # not 15.5h

    def test_returns_empty_for_no_sleep_records(self, tmp_path):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<HealthData locale="en_GB">\n'
            '  <Record type="HKQuantityTypeIdentifierBodyMass" value="80" unit="kg" '
            'startDate="2026-04-01 08:00:00 +0000" endDate="2026-04-01 08:00:00 +0000" '
            'creationDate="2026-04-01 08:00:00 +0000" />\n'
            "</HealthData>\n"
        )
        path = tmp_path / "export.xml"
        path.write_text(xml)
        assert load_sleep_records(path) == []


class TestFilterSleepByDate:
    def test_inclusive_bounds(self):
        data = [(date(2026, 4, d), float(d)) for d in range(1, 8)]
        result = filter_sleep_by_date(data, date(2026, 4, 3), date(2026, 4, 5))
        assert [d for d, _ in result] == [date(2026, 4, 3), date(2026, 4, 4), date(2026, 4, 5)]

    def test_returns_empty_when_no_match(self):
        data = [(date(2026, 3, 1), 7.5)]
        assert filter_sleep_by_date(data, date(2026, 4, 1), date(2026, 4, 30)) == []


class TestLoadSleepOnset:
    def test_onset_after_midnight(self, tmp_path):
        # Sleep starts at 00:30, ends at 08:00 — onset = 6.5h after 18:00
        xml = _make_sleep_xml([
            {"value": _ASLEEP, "start": "2026-04-10 00:30:00", "end": "2026-04-10 08:00:00"},
        ])
        path = tmp_path / "export.xml"
        path.write_text(xml)
        data = load_sleep_onset(path)
        assert len(data) == 1
        d, onset = data[0]
        assert d == date(2026, 4, 10)
        assert abs(onset - 6.5) < 0.01  # 00:30 = 6.5h after 18:00

    def test_onset_before_midnight(self, tmp_path):
        # Sleep starts at 22:00 — onset = 4.0h after 18:00
        xml = _make_sleep_xml([
            {"value": _ASLEEP, "start": "2026-04-10 22:00:00", "end": "2026-04-11 06:00:00"},
        ])
        path = tmp_path / "export.xml"
        path.write_text(xml)
        data = load_sleep_onset(path)
        d, onset = data[0]
        assert d == date(2026, 4, 11)
        assert abs(onset - 4.0) < 0.01  # 22:00 = 4.0h after 18:00

    def test_onset_uses_earliest_merged_interval(self, tmp_path):
        # Two overlapping sources: earliest start wins
        xml = _make_sleep_xml([
            {"value": _CORE,   "start": "2026-04-10 23:00:00", "end": "2026-04-11 03:00:00"},
            {"value": _ASLEEP, "start": "2026-04-10 22:30:00", "end": "2026-04-11 06:00:00"},
        ])
        path = tmp_path / "export.xml"
        path.write_text(xml)
        data = load_sleep_onset(path)
        _, onset = data[0]
        assert abs(onset - 4.5) < 0.01  # 22:30 = 4.5h after 18:00


class TestPlotSleep:
    DATA = [(date(2026, 4, d), 6.5 + d * 0.1) for d in range(1, 8)]
    ONSET_DATA = [(date(2026, 4, d), 4.0 + d * 0.1) for d in range(1, 8)]

    def test_saves_pdf(self, tmp_path):
        out = tmp_path / "sleep.pdf"
        plot_sleep(self.DATA, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "sleep.pdf"
        plot_sleep(self.DATA, out)
        assert out.exists()

    def test_raises_on_empty_data(self, tmp_path):
        with pytest.raises(ValueError, match="No sleep data"):
            plot_sleep([], tmp_path / "out.pdf")

    def test_saves_pdf_with_onset_subplot(self, tmp_path):
        out = tmp_path / "sleep_onset.pdf"
        plot_sleep(self.DATA, out, onset_data=self.ONSET_DATA)
        assert out.exists()
        assert out.stat().st_size > 0
