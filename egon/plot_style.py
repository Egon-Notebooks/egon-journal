"""
Shared matplotlib style for all egon-journal report plots.

Applying this style gives every figure a consistent, editorial look that
matches the Egon Notebooks aesthetic: clean serif typography, generous
spacing, and muted but distinct colour palettes.

Usage (at the top of each plot function, before creating figures):
    from egon.plot_style import apply_style
    apply_style()
"""
import matplotlib.pyplot as plt

# Ordered font preference: macOS Palatino → Linux/Windows fallbacks → generic serif.
# Palatino has an elegant, literary quality well-suited to personal journaling.
_FONT_SERIF = ["Palatino", "Palatino Linotype", "Georgia", "Times New Roman", "serif"]

# --- Size constants (exported so plot modules can use them explicitly) ---
TITLE_SIZE = 15      # subplot and figure titles
LABEL_SIZE = 12      # axis labels (ylabel / xlabel)
TICK_SIZE = 11       # tick labels
LEGEND_SIZE = 11     # legend entries
ANNOTATION_SIZE = 22 # right-side personality annotations (bigfive / mbti)


def apply_style() -> None:
    """
    Apply the egon-journal house style to matplotlib rcParams.

    Call this once at the start of every plot function so that all text,
    ticks, and legends inherit the correct font and size automatically.
    The change is global for the duration of the process; call
    ``matplotlib.rcdefaults()`` afterwards if you need to reset.
    """
    plt.rcParams.update({
        # --- Typography ---
        "font.family": "serif",
        "font.serif": _FONT_SERIF,
        "mathtext.fontset": "dejavuserif",

        # --- Font sizes ---
        "axes.titlesize": TITLE_SIZE,
        "axes.labelsize": LABEL_SIZE,
        "xtick.labelsize": TICK_SIZE,
        "ytick.labelsize": TICK_SIZE,
        "legend.fontsize": LEGEND_SIZE,

        # --- Figure background ---
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })
