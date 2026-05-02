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
      grid/domain toggles, tick count
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

    # --- Typography ---
    {"name": "fontFamily", "label": "Font family", "type": "select",
     "options": ["Liberation Sans, Arial, sans-serif", "Arial", "Helvetica",
                 "sans-serif", "Georgia", "Times", "serif", "Monaco",
                 "Menlo", "monospace"],
     "default": "Liberation Sans, Arial, sans-serif",
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
    {"name": "xGridShow", "label": "X grid", "type": "checkbox",
     "default": True,
     "apply": "setXGridShow", "group": "X-Axis"},
    {"name": "xDomainShow", "label": "X axis line", "type": "checkbox",
     "default": True,
     "apply": "setXDomainShow", "group": "X-Axis"},
    {"name": "xTickShow", "label": "X ticks", "type": "checkbox",
     "default": True,
     "apply": "setXTickShow", "group": "X-Axis"},
    {"name": "xDomainMin", "label": "X domain min (blank=auto)", "type": "text",
     "default": "",
     "apply": "setXDomainMin", "group": "X-Axis"},
    {"name": "xDomainMax", "label": "X domain max (blank=auto)", "type": "text",
     "default": "",
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
    {"name": "yGridShow", "label": "Y grid", "type": "checkbox",
     "default": True,
     "apply": "setYGridShow", "group": "Y-Axis"},
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
    {"name": "gridColor", "label": "Grid color", "type": "color",
     "default": "#E6E6E6",
     "path": "config.axis.gridColor", "group": "Axes"},
    {"name": "gridOpacity", "label": "Grid opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 1.0,
     "path": "config.axis.gridOpacity", "group": "Axes", "essential": True},
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
     "default": "#729FCF",
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
        "fontFamily": "Liberation Sans, Arial, sans-serif",
        "labelSize": 18,
        "axisTitleSize": 16,
        "legendLabelSize": 14,
        "legendTitleSize": 14,
        # Axes
        "gridColor": "#E6E6E6",
        "gridOpacity": 1.0,
        "domainColor": "#000000",
        "tickColor": "#000000",
        "labelColor": "#000000",
        "domainWidth": 1,
        "tickSize": 5,
        "xGridShow": True,
        "yGridShow": True,
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


BRIDGEWATER: Dict[str, Any] = {
    "name": "bridgewater",
    "label": "Bridgewater",
    "description": "Muted, data-dense, grey on off-white",
    "values": {
        "background": "#fafaf7",
        "fontFamily": "Helvetica",
        "titleSize": 16, "titleColor": "#1c1c1c", "titleWeight": "bold",
        "labelSize": 11, "axisTitleSize": 12,
        "legendLabelSize": 10, "legendTitleSize": 11,
        "gridColor": "#cccccc", "gridOpacity": 0.4,
        "domainColor": "#555555", "tickColor": "#555555", "labelColor": "#333333",
        "domainWidth": 0.5, "tickSize": 4,
        "legendOrient": "bottom",
        "padding": 8,
        "strokeWidth": 1.5, "lineOpacity": 0.95,
        "barOpacity": 0.9,
        "areaOpacity": 0.6,
        "primaryColor": "#2c3e50",
    },
    "palette": "bridgewater",
}


MINIMAL: Dict[str, Any] = {
    "name": "minimal",
    "label": "Minimal",
    "description": "Ultra-clean, no grid, tiny labels, press-ready",
    "values": {
        "background": "#ffffff",
        "fontFamily": "Helvetica",
        "titleSize": 14, "titleColor": "#111111", "titleWeight": "normal",
        "labelSize": 10, "axisTitleSize": 11,
        "legendLabelSize": 10,
        "gridColor": "#ffffff", "gridOpacity": 0.0,
        "xGridShow": False, "yGridShow": False,
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
        "gridColor": "#333333", "gridOpacity": 0.6,
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
        "gridColor": "#dddddd", "gridOpacity": 0.7,
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
    GS_CLEAN["name"]:    GS_CLEAN,
    BRIDGEWATER["name"]: BRIDGEWATER,
    MINIMAL["name"]:     MINIMAL,
    DARK["name"]:        DARK,
    PRINT["name"]:       PRINT,
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
    "colors": ["#003359", "#B9D9EB", "#729FCF", "#A6A6A6", "#C00000",
               "#4F81BD", "#9BBB59", "#8064A2", "#F79646", "#4BACC6"],
}
GS_DIVERGING: Dict[str, Any] = {
    "name": "gs_diverging", "label": "GS Diverging", "kind": "diverging",
    "colors": ["#C00000", "#F79646", "#FFFFFF", "#729FCF", "#003359"],
}
BRIDGEWATER_PALETTE: Dict[str, Any] = {
    "name": "bridgewater", "label": "Bridgewater", "kind": "categorical",
    "colors": ["#2c3e50", "#7f8c8d", "#c0392b", "#16a085", "#d35400",
               "#8e44ad", "#2980b9"],
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
VIRIDIS: Dict[str, Any]  = {"name": "viridis",  "label": "Viridis",  "kind": "sequential", "scheme": "viridis"}
BLUES: Dict[str, Any]    = {"name": "blues",    "label": "Blues",    "kind": "sequential", "scheme": "blues"}
REDS: Dict[str, Any]     = {"name": "reds",     "label": "Reds",     "kind": "sequential", "scheme": "reds"}
GREENS: Dict[str, Any]   = {"name": "greens",   "label": "Greens",   "kind": "sequential", "scheme": "greens"}
REDBLUE: Dict[str, Any]  = {"name": "redblue",  "label": "Red-Blue", "kind": "diverging",  "scheme": "redblue"}
SPECTRAL: Dict[str, Any] = {"name": "spectral", "label": "Spectral", "kind": "diverging",  "scheme": "spectral"}


PALETTES: Dict[str, Dict[str, Any]] = {
    p["name"]: p for p in [
        GS_PRIMARY, GS_DIVERGING, BRIDGEWATER_PALETTE, MONO_BLUE, MONO_GREY,
        VIVID, TABLEAU, OKABE_ITO,
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
.layout { display: grid; grid-template-columns: 1fr 440px; gap: 16px; align-items: start; }
.panel { border: 1px solid #000; padding: 10px; }
.sidebar-panel { padding: 0; min-height: 320px; overflow: hidden; display: flex; flex-direction: column; box-sizing: border-box; }
.sidebar-panel .tab-content { padding: 12px; flex: 1 1 0; overflow: auto; max-height: none; min-height: 0; }
.chart-panel.fullscreen { grid-column: 1 / span 2; }
#chart { min-height: 400px; overflow: auto; }
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
</style>
</head>
<body>

<h1>__TITLE__</h1>

<div class="toolbar">
  <label>Spec sheet:</label>
  <select id="specSheetSelect" style="min-width: 160px;"></select>
  <button onclick="overwriteCurrentSheet()">Save</button>
  <button onclick="saveAsNewSheet()">Save as new</button>
  <button onclick="deleteCurrentSheet()">Delete</button>
  <button onclick="downloadSheet()">Download</button>
  <button onclick="document.getElementById('uploadInput').click()">Upload</button>
  <input type="file" id="uploadInput" accept=".json" style="display:none;" onchange="uploadSheet(this.files[0])" />
  <span id="status" style="margin-left:12px; font-size:11px; color:#555;"></span>
</div>

<div class="layout" id="mainLayout">

  <div class="panel chart-panel" id="chartPanel">
    <div class="chart-toolbar">
      <button onclick="resetView()" title="Reset chart view to default zoom/pan">Reset view</button>
      <button onclick="toggleFullscreen()" title="Hide sidebar and knob cards to maximize chart" id="fullscreenBtn">Fullscreen</button>
      <button onclick="exportPNG(2)">PNG 2x</button>
      <button onclick="exportSVG()">SVG</button>
      <span id="sizeSummary" class="size-summary"></span>
    </div>
    <div id="chart"></div>
  </div>

  <!-- Right sidebar: Data / Code / Metadata / Export / Raw tabs -->
  <div class="panel sidebar-panel info-tabs" id="sidebarPanel">
    <div class="tab-bar">
      <button class="tab-button active" data-tab="data" onclick="switchTab('data')">Data</button>
      <button class="tab-button" data-tab="code" onclick="switchTab('code')">Code</button>
      <button class="tab-button" data-tab="metadata" onclick="switchTab('metadata')">Metadata</button>
      <button class="tab-button" data-tab="export" onclick="switchTab('export')">Export</button>
      <button class="tab-button" data-tab="raw" onclick="switchTab('raw')">Raw</button>
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
          <button onclick="exportPNG(1)">PNG 1x</button>
          <button onclick="exportPNG(2)">PNG 2x</button>
          <button onclick="exportPNG(4)">PNG 4x</button>
          <button onclick="exportSVG()">SVG</button>
        </div>
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

    <div class="tab-content hidden" id="tab-raw">
      <details open>
        <summary>Current spec (vega-lite JSON, read-only)</summary>
        <textarea id="specText" readonly></textarea>
      </details>
      <details>
        <summary>Current overrides (read-only)</summary>
        <textarea id="overridesText" readonly></textarea>
      </details>
      <details>
        <summary>Active spec sheet (read-only)</summary>
        <textarea id="sheetText" readonly></textarea>
      </details>
    </div>
  </div>

</div>

<!-- Knob cards (below chart, responsive grid) -->
<div class="knobs-section" id="knobsSection">
  <h2>Controls</h2>
  <input type="search" class="search-box" id="searchBox" placeholder="Search knobs (e.g. 'title', 'axis', 'color')..." oninput="filterKnobs(this.value)" />
  <div class="knob-cards" id="knobContainer"></div>
  <div id="annotationSection"></div>
  <div id="perSeriesSection"></div>
  <div style="margin-top: 10px;">
    <fieldset class="knob-card">
      <legend>Session preferences (localStorage)</legend>
      <div class="row">
        <button onclick="resetToTheme()">Reset to theme</button>
        <button onclick="clearOverrides()">Clear overrides</button>
      </div>
      <div class="note">Spec sheets persist preferences across sessions. See top toolbar.</div>
    </fieldset>
  </div>
</div>

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
   APPLY FUNCTIONS (complex spec mutations)
   ============================================================ */
const APPLY_FUNCTIONS = {
  setWidth: (spec, value) => walkSetSize(spec, "width", value),
  setHeight: (spec, value) => walkSetSize(spec, "height", value),
  setTitleText: (spec, value) => {
    if (!value) {
      if (typeof spec.title === "object" && spec.title !== null) {
        delete spec.title.text;
        if (Object.keys(spec.title).length === 0) delete spec.title;
      } else {
        delete spec.title;
      }
      return;
    }
    if (typeof spec.title !== "object" || spec.title === null) spec.title = {};
    spec.title.text = value;
  },
  setSubtitleText: (spec, value) => {
    if (typeof spec.title !== "object" || spec.title === null) spec.title = {};
    if (!value) { delete spec.title.subtitle; return; }
    spec.title.subtitle = value;
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
  setXGridShow: (spec, value) =>
    setBothAxisProperty(spec, "x", "axisX", "grid", !!value),
  setYGridShow: (spec, value) =>
    setBothAxisProperty(spec, "y", "axisY", "grid", !!value),
  setXDomainShow: (spec, value) =>
    setBothAxisProperty(spec, "x", "axisX", "domain", !!value),
  setYDomainShow: (spec, value) =>
    setBothAxisProperty(spec, "y", "axisY", "domain", !!value),
  setXTickShow: (spec, value) =>
    setBothAxisProperty(spec, "x", "axisX", "ticks", !!value),
  setYTickShow: (spec, value) =>
    setBothAxisProperty(spec, "y", "axisY", "ticks", !!value),
  setXDomainMin: (spec, value) => setDomainBound(spec, "x", 0, value),
  setXDomainMax: (spec, value) => setDomainBound(spec, "x", 1, value),
  setYDomainMin: (spec, value) => setDomainBound(spec, "y", 0, value),
  setYDomainMax: (spec, value) => setDomainBound(spec, "y", 1, value),
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

function walkSetSize(node, key, value) {
  // Set width or height everywhere it already exists in the spec tree
  // (top-level + every layer/concat panel). For layered PRISM specs,
  // size is carried by the inner layer, not the root, so a top-level-
  // only update would be ignored. Always set at the top level too so
  // single-view specs still work.
  if (!node || typeof node !== "object") return;
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
  for (const subKey of ["layer", "concat", "hconcat", "vconcat"]) {
    if (Array.isArray(node[subKey])) {
      for (const child of node[subKey]) walkSetSize(child, key, value);
    }
  }
  if (node.spec) walkSetSize(node.spec, key, value);
}

function walkExtractSize(node, key) {
  // Find the first numeric width/height anywhere in the spec tree.
  if (!node || typeof node !== "object") return undefined;
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

function setDomainBound(spec, channel, idx, rawValue) {
  const num = parseFloat(rawValue);
  const isEmpty = rawValue === "" || rawValue == null || isNaN(num);
  walkEncoding(spec, channel, enc => {
    // Empty knob = "auto" semantically. Clear any explicit value at idx
    // (returns scale.domain to producer-set or vega-lite auto).
    if (isEmpty) {
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
    enc.scale.domain[idx] = num;
  });
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
   AXIS HELPERS
   Always update encoding.{channel}.axis.{prop} (overriding any
   producer-set value) AND config.{configKey}.{prop} (so the
   default applies if a panel has no encoding-level override).
   ============================================================ */
function setBothAxisProperty(spec, channel, configKey, prop, value) {
  setAxisEncodingProperty(spec, channel, prop, value);
  setAxisConfigProperty(spec, configKey, prop, value);
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
  currentKnobValues[knob.name] = value;
  overrides[knob.name] = value;
  applyKnob(knob, value);
  if (knob.name === "width" || knob.name === "height") {
    currentDimPreset = "custom";
    const sel = document.getElementById("dimPresetSelect");
    if (sel) sel.value = "custom";
  }
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
  }
  if (record) overrides.__dimPreset__ = presetName;
  initializeKnobs();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
  syncSelectors();
}

/* ============================================================
   RENDER + SUMMARY
   ============================================================ */
function renderChart() {
  vegaEmbed("#chart", currentSpec, { renderer: "svg", actions: false })
    .then(r => {
      vegaView = r.view;
      // After the chart has been laid out, sync the sidebar height so the
      // info tabs never extend past the bottom of the chart panel.
      requestAnimationFrame(syncSidebarHeight);
    })
    .catch(err => { setStatus("render error: " + err.message); });
  // Refresh dependent tabs whenever chart changes
  try { refreshDependentTabs(); } catch (e) { /* tabs not yet initialized */ }
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
function installSidebarHeightObserver() {
  const chartPanel = document.getElementById("chartPanel");
  if (!chartPanel) return;
  if (typeof ResizeObserver !== "undefined" && !_sidebarResizeObserver) {
    _sidebarResizeObserver = new ResizeObserver(() => syncSidebarHeight());
    _sidebarResizeObserver.observe(chartPanel);
  }
  window.addEventListener("resize", syncSidebarHeight);
}

function updateSizeSummary() {
  const w = currentKnobValues["width"] ?? "?";
  const h = currentKnobValues["height"] ?? "?";
  const pad = currentKnobValues["padding"] ?? 0;
  const autosize = currentKnobValues["autosize"] ?? "pad";
  const preset = currentDimPreset ?? "custom";
  const ratio = (w !== "?" && h !== "?") ? (w / h).toFixed(2) : "?";
  document.getElementById("sizeSummary").textContent =
    "width=" + w + "  height=" + h + "  aspect=" + ratio + "  padding=" + pad + "  autosize=" + autosize + "  preset=" + preset;
}

/* ============================================================
   EXPORT
   ============================================================ */
function exportPNG(scale) {
  scale = scale || 2;
  if (!vegaView) return;
  vegaView.toImageURL("png", scale).then(url => downloadURL(url, FILENAME + "_" + scale + "x.png"));
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
function resetView() {
  renderChart();
  setStatus("view reset");
}

function toggleFullscreen() {
  const layout = document.getElementById("mainLayout");
  const sidebar = document.getElementById("sidebarPanel");
  const knobs = document.getElementById("knobsSection");
  const btn = document.getElementById("fullscreenBtn");
  if (sidebar.classList.contains("hidden")) {
    sidebar.classList.remove("hidden");
    knobs.classList.remove("hidden");
    layout.style.gridTemplateColumns = "1fr 440px";
    btn.textContent = "Fullscreen";
    requestAnimationFrame(syncSidebarHeight);
  } else {
    sidebar.classList.add("hidden");
    knobs.classList.add("hidden");
    layout.style.gridTemplateColumns = "1fr";
    btn.textContent = "Exit fullscreen";
  }
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
  if (!spec) return null;
  if (typeof spec.title === "string") return spec.title;
  if (spec.title && typeof spec.title === "object") return spec.title.text || null;
  return null;
}
function _extractSubtitle(spec) {
  if (!spec || !spec.title || typeof spec.title !== "object") return null;
  return spec.title.subtitle || null;
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
  currentSpec = deepClone(ORIGINAL_SPEC);
  overrides = {};
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
  currentSpec = deepClone(ORIGINAL_SPEC);
  overrides = {};
  populateKnobValuesFromSpec();
  initializeKnobs();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
  setStatus("reset to producer original");
}

function clearOverrides() {
  overrides = {};
  currentSpec = deepClone(ORIGINAL_SPEC);
  populateKnobValuesFromSpec();
  initializeKnobs();
  renderChart();
  updateTextAreas();
  updateSizeSummary();
  setStatus("overrides cleared");
}

function updateTextAreas() {
  document.getElementById("specText").value = JSON.stringify(currentSpec, null, 2);
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
    case "setXGridShow":    return _extractAxisProp(currentSpec, "x", "axisX", "grid");
    case "setYGridShow":    return _extractAxisProp(currentSpec, "y", "axisY", "grid");
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
  requestAnimationFrame(syncSidebarHeight);
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
                     "format": "%b %d, %Y"},
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
