"""
Full combined PDF report for egon-journal.

All pages are A4 (8.27 × 11.69 in).  Figure pages rescale the captured
matplotlib figure to fit within the page margins, then add a caption and a
short commentary paragraph below.

The only persistent cache is JSON-serialised ML scoring for Big Five and MBTI
(the slow operations).  All other figures are rendered fresh every run.

Usage:
    from egon.full_report import generate_full_report
    generate_full_report(
        journal_entries=entries,
        xml_path=xml,
        start=start, end=end, label="2026-Q1",
        output_path=Path("reports/full-report/2026-Q1.pdf"),
    )
"""

import io
import json
import struct
import textwrap
from datetime import date as date_type
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from egon.analytics.correlation_plot import (
    plot_correlation_matrix,
    plot_highlighted_correlations,
)
from egon.analytics.loader import JournalEntry
from egon.analytics.pronoun_ratio_plot import plot_pronoun_ratio
from egon.analytics.word_count import plot_word_count
from egon.analytics.wordcloud_plot import plot_wordcloud
from egon.config import ReportConfig, load_report_config
from egon.health.apple_health import (
    daily_mean,
    daily_sum,
    filter_by_date,
    infer_unit,
    load_records,
)
from egon.health.exercise_plot import plot_exercise
from egon.health.hrv_plot import plot_hrv
from egon.health.resting_heart_rate_plot import plot_resting_heart_rate
from egon.health.sleep import filter_sleep_by_date, load_sleep_onset, load_sleep_records
from egon.health.sleep_plot import plot_sleep
from egon.health.step_count_plot import plot_step_count
from egon.health.vo2max_plot import plot_vo2max
from egon.health.weight_plot import plot_weight
from egon.limbic.bigfive import BigFiveScores, bigfive_by_day
from egon.limbic.bigfive_plot import plot_bigfive
from egon.limbic.emotion import EmotionScores, emotion_by_day
from egon.limbic.emotion_plot import plot_emotion
from egon.limbic.mbti import MBTIScores, mbti_by_day
from egon.limbic.mbti_plot import plot_mbti
from egon.limbic.sentiment_plot import plot_sentiment
from egon.plot_style import apply_style

_LOGO_PATH = Path(__file__).resolve().parents[1] / "content" / "egon_logo.png"

# Type alias for a named daily time series
Signals = dict[str, list[tuple[date_type, float]]]

# ---------------------------------------------------------------------------
# Page dimensions (A4) and layout constants
# ---------------------------------------------------------------------------

_W = 8.27  # A4 width  (inches)
_H = 11.69  # A4 height (inches)

_MARGIN_H = 0.65  # left/right margin (inches)
_MARGIN_V = 0.55  # top/bottom margin (inches)

# Space reserved at the bottom of each figure page for caption + commentary
_TEXT_AREA_H = 1.80  # inches

_NAVY = "#1D3461"
_BLUE = "#4C72B0"
_LIGHT = "#EEF3FA"
_RULE = "#C5D3E8"
_BODY = "#2D2D2D"
_CAPTION = "#6B7A8D"
_WHITE = "#FFFFFF"

# ---------------------------------------------------------------------------
# Placeholder commentary text — one entry per figure
# ---------------------------------------------------------------------------

_LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, "
    "quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo "
    "consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse."
)

