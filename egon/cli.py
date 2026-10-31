"""
CLI entry point for egon-journal.

Run via:  uv run egon <command>
"""

import contextlib
import io
import os
import re
import subprocess
import sys
import time
from datetime import date as date_type
from pathlib import Path
from typing import NamedTuple, Optional

import typer
import yaml
from dotenv import load_dotenv

from egon.analytics.loader import load_journal_entries
from egon.analytics.word_count import (
    filter_entries,
    last_complete_period,
    parse_period_value,
    period_bounds,
    period_label,
    word_counts_by_day,
)
from egon.config import load_local_llm_config
from egon.health.apple_health import (
    daily_mean,
    daily_sum,
    filter_by_date,
    infer_unit,
    load_records,
)
from egon.health.sleep import filter_sleep_by_date, load_sleep_onset, load_sleep_records
from egon.limbic.sentiment import sentiment_by_day
from egon.linker import index_graph, inject_wikilinks, load_topics
from egon.local_llm import DEFAULT_MODEL, check_hardware, ensure_model, generate_journal_prompt
from egon.node_types.journal_entry import generate_journal_entry
from egon.node_types.program import (
    generate_program as _generate_program,
)
from egon.node_types.program import (
    generate_programs_from_dir,
    load_program_yaml,
)
from egon.node_types.prompt import generate_prompts_from_dir
from egon.node_types.summary import generate_monthly_summary, generate_weekly_summary
from egon.report import figures
from egon.report.html import Figure, Report, Section, Stat, single_figure_report, write_report
from egon.schema import validate as _validate_frontmatter

load_dotenv()

app = typer.Typer(
    name="egon",
    help="egon-journal: structured journaling for the Egon graph.",
    no_args_is_help=True,
)

_REPO_ROOT = Path(__file__).parent.parent
_CONTENT_DIR = _REPO_ROOT / "content"
_GENERATED_DIR = _REPO_ROOT / "generated"


# ---------------------------------------------------------------------------
# Output directory helpers
# ---------------------------------------------------------------------------


