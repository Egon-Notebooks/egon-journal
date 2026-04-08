"""
Full combined PDF report for egon-journal.

Assembles all individual report figures into a single professionally formatted
PDF document, organised into three sections with a cover page and executive
summary.

All figures are rendered directly into the PDF as vector graphics — no PNG
intermediate files.  The only persistent cache is the JSON-serialised ML
scoring results for Big Five and MBTI (the slow operations): if those JSON
files already exist in ``reports/full-report/.cache/<label>/``, the model is
not re-invoked.  Delete those files to force a full re-score.

Usage (called from CLI with ``uv run egon report --full``):
    from egon.full_report import generate_full_report
    generate_full_report(
        journal_entries=entries,
        xml_path=xml,
        start=start,
        end=end,
        label="2026-Q1",
        output_path=Path("reports/full-report/2026-Q1.pdf"),
    )
"""
import json
import textwrap
from datetime import date as date_type
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from egon.analytics.loader import JournalEntry
from egon.analytics.word_count import plot_word_count
from egon.analytics.wordcloud_plot import plot_wordcloud
from egon.health.apple_health import (
    daily_mean,
    daily_sum,
    filter_by_date,
    infer_unit,
    load_records,
)
from egon.health.hrv_plot import plot_hrv
from egon.health.resting_heart_rate_plot import plot_resting_heart_rate
from egon.health.sleep import filter_sleep_by_date, load_sleep_onset, load_sleep_records
from egon.health.sleep_plot import plot_sleep
from egon.health.step_count_plot import plot_step_count
from egon.health.vo2max_plot import plot_vo2max
from egon.health.weight_plot import plot_weight
from egon.limbic.bigfive import BigFiveScores, bigfive_by_day
from egon.limbic.bigfive_plot import plot_bigfive
from egon.limbic.mbti import MBTIScores, mbti_by_day
from egon.limbic.mbti_plot import plot_mbti
from egon.limbic.sentiment_plot import plot_sentiment
from egon.plot_style import apply_style

# ---------------------------------------------------------------------------
# Layout & colour constants
# ---------------------------------------------------------------------------

_W = 8.5    # page width  (US Letter, inches)
_H = 11.0   # page height (US Letter, inches)

_NAVY    = "#1D3461"
_BLUE    = "#4C72B0"
_LIGHT   = "#EEF3FA"
_RULE    = "#C5D3E8"
_BODY    = "#2D2D2D"
_CAPTION = "#6B7A8D"
_WHITE   = "#FFFFFF"

# ---------------------------------------------------------------------------
# Section copy
# ---------------------------------------------------------------------------

_EXEC_SUMMARY = (
    "This report covers the selected period and draws on your written journal "
    "entries alongside Apple Health data to provide a structured overview of "
    "your psychological and physical wellbeing. The goal is to surface patterns "
    "that are difficult to perceive day-to-day and to give you — and anyone you "
    "choose to share this with — a common language for discussing how you have been."
    "\n\n"
    "The pages that follow are arranged from the most subjective signals (what you "
    "wrote, how you expressed yourself) through to more objective physiological "
    "markers (what your body recorded). Reading them together may reveal connections "
    "between your inner world and your physical state: for instance, whether nights "
    "of poor sleep precede days of lower-sentiment writing, or whether high activity "
    "correlates with a more open, positive tone."
    "\n\n"
    "Personality trait scores (Big Five, MBTI) reflect the emotional and cognitive "
    "tone of your writing during this period rather than fixed character traits. "
    "They should be interpreted as a snapshot of how you expressed yourself. Sudden "
    "shifts in physiological metrics — weight, resting heart rate, or sleep — are "
    "worth noting and may be worth discussing with a healthcare professional."
)

_JOURNAL_INTRO = (
    "Journal insights are derived directly from your written entries. Word count "
    "captures your daily expressive output and engagement with the journaling "
    "practice. Sentiment reflects the overall emotional valence of your language "
    "on each day — whether your words tended toward the positive, neutral, or "
    "negative. The word cloud highlights the themes and topics that appeared most "
    "frequently across the period."
    "\n\n"
    "Together these three views give a picture of your expressive rhythm: how much "
    "you wrote, how you felt as you wrote, and what was on your mind. Gaps in the "
    "word count chart may indicate days without an entry and are worth noting as "
    "part of the broader picture."
)

