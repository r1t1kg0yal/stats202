"""
echarts.config -- single-source style configuration, locked to the
Goldman Sachs brand identity.

EDIT STYLES HERE. There is exactly one theme (``gs_clean``) and a
minimal set of Goldman Sachs palettes: one categorical (``gs_primary``),
one sequential (``gs_blues``), and one diverging (``gs_diverging``).

    PALETTES                GS palettes (3)
    THEMES                  GS theme (1)
    DIMENSION_PRESETS       12 named (w, h) presets
    TYPOGRAPHY_OVERRIDES    small-preset font-size overrides

Three sections:
    1. PALETTES           categorical / sequential / diverging
    2. THEMES             ECharts theme JSON + knob_values
    3. DIMENSIONS         (w, h) presets + typography overrides

Accessors (get_theme / get_palette / get_dimension_preset) raise
ValueError for unknown names -- no silent fallbacks.

Brand provenance
----------------
Tokens at the top derive from the published GS brand guidelines and
design system:

  - PMS 652 "GS Sky Blue" #7399C6 -- the core logo color.
  - GS Navy #002F6C -- used for deep headlines / primary series in
    print (investor-relations decks, sustainability reports).
  - Typeface stack: "Goldman Sans" / "GS Sans" (2020+ house sans), with
    "GS Serif" available for report-grade headlines. Web-safe
    fallbacks: Helvetica Neue, Arial.
"""

from __future__ import annotations

from typing import Any, Dict, List


# =============================================================================
# GS BRAND TOKENS
# =============================================================================
# Single source of truth for brand colors and fonts. Palettes and the
# theme below are built from these constants so a token change
# propagates everywhere.

GS_SKY          = "#7399C6"   # PMS 652 -- core logo color
GS_NAVY         = "#002F6C"   # deep navy -- headlines / primary series
GS_NAVY_DEEP    = "#001B40"   # darker navy -- reserved for deep accents
GS_INK          = "#1A1A1A"   # body text
GS_PAPER        = "#FFFFFF"
GS_BG           = "#F7F9FB"   # off-white surface for dashboard chrome
GS_GREY_80      = "#333333"
GS_GREY_70      = "#595959"
GS_GREY_40      = "#999999"
GS_GREY_20      = "#BFBFBF"
GS_GREY_10      = "#D9DCE1"
GS_GREY_05      = "#EEF1F5"

# Dark-mode chrome tokens. The brand mark stays navy in either mode
# (it's the iconic GS logo), but the dashboard surfaces invert from
# off-white to dark navy-tinted greys so chart series and KPI text
# stay legible. These are paired 1:1 with the light tokens above so
# every CSS variable in the chrome has a dark twin.
GS_DARK_BG          = "#0A1525"   # page background (very dark navy)
GS_DARK_SURFACE     = "#142442"   # cards / tiles
GS_DARK_SURFACE_2   = "#1B2D4F"   # subtle inset (drawer, controls)
GS_DARK_SURFACE_HOV = "#233758"   # hover overlay
GS_DARK_TEXT        = "#F2F4F8"   # primary text
GS_DARK_TEXT_DIM    = "#B5C0D0"   # secondary text
GS_DARK_TEXT_FAINT  = "#7A8699"   # tertiary text
GS_DARK_BORDER      = "#233758"   # default border
GS_DARK_BORDER_STR  = "#2D4570"   # strong border