def _resolve_output(cli_output: Optional[Path], env_var: str) -> Path:
    if cli_output:
        return cli_output
    env_dir = os.environ.get(env_var)
    if env_dir:
        return Path(env_dir)
    return _GENERATED_DIR


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def new_entry(
    date: Optional[str] = typer.Option(None, help="Entry date as YYYY-MM-DD (default: today)"),
    open: bool = typer.Option(False, "--open", help="Open the file in $EDITOR after creating"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Create a journal entry for today (or a given date)."""
    entry_date = date_type.fromisoformat(date) if date else date_type.today()
    out_dir = _resolve_output(output, "EGON_JOURNAL_DIR")
    path = generate_journal_entry(entry_date, out_dir)
    typer.echo(f"Created: {path}")
    if open:
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(path)])


@app.command()
def new_summary(
    period: str = typer.Option(..., help="'week' or 'month'"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Create a weekly or monthly summary template for the current period."""
    today = date_type.today()
    out_dir = _resolve_output(output, "EGON_SUMMARIES_DIR")
    if period == "week":
        path = generate_weekly_summary(today, out_dir)
    elif period == "month":
        path = generate_monthly_summary(today, out_dir)
    else:
        typer.echo(f"Error: --period must be 'week' or 'month', got '{period}'", err=True)
        raise typer.Exit(1)
    typer.echo(f"Created: {path}")


@app.command()
def generate_prompts(
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Generate all prompt nodes from YAML source files in content/prompts/."""
    prompts_dir = _CONTENT_DIR / "prompts"
    if not prompts_dir.exists():
        typer.echo(f"Error: prompts directory not found: {prompts_dir}", err=True)
        raise typer.Exit(1)
    out_dir = _resolve_output(output, "EGON_GRAPH_DIR")
    paths = generate_prompts_from_dir(prompts_dir, date_type.today(), out_dir)
    for p in paths:
        typer.echo(f"Generated: {p}")
    typer.echo(f"Done. {len(paths)} prompt(s) generated.")


@app.command(name="generate-program")
def generate_program(
    name: str = typer.Option(..., "--name", help="Program title (must match YAML 'title' field)"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Generate all nodes for a specific program by title."""
    programs_dir = _CONTENT_DIR / "programs"
    source = _find_program(programs_dir, name)
    if source is None:
        typer.echo(f"Error: no program found with title '{name}'", err=True)
        raise typer.Exit(1)
    out_dir = _resolve_output(output, "EGON_GRAPH_DIR")
    paths = _generate_program(source, date_type.today(), out_dir)
    for p in paths:
        typer.echo(f"Generated: {p}")
    typer.echo(f"Done. {len(paths)} node(s) generated.")


@app.command()
def generate_all_programs(
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Generate all program nodes from YAML source files in content/programs/."""
    programs_dir = _CONTENT_DIR / "programs"
    if not programs_dir.exists():
        typer.echo(f"Error: programs directory not found: {programs_dir}", err=True)
        raise typer.Exit(1)
    out_dir = _resolve_output(output, "EGON_GRAPH_DIR")
    paths = generate_programs_from_dir(programs_dir, date_type.today(), out_dir)
    for p in paths:
        typer.echo(f"Generated: {p}")
    typer.echo(f"Done. {len(paths)} node(s) generated.")


@app.command()
def list_programs() -> None:
    """List available programs from YAML source files."""
    programs_dir = _CONTENT_DIR / "programs"
    if not programs_dir.exists():
        typer.echo("No programs directory found.")
        return
    found = False
    for yaml_path in sorted(programs_dir.glob("*.yaml")):
        source = load_program_yaml(yaml_path)
        title = source.get("title", yaml_path.stem)
        duration = source.get("duration_days", "?")
        typer.echo(f"  {title} ({duration} days)")
        found = True
    if not found:
        typer.echo("No programs found.")


@app.command(name="validate")
def validate_nodes(
    path: Path = typer.Option(..., "--path", help="File or directory to validate"),
) -> None:
    """Validate the frontmatter of Egon Markdown nodes."""
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = sorted(path.rglob("*.md"))
    else:
        typer.echo(f"Error: path does not exist: {path}", err=True)
        raise typer.Exit(1)

    total = 0
    invalid = 0
    for md_file in files:
        content = md_file.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError as exc:
            typer.echo(f"YAML ERROR: {md_file}\n  {exc}", err=True)
            invalid += 1
            continue
        if not isinstance(fm, dict):
            continue
        total += 1
        errors = _validate_frontmatter(fm)
        if errors:
            invalid += 1
            typer.echo(f"INVALID: {md_file}")
            for err in errors:
                typer.echo(f"  - {err}")
        else:
            typer.echo(f"OK: {md_file}")

    if invalid:
        typer.echo(f"\n{invalid} file(s) with errors.", err=True)
        raise typer.Exit(1)
    else:
        typer.echo(f"\nAll {total} node(s) valid.")


@app.command(name="index")
def index_cmd(
    graph_dir: Path = typer.Option(..., "--graph-dir", help="Path to the Egon graph directory"),
) -> None:
    """Output all node titles in a graph directory (one per line, suitable for TOPICS.txt)."""
    if not graph_dir.is_dir():
        typer.echo(f"Error: directory not found: {graph_dir}", err=True)
        raise typer.Exit(1)
    for title in index_graph(graph_dir):
        typer.echo(title)


@app.command()
def link(
    file: Path = typer.Argument(..., help="Markdown file to inject wikilinks into"),
    topics_file: Path = typer.Option(Path("TOPICS.txt"), "--topics", help="Path to TOPICS.txt"),
) -> None:
    """Inject wikilinks into a Markdown file based on TOPICS.txt."""
    if not file.is_file():
        typer.echo(f"Error: file not found: {file}", err=True)
        raise typer.Exit(1)
    topics = load_topics(topics_file)
    if not topics:
        typer.echo("No topics found. Run 'egon index --graph-dir <dir> > TOPICS.txt' first.")
        raise typer.Exit(1)

    content = file.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) == 3:
            new_body = inject_wikilinks(parts[2], topics)
            file.write_text(f"---{parts[1]}---{new_body}", encoding="utf-8")
            typer.echo(f"Linked: {file}")
            return

    file.write_text(inject_wikilinks(content, topics), encoding="utf-8")
    typer.echo(f"Linked: {file}")


@app.command(name="export-context")
def export_context(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    months: int = typer.Option(
        3,
        "--months",
        help="Number of months to aggregate (counting back from today)",
        min=1,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output file path (default: print to stdout)",
    ),
) -> None:
    """Aggregate journal entries into a single Markdown file for use as LLM context."""
    import calendar

    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    today = date_type.today()
    raw_month = today.month - months
    start_year = today.year + raw_month // 12
    start_month = raw_month % 12
    if start_month == 0:
        start_month = 12
        start_year -= 1
    max_day = calendar.monthrange(start_year, start_month)[1]
    start = date_type(start_year, start_month, min(today.day, max_day))

    all_entries = load_journal_entries(resolved_dir)
    entries = filter_entries(all_entries, start, today)

    if not entries:
        typer.echo(f"No journal entries found between {start} and {today}.", err=True)
        raise typer.Exit(1)

    header = (
        f"# Journal context — {start} to {today} ({months} month{'s' if months != 1 else ''})\n"
    )
    parts = [header]
    for entry in entries:
        parts.append(f"\n## {entry.date}\n")
        parts.append(entry.body.strip())
        parts.append("\n\n---")
    parts.append("\n")
    content = "\n".join(parts)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        typer.echo(f"Exported {len(entries)} entries to: {output}")
    else:
        typer.echo(content)


@app.command(name="suggest-prompt")
def suggest_prompt(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    months: int = typer.Option(
        3,
        "--months",
        help="Number of months of entries to use as context",
        min=1,
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help=f"Ollama model to use (default: from egon.toml or {DEFAULT_MODEL})",
    ),
) -> None:
    """Generate a journaling prompt for today using a local LLM via Ollama."""
    import calendar

    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    today = date_type.today()
    raw_month = today.month - months
    start_year = today.year + raw_month // 12
    start_month = raw_month % 12
    if start_month == 0:
        start_month = 12
        start_year -= 1
    max_day = calendar.monthrange(start_year, start_month)[1]
    start = date_type(start_year, start_month, min(today.day, max_day))

    all_entries = load_journal_entries(resolved_dir)
    entries = filter_entries(all_entries, start, today)
    if not entries:
        typer.echo(f"No journal entries found between {start} and {today}.", err=True)
        raise typer.Exit(1)

    resolved_model = model or load_local_llm_config().model
    typer.echo(f"Using model: {resolved_model}")
    typer.echo("🔒 All inference runs locally — no data is sent to any external service.")
    typer.echo(check_hardware(resolved_model))
    typer.echo(f"Loaded {len(entries)} entries ({start} → {today})")

    import time

    try:
        ensure_model(resolved_model)
        typer.echo("Generating prompt…")
        _t0 = time.perf_counter()
        question = generate_journal_prompt(entries, resolved_model)
        elapsed = time.perf_counter() - _t0
    except ImportError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"\n{question}\n")
    typer.echo(f"({elapsed:.1f}s)", err=True)


@app.command(name="report-word-count")
def report_word_count(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/word_count/<period-label>.html)",
    ),
) -> None:
    """Chart journal word count by day as an HTML report."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    if not all_entries:
        typer.echo(f"No journal entries found in: {resolved_dir}", err=True)
        raise typer.Exit(1)

    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{period}' ({label}).", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/word_count/{label}.html")

    typer.echo(f"Found {len(entries)} journal entries for {label}.")
    _save_figure(
        figures.word_count_figure(word_counts_by_day(entries)), resolved_output, label, start, end
    )


@app.command(name="report-sentiment")
def report_sentiment(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/sentiment/<period-label>.html)",
    ),
) -> None:
    """Chart VADER sentiment by day as an HTML report."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    if not all_entries:
        typer.echo(f"No journal entries found in: {resolved_dir}", err=True)
        raise typer.Exit(1)

    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/sentiment/{label}.html")

    typer.echo(f"Found {len(entries)} journal entries for {label}.")
    _save_figure(
        figures.sentiment_figure(sentiment_by_day(entries)), resolved_output, label, start, end
    )


@app.command(name="report-wordcloud")
def report_wordcloud(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/wordcloud/<period-label>.html)",
    ),
) -> None:
    """Rank the most frequent meaningful words in journal entries (HTML report)."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    if not all_entries:
        typer.echo(f"No journal entries found in: {resolved_dir}", err=True)
        raise typer.Exit(1)

    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/wordcloud/{label}.html")

    from egon.analytics.words import frequent_words

    typer.echo(f"Found {len(entries)} journal entries for {label}.")
    _save_figure(
        figures.frequent_words_figure(frequent_words(entries)), resolved_output, label, start, end
    )


@app.command(name="report-bigfive")
def report_bigfive(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/bigfive/<period-label>.html)",
    ),
) -> None:
    """Plot Big Five personality trait scores from journal entries (requires --extra limbic)."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    if not all_entries:
        typer.echo(f"No journal entries found in: {resolved_dir}", err=True)
        raise typer.Exit(1)

    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    data = _model_scores("bigfive", entries, label)

    resolved_output = output or Path(f"reports/bigfive/{label}.html")
    _save_figure(figures.bigfive_figure(data), resolved_output, label, start, end)


@app.command(name="report-mbti")
def report_mbti(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/mbti/<period-label>.html)",
    ),
) -> None:
    """Plot MBTI personality dimension scores from journal entries (requires --extra limbic)."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    if not all_entries:
        typer.echo(f"No journal entries found in: {resolved_dir}", err=True)
        raise typer.Exit(1)

    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    data = _model_scores("mbti", entries, label)

    resolved_output = output or Path(f"reports/mbti/{label}.html")
    _save_figure(figures.mbti_figure(data), resolved_output, label, start, end)


