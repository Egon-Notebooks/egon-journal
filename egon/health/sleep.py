"""
Sleep analysis loader for Apple Health data.

SleepAnalysis is a category type — the meaningful data is the duration of each
record (endDate - startDate), not the numeric value attribute. Each record
represents a contiguous window of a particular sleep stage.

Category value strings (HKCategoryValueSleepAnalysis):
  HKCategoryValueSleepAnalysisInBed             — device in bed, not necessarily asleep
  HKCategoryValueSleepAnalysisAsleepUnspecified — asleep, stage not determined
  HKCategoryValueSleepAnalysisAwake             — awake during the night
  HKCategoryValueSleepAnalysisAsleepCore        — light / core sleep (Apple Watch Series 4+)
  HKCategoryValueSleepAnalysisAsleepDeep        — deep sleep
  HKCategoryValueSleepAnalysisAsleepREM         — REM sleep

"Time asleep" is the sum of durations for all Asleep* stages (everything
except InBed and Awake).

Records are attributed to the date of their endDate (i.e. the morning the
sleeper woke up), so a night starting 2026-04-03 23:00 and ending
2026-04-04 07:00 counts toward 2026-04-04.

Sleep onset is represented as hours after 18:00 (6 PM), so that 22:00 = 4.0
and 00:30 = 6.5. This keeps values positive and monotonic across midnight.
"""
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date as date_type, datetime
from pathlib import Path

_SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"

# String values that count as asleep (excludes InBed and Awake)
_ASLEEP_VALUES = {
    "HKCategoryValueSleepAnalysisAsleepUnspecified",
    "HKCategoryValueSleepAnalysisAsleepCore",
    "HKCategoryValueSleepAnalysisAsleepDeep",
    "HKCategoryValueSleepAnalysisAsleepREM",
}

_ONSET_REF_HOUR = 18  # 6 PM — onset values are hours after this


def _parse_dt(s: str) -> datetime:
    """Parse Apple Health datetime string, ignoring timezone offset."""
    return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")


def _merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """
    Given a list of (start, end) datetime pairs, return a list of
    non-overlapping merged intervals sorted by start time.
    """
    if not intervals:
        return []
    sorted_ivs = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_ivs[0]]
    for start, end in sorted_ivs[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _onset_hours(dt: datetime) -> float:
    """
    Hours after 18:00 (6 PM). Handles cross-midnight: 00:30 → 6.5, 22:00 → 4.0.
    """
    h = dt.hour + dt.minute / 60 + dt.second / 3600
    if h < _ONSET_REF_HOUR:
        h += 24
    return h - _ONSET_REF_HOUR


def _collect_by_date(xml_path: Path) -> dict[date_type, list[tuple[datetime, datetime]]]:
    """
    Parse export.xml and return a dict mapping wake-up date → list of raw
    (start, end) asleep intervals (not yet merged).
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    by_date: dict[date_type, list[tuple[datetime, datetime]]] = defaultdict(list)

    for elem in root.iter("Record"):
        attrib = elem.attrib
        if attrib.get("type") != _SLEEP_TYPE:
            continue
        if attrib.get("value", "") not in _ASLEEP_VALUES:
            continue
        try:
            start = _parse_dt(attrib["startDate"])
            end = _parse_dt(attrib["endDate"])
        except (KeyError, ValueError):
            continue
        if (end - start).total_seconds() <= 0:
            continue
        by_date[end.date()].append((start, end))

    return dict(by_date)


def load_sleep_records(xml_path: Path) -> list[tuple[date_type, float]]:
    """
    Parse export.xml and return daily total time asleep in hours,
    sorted by date ascending.

    Each tuple is (date, hours_asleep). The date is the calendar date
    of the endDate of the sleep session (i.e. the morning after).

    Overlapping intervals from multiple sources (Apple Watch, AutoSleep,
    Pillow, etc.) are merged before summing so no time is double-counted.
    """
    by_date = _collect_by_date(xml_path)
    result = []
    for day, intervals in by_date.items():
        merged = _merge_intervals(intervals)
        hours = sum((e - s).total_seconds() / 3600 for s, e in merged)
        result.append((day, hours))
    return sorted(result, key=lambda x: x[0])


def load_sleep_onset(xml_path: Path) -> list[tuple[date_type, float]]:
    """
    Parse export.xml and return daily sleep onset time in hours after 18:00,
    sorted by date ascending.

    Each tuple is (date, onset_hours) where onset_hours is hours elapsed since
    18:00 on the evening before the wake-up date. For example:
      22:00 → 4.0,  23:30 → 5.5,  00:30 → 6.5,  02:00 → 8.0

    Onset is defined as the start of the earliest merged interval for the night.
    Overlapping intervals from multiple sources are merged first so that an
    early AutoSleep block does not create an artificially early onset.
    """
    by_date = _collect_by_date(xml_path)
    result = []
    for day, intervals in by_date.items():
        merged = _merge_intervals(intervals)
        onset_dt = merged[0][0]  # start of earliest merged interval
        result.append((day, _onset_hours(onset_dt)))
    return sorted(result, key=lambda x: x[0])


def filter_sleep_by_date(
    data: list[tuple[date_type, float]],
    start: date_type,
    end: date_type,
) -> list[tuple[date_type, float]]:
    """Return only entries within [start, end] inclusive."""
    return [(d, v) for d, v in data if start <= d <= end]
