"""
Assemble report sections and chart specs into one self-contained HTML file.

The output has no external references: Vega, Vega-Lite and vega-embed, the
fonts, the stylesheet and every chart's data are inlined.  A report therefore
opens offline, can be emailed or archived as a single file, and never makes a
network request — personal data stays on the device.

Usage:
    report = Report(title="2026-Q1", start=..., end=..., sections=[...])
    write_report(report, Path("reports/full_report/2026-Q1.html"))
"""

import base64
import json
from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from egon.report import theme

_STATIC = Path(__file__).parent / "static"

_FONTS = [
    ("Cormorant Garamond", 500, "cormorant-garamond-latin-500-normal.woff2"),
    ("Cormorant Garamond", 600, "cormorant-garamond-latin-600-normal.woff2"),
    ("Cormorant Garamond", 700, "cormorant-garamond-latin-700-normal.woff2"),
    ("DM Sans", 400, "dm-sans-latin-400-normal.woff2"),
    ("DM Sans", 500, "dm-sans-latin-500-normal.woff2"),
    ("DM Sans", 600, "dm-sans-latin-600-normal.woff2"),
]
_VENDOR = ["vega.min.js", "vega-lite.min.js", "vega-embed.min.js"]


@dataclass
class Stat:
    """One headline number in a section's stat row."""

    label: str
    value: str
    unit: str = ""
    note: str = ""  # e.g. "+3 ms vs first fortnight"


@dataclass
class Table:
    columns: list[str]
    rows: list[list[Any]]


@dataclass
class Figure:
    key: str  # stable id, e.g. "hrv"
    title: str
    spec: dict[str, Any]
    number: str = ""  # e.g. "3.3"; assigned by the report that shows the figure
    caption: str = ""  # one line under the title: what is plotted
    why: str = ""  # why this signal matters for mental health and wellbeing
    how_to_read: str = ""  # how to read the chart
    commentary: str = ""  # observations for this period (LLM or placeholder)
    table: Table | None = None  # accessible data view
    headline: list[Stat] = field(default_factory=list)  # key estimates shown above the chart


@dataclass
class Section:
    number: int
    title: str
    intro: str = ""
    stats: list[Stat] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    notes: list[tuple[str, str]] = field(default_factory=list)  # (heading, text) blocks

    @property
    def anchor(self) -> str:
        return f"section-{self.number}"


@dataclass
class Report:
    title: str  # period label, e.g. "2026-Q1"
    start: date_type
    end: date_type
    sections: list[Section]
    kind: str = "Personal report"
    synthetic: bool = False  # demo data: shows a banner and marks the file
    persona: str | None = None
    generated: datetime = field(default_factory=datetime.now)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (figure, reason); not rendered


@cache
def _font_css() -> str:
    faces = []
    for family, weight, filename in _FONTS:
        data = base64.b64encode((_STATIC / "fonts" / filename).read_bytes()).decode()
        faces.append(
            "@font-face{"
            f"font-family:'{family}';font-style:normal;font-weight:{weight};"
            "font-display:swap;"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}"
        )
    return "\n".join(faces)


@cache
def _vendor_js() -> str:
    return "\n;\n".join((_STATIC / "vendor" / name).read_text(encoding="utf-8") for name in _VENDOR)


def _env() -> Environment:
    env = Environment(
        loader=PackageLoader("egon.report", "templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["paragraphs"] = lambda text: [p.strip() for p in text.split("\n\n") if p.strip()]
    return env


def _script_json(obj: Any) -> str:
    """JSON safe to embed inside a <script> element."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")


def render_report(report: Report) -> str:
    specs = {fig.key: fig.spec for sec in report.sections for fig in sec.figures}
    template = _env().get_template("report.html.j2")
    return template.render(
        report=report,
        font_css=_font_css(),
        css=(_STATIC / "report.css").read_text(encoding="utf-8"),
        js=(_STATIC / "report.js").read_text(encoding="utf-8"),
        vendor_js=_vendor_js(),
        specs_json=_script_json(specs),
        dark_map_json=_script_json(theme.DARK_MAP),
    )


def write_report(report: Report, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(report), encoding="utf-8")
    return output_path


def single_figure_report(
    figure: Figure,
    *,
    label: str,
    start: date_type,
    end: date_type,
    stats: list[Stat] | None = None,
) -> Report:
    """Wrap one figure in a minimal report (used by the ``report-*`` commands)."""
    section = Section(number=1, title=figure.title, stats=stats or [], figures=[figure])
    return Report(title=label, start=start, end=end, sections=[section], kind=figure.title)
