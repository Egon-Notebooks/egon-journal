"""
Frontmatter field definitions and validation for all Egon node types.

The validate() function accepts a frontmatter dict and returns a list of
error strings. An empty list means the node is valid.
"""

from datetime import date as date_type

VALID_NODE_TYPES = frozenset(
    {
        "article",
        "journal",
        "prompt",
        "program",
        "program-day",
        "summary",
    }
)

# Fields required on every node type
_UNIVERSAL_REQUIRED = ["title", "date", "type", "tags", "egon_version"]

# Additional required fields per node type (beyond universal)
_NODE_REQUIRED: dict[str, list[str]] = {
    "article": [],
    "journal": [],  # mood and energy are optional
    "prompt": ["related_article"],
    "program": ["duration_days"],
    "program-day": ["program", "day"],
    "summary": ["period", "period_label"],
}


def _check_universal(fm: dict) -> list[str]:
    errors: list[str] = []

    for field in _UNIVERSAL_REQUIRED:
        if field not in fm:
            errors.append(f"Missing required field: '{field}'")

    if "type" in fm and fm["type"] not in VALID_NODE_TYPES:
        errors.append(f"Invalid type: '{fm['type']}'. Must be one of: {sorted(VALID_NODE_TYPES)}")

    if "date" in fm:
        d = fm["date"]
        if isinstance(d, date_type):
            pass  # already a valid date object
        elif isinstance(d, str):
            try:
                date_type.fromisoformat(d)
            except ValueError:
                errors.append(f"Field 'date' is not a valid ISO date: '{d}'")
        else:
            errors.append(f"Field 'date' must be a string or date, got {type(d).__name__}")

    if "egon_version" in fm and str(fm["egon_version"]) != "1":
        errors.append(f"Field 'egon_version' must be '1', got '{fm['egon_version']}'")

    if "tags" in fm and not isinstance(fm["tags"], list):
        errors.append("Field 'tags' must be a list")

    return errors


def _check_type_fields(fm: dict) -> list[str]:
    errors: list[str] = []
    node_type = fm.get("type")

    if node_type not in _NODE_REQUIRED:
        return errors  # unknown type already flagged by universal check

    for field in _NODE_REQUIRED[node_type]:
        if field not in fm:
            errors.append(f"Missing required field for type '{node_type}': '{field}'")

    if node_type == "summary" and "period" in fm:
        if fm["period"] not in ("week", "month"):
            errors.append(f"Field 'period' must be 'week' or 'month', got '{fm['period']}'")

    if node_type == "program-day" and "day" in fm:
        if not isinstance(fm["day"], int) or fm["day"] < 1:
            errors.append("Field 'day' must be a positive integer")

    if node_type == "program" and "duration_days" in fm:
        if not isinstance(fm["duration_days"], int) or fm["duration_days"] < 1:
            errors.append("Field 'duration_days' must be a positive integer")

    return errors


def validate(frontmatter: dict) -> list[str]:
    """
    Validate a frontmatter dict. Returns a list of error strings.
    An empty list means the node is valid.
    """
    errors = _check_universal(frontmatter)
    errors.extend(_check_type_fields(frontmatter))
    return errors