# Dark-mode chart-series palette. Each is a brightened twin of the
# matching light brand colour above. The dark bg (#142442) and page
# (#0A1525) are too close in luminance to GS_NAVY / GS_FOREST /
# GS_BURGUNDY / GS_BRICK / GS_STEEL / GS_SLATE / GS_TEAL for those
# tokens to render as visible chart marks, so dark mode swaps them
# for these brighter variants. Hue order is preserved so a multi-
# series chart's colour identity carries across the toggle: a series
# that was "GS Navy" in light mode appears as the bright royal-blue
# variant in dark mode, not as a different hue entirely.
GS_NAVY_BRIGHT      = "#5A8FCF"   # brighter royal blue (was GS_NAVY)
GS_GOLD_BRIGHT      = "#DBC275"   # brighter gold       (was GS_GOLD)
GS_BURGUNDY_BRIGHT  = "#D17A9D"   # rose                (was GS_BURGUNDY)
GS_FOREST_BRIGHT    = "#6FCD56"   # bright green        (was GS_FOREST)
GS_SLATE_BRIGHT     = "#9CB8C7"   # bright slate        (was GS_SLATE)
GS_PLUM_BRIGHT      = "#B79DD8"   # bright lavender     (was GS_PLUM)
GS_AMBER_BRIGHT     = "#F0A845"   # bright amber/orange (was GS_AMBER)
GS_BRICK_BRIGHT     = "#D87A7A"   # bright brick/coral  (was GS_BRICK)
GS_STEEL_BRIGHT     = "#93AECF"   # bright steel        (was GS_STEEL)
GS_TEAL_BRIGHT      = "#4FBFBA"   # bright teal         (was GS_TEAL)

# accents for multi-series charts -- all desaturated so they coexist
# with GS Navy and Sky Blue without clashing.
GS_GOLD         = "#B08D3F"
GS_BURGUNDY     = "#8C1D40"
GS_FOREST       = "#3E7C17"
GS_SLATE        = "#5A7D8C"
GS_PLUM         = "#6E4B9E"
GS_AMBER        = "#D47B00"
GS_BRICK        = "#9B2C2C"
GS_STEEL        = "#4C6B8A"
GS_TEAL         = "#157F7D"

# semantic colors for KPI deltas, up/down markers
GS_POS          = "#2E7D32"
GS_NEG          = "#B3261E"

# Typeface stacks. The GS in-house families (Goldman Sans, GS Sans, GS
# Serif) are proprietary so we reference them at the front of the stack
# and fall back to web-safe equivalents.
GS_FONT_SANS = (
    '"Goldman Sans", "GS Sans", "Basis Grotesque", '
    '"Helvetica Neue", Arial, sans-serif'
)
GS_FONT_SERIF = (
    '"GS Serif", Georgia, "Times New Roman", serif'
)
GS_FONT_MONO = (
    '"GS Sans Mono", "JetBrains Mono", "SF Mono", Consolas, monospace'
)


# =============================================================================
# SECTION 1 -- PALETTES
# =============================================================================
#
# Three GS palettes:
#
#   gs_primary      categorical   navy + sky + accents
#   gs_blues        sequential    single-hue sky-to-navy ramp
#   gs_diverging    diverging     burgundy -> gold -> white -> sky -> navy
#
# Applied to options as:
#   categorical  -> option.color = colors
#   sequential   -> visualMap.inRange.color stops
#   diverging    -> same; 5-point ramp centered at white

PALETTES: Dict[str, Dict[str, Any]] = {
    "gs_primary": {
        "name": "gs_primary",
        "label": "GS Primary (navy + sky + accents)",
        "kind": "categorical",
        "colors": [
            GS_NAVY,       # primary series
            GS_SKY,        # secondary series (logo color)
            GS_GOLD,
            GS_BURGUNDY,
            GS_FOREST,
            GS_SLATE,
            GS_PLUM,
            GS_AMBER,
            GS_BRICK,
            GS_STEEL,
        ],
    },
    "gs_blues": {
        "name": "gs_blues",
        "label": "GS Blues (sky-to-navy sequential)",
        "kind": "sequential",
        "colors": [
            "#F5F8FC", "#D0DCED", "#9BB4D4", "#6288B3", "#305890",
            GS_NAVY_DEEP,
        ],
    },
    "gs_diverging": {
        "name": "gs_diverging",
        "label": "GS Diverging (burgundy-gold-navy)",
        "kind": "diverging",
        "colors": [GS_BURGUNDY, GS_AMBER, GS_PAPER, GS_SKY, GS_NAVY],
    },
}