# ---------------------------------------------------------------------------
# Health reports
# ---------------------------------------------------------------------------


def _model_scores(name: str, entries: list, label: str) -> list:
    """Model scores for *entries*, from the shared per-period cache when available."""
    from egon.report.data import SCORE_CACHE_ROOT, cached_scores, scorers

    typer.echo(f"Found {len(entries)} journal entries for {label}.")
    scores, status = cached_scores(name, scorers()[name], entries, SCORE_CACHE_ROOT / label)
    if scores is None:
        typer.echo(f"Error: {name} model {status}", err=True)
        raise typer.Exit(1)
    if status == "cached":
        typer.echo(f"Using cached {name} scores ({SCORE_CACHE_ROOT / label}).")
    return scores


def _require_html(output: Path) -> None:
    if output.suffix.lower() not in {".html", ".htm"}:
        typer.echo(
            f"Error: reports are written as HTML; got '{output.suffix}'. "
            "Use an .html path — and print or 'Save as PDF' from your browser for a PDF.",
            err=True,
        )
        raise typer.Exit(1)


def _save_figure(
    figure: Figure,
    output: Path,
    label: str,
    start: date_type,
    end: date_type,
    stats: list[Stat] | None = None,
) -> None:
    """Write one figure as a standalone HTML report."""
    _require_html(output)
    report = single_figure_report(figure, label=label, start=start, end=end, stats=stats)
    write_report(report, output)
    typer.echo(f"Saved: {output}")


