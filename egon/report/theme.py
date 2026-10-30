"""
Egon visual language for report charts (Vega-Lite via Altair).

Every chart is specified with the *light* colours below.  The HTML shell swaps
each light hex for its dark counterpart when the reader is in dark mode, so
chart code never has to know about themes — it only ever names a role.

The categorical palette was validated with the dataviz palette checker
(lightness band, chroma floor, colour-vision-deficiency separation and
contrast) against both surfaces.  The slot ORDER is part of that validation:
when several series sit next to each other, assign them in slot order, never
cycled or re-shuffled.  Re-run the validator if you change a hex value.

Palette (light / dark):
  1 ink blue     #2a66a8 / #5a93d6
  2 terracotta   #c0582f / #d96a3c
  3 sage         #2f9a7e / #2f9a7e
  4 ochre        #b8860b / #a8820f
  5 plum         #9a5196 / #b773b3
  6 moss         #5f8a2a / #5f8f2a
  7 rose         #d6728a / #c473a8
  8 oxblood      #a83232 / #b8403c
"""

from typing import Any

import altair as alt

# --- Categorical palette ------------------------------------------------------

SERIES_LIGHT: list[str] = [
    "#2a66a8",
    "#c0582f",
    "#2f9a7e",
    "#b8860b",
    "#9a5196",
    "#5f8a2a",
    "#d6728a",
    "#a83232",
]
SERIES_DARK: list[str] = [
    "#5a93d6",
    "#d96a3c",
    "#2f9a7e",
    "#a8820f",
    "#b773b3",
    "#5f8f2a",
    "#c473a8",
    "#b8403c",
]

BLUE, TERRACOTTA, SAGE, OCHRE, PLUM, MOSS, ROSE, OXBLOOD = SERIES_LIGHT

# --- Chrome & ink (aligned with egonnotebooks.com) ------------------------------

SURFACE = "#fffdf9"  # card / chart surface
PAGE = "#f7f4ef"  # page plane (site --color-base)
INK = "#1c1917"  # primary text
INK_SECONDARY = "#4a4541"
INK_MUTED = "#6b6560"  # axis labels, captions (site --color-ink-muted)
GRID = "#ebe6de"  # hairline gridlines
AXIS = "#cfc8bd"  # baseline / domain
NEUTRAL = "#c9c2b8"  # "nothing" fill: neutral category, raw-observation dots
ACCENT = "#8b1a1a"  # site accent (oxblood) — UI only, never a data series

# Sequential ramp end-points (one hue, terracotta): light = "little", dark = "a lot".
SEQ_LOW = "#f6ebe4"
SEQ_HIGH = "#9c3f1d"

DARK_CHROME: dict[str, str] = {
    SURFACE: "#211e1b",
    PAGE: "#161412",
    INK: "#f0ece6",
    INK_SECONDARY: "#cdc6bb",
    INK_MUTED: "#9a938a",
    GRID: "#2f2b27",
    AXIS: "#4a443e",
    NEUTRAL: "#5c5650",
    ACCENT: "#d46a6a",
    SEQ_LOW: "#2a2420",
    SEQ_HIGH: "#e0784a",
}

# Light hex -> dark hex.  The HTML shell applies this to every spec in dark mode.
DARK_MAP: dict[str, str] = {
    **dict(zip(SERIES_LIGHT, SERIES_DARK, strict=True)),
    **DARK_CHROME,
}

FONT_BODY = '"DM Sans", system-ui, -apple-system, "Segoe UI", sans-serif'

# --- Mark constants -------------------------------------------------------------

LINE_WIDTH = 2
DOT_SIZE = 64  # Vega-Lite size is area in px²: 64 ≈ 8 px diameter
RAW_DOT_SIZE = 22  # small, recessive dots for raw daily observations
BAR_MAX = 24  # px — bars never fill their band
CHART_HEIGHT = 240
LABEL_GUTTER = 72  # px of right padding for direct labels outside the plot


def config() -> dict[str, Any]:
    """Top-level Vega-Lite ``config`` block for every Egon chart."""
    return {
        "background": None,  # transparent: charts inherit their card surface
        "padding": {"top": 8, "right": 12, "bottom": 4, "left": 4},
        "font": FONT_BODY,
        "view": {"stroke": None, "continuousWidth": 640, "continuousHeight": CHART_HEIGHT},
        "axis": {
            "labelColor": INK_MUTED,
            "labelFont": FONT_BODY,
            "labelFontSize": 11,
            "titleColor": INK_MUTED,
            "titleFont": FONT_BODY,
            "titleFontSize": 11,
            "titleFontWeight": 500,
            "gridColor": GRID,
            "gridWidth": 1,
            "domainColor": AXIS,
            "tickColor": AXIS,
            "tickSize": 4,
            "labelPadding": 6,
            "titlePadding": 10,
        },
        "axisX": {"grid": False, "labelFlush": True},
        "axisY": {"domain": False, "ticks": False, "tickCount": 5},
        "legend": {
            "labelColor": INK_SECONDARY,
            "labelFont": FONT_BODY,
            "labelFontSize": 12,
            "titleColor": INK_MUTED,
            "titleFontSize": 11,
            "titleFontWeight": 500,
            "symbolType": "circle",
            "symbolSize": 90,
            "symbolStrokeWidth": 0,
            "orient": "top",
            "direction": "horizontal",
            "columnPadding": 16,
            "offset": 12,
        },
        "range": {"category": SERIES_LIGHT},
        "line": {"strokeWidth": LINE_WIDTH, "strokeCap": "round", "strokeJoin": "round"},
        "bar": {"cornerRadiusEnd": 4, "maxBandSize": BAR_MAX},
        "point": {"size": DOT_SIZE, "filled": True},
        "text": {"font": FONT_BODY, "fontSize": 11, "color": INK_SECONDARY},
        "title": {"font": FONT_BODY, "color": INK, "fontSize": 13, "fontWeight": 500},
        "header": {"labelFont": FONT_BODY, "labelColor": INK_SECONDARY, "titleFont": FONT_BODY},
        "tooltipFormat": {"numberFormat": ".2f"},
    }


def to_spec(chart: alt.TopLevelMixin) -> dict[str, Any]:
    """Serialise an Altair chart to a Vega-Lite dict with the Egon config applied."""
    spec = chart.to_dict()
    spec["config"] = config()
    # Single views stretch to their card ("fit-x" + width="container").  The
    # HTML shell resolves width="container" inside concatenations itself,
    # because Vega-Lite only supports container sizing for single views.
    is_concat = "hconcat" in spec or "vconcat" in spec or "concat" in spec
    spec["autosize"] = {"type": "pad" if is_concat else "fit-x", "contains": "padding"}
    return spec