def get_palette(name: str) -> Dict[str, Any]:
    """Return palette spec by name. Raises ValueError on unknown name."""
    if name not in PALETTES:
        raise ValueError(
            f"Unknown palette '{name}'. Available: "
            f"{', '.join(sorted(PALETTES.keys()))}"
        )
    return PALETTES[name]


def list_palettes() -> List[Dict[str, Any]]:
    """Return list of summary dicts for all palettes."""
    return [
        {"name": p["name"], "label": p["label"], "kind": p["kind"],
         "n_colors": len(p["colors"])}
        for p in PALETTES.values()
    ]


def palette_colors(name: str) -> List[str]:
    """Return just the color list for a palette. Raises on unknown name."""
    return list(get_palette(name)["colors"])


# =============================================================================
# SECTION 2 -- THEME
# =============================================================================
#
# One theme. ``gs_clean`` is the canonical Goldman Sachs look: navy
# primary series, sky blue secondary, GS Sans typeface, white paper
# background with a thin grey grid. This is the only theme; callers
# that accept a ``theme`` parameter exist for API symmetry but there is
# nothing else to choose.
#
# The theme dict has two top-level parts:
#
#   "echarts":     ECharts theme JSON (registered in-browser via
#                  echarts.registerTheme)
#   "knob_values": flat {knob_name: value} map consumed by the editor


def _axis_block(label_color: str, axis_color: str, split_color: str,
                 label_size: int = 12) -> Dict[str, Any]:
    return {
        "axisLine": {"show": True, "lineStyle": {"color": axis_color}},
        "axisTick": {"show": True, "lineStyle": {"color": axis_color}},
        "axisLabel": {"show": True, "color": label_color,
                       "fontSize": label_size},
        "splitLine": {"show": True, "lineStyle": {"color": [split_color]}},
        "splitArea": {"show": False},
        "nameTextStyle": {"color": label_color, "fontSize": label_size},
    }


def _build_gs_clean() -> Dict[str, Any]:
    palette = palette_colors("gs_primary")
    echarts_theme = {
        "color": palette,
        "backgroundColor": GS_PAPER,
        "textStyle": {"fontFamily": GS_FONT_SANS, "color": GS_INK},
        "title": {
            "textStyle": {
                "fontFamily": GS_FONT_SANS,
                "fontSize": 18, "fontWeight": 600, "color": GS_INK,
            },
            "subtextStyle": {
                "fontFamily": GS_FONT_SANS,
                "fontSize": 12, "color": GS_GREY_70,
            },
            "left": "left",
        },
        "line": {"lineStyle": {"width": 2}, "symbolSize": 6,
                  "symbol": "circle", "smooth": False},
        "bar": {"itemStyle": {"borderRadius": 0}},
        "scatter": {"symbolSize": 10, "symbol": "circle"},
        "categoryAxis": _axis_block(GS_INK, GS_GREY_40, GS_GREY_10),
        "valueAxis": {
            **_axis_block(GS_INK, GS_GREY_40, GS_GREY_10),
            "axisLine": {"show": False,
                          "lineStyle": {"color": GS_GREY_40}},
            "axisTick": {"show": False,
                          "lineStyle": {"color": GS_GREY_40}},
        },
        "timeAxis": _axis_block(GS_INK, GS_GREY_40, GS_GREY_10),
        "logAxis":  _axis_block(GS_INK, GS_GREY_40, GS_GREY_10),
        "legend": {
            "textStyle": {"color": GS_INK, "fontSize": 12,
                            "fontFamily": GS_FONT_SANS},
            "orient": "horizontal", "top": 42, "right": 10,
            "type": "scroll",
        },
        "tooltip": {
            "backgroundColor": GS_PAPER,
            "borderColor": GS_GREY_10,
            "borderWidth": 1,
            "textStyle": {"color": GS_INK, "fontFamily": GS_FONT_SANS,
                           "fontSize": 12},
            "axisPointer": {
                "lineStyle": {"color": GS_GREY_70, "width": 1},
                "crossStyle": {"color": GS_GREY_70, "width": 1},
            },
        },
        "visualMap": {"color": palette_colors("gs_blues")},
        "toolbox": {
            "top": 8,
            "right": 10,
            "itemSize": 14,
            "itemGap": 8,
            "iconStyle": {"borderColor": GS_GREY_70},
            "emphasis": {"iconStyle": {"borderColor": GS_NAVY}},
        },
    }
    knob_values = {
        "backgroundColor": GS_PAPER,
        "fontFamily": GS_FONT_SANS,
        "titleSize": 18,
        "titleColor": GS_INK,
        "titleWeight": "600",
        "titleLeft": "left",
        "subtitleSize": 12,
        "subtitleColor": GS_GREY_70,
        "labelSize": 12,
        "axisTitleSize": 12,
        "legendLabelSize": 12,
        "gridColor": GS_GREY_10,
        "gridShow": True,
        "gridTop": 80,
        "gridRight": 20,
        "gridBottom": 84,
        "gridLeft": 76,
        "legendShow": True,
        "legendOrient": "horizontal",
        "legendPosition": "top",
        "tooltipShow": True,
        "tooltipTrigger": "axis",
        "axisPointerType": "cross",
        "toolboxShow": True,
        "dataZoomShow": False,
        "strokeWidth": 2,
        "pointSize": 10,
        "barOpacity": 1.0,
        "areaOpacity": 0.3,
        "primaryColor": GS_NAVY,
        "splitLineColor": GS_GREY_10,
    }
    return {
        "name": "gs_clean",
        "label": "GS Clean (canonical)",
        "description": "Navy + sky on paper, GS Sans, thin grey grid",
        "palette": "gs_primary",
        "echarts": echarts_theme,
        "knob_values": knob_values,
    }