def _save_section(
    title: str,
    section_figures: list[Figure],
    output: Path,
    label: str,
    start: date_type,
    end: date_type,
) -> None:
    """Write several related figures as one HTML report."""
    _require_html(output)
    for i, fig in enumerate(section_figures, start=1):
        fig.number = str(i)
    section = Section(number=1, title=title, figures=section_figures)
    write_report(Report(title=label, start=start, end=end, sections=[section], kind=title), output)
    typer.echo(f"Saved: {output}")


class _StepResult(NamedTuple):
    name: str
    status: str  # "ok" | "skipped" | "failed"
    path: str | None
    detail: str


_FOUND_RE = re.compile(r"Found (\d[\d,]*) (journal entries|days|nights)")
_SIGNALS_RE = re.compile(r"across (\d+) signals")


def _one_line(exc: BaseException) -> str:
    """The message of *exc* plus its follow-up hint line, on one line."""
    lines = [ln.strip() for ln in str(exc).strip().splitlines() if ln.strip()]
    return " ".join(lines[:2]) if lines else type(exc).__name__


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(round(seconds), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def _print_report_header(
    label: str,
    start: date_type,
    end: date_type,
    journal_dir: Path,
    entries: list,
    xml: Path | None,
) -> None:
    typer.echo(f"Egon reports · {label} ({start:%-d %B %Y} – {end:%-d %B %Y})")
    if journal_dir.is_dir():
        typer.echo(f"  Journal       {len(entries)} entries in this period · {journal_dir}")
    else:
        typer.echo(f"  Journal       not found ({journal_dir}) — set EGON_JOURNAL_DIR")
    if xml and xml.is_file():
        size_mb = xml.stat().st_size / 1_000_000
        size = f"{size_mb:,.0f} MB" if size_mb >= 1 else "<1 MB"
        typer.echo(f"  Apple Health  {xml.name} ({size}, parsed once)")
    else:
        typer.echo("  Apple Health  not configured — set EGON_APPLE_HEALTH_XML for health reports")
    typer.echo("  Output        reports/ (HTML, works offline · contains your personal data)")


def _run_report_step(name: str, fn) -> _StepResult:
    """Run one report command quietly and print a one-line result."""
    live = sys.stdout.isatty()
    if live:  # show what is running; the result line overwrites it
        typer.echo(f"  … {name:<20}", nl=False)
    out, err = io.StringIO(), io.StringIO()
    started = time.monotonic()
    status = "ok"
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            fn()
    except typer.Exit:
        status = "skipped"
    except ImportError as exc:  # an optional extra isn't installed: skip, don't fail
        status = "skipped"
        err.write(f"Error: {_one_line(exc)}\n")
    except Exception as exc:
        status = "failed"
        err.write(f"Error: {_one_line(exc)}\n")
    elapsed = time.monotonic() - started

    cr = "\r" if live else ""
    text = out.getvalue()
    saved = re.findall(r"Saved: (.+)", text)
    path = saved[-1].strip() if saved else None
    if m := _FOUND_RE.search(text):
        unit = "entries" if m.group(2) == "journal entries" else m.group(2)
        detail = f"{m.group(1)} {unit}"
    elif m := _SIGNALS_RE.search(text):
        detail = f"{m.group(1)} signals"
    else:
        detail = ""

    if status == "ok":
        timing = f"  ({_fmt_duration(elapsed)})" if elapsed >= 5 else ""
        typer.echo(f"{cr}  ✓ {name:<20}{detail:<14}{path or ''}{timing}")
    else:
        err_lines = [ln.strip() for ln in err.getvalue().splitlines() if ln.strip()]
        out_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        lines = err_lines or out_lines
        reason = lines[-1].removeprefix("Error: ") if lines else "no output"
        mark = "–" if status == "skipped" else "✗"
        typer.echo(f"{cr}  {mark} {name:<20}{reason}")
    return _StepResult(name, status, path, detail)


def _run_full_report(
    entries: list,
    xml: Path | None,
    start: date_type,
    end: date_type,
    label: str,
    full_output: Path,
) -> str | None:
    def _parse_target(env_key: str) -> float | None:
        raw = os.getenv(env_key, "").strip()
        try:
            return float(raw) if raw else None
        except ValueError:
            return None

    from egon.config import load_report_config
    from egon.full_report import generate_full_report

    started = time.monotonic()
    try:
        report = generate_full_report(
            journal_entries=entries,
            xml_path=xml,
            start=start,
            end=end,
            label=label,
            target_body_mass=_parse_target("EGON_TARGET_BODY_MASS"),
            target_lean_body_mass=_parse_target("EGON_TARGET_LEAN_BODY_MASS"),
            target_resting_heart_rate=_parse_target("EGON_TARGET_RESTING_HEART_RATE"),
            target_exercise_minutes=_parse_target("EGON_TARGET_EXERCISE_MINUTES"),
            output_path=full_output,
            config=load_report_config(),
        )
    except Exception as exc:
        typer.echo(f"  ✗ full report failed: {exc}", err=True)
        return None

    sections = [s for s in report.sections if s.figures]
    n_figures = sum(len(s.figures) for s in sections)
    typer.echo(
        f"  ✓ {n_figures} figures in {len(sections)} sections · {full_output}"
        f"  ({_fmt_duration(time.monotonic() - started)})"
    )
    for name, reason in report.skipped:
        typer.echo(f"  – {name:<20}{reason}")
    return str(full_output)


def _resolve_apple_health_xml(cli_path: Optional[Path]) -> Optional[Path]:
    if cli_path:
        return cli_path
    env_val = os.environ.get("EGON_APPLE_HEALTH_XML")
    return Path(env_val) if env_val else None


def _load_and_report(xml_path: Path) -> dict:
    """Parse export.xml and print the available metric names."""
    typer.echo(f"Parsing {xml_path.name} ...")
    records = load_records(xml_path)
    metrics = sorted(records.keys())
    typer.echo(f"Found {len(metrics)} metric(s): {', '.join(metrics)}")
    return records


@app.command(name="report-weight")
def report_weight(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/weight/<period-label>.html)",
    ),
) -> None:
    """Plot daily mean weight from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    weight_records = records.get("BodyMass", [])
    if not weight_records:
        typer.echo("Error: no BodyMass records found in export.", err=True)
        raise typer.Exit(1)

    unit = infer_unit(weight_records)
    data = filter_by_date(daily_mean(weight_records), start, end)
    if not data:
        typer.echo(f"No weight data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    lean_records = records.get("LeanBodyMass", [])
    lean_data = filter_by_date(daily_mean(lean_records), start, end) if lean_records else None
    if lean_data:
        typer.echo(f"Found {len(lean_data)} days of lean body mass data for {label}.")

    def _parse_target(env_key: str) -> float | None:
        raw = os.getenv(env_key, "").strip()
        try:
            return float(raw) if raw else None
        except ValueError:
            typer.echo(f"Warning: {env_key}={raw!r} is not a valid number — ignoring.", err=True)
            return None

    target_body_mass = _parse_target("EGON_TARGET_BODY_MASS")
    target_lean_body_mass = _parse_target("EGON_TARGET_LEAN_BODY_MASS")

    resolved_output = output or Path(f"reports/weight/{label}.html")

    typer.echo(f"Found {len(data)} days of weight data for {label}.")
    figure = figures.weight_figure(
        data,
        unit=unit,
        lean_data=lean_data,
        target=target_body_mass,
        lean_target=target_lean_body_mass,
    )
    _save_figure(figure, resolved_output, label, start, end)


@app.command(name="report-resting-heart-rate")
def report_resting_heart_rate(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/resting_heart_rate/<period-label>.html)",
    ),
) -> None:
    """Plot daily mean resting heart rate from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    rhr_records = records.get("RestingHeartRate", [])
    if not rhr_records:
        typer.echo("Error: no RestingHeartRate records found in export.", err=True)
        raise typer.Exit(1)

    unit = infer_unit(rhr_records)
    data = filter_by_date(daily_mean(rhr_records), start, end)
    if not data:
        typer.echo(f"No resting heart rate data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/resting_heart_rate/{label}.html")

    def _parse_target(env_key: str) -> float | None:
        raw = os.getenv(env_key, "").strip()
        try:
            return float(raw) if raw else None
        except ValueError:
            typer.echo(f"Warning: {env_key}={raw!r} is not a valid number — ignoring.", err=True)
            return None

    typer.echo(f"Found {len(data)} days of resting heart rate data for {label}.")
    figure = figures.resting_heart_rate_figure(
        data, unit=unit, target=_parse_target("EGON_TARGET_RESTING_HEART_RATE")
    )
    _save_figure(figure, resolved_output, label, start, end)