_PERSONALITY_INTRO = (
    "Personality and affective pattern scores are inferred from the language you "
    "used in your journal entries. The Big Five model scores your writing on five "
    "dimensions — Openness, Conscientiousness, Extraversion, Agreeableness, and "
    "Neuroticism — that are widely used in psychological research. The MBTI model "
    "classifies entries across four binary dimensions (E/I, N/S, T/F, J/P)."
    "\n\n"
    "Day-to-day variation is typically more meaningful than absolute values; look "
    "for trends and shifts over time rather than interpreting individual data points "
    "as fixed personality markers. A prolonged shift in Neuroticism or a sustained "
    "drop in Extraversion, for example, may be worth reflecting on. The dashed "
    "average line on each subplot shows your central tendency over the full period."
)

_PHYSIO_INTRO = (
    "Physiological measures are drawn from your Apple Health data. Each metric has "
    "known associations with mental health and wellbeing: resting heart rate and "
    "heart rate variability (HRV) reflect autonomic nervous system state and "
    "recovery; sleep duration and onset regularity are strongly linked to mood "
    "regulation and depressive symptoms; body weight changes can signal stress or "
    "lifestyle shifts; step count captures daily physical activity; and VO\u2082 max "
    "tracks aerobic fitness over time."
    "\n\n"
    "Not all metrics may be present — data availability depends on your Apple Health "
    "export and the devices you use. Metrics that were not recorded during the "
    "selected period are omitted from this section. Where available, a dashed "
    "average or reference line is shown to provide a baseline for comparison."
)

# ---------------------------------------------------------------------------
# ML data cache helpers (JSON — avoids re-running the model on repeat runs)
# ---------------------------------------------------------------------------

def _save_bigfive_cache(
    data: list[tuple[date_type, BigFiveScores]], path: Path
) -> None:
    payload = [[d.isoformat(), list(s)] for d, s in data]
    path.write_text(json.dumps(payload))


def _load_bigfive_cache(
    path: Path,
) -> list[tuple[date_type, BigFiveScores]]:
    payload = json.loads(path.read_text())
    return [(date_type.fromisoformat(d), BigFiveScores(*s)) for d, s in payload]


def _save_mbti_cache(
    data: list[tuple[date_type, MBTIScores]], path: Path
) -> None:
    payload = [[d.isoformat(), list(s)] for d, s in data]
    path.write_text(json.dumps(payload))


def _load_mbti_cache(
    path: Path,
) -> list[tuple[date_type, MBTIScores]]:
    payload = json.loads(path.read_text())
    return [(date_type.fromisoformat(d), MBTIScores(*s)) for d, s in payload]


# ---------------------------------------------------------------------------
# Page-building helpers (all vector, no raster intermediates)
# ---------------------------------------------------------------------------

def _para(text: str, width: int = 88) -> str:
    return "\n\n".join(
        textwrap.fill(p.replace("\n", " "), width=width)
        for p in text.split("\n\n")
    )


def _add_footer(fig) -> None:
    ax = fig.add_axes([0, 0, 1, 0.038])
    ax.set_facecolor(_WHITE)
    ax.axis("off")
    ax.axhline(0.92, xmin=0.04, xmax=0.96, color=_RULE, linewidth=0.7)
    ax.text(0.5, 0.32, "Egon Notebooks",
            ha="center", va="center", color=_CAPTION,
            fontsize=8, fontfamily="serif", transform=ax.transAxes)