def _build_gs_clean_dark() -> Dict[str, Any]:
    """Dark twin of ``gs_clean``.

    The chart palette mirrors ``gs_primary`` slot-for-slot but each
    entry is swapped for the brightened twin defined at the top of
    this module so every series remains visible against the dark
    navy chart surface (#142442). The slot order is preserved so a
    series that was, say, the third colour in light mode renders in
    the bright twin of the third colour in dark mode -- colour
    identity carries across the toggle. Backgrounds, text, axis
    lines, and grid lines are pulled from the GS_DARK_* tokens.
    """
    palette = [
        GS_NAVY_BRIGHT,       # primary  -- was GS_NAVY
        GS_SKY,               # secondary (already light, unchanged)
        GS_GOLD_BRIGHT,       # was GS_GOLD
        GS_BURGUNDY_BRIGHT,   # was GS_BURGUNDY
        GS_FOREST_BRIGHT,     # was GS_FOREST
        GS_SLATE_BRIGHT,      # was GS_SLATE
        GS_PLUM_BRIGHT,       # was GS_PLUM
        GS_AMBER_BRIGHT,      # was GS_AMBER
        GS_BRICK_BRIGHT,      # was GS_BRICK
        GS_STEEL_BRIGHT,      # was GS_STEEL
    ]
    bg = GS_DARK_SURFACE
    grid = GS_DARK_BORDER
    axis = GS_DARK_TEXT_FAINT
    label = GS_DARK_TEXT
    echarts_theme = {
        "color": palette,
        "backgroundColor": bg,
        "textStyle": {"fontFamily": GS_FONT_SANS, "color": label},
        "title": {
            "textStyle": {
                "fontFamily": GS_FONT_SANS,
                "fontSize": 18, "fontWeight": 600, "color": label,
            },
            "subtextStyle": {
                "fontFamily": GS_FONT_SANS,
                "fontSize": 12, "color": GS_DARK_TEXT_DIM,
            },
            "left": "left",
        },
        "line": {"lineStyle": {"width": 2}, "symbolSize": 6,
                  "symbol": "circle", "smooth": False},
        "bar": {"itemStyle": {"borderRadius": 0}},
        "scatter": {"symbolSize": 10, "symbol": "circle"},
        "categoryAxis": _axis_block(label, axis, grid),
        "valueAxis": {
            **_axis_block(label, axis, grid),
            "axisLine": {"show": False,
                          "lineStyle": {"color": axis}},
            "axisTick": {"show": False,
                          "lineStyle": {"color": axis}},
        },
        "timeAxis": _axis_block(label, axis, grid),
        "logAxis":  _axis_block(label, axis, grid),
        "legend": {
            "textStyle": {"color": label, "fontSize": 12,
                            "fontFamily": GS_FONT_SANS},
            "orient": "horizontal", "top": 42, "right": 10,
            "type": "scroll",
        },
        "tooltip": {
            "backgroundColor": GS_DARK_SURFACE_2,
            "borderColor": GS_DARK_BORDER_STR,
            "borderWidth": 1,
            "textStyle": {"color": label, "fontFamily": GS_FONT_SANS,
                           "fontSize": 12},
            "axisPointer": {
                "lineStyle": {"color": GS_DARK_TEXT_DIM, "width": 1},
                "crossStyle": {"color": GS_DARK_TEXT_DIM, "width": 1},
            },
        },
        # Inverted single-hue ramp for dark-mode heatmaps: the
        # ``low`` end sits just above the chart surface so empty
        # cells fade out, while the ``high`` end is a bright sky
        # tint that pops against the dark navy bg. Mirrors gs_blues
        # in stop count but flips lightness direction.
        "visualMap": {"color": [
            "#1B2D4F", "#2C4670", "#3D5F90",
            "#5079AE", "#6F9CC9", "#A6CFEC",
        ]},
        "toolbox": {
            "top": 8,
            "right": 10,
            "itemSize": 14,
            "itemGap": 8,
            "iconStyle": {"borderColor": GS_DARK_TEXT_DIM},
            "emphasis": {"iconStyle": {"borderColor": GS_SKY}},
        },
    }
    knob_values = {
        "backgroundColor": bg,
        "fontFamily": GS_FONT_SANS,
        "titleSize": 18,
        "titleColor": label,
        "titleWeight": "600",
        "titleLeft": "left",
        "subtitleSize": 12,
        "subtitleColor": GS_DARK_TEXT_DIM,
        "labelSize": 12,
        "axisTitleSize": 12,
        "legendLabelSize": 12,
        "gridColor": grid,
        "gridShow": True,
        "gridTop": 80,
        "gridRight": 20,
        "gridBottom": 84,
        "gridLeft": 76,
        "legendShow": True,
        "legendOrient": "horizontal",
        "legendPosition": "top",
        "tooltipShow": True,
        "tooltipTrigger": "axis",
        "axisPointerType": "cross",
        "toolboxShow": True,
        "dataZoomShow": False,
        "strokeWidth": 2,
        "pointSize": 10,
        "barOpacity": 1.0,
        "areaOpacity": 0.3,
        "primaryColor": GS_NAVY_BRIGHT,
        "splitLineColor": grid,
    }
    return {
        "name": "gs_clean_dark",
        "label": "GS Clean -- Dark",
        "description": "Sky-on-navy, GS Sans, dark navy surfaces",
        "palette": "gs_primary",
        "echarts": echarts_theme,
        "knob_values": knob_values,
    }