@app.command(name="report-hrv")
def report_hrv(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/hrv/<period-label>.html)",
    ),
) -> None:
    """Plot daily mean heart rate variability (HRV SDNN) from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    hrv_records = records.get("HeartRateVariabilitySDNN", [])
    if not hrv_records:
        typer.echo("Error: no HeartRateVariabilitySDNN records found in export.", err=True)
        raise typer.Exit(1)

    unit = infer_unit(hrv_records)
    data = filter_by_date(daily_mean(hrv_records), start, end)
    if not data:
        typer.echo(f"No HRV data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/hrv/{label}.html")

    typer.echo(f"Found {len(data)} days of HRV data for {label}.")
    _save_figure(
        figures.hrv_figure(data, unit=unit),
        resolved_output,
        label,
        start,
        end,
        stats=figures.hrv_stats(data, unit),
    )


@app.command(name="report-sleep")
def report_sleep(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/sleep/<period-label>.html)",
    ),
) -> None:
    """Plot nightly hours asleep from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Parsing {resolved_xml.name} ...")
    all_data = load_sleep_records(resolved_xml)
    if not all_data:
        typer.echo("Error: no SleepAnalysis records found in export.", err=True)
        raise typer.Exit(1)

    data = filter_sleep_by_date(all_data, start, end)
    if not data:
        typer.echo(f"No sleep data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    all_onset = load_sleep_onset(resolved_xml)
    onset_data = filter_sleep_by_date(all_onset, start, end) or None

    resolved_output = output or Path(f"reports/sleep/{label}.html")

    typer.echo(f"Found {len(data)} nights of sleep data for {label}.")
    _save_figure(figures.sleep_figure(data, onset_data), resolved_output, label, start, end)


@app.command(name="report-step-count")
def report_step_count(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/step_count/<period-label>.html)",
    ),
) -> None:
    """Plot daily step count from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    step_records = records.get("StepCount", [])
    if not step_records:
        typer.echo("Error: no StepCount records found in export.", err=True)
        raise typer.Exit(1)

    data = filter_by_date(daily_sum(step_records), start, end)
    if not data:
        typer.echo(f"No step count data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/step_count/{label}.html")

    typer.echo(f"Found {len(data)} days of step count data for {label}.")
    _save_figure(figures.step_count_figure(data), resolved_output, label, start, end)


@app.command(name="report-vo2max")
def report_vo2max(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/vo2max/<period-label>.html)",
    ),
) -> None:
    """Plot daily mean VO2 max from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    vo2max_records = records.get("VO2Max", [])
    if not vo2max_records:
        typer.echo("Error: no VO2Max records found in export.", err=True)
        raise typer.Exit(1)

    unit = infer_unit(vo2max_records)
    data = filter_by_date(daily_mean(vo2max_records), start, end)
    if not data:
        typer.echo(f"No VO2 max data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/vo2max/{label}.html")

    typer.echo(f"Found {len(data)} days of VO2 max data for {label}.")
    _save_figure(figures.vo2max_figure(data, unit=unit), resolved_output, label, start, end)