def _cover_page(pdf: PdfPages, label: str, start: date_type, end: date_type) -> None:
    apply_style()
    fig = plt.figure(figsize=(_W, _H), facecolor=_WHITE)

    top_h = 0.17
    ax_top = fig.add_axes([0, 1 - top_h, 1, top_h])
    ax_top.set_facecolor(_NAVY)
    ax_top.axis("off")
    ax_top.text(0.5, 0.60, "EGON NOTEBOOKS",
                ha="center", va="center", color=_WHITE,
                fontsize=28, fontweight="bold", fontfamily="serif",
                transform=ax_top.transAxes)
    ax_top.text(0.5, 0.22, "Personal Journal & Health Report",
                ha="center", va="center", color=_WHITE,
                fontsize=12, fontfamily="serif", alpha=0.80,
                transform=ax_top.transAxes)

    ax = fig.add_axes([0.12, 0.10, 0.76, 0.71])
    ax.set_facecolor(_WHITE)
    ax.axis("off")
    ax.text(0.5, 0.86, label,
            ha="center", va="top", color=_BLUE,
            fontsize=34, fontfamily="serif", fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.5, 0.71,
            f"{start.strftime('%B %-d')} \u2013 {end.strftime('%B %-d, %Y')}",
            ha="center", va="top", color=_NAVY,
            fontsize=13, fontfamily="serif",
            transform=ax.transAxes)
    # Decorative rule via plot() — axhline does not accept transform kwarg
    ax.plot([0.10, 0.90], [0.60, 0.60], color=_RULE, linewidth=1.0,
            transform=ax.transAxes, clip_on=False)
    ax.text(0.5, 0.52,
            f"Generated {date_type.today().strftime('%B %-d, %Y')}",
            ha="center", va="top", color=_CAPTION,
            fontsize=11, fontfamily="serif",
            transform=ax.transAxes)

    ax_bot = fig.add_axes([0, 0, 1, 0.038])
    ax_bot.set_facecolor(_NAVY)
    ax_bot.axis("off")
    ax_bot.text(0.96, 0.5, "egonnotebooks.com",
                ha="right", va="center", color=_WHITE,
                fontsize=8.5, fontfamily="serif", alpha=0.65,
                transform=ax_bot.transAxes)

    pdf.savefig(fig)
    plt.close(fig)