_FIG_COMMENTARY = {
    "word-count": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about writing volume and consistency over the period.]"
    ),
    "sentiment": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about emotional tone and notable shifts in sentiment.]"
    ),
    "wordcloud": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about recurring themes and topics.]"
    ),
    "pronoun-ratio": (
        "First-person pronouns (I, me, my, mine, myself) as a fraction of total "
        "words per journal entry. Research by Pennebaker and colleagues links "
        "elevated first-person singular pronoun use with self-focused attention, "
        "depressive rumination, and emotional distress. Day-to-day variation is "
        "normal; a sustained upward trend over weeks may be worth noting. "
        "[Replace with observations about your own pronoun pattern and any "
        "periods that stand out.]"
    ),
    "topic-summary": (
        "BERTopic discovers latent themes in the journal corpus by clustering "
        "semantically similar entries.  Each bar represents one discovered topic; "
        "the label shows its most representative keywords.  Bar length reflects "
        "how many entries belong to that topic.  Topic ids are assigned by size "
        "(largest first); the exact keywords depend on the period analysed. "
        "[Replace with observations about which themes dominate your writing.]"
    ),
    "topic-timeline": (
        "The same topics as the summary chart, tracked month by month.  A growing "
        "slice indicates a theme that is becoming more prominent in your writing; "
        "a shrinking one has receded.  Abrupt shifts often coincide with life "
        "events — a new project, a relationship change, a health episode. "
        "[Replace with observations about how your recurring themes have evolved "
        "over the period.]"
    ),
    "emotion": (
        "Emotion probabilities are inferred from the language in your journal entries "
        "using a DistilRoBERTa model trained on six emotion datasets "
        "(Hartmann et al. 2022).  The stacked area chart shows all seven emotions; "
        "the line chart below isolates joy and sadness for easier day-to-day reading.  "
        "Sustained elevation of sadness or fear over multiple weeks may be worth "
        "discussing with a therapist; transient spikes are normal. "
        "[Replace with observations about dominant emotions and any notable shifts.]"
    ),
    "bigfive": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about dominant traits and any notable trends over the period.]"
    ),
    "mbti": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about personality dimension stability and any notable shifts.]"
    ),
    "weight": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about weight trends and progress toward goals if applicable.]"
    ),
    "resting-heart-rate": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about resting heart rate and cardiovascular recovery.]"
    ),
    "hrv": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about HRV variability and autonomic nervous system state.]"
    ),
    "sleep": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about sleep duration, onset regularity, and any patterns.]"
    ),
    "step-count": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about physical activity levels and the 10,000-step goal.]"
    ),
    "vo2max": (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
        "veniam, quis nostrud exercitation ullamco laboris. [Replace with "
        "observations about aerobic fitness trajectory over the period.]"
    ),
    "exercise": (
        "Apple Exercise Time measures minutes per day during which your heart rate "
        "was elevated above a brisk-walk threshold, matching the Apple Watch Exercise "
        "ring.  The WHO recommends at least 150 minutes of moderate-intensity activity "
        "per week — equivalent to the 30-minute daily guideline shown here.  "
        "[Replace with observations about exercise consistency and any weeks that "
        "stand out above or below the guideline.]"
    ),
    "correlation-matrix": (
        "Each cell shows the Pearson correlation coefficient between a pair of "
        "daily time series. Values range from −1 (perfect inverse relationship) "
        "to +1 (perfect positive relationship). Bold cells are statistically "
        "significant (p < 0.05); faded cells are not. Only days on which both "
        "signals were recorded are used per pair, so sample sizes vary. "
        "[Replace with observations about the strongest or most surprising "
        "associations in the matrix.]"
    ),
    "highlighted-correlations": (
        "These four scatter plots examine relationships between physiological and "
        "psychological signals that have well-documented links to mental health and "
        "wellbeing. Sleep quality predicts next-day mood; HRV and resting heart rate "
        "both reflect autonomic nervous system tone, which is closely tied to anxiety "
        "and stress; step count is a proxy for the mood-lifting effect of physical "
        "activity. The regression line shows the direction of the linear trend; the "
        "r and p values indicate its strength and reliability. "
        "[Replace with observations about which relationships are strongest for you "
        "and what they might suggest about your recovery and energy patterns.]"
    ),
}

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
    "drop in Extraversion, for example, may be worth reflecting on."
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
    "selected period are omitted from this section."
)

# ---------------------------------------------------------------------------
# ML data cache helpers
# ---------------------------------------------------------------------------


def _save_bigfive_cache(data: list[tuple[date_type, BigFiveScores]], path: Path) -> None:
    path.write_text(json.dumps([[d.isoformat(), list(s)] for d, s in data]))


def _load_bigfive_cache(path: Path) -> list[tuple[date_type, BigFiveScores]]:
    return [
        (date_type.fromisoformat(d), BigFiveScores(*s)) for d, s in json.loads(path.read_text())
    ]


def _save_mbti_cache(data: list[tuple[date_type, MBTIScores]], path: Path) -> None:
    path.write_text(json.dumps([[d.isoformat(), list(s)] for d, s in data]))


def _load_mbti_cache(path: Path) -> list[tuple[date_type, MBTIScores]]:
    return [(date_type.fromisoformat(d), MBTIScores(*s)) for d, s in json.loads(path.read_text())]


# ---------------------------------------------------------------------------
# Page helpers
# ---------------------------------------------------------------------------


def _para(text: str, width: int = 86) -> str:
    return "\n\n".join(textwrap.fill(p.replace("\n", " "), width=width) for p in text.split("\n\n"))