THEMES: Dict[str, Dict[str, Any]] = {
    "gs_clean": _build_gs_clean(),
    "gs_clean_dark": _build_gs_clean_dark(),
}


def get_theme(name: str) -> Dict[str, Any]:
    """Return theme spec by name. Raises ValueError on unknown name."""
    if name not in THEMES:
        raise ValueError(
            f"Unknown theme '{name}'. Available: "
            f"{', '.join(sorted(THEMES.keys()))}"
        )
    return THEMES[name]


def list_themes() -> List[Dict[str, Any]]:
    """Return list of summary dicts for all themes."""
    return [
        {"name": t["name"], "label": t["label"],
         "description": t["description"], "palette": t["palette"]}
        for t in THEMES.values()
    ]


# =============================================================================
# SECTION 3 -- DIMENSIONS
# =============================================================================
#
# 12 presets mirroring chart_studio exactly.
#
#   wide          700x350   default for time series
#   square        450x450   scatter, heatmaps
#   tall          400x550   vertical bars, rankings
#   compact       400x300   small dashboard components
#   presentation  900x500   slides
#   thumbnail     300x200   previews
#   teams         420x210   Microsoft Teams (mandatory)
#   report        600x400   report body
#   dashboard     800x500   dashboard tile
#   widescreen    1200x500  widescreen banner
#   twopack       540x360   half of a 2-pack
#   fourpack      420x280   quarter of a 2x2 grid
#   custom        600x400   preserves spec's own dimensions
#
# Typography overrides kick in for small presets (teams/thumbnail/compact)
# so labels remain legible at smaller sizes.