def _text_page(
    pdf: PdfPages,
    title: str,
    body: str,
    section_num: int | None = None,
) -> None:
    apply_style()
    fig = plt.figure(figsize=(_W, _H), facecolor=_WHITE)

    hdr_h = 0.14
    ax_hdr = fig.add_axes([0, 1 - hdr_h, 1, hdr_h])
    ax_hdr.set_facecolor(_LIGHT)
    ax_hdr.axis("off")
    ax_hdr.axhline(0.02, xmin=0, xmax=1, color=_RULE, linewidth=0.8)
    if section_num is not None:
        ax_hdr.text(0.055, 0.54, str(section_num),
                    ha="center", va="center", color=_BLUE,
                    fontsize=32, fontweight="bold", fontfamily="serif",
                    alpha=0.55, transform=ax_hdr.transAxes)
        ax_hdr.text(0.13, 0.54, title,
                    ha="left", va="center", color=_NAVY,
                    fontsize=17, fontweight="bold", fontfamily="serif",
                    transform=ax_hdr.transAxes)
    else:
        ax_hdr.text(0.055, 0.54, title,
                    ha="left", va="center", color=_NAVY,
                    fontsize=17, fontweight="bold", fontfamily="serif",
                    transform=ax_hdr.transAxes)

    body_top = 1 - hdr_h - 0.04
    ax_body = fig.add_axes([0.08, 0.06, 0.84, body_top - 0.06])
    ax_body.set_facecolor(_WHITE)
    ax_body.axis("off")
    ax_body.text(0, 1, _para(body),
                 ha="left", va="top", color=_BODY,
                 fontsize=11, fontfamily="serif",
                 linespacing=1.70, transform=ax_body.transAxes)

    _add_footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _figure_page(pdf: PdfPages, fig: plt.Figure, caption: str) -> None:
    """
    Annotate the captured figure with a caption and save it to the PDF.

    The figure is saved at its natural size as fully vector content.
    A uniform padding of 0.45 inches is added on every side so that nothing
    crowds the page edge.  The italic caption is placed just below the plot
    area.
    """
    apply_style()
    fig.text(0.5, 0.005, caption,
             ha="center", va="bottom", color=_CAPTION,
             fontsize=10, fontfamily="serif", style="italic")
    pdf.savefig(fig, bbox_inches="tight", pad_inches=0.45)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_full_report(
    *,
    journal_entries: list[JournalEntry],
    xml_path: Path | None,
    start: date_type,
    end: date_type,
    label: str,
    target_body_mass: float | None = None,
    target_lean_body_mass: float | None = None,
    output_path: Path,
) -> None:
    """
    Compile all report figures into a single vector PDF and save to *output_path*.

    ML scoring results (Big Five, MBTI) are cached as JSON in
    ``<output_dir>/.cache/<label>/`` so that re-running skips the model.
    Delete those files (or the whole cache directory) to force a re-score.
    All other figures are rendered fresh on every run.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = output_path.parent / ".cache" / label
    cache_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # ML data — load from JSON cache or re-score
    # -----------------------------------------------------------------------
    bf_cache   = cache_dir / "bigfive_data.json"
    mbti_cache = cache_dir / "mbti_data.json"

    bigfive_data = None
    mbti_data    = None

    if journal_entries:
        if bf_cache.exists():
            print("  [full report] Big Five: loading cached scores")
            try:
                bigfive_data = _load_bigfive_cache(bf_cache)
            except Exception as exc:
                print(f"  [full report] Big Five cache corrupt, re-scoring: {exc}")

        if bigfive_data is None:
            try:
                bigfive_data = bigfive_by_day(journal_entries)
                _save_bigfive_cache(bigfive_data, bf_cache)
            except Exception as exc:
                print(f"  [full report] Big Five scoring unavailable: {exc}")

        if mbti_cache.exists():
            print("  [full report] MBTI: loading cached scores")
            try:
                mbti_data = _load_mbti_cache(mbti_cache)
            except Exception as exc:
                print(f"  [full report] MBTI cache corrupt, re-scoring: {exc}")

        if mbti_data is None:
            try:
                mbti_data = mbti_by_day(journal_entries)
                _save_mbti_cache(mbti_data, mbti_cache)
            except Exception as exc:
                print(f"  [full report] MBTI scoring unavailable: {exc}")

    # -----------------------------------------------------------------------
    # Health records (load once)
    # -----------------------------------------------------------------------
    health_records: dict = {}
    if xml_path and xml_path.is_file():
        try:
            health_records = load_records(xml_path)
        except Exception as exc:
            print(f"  [full report] Failed to load Apple Health data: {exc}")

    # -----------------------------------------------------------------------
    # Helper: call a plot function with output_path=None to capture the figure
    # -----------------------------------------------------------------------
    def _capture(fn, name: str, *args, **kwargs) -> plt.Figure | None:
        try:
            return fn(*args, output_path=None, **kwargs)
        except Exception as exc:
            print(f"  [full report] skipping '{name}': {exc}")
            return None

    # -----------------------------------------------------------------------
    # Assemble the PDF (all figures rendered directly — fully vector)
    # -----------------------------------------------------------------------
    with PdfPages(str(output_path)) as pdf:

        _cover_page(pdf, label, start, end)
        _text_page(pdf, "Executive Summary", _EXEC_SUMMARY)

        # Section 1 — Journal Insights
        _text_page(pdf, "Journal Insights", _JOURNAL_INTRO, section_num=1)

        fig = _capture(plot_word_count, "word-count",
                       journal_entries, title=f"Journal word count \u2014 {label}")
        if fig:
            _figure_page(pdf, fig, "Figure 1.1 \u2014 Daily journal word count")

        fig = _capture(plot_sentiment, "sentiment",
                       journal_entries, title=f"Journal sentiment \u2014 {label}")
        if fig:
            _figure_page(pdf, fig,
                         "Figure 1.2 \u2014 Daily sentiment score "
                         "(VADER compound, \u22121 to +1)")

        fig = _capture(plot_wordcloud, "wordcloud",
                       journal_entries, title=f"Journal word cloud \u2014 {label}")
        if fig:
            _figure_page(pdf, fig,
                         "Figure 1.3 \u2014 Word cloud of most frequent themes")

        # Section 2 — Personality & Affective Patterns
        _text_page(pdf, "Personality & Affective Patterns",
                   _PERSONALITY_INTRO, section_num=2)

        if bigfive_data:
            fig = _capture(plot_bigfive, "bigfive",
                           bigfive_data,
                           title=f"Big Five personality traits \u2014 {label}")
            if fig:
                _figure_page(pdf, fig,
                             "Figure 2.1 \u2014 Big Five personality trait scores "
                             "by day (O, C, E, A, N)")

        if mbti_data:
            fig = _capture(plot_mbti, "mbti",
                           mbti_data,
                           title=f"MBTI personality dimensions \u2014 {label}")
            if fig:
                _figure_page(pdf, fig,
                             "Figure 2.2 \u2014 MBTI dimension scores by day "
                             "(E/I, N/S, T/F, J/P)")

        # Section 3 — Physiological Measures
        _text_page(pdf, "Physiological Measures", _PHYSIO_INTRO, section_num=3)

        if (weight_recs := health_records.get("BodyMass")):
            unit        = infer_unit(weight_recs)
            weight_data = filter_by_date(daily_mean(weight_recs), start, end)
            lean_recs   = health_records.get("LeanBodyMass", [])
            lean_data   = (
                filter_by_date(daily_mean(lean_recs), start, end) or None
                if lean_recs else None
            )
            if weight_data:
                fig = _capture(plot_weight, "weight",
                               weight_data,
                               title=f"Weight \u2014 {label}", unit=unit,
                               lean_data=lean_data,
                               target_body_mass=target_body_mass,
                               target_lean_body_mass=target_lean_body_mass)
                if fig:
                    _figure_page(pdf, fig,
                                 "Figure 3.1 \u2014 Daily body weight "
                                 "(and lean body mass if available)")

        if (rhr_recs := health_records.get("RestingHeartRate")):
            rhr_unit = infer_unit(rhr_recs)
            rhr_data = filter_by_date(daily_mean(rhr_recs), start, end)
            if rhr_data:
                fig = _capture(plot_resting_heart_rate, "resting-heart-rate",
                               rhr_data,
                               title=f"Resting heart rate \u2014 {label}",
                               unit=rhr_unit)
                if fig:
                    _figure_page(pdf, fig,
                                 "Figure 3.2 \u2014 Daily resting heart rate")

        if (hrv_recs := health_records.get("HeartRateVariabilitySDNN")):
            hrv_unit = infer_unit(hrv_recs)
            hrv_data = filter_by_date(daily_mean(hrv_recs), start, end)
            if hrv_data:
                fig = _capture(plot_hrv, "hrv",
                               hrv_data,
                               title=f"Heart rate variability \u2014 {label}",
                               unit=hrv_unit)
                if fig:
                    _figure_page(pdf, fig,
                                 "Figure 3.3 \u2014 Daily heart rate variability "
                                 "(HRV SDNN)")

        if xml_path and xml_path.is_file():
            try:
                sleep_data  = filter_sleep_by_date(
                    load_sleep_records(xml_path), start, end)
                onset_data  = filter_sleep_by_date(
                    load_sleep_onset(xml_path), start, end) or None
                if sleep_data:
                    fig = _capture(plot_sleep, "sleep",
                                   sleep_data,
                                   title=f"Time asleep \u2014 {label}",
                                   onset_data=onset_data)
                    if fig:
                        _figure_page(pdf, fig,
                                     "Figure 3.4 \u2014 Nightly time asleep "
                                     "and sleep onset time")
            except Exception as exc:
                print(f"  [full report] skipping 'sleep': {exc}")

        if (step_recs := health_records.get("StepCount")):
            steps_data = filter_by_date(daily_sum(step_recs), start, end)
            if steps_data:
                fig = _capture(plot_step_count, "step-count",
                               steps_data,
                               title=f"Daily step count \u2014 {label}")
                if fig:
                    _figure_page(pdf, fig,
                                 "Figure 3.5 \u2014 Daily step count")

        if (vo2_recs := health_records.get("VO2Max")):
            vo2_unit = infer_unit(vo2_recs)
            vo2_data = filter_by_date(daily_mean(vo2_recs), start, end)
            if vo2_data:
                fig = _capture(plot_vo2max, "vo2max",
                               vo2_data,
                               title=f"VO\u2082 max \u2014 {label}",
                               unit=vo2_unit)
                if fig:
                    _figure_page(pdf, fig,
                                 "Figure 3.6 \u2014 Daily VO\u2082 max (mL/min/kg)")