def _add_footer(fig: plt.Figure) -> None:
    ax = fig.add_axes([0, 0, 1, 0.03])
    ax.set_facecolor(_WHITE)
    ax.axis("off")
    ax.axhline(0.9, xmin=0.04, xmax=0.96, color=_RULE, linewidth=0.6)
    ax.text(
        0.5,
        0.28,
        "Egon Notebooks",
        ha="center",
        va="center",
        color=_CAPTION,
        fontsize=7.5,
        fontfamily="serif",
        transform=ax.transAxes,
    )


def _cover_page(pdf: PdfPages, label: str, start: date_type, end: date_type) -> None:
    apply_style()
    fig = plt.figure(figsize=(_W, _H), facecolor=_WHITE)

    logo_img = mpimg.imread(_LOGO_PATH) if _LOGO_PATH.is_file() else None

    # --- Navy header band with logo + "Egon Notebooks" ---
    top_h = 0.17
    ax_top = fig.add_axes([0, 1 - top_h, 1, top_h])
    ax_top.set_facecolor(_NAVY)
    ax_top.axis("off")

    if logo_img is not None:
        logo_size = 0.13  # fraction of figure height
        logo_left = 0.30
        ax_logo = fig.add_axes(
            [logo_left, 1 - top_h + (top_h - logo_size) / 2, logo_size, logo_size]
        )
        ax_logo.imshow(logo_img)
        ax_logo.axis("off")
        text_x = logo_left + logo_size + 0.02
        # convert figure x to axes fraction
        text_x_frac = text_x
        ax_top.text(
            text_x_frac,
            0.60,
            "Egon Notebooks",
            ha="left",
            va="center",
            color=_WHITE,
            fontsize=26,
            fontweight="bold",
            fontfamily="serif",
            transform=fig.transFigure,
        )
        ax_top.text(
            text_x_frac,
            1 - top_h + top_h * 0.22,
            "Personal Journal & Health Report",
            ha="left",
            va="center",
            color=_WHITE,
            fontsize=10,
            fontfamily="serif",
            alpha=0.80,
            transform=fig.transFigure,
        )
    else:
        ax_top.text(
            0.5,
            0.60,
            "Egon Notebooks",
            ha="center",
            va="center",
            color=_WHITE,
            fontsize=26,
            fontweight="bold",
            fontfamily="serif",
            transform=ax_top.transAxes,
        )
        ax_top.text(
            0.5,
            0.22,
            "Personal Journal & Health Report",
            ha="center",
            va="center",
            color=_WHITE,
            fontsize=11,
            fontfamily="serif",
            alpha=0.80,
            transform=ax_top.transAxes,
        )

    # --- Body: period label, date range, generated date ---
    ax = fig.add_axes([0.12, 0.10, 0.76, 0.71])
    ax.set_facecolor(_WHITE)
    ax.axis("off")
    ax.text(
        0.5,
        0.78,
        label,
        ha="center",
        va="top",
        color=_BLUE,
        fontsize=32,
        fontfamily="serif",
        fontweight="bold",
        transform=ax.transAxes,
    )
    ax.text(
        0.5,
        0.62,
        f"{start.strftime('%B %-d')} \u2013 {end.strftime('%B %-d, %Y')}",
        ha="center",
        va="top",
        color=_NAVY,
        fontsize=12,
        fontfamily="serif",
        transform=ax.transAxes,
    )
    ax.plot(
        [0.10, 0.90],
        [0.50, 0.50],
        color=_RULE,
        linewidth=0.9,
        transform=ax.transAxes,
        clip_on=False,
    )
    ax.text(
        0.5,
        0.42,
        f"Generated {date_type.today().strftime('%B %-d, %Y')}",
        ha="center",
        va="top",
        color=_CAPTION,
        fontsize=10,
        fontfamily="serif",
        transform=ax.transAxes,
    )

    ax_bot = fig.add_axes([0, 0, 1, 0.03])
    ax_bot.set_facecolor(_NAVY)
    ax_bot.axis("off")
    ax_bot.text(
        0.96,
        0.5,
        "egonnotebooks.com",
        ha="right",
        va="center",
        color=_WHITE,
        fontsize=8,
        fontfamily="serif",
        alpha=0.65,
        transform=ax_bot.transAxes,
    )

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

    hdr_h = 0.13
    ax_hdr = fig.add_axes([0, 1 - hdr_h, 1, hdr_h])
    ax_hdr.set_facecolor(_LIGHT)
    ax_hdr.axis("off")
    ax_hdr.axhline(0.03, xmin=0, xmax=1, color=_RULE, linewidth=0.7)
    if section_num is not None:
        ax_hdr.text(
            0.055,
            0.55,
            str(section_num),
            ha="center",
            va="center",
            color=_BLUE,
            fontsize=30,
            fontweight="bold",
            fontfamily="serif",
            alpha=0.50,
            transform=ax_hdr.transAxes,
        )
        ax_hdr.text(
            0.13,
            0.55,
            title,
            ha="left",
            va="center",
            color=_NAVY,
            fontsize=16,
            fontweight="bold",
            fontfamily="serif",
            transform=ax_hdr.transAxes,
        )
    else:
        ax_hdr.text(
            0.055,
            0.55,
            title,
            ha="left",
            va="center",
            color=_NAVY,
            fontsize=16,
            fontweight="bold",
            fontfamily="serif",
            transform=ax_hdr.transAxes,
        )

    body_top = 1 - hdr_h - 0.04
    ax_body = fig.add_axes([0.08, 0.055, 0.84, body_top - 0.055])
    ax_body.set_facecolor(_WHITE)
    ax_body.axis("off")
    ax_body.text(
        0,
        1,
        _para(body),
        ha="left",
        va="top",
        color=_BODY,
        fontsize=10.5,
        fontfamily="serif",
        linespacing=1.70,
        transform=ax_body.transAxes,
    )

    _add_footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


