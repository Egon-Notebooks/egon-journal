"""
Apple Health XML parser.

How to export your data:
  Health app → profile picture → Export All Health Data → share the zip.
  Unzip it — the file you need is export.xml inside the zip.

Set EGON_APPLE_HEALTH_XML in .env to the full path of that export.xml file.

https://towardsdatascience.com/analyse-your-health-with-python-and-apple-health-11c12894aae2

No network calls. No third-party dependencies beyond the standard library.
All date handling uses date objects (not datetime) so records align naturally
with journal entries.
"""
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date as date_type, datetime
from pathlib import Path
from statistics import mean
from typing import NamedTuple

# Prefix Apple prepends to most quantity/category type identifiers
_QUANTITY_PREFIX = "HKQuantityTypeIdentifier"
_CATEGORY_PREFIX = "HKCategoryTypeIdentifier"


class HealthRecord(NamedTuple):
    date: date_type
    value: float
    unit: str


def _strip_prefix(type_str: str) -> str:
    for prefix in (_QUANTITY_PREFIX, _CATEGORY_PREFIX):
        if type_str.startswith(prefix):
            return type_str[len(prefix):]
    return type_str


def _parse_date(date_str: str) -> date_type:
    """Parse Apple Health date strings like '2026-04-03 08:15:00 +0100'."""
    # Take only the date portion — timezone offsets vary, we only care about the day
    return datetime.strptime(date_str[:10], "%Y-%m-%d").date()


def load_records(xml_path: Path) -> dict[str, list[HealthRecord]]:
    """
    Parse export.xml and return a dict mapping metric name → list[HealthRecord].

    Metric names have the HKQuantityTypeIdentifier / HKCategoryTypeIdentifier
    prefix stripped, e.g. "BodyMass", "RestingHeartRate", "StepCount".

    Only numeric records are included; non-numeric values are skipped.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    records: dict[str, list[HealthRecord]] = defaultdict(list)

    for elem in root.iter("Record"):
        attrib = elem.attrib
        raw_type = attrib.get("type", "")
        raw_value = attrib.get("value", "")
        unit = attrib.get("unit", "")
        end_date_str = attrib.get("endDate", "")

        try:
            value = float(raw_value)
        except (ValueError, TypeError):
            continue

        try:
            record_date = _parse_date(end_date_str)
        except ValueError:
            continue

        metric = _strip_prefix(raw_type)
        records[metric].append(HealthRecord(date=record_date, value=value, unit=unit))

    return dict(records)


def daily_mean(records: list[HealthRecord]) -> list[tuple[date_type, float]]:
    """
    Aggregate a list of HealthRecords to one value per day (mean).
    Returns a list of (date, mean_value) tuples sorted by date.
    """
    by_date: dict[date_type, list[float]] = defaultdict(list)
    for r in records:
        by_date[r.date].append(r.value)
    return sorted(
        ((d, mean(values)) for d, values in by_date.items()),
        key=lambda x: x[0],
    )


def daily_sum(records: list[HealthRecord]) -> list[tuple[date_type, float]]:
    """
    Aggregate a list of HealthRecords to one value per day (sum).
    Returns a list of (date, sum_value) tuples sorted by date.
    """
    by_date: dict[date_type, list[float]] = defaultdict(list)
    for r in records:
        by_date[r.date].append(r.value)
    return sorted(
        ((d, sum(values)) for d, values in by_date.items()),
        key=lambda x: x[0],
    )


def filter_by_date(
    data: list[tuple[date_type, float]],
    start: date_type,
    end: date_type,
) -> list[tuple[date_type, float]]:
    """Return only entries within [start, end] inclusive."""
    return [(d, v) for d, v in data if start <= d <= end]


def infer_unit(records: list[HealthRecord]) -> str:
    """Return the most common unit string from a list of records."""
    if not records:
        return ""
    return max(set(r.unit for r in records), key=lambda u: sum(1 for r in records if r.unit == u))