DIMENSION_PRESETS: Dict[str, Dict[str, Any]] = {
    "wide":         {"width": 700,  "height": 350, "label": "Wide (700x350) [default]",                    "prism": True},
    "square":       {"width": 450,  "height": 450, "label": "Square (450x450)",                            "prism": True},
    "tall":         {"width": 400,  "height": 550, "label": "Tall (400x550)",                              "prism": True},
    "compact":      {"width": 400,  "height": 300, "label": "Compact (400x300)",                           "prism": True},
    "presentation": {"width": 900,  "height": 500, "label": "Presentation (900x500)",                      "prism": True},
    "thumbnail":    {"width": 300,  "height": 200, "label": "Thumbnail (300x200)",                         "prism": True},
    "teams":        {"width": 420,  "height": 210, "label": "Teams (420x210) [mandatory for MS Teams]",    "prism": True},
    "report":       {"width": 600,  "height": 400, "label": "Report (600x400)",                            "prism": False},
    "dashboard":    {"width": 800,  "height": 500, "label": "Dashboard (800x500)",                         "prism": False},
    "widescreen":   {"width": 1200, "height": 500, "label": "Widescreen (1200x500)",                       "prism": False},
    "twopack":      {"width": 540,  "height": 360, "label": "2-pack tile (540x360)",                       "prism": False},
    "fourpack":     {"width": 420,  "height": 280, "label": "4-pack tile (420x280)",                       "prism": False},
    "custom":       {"width": 600,  "height": 400, "label": "Custom",                                      "prism": False},
}


TYPOGRAPHY_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "teams": {
        "titleSize":        12,
        "labelSize":        8,
        "axisTitleSize":    9,
        "legendLabelSize":  8,
        "legendTitleSize":  9,
        "strokeWidth":      1.5,
        "pointSize":        5,
    },
    "thumbnail": {
        "titleSize":        10,
        "labelSize":        7,
        "axisTitleSize":    8,
        "legendLabelSize":  7,
        "legendTitleSize":  8,
        "strokeWidth":      1.2,
        "pointSize":        4,
    },
    "compact": {
        "titleSize":        14,
        "labelSize":        10,
        "axisTitleSize":    11,
        "legendLabelSize":  10,
        "legendTitleSize":  11,
        "strokeWidth":      1.8,
        "pointSize":        6,
    },
}


def get_dimension_preset(name: str) -> Dict[str, Any]:
    """Return preset dict by name. Raises ValueError on unknown name."""
    if name not in DIMENSION_PRESETS:
        raise ValueError(
            f"Unknown dimension preset '{name}'. "
            f"Available: {', '.join(sorted(DIMENSION_PRESETS.keys()))}"
        )
    return DIMENSION_PRESETS[name]


def get_typography_override(preset_name: str) -> Dict[str, Any]:
    """Return typography override dict for a preset, or empty dict if none."""
    return dict(TYPOGRAPHY_OVERRIDES.get(preset_name, {}))


def list_dimensions() -> List[Dict[str, Any]]:
    """Return list of summary dicts for all presets."""
    return [
        {"name": n, "width": d["width"], "height": d["height"],
         "label": d["label"], "prism": d["prism"],
         "has_typography_override": n in TYPOGRAPHY_OVERRIDES}
        for n, d in DIMENSION_PRESETS.items()
    ]