def _tight_size(fig: plt.Figure) -> tuple[float, float]:
    """
    Return the (width, height) in inches of the tight bounding box of *fig*,
    i.e. including all annotations, tick labels, etc. that extend outside axes.
    Uses a throw-away PNG render to force the renderer to compute text extents.
    """
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=72)
    buf.seek(0)
    # bbox_inches="tight" saves at the tight-bbox size; read back the pixel dims
    buf.seek(16)  # PNG IHDR chunk starts at byte 16
    w_px, h_px = struct.unpack(">II", buf.read(8))
    dpi = 72
    return w_px / dpi, h_px / dpi


def _figure_page(
    pdf: PdfPages,
    fig: plt.Figure,
    caption: str,
    commentary: str,
) -> None:
    """
    Fit *fig* onto an A4 page with margins, add a caption and commentary
    paragraph below it, and write the page to *pdf*.

    We measure the actual tight bounding box (including annotations outside
    axes) with a cheap 72-DPI probe render, then scale uniformly to fit the
    available area.  This avoids overflow from large right-side annotations
    (bigfive/mbti) or wide tick labels (sleep onset).  All content in the
    final PDF is vector.
    """
    apply_style()

    # Finalise layout so axes positions are stable before we read them.
    engine = fig.get_layout_engine()
    if engine is not None:
        engine.execute(fig)
        fig.set_layout_engine(None)

    # Measure the true content size including everything outside axes.
    tight_w, tight_h = _tight_size(fig)

    # Available plot area on A4 (inches)
    avail_w = _W - 2 * _MARGIN_H
    avail_h = _H - 2 * _MARGIN_V - _TEXT_AREA_H

    # Scale uniformly to fit within the available area.
    # The 0.82 safety factor guards against annotations that the tight-bbox
    # probe slightly underestimates (e.g. large right-side labels in bigfive/mbti).
    scale = min(avail_w / tight_w, avail_h / tight_h) * 0.82
    plot_w = tight_w * scale
    plot_h = tight_h * scale

    # The original axes positions are expressed as fractions of the *original*
    # figure size, not the tight bbox.  We need to map them into the portion of
    # the A4 page that the rescaled tight bbox occupies.
    orig_w, orig_h = fig.get_size_inches()

    # How the original figure maps onto the tight bbox (tight bbox may be
    # slightly larger or smaller than the figure due to savefig padding).
    # In practice tight_w ≥ orig_w, so this ratio ≤ 1.
    fw_ratio = orig_w / tight_w  # fraction of tight bbox width that is the figure
    fh_ratio = orig_h / tight_h

    # Centre the plot area horizontally; sit it at the top of the page body.
    plot_left = (_W - plot_w) / 2 / _W
    plot_bottom = (_MARGIN_V + _TEXT_AREA_H) / _H
    plot_width = plot_w / _W
    plot_height = plot_h / _H

    # Resize figure to A4 and remap all axes into the plot area.
    fig.set_size_inches(_W, _H)
    fig.set_facecolor(_WHITE)

    for ax in fig.get_axes():
        pos = ax.get_position()
        ax.set_position(
            [
                plot_left + pos.x0 * plot_width * fw_ratio,
                plot_bottom + pos.y0 * plot_height * fh_ratio,
                pos.width * plot_width * fw_ratio,
                pos.height * plot_height * fh_ratio,
            ]
        )

    # Commentary paragraph
    commentary_bottom = (_MARGIN_V + 0.42) / _H
    commentary_height = (_TEXT_AREA_H - 0.52) / _H
    ax_text = fig.add_axes([_MARGIN_H / _W, commentary_bottom, avail_w / _W, commentary_height])
    ax_text.axis("off")
    ax_text.text(
        0,
        1,
        _para(commentary, width=82),
        ha="left",
        va="top",
        color=_BODY,
        fontsize=9.5,
        fontfamily="serif",
        linespacing=1.55,
        transform=ax_text.transAxes,
    )

    # Caption line
    fig.text(
        0.5,
        (_MARGIN_V + 0.12) / _H,
        caption,
        ha="center",
        va="bottom",
        color=_CAPTION,
        fontsize=9,
        fontfamily="serif",
        style="italic",
    )

    _add_footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Signal assembly (shared by full report and standalone correlation command)
