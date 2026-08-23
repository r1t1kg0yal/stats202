"""House style -- the single source of truth for how Altair output looks.

Everything that decides an appearance lives here: the colour palettes, the
heatmap gradients, the canvas ladder, the typographic ramp, and the named
house styles. Three modules read this one and none of them define an
appearance of their own:

    chart_functions.py               ──┐
    chart_functions_studio.py        ──┼──►  house_style.py
    chart_functions_studio_tables.py ──┘

The import graph runs one way. Nothing here imports a sibling, so a colour
can never be defined in two places and drift.

Why this module exists
----------------------
Before it, four registries described the same look and disagreed:

    engine charts   gs_clean only
    chart studio    gs_clean / minimal / dark / print
    table studio    gs_clean / mono / print / slate
    engine tables   a fourth private copy of the gs_clean colours

The same palette carried two names depending on which side asked for it
(``colorblind`` here, ``okabe_ito`` there), the theme labelled "exact
match to PRISM GS_CLEAN" set a different axis-title size than the engine
it claimed to match, and a ``slate`` table could not be paired with a
``slate`` chart because no such chart existed.

A house style is one identity rendered on two surfaces. Charts and tables
placed in the same exhibit match because they read the same anchors, not
because two lists happened to be edited together.

Vocabulary
----------
Palette names are SEMANTIC (what you want) rather than provenance-based
(where the hexes came from), because the semantic name is the one an LLM
can pick correctly: ``colorblind`` says what it guarantees, ``okabe_ito``
says who published it. Provenance names remain as aliases so either
vocabulary resolves.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "PALETTES", "GRADIENTS", "DIMENSIONS", "TYPE_SCALE", "HOUSE_STYLES",
    "DEFAULT_HOUSE_STYLE", "FONT_STACK",
    "GS_PRIMARY", "GS_DIVERGING", "MONO_BLUE", "MONO_GREY",
    "VIVID", "TABLEAU", "OKABE_ITO", "PASTEL",
    "resolve_palette", "get_palette", "palette_colors", "label_colors",
    "list_palettes", "categorical_palette_names",
    "is_gradient", "gradient_names", "gradients_of_kind",
    "get_dimensions", "dimension_names", "prism_dimension_names",
    "get_house_style", "house_style_names",
    "chart_axis_font_px", "table_font_px", "Y_AXIS_TITLE_MAX_CHARS",
    "table_theme", "TABLE_RAMPS", "RAG_COLORS", "RAMP_GREEN", "RAMP_GREY",
]


# ===========================================================================
# TYPOGRAPHY
# ===========================================================================

FONT_STACK: str = "GS Sans, Liberation Sans, Arial, sans-serif"

# One ramp for both surfaces. Font sizes are a property of the SLOT, never
# of the house style -- a skin recolours, it does not resize. Keeping the
# ramp here is what stops a second module from quietly setting an axis
# title to 16 while the renderer draws it at 18.
TYPE_SCALE: Dict[str, Dict[str, int]] = {
    "chart": {
        "title":                     26,
        "subtitle":                  14,
        "axis_label":                18,
        "axis_title":                18,
        "legend_label":              14,
        "legend_title":              14,
        # Composite slots. The super-title outranks a standalone title so a
        # pack header reads as the parent of its panels, and the per-panel
        # title drops below the standalone size so it defers upward.
        "composite_super_title":     32,
        "composite_super_subtitle":  22,
        "subchart_title":            18,
        "subchart_subtitle":         12,
    },
    "table": {
        "title":     22,
        "subtitle":  13,
        "header":    14,
        "body":      13,
        "caption":   11,
    },
}


# Hard cap on a y-axis title. The style guide puts the visual sweet spot
# near 16 characters; past this the label is a sentence rather than a
# label, and the engine refuses it. It lives here rather than in the
# renderer because the studio COMPOSES axis titles -- "Yield (%), 12-period
# annualised vol, %" -- and a copy of the limit that drifted would let it
# build a chart whose own regenerated call the engine rejects.
Y_AXIS_TITLE_MAX_CHARS: int = 28


def chart_axis_font_px() -> int:
    """Axis tick-label size in px -- the anchor for label width budgets."""
    return TYPE_SCALE["chart"]["axis_label"]


def table_font_px(slot: str) -> int:
    """Table font size for ``slot`` (title / subtitle / header / body / caption)."""
    try:
        return TYPE_SCALE["table"][slot]
    except KeyError:
        raise ValueError(
            f"Unknown table type slot {slot!r}. "
            f"Available: {', '.join(sorted(TYPE_SCALE['table']))}."
        ) from None


# ===========================================================================
# PALETTES
# ===========================================================================
#
# Categorical palettes are explicit hex lists because the engine hands them
# to Vega as a scale range. Sequential / diverging ramps are Vega scheme
# NAMES (see GRADIENTS) because Vega generates those colours itself.

GS_PRIMARY: Dict[str, Any] = {
    "name": "gs_primary",
    "label": "GS Primary",
    "kind": "categorical",
    "aliases": (),
    # Slot order: 0 navy (primary), 1 light blue (secondary), 2 mid blue,
    # 3 grey, 4 red (accent), 5 cobalt, 6 olive, 7 purple, 8 orange, 9 teal.
    "colors": ["#003359", "#94C7DD", "#5C92CB", "#A6A6A6", "#C00000",
               "#4F81BD", "#9BBB59", "#8064A2", "#F79646", "#4BACC6"],
    # Per-slot hex for LastValueLabel text. Identical to ``colors`` for the
    # slots that survive as 15pt type on white (navy, red, cobalt, purple,
    # orange, teal); darkened (HSL L * 0.55, hue and saturation preserved)
    # for the four that do not (light blue, mid blue, grey, olive).
    "label_colors": ["#003359", "#307A9A", "#274F7B", "#5B5B5B", "#C00000",
                     "#4F81BD", "#566B2C", "#8064A2", "#F79646", "#4BACC6"],
}

COLORBLIND: Dict[str, Any] = {
    "name": "colorblind",
    "label": "Colourblind-safe (Okabe-Ito)",
    "kind": "categorical",
    "aliases": ("okabe_ito", "okabe-ito"),
    "colors": ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2",
               "#D55E00", "#CC79A7", "#000000"],
}

BOLD: Dict[str, Any] = {
    "name": "bold",
    "label": "Bold",
    "kind": "categorical",
    "aliases": ("vivid",),
    "colors": ["#4c72ff", "#ffb347", "#ff6b6b", "#2ecc71", "#9b59b6",
               "#f39c12", "#1abc9c"],
}

BUSINESS: Dict[str, Any] = {
    "name": "business",
    "label": "Business (Tableau 10)",
    "kind": "categorical",
    "aliases": ("tableau", "tableau10"),
    "colors": ["#4c78a8", "#f58518", "#e45756", "#72b7b2", "#54a24b",
               "#eeca3b", "#b279a2", "#ff9da6", "#9d755d", "#bab0ac"],
}

MONO_NAVY: Dict[str, Any] = {
    "name": "mono_navy",
    "label": "Monochrome Navy",
    "kind": "categorical",
    "aliases": ("mono_blue",),
    "colors": ["#08306b", "#2171b5", "#6baed6", "#c6dbef", "#deebf7"],
}

MONO_GREY_P: Dict[str, Any] = {
    "name": "mono_grey",
    "label": "Monochrome Grey",
    "kind": "categorical",
    "aliases": ("mono_gray",),
    "colors": ["#111111", "#444444", "#777777", "#aaaaaa", "#dddddd"],
}

PASTEL_P: Dict[str, Any] = {
    "name": "pastel",
    "label": "Pastel",
    "kind": "categorical",
    "aliases": (),
    "colors": ["#A8DADC", "#FFB4A2", "#B5EAEA", "#FCE38A", "#C1A7E2",
               "#F8B5C8", "#A0D2DB", "#FFCFD2"],
}

GS_DIVERGING_P: Dict[str, Any] = {
    "name": "gs_diverging",
    "label": "GS Diverging",
    "kind": "diverging",
    "aliases": (),
    "colors": ["#C00000", "#F79646", "#FFFFFF", "#5C92CB", "#003359"],
}


_PALETTE_LIST: Tuple[Dict[str, Any], ...] = (
    GS_PRIMARY, COLORBLIND, BOLD, BUSINESS,
    MONO_NAVY, MONO_GREY_P, PASTEL_P, GS_DIVERGING_P,
)

PALETTES: Dict[str, Dict[str, Any]] = {p["name"]: p for p in _PALETTE_LIST}

_PALETTE_ALIASES: Dict[str, str] = {
    alias: p["name"] for p in _PALETTE_LIST for alias in p["aliases"]
}

# Provenance-named aliases kept as module attributes so callers that grew up
# against the studio vocabulary keep resolving. These are the SAME objects,
# never copies -- editing a hex in one place changes it everywhere.
GS_DIVERGING = GS_DIVERGING_P
MONO_BLUE = MONO_NAVY
MONO_GREY = MONO_GREY_P
VIVID = BOLD
TABLEAU = BUSINESS
OKABE_ITO = COLORBLIND
PASTEL = PASTEL_P


def resolve_palette(name: str) -> str:
    """Map any accepted palette spelling to its canonical name.

    Accepts semantic names (``colorblind``) and provenance aliases
    (``okabe_ito``) alike so a studio selection and an engine kwarg cannot
    disagree about the same colours.
    """
    key = str(name).strip().lower()
    if key in PALETTES:
        return key
    if key in _PALETTE_ALIASES:
        return _PALETTE_ALIASES[key]
    raise ValueError(
        f"Unknown palette {name!r}. Available: "
        f"{', '.join(sorted(PALETTES))}."
    )


def get_palette(name: str) -> Dict[str, Any]:
    """Return the palette record for ``name`` (canonical or alias)."""
    return PALETTES[resolve_palette(name)]


def palette_colors(name: str) -> List[str]:
    """Hex list for ``name``, as a fresh list the caller may mutate."""
    return list(get_palette(name)["colors"])


def label_colors(name: str) -> List[str]:
    """Per-slot text hex for ``name``.

    Falls back to the mark colours for palettes that do not publish a
    darkened text variant, which is the behaviour every non-GS palette has
    always had.
    """
    palette = get_palette(name)
    return list(palette.get("label_colors", palette["colors"]))


def list_palettes() -> List[Dict[str, Any]]:
    """All palette records, canonical order."""
    return [copy.deepcopy(p) for p in _PALETTE_LIST]


def categorical_palette_names() -> List[str]:
    """Canonical names of the categorical palettes, in registry order."""
    return [p["name"] for p in _PALETTE_LIST if p["kind"] == "categorical"]


# ===========================================================================
# GRADIENTS (Vega-generated sequential / diverging ramps)
# ===========================================================================

GRADIENTS: Dict[str, str] = {
    # sequential
    "blues": "sequential", "greens": "sequential", "reds": "sequential",
    "oranges": "sequential", "purples": "sequential", "greys": "sequential",
    "viridis": "sequential", "plasma": "sequential", "magma": "sequential",
    "cividis": "sequential", "turbo": "sequential", "inferno": "sequential",
    "rainbow": "sequential",
    # diverging
    "redblue": "diverging", "spectral": "diverging",
    "browngreen": "diverging", "redyellowblue": "diverging",
    "redyellowgreen": "diverging", "blueorange": "diverging",
}


def is_gradient(name: str) -> bool:
    return str(name).strip().lower() in GRADIENTS


def gradient_names() -> List[str]:
    return sorted(GRADIENTS)


def gradients_of_kind(kind: str) -> List[str]:
    return sorted(n for n, k in GRADIENTS.items() if k == kind)


# ===========================================================================
# DIMENSIONS
# ===========================================================================
#
# One canvas ladder. ``prism`` marks the presets the skill publishes to
# PRISM; the rest exist because the studio offers them as resize targets and
# a studio selection has to be expressible as a make_chart() kwarg.

DIMENSIONS: Dict[str, Dict[str, Any]] = {
    "wide":         {"width": 700,  "height": 350,  "label": "Wide (700x350)",         "prism": True},
    "square":       {"width": 450,  "height": 450,  "label": "Square (450x450)",       "prism": True},
    "tall":         {"width": 400,  "height": 550,  "label": "Tall (400x550)",         "prism": True},
    "compact":      {"width": 400,  "height": 300,  "label": "Compact (400x300)",      "prism": True},
    "presentation": {"width": 900,  "height": 500,  "label": "Presentation (900x500)", "prism": True},
    "thumbnail":    {"width": 300,  "height": 200,  "label": "Thumbnail (300x200)",    "prism": True},
    "teams":        {"width": 420,  "height": 210,  "label": "Teams (420x210)",        "prism": True},
    "report":       {"width": 600,  "height": 400,  "label": "Report (600x400)",       "prism": False},
    "dashboard":    {"width": 800,  "height": 500,  "label": "Dashboard (800x500)",    "prism": False},
    "widescreen":   {"width": 1200, "height": 500,  "label": "Widescreen (1200x500)",  "prism": False},
    "twopack":      {"width": 540,  "height": 360,  "label": "2-pack tile (540x360)",  "prism": False},
    "fourpack":     {"width": 420,  "height": 280,  "label": "4-pack tile (420x280)",  "prism": False},
    # Sentinel: facet panel dimensions derive from the grid shape at render
    # time. The pair is the usable outer area on US Letter portrait that
    # the facet resolver divides up.
    "page_grid":    {"width": 1200, "height": 1600, "label": "Page grid (facet)",      "prism": True},
}

# Small canvases need a tighter ramp or the type overwhelms the plot. Applied
# by whichever consumer is rendering; the values live here so both agree.
DIMENSION_TYPE_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "teams": {
        "title": 12, "axis_label": 8, "axis_title": 9,
        "legend_label": 8, "legend_title": 9,
        "stroke_width": 1.5, "point_size": 40,
    },
    "thumbnail": {
        "title": 10, "axis_label": 7, "axis_title": 8,
        "legend_label": 7, "legend_title": 8,
        "stroke_width": 1.2, "point_size": 30,
    },
    "compact": {
        "title": 18, "axis_label": 12, "axis_title": 13,
        "legend_label": 10, "legend_title": 11,
        "stroke_width": 1.8, "point_size": 50,
    },
}


def get_dimensions(name: str) -> Tuple[int, int]:
    """(width, height) in px for a preset name."""
    key = str(name).strip().lower()
    if key not in DIMENSIONS:
        raise ValueError(
            f"Unknown dimension preset {name!r}. Available: "
            f"{', '.join(sorted(DIMENSIONS))}."
        )
    entry = DIMENSIONS[key]
    return entry["width"], entry["height"]


def dimension_names() -> List[str]:
    return list(DIMENSIONS)


def prism_dimension_names() -> List[str]:
    return [n for n, d in DIMENSIONS.items() if d["prism"]]


# ===========================================================================
# HOUSE STYLES
# ===========================================================================
#
# A house style is a set of colour anchors, a palette, and a gradient. Both
# surfaces read the same anchors:
#
#   ANCHOR         CHART USE                      TABLE USE
#   primary        series slot 0, emphasis        header band, total row
#   secondary      series slot 1                  secondary header band
#   accent         alert / threshold marks        negative values
#   background     canvas fill                    canvas fill
#   ink            axis line, ticks, tick labels, body text
#                  title text
#   subtitle_ink   subtitle prose                 -
#   muted_ink      -                              de-emphasised cell text
#   rule           -                              cell borders
#   band           -                              zebra row fill
#   band_alt       -                              subtotal row fill
#   highlight      -                              highlighted column fill
#   positive       -                              positive numeric text
#   negative       -                              negative numeric text
#   header_ink     -                              text on the primary band
#
# ``subtitle_ink`` and ``muted_ink`` stay distinct deliberately: prose under
# a chart title and a de-emphasised table cell are different jobs and have
# always carried different values. They are adjacent here so the difference
# is a visible decision rather than an accident split across two files.

GS_CLEAN_STYLE: Dict[str, Any] = {
    "name": "gs_clean",
    "label": "GS Clean",
    "description": "PRISM default. Navy on white, GS Sans, full colour palette.",
    "palette": "gs_primary",
    "gradient": "blues",
    "diverging_gradient": "redblue",
    "font_family": FONT_STACK,
    "primary":      "#003359",
    "secondary":    "#94C7DD",
    "accent":       "#C00000",
    "background":   "#FFFFFF",
    "ink":          "#000000",
    "subtitle_ink": "#333333",
    "muted_ink":    "#5B5B5B",
    "trendline":    "#999999",
    "rule":         "#1F1F1F",
    "band":         "#F7F7F7",
    "band_alt":     "#EFEFEF",
    "highlight":    "#E8F0F7",
    "positive":     "#0E7A28",
    "negative":     "#C00000",
    "header_ink":   "#FFFFFF",
    "mark_overrides": {},
}

MONO_STYLE: Dict[str, Any] = {
    "name": "mono",
    "label": "Monochrome",
    "description": "Greyscale throughout. Use when colour would imply a "
                   "distinction the data does not support.",
    "palette": "mono_grey",
    "gradient": "greys",
    "diverging_gradient": "greys",
    "font_family": FONT_STACK,
    "primary":      "#1F1F1F",
    "secondary":    "#5B5B5B",
    "accent":       "#1F1F1F",
    "background":   "#FFFFFF",
    "ink":          "#000000",
    "subtitle_ink": "#5B5B5B",
    "muted_ink":    "#5B5B5B",
    "trendline":    "#999999",
    "rule":         "#1F1F1F",
    "band":         "#F4F4F4",
    "band_alt":     "#E8E8E8",
    "highlight":    "#EDEDED",
    "positive":     "#1F1F1F",
    "negative":     "#1F1F1F",
    "header_ink":   "#FFFFFF",
    "mark_overrides": {},
}

PRINT_STYLE: Dict[str, Any] = {
    "name": "print",
    "label": "Print",
    "description": "Maximum contrast, heavier strokes, no fills. Survives "
                   "photocopying and greyscale printing.",
    "palette": "mono_grey",
    "gradient": "greys",
    "diverging_gradient": "greys",
    "font_family": FONT_STACK,
    "primary":      "#000000",
    "secondary":    "#444444",
    "accent":       "#000000",
    "background":   "#FFFFFF",
    "ink":          "#000000",
    "subtitle_ink": "#333333",
    "muted_ink":    "#333333",
    "trendline":    "#666666",
    "rule":         "#000000",
    "band":         "#FFFFFF",
    "band_alt":     "#F2F2F2",
    "highlight":    "#F2F2F2",
    "positive":     "#000000",
    "negative":     "#000000",
    "header_ink":   "#FFFFFF",
    "mark_overrides": {
        "line": {"strokeWidth": 3},
        "point": {"size": 80},
    },
}

SLATE_STYLE: Dict[str, Any] = {
    "name": "slate",
    "label": "Slate",
    "description": "Muted slate frame with the standard series palette. "
                   "Reads quieter than gs_clean without losing colour.",
    "palette": "gs_primary",
    "gradient": "blues",
    "diverging_gradient": "redblue",
    "font_family": FONT_STACK,
    "primary":      "#22303C",
    "secondary":    "#4A6274",
    "accent":       "#C00000",
    "background":   "#FFFFFF",
    "ink":          "#12181F",
    "subtitle_ink": "#5A6B79",
    "muted_ink":    "#5A6B79",
    "trendline":    "#8A9AA6",
    "rule":         "#22303C",
    "band":         "#F5F7F9",
    "band_alt":     "#E9EEF2",
    "highlight":    "#EAF1F7",
    "positive":     "#0E7A28",
    "negative":     "#B3261E",
    "header_ink":   "#FFFFFF",
    "mark_overrides": {},
}

DARK_STYLE: Dict[str, Any] = {
    "name": "dark",
    "label": "Dark",
    "description": "Light-on-dark for screen viewing. Not a print style.",
    "palette": "bold",
    "gradient": "viridis",
    "diverging_gradient": "spectral",
    "font_family": FONT_STACK,
    "primary":      "#4C72FF",
    "secondary":    "#8FA6FF",
    "accent":       "#FF6B6B",
    "background":   "#121212",
    "ink":          "#EAEAEA",
    "subtitle_ink": "#B0B0B0",
    "muted_ink":    "#9A9A9A",
    "trendline":    "#7A7A7A",
    "rule":         "#3A3A3A",
    "band":         "#1C1C1C",
    "band_alt":     "#262626",
    "highlight":    "#1E2A44",
    "positive":     "#4ADE80",
    "negative":     "#FF6B6B",
    "header_ink":   "#FFFFFF",
    "mark_overrides": {},
}


_HOUSE_STYLE_LIST: Tuple[Dict[str, Any], ...] = (
    GS_CLEAN_STYLE, MONO_STYLE, PRINT_STYLE, SLATE_STYLE, DARK_STYLE,
)

HOUSE_STYLES: Dict[str, Dict[str, Any]] = {
    s["name"]: s for s in _HOUSE_STYLE_LIST
}

DEFAULT_HOUSE_STYLE: str = "gs_clean"


def get_house_style(name: Optional[str] = None) -> Dict[str, Any]:
    """Deep-copied house style record.

    Copied because both consumers merge their own surface-specific keys on
    top; a shared mutable would let one surface's merge leak into the other.
    """
    key = DEFAULT_HOUSE_STYLE if name is None else str(name).strip().lower()
    if key not in HOUSE_STYLES:
        raise ValueError(
            f"Unknown house style {name!r}. Available: "
            f"{', '.join(sorted(HOUSE_STYLES))}."
        )
    return copy.deepcopy(HOUSE_STYLES[key])


def house_style_names() -> List[str]:
    """Canonical house style names, in registry order."""
    return [s["name"] for s in _HOUSE_STYLE_LIST]


# ===========================================================================
# TABLE SURFACE
# ===========================================================================

# Anchor name on the house style -> key the table engine and table studio
# both use for it. Declared as data rather than written twice so a new
# anchor reaches both surfaces at once.
_TABLE_ANCHOR_KEYS: Tuple[Tuple[str, str], ...] = (
    ("primary",    "primary_color"),
    ("secondary",  "secondary_color"),
    ("accent",     "accent_color"),
    ("background", "background_color"),
    ("band",       "row_band_color"),
    ("band_alt",   "subtotal_band"),
    ("primary",    "total_band"),
    ("rule",       "border_color"),
    ("muted_ink",  "muted_text"),
    ("header_ink", "header_text"),
    ("ink",        "body_text"),
    ("positive",   "positive_text"),
    ("negative",   "negative_text"),
    ("highlight",  "highlight_color"),
)


def table_theme(name: Optional[str] = None, *, include_label: bool = False) -> Dict[str, Any]:
    """Table-side colour anchors for a house style.

    The table engine renders the PNG and the table studio recolours it live
    in the browser; both read this, so a colour changed in the editor is the
    colour the regenerated call produces.
    """
    style = get_house_style(name)
    theme = {key: style[anchor] for anchor, key in _TABLE_ANCHOR_KEYS}
    if include_label:
        theme = {"label": style["label"], **theme}
    return theme


# Conditional-formatting ramps for table cells. Deliberately NOT keyed by
# house style: ``rwg`` means red-negative / green-positive whatever frame
# the table wears, because the ramp encodes the DATA's sign, not the
# document's identity. A mono table still shows a red loss.
#
# ``max_i`` caps fill intensity so the darkest cell stays readable with body
# text on top.
RAMP_GREEN: str = "#3C9A4E"
RAMP_GREY: str = "#5B5B5B"

TABLE_RAMPS: Dict[str, Dict[str, Any]] = {
    "bw":      {"kind": "sequential", "end": GS_PRIMARY["colors"][2], "max_i": 0.70},
    "wb":      {"kind": "sequential", "end": GS_PRIMARY["colors"][2], "max_i": 0.70},
    "wb_full": {"kind": "sequential", "end": GS_PRIMARY["colors"][0], "max_i": 0.65},
    "wg":      {"kind": "sequential", "end": RAMP_GREEN,              "max_i": 0.65},
    "wr":      {"kind": "sequential", "end": GS_PRIMARY["colors"][4], "max_i": 0.55},
    "wo":      {"kind": "sequential", "end": GS_PRIMARY["colors"][8], "max_i": 0.65},
    "wgrey":   {"kind": "sequential", "end": RAMP_GREY,               "max_i": 0.55},
    "rwg":     {"kind": "diverging", "neg": GS_PRIMARY["colors"][4], "pos": RAMP_GREEN,              "max_i": 0.65},
    "rwb":     {"kind": "diverging", "neg": GS_PRIMARY["colors"][4], "pos": GS_PRIMARY["colors"][0], "max_i": 0.65},
    "bwr":     {"kind": "diverging", "neg": GS_PRIMARY["colors"][0], "pos": GS_PRIMARY["colors"][4], "max_i": 0.65},
    "owb":     {"kind": "diverging", "neg": GS_PRIMARY["colors"][8], "pos": GS_PRIMARY["colors"][0], "max_i": 0.65},
}

# Discrete red / amber / green buckets. Pale enough to sit under body text.
RAG_COLORS: Dict[str, str] = {
    "red": "#F4D6D6", "amber": "#FCE9CC", "green": "#D8EED8",
}