@app.command(name="report-topics")
def report_topics(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Output directory (default: reports/topics)",
    ),
) -> None:
    """Discover journal topics (BERTopic) and save a summary and timeline as HTML."""
    from egon.analytics.topics import fit_topics, topic_summary, topic_timeline

    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(f"Error: journal directory not found: {resolved_dir}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    out_dir = output_dir or Path("reports/topics")

    try:
        topic_ids, _docs, model = fit_topics(entries)
        summary = topic_summary(model)
    except (ImportError, ValueError) as exc:
        typer.echo(f"Error: {_one_line(exc)}", err=True)
        raise typer.Exit(1)
    section_figures = [figures.topic_summary_figure(summary)]
    try:
        timeline = topic_timeline(entries, topic_ids, model)
        section_figures.append(figures.topic_timeline_figure(timeline, summary))
    except ValueError as exc:
        typer.echo(f"Skipping timeline: {exc}")
    _save_section("Recurring themes", section_figures, out_dir / f"{label}.html", label, start, end)


@app.command(name="report-exercise")
def report_exercise(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/exercise/<period-label>.html)",
    ),
) -> None:
    """Plot daily Apple Exercise Time from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    exercise_recs = records.get("AppleExerciseTime", [])
    if not exercise_recs:
        typer.echo("Error: no AppleExerciseTime records found in export.", err=True)
        raise typer.Exit(1)

    data = filter_by_date(daily_sum(exercise_recs), start, end)
    if not data:
        typer.echo(f"No exercise data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    def _parse_target(env_key: str) -> float | None:
        raw = os.getenv(env_key, "").strip()
        try:
            return float(raw) if raw else None
        except ValueError:
            typer.echo(f"Warning: {env_key}={raw!r} is not a valid number — ignoring.", err=True)
            return None

    resolved_output = output or Path(f"reports/exercise/{label}.html")

    typer.echo(f"Found {len(data)} days of exercise data for {label}.")
    figure = figures.exercise_figure(data, target=_parse_target("EGON_TARGET_EXERCISE_MINUTES"))
    _save_figure(figure, resolved_output, label, start, end)


@app.command(name="report-emotion")
def report_emotion(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/emotion/<period-label>.html)",
    ),
) -> None:
    """Plot daily emotion profile from journal entries (anger/fear/joy/sadness etc.)."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(f"Error: journal directory not found: {resolved_dir}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    data = _model_scores("emotion", entries, label)

    resolved_output = output or Path(f"reports/emotion/{label}.html")

    _save_figure(figures.emotion_figure(data), resolved_output, label, start, end)