# ---------------------------------------------------------------------------


def build_signals(
    *,
    journal_entries: list[JournalEntry],
    health_records: dict,
    xml_path: Path | None,
    start: date_type,
    end: date_type,
    bigfive_data: list | None = None,
    mbti_data: list | None = None,
    emotion_data: list | None = None,
) -> Signals:
    """
    Collect all available daily time series into a name→data dict.

    Each value is a ``list[tuple[date, float]]`` suitable for the correlation
    plot functions.  Only signals that have data for the given period are
    included.
    """
    from egon.analytics.word_count import word_counts_by_day
    from egon.limbic.sentiment import sentiment_by_day

    signals: Signals = {}

    if journal_entries:
        try:
            signals["word count"] = [(d, float(v)) for d, v in word_counts_by_day(journal_entries)]
        except Exception:
            pass
        try:
            signals["sentiment"] = sentiment_by_day(journal_entries)
        except Exception:
            pass

    if bigfive_data:
        for i, name in enumerate(["B5-O", "B5-C", "B5-E", "B5-A", "B5-N"]):
            signals[name] = [(d, s[i]) for d, s in bigfive_data]

    if mbti_data:
        for i, name in enumerate(["MBTI E/I", "MBTI N/S", "MBTI T/F", "MBTI J/P"]):
            signals[name] = [(d, float(s[i])) for d, s in mbti_data]

    if emotion_data:
        from egon.limbic.emotion import EMOTIONS

        for i, name in enumerate(EMOTIONS):
            signals[f"emo-{name}"] = [(d, s[i]) for d, s in emotion_data]

    if weight_recs := health_records.get("BodyMass"):
        if wd := filter_by_date(daily_mean(weight_recs), start, end):
            signals["weight"] = wd
    if lean_recs := health_records.get("LeanBodyMass"):
        if ld := filter_by_date(daily_mean(lean_recs), start, end):
            signals["lean mass"] = ld
    if rhr_recs := health_records.get("RestingHeartRate"):
        if rd := filter_by_date(daily_mean(rhr_recs), start, end):
            signals["resting HR"] = rd
    if hrv_recs := health_records.get("HeartRateVariabilitySDNN"):
        if hd := filter_by_date(daily_mean(hrv_recs), start, end):
            signals["HRV"] = hd
    if step_recs := health_records.get("StepCount"):
        if sd := filter_by_date(daily_sum(step_recs), start, end):
            signals["steps"] = sd
    if ex_recs := health_records.get("AppleExerciseTime"):
        if ed := filter_by_date(daily_sum(ex_recs), start, end):
            signals["exercise (min)"] = ed
    if vo2_recs := health_records.get("VO2Max"):
        if vd := filter_by_date(daily_mean(vo2_recs), start, end):
            signals["VO\u2082 max"] = vd
    if xml_path and xml_path.is_file():
        try:
            if sleep_sig := filter_sleep_by_date(load_sleep_records(xml_path), start, end):
                signals["sleep (h)"] = sleep_sig
            if onset_sig := filter_sleep_by_date(load_sleep_onset(xml_path), start, end):
                signals["sleep onset"] = onset_sig
        except Exception:
            pass

    return signals


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
    target_resting_heart_rate: float | None = None,
    target_exercise_minutes: float | None = None,
    output_path: Path,
    config: ReportConfig | None = None,
) -> None:
    """
    Compile all report figures into a single A4 PDF and save to *output_path*.

    Big Five and MBTI scores are cached as JSON in
    ``<output_dir>/.cache/<label>/`` to avoid re-running the model.
    Delete those files to force a full re-score.
    """
    cfg = config if config is not None else load_report_config()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = output_path.parent / ".cache" / label
    cache_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # ML cache
    # -----------------------------------------------------------------------
    bf_cache = cache_dir / "bigfive_data.json"
    mbti_cache = cache_dir / "mbti_data.json"
    emotion_cache = cache_dir / "emotion_data.json"
    bigfive_data = None
    mbti_data = None
    emotion_data: list | None = None

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

        if cfg.enabled("emotion"):
            if emotion_cache.exists():
                print("  [full report] Emotion: loading cached scores")
                try:
                    raw = json.loads(emotion_cache.read_text())
                    emotion_data = [(date_type.fromisoformat(d), EmotionScores(*s)) for d, s in raw]
                except Exception as exc:
                    print(f"  [full report] Emotion cache corrupt, re-scoring: {exc}")
            if emotion_data is None:
                try:
                    emotion_data = emotion_by_day(journal_entries)
                    emotion_cache.write_text(
                        json.dumps([[d.isoformat(), list(s)] for d, s in emotion_data])
                    )
                except Exception as exc:
                    print(f"  [full report] Emotion scoring unavailable: {exc}")

    # -----------------------------------------------------------------------
    # Health records
    # -----------------------------------------------------------------------
    health_records: dict = {}
    if xml_path and xml_path.is_file():
        try:
            health_records = load_records(xml_path)
        except Exception as exc:
            print(f"  [full report] Failed to load Apple Health data: {exc}")

    # -----------------------------------------------------------------------
    # Collect all daily time series for cross-signal correlation analysis
    # -----------------------------------------------------------------------
    signals = build_signals(
        journal_entries=journal_entries,
        health_records=health_records,
        xml_path=xml_path,
        start=start,
        end=end,
        bigfive_data=bigfive_data,
        mbti_data=mbti_data,
        emotion_data=emotion_data,
    )

    def _capture(fn, name: str, *args, **kwargs) -> plt.Figure | None:
        try:
            return fn(*args, output_path=None, **kwargs)
        except Exception as exc:
            print(f"  [full report] skipping '{name}': {exc}")
            return None

    def _fp(fig, caption, key):
        _figure_page(pdf, fig, caption, _FIG_COMMENTARY[key])

    # -----------------------------------------------------------------------
    # Assemble PDF
    # -----------------------------------------------------------------------
    with PdfPages(str(output_path)) as pdf:
        _cover_page(pdf, label, start, end)
        _text_page(pdf, "Executive Summary", _EXEC_SUMMARY)

        # --- Section 1: Journal Insights ---
        _text_page(pdf, "Journal Insights", _JOURNAL_INTRO, section_num=1)

        if cfg.enabled("word_count"):
            fig = _capture(
                plot_word_count,
                "word-count",
                journal_entries,
                title=f"Journal word count \u2014 {label}",
            )
            if fig:
                _fp(fig, "Figure 1.1 \u2014 Daily journal word count", "word-count")

        if cfg.enabled("sentiment"):
            fig = _capture(
                plot_sentiment,
                "sentiment",
                journal_entries,
                title=f"Journal sentiment \u2014 {label}",
            )
            if fig:
                _fp(
                    fig,
                    "Figure 1.2 \u2014 Daily sentiment score (VADER compound, \u22121 to +1)",
                    "sentiment",
                )

        if cfg.enabled("wordcloud"):
            fig = _capture(
                plot_wordcloud,
                "wordcloud",
                journal_entries,
                title=f"Journal word cloud \u2014 {label}",
            )
            if fig:
                _fp(fig, "Figure 1.3 \u2014 Word cloud of most frequent themes", "wordcloud")

        if cfg.enabled("pronoun_ratio"):
            fig = _capture(
                plot_pronoun_ratio,
                "pronoun-ratio",
                journal_entries,
                title=f"First-person pronoun ratio \u2014 {label}",
            )
            if fig:
                _fp(
                    fig,
                    "Figure 1.4 \u2014 First-person pronoun ratio (I / me / my / mine / myself)",
                    "pronoun-ratio",
                )

        if cfg.enabled("topics"):
            try:
                from egon.analytics.topic_plot import plot_topic_summary, plot_topic_timeline

                fig = _capture(
                    plot_topic_summary,
                    "topic-summary",
                    journal_entries,
                    title=f"Journal topic summary \u2014 {label}",
                )
                if fig:
                    _fp(
                        fig,
                        "Figure 1.5 \u2014 Discovered topics and their representative keywords",
                        "topic-summary",
                    )

                fig = _capture(
                    plot_topic_timeline,
                    "topic-timeline",
                    journal_entries,
                    title=f"Journal topic timeline \u2014 {label}",
                )
                if fig:
                    _fp(
                        fig,
                        "Figure 1.6 \u2014 Topic prevalence by month",
                        "topic-timeline",
                    )
            except ImportError:
                print(
                    "  [full report] skipping 'topics': BERTopic not installed "
                    "(run: uv sync --extra topics)"
                )

        # --- Section 2: Personality & Affective Patterns ---
        _text_page(pdf, "Personality & Affective Patterns", _PERSONALITY_INTRO, section_num=2)

        if bigfive_data and cfg.enabled("bigfive"):
            fig = _capture(
                plot_bigfive,
                "bigfive",
                bigfive_data,
                title=f"Big Five personality traits \u2014 {label}",
            )
            if fig:
                _fp(
                    fig, "Figure 2.1 \u2014 Big Five trait scores by day (O, C, E, A, N)", "bigfive"
                )

        if mbti_data and cfg.enabled("mbti"):
            fig = _capture(
                plot_mbti, "mbti", mbti_data, title=f"MBTI personality dimensions \u2014 {label}"
            )
            if fig:
                _fp(
                    fig,
                    "Figure 2.2 \u2014 MBTI dimension scores by day (E/I, N/S, T/F, J/P)",
                    "mbti",
                )

        if emotion_data and cfg.enabled("emotion"):
            fig = _capture(
                plot_emotion,
                "emotion",
                emotion_data,
                title=f"Daily emotion profile \u2014 {label}",
            )
            if fig:
                _fp(
                    fig,
                    "Figure 2.3 \u2014 Daily emotion probabilities "
                    "(anger / fear / joy / sadness \u2026)",
                    "emotion",
                )

        # --- Section 3: Physiological Measures ---
        _text_page(pdf, "Physiological Measures", _PHYSIO_INTRO, section_num=3)

        if cfg.enabled("weight") and (weight_recs := health_records.get("BodyMass")):
            unit = infer_unit(weight_recs)
            weight_data = filter_by_date(daily_mean(weight_recs), start, end)
            lean_recs = health_records.get("LeanBodyMass", [])
            lean_data = (
                filter_by_date(daily_mean(lean_recs), start, end) or None if lean_recs else None
            )
            if weight_data:
                fig = _capture(
                    plot_weight,
                    "weight",
                    weight_data,
                    title=f"Weight \u2014 {label}",
                    unit=unit,
                    lean_data=lean_data,
                    target_body_mass=target_body_mass,
                    target_lean_body_mass=target_lean_body_mass,
                )
                if fig:
                    _fp(
                        fig,
                        "Figure 3.1 \u2014 Daily body weight (and lean body mass if available)",
                        "weight",
                    )

        if cfg.enabled("resting_heart_rate") and (
            rhr_recs := health_records.get("RestingHeartRate")
        ):
            rhr_unit = infer_unit(rhr_recs)
            rhr_data = filter_by_date(daily_mean(rhr_recs), start, end)
            if rhr_data:
                fig = _capture(
                    plot_resting_heart_rate,
                    "resting-heart-rate",
                    rhr_data,
                    title=f"Resting heart rate \u2014 {label}",
                    unit=rhr_unit,
                    target_resting_heart_rate=target_resting_heart_rate,
                )
                if fig:
                    _fp(fig, "Figure 3.2 \u2014 Daily resting heart rate", "resting-heart-rate")

        if cfg.enabled("hrv") and (hrv_recs := health_records.get("HeartRateVariabilitySDNN")):
            hrv_unit = infer_unit(hrv_recs)
            hrv_data = filter_by_date(daily_mean(hrv_recs), start, end)
            if hrv_data:
                fig = _capture(
                    plot_hrv,
                    "hrv",
                    hrv_data,
                    title=f"Heart rate variability \u2014 {label}",
                    unit=hrv_unit,
                )
                if fig:
                    _fp(fig, "Figure 3.3 \u2014 Daily heart rate variability (HRV SDNN)", "hrv")

        if cfg.enabled("sleep") and xml_path and xml_path.is_file():
            try:
                sleep_data = filter_sleep_by_date(load_sleep_records(xml_path), start, end)
                onset_data = filter_sleep_by_date(load_sleep_onset(xml_path), start, end) or None
                if sleep_data:
                    fig = _capture(
                        plot_sleep,
                        "sleep",
                        sleep_data,
                        title=f"Time asleep \u2014 {label}",
                        onset_data=onset_data,
                    )
                    if fig:
                        _fp(
                            fig,
                            "Figure 3.4 \u2014 Nightly time asleep and sleep onset time",
                            "sleep",
                        )
            except Exception as exc:
                print(f"  [full report] skipping 'sleep': {exc}")

        if cfg.enabled("step_count") and (step_recs := health_records.get("StepCount")):
            steps_data = filter_by_date(daily_sum(step_recs), start, end)
            if steps_data:
                fig = _capture(
                    plot_step_count,
                    "step-count",
                    steps_data,
                    title=f"Daily step count \u2014 {label}",
                )
                if fig:
                    _fp(fig, "Figure 3.5 \u2014 Daily step count", "step-count")

        if cfg.enabled("exercise") and (ex_recs := health_records.get("AppleExerciseTime")):
            exercise_data = filter_by_date(daily_sum(ex_recs), start, end)
            if exercise_data:
                fig = _capture(
                    plot_exercise,
                    "exercise",
                    exercise_data,
                    title=f"Daily exercise time \u2014 {label}",
                    target_exercise_minutes=target_exercise_minutes,
                )
                if fig:
                    _fp(fig, "Figure 3.6 \u2014 Daily Apple Exercise Time (min)", "exercise")

        if cfg.enabled("vo2max") and (vo2_recs := health_records.get("VO2Max")):
            vo2_unit = infer_unit(vo2_recs)
            vo2_data = filter_by_date(daily_mean(vo2_recs), start, end)
            if vo2_data:
                fig = _capture(
                    plot_vo2max,
                    "vo2max",
                    vo2_data,
                    title=f"VO\u2082 max \u2014 {label}",
                    unit=vo2_unit,
                )
                if fig:
                    _fp(fig, "Figure 3.7 \u2014 Daily VO\u2082 max (mL/min/kg)", "vo2max")

        # --- Section 4: Cross-Signal Analysis ---
        _CROSS_SIGNAL_INTRO = (
            "This section examines relationships between the time series collected "
            "across the other three sections. Rather than looking at each signal in "
            "isolation, the correlation matrix below asks: on days when one metric "
            "was higher than usual, were other metrics systematically higher or lower "
            "too? Strong correlations do not prove causation, but they can surface "
            "patterns worth exploring — for example, whether poor sleep reliably "
            "precedes lower mood the following day, or whether physical activity "
            "aligns with higher extraversion scores in your writing."
            "\n\n"
            "Only days on which both signals in a pair were recorded contribute to "
            "that pair\u2019s correlation, so cells involving infrequently recorded "
            "metrics (e.g. VO\u2082 max, lean body mass) may rest on fewer data "
            "points. The highlighted scatter plots on the following page focus on "
            "four pairs with well-documented links to mental health and wellbeing."
        )
        _text_page(pdf, "Cross-Signal Analysis", _CROSS_SIGNAL_INTRO, section_num=4)

        corr_dir = output_path.parent.parent / "correlations"

        if len(signals) >= 2 and cfg.enabled("correlation_matrix"):
            fig = _capture(
                plot_correlation_matrix,
                "correlation-matrix",
                signals,
                title=f"Cross-signal correlation matrix \u2014 {label}",
            )
            if fig:
                _fp(
                    fig,
                    "Figure 4.1 \u2014 Pairwise Pearson correlations across all daily signals",
                    "correlation-matrix",
                )
                corr_dir.mkdir(parents=True, exist_ok=True)
                fig.savefig(corr_dir / f"{label}_matrix.pdf")
                plt.close(fig)

        if len(signals) >= 2 and cfg.enabled("highlighted_correlations"):
            fig = _capture(
                plot_highlighted_correlations,
                "highlighted-correlations",
                signals,
                title=f"Key cross-signal relationships \u2014 {label}",
            )
            if fig:
                _fp(
                    fig,
                    "Figure 4.2 \u2014 Mental-health-relevant signal pairs",
                    "highlighted-correlations",
                )
                corr_dir.mkdir(parents=True, exist_ok=True)
                fig.savefig(corr_dir / f"{label}_highlighted.pdf")
                plt.close(fig)