# =============================================================================
# SECTION 4 -- NUMERIC FORMATTING POLICY
# =============================================================================
#
# Hard global cap on decimal places anywhere a dashboard renders a number:
# axis tick labels, tooltips, KPI values, table cells, heatmap cell labels,
# correlation-matrix coefficients, regression statistics, etc.
#
# This is a non-negotiable house rule. Author-supplied options like
# ``value_decimals``, ``decimals``, ``delta_decimals``, ``tooltip.decimals``,
# and table format suffixes (``"number:3"``) are clamped to this cap before
# they reach a formatter. Hard-coded ``toFixed(...)`` literals in the
# runtime JS are also bounded by this cap. Callers asking for more
# precision are silently coerced down -- a number rendered to 4 decimals
# implies precision the data rarely supports and forces a reader to decode
# digits that don't change behaviour.
#
# To raise the cap (e.g. to 3) update this constant; the JS-side mirror in
# ``rendering.py`` is generated from this value at compile time so the two
# halves can never drift.

MAX_DASHBOARD_DECIMALS: int = 2


def clamp_decimals(value: Any, default: int = 2) -> int:
    """Coerce ``value`` to an int and clamp to ``[0, MAX_DASHBOARD_DECIMALS]``.

    Used at every Python-side boundary that accepts a user-supplied
    decimals/precision option. ``default`` covers ``None`` / non-numeric
    input. The default itself is also clamped so callers can pass any
    historical default without re-introducing a > 2 decimal path.
    """
    cap = MAX_DASHBOARD_DECIMALS
    fb = max(0, min(cap, int(default)))
    if value is None:
        return fb
    try:
        n = int(value)
    except (TypeError, ValueError):
        try:
            n = int(float(value))
        except (TypeError, ValueError):
            return fb
    if n < 0:
        return 0
    if n > cap:
        return cap
    return n


__all__ = [
    # brand tokens -- downstream modules (dashboard_html, editor_html,
    # png_export) import these directly so the CSS/HTML chrome stays in
    # sync with the chart palette.
    "GS_SKY", "GS_NAVY", "GS_NAVY_DEEP", "GS_INK", "GS_PAPER", "GS_BG",
    "GS_GREY_80", "GS_GREY_70", "GS_GREY_40", "GS_GREY_20",
    "GS_GREY_10", "GS_GREY_05",
    "GS_DARK_BG", "GS_DARK_SURFACE", "GS_DARK_SURFACE_2",
    "GS_DARK_SURFACE_HOV", "GS_DARK_TEXT", "GS_DARK_TEXT_DIM",
    "GS_DARK_TEXT_FAINT", "GS_DARK_BORDER", "GS_DARK_BORDER_STR",
    "GS_NAVY_BRIGHT", "GS_GOLD_BRIGHT", "GS_BURGUNDY_BRIGHT",
    "GS_FOREST_BRIGHT", "GS_SLATE_BRIGHT", "GS_PLUM_BRIGHT",
    "GS_AMBER_BRIGHT", "GS_BRICK_BRIGHT", "GS_STEEL_BRIGHT",
    "GS_TEAL_BRIGHT",
    "GS_GOLD", "GS_BURGUNDY", "GS_FOREST", "GS_SLATE", "GS_PLUM",
    "GS_AMBER", "GS_BRICK", "GS_STEEL", "GS_TEAL",
    "GS_POS", "GS_NEG",
    "GS_FONT_SANS", "GS_FONT_SERIF", "GS_FONT_MONO",
    # public config API
    "PALETTES", "THEMES", "DIMENSION_PRESETS", "TYPOGRAPHY_OVERRIDES",
    "get_palette", "palette_colors", "list_palettes",
    "get_theme", "list_themes",
    "get_dimension_preset", "get_typography_override", "list_dimensions",
    # numeric formatting policy
    "MAX_DASHBOARD_DECIMALS", "clamp_decimals",
]