@app.command(name="report-stress")
def report_stress(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/stress/<period-label>.html)",
    ),
) -> None:
    """Plot psychological stress signal from journal entries (requires --extra limbic)."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    data = _model_scores("stress", entries, label)

    resolved_output = output or Path(f"reports/stress/{label}.html")

    _save_figure(figures.stress_figure(data), resolved_output, label, start, end)


@app.command(name="report-loneliness")
def report_loneliness(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/loneliness/<period-label>.html)",
    ),
) -> None:
    """Plot loneliness signal from journal entries (requires --extra limbic)."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    data = _model_scores("loneliness", entries, label)

    resolved_output = output or Path(f"reports/loneliness/{label}.html")

    _save_figure(figures.loneliness_figure(data), resolved_output, label, start, end)


@app.command(name="report-cognitive-bias")
def report_cognitive_bias(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output HTML path (default: reports/cognitive_bias/<period-label>.html)",
    ),
) -> None:
    """Plot cognitive bias profile from journal entries (requires --extra limbic)."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    data = _model_scores("cognitive_bias", entries, label)

    resolved_output = output or Path(f"reports/cognitive_bias/{label}.html")

    _save_figure(figures.cognitive_bias_figure(data), resolved_output, label, start, end)


@app.command(name="report-correlations")
def report_correlations(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Output directory (default: reports/correlations)",
    ),
) -> None:
    """Correlate all available journal and health signals; save the analysis as HTML."""
    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    out_dir = output_dir or Path("reports/correlations")

    # --- Journal entries ---
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    entries: list = []
    if resolved_dir.is_dir():
        from egon.analytics.word_count import filter_entries

        all_entries = load_journal_entries(resolved_dir)
        entries = filter_entries(all_entries, start, end)

    # --- Health records ---
    from egon.report.data import build_signals, health_series

    resolved_xml = _resolve_apple_health_xml(xml_path)
    health_records: dict = {}
    sleep_hours: list = []
    sleep_onset: list = []
    if resolved_xml and resolved_xml.is_file():
        health_records = _load_and_report(resolved_xml)
        try:
            sleep_hours = filter_sleep_by_date(load_sleep_records(resolved_xml), start, end)
            sleep_onset = filter_sleep_by_date(load_sleep_onset(resolved_xml), start, end)
        except Exception:
            pass

    # --- Build signals ---
    signals = build_signals(
        journal_entries=entries,
        health=health_series(health_records, start, end),
        sleep_hours=sleep_hours,
        sleep_onset=sleep_onset,
    )

    if len(signals) < 2:
        typer.echo("Error: fewer than 2 signals available — nothing to correlate.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Computing correlations across {len(signals)} signals for {label}.")

    from egon.config import load_report_config

    cfg = load_report_config()
    try:
        section_figures = [figures.correlation_matrix_figure(signals)]
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    for name, build in [
        (
            "top pairs",
            lambda: figures.top_pairs_figure(signals, cfg.excluded_correlation_pairs),
        ),
        ("highlighted pairs", lambda: figures.highlighted_correlations_figure(signals)),
    ]:
        try:
            section_figures.append(build())
        except ValueError as exc:
            typer.echo(f"Skipping {name}: {exc}")
    _save_section(
        "Cross-signal correlations", section_figures, out_dir / f"{label}.html", label, start, end
    )


@app.command(name="health-summary")
def health_summary(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "month",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help=f"Ollama model to use (default: from egon.toml or {DEFAULT_MODEL})",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Write the summary as Markdown to this path instead of stdout",
    ),
    stats_only: bool = typer.Option(
        False,
        "--stats-only",
        help="Print the computed statistics block and exit without calling the LLM",
    ),
) -> None:
    """Summarize Apple Health data for a period using a local LLM via Ollama."""
    from egon.health.llm_summary import (
        build_health_stats,
        format_health_stats,
        generate_health_summary,
    )

    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml or not resolved_xml.is_file():
        typer.echo(
            "Error: Apple Health export.xml not found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)
    stats = build_health_stats(records, resolved_xml, start, end)
    if not stats:
        typer.echo(f"No health data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    stats_text = format_health_stats(stats, label, start, end)

    if stats_only:
        typer.echo(stats_text)
        return

    resolved_model = model or load_local_llm_config().model
    typer.echo(f"Using model: {resolved_model}")
    typer.echo("🔒 All inference runs locally — no data is sent to any external service.")
    typer.echo(check_hardware(resolved_model))
    typer.echo(f"Found data for {len(stats)} metric(s) ({start} → {end})")

    import time

    try:
        ensure_model(resolved_model)
        typer.echo("Generating summary…")
        _t0 = time.perf_counter()
        summary = generate_health_summary(stats_text, resolved_model)
        elapsed = time.perf_counter() - _t0
    except (ImportError, RuntimeError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    if output:
        markdown = f"# Health Summary — {label}\n\n{summary}\n\n---\n\n{stats_text}\n"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
        typer.echo(f"Saved: {output}")
    else:
        typer.echo(f"\n{summary}\n")
    typer.echo(f"({elapsed:.1f}s)", err=True)


@app.command(name="report")
def report_all(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files (default: $EGON_JOURNAL_DIR)",
    ),
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. Overrides --period.",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Also compile all figures into one combined HTML report.",
    ),
) -> None:
    """Generate all reports for the given period."""
    _kw = dict(period=period, for_period=for_period, output=None)
    _journal_reports = [
        ("word-count", lambda: report_word_count(journal_dir=journal_dir, **_kw)),
        ("sentiment", lambda: report_sentiment(journal_dir=journal_dir, **_kw)),
        ("stress", lambda: report_stress(journal_dir=journal_dir, **_kw)),
        ("loneliness", lambda: report_loneliness(journal_dir=journal_dir, **_kw)),
        ("wordcloud", lambda: report_wordcloud(journal_dir=journal_dir, **_kw)),
        ("bigfive", lambda: report_bigfive(journal_dir=journal_dir, **_kw)),
        ("mbti", lambda: report_mbti(journal_dir=journal_dir, **_kw)),
        ("emotion", lambda: report_emotion(journal_dir=journal_dir, **_kw)),
        ("cognitive-bias", lambda: report_cognitive_bias(journal_dir=journal_dir, **_kw)),
        (
            "topics",
            lambda: report_topics(
                journal_dir=journal_dir,
                period=period,
                for_period=for_period,
                output_dir=None,
            ),
        ),
    ]
    _hkw = dict(period=period, for_period=for_period, output=None)
    _health_reports = [
        ("weight", lambda: report_weight(xml_path=xml_path, **_hkw)),
        ("resting-heart-rate", lambda: report_resting_heart_rate(xml_path=xml_path, **_hkw)),
        ("hrv", lambda: report_hrv(xml_path=xml_path, **_hkw)),
        ("sleep", lambda: report_sleep(xml_path=xml_path, **_hkw)),
        ("step-count", lambda: report_step_count(xml_path=xml_path, **_hkw)),
        ("vo2max", lambda: report_vo2max(xml_path=xml_path, **_hkw)),
        ("exercise", lambda: report_exercise(xml_path=xml_path, **_hkw)),
        (
            "correlations",
            lambda: report_correlations(
                journal_dir=journal_dir,
                xml_path=xml_path,
                period=period,
                for_period=for_period,
                output_dir=None,
            ),
        ),
    ]

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            _ref = last_complete_period(period, date_type.today())
            start, end = period_bounds(period, _ref)
            label = period_label(period, _ref)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    entries: list = []
    if resolved_dir.is_dir():
        entries = filter_entries(load_journal_entries(resolved_dir), start, end)
    resolved_xml = _resolve_apple_health_xml(xml_path)

    started = time.monotonic()
    _print_report_header(label, start, end, resolved_dir, entries, resolved_xml)

    results: list[_StepResult] = []
    have_health = bool(resolved_xml and resolved_xml.is_file())
    for heading, steps in [
        ("Journal reports", _journal_reports),
        ("Health reports", _health_reports),
    ]:
        typer.echo(f"\n{heading}")
        if heading == "Health reports" and not have_health:
            typer.echo(
                "  – weight, resting HR, HRV, sleep, steps, VO₂ max, exercise: no Apple Health "
                "export (set EGON_APPLE_HEALTH_XML in .env or pass --xml)"
            )
        for name, fn in steps:
            if heading == "Health reports" and not have_health and name != "correlations":
                results.append(_StepResult(name, "skipped", None, ""))
                continue
            results.append(_run_report_step(name, fn))

    ok = [r for r in results if r.status == "ok"]
    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]
    open_hint = ok[0].path if ok else None

    if full:
        typer.echo("\nFull report")
        full_path = _run_full_report(
            entries,
            resolved_xml,
            start,
            end,
            label,
            full_output=Path(f"reports/full_report/{label}.html"),
        )
        if full_path:
            open_hint = full_path

    typer.echo(
        f"\nDone in {_fmt_duration(time.monotonic() - started)} · "
        f"{len(ok)} reports generated, {len(skipped)} skipped, {len(failed)} failed"
    )
    if open_hint:
        typer.echo(f"Open: open {open_hint}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_program(programs_dir: Path, title: str) -> Optional[dict]:
    """Return the YAML source dict for the program whose title matches, or None."""
    if not programs_dir.exists():
        return None
    for yaml_path in sorted(programs_dir.glob("*.yaml")):
        source = load_program_yaml(yaml_path)
        if source.get("title") == title:
            return source
    return None
