#!/usr/bin/env python3
"""
chart_functions_studio v0.4 -- single-file interactive editor for
PRISM-style vega-lite/altair charts.

PAIRS ALONGSIDE PRISM's make_chart() as an additive, optional HTML
companion. PRISM keeps producing charts as today. When interactive=True
is passed (or wrap_interactive_prism() is called separately),
chart_functions_studio wraps the altair chart into a self-contained
HTML editor with:

    - live chart preview (vega-embed from CDN)
    - ~140 editable knobs covering every vega-lite config path
    - editable text fields: title, subtitle, source, axis titles, legend title
    - full axes control: rotation, format, domain, zero-start, log scale,
      domain toggles, tick count
    - per-side padding, stroke dash, point shape, bar orientation
    - per-series color override (detected dynamically from the spec)
    - theme presets (gs_clean matches PRISM exactly)
    - palette library (14 palettes: categorical / sequential / diverging)
    - dimension presets (PRISM's 7 canonical + 5 extras)
    - typography auto-override when small presets selected
    - SPEC SHEETS: named bundles of user preferences saved per-user
      (the full chart style: theme + palette + dimensions + all knob
      overrides). Save multiple sheets, switch via dropdown, download
      or upload as JSON for team sharing.
    - export: PNG, SVG, raw spec JSON, spec sheet JSON
    - search box: filter knobs by name
    - essentials group always-visible for common edits
    - dynamic annotation controls (when PRISM tags layers with "name")
    - composite support (hconcat / vconcat / concat)
    - preference persistence via localStorage

INPUT: vega-lite spec as
    - dict
    - JSON string
    - altair Chart (anything with .to_dict() or .to_json())

OUTPUT: self-contained HTML. Zero Python runtime deps (stdlib only).
CDN deps (vega@5, vega-lite@5, vega-embed@6 from jsdelivr).

LIBRARY USAGE

    from chart_functions_studio import wrap_interactive, wrap_interactive_prism

    # generic path (any altair/vega-lite spec)
    result = wrap_interactive(my_vega_spec, output_path="out.html")

    # PRISM-specific path (adds session-path convention, GS_CLEAN theme
    # as default, reads user's active spec sheet from user_id)
    result = wrap_interactive_prism(
        altair_chart=chart,
        chart_type='multi_line',
        dimensions='wide',
        annotations=my_annotations,
        user_id='ritik',
        session_path='sessions/20260417_xxx',
    )
    # -> result.editor_html_path, result.editor_url, result.chart_id

CLI USAGE

    python chart_functions_studio.py                # interactive menu
    python chart_functions_studio.py wrap spec.json
    python chart_functions_studio.py wrap spec.json --open --theme gs_clean
    python chart_functions_studio.py demo           # generate sample HTML
    python chart_functions_studio.py demo --matrix  # every sample x theme
    python chart_functions_studio.py list themes
    python chart_functions_studio.py list palettes
    python chart_functions_studio.py list dimensions
    python chart_functions_studio.py list knobs --chart-type line
    python chart_functions_studio.py info spec.json
    python chart_functions_studio.py test           # built-in smoke tests

DESIGN RULES

    - No fallbacks. Unknown theme/palette/preset raises ValueError.
    - Spec sheet scope: global by default, per-chart-type opt-in.
    - Titles/subtitle/axis-titles/legend-title are PER-CHART content,
      not part of spec sheet. Spec sheet stores styling only.
    - Precedence (low to high):
        knob default -> theme -> preset typography override ->
        user spec sheet -> live session changes.
    - Single file. Keep it that way. No package structure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import webbrowser
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union


__version__ = "0.4.0"


# =============================================================================
# DIMENSION PRESETS
# =============================================================================
#
# PRISM's 7 canonical presets first, followed by 5 useful extras.
# Each preset is a width/height pair + optional typography override
# keyed in TYPOGRAPHY_OVERRIDES.
# =============================================================================

DIMENSION_PRESETS: Dict[str, Dict[str, Any]] = {
    # PRISM canonical
    "wide":         {"width": 700,  "height": 350, "label": "Wide (700x350) [default]",   "prism": True},
    "square":       {"width": 450,  "height": 450, "label": "Square (450x450)",            "prism": True},
    "tall":         {"width": 400,  "height": 550, "label": "Tall (400x550)",              "prism": True},
    "compact":      {"width": 400,  "height": 300, "label": "Compact (400x300)",           "prism": True},
    "presentation": {"width": 900,  "height": 500, "label": "Presentation (900x500)",      "prism": True},
    "thumbnail":    {"width": 300,  "height": 200, "label": "Thumbnail (300x200)",         "prism": True},
    "teams":        {"width": 420,  "height": 210, "label": "Teams (420x210) [mandatory for MS Teams]", "prism": True},
    # Extras (useful but not PRISM-canonical)
    "report":       {"width": 600,  "height": 400, "label": "Report (600x400)",            "prism": False},
    "dashboard":    {"width": 800,  "height": 500, "label": "Dashboard (800x500)",         "prism": False},
    "widescreen":   {"width": 1200, "height": 500, "label": "Widescreen (1200x500)",       "prism": False},
    "twopack":      {"width": 540,  "height": 360, "label": "2-pack tile (540x360)",       "prism": False},
    "fourpack":     {"width": 420,  "height": 280, "label": "4-pack tile (420x280)",       "prism": False},
    "custom":       {"width": 600,  "height": 400, "label": "Custom",                       "prism": False},
}


# When a small dimension preset is selected, the editor applies these
# typography overrides automatically so the chart stays legible.
TYPOGRAPHY_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "teams": {
        "titleSize":       12,
        "labelSize":       8,
        "axisTitleSize":   9,
        "legendLabelSize": 8,
        "legendTitleSize": 9,
        "strokeWidth":     1.5,
        "pointSize":       40,
    },
    "thumbnail": {
        "titleSize":       10,
        "labelSize":       7,
        "axisTitleSize":   8,
        "legendLabelSize": 7,
        "legendTitleSize": 8,
        "strokeWidth":     1.2,
        "pointSize":       30,
    },
    "compact": {
        "titleSize":       18,
        "labelSize":       12,
        "axisTitleSize":   13,
        "legendLabelSize": 10,
        "legendTitleSize": 11,
        "strokeWidth":     1.8,
        "pointSize":       50,
    },
}


def get_dimension_preset(name: str) -> Dict[str, Any]:
    if name not in DIMENSION_PRESETS:
        available = ", ".join(sorted(DIMENSION_PRESETS.keys()))
        raise ValueError(f"Unknown dimension preset '{name}'. Available: {available}")
    return DIMENSION_PRESETS[name]


def list_dimension_presets() -> List[Dict[str, Any]]:
    return [
        {"name": n, "label": p["label"], "width": p["width"], "height": p["height"], "prism": p.get("prism", False)}
        for n, p in DIMENSION_PRESETS.items()
    ]


# =============================================================================
# KNOBS
# =============================================================================
#
# Every knob has:
#   name       unique identifier (stable across versions, used in spec sheets)
#   label      display text in the editor panel
#   type       widget type: range | select | checkbox | color | text
#   default    initial value
#   group      UI section: Essentials, Title, X-Axis, Y-Axis, Legend,
#              <mark>, Colors, Annotations, Layout, Typography, Advanced
#   EITHER:
#     path     dotted path inside the vega-lite spec (simple case)
#   OR:
#     apply    named custom-apply function, runs in browser JS
#     applyArgs  list of static arguments passed to the apply function
#   Optional:
#     min / max / step   for range
#     options            for select
#     essential          bool: include in Essentials group
#     semantic           bool: if True, treat as data-semantic -- spec
#                        sheet overrides are NOT applied to this knob
#                        (reserved for future; today all knobs are
#                        stylistic).
#
# Custom apply functions live in the JS registry (see HTML_TEMPLATE) and
# are invoked when the knob's value changes. Use them when:
#   - the target path depends on spec structure (e.g. encoding paths
#     that might live at the top level or in layers)
#   - multiple spec paths need to be mutated from a single knob
#     (e.g. "show legend" toggles both legend visibility and layout)
#   - the value needs transformation (e.g. strokeDash select -> array)
# =============================================================================


UNIVERSAL_KNOBS: List[Dict[str, Any]] = [
    # --- Dimensions (Essentials) ---
    # width/height use apply-based handlers because layered specs (e.g.
    # PRISM annotation overlays) carry width/height on each layer rather
    # than at the spec root. Setting only the top-level path leaves the
    # chart at the layer-level size; setWidth/setHeight walk the tree.
    {"name": "width",    "label": "Width",      "type": "range",
     "min": 200, "max": 1600, "step": 10, "default": 700,
     "apply": "setWidth", "group": "Dimensions", "essential": True},
    {"name": "height",   "label": "Height",     "type": "range",
     "min": 150, "max": 1200, "step": 10, "default": 350,
     "apply": "setHeight", "group": "Dimensions", "essential": True},
    {"name": "padding",  "label": "Padding (all sides)", "type": "range",
     "min": 0, "max": 60, "step": 2, "default": 10,
     "path": "padding", "group": "Dimensions"},
    {"name": "paddingLeft",   "label": "Padding left",   "type": "range",
     "min": 0, "max": 80, "step": 2, "default": 10,
     "path": "padding.left", "group": "Layout"},
    {"name": "paddingRight",  "label": "Padding right",  "type": "range",
     "min": 0, "max": 80, "step": 2, "default": 10,
     "path": "padding.right", "group": "Layout"},
    {"name": "paddingTop",    "label": "Padding top",    "type": "range",
     "min": 0, "max": 80, "step": 2, "default": 10,
     "path": "padding.top", "group": "Layout"},
    {"name": "paddingBottom", "label": "Padding bottom", "type": "range",
     "min": 0, "max": 80, "step": 2, "default": 10,
     "path": "padding.bottom", "group": "Layout"},
    {"name": "autosize", "label": "Autosize mode", "type": "select",
     "options": ["pad", "fit", "fit-x", "fit-y", "none"], "default": "pad",
     "path": "autosize.type", "group": "Layout"},
    {"name": "autosizeContains", "label": "Autosize contains", "type": "select",
     "options": ["content", "padding"], "default": "content",
     "path": "autosize.contains", "group": "Layout"},
    {"name": "background", "label": "Background", "type": "color",
     "default": "#ffffff",
     "path": "background", "group": "Dimensions", "essential": True},
    {"name": "viewStrokeColor", "label": "View border color", "type": "color",
     "default": "#ffffff",
     "path": "config.view.stroke", "group": "Layout"},
    {"name": "viewStrokeWidth", "label": "View border width", "type": "range",
     "min": 0, "max": 4, "step": 0.5, "default": 0,
     "path": "config.view.strokeWidth", "group": "Layout"},

    # --- Title & Subtitle (editable text!) ---
    {"name": "titleText", "label": "Title text", "type": "text",
     "default": "",
     "apply": "setTitleText", "group": "Title", "essential": True},
    {"name": "titleSize", "label": "Title size", "type": "range",
     "min": 10, "max": 32, "step": 1, "default": 26,
     "path": "config.title.fontSize", "group": "Title", "essential": True},
    {"name": "titleColor", "label": "Title color", "type": "color",
     "default": "#000000",
     "path": "config.title.color", "group": "Title"},
    {"name": "titleWeight", "label": "Title weight", "type": "select",
     "options": ["normal", "bold"], "default": "bold",
     "path": "config.title.fontWeight", "group": "Title"},
    {"name": "titleAnchor", "label": "Title anchor", "type": "select",
     "options": ["start", "middle", "end"], "default": "start",
     "path": "config.title.anchor", "group": "Title"},
    {"name": "titleOffset", "label": "Title offset", "type": "range",
     "min": 0, "max": 30, "step": 1, "default": 4,
     "path": "config.title.offset", "group": "Title"},
    {"name": "subtitleText", "label": "Subtitle text", "type": "text",
     "default": "",
     "apply": "setSubtitleText", "group": "Title"},
    {"name": "subtitleSize", "label": "Subtitle size", "type": "range",
     "min": 8, "max": 22, "step": 1, "default": 14,
     "path": "config.title.subtitleFontSize", "group": "Title"},
    {"name": "subtitleColor", "label": "Subtitle color", "type": "color",
     "default": "#333333",
     "path": "config.title.subtitleColor", "group": "Title"},
    {"name": "subtitleWeight", "label": "Subtitle weight", "type": "select",
     "options": ["normal", "bold"], "default": "normal",
     "path": "config.title.subtitleFontWeight", "group": "Title"},
    # The producer renders source= / caption= as a dedicated text panel
    # concatenated below the plot, not as part of the title block, so this
    # knob resolves that panel and rewrites its pre-wrapped mark.text.
    {"name": "captionText", "label": "Source / caption", "type": "text",
     "default": "",
     "apply": "setCaptionText", "group": "Title", "essential": True},

    # --- Typography ---
    {"name": "fontFamily", "label": "Font family", "type": "select",
     "options": ["GS Sans, Liberation Sans, Arial, sans-serif",
                 "Liberation Sans, Arial, sans-serif", "Arial", "Helvetica",
                 "sans-serif", "Georgia", "Times", "serif", "Monaco",
                 "Menlo", "monospace"],
     "default": "GS Sans, Liberation Sans, Arial, sans-serif",
     "path": "config.font", "group": "Typography"},
    {"name": "labelSize", "label": "Tick label size", "type": "range",
     "min": 6, "max": 22, "step": 1, "default": 18,
     "path": "config.axis.labelFontSize", "group": "Typography"},
    {"name": "axisTitleSize", "label": "Axis title size", "type": "range",
     "min": 6, "max": 22, "step": 1, "default": 16,
     "path": "config.axis.titleFontSize", "group": "Typography"},
    {"name": "legendLabelSize", "label": "Legend label size", "type": "range",
     "min": 6, "max": 18, "step": 1, "default": 14,
     "path": "config.legend.labelFontSize", "group": "Typography"},
    {"name": "legendTitleSize", "label": "Legend title size", "type": "range",
     "min": 6, "max": 18, "step": 1, "default": 14,
     "path": "config.legend.titleFontSize", "group": "Typography"},

    # --- X-Axis ---
    # All X-axis knobs use apply functions that target encoding.x.axis.* AND
    # config.axisX.* so they always win even when the producer has set
    # encoding-level styling (vega-lite gives encoding precedence over config).
    {"name": "xAxisTitle", "label": "X-axis title", "type": "text",
     "default": "",
     "apply": "setXAxisTitle", "group": "X-Axis"},
    {"name": "xLabelAngle", "label": "X label angle", "type": "range",
     "min": -90, "max": 90, "step": 5, "default": 0,
     "apply": "setXLabelAngle", "group": "X-Axis", "essential": True},
    {"name": "xTickCount", "label": "X tick count", "type": "range",
     "min": 2, "max": 20, "step": 1, "default": 6,
     "apply": "setXTickCount", "group": "X-Axis"},
    {"name": "xLabelFormat", "label": "X label format", "type": "select",
     "options": ["", ",", ".2f", ".1%", "%Y", "%b %Y", "%b %d", "%Y-%m-%d", "$,.0f"],
     "default": "",
     "apply": "setXAxisFormat", "group": "X-Axis"},
    {"name": "xDomainShow", "label": "X axis line", "type": "checkbox",
     "default": True,
     "apply": "setXDomainShow", "group": "X-Axis"},
    {"name": "xTickShow", "label": "X ticks", "type": "checkbox",
     "default": True,
     "apply": "setXTickShow", "group": "X-Axis"},
    {"name": "xDomainMin", "label": "X domain min (number or date, blank=auto)",
     "type": "text", "default": "",
     "apply": "setXDomainMin", "group": "X-Axis"},
    {"name": "xDomainMax", "label": "X domain max (number or date, blank=auto)",
     "type": "text", "default": "",
     "apply": "setXDomainMax", "group": "X-Axis"},
    {"name": "xZeroStart", "label": "X zero-start", "type": "select",
     "options": ["auto", "force", "off"], "default": "auto",
     "apply": "setXZeroStart", "group": "X-Axis"},
    {"name": "xLogScale", "label": "X log scale", "type": "checkbox",
     "default": False,
     "apply": "setXLogScale", "group": "X-Axis"},

    # --- Y-Axis ---
    {"name": "yAxisTitle", "label": "Y-axis title", "type": "text",
     "default": "",
     "apply": "setYAxisTitle", "group": "Y-Axis"},
    {"name": "yLabelAngle", "label": "Y label angle", "type": "range",
     "min": -90, "max": 90, "step": 5, "default": 0,
     "apply": "setYLabelAngle", "group": "Y-Axis", "essential": True},
    {"name": "yTickCount", "label": "Y tick count", "type": "range",
     "min": 2, "max": 20, "step": 1, "default": 6,
     "apply": "setYTickCount", "group": "Y-Axis"},
    {"name": "yLabelFormat", "label": "Y label format", "type": "select",
     "options": ["", ",", ".2f", ".1%", "%Y", "$,.0f", ".0f"],
     "default": "",
     "apply": "setYAxisFormat", "group": "Y-Axis"},
    {"name": "yDomainShow", "label": "Y axis line", "type": "checkbox",
     "default": True,
     "apply": "setYDomainShow", "group": "Y-Axis"},
    {"name": "yTickShow", "label": "Y ticks", "type": "checkbox",
     "default": True,
     "apply": "setYTickShow", "group": "Y-Axis"},
    {"name": "yDomainMin", "label": "Y domain min (blank=auto)", "type": "text",
     "default": "",
     "apply": "setYDomainMin", "group": "Y-Axis"},
    {"name": "yDomainMax", "label": "Y domain max (blank=auto)", "type": "text",
     "default": "",
     "apply": "setYDomainMax", "group": "Y-Axis"},
    {"name": "yZeroStart", "label": "Y zero-start", "type": "select",
     "options": ["auto", "force", "off"], "default": "auto",
     "apply": "setYZeroStart", "group": "Y-Axis"},
    {"name": "yLogScale", "label": "Y log scale", "type": "checkbox",
     "default": False,
     "apply": "setYLogScale", "group": "Y-Axis"},
    {"name": "yInvert", "label": "Y invert (for rates)", "type": "checkbox",
     "default": False,
     "apply": "setYInvert", "group": "Y-Axis"},

    # --- Axes shared styling ---
    {"name": "domainColor", "label": "Axis line color", "type": "color",
     "default": "#000000",
     "path": "config.axis.domainColor", "group": "Axes"},
    {"name": "tickColor", "label": "Tick color", "type": "color",
     "default": "#000000",
     "path": "config.axis.tickColor", "group": "Axes"},
    {"name": "labelColor", "label": "Label color", "type": "color",
     "default": "#000000",
     "path": "config.axis.labelColor", "group": "Axes"},
    {"name": "domainWidth", "label": "Axis line width", "type": "range",
     "min": 0.5, "max": 3, "step": 0.5, "default": 1,
     "path": "config.axis.domainWidth", "group": "Axes"},
    {"name": "tickSize", "label": "Tick size", "type": "range",
     "min": 0, "max": 12, "step": 1, "default": 5,
     "path": "config.axis.tickSize", "group": "Axes"},

    # --- Legend ---
    {"name": "legendShow", "label": "Show legend", "type": "checkbox",
     "default": True,
     "apply": "setLegendShow", "group": "Legend"},
    {"name": "legendTitle", "label": "Legend title text", "type": "text",
     "default": "",
     "apply": "setLegendTitle", "group": "Legend"},
    {"name": "legendOrient", "label": "Legend position", "type": "select",
     "options": ["right", "left", "top", "bottom", "top-right", "top-left",
                 "bottom-right", "bottom-left", "none"], "default": "right",
     "path": "config.legend.orient", "group": "Legend", "essential": True},
    {"name": "legendSymbolType", "label": "Legend symbol", "type": "select",
     "options": ["circle", "square", "diamond", "triangle-up",
                 "triangle-down", "cross", "stroke"], "default": "circle",
     "path": "config.legend.symbolType", "group": "Legend"},
    {"name": "legendSymbolSize", "label": "Symbol size", "type": "range",
     "min": 20, "max": 300, "step": 10, "default": 100,
     "path": "config.legend.symbolSize", "group": "Legend"},
    {"name": "legendColumns", "label": "Legend columns", "type": "range",
     "min": 1, "max": 6, "step": 1, "default": 1,
     "path": "config.legend.columns", "group": "Legend"},
    {"name": "legendRowPadding", "label": "Row padding", "type": "range",
     "min": 0, "max": 10, "step": 1, "default": 2,
     "path": "config.legend.rowPadding", "group": "Legend"},
    {"name": "legendTitlePadding", "label": "Title padding", "type": "range",
     "min": 0, "max": 20, "step": 1, "default": 5,
     "path": "config.legend.titlePadding", "group": "Legend"},
    {"name": "legendPadding", "label": "Legend padding", "type": "range",
     "min": 0, "max": 30, "step": 1, "default": 5,
     "path": "config.legend.padding", "group": "Legend"},
    {"name": "legendLabelColor", "label": "Legend label color", "type": "color",
     "default": "#000000",
     "path": "config.legend.labelColor", "group": "Legend"},
    {"name": "legendTitleColor", "label": "Legend title color", "type": "color",
     "default": "#000000",
     "path": "config.legend.titleColor", "group": "Legend"},

    # --- Colors (primary is a synthetic knob that sets palette[0]) ---
    {"name": "primaryColor", "label": "Primary color", "type": "color",
     "default": "#003359",
     "apply": "setPrimaryColor", "group": "Colors", "essential": True},

    # --- Interactivity ---
    {"name": "tooltipEnabled", "label": "Hover tooltips", "type": "checkbox",
     "default": True,
     "apply": "setTooltipEnabled", "group": "Interactivity", "essential": True},
    {"name": "tooltipShowAllFields", "label": "Show all data fields in tooltip", "type": "checkbox",
     "default": True,
     "apply": "setTooltipContent", "group": "Interactivity"},
    {"name": "crosshairEnabled", "label": "Crosshair on line/area", "type": "checkbox",
     "default": False,
     "apply": "setCrosshair", "group": "Interactivity"},
    {"name": "brushZoomX", "label": "Brush zoom X", "type": "checkbox",
     "default": False,
     "apply": "setBrushZoomX", "group": "Interactivity"},
    {"name": "brushZoomY", "label": "Brush zoom Y", "type": "checkbox",
     "default": False,
     "apply": "setBrushZoomY", "group": "Interactivity"},
    {"name": "legendClickToggle", "label": "Click legend to toggle series", "type": "checkbox",
     "default": True,
     "apply": "setLegendClickToggle", "group": "Interactivity"},
]


# --- Mark-specific knobs ---

LINE_KNOBS: List[Dict[str, Any]] = [
    {"name": "strokeWidth", "label": "Line width", "type": "range",
     "min": 0.5, "max": 6, "step": 0.5, "default": 2,
     "path": "config.line.strokeWidth", "group": "Line"},
    {"name": "lineOpacity", "label": "Line opacity", "type": "range",
     "min": 0.2, "max": 1, "step": 0.05, "default": 1.0,
     "path": "config.line.opacity", "group": "Line"},
    {"name": "interpolate", "label": "Interpolation", "type": "select",
     "options": ["linear", "monotone", "basis", "step", "step-after", "step-before"],
     "default": "linear",
     "path": "config.line.interpolate", "group": "Line"},
    {"name": "strokeDash", "label": "Stroke dash pattern", "type": "select",
     "options": ["solid", "dashed", "dotted", "dash-dot", "long-dash"],
     "default": "solid",
     "apply": "setStrokeDash", "group": "Line"},
    {"name": "strokeCap", "label": "Stroke cap", "type": "select",
     "options": ["butt", "round", "square"], "default": "butt",
     "path": "config.line.strokeCap", "group": "Line"},
    {"name": "linePointSize", "label": "Point size on line", "type": "range",
     "min": 0, "max": 200, "step": 10, "default": 0,
     "path": "config.point.size", "group": "Line"},
    {"name": "linePointFilled", "label": "Points filled", "type": "checkbox",
     "default": True,
     "path": "config.point.filled", "group": "Line"},
]


BAR_KNOBS: List[Dict[str, Any]] = [
    {"name": "barOpacity", "label": "Bar opacity", "type": "range",
     "min": 0.3, "max": 1, "step": 0.05, "default": 1.0,
     "path": "config.bar.opacity", "group": "Bar"},
    {"name": "barCornerRadius", "label": "Corner radius", "type": "range",
     "min": 0, "max": 20, "step": 1, "default": 0,
     "path": "config.bar.cornerRadius", "group": "Bar"},
    {"name": "barStroke", "label": "Bar outline color", "type": "color",
     "default": "#00000000",
     "path": "config.bar.stroke", "group": "Bar"},
    {"name": "barStrokeWidth", "label": "Outline width", "type": "range",
     "min": 0, "max": 4, "step": 0.5, "default": 0,
     "path": "config.bar.strokeWidth", "group": "Bar"},
    {"name": "barBandPaddingInner", "label": "Bar gap (inner)", "type": "range",
     "min": 0, "max": 0.9, "step": 0.05, "default": 0.1,
     "path": "config.scale.bandPaddingInner", "group": "Bar"},
    {"name": "barBandPaddingOuter", "label": "Bar gap (outer)", "type": "range",
     "min": 0, "max": 0.9, "step": 0.05, "default": 0.05,
     "path": "config.scale.bandPaddingOuter", "group": "Bar"},
]


POINT_KNOBS: List[Dict[str, Any]] = [
    {"name": "pointSize", "label": "Point size", "type": "range",
     "min": 10, "max": 500, "step": 10, "default": 60,
     "path": "config.point.size", "group": "Scatter"},
    {"name": "pointOpacity", "label": "Point opacity", "type": "range",
     "min": 0.2, "max": 1, "step": 0.05, "default": 0.7,
     "path": "config.point.opacity", "group": "Scatter"},
    {"name": "pointFilled", "label": "Filled", "type": "checkbox",
     "default": True,
     "path": "config.point.filled", "group": "Scatter"},
    {"name": "pointShape", "label": "Point shape", "type": "select",
     "options": ["circle", "square", "diamond", "triangle-up",
                 "triangle-down", "cross", "stroke"],
     "default": "circle",
     "path": "config.point.shape", "group": "Scatter"},
    {"name": "pointStrokeWidth", "label": "Outline width", "type": "range",
     "min": 0, "max": 4, "step": 0.5, "default": 1,
     "path": "config.point.strokeWidth", "group": "Scatter"},
]


AREA_KNOBS: List[Dict[str, Any]] = [
    {"name": "areaOpacity", "label": "Area opacity", "type": "range",
     "min": 0.2, "max": 1, "step": 0.05, "default": 0.7,
     "path": "config.area.opacity", "group": "Area"},
    {"name": "areaInterpolate", "label": "Interpolation", "type": "select",
     "options": ["linear", "monotone", "basis", "step", "step-after", "step-before"],
     "default": "linear",
     "path": "config.area.interpolate", "group": "Area"},
    {"name": "areaLine", "label": "Show edge line", "type": "checkbox",
     "default": True,
     "path": "config.area.line", "group": "Area"},
]


ARC_KNOBS: List[Dict[str, Any]] = [
    {"name": "innerRadius", "label": "Inner radius", "type": "range",
     "min": 0, "max": 150, "step": 5, "default": 50,
     "path": "config.arc.innerRadius", "group": "Arc"},
    {"name": "outerRadius", "label": "Outer radius", "type": "range",
     "min": 60, "max": 300, "step": 5, "default": 100,
     "path": "config.arc.outerRadius", "group": "Arc"},
    {"name": "padAngle", "label": "Slice gap", "type": "range",
     "min": 0, "max": 0.1, "step": 0.005, "default": 0.02,
     "path": "config.arc.padAngle", "group": "Arc"},
    {"name": "arcCornerRadius", "label": "Corner radius", "type": "range",
     "min": 0, "max": 20, "step": 1, "default": 3,
     "path": "config.arc.cornerRadius", "group": "Arc"},
]


RECT_KNOBS: List[Dict[str, Any]] = [
    {"name": "rectOpacity", "label": "Cell opacity", "type": "range",
     "min": 0.3, "max": 1, "step": 0.05, "default": 1.0,
     "path": "config.rect.opacity", "group": "Heatmap"},
    {"name": "rectStroke", "label": "Cell border", "type": "color",
     "default": "#ffffff",
     "path": "config.rect.stroke", "group": "Heatmap"},
    {"name": "rectStrokeWidth", "label": "Border width", "type": "range",
     "min": 0, "max": 4, "step": 0.5, "default": 0.5,
     "path": "config.rect.strokeWidth", "group": "Heatmap"},
]


BOXPLOT_KNOBS: List[Dict[str, Any]] = [
    {"name": "boxSize", "label": "Box size", "type": "range",
     "min": 10, "max": 60, "step": 2, "default": 20,
     "path": "config.boxplot.size", "group": "Box"},
    {"name": "boxExtent", "label": "Whisker extent", "type": "select",
     "options": ["1.5", "min-max"], "default": "1.5",
     "path": "config.boxplot.extent", "group": "Box"},
]


# New PRISM chart types:
SCATTER_MULTI_KNOBS: List[Dict[str, Any]] = POINT_KNOBS + [
    {"name": "trendlineStrokeWidth", "label": "Trendline width", "type": "range",
     "min": 0.5, "max": 4, "step": 0.5, "default": 1.5,
     "path": "config.rule.strokeWidth", "group": "Scatter"},
    {"name": "trendlineDash", "label": "Trendline dash", "type": "select",
     "options": ["solid", "dashed", "dotted"], "default": "dashed",
     "apply": "setTrendlineDash", "group": "Scatter"},
]


BAR_HORIZONTAL_KNOBS: List[Dict[str, Any]] = BAR_KNOBS + [
    {"name": "barOrient", "label": "Orientation", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "path": "config.bar.orient", "group": "Bar"},
]


BULLET_KNOBS: List[Dict[str, Any]] = BAR_KNOBS + [
    {"name": "bulletMarkerSize", "label": "Target marker size", "type": "range",
     "min": 4, "max": 20, "step": 1, "default": 10,
     "path": "config.tick.size", "group": "Bullet"},
    {"name": "bulletMarkerColor", "label": "Target marker color", "type": "color",
     "default": "#000000",
     "path": "config.tick.color", "group": "Bullet"},
]


WATERFALL_KNOBS: List[Dict[str, Any]] = BAR_KNOBS + [
    {"name": "connectorStrokeWidth", "label": "Connector width", "type": "range",
     "min": 0.5, "max": 3, "step": 0.5, "default": 1,
     "path": "config.rule.strokeWidth", "group": "Waterfall"},
    {"name": "connectorColor", "label": "Connector color", "type": "color",
     "default": "#666666",
     "path": "config.rule.stroke", "group": "Waterfall"},
    {"name": "positiveColor", "label": "Positive bar color", "type": "color",
     "default": "#5C92CB",
     "apply": "setWaterfallPositive", "group": "Waterfall"},
    {"name": "negativeColor", "label": "Negative bar color", "type": "color",
     "default": "#C00000",
     "apply": "setWaterfallNegative", "group": "Waterfall"},
]


MARK_KNOB_MAP: Dict[str, List[Dict[str, Any]]] = {
    "line":           LINE_KNOBS,
    "bar":            BAR_KNOBS,
    "bar_horizontal": BAR_HORIZONTAL_KNOBS,
    "point":          POINT_KNOBS,
    "circle":         POINT_KNOBS,
    "square":         POINT_KNOBS,
    "scatter_multi":  SCATTER_MULTI_KNOBS,
    "area":           AREA_KNOBS,
    "arc":            ARC_KNOBS,
    "rect":           RECT_KNOBS,
    "boxplot":        BOXPLOT_KNOBS,
    "bullet":         BULLET_KNOBS,
    "waterfall":      WATERFALL_KNOBS,
}


def knobs_for_chart(chart_type: str) -> List[Dict[str, Any]]:
    """Universal knobs + mark-specific knobs for the given chart type."""
    base = list(UNIVERSAL_KNOBS)
    mark_specific = MARK_KNOB_MAP.get(chart_type, [])
    return base + list(mark_specific)


def list_supported_marks() -> List[str]:
    return sorted(MARK_KNOB_MAP.keys())


# =============================================================================
# THEMES
# =============================================================================
#
# A theme = flat dict of knob-name -> value + optional default palette.
# The GS_CLEAN theme mirrors PRISM's GS_CLEAN exactly.
# =============================================================================


GS_CLEAN: Dict[str, Any] = {
    "name": "gs_clean",
    "label": "GS Clean (PRISM default)",
    "description": "Exact match to PRISM GS_CLEAN: navy #003359, Liberation Sans, 26pt title",
    "values": {
        # Dimensions
        "background": "#ffffff",
        "padding": 10,
        "viewStrokeWidth": 0,
        "autosize": "pad",
        # Title
        "titleSize": 26,
        "titleColor": "#000000",
        "titleWeight": "bold",
        "titleAnchor": "start",
        "titleOffset": 4,
        "subtitleSize": 14,
        "subtitleColor": "#333333",
        "subtitleWeight": "normal",
        # Typography
        "fontFamily": "GS Sans, Liberation Sans, Arial, sans-serif",
        "labelSize": 18,
        "axisTitleSize": 16,
        "legendLabelSize": 14,
        "legendTitleSize": 14,
        # Axes
        "domainColor": "#000000",
        "tickColor": "#000000",
        "labelColor": "#000000",
        "domainWidth": 1,
        "tickSize": 5,
        "xDomainShow": True,
        "yDomainShow": True,
        "xLabelAngle": 0,
        "yLabelAngle": 0,
        # Legend
        "legendShow": True,
        "legendOrient": "right",
        "legendSymbolType": "circle",
        "legendSymbolSize": 100,
        "legendColumns": 1,
        "legendRowPadding": 2,
        "legendTitlePadding": 5,
        "legendPadding": 5,
        # Mark defaults
        "strokeWidth": 2,
        "lineOpacity": 1.0,
        "interpolate": "linear",
        "strokeDash": "solid",
        "linePointSize": 0,
        "linePointFilled": True,
        "pointSize": 60,
        "pointOpacity": 0.7,
        "pointFilled": True,
        "pointShape": "circle",
        "pointStrokeWidth": 1,
        "barOpacity": 1.0,
        "barCornerRadius": 0,
        "barStrokeWidth": 0,
        "areaOpacity": 0.7,
        "areaInterpolate": "linear",
        "areaLine": True,
        "innerRadius": 50,
        "outerRadius": 100,
        "padAngle": 0.02,
        "arcCornerRadius": 3,
        "rectOpacity": 1.0,
        "rectStroke": "#ffffff",
        "rectStrokeWidth": 0.5,
        "boxSize": 20,
        # Colors
        "primaryColor": "#003359",
        # Interactivity
        "tooltipEnabled": True,
        "tooltipShowAllFields": True,
        "crosshairEnabled": False,
        "brushZoomX": False,
        "brushZoomY": False,
        "legendClickToggle": True,
    },
    "palette": "gs_primary",
}


MINIMAL: Dict[str, Any] = {
    "name": "minimal",
    "label": "Minimal",
    "description": "Ultra-clean, tiny labels, press-ready",
    "values": {
        "background": "#ffffff",
        "fontFamily": "Helvetica",
        "titleSize": 14, "titleColor": "#111111", "titleWeight": "normal",
        "labelSize": 10, "axisTitleSize": 11,
        "legendLabelSize": 10,
        "domainColor": "#000000", "tickColor": "#000000", "labelColor": "#000000",
        "domainWidth": 0.5, "tickSize": 3,
        "legendOrient": "none",
        "padding": 4,
        "strokeWidth": 1.5, "lineOpacity": 1.0,
        "barOpacity": 1.0,
        "primaryColor": "#08306b",
    },
    "palette": "mono_blue",
}


DARK: Dict[str, Any] = {
    "name": "dark",
    "label": "Dark",
    "description": "Dark background, light text, vivid palette",
    "values": {
        "background": "#121212",
        "fontFamily": "Helvetica",
        "titleSize": 16, "titleColor": "#eaeaea", "titleWeight": "bold",
        "labelSize": 12, "axisTitleSize": 13,
        "legendLabelSize": 11, "legendTitleSize": 12,
        "domainColor": "#888888", "tickColor": "#888888", "labelColor": "#cccccc",
        "domainWidth": 1, "tickSize": 5,
        "legendOrient": "right",
        "padding": 12,
        "strokeWidth": 2, "lineOpacity": 1.0,
        "barOpacity": 1.0,
        "areaOpacity": 0.7,
        "primaryColor": "#4c72ff",
    },
    "palette": "vivid",
}


PRINT: Dict[str, Any] = {
    "name": "print",
    "label": "Print / Report",
    "description": "Black on white, thicker lines, large fonts",
    "values": {
        "background": "#ffffff",
        "fontFamily": "Georgia",
        "titleSize": 18, "titleColor": "#000000", "titleWeight": "bold",
        "labelSize": 14, "axisTitleSize": 15,
        "legendLabelSize": 13, "legendTitleSize": 14,
        "domainColor": "#000000", "tickColor": "#000000", "labelColor": "#000000",
        "domainWidth": 1.5, "tickSize": 6,
        "legendOrient": "right",
        "padding": 16,
        "strokeWidth": 3, "lineOpacity": 1.0,
        "barOpacity": 1.0,
        "primaryColor": "#003359",
    },
    "palette": "gs_primary",
}


THEMES: Dict[str, Dict[str, Any]] = {
    GS_CLEAN["name"]: GS_CLEAN,
    MINIMAL["name"]:  MINIMAL,
    DARK["name"]:     DARK,
    PRINT["name"]:    PRINT,
}


def get_theme(name: str) -> Dict[str, Any]:
    if name not in THEMES:
        available = ", ".join(sorted(THEMES.keys()))
        raise ValueError(f"Unknown theme '{name}'. Available: {available}")
    return THEMES[name]


def list_themes() -> List[Dict[str, Any]]:
    return [
        {"name": t["name"], "label": t["label"], "description": t["description"]}
        for t in THEMES.values()
    ]


# =============================================================================
# PALETTES
# =============================================================================


GS_PRIMARY: Dict[str, Any] = {
    "name": "gs_primary", "label": "GS Primary (PRISM default)", "kind": "categorical",
    "colors":       ["#003359", "#94C7DD", "#5C92CB", "#A6A6A6", "#C00000",
                     "#4F81BD", "#9BBB59", "#8064A2", "#F79646", "#4BACC6"],
    # Per-slot LastValueLabel hex. Identical to ``colors`` for slots that
    # are readable as 15pt text on white (slots 0 navy, 4 red, 5 cobalt,
    # 7 purple, 8 orange, 9 teal). Darker derived hex (HSL L * 0.55,
    # hue/sat preserved) for the readability-weak slots (1 light blue,
    # 2 mid blue, 3 grey, 6 olive). Engine reads via
    # ``skin['label_color_scheme']``; falls back to ``colors`` when
    # not set so other palettes keep today's match-line behaviour.
    "label_colors": ["#003359", "#307A9A", "#274F7B", "#5B5B5B", "#C00000",
                     "#4F81BD", "#566B2C", "#8064A2", "#F79646", "#4BACC6"],
}
GS_DIVERGING: Dict[str, Any] = {
    "name": "gs_diverging", "label": "GS Diverging", "kind": "diverging",
    "colors": ["#C00000", "#F79646", "#FFFFFF", "#5C92CB", "#003359"],
}
MONO_BLUE: Dict[str, Any] = {
    "name": "mono_blue", "label": "Monochrome Blue", "kind": "categorical",
    "colors": ["#08306b", "#2171b5", "#6baed6", "#c6dbef", "#deebf7"],
}
MONO_GREY: Dict[str, Any] = {
    "name": "mono_grey", "label": "Monochrome Grey", "kind": "categorical",
    "colors": ["#111111", "#444444", "#777777", "#aaaaaa", "#dddddd"],
}
VIVID: Dict[str, Any] = {
    "name": "vivid", "label": "Vivid", "kind": "categorical",
    "colors": ["#4c72ff", "#ffb347", "#ff6b6b", "#2ecc71", "#9b59b6",
               "#f39c12", "#1abc9c"],
}
TABLEAU: Dict[str, Any] = {
    "name": "tableau", "label": "Tableau 10", "kind": "categorical",
    "colors": ["#4c78a8", "#f58518", "#e45756", "#72b7b2", "#54a24b",
               "#eeca3b", "#b279a2", "#ff9da6", "#9d755d", "#bab0ac"],
}
OKABE_ITO: Dict[str, Any] = {
    "name": "okabe_ito", "label": "Okabe-Ito (colorblind-safe)", "kind": "categorical",
    "colors": ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2",
               "#D55E00", "#CC79A7", "#000000"],
}
PASTEL: Dict[str, Any] = {
    "name": "pastel", "label": "Pastel (soft, low-saturation)", "kind": "categorical",
    "colors": ["#A8DADC", "#FFB4A2", "#B5EAEA", "#FCE38A", "#C1A7E2",
               "#F8B5C8", "#A0D2DB", "#FFCFD2"],
}
VIRIDIS: Dict[str, Any]  = {"name": "viridis",  "label": "Viridis",  "kind": "sequential", "scheme": "viridis"}
BLUES: Dict[str, Any]    = {"name": "blues",    "label": "Blues",    "kind": "sequential", "scheme": "blues"}
REDS: Dict[str, Any]     = {"name": "reds",     "label": "Reds",     "kind": "sequential", "scheme": "reds"}
GREENS: Dict[str, Any]   = {"name": "greens",   "label": "Greens",   "kind": "sequential", "scheme": "greens"}
REDBLUE: Dict[str, Any]  = {"name": "redblue",  "label": "Red-Blue", "kind": "diverging",  "scheme": "redblue"}
SPECTRAL: Dict[str, Any] = {"name": "spectral", "label": "Spectral", "kind": "diverging",  "scheme": "spectral"}


PALETTES: Dict[str, Dict[str, Any]] = {
    p["name"]: p for p in [
        GS_PRIMARY, GS_DIVERGING, MONO_BLUE, MONO_GREY,
        VIVID, TABLEAU, OKABE_ITO, PASTEL,
        VIRIDIS, BLUES, REDS, GREENS, REDBLUE, SPECTRAL,
    ]
}


def get_palette(name: str) -> Dict[str, Any]:
    if name not in PALETTES:
        available = ", ".join(sorted(PALETTES.keys()))
        raise ValueError(f"Unknown palette '{name}'. Available: {available}")
    return PALETTES[name]


def list_palettes() -> List[Dict[str, Any]]:
    return list(PALETTES.values())


def list_palettes_by_kind(kind: str) -> List[Dict[str, Any]]:
    return [p for p in PALETTES.values() if p["kind"] == kind]


# =============================================================================
# CHART TYPE DETECTOR
# =============================================================================


MARK_ALIAS: Dict[str, str] = {
    "point": "point", "circle": "point", "square": "point",
    "line": "line", "trail": "line",
    "bar": "bar",
    "area": "area",
    "rect": "rect",
    "arc": "arc",
    "boxplot": "boxplot",
    "tick": "point",
}

ANNOTATION_MARKS = {"text", "rule", "geoshape", "image"}

DETECT_PRIORITY: List[str] = ["bar", "area", "arc", "rect", "boxplot", "line", "point"]


def _extract_mark(node: Any) -> Optional[str]:
    if not isinstance(node, dict):
        return None
    mark = node.get("mark")
    if isinstance(mark, str):
        return mark
    if isinstance(mark, dict):
        return mark.get("type")
    return None


def _walk_marks(node: Any, found: List[str]) -> None:
    if not isinstance(node, dict):
        return
    mark = _extract_mark(node)
    if mark:
        found.append(mark)
    for key in ("layer", "concat", "hconcat", "vconcat", "spec"):
        val = node.get(key)
        if isinstance(val, list):
            for item in val:
                _walk_marks(item, found)
        elif isinstance(val, dict):
            _walk_marks(val, found)
    if "repeat" in node:
        spec = node.get("spec")
        if isinstance(spec, dict):
            _walk_marks(spec, found)


def detect_chart_type(spec: Dict[str, Any]) -> str:
    """Return the primary mark type from a vega-lite spec.

    Annotation marks (text, rule, geoshape, image) are ignored.
    """
    raw_marks: List[str] = []
    _walk_marks(spec, raw_marks)
    if not raw_marks:
        raise ValueError(
            "Could not detect a mark in the vega-lite spec. The spec must contain "
            "'mark' at top level, inside a layer, or inside a concat/repeat/facet spec."
        )

    primary = [m for m in raw_marks if m not in ANNOTATION_MARKS] or raw_marks
    normalized = [MARK_ALIAS.get(m, m) for m in primary]

    counts: Dict[str, int] = {}
    for m in normalized:
        counts[m] = counts.get(m, 0) + 1

    max_count = max(counts.values())
    top = [m for m in normalized if counts[m] == max_count]
    for candidate in DETECT_PRIORITY:
        if candidate in top:
            return candidate
    return normalized[0]


def list_all_marks(spec: Dict[str, Any]) -> List[str]:
    raw: List[str] = []
    _walk_marks(spec, raw)
    return [MARK_ALIAS.get(m, m) for m in raw]


def detect_composite(spec: Dict[str, Any]) -> Optional[str]:
    """Return 'hconcat' | 'vconcat' | 'concat' | 'layer' | None if not composite."""
    if not isinstance(spec, dict):
        return None
    for key in ("hconcat", "vconcat", "concat"):
        if key in spec and isinstance(spec[key], list) and len(spec[key]) > 1:
            return key
    if "layer" in spec and isinstance(spec["layer"], list) and len(spec["layer"]) > 1:
        return "layer"
    return None


# =============================================================================
# HTML TEMPLATE
# =============================================================================
#
# Template uses literal __TOKEN__ placeholders (no format-string escaping).
# Pre-serialized JSON strings are inserted at render time.
# =============================================================================


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
<style>
body { margin: 0; padding: 16px; font-family: sans-serif; font-size: 13px; }
h1 { font-size: 16px; margin: 0 0 12px 0; }
h2 { font-size: 13px; margin: 0; }
h3 { font-size: 12px; margin: 8px 0 4px 0; }
/* The sidebar gives width back to the chart on a narrow window rather
   than holding 440px and pushing the chart into a scroller. */
.layout { display: grid; grid-template-columns: minmax(0, 1fr) clamp(340px, 34vw, 440px);
  gap: 16px; align-items: start; }
.panel { border: 1px solid #000; padding: 10px; }
.sidebar-panel { padding: 0; min-height: 320px; overflow: hidden; display: flex; flex-direction: column; box-sizing: border-box; }
.sidebar-panel .tab-content { padding: 12px; flex: 1 1 0; overflow: auto; max-height: none; min-height: 0; }
.chart-panel.fullscreen { grid-column: 1 / span 2; }
/* No min-height and no inner scroller: the wrapper is sized to the SVG so
   the resize frame can trace it, and any overflow scrolls at panel level. */
#chart { overflow: visible; }
.knob { margin: 4px 0; display: grid; grid-template-columns: 120px 1fr 50px; gap: 6px; align-items: center; }
.knob label { font-size: 11px; }
.knob input[type=range] { width: 100%; }
.knob input[type=color] { width: 100%; height: 22px; padding: 0; }
.knob input[type=text] { width: 100%; font-size: 11px; box-sizing: border-box; }
.knob select { width: 100%; font-size: 11px; }
.knob .val { font-size: 11px; text-align: right; font-family: monospace; }
details { margin: 4px 0; }
summary { cursor: pointer; font-weight: bold; font-size: 12px; padding: 3px 0; }
fieldset { border: 1px solid #888; margin: 6px 0; padding: 6px; }
legend { font-size: 11px; font-weight: bold; padding: 0 4px; }
.row { display: flex; gap: 6px; margin: 4px 0; flex-wrap: wrap; }
button { font-size: 11px; padding: 4px 8px; cursor: pointer; }
textarea { width: 100%; font-family: monospace; font-size: 10px; box-sizing: border-box; min-height: 140px; }
.note { font-size: 10px; color: #555; margin-top: 4px; }
.toolbar { margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #000; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.toolbar label { font-weight: bold; font-size: 12px; margin-right: 4px; }
.chart-toolbar { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; border-bottom: 1px solid #ccc; padding-bottom: 6px; }
.size-summary { font-family: monospace; font-size: 11px; color: #666; margin-left: 12px; flex: 1; }
.search-box { width: 100%; font-size: 12px; padding: 4px; box-sizing: border-box; margin-bottom: 8px; }
.hidden { display: none !important; }
/* Info tabs (live in right sidebar) */
.info-tabs { display: flex; flex-direction: column; height: 100%; }
.tab-bar { display: flex; border-bottom: 1px solid #000; background: #f0f0f0; flex-shrink: 0; }
.tab-button { border: none; background: none; font-size: 12px; font-weight: bold; padding: 8px 12px; cursor: pointer; border-right: 1px solid #ccc; font-family: sans-serif; }
.tab-button.active { background: #fff; border-bottom: 2px solid #003359; }
.tab-content { padding: 12px; max-height: 600px; overflow: auto; }
/* Knob cards section (lives below chart) */
.knobs-section { margin-top: 16px; padding: 10px; border: 1px solid #000; }
.knobs-section h2 { margin: 0 0 8px 0; font-size: 13px; }
.knob-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 10px; align-items: start; margin-top: 8px; }
.knob-card { border: 1px solid #000; padding: 8px 10px; background: #fff; margin: 0; }
.knob-card > summary { font-size: 12px; font-weight: bold; padding: 2px 0; margin-bottom: 4px; }
.knob-card[open] > summary { border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-bottom: 6px; }
.knob-card fieldset { border: 0; padding: 0; margin: 0; }
.knob-card .knob { margin: 3px 0; }
.tab-toolbar { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
.tab-toolbar input[type=search] { flex: 1; min-width: 200px; font-size: 12px; padding: 4px; }
/* Data table */
.data-table { border-collapse: collapse; font-size: 11px; font-family: monospace; width: 100%; }
.data-table th, .data-table td { border: 1px solid #ccc; padding: 3px 6px; text-align: left; }
.data-table th { background: #f0f0f0; cursor: pointer; user-select: none; font-weight: bold; }
.data-table th.sort-asc::after { content: " v"; }
.data-table th.sort-desc::after { content: " ^"; }
.data-table tr:nth-child(even) { background: #fafafa; }
.data-table tr.filtered-out { display: none; }
/* Code viewer */
.code-subtabs { display: flex; gap: 4px; margin-bottom: 6px; }
.code-sub-btn { border: 1px solid #ccc; background: #fafafa; font-size: 11px; padding: 3px 8px; cursor: pointer; }
.code-sub-btn.active { background: #fff; border-color: #003359; border-bottom-color: #fff; font-weight: bold; }
.code-block { border: 1px solid #ccc; background: #fafafa; font-family: monospace; font-size: 11px; padding: 8px; overflow: auto; max-height: 400px; white-space: pre; margin: 0; }
/* Metadata grid */
.meta-section { margin-bottom: 12px; }
.meta-section h3 { margin: 4px 0; font-size: 12px; }
.meta-grid { display: grid; grid-template-columns: 180px 1fr; gap: 2px 12px; font-size: 11px; }
.meta-grid .meta-key { color: #555; font-weight: bold; }
.meta-grid .meta-val { font-family: monospace; word-break: break-all; }
/* ---- In-place text editing -------------------------------------------
   Vega marks guide text (title, subtitle, axis titles, tick labels,
   legend text) with pointer-events="none" so clicks pass through. That
   is a presentation attribute, which any CSS declaration outranks in the
   cascade -- this rule is what makes those glyphs hit-testable at all.
   ---------------------------------------------------------------------- */
#chart svg text { pointer-events: all; }
#chart svg text.cfs-editable { cursor: text; }
#chart svg text.cfs-editable:hover {
  fill: #0b62c4 !important; paint-order: stroke;
  stroke: #d6e6fb; stroke-width: 5px; stroke-linejoin: round; }
#chart svg text.cfs-derived { cursor: help; }
#chart svg text.cfs-derived:hover {
  fill: #8a6d1f !important; paint-order: stroke;
  stroke: #fbf0cf; stroke-width: 5px; stroke-linejoin: round; }
.cfs-inline-editor { position: absolute; z-index: 9999; padding: 1px 4px;
  border: 2px solid #0b62c4; background: #fff; font-family: inherit;
  box-shadow: 0 3px 12px rgba(0,0,0,0.22); }
.cfs-toast { position: fixed; bottom: 16px; left: 50%;
  transform: translateX(-50%); background: #22262e; color: #fff;
  padding: 9px 16px; font-size: 12px; max-width: 620px; opacity: 0;
  pointer-events: none; transition: opacity 0.18s; z-index: 10000; }
.cfs-toast.on { opacity: 1; }
/* The south and south-east grips overhang the wrapper by 7px, so the gap
   the eye sees is this margin minus that. */
.cfs-hint { font-size: 10px; color: #555; margin-left: 12px; margin-top: 30px; }

/* ---- Direct manipulation: right-click menus ---------------------------
   Every non-text chart element (line, bar, point, axis, legend, plot
   background) resolves to a target and opens a menu at the pointer. The
   menu is a single reused root; it is rebuilt per open rather than
   pre-rendered, because the items depend on what was hit.
   ---------------------------------------------------------------------- */
#chart svg .cfs-hit { cursor: context-menu; }
#chart svg .cfs-hit:hover { filter: brightness(1.12) saturate(1.25); }
.cfs-menu { position: absolute; z-index: 10001; min-width: 214px;
  max-width: 306px; max-height: 78vh; overflow-y: auto;
  background: #fff; border: 1px solid #b9c2cd; border-radius: 7px;
  box-shadow: 0 8px 28px rgba(16,32,56,.20); padding: 5px 0;
  font-family: sans-serif; font-size: 12.5px; color: #16202c;
  display: none; user-select: none; }
.cfs-menu.on { display: block; }
.cfs-menu-head { padding: 6px 13px 7px; font-size: 11px; color: #6b7b8f;
  border-bottom: 1px solid #e6ebf1; margin-bottom: 4px; }
.cfs-menu-head b { display: block; font-size: 12.5px; color: #16202c;
  font-weight: 650; margin-bottom: 1px; }
.cfs-item { padding: 6px 13px; cursor: pointer; display: flex;
  align-items: center; gap: 9px; white-space: nowrap; }
.cfs-item:hover { background: #eaf2fb; }
.cfs-item.cfs-disabled { color: #a3aebc; cursor: default; }
.cfs-item.cfs-disabled:hover { background: none; }
.cfs-item .cfs-acc { margin-left: auto; color: #8593a5; font-size: 11px;
  font-family: ui-monospace, Menlo, monospace; padding-left: 18px; }
.cfs-item.cfs-on .cfs-acc { color: #1d6fc4; }
.cfs-sep { height: 1px; background: #e6ebf1; margin: 4px 0; }
.cfs-sub { padding: 3px 13px 7px; }
.cfs-sub-label { font-size: 10.5px; color: #7b8a9c; margin-bottom: 5px;
  text-transform: uppercase; letter-spacing: .4px; }
.cfs-swatches { display: grid; grid-template-columns: repeat(8, 19px);
  gap: 5px; }
.cfs-sw { width: 19px; height: 19px; border-radius: 4px; cursor: pointer;
  border: 1px solid rgba(0,0,0,.22); }
.cfs-sw:hover { transform: scale(1.16); }
.cfs-sw.cfs-cur { box-shadow: 0 0 0 2px #fff, 0 0 0 3.5px #1d6fc4; }
.cfs-steps { display: flex; align-items: center; gap: 7px; }
.cfs-steps button { font-size: 13px; width: 26px; height: 24px; padding: 0;
  line-height: 1; border: 1px solid #c3ccd8; background: #fff;
  border-radius: 5px; cursor: pointer; }
.cfs-steps button:hover { background: #eaf2fb; border-color: #1d6fc4; }
.cfs-steps .cfs-num { font-family: ui-monospace, Menlo, monospace;
  font-size: 12px; min-width: 44px; text-align: center; }
.cfs-menu input[type=color] { width: 100%; height: 26px; padding: 0;
  border: 1px solid #c3ccd8; border-radius: 5px; cursor: pointer;
  background: #fff; }
.cfs-dates { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
.cfs-dates input { border: 1px solid #c3ccd8; border-radius: 5px; padding: 3px 5px;
                   font: 11.5px inherit; color: #16202e; background: #fff; }
.cfs-dates button { border: 1px solid #1d6fc4; background: #1d6fc4; color: #fff;
                    border-radius: 5px; padding: 3px 10px; cursor: pointer;
                    font: 600 11.5px inherit; }
.cfs-dates button:hover { background: #175da6; }
.cfs-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.cfs-chip { border: 1px solid #c3ccd8; background: #fff; border-radius: 5px;
  padding: 4px 9px; font-size: 11.5px; cursor: pointer; }
.cfs-chip:hover { background: #eaf2fb; border-color: #1d6fc4; }
.cfs-chip.cfs-cur { background: #1d6fc4; border-color: #1d6fc4; color: #fff; }

/* ---- Direct manipulation: drag-to-resize ------------------------------
   The wrapper is sized in JS to the rendered SVG's exact box, so the
   frame and its handles trace the chart's own circumference rather than
   the panel's. Pinning them to the panel put the drag edge metres away
   from the chart whenever the chart was narrower than its container --
   which, in fullscreen, is always.
   ---------------------------------------------------------------------- */
.chart-panel { overflow-x: auto; }
#chartWrap { position: relative; display: inline-block; vertical-align: top; }
.cfs-frame { position: absolute; inset: -2px; pointer-events: none;
  border: 1px dashed #a9bed4; border-radius: 3px;
  opacity: 0; transition: opacity .12s; z-index: 15; }
#chartWrap:hover .cfs-frame, body.cfs-resizing .cfs-frame { opacity: 1; }
body.cfs-resizing .cfs-frame { border-style: solid; border-color: #1d6fc4;
  box-shadow: 0 0 0 3px rgba(29,111,196,.13); }
.cfs-grip { position: absolute; opacity: 0; transition: opacity .12s;
  background: #fff; border: 1.5px solid #1d6fc4; border-radius: 2px;
  box-shadow: 0 1px 3px rgba(16,32,56,.28); z-index: 20; }
#chartWrap:hover .cfs-grip, .cfs-grip.cfs-live { opacity: 1; }
.cfs-grip:hover, .cfs-grip.cfs-live { background: #1d6fc4; }
.cfs-grip-e  { right: -6px; top: 50%; margin-top: -13px;
  width: 9px; height: 26px; cursor: ew-resize; }
.cfs-grip-s  { bottom: -6px; left: 50%; margin-left: -13px;
  height: 9px; width: 26px; cursor: ns-resize; }
.cfs-grip-se { right: -7px; bottom: -7px; width: 12px; height: 12px;
  cursor: nwse-resize; }
body.cfs-resizing { cursor: nwse-resize; user-select: none; }
body.cfs-resizing #chart svg { pointer-events: none; }
.cfs-sizetag { position: fixed; z-index: 10002; background: #22262e;
  color: #fff; font: 11.5px/1 ui-monospace, Menlo, monospace;
  padding: 6px 9px; border-radius: 5px; pointer-events: none; display: none; }
.cfs-sizetag.on { display: block; }

/* ---- Advanced controls disclosure ---- */
.chart-toolbar button.primary { background: #003359; color: #fff;
  border: 1px solid #003359; border-radius: 4px; font-weight: 650;
  padding: 5px 14px; }
.chart-toolbar button.primary:hover { background: #00263f; }
.knobs-section > summary { font-size: 12.5px; font-weight: 650;
  padding: 7px 4px; cursor: pointer; }
.knobs-section .knobs-sub { font-weight: 400; color: #6b7b8f;
  font-size: 11px; margin-left: 8px; }
.knobs-section .knobs-body { padding-top: 8px;
  border-top: 1px solid #ccc; margin-top: 4px; }
</style>
</head>
<body>

<h1>__TITLE__</h1>

<input type="file" id="uploadInput" accept=".json" style="display:none;" onchange="uploadSheet(this.files[0])" />

<div class="layout" id="mainLayout">

  <div class="panel chart-panel" id="chartPanel">
    <div class="chart-toolbar">
      <button class="primary" onclick="downloadChart()" id="downloadBtn"
        title="Download the chart exactly as it looks now, as a print-resolution PNG">Download</button>
      <button onclick="undoLastEdit()" id="undoBtn"
        title="Undo the last edit">Undo</button>
      <button onclick="resetView()" title="Discard every edit and return to the chart as PRISM built it">Reset</button>
      <button onclick="toggleFullscreen()" title="Hide the side panel to maximise the chart" id="fullscreenBtn">Fullscreen</button>
      <button onclick="toggleChartFit()" id="fitBtn" class="hidden">Actual size</button>
      <span id="sizeSummary" class="size-summary"></span>
      <span id="status" style="font-size:11px; color:#555;"></span>
    </div>
    <div id="chartWrap">
      <div id="chart"></div>
      <div class="cfs-frame"></div>
      <div class="cfs-grip cfs-grip-e"  data-grip="e"  title="Drag to change width"></div>
      <div class="cfs-grip cfs-grip-s"  data-grip="s"  title="Drag to change height"></div>
      <div class="cfs-grip cfs-grip-se" data-grip="se" title="Drag to resize both"></div>
    </div>
    <div class="cfs-hint"><strong>Double-click</strong> any text to retype it.
      <strong>Right-click</strong> a line, bar, point, axis, legend or the
      background for its options. <strong>Drag</strong> the chart's right or
      bottom edge to resize.</div>
  </div>

  <!-- Right sidebar: Data / Code / Metadata / Export tabs -->
  <div class="panel sidebar-panel info-tabs" id="sidebarPanel">
    <div class="tab-bar">
      <button class="tab-button active" data-tab="data" onclick="switchTab('data')">Data</button>
      <button class="tab-button" data-tab="code" onclick="switchTab('code')">Code</button>
      <button class="tab-button" data-tab="metadata" onclick="switchTab('metadata')">Metadata</button>
      <button class="tab-button" data-tab="export" onclick="switchTab('export')">Export</button>
    </div>

    <div class="tab-content" id="tab-data">
      <div class="tab-toolbar">
        <select id="dataSourceSelect" onchange="onDataSourceChange()" style="font-size: 11px; max-width: 220px;"></select>
        <input type="search" id="dataSearchBox" placeholder="Search rows..." oninput="filterDataTable(this.value)" />
        <span id="dataSummaryLine" style="font-family: monospace; font-size: 11px;"></span>
        <button onclick="downloadDataCSV()">CSV</button>
        <button onclick="downloadDataTSV()">TSV</button>
        <button onclick="downloadDataJSON()">JSON</button>
        <button onclick="copyDataAsMarkdown()">Copy MD</button>
      </div>
      <div id="dataTableContainer"></div>
    </div>

    <div class="tab-content hidden" id="tab-code">
      <div class="code-subtabs">
        <button class="code-sub-btn active" data-codetab="vl" onclick="switchCodeSubtab('vl')">Vega-Lite JSON</button>
        <button class="code-sub-btn" data-codetab="altair" onclick="switchCodeSubtab('altair')">Altair Python</button>
        <button class="code-sub-btn" data-codetab="data" onclick="switchCodeSubtab('data')">Data (pd.DataFrame)</button>
      </div>
      <div id="code-vl" class="code-pane">
        <button onclick="copyText('vegaLiteCode')">Copy</button>
        <button onclick="downloadText('vegaLiteCode', FILENAME + '_spec.json', 'application/json')">Download</button>
        <pre class="code-block" id="vegaLiteCode"></pre>
      </div>
      <div id="code-altair" class="code-pane hidden">
        <button onclick="copyText('altairCode')">Copy</button>
        <button onclick="downloadText('altairCode', FILENAME + '_altair.py', 'text/x-python')">Download .py</button>
        <pre class="code-block" id="altairCode"></pre>
      </div>
      <div id="code-data" class="code-pane hidden">
        <button onclick="copyText('dataCode')">Copy</button>
        <button onclick="downloadText('dataCode', FILENAME + '_data.py', 'text/x-python')">Download .py</button>
        <pre class="code-block" id="dataCode"></pre>
      </div>
    </div>

    <div class="tab-content hidden" id="tab-metadata">
      <div id="metadataContainer"></div>
    </div>

    <div class="tab-content hidden" id="tab-export">
      <fieldset>
        <legend>Image</legend>
        <div class="row">
          <button onclick="exportPNG(2)">Download PNG</button>
          <button onclick="exportPNG(4)">Extra large</button>
        </div>
        <div class="note">Download matches what you see, including every edit.
          Extra large doubles the resolution for print.</div>
      </fieldset>
      <fieldset>
        <legend>Data</legend>
        <div class="row">
          <button onclick="downloadDataCSV()">CSV</button>
          <button onclick="downloadDataTSV()">TSV</button>
          <button onclick="downloadDataJSON()">JSON</button>
        </div>
      </fieldset>
      <fieldset>
        <legend>Code</legend>
        <div class="row">
          <button onclick="downloadAltair()">Altair .py</button>
          <button onclick="downloadDataPython()">Data .py</button>
        </div>
      </fieldset>
      <fieldset>
        <legend>Spec</legend>
        <div class="row">
          <button onclick="exportSpec()">Vega-Lite JSON</button>
          <button onclick="exportOverrides()">Overrides JSON</button>
          <button onclick="downloadSheet()">Spec Sheet JSON</button>
        </div>
      </fieldset>
      <fieldset>
        <legend>Composite</legend>
        <div class="row">
          <button onclick="exportStandaloneHTML()">Standalone HTML snapshot</button>
        </div>
        <div class="note">Saves the current interactive editor with all state baked in.</div>
      </fieldset>
      <fieldset>
        <legend>Share</legend>
        <div class="row">
          <button onclick="openInVegaEditor()">Open in Vega Editor</button>
        </div>
        <div class="note">Opens the current spec in vega.github.io/editor for debugging.</div>
      </fieldset>
    </div>

  </div>

</div>

<div class="cfs-toast" id="cfsToast"></div>

<!-- Every control also reachable by right-clicking the chart. Collapsed by
     default: the panel is the exhaustive fallback, not the primary surface. -->
<details class="knobs-section" id="knobsSection">
  <summary id="knobsSummary">Advanced controls
    <span class="knobs-sub">every setting, including the ones with no
      right-click equivalent</span></summary>
  <div class="knobs-body">
    <input type="search" class="search-box" id="searchBox" placeholder="Search all controls (e.g. 'title', 'axis', 'color')..." oninput="filterKnobs(this.value)" />
    <div class="knob-cards" id="knobContainer"></div>
    <div id="annotationSection"></div>
    <div id="perSeriesSection"></div>
    <div style="margin-top: 10px;">
      <fieldset class="knob-card">
        <legend>Saved looks and session preferences</legend>
        <div class="row" style="align-items:center;">
          <label style="font-size:11px;">Spec sheet:</label>
          <select id="specSheetSelect" style="min-width: 150px; font-size: 11px;"></select>
          <button onclick="overwriteCurrentSheet()">Save</button>
          <button onclick="saveAsNewSheet()">Save as new</button>
          <button onclick="deleteCurrentSheet()">Delete</button>
          <button onclick="downloadSheet()">Export .json</button>
          <button onclick="document.getElementById('uploadInput').click()">Import</button>
        </div>
        <div class="row">
          <button onclick="revertTextEdits()" title="Undo every in-place text edit at once, leaving styling alone">Revert text edits</button>
          <button onclick="resetToTheme()">Reset to theme</button>
          <button onclick="clearOverrides()">Clear overrides</button>
        </div>
        <div class="note">A spec sheet is a reusable bundle of theme, palette
          and control values. It persists across sessions in this browser.</div>
      </fieldset>
    </div>
  </div>
</details>

<div class="cfs-menu" id="cfsMenu"></div>
<div class="cfs-sizetag" id="cfsSizeTag"></div>

<script>
/* ============================================================
   CONSTANTS INJECTED FROM PYTHON
   ============================================================ */
const ORIGINAL_SPEC = __SPEC_JSON__;
const KNOBS = __KNOBS_JSON__;
const THEMES = __THEMES_JSON__;
const PALETTES = __PALETTES_JSON__;
const DIM_PRESETS = __DIMENSIONS_JSON__;
const TYPOGRAPHY_OVERRIDES = __TYPOGRAPHY_OVERRIDES_JSON__;
const INITIAL_THEME = __INITIAL_THEME__;
const INITIAL_PALETTE = __INITIAL_PALETTE__;
const INITIAL_DIM_PRESET = __INITIAL_DIM_PRESET__;
const INITIAL_OVERRIDES = __INITIAL_OVERRIDES__;
const INITIAL_SPEC_SHEETS = __INITIAL_SPEC_SHEETS__;
const INITIAL_ACTIVE_SHEET = __INITIAL_ACTIVE_SHEET__;
const PREF_KEY = "__PREF_KEY__";
const SHEETS_KEY = "__SHEETS_KEY__";
const FILENAME = "__FILENAME__";

/* ============================================================
   STATE
   ============================================================ */
let currentSpec = deepClone(ORIGINAL_SPEC);
let currentKnobValues = {};
let currentTheme = INITIAL_THEME;
let currentPalette = INITIAL_PALETTE;
let currentDimPreset = INITIAL_DIM_PRESET;
let currentSpecSheet = INITIAL_ACTIVE_SHEET || "(none)";
let specSheets = {};  // name -> spec sheet object
let overrides = {};
let vegaView = null;

/* ============================================================
   HELPERS
   ============================================================ */
function deepClone(obj) { return JSON.parse(JSON.stringify(obj)); }

function setPath(obj, path, value) {
  const parts = path.split(".");
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    if (cur[parts[i]] === undefined || cur[parts[i]] === null || typeof cur[parts[i]] !== "object") {
      cur[parts[i]] = {};
    }
    cur = cur[parts[i]];
  }
  cur[parts[parts.length - 1]] = value;
}

function getPath(obj, path) {
  const parts = path.split(".");
  let cur = obj;
  for (const p of parts) {
    if (cur === null || cur === undefined) return undefined;
    cur = cur[p];
  }
  return cur;
}

function normalizeColor(c) {
  if (!c) return "#000000";
  if (typeof c !== "string") return "#000000";
  if (c.length === 9 && c.startsWith("#")) return c.substring(0, 7);
  return c;
}

function walkEncoding(spec, channel, fn) {
  // Recursively find 'encoding.{channel}' and apply fn(encodingObj)
  let found = false;
  function walk(node) {
    if (!node || typeof node !== "object") return;
    if (node.encoding && node.encoding[channel]) {
      fn(node.encoding[channel]);
      found = true;
    }
    for (const key of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(node[key])) {
        for (const sub of node[key]) walk(sub);
      }
    }
    if (node.spec) walk(node.spec);
  }
  walk(spec);
  if (!found && spec.encoding) {
    spec.encoding[channel] = {};
    fn(spec.encoding[channel]);
  }
}

/* ============================================================
   TEXT-BEARING SPEC NAVIGATION

   The producer wraps the plot in a concat as soon as a caption /
   source / side panel exists, which moves the title off the spec
   root and onto the data panel. Anything that reads or writes chart
   TEXT therefore has to locate the owning node first rather than
   assume the root.

   Layouts this has to cope with (all producer-generated):

     plain               spec.title
     source=/caption=    spec.vconcat[0].title
                         spec.vconcat[1].mark.text        <- caption
     + side panels       spec.hconcat[1].vconcat[0].title
                         spec.hconcat[1].vconcat[1]       <- caption
                         spec.hconcat[0] / [2]            <- side panels
     composite / facet   spec.title                       <- super-title
                         spec.<c>[i].<c>[j].layer[0].title <- panel title
   ============================================================ */

function isTextPanelNode(node) {
  // A producer text panel is a single mark_text chart whose string is
  // baked into mark.text (caption, source, side narrative).
  return !!(node && typeof node === "object" &&
            node.mark && typeof node.mark === "object" &&
            node.mark.type === "text" &&
            typeof node.mark.text === "string");
}

function concatKeyOf(node) {
  if (!node || typeof node !== "object") return null;
  for (const key of ["vconcat", "hconcat", "concat"]) {
    if (Array.isArray(node[key])) return key;
  }
  return null;
}

function findTitleHost(spec) {
  // Return {node, path} for the node that owns the chart's primary title.
  // Prefers a node that already HAS a title (so a composite's super-title
  // wins over its panel titles); otherwise returns the primary data panel
  // so a first-ever title lands where the producer would have put it.
  if (!spec || typeof spec !== "object") return null;
  if (spec.title != null) return { node: spec, path: "spec" };

  const queue = [{ node: spec, path: "spec" }];
  const dataPanels = [];
  while (queue.length) {
    const { node, path } = queue.shift();
    if (node.title != null) return { node, path };
    const ck = concatKeyOf(node);
    if (ck) {
      node[ck].forEach((child, i) => {
        if (!isTextPanelNode(child)) {
          queue.push({ node: child, path: `${path}.${ck}[${i}]` });
        }
      });
      continue;
    }
    if (Array.isArray(node.layer)) {
      node.layer.forEach((child, i) =>
        queue.push({ node: child, path: `${path}.layer[${i}]` }));
    }
    if (node.spec) queue.push({ node: node.spec, path: `${path}.spec` });
    dataPanels.push({ node, path });
  }
  // No title anywhere: the shallowest non-text panel is the data chart.
  return dataPanels.length ? dataPanels[0] : { node: spec, path: "spec" };
}

function findTextPanels(spec) {
  // Classify every producer text panel. Captions sit at vconcat index >= 1
  // (below the plot); side narratives are hconcat edge children.
  const found = [];
  function walk(node, path) {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node.vconcat)) {
      node.vconcat.forEach((child, i) => {
        const p = `${path}.vconcat[${i}]`;
        if (i >= 1 && isTextPanelNode(child)) {
          found.push({ role: "caption", node: child, path: p });
        } else {
          walk(child, p);
        }
      });
    }
    if (Array.isArray(node.hconcat)) {
      const last = node.hconcat.length - 1;
      node.hconcat.forEach((child, i) => {
        const p = `${path}.hconcat[${i}]`;
        if (isTextPanelNode(child) && (i === 0 || i === last)) {
          found.push({
            role: i === 0 ? "side_left" : "side_right",
            node: child, path: p,
          });
        } else {
          walk(child, p);
        }
      });
    }
    if (Array.isArray(node.concat)) {
      node.concat.forEach((child, i) => walk(child, `${path}.concat[${i}]`));
    }
    if (Array.isArray(node.layer)) {
      node.layer.forEach((child, i) => walk(child, `${path}.layer[${i}]`));
    }
    if (node.spec) walk(node.spec, `${path}.spec`);
  }
  walk(spec, "spec");
  return found;
}

function findCaptionPanel(spec) {
  const panels = findTextPanels(spec);
  return panels.find(p => p.role === "caption") || null;
}

/* ---- Text-panel re-wrap ------------------------------------
   Producer text panels carry text pre-wrapped with literal "\n" and a
   height derived from the resulting line count (there is no width-aware
   autowrap in vega-lite mark_text). Editing the string therefore has to
   re-wrap it and re-derive the height, or long text overflows the panel.
   Mirrors chart_functions._wrap_text_to_width / _build_text_panel. ---- */

function wrapTextToWidth(text, widthPx, fontSize) {
  if (!text) return "";
  const charW = Math.max(1.0, fontSize * 0.55);
  const perLine = Math.max(1, Math.floor(widthPx / charW));
  const out = [];
  for (const paragraph of String(text).split("\n")) {
    const tokens = [];
    for (const raw of paragraph.split(/\s+/).filter(Boolean)) {
      if (raw.length > perLine) {
        for (let i = 0; i < raw.length; i += perLine) {
          tokens.push(raw.substring(i, i + perLine));
        }
      } else {
        tokens.push(raw);
      }
    }
    if (!tokens.length) { out.push(""); continue; }
    let line = tokens[0];
    for (const word of tokens.slice(1)) {
      if (line.length + 1 + word.length <= perLine) line = line + " " + word;
      else { out.push(line); line = word; }
    }
    out.push(line);
  }
  return out.join("\n");
}

function padFromNode(node, fallback) {
  // Recover the panel padding the engine used from the spec's outer padding.
  const p = node.padding;
  if (typeof p === "number") return p;
  if (!p || typeof p !== "object") return fallback;
  const edges = ["left", "right", "top", "bottom"]
    .map(k => Number(p[k]))
    .filter(v => Number.isFinite(v));
  return edges.length ? Math.max(...edges) : fallback;
}

function rewrapTextPanel(panel, newText) {
  // Rewrite a text panel's string, re-wrapped to its own content width,
  // and grow/shrink its height to match the new line count.
  const node = panel.node;
  const fontSize = Number(node.mark.fontSize) || 12;
  const width = Number(node.width) || 700;
  // The engine sets all four outer-padding edges to the panel padding and
  // then zeroes exactly the one edge abutting the chart, so the max over the
  // four edges recovers the original padding -- which is also the value the
  // engine used for the content width and the height. Reading a single named
  // edge would read the zeroed one on left/right side panels.
  const pad = padFromNode(node, 5);
  const contentW = Math.max(1, width - 2 * pad);
  const wrapped = wrapTextToWidth(newText, contentW, fontSize);
  node.mark.text = wrapped;
  const nLines = Math.max(1, wrapped.split("\n").length);
  const lineHeight = Math.max(fontSize + 2, Math.floor(fontSize * 1.45));
  node.height = nLines * lineHeight + 2 * pad;
  return wrapped;
}

/* ============================================================
   APPLY FUNCTIONS (complex spec mutations)
   ============================================================ */
const APPLY_FUNCTIONS = {
  setWidth: (spec, value) => walkSetSize(spec, "width", value),
  setHeight: (spec, value) => walkSetSize(spec, "height", value),
  // Title / subtitle must be written to the node that OWNS the title, not
  // to the spec root: any chart with a source / caption / side panel is
  // wrapped in a concat and carries its title on the inner data panel.
  // Writing the root there would render a second, unstyled title above the
  // whole concat instead of editing the real one.
  setTitleText: (spec, value) => {
    const host = findTitleHost(spec);
    if (!host) return;
    const node = host.node;
    if (!value) {
      if (typeof node.title === "object" && node.title !== null) {
        delete node.title.text;
        if (Object.keys(node.title).length === 0) delete node.title;
      } else {
        delete node.title;
      }
      return;
    }
    if (typeof node.title === "string") node.title = { text: node.title };
    if (typeof node.title !== "object" || node.title === null) node.title = {};
    node.title.text = value;
  },
  setSubtitleText: (spec, value) => {
    const host = findTitleHost(spec);
    if (!host) return;
    const node = host.node;
    if (typeof node.title === "string") node.title = { text: node.title };
    if (typeof node.title !== "object" || node.title === null) node.title = {};
    if (!value) { delete node.title.subtitle; return; }
    node.title.subtitle = value;
  },
  setCaptionText: (spec, value) => {
    // Empty value = "not overridden"; leave the producer's caption alone.
    // There is no caption panel to create from scratch here -- its width /
    // height / padding geometry is producer-computed.
    if (!value) return;
    const panel = findCaptionPanel(spec);
    if (!panel) return;
    rewrapTextPanel(panel, value);
  },
  setXAxisTitle: (spec, value) => {
    // Empty value = "user hasn't overridden" -> preserve producer titles.
    // We write to BOTH encoding.x.title (shorthand) AND encoding.x.axis.title
    // because vega-lite gives encoding.x.axis.title precedence over
    // encoding.x.title; if the producer set the former, just writing the
    // latter is silently ignored.
    if (!value) return;
    walkEncoding(spec, "x", enc => {
      enc.title = value;
      if (enc.axis && typeof enc.axis === "object") enc.axis.title = value;
    });
  },
  setYAxisTitle: (spec, value) => {
    if (!value) return;
    walkEncoding(spec, "y", enc => {
      enc.title = value;
      if (enc.axis && typeof enc.axis === "object") enc.axis.title = value;
    });
  },
  setLegendTitle: (spec, value) => {
    if (!value) return;
    walkEncoding(spec, "color", enc => {
      enc.title = value;
      if (enc.legend && typeof enc.legend === "object") enc.legend.title = value;
    });
  },
  setLegendShow: (spec, value) => {
    walkEncoding(spec, "color", enc => {
      if (!value) enc.legend = null;
      else if (enc.legend === null) enc.legend = {};
    });
  },
  // ----- Axis property helpers (apply to BOTH encoding-level AND
  //       config-level so the knob always wins regardless of where
  //       the producer put their styling). ---------------------------
  setXAxisFormat: (spec, value) =>
    setBothAxisProperty(spec, "x", "axisX", "format", value || undefined),
  setYAxisFormat: (spec, value) =>
    setBothAxisProperty(spec, "y", "axisY", "format", value || undefined),
  setXLabelAngle: (spec, value) =>
    setBothAxisProperty(spec, "x", "axisX", "labelAngle", value),
  setYLabelAngle: (spec, value) =>
    setBothAxisProperty(spec, "y", "axisY", "labelAngle", value),
  setXTickCount: (spec, value) =>
    setBothAxisProperty(spec, "x", "axisX", "tickCount", value),
  setYTickCount: (spec, value) =>
    setBothAxisProperty(spec, "y", "axisY", "tickCount", value),
  setXDomainShow: (spec, value) =>
    setBothAxisProperty(spec, "x", "axisX", "domain", !!value),
  setYDomainShow: (spec, value) =>
    setBothAxisProperty(spec, "y", "axisY", "domain", !!value),
  setXTickShow: (spec, value) =>
    setBothAxisProperty(spec, "x", "axisX", "ticks", !!value),
  setYTickShow: (spec, value) =>
    setBothAxisProperty(spec, "y", "axisY", "ticks", !!value),
  setXDomainMin: (spec, value) => setDomainBoundRepaired(spec, "x", 0, value),
  setXDomainMax: (spec, value) => setDomainBoundRepaired(spec, "x", 1, value),
  setYDomainMin: (spec, value) => setDomainBoundRepaired(spec, "y", 0, value),
  setYDomainMax: (spec, value) => setDomainBoundRepaired(spec, "y", 1, value),
  setXZeroStart: (spec, value) => setZeroStart(spec, "x", value),
  setYZeroStart: (spec, value) => setZeroStart(spec, "y", value),
  setXLogScale: (spec, value) => setScaleType(spec, "x", value ? "log" : null),
  setYLogScale: (spec, value) => setScaleType(spec, "y", value ? "log" : null),
  setYInvert: (spec, value) => {
    walkEncoding(spec, "y", enc => {
      if (!enc.scale) enc.scale = {};
      enc.scale.reverse = !!value;
    });
  },
  setStrokeDash: (spec, value) => {
    const map = {
      "solid":     undefined,
      "dashed":    [6, 4],
      "dotted":    [1, 2],
      "dash-dot":  [6, 3, 2, 3],
      "long-dash": [10, 4],
    };
    const arr = map[value];
    if (arr === undefined) {
      if (spec.config && spec.config.line) delete spec.config.line.strokeDash;
    } else {
      setPath(spec, "config.line.strokeDash", arr);
    }
  },
  setTrendlineDash: (spec, value) => {
    const map = { "solid": undefined, "dashed": [6, 4], "dotted": [1, 2] };
    const arr = map[value];
    if (arr === undefined) {
      if (spec.config && spec.config.rule) delete spec.config.rule.strokeDash;
    } else {
      setPath(spec, "config.rule.strokeDash", arr);
    }
  },
  setPrimaryColor: (spec, value) => {
    const pal = PALETTES[currentPalette];
    if (!pal || !pal.colors) { setPath(spec, "config.range.category.0", value); return; }
    const newColors = pal.colors.slice();
    newColors[0] = value;
    setPath(spec, "config.range.category", newColors);
  },
  setWaterfallPositive: (spec, value) => {
    const cats = getPath(spec, "config.range.category") || (PALETTES[currentPalette]?.colors || []);
    const arr = cats.slice();
    arr[0] = value;
    setPath(spec, "config.range.category", arr);
  },
  setWaterfallNegative: (spec, value) => {
    const cats = getPath(spec, "config.range.category") || (PALETTES[currentPalette]?.colors || []);
    const arr = cats.slice();
    arr[1] = value;
    setPath(spec, "config.range.category", arr);
  },

  // --- Interactivity ---
  // Tooltip handling must cope with THREE places a tooltip can live:
  //   1. encoding.tooltip          (producer-set, common in PRISM)
  //   2. mark.tooltip               (producer-set at mark level)
  //   3. config.mark.tooltip        (our default, or producer config)
  //
  // If the producer set encoding.tooltip, we must NOT add config.mark.tooltip
  // on top (Vega-Lite merges the two tooltip expressions and produces
  // malformed output with unbalanced parens). When the knob is off, we
  // disable ALL three paths. When the knob is on, if the producer configured
  // an encoding.tooltip we leave it, otherwise we use config.mark.tooltip.
  setTooltipEnabled: (spec, value) => {
    if (!spec.config) spec.config = {};
    if (!spec.config.mark) spec.config.mark = {};
    if (value) {
      // Prefer producer's explicit encoding.tooltip if one exists; don't
      // stack a second tooltip on top.
      if (specHasEncodingTooltip(spec) || specHasMarkTooltip(spec)) {
        // Clear any previously-set config.mark.tooltip so we don't collide.
        if (spec.config.mark.tooltip !== undefined) delete spec.config.mark.tooltip;
        return;
      }
      const showAll = currentKnobValues.tooltipShowAllFields !== false;
      spec.config.mark.tooltip = showAll ? { content: "data" } : true;
    } else {
      // Disable everywhere: config, mark, encoding.
      spec.config.mark.tooltip = null;
      disableAllTooltips(spec);
    }
  },
  setTooltipContent: (spec, value) => {
    if (!spec.config) spec.config = {};
    if (!spec.config.mark) spec.config.mark = {};
    if (currentKnobValues.tooltipEnabled === false) return;
    if (specHasEncodingTooltip(spec) || specHasMarkTooltip(spec)) return;
    spec.config.mark.tooltip = value ? { content: "data" } : true;
  },
  setCrosshair: (spec, value) => {
    // Crosshair is a rule-based hover selection. We tag it with name so we
    // can remove it cleanly. Composite specs (hconcat/vconcat) cannot accept
    // a top-level layer, so the crosshair is skipped for those.
    removeNamedLayer(spec, "__crosshair__");
    if (!value) return;
    if (isCompositeSpec(spec)) return;
    const xField = findEncodingField(spec, "x");
    if (!xField) return;
    const rule = {
      name: "__crosshair__",
      mark: { type: "rule", color: "#888", strokeDash: [4, 4] },
      encoding: {
        x: { field: xField.field, type: xField.type },
      },
      params: [{
        name: "__crosshair_hover__",
        select: { type: "point", encodings: ["x"], nearest: true, on: "pointerover", clear: "pointerout" },
      }],
      transform: [{ filter: { param: "__crosshair_hover__", empty: false } }],
    };
    addLayer(spec, rule);
  },
  setBrushZoomX: (spec, value) => {
    // scale-bound interval params only work on single-view specs.
    removeParamRecursive(spec, "__zoom_x__");
    if (!value || isCompositeSpec(spec)) return;
    setSelectionParam(spec, "__zoom_x__", value, ["x"]);
  },
  setBrushZoomY: (spec, value) => {
    removeParamRecursive(spec, "__zoom_y__");
    if (!value || isCompositeSpec(spec)) return;
    setSelectionParam(spec, "__zoom_y__", value, ["y"]);
  },
  setLegendClickToggle: (spec, value) => {
    // Always clear any previous legend selection from every level of the tree
    // (vega-lite compiles composites into multiple units, and duplicate
    // params at the composite root cause "Duplicate signal name" errors).
    removeParamRecursive(spec, "__legend_sel__");
    if (!value) return;
    // Find a panel with a NOMINAL/ORDINAL color encoding - that's the only
    // kind of color legend that makes sense to click-toggle. Continuous color
    // ramps (heatmaps) are skipped.
    const target = findNominalColorPanel(spec);
    if (!target) return;
    if (!Array.isArray(target.panel.params)) target.panel.params = [];
    target.panel.params.push({
      name: "__legend_sel__",
      select: { type: "point", fields: [target.field] },
      bind: "legend",
    });
    // Bind opacity to the selection, limited to the same panel's subtree.
    walkEncoding(target.panel, "opacity", enc => {
      enc.condition = { param: "__legend_sel__", value: 1 };
      enc.value = 0.15;
    });
  },
};

function findEncodingField(spec, channel) {
  let result = null;
  function walk(node) {
    if (result || !node || typeof node !== "object") return;
    if (node.encoding && node.encoding[channel] && node.encoding[channel].field) {
      result = { field: node.encoding[channel].field, type: node.encoding[channel].type || "nominal" };
      return;
    }
    for (const key of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(node[key])) { for (const s of node[key]) walk(s); }
    }
    if (node.spec) walk(node.spec);
  }
  walk(spec);
  return result;
}

function removeNamedLayer(spec, name) {
  if (Array.isArray(spec.layer)) {
    spec.layer = spec.layer.filter(l => l.name !== name);
    if (spec.layer.length === 0) delete spec.layer;
    else if (spec.layer.length === 1 && spec.mark === undefined) {
      // collapse back to single spec if only one layer remains
      const only = spec.layer[0];
      Object.assign(spec, only);
      delete spec.layer;
    }
  }
}

function addLayer(spec, layerObj) {
  if (Array.isArray(spec.layer)) {
    spec.layer.push(layerObj);
    return;
  }
  // Wrap current spec into a layer + add new layer
  const base = {};
  for (const k of ["mark", "encoding", "transform", "selection", "params"]) {
    if (spec[k] !== undefined) { base[k] = spec[k]; delete spec[k]; }
  }
  if (Object.keys(base).length > 0) {
    spec.layer = [base, layerObj];
  } else {
    spec.layer = [layerObj];
  }
}

function setParam(spec, paramObj) {
  if (!Array.isArray(spec.params)) spec.params = [];
  const idx = spec.params.findIndex(p => p.name === paramObj.name);
  if (idx >= 0) spec.params[idx] = paramObj;
  else spec.params.push(paramObj);
}

function removeParam(spec, name) {
  if (!Array.isArray(spec.params)) return;
  spec.params = spec.params.filter(p => p.name !== name);
  if (spec.params.length === 0) delete spec.params;
}

function removeParamRecursive(spec, name) {
  // Strip a named param from every node in the spec tree. Needed for composite
  // specs where the same param may have been injected into multiple panels.
  function walk(node) {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node.params)) {
      node.params = node.params.filter(p => p.name !== name);
      if (node.params.length === 0) delete node.params;
    }
    for (const key of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(node[key])) {
        for (const sub of node[key]) walk(sub);
      }
    }
    if (node.spec) walk(node.spec);
  }
  walk(spec);
}

function isCompositeSpec(spec) {
  if (!spec || typeof spec !== "object") return false;
  for (const key of ["hconcat", "vconcat", "concat"]) {
    if (Array.isArray(spec[key]) && spec[key].length > 1) return true;
  }
  return false;
}

function findNominalColorPanel(spec) {
  // Walk the spec tree and return the first panel that has a categorical
  // color encoding. Returns { panel, field } or null if none found.
  let result = null;
  function walk(node) {
    if (result || !node || typeof node !== "object") return;
    if (node.encoding && node.encoding.color && node.encoding.color.field) {
      const t = node.encoding.color.type || "nominal";
      if (t === "nominal" || t === "ordinal") {
        result = { panel: node, field: node.encoding.color.field };
        return;
      }
    }
    for (const key of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(node[key])) {
        for (const sub of node[key]) walk(sub);
      }
    }
    if (node.spec) walk(node.spec);
  }
  walk(spec);
  return result;
}

function setSelectionParam(spec, name, enabled, encodings) {
  if (!enabled) { removeParam(spec, name); return; }
  setParam(spec, {
    name: name,
    select: { type: "interval", encodings: encodings },
    bind: "scales",
  });
}

function specHasEncodingTooltip(spec) {
  if (!spec || typeof spec !== "object") return false;
  if (spec.encoding && spec.encoding.tooltip !== undefined) return true;
  for (const key of ["layer", "hconcat", "vconcat", "concat"]) {
    if (Array.isArray(spec[key])) {
      for (const child of spec[key]) {
        if (specHasEncodingTooltip(child)) return true;
      }
    }
  }
  if (spec.spec && specHasEncodingTooltip(spec.spec)) return true;
  return false;
}

function specHasMarkTooltip(spec) {
  if (!spec || typeof spec !== "object") return false;
  if (spec.mark && typeof spec.mark === "object" && spec.mark.tooltip !== undefined) return true;
  for (const key of ["layer", "hconcat", "vconcat", "concat"]) {
    if (Array.isArray(spec[key])) {
      for (const child of spec[key]) {
        if (specHasMarkTooltip(child)) return true;
      }
    }
  }
  if (spec.spec && specHasMarkTooltip(spec.spec)) return true;
  return false;
}

function disableAllTooltips(spec) {
  if (!spec || typeof spec !== "object") return;
  if (spec.encoding && spec.encoding.tooltip !== undefined) {
    delete spec.encoding.tooltip;
  }
  if (spec.mark && typeof spec.mark === "object" && spec.mark.tooltip !== undefined) {
    spec.mark.tooltip = false;
  }
  for (const key of ["layer", "hconcat", "vconcat", "concat"]) {
    if (Array.isArray(spec[key])) {
      for (const child of spec[key]) disableAllTooltips(child);
    }
  }
  if (spec.spec) disableAllTooltips(spec.spec);
}

/* How a text panel should follow the plot's size depends entirely on
   which way it is stacked against it:

     vconcat (caption / source strip, sits BELOW the plot)
        width  must match, or the concat renders ragged
        height is the height of its text -- forcing it pads dead space

     hconcat (side narrative, sits BESIDE the plot)
        width  is its own column, independent of the plot
        height is the height of its text, same as above

   So the walk has to know its stacking context, not just the node. */
function walkSetSize(node, key, value, stack) {
  // Set width or height everywhere it already exists in the spec tree
  // (top-level + every layer/concat panel). For layered PRISM specs,
  // size is carried by the inner layer, not the root, so a top-level-
  // only update would be ignored. Always set at the top level too so
  // single-view specs still work.
  if (!node || typeof node !== "object") return;
  stack = stack || "root";
  if (isTextPanelNode(node) && !(key === "width" && stack === "vstack")) return;
  // Always set at the current node (top-level or this panel).
  // For layered specs, this updates layer[0], layer[1], etc.; the layer
  // that vega-lite picks for layout will get the right value.
  if (key in node || node === currentSpec) {
    // For arrays inside encoding (e.g. tooltip list) this is wrong,
    // but `width` / `height` only ever appear as scalar properties,
    // so the typeof-number / typeof-undefined check below is safe.
    if (typeof node[key] === "number" || node[key] === undefined ||
        node === currentSpec) {
      node[key] = value;
    }
  }
  // Layers share their parent's stacking context; they are drawn on top
  // of one another, not next to one another.
  if (Array.isArray(node.layer)) {
    for (const child of node.layer) walkSetSize(child, key, value, stack);
  }
  for (const [subKey, kind] of [["vconcat", "vstack"], ["concat", "vstack"],
                                ["hconcat", "hstack"]]) {
    if (Array.isArray(node[subKey])) {
      for (const child of node[subKey]) walkSetSize(child, key, value, kind);
    }
  }
  if (node.spec) walkSetSize(node.spec, key, value, stack);
}

function walkExtractSize(node, key) {
  // Find the first numeric width/height belonging to an actual plot.
  // Text panels are skipped: a side narrative's width describes a column
  // of prose, and reporting it as "the chart width" makes both the size
  // readout and the drag origin wrong on every chart with side panels.
  if (!node || typeof node !== "object") return undefined;
  if (isTextPanelNode(node)) return undefined;
  if (typeof node[key] === "number") return node[key];
  for (const subKey of ["layer", "concat", "hconcat", "vconcat"]) {
    if (Array.isArray(node[subKey])) {
      for (const child of node[subKey]) {
        const v = walkExtractSize(child, key);
        if (v !== undefined) return v;
      }
    }
  }
  if (node.spec) return walkExtractSize(node.spec, key);
  return undefined;
}

/* Reads the bound the way the encoding it lands on will be read.
   parseFloat on a temporal axis turned "2022-06-30" into 2022, which
   vega reads as 2022 MILLISECONDS after the epoch -- the chart collapsed
   into a three-millisecond window in 1970. Returns true when a temporal
   bound was written, so the caller knows the window moved. */
function setDomainBound(spec, channel, idx, rawValue) {
  const isBlank = rawValue === "" || rawValue == null;
  let wroteTemporal = false;
  walkEncoding(spec, channel, enc => {
    // Side text panels carry an empty x encoding with no field and no
    // type. It has no scale to bound, and parseFloat happily wrote a
    // half-parsed year into it.
    if (!enc.field && !enc.type && !enc.aggregate && !enc.datum) return;
    const temporal = enc.type === "temporal";
    let value = null;
    if (!isBlank) {
      if (temporal) {
        const d = parseSpecDate(rawValue);
        if (d) value = formatSpecDate(d, true);
      } else {
        const num = parseFloat(rawValue);
        if (!isNaN(num)) value = num;
      }
    }
    // Blank knob means "auto"; so does a value this encoding cannot read,
    // because the alternative is writing a bound that silently destroys
    // the axis. Clearing at idx returns the scale to producer-set or
    // vega-lite auto.
    if (value === null) {
      if (enc.scale && Array.isArray(enc.scale.domain)) {
        enc.scale.domain[idx] = null;
        if (enc.scale.domain[0] === null && enc.scale.domain[1] === null) {
          delete enc.scale.domain;
        }
      }
      return;
    }
    if (!enc.scale) enc.scale = {};
    if (!Array.isArray(enc.scale.domain)) enc.scale.domain = [null, null];
    enc.scale.domain[idx] = value;
    if (temporal) wroteTemporal = true;
  });
  return wroteTemporal;
}

/* The Advanced-controls entry point. Writing a temporal x bound is the
   same edit the right-click menu makes, so it has to leave the chart in
   the same state -- otherwise the panel documented as "every setting"
   is also the one back door that produces the clamp-only breakage the
   repair set exists to prevent. */
function setDomainBoundRepaired(spec, channel, idx, rawValue) {
  const wroteTemporal = setDomainBound(spec, channel, idx, rawValue);
  const info = temporalPlotInfo(spec);
  if (!info) return;
  if (channel === "x") {
    if (!wroteTemporal) return;
    // Resolve the end the user left blank against the data, so one typed
    // bound produces the window actually on screen rather than a
    // half-specified domain nothing else in the file knows how to read.
    const win = effectiveXWindow(spec, info);
    if (win) applyTimeWindow(spec, win[0], win[1], { info: info });
    return;
  }
  // A y bound moves the end-of-line labels even though the window did
  // not, because they are spaced in pixel space against the domain.
  if (channel === "y" && info.yField) {
    const win = currentWindow(spec, info) || dataExtent(info);
    const dom = currentYDomain(spec, info.yField);
    if (win && Array.isArray(dom) && dom[0] !== null && dom[1] !== null) {
      relocateEndlineLabels(spec, info, rowsInWindow(info, win[0], win[1]), dom);
    }
  }
}

function setZeroStart(spec, channel, mode) {
  walkEncoding(spec, channel, enc => {
    if (!enc.scale) enc.scale = {};
    if (mode === "auto") delete enc.scale.zero;
    else if (mode === "force") enc.scale.zero = true;
    else if (mode === "off") enc.scale.zero = false;
  });
}

function setScaleType(spec, channel, scaleType) {
  walkEncoding(spec, channel, enc => {
    if (!enc.scale) enc.scale = {};
    if (scaleType === null) delete enc.scale.type;
    else enc.scale.type = scaleType;
  });
}

/* ============================================================
   ENGINE PORTS

   Time windowing cannot be expressed as "write scale.domain and
   re-render": the producer hard-writes the y domain from the full
   frame, picks the x tick strategy for the full span, and pins the
   end-of-line labels at max(x). Repairing those needs the same
   arithmetic the engine used to derive them in the first place, and
   the studio is a static page with no Python behind it.

   So three engine functions are ported here verbatim in behaviour:
   calculate_y_axis_domain, determine_date_format (its calendar and
   intraday ladders), and _stagger_lvl_text_y. They are pure -- no
   DOM, no spec -- so the parity harness in dev/ can drive them
   against their Python originals through a headless browser and
   assert byte-equal output. Anything that changes here has to keep
   that harness green; an approximation is not good enough, because
   the repair rewrites label positions in place and error accumulates
   across successive window edits.
   ============================================================ */

/* The producer embeds naive ISO strings ("2020-03-31T00:00:00"), which
   are wall-clock instants with no zone. Two traps follow.

   Date's own parser disagrees with itself: a date-only string is read
   as UTC while a date-time string is read as local, so the two forms
   in one dataset land an offset apart. Parse the fields explicitly.

   And the fields are then loaded as UTC rather than local, which makes
   every span DST-free. A window over 2020-01-01..2020-09-30 is 273
   days to the engine, whose pandas timestamps are equally naive, but
   272 days and 23 hours to a local-time Date -- and truncating that to
   whole days drops a tick, moves a ladder rung, and puts the studio's
   axis one stride away from the one the engine would have drawn. Every
   accessor below is therefore a getUTC*: the whole module treats these
   as wall-clock, exactly as the engine does. */
function parseSpecDate(v) {
  if (v instanceof Date) return isFinite(v.getTime()) ? v : null;
  if (typeof v === "number") { const d = new Date(v); return isFinite(d.getTime()) ? d : null; }
  if (typeof v !== "string") return null;
  const m = v.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?)?/);
  if (!m) { const d = new Date(v); return isFinite(d.getTime()) ? d : null; }
  const ms = m[7] ? Math.round(parseFloat("0." + m[7]) * 1000) : 0;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3],
                              +(m[4] || 0), +(m[5] || 0), +(m[6] || 0), ms));
  // Date.UTC rolls out-of-range components over, so a typo'd "2022-13-45"
  // would come back as 2023-02-14 -- a different date, silently accepted.
  // Anything the user can type has to fail loudly instead.
  if (d.getUTCFullYear() !== +m[1] || d.getUTCMonth() !== +m[2] - 1 ||
      d.getUTCDate() !== +m[3]) return null;
  return d;
}

/* Round-trip of parseSpecDate. Midnight is written date-only so a
   window written by the studio reads the way the producer's own
   annotation rows do. */
function formatSpecDate(d, forceTime) {
  const p = n => (n < 10 ? "0" : "") + n;
  const day = d.getUTCFullYear() + "-" + p(d.getUTCMonth() + 1) + "-" + p(d.getUTCDate());
  if (!forceTime && !d.getUTCHours() && !d.getUTCMinutes() && !d.getUTCSeconds()) return day;
  return day + "T" + p(d.getUTCHours()) + ":" + p(d.getUTCMinutes()) +
         ":" + p(d.getUTCSeconds());
}

function cfsMedian(arr) {
  if (!arr.length) return null;
  const s = arr.slice().sort((a, b) => a - b);
  const mid = s.length >> 1;
  return (s.length % 2) ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

function cfsNum(v) {
  if (typeof v === "number") return isFinite(v) ? v : null;
  if (typeof v === "string" && v.trim() !== "") {
    const n = parseFloat(v);
    return isFinite(n) ? n : null;
  }
  return null;
}

/* ---- port of calculate_y_axis_domain (engine chart_functions.py) ----
   The snap-to-zero rule is the part that cannot be approximated. Both
   gates have to fire: the floor must be within 20% of the data SPAN
   (so "0.5% to 10% unemployment" pulls zero in as a useful reference)
   and within 5% of the data TOP (so an indexed-performance series
   running 80-735 does not, because 80 is nowhere near zero in
   absolute terms even though it looks close relative to the range).
   Dropping either gate produces a domain that is right at some
   windows and wrong at others. */
function calcYAxisDomain(values, opts) {
  opts = opts || {};
  const includeZero = !!opts.includeZero;
  const preventZeroStart = opts.preventZeroStart !== false;
  const paddingPct = (opts.paddingPct === undefined) ? 0.05 : opts.paddingPct;

  let dataMin = Infinity, dataMax = -Infinity, n = 0;
  for (const raw of values) {
    const v = cfsNum(raw);
    if (v === null) continue;
    if (v < dataMin) dataMin = v;
    if (v > dataMax) dataMax = v;
    n++;
  }
  if (!n) return [0.0, 1.0];

  const dataRange = dataMax - dataMin;
  if (dataRange === 0) {
    if (dataMax === 0) return [-1.0, 1.0];
    const synthetic = Math.abs(dataMax) * 0.05;
    return [dataMax - synthetic, dataMax + synthetic];
  }

  let domainMin = dataMin, domainMax = dataMax;
  if (preventZeroStart && domainMin > 0) {
    const relative = dataRange > 0 ? dataRange * 0.2 : Math.abs(domainMin) * 0.2;
    const absolute = Math.abs(domainMax) * 0.05;
    if (domainMin <= relative && domainMin <= absolute) domainMin = 0.0;
  }
  const padding = (domainMax - domainMin) * paddingPct;
  domainMin -= padding;
  domainMax += padding;
  if (includeZero) {
    domainMin = Math.min(domainMin, 0.0);
    domainMax = Math.max(domainMax, 0.0);
  }
  return [domainMin, domainMax];
}

/* ---- port of the determine_date_format ladder ---- */

const CFS_AXIS_LABEL_FONT = 18;
const CFS_NICE_MONTH_STEPS = [1, 2, 3, 6, 12, 24, 36, 60, 120];
const CFS_NICE_YEAR_STEPS = [1, 2, 5, 10, 20, 25, 50, 100];
const CFS_TICK_STEP_LADDER = [
  ["year", 10], ["year", 5], ["year", 2], ["year", 1],
  ["month", 6], ["month", 3], ["month", 1],
  ["week", 2], ["week", 1], ["day", 7], ["day", 3], ["day", 1],
];
const CFS_INTRADAY_STRIDES_S = [
  10, 30, 60, 300, 600, 900, 1800,
  3600, 7200, 10800, 21600, 43200, 86400, 172800,
];

function maxTicksForWidth(chartWidth, sampleLabel, labelAngle, fontSize) {
  if (fontSize === undefined || fontSize === null) fontSize = CFS_AXIS_LABEL_FONT;
  const n = Math.max(String(sampleLabel).length, 1);
  const charW = fontSize * 0.6;
  const breathing = Math.max(fontSize * 1.5, 24);
  let per;
  if (labelAngle === 0) per = n * charW + breathing;
  else if (Math.abs(labelAngle) >= 90) per = fontSize + breathing * 0.5;
  else per = n * charW * 0.7 + breathing * 0.6;
  return Math.max(Math.floor(chartWidth / per), 2);
}

function formatForStep(interval, step) {
  if (interval === "year") return ["%Y", "2025"];
  if (interval === "month" && step >= 12) return ["%Y", "2025"];
  if (interval === "month") return ["%b %y", "Mar 25"];
  if (interval === "week" || interval === "day") return ["%d %b", "06 Mar"];
  if (interval === "hour") return ["%H:%M", "09:30"];
  if (interval === "minute" || interval === "second") return ["%H:%M:%S", "09:30:00"];
  return ["%Y", "2025"];
}

/* Vega-Lite silently ignores {"interval":"month","step":N} for N >= 12
   and falls back to default annual ticks, so month steps of a year or
   more have to be re-expressed as year steps. */
function temporalTickStep(interval, step) {
  if (interval === "month" && step >= 12) {
    return { interval: "year", step: Math.max(1, Math.round(step / 12)) };
  }
  return { interval: interval, step: step };
}

function coarsenMonthStepToFit(spanMonths, chartWidth, initialStep, fontSize) {
  let last = null;
  for (const step of CFS_NICE_MONTH_STEPS) {
    if (step < initialStep) continue;
    const fmt = step >= 12 ? "%Y" : "%b %y";
    const sample = step >= 12 ? "2025" : "Mar 25";
    const nTicks = Math.max(Math.trunc(spanMonths / step) + 1, 2);
    last = { step: step, fmt: fmt, sample: sample, nTicks: nTicks };
    if (nTicks <= maxTicksForWidth(chartWidth, sample, 0, fontSize)) return last;
  }
  if (last === null) {
    return { step: Math.max(initialStep, 1), fmt: "%b %y", sample: "Mar 25", nTicks: 2 };
  }
  return last;
}

function stepForTarget(spanMonths, targetTicks) {
  const raw = Math.max(spanMonths / Math.max(targetTicks, 1), 1.0);
  for (const nice of CFS_NICE_MONTH_STEPS) if (raw <= nice) return nice;
  return 120;
}

/* Vega-Lite anchors temporal ticks to the calendar, not to the data,
   so a configuration can be arithmetically sensible and still render
   one lonely tick. Mirror the anchoring to count what will actually
   appear inside the range. */
function countCalendarTicksInRange(minDate, maxDate, tickStep, tickCount) {
  if (!tickStep) return (typeof tickCount === "number") ? tickCount : 2;
  const interval = tickStep.interval;
  let step = parseInt(tickStep.step, 10);
  if (!isFinite(step) || step < 1) step = 1;
  const lo = minDate.getTime(), hi = maxDate.getTime();

  if (interval === "year") {
    let count = 0;
    for (let y = minDate.getUTCFullYear(); y <= maxDate.getUTCFullYear(); y++) {
      if (y % step !== 0) continue;
      const t = Date.UTC(y, 0, 1);
      if (t >= lo && t <= hi) count++;
    }
    return count;
  }
  if (interval === "month") {
    let count = 0;
    for (let y = minDate.getUTCFullYear(); y <= maxDate.getUTCFullYear() + 1; y++) {
      for (let mo = 1; mo <= 12; mo++) {
        if ((mo - 1) % step !== 0) continue;
        const t = Date.UTC(y, mo - 1, 1);
        if (t >= lo && t <= hi) count++;
      }
    }
    return count;
  }
  // pandas Timedelta.days truncates to whole days before the division.
  const spanDays = Math.trunc((hi - lo) / 86400000);
  if (interval === "week") return Math.max(Math.trunc(spanDays / (7 * step)), 1);
  if (interval === "day") return Math.max(Math.trunc(spanDays / step) + 1, 1);
  const spanSec = (hi - lo) / 1000;
  if (interval === "hour") return Math.max(Math.trunc(spanSec / 3600 / step) + 1, 1);
  if (interval === "minute") return Math.max(Math.trunc(spanSec / 60 / step) + 1, 1);
  if (interval === "second") return Math.max(Math.trunc(spanSec / step) + 1, 1);
  return 2;
}

function ensureMinTemporalTicks(cfg, minDate, maxDate, nSamples, minTicks) {
  if (minTicks === undefined) minTicks = 2;
  if (!cfg.tickStep) return cfg;
  if (!nSamples) return cfg;
  const effectiveMin = Math.max(1, Math.min(minTicks, nSamples));
  if (countCalendarTicksInRange(minDate, maxDate, cfg.tickStep, cfg.tickCount) >= effectiveMin) {
    return cfg;
  }
  const curInterval = cfg.tickStep.interval;
  let curStep = parseInt(cfg.tickStep.step, 10);
  if (!isFinite(curStep)) curStep = 1;
  let startIdx = 0;
  for (let i = 0; i < CFS_TICK_STEP_LADDER.length; i++) {
    if (CFS_TICK_STEP_LADDER[i][0] === curInterval && CFS_TICK_STEP_LADDER[i][1] === curStep) {
      startIdx = i;
      break;
    }
  }
  for (let i = startIdx + 1; i < CFS_TICK_STEP_LADDER.length; i++) {
    const iv = CFS_TICK_STEP_LADDER[i][0], st = CFS_TICK_STEP_LADDER[i][1];
    const candidate = { interval: iv, step: st };
    if (countCalendarTicksInRange(minDate, maxDate, candidate, null) < effectiveMin) continue;
    return {
      format: formatForStep(iv, st)[0],
      tickCount: cfg.tickCount,
      labelAngle: 0,
      description: "Coarsening dropped to (" + iv + " step=" + st + ") for >= " +
                   effectiveMin + " ticks in range",
      tickStep: candidate,
      labelExpr: cfg.labelExpr,
    };
  }
  return cfg;
}

/* Reduce a list of Date objects to everything the ladder needs. The
   engine measures cadence on DE-DUPLICATED dates (a long-format
   multi-line repeats each date once per series, which would drive the
   median inter-sample gap to zero and misfire the intraday branch)
   but counts samples on the raw rows. */
function summarizeDates(dates) {
  let n = 0;
  const uniq = Object.create(null);
  for (const d of dates) {
    if (!d || !isFinite(d.getTime())) continue;
    n++;
    uniq[d.getTime()] = true;
  }
  const times = Object.keys(uniq).map(Number).sort((a, b) => a - b);
  if (!times.length) return { n: 0, times: [], diffsMs: [] };
  const diffs = [];
  for (let i = 1; i < times.length; i++) diffs.push(times[i] - times[i - 1]);
  return {
    n: n,
    times: times,
    min: new Date(times[0]),
    max: new Date(times[times.length - 1]),
    diffsMs: diffs,
  };
}

function determineDateFormatRaw(s, chartWidth, fontSize) {
  if (!s.n) {
    return { format: "%b %y", tickCount: 12, labelAngle: null,
             description: "Show month and year (span 1-3 years)",
             tickStep: null, labelExpr: null };
  }
  const spanMs = s.max.getTime() - s.min.getTime();
  const spanDays = Math.trunc(spanMs / 86400000);
  const spanHours = spanMs / 3600000;
  const spanSeconds = spanMs / 1000;
  const mt = (w, sample) => maxTicksForWidth(w, sample, 0, fontSize);

  // ---- intraday, by inter-sample cadence rather than points-per-day ----
  if (spanHours <= 5 * 24 && s.n >= 2) {
    const medDiffSec = s.diffsMs.length ? cfsMedian(s.diffsMs) / 1000 : Infinity;
    if (medDiffSec < 20 * 3600) {
      const days = Object.create(null);
      for (const t of s.times) {
        const d = new Date(t);
        days[d.getUTCFullYear() + "-" + d.getUTCMonth() + "-" + d.getUTCDate()] = true;
      }
      const singleSession = Object.keys(days).length === 1;
      const labelExpr = singleSession
        ? "(datum.index === 0) ? timeFormat(datum.value, '%d %b') " +
          ": timeFormat(datum.value, '%H:%M')"
        : "(hours(datum.value) === 0 && minutes(datum.value) === 0 " +
          "&& seconds(datum.value) === 0) ? timeFormat(datum.value, '%d %b') " +
          ": timeFormat(datum.value, '%H:%M')";
      const sampleLabel = singleSession ? "May 27" : "Apr 28";
      const shape = strideS => (strideS >= 86400)
        ? { format: "%d %b", labelExpr: null, sample: "06 Mar" }
        : { format: null, labelExpr: labelExpr, sample: sampleLabel };

      let stride;
      if (spanSeconds <= 60) stride = 10;
      else if (spanSeconds <= 300) stride = 30;
      else if (spanHours <= 0.5) stride = 300;
      else if (spanHours <= 1) stride = 600;
      else if (spanHours <= 2) stride = 900;
      else if (spanHours <= 3) stride = 1800;
      else if (spanHours <= 7) stride = 3600;
      else if (spanHours <= 14) stride = 7200;
      else if (spanHours <= 24) stride = 10800;
      else if (spanHours <= 48) stride = 21600;
      else if (spanHours <= 72) stride = 43200;
      else stride = 86400;

      const coarsest = CFS_INTRADAY_STRIDES_S[CFS_INTRADAY_STRIDES_S.length - 1];
      let sh = shape(stride);
      let nTicks = Math.max(Math.trunc(spanSeconds / stride) + 1, 2);
      while (nTicks > mt(chartWidth, sh.sample) && stride < coarsest) {
        let next = coarsest;
        for (const c of CFS_INTRADAY_STRIDES_S) { if (c > stride) { next = c; break; } }
        stride = next;
        sh = shape(stride);
        nTicks = Math.max(Math.trunc(spanSeconds / stride) + 1, 2);
      }
      let strideLabel;
      if (stride < 60) strideLabel = stride + "s";
      else if (stride < 3600) strideLabel = Math.trunc(stride / 60) + "min";
      else if (stride < 86400) strideLabel = Math.trunc(stride / 3600) + "h";
      else strideLabel = Math.trunc(stride / 86400) + "d";
      // Intraday axes take a plain integer tickCount: an interval/step
      // hint on this branch compiles but explodes inside vl-convert.
      return { format: sh.format, tickCount: Math.max(nTicks, 2), labelAngle: 0,
               description: "Intraday ticks (every " + strideLabel + ")",
               tickStep: null, labelExpr: sh.labelExpr };
    }
  }

  if (spanDays <= 5) {
    let estimated = Math.max(spanDays, 1);
    let tickStep = null;
    if (estimated > mt(chartWidth, "06 Mar") && estimated > 2) {
      tickStep = { interval: "day", step: 2 };
      estimated = Math.max(Math.trunc(spanDays / 2) + 1, 2);
    }
    return { format: "%d %b", tickCount: tickStep === null ? estimated : null,
             labelAngle: 0, description: "Short span <= 5 days with explicit daily ticks",
             tickStep: tickStep, labelExpr: null };
  }

  const spanYears = spanDays / 365.25;
  const spanMonths = spanDays / 30.44;

  if (spanYears > 10) {
    let stride = spanYears > 50 ? 10 : (spanYears > 15 ? 5 : 2);
    const maxH = mt(chartWidth, "2025");
    let nTicks = Math.max(Math.trunc(spanYears / stride) + 1, 2);
    if (nTicks > maxH) {
      for (const nice of CFS_NICE_YEAR_STEPS) {
        if (nice > stride) {
          stride = nice;
          nTicks = Math.max(Math.trunc(spanYears / stride) + 1, 2);
          if (nTicks <= maxH) break;
        }
      }
    }
    return { format: "%Y", tickCount: null, labelAngle: 0,
             description: "Multi-year ticks (every " + stride + " years)",
             tickStep: { interval: "year", step: stride }, labelExpr: null };
  }

  if (s.n >= 24 && s.diffsMs.length > 0) {
    const medDiffDays = cfsMedian(s.diffsMs.map(ms => Math.trunc(ms / 86400000)));
    if (medDiffDays >= 2 && medDiffDays <= 30 && spanYears <= 10) {
      const c = coarsenMonthStepToFit(spanMonths, chartWidth,
                                      stepForTarget(spanMonths, 5), fontSize);
      return { format: c.fmt, tickCount: null, labelAngle: 0,
               description: "Sub-annual ticks (every " + c.step + " months)",
               tickStep: temporalTickStep("month", c.step), labelExpr: null };
    }
  }

  if (spanYears >= 3) {
    const initial = spanYears >= 8 ? 24 : (spanYears >= 4 ? 12 : 6);
    const c = coarsenMonthStepToFit(spanMonths, chartWidth, initial, fontSize);
    return { format: c.fmt, tickCount: null, labelAngle: 0,
             description: "Year-month ticks (every " + c.step + " months)",
             tickStep: temporalTickStep("month", c.step), labelExpr: null };
  }

  if (spanYears > 1) {
    const initial = spanYears <= 2.5 ? 6 : 12;
    const c = coarsenMonthStepToFit(spanMonths, chartWidth, initial, fontSize);
    return { format: c.fmt, tickCount: null, labelAngle: 0,
             description: "Semi-annual to annual ticks (every " + c.step + " months)",
             tickStep: temporalTickStep("month", c.step), labelExpr: null };
  }

  if (spanMonths > 6) {
    // Never bump to semi-annual here: a calendar-aligned 6-month step on
    // a 9-month span lands on at most one boundary inside the range.
    const nTicks = Math.max(Math.trunc(spanMonths / 3) + 1, 2);
    if (nTicks > mt(chartWidth, "Mar 25")) {
      const c = coarsenMonthStepToFit(spanMonths, chartWidth, 6, fontSize);
      return { format: c.fmt, tickCount: null, labelAngle: 0,
               description: "Coarsened quarterly ticks (every " + c.step + " months)",
               tickStep: temporalTickStep("month", c.step), labelExpr: null };
    }
    return { format: "%b %y", tickCount: null, labelAngle: 0,
             description: "Quarterly ticks (every 3 months)",
             tickStep: temporalTickStep("month", 3), labelExpr: null };
  }

  if (spanMonths > 1) {
    const c = coarsenMonthStepToFit(spanMonths, chartWidth, 1, fontSize);
    return { format: c.fmt, tickCount: null, labelAngle: 0,
             description: "Monthly ticks (every " + c.step + " month)",
             tickStep: temporalTickStep("month", c.step), labelExpr: null };
  }

  if (spanDays > 14) {
    let stepDays = 7;
    const nTicks = Math.max(Math.trunc(spanDays / stepDays) + 1, 2);
    if (nTicks > mt(chartWidth, "06 Mar")) stepDays = 14;
    return { format: "%d %b", tickCount: null, labelAngle: 0,
             description: "Weekly ticks (every " + stepDays + " days)",
             tickStep: { interval: "week", step: Math.max(Math.trunc(stepDays / 7), 1) },
             labelExpr: null };
  }

  const desiredMax = Math.max(Math.min(Math.trunc(spanDays), 7), 4);
  return { format: "%d %b",
           tickCount: Math.max(Math.min(desiredMax, mt(chartWidth, "06 Mar")), 2),
           labelAngle: 0, description: "Short date (span < 2 weeks)",
           tickStep: null, labelExpr: null };
}

function determineDateFormat(dates, chartWidth, fontSize) {
  const s = summarizeDates(dates);
  const cfg = determineDateFormatRaw(s, chartWidth, fontSize);
  if (!s.n) return cfg;
  return ensureMinTemporalTicks(cfg, s.min, s.max, s.n);
}

/* ---- port of _stagger_lvl_text_y ----
   Collision detection happens in pixel space, so the gap depends on
   the y domain and the plot height as well as the font. Using a fixed
   data-unit gap looks right at one window and wrong at the next. */
function staggerLvlTextY(rows, yField, fontSize, yDomain, chartHeightPx) {
  if (!rows.length) return;
  const yLo = Number(yDomain[0]), yHi = Number(yDomain[1]);
  if (!(yHi > yLo)) {
    for (const r of rows) r._y_text = cfsNum(r[yField]);
    return;
  }
  const yRange = yHi - yLo;
  const lineHeightPx = Math.max(1.0, fontSize * 1.4);
  const lineHeightY = lineHeightPx / Math.max(chartHeightPx, 1) * yRange;

  const order = rows.map((r, i) => i);
  order.sort((a, b) => {
    const d = (cfsNum(rows[b][yField]) || 0) - (cfsNum(rows[a][yField]) || 0);
    return d !== 0 ? d : a - b;
  });
  const vals = order.map(i => cfsNum(rows[i][yField]) || 0);
  const n = vals.length;

  for (let i = 1; i < n; i++) {
    if (vals[i - 1] - vals[i] < lineHeightY) vals[i] = vals[i - 1] - lineHeightY;
  }
  if (vals[n - 1] < yLo) {
    vals[n - 1] = yLo + lineHeightY * 0.5;
    for (let i = n - 2; i >= 0; i--) {
      if (vals[i] - vals[i + 1] < lineHeightY) vals[i] = vals[i + 1] + lineHeightY;
    }
  }
  if (vals[0] > yHi) {
    vals[0] = yHi - lineHeightY * 0.5;
    for (let i = 1; i < n; i++) {
      const minGap = (i < n - 1) ? lineHeightY : lineHeightY * 0.5;
      if (vals[i - 1] - vals[i] < minGap) vals[i] = vals[i - 1] - minGap;
    }
  }
  for (let k = 0; k < n; k++) rows[order[k]]._y_text = vals[k];
}

/* ============================================================
   AXIS HELPERS
   Update encoding.{channel}.axis.{prop} (overriding any producer-set
   value) AND config.{configKey}.{prop} (so the default applies if a
   panel has no encoding-level override).

   `scopeNode` narrows both halves to one panel of a composite. The
   config half is then skipped entirely rather than narrowed, because
   config.axisX / config.axisY are document-wide by construction --
   writing one while the user is editing a single panel of a 6-pack
   restyles its five siblings. Encoding-level writes outrank config,
   so a scoped edit still wins wherever it lands.
   ============================================================ */
function setBothAxisProperty(spec, channel, configKey, prop, value, scopeNode) {
  setAxisEncodingProperty(scopeNode || spec, channel, prop, value);
  if (!scopeNode) setAxisConfigProperty(spec, configKey, prop, value);
}

function setAxisEncodingProperty(spec, channel, prop, value) {
  walkEncoding(spec, channel, enc => {
    // axis === null means producer hid the axis entirely; respect that.
    if (enc.axis === null) return;
    if (typeof enc.axis !== "object" || enc.axis === undefined) enc.axis = {};
    if (value === undefined || value === null || value === "") {
      delete enc.axis[prop];
    } else {
      enc.axis[prop] = value;
    }
  });
}

function setAxisConfigProperty(spec, configKey, prop, value) {
  if (value === undefined || value === null || value === "") {
    setPath(spec, "config." + configKey + "." + prop, undefined);
  } else {
    setPath(spec, "config." + configKey + "." + prop, value);
  }
}

/* ============================================================
   TIME WINDOW

   Narrowing a time axis is a six-step repair, not a domain write.
   Clamping x alone leaves the y range spanning the whole series, the
   tick stride tuned for a span that is no longer shown, and the
   end-of-line labels stranded at the original max(x) -- which vega
   lays out anyway, inflating the canvas by two thirds on a fifteen
   year chart.

   The mechanism is a CLAMP and never a transform filter. Filtering
   truncates the data tab and the CSV export, deletes the end-of-line
   rows outright, and -- decisively -- makes the operation lossy, so
   widening a window afterwards cannot recover what narrowing threw
   away. Clamping keeps whole data in the spec, which is what lets
   every window recompute from scratch and makes drag-to-pan safe.
   ============================================================ */

const CFS_DATA_MARKS = ["line", "area", "bar", "point", "circle", "square",
                        "rect", "arc", "tick", "trail"];
const CFS_LVL_FIELD = "_y_text";

/* Where does this node sit in the whole spec, and what data does it
   inherit from above? Both matter when the caller handed us a panel
   rather than the root: identity keys have to be absolute so two
   panels with inline data at the same relative path do not collide,
   and a spec that binds its data above the panel would otherwise look
   like a panel with no data at all. */
function locateNode(target) {
  let out = { path: "spec", rows: null, key: null };
  if (target === currentSpec) return out;
  (function walk(node, path, rows, key) {
    if (!node || typeof node !== "object") return false;
    const d = node.data;
    if (d) {
      if (d.name && currentSpec.datasets && Array.isArray(currentSpec.datasets[d.name])) {
        rows = currentSpec.datasets[d.name]; key = "ds:" + d.name;
      } else if (Array.isArray(d.values)) {
        rows = d.values; key = "at:" + path;
      }
    }
    if (node === target) { out = { path: path, rows: rows, key: key }; return true; }
    for (const k of ["layer", "concat", "hconcat", "vconcat"]) {
      if (!Array.isArray(node[k])) continue;
      for (let i = 0; i < node[k].length; i++) {
        if (walk(node[k][i], path + "." + k + "[" + i + "]", rows, key)) return true;
      }
    }
    if (node.spec) return walk(node.spec, path + ".spec", rows, key);
    return false;
  })(currentSpec, "spec", null, null);
  return out;
}

/* Depth-first walk yielding every mark node together with the dataset
   it draws from and a stable identity for that dataset. Data is
   inherited: the producer binds an annotation's rows on the group node
   and lets the rule and its label sublayers read them from there, so a
   walk that only reads node.data misses both. */
function walkDataNodes(root, fn) {
  const seed = locateNode(root);
  (function walk(node, path, rows, key) {
    if (!node || typeof node !== "object") return;
    const d = node.data;
    if (d) {
      if (d.name && currentSpec.datasets && Array.isArray(currentSpec.datasets[d.name])) {
        rows = currentSpec.datasets[d.name]; key = "ds:" + d.name;
      } else if (Array.isArray(d.values)) {
        rows = d.values; key = "at:" + path;
      }
    }
    if (node.mark) fn(node, rows, key);
    for (const k of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(node[k])) {
        node[k].forEach((c, i) => walk(c, path + "." + k + "[" + i + "]", rows, key));
      }
    }
    if (node.spec) walk(node.spec, path + ".spec", rows, key);
  })(root, seed.path, seed.rows, seed.key);
}

/* usermeta is vega-lite's sanctioned home for editor state -- the
   compiler ignores it -- and is already where in-place renames and
   per-series line styling live. */
function windowStore() {
  if (!currentSpec.usermeta) currentSpec.usermeta = {};
  const m = currentSpec.usermeta;
  if (!m.cfsWindow) m.cfsWindow = {};
  if (!m.cfsWindow.anchors) m.cfsWindow.anchors = {};
  return m.cfsWindow;
}

function encFieldOf(node, channel) {
  const e = node.encoding && node.encoding[channel];
  return (e && !Array.isArray(e) && e.field !== undefined) ? e.field : null;
}

/* The end-of-line label layer, identified by the derived y field the
   engine writes for it. It is the one text layer deliberately drawn
   outside the plot rect (align left, positive dx), so it is excluded
   from clipping and relocated instead. */
function isLvlNode(node) {
  return markTypeOf(node) === "text" && encFieldOf(node, "y") === CFS_LVL_FIELD;
}

/* What is this panel actually plotting? Returns null when the panel
   has no temporal x, which is how a bar-by-category or a scatter
   opts out of the whole feature. */
function temporalPlotInfo(root) {
  let xField = null, yField = null, colorField = null;
  let width = null, height = null;
  const seriesNodes = [];
  walkDataNodes(root, (node, rows) => {
    const xe = node.encoding && node.encoding.x;
    if (!xe || Array.isArray(xe) || xe.type !== "temporal" || !xe.field) return;
    if (CFS_DATA_MARKS.indexOf(markTypeOf(node)) < 0) return;
    if (!rows || !rows.length) return;
    if (xField === null) xField = xe.field;
    if (xe.field !== xField) return;
    const yf = encFieldOf(node, "y");
    if (yf && yf !== CFS_LVL_FIELD && yField === null) yField = yf;
    const cf = encFieldOf(node, "color");
    if (cf && colorField === null) colorField = cf;
    seriesNodes.push({ node: node, rows: rows });
  });
  if (xField === null || !seriesNodes.length) return null;
  width = walkExtractSize(root, "width");
  height = walkExtractSize(root, "height");
  return {
    xField: xField, yField: yField, colorField: colorField,
    seriesNodes: seriesNodes,
    width: (typeof width === "number") ? width : 600,
    height: (typeof height === "number") ? height : 350,
  };
}

/* Full extent of the plotted data, ignoring any window in force --
   the anchor "Max" returns to and the ceiling a drag cannot pan past. */
function dataExtent(info) {
  let lo = null, hi = null;
  for (const s of info.seriesNodes) {
    for (const r of s.rows) {
      const d = parseSpecDate(r[info.xField]);
      if (!d) continue;
      const t = d.getTime();
      if (lo === null || t < lo) lo = t;
      if (hi === null || t > hi) hi = t;
    }
  }
  return (lo === null) ? null : [new Date(lo), new Date(hi)];
}

/* Typical spacing between samples, which is what decides whether a short
   preset could hold any data at all. Median rather than mean so a single
   multi-year gap in an otherwise daily series does not read as the
   cadence. */
function dataCadence(info) {
  const dates = [];
  for (const s of info.seriesNodes) {
    for (const r of s.rows) {
      const d = parseSpecDate(r[info.xField]);
      if (d) dates.push(d);
    }
  }
  const sum = summarizeDates(dates);
  return sum.diffsMs.length ? cfsMedian(sum.diffsMs) : null;
}

function currentWindow(root, info) {
  let dom = null;
  walkEncoding(root, "x", enc => {
    if (dom) return;
    if (enc && enc.scale && Array.isArray(enc.scale.domain) && enc.scale.domain.length === 2) {
      const a = parseSpecDate(enc.scale.domain[0]), b = parseSpecDate(enc.scale.domain[1]);
      if (a && b) dom = [a, b];
    }
  });
  return dom || dataExtent(info);
}

/* The window the studio wrote, or null when the axis is still on auto.
   currentWindow cannot answer this -- it reports the data extent for an
   unclamped axis, which is the right answer for "what span is on screen"
   and the wrong one for "did anyone clamp this". */
function explicitXWindow(root, info) {
  let win = null;
  walkEncoding(root, "x", enc => {
    if (win || !enc || enc.type !== "temporal" || !enc.scale ||
        !Array.isArray(enc.scale.domain) || enc.scale.domain.length !== 2) return;
    const a = parseSpecDate(enc.scale.domain[0]);
    const b = parseSpecDate(enc.scale.domain[1]);
    if (a && b) win = [a, b];
  });
  return win;
}

/* A tick choice is calibrated against a canvas width, and only the
   calendar-boundary branches let vega-lite re-fit afterwards. The
   intraday branch pins an explicit count, so the nine ticks that suit
   1400px still ask for nine at 200px and print on top of each other.
   Re-run the choice for every panel the studio has clamped.

   Panels the studio has NOT clamped keep the producer's ticks: their
   span is whatever vega-lite infers, so there is nothing here to
   calibrate against and the engine already chose for this data. */
function retuneWindowedTicks(root) {
  let touched = 0;
  for (const p of temporalPanels(root || currentSpec)) {
    const win = explicitXWindow(p.node, p.info);
    if (!win) continue;
    const inWindow = rowsInWindow(p.info, win[0], win[1]);
    if (!inWindow.length) continue;
    const cfg = determineDateFormat(inWindow.map(e => e.date), p.info.width,
                                    axisLabelFontSize());
    applyDateFormatConfig(p.node, p.info.xField, cfg);
    touched++;
  }
  return touched;
}

/* What the viewer is actually looking at, end by end. Differs from
   currentWindow in that a domain with only one end set resolves the OTHER
   end against the data rather than discarding the pair -- which is the
   state the Advanced-controls knobs produce, since they write one bound
   per edit. currentWindow's all-or-nothing fallback would read a
   half-set pair as the full extent and clobber the bound just typed. */
function effectiveXWindow(root, info) {
  const extent = dataExtent(info);
  if (!extent) return null;
  let lo = null, hi = null;
  walkEncoding(root, "x", enc => {
    if (!enc || enc.type !== "temporal" || !enc.scale ||
        !Array.isArray(enc.scale.domain)) return;
    if (lo === null) lo = parseSpecDate(enc.scale.domain[0]);
    if (hi === null) hi = parseSpecDate(enc.scale.domain[1]);
  });
  return [lo || extent[0], hi || extent[1]];
}

/* Rows of the primary series that fall inside the window, with their
   dates already parsed. Everything downstream measures from this. */
function rowsInWindow(info, lo, hi) {
  const out = [];
  const loT = lo.getTime(), hiT = hi.getTime();
  for (const s of info.seriesNodes) {
    for (const r of s.rows) {
      const d = parseSpecDate(r[info.xField]);
      if (!d) continue;
      const t = d.getTime();
      if (t < loT || t > hiT) continue;
      out.push({ row: r, date: d });
    }
  }
  return out;
}

/* The six steps. Returns a report the caller turns into an undo label
   and a toast; the parity harness asserts on it directly. */
function applyTimeWindow(root, lo, hi, opts) {
  opts = opts || {};
  const info = opts.info || temporalPlotInfo(root);
  if (!info) return { ok: false, reason: "no temporal x axis in this panel" };

  const inWindow = rowsInWindow(info, lo, hi);
  if (!inWindow.length) return { ok: false, reason: "no data inside that window" };

  const report = { ok: true, window: [formatSpecDate(lo), formatSpecDate(hi)] };

  // 1. clamp every temporal x encoding in scope, including the ones on
  //    the annotation and label layers -- a layer left on an unclamped
  //    scale is drawn against a different x mapping from its siblings.
  let clamped = 0;
  walkEncoding(root, "x", enc => {
    if (!enc || enc.type !== "temporal" || enc.field !== info.xField) return;
    if (!enc.scale) enc.scale = {};
    enc.scale.domain = [formatSpecDate(lo, true), formatSpecDate(hi, true)];
    clamped++;
  });
  report.clamped = clamped;

  // 2. clip. Everything except the end-of-line labels, which live in the
  //    right margin by design and are re-anchored in step 6 instead.
  let clipped = 0;
  walkDataNodes(root, node => {
    if (isTextPanelNode(node) || isLvlNode(node)) return;
    setMarkProp(node, "clip", true);
    clipped++;
  });
  report.clipped = clipped;

  // 3. refit the range from the windowed rows of the DATA marks only.
  //    Reading every node instead would pull in the annotation label
  //    rows, which carry the pre-window maximum and would reproduce
  //    the old domain almost exactly -- a bug that looks like a no-op.
  let yDomain = null;
  if (info.yField && nonLinearYScale(root, info.yField)) {
    // The engine's domain arithmetic is linear throughout -- additive
    // padding, and a floor that snaps to zero, which no log axis can
    // even represent. Refitting a log scale with it would produce a
    // domain vega cannot draw, so the range is left for vega to fit
    // from the clamped data and the caller is told why.
    report.yNote = "y scale is not linear; range left for vega to fit";
  } else if (info.yField) {
    const vals = [];
    for (const e of inWindow) {
      const v = cfsNum(e.row[info.yField]);
      if (v !== null) vals.push(v);
    }
    if (vals.length) {
      yDomain = calcYAxisDomain(vals, { includeZero: !!opts.includeZero });
      setYDomain(root, info.yField, yDomain);
      report.yDomain = yDomain;
    }
  }

  // 4. re-anchor annotation furniture. A vline's LABEL is parked at the
  //    data maximum by the producer, so it floats off the top once the
  //    range refits; a hline's VALUE is a coordinate the user chose and
  //    must not move. Matching on the old maximum separates them without
  //    having to guess from the layer shape.
  report.rebased = rebaseAnnotationFurniture(root, info, inWindow);

  // 5. retune the ticks for the span now on screen.
  const cfg = determineDateFormat(inWindow.map(e => e.date), info.width,
                                  axisLabelFontSize());
  applyDateFormatConfig(root, info.xField, cfg);
  report.ticks = { format: cfg.format, tickCount: cfg.tickCount,
                   tickStep: cfg.tickStep, description: cfg.description };

  // 6. move the end-of-line labels to the last point each series still
  //    has inside the window, then re-run the collision pass against the
  //    refitted domain.
  report.labels = relocateEndlineLabels(root, info, inWindow, yDomain);

  return report;
}

function setYDomain(root, yField, domain) {
  walkEncoding(root, "y", enc => {
    if (!enc || enc.type !== "quantitative") return;
    if (enc.field !== yField && enc.field !== CFS_LVL_FIELD) return;
    if (enc.scale && enc.scale.type && enc.scale.type !== "linear") return;
    if (!enc.scale) enc.scale = {};
    enc.scale.domain = domain.slice();
  });
}

function nonLinearYScale(root, yField) {
  return !!yScaleTypeOf(root, yField);
}

/* The non-linear scale type on this y field, or null when it is linear
   (explicitly or by omission). */
function yScaleTypeOf(root, yField) {
  let type = null;
  walkEncoding(root, "y", enc => {
    if (!enc || enc.field !== yField) return;
    if (enc.scale && enc.scale.type && enc.scale.type !== "linear") {
      type = enc.scale.type;
    }
  });
  return type;
}

/* config.axis.labelFontSize is what the tick-width estimate has to
   assume; the GS skin sets 18 and the engine's ladder is calibrated
   to it. */
function axisLabelFontSize() {
  const v = getPath(currentSpec, "config.axisX.labelFontSize") ||
            getPath(currentSpec, "config.axis.labelFontSize");
  return (typeof v === "number" && v > 0) ? v : CFS_AXIS_LABEL_FONT;
}

/* Only a vline's LABEL is furniture. Every other annotation that emits
   an (x, y) label row -- point label, callout, arrow, segment, point
   highlight -- is sitting on a coordinate the caller chose, and moving
   it would relocate the annotation itself. What separates them is that
   the producer parks the vline label at the data maximum and nothing
   else does, so the test is equality with that maximum.

   The pristine value has to be remembered, not re-read: after the first
   window the row no longer holds the maximum, so a second pass -- which
   is every frame of a drag -- would stop recognising it and leave the
   label behind at the previous window's anchor. */
function rebaseAnnotationFurniture(root, info, inWindow) {
  if (!info.yField) return 0;
  let oldMax = null, newMax = null;
  for (const s of info.seriesNodes) {
    for (const r of s.rows) {
      const v = cfsNum(r[info.yField]);
      if (v !== null && (oldMax === null || v > oldMax)) oldMax = v;
    }
  }
  for (const e of inWindow) {
    const v = cfsNum(e.row[info.yField]);
    if (v !== null && (newMax === null || v > newMax)) newMax = v;
  }
  if (oldMax === null || newMax === null) return 0;
  const eps = Math.max(Math.abs(oldMax), 1) * 1e-9;

  const anchors = windowStore().anchors;
  let touched = 0;
  const seen = Object.create(null);
  walkDataNodes(root, (node, rows, key) => {
    if (markTypeOf(node) !== "text" || isLvlNode(node) || !rows || !key) return;
    if (seen[key]) return;
    seen[key] = true;
    let pristine = anchors[key];
    if (!Array.isArray(pristine) || pristine.length !== rows.length) {
      pristine = rows.map(r => {
        const v = cfsNum(r[info.yField]);
        return (v === null || r[info.xField] === undefined) ? null : v;
      });
      anchors[key] = pristine;
    }
    rows.forEach((r, i) => {
      const p = pristine[i];
      if (p === null || p === undefined) return;
      if (Math.abs(p - oldMax) > eps) return;
      r[info.yField] = newMax;
      touched++;
    });
  });
  return touched;
}

function applyDateFormatConfig(root, xField, cfg) {
  walkEncoding(root, "x", enc => {
    if (!enc || enc.type !== "temporal" || enc.field !== xField) return;
    if (enc.axis === null) return;
    if (typeof enc.axis !== "object" || enc.axis === undefined) enc.axis = {};
    if (cfg.format) { enc.axis.format = cfg.format; enc.axis.formatType = "time"; }
    else delete enc.axis.format;
    if (cfg.labelExpr) enc.axis.labelExpr = cfg.labelExpr;
    else delete enc.axis.labelExpr;
    // tickCount carries either the soft integer hint or the explicit
    // interval/step; they are mutually exclusive on one axis.
    if (cfg.tickStep) enc.axis.tickCount = cfg.tickStep;
    else if (typeof cfg.tickCount === "number") enc.axis.tickCount = cfg.tickCount;
    else delete enc.axis.tickCount;
  });
}

/* End-of-line labels are a separate text layer the producer pins at
   max(x) with a positive dx, which is why an unrepaired window leaves
   them stranded off the right of the plot and vega grows the canvas by
   two thirds to lay them out.

   Rebuilt from a remembered pristine copy rather than edited in place.
   A series that falls out of the window loses its label -- there is no
   line end left to label -- and an in-place edit would have no way to
   bring it back when the window widens again, which is every drag that
   reverses direction. */
function relocateEndlineLabels(root, info, inWindow, yDomain) {
  const out = { moved: 0, dropped: 0 };
  const targets = [];
  const seen = Object.create(null);
  walkDataNodes(root, (node, rows, key) => {
    if (!isLvlNode(node) || !rows || !key || seen[key]) return;
    seen[key] = true;
    targets.push({ node: node, rows: rows, key: key });
  });
  if (!targets.length) return out;

  const last = Object.create(null);
  for (const e of inWindow) {
    const k = info.colorField ? String(e.row[info.colorField]) : "";
    const prev = last[k];
    if (!prev || e.date.getTime() > prev.date.getTime()) last[k] = e;
  }

  const store = windowStore();
  if (!store.labels) store.labels = {};
  const domain = yDomain || currentYDomain(root, info.yField);

  for (const t of targets) {
    let pristine = store.labels[t.key];
    if (!Array.isArray(pristine)) {
      pristine = deepClone(t.rows);
      store.labels[t.key] = pristine;
    }
    const rebuilt = [];
    for (const p of pristine) {
      const k = info.colorField ? String(p[info.colorField]) : "";
      const anchor = last[k];
      if (!anchor) { out.dropped++; continue; }
      const r = Object.assign({}, p);
      r[info.xField] = anchor.row[info.xField];
      if (info.yField) r[info.yField] = anchor.row[info.yField];
      rebuilt.push(r);
      out.moved++;
    }
    if (domain && info.yField) {
      const fs = (typeof t.node.mark === "object" && t.node.mark.fontSize) || 11;
      staggerLvlTextY(rebuilt, info.yField, fs, domain, info.height);
    }
    // In place, because a shared label dataset is shared by the text
    // layer and its dot layer, and both want the same relocation.
    t.rows.length = 0;
    for (const r of rebuilt) t.rows.push(r);
  }
  return out;
}

function currentYDomain(root, yField) {
  let dom = null;
  walkEncoding(root, "y", enc => {
    if (dom) return;
    if (enc && enc.field === yField && enc.scale && Array.isArray(enc.scale.domain)) {
      dom = enc.scale.domain;
    }
  });
  return dom;
}

/* Undo restores a whole-spec snapshot, so nothing here has to be
   individually reversible -- but "Max" still has to mean the data's
   own extent rather than "whatever the producer emitted", because by
   then the producer's domain has been overwritten. */
function clearTimeWindow(root, info) {
  const extent = dataExtent(info);
  if (!extent) return { ok: false, reason: "no dated rows in this panel" };
  return applyTimeWindow(root, extent[0], extent[1], { info: info });
}

/* Range-only edit: keep the window, recompute the y domain. */
function refitYRange(root, opts) {
  opts = opts || {};
  const info = opts.info || temporalPlotInfo(root);
  if (!info || !info.yField) return { ok: false, reason: "no quantitative y axis here" };
  const win = currentWindow(root, info);
  if (!win) return { ok: false, reason: "no dated rows in this panel" };
  const inWindow = rowsInWindow(info, win[0], win[1]);
  if (!inWindow.length) return { ok: false, reason: "no data inside the current window" };

  if (nonLinearYScale(root, info.yField)) {
    return { ok: false, reason: "this y axis is not linear, so a linear refit would break it" };
  }
  const vals = [];
  for (const e of inWindow) {
    const v = cfsNum(e.row[info.yField]);
    if (v !== null) vals.push(v);
  }
  if (!vals.length) return { ok: false, reason: "no numeric values inside the window" };

  const domain = calcYAxisDomain(vals, { includeZero: !!opts.includeZero });
  setYDomain(root, info.yField, domain);
  // The labels are spaced in pixel space, so a range change moves them
  // even though the window did not.
  relocateEndlineLabels(root, info, inWindow, domain);
  return { ok: true, yDomain: domain };
}

/* Named windows. Anchored on the data's own right edge rather than
   today's date: a chart of data that ends in 2019 should answer "1Y"
   with its own last year, not with an empty window. */
const CFS_WINDOW_PRESETS = [
  { label: "1H", hours: 1 },
  { label: "4H", hours: 4 },
  { label: "1D", hours: 24 },
  { label: "5D", hours: 120 },
  { label: "1M", months: 1 },
  { label: "3M", months: 3 },
  { label: "6M", months: 6 },
  { label: "YTD", ytd: true },
  { label: "1Y", months: 12 },
  { label: "3Y", months: 36 },
  { label: "5Y", months: 60 },
  { label: "10Y", months: 120 },
  { label: "Max", max: true },
];

function presetWindow(preset, extent) {
  const hi = extent[1];
  if (preset.max) return [extent[0], hi];
  if (preset.ytd) {
    const start = new Date(Date.UTC(hi.getUTCFullYear(), 0, 1));
    return [start < extent[0] ? extent[0] : start, hi];
  }
  if (preset.hours) {
    const start = new Date(hi.getTime() - preset.hours * 36e5);
    return [start < extent[0] ? extent[0] : start, hi];
  }
  // Calendar months, not 30-day multiples: "3M" back from 31 May has to
  // land on 28 February, which is what pandas' DateOffset does too.
  const start = new Date(Date.UTC(
    hi.getUTCFullYear(), hi.getUTCMonth() - preset.months, hi.getUTCDate(),
    hi.getUTCHours(), hi.getUTCMinutes(), hi.getUTCSeconds()));
  return [start < extent[0] ? extent[0] : start, hi];
}

/* Only the presets that actually narrow THIS chart to something with data
   in it. A six-hour session offered 1M through 10Y would be eight chips
   that all mean Max; a fifteen-year quarterly series offered 1H would be
   a chip that can only ever report an empty window. Max always stays,
   because it is how a narrowed chart gets back. */
function windowPresetsFor(extent, cadenceMs) {
  if (!extent) return [];
  const span = extent[1].getTime() - extent[0].getTime();
  const floor = (typeof cadenceMs === "number" && cadenceMs > 0)
    ? cadenceMs * CFS_MIN_PRESET_SAMPLES : 0;
  const out = [];
  for (const p of CFS_WINDOW_PRESETS) {
    if (p.max) { out.push(p); continue; }
    const w = presetWindow(p, extent);
    // Indistinguishable from Max.
    if (w[0].getTime() - extent[0].getTime() <= Math.max(6e4, span * 0.02)) continue;
    // Too narrow to hold a readable number of samples.
    if (w[1].getTime() - w[0].getTime() < floor) continue;
    out.push(p);
  }
  return out;
}

/* Below this many samples a window is a line with nothing to read. */
const CFS_MIN_PRESET_SAMPLES = 3;

/* Which preset, if any, describes the window in force. Drives the
   highlighted chip so the menu reports state instead of just offering
   actions. */
function activePresetLabel(root, info) {
  const extent = dataExtent(info);
  const win = currentWindow(root, info);
  if (!extent || !win) return null;
  // Wall-clock presets rarely coincide exactly with a sample, so allow a
  // slice of the span -- but never so much that neighbouring presets on a
  // short intraday chart both claim the same window.
  const span = extent[1].getTime() - extent[0].getTime();
  const tol = Math.min(36e5, Math.max(6e4, span * 0.01));
  for (const p of CFS_WINDOW_PRESETS) {
    const w = presetWindow(p, extent);
    if (Math.abs(w[0].getTime() - win[0].getTime()) < tol &&
        Math.abs(w[1].getTime() - win[1].getTime()) < tol) return p.label;
  }
  return null;
}

/* ============================================================
   KNOB APPLICATION
   ============================================================ */
function applyKnob(knob, value) {
  if (knob.apply) {
    const fn = APPLY_FUNCTIONS[knob.apply];
    if (!fn) {
      console.warn("Unknown apply function:", knob.apply);
      return;
    }
    fn(currentSpec, value, knob.applyArgs || []);
  } else if (knob.path) {
    setPath(currentSpec, knob.path, value);
  }
}

function onKnobChange(knob, value) {
  pushUndo(knob.label || knob.name);
  currentKnobValues[knob.name] = value;
  overrides[knob.name] = value;
  applyKnob(knob, value);
  if (knob.name === "width" || knob.name === "height") {
    currentDimPreset = "custom";
    const sel = document.getElementById("dimPresetSelect");
    if (sel) sel.value = "custom";
  }
  if (knob.name === "width") retuneWindowedTicks();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
}

/* ============================================================
   UI RENDERING
   ============================================================ */
const ESSENTIALS_GROUP_NAME = "Essentials";
const GROUP_ORDER = [
  "Essentials", "Dimensions", "Title", "X-Axis", "Y-Axis", "Axes", "Legend",
  "Line", "Bar", "Scatter", "Area", "Arc", "Heatmap", "Box", "Bullet", "Waterfall",
  "Colors", "Annotations", "Per-Series Colors", "Layout", "Typography", "Advanced",
];

function initializeKnobs() {
  const container = document.getElementById("knobContainer");
  container.innerHTML = "";

  // Presets card (theme / palette / dimensions)
  const presets = document.createElement("details");
  presets.className = "knob-card";
  presets.open = true;
  const psum = document.createElement("summary");
  psum.textContent = "Presets";
  presets.appendChild(psum);

  presets.appendChild(renderPresetRow("Theme", "themeSelect", THEMES, currentTheme,
    (v) => applyTheme(v, true)));
  presets.appendChild(renderPresetRow("Palette", "paletteSelect", PALETTES, currentPalette,
    (v) => applyPalette(v, true)));
  presets.appendChild(renderPresetRow("Dimensions", "dimPresetSelect", DIM_PRESETS, currentDimPreset,
    (v) => applyDimensionPreset(v, true)));
  container.appendChild(presets);

  // Essentials card (knobs marked essential)
  const essentialKnobs = KNOBS.filter(k => k.essential);
  if (essentialKnobs.length > 0) {
    const essDetails = document.createElement("details");
    essDetails.className = "knob-card";
    essDetails.open = true;
    const summary = document.createElement("summary");
    summary.textContent = "Essentials";
    essDetails.appendChild(summary);
    for (const k of essentialKnobs) essDetails.appendChild(renderKnob(k));
    container.appendChild(essDetails);
  }

  // One card per knob group (all open by default in the grid)
  const groups = {};
  for (const k of KNOBS) {
    const g = k.group || "Other";
    if (!groups[g]) groups[g] = [];
    groups[g].push(k);
  }

  const sortedGroups = Object.keys(groups).sort((a, b) => {
    const ai = GROUP_ORDER.indexOf(a);
    const bi = GROUP_ORDER.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  for (const gname of sortedGroups) {
    if (gname === "Essentials") continue;
    const details = document.createElement("details");
    details.className = "knob-card";
    details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = gname;
    details.appendChild(summary);
    for (const k of groups[gname]) details.appendChild(renderKnob(k));
    container.appendChild(details);
  }
}

function renderPresetRow(label, id, options, current, onChange) {
  const wrap = document.createElement("div");
  wrap.className = "knob";
  const lbl = document.createElement("label");
  lbl.textContent = label;
  wrap.appendChild(lbl);
  const sel = document.createElement("select");
  sel.id = id;
  for (const [name, obj] of Object.entries(options)) {
    const o = document.createElement("option");
    o.value = name;
    o.textContent = obj.label || name;
    sel.appendChild(o);
  }
  sel.value = current;
  sel.onchange = () => onChange(sel.value);
  wrap.appendChild(sel);
  const empty = document.createElement("span");
  empty.className = "val";
  wrap.appendChild(empty);
  return wrap;
}

function renderKnob(knob) {
  const wrap = document.createElement("div");
  wrap.className = "knob";
  wrap.dataset.knobName = knob.name;
  wrap.dataset.knobLabel = (knob.label || "").toLowerCase();
  wrap.dataset.knobGroup = (knob.group || "").toLowerCase();
  wrap.dataset.knobPath = (knob.path || knob.apply || "").toLowerCase();

  const label = document.createElement("label");
  label.textContent = knob.label;
  label.htmlFor = "knob_" + knob.name;
  wrap.appendChild(label);

  let input;
  const valDisplay = document.createElement("span");
  valDisplay.className = "val";
  const val = currentKnobValues[knob.name];

  if (knob.type === "range") {
    input = document.createElement("input");
    input.type = "range";
    input.min = knob.min; input.max = knob.max; input.step = knob.step;
    input.value = (val === undefined) ? knob.default : val;
    valDisplay.textContent = input.value;
    input.oninput = () => {
      const v = parseFloat(input.value);
      valDisplay.textContent = v;
      onKnobChange(knob, v);
    };
  } else if (knob.type === "checkbox") {
    input = document.createElement("input");
    input.type = "checkbox";
    input.checked = (val === undefined) ? !!knob.default : !!val;
    valDisplay.textContent = input.checked ? "on" : "off";
    input.onchange = () => {
      valDisplay.textContent = input.checked ? "on" : "off";
      onKnobChange(knob, input.checked);
    };
  } else if (knob.type === "select") {
    input = document.createElement("select");
    for (const opt of knob.options) {
      const o = document.createElement("option");
      o.value = opt; o.textContent = opt || "(none)";
      input.appendChild(o);
    }
    input.value = (val === undefined) ? knob.default : val;
    valDisplay.textContent = "";
    input.onchange = () => onKnobChange(knob, input.value);
  } else if (knob.type === "color") {
    input = document.createElement("input");
    input.type = "color";
    input.value = normalizeColor((val === undefined) ? knob.default : val);
    valDisplay.textContent = input.value;
    input.oninput = () => {
      valDisplay.textContent = input.value;
      onKnobChange(knob, input.value);
    };
  } else if (knob.type === "text") {
    input = document.createElement("input");
    input.type = "text";
    input.value = (val === undefined) ? (knob.default || "") : (val || "");
    valDisplay.textContent = "";
    input.oninput = () => onKnobChange(knob, input.value);
  } else {
    input = document.createElement("span");
    input.textContent = "(unsupported type: " + knob.type + ")";
  }

  input.id = "knob_" + knob.name;
  wrap.appendChild(input);
  wrap.appendChild(valDisplay);
  return wrap;
}

function filterKnobs(query) {
  const q = (query || "").toLowerCase().trim();
  const rows = document.querySelectorAll(".knob[data-knob-name]");
  for (const r of rows) {
    if (!q) {
      r.classList.remove("hidden");
      continue;
    }
    const hay = r.dataset.knobName + " " + r.dataset.knobLabel + " " + r.dataset.knobGroup + " " + r.dataset.knobPath;
    if (hay.toLowerCase().includes(q)) r.classList.remove("hidden");
    else r.classList.add("hidden");
  }
}

/* ============================================================
   THEME / PALETTE / DIMENSION APPLICATION

   Theme application has TWO modes:
     - default ("merge"): only knobs the theme explicitly defines get
       overwritten. Other spec values (producer-set styling) stay
       untouched. This is the default whenever applyTheme runs from a
       user gesture (theme dropdown, spec sheet apply).
     - force=true: every knob is reset to theme.values[k] OR k.default.
       Used by "Reset to theme" button to fully wipe overrides.
   ============================================================ */
function applyTheme(themeName, record, opts) {
  const theme = THEMES[themeName];
  if (!theme) { setStatus("theme '" + themeName + "' not found"); return; }
  const force = !!(opts && opts.force);
  currentTheme = themeName;
  for (const k of KNOBS) {
    if (theme.values[k.name] === undefined) {
      if (force) {
        // Force-reset: apply the knob's own default (no spec extraction).
        currentKnobValues[k.name] = k.default;
        applyKnob(k, k.default);
      }
      // Otherwise leave producer's spec value alone.
      continue;
    }
    const v = theme.values[k.name];
    currentKnobValues[k.name] = v;
    applyKnob(k, v);
  }
  if (theme.palette) applyPalette(theme.palette, false);
  if (record) overrides.__theme__ = themeName;
  initializeKnobs();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
}

function applyPalette(paletteName, record) {
  const pal = PALETTES[paletteName];
  if (!pal) { setStatus("palette '" + paletteName + "' not found"); return; }
  currentPalette = paletteName;
  if (!currentSpec.config) currentSpec.config = {};
  if (!currentSpec.config.range) currentSpec.config.range = {};
  if (pal.kind === "categorical") {
    currentSpec.config.range.category = pal.colors.slice();
  } else if (pal.kind === "sequential") {
    if (pal.scheme) {
      currentSpec.config.range.heatmap = { scheme: pal.scheme };
      currentSpec.config.range.ramp = { scheme: pal.scheme };
    } else if (pal.colors) {
      currentSpec.config.range.heatmap = pal.colors.slice();
      currentSpec.config.range.ramp = pal.colors.slice();
    }
  } else if (pal.kind === "diverging") {
    if (pal.scheme) currentSpec.config.range.diverging = { scheme: pal.scheme };
    else if (pal.colors) currentSpec.config.range.diverging = pal.colors.slice();
  }
  if (record) overrides.__palette__ = paletteName;
  renderChart();
  updateTextAreas();
  syncSelectors();
}

function applyDimensionPreset(presetName, record) {
  const preset = DIM_PRESETS[presetName];
  if (!preset) { setStatus("dimension preset '" + presetName + "' not found"); return; }
  currentDimPreset = presetName;
  if (presetName !== "custom") {
    currentKnobValues["width"] = preset.width;
    currentKnobValues["height"] = preset.height;
    overrides["width"] = preset.width;
    overrides["height"] = preset.height;
    // walkSetSize handles layered specs where width/height are inside
    // each layer rather than at the spec root.
    walkSetSize(currentSpec, "width",  preset.width);
    walkSetSize(currentSpec, "height", preset.height);
    // Apply typography override if defined for this preset
    const typo = TYPOGRAPHY_OVERRIDES[presetName];
    if (typo) {
      for (const [k, v] of Object.entries(typo)) {
        currentKnobValues[k] = v;
        const knob = KNOBS.find(kk => kk.name === k);
        if (knob) applyKnob(knob, v);
      }
    }
    retuneWindowedTicks();
  }
  if (record) overrides.__dimPreset__ = presetName;
  initializeKnobs();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
  syncSelectors();
}

/* ============================================================
   IN-PLACE TEXT EDITING

   Double-click any text glyph in the chart to edit it where it sits.
   Works because the chart renders with renderer:"svg", so every glyph is
   a real <text> node that Vega has already stamped with enough identity
   to resolve back to an exact vega-lite spec path. Two identity sources,
   both emitted by Vega with no cooperation needed from the producer:

   1. The CSS class chain.
        data marks    "mark-text role-mark <vegaMarkName>"
        guide marks   "mark-text role-{title-text|title-subtitle|
                       axis-title|axis-label|legend-title|legend-label}"
        owning panel  ancestor "mark-group role-scope <scopeName>_group"
      Both name forms encode the spec path in Vega-Lite's deterministic
      naming scheme, so they decode with one tokenizer:
        concat_0_layer_1_layer_2_marks -> spec.vconcat[0].layer[1].layer[2]

   2. node.__data__ -- the live scenegraph item, giving item.datum (which
      data row a data-driven label came from) and, via the axis group,
      item.orient so a dual-axis chart's two y-titles stay distinct.

   Every text surface is editable, but they are not all editable the same
   way, because only some of them are typed strings in the first place:

     free text     title / subtitle / axis + legend titles / caption /
                   side panels / annotation labels. The string sits in the
                   spec; write it directly.
     datum text    direct series ("LVL") labels, whose text is a `_label`
                   column with one row per series. Write that cell.
     value labels  a numeric field plus a d3 format string. Materialise the
                   currently rendered strings into a text column, repoint
                   encoding.text at it, then write the one cell. The label
                   stops tracking the number, so this one warns.
     scale labels  axis ticks and legend entries, generated by the scale.
                   Overridable only through a labelExpr rename map.

   Two ordering rules that are easy to get wrong:

   1. closeInlineEditor() must drop its handle before detaching the node --
      the removal fires `blur` synchronously and blur is wired to the same
      function, so it re-enters. See the comment there.
   2. A producer-authored labelExpr must be preserved as the base of any
      rename map. The engine emits labelExpr for intraday axes, facet-header
      hiding and stride-based tick fitting, so overwriting it would silently
      undo real layout work.

   Edits mutate currentSpec, so they flow into every export path (PNG and
   SVG render from the live view; spec JSON and the standalone snapshot
   serialise currentSpec). They never enter `overrides`, which is a styling
   bundle, not chart content.
   ============================================================ */

const EDITABLE_ROLES = new Set([
  "mark", "title-text", "title-subtitle", "axis-title", "legend-title",
  "axis-label", "legend-label",
]);

/* Column injected when a formatted numeric label is converted to free text. */
const CFS_TEXT_COL = "_cfs_label";

/* ---- undo journal ----
   Each edit pushes a closure that restores the pre-edit state, keyed so that
   re-editing the same surface keeps the FIRST original rather than the
   previous value. Deliberately JS-side rather than serialised into the spec:
   these hold live node references, and a standalone snapshot is by definition
   a new baseline, so there is nothing meaningful to revert to across one. */
let _textJournal = [];

function journalOriginal(key, undo) {
  for (const e of _textJournal) { if (e.key === key) return; }
  _textJournal.push({ key: key, undo: undo });
}

/* Rename maps DO have to survive a snapshot, because rebuilding a labelExpr
   needs both the producer's original expression and every rename applied so
   far. usermeta is vega-lite's sanctioned home for editor state -- the
   compiler ignores it entirely. */
function textEditStore() {
  if (!currentSpec.usermeta) currentSpec.usermeta = {};
  const m = currentSpec.usermeta;
  if (!m.cfsTextEdits) m.cfsTextEdits = { renames: {} };
  if (!m.cfsTextEdits.renames) m.cfsTextEdits.renames = {};
  return m.cfsTextEdits;
}

/* ---- vega mark / scope name -> spec node ---- */
function decodeSpecPath(name) {
  const toks = name.match(/(?:concat|layer|child)_\d+/g) || [];
  let node = currentSpec, path = "spec";
  for (const tok of toks) {
    const sep = tok.lastIndexOf("_");
    const kind = tok.substring(0, sep), i = parseInt(tok.substring(sep + 1), 10);
    if (kind === "concat") {
      const key = concatKeyOf(node);
      if (!key || !node[key][i]) return null;
      node = node[key][i]; path += "." + key + "[" + i + "]";
    } else if (kind === "layer") {
      if (!Array.isArray(node.layer) || !node.layer[i]) return null;
      node = node.layer[i]; path += ".layer[" + i + "]";
    } else {
      if (!node.spec) return null;
      node = node.spec; path += ".spec";
    }
  }
  return { node: node, path: path };
}

/* A panel's title may live on the panel node or, when vega-lite hoisted it
   out of a single-layer view (which is what composite cells are), on one of
   its layers. Return whichever node actually carries it. */
function findTitleOwnerAt(node, path) {
  if (node.title != null) return { node: node, path: path };
  if (Array.isArray(node.layer)) {
    for (let i = 0; i < node.layer.length; i++) {
      if (node.layer[i] && node.layer[i].title != null) {
        return { node: node.layer[i], path: path + ".layer[" + i + "]" };
      }
    }
  }
  return { node: node, path: path };
}

/* Annotation labels are drawn twice -- a halo layer plus the real text
   layer, carrying the identical string. Editing one alone leaves a ghost
   of the old string behind the new one, so collect the whole set. */
function textValueSiblings(markName, hit) {
  const m = markName.match(/^(.*)_layer_(\d+)_marks$/);
  const value = hit.node.encoding.text.value;
  if (!m) return [hit.node];
  const parent = decodeSpecPath(m[1] + "_marks");
  if (!parent || !Array.isArray(parent.node.layer)) return [hit.node];
  const out = [];
  for (const sub of parent.node.layer) {
    const e = sub && sub.encoding && sub.encoding.text;
    if (e && !Array.isArray(e) && e.value === value) out.push(sub);
  }
  return out.length ? out : [hit.node];
}

/* ---- data-driven labels: find the spec row behind a clicked glyph ---- */

/* The rows a layer draws from, when they live in the spec's own datasets
   block (which is where vega-lite puts every non-inline dataset). */
function datasetRowsFor(node) {
  const d = node.data;
  if (!d) return null;
  if (Array.isArray(d.values)) return { name: null, rows: d.values };
  if (d.name && currentSpec.datasets && Array.isArray(currentSpec.datasets[d.name])) {
    return { name: d.name, rows: currentSpec.datasets[d.name] };
  }
  return null;
}

/* Match a scenegraph datum back to its spec row by counting agreeing
   primitive fields. Dates cannot be compared directly -- vega has already
   parsed the spec's ISO string into a Date -- so they are skipped rather
   than guessed at. Requires a UNIQUE best match: an ambiguous result means
   the caller must decline the edit rather than write to the wrong row. */
function findSpecRowIndex(rows, datum) {
  const comparable = v => (typeof v === "string" || typeof v === "number" ||
                           typeof v === "boolean");
  let best = -1, bestScore = 0, tied = false;
  for (let i = 0; i < rows.length; i++) {
    let score = 0;
    for (const k of Object.keys(rows[i])) {
      const a = rows[i][k], b = datum[k];
      if (!comparable(a) || !comparable(b)) continue;
      if (a === b) score++;
    }
    if (score > bestScore) { best = i; bestScore = score; tied = false; }
    else if (score === bestScore && score > 0) { tied = true; }
  }
  return (bestScore > 0 && !tied) ? best : -1;
}

/* ---- scale-driven labels: rename map -> labelExpr ---- */

function exprQuote(s) {
  return "'" + String(s).replace(/\\/g, "\\\\").replace(/'/g, "\\'") + "'";
}

/* Compose the rename map over whatever the producer's own expression yields,
   so a rename keys off the label the user actually sees. With no producer
   expression the subject is plain `datum.label` and the result stays short. */
function buildLabelExpr(base, map) {
  const subject = base ? "(" + base + ")" : "datum.label";
  const keys = Object.keys(map);
  if (!keys.length) return base;
  let out = "";
  for (const from of keys) {
    out += subject + " === " + exprQuote(from) + " ? " +
           exprQuote(map[from]) + " : ";
  }
  return out + subject;
}

/* Every encoding that draws the clicked guide. Mirrors the axis-title rule:
   a dual-axis chart's two y-axes are independent, so a rename on one side
   must not touch the other. */
function eachGuideEncoding(node, channel, guide, orient, fn) {
  walkEncoding(node, channel, enc => {
    if (enc[guide] === null) return;
    if (guide === "axis") {
      const encOrient = (enc.axis && typeof enc.axis === "object")
        ? enc.axis.orient : undefined;
      if (orient === "right" && encOrient !== "right") return;
      if (orient !== "right" && encOrient === "right") return;
    }
    if (!enc[guide] || typeof enc[guide] !== "object") enc[guide] = {};
    fn(enc[guide]);
  });
}

function readLabelExpr(node, channel, guide, orient) {
  let found;
  eachGuideEncoding(node, channel, guide, orient, g => {
    if (found === undefined) found = g.labelExpr;
  });
  return found === undefined ? null : found;
}

/* ---- walk the ancestors of a clicked <text> ---- */
function inspectTextNode(el) {
  let role = null, markName = null, scopeName = null, axisOrient = null;
  let cur = el;
  while (cur && cur.nodeType === 1) {
    const cls = cur.getAttribute("class");
    if (cls) {
      const toks = cls.split(/\s+/);
      if (role === null) {
        for (const t of toks) {
          if (t.indexOf("role-") === 0) { role = t.substring(5); break; }
        }
      }
      if (markName === null && toks.indexOf("role-mark") >= 0) {
        markName = toks[toks.length - 1];
      }
      if (scopeName === null && toks.indexOf("role-scope") >= 0) {
        scopeName = toks[toks.length - 1];
      }
    }
    // The axis group's orientation is the only thing that distinguishes a
    // left y-axis title from a right one, and it lives on the scenegraph
    // item of an ancestor that carries NO class attribute -- Vega puts
    // `class="mark-group role-axis"` on one wrapper and the bound item on
    // the wrapper inside it. So this read is keyed off the item's own
    // mark.role rather than off any class token.
    if (axisOrient === null) {
      const d = cur.__data__;
      if (d && d.mark && d.mark.role === "axis" && d.orient) {
        axisOrient = d.orient;
      }
    }
    cur = cur.parentNode;
  }
  const item = el.__data__ || (el.parentNode && el.parentNode.__data__) || null;
  return {
    role: role, markName: markName, scopeName: scopeName,
    axisOrient: axisOrient, item: item,
    text: (el.textContent || "").trim(),
  };
}

/* ---- classify into an editable (or explained) target ---- */
function resolveTextTarget(info) {
  const role = info.role;

  // Data marks: annotation labels, direct series labels, caption / source
  // panel, side narrative panels, value labels.
  if (role === "mark" && info.markName) {
    const hit = decodeSpecPath(info.markName);
    if (!hit) return { kind: "skip" };
    const n = hit.node;

    if (isTextPanelNode(n)) {
      const panels = findTextPanels(currentSpec);
      const match = panels.find(p => p.node === n);
      return {
        kind: "panel", panel: match || { role: "caption", node: n, path: hit.path },
        current: String(n.mark.text).split("\n").join(" ").trim(),
        label: (match ? match.role.replace("_", " ") : "text panel") +
               "  (" + hit.path + ")",
      };
    }

    const enc = n.encoding && n.encoding.text;
    if (enc && typeof enc === "object" && !Array.isArray(enc)) {
      if (enc.value !== undefined) {
        const nodes = textValueSiblings(info.markName, hit);
        return {
          kind: "literal", nodes: nodes, current: String(enc.value),
          label: (nodes.length > 1
                  ? "annotation label (" + nodes.length + " layers incl. halo)"
                  : "text mark") + "  (" + hit.path + ")",
        };
      }
      if (enc.field !== undefined) {
        const ds = datasetRowsFor(n);
        const datum = info.item && info.item.datum;
        if (!ds || !datum) {
          return { kind: "derived",
            why: "This label is generated from the data field '" + enc.field +
                 "', and its rows are not reachable from the spec, so there " +
                 "is no cell to edit. Change the data instead." };
        }
        const row = findSpecRowIndex(ds.rows, datum);
        if (row < 0) {
          return { kind: "derived",
            why: "This label comes from the data field '" + enc.field +
                 "', but its row could not be identified unambiguously, so " +
                 "editing it risks changing the wrong label." };
        }
        // A plain string column is the label itself (a direct series label);
        // anything formatted is a number being rendered through d3-format.
        const cell = ds.rows[row][enc.field];
        if (enc.format === undefined && typeof cell === "string") {
          return {
            kind: "datumText", dataset: ds.name, rows: ds.rows,
            row: row, field: enc.field, current: String(cell),
            label: "series label  (" + hit.path + " row " + row + ")",
          };
        }
        return {
          kind: "valueLabel", node: n, markName: info.markName,
          dataset: ds.name, rows: ds.rows, row: row, field: enc.field,
          current: info.text,
          label: "value label  (" + hit.path + " row " + row + ")",
        };
      }
    }
    return { kind: "skip" };
  }

  // Guide marks belong to the panel whose scope group encloses them.
  const scope = info.scopeName ? decodeSpecPath(info.scopeName)
                               : { node: currentSpec, path: "spec" };
  if (!scope) return { kind: "skip" };

  if (role === "title-text" || role === "title-subtitle") {
    const key = (role === "title-text") ? "text" : "subtitle";
    const owner = findTitleOwnerAt(scope.node, scope.path);
    const t = owner.node.title;
    let cur = "";
    if (typeof t === "string") cur = (key === "text") ? t : "";
    else if (t) cur = t[key] == null ? "" : String(t[key]);
    return {
      kind: "title", node: owner.node, titleKey: key, current: cur,
      label: (key === "text" ? "title" : "subtitle") + "  (" + owner.path + ")",
    };
  }

  if (role === "axis-title") {
    const ch = (info.axisOrient === "left" || info.axisOrient === "right")
      ? "y" : "x";
    return {
      kind: "axisTitle", node: scope.node, channel: ch,
      orient: info.axisOrient, current: info.text,
      label: ch.toUpperCase() + "-axis title" +
             (info.axisOrient ? " (" + info.axisOrient + ")" : "") +
             "  (" + scope.path + ")",
    };
  }

  if (role === "legend-title") {
    return {
      kind: "legendTitle", node: scope.node, current: info.text,
      label: "legend title  (" + scope.path + ")",
    };
  }

  // Scale-driven labels. There is no string in the spec to overwrite, so the
  // edit becomes a rename entry that compiles into the guide's labelExpr.
  if (role === "axis-label") {
    const ch = (info.axisOrient === "left" || info.axisOrient === "right")
      ? "y" : "x";
    return {
      kind: "labelRename", node: scope.node, guide: "axis", channel: ch,
      orient: info.axisOrient, current: info.text,
      key: scope.path + "|axis|" + ch + "|" + (info.axisOrient || ""),
      label: ch.toUpperCase() + "-axis tick label" +
             (info.axisOrient ? " (" + info.axisOrient + ")" : "") +
             "  (" + scope.path + ")",
    };
  }
  if (role === "legend-label") {
    return {
      kind: "labelRename", node: scope.node, guide: "legend", channel: "color",
      orient: null, current: info.text,
      key: scope.path + "|legend|color|",
      label: "legend entry  (" + scope.path + ")",
    };
  }
  return { kind: "skip" };
}

/* Producer literals may already be soft-wrapped with "\n" at a width we
   cannot recover from the spec. Re-wrap the replacement to the widest line
   of the original, which self-calibrates to whatever the producer chose.
   Single-line originals are left alone. */
function rewrapToExistingWidth(oldText, newText) {
  const old = String(oldText == null ? "" : oldText);
  if (old.indexOf("\n") < 0) return newText;
  let perLine = 0;
  for (const line of old.split("\n")) perLine = Math.max(perLine, line.length);
  if (perLine < 1) return newText;
  const words = String(newText).split(/\s+/).filter(Boolean);
  if (!words.length) return newText;
  const out = [];
  let line = words[0];
  for (const w of words.slice(1)) {
    if (line.length + 1 + w.length <= perLine) line = line + " " + w;
    else { out.push(line); line = w; }
  }
  out.push(line);
  return out.join("\n");
}

function writeAxisTitleScoped(ownerNode, channel, orient, value) {
  // Restrict to the clicked axis's own side so a dual-axis chart's left and
  // right titles stay independent (the producer tags them axis.orient).
  walkEncoding(ownerNode, channel, enc => {
    if (enc.axis === null) return;
    const encOrient = (enc.axis && typeof enc.axis === "object")
      ? enc.axis.orient : undefined;
    if (orient === "right" && encOrient !== "right") return;
    if (orient !== "right" && encOrient === "right") return;
    enc.title = value;
    if (enc.axis && typeof enc.axis === "object") enc.axis.title = value;
  });
}

function applyTextEdit(target, newText) {
  if (target.kind === "panel") {
    const panel = target.panel, was = panel.node.mark.text;
    journalOriginal("panel:" + panel.role + ":" + (panel.path || ""),
                    () => rewrapTextPanel(panel, String(was).split("\n").join(" ")));
    rewrapTextPanel(panel, newText);
    syncTextKnob(panel.role === "caption" ? "captionText" : null, newText);
  } else if (target.kind === "literal") {
    const nodes = target.nodes, was = nodes.map(n => n.encoding.text.value);
    journalOriginal("literal:" + target.label, () => {
      for (let i = 0; i < nodes.length; i++) nodes[i].encoding.text.value = was[i];
    });
    for (const n of nodes) {
      n.encoding.text.value =
        rewrapToExistingWidth(n.encoding.text.value, newText);
    }
  } else if (target.kind === "title") {
    const n = target.node, key = target.titleKey;
    // Cloned, not aliased: the write below mutates this same title object in
    // place, so holding the reference would "restore" the edited value.
    const was = (n.title && typeof n.title === "object")
      ? deepClone(n.title) : n.title;
    journalOriginal("title:" + key + ":" + target.label, () => {
      n.title = was;
      syncTextKnob(key === "text" ? "titleText" : "subtitleText",
                   typeof was === "string" ? was
                     : String((was && was[key]) || ""));
    });
    if (typeof n.title === "string") n.title = { text: n.title };
    if (n.title == null) n.title = {};
    n.title[key] = rewrapToExistingWidth(n.title[key], newText);
    syncTextKnob(key === "text" ? "titleText" : "subtitleText", newText);
  } else if (target.kind === "axisTitle") {
    const t = target, was = t.current;
    journalOriginal("axisTitle:" + t.label, () => {
      writeAxisTitleScoped(t.node, t.channel, t.orient, was);
      syncTextKnob(t.channel === "y" ? "yAxisTitle" : "xAxisTitle", was);
    });
    writeAxisTitleScoped(t.node, t.channel, t.orient, newText);
    syncTextKnob(t.channel === "y" ? "yAxisTitle" : "xAxisTitle", newText);
  } else if (target.kind === "legendTitle") {
    const node = target.node, was = target.current;
    journalOriginal("legendTitle:" + target.label, () => {
      writeLegendTitle(node, was);
      syncTextKnob("legendTitle", was);
    });
    writeLegendTitle(node, newText);
    syncTextKnob("legendTitle", newText);
  } else if (target.kind === "datumText") {
    const rows = target.rows, i = target.row, f = target.field;
    const was = rows[i][f];
    journalOriginal("cell:" + target.dataset + ":" + i + ":" + f,
                    () => { rows[i][f] = was; });
    rows[i][f] = newText;
  } else if (target.kind === "valueLabel") {
    if (!convertValueLabelLayer(target)) return;
    target.rows[target.row][CFS_TEXT_COL] = newText;
  } else if (target.kind === "labelRename") {
    if (!applyLabelRename(target, newText)) return;
  } else {
    return;
  }
  renderChart();
  updateTextAreas();
  setStatus("edited " + target.label);
}

function writeLegendTitle(node, value) {
  walkEncoding(node, "color", enc => {
    enc.title = value;
    if (enc.legend && typeof enc.legend === "object") enc.legend.title = value;
  });
}

/* Repoint a formatted numeric label layer at a plain text column so its
   strings become editable.

   The formatted strings are harvested from what is currently RENDERED rather
   than recomputed, because reimplementing d3-format here would be a second
   source of truth for every format spec the engine can emit. Every row of a
   value-label dataset is drawn (the engine pre-splits positive and negative
   into separate datasets and applies no filter), so the harvest is complete --
   and if it ever is not, the conversion is refused rather than silently
   blanking the labels it could not account for. */
function convertValueLabelLayer(target) {
  const node = target.node;
  if (node.encoding.text.field === CFS_TEXT_COL) return true;  // already converted

  const rendered = new Map();
  const svg = document.querySelector("#chart svg");
  if (svg) {
    for (const el of svg.querySelectorAll("text")) {
      const info = inspectTextNode(el);
      if (info.markName !== target.markName) continue;
      const d = info.item && info.item.datum;
      if (!d) continue;
      const idx = findSpecRowIndex(target.rows, d);
      if (idx >= 0) rendered.set(idx, (el.textContent || "").trim());
    }
  }
  const missing = [];
  for (let i = 0; i < target.rows.length; i++) {
    if (!rendered.has(i)) missing.push(i);
  }
  if (missing.length) {
    cfsToast("Cannot make these value labels editable: " + missing.length +
             " of " + target.rows.length + " rows are not currently drawn, so " +
             "their formatted text cannot be read back. Edit the data or the " +
             "format instead.");
    return false;
  }

  const wasEnc = node.encoding.text;
  const rows = target.rows;
  journalOriginal("valueLabel:" + target.dataset, () => {
    node.encoding.text = wasEnc;
    for (const r of rows) delete r[CFS_TEXT_COL];
  });
  for (const [i, s] of rendered) rows[i][CFS_TEXT_COL] = s;
  node.encoding.text = { field: CFS_TEXT_COL, type: "nominal" };
  cfsToast("This label now holds text instead of the number it was formatted " +
           "from, so it will no longer follow the data or the format knob. " +
           "Use \u201cRevert text\u201d to put it back.");
  return true;
}

/* Record a tick / legend-entry rename and recompile the guide's labelExpr. */
function applyLabelRename(target, newText) {
  const store = textEditStore();
  let entry = store.renames[target.key];
  if (!entry) {
    // Captured once, before this feature has ever written here, so `base` is
    // always the producer's own expression rather than one of ours.
    entry = { base: readLabelExpr(target.node, target.channel, target.guide,
                                  target.orient),
              map: {} };
    store.renames[target.key] = entry;
  }
  const key = target.key, guide = target.guide, node = target.node;
  const channel = target.channel, orient = target.orient;
  const baseExpr = entry.base;
  journalOriginal("labelExpr:" + key, () => {
    eachGuideEncoding(node, channel, guide, orient, g => {
      if (baseExpr == null) delete g.labelExpr;
      else g.labelExpr = baseExpr;
    });
    delete textEditStore().renames[key];
  });

  entry.map[target.current] = newText;
  const expr = buildLabelExpr(entry.base, entry.map);
  eachGuideEncoding(node, channel, guide, orient, g => { g.labelExpr = expr; });
  return true;
}

/* Undo every in-place text edit made in this session, newest first, leaving
   knob values and styling untouched. */
function revertTextEdits() {
  if (!_textJournal.length) { setStatus("no text edits to revert"); return; }
  const n = _textJournal.length;
  for (let i = _textJournal.length - 1; i >= 0; i--) _textJournal[i].undo();
  _textJournal = [];
  const m = currentSpec.usermeta;
  if (m && m.cfsTextEdits) {
    delete m.cfsTextEdits;
    if (!Object.keys(m).length) delete currentSpec.usermeta;
  }
  renderChart();
  updateTextAreas();
  setStatus("reverted " + n + " text edit" + (n === 1 ? "" : "s"));
}

/* Mirror the new value into the matching knob so the Controls panel does
   not display a stale string. Deliberately NOT recorded in `overrides`:
   text is per-chart content, and `overrides` is what spec sheets bundle. */
function syncTextKnob(knobName, value) {
  if (!knobName) return;
  currentKnobValues[knobName] = value;
  const input = document.getElementById("knob_" + knobName);
  if (input) input.value = value;
}

/* The Advanced panel's four domain boxes are a second view of the scale
   domains the window and range menus write. Re-reading them through the
   same extractor that populates them on load keeps the panel from
   reading "auto" while the chart in front of the user is clamped. */
const CFS_DOMAIN_KNOBS = [["xDomainMin", "x", 0], ["xDomainMax", "x", 1],
                          ["yDomainMin", "y", 0], ["yDomainMax", "y", 1]];

function syncDomainKnobs() {
  for (const [name, channel, idx] of CFS_DOMAIN_KNOBS) {
    if (!document.getElementById("knob_" + name)) continue;
    const v = _extractDomainBound(currentSpec, channel, idx);
    syncTextKnob(name, (v === undefined || v === null) ? "" : String(v));
  }
}

/* ---- the inline editor ---- */
let _cfsEditor = null;

function closeInlineEditor() {
  // Drop the handle BEFORE detaching. Removing a focused element makes the
  // browser fire `blur` synchronously, and this function is itself the blur
  // listener -- so it re-enters mid-statement. Nulling first turns that
  // re-entrant call into a no-op; leaving it until after the removal meant
  // the inner call detached the node and the outer call's remove() threw
  // NotFoundError, which escaped the Enter handler and discarded the edit.
  const ed = _cfsEditor;
  _cfsEditor = null;
  if (ed && ed.parentNode) ed.parentNode.removeChild(ed);
}

function beginInlineEdit(el) {
  closeInlineEditor();
  const target = resolveTextTarget(inspectTextNode(el));
  if (target.kind === "derived") { cfsToast(target.why); return; }
  if (target.kind === "skip") return;

  const box = el.getBoundingClientRect();
  const rotated = box.height > box.width * 1.5;
  const ed = document.createElement("input");
  ed.type = "text";
  ed.className = "cfs-inline-editor";
  ed.value = (target.current && target.current.length)
    ? target.current.split("\n").join(" ")
    : (el.textContent || "").trim();
  ed.title = "editing " + target.label;
  const width = Math.max(rotated ? 220 : box.width + 28, 110);
  ed.style.width = width + "px";
  ed.style.left = (window.scrollX +
    (rotated ? box.left : box.left - 4)) + "px";
  ed.style.top = (window.scrollY +
    (rotated ? box.top + box.height / 2 - 11 : box.top - 3)) + "px";
  // The computed size is in the SVG's own units, which are the screen's
  // only at 100%. Scaling it keeps the editor the size of the glyphs it
  // sits on top of.
  const fs = parseFloat(window.getComputedStyle(el).fontSize);
  if (fs > 0) ed.style.fontSize = (fs * _fitScale).toFixed(2) + "px";
  document.body.appendChild(ed);
  _cfsEditor = ed;
  ed.focus();
  ed.select();

  ed.addEventListener("keydown", e => {
    if (e.key === "Enter") {
      const v = ed.value;
      closeInlineEditor();
      // Snapshot before the edit so text retyping shares the one Undo
      // button with right-click changes and drags.
      if (v !== target.current) pushUndo("Renamed to \u201c" + v + "\u201d");
      applyTextEdit(target, v);
    } else if (e.key === "Escape") {
      closeInlineEditor();
    }
    e.stopPropagation();
  });
  ed.addEventListener("blur", closeInlineEditor);
}

/* Classify every glyph once per render so the cursor and hover highlight
   advertise up front which text is editable and which only explains
   itself. Re-run after each render because vega rebuilds the nodes. */
function wireTextTargets() {
  const svg = document.querySelector("#chart svg");
  if (!svg) return;
  const nodes = svg.querySelectorAll("text");
  for (const el of nodes) {
    const info = inspectTextNode(el);
    if (!EDITABLE_ROLES.has(info.role)) continue;
    const target = resolveTextTarget(info);
    if (target.kind === "skip") continue;
    el.classList.add(target.kind === "derived" ? "cfs-derived" : "cfs-editable");
    el.addEventListener("dblclick", e => {
      e.preventDefault();
      e.stopPropagation();
      beginInlineEdit(el);
    });
  }
}

function cfsToast(msg) {
  const el = document.getElementById("cfsToast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("on");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("on"), 4600);
}

/* ============================================================
   UNDO

   Text editing keeps its own journal of closures because it has to
   restore live node references. Everything reachable by right-click or
   by a drag is a whole-spec mutation instead, so the cheapest correct
   undo is a spec snapshot taken immediately before the change. Both
   paths funnel through here so one button covers the lot.
   ============================================================ */
let _undoStack = [];
const UNDO_LIMIT = 60;

/* Returns the entry so a caller that snapshots before it knows the final
   label -- a drag, which only knows its size on release -- can relabel it,
   or drop it if the gesture turned out to be a no-op. */
function pushUndo(label) {
  const entry = { spec: deepClone(currentSpec), label: label };
  _undoStack.push(entry);
  if (_undoStack.length > UNDO_LIMIT) _undoStack.shift();
  updateUndoButton();
  return entry;
}

function updateUndoButton() {
  const b = document.getElementById("undoBtn");
  if (!b) return;
  const n = _undoStack.length;
  b.disabled = n === 0;
  b.title = n ? ("Undo: " + _undoStack[n - 1].label) : "Nothing to undo";
}

function undoLastEdit() {
  if (!_undoStack.length) { cfsToast("Nothing to undo."); return; }
  closeMenu();
  const entry = _undoStack.pop();
  currentSpec = entry.spec;
  populateKnobValuesFromSpec();
  initializeKnobs();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
  updateUndoButton();
  cfsToast("Undone: " + entry.label);
}

/* Commit a spec mutation: snapshot, re-render, resync the panel. */
function commitEdit(label, fn) {
  pushUndo(label);
  const changed = fn();
  if (changed === false) {
    _undoStack.pop();
    updateUndoButton();
    return false;
  }
  renderChart();
  updateTextAreas();
  updateSizeSummary();
  syncDomainKnobs();
  setStatus(label);
  return true;
}

/* ============================================================
   DIRECT MANIPULATION: WHAT DID THE POINTER HIT?

   inspectTextNode's ancestor walk is not text-specific -- it reads
   class tokens and bound scenegraph items -- so the same walk
   classifies a line path or a legend swatch. What differs is the
   mapping from role to an actionable target.
   ============================================================ */

function axisChannelOf(orient) {
  return (orient === "left" || orient === "right") ? "y" : "x";
}

/* Every node in the tree whose colour encoding uses this field. A
   multi-line chart draws its series from several layers (the line, its
   end-of-line labels, sometimes a hover layer), and a recolour that
   misses one leaves the chart internally inconsistent. */
function colorNodesFor(field) {
  const out = [];
  (function walk(n) {
    if (!n || typeof n !== "object") return;
    const c = n.encoding && n.encoding.color;
    if (c && !Array.isArray(c) && c.field === field) out.push(n);
    for (const k of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(n[k])) n[k].forEach(walk);
    }
    if (n.spec) walk(n.spec);
  })(currentSpec);
  return out;
}

/* Distinct values of a field, in first-appearance order, across every
   dataset the spec carries. Used when the compiled view does not expose
   a top-level colour scale (concat specs resolve scales per panel). */
function distinctFieldValues(field) {
  const seen = [];
  const scan = rows => {
    for (const r of rows) {
      if (r && r[field] !== undefined && seen.indexOf(r[field]) < 0) seen.push(r[field]);
    }
  };
  if (currentSpec.datasets) {
    for (const rows of Object.values(currentSpec.datasets)) {
      if (Array.isArray(rows)) scan(rows);
    }
  }
  (function walk(n) {
    if (!n || typeof n !== "object") return;
    if (n.data && Array.isArray(n.data.values)) scan(n.data.values);
    for (const k of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(n[k])) n[k].forEach(walk);
    }
    if (n.spec) walk(n.spec);
  })(currentSpec);
  return seen;
}

/* What colour is each series actually painted right now? Read from the
   rendered scenegraph rather than from the spec, because the producer's
   colours may come from a config range, an explicit scale range, or a
   palette default, and only the render reconciles all three. */
function renderedSeriesColors(field) {
  const out = {};
  const svg = document.querySelector("#chart svg");
  if (!svg) return out;
  const sel = "g.role-mark path, g.role-mark rect, g.role-mark symbol, g.role-mark line, g.role-mark area";
  for (const el of svg.querySelectorAll(sel)) {
    const it = el.__data__ || (el.parentNode && el.parentNode.__data__);
    if (!it || !it.datum) continue;
    const key = it.datum[field];
    if (key == null || out[key]) continue;
    const c = it.stroke || it.fill;
    if (c && c !== "transparent") out[key] = normalizeColor(c);
  }
  return out;
}

function colorScaleInfo(field) {
  let domain = null;
  if (vegaView) {
    try {
      const sc = vegaView.scale("color");
      if (sc && typeof sc.domain === "function") domain = sc.domain().slice();
    } catch (e) { /* concat specs resolve colour per panel, not at root */ }
  }
  if (!domain || !domain.length) domain = distinctFieldValues(field);
  const painted = renderedSeriesColors(field);
  const pal = (PALETTES[currentPalette] && PALETTES[currentPalette].colors) || [];
  const colors = domain.map((d, i) => painted[d] || pal[i % (pal.length || 1)] || "#4C78A8");
  return { domain: domain, colors: colors };
}

/* The chart engine draws direct end-of-line labels from a dataset that
   carries its own readability-tuned colour column. Recolouring a series
   without touching that column leaves the label the old colour. */
function syncLabelColors(field, seriesValue, newColor) {
  let touched = 0;
  const scan = rows => {
    if (!Array.isArray(rows) || !rows.length) return;
    for (const col of Object.keys(rows[0])) {
      if (!/colou?r/i.test(col)) continue;
      for (const r of rows) {
        if (r[field] === seriesValue) { r[col] = newColor; touched++; }
      }
    }
  };
  if (currentSpec.datasets) {
    for (const rows of Object.values(currentSpec.datasets)) scan(rows);
  }
  (function walk(n) {
    if (!n || typeof n !== "object") return;
    if (n.data && Array.isArray(n.data.values)) scan(n.data.values);
    for (const k of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(n[k])) n[k].forEach(walk);
    }
    if (n.spec) walk(n.spec);
  })(currentSpec);
  return touched;
}

function setSeriesColor(field, seriesValue, newColor) {
  const info = colorScaleInfo(field);
  const i = info.domain.indexOf(seriesValue);
  if (i < 0) return false;
  const range = info.colors.slice();
  range[i] = newColor;
  const nodes = colorNodesFor(field);
  if (!nodes.length) return false;
  for (const n of nodes) {
    if (!n.encoding.color.scale) n.encoding.color.scale = {};
    n.encoding.color.scale.domain = info.domain.slice();
    n.encoding.color.scale.range = range;
  }
  syncLabelColors(field, seriesValue, newColor);
  return true;
}

/* ---- per-series line styling -------------------------------------------
   A scale-based strokeWidth encoding is accepted by the compiler and then
   ignored at render time -- vega-lite even warns that the channel "should
   not be used with an unsorted discrete field". A CONDITIONAL encoding
   does work, but only once the mark's own strokeWidth is deleted, because
   a mark property outranks the encoding.

   Conditions are rebuilt wholesale on every change rather than parsed back
   out of the previous test expressions, so the per-series values need
   somewhere durable to live. usermeta is vega-lite's sanctioned home for
   editor state -- the compiler ignores it entirely -- and is already where
   in-place text renames are kept.
   ------------------------------------------------------------------------ */
function seriesStyleStore() {
  if (!currentSpec.usermeta) currentSpec.usermeta = {};
  const m = currentSpec.usermeta;
  if (!m.cfsSeriesStyle) m.cfsSeriesStyle = {};
  const s = m.cfsSeriesStyle;
  if (!s.strokeWidth) s.strokeWidth = {};
  if (!s.strokeDash) s.strokeDash = {};
  if (!s.base) s.base = {};
  return s;
}

/* The mark-level value is the "every other series" arm of the condition
   list, so it has to be captured before the mark property is deleted. */
function baseStyleValue(channel, nodes, fallbackValue) {
  const store = seriesStyleStore();
  if (store.base[channel] === undefined) {
    let v;
    for (const n of nodes) {
      if (typeof n.mark === "object" && n.mark[channel] !== undefined) {
        v = n.mark[channel];
        break;
      }
    }
    if (v === undefined) v = getPath(currentSpec, "config.line." + channel);
    store.base[channel] = (v === undefined) ? fallbackValue : v;
  }
  return store.base[channel];
}

function writeSeriesConditions(field, channel, nodes, baseValue) {
  const perField = seriesStyleStore()[channel][field] || {};
  const entries = Object.entries(perField);
  for (const n of nodes) {
    if (typeof n.mark === "object") delete n.mark[channel];
    if (!entries.length) { delete n.encoding[channel]; continue; }
    n.encoding[channel] = {
      condition: entries.map(([series, value]) => ({
        test: "datum[" + exprQuote(field) + "] === " + exprQuote(series),
        value: value,
      })),
      value: baseValue,
    };
  }
  if (currentSpec.config && currentSpec.config.line) {
    delete currentSpec.config.line[channel];
  }
}

function styleableLineNodes(field) {
  return colorNodesFor(field).filter(n => {
    const mt = markTypeOf(n);
    return mt === "line" || mt === "rule";
  });
}

function setSeriesStrokeWidth(field, seriesValue, width) {
  const nodes = styleableLineNodes(field);
  if (!nodes.length) return false;
  const base = baseStyleValue("strokeWidth", nodes, 2);
  const store = seriesStyleStore();
  if (!store.strokeWidth[field]) store.strokeWidth[field] = {};
  store.strokeWidth[field][seriesValue] = width;
  writeSeriesConditions(field, "strokeWidth", nodes, base);
  return true;
}

function setSeriesDash(field, seriesValue, dashArr) {
  const nodes = styleableLineNodes(field);
  if (!nodes.length) return false;
  // Solid is an empty dash pattern, not an absent one: every arm of the
  // condition list has to name a concrete value.
  const base = baseStyleValue("strokeDash", nodes, []);
  const store = seriesStyleStore();
  if (!store.strokeDash[field]) store.strokeDash[field] = {};
  store.strokeDash[field][seriesValue] = dashArr || [];
  writeSeriesConditions(field, "strokeDash", nodes, base);
  return true;
}

function markTypeOf(node) {
  if (!node || !node.mark) return null;
  return typeof node.mark === "string" ? node.mark : node.mark.type;
}

/* Write a property onto a mark definition, promoting a bare string mark
   ("line") to object form so it can carry properties at all. */
function setMarkProp(node, prop, value) {
  if (!node || !node.mark) return;
  if (typeof node.mark === "string") node.mark = { type: node.mark };
  if (value === undefined || value === null) delete node.mark[prop];
  else node.mark[prop] = value;
}

function resolveHitTarget(el) {
  const info = inspectTextNode(el);
  const role = info.role || "";
  const scope = info.scopeName ? decodeSpecPath(info.scopeName)
                               : { node: currentSpec, path: "spec" };

  if (role.indexOf("axis") === 0) {
    const ch = axisChannelOf(info.axisOrient);
    return {
      kind: "axis", channel: ch, orient: info.axisOrient,
      scope: scope, info: info,
      title: ch.toUpperCase() + "-axis" +
             (info.axisOrient ? " (" + info.axisOrient + ")" : ""),
    };
  }

  if (role.indexOf("legend") === 0) {
    let series = null, field = null;
    const enc = firstColorEncoding();
    if (enc) {
      field = enc.field;
      if (role === "legend-label" || role === "legend-symbol") {
        const d = info.item && info.item.datum;
        series = d ? (d.value !== undefined ? d.value : d[field]) : null;
      }
    }
    return {
      kind: "legend", scope: scope, info: info, field: field, series: series,
      title: series != null ? ("Legend: " + series) : "Legend",
    };
  }

  if (role === "mark" && info.markName) {
    const hit = decodeSpecPath(info.markName);
    if (hit) {
      const node = hit.node;
      const mt = markTypeOf(node);
      if (isTextPanelNode(node)) {
        return { kind: "canvas", info: info, title: "Chart" };
      }
      const colorEnc = node.encoding && node.encoding.color;
      const field = (colorEnc && !Array.isArray(colorEnc)) ? colorEnc.field : undefined;
      const datum = info.item && info.item.datum;
      const series = (field && datum) ? datum[field] : null;
      const isAnnotation = (mt === "rule" || mt === "text") && !field;
      return {
        kind: isAnnotation ? "annotation" : "series",
        node: node, path: hit.path, markType: mt,
        field: field || null, series: series != null ? series : null,
        info: info,
        title: series != null ? String(series)
             : isAnnotation ? "Annotation"
             : (mt ? mt.charAt(0).toUpperCase() + mt.slice(1) : "Mark"),
      };
    }
  }

  return { kind: "canvas", info: info, title: "Chart" };
}

function firstColorEncoding() {
  let found = null;
  walkEncoding(currentSpec, "color", enc => {
    if (!found && enc && enc.field !== undefined) found = enc;
  });
  return found;
}

/* ============================================================
   CONTEXT MENU CHROME

   One reused root, rebuilt per open. Items are plain objects so an
   action's shape (click row / swatch grid / stepper / chips) is a
   rendering concern rather than a per-callsite DOM chore.
   ============================================================ */
let _menuEl = null;

function menuRoot() {
  if (!_menuEl) _menuEl = document.getElementById("cfsMenu");
  return _menuEl;
}

function closeMenu() {
  const m = menuRoot();
  if (m) { m.classList.remove("on"); m.innerHTML = ""; }
}

function menuRow(label, accessory, onClick, opts) {
  opts = opts || {};
  const d = document.createElement("div");
  d.className = "cfs-item" + (opts.disabled ? " cfs-disabled" : "") +
                (opts.on ? " cfs-on" : "");
  const s = document.createElement("span");
  s.textContent = label;
  d.appendChild(s);
  if (accessory) {
    const a = document.createElement("span");
    a.className = "cfs-acc";
    a.textContent = accessory;
    d.appendChild(a);
  }
  if (!opts.disabled && onClick) {
    d.addEventListener("click", () => {
      if (!opts.keepOpen) closeMenu();
      onClick();
    });
  }
  return d;
}

function menuSwatches(label, colors, current, onPick) {
  const wrap = document.createElement("div");
  wrap.className = "cfs-sub";
  if (label) {
    const l = document.createElement("div");
    l.className = "cfs-sub-label";
    l.textContent = label;
    wrap.appendChild(l);
  }
  const grid = document.createElement("div");
  grid.className = "cfs-swatches";
  for (const c of colors) {
    const b = document.createElement("div");
    b.className = "cfs-sw" + (normalizeColor(c).toLowerCase() ===
                              normalizeColor(current || "").toLowerCase() ? " cfs-cur" : "");
    b.style.background = c;
    b.title = c;
    b.addEventListener("click", () => { closeMenu(); onPick(c); });
    grid.appendChild(b);
  }
  wrap.appendChild(grid);
  const picker = document.createElement("input");
  picker.type = "color";
  picker.value = normalizeColor(current || "#4C78A8");
  picker.style.marginTop = "6px";
  picker.addEventListener("change", () => { closeMenu(); onPick(picker.value); });
  wrap.appendChild(picker);
  return wrap;
}

function menuStepper(label, valueText, onDown, onUp) {
  const wrap = document.createElement("div");
  wrap.className = "cfs-sub";
  const l = document.createElement("div");
  l.className = "cfs-sub-label";
  l.textContent = label;
  wrap.appendChild(l);
  const row = document.createElement("div");
  row.className = "cfs-steps";
  const minus = document.createElement("button");
  minus.textContent = "\u2212";
  const num = document.createElement("span");
  num.className = "cfs-num";
  num.textContent = valueText;
  const plus = document.createElement("button");
  plus.textContent = "+";
  // Steppers stay open: adjusting a tick count or a line weight is
  // inherently iterative, and reopening the menu between nudges would
  // make the common case the slow one.
  minus.addEventListener("click", () => { num.textContent = onDown(); });
  plus.addEventListener("click", () => { num.textContent = onUp(); });
  row.appendChild(minus); row.appendChild(num); row.appendChild(plus);
  wrap.appendChild(row);
  return wrap;
}

function menuChips(label, options, current, onPick) {
  const wrap = document.createElement("div");
  wrap.className = "cfs-sub";
  const l = document.createElement("div");
  l.className = "cfs-sub-label";
  l.textContent = label;
  wrap.appendChild(l);
  const row = document.createElement("div");
  row.className = "cfs-chips";
  for (const o of options) {
    const b = document.createElement("button");
    b.className = "cfs-chip" + (o.value === current ? " cfs-cur" : "");
    b.textContent = o.label;
    b.addEventListener("click", () => { closeMenu(); onPick(o.value); });
    row.appendChild(b);
  }
  wrap.appendChild(row);
  return wrap;
}

/* Two native date inputs plus an Apply. Deliberately not live-on-change:
   a half-typed year is a valid date input value, and windowing on it
   would rewrite the labels against a nonsense span. */
function menuDateRange(label, loStr, hiStr, minStr, maxStr, onApply) {
  const wrap = document.createElement("div");
  wrap.className = "cfs-sub";
  const l = document.createElement("div");
  l.className = "cfs-sub-label";
  l.textContent = label;
  wrap.appendChild(l);
  const row = document.createElement("div");
  row.className = "cfs-dates";
  const a = document.createElement("input");
  const b = document.createElement("input");
  for (const el of [a, b]) {
    el.type = "date";
    if (minStr) el.min = minStr;
    if (maxStr) el.max = maxStr;
  }
  a.value = loStr || "";
  b.value = hiStr || "";
  const go = document.createElement("button");
  go.textContent = "Apply";
  const commit = () => {
    if (!a.value || !b.value) { cfsToast("Pick both a start and an end date."); return; }
    if (a.value >= b.value) { cfsToast("The start date has to come before the end date."); return; }
    closeMenu();
    onApply(a.value, b.value);
  };
  go.addEventListener("click", commit);
  for (const el of [a, b]) {
    el.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); commit(); } });
  }
  row.appendChild(a); row.appendChild(b); row.appendChild(go);
  wrap.appendChild(row);
  return wrap;
}

function menuSep() {
  const d = document.createElement("div");
  d.className = "cfs-sep";
  return d;
}

function openMenu(x, y, title, subtitle, build) {
  const m = menuRoot();
  if (!m) return;
  m.innerHTML = "";
  const head = document.createElement("div");
  head.className = "cfs-menu-head";
  const b = document.createElement("b");
  b.textContent = title;
  head.appendChild(b);
  head.appendChild(document.createTextNode(subtitle || ""));
  m.appendChild(head);
  build(m);
  m.classList.add("on");
  // Place at the pointer, then pull back inside the viewport if the menu
  // would overhang. Measured after paint because the height depends on
  // which items the target produced.
  m.style.left = "0px"; m.style.top = "0px";
  const r = m.getBoundingClientRect();
  const pad = 8;
  let left = x, top = y;
  if (left + r.width + pad > window.innerWidth) left = x - r.width;
  if (top + r.height + pad > window.innerHeight + window.scrollY) {
    top = Math.max(window.scrollY + pad, y - r.height);
  }
  m.style.left = Math.max(pad, left) + "px";
  m.style.top = Math.max(pad, top) + "px";
}

/* ============================================================
   MENU CONTENT PER TARGET
   ============================================================ */

const DASH_CHOICES = [
  { label: "Solid", value: null },
  { label: "Dashed", value: [6, 4] },
  { label: "Dotted", value: [1, 2] },
  { label: "Dash-dot", value: [6, 3, 2, 3] },
  { label: "Long dash", value: [10, 4] },
];

/* Preset labels carry parenthetical sizes and mandate notes that are
   useful in a dropdown but too long for a chip. */
function shortPresetLabel(key) {
  const p = DIM_PRESETS[key] || {};
  const name = String(p.label || key).split("(")[0].trim();
  return (typeof p.width === "number" && key !== "custom")
    ? name + " " + p.width + "\u00d7" + p.height
    : name;
}

function paletteColors() {
  const pal = (PALETTES[currentPalette] && PALETTES[currentPalette].colors) || [];
  const extra = ["#003359", "#5C92CB", "#8FBCE6", "#C00000", "#E8A33D",
                 "#2E7D5B", "#7A5195", "#6B7B8F"];
  const out = [];
  for (const c of pal.concat(extra)) {
    if (c && out.indexOf(c) < 0) out.push(c);
  }
  return out.slice(0, 16);
}

function buildSeriesMenu(t, m) {
  const hasSeries = t.field && t.series != null;
  const info = hasSeries ? colorScaleInfo(t.field) : null;
  const idx = info ? info.domain.indexOf(t.series) : -1;
  const curColor = (idx >= 0) ? info.colors[idx]
    : normalizeColor((typeof t.node.mark === "object" && (t.node.mark.color ||
        t.node.mark.stroke || t.node.mark.fill)) || "#4C78A8");

  m.appendChild(menuSwatches("Colour", paletteColors(), curColor, c => {
    commitEdit(hasSeries ? ("Recoloured " + t.series) : "Recoloured mark", () => {
      if (hasSeries) return setSeriesColor(t.field, t.series, c);
      setMarkProp(t.node, t.markType === "line" ? "stroke" : "fill", c);
      setMarkProp(t.node, "color", c);
      return true;
    });
  }));

  if (t.markType === "line" || t.markType === "rule") {
    m.appendChild(menuSep());
    let w = currentLineWidth(t);
    m.appendChild(menuStepper("Thickness", w.toFixed(1) + " px",
      () => { w = Math.max(0.5, +(w - 0.5).toFixed(1)); applyLineWidth(t, w); return w.toFixed(1) + " px"; },
      () => { w = Math.min(12, +(w + 0.5).toFixed(1)); applyLineWidth(t, w); return w.toFixed(1) + " px"; }));

    m.appendChild(menuChips("Line style",
      DASH_CHOICES.map(d => ({ label: d.label, value: d.label })), null, label => {
        const choice = DASH_CHOICES.find(d => d.label === label);
        commitEdit("Line style: " + label, () => {
          if (hasSeries) return setSeriesDash(t.field, t.series, choice.value);
          setMarkProp(t.node, "strokeDash", choice.value || undefined);
          return true;
        });
      }));
  }

  if (t.markType === "bar" || t.markType === "area" || t.markType === "arc" ||
      t.markType === "rect" || t.markType === "point" || t.markType === "circle") {
    m.appendChild(menuSep());
    let op = (typeof t.node.mark === "object" && t.node.mark.opacity) || 1;
    m.appendChild(menuStepper("Opacity", Math.round(op * 100) + "%",
      () => { op = Math.max(0.1, +(op - 0.1).toFixed(2)); applyOpacity(t, op); return Math.round(op * 100) + "%"; },
      () => { op = Math.min(1, +(op + 0.1).toFixed(2)); applyOpacity(t, op); return Math.round(op * 100) + "%"; }));
  }

  if (t.markType === "point" || t.markType === "circle") {
    m.appendChild(menuSep());
    let sz = (typeof t.node.mark === "object" && t.node.mark.size) || 60;
    m.appendChild(menuStepper("Point size", String(Math.round(sz)),
      () => { sz = Math.max(10, sz - 20); applyPointSize(t, sz); return String(Math.round(sz)); },
      () => { sz = Math.min(600, sz + 20); applyPointSize(t, sz); return String(Math.round(sz)); }));
  }

  if (hasSeries) {
    m.appendChild(menuSep());
    m.appendChild(menuRow("Recolour every series\u2026", null, () => {
      openPaletteMenu();
    }));
  }
}

function currentLineWidth(t) {
  if (t.field && t.series != null) {
    const per = seriesStyleStore().strokeWidth[t.field];
    if (per && typeof per[t.series] === "number") return per[t.series];
    const base = seriesStyleStore().base.strokeWidth;
    if (typeof base === "number") return base;
  }
  if (typeof t.node.mark === "object" && typeof t.node.mark.strokeWidth === "number") {
    return t.node.mark.strokeWidth;
  }
  const cfg = getPath(currentSpec, "config.line.strokeWidth");
  return typeof cfg === "number" ? cfg : 2;
}

function applyLineWidth(t, w) {
  commitEdit("Line thickness " + w + "px", () => {
    if (t.field && t.series != null) return setSeriesStrokeWidth(t.field, t.series, w);
    setMarkProp(t.node, "strokeWidth", w);
    return true;
  });
}

function applyOpacity(t, op) {
  commitEdit("Opacity " + Math.round(op * 100) + "%", () => {
    setMarkProp(t.node, "opacity", op);
    return true;
  });
}

function applyPointSize(t, sz) {
  commitEdit("Point size " + Math.round(sz), () => {
    setMarkProp(t.node, "size", Math.round(sz));
    return true;
  });
}

/* A per-series recolour writes an explicit scale.range, which outranks
   the config-level range a palette sets. Clearing those ranges is what
   makes "recolour every series" actually mean every series. */
function clearPerSeriesColorRanges() {
  (function walk(n) {
    if (!n || typeof n !== "object") return;
    const c = n.encoding && n.encoding.color;
    if (c && !Array.isArray(c) && c.scale && c.scale.range) {
      delete c.scale.range;
      if (!Object.keys(c.scale).length) delete c.scale;
    }
    for (const k of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(n[k])) n[k].forEach(walk);
    }
    if (n.spec) walk(n.spec);
  })(currentSpec);
}

function openPaletteMenu() {
  const r = menuRoot().getBoundingClientRect();
  openMenu(r.left, r.top, "Palette", "applies to every series", m => {
    for (const [name, rec] of Object.entries(PALETTES)) {
      const row = menuRow(rec.label || name, null, () => {
        commitEdit("Palette: " + (rec.label || name), () => {
          clearPerSeriesColorRanges();
          applyPalette(name, true);
          return true;
        });
      }, { on: name === currentPalette });
      const strip = document.createElement("span");
      strip.style.cssText = "display:flex;gap:2px;margin-left:auto";
      for (const c of (rec.colors || []).slice(0, 6)) {
        const dot = document.createElement("span");
        dot.style.cssText = "width:10px;height:10px;border-radius:2px;background:" + c;
        strip.appendChild(dot);
      }
      row.appendChild(strip);
      m.appendChild(row);
    }
  });
}

/* Every node that draws a plot in its own right, so the menu can tell
   a single chart from one panel of a pack. `layer` is not a split --
   a layered chart is one panel -- but the concat keys are. */
function leafPanels(root) {
  const out = [];
  (function walk(node) {
    if (!node || typeof node !== "object") return;
    const ck = concatKeyOf(node);
    if (ck) { for (const c of node[ck]) walk(c); return; }
    if (node.spec) { walk(node.spec); return; }
    if (isTextPanelNode(node)) return;
    if (node.mark || Array.isArray(node.layer)) out.push(node);
  })(root);
  return out;
}

function temporalPanels(root) {
  const out = [];
  for (const p of leafPanels(root)) {
    const info = temporalPlotInfo(p);
    if (info) out.push({ node: p, info: info });
  }
  return out;
}

function buildAxisMenu(t, m) {
  const ch = t.channel;
  const cfgKey = ch === "y" ? "axisY" : "axisX";
  // Panels resolve their scales independently, so an edit aimed at one
  // of them has to stay inside it. A single-panel chart keeps the
  // document-wide write, where it is useful rather than surprising.
  const panels = leafPanels(currentSpec);
  const scopeNode = (panels.length > 1 && t.scope && t.scope.node &&
                     t.scope.node !== currentSpec) ? t.scope.node : null;
  const root = scopeNode || currentSpec;
  const readRoot = scopeNode || currentSpec;
  const info = temporalPlotInfo(root);

  if (ch === "x" && info) appendTimeWindowSection(t, m, root, info, scopeNode);
  if (ch === "y" && info) appendValueRangeSection(t, m, root, info);

  let ticks = currentTickCount(t, readRoot);
  m.appendChild(menuStepper("Number of ticks", String(ticks),
    () => { ticks = Math.max(2, ticks - 1); applyTickCount(t, ticks, scopeNode); return String(ticks); },
    () => { ticks = Math.min(40, ticks + 1); applyTickCount(t, ticks, scopeNode); return String(ticks); }));

  m.appendChild(menuSep());
  const curAngle = readAxisProp(ch, cfgKey, "labelAngle", readRoot);
  m.appendChild(menuChips("Label angle", [
    { label: "0\u00b0", value: 0 }, { label: "30\u00b0", value: -30 },
    { label: "45\u00b0", value: -45 }, { label: "90\u00b0", value: -90 },
  ], typeof curAngle === "number" ? curAngle : 0, v => {
    commitEdit("Label angle " + v + "\u00b0", () => {
      setBothAxisProperty(currentSpec, ch, cfgKey, "labelAngle", v, scopeNode);
      return true;
    });
  }));

  m.appendChild(menuSep());
  const gridOn = readAxisProp(ch, cfgKey, "grid", readRoot) !== false;
  m.appendChild(menuRow(gridOn ? "Hide gridlines" : "Show gridlines",
    gridOn ? "on" : "off", () => {
      commitEdit(gridOn ? "Gridlines off" : "Gridlines on", () => {
        setBothAxisProperty(currentSpec, ch, cfgKey, "grid", !gridOn, scopeNode);
        return true;
      });
    }, { on: gridOn }));

  const labelsOn = readAxisProp(ch, cfgKey, "labels", readRoot) !== false;
  m.appendChild(menuRow(labelsOn ? "Hide tick labels" : "Show tick labels",
    labelsOn ? "on" : "off", () => {
      commitEdit(labelsOn ? "Tick labels off" : "Tick labels on", () => {
        setBothAxisProperty(currentSpec, ch, cfgKey, "labels", !labelsOn, scopeNode);
        return true;
      });
    }, { on: labelsOn }));

  const domainOn = readAxisProp(ch, cfgKey, "domain", readRoot) !== false;
  m.appendChild(menuRow(domainOn ? "Hide axis line" : "Show axis line",
    domainOn ? "on" : "off", () => {
      commitEdit(domainOn ? "Axis line off" : "Axis line on", () => {
        setBothAxisProperty(currentSpec, ch, cfgKey, "domain", !domainOn, scopeNode);
        return true;
      });
    }, { on: domainOn }));

  m.appendChild(menuSep());
  // `format` means a d3 number pattern on a quantitative axis and a
  // strftime pattern on a temporal one, so offering ".0%" for a date
  // axis produces garbage. Branch on what the axis actually encodes.
  if (ch === "x" && info) {
    m.appendChild(menuChips("Date format", [
      { label: "2025", value: "%Y" }, { label: "Mar 25", value: "%b %y" },
      { label: "06 Mar", value: "%d %b" }, { label: "Mar 2025", value: "%b %Y" },
      { label: "09:30", value: "%H:%M" },
    ], readAxisProp(ch, cfgKey, "format", readRoot) || "", v => {
      commitEdit("Date format " + v, () => {
        setAxisEncodingProperty(root, ch, "format", v);
        setAxisEncodingProperty(root, ch, "formatType", "time");
        return true;
      });
    }));
  } else {
    m.appendChild(menuChips("Number format", [
      { label: "Auto", value: "" }, { label: "1,235", value: "," },
      { label: "1.2", value: ".1f" }, { label: "1.23", value: ".2f" },
      { label: "12%", value: ".0%" }, { label: "1.2k", value: ".2s" },
    ], readAxisProp(ch, cfgKey, "format", readRoot) || "", v => {
      commitEdit("Number format " + (v || "auto"), () => {
        setBothAxisProperty(currentSpec, ch, cfgKey, "format", v || undefined, scopeNode);
        return true;
      });
    }));
  }

  m.appendChild(menuSep());
  m.appendChild(menuRow("Rename axis title\u2026", "double-click", () => {
    const el = findAxisTitleEl(t.orient);
    if (el) beginInlineEdit(el);
    else cfsToast("This axis has no title to rename. Add one from Advanced controls.");
  }));
}

/* ---- the time-window rows on a temporal x axis ---- */
function appendTimeWindowSection(t, m, root, info, scopeNode) {
  const extent = dataExtent(info);
  if (!extent) return;
  const win = currentWindow(root, info);
  const active = activePresetLabel(root, info);

  const run = (label, lo, hi, target) => {
    commitEdit(label, () => {
      const nodes = target || [{ node: root, info: info }];
      let ok = 0, why = null;
      for (const n of nodes) {
        const r = applyTimeWindow(n.node, lo, hi, { info: n.info });
        if (r.ok) ok++; else why = r.reason;
      }
      if (!ok) { cfsToast("Could not window this chart: " + (why || "no data")); return false; }
      return true;
    });
  };

  const presets = windowPresetsFor(extent, dataCadence(info));
  if (presets.length > 1) {
    m.appendChild(menuChips("Time window",
      presets.map(p => ({ label: p.label, value: p.label })),
      active, v => {
        const p = CFS_WINDOW_PRESETS.filter(q => q.label === v)[0];
        const w = presetWindow(p, extent);
        run("Window: " + v, w[0], w[1]);
      }));
  }

  m.appendChild(menuDateRange("From / to",
    win ? formatSpecDate(win[0]).slice(0, 10) : "",
    win ? formatSpecDate(win[1]).slice(0, 10) : "",
    formatSpecDate(extent[0]).slice(0, 10),
    formatSpecDate(extent[1]).slice(0, 10),
    (a, b) => {
      const lo = parseSpecDate(a), hi = parseSpecDate(b);
      if (!lo || !hi) { cfsToast("Could not read those dates."); return; }
      run("Window: " + a + " to " + b, lo, hi);
    }));

  // Packs are usually read on a common timeline, but not always -- so
  // the scoped action stays primary and this sits beside it, the way a
  // recolour-every-series row sits beside a single-series recolour.
  if (scopeNode) {
    const all = temporalPanels(currentSpec);
    if (all.length > 1) {
      m.appendChild(menuRow("Apply this window to every panel", all.length + " panels", () => {
        const w = win || extent;
        run("Windowed all panels", w[0], w[1], all);
      }));
    }
  }
  m.appendChild(menuRow("Drag along this axis to pan", "hint", null, { disabled: true }));
  m.appendChild(menuSep());
}

/* ---- the range rows on a quantitative y axis ---- */
function appendValueRangeSection(t, m, root, info) {
  if (!info.yField) return;
  // A log or symlog axis cannot take the engine's linear domain arithmetic,
  // and zero is not even on it. Offering rows that could only ever toast an
  // error reads as breakage, so say why instead.
  if (nonLinearYScale(root, info.yField)) {
    m.appendChild(menuRow("Range fitting needs a linear axis",
                          yScaleTypeOf(root, info.yField) || "non-linear",
                          null, { disabled: true }));
    m.appendChild(menuSep());
    return;
  }
  m.appendChild(menuRow("Fit range to visible data", "auto", () => {
    commitEdit("Range fitted to view", () => {
      const r = refitYRange(root, { info: info });
      if (!r.ok) { cfsToast("Could not fit the range: " + r.reason); return false; }
      return true;
    });
  }));
  const dom = currentYDomain(root, info.yField);
  const atZero = Array.isArray(dom) && Number(dom[0]) <= 0 && Number(dom[1]) >= 0;
  m.appendChild(menuRow("Start range at zero", atZero ? "on" : "off", () => {
    commitEdit("Range starts at zero", () => {
      const r = refitYRange(root, { info: info, includeZero: true });
      if (!r.ok) { cfsToast("Could not fit the range: " + r.reason); return false; }
      return true;
    });
  }, { on: atZero }));
  m.appendChild(menuSep());
}

function currentTickCount(t, root) {
  const cfgKey = t.channel === "y" ? "axisY" : "axisX";
  const explicit = readAxisProp(t.channel, cfgKey, "tickCount", root);
  if (typeof explicit === "number") return explicit;
  // No explicit count: count what is actually on screen, so the first
  // nudge moves relative to what the user is looking at.
  const svg = document.querySelector("#chart svg");
  if (!svg) return 6;
  let best = 0;
  for (const g of svg.querySelectorAll("g.role-axis")) {
    const d = g.__data__ || (g.firstChild && g.firstChild.__data__);
    const orient = d && d.orient;
    const chan = axisChannelOf(orient);
    if (orient && chan !== t.channel) continue;
    const n = g.querySelectorAll("g.role-axis-label text, text.role-axis-label").length ||
              g.querySelectorAll("text").length;
    if (n > best) best = n;
  }
  return best > 1 ? best : 6;
}

function applyTickCount(t, n, scopeNode) {
  const cfgKey = t.channel === "y" ? "axisY" : "axisX";
  commitEdit("Ticks: " + n, () => {
    setBothAxisProperty(currentSpec, t.channel, cfgKey, "tickCount", n, scopeNode);
    return true;
  });
}

function readAxisProp(channel, cfgKey, prop, root) {
  let v;
  walkEncoding(root || currentSpec, channel, enc => {
    if (v === undefined && enc && enc.axis && typeof enc.axis === "object" &&
        enc.axis[prop] !== undefined) v = enc.axis[prop];
  });
  if (v === undefined) v = getPath(currentSpec, "config." + cfgKey + "." + prop);
  return v;
}

function findAxisTitleEl(orient) {
  const svg = document.querySelector("#chart svg");
  if (!svg) return null;
  for (const el of svg.querySelectorAll("text")) {
    const info = inspectTextNode(el);
    if (info.role === "axis-title" &&
        (!orient || info.axisOrient === orient)) return el;
  }
  return null;
}

function buildLegendMenu(t, m) {
  if (t.field && t.series != null) {
    const info = colorScaleInfo(t.field);
    const i = info.domain.indexOf(t.series);
    m.appendChild(menuSwatches("Colour of " + t.series, paletteColors(),
      i >= 0 ? info.colors[i] : null, c => {
        commitEdit("Recoloured " + t.series, () =>
          setSeriesColor(t.field, t.series, c));
      }));
    m.appendChild(menuSep());
  }

  const cur = readLegendProp("orient") || "right";
  m.appendChild(menuChips("Position", [
    { label: "Right", value: "right" }, { label: "Left", value: "left" },
    { label: "Top", value: "top" }, { label: "Bottom", value: "bottom" },
    { label: "Top-right", value: "top-right" },
  ], cur, v => {
    commitEdit("Legend " + v, () => {
      walkEncoding(currentSpec, "color", enc => {
        if (enc.legend === null) enc.legend = {};
        if (typeof enc.legend !== "object") enc.legend = {};
        enc.legend.orient = v;
      });
      return true;
    });
  }));

  m.appendChild(menuChips("Direction", [
    { label: "Vertical", value: "vertical" },
    { label: "Horizontal", value: "horizontal" },
  ], readLegendProp("direction") || "vertical", v => {
    commitEdit("Legend " + v, () => {
      walkEncoding(currentSpec, "color", enc => {
        if (typeof enc.legend !== "object" || enc.legend === null) enc.legend = {};
        enc.legend.direction = v;
      });
      return true;
    });
  }));

  m.appendChild(menuSep());
  m.appendChild(menuRow("Rename legend title\u2026", "double-click", () => {
    const el = findRoleEl("legend-title");
    if (el) beginInlineEdit(el);
    else cfsToast("This legend has no title to rename.");
  }));
  m.appendChild(menuRow("Hide the legend", null, () => {
    commitEdit("Legend hidden", () => {
      walkEncoding(currentSpec, "color", enc => { enc.legend = null; });
      return true;
    });
  }));
}

function readLegendProp(prop) {
  let v;
  walkEncoding(currentSpec, "color", enc => {
    if (v === undefined && enc && enc.legend && typeof enc.legend === "object" &&
        enc.legend[prop] !== undefined) v = enc.legend[prop];
  });
  return v;
}

function findRoleEl(role) {
  const svg = document.querySelector("#chart svg");
  if (!svg) return null;
  for (const el of svg.querySelectorAll("text")) {
    if (inspectTextNode(el).role === role) return el;
  }
  return null;
}

function buildAnnotationMenu(t, m) {
  const cur = normalizeColor((typeof t.node.mark === "object" &&
    (t.node.mark.color || t.node.mark.stroke)) || "#888888");
  m.appendChild(menuSwatches("Colour", paletteColors(), cur, c => {
    commitEdit("Annotation colour", () => {
      setMarkProp(t.node, "color", c);
      setMarkProp(t.node, "stroke", c);
      return true;
    });
  }));
  m.appendChild(menuSep());
  m.appendChild(menuChips("Line style",
    DASH_CHOICES.map(d => ({ label: d.label, value: d.label })), null, label => {
      const choice = DASH_CHOICES.find(d => d.label === label);
      commitEdit("Annotation " + label, () => {
        setMarkProp(t.node, "strokeDash", choice.value || undefined);
        return true;
      });
    }));
  m.appendChild(menuSep());
  m.appendChild(menuRow("Remove this annotation", null, () => {
    commitEdit("Annotation removed", () => removeNodeFromSpec(t.node));
  }));
}

/* Drop a layer out of whichever array holds it. */
function removeNodeFromSpec(target) {
  let removed = false;
  (function walk(n) {
    if (!n || typeof n !== "object" || removed) return;
    for (const k of ["layer", "concat", "hconcat", "vconcat"]) {
      if (!Array.isArray(n[k])) continue;
      const i = n[k].indexOf(target);
      if (i >= 0) { n[k].splice(i, 1); removed = true; return; }
      n[k].forEach(walk);
    }
    if (n.spec) walk(n.spec);
  })(currentSpec);
  if (!removed) cfsToast("That annotation is not a removable layer.");
  return removed;
}

function buildCanvasMenu(t, m) {
  const w = walkExtractSize(currentSpec, "width");
  const h = walkExtractSize(currentSpec, "height");
  // The seven PRISM-canonical presets only. The extras (report,
  // dashboard, widescreen, tile sizes) stay in Advanced -- a chart being
  // hand-finished for publication is going to one of these or to a
  // dragged size, and thirteen chips is a wall, not a choice.
  const sizes = Object.keys(DIM_PRESETS)
    .filter(k => DIM_PRESETS[k].prism || k === currentDimPreset)
    .map(k => ({ label: shortPresetLabel(k), value: k }));
  m.appendChild(menuChips("Size  (or drag the chart's edge)", sizes,
    currentDimPreset, v => {
      commitEdit("Size: " + v, () => { applyDimensionPreset(v, true); return true; });
    }));

  m.appendChild(menuSep());
  m.appendChild(menuRow("Edit the title\u2026", "double-click", () => {
    const el = findRoleEl("title-text");
    if (el) beginInlineEdit(el);
    else cfsToast("This chart has no title. Add one from Advanced controls.");
  }));
  m.appendChild(menuRow("Edit the subtitle\u2026", "double-click", () => {
    const el = findRoleEl("title-subtitle");
    if (el) beginInlineEdit(el);
    else cfsToast("This chart has no subtitle. Add one from Advanced controls.");
  }));

  m.appendChild(menuSep());
  m.appendChild(menuRow("Change the palette\u2026", currentPalette, () => {
    openPaletteMenu();
  }));
  m.appendChild(menuRow("Change the theme\u2026", currentTheme, () => {
    const r = menuRoot().getBoundingClientRect();
    openMenu(r.left, r.top, "Theme", "typography and framing", mm => {
      for (const [name, rec] of Object.entries(THEMES)) {
        mm.appendChild(menuRow(rec.label || name, null, () => {
          commitEdit("Theme: " + (rec.label || name), () => {
            applyTheme(name, true);
            return true;
          });
        }, { on: name === currentTheme }));
      }
    });
  }));

  m.appendChild(menuSep());
  m.appendChild(menuRow("Download this chart", "PNG", () => downloadChart()));
  m.appendChild(menuRow("Advanced controls\u2026",
    String(KNOBS.length), () => {
      const d = document.getElementById("knobsSection");
      if (d) { d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" }); }
    }));
}

/* ============================================================
   WIRING: one delegated listener, re-marked hit targets per render
   ============================================================ */
function onChartContextMenu(e) {
  const el = e.target;
  if (!el || !el.closest || !el.closest("#chart")) return;
  e.preventDefault();
  e.stopPropagation();
  closeInlineEditor();
  const t = resolveHitTarget(el);
  const x = e.clientX + window.scrollX;
  const y = e.clientY + window.scrollY;
  let sub = {
    axis: "ticks, labels, gridlines",
    legend: "position and entries",
    annotation: "colour, style, remove",
    canvas: "size, palette, theme",
  }[t.kind] || "";
  if (t.kind === "series") {
    sub = (t.field && t.series != null)
      ? ("this series only \u2014 " + (t.markType || "mark"))
      : ("every " + (t.markType || "mark") + " on the chart");
  }
  openMenu(x, y, t.title, sub, m => {
    if (t.kind === "series") buildSeriesMenu(t, m);
    else if (t.kind === "axis") buildAxisMenu(t, m);
    else if (t.kind === "legend") buildLegendMenu(t, m);
    else if (t.kind === "annotation") buildAnnotationMenu(t, m);
    else buildCanvasMenu(t, m);
  });
}

/* Advertise which glyphs answer a right-click, the same way the text
   pass advertises which answer a double-click. */
function wireHitTargets() {
  const svg = document.querySelector("#chart svg");
  if (!svg) return;
  const sel = "g.role-mark path, g.role-mark rect, g.role-mark symbol, " +
              "g.role-mark line, g.role-mark area, g.role-legend rect, " +
              "g.role-legend path, g.role-legend symbol";
  for (const el of svg.querySelectorAll(sel)) {
    const bb = el.getBBox ? el.getBBox() : null;
    if (bb && bb.width < 0.5 && bb.height < 0.5) continue;
    el.classList.add("cfs-hit");
  }
}

/* ============================================================
   DRAG TO RESIZE

   The obvious implementation -- vegaView.width() / .height(), which
   resize without recompiling the spec -- does not work on the specs
   PRISM emits. Every chart with a source strip or a caption is a
   vconcat, and vega-lite compiles those so the plot's height lives in a
   `concat_0_height` layout signal rather than the root `height`. Setting
   the root signal, or any of the concat signals, moves nothing; only
   width propagates, and then only on single-column charts. So the
   incremental path silently no-oped for the whole drag and the chart
   snapped to its new size on release.

   Recompiling the spec every frame is the honest alternative, and it is
   affordable: a full re-embed is ~5-13ms against a 16ms frame budget.
   What it needs is serialisation -- two vegaEmbed calls in flight on the
   same container leave a half-laid-out SVG -- so frames are coalesced
   behind the in-flight render rather than queued up behind it.

   The spec is mutated on every frame, but the undo snapshot is taken
   once at pointer-down, so a drag costs one undo entry, not hundreds.
   ============================================================ */
let _resize = null;
let _pan = null;
let _dragFrame = null;
let _dragRenderInFlight = false;
let _dragRenderQueued = false;
let _dragRenderTail = Promise.resolve();

/* Coalescing, not queueing: while a render is in flight later frames
   collapse into a single pending flag, so releasing the pointer never
   leaves a backlog of stale sizes to work through. _dragRenderTail lets
   the release handler wait for the last frame instead of racing it. */
/* The gesture supplies the per-frame spec write through _dragFrame; the
   loop only owns the coalescing. Returning false from the frame aborts
   without rendering, which is how a gesture that ended mid-flight stops
   the queue. */
function scheduleDragRender() {
  if (_dragRenderInFlight) { _dragRenderQueued = true; return; }
  _dragRenderInFlight = true;
  _dragRenderTail = new Promise(resolve => {
    requestAnimationFrame(() => {
      if (!_dragFrame || _dragFrame() === false) {
        _dragRenderInFlight = false;
        _dragRenderQueued = false;
        resolve();
        return;
      }
      renderChart({ light: true }).then(() => {
        _dragRenderInFlight = false;
        resolve();
        if (_dragRenderQueued) { _dragRenderQueued = false; scheduleDragRender(); }
      });
    });
  });
}

/* ---- fit the chart to the panel ---------------------------------------
   A composite, a facet grid or a presentation-sized single chart is
   routinely wider than the column the editor gives it, and a chart the
   user can only reach half of is not editable. Vega's SVG carries a
   viewBox, so shrinking the element's CSS box scales the drawing with no
   loss of crispness and without touching the spec -- the download still
   exports at the chart's real size.

   Width only. The page scrolls vertically anyway, and matching the panel
   on both axes would shrink a tall chart for no reason.
   ---------------------------------------------------------------------- */
let _fitEnabled = true;   // session-only; the toolbar button flips it
let _fitScale = 1;        // 1 means the chart is at its real size
let _fitFrozen = null;    // scale held still for the length of a drag

function chartAvailableWidth() {
  const panel = document.getElementById("chartPanel");
  if (!panel) return 0;
  const cs = getComputedStyle(panel);
  return panel.clientWidth -
    parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
}

/* The size vega laid the chart out at, which is the viewBox rather than
   the width attribute: once this function has scaled the element, the
   attribute still reads the natural size but the CSS box does not, and
   measuring the box instead would ratchet the chart smaller on every
   render. */
function naturalChartSize(svg) {
  const vb = (svg.getAttribute("viewBox") || "").trim().split(/[\s,]+/);
  if (vb.length === 4) {
    const w = parseFloat(vb[2]), h = parseFloat(vb[3]);
    if (w > 0 && h > 0) return { w: w, h: h };
  }
  const aw = parseFloat(svg.getAttribute("width"));
  const ah = parseFloat(svg.getAttribute("height"));
  return { w: aw > 0 ? aw : 0, h: ah > 0 ? ah : 0 };
}

function applyChartFit() {
  const svg = document.querySelector("#chart svg");
  if (!svg) return;
  const nat = naturalChartSize(svg);
  if (!(nat.w > 0 && nat.h > 0)) return;
  const avail = chartAvailableWidth();
  let scale;
  if (_fitFrozen !== null) scale = _fitFrozen;
  else if (!_fitEnabled || !(avail > 0)) scale = 1;
  else scale = Math.min(1, avail / nat.w);
  _fitScale = scale;
  if (scale >= 1) {
    svg.style.width = "";
    svg.style.height = "";
  } else {
    // Floor rather than round: a half-pixel over the panel is enough to
    // put the scrollbar back, which is the thing being fixed.
    svg.style.width = Math.floor(nat.w * scale) + "px";
    svg.style.height = Math.floor(nat.h * scale) + "px";
  }
  updateFitButton(nat.w, avail);
  updateSizeSummary();
}

/* The button is the escape hatch, so it only exists when there is
   something to escape from -- on a chart that already fits, both modes
   render identically. */
function updateFitButton(naturalWidth, avail) {
  const btn = document.getElementById("fitBtn");
  if (!btn) return;
  btn.classList.toggle("hidden", !(naturalWidth > avail + 1));
  btn.textContent = _fitEnabled ? "Actual size" : "Fit to panel";
  btn.title = _fitEnabled
    ? "Show the chart at 100%; the panel will scroll"
    : "Scale the chart down so all of it is visible. Its real size, and "
      + "the size it downloads at, do not change.";
}

function toggleChartFit() {
  _fitEnabled = !_fitEnabled;
  applyChartFit();
  syncChartFrame();
  syncSidebarHeight();
  cfsToast(_fitEnabled
    ? "Fitted to the panel. The chart's real size is unchanged."
    : "Showing the chart at 100%. Scroll the panel to reach the rest.");
}

/* Collapse the wrapper onto the rendered SVG so the frame and its three
   handles sit on the chart's own edge. Vega picks the SVG's size from the
   spec plus whatever the axes and legend need, so the only reliable
   source is the rendered box -- re-measured after every render. */
function syncChartFrame() {
  const wrap = document.getElementById("chartWrap");
  const svg = document.querySelector("#chart svg");
  if (!wrap || !svg) return;
  const box = svg.getBoundingClientRect();
  if (box.width < 1 || box.height < 1) return;
  wrap.style.width = Math.ceil(box.width) + "px";
  wrap.style.height = Math.ceil(box.height) + "px";
}

function installResizeGrips() {
  const wrap = document.getElementById("chartWrap");
  if (!wrap) return;
  for (const g of wrap.querySelectorAll(".cfs-grip")) {
    g.addEventListener("pointerdown", e => beginResize(e, g.dataset.grip));
  }
}

function beginResize(e, mode) {
  e.preventDefault();
  const w = walkExtractSize(currentSpec, "width");
  const h = walkExtractSize(currentSpec, "height");
  if (typeof w !== "number" || typeof h !== "number") {
    cfsToast("This chart has no explicit size to drag; use Advanced controls.");
    return;
  }
  // Hold the fit still for the gesture. Re-fitting on every frame would
  // pin the frame to the panel edge and the chart would appear not to
  // respond at all; frozen, the edge tracks the pointer and the release
  // render settles it back into the panel.
  _fitFrozen = _fitScale;
  _resize = {
    mode: mode, x0: e.clientX, y0: e.clientY, w0: w, h0: h, w: w, h: h,
    // Snapshot up front: the spec is rewritten on every frame, so by
    // release there is no pre-drag state left to capture.
    undoEntry: pushUndo("Resize"),
  };
  _dragFrame = () => {
    const r = _resize;
    if (!r) return false;
    if (r.mode !== "s") walkSetSize(currentSpec, "width", r.w);
    if (r.mode !== "e") walkSetSize(currentSpec, "height", r.h);
    return true;
  };
  document.body.classList.add("cfs-resizing");
  e.target.classList.add("cfs-live");
  closeMenu();
  const tag = document.getElementById("cfsSizeTag");
  if (tag) tag.classList.add("on");
  window.addEventListener("pointermove", onResizeMove);
  window.addEventListener("pointerup", endResize, { once: true });
}

function onResizeMove(e) {
  if (!_resize) return;
  const r = _resize;
  // A pointer travelling one screen pixel across a chart drawn at 80%
  // is worth 1.25 chart pixels, so the delta is read back through the
  // frozen scale before it reaches the spec.
  const s = (_fitFrozen && _fitFrozen > 0) ? _fitFrozen : 1;
  if (r.mode !== "s") r.w = Math.max(160, Math.round(r.w0 + (e.clientX - r.x0) / s));
  if (r.mode !== "e") r.h = Math.max(100, Math.round(r.h0 + (e.clientY - r.y0) / s));
  const tag = document.getElementById("cfsSizeTag");
  if (tag) {
    tag.textContent = r.w + " x " + r.h + "  (" + (r.w / r.h).toFixed(2) + ")";
    tag.style.left = (e.clientX + 16) + "px";
    tag.style.top = (e.clientY + 16) + "px";
  }
  // The frame is re-measured off the real SVG by syncChartFrame after each
  // render rather than extrapolated from the pointer delta: axis labels and
  // legends reflow as the plot resizes, so the box and the spec size do not
  // move in lockstep.
  r.moved = true;
  scheduleDragRender();
}

/* Discard a drag's pointer-down snapshot when the gesture turned out not to
   change anything. Guarded on identity because an edit made from a context
   menu mid-drag would have pushed a later entry that must not be eaten. */
function dropResizeUndo(r) {
  if (!r || !r.undoEntry) return;
  if (_undoStack[_undoStack.length - 1] !== r.undoEntry) return;
  _undoStack.pop();
  updateUndoButton();
}

function endResize() {
  window.removeEventListener("pointermove", onResizeMove);
  const r = _resize;
  _resize = null;
  _dragFrame = null;
  _dragRenderQueued = false;
  // Hand the fit back to the panel; the render below settles the new size
  // into it. Released before the early returns so an aborted gesture does
  // not leave the chart pinned at the drag's scale.
  _fitFrozen = null;
  document.body.classList.remove("cfs-resizing");
  for (const g of document.querySelectorAll(".cfs-grip.cfs-live")) {
    g.classList.remove("cfs-live");
  }
  const tag = document.getElementById("cfsSizeTag");
  if (tag) tag.classList.remove("on");
  if (!r) return;
  const netChange = !(r.w === r.w0 && r.h === r.h0);
  // A grip click that never moved is not an edit, and nothing was rendered,
  // so there is nothing to clean up beyond the snapshot.
  if (!r.moved) {
    dropResizeUndo(r);
    return;
  }
  // Dragging out and back to the starting size is also not an edit, but the
  // spec was rewritten and re-rendered on the way, so the full render still
  // has to run to rewire the targets the light frames skipped.
  const label = netChange ? ("Resized to " + r.w + " x " + r.h)
                          : ("Size unchanged: " + r.w + " x " + r.h);
  // The last drag frame may have been coalesced away, so write the final
  // size unconditionally rather than trusting the render loop to have
  // landed on it.
  if (r.mode !== "s") walkSetSize(currentSpec, "width", r.w);
  if (r.mode !== "e") walkSetSize(currentSpec, "height", r.h);
  if (r.mode !== "s") retuneWindowedTicks();
  if (netChange) {
    if (r.mode !== "s") {
      currentKnobValues["width"] = r.w;
      overrides["width"] = r.w;
    }
    if (r.mode !== "e") {
      currentKnobValues["height"] = r.h;
      overrides["height"] = r.h;
    }
    currentDimPreset = "custom";
    const sel = document.getElementById("dimPresetSelect");
    if (sel) sel.value = "custom";
    if (r.undoEntry) r.undoEntry.label = label;
    updateUndoButton();
  } else {
    dropResizeUndo(r);
  }
  // Full render: the drag ran on light frames, so text and hit targets are
  // unwired and the side tabs still describe the pre-drag size. Wait for any
  // frame still in flight -- a second vegaEmbed on the same container mid
  // render leaves a collapsed SVG behind.
  const finish = () => {
    renderChart();
    updateTextAreas();
    updateSizeSummary();
    setStatus(label);
  };
  if (_dragRenderInFlight) _dragRenderTail.then(finish);
  else finish();
}

/* ============================================================
   DRAG TO PAN A TIME AXIS

   Same shape as the resize drag -- one undo snapshot at pointer-down,
   coalesced light frames, a full render on release -- but it does not
   claim the pointer on the way down. A single click on a date label
   still has to open the context menu, and a double-click still has to
   start an inline rename, so the gesture only commits to panning once
   the pointer has actually travelled.

   The window is translated, never rescaled: the span stays fixed and
   both edges move together, stopping against the data's own extent so
   a drag cannot run off into empty space.
   ============================================================ */

/* The rendered plot width in CSS pixels. Vega sizes the SVG from the
   spec plus whatever the axes and legend need, so the spec width is
   the plot rect only if nothing has scaled it -- measure the axis the
   pointer is on instead, and keep the spec value for when there is no
   rendered geometry to read (the parity harness drives this headless). */
function measuredAxisWidth(orient, fallback) {
  const svg = document.querySelector("#chart svg");
  if (svg) {
    for (const g of svg.querySelectorAll("g.role-axis")) {
      const d = g.__data__ || (g.firstChild && g.firstChild.__data__);
      if (d && d.orient && d.orient !== orient) continue;
      const line = g.querySelector("line.background, path.background, line.domain");
      const box = (line || g).getBoundingClientRect();
      if (box.width >= 1) return box.width;
    }
  }
  return fallback;
}

function beginPan(e) {
  if (e.button !== 0 || _pan || _resize) return;
  const t = resolveHitTarget(e.target);
  if (!t || t.kind !== "axis" || t.channel !== "x") return;
  const panels = leafPanels(currentSpec);
  const scopeNode = (panels.length > 1 && t.scope && t.scope.node &&
                     t.scope.node !== currentSpec) ? t.scope.node : null;
  const root = scopeNode || currentSpec;
  const info = temporalPlotInfo(root);
  if (!info) return;
  const extent = dataExtent(info);
  const win = currentWindow(root, info);
  if (!extent || !win) return;
  const width = measuredAxisWidth(t.orient, info.width);
  if (!(width > 0)) return;
  const span = win[1].getTime() - win[0].getTime();
  if (!(span > 0)) return;

  _pan = {
    root: root, info: info,
    eLo: extent[0].getTime(), eHi: extent[1].getTime(),
    lo0: win[0].getTime(), span: span,
    lo: win[0].getTime(), hi: win[1].getTime(),
    x0: e.clientX, msPerPx: span / width,
    started: false, undoEntry: null,
  };
  window.addEventListener("pointermove", onPanMove);
  window.addEventListener("pointerup", endPan, { once: true });
  window.addEventListener("pointercancel", endPan, { once: true });
}

function onPanMove(e) {
  const p = _pan;
  if (!p) return;
  const dx = e.clientX - p.x0;
  if (!p.started) {
    // Below the threshold this is still a click or the start of a
    // double-click, and neither should have moved the window.
    if (Math.abs(dx) < 4) return;
    p.started = true;
    p.undoEntry = pushUndo("Pan");
    closeMenu();
    document.body.classList.add("cfs-resizing");
    const tag = document.getElementById("cfsSizeTag");
    if (tag) tag.classList.add("on");
    _dragFrame = () => {
      const q = _pan;
      if (!q || !q.started) return false;
      return applyTimeWindow(q.root, new Date(q.lo), new Date(q.hi),
                             { info: q.info }).ok !== false;
    };
  }
  // Grab-and-drag: pulling the axis right brings earlier data into view.
  let lo = p.lo0 - dx * p.msPerPx;
  let hi = lo + p.span;
  if (lo < p.eLo) { lo = p.eLo; hi = lo + p.span; }
  if (hi > p.eHi) { hi = p.eHi; lo = Math.max(hi - p.span, p.eLo); }
  p.lo = lo; p.hi = hi;
  const tag = document.getElementById("cfsSizeTag");
  if (tag) {
    tag.textContent = formatSpecDate(new Date(lo)).slice(0, 10) + "  \u2192  " +
                      formatSpecDate(new Date(hi)).slice(0, 10);
    tag.style.left = (e.clientX + 16) + "px";
    tag.style.top = (e.clientY + 16) + "px";
  }
  scheduleDragRender();
}

function endPan() {
  window.removeEventListener("pointermove", onPanMove);
  const p = _pan;
  _pan = null;
  _dragFrame = null;
  _dragRenderQueued = false;
  document.body.classList.remove("cfs-resizing");
  const tag = document.getElementById("cfsSizeTag");
  if (tag) tag.classList.remove("on");
  // Never crossed the threshold, so nothing was snapshotted or drawn and
  // the click is still free to become a menu or a rename.
  if (!p || !p.started) return;

  const label = "Window: " + formatSpecDate(new Date(p.lo)).slice(0, 10) +
                " to " + formatSpecDate(new Date(p.hi)).slice(0, 10);
  // The last frame may have been coalesced away, so write the final
  // window unconditionally rather than trusting the loop to have
  // landed on it.
  const res = applyTimeWindow(p.root, new Date(p.lo), new Date(p.hi), { info: p.info });
  if (!res.ok) dropResizeUndo(p);
  else if (p.undoEntry) { p.undoEntry.label = label; updateUndoButton(); }

  const finish = () => {
    renderChart();
    updateTextAreas();
    updateSizeSummary();
    syncDomainKnobs();
    setStatus(res.ok ? label : ("Pan failed: " + res.reason));
  };
  if (_dragRenderInFlight) _dragRenderTail.then(finish);
  else finish();
}

/* ============================================================
   RENDER + SUMMARY
   ============================================================ */
/* Deliberately does NOT close the context menu. Steppers (tick count,
   line thickness, opacity) re-render on every nudge, and a menu that
   vanished after the first click would make the iterative case
   unusable. Menu targets hold spec nodes, not DOM nodes, so they stay
   valid across a re-render -- the two paths that REPLACE currentSpec,
   undo and reset, close the menu themselves. */
/* Returns the embed promise so callers that must not overlap renders --
   the resize drag, which fires one per animation frame -- can wait for the
   SVG to actually exist before starting the next. Overlapping vegaEmbed
   calls on one container leave a half-laid-out SVG behind.

   opts.light strips a drag frame down to the embed itself: re-wiring text
   and hit targets walks every node in the scenegraph, and the Data / Code /
   Metadata tabs re-serialise the whole spec. Neither is observable while
   the pointer is down, and both run again on release. */
function renderChart(opts) {
  opts = opts || {};
  closeInlineEditor();
  const done = vegaEmbed("#chart", currentSpec, { renderer: "svg", actions: false })
    .then(r => {
      vegaView = r.view;
      // Fit before the frame is measured: the frame traces the SVG's box,
      // and the fit is what decides how big that box is.
      applyChartFit();
      syncChartFrame();
      if (opts.light) return;
      wireTextTargets();
      wireHitTargets();
      // After the chart has been laid out, sync the sidebar height so the
      // info tabs never extend past the bottom of the chart panel.
      requestAnimationFrame(() => {
        applyChartFit(); syncChartFrame(); syncSidebarHeight();
      });
    })
    .catch(err => { setStatus("render error: " + err.message); });
  if (!opts.light) {
    // Refresh dependent tabs whenever chart changes
    try { refreshDependentTabs(); } catch (e) { /* tabs not yet initialized */ }
  }
  return done;
}

function refreshDependentTabs() {
  if (typeof renderDataTable === "function") renderDataTable();
  if (typeof renderCodeTab === "function") renderCodeTab();
  if (typeof renderMetadata === "function") renderMetadata();
}

/* ============================================================
   SIDEBAR HEIGHT SYNC
   Cap the info sidebar to the chart panel's height so the
   knob cards below the chart stay visible.
   ============================================================ */
function syncSidebarHeight() {
  const chartPanel = document.getElementById("chartPanel");
  const sidebar = document.getElementById("sidebarPanel");
  if (!chartPanel || !sidebar) return;
  if (sidebar.classList.contains("hidden")) return;
  const h = chartPanel.getBoundingClientRect().height;
  if (h > 0) {
    sidebar.style.height = h + "px";
    sidebar.style.maxHeight = h + "px";
  }
}

let _sidebarResizeObserver = null;
let _lastFitWidth = null;
let _viewportSyncQueued = false;

/* Re-fit only when the panel actually got wider or narrower. The observer
   also fires for the height change the fit itself causes, and refitting on
   that would be a loop. */
function onPanelResized() {
  const w = chartAvailableWidth();
  if (_lastFitWidth === null || Math.abs(w - _lastFitWidth) >= 1) {
    _lastFitWidth = w;
    applyChartFit();
    syncChartFrame();
  }
  syncSidebarHeight();
}

function onViewportResized() {
  if (_viewportSyncQueued) return;
  _viewportSyncQueued = true;
  requestAnimationFrame(() => {
    _viewportSyncQueued = false;
    _lastFitWidth = chartAvailableWidth();
    applyChartFit();
    syncChartFrame();
    syncSidebarHeight();
  });
}

function installSidebarHeightObserver() {
  const chartPanel = document.getElementById("chartPanel");
  if (!chartPanel) return;
  if (typeof ResizeObserver !== "undefined" && !_sidebarResizeObserver) {
    _sidebarResizeObserver = new ResizeObserver(onPanelResized);
    _sidebarResizeObserver.observe(chartPanel);
  }
  window.addEventListener("resize", onViewportResized);
}

function updateSizeSummary() {
  const w = currentKnobValues["width"] ?? "?";
  const h = currentKnobValues["height"] ?? "?";
  const pad = currentKnobValues["padding"] ?? 0;
  const autosize = currentKnobValues["autosize"] ?? "pad";
  const preset = currentDimPreset ?? "custom";
  const ratio = (w !== "?" && h !== "?") ? (w / h).toFixed(2) : "?";
  // The width / height reported are always the chart's real ones; the zoom
  // is appended so a scaled-down view never reads as a smaller chart.
  const zoom = _fitScale < 0.999
    ? "  zoom=" + Math.round(_fitScale * 100) + "%" : "";
  document.getElementById("sizeSummary").textContent =
    "width=" + w + "  height=" + h + "  aspect=" + ratio + "  padding=" + pad + "  autosize=" + autosize + "  preset=" + preset + zoom;
}

/* ============================================================
   EXPORT
   ============================================================ */
/* The one download the toolbar offers. 2x matches what chart_functions
   renders server-side, so a chart downloaded here and the same chart
   downloaded from PRISM are the same asset apart from the edits. */
function downloadChart() {
  if (!vegaView) { cfsToast("The chart is still rendering."); return; }
  closeMenu();
  vegaView.toImageURL("png", 2)
    .then(url => {
      downloadURL(url, FILENAME + ".png");
      setStatus("downloaded " + FILENAME + ".png");
    })
    .catch(err => cfsToast("Download failed: " + err.message));
}

function exportPNG(scale) {
  scale = scale || 2;
  if (!vegaView) return;
  const suffix = scale === 2 ? "" : "_" + scale + "x";
  vegaView.toImageURL("png", scale).then(url => downloadURL(url, FILENAME + suffix + ".png"));
}

function exportSVG() {
  if (!vegaView) return;
  vegaView.toSVG().then(svg => {
    const blob = new Blob([svg], { type: "image/svg+xml" });
    downloadURL(URL.createObjectURL(blob), FILENAME + ".svg");
  });
}

function exportSpec() {
  const blob = new Blob([JSON.stringify(currentSpec, null, 2)], { type: "application/json" });
  downloadURL(URL.createObjectURL(blob), FILENAME + "_spec.json");
}

function exportOverrides() {
  const payload = {
    theme: currentTheme,
    palette: currentPalette,
    dimensionPreset: currentDimPreset,
    spec_sheet: currentSpecSheet,
    overrides: overrides,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  downloadURL(URL.createObjectURL(blob), FILENAME + "_overrides.json");
}

function exportStandaloneHTML() {
  // Capture current doc + inject current state as the INITIAL_* constants
  const snapshotSpec = deepClone(currentSpec);
  const snapshotSheet = (currentSpecSheet !== "(none)" && specSheets[currentSpecSheet])
    ? specSheets[currentSpecSheet]
    : buildSpecSheetObject("(snapshot " + new Date().toISOString() + ")");
  let html = document.documentElement.outerHTML;
  // Replace the ORIGINAL_SPEC constant in the script with the current spec
  // Replace INITIAL_OVERRIDES/SHEETS with current state. We do this via string
  // replacement of the const assignments.
  html = html.replace(/const\s+ORIGINAL_SPEC\s*=\s*[^;]+;/,
    "const ORIGINAL_SPEC = " + JSON.stringify(snapshotSpec) + ";");
  html = html.replace(/const\s+INITIAL_OVERRIDES\s*=\s*[^;]+;/,
    "const INITIAL_OVERRIDES = " + JSON.stringify(overrides) + ";");
  html = html.replace(/const\s+INITIAL_SPEC_SHEETS\s*=\s*[^;]+;/,
    "const INITIAL_SPEC_SHEETS = " + JSON.stringify(specSheets) + ";");
  html = html.replace(/const\s+INITIAL_ACTIVE_SHEET\s*=\s*[^;]+;/,
    "const INITIAL_ACTIVE_SHEET = \"" + currentSpecSheet + "\";");
  const blob = new Blob([html], { type: "text/html" });
  downloadURL(URL.createObjectURL(blob), FILENAME + "_snapshot.html");
  setStatus("snapshot exported");
}

function openInVegaEditor() {
  const base = "https://vega.github.io/editor/#/edited";
  const payload = {
    mode: "vega-lite",
    spec: JSON.stringify(currentSpec, null, 2),
  };
  // Vega editor uses hash-based routing with URL-encoded JSON
  const url = "https://vega.github.io/editor/#/url/vega-lite/" + encodeURIComponent(btoa(JSON.stringify(currentSpec)));
  window.open(url, "_blank");
}

function downloadURL(url, filename) {
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
}

function downloadBlob(text, filename, mime) {
  const blob = new Blob([text], { type: mime });
  downloadURL(URL.createObjectURL(blob), filename);
}

function copyText(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(
    () => setStatus("copied to clipboard"),
    (err) => setStatus("copy failed: " + err.message)
  );
}

function downloadText(elementId, filename, mime) {
  const el = document.getElementById(elementId);
  if (!el) return;
  downloadBlob(el.textContent, filename, mime || "text/plain");
}

/* ============================================================
   VIEW CONTROLS
   ============================================================ */
/* Reset means "the chart as PRISM handed it over" -- every in-place
   edit, right-click change and drag discarded in one step. The whole
   pre-reset spec goes on the undo stack so this is not a trapdoor. */
function resetView() {
  closeMenu();
  pushUndo("Reset to original");
  currentSpec = deepClone(ORIGINAL_SPEC);
  _textJournal = [];
  overrides = {};
  currentTheme = INITIAL_THEME;
  currentPalette = INITIAL_PALETTE;
  populateKnobValuesFromSpec();
  currentDimPreset = detectDimPresetFromSpec();
  initializeKnobs();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
  syncSelectors();
  setStatus("reset to the original chart");
  cfsToast("Back to the chart as PRISM built it. Undo brings your edits back.");
}

function toggleFullscreen() {
  const layout = document.getElementById("mainLayout");
  const sidebar = document.getElementById("sidebarPanel");
  const knobs = document.getElementById("knobsSection");
  const btn = document.getElementById("fullscreenBtn");
  if (sidebar.classList.contains("hidden")) {
    sidebar.classList.remove("hidden");
    knobs.classList.remove("hidden");
    // Back to the stylesheet's responsive pair rather than a hard 440px.
    layout.style.gridTemplateColumns = "";
    btn.textContent = "Fullscreen";
  } else {
    sidebar.classList.add("hidden");
    knobs.classList.add("hidden");
    layout.style.gridTemplateColumns = "1fr";
    btn.textContent = "Exit fullscreen";
  }
  // The chart's share of the window just changed by 440-odd pixels, which
  // is usually the difference between needing the fit and not.
  requestAnimationFrame(onViewportResized);
}

/* ============================================================
   TABS
   ============================================================ */
function switchTab(tabName) {
  const tabs = document.querySelectorAll(".tab-content");
  for (const t of tabs) t.classList.add("hidden");
  const active = document.getElementById("tab-" + tabName);
  if (active) active.classList.remove("hidden");
  const btns = document.querySelectorAll(".tab-button");
  for (const b of btns) b.classList.remove("active");
  const activeBtn = document.querySelector('.tab-button[data-tab="' + tabName + '"]');
  if (activeBtn) activeBtn.classList.add("active");
  // Re-render content on switch (cheap, ensures latest state)
  if (tabName === "data") { renderDataTable(); }
  else if (tabName === "code") { renderCodeTab(); }
  else if (tabName === "metadata") { renderMetadata(); }
}

function switchCodeSubtab(name) {
  for (const pane of document.querySelectorAll(".code-pane")) pane.classList.add("hidden");
  const p = document.getElementById("code-" + name);
  if (p) p.classList.remove("hidden");
  for (const b of document.querySelectorAll(".code-sub-btn")) b.classList.remove("active");
  const btn = document.querySelector('.code-sub-btn[data-codetab="' + name + '"]');
  if (btn) btn.classList.add("active");
  renderCodeTab();
}

/* ============================================================
   DATA TAB: extraction, table, sort, filter, stats

   Specs may carry data in multiple places:
     - top-level spec.data.values (single-view spec)
     - any layer / concat panel inline data.values
     - top-level spec.datasets pool (named datasets, referenced by
       layers via data: {name: ...})
   PRISM annotation layers each create a tiny named dataset (1 row),
   so we collect ALL data sources and default to the largest one
   (which is reliably the chart's data, not an annotation marker).
   The Data tab dropdown lets the user inspect any of them.
   ============================================================ */
let _dataRows = [];           // cached data rows (currently-displayed source)
let _dataColumns = [];        // cached column names
let _sortColumn = null;
let _sortAscending = true;
let _dataSources = [];        // [{label, rows}, ...] sorted by row count desc
let _currentDataSourceIdx = 0;

function collectAllDataSources(spec) {
  // Walk the entire spec tree, collecting every inline data.values it sees,
  // plus every named dataset in the top-level datasets pool. Returns a list
  // of {label, rows} sorted by row count descending.
  const sources = [];
  const seen = new WeakSet();

  function walk(node, path) {
    if (!node || typeof node !== "object" || seen.has(node)) return;
    seen.add(node);
    if (node.data && Array.isArray(node.data.values)) {
      sources.push({
        label: path,
        rows: node.data.values,
      });
    }
    for (const key of ["layer", "hconcat", "vconcat", "concat"]) {
      if (Array.isArray(node[key])) {
        node[key].forEach((child, i) => walk(child, `${path} > ${key}[${i}]`));
      }
    }
    if (node.spec) walk(node.spec, `${path} > spec`);
  }
  walk(spec, "main");

  if (spec && typeof spec === "object" && spec.datasets) {
    for (const [name, vals] of Object.entries(spec.datasets)) {
      if (Array.isArray(vals)) {
        // Named datasets are typically auto-hashed by altair (e.g.
        // "data-ab12cd..."). Show a friendlier label.
        sources.push({ label: "dataset: " + name.slice(0, 18), rows: vals });
      }
    }
  }

  // Largest first so the chart's main series wins by default over
  // 1-row annotation markers.
  sources.sort((a, b) => b.rows.length - a.rows.length);
  return sources;
}

function refreshDataCache() {
  _dataSources = collectAllDataSources(currentSpec);
  if (_currentDataSourceIdx >= _dataSources.length) _currentDataSourceIdx = 0;
  populateDataSourceSelect();
  const src = _dataSources[_currentDataSourceIdx];
  _dataRows = src ? src.rows.slice() : [];
  if (_dataRows.length > 0) {
    const colSet = new Set();
    for (const row of _dataRows) {
      if (row && typeof row === "object") {
        for (const k of Object.keys(row)) colSet.add(k);
      }
    }
    _dataColumns = Array.from(colSet);
  } else {
    _dataColumns = [];
  }
}

function populateDataSourceSelect() {
  const sel = document.getElementById("dataSourceSelect");
  if (!sel) return;
  if (_dataSources.length <= 1) {
    sel.style.display = "none";
    return;
  }
  sel.style.display = "";
  sel.innerHTML = "";
  _dataSources.forEach((src, i) => {
    const opt = document.createElement("option");
    opt.value = String(i);
    const rowCount = src.rows.length;
    const colCount = (src.rows[0] && typeof src.rows[0] === "object")
      ? Object.keys(src.rows[0]).length : 0;
    opt.textContent = `${rowCount}r x ${colCount}c -- ${src.label}`;
    sel.appendChild(opt);
  });
  sel.value = String(_currentDataSourceIdx);
}

function onDataSourceChange() {
  const sel = document.getElementById("dataSourceSelect");
  if (!sel) return;
  _currentDataSourceIdx = parseInt(sel.value, 10) || 0;
  _sortColumn = null;
  _sortAscending = true;
  renderDataTable();
}

function renderDataTable() {
  refreshDataCache();
  const container = document.getElementById("dataTableContainer");
  if (!container) return;
  if (_dataRows.length === 0) {
    container.innerHTML = "<p style='color:#888;'>(No inline data in this spec.)</p>";
    document.getElementById("dataSummaryLine").textContent = "";
    return;
  }

  const rows = _sortedRows();
  const table = document.createElement("table");
  table.className = "data-table";
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  const idxTh = document.createElement("th");
  idxTh.textContent = "#";
  headerRow.appendChild(idxTh);
  for (const col of _dataColumns) {
    const th = document.createElement("th");
    th.textContent = col;
    th.onclick = () => {
      if (_sortColumn === col) _sortAscending = !_sortAscending;
      else { _sortColumn = col; _sortAscending = true; }
      renderDataTable();
    };
    if (_sortColumn === col) th.className = _sortAscending ? "sort-asc" : "sort-desc";
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (let i = 0; i < rows.length; i++) {
    const tr = document.createElement("tr");
    const idxTd = document.createElement("td");
    idxTd.textContent = (i + 1);
    tr.appendChild(idxTd);
    for (const col of _dataColumns) {
      const td = document.createElement("td");
      const v = rows[i][col];
      td.textContent = v === undefined || v === null ? "" : String(v);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);

  container.innerHTML = "";
  container.appendChild(table);
  document.getElementById("dataSummaryLine").textContent =
    "Rows: " + _dataRows.length + " | Columns: " + _dataColumns.length;
}

function _sortedRows() {
  const rows = _dataRows.slice();
  if (!_sortColumn) return rows;
  rows.sort((a, b) => {
    const av = a[_sortColumn];
    const bv = b[_sortColumn];
    if (av === undefined || av === null) return 1;
    if (bv === undefined || bv === null) return -1;
    if (typeof av === "number" && typeof bv === "number") {
      return _sortAscending ? av - bv : bv - av;
    }
    return _sortAscending
      ? String(av).localeCompare(String(bv))
      : String(bv).localeCompare(String(av));
  });
  return rows;
}

function filterDataTable(query) {
  const q = (query || "").toLowerCase().trim();
  const rows = document.querySelectorAll("#dataTableContainer tbody tr");
  let visible = 0;
  for (const tr of rows) {
    if (!q) { tr.classList.remove("filtered-out"); visible++; continue; }
    if (tr.textContent.toLowerCase().includes(q)) {
      tr.classList.remove("filtered-out"); visible++;
    } else {
      tr.classList.add("filtered-out");
    }
  }
  document.getElementById("dataSummaryLine").textContent =
    "Rows: " + visible + " of " + _dataRows.length + " | Columns: " + _dataColumns.length;
}

function downloadDataCSV() {
  refreshDataCache();
  if (_dataRows.length === 0) { setStatus("no data to download"); return; }
  const lines = [_dataColumns.join(",")];
  for (const row of _dataRows) {
    lines.push(_dataColumns.map(c => _csvCell(row[c])).join(","));
  }
  downloadBlob(lines.join("\n"), FILENAME + ".csv", "text/csv");
}

function downloadDataTSV() {
  refreshDataCache();
  if (_dataRows.length === 0) { setStatus("no data to download"); return; }
  const lines = [_dataColumns.join("\t")];
  for (const row of _dataRows) {
    lines.push(_dataColumns.map(c => {
      const v = row[c]; return v === undefined || v === null ? "" : String(v);
    }).join("\t"));
  }
  downloadBlob(lines.join("\n"), FILENAME + ".tsv", "text/tab-separated-values");
}

function downloadDataJSON() {
  refreshDataCache();
  if (_dataRows.length === 0) { setStatus("no data to download"); return; }
  downloadBlob(JSON.stringify(_dataRows, null, 2), FILENAME + "_data.json", "application/json");
}

function _csvCell(v) {
  if (v === undefined || v === null) return "";
  const s = String(v);
  if (/[",\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

function copyDataAsMarkdown() {
  refreshDataCache();
  if (_dataRows.length === 0) { setStatus("no data"); return; }
  const hdr = "| " + _dataColumns.join(" | ") + " |";
  const sep = "| " + _dataColumns.map(() => "---").join(" | ") + " |";
  const rows = _dataRows.map(row =>
    "| " + _dataColumns.map(c => {
      const v = row[c]; return v === undefined || v === null ? "" : String(v);
    }).join(" | ") + " |"
  );
  const md = [hdr, sep, ...rows].join("\n");
  navigator.clipboard.writeText(md).then(
    () => setStatus("copied markdown to clipboard"),
    (err) => setStatus("copy failed: " + err.message)
  );
}

/* ============================================================
   CODE TAB: vega-lite / altair / data codegen
   ============================================================ */
function renderCodeTab() {
  const vlEl = document.getElementById("vegaLiteCode");
  const altairEl = document.getElementById("altairCode");
  const dataEl = document.getElementById("dataCode");
  if (vlEl) vlEl.textContent = JSON.stringify(currentSpec, null, 2);
  if (altairEl) altairEl.textContent = generateAltairCode(currentSpec);
  if (dataEl) dataEl.textContent = generateDataCode(currentSpec);
}

function _largestDataset(spec) {
  // Return the rows of the largest data source in the spec (the chart's
  // main data, not annotation markers). Used by codegen below.
  const sources = collectAllDataSources(spec);
  return sources.length > 0 ? sources[0].rows : null;
}

function generateDataCode(spec) {
  const rows = _largestDataset(spec);
  const out = ["import pandas as pd", ""];
  if (!rows || rows.length === 0) {
    out.push("# No inline data in this spec.");
    return out.join("\n");
  }
  out.push("data = [");
  for (const row of rows) out.push("    " + JSON.stringify(row) + ",");
  out.push("]");
  out.push("df = pd.DataFrame(data)");
  out.push("");
  out.push("# df has " + rows.length + " rows, " + Object.keys(rows[0] || {}).length + " columns");
  return out.join("\n");
}

function generateAltairCode(spec) {
  // Best-effort codegen -- handles common cases. Complex composites may not
  // round-trip perfectly; the Vega-Lite JSON is always the source of truth.
  const out = [];
  out.push("import altair as alt");
  out.push("import pandas as pd");
  out.push("");

  const rows = _largestDataset(spec);
  if (rows && rows.length > 0) {
    out.push("data = [");
    for (const row of rows) out.push("    " + JSON.stringify(row) + ",");
    out.push("]");
    out.push("df = pd.DataFrame(data)");
    out.push("");
  } else {
    out.push("# df = pd.DataFrame(...)  # supply your data here");
    out.push("");
  }

  // Detect top-level mark vs layered
  const composite = detectCompositeJS(spec);
  if (composite === "layer") {
    out.push("# NOTE: This chart is layered. The codegen below shows the primary layer.");
    out.push("# Full layering requires composing alt.layer(...) from the individual layers.");
    out.push("");
  }

  // Pull the "primary" spec: either top-level mark/encoding or first layer
  let primary = spec;
  if (Array.isArray(spec.layer) && spec.layer.length > 0) {
    primary = Object.assign({}, spec, spec.layer.find(l => l.mark) || spec.layer[0]);
  }

  const mark = typeof primary.mark === "string" ? { type: primary.mark } : (primary.mark || {});
  const markType = mark.type || "line";
  const markArgs = Object.assign({}, mark);
  delete markArgs.type;
  const markArgsStr = Object.entries(markArgs)
    .map(([k, v]) => k + "=" + _pyRepr(v))
    .join(", ");

  out.push("chart = (");
  out.push("    alt.Chart(df)");
  out.push("    .mark_" + markType + "(" + markArgsStr + ")");

  // Encoding
  const enc = primary.encoding || {};
  const channelLines = [];
  for (const [ch, def] of Object.entries(enc)) {
    if (!def || typeof def !== "object") continue;
    channelLines.push(_altairEncodingLine(ch, def));
  }
  if (channelLines.length > 0) {
    out.push("    .encode(");
    for (const line of channelLines) out.push("        " + line + ",");
    out.push("    )");
  }

  // Properties
  const props = [];
  if (spec.title) {
    const t = typeof spec.title === "string" ? spec.title : spec.title.text;
    if (t) props.push('title=' + _pyRepr(t));
  }
  if (spec.width !== undefined) props.push("width=" + spec.width);
  if (spec.height !== undefined) props.push("height=" + spec.height);
  if (props.length > 0) out.push("    .properties(" + props.join(", ") + ")");

  out.push(")");
  out.push("");
  out.push("# Save: chart.save('output.html')");
  out.push("# Or render in Jupyter: chart");

  return out.join("\n");
}

function _altairEncodingLine(channel, def) {
  const cap = channel.charAt(0).toUpperCase() + channel.slice(1);
  const field = def.field;
  const typeMap = { temporal: "T", quantitative: "Q", nominal: "N", ordinal: "O" };
  const typeCode = def.type ? (typeMap[def.type] || "N") : "N";
  const args = [];
  if (field) args.push(_pyRepr(field + ":" + typeCode));
  if (def.title !== undefined) args.push("title=" + _pyRepr(def.title));
  if (def.aggregate) args.push("aggregate=" + _pyRepr(def.aggregate));
  if (def.bin) args.push("bin=" + _pyRepr(def.bin));
  if (def.sort !== undefined) args.push("sort=" + _pyRepr(def.sort));
  if (def.stack !== undefined) args.push("stack=" + _pyRepr(def.stack));
  if (def.value !== undefined) args.push("value=" + _pyRepr(def.value));
  return channel + "=alt." + cap + "(" + args.join(", ") + ")";
}

function _pyRepr(v) {
  if (v === null) return "None";
  if (v === true) return "True";
  if (v === false) return "False";
  if (typeof v === "number") return String(v);
  if (typeof v === "string") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(_pyRepr).join(", ") + "]";
  if (typeof v === "object") {
    const parts = [];
    for (const [k, val] of Object.entries(v)) parts.push(JSON.stringify(k) + ": " + _pyRepr(val));
    return "{" + parts.join(", ") + "}";
  }
  return JSON.stringify(v);
}

function detectCompositeJS(spec) {
  if (!spec || typeof spec !== "object") return null;
  for (const key of ["hconcat", "vconcat", "concat"]) {
    if (Array.isArray(spec[key]) && spec[key].length > 1) return key;
  }
  if (Array.isArray(spec.layer) && spec.layer.length > 1) return "layer";
  return null;
}

function downloadAltair() {
  downloadBlob(generateAltairCode(currentSpec), FILENAME + "_altair.py", "text/x-python");
}

function downloadDataPython() {
  downloadBlob(generateDataCode(currentSpec), FILENAME + "_data.py", "text/x-python");
}

/* ============================================================
   METADATA TAB
   ============================================================ */
function renderMetadata() {
  refreshDataCache();
  const container = document.getElementById("metadataContainer");
  if (!container) return;

  const title = _extractTitle(currentSpec);
  const subtitle = _extractSubtitle(currentSpec);
  const allMarks = _walkAllMarks(currentSpec);
  const composite = detectCompositeJS(currentSpec);
  const colorField = findEncodingField(currentSpec, "color");
  const xField = findEncodingField(currentSpec, "x");
  const yField = findEncodingField(currentSpec, "y");

  const numericCols = [];
  const categoricalCols = [];
  const temporalCols = [];
  for (const col of _dataColumns) {
    const sample = _dataRows.slice(0, 50).map(r => r[col]);
    const numeric = sample.filter(v => typeof v === "number" && !isNaN(v)).length;
    const dateLike = sample.filter(v => typeof v === "string" && /^\d{4}-\d{2}(-\d{2})?/.test(v)).length;
    if (dateLike > sample.length * 0.5) temporalCols.push(col);
    else if (numeric > sample.length * 0.5) numericCols.push(col);
    else categoricalCols.push(col);
  }

  const overrideCount = Object.keys(overrides).filter(k => !k.startsWith("__")).length;

  const sections = [
    { title: "Chart", rows: [
      ["Title", title || "(untitled)"],
      ["Subtitle", subtitle || "(none)"],
      ["Generated at", new Date().toLocaleString()],
      ["Schema", "vega-lite v5"],
      ["Chart ID", FILENAME],
    ]},
    { title: "Chart configuration", rows: [
      ["Primary mark", _extractPrimaryMark(currentSpec)],
      ["All marks in spec", allMarks.join(", ") || "(none)"],
      ["Composite layout", composite || "no"],
      ["Theme (selector default)", currentTheme],
      ["Palette (selector default)", currentPalette],
      ["Dimension preset (selector default)", currentDimPreset],
      ["Active spec sheet", currentSpecSheet],
      ["Knob overrides active", String(overrideCount)],
    ]},
    { title: "Data", rows: [
      ["Rows", String(_dataRows.length)],
      ["Columns", String(_dataColumns.length)],
      ["Column names", _dataColumns.join(", ") || "(none)"],
      ["Temporal columns", temporalCols.join(", ") || "(none)"],
      ["Numeric columns", numericCols.join(", ") || "(none)"],
      ["Categorical columns", categoricalCols.join(", ") || "(none)"],
      ["Size", _approxSize(_dataRows) + " KB (approx)"],
    ]},
    { title: "Encoding", rows: [
      ["X field", xField ? (xField.field + " : " + xField.type) : "(none)"],
      ["Y field", yField ? (yField.field + " : " + yField.type) : "(none)"],
      ["Color field", colorField ? (colorField.field + " : " + colorField.type) : "(none)"],
    ]},
    { title: "Interactivity enabled", rows: [
      ["Tooltips", currentKnobValues.tooltipEnabled ? "on" : "off"],
      ["Crosshair", currentKnobValues.crosshairEnabled ? "on" : "off"],
      ["Brush zoom X", currentKnobValues.brushZoomX ? "on" : "off"],
      ["Brush zoom Y", currentKnobValues.brushZoomY ? "on" : "off"],
      ["Legend click toggle", currentKnobValues.legendClickToggle ? "on" : "off"],
    ]},
  ];

  let html = "";
  for (const section of sections) {
    html += "<div class='meta-section'><h3>" + section.title + "</h3><div class='meta-grid'>";
    for (const [k, v] of section.rows) {
      html += "<span class='meta-key'>" + k + "</span><span class='meta-val'>" + _escapeHtml(String(v)) + "</span>";
    }
    html += "</div></div>";
  }

  container.innerHTML = html;
}

function _extractTitle(spec) {
  // Resolve through the concat wrapper the producer adds for captions /
  // side panels, otherwise every source-bearing chart reads as untitled.
  const host = spec ? findTitleHost(spec) : null;
  const t = host && host.node.title;
  if (!t) return null;
  if (typeof t === "string") return t;
  return t.text || null;
}
function _extractSubtitle(spec) {
  const host = spec ? findTitleHost(spec) : null;
  const t = host && host.node.title;
  if (!t || typeof t !== "object") return null;
  return t.subtitle || null;
}
function _extractCaption(spec) {
  const panel = spec ? findCaptionPanel(spec) : null;
  if (!panel) return null;
  // Unwrap the producer's soft line breaks so the knob shows one string;
  // rewrapTextPanel re-derives them on write.
  return String(panel.node.mark.text).split("\n").join(" ").trim() || null;
}
function _extractPrimaryMark(spec) {
  if (!spec) return "(none)";
  if (typeof spec.mark === "string") return spec.mark;
  if (spec.mark && typeof spec.mark === "object") return spec.mark.type || "(unknown)";
  if (Array.isArray(spec.layer) && spec.layer.length > 0) {
    for (const l of spec.layer) {
      const m = _extractPrimaryMark(l);
      if (m && m !== "(none)") return m;
    }
  }
  return "(none)";
}
function _walkAllMarks(spec) {
  const found = [];
  function walk(n) {
    if (!n || typeof n !== "object") return;
    if (typeof n.mark === "string") found.push(n.mark);
    else if (n.mark && typeof n.mark === "object" && n.mark.type) found.push(n.mark.type);
    for (const key of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(n[key])) for (const s of n[key]) walk(s);
    }
    if (n.spec) walk(n.spec);
  }
  walk(spec);
  return Array.from(new Set(found));
}
function _approxSize(rows) {
  try { return (JSON.stringify(rows).length / 1024).toFixed(1); }
  catch (e) { return "?"; }
}
function _escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* ============================================================
   SPEC SHEETS
   ============================================================ */
function loadSpecSheetsFromStorage() {
  const raw = localStorage.getItem(SHEETS_KEY);
  if (!raw) { specSheets = deepClone(INITIAL_SPEC_SHEETS) || {}; return; }
  try {
    specSheets = JSON.parse(raw);
  } catch (e) {
    specSheets = {};
  }
}

function saveSpecSheetsToStorage() {
  localStorage.setItem(SHEETS_KEY, JSON.stringify(specSheets));
}

function buildSpecSheetObject(name) {
  return {
    schema_version: 1,
    spec_sheet_id: name,
    name: name,
    scope: "global",
    base_theme: currentTheme,
    base_palette: currentPalette,
    base_dimension_preset: currentDimPreset,
    overrides: Object.fromEntries(
      Object.entries(overrides).filter(([k, v]) => !k.startsWith("__"))
    ),
    updated_at: new Date().toISOString(),
  };
}

function applySpecSheet(name) {
  currentSpecSheet = name;
  const sheet = specSheets[name];
  if (!sheet) { setStatus("spec sheet '" + name + "' not found"); return; }
  // Rebuilding from the original invalidates any spec node an open menu
  // is holding, so the menu has to go with it.
  closeMenu();
  currentSpec = deepClone(ORIGINAL_SPEC);
  overrides = {};
  // The spec just went back to the producer's, so every knob value read
  // off the old one is now describing a chart that no longer exists --
  // including the domain boxes, which would keep advertising a window
  // this sheet just discarded. Re-read before the sheet's own overrides
  // go on top.
  populateKnobValuesFromSpec();
  // The undo closures point into the spec being discarded.
  _textJournal = [];
  if (sheet.base_theme) applyTheme(sheet.base_theme, false);
  if (sheet.base_palette) applyPalette(sheet.base_palette, false);
  if (sheet.base_dimension_preset) applyDimensionPreset(sheet.base_dimension_preset, false);
  if (sheet.overrides) {
    for (const [name_, value] of Object.entries(sheet.overrides)) {
      if (name_.startsWith("__")) continue;
      const knob = KNOBS.find(k => k.name === name_);
      if (knob) {
        currentKnobValues[name_] = value;
        overrides[name_] = value;
        applyKnob(knob, value);
      }
    }
  }
  initializeKnobs();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
  syncSelectors();
  setStatus("applied spec sheet '" + name + "'");
}

function overwriteCurrentSheet() {
  if (currentSpecSheet === "(none)") {
    setStatus("no active sheet; use 'Save as new'");
    return;
  }
  specSheets[currentSpecSheet] = buildSpecSheetObject(currentSpecSheet);
  saveSpecSheetsToStorage();
  setStatus("overwrote '" + currentSpecSheet + "'");
  updateTextAreas();
}

function saveAsNewSheet() {
  const name = prompt("Name for new spec sheet:");
  if (!name) return;
  if (specSheets[name]) {
    if (!confirm("Overwrite existing sheet '" + name + "'?")) return;
  }
  currentSpecSheet = name;
  specSheets[name] = buildSpecSheetObject(name);
  saveSpecSheetsToStorage();
  populateSpecSheetSelect();
  document.getElementById("specSheetSelect").value = name;
  setStatus("saved new sheet '" + name + "'");
  updateTextAreas();
}

function deleteCurrentSheet() {
  if (currentSpecSheet === "(none)") return;
  if (!confirm("Delete sheet '" + currentSpecSheet + "'?")) return;
  delete specSheets[currentSpecSheet];
  currentSpecSheet = "(none)";
  saveSpecSheetsToStorage();
  populateSpecSheetSelect();
  setStatus("deleted");
  updateTextAreas();
}

function downloadSheet() {
  let sheet;
  if (currentSpecSheet !== "(none)" && specSheets[currentSpecSheet]) {
    sheet = specSheets[currentSpecSheet];
  } else {
    sheet = buildSpecSheetObject("(unsaved)");
  }
  const blob = new Blob([JSON.stringify(sheet, null, 2)], { type: "application/json" });
  downloadURL(URL.createObjectURL(blob), (sheet.name || "spec_sheet") + ".json");
}

function uploadSheet(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const sheet = JSON.parse(e.target.result);
      if (!sheet.name) { setStatus("invalid spec sheet: missing 'name' field"); return; }
      specSheets[sheet.name] = sheet;
      saveSpecSheetsToStorage();
      populateSpecSheetSelect();
      document.getElementById("specSheetSelect").value = sheet.name;
      applySpecSheet(sheet.name);
      setStatus("uploaded and applied '" + sheet.name + "'");
    } catch (err) {
      setStatus("upload failed: " + err.message);
    }
  };
  reader.readAsText(file);
}

function populateSpecSheetSelect() {
  const sel = document.getElementById("specSheetSelect");
  sel.innerHTML = "";
  const noneOpt = document.createElement("option");
  noneOpt.value = "(none)"; noneOpt.textContent = "(none)";
  sel.appendChild(noneOpt);
  for (const name of Object.keys(specSheets)) {
    const o = document.createElement("option");
    o.value = name; o.textContent = name;
    sel.appendChild(o);
  }
  sel.value = currentSpecSheet;
  sel.onchange = () => {
    if (sel.value === "(none)") {
      currentSpecSheet = "(none)";
      setStatus("no active sheet");
    } else {
      applySpecSheet(sel.value);
    }
  };
}

function syncSelectors() {
  const t = document.getElementById("themeSelect"); if (t) t.value = currentTheme;
  const p = document.getElementById("paletteSelect"); if (p) p.value = currentPalette;
  const d = document.getElementById("dimPresetSelect"); if (d) d.value = currentDimPreset;
  const ss = document.getElementById("specSheetSelect"); if (ss) ss.value = currentSpecSheet;
}

/* ============================================================
   MISC UI
   ============================================================ */
function resetToTheme() {
  // Wipe spec back to producer-original then re-render. The user can
  // then explicitly pick a theme from the dropdown if they want to
  // override the producer's styling.
  closeMenu();
  currentSpec = deepClone(ORIGINAL_SPEC);
  overrides = {};
  _textJournal = [];
  populateKnobValuesFromSpec();
  initializeKnobs();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
  setStatus("reset to producer original");
}

function clearOverrides() {
  closeMenu();
  overrides = {};
  currentSpec = deepClone(ORIGINAL_SPEC);
  _textJournal = [];
  populateKnobValuesFromSpec();
  initializeKnobs();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
  setStatus("overrides cleared");
}

/* The raw-JSON mirrors were retired with the Raw tab; the Code tab and
   the Export tab already serialise the spec on demand. Kept as a no-op
   guard so the many call sites do not each need a condition. */
function updateTextAreas() {
  const spec = document.getElementById("specText");
  if (!spec) return;
  spec.value = JSON.stringify(currentSpec, null, 2);
  document.getElementById("overridesText").value = JSON.stringify({
    theme: currentTheme,
    palette: currentPalette,
    dimensionPreset: currentDimPreset,
    spec_sheet: currentSpecSheet,
    overrides: overrides,
  }, null, 2);
  const sheetArea = document.getElementById("sheetText");
  if (currentSpecSheet !== "(none)" && specSheets[currentSpecSheet]) {
    sheetArea.value = JSON.stringify(specSheets[currentSpecSheet], null, 2);
  } else {
    sheetArea.value = JSON.stringify(buildSpecSheetObject("(unsaved)"), null, 2);
  }
}

function setStatus(msg) {
  document.getElementById("status").textContent = msg;
}

/* ============================================================
   POPULATE KNOB VALUES FROM SPEC

   Initial knob values must reflect what is ALREADY in the spec, not
   the chart_functions_studio defaults. The producer (PRISM /
   chart_functions.py) bakes its full theme into the spec before
   we wrap it; if we apply our own defaults on top we destroy the
   producer's work and the editor's first paint diverges from the
   producer's PNG.

   For each knob we try, in order:
     1. path-based knob: read getPath(currentSpec, knob.path)
     2. apply-based knob: try a known reverse extractor
     3. fall back to knob.default (slider position will be the default
        but the chart still renders correctly because we never WRITE
        anything during init).
   ============================================================ */
function populateKnobValuesFromSpec() {
  for (const k of KNOBS) {
    let v;
    if (k.path) {
      v = getPath(currentSpec, k.path);
    } else if (k.apply) {
      v = extractApplyKnobValue(k);
    }
    if (v === undefined || v === null) v = k.default;
    currentKnobValues[k.name] = v;
  }
}

function detectDimPresetFromSpec() {
  // Match the spec's width/height to a known preset so the dropdown's
  // initial value corresponds to what's actually rendered. Falls back to
  // "custom" if no preset matches.
  const w = currentKnobValues.width;
  const h = currentKnobValues.height;
  if (w == null || h == null) return "custom";
  for (const [name, preset] of Object.entries(DIM_PRESETS)) {
    if (name === "custom") continue;
    if (preset.width === w && preset.height === h) return name;
  }
  return "custom";
}

function extractApplyKnobValue(knob) {
  // Reverse of APPLY_FUNCTIONS: look the value up in the spec where
  // the apply function would have written it. Used ONLY to populate
  // initial knob values; doesn't write anything.
  switch (knob.apply) {
    case "setWidth":        return walkExtractSize(currentSpec, "width");
    case "setHeight":       return walkExtractSize(currentSpec, "height");
    case "setTitleText":    return _extractTitle(currentSpec);
    case "setSubtitleText": return _extractSubtitle(currentSpec);
    case "setCaptionText":  return _extractCaption(currentSpec);
    case "setXAxisTitle":   return _extractEncodingProp(currentSpec, "x", "title");
    case "setYAxisTitle":   return _extractEncodingProp(currentSpec, "y", "title");
    case "setLegendTitle":  return _extractEncodingProp(currentSpec, "color", "title");
    case "setLegendShow": {
      const enc = _firstEncodingChannel(currentSpec, "color");
      if (enc && enc.legend === null) return false;
      return true;
    }
    case "setXAxisFormat":  return _extractAxisProp(currentSpec, "x", "axisX", "format");
    case "setYAxisFormat":  return _extractAxisProp(currentSpec, "y", "axisY", "format");
    case "setXLabelAngle":  return _extractAxisProp(currentSpec, "x", "axisX", "labelAngle");
    case "setYLabelAngle":  return _extractAxisProp(currentSpec, "y", "axisY", "labelAngle");
    case "setXTickCount":   return _extractAxisProp(currentSpec, "x", "axisX", "tickCount");
    case "setYTickCount":   return _extractAxisProp(currentSpec, "y", "axisY", "tickCount");
    case "setXDomainShow":  return _extractAxisProp(currentSpec, "x", "axisX", "domain");
    case "setYDomainShow":  return _extractAxisProp(currentSpec, "y", "axisY", "domain");
    case "setXTickShow":    return _extractAxisProp(currentSpec, "x", "axisX", "ticks");
    case "setYTickShow":    return _extractAxisProp(currentSpec, "y", "axisY", "ticks");
    case "setXDomainMin":   return _extractDomainBound(currentSpec, "x", 0);
    case "setXDomainMax":   return _extractDomainBound(currentSpec, "x", 1);
    case "setYDomainMin":   return _extractDomainBound(currentSpec, "y", 0);
    case "setYDomainMax":   return _extractDomainBound(currentSpec, "y", 1);
    case "setXZeroStart":   return _extractZeroStart(currentSpec, "x");
    case "setYZeroStart":   return _extractZeroStart(currentSpec, "y");
    case "setXLogScale":    return _extractLogScale(currentSpec, "x");
    case "setYLogScale":    return _extractLogScale(currentSpec, "y");
    case "setYInvert": {
      const enc = _firstEncodingChannel(currentSpec, "y");
      return !!(enc && enc.scale && enc.scale.reverse);
    }
    case "setStrokeDash": {
      const arr = getPath(currentSpec, "config.line.strokeDash");
      if (!arr) return "solid";
      const j = JSON.stringify(arr);
      if (j === "[6,4]")          return "dashed";
      if (j === "[1,2]")          return "dotted";
      if (j === "[6,3,2,3]")      return "dash-dot";
      if (j === "[10,4]")         return "long-dash";
      return "solid";
    }
    case "setTrendlineDash": {
      const arr = getPath(currentSpec, "config.rule.strokeDash");
      if (!arr) return "solid";
      const j = JSON.stringify(arr);
      if (j === "[6,4]") return "dashed";
      if (j === "[1,2]") return "dotted";
      return "solid";
    }
    case "setPrimaryColor": {
      const cats = getPath(currentSpec, "config.range.category");
      if (Array.isArray(cats) && cats.length > 0) return cats[0];
      return undefined;
    }
    case "setTooltipEnabled":
      return _extractTooltipEnabled(currentSpec);
    case "setTooltipContent":
      return _extractTooltipShowAllFields(currentSpec);
  }
  return undefined;
}

function _firstEncodingChannel(spec, channel) {
  let result = null;
  function walk(node) {
    if (result || !node || typeof node !== "object") return;
    if (node.encoding && node.encoding[channel]) {
      result = node.encoding[channel];
      return;
    }
    for (const key of ["layer", "concat", "hconcat", "vconcat"]) {
      if (Array.isArray(node[key])) for (const s of node[key]) walk(s);
    }
    if (node.spec) walk(node.spec);
  }
  walk(spec);
  return result;
}

function _extractEncodingProp(spec, channel, prop) {
  const enc = _firstEncodingChannel(spec, channel);
  if (!enc) return undefined;
  if (prop in enc) return enc[prop];
  if (enc.axis && typeof enc.axis === "object" && prop in enc.axis) {
    return enc.axis[prop];
  }
  return undefined;
}

function _extractAxisProp(spec, channel, configKey, prop) {
  const enc = _firstEncodingChannel(spec, channel);
  if (enc && enc.axis && typeof enc.axis === "object" && prop in enc.axis) {
    return enc.axis[prop];
  }
  return getPath(spec, "config." + configKey + "." + prop);
}

function _extractDomainBound(spec, channel, idx) {
  const enc = _firstEncodingChannel(spec, channel);
  if (enc && enc.scale && Array.isArray(enc.scale.domain)) {
    const v = enc.scale.domain[idx];
    if (v === null || v === undefined) return "";
    return String(v);
  }
  return "";
}

function _extractZeroStart(spec, channel) {
  const enc = _firstEncodingChannel(spec, channel);
  if (!enc || !enc.scale) return "auto";
  if (enc.scale.zero === true)  return "force";
  if (enc.scale.zero === false) return "off";
  return "auto";
}

function _extractLogScale(spec, channel) {
  const enc = _firstEncodingChannel(spec, channel);
  return !!(enc && enc.scale && enc.scale.type === "log");
}

function _extractTooltipEnabled(spec) {
  // Match wrap-time logic: tooltip is "on" if any of encoding.tooltip,
  // mark.tooltip, config.mark.tooltip is set to a non-disabling value.
  if (specHasEncodingTooltip(spec) || specHasMarkTooltip(spec)) return true;
  const cfgT = getPath(spec, "config.mark.tooltip");
  if (cfgT === null || cfgT === false) return false;
  if (cfgT === undefined) return true;
  return true;
}

function _extractTooltipShowAllFields(spec) {
  const cfgT = getPath(spec, "config.mark.tooltip");
  if (cfgT && typeof cfgT === "object" && cfgT.content === "data") return true;
  return cfgT === true ? false : true;
}

/* ============================================================
   INIT

   ARCHITECTURE: the spec we receive is already fully styled by the
   producer (chart_functions.py bakes the theme + dimensions in
   before calling wrap_interactive_prism). The editor's first
   paint must therefore be a faithful replay of the spec, NOT a
   re-application of the editor's own theme defaults.

   Steps:
     1. Read spec sheets from storage; populate sheet dropdown.
     2. Sync selectors (theme/palette/dimension dropdowns) to the
        labels passed in from Python (these are display-only -- we
        do NOT push them onto the spec on init).
     3. Extract initial knob values from the current spec so the
        sliders/checkboxes show whatever the producer already set.
     4. Apply any INITIAL_OVERRIDES (from spec sheets / explicit
        wrap_interactive() overrides arg). These DO write to spec.
     5. If a saved spec sheet is active, apply it (this is an
        explicit user-state restoration -- it WILL overwrite spec).
     6. renderChart -- producers spec, possibly with overrides, but
        never with editor defaults baked on top.
   ============================================================ */
function init() {
  loadSpecSheetsFromStorage();
  populateSpecSheetSelect();

  // Capture spec values into knob state without mutating the spec.
  populateKnobValuesFromSpec();

  // Detect the actual dimension preset from the spec so the dropdown
  // matches what's rendered (not what was passed from python).
  currentDimPreset = detectDimPresetFromSpec();

  // Apply explicit overrides (from a saved sheet payload or python-side
  // overrides=). These are intentional user choices, not theme defaults.
  if (INITIAL_OVERRIDES) {
    for (const [name, value] of Object.entries(INITIAL_OVERRIDES)) {
      if (name.startsWith("__")) continue;
      const knob = KNOBS.find(k => k.name === name);
      if (knob) {
        currentKnobValues[name] = value;
        overrides[name] = value;
        applyKnob(knob, value);
      }
    }
  }

  initializeKnobs();

  // Spec sheets are an explicit user-state restoration; let them
  // re-apply their full theme/palette/dim/overrides bundle.
  if (currentSpecSheet !== "(none)" && specSheets[currentSpecSheet]) {
    applySpecSheet(currentSpecSheet);
  } else {
    renderChart();
  }

  updateTextAreas();
  updateSizeSummary();
  syncSelectors();
  refreshDependentTabs();
  installSidebarHeightObserver();
  installDirectManipulation();
  updateUndoButton();
  requestAnimationFrame(syncSidebarHeight);
}

/* Delegated rather than per-node: vega rebuilds the SVG on every render,
   so listeners bound to marks would have to be re-bound each time. The
   container survives, so one listener does. */
function installDirectManipulation() {
  const host = document.getElementById("chart");
  if (host) {
    host.addEventListener("contextmenu", onChartContextMenu);
    host.addEventListener("pointerdown", beginPan);
  }
  installResizeGrips();

  document.addEventListener("pointerdown", e => {
    const m = menuRoot();
    if (m && m.classList.contains("on") && !m.contains(e.target)) closeMenu();
  });
  window.addEventListener("keydown", e => {
    if (e.key === "Escape") closeMenu();
    const meta = e.metaKey || e.ctrlKey;
    if (meta && e.key.toLowerCase() === "z" && !e.shiftKey) {
      const tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      e.preventDefault();
      undoLastEdit();
    }
    if (meta && e.key.toLowerCase() === "s") { e.preventDefault(); downloadChart(); }
  });
  window.addEventListener("scroll", closeMenu, { passive: true });
}

init();
</script>

</body>
</html>
"""


def _render_template(
    spec_json: str,
    knobs_json: str,
    themes_json: str,
    palettes_json: str,
    dimensions_json: str,
    typography_overrides_json: str,
    initial_theme: str,
    initial_palette: str,
    initial_dim_preset: str,
    initial_overrides_json: str,
    initial_spec_sheets_json: str,
    initial_active_sheet: str,
    title: str,
    filename: str,
    pref_key: str,
    sheets_key: str,
) -> str:
    replacements = {
        "__SPEC_JSON__":                 spec_json,
        "__KNOBS_JSON__":                knobs_json,
        "__THEMES_JSON__":               themes_json,
        "__PALETTES_JSON__":             palettes_json,
        "__DIMENSIONS_JSON__":           dimensions_json,
        "__TYPOGRAPHY_OVERRIDES_JSON__": typography_overrides_json,
        "__INITIAL_THEME__":             f'"{initial_theme}"',
        "__INITIAL_PALETTE__":           f'"{initial_palette}"',
        "__INITIAL_DIM_PRESET__":        f'"{initial_dim_preset}"',
        "__INITIAL_OVERRIDES__":         initial_overrides_json,
        "__INITIAL_SPEC_SHEETS__":       initial_spec_sheets_json,
        "__INITIAL_ACTIVE_SHEET__":      f'"{initial_active_sheet}"',
        "__TITLE__":                     title,
        "__FILENAME__":                  filename,
        "__PREF_KEY__":                  pref_key,
        "__SHEETS_KEY__":                sheets_key,
    }
    out = HTML_TEMPLATE
    for token, value in replacements.items():
        out = out.replace(token, value)
    return out


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class InteractiveResult:
    html: str
    html_path: Optional[str]
    chart_id: str
    chart_type: str
    theme: str
    palette: str
    dimension_preset: str
    knob_names: List[str]


@dataclass
class PrismSpecSheet:
    """User-owned bundle of chart styling preferences.

    A spec sheet is saved per-user (and per-chart-type if scope != 'global').
    The active spec sheet is applied on top of theme and palette defaults
    when the editor opens.
    """
    spec_sheet_id: str
    name: str
    base_theme: str = "gs_clean"
    base_palette: str = "gs_primary"
    base_dimension_preset: str = "wide"
    overrides: Dict[str, Any] = field(default_factory=dict)
    scope: str = "global"
    description: str = ""
    owner: str = ""
    schema_version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PrismSpecSheet":
        required = {"spec_sheet_id", "name"}
        missing = required - set(d.keys())
        if missing:
            raise ValueError(f"Spec sheet missing required fields: {missing}")
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, s: str) -> "PrismSpecSheet":
        return cls.from_dict(json.loads(s))


@dataclass
class PrismInteractiveResult:
    """Returned by wrap_interactive_prism(). Designed to extend PRISM's
    ChartResult interface -- your integration can copy these fields onto
    the existing ChartResult dataclass."""
    editor_html: str
    editor_html_path: Optional[str]
    editor_url: Optional[str]           # presigned URL if uploaded
    chart_id: str
    chart_type: str
    theme: str
    palette: str
    dimension_preset: str
    knob_names: List[str]
    active_spec_sheet: Optional[str]
    applied_spec_sheet_id: Optional[str]


# =============================================================================
# PUBLIC API -- GENERIC
# =============================================================================


def _coerce_spec(spec: Any) -> Dict[str, Any]:
    if isinstance(spec, dict):
        return spec
    if isinstance(spec, str):
        return json.loads(spec)
    if hasattr(spec, "to_dict"):
        return spec.to_dict()
    if hasattr(spec, "to_json"):
        return json.loads(spec.to_json())
    raise TypeError(
        f"Cannot coerce {type(spec).__name__} to a vega-lite spec dict. "
        "Pass a dict, JSON string, or object with .to_dict() / .to_json()."
    )


def _compute_chart_id(spec: Dict[str, Any]) -> str:
    canonical = json.dumps(spec, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(canonical).hexdigest()[:12]


# =============================================================================
# RENDER VALIDATION (no required Python deps)
#
# Layers (best-effort, use whatever is available):
#   1. node + vega + vega-lite  (gold standard -- actually runs the spec
#      through vega's runtime, catches what the browser would catch)
#   2. Structural heuristics    (zero deps, catches known-bad patterns like
#      tooltip-collision and apostrophe-in-format-string)
#
# If node+vega is unavailable, layer 2 alone still catches the known bugs.
# No Python package dependencies are required at runtime.
# =============================================================================


@dataclass
class RenderDiagnostic:
    ok: bool
    compile_ok: bool
    expressions_ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    broken_expressions: List[Dict[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        if self.ok:
            return "OK"
        lines = []
        if not self.compile_ok:
            lines.append("  COMPILE FAILED:")
            for e in self.errors:
                lines.append(f"    {e[:300]}")
        if not self.expressions_ok:
            lines.append("  BROKEN EXPRESSIONS:")
            for be in self.broken_expressions:
                lines.append(f"    at {be['path']}:")
                lines.append(f"      {be['expr'][:200]}")
                lines.append(f"      reason: {be['reason']}")
        if self.warnings:
            lines.append("  WARNINGS:")
            for w in self.warnings:
                lines.append(f"    {w[:200]}")
        return "\n".join(lines) if lines else "OK"


_NODE_RENDER_SCRIPT = r"""
const vega = require('vega');
const vl = require('vega-lite');
const fs = require('fs');

async function main() {
  const specStr = fs.readFileSync(0, 'utf8');
  const spec = JSON.parse(specStr);
  try {
    const {spec: vegaSpec} = vl.compile(spec);
    const runtime = vega.parse(vegaSpec);
    const view = new vega.View(runtime, {renderer: 'none'});
    await view.runAsync();
    // Also exercise tooltip-like eval paths
    await view.toSVG();
    console.log(JSON.stringify({ok: true}));
  } catch (e) {
    console.log(JSON.stringify({
      ok: false,
      error: e.message,
      stack: e.stack ? e.stack.split('\n').slice(0, 3).join(' | ') : null,
    }));
    process.exit(0);
  }
}
main().catch(e => {
  console.log(JSON.stringify({ok: false, error: String(e)}));
  process.exit(0);
});
"""


def _find_node_modules_with_vega() -> Optional[str]:
    """Return the path to a node_modules directory that contains vega and
    vega-lite, or None if not found anywhere standard.

    Checks (in order):
        1. CWD/node_modules
        2. ancestors of CWD
        3. /tmp/node_modules (test/dev convention)
        4. ~/.node_modules
    """
    candidates: List[Path] = []
    here = Path.cwd()
    candidates.append(here)
    candidates.extend(here.parents)
    candidates.append(Path("/tmp"))
    candidates.append(Path.home() / ".node_modules")
    for d in candidates:
        nm = d / "node_modules"
        if (nm / "vega").exists() and (nm / "vega-lite").exists():
            return str(nm)
    return None


def _try_node_render_check(spec_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run the spec through node+vega+vega-lite (if available) to catch
    runtime render errors that static compilation misses.

    Returns:
        {"ok": True} on success
        {"ok": False, "error": "..."} on render error
        None if node or the packages aren't available
    """
    import os
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("node"):
        return None

    node_modules = _find_node_modules_with_vega()
    if node_modules is None:
        return None

    # Write the script ADJACENT to node_modules so node can resolve `vega`
    # via its usual lookup rules. Using tempfile's default would put the
    # script in /var/folders/... where vega isn't installed.
    script_dir = Path(node_modules).parent
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     dir=str(script_dir)) as f:
        f.write(_NODE_RENDER_SCRIPT)
        script_path = f.name

    env = dict(os.environ)
    # Belt + suspenders: also set NODE_PATH in case the script was moved.
    existing_node_path = env.get("NODE_PATH", "")
    env["NODE_PATH"] = (node_modules + (os.pathsep + existing_node_path)
                        if existing_node_path else node_modules)

    try:
        result = subprocess.run(
            ["node", script_path],
            input=json.dumps(spec_dict, default=str),
            capture_output=True, text=True, timeout=30,
            cwd=str(script_dir),
            env=env,
        )
        output = result.stdout.strip()
        if not output:
            return {"ok": False,
                    "error": f"node exit {result.returncode}: {result.stderr[:300]}"}
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"ok": False,
                    "error": f"unparseable node output: {output[:200]}"}
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def validate_spec_renders(spec: Any, include_warnings: bool = True,
                          use_node: bool = True) -> RenderDiagnostic:
    """Validate that a vega-lite spec will render without runtime errors.

    Zero Python package dependencies. Uses whichever of these is available:

    1. **node + vega + vega-lite** (``npm install vega vega-lite``, anywhere
       on the node require path or in /tmp/node_modules): actually runs the
       spec through vega's runtime parser. Catches the exact class of
       expression-parse errors the browser produces -- this is the gold
       standard.

    2. **Structural heuristics** (always available): catches known-bad
       spec patterns -- encoding.tooltip colliding with config.mark.tooltip,
       ASCII apostrophes in axis/legend format strings, obviously
       unbalanced parens in any expression strings present in the raw spec.

    If node+vega is unavailable, heuristics alone catch the main bug
    classes we've hit (the PRISM tooltip/apostrophe bugs). The validator
    never fails just because the optional dependency is missing.
    """
    spec_dict = _coerce_spec(spec)

    errors: List[str] = []
    warnings: List[str] = []
    broken: List[Dict[str, str]] = []
    compile_ok = True
    node_ran = False

    # --- Node runtime check (gold standard, if node + vega + vega-lite exist) ---
    if use_node:
        node_result = _try_node_render_check(spec_dict)
        if node_result is not None:
            node_ran = True
            if not node_result["ok"]:
                errors.append("node+vega runtime: " + node_result.get("error", "unknown"))
                broken.append({
                    "path": "(runtime)",
                    "expr": node_result.get("error", ""),
                    "reason": "vega runtime parse error",
                })

    if not node_ran and include_warnings:
        warnings.append(
            "node+vega not available for runtime render check "
            "(install with `npm install vega vega-lite` or place them in "
            "/tmp/node_modules). Falling back to structural heuristics only."
        )

    # --- Static expression scan of any expression strings in the raw spec ---
    # (The spec rarely has expressions at this level, but scan anyway.)
    for path, expr in _collect_raw_spec_expressions(spec_dict):
        reason = _check_expression_for_bugs(expr)
        if reason:
            broken.append({"path": path, "expr": expr, "reason": reason})

    # --- Structural warnings ---
    if _spec_has_encoding_tooltip_anywhere(spec_dict):
        def has_conflicting_cmt(s):
            if not isinstance(s, dict):
                return False
            cfg = s.get("config", {})
            cm = cfg.get("mark") if isinstance(cfg, dict) else None
            if isinstance(cm, dict) and "tooltip" in cm:
                return True
            for key in ("layer", "hconcat", "vconcat", "concat"):
                v = s.get(key)
                if isinstance(v, list):
                    for c in v:
                        if has_conflicting_cmt(c):
                            return True
            return False
        if has_conflicting_cmt(spec_dict) and include_warnings:
            warnings.append(
                "Spec has BOTH encoding.tooltip and config.mark.tooltip; "
                "Vega-Lite will generate two description expressions and merge "
                "them, often causing render errors. Call wrap_interactive() to "
                "auto-sanitize."
            )

    def _has_apostrophe_in_formats(s):
        if not isinstance(s, dict):
            return False
        for key in ("format", "labelFormat"):
            v = s.get(key)
            if isinstance(v, str) and "'" in v:
                return True
        axis = s.get("axis")
        if isinstance(axis, dict):
            for k in ("format", "labelFormat"):
                v = axis.get(k)
                if isinstance(v, str) and "'" in v:
                    return True
        enc = s.get("encoding")
        if isinstance(enc, dict):
            for ch in enc.values():
                if isinstance(ch, dict):
                    v = ch.get("format")
                    if isinstance(v, str) and "'" in v:
                        return True
                    ax = ch.get("axis")
                    if isinstance(ax, dict):
                        for k in ("format", "labelFormat"):
                            if isinstance(ax.get(k), str) and "'" in ax[k]:
                                return True
        for key in ("layer", "hconcat", "vconcat", "concat"):
            val = s.get(key)
            if isinstance(val, list):
                for c in val:
                    if _has_apostrophe_in_formats(c):
                        return True
        return False

    if _has_apostrophe_in_formats(spec_dict) and include_warnings:
        warnings.append(
            "Spec has ASCII apostrophe (') in a format string (e.g. \"%b '%y\"). "
            "This breaks at runtime because vega.parse() re-serializes with "
            "single quotes. Call wrap_interactive() to auto-rewrite to typographic "
            "right-single-quote (\u2019), visually identical but safe."
        )

    ok = len(broken) == 0 and compile_ok
    return RenderDiagnostic(
        ok=ok, compile_ok=compile_ok,
        expressions_ok=len(broken) == 0,
        errors=errors,
        warnings=warnings if include_warnings else [],
        broken_expressions=broken,
    )


def _collect_raw_spec_expressions(node: Any, path: str = "") -> List[tuple]:
    """Walk a raw vega-lite spec looking for expression strings that the user
    may have hand-written (rare in practice, but params.expr, transform
    filters, and param selections can contain expressions).

    Returns list of (path, expr) tuples.
    """
    found: List[tuple] = []
    if isinstance(node, dict):
        for k, v in node.items():
            child_path = path + "." + str(k)
            if k in ("signal", "expr") and isinstance(v, str):
                found.append((child_path, v))
            elif k == "filter" and isinstance(v, str):
                # transform filters can be expression strings
                found.append((child_path, v))
            else:
                found.extend(_collect_raw_spec_expressions(v, child_path))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found.extend(_collect_raw_spec_expressions(item, path + "[" + str(i) + "]"))
    return found


def _check_expression_for_bugs(expr: str) -> Optional[str]:
    """Return a human-readable reason string if the expression contains
    known-bad patterns, else None."""
    # 1. Paren balance (ignoring parens inside strings)
    depth = 0
    in_str = None  # current open quote char, or None
    escape = False
    for ch in expr:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if in_str:
            if ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return "unbalanced parens: extra closing paren"
    if depth > 0:
        return f"unbalanced parens: {depth} unclosed opening paren(s)"

    # 2. Single-quoted format strings with embedded apostrophes.
    # Pattern: '...X...' where X is an apostrophe inside a single-quoted
    # string without proper escaping. Look for <'><non-apostrophe chars>
    # <'><letter or %><more>
    import re
    # Match a single-quoted literal that contains another single quote
    # Simpler: match the known-bad pattern '...'...'%'
    bad_apos = re.search(r"'[^']*'[A-Za-z%][^']*'", expr)
    if bad_apos:
        return ("single-quoted format string contains unescaped apostrophe: "
                + bad_apos.group(0)[:60])

    return None


def _is_meaningful_tooltip(tooltip_val: Any) -> bool:
    """Distinguish "tooltip explicitly set and active" from "tooltip
    explicitly disabled or absent".

    Meaningful (active):
        - list with at least one item
        - dict with a 'field' or 'content' key
        - True
    Not meaningful (disabled or absent):
        - None, False, empty list, empty dict
    """
    if tooltip_val is None or tooltip_val is False:
        return False
    if isinstance(tooltip_val, list):
        return len(tooltip_val) > 0
    if isinstance(tooltip_val, dict):
        return bool(tooltip_val) and (
            "field" in tooltip_val
            or "content" in tooltip_val
            or "value" in tooltip_val
        )
    if tooltip_val is True:
        return True
    return False


def _spec_has_any_tooltip(spec: Any) -> bool:
    """Return True if ANY tooltip key is set anywhere -- whether meaningful
    (actively shows a tooltip) or explicit-disable (null/False/empty).

    Used by wrap_interactive() to decide whether to inject a default
    tooltip. We respect an explicit disable just as much as an explicit
    enable -- the producer's intent wins either way.
    """
    if not isinstance(spec, dict):
        return False
    enc = spec.get("encoding")
    if isinstance(enc, dict) and "tooltip" in enc:
        return True
    mark = spec.get("mark")
    if isinstance(mark, dict) and "tooltip" in mark:
        return True
    cfg = spec.get("config")
    if isinstance(cfg, dict):
        cmark = cfg.get("mark")
        if isinstance(cmark, dict) and "tooltip" in cmark:
            return True
    for key in ("layer", "hconcat", "vconcat", "concat"):
        val = spec.get(key)
        if isinstance(val, list):
            for child in val:
                if _spec_has_any_tooltip(child):
                    return True
    if isinstance(spec.get("spec"), dict):
        if _spec_has_any_tooltip(spec["spec"]):
            return True
    return False


def _spec_has_encoding_tooltip_anywhere(spec: Any) -> bool:
    """Return True if spec (or any descendant) has a meaningful encoding.
    tooltip or mark.tooltip. These are producer-explicit tooltips that
    should win over any config.mark.tooltip global default.

    null/False/empty tooltips don't count -- they're explicit disables.
    """
    if not isinstance(spec, dict):
        return False
    enc = spec.get("encoding")
    if isinstance(enc, dict) and "tooltip" in enc:
        if _is_meaningful_tooltip(enc["tooltip"]):
            return True
    mark = spec.get("mark")
    if isinstance(mark, dict) and "tooltip" in mark:
        if _is_meaningful_tooltip(mark["tooltip"]):
            return True
    for key in ("layer", "hconcat", "vconcat", "concat"):
        val = spec.get(key)
        if isinstance(val, list):
            for child in val:
                if _spec_has_encoding_tooltip_anywhere(child):
                    return True
    if isinstance(spec.get("spec"), dict):
        if _spec_has_encoding_tooltip_anywhere(spec["spec"]):
            return True
    return False


def _strip_config_mark_tooltip(spec: Any) -> None:
    """Recursively remove config.mark.tooltip from the spec. Used when we
    detect an encoding.tooltip elsewhere -- keeping both causes Vega-Lite
    to generate TWO description/tooltip expressions and merge them with '+',
    producing malformed expressions (especially when the axis format
    contains literal apostrophes like '%b \\'%y')."""
    if not isinstance(spec, dict):
        return
    cfg = spec.get("config")
    if isinstance(cfg, dict):
        cmark = cfg.get("mark")
        if isinstance(cmark, dict) and "tooltip" in cmark:
            del cmark["tooltip"]
            if not cmark:
                del cfg["mark"]
            if not cfg:
                del spec["config"]
    for key in ("layer", "hconcat", "vconcat", "concat"):
        val = spec.get(key)
        if isinstance(val, list):
            for child in val:
                _strip_config_mark_tooltip(child)
    if isinstance(spec.get("spec"), dict):
        _strip_config_mark_tooltip(spec["spec"])


def _sanitize_tooltip_collision(spec: Any) -> bool:
    """If the spec has encoding.tooltip or mark.tooltip anywhere, strip
    config.mark.tooltip from root AND all nested specs to prevent
    Vega-Lite description-signal collision. Returns True if any strip
    occurred.

    Addresses one of two distinct render-error classes:
        Expression parse error: ("date: " + ... + "; Date: " + ...))
    where Vega-Lite merges two description expressions and the paren
    count gets mis-aligned.
    """
    if not _spec_has_encoding_tooltip_anywhere(spec):
        return False

    def count_tooltips(s):
        n = 0
        if isinstance(s, dict):
            cfg = s.get("config")
            if isinstance(cfg, dict):
                cmark = cfg.get("mark")
                if isinstance(cmark, dict) and "tooltip" in cmark:
                    n += 1
            for key in ("layer", "hconcat", "vconcat", "concat"):
                val = s.get(key)
                if isinstance(val, list):
                    for c in val:
                        n += count_tooltips(c)
            if isinstance(s.get("spec"), dict):
                n += count_tooltips(s["spec"])
        return n

    before = count_tooltips(spec)
    _strip_config_mark_tooltip(spec)
    return before > 0


# Typographic right single quote -- visually identical to ASCII apostrophe
# but safe when embedded in single-quoted expression strings.
_APOSTROPHE_REPLACEMENT = "\u2019"


def _sanitize_apostrophe_formats(spec: Any, _depth: int = 0) -> int:
    """Replace literal apostrophes in axis.format / axis.labelFormat /
    encoding.*.axis.format strings with the typographic right-single-quote
    character.

    Addresses the second render-error class:
        Expression parse error: (timeFormat(datum["date"], '%b '%y'))
    which happens because vega.parse() re-serializes format strings with
    SINGLE quotes at runtime. A literal apostrophe inside the format
    (e.g. "%b '%y" as a financial convention for "Jan '25") then
    prematurely terminates the wrapping single-quoted string.

    d3-time-format treats the typographic quote (U+2019) identically to the
    ASCII apostrophe as a literal character, so the substitution is
    purely cosmetic but prevents expression parse errors.

    Returns the number of substitutions made (recursively).
    """
    if _depth > 50 or not isinstance(spec, dict):
        return 0

    count = 0

    def _replace(v: Any) -> Any:
        nonlocal count
        if isinstance(v, str) and "'" in v:
            count += v.count("'")
            return v.replace("'", _APOSTROPHE_REPLACEMENT)
        return v

    # Walk common format locations
    for key in ("format", "labelFormat"):
        if key in spec:
            spec[key] = _replace(spec[key])

    axis = spec.get("axis")
    if isinstance(axis, dict):
        for k in ("format", "labelFormat"):
            if k in axis:
                axis[k] = _replace(axis[k])

    # encoding.{x,y,color,...}.axis.format / encoding.*.format
    # PRISM-specific: encoding.tooltip is a LIST of dicts (one per field),
    # each of which may have a `format`. Same for encoding.detail/order.
    def _sanitize_channel_def(ch_def):
        if not isinstance(ch_def, dict):
            return
        if "format" in ch_def:
            ch_def["format"] = _replace(ch_def["format"])
        ax = ch_def.get("axis")
        if isinstance(ax, dict):
            for k in ("format", "labelFormat"):
                if k in ax:
                    ax[k] = _replace(ax[k])
        lg = ch_def.get("legend")
        if isinstance(lg, dict):
            for k in ("format", "labelFormat"):
                if k in lg:
                    lg[k] = _replace(lg[k])
        # Scale-nested format (e.g. color scales with formatted legends)
        sc = ch_def.get("scale")
        if isinstance(sc, dict):
            for k in ("format", "labelFormat"):
                if k in sc:
                    sc[k] = _replace(sc[k])

    enc = spec.get("encoding")
    if isinstance(enc, dict):
        for channel, ch_def in enc.items():
            if isinstance(ch_def, list):
                # encoding.tooltip = [{...}, {...}, ...]
                for item in ch_def:
                    _sanitize_channel_def(item)
            else:
                _sanitize_channel_def(ch_def)

    # config.axisX / config.axisY / config.axis / config.legend
    cfg = spec.get("config")
    if isinstance(cfg, dict):
        for axis_key in ("axis", "axisX", "axisY", "axisTop", "axisBottom",
                         "axisLeft", "axisRight", "legend"):
            axcfg = cfg.get(axis_key)
            if isinstance(axcfg, dict):
                for k in ("format", "labelFormat"):
                    if k in axcfg:
                        axcfg[k] = _replace(axcfg[k])

    # Title/subtitle can have time expressions too (rare, but safe)
    title = spec.get("title")
    if isinstance(title, dict):
        for k in ("text", "subtitle"):
            v = title.get(k)
            if isinstance(v, str) and "'" in v:
                # Don't touch title text -- user content
                pass

    # Recurse into nested specs
    for key in ("layer", "hconcat", "vconcat", "concat"):
        val = spec.get(key)
        if isinstance(val, list):
            for child in val:
                count += _sanitize_apostrophe_formats(child, _depth + 1)
    if isinstance(spec.get("spec"), dict):
        count += _sanitize_apostrophe_formats(spec["spec"], _depth + 1)

    return count


def wrap_interactive(
    spec: Any,
    chart_type: Optional[str] = None,
    theme: str = "gs_clean",
    palette: Optional[str] = None,
    dimension_preset: str = "custom",
    overrides: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    output_path: Optional[Union[str, Path]] = None,
    filename_base: Optional[str] = None,
    pref_key: Optional[str] = None,
    sheets_key: Optional[str] = None,
    spec_sheets: Optional[Dict[str, Dict[str, Any]]] = None,
    active_spec_sheet: Optional[str] = None,
) -> InteractiveResult:
    """Wrap a vega-lite spec into an interactive HTML editor.

    Parameters
    ----------
    spec : dict | str | altair-like
    chart_type : str, optional (auto-detected if None)
    theme : str (default "gs_clean")
    palette : str, optional (uses theme default if None)
    dimension_preset : str (default "custom" keeps the spec's own dims)
    overrides : dict, optional  (keyed by knob name)
    title : str, optional (defaults to spec.title or "Chart Studio - {id}")
    output_path : str|Path, optional (writes HTML to this path)
    filename_base : str, optional (export filename prefix)
    pref_key : str, optional (localStorage key for session overrides)
    sheets_key : str, optional (localStorage key for spec sheet library)
    spec_sheets : dict, optional (pre-populated spec sheets for this session)
    active_spec_sheet : str, optional (name of the initially-active sheet)
    """
    spec_dict = _coerce_spec(spec)

    # ---- Tooltip collision sanitization ----
    #
    # If the producer (e.g. PRISM's chart_functions.py) has set an
    # encoding.tooltip OR mark.tooltip anywhere in the spec, then any
    # config.mark.tooltip (whether we injected it or the producer did)
    # will cause Vega-Lite to generate TWO description/tooltip signals
    # that get merged with '+', producing malformed expression strings.
    #
    # Symptom: browser shows
    #   Expression parse error: ("date: " + timeFormat(..., '%b '%y')) + ...
    #
    # The apostrophe in axis format strings (common in financial charts,
    # e.g. "%b '%y" meaning "Jan '25") amplifies this -- when Vega wraps
    # the auto-generated description expression in single quotes, the
    # embedded apostrophe prematurely closes the string literal.
    #
    # Fix: strip config.mark.tooltip whenever an encoding.tooltip exists.
    _sanitize_tooltip_collision(spec_dict)

    # ---- Apostrophe-in-format sanitization ----
    # Axis formats like "%b '%y" (financial convention for "Jan '25") break
    # at runtime when vega.parse() re-serializes the signal with single
    # quotes. Replace ASCII apostrophe with typographic right-single-quote.
    _sanitize_apostrophe_formats(spec_dict)

    # Enable tooltips by default, but ONLY if the spec doesn't already have one
    # configured anywhere (sanitization above may have stripped config-level).
    if not _spec_has_any_tooltip(spec_dict):
        if "config" not in spec_dict:
            spec_dict["config"] = {}
        if "mark" not in spec_dict["config"]:
            spec_dict["config"]["mark"] = {}
        spec_dict["config"]["mark"]["tooltip"] = {"content": "data"}

    if chart_type is None:
        chart_type = detect_chart_type(spec_dict)
    if chart_type not in MARK_KNOB_MAP:
        supported = ", ".join(list_supported_marks())
        raise ValueError(
            f"chart_type '{chart_type}' has no registered knobs. Supported: {supported}"
        )

    get_theme(theme)
    if palette is None:
        palette = get_theme(theme).get("palette", "gs_primary")
    get_palette(palette)
    get_dimension_preset(dimension_preset)

    chart_id = _compute_chart_id(spec_dict)
    knob_list = knobs_for_chart(chart_type)

    if title is None:
        if isinstance(spec_dict.get("title"), str):
            title = spec_dict["title"]
        elif isinstance(spec_dict.get("title"), dict) and isinstance(spec_dict["title"].get("text"), str):
            title = spec_dict["title"]["text"]
        else:
            title = f"Chart Studio - {chart_id}"

    if filename_base is None:
        filename_base = f"chart_{chart_id}"

    if pref_key is None:
        pref_key = f"chart_studio_prefs_{chart_type}"
    if sheets_key is None:
        sheets_key = "chart_studio_spec_sheets"

    html = _render_template(
        spec_json=json.dumps(spec_dict, default=str),
        knobs_json=json.dumps(knob_list),
        themes_json=json.dumps(THEMES),
        palettes_json=json.dumps(PALETTES),
        dimensions_json=json.dumps(DIMENSION_PRESETS),
        typography_overrides_json=json.dumps(TYPOGRAPHY_OVERRIDES),
        initial_theme=theme,
        initial_palette=palette,
        initial_dim_preset=dimension_preset,
        initial_overrides_json=json.dumps(overrides or {}),
        initial_spec_sheets_json=json.dumps(spec_sheets or {}),
        initial_active_sheet=active_spec_sheet or "(none)",
        title=title,
        filename=filename_base,
        pref_key=pref_key,
        sheets_key=sheets_key,
    )

    html_path: Optional[str] = None
    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
        html_path = str(p.resolve())

    return InteractiveResult(
        html=html, html_path=html_path, chart_id=chart_id,
        chart_type=chart_type, theme=theme, palette=palette,
        dimension_preset=dimension_preset,
        knob_names=[k["name"] for k in knob_list],
    )


@dataclass
class ChartStudio:
    """Builder alternative to wrap_interactive()."""
    spec: Any
    chart_type: Optional[str] = None
    theme: str = "gs_clean"
    palette: Optional[str] = None
    dimension_preset: str = "custom"
    overrides: Dict[str, Any] = field(default_factory=dict)
    title: Optional[str] = None
    spec_sheets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    active_spec_sheet: Optional[str] = None

    def set_theme(self, name: str) -> "ChartStudio":
        get_theme(name); self.theme = name; return self

    def set_palette(self, name: str) -> "ChartStudio":
        get_palette(name); self.palette = name; return self

    def set_dimension_preset(self, name: str) -> "ChartStudio":
        get_dimension_preset(name); self.dimension_preset = name; return self

    def set_override(self, name: str, value: Any) -> "ChartStudio":
        self.overrides[name] = value; return self

    def set_overrides(self, mapping: Dict[str, Any]) -> "ChartStudio":
        self.overrides.update(mapping); return self

    def add_spec_sheet(self, sheet: Union[PrismSpecSheet, Dict[str, Any]]) -> "ChartStudio":
        if isinstance(sheet, PrismSpecSheet):
            sheet = sheet.to_dict()
        self.spec_sheets[sheet["name"]] = sheet
        return self

    def set_active_spec_sheet(self, name: str) -> "ChartStudio":
        self.active_spec_sheet = name; return self

    def build(self, output_path: Optional[Union[str, Path]] = None) -> InteractiveResult:
        return wrap_interactive(
            spec=self.spec, chart_type=self.chart_type,
            theme=self.theme, palette=self.palette,
            dimension_preset=self.dimension_preset,
            overrides=self.overrides, title=self.title,
            output_path=output_path,
            spec_sheets=self.spec_sheets,
            active_spec_sheet=self.active_spec_sheet,
        )


# =============================================================================
# PRISM-SPECIFIC BINDING
# =============================================================================
#
# Designed to slot into PRISM's make_chart() interactive=True path.
# Mirrors the existing ChartResult shape while adding editor-specific fields.
# =============================================================================


def wrap_interactive_prism(
    altair_chart: Any,
    chart_type: str,
    dimensions: str = "wide",
    annotations: Optional[List[Any]] = None,
    user_id: Optional[str] = None,
    session_path: Optional[Union[str, Path]] = None,
    chart_name: Optional[str] = None,
    save_as: Optional[str] = None,
    spec_sheets: Optional[Dict[str, Dict[str, Any]]] = None,
    active_spec_sheet: Optional[str] = None,
) -> PrismInteractiveResult:
    """PRISM-facing wrapper. Maps PRISM's make_chart conventions onto
    chart_functions_studio's generic wrap_interactive().

    Parameters
    ----------
    altair_chart : altair.Chart (or dict / JSON string)
        The chart object PRISM's make_chart() produces.
    chart_type : str
        PRISM chart_type: multi_line, scatter, scatter_multi, bar,
        bar_horizontal, heatmap, histogram, boxplot, area, donut,
        bullet, waterfall.
    dimensions : str (default 'wide')
        PRISM dimension preset name.
    annotations : list, optional
        PRISM's annotation list (VLine, HLine, Band, Arrow, PointLabel,
        TrendLine). Currently not surfaced as editor knobs -- future phase.
    user_id : str, optional
        Used to build the localStorage key so preferences isolate per user.
    session_path : str|Path
        PRISM session folder. Editor HTML is written to
        {session_path}/charts/{chart_name}_editor.html
    chart_name : str, optional
        Base name for the saved HTML. Defaults to timestamped name.
    save_as : str, optional
        Explicit filename (PRISM convention: overrides chart_name).
    spec_sheets : dict, optional
        Pre-loaded spec sheets from user's preference store.
    active_spec_sheet : str, optional
        ID of the user's active spec sheet.

    Returns
    -------
    PrismInteractiveResult
    """
    # Composite chart_types (``<layout>_composite``) and composite specs
    # (top-level ``hconcat`` / ``vconcat`` / ``concat``) bypass the
    # single-mark whitelist. The studio's ``detect_chart_type`` walks the
    # spec tree and picks the dominant mark from the sub-charts, which is
    # the correct knob set to load.
    spec_for_detect = _coerce_spec(altair_chart)
    is_composite = (
        chart_type.endswith("_composite")
        or detect_composite(spec_for_detect) is not None
    )

    if is_composite:
        chart_type_for_knobs = None  # let wrap_interactive auto-detect
    else:
        chart_type_for_knobs = _prism_chart_type_to_mark(chart_type)

    # map PRISM dimensions to chart_functions_studio preset
    if dimensions not in DIMENSION_PRESETS:
        raise ValueError(
            f"Unknown PRISM dimensions '{dimensions}'. "
            f"Available: {', '.join(sorted(DIMENSION_PRESETS.keys()))}"
        )

    # localStorage keys scoped per-user for isolation
    pref_key = f"chart_studio_prefs_{user_id or 'anon'}_{chart_type}"
    sheets_key = f"chart_studio_sheets_{user_id or 'anon'}"

    # determine output path following PRISM session convention
    html_path: Optional[Path] = None
    if save_as:
        html_path = Path(save_as)
    elif session_path:
        sp = Path(session_path)
        name = chart_name or f"chart_{int(datetime.now(timezone.utc).timestamp())}"
        html_path = sp / "charts" / f"{name}_editor.html"

    result = wrap_interactive(
        spec=altair_chart,
        chart_type=chart_type_for_knobs,
        theme="gs_clean",
        palette=None,  # uses gs_primary default
        dimension_preset=dimensions,
        overrides=None,
        title=None,
        output_path=html_path,
        filename_base=chart_name or None,
        pref_key=pref_key,
        sheets_key=sheets_key,
        spec_sheets=spec_sheets,
        active_spec_sheet=active_spec_sheet,
    )

    return PrismInteractiveResult(
        editor_html=result.html,
        editor_html_path=result.html_path,
        editor_url=None,  # populated by caller after S3 upload if desired
        chart_id=result.chart_id,
        chart_type=result.chart_type,
        theme=result.theme,
        palette=result.palette,
        dimension_preset=result.dimension_preset,
        knob_names=result.knob_names,
        active_spec_sheet=active_spec_sheet,
        applied_spec_sheet_id=active_spec_sheet,
    )


def _prism_chart_type_to_mark(prism_chart_type: str) -> str:
    """Map PRISM's chart_type names to chart_functions_studio's mark keys.

    Accepts every chart_type that ``chart_functions.make_chart`` itself
    recognises, including ``timeseries`` (which routes through the same
    line-mark builders as ``multi_line``).

    Composite chart_types (``2_horizontal_composite``, ``4_grid_composite``,
    etc.) are NOT handled here -- callers should detect composites
    upstream and bypass this mapping in favour of spec-driven detection
    via ``detect_chart_type``.
    """
    mapping = {
        "multi_line":      "line",
        "timeseries":      "line",
        "line":            "line",
        "scatter":         "point",
        "scatter_multi":   "scatter_multi",
        "bar":             "bar",
        "bar_horizontal":  "bar_horizontal",
        "heatmap":         "rect",
        "histogram":       "bar",
        "boxplot":         "boxplot",
        "area":            "area",
        "donut":           "arc",
        "bullet":          "bullet",
        "waterfall":       "waterfall",
    }
    if prism_chart_type not in mapping:
        raise ValueError(
            f"Unknown PRISM chart_type '{prism_chart_type}'. "
            f"Valid: {', '.join(sorted(mapping.keys()))}"
        )
    return mapping[prism_chart_type]


# =============================================================================
# TABLE STUDIO BRIDGE
# =============================================================================
#
# The table studio lives in its own file. Charts and tables share a visual
# language and a session layout but nothing below the shell -- one mutates a
# Vega-Lite spec for vega-embed, the other renders a DOM table from a cell
# model -- so merging them would mean two unrelated templates in one
# namespace. Re-exporting here means a caller that already imports the chart
# studio does not need to learn a second module path:
#
#     from chart_functions_studio import wrap_table_interactive_prism
#
# ``chart_functions.py`` imports the table studio directly, via
# ``prism_mcp.utils.chart_functions_studio_tables``. This bridge is for
# everyone else. Deleting chart_functions_studio_tables.py disables the
# feature; this import is the only place the chart studio references it.
# =============================================================================

from chart_functions_studio_tables import (  # noqa: E402, F401
    TABLE_STUDIO_ENABLED,
    TABLE_THEMES,
    InteractiveTableResult,
    PrismInteractiveTableResult,
    TableStyleSheet,
    persist_editable_table,
    wrap_table_interactive,
    wrap_table_interactive_prism,
)


# =============================================================================
# SAMPLES (for demos, tests, CLI)
# =============================================================================


def _sample_line() -> Dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Monthly Values",
        "data": {"values": [
            {"date": "2023-01-01", "series": "A", "value": 10.0},
            {"date": "2023-02-01", "series": "A", "value": 12.3},
            {"date": "2023-03-01", "series": "A", "value": 11.1},
            {"date": "2023-04-01", "series": "A", "value": 14.6},
            {"date": "2023-05-01", "series": "A", "value": 16.2},
            {"date": "2023-06-01", "series": "A", "value": 15.8},
            {"date": "2023-07-01", "series": "A", "value": 18.4},
            {"date": "2023-08-01", "series": "A", "value": 20.1},
            {"date": "2023-09-01", "series": "A", "value": 19.7},
            {"date": "2023-10-01", "series": "A", "value": 22.0},
            {"date": "2023-11-01", "series": "A", "value": 21.3},
            {"date": "2023-12-01", "series": "A", "value": 23.5},
            {"date": "2023-01-01", "series": "B", "value": 5.0},
            {"date": "2023-02-01", "series": "B", "value": 6.2},
            {"date": "2023-03-01", "series": "B", "value": 6.8},
            {"date": "2023-04-01", "series": "B", "value": 7.4},
            {"date": "2023-05-01", "series": "B", "value": 8.1},
            {"date": "2023-06-01", "series": "B", "value": 9.0},
            {"date": "2023-07-01", "series": "B", "value": 10.2},
            {"date": "2023-08-01", "series": "B", "value": 11.5},
            {"date": "2023-09-01", "series": "B", "value": 12.1},
            {"date": "2023-10-01", "series": "B", "value": 12.8},
            {"date": "2023-11-01", "series": "B", "value": 13.7},
            {"date": "2023-12-01", "series": "B", "value": 14.5},
        ]},
        "mark": {"type": "line"},
        "encoding": {
            "x": {"field": "date", "type": "temporal", "title": "Date"},
            "y": {"field": "value", "type": "quantitative", "title": "Value"},
            "color": {"field": "series", "type": "nominal", "title": "Series"},
        },
        "width": 700, "height": 350,
    }


def _sample_bar() -> Dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Annual Revenue by Sector",
        "data": {"values": [
            {"sector": "Tech", "revenue": 145},
            {"sector": "Finance", "revenue": 112},
            {"sector": "Healthcare", "revenue": 98},
            {"sector": "Energy", "revenue": 76},
            {"sector": "Retail", "revenue": 64},
            {"sector": "Industrial", "revenue": 58},
            {"sector": "Materials", "revenue": 42},
        ]},
        "mark": {"type": "bar"},
        "encoding": {
            "x": {"field": "sector", "type": "nominal", "title": "Sector", "sort": "-y"},
            "y": {"field": "revenue", "type": "quantitative", "title": "Revenue ($B)"},
            "color": {"field": "sector", "type": "nominal", "legend": None},
        },
        "width": 700, "height": 350,
    }


def _sample_bar_horizontal() -> Dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Top Products by Revenue",
        "data": {"values": [
            {"product": "Product A", "revenue": 245},
            {"product": "Product B", "revenue": 198},
            {"product": "Product C", "revenue": 176},
            {"product": "Product D", "revenue": 154},
            {"product": "Product E", "revenue": 132},
            {"product": "Product F", "revenue": 98},
            {"product": "Product G", "revenue": 76},
        ]},
        "mark": {"type": "bar"},
        "encoding": {
            "y": {"field": "product", "type": "nominal", "sort": "-x", "title": None},
            "x": {"field": "revenue", "type": "quantitative", "title": "Revenue ($M)"},
        },
        "width": 700, "height": 350,
    }


def _sample_scatter() -> Dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Returns vs Volatility",
        "data": {"values": [
            {"name": "SPX",   "vol": 14.1, "ret": 8.5,  "cluster": "US"},
            {"name": "NDX",   "vol": 19.0, "ret": 12.8, "cluster": "US"},
            {"name": "DJI",   "vol": 12.5, "ret": 7.1,  "cluster": "US"},
            {"name": "DAX",   "vol": 16.2, "ret": 6.2,  "cluster": "EU"},
            {"name": "CAC",   "vol": 15.7, "ret": 5.8,  "cluster": "EU"},
            {"name": "FTSE",  "vol": 13.9, "ret": 4.3,  "cluster": "EU"},
            {"name": "N225",  "vol": 18.5, "ret": 9.2,  "cluster": "APAC"},
            {"name": "HSI",   "vol": 22.3, "ret": -2.1, "cluster": "APAC"},
            {"name": "KOSPI", "vol": 17.8, "ret": 3.7,  "cluster": "APAC"},
        ]},
        "mark": {"type": "point"},
        "encoding": {
            "x": {"field": "vol", "type": "quantitative", "title": "Volatility (%)"},
            "y": {"field": "ret", "type": "quantitative", "title": "Return (%)"},
            "color": {"field": "cluster", "type": "nominal", "title": "Region"},
        },
        "width": 700, "height": 350,
    }


def _sample_area() -> Dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Stacked Components Over Time",
        "data": {"values": [
            {"date": "2023-Q1", "component": "Labor",   "share": 42},
            {"date": "2023-Q2", "component": "Labor",   "share": 40},
            {"date": "2023-Q3", "component": "Labor",   "share": 41},
            {"date": "2023-Q4", "component": "Labor",   "share": 43},
            {"date": "2023-Q1", "component": "Capital", "share": 30},
            {"date": "2023-Q2", "component": "Capital", "share": 32},
            {"date": "2023-Q3", "component": "Capital", "share": 31},
            {"date": "2023-Q4", "component": "Capital", "share": 29},
            {"date": "2023-Q1", "component": "Tax",     "share": 18},
            {"date": "2023-Q2", "component": "Tax",     "share": 19},
            {"date": "2023-Q3", "component": "Tax",     "share": 17},
            {"date": "2023-Q4", "component": "Tax",     "share": 18},
            {"date": "2023-Q1", "component": "Other",   "share": 10},
            {"date": "2023-Q2", "component": "Other",   "share": 9},
            {"date": "2023-Q3", "component": "Other",   "share": 11},
            {"date": "2023-Q4", "component": "Other",   "share": 10},
        ]},
        "mark": {"type": "area"},
        "encoding": {
            "x": {"field": "date", "type": "ordinal", "title": "Quarter"},
            "y": {"field": "share", "type": "quantitative", "stack": "zero", "title": "Share (%)"},
            "color": {"field": "component", "type": "nominal", "title": "Component"},
        },
        "width": 700, "height": 350,
    }


def _sample_heatmap() -> Dict[str, Any]:
    assets = ["SPX", "UST10Y", "OIL", "GOLD", "USD"]
    corr = {
        ("SPX", "SPX"): 1.00, ("SPX", "UST10Y"): -0.35, ("SPX", "OIL"): 0.22,
        ("SPX", "GOLD"): -0.15, ("SPX", "USD"): -0.28,
        ("UST10Y", "UST10Y"): 1.00, ("UST10Y", "OIL"): 0.18,
        ("UST10Y", "GOLD"): -0.42, ("UST10Y", "USD"): 0.55,
        ("OIL", "OIL"): 1.00, ("OIL", "GOLD"): 0.08, ("OIL", "USD"): -0.31,
        ("GOLD", "GOLD"): 1.00, ("GOLD", "USD"): -0.48,
        ("USD", "USD"): 1.00,
    }
    vals = []
    for a in assets:
        for b in assets:
            key = (a, b) if (a, b) in corr else (b, a)
            vals.append({"row": a, "col": b, "corr": corr.get(key, 0.0)})
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Cross-Asset Correlation",
        "data": {"values": vals},
        "mark": {"type": "rect"},
        "encoding": {
            "x": {"field": "col", "type": "nominal", "title": None},
            "y": {"field": "row", "type": "nominal", "title": None},
            "color": {"field": "corr", "type": "quantitative",
                       "scale": {"scheme": "redblue", "domain": [-1, 1]}},
        },
        "width": 450, "height": 450,
    }


def _sample_donut() -> Dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Portfolio Allocation",
        "data": {"values": [
            {"asset": "Equities",     "weight": 55},
            {"asset": "Bonds",        "weight": 25},
            {"asset": "Commodities",  "weight": 8},
            {"asset": "Cash",         "weight": 7},
            {"asset": "Alternatives", "weight": 5},
        ]},
        "mark": {"type": "arc"},
        "encoding": {
            "theta": {"field": "weight", "type": "quantitative"},
            "color": {"field": "asset", "type": "nominal", "title": "Asset Class"},
        },
        "width": 450, "height": 450,
    }


def _sample_multiline_with_annotation() -> Dict[str, Any]:
    """Layered spec: primary line + rule (vline) + text annotation.
    Tests that detector ignores annotation marks."""
    base = _sample_line()
    events = [{"date": "2023-06-15", "label": "Policy change"}]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Monthly Values with Event",
        "data": base["data"],
        "layer": [
            {
                "mark": {"type": "line"},
                "encoding": base["encoding"],
            },
            {
                "data": {"values": events},
                "mark": {"type": "rule", "strokeDash": [4, 4], "color": "#C00000"},
                "encoding": {"x": {"field": "date", "type": "temporal"}},
            },
            {
                "data": {"values": events},
                "mark": {"type": "text", "align": "left", "dx": 5, "dy": -5, "color": "#C00000"},
                "encoding": {
                    "x": {"field": "date", "type": "temporal"},
                    "text": {"field": "label", "type": "nominal"},
                },
            },
        ],
        "width": 700, "height": 350,
    }


SAMPLES: Dict[str, Callable[[], Dict[str, Any]]] = {
    "line":               _sample_line,
    "bar":                _sample_bar,
    "bar_horizontal":     _sample_bar_horizontal,
    "scatter":            _sample_scatter,
    "area":               _sample_area,
    "heatmap":            _sample_heatmap,
    "donut":              _sample_donut,
    "multiline_annotated": _sample_multiline_with_annotation,
}


def get_sample(name: str) -> Dict[str, Any]:
    if name not in SAMPLES:
        available = ", ".join(sorted(SAMPLES.keys()))
        raise KeyError(f"Sample '{name}' not found. Available: {available}")
    return SAMPLES[name]()


def list_sample_names() -> List[str]:
    return list(SAMPLES.keys())


# =============================================================================
# DEMO GENERATION
# =============================================================================


DEFAULT_DEMO_OUTPUT_DIR = Path(__file__).parent / "chart_functions_studio_demos"


def generate_demo_all(output_dir: Path, theme: str, palette: Optional[str]) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[Path] = []
    for name in list_sample_names():
        out_path = output_dir / f"{name}_{theme}.html"
        result = wrap_interactive(
            spec=get_sample(name), theme=theme, palette=palette,
            output_path=out_path,
            title=f"chart_functions_studio demo - {name} ({theme})",
        )
        outputs.append(Path(result.html_path))
        print(f"  wrote {out_path.name}  chart_type={result.chart_type}")
    return outputs


def generate_demo_one(name: str, output_dir: Path, theme: str, palette: Optional[str]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{name}_{theme}.html"
    result = wrap_interactive(
        spec=get_sample(name), theme=theme, palette=palette,
        output_path=out_path,
        title=f"chart_functions_studio demo - {name} ({theme})",
    )
    print(f"  wrote {out_path.name}  chart_type={result.chart_type}")
    return Path(result.html_path)


def generate_demo_matrix(output_dir: Path) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[Path] = []
    for sample_name in list_sample_names():
        for theme_info in list_themes():
            theme = theme_info["name"]
            out_path = output_dir / f"{sample_name}_{theme}.html"
            result = wrap_interactive(
                spec=get_sample(sample_name), theme=theme,
                output_path=out_path, title=f"{sample_name} ({theme})",
            )
            outputs.append(Path(result.html_path))
    print(f"  wrote {len(outputs)} files to {output_dir}")
    return outputs


# =============================================================================
# BUILT-IN SMOKE TESTS (python chart_functions_studio.py test)
# =============================================================================


def run_smoke_tests() -> int:
    """Quick end-to-end smoke tests. Returns 0 on success, 1 on failure.

    For the full unittest suite, see test_chart_functions_studio.py.
    """
    failures: List[str] = []
    passes = 0

    def check(cond: bool, msg: str) -> None:
        nonlocal passes
        if cond:
            passes += 1
            print(f"  [OK]   {msg}")
        else:
            failures.append(msg)
            print(f"  [FAIL] {msg}")

    print("chart_functions_studio smoke tests")
    print("=" * 40)

    # 1. Basic wrap_interactive
    print("\n-- wrap_interactive basic --")
    try:
        r = wrap_interactive(_sample_line())
        check(r.chart_type == "line", f"chart_type detected as line (got: {r.chart_type})")
        check(r.theme == "gs_clean", f"default theme = gs_clean (got: {r.theme})")
        check(r.palette == "gs_primary", f"default palette = gs_primary (got: {r.palette})")
        check(len(r.html) > 10000, f"HTML length > 10k (got: {len(r.html)})")
        check(len(r.knob_names) > 40, f"knob count > 40 (got: {len(r.knob_names)})")
    except Exception as e:
        failures.append(f"basic wrap failed: {e}")

    # 2. All themes work
    print("\n-- all themes --")
    for t in list_themes():
        try:
            r = wrap_interactive(_sample_line(), theme=t["name"])
            check(r.theme == t["name"], f"theme {t['name']} applies")
        except Exception as e:
            failures.append(f"theme {t['name']} failed: {e}")

    # 3. All palettes work
    print("\n-- all palettes --")
    for p in list_palettes():
        try:
            r = wrap_interactive(_sample_line(), palette=p["name"])
            check(r.palette == p["name"], f"palette {p['name']} applies")
        except Exception as e:
            failures.append(f"palette {p['name']} failed: {e}")

    # 4. All dimension presets
    print("\n-- all dimension presets --")
    for d in list_dimension_presets():
        try:
            r = wrap_interactive(_sample_line(), dimension_preset=d["name"])
            check(r.dimension_preset == d["name"], f"preset {d['name']}")
        except Exception as e:
            failures.append(f"preset {d['name']} failed: {e}")

    # 5. All samples
    print("\n-- all samples --")
    for name in list_sample_names():
        try:
            r = wrap_interactive(get_sample(name))
            check(r.chart_id, f"sample '{name}' -> chart_type={r.chart_type}")
        except Exception as e:
            failures.append(f"sample {name} failed: {e}")

    # 6. Error paths
    print("\n-- error paths --")
    for bad_theme in ["nonexistent", "gs_reseach", ""]:
        try:
            wrap_interactive(_sample_line(), theme=bad_theme)
            failures.append(f"bad theme '{bad_theme}' should raise")
            print(f"  [FAIL] bad theme '{bad_theme}' should raise")
        except ValueError:
            print(f"  [OK]   bad theme '{bad_theme}' raised ValueError")
            passes += 1
    for bad_palette in ["nope", ""]:
        try:
            wrap_interactive(_sample_line(), palette=bad_palette)
            failures.append(f"bad palette '{bad_palette}' should raise")
            print(f"  [FAIL] bad palette '{bad_palette}' should raise")
        except ValueError:
            print(f"  [OK]   bad palette '{bad_palette}' raised ValueError")
            passes += 1

    # 7. PRISM binding
    print("\n-- PRISM binding --")
    try:
        r = wrap_interactive_prism(
            altair_chart=_sample_line(),
            chart_type="multi_line",
            dimensions="wide",
            user_id="testuser",
        )
        check(r.chart_id, "PRISM binding returns chart_id")
        check(r.theme == "gs_clean", "PRISM defaults to gs_clean")
    except Exception as e:
        failures.append(f"PRISM binding failed: {e}")

    # 8. Spec sheet serialization
    print("\n-- spec sheet serialization --")
    try:
        sheet = PrismSpecSheet(
            spec_sheet_id="test_sheet", name="Test Sheet",
            overrides={"titleSize": 20, "strokeWidth": 3},
        )
        j = sheet.to_json()
        sheet2 = PrismSpecSheet.from_json(j)
        check(sheet2.name == sheet.name, "spec sheet JSON roundtrip")
        check(sheet2.overrides == sheet.overrides, "spec sheet overrides preserved")
    except Exception as e:
        failures.append(f"spec sheet serialization failed: {e}")

    # 9. Detector edge cases
    print("\n-- detector edge cases --")
    try:
        ct = detect_chart_type(_sample_multiline_with_annotation())
        check(ct == "line", f"layered line+rule+text -> line (got: {ct})")
    except Exception as e:
        failures.append(f"detector layered failed: {e}")

    # Render validation across all PRISM chart types + tooltip patterns
    print("\n-- render validation (PRISM chart type matrix) --")
    import re as _re
    prism_matrix = {
        "multi_line": {
            "data": {"values": [
                {"date": "2023-01-01", "Series": "A", "Value": 10},
                {"date": "2023-02-01", "Series": "A", "Value": 12},
            ]},
            "mark": {"type": "line"},
            "encoding": {
                "x": {"field": "date", "type": "temporal",
                      "axis": {"format": "%b '%y", "formatType": "time"}},
                "y": {"field": "Value", "type": "quantitative"},
                "color": {"field": "Series", "type": "nominal", "title": "Series"},
                "tooltip": [
                    {"field": "date", "type": "temporal", "title": "Date",
                     "format": "%b %y"},
                    {"field": "Value", "type": "quantitative", "format": ",.2f"},
                    {"field": "Series", "type": "nominal", "title": "Series"},
                ],
            },
        },
        "histogram": {
            "data": {"values": [{"x": i % 10} for i in range(100)]},
            "mark": {"type": "bar"},
            "encoding": {
                "x": {"bin": True, "field": "x", "type": "quantitative",
                      "title": "Bin Range"},
                "y": {"aggregate": "count", "type": "quantitative"},
                "tooltip": [
                    {"bin": True, "field": "x", "type": "quantitative",
                     "title": "Bin Range"},
                    {"aggregate": "count", "type": "quantitative", "title": "Count"},
                ],
            },
        },
        "heatmap": {
            "data": {"values": [
                {"row": "A", "col": "X", "value": 0.1},
                {"row": "B", "col": "Y", "value": 0.5},
            ]},
            "mark": {"type": "rect"},
            "encoding": {
                "x": {"field": "col", "type": "nominal"},
                "y": {"field": "row", "type": "nominal"},
                "color": {"field": "value", "type": "quantitative"},
                "tooltip": [
                    {"field": "col", "type": "nominal"},
                    {"field": "row", "type": "nominal"},
                    {"field": "value", "type": "quantitative",
                     "title": "Value", "format": ",.2f"},
                ],
            },
        },
        "donut": {
            "data": {"values": [
                {"cat": "A", "val": 55}, {"cat": "B", "val": 45},
            ]},
            "mark": {"type": "arc"},
            "encoding": {
                "theta": {"field": "val", "type": "quantitative"},
                "color": {"field": "cat", "type": "nominal"},
                "tooltip": [
                    {"field": "cat", "type": "nominal"},
                    {"field": "val", "type": "quantitative", "format": ",.0f"},
                ],
            },
        },
        "boxplot": {
            "data": {"values": [{"cat": "A", "y": i} for i in range(20)]},
            "mark": {"type": "boxplot"},
            "encoding": {
                "x": {"field": "cat", "type": "nominal"},
                "y": {"field": "y", "type": "quantitative"},
            },
        },
        "tooltip_disabled": {
            # Producer explicitly disables tooltip; we should respect it.
            "data": {"values": [{"x": 1, "y": 2}]},
            "mark": "line",
            "encoding": {
                "x": {"field": "x", "type": "quantitative"},
                "y": {"field": "y", "type": "quantitative"},
                "tooltip": None,
            },
        },
    }
    for chart_name, spec_in in prism_matrix.items():
        try:
            r = wrap_interactive(spec_in)
            m = _re.search(r"const ORIGINAL_SPEC = (\{.+?\});\n", r.html)
            sanitized = json.loads(m.group(1))
            diag = validate_spec_renders(sanitized, include_warnings=False)
            if diag.ok:
                passes += 1
                print(f"  [OK]   {chart_name:18s} wrap->render clean")
            else:
                failures.append(f"{chart_name}: " + diag.summary())
                print(f"  [FAIL] {chart_name:18s} failed render:")
                for line in diag.summary().split("\n"):
                    print(f"         {line}")
        except Exception as e:
            failures.append(f"{chart_name} crashed: {e}")
            print(f"  [FAIL] {chart_name:18s} crashed: {e}")

    print("\n" + "=" * 40)
    print(f"  {passes} passed, {len(failures)} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
        return 1
    return 0


# =============================================================================
# CLI
# =============================================================================


def cmd_wrap(args: argparse.Namespace) -> int:
    spec_path = Path(args.input)
    if not spec_path.exists():
        print(f"error: input file not found: {spec_path}", file=sys.stderr)
        return 2
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    output_path = Path(args.output) if args.output else spec_path.with_suffix(".html")
    result = wrap_interactive(
        spec=spec, chart_type=args.chart_type, theme=args.theme,
        palette=args.palette, dimension_preset=args.dimension_preset,
        output_path=output_path, title=args.title,
    )
    print(f"wrote {result.html_path}")
    print(f"  chart_id          {result.chart_id}")
    print(f"  chart_type        {result.chart_type}")
    print(f"  theme             {result.theme}")
    print(f"  palette           {result.palette}")
    print(f"  dimension_preset  {result.dimension_preset}")
    print(f"  knobs             {len(result.knob_names)}")
    if args.open:
        webbrowser.open(f"file://{result.html_path}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_DEMO_OUTPUT_DIR
    if args.matrix:
        generate_demo_matrix(output_dir)
    elif args.sample:
        generate_demo_one(args.sample, output_dir, args.theme, args.palette)
    else:
        generate_demo_all(output_dir, args.theme, args.palette)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    what = args.what
    if what == "themes":
        for t in list_themes():
            print(f"{t['name']:20s} {t['label']:35s} {t['description']}")
    elif what == "palettes":
        for p in list_palettes():
            kind = p["kind"]
            if "colors" in p:
                cols = " ".join(p["colors"][:5])
                print(f"{p['name']:20s} {p['label']:35s} {kind:12s} {cols}")
            else:
                print(f"{p['name']:20s} {p['label']:35s} {kind:12s} scheme={p.get('scheme','')}")
    elif what == "dimensions":
        for d in list_dimension_presets():
            marker = " [PRISM]" if d.get("prism") else ""
            print(f"  {d['name']:15s} {d['width']:5d}x{d['height']:<5d}  {d['label']}{marker}")
    elif what == "knobs":
        if args.chart_type:
            ks = knobs_for_chart(args.chart_type)
        else:
            ks = list(UNIVERSAL_KNOBS)
        for k in ks:
            flag = " [ESS]" if k.get("essential") else ""
            path = k.get("path") or f"apply:{k.get('apply')}"
            print(f"  [{k['group']:15s}] {k['name']:25s} {k['type']:8s} default={k.get('default')}  path={path}{flag}")
    elif what == "marks":
        for m in list_supported_marks():
            print(f"  {m}")
    elif what == "samples":
        for s in list_sample_names():
            ct = detect_chart_type(get_sample(s))
            print(f"  {s:25s} chart_type={ct}")
    else:
        print(f"unknown list target: {what}", file=sys.stderr)
        return 2
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    path = Path(args.input)
    if not path.exists():
        print(f"error: input file not found: {path}", file=sys.stderr)
        return 2
    spec = json.loads(path.read_text(encoding="utf-8"))
    chart_type = detect_chart_type(spec)
    all_marks = list_all_marks(spec)
    title = spec.get("title")
    if isinstance(title, dict): title = title.get("text")
    if not isinstance(title, str): title = "(untitled)"
    width = spec.get("width", "(not set)")
    height = spec.get("height", "(not set)")
    composite = detect_composite(spec)
    print(f"file              {path}")
    print(f"title             {title}")
    print(f"chart_type        {chart_type}")
    print(f"marks             {all_marks}")
    print(f"composite         {composite or 'no'}")
    print(f"width             {width}")
    print(f"height            {height}")
    print(f"knobs available   {len(knobs_for_chart(chart_type))}")
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    args.open = True
    return cmd_wrap(args)


def cmd_test(args: argparse.Namespace) -> int:
    return run_smoke_tests()


def _prompt(msg: str, default: Optional[str] = None, choices: Optional[List[str]] = None) -> str:
    suffix = ""
    if choices: suffix = f" [{'/'.join(choices)}]"
    if default is not None: suffix += f" (default: {default})"
    while True:
        raw = input(f"{msg}{suffix}: ").strip()
        if not raw and default is not None: return default
        if choices and raw not in choices:
            print(f"  must be one of: {', '.join(choices)}")
            continue
        if raw: return raw


def interactive_menu() -> int:
    print("")
    print(f"chart_functions_studio interactive CLI (v{__version__})")
    print("=" * 40)
    while True:
        print("")
        print("  1. Wrap a vega-lite JSON file into interactive HTML")
        print("  2. Generate demos for built-in sample specs")
        print("  3. List themes")
        print("  4. List palettes")
        print("  5. List dimension presets")
        print("  6. List knobs for a chart type")
        print("  7. List samples")
        print("  8. Inspect a vega-lite JSON file")
        print("  9. Generate theme-matrix grid (every sample x every theme)")
        print("  t. Run built-in smoke tests")
        print("  q. Quit")
        choice = input("choice: ").strip().lower()
        if choice == "q": return 0
        elif choice == "1": _menu_wrap()
        elif choice == "2": _menu_demo()
        elif choice == "3": _run_list("themes")
        elif choice == "4": _run_list("palettes")
        elif choice == "5": _run_list("dimensions")
        elif choice == "6":
            ct = _prompt("chart type", choices=list_supported_marks())
            _run_list("knobs", chart_type=ct)
        elif choice == "7": _run_list("samples")
        elif choice == "8": _menu_info()
        elif choice == "9": _menu_matrix()
        elif choice == "t": run_smoke_tests()
        else: print("  invalid choice")


def _menu_wrap() -> None:
    inp = _prompt("path to vega-lite JSON file")
    out = _prompt("output HTML path (blank = same dir)", default="")
    theme_names = [t["name"] for t in list_themes()]
    theme = _prompt("theme", default="gs_clean", choices=theme_names)
    palette = _prompt("palette (blank = theme default)", default="")
    dim_names = list(DIMENSION_PRESETS.keys())
    dim = _prompt("dimension preset", default="custom", choices=dim_names)
    open_after = _prompt("open in browser after?", default="n", choices=["y", "n"]) == "y"
    args = argparse.Namespace(
        input=inp, output=out or None, theme=theme,
        palette=palette or None, dimension_preset=dim,
        chart_type=None, title=None, open=open_after,
    )
    cmd_wrap(args)


def _menu_demo() -> None:
    sample_names = list_sample_names()
    print(f"  samples: {', '.join(sample_names)}")
    sample = _prompt("sample name (blank = all)", default="")
    theme_names = [t["name"] for t in list_themes()]
    theme = _prompt("theme", default="gs_clean", choices=theme_names)
    out_dir = _prompt("output dir (blank = default)", default="")
    args = argparse.Namespace(
        sample=sample or None, output_dir=out_dir or None,
        theme=theme, palette=None, matrix=False,
    )
    cmd_demo(args)


def _menu_matrix() -> None:
    out_dir = _prompt("output dir (blank = default)", default="")
    args = argparse.Namespace(
        sample=None, output_dir=out_dir or None,
        theme="gs_clean", palette=None, matrix=True,
    )
    cmd_demo(args)


def _menu_info() -> None:
    inp = _prompt("path to vega-lite JSON file")
    args = argparse.Namespace(input=inp)
    cmd_info(args)


def _run_list(what: str, chart_type: Optional[str] = None) -> None:
    args = argparse.Namespace(what=what, chart_type=chart_type)
    cmd_list(args)


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        return interactive_menu()

    parser = argparse.ArgumentParser(prog="chart_functions_studio",
        description=f"Interactive editor for PRISM vega-lite charts (v{__version__})")
    subparsers = parser.add_subparsers(dest="command", required=True)

    theme_names = list(THEMES.keys())
    palette_names = list(PALETTES.keys())
    dim_names = list(DIMENSION_PRESETS.keys())

    p_wrap = subparsers.add_parser("wrap", help="Wrap a vega-lite JSON file into interactive HTML")
    p_wrap.add_argument("input")
    p_wrap.add_argument("--output", default=None)
    p_wrap.add_argument("--theme", default="gs_clean", choices=theme_names)
    p_wrap.add_argument("--palette", default=None, choices=palette_names)
    p_wrap.add_argument("--dimension-preset", default="custom", choices=dim_names)
    p_wrap.add_argument("--chart-type", default=None)
    p_wrap.add_argument("--title", default=None)
    p_wrap.add_argument("--open", action="store_true")
    p_wrap.set_defaults(func=cmd_wrap)

    p_open = subparsers.add_parser("open", help="Wrap + open in browser")
    p_open.add_argument("input")
    p_open.add_argument("--output", default=None)
    p_open.add_argument("--theme", default="gs_clean", choices=theme_names)
    p_open.add_argument("--palette", default=None, choices=palette_names)
    p_open.add_argument("--dimension-preset", default="custom", choices=dim_names)
    p_open.add_argument("--chart-type", default=None)
    p_open.add_argument("--title", default=None)
    p_open.set_defaults(func=cmd_open)

    p_demo = subparsers.add_parser("demo", help="Generate demo HTML files")
    p_demo.add_argument("--sample", choices=list_sample_names(), default=None)
    p_demo.add_argument("--output-dir", default=None)
    p_demo.add_argument("--theme", default="gs_clean", choices=theme_names)
    p_demo.add_argument("--palette", default=None, choices=palette_names)
    p_demo.add_argument("--matrix", action="store_true")
    p_demo.set_defaults(func=cmd_demo)

    p_list = subparsers.add_parser("list", help="List themes/palettes/dimensions/knobs/marks/samples")
    p_list.add_argument("what", choices=["themes", "palettes", "dimensions", "knobs", "marks", "samples"])
    p_list.add_argument("--chart-type", default=None)
    p_list.set_defaults(func=cmd_list)

    p_info = subparsers.add_parser("info", help="Inspect a vega-lite JSON file")
    p_info.add_argument("input")
    p_info.set_defaults(func=cmd_info)

    p_test = subparsers.add_parser("test", help="Run built-in smoke tests")
    p_test.set_defaults(func=cmd_test)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
