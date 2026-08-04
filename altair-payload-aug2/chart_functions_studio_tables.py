#!/usr/bin/env python3
"""
chart_functions_studio_tables v0.1 -- single-file interactive editor for
PRISM-style static tables.

The table-side twin of ``chart_functions_studio``. Same relationship to
``make_table`` that the chart studio has to ``make_chart``: an additive,
optional HTML companion that leaves the PNG path untouched. PRISM keeps
producing table PNGs exactly as today; when ``interactive=True`` is passed
to ``make_table`` (or ``wrap_table_interactive_prism`` is called
separately), the emitted PNG gains a self-contained HTML editor beside it.

WHY A SEPARATE FILE

    Charts and tables have almost nothing in common below the shell. The
    chart studio is a Vega-Lite spec mutator wrapped around vega-embed;
    a table has no spec and no browser-side engine, so this module renders
    a DOM ``<table>`` from a serialised CELL MODEL instead. Keeping the two
    in one file would mean two unrelated 6,000-line templates sharing a
    namespace. Keeping them apart means the table studio can be disabled by
    flipping one constant, and deleted by removing one file.

ENABLE / DISABLE

    ``TABLE_STUDIO_ENABLED`` (below) is the master switch. ``make_table``
    reads it whenever ``interactive`` is left at its default of ``None``:

        TABLE_STUDIO_ENABLED = True   -> make_table() emits the companion
        TABLE_STUDIO_ENABLED = False  -> make_table() is PNG-only, as before

    An explicit ``make_table(interactive=True/False)`` always wins over the
    constant. Nothing else in the engine changes either way.

THE CELL MODEL IS THE CONTRACT

    ``chart_functions.py`` owns resolution -- it has pandas, PIL font
    metrics, and the ``_tbl_*`` resolvers. It hands this module a finished
    cell model: every cell's formatted text, background, foreground,
    alignment, wrapped lines and geometry, plus the raw values so the
    browser can re-derive all of it after an edit. This module owns
    presentation and never imports ``chart_functions``, which is what keeps
    the import graph acyclic (``chart_functions`` -> studio, never back).

    Model shape (see ``chart_functions._tbl_build_cell_model``):

        {
          "canvas":  {"w": int, "h": int},
          "theme":   {...font sizes, band colours, text colours...},
          "geom":    {"table_x", "table_w", "header_h", "group_band_h",
                      "body_top_y",
                      "col_widths": [...], "row_default_h"},
          "title":   {"lines": [...], "subtitle": [...], "caption": [...]},
          "header_levels": [[[label, span], ...], ...],
          "columns": [{"name", "kind", "align", "fmt", "width", "wrap",
                       "numeric", "minibar_src"}, ...],
          "rows":    [{"r", "h", "kind", "group", "cells": [
                        {"c", "kind", "raw", "text", "lines",
                         "bg", "fg", "indent", "spark", "bar"}, ...]}, ...],
        }

    ``kwargs`` is the ORIGINAL ``make_table`` call, JSON-safe.

    In the browser the state splits in two and the model becomes derived:

        K   the kwargs. Styling, and what the Code tab serialises straight
            back to a runnable ``make_table(...)`` call.
        D   the data. Which columns exist, in what order, and the raw value
            behind every cell -- everything the engine received as the
            DataFrame, plus the text / line-break / height baselines it
            measured, carried alongside the value they describe.
        M   the cell model above, rebuilt from (K, D) on every change and
            never written to directly.

    Unlike the chart studio -- whose state is a mutated Vega-Lite spec with
    no inverse -- the round-trip here is an identity: K regenerates the
    call and D regenerates the DataFrame, so a structurally edited table
    re-runs through ``make_table`` and lands where the studio was showing
    it. K addresses D by POSITION in nine places, which is what
    ``applyStructural()`` exists to keep true.

S3 / PERSISTENCE PARITY

    ``persist_editable_table`` writes the same artifact family
    ``chart_functions._persist_editable_spec`` writes for charts, with
    ``table`` substituted for ``chart`` throughout. Nothing about the
    shape, the key names, or the manifest merge differs:

        {session_path}/tables/{table_id}.table.json   model + kwargs
        {session_path}/tables/{table_id}.meta.json    studio open arguments
        {session_path}/tables/table_manifest.json     png_path -> table_id
        {session_path}/tables/{name}_editor.html      the studio itself

    ``table_id`` is a sha1 prefix of the canonical model, mirroring
    ``_compute_chart_id``, so re-emitting an identical table rewrites
    identical bytes.

INPUT:  a cell model dict + the make_table kwargs dict.
OUTPUT: self-contained HTML. Zero Python runtime deps (stdlib only) and
        zero CDN deps -- a table needs no charting runtime, so unlike the
        chart studio this file has no external <script> at all.

LIBRARY USAGE

    from chart_functions_studio_tables import wrap_table_interactive_prism

    result = wrap_table_interactive_prism(
        model=cell_model,
        kwargs=table_kwargs,
        user_id='ritik',
        session_path='sessions/20260727_xxx',
        table_name='macro_snapshot',
    )
    # -> result.editor_html, result.editor_html_path, result.table_id

CLI USAGE

    python chart_functions_studio_tables.py             # interactive menu
    python chart_functions_studio_tables.py demo
    python chart_functions_studio_tables.py demo --open
    python chart_functions_studio_tables.py wrap model.json --open
    python chart_functions_studio_tables.py list formats
    python chart_functions_studio_tables.py list knobs
    python chart_functions_studio_tables.py info model.json

DESIGN RULES

    - No fallbacks. Unknown theme / format / colour mode raises ValueError.
    - Gesture-first. Every control is reachable by right-clicking the thing
      it affects; the Advanced panel is the exhaustive fallback, collapsed
      by default. This is the direction the chart studio is moving in, and
      tables are the easier case for it -- a cell is a grid coordinate, not
      a 2px stroke that has to be hit-tested.
    - Resize is expressed in kwargs, not in pixels. ``make_table`` has no
      width or height argument -- a table's canvas is derived from its
      content -- so the whole-table drag writes ``column_widths`` scaled in
      proportion and ``row_height_scale``, and the per-column drag writes a
      single ``column_widths`` entry. That is what keeps a resized table
      regenerable from the Code tab like every other edit.
    - Style sheets store STYLING only. Titles, captions, cell values and
      per-cell colour overrides are per-table content and never travel in
      a saved sheet.
    - Precedence (low to high):
        engine default -> theme -> style sheet -> live session edit.
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
from typing import Any, Dict, List, Optional, Union

from prism_mcp.utils import chart_house_style as _house


__version__ = "0.1.0"


# =============================================================================
# MASTER SWITCH
# =============================================================================
#
# Consulted by ``chart_functions.make_table`` only when its ``interactive``
# kwarg is left at ``None``. Flip to False to turn the companion off engine
# wide without touching a call site.
# =============================================================================

TABLE_STUDIO_ENABLED: bool = True


# =============================================================================
# SESSION LAYOUT -- mirrors _CHART_SPEC_PREFIX / _CHART_MANIFEST_NAME
# =============================================================================

TABLE_MODEL_PREFIX = "tables"
TABLE_MANIFEST_NAME = "table_manifest.json"


# =============================================================================
# PALETTES
#
# Shipped into the template so the browser resolves colour scales with the
# same maths the engine used, which is what lets a colour-mode change apply
# live instead of round-tripping to Python. Reading them from the house
# style is what makes "same maths" true: this module previously carried its
# own copy, and the ``wo`` / ``owb`` orange had drifted a shade away from
# the one the engine renders.
# =============================================================================

TABLE_PALETTES: Dict[str, Dict[str, Any]] = {
    name: dict(ramp) for name, ramp in _house.TABLE_RAMPS.items()
}

RAG_COLORS = dict(_house.RAG_COLORS)


# =============================================================================
# THEMES
#
# One per house style, so every table skin has a chart skin of the same name
# to sit beside. Applied browser-side and serialised into the regenerated
# call as ``skin=``.
# =============================================================================

TABLE_THEMES: Dict[str, Dict[str, Any]] = {
    name: _house.table_theme(name, include_label=True)
    for name in _house.house_style_names()
}


# =============================================================================
# FORMAT CATALOGS
#
# Number hints mirror chart_functions._tbl_smart_format exactly. Date hints
# are the named forms the engine gained alongside this module -- previously
# a table author had to know that a raw strftime string was accepted, which
# nothing documented.
# =============================================================================

NUMBER_FORMATS: List[Dict[str, str]] = [
    {"hint": "",             "label": "auto",     "sample": "1.23k"},
    {"hint": "pct",          "label": "12.3%",    "sample": "12.3%"},
    {"hint": "pct_signed",   "label": "+12.3%",   "sample": "+12.3%"},
    {"hint": "pct2",         "label": "12.34%",   "sample": "12.34%"},
    {"hint": "pct2_signed",  "label": "+12.34%",  "sample": "+12.34%"},
    {"hint": "bp",           "label": "42bp",     "sample": "42bp"},
    {"hint": "bp_signed",    "label": "+42bp",    "sample": "+42bp"},
    {"hint": "currency",     "label": "$1.20B",   "sample": "$1.20B"},
    {"hint": "ratio",        "label": "2.45x",    "sample": "2.45x"},
    {"hint": "int",          "label": "12,345",   "sample": "12,345"},
]

DATE_FORMATS: List[Dict[str, str]] = [
    {"hint": "date_dmy",     "label": "24 Jul",     "strftime": "%d %b"},
    {"hint": "date_dmy_yy",  "label": "24 Jul 26",  "strftime": "%d %b %y"},
    {"hint": "date_mon_yy",  "label": "Jul 26",     "strftime": "%b %y"},
    {"hint": "date_mon_yyyy", "label": "Jul 2026",  "strftime": "%b %Y"},
    {"hint": "date_year",    "label": "2026",       "strftime": "%Y"},
    {"hint": "date_iso",     "label": "2026-07-24", "strftime": "%Y-%m-%d"},
    {"hint": "date_slash",   "label": "24/07/26",   "strftime": "%d/%m/%y"},
    {"hint": "date_qtr",     "label": "Q3 26",      "strftime": "Q%q %y"},
    {"hint": "date_time",    "label": "14:30",      "strftime": "%H:%M"},
]

COLOR_MODES: List[Dict[str, str]] = [
    {"mode": "",          "label": "none",
     "note": "No conditional background."},
    {"mode": "rwg",       "label": "rwg",
     "note": "Red negative to green positive, white at zero. Returns, P&L."},
    {"mode": "bw",        "label": "bw",
     "note": "White to navy as magnitude rises. Unsigned levels."},
    {"mode": "rag",       "label": "rag",
     "note": "Discrete red / amber / green. Needs thresholds."},
    {"mode": "highlight", "label": "highlight",
     "note": "Flat light-blue column tint."},
]

HEATMAP_SCOPES = [
    {"scope": "column", "label": "Column", "note": "Each column scales on its own values."},
    {"scope": "row",    "label": "Row",    "note": "Scale across the selected columns within each row."},
    {"scope": "group",  "label": "Group",  "note": "One scale across every selected cell."},
]

SWATCHES: List[str] = [
    "#003359", "#5C92CB", "#94C7DD", "#C00000", "#0E7A28", "#E8A33D",
    "#7A5CB8", "#2B7A78", "#F4D6D6", "#FCE9CC", "#D8EED8", "#E8F0F7",
    "#EFEFEF", "#F7F7F7", "#FFFFFF", "#000000",
]


# =============================================================================
# KNOB REGISTRY -- the Advanced disclosure
#
# Every knob here is ALSO reachable by right-clicking the thing it affects.
# The panel exists for the cases a gesture cannot cover (a table with no
# caption has no caption to right-click) and for users who prefer a list.
# ``apply`` names a JS handler; ``kwarg`` names the make_table parameter the
# knob writes, which is what the Code tab serialises.
# =============================================================================

TABLE_KNOBS: List[Dict[str, Any]] = [
    # ---- Text -------------------------------------------------------------
    {"name": "title", "label": "Title", "group": "Text", "type": "text",
     "kwarg": "title", "essential": True},
    {"name": "subtitle", "label": "Subtitle", "group": "Text", "type": "text",
     "kwarg": "subtitle"},
    {"name": "caption", "label": "Caption", "group": "Text", "type": "text",
     "kwarg": "caption"},
    {"name": "source", "label": "Source", "group": "Text", "type": "text",
     "kwarg": "source",
     "help": "Fills an unset caption as 'Source: ...'"},

    # ---- Layout -----------------------------------------------------------
    {"name": "target_html_width", "label": "Display width", "group": "Layout",
     "type": "select", "kwarg": "target_html_width", "essential": True,
     "options": [["720", "Report (720)"], ["600", "Email (600)"],
                 ["960", "Slide (960)"], ["1120", "Wide (1120)"]],
     "help": "Width the table is normalised to read at."},
    {"name": "row_bands", "label": "Zebra banding", "group": "Layout",
     "type": "checkbox", "kwarg": "row_bands", "essential": True},
    {"name": "show_index", "label": "Show index", "group": "Layout",
     "type": "checkbox", "kwarg": "show_index"},
    {"name": "body_font_size", "label": "Body font", "group": "Layout",
     "type": "range", "min": 9, "max": 22, "step": 1, "essential": True,
     "help": "Engine picks this automatically; this overrides it."},
    {"name": "header_font_size", "label": "Header font", "group": "Layout",
     "type": "range", "min": 9, "max": 24, "step": 1},
    {"name": "title_font_size", "label": "Title font", "group": "Layout",
     "type": "range", "min": 12, "max": 34, "step": 1},
    {"name": "row_height_scale", "label": "Row height", "group": "Layout",
     "type": "range", "min": 0.7, "max": 2.0, "step": 0.05},

    # ---- Colour -----------------------------------------------------------
    {"name": "theme", "label": "Theme", "group": "Colour", "type": "select",
     "kwarg": "skin", "essential": True,
     "options": [[k, v["label"]] for k, v in TABLE_THEMES.items()]},
    {"name": "primary_color", "label": "Header band", "group": "Colour",
     "type": "color", "essential": True},
    {"name": "row_band_color", "label": "Zebra shade", "group": "Colour",
     "type": "color"},
    {"name": "positive_text", "label": "Positive text", "group": "Colour",
     "type": "color", "help": "Used by signed_columns."},
    {"name": "negative_text", "label": "Negative text", "group": "Colour",
     "type": "color", "help": "Used by signed_columns."},
    {"name": "highlight_color", "label": "Highlight tint", "group": "Colour",
     "type": "color", "help": "Used by highlight_columns."},
]

KNOB_GROUP_ORDER = ["Text", "Layout", "Colour"]


# =============================================================================
# HTML TEMPLATE
#
# One string, token-substituted by _render_table_template. Same shape as the
# chart studio's HTML_TEMPLATE and deliberately the same visual language:
# 1px black panel borders, GS navy accents, 13px sans body, monospace for
# values, a right sidebar of tabs, and a collapsed Advanced disclosure.
# =============================================================================

TABLE_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ &mdash; Table Studio</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; padding: 14px 16px 40px; background: #fff; color: #111;
  font: 13px/1.5 sans-serif; }
h1 { font-size: 19px; margin: 0 0 3px; font-weight: 700; letter-spacing: -.2px; }
.subline { font-size: 12px; color: #666; margin: 0 0 12px; }
.subline b { color: #003359; font-weight: 650; }

/* ---- layout: table panel + sidebar, mirroring the chart studio ---- */
.layout { display: grid; gap: 12px;
  grid-template-columns: minmax(0, 1fr) clamp(340px, 34vw, 440px); }
@media (max-width: 1080px) { .layout { grid-template-columns: 1fr; } }
.panel { border: 1px solid #000; background: #fff; min-width: 0; }
.panel-body { padding: 10px; }

/* ---- toolbar ---- */
.table-toolbar { display: flex; gap: 6px; align-items: center; flex-wrap: wrap;
  padding: 7px 9px; border-bottom: 1px solid #000; background: #fafafa; }
.table-toolbar button { font: 12px sans-serif; padding: 4px 11px; cursor: pointer;
  border: 1px solid #c8d2de; background: #fff; border-radius: 4px; }
.table-toolbar button:hover { background: #eef4fb; border-color: #9dc0e4; color: #1d4b80; }
.table-toolbar button.primary { background: #003359; color: #fff;
  border: 1px solid #003359; border-radius: 4px; font-weight: 650; }
.table-toolbar button.primary:hover { background: #0b4b7a; color: #fff; }
.table-toolbar button[disabled] { opacity: .4; cursor: default; }
.table-toolbar button.hidden { display: none; }
.sizetag { margin-left: auto; font: 11px ui-monospace, Menlo, monospace;
  color: #667; white-space: nowrap; }

/* ---- the table itself ----
   Three nested boxes, because the table is drawn at its real size and then
   scaled to fit the panel:
     #tableWrap   the panel's scroller and padding
     #tableScale  the table's footprint AT THE CURRENT ZOOM -- sized in JS,
                  and what the resize frame and its grips trace, so they
                  stay full-size and on the artifact's own edge however far
                  the table has been scaled down
     #tableMount  the table at 100%, carrying the scale transform
   -------------------------------------------------------------------- */
#tableWrap { overflow: auto; padding: 14px; background: #fff; }
#tableScale { position: relative; display: inline-block; vertical-align: top; }
#tableMount { display: block; transform-origin: 0 0; }
.pt-frame { padding: 12px; display: inline-block; background: #fff;
  position: relative; }
table.pt { border-collapse: collapse; table-layout: fixed; background: #fff; }
table.pt td, table.pt th { padding: 0; margin: 0; overflow: hidden;
  border: 0; vertical-align: middle; }
table.pt .cw { padding: 0 8px; display: flex; flex-direction: column;
  justify-content: center; height: 100%; }
table.pt .ln { white-space: pre; overflow: hidden; text-overflow: ellipsis; }
table.pt thead th { font-weight: 700; position: relative; text-align: left; }
table.pt thead th .cw { justify-content: center; }
table.pt thead th.super { text-align: center; }
table.pt tbody tr.grp td { font-weight: 700; }
table.pt td.sel { outline: 2px solid #1d6fc4; outline-offset: -2px; }
table.pt th.colsel { box-shadow: inset 0 -3px 0 #94C7DD; }
table.pt th .grip { position: absolute; top: 0; right: -3px; width: 7px;
  height: 100%; cursor: col-resize; z-index: 5; }
table.pt th .grip:hover { background: rgba(148,199,221,.75); }
.pt-title { font-weight: 700; color: #000; }
.pt-sub, .pt-cap { color: #5B5B5B; }
.pt-cap { font-style: italic; }
.pt-rule { height: 1px; }

/* ---- whole-table resize: the chart studio's grips, traced around
   #tableScale rather than the panel, so the drag edge sits on the artifact's
   own circumference. ---------------------------------------------------- */
.ts-frame { position: absolute; inset: -2px; pointer-events: none;
  border: 1px dashed #a9bed4; border-radius: 3px;
  opacity: 0; transition: opacity .12s; z-index: 4; }
#tableScale:hover .ts-frame, body.ts-resizing .ts-frame { opacity: 1; }
body.ts-resizing .ts-frame { border-style: solid; border-color: #1d6fc4;
  box-shadow: 0 0 0 3px rgba(29,111,196,.13); }
.ts-grip { position: absolute; opacity: 0; transition: opacity .12s;
  background: #fff; border: 1.5px solid #1d6fc4; border-radius: 2px;
  box-shadow: 0 1px 3px rgba(16,32,56,.28); z-index: 6; }
#tableScale:hover .ts-grip, body.ts-resizing .ts-grip { opacity: 1; }
.ts-grip:hover, .ts-grip.live { background: #1d6fc4; }
.ts-grip-e  { right: -6px; top: 50%; margin-top: -13px;
  width: 9px; height: 26px; cursor: ew-resize; }
.ts-grip-s  { bottom: -6px; left: 50%; margin-left: -13px;
  height: 9px; width: 26px; cursor: ns-resize; }
.ts-grip-se { right: -7px; bottom: -7px; width: 12px; height: 12px;
  cursor: nwse-resize; }
body.ts-resizing { cursor: nwse-resize; user-select: none; }
/* The table stops taking the pointer for the length of the gesture, so a
   drag that strays over the cells does not also paint a range selection. */
body.ts-resizing table.pt { pointer-events: none; }
.ts-sizetag { position: fixed; z-index: 10002; background: #22262e;
  color: #fff; font: 11.5px/1 ui-monospace, Menlo, monospace;
  padding: 6px 9px; border-radius: 5px; pointer-events: none; display: none; }
.ts-sizetag.on { display: block; }
.editing { outline: 2px solid #1d6fc4; background: #fff !important;
  color: #000 !important; }
.hint { font-size: 11.5px; color: #778; padding: 0 10px 9px; }
.hint b { color: #003359; font-weight: 640; }

/* ---- sidebar tabs ---- */
.tabs { display: flex; border-bottom: 1px solid #000; }
.tab-button { flex: 1; font: 12px sans-serif; padding: 7px 4px; cursor: pointer;
  border: 0; border-right: 1px solid #ddd; background: #f3f3f3; color: #333; }
.tab-button:last-child { border-right: 0; }
.tab-button.active { background: #003359; color: #fff; font-weight: 650; }
.tab-pane { display: none; padding: 10px; max-height: 640px; overflow: auto; }
.tab-pane.active { display: block; }
.tab-toolbar { display: flex; gap: 6px; align-items: center; margin-bottom: 8px;
  flex-wrap: wrap; }
.tab-toolbar input[type=search] { flex: 1; min-width: 160px; font-size: 12px;
  padding: 4px; }
.tab-toolbar button { font: 11.5px sans-serif; padding: 3px 9px; cursor: pointer;
  border: 1px solid #ccc; background: #fafafa; border-radius: 3px; }
.tab-toolbar button:hover { background: #eef4fb; border-color: #9dc0e4; }
.data-table { border-collapse: collapse; font-size: 11px;
  font-family: ui-monospace, Menlo, monospace; width: 100%; }
.data-table th, .data-table td { border: 1px solid #ccc; padding: 3px 6px;
  text-align: left; }
.data-table th { background: #f0f0f0; cursor: pointer; user-select: none;
  font-weight: bold; }
.data-table tr:nth-child(even) { background: #fafafa; }
.data-table tr.filtered-out { display: none; }
pre.code { background: #0f1722; color: #d6e2ef; border-radius: 6px;
  padding: 12px 13px; font: 11.6px/1.6 ui-monospace, Menlo, monospace;
  white-space: pre; overflow: auto; margin: 0; max-height: 520px; }
pre.code .st { color: #a5d6a7; } pre.code .kw { color: #7fb2e8; }
pre.code .nm { color: #f0c987; } pre.code .cm { color: #6b7b8f; }
.meta-grid { display: grid; grid-template-columns: 128px 1fr; gap: 5px 12px;
  font-size: 12px; }
.meta-grid dt { color: #778; } .meta-grid dd { margin: 0;
  font-family: ui-monospace, Menlo, monospace; font-size: 11.5px; }
.export-sec { margin-bottom: 14px; }
.export-sec h4 { margin: 0 0 6px; font-size: 11px; letter-spacing: 1px;
  text-transform: uppercase; color: #778; font-weight: 700; }
.export-sec button { display: block; width: 100%; text-align: left;
  margin-bottom: 4px; font: 12px sans-serif; padding: 6px 10px; cursor: pointer;
  border: 1px solid #ccc; background: #fafafa; border-radius: 3px; }
.export-sec button:hover { background: #eef4fb; border-color: #9dc0e4;
  color: #1d4b80; }

/* ---- advanced disclosure ---- */
.knobs-section { margin-top: 12px; border: 1px solid #000; background: #fff; }
.knobs-section > summary { cursor: pointer; padding: 8px 11px; font-weight: 650;
  background: #fafafa; border-bottom: 1px solid transparent; font-size: 13px; }
.knobs-section[open] > summary { border-bottom: 1px solid #000; }
.knobs-sub { font-weight: 400; color: #778; font-size: 11.5px; margin-left: 8px; }
.knobs-body { padding: 11px; display: grid; gap: 11px;
  grid-template-columns: repeat(auto-fill, minmax(268px, 1fr)); }
.knob-card { border: 1px solid #ddd; border-radius: 5px; padding: 9px 11px; }
.knob-card h3 { margin: 0 0 7px; font-size: 10.5px; letter-spacing: 1px;
  text-transform: uppercase; color: #778; font-weight: 700; }
.knob-row { display: grid; grid-template-columns: 96px 1fr 46px; gap: 7px;
  align-items: center; margin-bottom: 6px; }
.knob-row label { font-size: 11.5px; color: #333; }
.knob-row input[type=range] { width: 100%; }
.knob-row input[type=text], .knob-row select { width: 100%; font-size: 11.5px;
  padding: 2px 4px; }
.knob-row input[type=color] { width: 100%; height: 21px; padding: 0; border: 0; }
.knob-val { font: 11px ui-monospace, Menlo, monospace; color: #667;
  text-align: right; }
.sheet-panel { grid-column: 1 / -1; border-top: 1px solid #ddd; padding-top: 10px;
  display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.sheet-panel select { font-size: 11.5px; padding: 3px 5px; min-width: 150px; }
.sheet-panel button { font: 11.5px sans-serif; padding: 3px 9px; cursor: pointer;
  border: 1px solid #ccc; background: #fafafa; border-radius: 3px; }
.sheet-panel button:hover { background: #eef4fb; border-color: #9dc0e4; }
.sheet-panel .lbl { font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase;
  color: #778; font-weight: 700; margin-right: 2px; }

/* ---- context menu: same kit as the chart studio ---- */
.cfsmenu { position: fixed; z-index: 9999; background: #fff;
  border: 1px solid #c8d2de; border-radius: 7px;
  box-shadow: 0 8px 26px rgba(12,26,45,.19); padding: 6px; min-width: 236px;
  max-width: 330px; font: 13px/1.4 sans-serif; max-height: 86vh; overflow: auto; }
.cfsmenu .mh { font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase;
  color: #8494a6; padding: 7px 9px 4px; }
.cfsmenu .mr { display: flex; justify-content: space-between; gap: 14px;
  align-items: center; padding: 6px 9px; border-radius: 5px; cursor: pointer; }
.cfsmenu .mr:hover { background: #eef4fb; color: #1d6fc4; }
.cfsmenu .mr .k { font: 11px ui-monospace, Menlo, monospace; color: #9aa8b8;
  white-space: nowrap; }
.cfsmenu .sep { height: 1px; background: #e6ecf3; margin: 5px 4px; }
.cfsmenu .sw { display: grid; grid-template-columns: repeat(8, 1fr); gap: 4px;
  padding: 6px 9px; }
.cfsmenu .sw i { display: block; height: 19px; border-radius: 3px; cursor: pointer;
  border: 1px solid rgba(0,0,0,.14); }
.cfsmenu .sw i:hover { transform: scale(1.14); }
.cfsmenu .chips { display: flex; flex-wrap: wrap; gap: 4px; padding: 6px 9px; }
.cfsmenu .chips b { font-weight: 500; font-size: 12px; padding: 3px 8px;
  border: 1px solid #d3dce6; border-radius: 20px; cursor: pointer;
  background: #fbfcfe; white-space: nowrap; }
.cfsmenu .chips b:hover { background: #e8f0fa; border-color: #9dc0e4; color: #1d4b80; }
.cfsmenu .chips b.on { background: #003359; border-color: #003359; color: #fff; }
.cfsmenu .num { display: flex; gap: 6px; padding: 6px 9px; align-items: center; }
.cfsmenu .num input { flex: 1; min-width: 0; font: 12px ui-monospace, Menlo, monospace;
  padding: 4px 6px; border: 1px solid #d3dce6; border-radius: 5px; }
.cfsmenu .num button { font: 12px sans-serif; padding: 4px 11px; cursor: pointer;
  border: 1px solid #003359; background: #003359; color: #fff; border-radius: 5px; }
.cfsmenu .note { font-size: 11.5px; color: #8494a6; padding: 2px 9px 7px;
  line-height: 1.45; }

/* ---- toast ---- */
.toast { position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%);
  background: #22262e; color: #fff; padding: 9px 17px; border-radius: 7px;
  font-size: 13px; z-index: 10000; opacity: 0; transition: opacity .18s;
  pointer-events: none; max-width: 70vw; }
.toast.on { opacity: 1; }

body.fullscreen .layout { grid-template-columns: 1fr; }
body.fullscreen .sidebar, body.fullscreen .knobs-section { display: none; }
</style>
</head>
<body>

<h1 id="pageTitle">__TITLE__</h1>
<p class="subline">Table Studio &middot; <span id="shapeLine"></span> &middot;
  <b>right-click</b> a cell, a header, or the table background &middot;
  <b>double-click</b> a cell to change its value &middot; <b>drag</b> the
  table's edge or a header edge to resize</p>

<div class="layout">

  <!-- ============ table panel ============ -->
  <div class="panel" id="tablePanel">
    <div class="table-toolbar">
      <button id="btnPng" class="primary">Download</button>
      <button id="btnUndo" disabled>Undo</button>
      <button id="btnReset">Reset</button>
      <button id="btnFull">Fullscreen</button>
      <button id="btnFit" class="hidden">Actual size</button>
      <button id="btnAdvanced">All controls</button>
      <span class="sizetag" id="sizeTag"></span>
    </div>
    <div id="tableWrap">
      <div id="tableScale">
        <div id="tableMount"></div>
        <div class="ts-frame"></div>
        <div class="ts-grip ts-grip-e"  data-ts-grip="e"
          title="Drag to widen or narrow every column"></div>
        <div class="ts-grip ts-grip-s"  data-ts-grip="s"
          title="Drag to change row height"></div>
        <div class="ts-grip ts-grip-se" data-ts-grip="se"
          title="Drag to resize both"></div>
      </div>
    </div>
    <div class="hint" id="hintLine"></div>
    <div class="ts-sizetag" id="tsSizeTag"></div>
  </div>

  <!-- ============ sidebar ============ -->
  <div class="panel sidebar">
    <div class="tabs">
      <button class="tab-button active" data-tab="data">Data</button>
      <button class="tab-button" data-tab="code">Code</button>
      <button class="tab-button" data-tab="metadata">Metadata</button>
      <button class="tab-button" data-tab="export">Export</button>
    </div>

    <div class="tab-pane active" id="pane-data">
      <div class="tab-toolbar">
        <input type="search" id="dataSearch" placeholder="Filter rows...">
        <button data-dl="csv">CSV</button>
        <button data-dl="tsv">TSV</button>
        <button data-dl="json">JSON</button>
      </div>
      <div id="dataTableContainer"></div>
    </div>

    <div class="tab-pane" id="pane-code">
      <div class="tab-toolbar">
        <button id="btnCopyCall">Copy call</button>
        <button id="btnDlCall">Download .py</button>
        <span style="font-size:11px;color:#778">regenerated from your edits</span>
      </div>
      <pre class="code" id="codePane"></pre>
    </div>

    <div class="tab-pane" id="pane-metadata">
      <dl class="meta-grid" id="metaGrid"></dl>
    </div>

    <div class="tab-pane" id="pane-export">
      <div class="export-sec"><h4>Image</h4>
        <button data-x="png2">PNG (2x, what PRISM emits)</button>
        <button data-x="png1">PNG (1x, on-screen size)</button>
        <button data-x="png4">PNG (4x, extra large)</button>
      </div>
      <div class="export-sec"><h4>Code</h4>
        <button data-x="call">make_table(...) call &mdash; .py</button>
        <button data-x="datapy">DataFrame rebuild &mdash; .py</button>
      </div>
      <div class="export-sec"><h4>Data</h4>
        <button data-x="csv">CSV</button>
        <button data-x="tsv">TSV</button>
        <button data-x="json">JSON</button>
      </div>
      <div class="export-sec"><h4>State</h4>
        <button data-x="kwargs">make_table kwargs &mdash; .json</button>
        <button data-x="model">Cell model &mdash; .json</button>
        <button data-x="sheet">Style sheet &mdash; .json</button>
      </div>
    </div>
  </div>
</div>

<details class="knobs-section" id="knobsSection">
  <summary id="knobsSummary">Advanced controls
    <span class="knobs-sub">everything above is also reachable by
      right-clicking the thing it affects</span></summary>
  <div class="knobs-body" id="knobsBody"></div>
</details>

<script>
// ===========================================================================
// INJECTED STATE
// ===========================================================================
const BASE_MODEL   = __MODEL_JSON__;
const BASE_KWARGS  = __KWARGS_JSON__;
const KNOBS        = __KNOBS_JSON__;
const THEMES       = __THEMES_JSON__;
const PALETTES     = __PALETTES_JSON__;
const RAG_COLORS   = __RAG_COLORS_JSON__;
const NUMBER_FORMATS = __NUMBER_FORMATS_JSON__;
const DATE_FORMATS   = __DATE_FORMATS_JSON__;
const COLOR_MODES    = __COLOR_MODES_JSON__;
const HEATMAP_SCOPES = __HEATMAP_SCOPES_JSON__;
const SWATCHES     = __SWATCHES_JSON__;
const GROUP_ORDER  = __GROUP_ORDER_JSON__;
const PREF_KEY     = "__PREF_KEY__";
const SHEETS_KEY   = "__SHEETS_KEY__";
const FILENAME     = "__FILENAME__";
const TABLE_ID     = "__TABLE_ID__";
const PNG_PATH     = "__PNG_PATH__";
const DF_NAME      = "__DF_NAME__";
const INITIAL_SHEETS = __SHEETS_JSON__;
const INITIAL_ACTIVE_SHEET = "__ACTIVE_SHEET__";

// ===========================================================================
// LIVE STATE
//   K -- the make_table kwargs. Styling, and the studio's state for it;
//        every gesture writes here and the Code tab serialises it straight
//        back to Python.
//   D -- the data. Which columns exist, in what order, the raw value behind
//        every cell, and the baselines the engine itself produced for them.
//        A structural edit (add / delete / move a row or column) mutates D
//        and nothing else; every visual consequence falls out of rebuild().
//   M -- the cell model. Derived, and ONLY derived: rebuild() is
//        (K, D) -> M and is the single path from state to pixels.
//
// K addresses D by POSITION in nine places, so the two cannot move
// independently -- see POSITIONAL and applyStructural() below.
// ===========================================================================
const clone = (o) => JSON.parse(JSON.stringify(o));

let K = clone(BASE_KWARGS);
let M = clone(BASE_MODEL);
const BASE_THEME = clone(BASE_MODEL.theme);

// Splits the engine's model into the data half. The baselines travel with
// the value they describe rather than with a position, so a row that moves
// keeps the exact text, line breaks and height PIL measured for it instead
// of being re-measured with whatever font the browser happens to have.
function extractData(model) {
  return {
    columns: model.columns.map((c, ci) => ({
      name: c.name,
      kind: c.kind,
      int_dtype: !!c.int_dtype,
      wrap: !!c.wrap,
      minibar_src: c.minibar_src || null,
      w0: model.geom.col_widths[ci],
      fmt0: c.fmt == null ? null : c.fmt,
      align0: c.align,
    })),
    rows: model.rows.map((row) => ({
      h0: row.h,
      cells: row.cells.map((cell) => ({
        raw: cell.raw === undefined ? null : cell.raw,
        spark: cell.spark || null,
        text0: cell.text,
        lines0: cell.lines,
      })),
    })),
    // What was DONE to the data, in order, alongside what it now is. A
    // structural edit that is a rule -- drop this column, sort by that one,
    // total at the bottom -- can be replayed over next month's numbers; one
    // that is a typed value cannot. Recording both lets the codegen emit the
    // original frame plus the rules when every edit is replayable, and fall
    // back to the edited frame when one of them is not.
    ops: [],
  };
}

let D = extractData(BASE_MODEL);
let selection = [];          // [[r,c], ...]
let colSelection = [];       // [c, ...] for heatmap grouping
let _undo = [];
let sheets = clone(INITIAL_SHEETS || {});
let activeSheet = INITIAL_ACTIVE_SHEET || "(none)";
let _sortCol = null, _sortAsc = true;

// ===========================================================================
// SMALL UTILITIES
// ===========================================================================
const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function toast(msg) {
  let t = document.getElementById("_toast");
  if (!t) { t = document.createElement("div"); t.id = "_toast";
            t.className = "toast"; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add("on");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 1900);
}

function download(name, text, mime) {
  const blob = new Blob([text], { type: mime || "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 200);
}

function syncUndoButton() {
  const b = document.getElementById("btnUndo");
  const top = _undo[_undo.length - 1];
  b.disabled = !top;
  b.textContent = "Undo";
  b.title = top ? "Undo: " + top.label : "";
}

// Returns the entry so a gesture that snapshots at pointer-down can take it
// back off the stack if the drag turned out to change nothing.
//
// Both halves of the state are snapshotted, unconditionally. A structural
// edit moves D and K together, and an undo that restored only one of them
// would leave the styling addressing rows that are no longer there -- so
// there is one snapshot shape rather than a styling one and a data one to
// pick between at every call site.
function pushUndo(label) {
  const entry = { K: clone(K), D: clone(D), label: label || "edit" };
  _undo.push(entry);
  if (_undo.length > 60) _undo.shift();
  syncUndoButton();
  return entry;
}

function restoreSnapshot(entry) {
  K = entry.K;
  D = entry.D;
}

/**
 * Record what a structural edit was, in pandas.
 *
 * `py` is the line that reproduces the edit over any frame with the same
 * columns. Passing null instead says the edit cannot be replayed -- it typed
 * a value, or addressed a row by position -- and `why` is shown to the user
 * in the generated code as the reason the original frame could not be kept.
 * One unreplayable edit is enough to take the whole call out of replay mode,
 * because the later rules were expressed against the edited frame.
 */
function pushOp(py, why) {
  D.ops = D.ops || [];
  D.ops.push(py == null ? { py: null, why: why } : { py: py });
}

function dataIsReplayable() {
  return (D.ops || []).every((o) => o.py != null);
}

const pyBool = (v) => (v ? "True" : "False");
const pyNames = (names) => "[" + names.map(pyLit).join(", ") + "]";

// ===========================================================================
// COLOUR MATHS -- ports of chart_functions._tbl_* so a colour-mode change
// resolves live instead of needing a Python round-trip.
// ===========================================================================
function hex2rgb(h) {
  h = String(h || "#000000").replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16),
          parseInt(h.slice(4, 6), 16)];
}
// Lower case, matching _rgb_to_hex's "%02x". Both sides compute the same
// colour; spelling it the same way is what lets a heatmap cell survive the
// codegen round-trip as the identical literal rather than a same-pixel
// different-string one.
//
// Python's round() breaks a tie to the nearest EVEN integer where
// Math.round() breaks it upward, so a channel landing exactly on .5 -- which
// pale heat shades do land on -- would otherwise render one step off the
// engine for the same arithmetic.
function roundHalfEven(n) {
  const f = Math.floor(n), d = n - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}
function rgb2hex(r, g, b) {
  const c = (n) => Math.max(0, Math.min(255, roundHalfEven(n)))
                     .toString(16).padStart(2, "0");
  return "#" + c(r) + c(g) + c(b);
}
function blend(c1, c2, t) {
  t = Math.max(0, Math.min(1, t));
  const a = hex2rgb(c1), b = hex2rgb(c2);
  return rgb2hex(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t,
                 a[2] + (b[2] - a[2]) * t);
}
function readableOn(bg) {
  const [r, g, b] = hex2rgb(bg);
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) > 140 ? "#000000" : "#FFFFFF";
}
function relLum(hexc) {
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  const [r, g, b] = hex2rgb(hexc).map((v) => v / 255);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function contrastRatio(fg, bg) {
  const a = relLum(fg), b = relLum(bg);
  const hi = Math.max(a, b), lo = Math.min(a, b);
  return (hi + 0.05) / (lo + 0.05);
}
function paletteSeq(pal, value, vmin, vmax) {
  if (vmax === vmin) return null;
  const t = Math.max(0, Math.min(1, (value - vmin) / (vmax - vmin)));
  const spec = PALETTES[pal] || PALETTES["bw"];
  if (spec.kind !== "sequential") return blend("#FFFFFF", spec.pos, t * spec.max_i);
  return blend("#FFFFFF", spec.end, t > 0 ? t * spec.max_i + 0.05 : 0);
}
function paletteDiv(pal, value, extent, center) {
  if (!extent) return null;
  center = center || 0;
  const t = Math.max(-1, Math.min(1, (value - center) / extent));
  const spec = PALETTES[pal] || PALETTES["rwg"];
  if (spec.kind !== "diverging") {
    return t >= 0 ? blend("#FFFFFF", spec.end, Math.abs(t) * spec.max_i)
                  : blend("#FFFFFF", "#5B5B5B", Math.abs(t) * spec.max_i);
  }
  return t >= 0 ? blend("#FFFFFF", spec.pos, t * spec.max_i)
                : blend("#FFFFFF", spec.neg, Math.abs(t) * spec.max_i);
}
function ragColor(v, thr) {
  if (v == null || thr == null) return null;
  if (Array.isArray(thr) && thr.length === 2) {
    if (v < thr[0]) return RAG_COLORS.red;
    if (v < thr[1]) return RAG_COLORS.amber;
    return RAG_COLORS.green;
  }
  if (typeof thr === "object") {
    if (thr.red_below != null && thr.amber_below != null) {
      if (v < +thr.red_below) return RAG_COLORS.red;
      if (v < +thr.amber_below) return RAG_COLORS.amber;
      return RAG_COLORS.green;
    }
    if (thr.amber_above != null && thr.red_above != null) {
      if (v > +thr.red_above) return RAG_COLORS.red;
      if (v > +thr.amber_above) return RAG_COLORS.amber;
      return RAG_COLORS.green;
    }
  }
  return null;
}

// ===========================================================================
// FORMATTING -- port of chart_functions._tbl_smart_format
// ===========================================================================
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
                "Jul","Aug","Sep","Oct","Nov","Dec"];
const pad2 = (n) => (n < 10 ? "0" : "") + n;

// The model carries pandas' isoformat() of a NAIVE Timestamp. Parsing the
// components directly rather than through Date() keeps it naive: Date()
// would read "2026-07-24T00:00:00" as local time and any subsequent
// getUTC* would shift it by the viewer's offset, so the same table would
// print different times in London and New York.
function dateParts(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(String(iso));
  if (!m) return { dd: "", mon: "", yyyy: "", yy: "", mm: "", HH: "", MI: "", q: "Q1" };
  const mo = parseInt(m[2], 10);
  return { dd: m[3], mon: MONTHS[mo - 1], yyyy: m[1], yy: m[1].slice(2),
           mm: m[2], HH: m[4] || "00", MI: m[5] || "00",
           q: "Q" + (Math.floor((mo - 1) / 3) + 1) };
}
function strftimeLite(iso, fmt) {
  const p = dateParts(iso);
  return String(fmt).replace(/%d/g, p.dd).replace(/%b/g, p.mon)
    .replace(/%Y/g, p.yyyy).replace(/%y/g, p.yy).replace(/%m/g, p.mm)
    .replace(/%H/g, p.HH).replace(/%M/g, p.MI).replace(/%q/g, p.q.slice(1));
}
function fmtDate(iso, hint) {
  const named = DATE_FORMATS.find((f) => f.hint === hint);
  if (named) return strftimeLite(iso, named.strftime);
  if (hint && hint.indexOf("%") >= 0) return strftimeLite(iso, hint);
  return strftimeLite(iso, "%d %b");
}
// Line-for-line port of chart_functions._tbl_smart_format's numeric branch.
// The two must agree exactly: the engine formats the PNG and this formats the
// DOM, and a cell whose text differs between them would make the studio's
// preview a lie. Python's "{:+.1f}" prints "+0.0", not "0.0", hence sg() on
// >= 0 rather than > 0; "{:,.1f}" groups thousands, hence the grouped forms.
function grp(n, d) {
  return n.toLocaleString("en-US",
    { minimumFractionDigits: d, maximumFractionDigits: d });
}
function fmtNumber(v, hint) {
  const n = Number(v);
  if (!isFinite(n)) return String(v);
  // Python's format spec keeps the sign of -0.0 ("-0.0") where JS toFixed
  // drops it, and applies "+" to the ROUNDED integer for the bp forms, so
  // -0.45bp_signed is "+0bp" rather than "-0bp".
  const neg0 = Object.is(n, -0) ? "-" : "";
  const fx = (d) => neg0 + n.toFixed(d);
  const sg = (x) => (x >= 0 ? "+" : "");
  const rounded = () => { const r = Math.round(n); return r === 0 ? 0 : r; };
  switch (hint) {
    case "pct": case "percent": return fx(1) + "%";
    case "pct_signed":   return (neg0 ? "" : sg(n)) + fx(1) + "%";
    case "pct2":         return fx(2) + "%";
    case "pct2_signed":  return (neg0 ? "" : sg(n)) + fx(2) + "%";
    case "bp": case "bps": return rounded() + "bp";
    case "bp_signed":    return sg(rounded()) + rounded() + "bp";
    case "ratio":        return fx(2) + "x";
    case "int":          return grp(rounded(), 0);
    case "currency": {
      const a = Math.abs(n), s = n < 0 ? "-" : "";
      if (a >= 1e9) return s + "$" + (a / 1e9).toFixed(2) + "B";
      if (a >= 1e6) return s + "$" + (a / 1e6).toFixed(2) + "M";
      if (a >= 1e3) return s + "$" + grp(a / 1e3, 1) + "k";
      return s + "$" + grp(a, 2);
    }
  }
  // Auto. The calendar-year heuristic only fires when no hint was given at
  // all, matching the engine's `hint is None` gate -- an explicit empty
  // string means "the default number path", not "guess at years".
  const a = Math.abs(n);
  if (hint == null && Number.isInteger(n) && a >= 1900 && a <= 2200) return String(n);
  if (a >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return grp(n, 1);
  if (a >= 1) return fx(2);
  if (a === 0) return "0.00";   // engine returns the literal, sign and all
  return fx(3);
}
function formatRaw(raw, hint) {
  if (raw == null) return "";
  if (typeof raw === "object" && raw.__date__) return fmtDate(raw.__date__, hint);
  if (typeof raw === "number") return fmtNumber(raw, hint);
  return String(raw);
}

// ===========================================================================
// TEXT MEASUREMENT
//
// Canvas metrics stand in for PIL's font.getlength so a column dragged
// narrower re-wraps where the engine would re-wrap it. They are not the same
// metrics though -- the browser may not have GS Sans, and even when it does,
// hinting differs -- so measurement is used only where the engine's own
// answer has been invalidated. An untouched cell keeps the lines PIL
// produced, which is what makes the initial render match the PNG exactly
// instead of merely closely. See ``pristine()``.
// ===========================================================================
// Python's int() truncates toward zero. Every geometry constant the engine
// derives goes through it, so the port needs the same rounding or the two
// layouts drift a pixel at a time.
const trunc = Math.trunc;

const _mctx = document.createElement("canvas").getContext("2d");
function fontStr(size, bold) {
  return (bold ? "bold " : "") + size + "px " + (M.theme.font_family || "Arial, Helvetica, sans-serif");
}
function measure(text, size, bold) {
  _mctx.font = fontStr(size, bold);
  return _mctx.measureText(String(text == null ? "" : text)).width;
}
function wrapText(text, maxW, size, bold) {
  if (text == null || text === "") return [""];
  const out = [];
  String(text).split("\n").forEach((para) => {
    const words = para.split(/\s+/).filter(Boolean);
    if (!words.length) { out.push(""); return; }
    let cur = "";
    words.forEach((w) => {
      const cand = cur ? cur + " " + w : w;
      if (measure(cand, size, bold) <= maxW) { cur = cand; }
      else {
        if (cur) out.push(cur);
        if (measure(w, size, bold) > maxW) {
          let chunk = "";
          for (const ch of w) {
            if (measure(chunk + ch, size, bold) > maxW && chunk) {
              out.push(chunk); chunk = ch;
            } else chunk += ch;
          }
          cur = chunk;
        } else cur = w;
      }
    });
    if (cur) out.push(cur);
  });
  return out.length ? out : [""];
}

// ===========================================================================
// MODEL REBUILD -- K + raw values -> M
//
// The single place the studio derives presentation from state. Every gesture
// mutates K then calls redraw(), so there is exactly one code path from
// kwargs to pixels, the same way the engine has exactly one.
// ===========================================================================
function theme() { return M.theme; }
function colByName(name) { return M.columns.findIndex((c) => c.name === name); }
// The data's own lookup. M is last frame's render, so anything running
// between one redraw and the next has to ask D instead.
function dColByName(name) { return D.columns.findIndex((c) => c.name === name); }
function ck(r, c) { return r + "," + c; }

function columnNumbers(ci) {
  const out = [];
  M.rows.forEach((row) => {
    const cell = row.cells[ci];
    if (cell && typeof cell.raw === "number" && isFinite(cell.raw)) out.push(cell.raw);
  });
  return out;
}
function rowNumbers(rowIdx, cols) {
  const out = [];
  cols.forEach((name) => {
    const ci = colByName(name); if (ci < 0) return;
    const cell = M.rows[rowIdx].cells[ci];
    if (cell && typeof cell.raw === "number" && isFinite(cell.raw)) out.push(cell.raw);
  });
  return out;
}

function resolveHeatmap(r, ci) {
  const groups = K.heatmap_groups || [];
  const name = M.columns[ci].name;
  for (const g of groups) {
    if (!(g.columns || []).includes(name)) continue;
    const cell = M.rows[r].cells[ci];
    if (typeof cell.raw !== "number" || !isFinite(cell.raw)) return null;
    const pal = g.palette || (g.mode === "diverging" ? "rwg" : "bw");
    const mode = g.mode || (["rwg","rwb","bwr","owb"].includes(pal) ? "diverging" : "sequential");
    const center = g.center == null ? 0 : +g.center;
    let pool = [];
    if (g.scope === "row") pool = rowNumbers(r, g.columns);
    else if (g.scope === "group") {
      g.columns.forEach((n) => { const i = colByName(n);
        if (i >= 0) pool = pool.concat(columnNumbers(i)); });
    } else pool = columnNumbers(ci);
    if (!pool.length) return null;
    const lo = Math.min(...pool), hi = Math.max(...pool);
    if (mode === "sequential") return paletteSeq(pal, cell.raw, lo, hi);
    const extent = Math.max(Math.abs(lo - center), Math.abs(hi - center));
    return paletteDiv(pal, cell.raw, extent, center);
  }
  return null;
}

function resolveColumnMode(r, ci) {
  const name = M.columns[ci].name;
  const raw = (K.column_color_modes || {})[name];
  if (!raw) return null;
  const spec = (typeof raw === "string") ? { mode: raw } : raw;
  const mode = spec.mode || "none";
  const cell = M.rows[r].cells[ci];
  const v = (typeof cell.raw === "number" && isFinite(cell.raw)) ? cell.raw : null;
  if (mode === "rag") {
    const thr = spec.thresholds || (K.rag_thresholds || {})[name];
    return (thr == null || v == null) ? null : ragColor(v, thr);
  }
  if (mode === "highlight") return spec.color || theme().highlight_color || "#E8F0F7";
  if (v == null) return null;
  const pal = spec.palette || (["heatmap","sequential","bw"].includes(mode) ? "bw" : "rwg");
  const center = spec.center == null ? 0 : +spec.center;
  const pool = columnNumbers(ci);
  if (!pool.length) return null;
  const lo = Math.min(...pool), hi = Math.max(...pool);
  if (mode === "bw" || mode === "heatmap" || mode === "sequential")
    return paletteSeq(pal === "rwg" ? "bw" : pal, v, lo, hi);
  if (mode === "rwg" || mode === "diverging" || mode === "diverging_at_zero") {
    const extent = Math.max(Math.abs(lo - center), Math.abs(hi - center));
    return paletteDiv(pal === "bw" ? "rwg" : pal, v, extent, center);
  }
  return null;
}

function rebuild() {
  // --- theme ---
  const base = THEMES[K.skin || "gs_clean"];
  M.theme = Object.assign({}, BASE_THEME, base, K._theme_overrides || {});
  const th = M.theme;
  const bodyFs = th.body_font_size, headFs = th.header_font_size;

  // --- columns, from D ---
  M.columns = D.columns.map((dc) => ({
    name: dc.name,
    kind: dc.kind,
    int_dtype: dc.int_dtype,
    wrap: dc.wrap,
    minibar_src: dc.minibar_src,
    numeric: dc.kind === "num",
    fmt0: dc.fmt0,
    align0: dc.align0,
    fmt: (K.column_formats || {})[dc.name] ?? dc.fmt0 ?? null,
    align: (K.column_aligns || {})[dc.name] || dc.align0,
    width: (K.column_widths || {})[dc.name] || dc.w0,
  }));
  M.geom.col_widths = M.columns.map((col) => col.width);

  // Formulas and aggregate rows are re-evaluated into D before anything
  // reads a value, so a computed column behaves as an ordinary column of
  // numbers everywhere downstream -- including the minibar extents and the
  // wrapped-line measurement below.
  materialiseDerived();

  // A column is pristine while nothing that could change where its text
  // breaks has moved. While it is, the engine's own wrapped lines are used
  // verbatim rather than being re-measured in the browser.
  const fontPristine = bodyFs === BASE_THEME.body_font_size;
  const pristine = (ci) => fontPristine
    && M.columns[ci].fmt === M.columns[ci].fmt0
    && !((K.column_widths || {})[M.columns[ci].name]);

  // --- minibar scale, from D ---
  // The bar and the extent it is drawn against are data, not styling, so
  // both are derived here rather than baked at build time -- deleting the
  // largest row has to rescale every remaining bar, the same way re-running
  // make_table on the smaller frame would.
  const barMax = {};
  D.columns.forEach((dc) => {
    if (dc.kind !== "minibar") return;
    const si = D.columns.findIndex((c) => c.name === dc.minibar_src);
    let m = 0;
    if (si >= 0) D.rows.forEach((row) => {
      const v = row.cells[si] ? row.cells[si].raw : null;
      if (typeof v === "number" && isFinite(v)) m = Math.max(m, Math.abs(v));
    });
    barMax[dc.name] = m;
  });

  // --- rows, from D ---
  M.rows = D.rows.map((dr, r) => ({
    r: r,
    h: dr.h0,
    h0: dr.h0,
    kind: "normal",
    group: null,
    row_bg: null,
    cells: dr.cells.map((dcell, ci) => {
      const dc = D.columns[ci];
      const kind = dc ? dc.kind : "text";
      const cell = {
        c: ci,
        kind: (kind === "spark" || kind === "minibar") ? kind : "text",
        raw: dcell.raw,
        text: "", lines: [], bg: null, fg: null, indent: 0,
        text0: dcell.text0, lines0: dcell.lines0,
      };
      if (kind === "spark") cell.spark = dcell.spark || [];
      if (kind === "minibar") {
        const si = D.columns.findIndex((c) => c.name === dc.minibar_src);
        const v = (si >= 0 && dr.cells[si]) ? dr.cells[si].raw : null;
        cell.bar = {
          v: (typeof v === "number" && isFinite(v)) ? v : 0.0,
          max: barMax[dc.name] || 0.0,
        };
      }
      return cell;
    }),
  }));

  const highlight = K.highlight_columns || [];
  const signed    = K.signed_columns || [];
  const totals    = K.total_rows || [];
  const subs      = K.subtotal_rows || [];
  const rowCols   = K.row_colors || {};
  const cellCols  = K.cell_colors || {};
  const cellTexts = K.cell_text_colors || {};
  const indents   = K.row_indent || [];
  const scale     = K.row_height_scale || 1.0;

  // --- group bands ---
  const groupStart = {};
  let cursor = 0;
  (K.row_groups || []).forEach(([label, count]) => {
    groupStart[cursor] = label; cursor += count;
  });

  M.rows.forEach((row, r) => {
    row.group = groupStart[r] != null ? groupStart[r] : null;
    row.kind = totals.includes(r) ? "total"
             : subs.includes(r) ? "subtotal" : "normal";

    // row background, in the engine's paint order
    let rowBg = null;
    if (row.kind === "total") rowBg = th.total_band;
    else if (row.kind === "subtotal") rowBg = th.subtotal_band;
    else {
      if (K.row_bands !== false && r % 2 === 1) rowBg = th.row_band_color;
      if (rowCols[r]) rowBg = rowCols[r];
    }
    row.row_bg = rowBg;

    let maxLines = 1;
    let rowDirty = false;
    row.cells.forEach((cell, ci) => {
      const col = M.columns[ci];

      // ---- background ----
      let bg = null;
      if (row.kind !== "total") {
        // The engine paints the highlight over the row band, not instead of
        // it, and leaves subtotal rows alone.
        if (highlight.includes(col.name) && row.kind !== "subtotal")
          bg = th.highlight_color;
        const hm = resolveHeatmap(r, ci);
        const cm = hm == null ? resolveColumnMode(r, ci) : hm;
        if (cm != null) bg = cm;
      }
      if (cellCols[ck(r, ci)]) bg = cellCols[ck(r, ci)];
      cell.bg = bg;

      if (cell.kind === "spark" || cell.kind === "minibar") return;

      // ---- text ----
      const ov = (K.value_overrides || {})[ck(r, ci)];
      cell.text = ov !== undefined ? String(ov) : formatRaw(cell.raw, col.fmt);

      // ---- foreground ----
      let fg = cellTexts[ck(r, ci)] || null;
      if (!fg) {
        const eff = bg || rowBg;
        if (row.kind === "total") fg = "#FFFFFF";
        else if (signed.includes(col.name) && typeof cell.raw === "number") {
          fg = cell.raw > 0 ? th.positive_text
             : cell.raw < 0 ? th.negative_text : th.body_text;
          if (eff && fg !== th.body_text && contrastRatio(fg, eff) < 3.0)
            fg = readableOn(eff);
        } else if (eff) fg = readableOn(eff);
        else fg = th.body_text;
      }
      cell.fg = fg;

      // ---- indent + wrapping ----
      cell.indent = (ci === 0 && indents[r]) ? indents[r] * 16 : 0;
      if (pristine(ci) && cell.text === cell.text0) {
        cell.lines = cell.lines0;
      } else {
        const avail = Math.max(20, col.width - 20 - cell.indent);
        const bold = row.kind !== "normal";
        cell.lines = (col.wrap || measure(cell.text, bodyFs, bold) > avail)
          ? wrapText(cell.text, avail, bodyFs, bold) : [cell.text];
        rowDirty = true;
      }
      if (cell.lines.length > maxLines) maxLines = cell.lines.length;
    });

    if (!rowDirty && scale === 1.0 && bodyFs === BASE_THEME.body_font_size) {
      row.h = row.h0;
    } else {
      // _tbl_row_heights, verbatim. Python's int() truncates, so trunc()
      // rather than round() -- the difference is a pixel per row, and rows
      // accumulate.
      const lineH = trunc(bodyFs * 1.45);
      const baseH = trunc(bodyFs * 1.95);
      let h = Math.max(baseH, maxLines * lineH + 8);
      if (scale !== 1.0)
        h = Math.max(maxLines * lineH + 8, trunc(h * scale));
      row.h = h;
    }
  });

  // --- header height + canvas ---
  // Every constant below is _tbl_layout's. They were previously eyeballed,
  // which left the browser table a few pixels taller per band than the PNG
  // and drifting further apart the further down the table you looked.
  const levels = (K.header_levels || M.header_levels || []).length;
  M.geom.header_h = trunc(headFs * 1.7) * (levels + 1);
  M.geom.group_band_h = trunc(bodyFs * 1.85);

  const tableW = M.geom.col_widths.reduce((a, b) => a + b, 0);
  const nGroups = Object.keys(groupStart).length;

  // _tbl_measure_title: one 6px lead, one 8px trail, and the line totals
  // truncated as a product rather than per line.
  let titleH = 0;
  if (M.title.lines.length || M.title.subtitle.length) {
    titleH = 6;
    if (M.title.lines.length)
      titleH += trunc(M.title.lines.length * th.title_font_size * 1.2);
    if (M.title.subtitle.length)
      titleH += trunc(M.title.subtitle.length * th.subtitle_font_size * 1.4);
    titleH += 8;
  }
  // _tbl_measure_caption.
  const capH = M.title.caption.length
    ? trunc(M.title.caption.length * th.caption_font_size * 1.4) + 12 : 0;
  const bodyH = M.rows.reduce((a, r) => a + r.h, 0) + nGroups * M.geom.group_band_h;

  M.geom.table_w = tableW;
  // The rows-plus-bands band on its own, which is the only part of the canvas
  // row_height_scale moves -- the vertical drag scales against it rather than
  // against the whole canvas, so title and caption do not dilute the gesture.
  M.geom.body_h = bodyH;
  M.geom.body_top_y = titleH + M.geom.header_h + (titleH ? 8 : 0);
  M.canvas.w = tableW + 24;
  // _TBL_BODY_PAD_BOTTOM is 6.
  M.canvas.h = M.geom.body_top_y + bodyH + capH + 6;
}

// ===========================================================================
// RENDER
// ===========================================================================
// sparkGeom / barGeom are line-for-line ports of _tbl_draw_sparkline and
// _tbl_draw_minibar. Both render paths (SVG for the live DOM, canvas for the
// PNG export) consume them, so there is one description of the shape rather
// than three that drift. Coordinates come back relative to the w x h box the
// engine is handed, which the callers place at the same 8px inset the engine
// uses.
function sparkGeom(series, w, h) {
  const vals = (series || []).filter((v) => v != null && !Number.isNaN(v));
  if (vals.length < 2) return null;
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi === lo) hi = lo + 1.0;
  const n = vals.length;
  const pts = vals.map((v, i) => [
    Math.round(i * w / Math.max(1, n - 1)),
    h - Math.round((v - lo) / (hi - lo) * h),
  ]);
  return {pts: pts, last: pts[pts.length - 1]};
}
function barGeom(bar, w, h) {
  if (!bar || bar.v == null || bar.max == null || !bar.max) return null;
  const barH = Math.max(8, h - 6);
  const by = Math.floor((h - barH) / 2);
  const frac = Math.min(1.0, Math.abs(bar.v) / Math.abs(bar.max));
  const bw = Math.round(frac * w);
  return {by: by, h: barH, w: bw, x: bar.v >= 0 ? 0 : w - bw,
          neg: bar.v < 0};
}
function sparkSVG(series, w, h, th) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("width", Math.max(10, w));
  svg.setAttribute("height", Math.max(6, h));
  // The engine's topmost point sits exactly on y=0, so half the 2px stroke
  // falls outside the box. The PNG has row padding to absorb it; the SVG
  // needs to be told not to clip.
  svg.setAttribute("overflow", "visible");
  svg.style.display = "block"; svg.style.margin = "0 8px";
  const g = sparkGeom(series, w, h);
  if (!g) return svg;
  const base = document.createElementNS(ns, "line");
  base.setAttribute("x1", "0"); base.setAttribute("x2", String(w));
  base.setAttribute("y1", String(h)); base.setAttribute("y2", String(h));
  base.setAttribute("stroke", "#DDDDDD"); base.setAttribute("stroke-width", "1");
  svg.appendChild(base);
  const pl = document.createElementNS(ns, "polyline");
  pl.setAttribute("points", g.pts.map((p) => p[0] + "," + p[1]).join(" "));
  pl.setAttribute("fill", "none");
  pl.setAttribute("stroke", th.primary_color);
  pl.setAttribute("stroke-width", "2");
  svg.appendChild(pl);
  const dot = document.createElementNS(ns, "circle");
  dot.setAttribute("cx", String(g.last[0])); dot.setAttribute("cy", String(g.last[1]));
  dot.setAttribute("r", "3.5"); dot.setAttribute("fill", th.primary_color);
  svg.appendChild(dot);
  return svg;
}
function barSVG(bar, w, h, th) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("width", Math.max(10, w));
  svg.setAttribute("height", Math.max(6, h));
  svg.style.display = "block"; svg.style.margin = "0 8px";
  const g = barGeom(bar, w, h);
  if (!g) return svg;
  const track = document.createElementNS(ns, "rect");
  track.setAttribute("x", "0.5"); track.setAttribute("y", String(g.by + 0.5));
  track.setAttribute("width", String(Math.max(0, w - 1)));
  track.setAttribute("height", String(g.h));
  track.setAttribute("fill", "#FAFAFA"); track.setAttribute("stroke", "#E0E0E0");
  track.setAttribute("stroke-width", "1");
  svg.appendChild(track);
  const r = document.createElementNS(ns, "rect");
  r.setAttribute("x", String(g.x)); r.setAttribute("y", String(g.by));
  r.setAttribute("width", String(g.w)); r.setAttribute("height", String(g.h));
  r.setAttribute("fill", g.neg ? th.negative_text : th.primary_color);
  svg.appendChild(r);
  return svg;
}

function renderTable() {
  const th = M.theme, g = M.geom;
  const mount = document.getElementById("tableMount");
  const frame = document.createElement("div");
  frame.className = "pt-frame";
  frame.id = "ptFrame";
  frame.style.fontFamily = th.font_family || "Arial, Helvetica, sans-serif";
  frame.style.background = th.background_color;

  M.title.lines.forEach((line) => {
    const t = document.createElement("div");
    t.className = "pt-title"; t.dataset.role = "title";
    t.style.fontSize = th.title_font_size + "px";
    t.style.height = trunc(th.title_font_size * 1.2) + "px";
    t.textContent = line; frame.appendChild(t);
  });
  M.title.subtitle.forEach((line) => {
    const s = document.createElement("div");
    s.className = "pt-sub"; s.dataset.role = "subtitle";
    s.style.fontSize = th.subtitle_font_size + "px";
    s.style.height = trunc(th.subtitle_font_size * 1.4) + "px";
    s.style.color = th.muted_text;
    s.textContent = line; frame.appendChild(s);
  });

  const tbl = document.createElement("table");
  tbl.className = "pt"; tbl.id = "ptTable";
  tbl.style.width = g.table_w + "px";
  tbl.style.fontSize = th.body_font_size + "px";

  const cg = document.createElement("colgroup");
  g.col_widths.forEach((w) => {
    const c = document.createElement("col"); c.style.width = w + "px";
    cg.appendChild(c);
  });
  tbl.appendChild(cg);

  const levels = K.header_levels || M.header_levels || [];
  const rowH = trunc(g.header_h / (levels.length + 1));
  const thead = document.createElement("thead");
  levels.forEach((level, li) => {
    const tr = document.createElement("tr");
    level.forEach(([label, span], si) => {
      const el = document.createElement("th");
      el.colSpan = span; el.className = "super";
      el.dataset.superLevel = li; el.dataset.superIdx = si;
      el.style.height = rowH + "px";
      el.style.background = th.primary_color; el.style.color = th.header_text;
      el.style.fontSize = th.header_font_size + "px";
      if (si > 0) el.style.borderLeft = "1px solid rgba(255,255,255,.45)";
      el.innerHTML = "<div class='cw'><div class='ln'>" + esc(label) + "</div></div>";
      tr.appendChild(el);
    });
    thead.appendChild(tr);
  });
  const hr = document.createElement("tr");
  M.columns.forEach((col, ci) => {
    const el = document.createElement("th");
    el.dataset.c = ci;
    if (colSelection.includes(ci)) el.className = "colsel";
    el.style.height = rowH + "px";
    el.style.background = th.primary_color; el.style.color = th.header_text;
    el.style.fontSize = th.header_font_size + "px";
    el.style.textAlign = col.align;
    el.innerHTML = "<div class='cw'><div class='ln'>" + esc(col.name) + "</div></div>";
    const grip = document.createElement("div");
    grip.className = "grip"; grip.dataset.c = ci; el.appendChild(grip);
    hr.appendChild(el);
  });
  thead.appendChild(hr);
  tbl.appendChild(thead);

  const tb = document.createElement("tbody");
  M.rows.forEach((row) => {
    if (row.group) {
      const gr = document.createElement("tr");
      gr.className = "grp";
      const td = document.createElement("td");
      td.colSpan = M.columns.length;
      td.style.height = g.group_band_h + "px";
      td.style.background = th.primary_color; td.style.color = th.header_text;
      td.innerHTML = "<div class='cw' style='padding-left:12px'><div class='ln'>"
                     + esc(row.group) + "</div></div>";
      gr.appendChild(td); tb.appendChild(gr);
    }
    const tr = document.createElement("tr");
    tr.dataset.r = row.r;
    if (row.row_bg) tr.style.background = row.row_bg;
    if (row.kind !== "normal") tr.style.fontWeight = "700";
    if (K.row_bands === false && row.r > 0 && row.kind === "normal")
      tr.style.borderTop = "1px solid #E0E0E0";

    row.cells.forEach((cell, ci) => {
      const col = M.columns[ci];
      const td = document.createElement("td");
      td.dataset.r = row.r; td.dataset.c = ci;
      td.style.height = row.h + "px";
      if (cell.bg) {
        // The engine insets a coloured cell rect 1px on every side so the
        // row band shows through. content-box clipping reproduces that.
        td.style.background = cell.bg;
        td.style.border = "1px solid transparent";
        td.style.backgroundClip = "content-box";
      }
      if (selection.some(([a, b]) => a === row.r && b === ci)) td.classList.add("sel");

      if (cell.kind === "spark") {
        td.appendChild(sparkSVG(cell.spark, col.width - 16, row.h - 12, th));
      } else if (cell.kind === "minibar") {
        td.appendChild(barSVG(cell.bar, col.width - 16, row.h - 8, th));
      } else {
        const w = document.createElement("div");
        w.className = "cw";
        w.style.textAlign = col.align; w.style.color = cell.fg;
        if (cell.indent) w.style.paddingLeft = (8 + cell.indent) + "px";
        cell.lines.forEach((L) => {
          const d = document.createElement("div");
          d.className = "ln"; d.textContent = L; w.appendChild(d);
        });
        td.appendChild(w);
      }
      tr.appendChild(td);
    });
    tb.appendChild(tr);
  });
  tbl.appendChild(tb);

  const ruleTop = document.createElement("div");
  ruleTop.className = "pt-rule"; ruleTop.style.background = th.border_color;
  ruleTop.style.width = g.table_w + "px";
  frame.appendChild(ruleTop);
  frame.appendChild(tbl);
  const ruleBot = document.createElement("div");
  ruleBot.className = "pt-rule"; ruleBot.style.background = th.border_color;
  ruleBot.style.width = g.table_w + "px";
  frame.appendChild(ruleBot);

  M.title.caption.forEach((line) => {
    const c = document.createElement("div");
    c.className = "pt-cap"; c.dataset.role = "caption";
    c.style.fontSize = th.caption_font_size + "px";
    c.style.lineHeight = trunc(th.caption_font_size * 1.4) + "px";
    c.style.color = th.muted_text; c.style.marginTop = "6px";
    c.textContent = line; frame.appendChild(c);
  });

  mount.innerHTML = ""; mount.appendChild(frame);
  wireGestures(tbl, frame);
  // The resize frame and its grips sit outside the scaled subtree, so the box
  // they trace has to be re-measured off the new table on every render.
  applyTableFit();
}

// ===========================================================================
// FIT THE TABLE TO THE PANEL
//
// A table is routinely wider than the column the editor gives it -- nine
// columns, a set of pinned widths, or a couple of east drags will do it, and a
// laptop window leaves this panel under 800px -- while the handles the studio
// is built around live on the table's own right and bottom edge. Off the right
// of a scroller they are invisible and unreachable, so the gesture disappears
// exactly on the tables that most need it, and one drag past the panel's width
// used to put the handle being held beyond the edge it had just created. So the
// same deal the chart studio strikes: scale the artifact down until all of it
// and its drag bounds are inside the panel.
//
// The table is still built at its real size and only the painted result is
// scaled, so nothing downstream is affected -- the size tag, the Code tab and
// every PNG export still speak in the table's own pixels.
//
// Width only, as in the chart studio. The page scrolls vertically anyway, and
// squeezing a fifty-row table into a viewport's height would make it
// unreadable for no gain.
// ===========================================================================
let _tfEnabled = true;   // session-only; the toolbar button flips it
let _tfScale = 1;        // 1 means the table is at its real size
let _tfFrozen = null;    // scale held still for the length of a drag

// A pointer travelling one screen pixel across a table drawn at 80% is worth
// 1.25 table pixels, so every drag delta is read back through the frozen
// scale before it reaches the kwargs.
const tfDragScale = () => (_tfFrozen && _tfFrozen > 0 ? _tfFrozen : 1);

function tableAvailableWidth() {
  const wrap = document.getElementById("tableWrap");
  if (!wrap) return 0;
  const cs = getComputedStyle(wrap);
  return wrap.clientWidth -
    parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
}

// offsetWidth rather than getBoundingClientRect: a transform moves the painted
// box but not the layout one, so this keeps reading the table's real size
// instead of ratcheting it smaller on every render.
function naturalTableSize() {
  const f = document.getElementById("ptFrame");
  if (!f) return { w: 0, h: 0 };
  return { w: f.offsetWidth, h: f.offsetHeight };
}

function applyTableFit() {
  const mount = document.getElementById("tableMount");
  const box = document.getElementById("tableScale");
  if (!mount || !box) return;
  const nat = naturalTableSize();
  if (!(nat.w > 0 && nat.h > 0)) return;
  const avail = tableAvailableWidth();
  let s;
  if (_tfFrozen !== null) s = _tfFrozen;
  else if (!_tfEnabled || !(avail > 0)) s = 1;
  else s = Math.min(1, avail / nat.w);
  _tfScale = s;
  if (s >= 0.999) {
    mount.style.transform = "";
    box.style.width = ""; box.style.height = "";
  } else {
    mount.style.transform = "scale(" + s.toFixed(5) + ")";
    // Floor rather than round: half a pixel over the panel is enough to put
    // the scrollbar back, which is the thing being fixed.
    box.style.width  = Math.floor(nat.w * s) + "px";
    box.style.height = Math.floor(nat.h * s) + "px";
  }
  updateFitButton(nat.w, avail);
}

/* The button is the escape hatch, so it only exists when there is something
   to escape from -- on a table that already fits, both modes are identical. */
function updateFitButton(naturalWidth, avail) {
  const b = document.getElementById("btnFit");
  if (!b) return;
  b.classList.toggle("hidden", !(naturalWidth > avail + 1));
  b.textContent = _tfEnabled ? "Actual size" : "Fit to panel";
  b.title = _tfEnabled
    ? "Show the table at 100%; the panel will scroll"
    : "Scale the table down so all of it, and its drag handles, are visible. "
      + "Its real size, and the size it downloads at, do not change.";
}

function toggleTableFit() {
  _tfEnabled = !_tfEnabled;
  applyTableFit();
  updateSizeSummary();
  toast(_tfEnabled
    ? "Fitted to the panel. The table's real size is unchanged."
    : "Showing the table at 100%. Scroll the panel to reach the rest.");
}

// Re-fit only when the panel actually got wider or narrower. The observer also
// fires for the height change a fit itself causes, and refitting on that would
// be a loop.
let _tfObserver = null;
let _tfLastWidth = null;

function installFitObserver() {
  const wrap = document.getElementById("tableWrap");
  if (!wrap || _tfObserver || typeof ResizeObserver === "undefined") return;
  _tfLastWidth = tableAvailableWidth();
  _tfObserver = new ResizeObserver(() => {
    const w = tableAvailableWidth();
    if (Math.abs(w - _tfLastWidth) < 1) return;
    _tfLastWidth = w;
    applyTableFit();
    updateSizeSummary();
  });
  _tfObserver.observe(wrap);
}

// ===========================================================================
// TITLE / SUBTITLE / CAPTION lines derive from the kwargs too
// ===========================================================================
function rebuildTitleLines() {
  const cap = K.caption || (K.source ? "Source: " + K.source : null);
  M.title.lines    = K.title    ? String(K.title).split("\n")    : [];
  M.title.subtitle = K.subtitle ? String(K.subtitle).split("\n") : [];
  M.title.caption  = cap        ? String(cap).split("\n")        : [];
}

// Split out of redraw so a drag frame -- which rebuilds and re-renders
// without going through the full redraw -- can still keep the toolbar
// honest about the size it is producing.
function updateSizeSummary() {
  // The dimensions reported are always the table's real ones; the zoom is
  // appended so a scaled-down view never reads as a smaller table.
  const zoom = _tfScale < 0.999
    ? "  |  zoom " + Math.round(_tfScale * 100) + "%" : "";
  document.getElementById("sizeTag").textContent =
    M.canvas.w + " x " + M.canvas.h + " px  |  " + M.rows.length + " rows x "
    + M.columns.length + " cols  |  body " + M.theme.body_font_size + "px" + zoom;
}

function redraw(label) {
  rebuildTitleLines();
  rebuild();
  renderTable();
  refreshTabs();
  document.getElementById("pageTitle").textContent = K.title || "Table Studio";
  updateSizeSummary();
  document.getElementById("shapeLine").textContent =
    M.rows.length + " rows x " + M.columns.length + " columns";
  if (label) toast(label);
}

// ===========================================================================
// CONTEXT MENU KIT -- same widget vocabulary as the chart studio
// ===========================================================================
function closeMenu() { document.querySelectorAll(".cfsmenu").forEach((m) => m.remove()); }
document.addEventListener("click", closeMenu);
document.addEventListener("scroll", closeMenu, true);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });

function openMenu(x, y, build) {
  closeMenu();
  const m = document.createElement("div");
  m.className = "cfsmenu";
  m.addEventListener("click", (e) => e.stopPropagation());
  m.addEventListener("contextmenu", (e) => { e.preventDefault(); e.stopPropagation(); });
  build(m);
  document.body.appendChild(m);
  const r = m.getBoundingClientRect();
  m.style.left = Math.max(6, Math.min(x, window.innerWidth - r.width - 12)) + "px";
  m.style.top  = Math.max(6, Math.min(y, window.innerHeight - r.height - 12)) + "px";
  return m;
}
function mHead(m, t) {
  const d = document.createElement("div"); d.className = "mh";
  d.textContent = t; m.appendChild(d);
}
function mNote(m, t) {
  const d = document.createElement("div"); d.className = "note";
  d.innerHTML = t; m.appendChild(d);
}
function mRow(m, label, key, fn) {
  const d = document.createElement("div"); d.className = "mr";
  d.innerHTML = "<span>" + label + "</span><span class='k'>" + esc(key || "") + "</span>";
  d.onclick = () => { fn(); closeMenu(); }; m.appendChild(d);
}
function mSep(m) {
  const d = document.createElement("div"); d.className = "sep"; m.appendChild(d);
}
function mSwatches(m, fn) {
  const d = document.createElement("div"); d.className = "sw";
  SWATCHES.forEach((c) => {
    const i = document.createElement("i");
    i.style.background = c; i.title = c;
    i.onclick = () => { fn(c); closeMenu(); }; d.appendChild(i);
  });
  const pick = document.createElement("i");
  pick.style.background = "linear-gradient(135deg,#f66,#6f6,#66f)";
  pick.title = "Custom...";
  pick.onclick = () => {
    const inp = document.createElement("input");
    inp.type = "color"; inp.value = "#003359";
    inp.oninput = () => fn(inp.value.toUpperCase());
    inp.onchange = () => { fn(inp.value.toUpperCase()); closeMenu(); };
    inp.click();
  };
  d.appendChild(pick);
  m.appendChild(d);
}
function mChips(m, items, active, fn) {
  const d = document.createElement("div"); d.className = "chips";
  items.forEach(([val, label]) => {
    const b = document.createElement("b");
    b.textContent = label;
    if (String(val) === String(active == null ? "" : active)) b.className = "on";
    b.onclick = () => { fn(val); closeMenu(); }; d.appendChild(b);
  });
  m.appendChild(d);
}
function mNumber(m, placeholder, initial, fn) {
  const d = document.createElement("div"); d.className = "num";
  const i = document.createElement("input");
  i.type = "text"; i.placeholder = placeholder;
  i.value = initial == null ? "" : String(initial);
  const b = document.createElement("button"); b.textContent = "Apply";
  const go = () => { fn(i.value); closeMenu(); };
  b.onclick = go;
  i.onkeydown = (e) => { if (e.key === "Enter") go(); };
  d.appendChild(i); d.appendChild(b); m.appendChild(d);
  setTimeout(() => i.focus(), 30);
}
// A formula field is wider and monospaced than the numeric ones, because
// column names have to be typed exactly as they appear in the header.
function mFormula(m, initial, fn) {
  const d = document.createElement("div"); d.className = "num";
  const i = document.createElement("input");
  i.type = "text"; i.placeholder = "[Column A] - [Column B]";
  i.value = initial == null ? "" : String(initial);
  i.style.minWidth = "250px"; i.style.fontFamily = "ui-monospace, Menlo, monospace";
  const b = document.createElement("button"); b.textContent = "Apply";
  const go = () => { fn(i.value); closeMenu(); };
  b.onclick = go;
  i.onkeydown = (e) => { if (e.key === "Enter") go(); };
  d.appendChild(i); d.appendChild(b); m.appendChild(d);
  setTimeout(() => { i.focus(); i.select(); }, 30);
}
function mNewComputed(m, fn) {
  const d = document.createElement("div"); d.className = "num";
  const n = document.createElement("input");
  n.type = "text"; n.placeholder = "Name"; n.style.maxWidth = "104px";
  const i = document.createElement("input");
  i.type = "text"; i.placeholder = "[Column A] - [Column B]";
  i.style.minWidth = "210px"; i.style.fontFamily = "ui-monospace, Menlo, monospace";
  const b = document.createElement("button"); b.textContent = "Add";
  const go = () => { fn(n.value, i.value); closeMenu(); };
  b.onclick = go;
  [n, i].forEach((el) => {
    el.onkeydown = (e) => { if (e.key === "Enter") go(); };
  });
  d.appendChild(n); d.appendChild(i); d.appendChild(b); m.appendChild(d);
  setTimeout(() => n.focus(), 30);
}

// ===========================================================================
// GESTURES
// ===========================================================================
function paintSelection() {
  document.querySelectorAll("#ptTable td.sel").forEach((td) => td.classList.remove("sel"));
  selection.forEach(([r, c]) => {
    const td = document.querySelector('#ptTable td[data-r="' + r + '"][data-c="' + c + '"]');
    if (td) td.classList.add("sel");
  });
}

function beginEdit(el, commit) {
  el.contentEditable = "true";
  el.classList.add("editing");
  el.focus();
  const range = document.createRange(); range.selectNodeContents(el);
  const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
  const done = (save) => {
    el.contentEditable = "false"; el.classList.remove("editing");
    el.onblur = null; el.onkeydown = null;
    if (save) commit(el.textContent);
    else redraw();
  };
  el.onblur = () => done(true);
  el.onkeydown = (e) => {
    if (e.key === "Enter") { e.preventDefault(); done(true); }
    if (e.key === "Escape") { e.preventDefault(); done(false); }
  };
}

// Typing in a cell changes the value. Whatever else is selected in the same
// column changes with it, which is how you blank a range or set a floor.
function editCellValue(r, c) {
  const td = document.querySelector('#ptTable td[data-r="' + r + '"][data-c="' + c + '"]');
  const ln = td && td.querySelector(".ln");
  if (!ln) return;
  const targets = selection.some(([a, b]) => a === r && b === c)
    ? selection.slice() : [[r, c]];
  beginEdit(ln, (txt) => {
    if (setCellValues(targets, txt)) {
      redraw(targets.length > 1
        ? "Set " + targets.length + " cells" : "Set " + D.columns[c].name);
    } else redraw();
  });
}

function wireGestures(tbl, frame) {
  // ---- cells ----
  tbl.querySelectorAll("tbody td[data-c]").forEach((td) => {
    const r = +td.dataset.r, c = +td.dataset.c;

    td.oncontextmenu = (e) => {
      e.preventDefault(); e.stopPropagation();
      if (!selection.some(([a, b]) => a === r && b === c)) selection = [[r, c]];
      paintSelection();
      cellMenu(e.clientX, e.clientY, r, c);
    };
    td.ondblclick = (e) => {
      e.stopPropagation();
      editCellValue(r, c);
    };
    td.onmousedown = (e) => {
      if (e.button !== 0) return;
      let dragged = false;
      const over = (ev) => {
        const el = document.elementFromPoint(ev.clientX, ev.clientY);
        const cell = el && el.closest ? el.closest("td[data-c]") : null;
        if (!cell || !tbl.contains(cell) || !cell.dataset.r) return;
        dragged = true;
        const r1 = +cell.dataset.r, c1 = +cell.dataset.c;
        selection = [];
        for (let rr = Math.min(r, r1); rr <= Math.max(r, r1); rr++)
          for (let cc = Math.min(c, c1); cc <= Math.max(c, c1); cc++)
            selection.push([rr, cc]);
        paintSelection();
      };
      const up = () => {
        document.removeEventListener("mousemove", over);
        document.removeEventListener("mouseup", up);
        if (!dragged) { selection = [[r, c]]; paintSelection(); }
        else toast(selection.length + " cells selected \u2014 right-click to format");
      };
      document.addEventListener("mousemove", over);
      document.addEventListener("mouseup", up);
    };
  });

  // ---- column headers ----
  tbl.querySelectorAll("thead th[data-c]").forEach((th) => {
    const ci = +th.dataset.c;
    th.oncontextmenu = (e) => {
      e.preventDefault(); e.stopPropagation();
      headerMenu(e.clientX, e.clientY, ci, e.shiftKey);
    };
    th.onclick = (e) => {
      if (!e.shiftKey) { if (colSelection.length) { colSelection = []; renderTable(); } return; }
      e.preventDefault();
      const i = colSelection.indexOf(ci);
      if (i >= 0) colSelection.splice(i, 1); else colSelection.push(ci);
      renderTable();
      toast(colSelection.length + " columns selected \u2014 right-click one for heatmap grouping");
    };
    th.ondblclick = (e) => {
      e.stopPropagation();
      const ln = th.querySelector(".ln"); if (!ln) return;
      beginEdit(ln, (txt) => {
        const old = M.columns[ci].name;
        if (!txt || txt === old) { redraw(); return; }
        pushUndo("rename column");
        renameColumn(old, txt);
        redraw("Renamed " + JSON.stringify(old) + " to " + JSON.stringify(txt));
      });
    };
  });

  // ---- merged super-headers ----
  tbl.querySelectorAll("thead th.super").forEach((th) => {
    th.ondblclick = (e) => {
      e.stopPropagation();
      const ln = th.querySelector(".ln"); if (!ln) return;
      const li = +th.dataset.superLevel, si = +th.dataset.superIdx;
      beginEdit(ln, (txt) => {
        pushUndo("header group label");
        K.header_levels = clone(K.header_levels || M.header_levels);
        K.header_levels[li][si][0] = txt;
        redraw("header_levels[" + li + "][" + si + "]");
      });
    };
  });

  // ---- column resize grips ----
  tbl.querySelectorAll("thead th .grip").forEach((grip) => {
    grip.onmousedown = (e) => {
      e.preventDefault(); e.stopPropagation();
      const ci = +grip.dataset.c, name = M.columns[ci].name;
      const x0 = e.clientX, w0 = M.geom.col_widths[ci];
      pushUndo("column width");
      // Hold the fit still for the gesture. Re-fitting on every frame would
      // pin the table to the panel's width and the column would look like it
      // was refusing to move; frozen, the edge tracks the pointer and the
      // release settles the new width back into the panel.
      _tfFrozen = _tfScale;
      const mv = (ev) => {
        K.column_widths = K.column_widths || {};
        K.column_widths[name] =
          Math.max(48, Math.round(w0 + (ev.clientX - x0) / tfDragScale()));
        rebuild(); renderTable(); updateSizeSummary();
      };
      const up = () => {
        document.removeEventListener("mousemove", mv);
        document.removeEventListener("mouseup", up);
        _tfFrozen = null;
        redraw(name + " -> " + K.column_widths[name] + "px");
      };
      document.addEventListener("mousemove", mv);
      document.addEventListener("mouseup", up);
    };
  });

  // ---- title / subtitle / caption ----
  frame.querySelectorAll("[data-role]").forEach((el) => {
    const role = el.dataset.role;
    el.ondblclick = (e) => {
      e.stopPropagation();
      beginEdit(el, (txt) => {
        pushUndo(role);
        if (role === "caption") { K.caption = txt; K.source = null; }
        else K[role] = txt;
        redraw(role + " updated");
      });
    };
    el.oncontextmenu = (e) => {
      e.preventDefault(); e.stopPropagation();
      textMenu(e.clientX, e.clientY, role, el);
    };
  });

  // ---- the frame itself: the "whole table" target ----
  frame.oncontextmenu = (e) => {
    if (e.target.closest("td[data-c], th, [data-role]")) return;
    e.preventDefault(); e.stopPropagation();
    canvasMenu(e.clientX, e.clientY);
  };
}

// ===========================================================================
// WHOLE-TABLE RESIZE -- the chart studio's frame grips, mapped onto the two
// kwargs that actually move a table's dimensions:
//
//     east   ->  every column width scaled in proportion   (column_widths)
//     south  ->  row_height_scale
//     corner ->  both
//
// make_table has no width or height argument to write, because a table's
// canvas is derived from its content rather than chosen. So the drag cannot
// be applied directly; it has to be re-expressed as the kwargs the engine
// does take, which is also what makes it round-trip -- the resized table
// regenerates from the Code tab like any other edit.
//
// Both axes have floors the drag cannot talk the engine out of: 48px per
// column, and a row that can never be shorter than the text wrapped inside
// it. Past those the frame stops following the pointer; the size tag reads
// the canvas the model actually produced, not the one the pointer asked for,
// so the floor is visible rather than silent.
// ===========================================================================
const TS_MIN_COL_W = 48;
const TS_MIN_SCALE = 0.7, TS_MAX_SCALE = 2.0;
let _tsResize = null;
let _tsRaf = null;

// Wired once, at boot: the grips belong to #tableScale rather than to the
// table, so unlike everything else in the studio they survive a re-render.
function installFrameGrips() {
  document.querySelectorAll("#tableScale .ts-grip").forEach((g) => {
    g.onmousedown = (e) => beginFrameResize(e, g.dataset.tsGrip);
  });
}

function markLiveGrip(mode) {
  document.querySelectorAll(".ts-grip").forEach((g) => {
    g.classList.toggle("live", g.dataset.tsGrip === mode);
  });
}

function beginFrameResize(e, mode) {
  if (e.button !== 0) return;
  e.preventDefault(); e.stopPropagation();
  closeMenu();
  _tsResize = {
    mode: mode,
    x0: e.clientX, y0: e.clientY, px: e.clientX, py: e.clientY,
    w0: M.geom.col_widths.slice(),
    tableW0: Math.max(1, M.geom.table_w),
    bodyH0: Math.max(1, M.geom.body_h),
    scale0: +(K.row_height_scale || 1.0),
    moved: false,
    // Snapshot once, at pointer-down: the kwargs are rewritten on every
    // frame, so by release there is no pre-drag state left to capture.
    undoEntry: pushUndo("table size"),
  };
  // Frozen for the same reason as a column drag: a re-fit per frame would pin
  // the edge to the panel and the table would appear not to respond at all.
  _tfFrozen = _tfScale;
  document.body.classList.add("ts-resizing");
  markLiveGrip(mode);
  document.getElementById("tsSizeTag").classList.add("on");
  document.addEventListener("mousemove", onFrameResizeMove);
  document.addEventListener("mouseup", endFrameResize, { once: true });
}

// Widths are cut off a running total rather than rounded column by column:
// rounding each one independently loses up to half a pixel per column, and
// on a twelve-column table the right edge visibly lags the pointer.
function applyWidthDrag(r, dx) {
  const target = Math.max(r.w0.length * TS_MIN_COL_W, r.tableW0 + dx);
  const f = target / r.tableW0;
  const out = Object.assign({}, K.column_widths || {});
  let acc = 0, cut = 0;
  r.w0.forEach((w, ci) => {
    acc += w * f;
    const edge = Math.round(acc);
    out[M.columns[ci].name] = Math.max(TS_MIN_COL_W, edge - cut);
    cut = edge;
  });
  K.column_widths = out;
}

function applyHeightDrag(r, dy) {
  const target = Math.max(1, r.bodyH0 + dy);
  const s = r.scale0 * target / r.bodyH0;
  K.row_height_scale =
    Math.round(Math.min(TS_MAX_SCALE, Math.max(TS_MIN_SCALE, s)) * 100) / 100;
}

function onFrameResizeMove(e) {
  const r = _tsResize;
  if (!r) return;
  r.px = e.clientX; r.py = e.clientY;
  if (e.clientX !== r.x0 || e.clientY !== r.y0) r.moved = true;
  const s = tfDragScale();
  if (r.mode !== "s") applyWidthDrag(r, (e.clientX - r.x0) / s);
  if (r.mode !== "e") applyHeightDrag(r, (e.clientY - r.y0) / s);
  // Coalesce rather than queue: a re-wrap of every cell is more work than a
  // pointer event, and a backlog of stale sizes to grind through on release
  // is the one thing that makes a drag feel broken.
  if (_tsRaf) return;
  _tsRaf = requestAnimationFrame(() => {
    _tsRaf = null;
    if (!_tsResize) return;
    rebuild(); renderTable();
    updateSizeSummary();
    updateSizeTag(_tsResize);
  });
}

function updateSizeTag(r) {
  const t = document.getElementById("tsSizeTag");
  t.style.left = (r.px + 16) + "px";
  t.style.top  = (r.py + 16) + "px";
  t.textContent = M.canvas.w + " x " + M.canvas.h + " px"
    + (r.mode === "e" ? "" : "   rows x" + (+(K.row_height_scale || 1)).toFixed(2));
}

function endFrameResize() {
  document.removeEventListener("mousemove", onFrameResizeMove);
  const r = _tsResize;
  _tsResize = null;
  if (_tsRaf) { cancelAnimationFrame(_tsRaf); _tsRaf = null; }
  // Hand the fit back to the panel before the early returns below, so an
  // aborted gesture does not leave the table pinned at the drag's scale.
  _tfFrozen = null;
  document.body.classList.remove("ts-resizing");
  markLiveGrip(null);
  document.getElementById("tsSizeTag").classList.remove("on");
  if (!r) return;
  rebuild();
  const sameW = r.mode === "s"
    || M.geom.col_widths.every((w, i) => w === r.w0[i]);
  const sameH = r.mode === "e"
    || +(K.row_height_scale || 1) === r.scale0;
  // Dragging out and back is not an edit -- but the kwargs were rewritten on
  // the way, and pinning a width that was previously engine-decided is a
  // state change even when the number matches. So revert to the snapshot
  // rather than leaving the pins behind.
  if (!r.moved || (sameW && sameH)) {
    if (_undo[_undo.length - 1] === r.undoEntry) {
      restoreSnapshot(_undo.pop());
      syncUndoButton();
    }
    rebuild(); renderTable();
    return;
  }
  const parts = [];
  if (r.mode !== "s") parts.push("columns to " + M.geom.table_w + "px");
  if (r.mode !== "e") parts.push("row height x" + (+K.row_height_scale).toFixed(2));
  r.undoEntry.label = "table size";
  syncKnobs();
  redraw("Resized " + parts.join(", "));
}

// ===========================================================================
// STRUCTURAL EDITS
//
// Adding, deleting or moving a row or a column moves every row and column
// after it, and K addresses D by position in nine places. Miss one and the
// styling silently lands on the wrong row -- a defect with no error, no
// warning, and nothing on screen to say which row was meant.
//
// So the nine are declared ONCE, here, and an op supplies only an index
// map: old position -> new position, or null for "this one is gone". An op
// never names a kwarg, which is what stops the tenth op from forgetting the
// ninth structure. Adding a positional kwarg means adding a row to this
// table; the structural probe fails on any key in K it cannot classify.
//
//   form         shape in K                      remapped by
//   ----------   ----------------------------    -------------------------
//   indexList    [3, 7]                          mapping each, dropping
//                                                the deleted
//   indexMap     {"3": "#EEE"}                   rekeying
//   denseArray   [0, 1, 1, 0]  (one per row)     scatter into a fresh
//                                                array of the new length
//   spans        [["EM", 3], ["DM", 4]]          expand to one label per
//                                                row, remap, re-collapse
//   cellMap      {"3,2": "#EEE"}                 both halves independently
//   spanLevels   [[["H1", 2], ["H2", 3]], ...]   spans, per header level
// ===========================================================================
const POSITIONAL = [
  { key: "total_rows",       axis: "row",  form: "indexList" },
  { key: "subtotal_rows",    axis: "row",  form: "indexList" },
  { key: "row_colors",       axis: "row",  form: "indexMap" },
  { key: "row_indent",       axis: "row",  form: "denseArray", fill: 0 },
  { key: "row_groups",       axis: "row",  form: "spans" },
  { key: "cell_colors",      axis: "cell", form: "cellMap" },
  { key: "cell_text_colors", axis: "cell", form: "cellMap" },
  { key: "value_overrides",  axis: "cell", form: "cellMap" },
  { key: "header_levels",    axis: "col",  form: "spanLevels" },
];

// Keyed by column NAME, so they survive a reorder untouched but have to
// follow a rename and be dropped on a delete. minibar_columns is the one
// that carries a column name in its VALUE as well as its key -- renaming a
// minibar's source column and not following it here leaves the bar pointing
// at a column that no longer exists.
const NAME_KEYED = [
  { key: "column_formats",     form: "nameMap" },
  { key: "column_aligns",      form: "nameMap" },
  { key: "column_color_modes", form: "nameMap" },
  { key: "rag_thresholds",     form: "nameMap" },
  { key: "column_widths",      form: "nameMap" },
  { key: "minibar_columns",    form: "nameMapAndValue" },
  { key: "highlight_columns",  form: "nameList" },
  { key: "signed_columns",     form: "nameList" },
  { key: "heatmap_groups",     form: "groupCols" },
];

// Everything else in K. Listed so the probe can prove the three lists
// together account for every key the engine emits, rather than trusting
// that a new kwarg would have been noticed.
const INDEX_FREE = [
  "title", "subtitle", "caption", "source", "skin", "_theme_overrides",
  "row_bands", "row_height_scale", "show_index", "target_html_width",
  "save_as", "has_sparklines", "column_renames",
];

function spansToLabels(spans, n) {
  const out = new Array(n).fill(null);
  let cursor = 0;
  (spans || []).forEach((pair) => {
    const label = pair[0], count = pair[1];
    for (let i = 0; i < count && cursor < n; i++, cursor++) out[cursor] = label;
  });
  return out;
}

function labelsToSpans(labels) {
  const out = [];
  labels.forEach((l) => {
    const last = out[out.length - 1];
    if (last && last[0] === l) last[1] += 1; else out.push([l, 1]);
  });
  return out;
}

// A row inserted inside a band belongs to that band, so a hole left by the
// remap inherits from the row above it. A hole before the first band has
// nothing to inherit and becomes "", which is the studio's existing
// spelling for "covered by row_groups but showing no band".
function fillSpanHoles(labels) {
  let carry = "";
  return labels.map((l) => {
    if (l == null) return carry;
    carry = l; return l;
  });
}

function remapSpans(spans, map, nOld, nNew) {
  const old = spansToLabels(spans, nOld);
  const next = new Array(nNew).fill(null);
  old.forEach((label, i) => {
    const j = map(i);
    if (j != null && j >= 0 && j < nNew) next[j] = label;
  });
  return labelsToSpans(fillSpanHoles(next));
}

/**
 * Re-address every positional kwarg after a structural edit.
 *
 * rowMap / colMap are old-index -> new-index, or null for deleted. Either
 * may be omitted when that axis did not move. nRows / nCols are the counts
 * AFTER the edit, and default to D's, so the normal call site is
 * applyStructural({rowMap}) with D already mutated.
 */
function applyStructural(opts) {
  const rowMap = opts.rowMap || ((i) => i);
  const colMap = opts.colMap || ((i) => i);
  const nRowsOld = opts.nRowsOld == null ? D.rows.length : opts.nRowsOld;
  const nColsOld = opts.nColsOld == null ? D.columns.length : opts.nColsOld;
  const nRows = opts.nRows == null ? D.rows.length : opts.nRows;
  const nCols = opts.nCols == null ? D.columns.length : opts.nCols;

  POSITIONAL.forEach((spec) => {
    const cur = K[spec.key];
    if (cur == null) return;               // absent stays absent
    const map = spec.axis === "col" ? colMap : rowMap;
    const nOld = spec.axis === "col" ? nColsOld : nRowsOld;
    const nNew = spec.axis === "col" ? nCols : nRows;

    if (spec.form === "indexList") {
      const seen = new Set();
      K[spec.key] = cur
        .map((i) => map(+i))
        .filter((i) => {
          if (i == null || i < 0 || i >= nNew || seen.has(i)) return false;
          seen.add(i); return true;
        })
        .sort((a, b) => a - b);

    } else if (spec.form === "indexMap") {
      const out = {};
      Object.keys(cur).forEach((k) => {
        const i = map(+k);
        if (i != null && i >= 0 && i < nNew) out[i] = cur[k];
      });
      K[spec.key] = out;

    } else if (spec.form === "denseArray") {
      const out = new Array(nNew).fill(spec.fill);
      cur.forEach((v, i) => {
        const j = map(i);
        if (j != null && j >= 0 && j < nNew) out[j] = v;
      });
      K[spec.key] = out;

    } else if (spec.form === "spans") {
      K[spec.key] = remapSpans(cur, map, nOld, nNew);

    } else if (spec.form === "spanLevels") {
      K[spec.key] = cur.map((level) => remapSpans(level, map, nOld, nNew));

    } else if (spec.form === "cellMap") {
      const out = {};
      Object.keys(cur).forEach((k) => {
        const parts = k.split(",");
        const r = rowMap(+parts[0]), c = colMap(+parts[1]);
        if (r == null || c == null) return;
        if (r < 0 || r >= nRows || c < 0 || c >= nCols) return;
        out[r + "," + c] = cur[k];
      });
      K[spec.key] = out;
    }
  });
}

/**
 * Follow a column rename, or drop a deleted column's styling.
 *
 * renames is {oldName: newName}; drops is a Set of names going away. Both
 * are name-space edits, which is why they are separate from the positional
 * remap -- moving a column needs applyStructural, renaming one needs this,
 * and deleting one needs both.
 */
function applyNameChange(renames, drops) {
  renames = renames || {};
  drops = drops || new Set();
  const to = (n) => (Object.prototype.hasOwnProperty.call(renames, n) ? renames[n] : n);
  const gone = (n) => drops.has(n);

  NAME_KEYED.forEach((spec) => {
    const cur = K[spec.key];
    if (cur == null) return;

    if (spec.form === "nameMap" || spec.form === "nameMapAndValue") {
      const out = {};
      Object.keys(cur).forEach((n) => {
        if (gone(n)) return;
        let v = cur[n];
        if (spec.form === "nameMapAndValue" && typeof v === "string") {
          if (gone(v)) return;             // source column deleted: drop the bar
          v = to(v);
        }
        out[to(n)] = v;
      });
      K[spec.key] = out;

    } else if (spec.form === "nameList") {
      K[spec.key] = cur.filter((n) => !gone(n)).map(to);

    } else if (spec.form === "groupCols") {
      K[spec.key] = cur
        .map((g) => Object.assign({}, g, {
          columns: (g.columns || []).filter((n) => !gone(n)).map(to),
        }))
        .filter((g) => g.columns.length);   // an empty group colours nothing
    }
  });

  // A formula names its source columns too, so it follows a rename. A
  // deleted source cannot be followed: the column keeps the numbers it last
  // computed and loses the rule, rather than silently pointing at nothing.
  const stranded = [];
  D.columns.forEach((dc, ci) => {
    if (!dc.formula) return;
    if (dc.formula.deps.some(gone)) {
      delete dc.formula;
      inferColumn(ci);
      stranded.push(dc.name);
      return;
    }
    if (!dc.formula.deps.some((n) => to(n) !== n)) return;
    dc.formula.src = dc.formula.src.replace(
      /\[([^\]]*)\]/g, (whole, n) => "[" + to(n.trim()) + "]");
    dc.formula = compileFormula(dc.formula.src, dc.name);
  });
  if (stranded.length) {
    toast(stranded.join(", ") + ": kept the values, dropped the formula");
    // Those numbers were worked out here and are in no upstream frame.
    pushOp(null, "a formula was cut loose from a deleted source");
  }
}

function renameColumn(oldName, newName) {
  const ci = colByName(oldName);
  const wasComputed = ci >= 0 && !!D.columns[ci].formula;
  // A header is one of the things the engine sizes a column from, so a
  // longer or shorter one moves the width over there while the studio goes
  // on showing the old number. Only a rename that changes which of header
  // and content is the wider needs the studio's own measurement pinned.
  if (ci >= 0 && D.columns[ci].kind !== "spark") {
    const texts = M.rows.map((row) => {
      const t = row.cells[ci] ? row.cells[ci].text : null;
      return t == null ? "" : t;
    });
    let body = 0;
    texts.forEach((t) => {
      body = Math.max(body, measure(t, M.theme.body_font_size, false));
    });
    const before = Math.max(body, measure(oldName, M.theme.header_font_size, true));
    const after = Math.max(body, measure(newName, M.theme.header_font_size, true));
    if (Math.abs(after - before) > 0.5) {
      const w = measuredColumnWidth(newName, texts);
      D.columns[ci].w0 = w;
      pinColumnWidth(newName, w);
    }
  }
  if (ci >= 0) D.columns[ci].name = newName;
  applyNameChange({ [oldName]: newName }, null);
  K.column_renames = K.column_renames || {};
  K.column_renames[oldName] = newName;
  // A computed column is named by the df.insert that creates it, so there
  // is nothing in the frame to rename.
  if (!wasComputed) {
    pushOp(DF_NAME + " = " + DF_NAME + ".rename(columns="
           + pyLit({ [oldName]: newName }) + ")");
  }
}

// ---------------------------------------------------------------------------
// Duplicating an index copies whatever styling was attached to it. Like
// applyStructural this walks the registry rather than naming kwargs, so a
// duplicate cannot pick up eight of the nine.
// ---------------------------------------------------------------------------
function copyStyling(axis, from, to) {
  POSITIONAL.forEach((spec) => {
    const cur = K[spec.key];
    if (cur == null) return;
    if (spec.form === "spans" || spec.form === "spanLevels") return;  // adjacent: the span already covers it
    if (spec.form === "cellMap") {
      Object.keys(cur).slice().forEach((k) => {
        const p = k.split(",");
        const at = axis === "row" ? +p[0] : +p[1];
        if (at !== from) return;
        cur[axis === "row" ? to + "," + p[1] : p[0] + "," + to] = cur[k];
      });
      return;
    }
    if (spec.axis !== axis) return;
    if (spec.form === "indexList") {
      if (cur.includes(from) && !cur.includes(to)) {
        cur.push(to); cur.sort((a, b) => a - b);
      }
    } else if (spec.form === "indexMap") {
      if (cur[from] !== undefined) cur[to] = cur[from];
    } else if (spec.form === "denseArray") {
      cur[to] = cur[from];
    }
  });
}

function copyColumnStyling(fromName, toName) {
  NAME_KEYED.forEach((spec) => {
    const cur = K[spec.key];
    if (cur == null) return;
    if (spec.form === "nameMap" || spec.form === "nameMapAndValue") {
      if (cur[fromName] !== undefined) cur[toName] = cur[fromName];
    } else if (spec.form === "nameList") {
      if (cur.includes(fromName) && !cur.includes(toName)) cur.push(toName);
    } else if (spec.form === "groupCols") {
      cur.forEach((g) => {
        if ((g.columns || []).includes(fromName) && !g.columns.includes(toName))
          g.columns.push(toName);
      });
    }
  });
}

// old index -> new index for a single element moving from one slot to another.
function moveIndex(i, from, to) {
  if (i === from) return to;
  if (from < to) return (i > from && i <= to) ? i - 1 : i;
  return (i >= to && i < from) ? i + 1 : i;
}

// ---------------------------------------------------------------------------
// DATA EDITS
//
// A cell's value is data, not styling: changing it has to move the number
// the heatmap reads, the sort orders by, the minibar draws and the
// regenerated DataFrame carries. value_overrides remains for the other
// intent -- printing something a value is not -- and is reached from the
// menu rather than from a double-click.
// ---------------------------------------------------------------------------
const _NUM_RE = /^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$/;

function parseCellInput(txt, kind) {
  const s = String(txt == null ? "" : txt).trim();
  if (!s || s === "\u2014") return null;
  if (kind === "date" && /^\d{4}-\d{2}-\d{2}/.test(s)) return { __date__: s };
  // A numeric cell is read back through its own formatting, so whatever the
  // format added is taken off again before parsing. Without this, retyping
  // the "3.4%" or "$1.23B" already on screen would store a string and
  // collapse the whole column to text.
  if (kind === "num") {
    let bare = s.replace(/[,\s]/g, "").replace(/^\+/, "")
                .replace(/[%$\u00A3\u20AC]/g, "")
                .replace(/bp$/i, "").replace(/x$/i, "");
    let mult = 1;
    const mag = bare.match(/([kmb])$/i);
    if (mag) {
      const u = mag[1].toLowerCase();
      mult = u === "k" ? 1e3 : u === "m" ? 1e6 : 1e9;
      bare = bare.slice(0, -1);
    }
    if (_NUM_RE.test(bare)) return Number(bare) * mult;
  }
  const plain = s.replace(/,/g, "");
  if (_NUM_RE.test(plain)) return Number(plain);
  return s;
}

// Predict what pandas will infer from the regenerated literal. The studio
// and the engine have to agree about a column's type or the round-trip
// changes the formatting -- and note that ANY null makes an integer column
// float64 over there, so it has to here too.
function inferColumn(ci) {
  const dc = D.columns[ci];
  if (!dc || dc.kind === "spark" || dc.kind === "minibar") return;
  if (dc.formula) return;    // materialiseDerived owns a computed column's type
  const vals = D.rows.map((row) => (row.cells[ci] ? row.cells[ci].raw : null));
  const present = vals.filter((v) => v != null);
  let kind = "text";
  if (present.length
      && present.every((v) => typeof v === "object" && v.__date__)) kind = "date";
  else if (present.length
      && present.every((v) => typeof v === "number" && isFinite(v))) kind = "num";
  const wasNum = dc.kind === "num";
  dc.kind = kind;
  dc.int_dtype = kind === "num" && present.length === vals.length
                 && present.every((v) => Number.isInteger(v));
  dc.align0 = kind === "num" ? "right" : "left";
  if (kind !== "text") dc.wrap = false;

  // A number format, a heatmap or a minibar on a column that no longer
  // holds numbers is not a preference the engine can honour -- it would
  // fail on the regenerated call rather than render something.
  if (wasNum && kind !== "num") {
    dc.fmt0 = null;
    ["column_formats", "column_color_modes", "rag_thresholds",
     "minibar_columns"].forEach((k) => { if (K[k]) delete K[k][dc.name]; });
    if (K.signed_columns)
      K.signed_columns = K.signed_columns.filter((n) => n !== dc.name);
    if (K.heatmap_groups)
      K.heatmap_groups = K.heatmap_groups
        .map((g) => Object.assign({}, g, {
          columns: (g.columns || []).filter((n) => n !== dc.name) }))
        .filter((g) => g.columns.length);
  }
}

function setCellValues(cells, txt) {
  const targets = cells.filter(([r, c]) => {
    const dc = D.columns[c], dr = D.rows[r];
    if (!dc || !dr || dc.kind === "spark" || dc.kind === "minibar") return false;
    // A derived cell would be overwritten on the next rebuild. The label
    // column of a computed row is not derived, so that stays editable.
    if (dc.formula) return false;
    return !(dr.agg && c > 0 && dc.kind === "num");
  });
  if (!targets.length) {
    toast("That cell is computed \u2014 change the formula, or the values it reads");
    return false;
  }
  pushUndo(targets.length > 1 ? "edit " + targets.length + " cells" : "cell value");
  const touched = new Set();
  // The engine sizes a column from its widest content, so changing a value
  // can widen or narrow it over there while the studio goes on showing the
  // old width. Pinning what is on screen is what keeps the preview true.
  new Set(targets.map(([, c]) => c)).forEach((c) => {
    pinColumnWidth(D.columns[c].name, M.geom.col_widths[c]);
  });
  targets.forEach(([r, c]) => {
    const cell = D.rows[r].cells[c];
    cell.raw = parseCellInput(txt, D.columns[c].kind);
    // The engine measured its baseline against the OLD value.
    delete cell.text0;
    delete cell.lines0;
    // An override would mask the edit, so typing a value clears it.
    if (K.value_overrides) delete K.value_overrides[ck(r, c)];
    touched.add(c);
  });
  touched.forEach((c) => inferColumn(c));
  pushOp(null, "a value was typed in");
  return true;
}

// ---------------------------------------------------------------------------
// STRUCTURAL OPERATIONS
//
// Every one is the same shape: mutate D, describe the index shift, hand it
// to applyStructural. None of them names a styling kwarg except to READ it
// -- sort and filter consult total_rows to decide which rows are summaries
// and therefore hold their position, which is a decision about the
// operation rather than a remap.
// ---------------------------------------------------------------------------
// `opPy` is supplied by deleteRowsWhere, which deletes by a RULE and can
// therefore be replayed. A deletion driven by a click is by position and
// cannot be.
function deleteRows(idxs, opPy, why) {
  const drop = new Set(idxs.map(Number));
  if (!drop.size) return false;
  if (drop.size >= D.rows.length) {
    toast("A table needs at least one row");
    return false;
  }
  const nOld = D.rows.length;
  const map = new Map();
  let next = 0;
  for (let i = 0; i < nOld; i++) map.set(i, drop.has(i) ? null : next++);

  pushUndo(drop.size > 1 ? "delete " + drop.size + " rows" : "delete row");
  // Deleting a row can take a column's widest value with it, and the engine
  // sizes a column from its widest content -- so it would lay that column
  // out narrower than the studio is still showing it. Pinning the width it
  // already has is what keeps the preview true; a column whose widest value
  // survives is left for the engine to re-derive as before.
  D.columns.forEach((dc, c) => {
    if (dc.kind === "spark") return;
    let all = 0, left = 0;
    for (let i = 0; i < nOld; i++) {
      const cell = M.rows[i] && M.rows[i].cells[c];
      const w = (cell && cell.text != null)
        ? measure(cell.text, M.theme.body_font_size, false) : 0;
      if (w > all) all = w;
      if (!drop.has(i) && w > left) left = w;
    }
    if (left < all - 0.5) pinColumnWidth(dc.name, M.geom.col_widths[c]);
  });
  D.rows = D.rows.filter((_, i) => !drop.has(i));
  applyStructural({
    rowMap: (i) => (map.has(i) ? map.get(i) : null),
    nRowsOld: nOld,
  });
  pushOp(opPy || null, why || "rows were deleted by position");
  selection = [];
  return true;
}

function insertRow(at) {
  const nOld = D.rows.length;
  at = Math.max(0, Math.min(nOld, at));
  pushUndo("insert row");
  // No text0 / lines0: a new cell has no engine-measured baseline, so
  // rebuild() measures it live, which is exactly what should happen.
  D.rows.splice(at, 0, {
    h0: M.geom.row_default_h,
    cells: D.columns.map((dc) => ({
      raw: null,
      spark: dc.kind === "spark" ? [] : null,
    })),
  });
  applyStructural({
    rowMap: (i) => (i < at ? i : i + 1),
    nRowsOld: nOld,
  });
  pushOp(null, "a blank row was inserted");
  selection = [];
  return true;
}

function duplicateRow(r) {
  const nOld = D.rows.length;
  if (!D.rows[r]) return false;
  pushUndo("duplicate row");
  // The copy keeps text0 / lines0: same values, so the engine's own
  // measurement of them is still the right baseline.
  D.rows.splice(r + 1, 0, JSON.parse(JSON.stringify(D.rows[r])));
  applyStructural({ rowMap: (i) => (i <= r ? i : i + 1), nRowsOld: nOld });
  copyStyling("row", r, r + 1);
  pushOp(null, "a row was duplicated in place");
  selection = [];
  return true;
}

function moveRow(from, to) {
  const nOld = D.rows.length;
  to = Math.max(0, Math.min(nOld - 1, to));
  if (from === to || !D.rows[from]) return false;
  pushUndo("move row");
  D.rows.splice(to, 0, D.rows.splice(from, 1)[0]);
  applyStructural({ rowMap: (i) => moveIndex(i, from, to), nRowsOld: nOld });
  pushOp(null, "a row was moved by hand");
  selection = [];
  return true;
}

// Rows that summarise their neighbours hold their position and separate the
// sort into runs; so does a change of group band. With neither, that is one
// run over the whole table, i.e. an ordinary sort.
function _fixedRows() {
  return new Set([].concat(K.total_rows || [], K.subtotal_rows || []).map(Number));
}

function sortRows(ci, asc) {
  const nOld = D.rows.length;
  const fixed = _fixedRows();
  const bands = spansToLabels(K.row_groups, nOld);
  const key = (i) => {
    const cell = D.rows[i].cells[ci];
    const v = cell ? cell.raw : null;
    if (v == null) return null;
    if (typeof v === "object" && v.__date__) return v.__date__;
    return v;
  };
  const cmp = (a, b) => {
    const x = key(a), y = key(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;              // blanks sink, either direction
    if (y == null) return -1;
    const d = (typeof x === "number" && typeof y === "number")
      ? x - y : String(x).localeCompare(String(y));
    return d * (asc ? 1 : -1);
  };

  const order = D.rows.map((_, i) => i);
  let run = [];
  const flush = () => {
    if (run.length > 1) {
      const sorted = run.slice().sort(cmp);
      run.forEach((slot, k) => { order[slot] = sorted[k]; });
    }
    run = [];
  };
  for (let i = 0; i < nOld; i++) {
    if (fixed.has(i)) { flush(); continue; }
    if (run.length && bands[i] !== bands[run[0]]) flush();
    run.push(i);
  }
  flush();
  if (order.every((v, i) => v === i)) {
    toast("Already sorted by " + D.columns[ci].name);
    return false;
  }

  // A sort is replayable when it was one run over the whole table on a
  // column pandas would order the same way. Sorting inside bands or around
  // summary rows is not something sort_values does, and text ordering is the
  // browser's collation rather than Python's, so both fall back to the
  // edited frame rather than emit a line that would drift.
  const dc = D.columns[ci];
  const plain = !fixed.size && !(K.row_groups || []).length
    && !D.rows.some((r) => r.agg) && !dc.formula
    && (dc.kind === "num" || dc.kind === "date");

  pushUndo("sort by " + D.columns[ci].name);
  const map = new Array(nOld);
  order.forEach((oldI, newI) => { map[oldI] = newI; });
  D.rows = order.map((i) => D.rows[i]);
  applyStructural({ rowMap: (i) => map[i], nRowsOld: nOld });
  pushOp(
    plain
      ? DF_NAME + " = " + DF_NAME + ".sort_values(" + pyLit(dc.name)
        + ", ascending=" + pyBool(asc) + ", kind=\"stable\")"
        + ".reset_index(drop=True)"
      : null,
    "the sort ran within bands or around summary rows");
  selection = [];
  return true;
}

// make_table has no filter kwarg, so a filter is a deletion: the rows go,
// and the smaller frame is what the regenerated call carries. `keep` is the
// same predicate written as a pandas mask, so the filter can be replayed
// over a later pull -- unless summary rows were exempted from it, which is
// a carve-out no mask expresses.
function deleteRowsWhere(ci, test, label, keep) {
  const fixed = _fixedRows();
  const hit = [];
  D.rows.forEach((row, i) => {
    if (fixed.has(i)) return;
    const cell = row.cells[ci];
    if (test(cell ? cell.raw : null)) hit.push(i);
  });
  if (!hit.length) { toast("No rows are " + label); return false; }
  if (hit.length >= D.rows.length) {
    toast("That would delete every row");
    return false;
  }
  const replayable = keep && !fixed.size && !D.rows.some((r) => r.agg)
    && !D.columns[ci].formula;
  const ok = deleteRows(
    hit,
    replayable
      ? DF_NAME + " = " + DF_NAME + "[" + keep + "].reset_index(drop=True)"
      : null,
    "the filter stepped around summary rows");
  if (ok) toast("Deleted " + hit.length + " row" + (hit.length > 1 ? "s" : "")
                + " " + label);
  return ok;
}

// --- columns ---------------------------------------------------------------

function uniqueColumnName(base) {
  const taken = new Set(D.columns.map((c) => c.name));
  if (!taken.has(base)) return base;
  for (let i = 2; ; i++) if (!taken.has(base + " " + i)) return base + " " + i;
}

function measuredColumnWidth(name, texts) {
  let w = measure(name, M.theme.header_font_size, true);
  texts.forEach((t) => { w = Math.max(w, measure(t, M.theme.body_font_size, false)); });
  return Math.max(72, Math.min(280, Math.round(w) + 24));
}

// A column the engine never laid out has no engine-chosen width, and the
// browser's text metrics are not PIL's, so the studio cannot guess one that
// the engine would agree with. Its own guess is pinned instead, which the
// engine does honour. Only the new column needs this -- the engine
// re-derives every pre-existing width unchanged.
function pinColumnWidth(name, px) {
  K.column_widths = K.column_widths || {};
  K.column_widths[name] = Math.round(px);
}

function insertColumn(at, name) {
  const nOld = D.columns.length;
  at = Math.max(0, Math.min(nOld, at));
  const nm = uniqueColumnName(String(name || "").trim() || "New column");
  const w = measuredColumnWidth(nm, []);
  pushUndo("insert column");
  D.columns.splice(at, 0, {
    name: nm, kind: "text", int_dtype: false, wrap: false, minibar_src: null,
    w0: w, fmt0: null, align0: "left",
  });
  D.rows.forEach((row) => { row.cells.splice(at, 0, { raw: null }); });
  applyStructural({ colMap: (i) => (i < at ? i : i + 1), nColsOld: nOld });
  pinColumnWidth(nm, w);
  pushOp(null, "a blank column was added for values typed by hand");
  selection = [];
  return true;
}

function deleteColumns(idxs) {
  const drop = new Set(idxs.map(Number));
  if (!drop.size) return false;
  if (drop.size >= D.columns.length) {
    toast("A table needs at least one column");
    return false;
  }
  const nOld = D.columns.length;
  const gone = [...drop].map((i) => D.columns[i].name);
  // A computed column is never in the frame the call starts from -- it is
  // added by a df.insert further down -- so dropping one is expressed by
  // that insert simply no longer being emitted.
  const fromFrame = [...drop].filter((i) => !D.columns[i].formula)
                             .map((i) => D.columns[i].name);
  const map = new Map();
  let next = 0;
  for (let i = 0; i < nOld; i++) map.set(i, drop.has(i) ? null : next++);

  pushUndo(drop.size > 1 ? "delete " + drop.size + " columns" : "delete column");
  D.columns = D.columns.filter((_, i) => !drop.has(i));
  D.rows.forEach((row) => { row.cells = row.cells.filter((_, i) => !drop.has(i)); });
  applyStructural({ colMap: (i) => map.get(i), nColsOld: nOld });
  applyNameChange({}, new Set(gone));
  // A minibar reads from a source column; if that source has gone, the
  // column it fed is ordinary data again.
  D.columns.forEach((dc, ci) => {
    if (dc.minibar_src && gone.includes(dc.minibar_src)) {
      dc.minibar_src = null;
      dc.kind = "text";
      inferColumn(ci);
    }
  });
  pushOp(fromFrame.length
    ? DF_NAME + " = " + DF_NAME + ".drop(columns=" + pyNames(fromFrame) + ")"
    : "");
  selection = [];
  return true;
}

function duplicateColumn(ci) {
  const nOld = D.columns.length;
  const src = D.columns[ci];
  if (!src) return false;
  if (src.kind === "spark") {
    toast("Sparkline columns cannot be duplicated");
    return false;
  }
  const nm = uniqueColumnName(src.name + " copy");
  // "... copy" is a longer header than the original, so the engine would
  // lay the copy out wider. It is a column the engine has never seen, so
  // the studio's own width is pinned rather than guessed at.
  const w = measuredColumnWidth(nm, M.rows.map((row) => {
    const t = row.cells[ci] ? row.cells[ci].text : null;
    return t == null ? "" : t;
  }));
  pushUndo("duplicate column");
  const copy = Object.assign({}, src, { name: nm, w0: w });
  if (src.formula) copy.formula = clone(src.formula);   // not a shared object
  D.columns.splice(ci + 1, 0, copy);
  D.rows.forEach((row) => {
    row.cells.splice(ci + 1, 0, JSON.parse(JSON.stringify(row.cells[ci])));
  });
  applyStructural({ colMap: (i) => (i <= ci ? i : i + 1), nColsOld: nOld });
  copyStyling("col", ci, ci + 1);
  copyColumnStyling(src.name, nm);
  pinColumnWidth(nm, w);
  // Copying a computed column would have to land after the insert that
  // creates its source, which is emitted last; the copy of an ordinary one
  // is just another column of the frame.
  pushOp(src.formula
    ? null
    : DF_NAME + ".insert(" + (ci + 1) + ", " + pyLit(nm) + ", "
      + DF_NAME + "[" + pyLit(src.name) + "])",
    "a computed column was duplicated");
  selection = [];
  return true;
}

function moveColumn(from, to) {
  const nOld = D.columns.length;
  to = Math.max(0, Math.min(nOld - 1, to));
  if (from === to || !D.columns[from]) return false;
  pushUndo("move column");
  D.columns.splice(to, 0, D.columns.splice(from, 1)[0]);
  D.rows.forEach((row) => { row.cells.splice(to, 0, row.cells.splice(from, 1)[0]); });
  applyStructural({ colMap: (i) => moveIndex(i, from, to), nColsOld: nOld });
  // Reordering names a full column order, and a computed column is not in
  // the frame yet at that point in the script.
  pushOp(D.columns.some((c) => c.formula)
    ? null
    : DF_NAME + " = " + DF_NAME + "[" + pyNames(D.columns.map((c) => c.name)) + "]",
    "a column moved past a computed one");
  selection = [];
  return true;
}

// ---------------------------------------------------------------------------
// TRANSPOSE
//
// The three cell-addressed maps rotate straight through, and row_groups /
// header_levels are the same span structure on opposite axes so they swap.
// Everything else positional is row-only and has no column counterpart in
// make_table, and every name-keyed kwarg is addressed to columns that are
// now rows. Those are dropped, and the toast says which.
// ---------------------------------------------------------------------------
function transposeTable() {
  if (D.columns.some((c) => c.kind === "spark" || c.kind === "minibar")) {
    toast("Sparkline and minibar columns have no transposed form");
    return false;
  }
  const nOldR = D.rows.length, nOldC = D.columns.length;
  if (nOldC < 2 || !nOldR) { toast("Nothing to transpose"); return false; }

  const dropped = POSITIONAL.concat(NAME_KEYED).map((s) => s.key)
    .filter((k) => !["cell_colors", "cell_text_colors", "value_overrides",
                     "row_groups", "header_levels", "column_widths"].includes(k))
    .filter((k) => {
      const v = K[k];
      return v != null && (Array.isArray(v) ? v.length : Object.keys(v).length);
    });
  // A formula reads columns and a summary row reads rows; after a transpose
  // neither is addressing anything that still exists. The numbers they had
  // worked out survive as ordinary data.
  if (D.columns.some((c) => c.formula)) dropped.push("column formulas");
  if (D.rows.some((r) => r.agg)) dropped.push("summary rows keep their numbers");

  pushUndo("transpose");

  const oldCols = D.columns, oldRows = D.rows;
  const oldBands = K.row_groups ? spansToLabels(K.row_groups, nOldR) : null;
  const oldHeader = (K.header_levels || [])[0]
    ? spansToLabels(K.header_levels[0], nOldC) : null;

  const rot = (obj) => {
    if (obj == null) return null;
    const out = {};
    Object.keys(obj).forEach((k) => {
      const p = k.split(","), r = +p[0], c = +p[1];
      if (c < 1 || c >= nOldC || r < 0 || r >= nOldR) return;  // old col 0 is a header now
      out[(c - 1) + "," + (r + 1)] = obj[k];
    });
    return Object.keys(out).length ? out : null;
  };
  const kept = {
    cell_colors: rot(K.cell_colors),
    cell_text_colors: rot(K.cell_text_colors),
    value_overrides: rot(K.value_overrides),
  };

  const label = (v, i) => {
    if (v == null) return "col_" + (i + 1);
    if (typeof v === "object" && v.__date__) return String(v.__date__).slice(0, 10);
    return String(v);
  };
  const newNames = oldRows.map((row, i) => label(row.cells[0]
    ? row.cells[0].raw : null, i));

  const blank = (nm) => ({
    name: nm, kind: "text", int_dtype: false, wrap: false, minibar_src: null,
    w0: 0, fmt0: null, align0: "left",
  });
  const seen = new Set();
  D.columns = [blank("Field")].concat(newNames.map((nm) => {
    let out = nm;
    for (let i = 2; seen.has(out); i++) out = nm + " " + i;
    seen.add(out);
    return blank(out);
  }));
  D.rows = [];
  for (let c = 1; c < nOldC; c++) {
    const cells = [{ raw: oldCols[c].name }];
    for (let r = 0; r < nOldR; r++) {
      cells.push({ raw: oldRows[r].cells[c] ? oldRows[r].cells[c].raw : null });
    }
    D.rows.push({ h0: M.geom.row_default_h, cells: cells });
  }

  POSITIONAL.concat(NAME_KEYED).forEach((s) => { delete K[s.key]; });
  Object.keys(kept).forEach((k) => { if (kept[k]) K[k] = kept[k]; });
  if (oldBands) K.header_levels = [labelsToSpans([""].concat(oldBands))];
  if (oldHeader) {
    const spans = labelsToSpans(fillSpanHoles(oldHeader.slice(1)));
    if (spans.length) K.row_groups = spans;
  }

  // Every column here is new, so every width is a studio guess and every
  // one of them has to be pinned for the engine to agree.
  D.columns.forEach((dc, ci) => {
    inferColumn(ci);
    dc.w0 = measuredColumnWidth(dc.name,
      D.rows.map((row) => (row.cells[ci].raw == null ? "" : String(row.cells[ci].raw))));
    pinColumnWidth(dc.name, dc.w0);
  });

  // set_index/T/reset_index is the same rotation, but only when the labels
  // it promotes to headers are plain unique text -- pandas keeps duplicate
  // column names where the studio numbers them apart, and would use a
  // Timestamp where the studio uses the date's first ten characters.
  // infer_objects undoes T collapsing every column to object.
  const rotatable = !newNames.some((n, i) => newNames.indexOf(n) !== i)
    && oldCols[0].kind === "text" && !oldCols.some((c) => c.formula)
    && !oldRows.some((r) => r.agg);
  pushOp(rotatable
    ? DF_NAME + " = " + DF_NAME + ".set_index(" + pyLit(oldCols[0].name) + ").T"
      + ".rename_axis(\"Field\").reset_index().infer_objects()"
    : null,
    "the transposed headers are not plain unique text");

  selection = [];
  if (dropped.length) toast("Transposed \u2014 dropped " + dropped.join(", "));
  return true;
}

// ===========================================================================
// DERIVED VALUES
//
// A computed column has to be right in three places: on screen now, after a
// source cell is edited, and in the regenerated call. The third is what
// decides the design -- the formula is emitted as a df.insert() line rather
// than baked as numbers, so re-running against refreshed data recomputes it
// instead of freezing the column at today's value. That in turn forces the
// evaluation order below to match pandas exactly.
//
// Grammar:
//   expr    := term (('+' | '-') term)*
//   term    := factor (('*' | '/') factor)*
//   factor  := '-'? primary
//   primary := number | '[' column ']' | agg '(' expr ')' | '(' expr ')'
//   agg     := sum | mean | median | min | max | count
// ===========================================================================
const FORMULA_AGGS = ["sum", "mean", "median", "min", "max", "count"];

function tokenizeFormula(src) {
  const out = [];
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (/\s/.test(c)) { i++; continue; }
    if (c === "[") {
      const j = src.indexOf("]", i);
      if (j < 0) throw new Error("a [column name] is not closed");
      out.push({ t: "col", v: src.slice(i + 1, j).trim() });
      i = j + 1; continue;
    }
    if (/[0-9.]/.test(c)) {
      const m = /^[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?/.exec(src.slice(i));
      if (!m) throw new Error("could not read a number at position " + i);
      out.push({ t: "num", v: Number(m[0]) });
      i += m[0].length; continue;
    }
    if (/[a-zA-Z_]/.test(c)) {
      const m = /^[a-zA-Z_][a-zA-Z_0-9]*/.exec(src.slice(i));
      out.push({ t: "fn", v: m[0].toLowerCase() });
      i += m[0].length; continue;
    }
    if ("+-*/()".indexOf(c) >= 0) { out.push({ t: c }); i++; continue; }
    throw new Error("unexpected " + JSON.stringify(c)
                    + " \u2014 column names go in [square brackets]");
  }
  if (!out.length) throw new Error("the formula is empty");
  return out;
}

function parseFormula(src) {
  const tk = tokenizeFormula(src);
  let p = 0;
  const peek = () => tk[p];
  const eat = (t) => {
    if (!tk[p] || tk[p].t !== t) throw new Error("expected " + JSON.stringify(t));
    return tk[p++];
  };
  const expr = () => {
    let n = term();
    while (peek() && (peek().t === "+" || peek().t === "-"))
      n = { k: "bin", op: tk[p++].t, a: n, b: term() };
    return n;
  };
  const term = () => {
    let n = factor();
    while (peek() && (peek().t === "*" || peek().t === "/"))
      n = { k: "bin", op: tk[p++].t, a: n, b: factor() };
    return n;
  };
  const factor = () => {
    if (peek() && peek().t === "-") { p++; return { k: "neg", a: factor() }; }
    return primary();
  };
  const primary = () => {
    const t = peek();
    if (!t) throw new Error("the formula ends early");
    if (t.t === "num") { p++; return { k: "num", v: t.v }; }
    if (t.t === "col") { p++; return { k: "col", name: t.v }; }
    if (t.t === "(") { p++; const e = expr(); eat(")"); return e; }
    if (t.t === "fn") {
      if (FORMULA_AGGS.indexOf(t.v) < 0)
        throw new Error(JSON.stringify(t.v) + " is not a function \u2014 use "
                        + FORMULA_AGGS.join(", "));
      p++; eat("("); const e = expr(); eat(")");
      return { k: "agg", fn: t.v, a: e };
    }
    throw new Error("unexpected " + JSON.stringify(t.v == null ? t.t : t.v));
  };
  const ast = expr();
  if (p < tk.length) throw new Error("there is leftover input after the formula");
  return ast;
}

function formulaRefs(ast, out) {
  out = out || [];
  if (ast.k === "col" && out.indexOf(ast.name) < 0) out.push(ast.name);
  if (ast.a) formulaRefs(ast.a, out);
  if (ast.b) formulaRefs(ast.b, out);
  return out;
}

// Whether a node evaluates to one value per row rather than to a scalar.
// Only the per-row ones need guarding against a zero denominator.
function isSeriesNode(n) {
  if (n.k === "col") return true;
  if (n.k === "agg" || n.k === "num") return false;
  if (n.k === "neg") return isSeriesNode(n.a);
  return isSeriesNode(n.a) || isSeriesNode(n.b);
}

/** Parse and validate against the live columns. Throws with a readable why. */
function compileFormula(src, forColumn) {
  const ast = parseFormula(String(src || ""));
  const refs = formulaRefs(ast);
  const names = D.columns.map((c) => c.name);
  const missing = refs.filter((n) => names.indexOf(n) < 0);
  if (missing.length)
    throw new Error("no column called " + missing.map(JSON.stringify).join(", "));
  if (forColumn && refs.indexOf(forColumn) >= 0)
    throw new Error("a column cannot refer to itself");
  refs.forEach((n) => {
    const dc = D.columns[dColByName(n)];
    if (dc.kind === "spark")
      throw new Error(JSON.stringify(n) + " is a sparkline, not a number");
  });
  // pandas reduces a Series, so an aggregate needs a column inside it and
  // cannot wrap another aggregate -- both would be a scalar by then.
  (function walk(n, inAgg) {
    if (n.k === "agg") {
      if (inAgg) throw new Error("one " + n.fn + "() cannot sit inside another");
      if (!formulaRefs(n.a).length)
        throw new Error(n.fn + "() needs a [column] inside it");
      inAgg = true;
    }
    if (n.a) walk(n.a, inAgg);
    if (n.b) walk(n.b, inAgg);
  })(ast, false);
  // A chain is fine, a cycle is not, and a cycle would otherwise show up as
  // stale numbers rather than as an error.
  if (forColumn) {
    const seen = {};
    const reaches = (name) => {
      if (name === forColumn) return true;
      if (seen[name]) return false;
      seen[name] = true;
      const dc = D.columns[dColByName(name)];
      if (!dc || !dc.formula) return false;
      return dc.formula.deps.some(reaches);
    };
    if (refs.some(reaches))
      throw new Error("that would make the columns depend on each other in a loop");
  }
  return { src: String(src).trim(), ast: ast, deps: refs };
}

function evalFormulaNode(node, valueOf, aggOf) {
  switch (node.k) {
    case "num": return node.v;
    case "col": return valueOf(node.name);
    case "neg": {
      const v = evalFormulaNode(node.a, valueOf, aggOf);
      return v == null ? null : -v;
    }
    case "bin": {
      const a = evalFormulaNode(node.a, valueOf, aggOf);
      const b = evalFormulaNode(node.b, valueOf, aggOf);
      if (a == null || b == null) return null;
      if (node.op === "+") return a + b;
      if (node.op === "-") return a - b;
      if (node.op === "*") return a * b;
      return b === 0 ? null : a / b;   // matches the NaN guard the codegen emits
    }
    case "agg": return aggOf(node);
  }
  return null;
}

function reduceAgg(fn, vals) {
  if (fn === "count") return vals.length;
  if (!vals.length) return null;
  if (fn === "sum") return vals.reduce((s, v) => s + v, 0);
  if (fn === "mean") return vals.reduce((s, v) => s + v, 0) / vals.length;
  if (fn === "min") return Math.min.apply(null, vals);
  if (fn === "max") return Math.max.apply(null, vals);
  const s = vals.slice().sort((x, y) => x - y), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

// Aggregates run over the DATA rows only, so a share-of-total column does
// not fold the total row back into its own denominator.
function makeAggResolver(dataRows, valueAt) {
  const cache = {};
  const aggOf = (node) => {
    const key = JSON.stringify(node);
    if (Object.prototype.hasOwnProperty.call(cache, key)) return cache[key];
    const vals = [];
    dataRows.forEach((r) => {
      const v = evalFormulaNode(node.a, (n) => valueAt(r, n), aggOf);
      if (typeof v === "number" && isFinite(v)) vals.push(v);
    });
    cache[key] = reduceAgg(node.fn, vals);
    return cache[key];
  };
  return aggOf;
}

/** Dependency order, so a formula that reads another formula sees it fresh. */
function formulaOrder() {
  const pending = [];
  D.columns.forEach((c, i) => { if (c.formula) pending.push(i); });
  const done = {}, out = [];
  let guard = pending.length + 1;
  while (pending.length && guard-- > 0) {
    for (let k = 0; k < pending.length; k++) {
      const ci = pending[k];
      const blocked = D.columns[ci].formula.deps.some((n) => {
        const di = dColByName(n);
        return di >= 0 && D.columns[di].formula && !done[di];
      });
      if (!blocked) { out.push(ci); done[ci] = 1; pending.splice(k, 1); k--; }
    }
  }
  return out.concat(pending);
}

/** Which rows a computed row summarises. */
function aggSourceRows(r) {
  if (D.rows[r].agg.scope === "all") {
    const out = [];
    D.rows.forEach((row, i) => { if (!row.agg) out.push(i); });
    return out;
  }
  // A subtotal summarises the run of data rows immediately above it, which
  // needs no group bands and stays right when they change.
  const out = [];
  for (let i = r - 1; i >= 0 && !D.rows[i].agg; i--) out.unshift(i);
  return out;
}

/**
 * Write every derived value into D.
 *
 * D holds the formulas and the aggregate markers; these values are a cache
 * of what they currently evaluate to. Materialising rather than deriving
 * into M is deliberate -- sort, filter, heatmap extents, minibar scales and
 * the codegen all read D.rows[].cells[].raw, and every one of them should
 * see a computed column as an ordinary column of numbers.
 *
 * The order mirrors what the regenerated call does, and has to: the
 * aggregate rows are baked into the DataFrame literal and the df.insert()
 * lines run afterwards over every row, total rows included.
 */
function materialiseDerived() {
  const dataRows = [];
  D.rows.forEach((row, i) => { if (!row.agg) dataRows.push(i); });

  // 1. Computed rows fill their plain numeric columns.
  D.rows.forEach((row, r) => {
    if (!row.agg) return;
    const src = aggSourceRows(r);
    D.columns.forEach((dc, ci) => {
      if (ci === 0 || dc.formula || dc.kind !== "num") return;
      const cell = row.cells[ci];
      if (!cell) return;
      const vals = [];
      src.forEach((i) => {
        const v = D.rows[i].cells[ci] ? D.rows[i].cells[ci].raw : null;
        if (typeof v === "number" && isFinite(v)) vals.push(v);
      });
      cell.raw = reduceAgg(row.agg.fn, vals);
      delete cell.text0; delete cell.lines0;
    });
  });

  // 2. Computed columns, over EVERY row including the computed ones.
  const valueAt = (r, name) => {
    const ci = dColByName(name);
    if (ci < 0 || !D.rows[r] || !D.rows[r].cells[ci]) return null;
    const v = D.rows[r].cells[ci].raw;
    return (typeof v === "number" && isFinite(v)) ? v : null;
  };
  formulaOrder().forEach((ci) => {
    const f = D.columns[ci].formula;
    const aggOf = makeAggResolver(dataRows, valueAt);
    let whole = true, anyNull = false;
    D.rows.forEach((row, r) => {
      const cell = row.cells[ci];
      if (!cell) return;
      const v = evalFormulaNode(f.ast, (n) => valueAt(r, n), aggOf);
      cell.raw = (typeof v === "number" && isFinite(v)) ? v : null;
      if (cell.raw == null) anyNull = true;
      else if (!Number.isInteger(cell.raw)) whole = false;
      delete cell.text0; delete cell.lines0;
    });
    const dc = D.columns[ci];
    dc.kind = "num";
    dc.int_dtype = whole && !anyNull;
    dc.align0 = "right";
  });
}

// ---------------------------------------------------------------------------
// The gestures that create derived things.
// ---------------------------------------------------------------------------
function addComputedColumn(at, name, src) {
  const nOld = D.columns.length;
  const nm = uniqueColumnName(String(name || "").trim() || "Computed");
  const f = compileFormula(src, nm);          // throws; the caller toasts it
  at = Math.max(0, Math.min(nOld, at));
  pushUndo("computed column");
  D.columns.splice(at, 0, {
    name: nm, kind: "num", int_dtype: false, wrap: false, minibar_src: null,
    w0: 72, fmt0: null, align0: "right", formula: f,
  });
  D.rows.forEach((row) => { row.cells.splice(at, 0, { raw: null }); });
  applyStructural({ colMap: (i) => (i < at ? i : i + 1), nColsOld: nOld });
  // The values have to exist before the column can be measured, and it is a
  // column the engine has never laid out, so its width is pinned.
  materialiseDerived();
  const w = measuredColumnWidth(nm, D.rows.map(
    (row) => formatRaw(row.cells[at].raw, null)));
  D.columns[at].w0 = w;
  pinColumnWidth(nm, w);
  selection = [];
  return true;
}

function setColumnFormula(ci, src) {
  const dc = D.columns[ci];
  const f = compileFormula(src, dc.name);     // throws; the caller toasts it
  pushUndo("formula");
  dc.formula = f;
  dc.minibar_src = null;
  materialiseDerived();
  return true;
}

// Keeps the numbers, drops the rule that produced them. Also what happens
// on its own when a source column is deleted.
function detachFormula(ci) {
  if (!D.columns[ci].formula) return false;
  pushUndo("detach formula");
  delete D.columns[ci].formula;
  inferColumn(ci);
  // Without the rule those numbers are values, and values live in the frame.
  pushOp(null, "a formula was replaced by the numbers it produced");
  return true;
}

function addComputedRow(at, fn, scope, label, quiet) {
  const nOld = D.rows.length;
  at = Math.max(0, Math.min(nOld, at));
  // A grand total appended to the end is one pandas line. A subtotal sits
  // inside the frame at a position that says nothing about a later pull, so
  // it stays baked.
  const appendable = scope === "all" && at === nOld
    && !D.rows.some((r) => r.agg);
  if (!quiet) pushUndo("computed row");
  D.rows.splice(at, 0, {
    h0: M.geom.row_default_h,
    agg: { fn: fn, scope: scope },
    cells: D.columns.map((dc, ci) => ({
      raw: ci === 0 ? label : null,
      spark: dc.kind === "spark" ? [] : null,
    })),
  });
  applyStructural({ rowMap: (i) => (i < at ? i : i + 1), nRowsOld: nOld });
  const key = scope === "all" ? "total_rows" : "subtotal_rows";
  K[key] = (K[key] || []).concat([at]).sort((a, b) => a - b);
  if (appendable) {
    // Computed columns are not in the frame yet, so they are left out here
    // and pick the row up when their df.insert runs over every row.
    const parts = [pyLit(D.columns[0].name) + ": " + pyLit(label)];
    D.columns.forEach((dc, ci) => {
      if (ci === 0 || dc.formula || dc.kind !== "num") return;
      parts.push(pyLit(dc.name) + ": " + DF_NAME + "[" + pyLit(dc.name)
                 + "]." + fn + "()");
    });
    pushOp(DF_NAME + ".loc[len(" + DF_NAME + ")] = {" + parts.join(", ") + "}");
  } else {
    pushOp(null, "a summary row was placed inside the table");
  }
  selection = [];
  return true;
}

// One subtotal per group band, inserted bottom-up so the earlier insertions
// do not move the boundaries the later ones are measured against.
function addBandSubtotals(fn, word) {
  const labels = spansToLabels(K.row_groups, D.rows.length);
  if (!K.row_groups || !K.row_groups.length) {
    toast("There are no group bands to subtotal");
    return false;
  }
  const ends = [];
  labels.forEach((l, i) => {
    if (i + 1 >= labels.length || labels[i + 1] !== l) ends.push([i + 1, l]);
  });
  const usable = ends.filter(([e]) => e > 0 && !D.rows[e - 1].agg);
  if (!usable.length) { toast("Every band already ends in a computed row"); return false; }
  pushUndo("band subtotals");
  usable.slice().reverse().forEach(([end, label]) => {
    addComputedRow(end, fn, "band", (label || "Group") + " " + word, true);
  });
  return true;
}

// ---------------------------------------------------------------------------
// menus
// ---------------------------------------------------------------------------
function cellMenu(x, y, r, c) {
  const n = selection.length;
  const col = M.columns[c];
  openMenu(x, y, (m) => {
    mHead(m, n > 1 ? n + " cells selected" : "Cell " + col.name + " / row " + r);

    mHead(m, "Background \u2014 cell_colors");
    mSwatches(m, (hex) => {
      pushUndo("cell colour");
      K.cell_colors = K.cell_colors || {};
      selection.forEach(([rr, cc]) => { K.cell_colors[ck(rr, cc)] = hex; });
      redraw("cell_colors x" + n);
    });

    mHead(m, "Text colour \u2014 cell_text_colors");
    mSwatches(m, (hex) => {
      pushUndo("cell text colour");
      K.cell_text_colors = K.cell_text_colors || {};
      selection.forEach(([rr, cc]) => { K.cell_text_colors[ck(rr, cc)] = hex; });
      redraw("cell_text_colors x" + n);
    });

    mSep(m);
    mRow(m, "Clear cell formatting", String(n), () => {
      pushUndo("clear cells");
      selection.forEach(([rr, cc]) => {
        if (K.cell_colors) delete K.cell_colors[ck(rr, cc)];
        if (K.cell_text_colors) delete K.cell_text_colors[ck(rr, cc)];
        if (K.value_overrides) delete K.value_overrides[ck(rr, cc)];
      });
      redraw("cleared " + n + " cells");
    });
    mRow(m, "Change the value\u2026", "double-click", () => editCellValue(r, c));
    mRow(m, "Print something else here\u2026", "value_overrides", () => {
      openMenu(x, y, (mm) => {
        mHead(mm, "Text to print instead");
        mNote(mm, "The value underneath is unchanged, so the heatmap, any "
                  + "sort and the DataFrame still see it. Use this for "
                  + "\u2014, n/a, or a footnote marker.");
        mNumber(mm, "e.g. n/a", "", (txt) => {
          pushUndo("printed text");
          K.value_overrides = K.value_overrides || {};
          selection.forEach(([rr, cc]) => { K.value_overrides[ck(rr, cc)] = txt; });
          redraw("value_overrides x" + n);
        });
      });
    });

    mSep(m);
    mHead(m, "Row " + r + " \u2014 row_colors");
    mSwatches(m, (hex) => {
      pushUndo("row colour");
      K.row_colors = K.row_colors || {};
      const rows = [...new Set(selection.map(([rr]) => rr))];
      rows.forEach((rr) => { K.row_colors[rr] = hex; });
      redraw("row_colors x" + rows.length);
    });
    const isTotal = (K.total_rows || []).includes(r);
    const isSub = (K.subtotal_rows || []).includes(r);
    mRow(m, (isTotal ? "Unmark" : "Mark") + " as total row", "total_rows", () => {
      pushUndo("total row");
      K.total_rows = K.total_rows || [];
      K.total_rows = isTotal ? K.total_rows.filter((i) => i !== r)
                             : K.total_rows.concat([r]).sort((a, b) => a - b);
      redraw("total_rows");
    });
    mRow(m, (isSub ? "Unmark" : "Mark") + " as subtotal row", "subtotal_rows", () => {
      pushUndo("subtotal row");
      K.subtotal_rows = K.subtotal_rows || [];
      K.subtotal_rows = isSub ? K.subtotal_rows.filter((i) => i !== r)
                              : K.subtotal_rows.concat([r]).sort((a, b) => a - b);
      redraw("subtotal_rows");
    });
    mHead(m, "Indent \u2014 row_indent");
    mChips(m, [[0, "none"], [1, "1 level"], [2, "2 levels"]],
      (K.row_indent || [])[r] || 0, (lvl) => {
        pushUndo("row indent");
        K.row_indent = K.row_indent || M.rows.map(() => 0);
        while (K.row_indent.length < M.rows.length) K.row_indent.push(0);
        [...new Set(selection.map(([rr]) => rr))].forEach((rr) => {
          K.row_indent[rr] = +lvl;
        });
        redraw("row_indent");
      });
    mRow(m, "Start a group band here\u2026", "row_groups", () => {
      openMenu(x, y, (mm) => {
        mHead(mm, "Group label starting at row " + r);
        mNumber(mm, "e.g. Developed Markets", "", (label) => {
          if (!label) return;
          pushUndo("row group");
          insertGroupAt(r, label);
          redraw("row_groups");
        });
      });
    });
    mRow(m, "Clear row styling", "", () => {
      pushUndo("clear row");
      const rows = [...new Set(selection.map(([rr]) => rr))];
      rows.forEach((rr) => {
        if (K.row_colors) delete K.row_colors[rr];
        if (K.total_rows) K.total_rows = K.total_rows.filter((i) => i !== rr);
        if (K.subtotal_rows) K.subtotal_rows = K.subtotal_rows.filter((i) => i !== rr);
        if (K.row_indent) K.row_indent[rr] = 0;
      });
      redraw("row styling cleared");
    });

    mSep(m);
    mHead(m, "Rows");
    mNote(m, "Structural edits change the data, so the Data tab and the "
             + "DataFrame in the Code tab follow. Styling stays attached to "
             + "the row it was put on.");
    mRow(m, "Insert a blank row above", "", () => {
      if (insertRow(r)) redraw("Inserted a row at " + r);
    });
    mRow(m, "Insert a blank row below", "", () => {
      if (insertRow(r + 1)) redraw("Inserted a row at " + (r + 1));
    });
    mRow(m, "Duplicate this row", "", () => {
      if (duplicateRow(r)) redraw("Duplicated row " + r);
    });
    const delRows = [...new Set(selection.map(([rr]) => rr))];
    const delLabel = delRows.length > 1
      ? "Delete " + delRows.length + " selected rows" : "Delete this row";
    mRow(m, delLabel, "", () => {
      if (deleteRows(delRows.length ? delRows : [r]))
        redraw(delLabel.replace("Delete", "Deleted"));
    });
    mChips(m, [["up", "Move up"], ["down", "Move down"],
               ["top", "To top"], ["bottom", "To bottom"]], null, (where) => {
      const to = where === "up" ? r - 1 : where === "down" ? r + 1
               : where === "top" ? 0 : D.rows.length - 1;
      if (moveRow(r, to)) redraw("Moved row " + r + " to " + to);
    });
    if (D.rows[r].agg) {
      mRow(m, "Keep the numbers, stop recomputing this row", "", () => {
        pushUndo("detach summary row");
        delete D.rows[r].agg;
        redraw("Row " + r + " is now plain data");
      });
    } else {
      mRow(m, "Insert a summary row here\u2026", "subtotal_rows", () => {
        openMenu(x, y, (mm) => {
          mHead(mm, "Summarise the rows above");
          mNote(mm, "A summary row reads the run of ordinary rows directly "
                    + "above it and follows them as they are edited. Its "
                    + "numbers are written into the DataFrame as values, so "
                    + "the regenerated call reproduces the table you see.");
          summaryChoices(mm, (fn, label) => {
            if (addComputedRow(r, fn, "band", label))
              redraw("Inserted a " + fn + " row at " + r);
          });
        });
      });
    }

    mSep(m);
    mHead(m, "Sort and filter by " + col.name);
    mNote(m, "Total and subtotal rows hold their position and split the "
             + "sort, and so does a group band, so a sort reorders within "
             + "each band rather than across them.");
    mChips(m, [["asc", "Sort A\u2192Z / low\u2192high"],
               ["desc", "Sort Z\u2192A / high\u2192low"]], null, (dir) => {
      if (sortRows(c, dir === "asc")) redraw("Sorted by " + col.name);
    });
    // Each filter carries the pandas mask that KEEPS what it does not
    // delete, so the same rule can run again over a later pull.
    const dfc = DF_NAME + "[" + pyLit(col.name) + "]";
    mRow(m, "Delete rows where this is blank", "", () => {
      if (deleteRowsWhere(c, (v) => v == null, "blank in " + col.name,
                          dfc + ".notna()")) redraw();
    });
    const numFilter = (label, cmp, op) => {
      mRow(m, "Delete rows where this is " + label + "\u2026", "", () => {
        openMenu(x, y, (mm) => {
          mHead(mm, "Delete rows where " + col.name + " is " + label);
          mNumber(mm, "value", "", (txt) => {
            const t = parseCellInput(txt, col.kind);
            if (t == null) return;
            // Negated rather than inverted, so a blank -- which compares
            // false either way in both languages -- survives the filter.
            if (deleteRowsWhere(c, (v) => v != null && cmp(v, t),
                                label + " " + txt + " in " + col.name,
                                "~(" + dfc + " " + op + " " + pyLit(t) + ")")) redraw();
          });
        });
      });
    };
    if (col.kind === "num") {
      numFilter("below", (v, t) => v < t, "<");
      numFilter("above", (v, t) => v > t, ">");
    } else {
      mRow(m, "Delete rows that do not contain\u2026", "", () => {
        openMenu(x, y, (mm) => {
          mHead(mm, "Keep only rows whose " + col.name + " contains");
          mNumber(mm, "text", "", (txt) => {
            if (!txt) return;
            const needle = txt.toLowerCase();
            if (deleteRowsWhere(c,
                  (v) => v == null || !String(v).toLowerCase().includes(needle),
                  "without \u201c" + txt + "\u201d in " + col.name,
                  dfc + ".notna() & " + dfc + ".astype(str).str.lower()"
                  + ".str.contains(" + pyLit(needle) + ", regex=False)")) redraw();
          });
        });
      });
    }
  });
}

// The six ways a summary row can read the rows it covers, with the label it
// writes into the first column.
function summaryChoices(m, pick) {
  [["sum", "Total", "adds them up"],
   ["mean", "Average", "the arithmetic mean"],
   ["median", "Median", "the middle value"],
   ["min", "Minimum", "the smallest"],
   ["max", "Maximum", "the largest"],
   ["count", "Count", "how many are not blank"]].forEach(([fn, label, why]) => {
    mRow(m, label, why, () => pick(fn, label));
  });
}

function insertGroupAt(rowIdx, label) {
  // row_groups is a list of (label, count) covering every row in order.
  const n = M.rows.length;
  let groups = clone(K.row_groups || []);
  if (!groups.length) {
    if (rowIdx === 0) groups = [[label, n]];
    else groups = [["", rowIdx], [label, n - rowIdx]];
    K.row_groups = groups; return;
  }
  const out = []; let cursor = 0;
  groups.forEach(([lbl, cnt]) => {
    const start = cursor, end = cursor + cnt;
    if (rowIdx > start && rowIdx < end) {
      out.push([lbl, rowIdx - start]);
      out.push([label, end - rowIdx]);
    } else if (rowIdx === start) {
      out.push([label, cnt]);
    } else out.push([lbl, cnt]);
    cursor = end;
  });
  K.row_groups = out;
}

function headerMenu(x, y, ci, shift) {
  const col = M.columns[ci];
  const isDate = col.kind === "date";
  const firstCell = M.rows.length ? M.rows[0].cells[ci] : null;
  const sampleRaw = firstCell ? firstCell.raw : null;
  const preview = (hint) => {
    if (sampleRaw == null) return null;
    try { return formatRaw(sampleRaw, hint); } catch (e) { return null; }
  };

  openMenu(x, y, (m) => {
    mHead(m, "Column: " + col.name);

    if (colSelection.length > 1) {
      mHead(m, colSelection.length + " columns selected \u2014 heatmap_groups");
      mNote(m, "One shared colour scale across the selected columns. "
              + "Row scope compares within each row; group scope uses one "
              + "scale for the whole block.");
      HEATMAP_SCOPES.forEach((s) => {
        mRow(m, "Scale by " + s.label.toLowerCase(), s.scope, () => {
          pushUndo("heatmap group");
          const names = colSelection.slice().sort((a, b) => a - b)
                          .map((i) => M.columns[i].name);
          K.heatmap_groups = (K.heatmap_groups || []).filter(
            (g) => !(g.columns || []).some((n) => names.includes(n)));
          K.heatmap_groups.push({ columns: names, scope: s.scope,
                                  mode: "sequential" });
          colSelection = [];
          redraw("heatmap_groups: " + names.length + " cols, " + s.scope + " scope");
        });
      });
      mRow(m, "Diverging instead of sequential", "mode", () => {
        pushUndo("heatmap mode");
        const names = colSelection.slice().sort((a, b) => a - b)
                        .map((i) => M.columns[i].name);
        K.heatmap_groups = (K.heatmap_groups || []).filter(
          (g) => !(g.columns || []).some((n) => names.includes(n)));
        K.heatmap_groups.push({ columns: names, scope: "group",
                                mode: "diverging", palette: "rwg" });
        colSelection = [];
        redraw("heatmap_groups: diverging");
      });
      mSep(m);
    }

    if (isDate) {
      mHead(m, "Date format \u2014 column_formats");
      mChips(m, DATE_FORMATS.map((f) => [f.hint, preview(f.hint) || f.label]),
        col.fmt, (v) => {
          pushUndo("date format");
          K.column_formats = K.column_formats || {};
          K.column_formats[col.name] = v;
          redraw("column_formats[" + JSON.stringify(col.name) + "] = " + JSON.stringify(v));
        });
      mRow(m, "Custom strftime\u2026", "%d %b %y", () => {
        openMenu(x, y, (mm) => {
          mHead(mm, "strftime for " + col.name);
          mNumber(mm, "%d %b %y", col.fmt || "", (v) => {
            pushUndo("date format");
            K.column_formats = K.column_formats || {};
            K.column_formats[col.name] = v;
            redraw("column_formats set");
          });
        });
      });
    } else {
      mHead(m, "Number format \u2014 column_formats");
      mChips(m, NUMBER_FORMATS.map((f) => [f.hint, preview(f.hint) || f.label]),
        col.fmt || "", (v) => {
          pushUndo("number format");
          K.column_formats = K.column_formats || {};
          if (v) K.column_formats[col.name] = v;
          else delete K.column_formats[col.name];
          redraw("column_formats[" + JSON.stringify(col.name) + "] = "
                 + (v ? JSON.stringify(v) : "auto"));
        });

      mHead(m, "Conditional colour \u2014 column_color_modes");
      const curMode = (() => {
        const raw = (K.column_color_modes || {})[col.name];
        if (!raw) return "";
        return typeof raw === "string" ? raw : (raw.mode || "");
      })();
      mChips(m, COLOR_MODES.map((c) => [c.mode, c.label]), curMode, (v) => {
        pushUndo("colour mode");
        K.column_color_modes = K.column_color_modes || {};
        if (!v) { delete K.column_color_modes[col.name]; redraw("colour mode cleared"); return; }
        K.column_color_modes[col.name] = v;
        if (v === "rag" && !((K.rag_thresholds || {})[col.name])) {
          const pool = columnNumbers(ci);
          if (pool.length) {
            const lo = Math.min(...pool), hi = Math.max(...pool);
            const a = lo + (hi - lo) / 3, b = lo + 2 * (hi - lo) / 3;
            K.rag_thresholds = K.rag_thresholds || {};
            K.rag_thresholds[col.name] = { amber_above: +a.toFixed(2),
                                           red_above: +b.toFixed(2) };
            redraw("rag with thresholds seeded from the data \u2014 edit below");
            return;
          }
        }
        redraw("column_color_modes[" + JSON.stringify(col.name) + "] = " + JSON.stringify(v));
      });
      if (curMode === "rag") {
        const thr = (K.rag_thresholds || {})[col.name] || {};
        mHead(m, "RAG thresholds \u2014 higher is worse");
        mNumber(m, "amber_above, red_above",
          (thr.amber_above != null ? thr.amber_above : "") +
          (thr.red_above != null ? ", " + thr.red_above : ""),
          (v) => {
            const parts = String(v).split(",").map((s) => parseFloat(s.trim()));
            if (parts.length !== 2 || parts.some(isNaN)) {
              toast("Enter two numbers: amber_above, red_above"); return;
            }
            pushUndo("rag thresholds");
            K.rag_thresholds = K.rag_thresholds || {};
            K.rag_thresholds[col.name] = { amber_above: parts[0], red_above: parts[1] };
            redraw("rag_thresholds set");
          });
        mRow(m, "Flip to lower-is-worse", "red_below", () => {
          const t = (K.rag_thresholds || {})[col.name] || {};
          pushUndo("rag direction");
          K.rag_thresholds[col.name] = {
            red_below: t.amber_above != null ? t.amber_above : 0,
            amber_below: t.red_above != null ? t.red_above : 0 };
          redraw("rag_thresholds flipped");
        });
      }

      const isSigned = (K.signed_columns || []).includes(col.name);
      mRow(m, (isSigned ? "Remove" : "Apply") + " signed text colour", "signed_columns", () => {
        pushUndo("signed column");
        K.signed_columns = K.signed_columns || [];
        K.signed_columns = isSigned ? K.signed_columns.filter((n) => n !== col.name)
                                    : K.signed_columns.concat([col.name]);
        redraw("signed_columns");
      });
      const hasBar = !!((K.minibar_columns || {})[col.name]);
      mRow(m, (hasBar ? "Remove" : "Add") + " mini-bars", "minibar_columns", () => {
        pushUndo("minibar");
        K.minibar_columns = K.minibar_columns || {};
        const dc = D.columns[ci];
        if (hasBar) {
          delete K.minibar_columns[col.name];
          dc.minibar_src = null;
          dc.kind = "num";
          inferColumn(ci);
        } else {
          K.minibar_columns[col.name] = col.name;
          // A minibar draws its own column's numbers, and rebuild() rescales
          // the extent from D on every pass, so nothing is cached here.
          dc.minibar_src = col.name;
          dc.kind = "minibar";
        }
        redraw("minibar_columns");
      });
    }

    mHead(m, "Align \u2014 column_aligns");
    mChips(m, [["left", "left"], ["center", "center"], ["right", "right"]],
      col.align, (v) => {
        pushUndo("align");
        K.column_aligns = K.column_aligns || {};
        K.column_aligns[col.name] = v;
        redraw("column_aligns[" + JSON.stringify(col.name) + "] = " + JSON.stringify(v));
      });

    mSep(m);
    const hl = (K.highlight_columns || []).includes(col.name);
    mRow(m, (hl ? "Remove" : "Add") + " column highlight", "highlight_columns", () => {
      pushUndo("highlight");
      K.highlight_columns = K.highlight_columns || [];
      K.highlight_columns = hl ? K.highlight_columns.filter((n) => n !== col.name)
                               : K.highlight_columns.concat([col.name]);
      redraw("highlight_columns");
    });
    mRow(m, "Rename this column\u2026", "double-click", () => {
      const th = document.querySelector('#ptTable thead th[data-c="' + ci + '"]');
      const ln = th && th.querySelector(".ln");
      if (ln) beginEdit(ln, (txt) => {
        if (!txt || txt === col.name) { redraw(); return; }
        pushUndo("rename column");
        renameColumn(col.name, txt);
        redraw("renamed");
      });
    });
    mHead(m, "Width \u2014 drag the header edge");
    mNumber(m, "px", M.geom.col_widths[ci], (v) => {
      const w = parseInt(v, 10);
      if (isNaN(w)) { toast("Enter a pixel width"); return; }
      pushUndo("column width");
      K.column_widths = K.column_widths || {};
      K.column_widths[col.name] = Math.max(48, w);
      redraw("column_widths set");
    });
    mRow(m, "Reset width to engine default", String(D.columns[ci].w0) + "px", () => {
      pushUndo("column width");
      if (K.column_widths) delete K.column_widths[col.name];
      redraw("width reset");
    });
    mRow(m, "Clear all formatting on this column", "", () => {
      pushUndo("clear column");
      ["column_formats", "column_aligns", "column_color_modes",
       "rag_thresholds", "column_widths", "minibar_columns"].forEach((k) => {
        if (K[k]) delete K[k][col.name];
      });
      ["highlight_columns", "signed_columns"].forEach((k) => {
        if (K[k]) K[k] = K[k].filter((n) => n !== col.name);
      });
      K.heatmap_groups = (K.heatmap_groups || []).filter(
        (g) => !(g.columns || []).includes(col.name));
      redraw("column cleared");
    });

    mSep(m);
    mHead(m, "Columns");
    mNote(m, "Structural edits change the data, so the Data tab and the "
             + "DataFrame in the Code tab follow. A column the studio creates "
             + "gets its width pinned, because the engine has never laid that "
             + "column out and cannot otherwise be told what you are looking at.");
    const insertAt = (at) => {
      openMenu(x, y, (mm) => {
        mHead(mm, "Name for the new column");
        mNumber(mm, "e.g. Forecast", "", (nm) => {
          if (insertColumn(at, nm)) redraw("Inserted a column at " + at);
        });
      });
    };
    mRow(m, "Insert a blank column before", "", () => insertAt(ci));
    mRow(m, "Insert a blank column after", "", () => insertAt(ci + 1));
    mRow(m, "Duplicate this column", "", () => {
      if (duplicateColumn(ci)) redraw("Duplicated " + col.name);
    });
    mRow(m, "Delete this column", "", () => {
      if (deleteColumns([ci])) redraw("Deleted " + col.name);
    });
    mChips(m, [["left", "Move left"], ["right", "Move right"],
               ["first", "To front"], ["last", "To back"]], null, (where) => {
      const to = where === "left" ? ci - 1 : where === "right" ? ci + 1
               : where === "first" ? 0 : D.columns.length - 1;
      if (moveColumn(ci, to)) redraw("Moved " + col.name + " to " + to);
    });
    mChips(m, [["asc", "Sort rows A\u2192Z / low\u2192high"],
               ["desc", "Sort rows Z\u2192A / high\u2192low"]], null, (dir) => {
      if (sortRows(ci, dir === "asc")) redraw("Sorted by " + col.name);
    });

    mSep(m);
    mHead(m, "Computed \u2014 df.insert(...)");
    const formulaHelp = (mm) => {
      const nums = D.columns.filter((c) => c.kind === "num" && !c.formula)
                            .map((c) => "[" + c.name + "]");
      mNote(mm, "Numbers: " + (nums.join("  ") || "none")
                + ".  Combine them with + - * / ( ) and numbers, or wrap one in "
                + FORMULA_AGGS.join(", ") + " for a whole-column figure \u2014 "
                + "so [x] / sum([x]) * 100 is a share of the total. The formula "
                + "is written into the call as a df.insert() line, so re-running "
                + "it against fresh data recomputes the column instead of "
                + "freezing today's numbers.");
    };
    const dcf = D.columns[ci].formula;
    if (dcf) {
      mNote(m, col.name + "  =  " + dcf.src);
      mRow(m, "Edit this formula\u2026", "", () => {
        openMenu(x, y, (mm) => {
          mHead(mm, "Formula for " + col.name);
          formulaHelp(mm);
          mFormula(mm, dcf.src, (src) => {
            try {
              setColumnFormula(ci, src);
              redraw(col.name + " = " + src.trim());
            } catch (err) { toast(String(err.message || err)); }
          });
        });
      });
      mRow(m, "Keep the numbers, drop the formula", "", () => {
        if (detachFormula(ci)) redraw(col.name + " is now plain data");
      });
    }
    mRow(m, "Add a computed column after\u2026", "", () => {
      openMenu(x, y, (mm) => {
        mHead(mm, "New computed column");
        formulaHelp(mm);
        mNewComputed(mm, (nm, src) => {
          try {
            addComputedColumn(ci + 1, nm, src);
            redraw("Added " + JSON.stringify(nm) + " = " + String(src).trim());
          } catch (err) { toast(String(err.message || err)); }
        });
      });
    });

    mSep(m);
    mRow(m, "Transpose the whole table", "rows \u2194 columns", () => {
      openMenu(x, y, (mm) => {
        mHead(mm, "Transpose");
        mNote(mm, "Column " + JSON.stringify(M.columns[0].name) + " becomes the "
                  + "header row and the remaining columns become rows. Cell "
                  + "colours and printed text rotate with their cells, and the "
                  + "group bands become header bands. Row styling and every "
                  + "per-column setting address things that will not exist "
                  + "afterwards, so they are dropped.");
        mRow(mm, "Transpose", String(M.rows.length) + "\u00d7"
                 + String(M.columns.length) + " \u2192 "
                 + String(M.columns.length - 1) + "\u00d7"
                 + String(M.rows.length + 1), () => {
          if (transposeTable()) redraw("Transposed");
        });
      });
    });
  });
}

function textMenu(x, y, role, el) {
  const th = M.theme;
  const sizeKey = role === "title" ? "title_font_size"
                : role === "subtitle" ? "subtitle_font_size" : "caption_font_size";
  openMenu(x, y, (m) => {
    mHead(m, role.charAt(0).toUpperCase() + role.slice(1));
    mRow(m, "Edit the text\u2026", "double-click", () => beginEdit(el, (txt) => {
      pushUndo(role);
      if (role === "caption") { K.caption = txt; K.source = null; }
      else K[role] = txt;
      redraw(role + " updated");
    }));
    mHead(m, "Size");
    mChips(m, [[-2, "smaller"], [0, "reset"], [2, "larger"]], null, (d) => {
      pushUndo(role + " size");
      K._theme_overrides = K._theme_overrides || {};
      const cur = th[sizeKey];
      K._theme_overrides[sizeKey] = +d === 0 ? BASE_THEME[sizeKey]
                                             : Math.max(8, Math.min(40, cur + (+d)));
      redraw(sizeKey + " = " + K._theme_overrides[sizeKey]);
    });
    mSep(m);
    mRow(m, "Remove this " + role, "", () => {
      pushUndo("remove " + role);
      if (role === "caption") { K.caption = null; K.source = null; }
      else K[role] = null;
      redraw(role + " removed");
    });
  });
}

function canvasMenu(x, y) {
  openMenu(x, y, (m) => {
    mHead(m, "Whole table");
    mHead(m, "Theme \u2014 skin");
    mChips(m, Object.keys(THEMES).map((k) => [k, THEMES[k].label]),
      K.skin || "gs_clean", (v) => {
        pushUndo("theme");
        K.skin = v; K._theme_overrides = {};
        redraw("skin = " + JSON.stringify(v));
      });
    mHead(m, "Display width \u2014 target_html_width");
    mChips(m, [[600, "Email 600"], [720, "Report 720"],
               [960, "Slide 960"], [1120, "Wide 1120"]],
      K.target_html_width || 720, (v) => {
        pushUndo("display width");
        K.target_html_width = +v;
        redraw("target_html_width = " + v);
      });
    mSep(m);
    mHead(m, "Computed rows");
    mNote(m, "make_table's total_rows and subtotal_rows only style a row you "
             + "had already worked out. These work it out as well, and keep "
             + "it in step as the data underneath changes.");
    mRow(m, "Add a summary row at the bottom\u2026", "total_rows", () => {
      openMenu(x, y, (mm) => {
        mHead(mm, "Summarise every row");
        summaryChoices(mm, (fn, label) => {
          if (addComputedRow(D.rows.length, fn, "all", label))
            redraw("Added a " + fn + " row");
        });
      });
    });
    mRow(m, "Add a summary row to each group band\u2026", "subtotal_rows", () => {
      openMenu(x, y, (mm) => {
        mHead(mm, "Summarise each band");
        mNote(mm, "One row at the foot of every row_groups band, labelled with "
                  + "the band. A bottom total added afterwards skips them, so "
                  + "it never counts the same number twice.");
        summaryChoices(mm, (fn, label) => {
          if (addBandSubtotals(fn, label)) redraw("Added a " + fn + " row per band");
        });
      });
    });

    mSep(m);
    mRow(m, "Reset size to the engine's own layout", "drag the edge to resize", () => {
      pushUndo("table size");
      K.column_widths = {};
      K.row_height_scale = 1.0;
      syncKnobs();
      redraw("table size reset");
    });
    mRow(m, (K.row_bands === false ? "Enable" : "Disable") + " zebra banding",
      "row_bands", () => {
        pushUndo("row bands");
        K.row_bands = K.row_bands === false;
        redraw("row_bands = " + K.row_bands);
      });
    mRow(m, "Edit the title\u2026", "double-click", () => {
      const el = document.querySelector('[data-role="title"]');
      if (el) beginEdit(el, (t) => { pushUndo("title"); K.title = t; redraw("title"); });
      else { pushUndo("title"); K.title = "Untitled table"; redraw("title added"); }
    });
    mRow(m, "Edit the caption\u2026", "double-click", () => {
      const el = document.querySelector('[data-role="caption"]');
      if (el) beginEdit(el, (t) => { pushUndo("caption"); K.caption = t; K.source = null;
                                     redraw("caption"); });
      else { pushUndo("caption"); K.caption = "Source: "; redraw("caption added"); }
    });
    mSep(m);
    mRow(m, "Download this table", "PNG 2x", () => downloadPNG(2));
    mRow(m, "Copy the make_table call", "Python", () => copyCall());
    mRow(m, "Clear every conditional format", "", () => {
      pushUndo("clear all formatting");
      ["cell_colors", "cell_text_colors", "row_colors", "column_color_modes",
       "rag_thresholds"].forEach((k) => { K[k] = {}; });
      K.heatmap_groups = []; K.highlight_columns = [];
      redraw("all conditional formatting cleared");
    });
    mRow(m, "All controls\u2026", String(KNOBS.length), () => {
      const d = document.getElementById("knobsSection");
      d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

// ===========================================================================
// PNG EXPORT -- draws the cell model to a canvas with the same primitives
// the engine draws with PIL: filled rects, text runs, rules, sparklines.
// ===========================================================================
// Split from downloadPNG so the export can be rendered and inspected without
// going through a browser download -- the round-trip probe compares this
// canvas against the engine's PNG.
function buildCanvas(scale) {
  scale = scale || 2;
  const th = M.theme, g = M.geom;
  const W = M.canvas.w, H = M.canvas.h;
  const cv = document.createElement("canvas");
  cv.width = Math.round(W * scale); cv.height = Math.round(H * scale);
  const ctx = cv.getContext("2d");
  ctx.scale(scale, scale);
  ctx.textBaseline = "top";
  const FF = th.font_family || "Arial, Helvetica, sans-serif";
  const setFont = (size, bold) => { ctx.font = (bold ? "bold " : "") + size + "px " + FF; };

  ctx.fillStyle = th.background_color; ctx.fillRect(0, 0, W, H);

  // _tbl_draw_title starts the title band at y=6, not at the side padding.
  const PAD = g.table_x;
  let y = 6;

  // title / subtitle
  M.title.lines.forEach((line) => {
    setFont(th.title_font_size, true);
    ctx.fillStyle = "#000000"; ctx.textAlign = "left";
    ctx.fillText(line, PAD, y + 1);
    y += trunc(th.title_font_size * 1.2);
  });
  M.title.subtitle.forEach((line) => {
    setFont(th.subtitle_font_size, false);
    ctx.fillStyle = th.muted_text; ctx.textAlign = "left";
    ctx.fillText(line, PAD, y + 1);
    y += trunc(th.subtitle_font_size * 1.4);
  });
  // The body's origin is layout's answer, not an accumulation of the title
  // loop above, so a rounding difference in the title cannot shift the table.
  y = g.body_top_y - g.header_h;

  const x0 = PAD, tableW = g.table_w;
  const colX = [x0];
  g.col_widths.forEach((w) => colX.push(colX[colX.length - 1] + w));

  // header band(s)
  const levels = K.header_levels || M.header_levels || [];
  const rowH = trunc(g.header_h / (levels.length + 1));
  const drawCellText = (text, cx0, cx1, cy, ch, align, color, size, bold) => {
    setFont(size, bold);
    ctx.fillStyle = color;
    const ty = cy + (ch - size) / 2 - 1;
    if (align === "right") { ctx.textAlign = "right"; ctx.fillText(text, cx1 - 10, ty); }
    else if (align === "center") { ctx.textAlign = "center";
      ctx.fillText(text, (cx0 + cx1) / 2, ty); }
    else { ctx.textAlign = "left"; ctx.fillText(text, cx0 + 10, ty); }
  };

  levels.forEach((level) => {
    ctx.fillStyle = th.primary_color; ctx.fillRect(x0, y, tableW, rowH);
    let ci = 0;
    level.forEach(([label, span], si) => {
      const cx0 = colX[ci], cx1 = colX[ci + span];
      if (si > 0) {
        ctx.fillStyle = "rgba(255,255,255,.45)";
        ctx.fillRect(cx0, y, 1, rowH);
      }
      drawCellText(label, cx0, cx1, y, rowH, "center", th.header_text,
                   th.header_font_size, true);
      ci += span;
    });
    y += rowH;
  });
  ctx.fillStyle = th.primary_color; ctx.fillRect(x0, y, tableW, rowH);
  M.columns.forEach((col, ci) => {
    drawCellText(col.name, colX[ci], colX[ci + 1], y, rowH, col.align,
                 th.header_text, th.header_font_size, true);
  });
  y += rowH;

  // top rule
  ctx.fillStyle = th.border_color; ctx.fillRect(x0, y - 1, tableW, 1);

  // body
  M.rows.forEach((row) => {
    if (row.group) {
      ctx.fillStyle = th.primary_color;
      ctx.fillRect(x0, y, tableW, g.group_band_h);
      setFont(th.body_font_size, true);
      ctx.fillStyle = th.header_text; ctx.textAlign = "left";
      ctx.fillText(row.group, x0 + 12,
                   y + (g.group_band_h - th.body_font_size) / 2 - 1);
      y += g.group_band_h;
    }
    if (row.row_bg) { ctx.fillStyle = row.row_bg; ctx.fillRect(x0, y, tableW, row.h); }
    if (K.row_bands === false && row.r > 0 && row.kind === "normal") {
      ctx.fillStyle = "#E0E0E0"; ctx.fillRect(x0, y, tableW, 1);
    }
    row.cells.forEach((cell, ci) => {
      const col = M.columns[ci];
      const cx0 = colX[ci], cx1 = colX[ci + 1];
      if (cell.bg) {
        ctx.fillStyle = cell.bg;
        ctx.fillRect(cx0 + 1, y + 1, (cx1 - cx0) - 2, row.h - 2);
      }
      if (cell.kind === "spark") {
        const sx = cx0 + 8, sy = y + 6;
        const sw = (cx1 - cx0) - 16, sh = row.h - 12;
        const g = sparkGeom(cell.spark, sw, sh);
        if (g) {
          ctx.strokeStyle = "#DDDDDD"; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(sx, sy + sh); ctx.lineTo(sx + sw, sy + sh);
          ctx.stroke();
          ctx.strokeStyle = th.primary_color; ctx.lineWidth = 2;
          ctx.beginPath();
          g.pts.forEach((p, i) => (i === 0 ? ctx.moveTo(sx + p[0], sy + p[1])
                                           : ctx.lineTo(sx + p[0], sy + p[1])));
          ctx.stroke();
          ctx.fillStyle = th.primary_color;
          ctx.beginPath();
          ctx.arc(sx + g.last[0], sy + g.last[1], 3.5, 0, Math.PI * 2);
          ctx.fill();
        }
        return;
      }
      if (cell.kind === "minibar") {
        const bx = cx0 + 8, by0 = y + 4;
        const bw = (cx1 - cx0) - 16, bh = row.h - 8;
        const g = barGeom(cell.bar, bw, bh);
        if (g) {
          ctx.fillStyle = "#FAFAFA";
          ctx.fillRect(bx, by0 + g.by, bw, g.h);
          ctx.strokeStyle = "#E0E0E0"; ctx.lineWidth = 1;
          ctx.strokeRect(bx + 0.5, by0 + g.by + 0.5, bw - 1, g.h);
          ctx.fillStyle = g.neg ? th.negative_text : th.primary_color;
          ctx.fillRect(bx + g.x, by0 + g.by, g.w, g.h);
        }
        return;
      }
      const bold = row.kind !== "normal";
      const lines = cell.lines || [cell.text];
      const lineH = trunc(th.body_font_size * 1.45);
      let ty = y + (row.h - lines.length * lineH) / 2;
      lines.forEach((L) => {
        setFont(th.body_font_size, bold);
        ctx.fillStyle = cell.fg;
        if (col.align === "right") { ctx.textAlign = "right"; ctx.fillText(L, cx1 - 10, ty); }
        else if (col.align === "center") { ctx.textAlign = "center";
          ctx.fillText(L, (cx0 + cx1) / 2, ty); }
        else { ctx.textAlign = "left"; ctx.fillText(L, cx0 + 10 + (cell.indent || 0), ty); }
        ty += lineH;
      });
    });
    y += row.h;
  });

  // bottom rule + caption
  ctx.fillStyle = th.border_color; ctx.fillRect(x0, y, tableW, 1);
  y += 6;
  M.title.caption.forEach((line) => {
    setFont(th.caption_font_size, false);
    ctx.fillStyle = th.muted_text; ctx.textAlign = "left";
    ctx.fillText(line, x0, y);
    y += trunc(th.caption_font_size * 1.4);
  });

  return cv;
}

function downloadPNG(scale) {
  scale = scale || 2;
  const cv = buildCanvas(scale);
  cv.toBlob((blob) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = FILENAME + (scale === 2 ? "" : "_" + scale + "x") + ".png";
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 200);
    toast("PNG downloaded at " + scale + "x (" + cv.width + "x" + cv.height + ")");
  }, "image/png");
}

// ===========================================================================
// CODE GENERATION -- kwargs back to a runnable make_table(...) call.
//
// This is the table studio's defining property. The chart studio cannot do
// this because its state is a mutated Vega-Lite spec with no inverse; here
// the state IS the call, so serialising is a pretty-printer and the result
// is exact.
// ===========================================================================
function pyLit(v) {
  if (v === null || v === undefined) return "None";
  if (typeof v === "boolean") return v ? "True" : "False";
  if (typeof v === "number") return String(v);
  if (Array.isArray(v)) return "[" + v.map(pyLit).join(", ") + "]";
  if (typeof v === "object") {
    const ks = Object.keys(v);
    if (!ks.length) return "{}";
    return "{" + ks.map((k) => pyLit(k) + ": " + pyLit(v[k])).join(", ") + "}";
  }
  return '"' + String(v).replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
}
function pyDictBlock(obj, keyfn, valfn) {
  const ks = Object.keys(obj);
  if (!ks.length) return null;
  const body = ks.map((k) =>
    "        " + (keyfn ? keyfn(k) : pyLit(k)) + ": " + (valfn ? valfn(obj[k]) : pyLit(obj[k])) + ",");
  return "{\n" + body.join("\n") + "\n    }";
}
function cellKeyPy(k) {
  const [r, c] = k.split(",");
  const name = M.columns[+c] ? M.columns[+c].name : c;
  return "(" + r + ", " + pyLit(name) + ")";
}

function generateCall() {
  const L = [];
  const add = (k, v) => L.push("    " + k + "=" + v + ",");
  L.push("result = make_table(");
  L.push("    df=" + DF_NAME + ",");
  if (K.title) add("title", pyLit(K.title));
  if (K.subtitle) add("subtitle", pyLit(K.subtitle));
  if (K.caption) add("caption", pyLit(K.caption));
  if (K.source) add("source", pyLit(K.source));
  if (K.skin && K.skin !== "gs_clean") add("skin", pyLit(K.skin));
  const tov = pyDictBlock(K._theme_overrides || {});
  if (tov) add("theme_overrides", tov);

  // When the data block is replaying rules it already carries the rename as
  // a real line; the note is only needed where the frame arrives renamed.
  const renames = K.column_renames || {};
  if (Object.keys(renames).length && !dataIsReplayable()) {
    L.push("    # applied to the frame before the call:");
    L.push("    #   " + DF_NAME + " = " + DF_NAME + ".rename(columns="
           + pyLit(renames) + ")");
  }

  const cf = pyDictBlock(K.column_formats || {});
  if (cf) add("column_formats", cf);
  const ca = pyDictBlock(K.column_aligns || {});
  if (ca) add("column_aligns", ca);
  if ((K.header_levels || []).length) {
    const lv = (K.header_levels || []).map(
      (lvl) => "[" + lvl.map(([l, s]) => "(" + pyLit(l) + ", " + s + ")").join(", ") + "]");
    add("header_levels", "[\n        " + lv.join(",\n        ") + ",\n    ]");
  }
  if ((K.row_groups || []).length) {
    add("row_groups", "[" + (K.row_groups || []).map(
      ([l, c]) => "(" + pyLit(l) + ", " + c + ")").join(", ") + "]");
  }
  if ((K.row_indent || []).some((v) => v)) add("row_indent", pyLit(K.row_indent));
  if (K.row_bands === false) add("row_bands", "False");
  const rc = pyDictBlock(K.row_colors || {}, (k) => k);
  if (rc) add("row_colors", rc);

  const ccm = pyDictBlock(K.column_color_modes || {});
  if (ccm) add("column_color_modes", ccm);
  if ((K.heatmap_groups || []).length) {
    const gs = (K.heatmap_groups || []).map((g) =>
      "        {\"columns\": " + pyLit(g.columns) +
      ", \"scope\": " + pyLit(g.scope || "column") +
      ", \"mode\": " + pyLit(g.mode || "sequential") +
      (g.palette ? ", \"palette\": " + pyLit(g.palette) : "") + "},");
    add("heatmap_groups", "[\n" + gs.join("\n") + "\n    ]");
  }
  const rt = pyDictBlock(K.rag_thresholds || {});
  if (rt) add("rag_thresholds", rt);
  if ((K.highlight_columns || []).length) add("highlight_columns", pyLit(K.highlight_columns));
  if ((K.signed_columns || []).length) add("signed_columns", pyLit(K.signed_columns));

  const cc = pyDictBlock(K.cell_colors || {}, cellKeyPy);
  if (cc) add("cell_colors", cc);
  const ctc = pyDictBlock(K.cell_text_colors || {}, cellKeyPy);
  if (ctc) add("cell_text_colors", ctc);

  if ((K.total_rows || []).length) add("total_rows", pyLit(K.total_rows));
  if ((K.subtotal_rows || []).length) add("subtotal_rows", pyLit(K.subtotal_rows));

  if (K.has_sparklines) L.push("    sparkline_columns=sparkline_series,");
  const mb = pyDictBlock(K.minibar_columns || {});
  if (mb) add("minibar_columns", mb);

  if (K.row_height_scale && +K.row_height_scale !== 1.0)
    add("row_height_scale", String(K.row_height_scale));
  const cw = pyDictBlock(K.column_widths || {}, (k) => pyLit(k), (v) => String(v));
  if (cw) add("column_widths", cw);
  const vo = pyDictBlock(K.value_overrides || {}, cellKeyPy);
  if (vo) add("value_overrides", vo);

  if (K.show_index) add("show_index", "True");
  if (K.target_html_width && +K.target_html_width !== 720)
    add("target_html_width", String(K.target_html_width));
  add("save_as", pyLit(K.save_as || (FILENAME + ".png")));
  L.push("    interactive=True,");
  L.push(")");
  return L.join("\n");
}

/**
 * Render a formula as the pandas that reproduces it exactly.
 *
 * `maskVar` names an index of the data rows. It is threaded into aggregate
 * arguments only, so `[GDP] / sum([GDP])` divides every row -- total rows
 * included -- by a denominator that excludes them.
 */
function formulaToPandas(ast, maskVar) {
  const P = (n, masked) => {
    switch (n.k) {
      case "num": return String(n.v);
      case "col": return masked
        ? DF_NAME + ".loc[" + maskVar + ", " + pyLit(n.name) + "]"
        : DF_NAME + "[" + pyLit(n.name) + "]";
      case "neg": return "-" + P(n.a, masked);
      case "bin": {
        let b = P(n.b, masked);
        // Dividing by zero is a blank cell in the studio, so the zeros in a
        // denominator become NaN here instead of inf in the PNG.
        if (n.op === "/" && isSeriesNode(n.b))
          b = "(" + b + ').replace(0, float("nan"))';
        return "(" + P(n.a, masked) + " " + n.op + " " + b + ")";
      }
      case "agg": return "(" + P(n.a, !!maskVar) + ")." + n.fn + "()";
    }
    return "None";
  };
  return P(ast, false);
}

function usesAggregateFn(node) {
  if (node.k === "agg") return true;
  return (node.a && usesAggregateFn(node.a)) || (node.b && usesAggregateFn(node.b));
}

/** The `pd.DataFrame({...})` block for a set of columns and their values. */
function frameLiteral(cols, rows) {
  const L = [DF_NAME + " = pd.DataFrame({"];
  cols.forEach((col, k) => {
    const vals = rows.map((cells) => {
      const raw = cells[k];
      if (raw == null) return "None";
      if (typeof raw === "object" && raw.__date__)
        return '"' + raw.__date__.slice(0, 10) + '"';
      // Whole floats stringify without their decimal point, which would
      // rebuild a float column as an int one.
      if (typeof raw === "number")
        return (!col.int_dtype && Number.isInteger(raw)) ? raw.toFixed(1) : String(raw);
      return '"' + String(raw).replace(/"/g, '\\"') + '"';
    });
    L.push("    " + pyLit(col.name) + ": [" + vals.join(", ") + "],");
  });
  L.push("})");
  cols.forEach((col) => {
    if (col.kind === "date")
      L.push(DF_NAME + "[" + pyLit(col.name) + "] = pd.to_datetime("
             + DF_NAME + "[" + pyLit(col.name) + "])");
  });
  return L;
}

/**
 * The frame the call runs on.
 *
 * When every structural edit was a rule, the frame emitted is the ORIGINAL
 * one and the rules follow it as pandas, so swapping the literal for a live
 * pull re-applies them to next month's numbers. One edit that typed a value
 * or named a position breaks that, and the frame emitted is the edited one
 * instead -- correct, but no longer a description of how to get there.
 *
 * Computed columns are outside that choice: they are always a df.insert()
 * rule and are always left out of the literal.
 */
function generateDataCode() {
  const ops = (D.ops || []).filter((o) => o.py !== "");
  const replay = dataIsReplayable();
  const L = ["import pandas as pd", ""];

  if (replay) {
    const cols = BASE_MODEL.columns;
    L.push.apply(L, frameLiteral(cols, BASE_MODEL.rows.map(
      (row) => cols.map((c, k) => (row.cells[k] ? row.cells[k].raw : null)))));
    if (ops.length) {
      L.push("");
      L.push("# Rules, not values \u2014 point " + DF_NAME
             + " at a fresh pull and these still apply.");
      ops.forEach((o) => L.push(o.py));
    }
  } else {
    const keep = [];
    M.columns.forEach((c, ci) => { if (!D.columns[ci].formula) keep.push(ci); });
    const blocked = ops.find((o) => o.py == null);
    L.push("# " + blocked.why[0].toUpperCase() + blocked.why.slice(1)
           + ", so this is the edited frame rather than the original.");
    L.push.apply(L, frameLiteral(
      keep.map((ci) => M.columns[ci]),
      M.rows.map((row) => keep.map((ci) => (row.cells[ci] ? row.cells[ci].raw : null)))));
  }

  const order = formulaOrder();
  if (order.length) {
    const aggRows = [];
    D.rows.forEach((row, i) => { if (row.agg) aggRows.push(i); });
    const needsMask = aggRows.length
      && order.some((ci) => usesAggregateFn(D.columns[ci].formula.ast));
    const maskVar = needsMask ? "_data" : null;
    L.push("");
    if (needsMask)
      L.push(maskVar + " = " + DF_NAME + ".index.difference(["
             + aggRows.join(", ") + "])   # rows that are not totals");
    // Whichever frame was emitted, its columns are D's in D's order with the
    // computed ones missing, so an insert position counts what precedes it.
    const placed = [];
    D.columns.forEach((c, ci) => { if (!c.formula) placed.push(ci); });
    order.forEach((ci) => {
      const at = placed.filter((p) => p < ci).length;
      L.push(DF_NAME + ".insert(" + at + ", " + pyLit(M.columns[ci].name) + ", "
             + formulaToPandas(D.columns[ci].formula.ast, maskVar) + ")");
      placed.push(ci);
    });
  }
  return L.join("\n");
}

function copyCall() {
  navigator.clipboard.writeText(generateCall())
    .then(() => toast("make_table(...) copied to the clipboard"))
    .catch(() => toast("Clipboard blocked \u2014 use the Code tab and select the text"));
}

// ===========================================================================
// SIDEBAR TABS
// ===========================================================================
function rawMatrix() {
  return M.rows.map((row) => M.columns.map((col, ci) => {
    const cell = row.cells[ci];
    if (!cell) return "";
    if (cell.raw == null) return "";
    if (typeof cell.raw === "object" && cell.raw.__date__) return cell.raw.__date__.slice(0, 10);
    return cell.raw;
  }));
}
function toDelimited(sep) {
  const head = M.columns.map((c) => c.name).join(sep);
  const body = rawMatrix().map((r) => r.join(sep)).join("\n");
  return head + "\n" + body;
}
function toJSONRows() {
  const names = M.columns.map((c) => c.name);
  return JSON.stringify(rawMatrix().map(
    (r) => Object.fromEntries(r.map((v, i) => [names[i], v]))), null, 2);
}

function renderDataTab() {
  const host = document.getElementById("dataTableContainer");
  if (!host) return;
  const rows = rawMatrix().map((r, i) => ({ i: i, cells: r }));
  if (_sortCol != null) {
    rows.sort((a, b) => {
      const x = a.cells[_sortCol], y = b.cells[_sortCol];
      const n = (typeof x === "number" && typeof y === "number");
      const cmp = n ? x - y : String(x).localeCompare(String(y));
      return _sortAsc ? cmp : -cmp;
    });
  }
  const t = document.createElement("table");
  t.className = "data-table";
  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  const idxTh = document.createElement("th"); idxTh.textContent = "#";
  hr.appendChild(idxTh);
  M.columns.forEach((col, ci) => {
    const th = document.createElement("th");
    th.textContent = col.name + (_sortCol === ci ? (_sortAsc ? "  v" : "  ^") : "");
    th.onclick = () => {
      if (_sortCol === ci) _sortAsc = !_sortAsc; else { _sortCol = ci; _sortAsc = true; }
      renderDataTab();
    };
    hr.appendChild(th);
  });
  thead.appendChild(hr); t.appendChild(thead);
  const tb = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const idx = document.createElement("td"); idx.textContent = row.i;
    tr.appendChild(idx);
    row.cells.forEach((v) => {
      const td = document.createElement("td"); td.textContent = v; tr.appendChild(td);
    });
    tb.appendChild(tr);
  });
  t.appendChild(tb);
  host.innerHTML = ""; host.appendChild(t);
  filterDataTab();
}
function filterDataTab() {
  const q = (document.getElementById("dataSearch").value || "").toLowerCase();
  document.querySelectorAll("#dataTableContainer tbody tr").forEach((tr) => {
    tr.classList.toggle("filtered-out", q && !tr.textContent.toLowerCase().includes(q));
  });
}

function renderCodeTab() {
  const el = document.getElementById("codePane");
  el.innerHTML = esc(generateCall())
    .replace(/^(\s*#.*)$/gm, "<span class='cm'>$1</span>")
    .replace(/\b(make_table|result)\b/g, "<span class='nm'>$1</span>")
    .replace(/&quot;(?:[^&]|&(?!quot;))*&quot;/g, (m) => "<span class='st'>" + m + "</span>")
    .replace(/\b(True|False|None)\b/g, "<span class='kw'>$1</span>");
}

function renderMetadataTab() {
  const g = document.getElementById("metaGrid");
  const modes = Object.keys(K.column_color_modes || {}).length;
  const cells = Object.keys(K.cell_colors || {}).length
              + Object.keys(K.cell_text_colors || {}).length;
  const rows = [
    ["table_id", TABLE_ID],
    ["png_path", PNG_PATH || "(not persisted)"],
    ["shape", M.rows.length + " rows x " + M.columns.length + " cols"],
    ["canvas", M.canvas.w + " x " + M.canvas.h + " px"],
    ["theme", K.skin || "gs_clean"],
    ["display width", (K.target_html_width || 720) + " px"],
    ["body font", M.theme.body_font_size + " px"],
    ["column formats", String(Object.keys(K.column_formats || {}).length)],
    ["colour modes", String(modes)],
    ["heatmap groups", String((K.heatmap_groups || []).length)],
    ["cell overrides", String(cells)],
    ["row groups", String((K.row_groups || []).length)],
    ["totals / subtotals", (K.total_rows || []).length + " / "
                            + (K.subtotal_rows || []).length],
    ["edits this session", String(_undo.length)],
  ];
  g.innerHTML = rows.map(([k, v]) =>
    "<dt>" + esc(k) + "</dt><dd>" + esc(v) + "</dd>").join("");
}

function refreshTabs() {
  renderDataTab(); renderCodeTab(); renderMetadataTab();
  savePrefs();
}

// ===========================================================================
// ADVANCED PANEL
// ===========================================================================
function knobValue(k) {
  if (k.name === "theme") return K.skin || "gs_clean";
  if (k.name === "target_html_width") return String(K.target_html_width || 720);
  if (k.name === "row_height_scale") return K.row_height_scale || 1.0;
  if (k.kwarg && k.type === "checkbox")
    return k.kwarg === "row_bands" ? K.row_bands !== false : !!K[k.kwarg];
  if (k.kwarg) return K[k.kwarg] == null ? "" : K[k.kwarg];
  return (K._theme_overrides || {})[k.name] != null
    ? K._theme_overrides[k.name] : M.theme[k.name];
}
function setKnob(k, value) {
  pushUndo(k.label);
  if (k.name === "theme") { K.skin = value; K._theme_overrides = {}; }
  else if (k.name === "target_html_width") K.target_html_width = +value;
  else if (k.name === "row_height_scale") K.row_height_scale = +value;
  else if (k.kwarg === "row_bands") K.row_bands = !!value;
  else if (k.kwarg && k.type === "checkbox") K[k.kwarg] = !!value;
  else if (k.kwarg) K[k.kwarg] = value === "" ? null : value;
  else {
    K._theme_overrides = K._theme_overrides || {};
    K._theme_overrides[k.name] = k.type === "range" ? +value : value;
  }
  redraw(k.label + " updated");
}

function buildKnobs() {
  const body = document.getElementById("knobsBody");
  body.innerHTML = "";
  const byGroup = {};
  KNOBS.forEach((k) => { (byGroup[k.group] = byGroup[k.group] || []).push(k); });
  GROUP_ORDER.forEach((grp) => {
    if (!byGroup[grp]) return;
    const card = document.createElement("div");
    card.className = "knob-card";
    card.innerHTML = "<h3>" + esc(grp) + "</h3>";
    byGroup[grp].forEach((k) => card.appendChild(renderKnob(k)));
    body.appendChild(card);
  });

  const panel = document.createElement("div");
  panel.className = "sheet-panel";
  panel.innerHTML = "<span class='lbl'>Style sheet</span>";
  const sel = document.createElement("select");
  sel.id = "sheetSelect";
  panel.appendChild(sel);
  const mk = (label, fn) => {
    const b = document.createElement("button"); b.textContent = label;
    b.onclick = fn; panel.appendChild(b);
  };
  mk("Save as new", saveSheetAsNew);
  mk("Apply", () => applySheet(sel.value));
  mk("Delete", () => deleteSheet(sel.value));
  mk("Export .json", () => download(FILENAME + "_style_sheet.json",
      JSON.stringify(buildSheet(), null, 2), "application/json"));
  body.appendChild(panel);
  refreshSheetSelect();
}

function renderKnob(k) {
  const row = document.createElement("div");
  row.className = "knob-row";
  const lab = document.createElement("label");
  lab.textContent = k.label;
  if (k.help) lab.title = k.help;
  row.appendChild(lab);

  const val = knobValue(k);
  let input;
  if (k.type === "range") {
    input = document.createElement("input");
    input.type = "range"; input.min = k.min; input.max = k.max; input.step = k.step;
    input.value = val;
  } else if (k.type === "checkbox") {
    input = document.createElement("input");
    input.type = "checkbox"; input.checked = !!val;
  } else if (k.type === "select") {
    input = document.createElement("select");
    (k.options || []).forEach(([v, l]) => {
      const o = document.createElement("option");
      o.value = v; o.textContent = l; input.appendChild(o);
    });
    input.value = String(val);
  } else if (k.type === "color") {
    input = document.createElement("input");
    input.type = "color"; input.value = String(val || "#000000");
  } else {
    input = document.createElement("input");
    input.type = "text"; input.value = val == null ? "" : String(val);
  }
  input.dataset.knob = k.name;
  row.appendChild(input);

  const out = document.createElement("span");
  out.className = "knob-val";
  const show = () => {
    out.textContent = k.type === "checkbox" ? (input.checked ? "on" : "off")
      : k.type === "text" ? "" : String(input.value).slice(0, 9);
  };
  show();
  const ev = (k.type === "range" || k.type === "color") ? "input" : "change";
  input.addEventListener(ev, () => {
    show();
    setKnob(k, k.type === "checkbox" ? input.checked : input.value);
  });
  if (k.type === "text") {
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") input.blur(); });
  }
  row.appendChild(out);
  return row;
}

function syncKnobs() {
  KNOBS.forEach((k) => {
    const el = document.querySelector('[data-knob="' + k.name + '"]');
    if (!el) return;
    const v = knobValue(k);
    if (k.type === "checkbox") el.checked = !!v;
    else el.value = v == null ? "" : String(v);
  });
}

// ===========================================================================
// STYLE SHEETS + PREFS (localStorage, per-user keys supplied by the caller)
//
// Styling only. Titles, captions, cell values and per-cell overrides are
// per-table content and deliberately excluded, mirroring the chart studio's
// spec-sheet rule.
// ===========================================================================
const SHEET_FIELDS = ["skin", "_theme_overrides", "row_bands",
                      "target_html_width", "row_height_scale",
                      "column_formats", "column_aligns", "column_color_modes",
                      "rag_thresholds", "highlight_columns", "signed_columns",
                      "heatmap_groups", "column_widths"];

function buildSheet() {
  const o = { schema_version: 1, name: "", created_at: new Date().toISOString() };
  SHEET_FIELDS.forEach((f) => { if (K[f] != null) o[f] = clone(K[f]); });
  return o;
}
function saveSheetAsNew() {
  const name = prompt("Name this style sheet:", "House table style");
  if (!name) return;
  const s = buildSheet(); s.name = name;
  sheets[name] = s; activeSheet = name;
  persistSheets(); refreshSheetSelect();
  toast("Saved style sheet " + JSON.stringify(name));
}
function applySheet(name) {
  const s = sheets[name];
  if (!s) { toast("No style sheet selected"); return; }
  pushUndo("apply style sheet");
  SHEET_FIELDS.forEach((f) => { if (s[f] != null) K[f] = clone(s[f]); });
  activeSheet = name;
  syncKnobs(); redraw("Applied " + JSON.stringify(name));
}
function deleteSheet(name) {
  if (!sheets[name]) return;
  delete sheets[name];
  if (activeSheet === name) activeSheet = "(none)";
  persistSheets(); refreshSheetSelect();
  toast("Deleted " + JSON.stringify(name));
}
function refreshSheetSelect() {
  const sel = document.getElementById("sheetSelect");
  if (!sel) return;
  sel.innerHTML = "";
  const none = document.createElement("option");
  none.value = "(none)"; none.textContent = "(none)"; sel.appendChild(none);
  Object.keys(sheets).forEach((n) => {
    const o = document.createElement("option");
    o.value = n; o.textContent = n; sel.appendChild(o);
  });
  sel.value = activeSheet;
}
function persistSheets() {
  try { localStorage.setItem(SHEETS_KEY, JSON.stringify(sheets)); } catch (e) {}
}
function loadSheets() {
  try {
    const raw = localStorage.getItem(SHEETS_KEY);
    if (raw) sheets = Object.assign({}, sheets, JSON.parse(raw));
  } catch (e) {}
}
function savePrefs() {
  try {
    const o = {}; SHEET_FIELDS.forEach((f) => { if (K[f] != null) o[f] = K[f]; });
    localStorage.setItem(PREF_KEY, JSON.stringify(o));
  } catch (e) {}
}

// ===========================================================================
// WIRING
// ===========================================================================
document.querySelectorAll(".tab-button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll(".tab-button").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    document.getElementById("pane-" + b.dataset.tab).classList.add("active");
    refreshTabs();
  };
});
document.getElementById("dataSearch").addEventListener("input", filterDataTab);
document.querySelectorAll("#pane-data [data-dl]").forEach((b) => {
  b.onclick = () => {
    const k = b.dataset.dl;
    if (k === "csv") download(FILENAME + ".csv", toDelimited(","), "text/csv");
    if (k === "tsv") download(FILENAME + ".tsv", toDelimited("\t"), "text/tab-separated-values");
    if (k === "json") download(FILENAME + ".json", toJSONRows(), "application/json");
  };
});
document.querySelectorAll("#pane-export [data-x]").forEach((b) => {
  b.onclick = () => {
    const k = b.dataset.x;
    if (k === "png1") downloadPNG(1);
    if (k === "png2") downloadPNG(2);
    if (k === "png4") downloadPNG(4);
    if (k === "call") download(FILENAME + "_make_table.py", generateCall(), "text/x-python");
    if (k === "datapy") download(FILENAME + "_data.py", generateDataCode(), "text/x-python");
    if (k === "csv") download(FILENAME + ".csv", toDelimited(","), "text/csv");
    if (k === "tsv") download(FILENAME + ".tsv", toDelimited("\t"), "text/tab-separated-values");
    if (k === "json") download(FILENAME + ".json", toJSONRows(), "application/json");
    if (k === "kwargs") download(FILENAME + "_kwargs.json", JSON.stringify(K, null, 2),
                                 "application/json");
    if (k === "model") download(FILENAME + "_model.json", JSON.stringify(M, null, 2),
                                "application/json");
    if (k === "sheet") download(FILENAME + "_style_sheet.json",
                                JSON.stringify(buildSheet(), null, 2), "application/json");
  };
});
document.getElementById("btnCopyCall").onclick = copyCall;
document.getElementById("btnDlCall").onclick = () =>
  download(FILENAME + "_make_table.py", generateCall(), "text/x-python");
document.getElementById("btnPng").onclick = () => downloadPNG(2);
document.getElementById("btnReset").onclick = () => {
  pushUndo("reset");
  K = clone(BASE_KWARGS); D = extractData(BASE_MODEL);
  selection = []; colSelection = [];
  syncKnobs(); redraw("Reset to the original make_table call");
};
document.getElementById("btnUndo").onclick = () => {
  const s = _undo.pop();
  if (!s) return;
  restoreSnapshot(s);
  syncUndoButton();
  syncKnobs(); redraw("Undid: " + s.label);
};
document.getElementById("btnFull").onclick = () => {
  document.body.classList.toggle("fullscreen");
  document.getElementById("btnFull").textContent =
    document.body.classList.contains("fullscreen") ? "Exit fullscreen" : "Fullscreen";
};
document.getElementById("btnFit").onclick = toggleTableFit;
document.getElementById("btnAdvanced").onclick = () => {
  const d = document.getElementById("knobsSection");
  d.open = !d.open;
  if (d.open) d.scrollIntoView({ behavior: "smooth", block: "start" });
};
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "z") {
    e.preventDefault(); document.getElementById("btnUndo").click();
  }
});

document.getElementById("hintLine").innerHTML =
  "Every control is reachable from the table itself. <b>Right-click</b> a cell "
  + "for colour, its value, and the row operations \u2014 insert, duplicate, "
  + "delete, move, sort, filter; a header for format / colour mode / alignment "
  + "and the column operations, including transpose; the background for theme "
  + "and size. <b>Shift-click</b> several "
  + "headers then right-click one to build a shared heatmap scale. "
  + "<b>Drag</b> across cells to select a range, a header edge to resize one "
  + "column, or the table's own right / bottom / corner handle to resize the "
  + "whole thing. <b>Double-click</b> a cell to change its value, or any other "
  + "text to retype it. Everything you change is "
  + "reflected in the Code tab as a runnable make_table(...) call.";

loadSheets();
buildKnobs();
installFrameGrips();
redraw();
installFitObserver();
</script>
</body>
</html>
"""


def _render_table_template(
    *,
    model_json: str,
    kwargs_json: str,
    title: str,
    filename: str,
    pref_key: str,
    sheets_key: str,
    sheets_json: str,
    active_sheet: str,
    table_id: str,
    png_path: str,
    df_name: str,
) -> str:
    """Token-substitute ``TABLE_HTML_TEMPLATE``.

    Mirrors ``chart_functions_studio._render_template``: a flat dict of
    ``__TOKEN__`` -> value, applied with ``str.replace``. No templating
    engine, no f-string over a document containing braces.
    """
    replacements = {
        "__MODEL_JSON__":          model_json,
        "__KWARGS_JSON__":         kwargs_json,
        "__KNOBS_JSON__":          json.dumps(TABLE_KNOBS),
        "__THEMES_JSON__":         json.dumps(TABLE_THEMES),
        "__PALETTES_JSON__":       json.dumps(TABLE_PALETTES),
        "__RAG_COLORS_JSON__":     json.dumps(RAG_COLORS),
        "__NUMBER_FORMATS_JSON__": json.dumps(NUMBER_FORMATS),
        "__DATE_FORMATS_JSON__":   json.dumps(DATE_FORMATS),
        "__COLOR_MODES_JSON__":    json.dumps(COLOR_MODES),
        "__HEATMAP_SCOPES_JSON__": json.dumps(HEATMAP_SCOPES),
        "__SWATCHES_JSON__":       json.dumps(SWATCHES),
        "__GROUP_ORDER_JSON__":    json.dumps(KNOB_GROUP_ORDER),
        "__SHEETS_JSON__":         sheets_json,
        "__ACTIVE_SHEET__":        _js_str(active_sheet),
        "__TITLE__":               _html_escape(title),
        "__FILENAME__":            _js_str(filename),
        "__PREF_KEY__":            _js_str(pref_key),
        "__SHEETS_KEY__":          _js_str(sheets_key),
        "__TABLE_ID__":            _js_str(table_id),
        "__PNG_PATH__":            _js_str(png_path or ""),
        "__DF_NAME__":             _js_str(df_name),
    }
    out = TABLE_HTML_TEMPLATE
    for token, value in replacements.items():
        out = out.replace(token, value)
    return out


def _html_escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _js_str(s: str) -> str:
    """Escape for a double-quoted JS string literal inside the template."""
    return (str(s).replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n").replace("</", "<\\/"))


# =============================================================================
# DATACLASSES -- mirrors of InteractiveResult / PrismInteractiveResult
# =============================================================================


@dataclass
class InteractiveTableResult:
    html: str
    html_path: Optional[str]
    table_id: str
    theme: str
    n_rows: int
    n_cols: int
    knob_names: List[str]


@dataclass
class PrismInteractiveTableResult:
    """Returned by ``wrap_table_interactive_prism``. Extends PRISM's
    ``TableResult`` the same way ``PrismInteractiveResult`` extends
    ``ChartResult`` -- the caller copies these onto the existing
    dataclass."""
    editor_html: str
    editor_html_path: Optional[str]
    editor_url: Optional[str]        # presigned URL, filled after S3 upload
    table_id: str
    theme: str
    n_rows: int
    n_cols: int
    knob_names: List[str]
    active_style_sheet: Optional[str]
    applied_style_sheet_id: Optional[str]


@dataclass
class TableStyleSheet:
    """User-owned bundle of table styling preferences.

    Styling only: formats, alignments, colour modes, thresholds, widths and
    the theme. Titles, captions, cell values and per-cell colour overrides
    are per-table content and never travel in a sheet.
    """
    style_sheet_id: str
    name: str
    base_theme: str = "gs_clean"
    overrides: Dict[str, Any] = field(default_factory=dict)
    scope: str = "global"
    description: str = ""
    owner: str = ""
    schema_version: int = 1
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TableStyleSheet":
        required = {"style_sheet_id", "name"}
        missing = required - set(d.keys())
        if missing:
            raise ValueError(f"Style sheet missing required fields: {missing}")
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# =============================================================================
# IDENTITY
# =============================================================================


def _compute_table_id(model: Dict[str, Any]) -> str:
    """Content-addressed id for a table, mirroring ``_compute_chart_id``.

    sha1 of the canonical model JSON, truncated to 12 hex chars. Re-emitting
    an identical table produces an identical id, which is what makes the
    manifest idempotent.
    """
    canonical = json.dumps(model, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(canonical).hexdigest()[:12]


# =============================================================================
# PERSISTENCE -- the S3 artifact family, shaped exactly like the chart one
# =============================================================================


def persist_editable_table(
    model: Dict[str, Any],
    kwargs: Dict[str, Any],
    *,
    png_path: str,
    session_path: str,
    s3_manager: Any,
    title: Optional[str],
    editor_html: Optional[str] = None,
    editor_name: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Write the reopen artifacts beside an emitted table PNG.

    Deliberately the same artifact family, key naming and manifest merge
    that ``chart_functions._persist_editable_spec`` writes for charts, so
    PRISM reads tables with the pattern it already knows::

        {session_path}/tables/{table_id}.table.json   model + kwargs
        {session_path}/tables/{table_id}.meta.json    studio open arguments
        {session_path}/tables/table_manifest.json     png_path -> table_id
        {session_path}/tables/{name}_editor.html      the studio (optional)

    ``table_id`` comes from ``_compute_table_id``, so an id resolved out of
    the manifest is the same id the studio derives from the same model.

    Returns ``{"table_id", "model_path", "editor_html_path"}``.
    """
    table_id = _compute_table_id(model)
    prefix = f"{session_path.rstrip('/')}/{TABLE_MODEL_PREFIX}"
    model_key = f"{prefix}/{table_id}.table.json"
    manifest_key = f"{prefix}/{TABLE_MANIFEST_NAME}"
    stamp = datetime.now(timezone.utc).isoformat()

    payload = {
        "schema_version": 1,
        "table_id": table_id,
        "model": model,
        "kwargs": kwargs,
    }

    editor_key: Optional[str] = None
    if editor_html is not None:
        name = editor_name or f"table_{table_id}"
        editor_key = f"{prefix}/{name}_editor.html"

    meta = {
        "schema_version": 1,
        "table_id": table_id,
        "artifact": "table",
        "title": title,
        "n_rows": len(model.get("rows", [])),
        "n_cols": len(model.get("columns", [])),
        "canvas": model.get("canvas"),
        "png_path": png_path,
        "model_path": model_key,
        "editor_html_path": editor_key,
        "created_at": stamp,
    }

    s3_manager.put(json.dumps(payload, default=str).encode("utf-8"), model_key)
    s3_manager.put(
        json.dumps(meta, indent=2, default=str).encode("utf-8"),
        f"{prefix}/{table_id}.meta.json",
    )
    if editor_key is not None:
        s3_manager.put(editor_html.encode("utf-8"), editor_key)

    try:
        manifest = json.loads(s3_manager.get(manifest_key).decode("utf-8"))
    except Exception:  # noqa: BLE001 - absent until the session's first table
        manifest = {"schema_version": 1, "tables": {}}
    manifest.setdefault("tables", {})[png_path] = table_id
    manifest["updated_at"] = stamp
    s3_manager.put(json.dumps(manifest, indent=2).encode("utf-8"), manifest_key)

    return {
        "table_id": table_id,
        "model_path": model_key,
        "editor_html_path": editor_key,
    }


# =============================================================================
# PUBLIC API -- GENERIC
# =============================================================================


def wrap_table_interactive(
    model: Dict[str, Any],
    kwargs: Optional[Dict[str, Any]] = None,
    *,
    theme: str = "gs_clean",
    title: Optional[str] = None,
    output_path: Optional[Union[str, Path]] = None,
    filename_base: Optional[str] = None,
    pref_key: Optional[str] = None,
    sheets_key: Optional[str] = None,
    style_sheets: Optional[Dict[str, Dict[str, Any]]] = None,
    active_style_sheet: Optional[str] = None,
    png_path: Optional[str] = None,
    df_name: str = "df",
) -> InteractiveTableResult:
    """Wrap a table cell model into a self-contained interactive editor.

    Parameters
    ----------
    model : dict
        Cell model from ``chart_functions._tbl_build_cell_model``.
    kwargs : dict, optional
        The originating ``make_table`` call, JSON-safe. Becomes the studio's
        live state and the basis of the regenerated Python in the Code tab.
    theme : str (default "gs_clean")
    title : str, optional (defaults to the model's own title)
    output_path : str | Path, optional (writes the HTML there)
    filename_base : str, optional (export filename prefix)
    pref_key / sheets_key : str, optional (localStorage keys)
    style_sheets : dict, optional (pre-loaded sheets for this session)
    active_style_sheet : str, optional
    png_path : str, optional (recorded in the Metadata tab)
    df_name : str (default "df") -- variable name used in generated Python
    """
    if theme not in TABLE_THEMES:
        raise ValueError(
            f"Unknown table theme '{theme}'. "
            f"Available: {', '.join(sorted(TABLE_THEMES.keys()))}"
        )
    if not isinstance(model, dict) or "rows" not in model or "columns" not in model:
        raise ValueError(
            "wrap_table_interactive() needs a cell model dict with 'rows' and "
            "'columns'. Build one with chart_functions._tbl_build_cell_model()."
        )

    kwargs = dict(kwargs or {})
    table_id = _compute_table_id(model)

    if title is None:
        lines = (model.get("title") or {}).get("lines") or []
        title = lines[0] if lines else f"Table Studio - {table_id}"

    if filename_base is None:
        filename_base = f"table_{table_id}"
    if pref_key is None:
        pref_key = "table_studio_prefs"
    if sheets_key is None:
        sheets_key = "table_studio_style_sheets"

    html = _render_table_template(
        model_json=json.dumps(model, default=str),
        kwargs_json=json.dumps(kwargs, default=str),
        title=title,
        filename=filename_base,
        pref_key=pref_key,
        sheets_key=sheets_key,
        sheets_json=json.dumps(style_sheets or {}),
        active_sheet=active_style_sheet or "(none)",
        table_id=table_id,
        png_path=png_path or "",
        df_name=df_name,
    )

    html_path: Optional[str] = None
    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
        html_path = str(p.resolve())

    return InteractiveTableResult(
        html=html, html_path=html_path, table_id=table_id, theme=theme,
        n_rows=len(model.get("rows", [])), n_cols=len(model.get("columns", [])),
        knob_names=[k["name"] for k in TABLE_KNOBS],
    )


# =============================================================================
# PUBLIC API -- PRISM BINDING
#
# Slots into make_table()'s interactive=True path exactly the way
# wrap_interactive_prism slots into make_chart()'s.
# =============================================================================


def wrap_table_interactive_prism(
    model: Dict[str, Any],
    kwargs: Optional[Dict[str, Any]] = None,
    *,
    user_id: Optional[str] = None,
    session_path: Optional[Union[str, Path]] = None,
    table_name: Optional[str] = None,
    save_as: Optional[str] = None,
    style_sheets: Optional[Dict[str, Dict[str, Any]]] = None,
    active_style_sheet: Optional[str] = None,
    png_path: Optional[str] = None,
    df_name: str = "df",
    write_local: bool = False,
) -> PrismInteractiveTableResult:
    """PRISM-facing wrapper. Maps ``make_table`` conventions onto
    ``wrap_table_interactive``.

    Parameters
    ----------
    model : dict
        Cell model produced by ``chart_functions._tbl_build_cell_model``.
    kwargs : dict
        The originating ``make_table`` call, JSON-safe.
    user_id : str, optional
        Scopes the localStorage keys so preferences isolate per user, the
        same convention ``wrap_interactive_prism`` uses.
    session_path : str | Path
        PRISM session folder. Names the editor
        ``{session_path}/tables/{table_name}_editor.html``.
    table_name : str, optional
        Base name for the saved HTML. Defaults to ``table_{table_id}``.
    save_as : str, optional
        Explicit path (PRISM convention: overrides ``table_name``).
    png_path : str, optional
        The emitted PNG this editor belongs to; surfaces in Metadata.
    df_name : str
        Variable name used by the regenerated Python.
    write_local : bool (default False)
        Write the HTML to the local filesystem. PRISM stores through the S3
        manager instead (see ``persist_editable_table``), so this stays off
        in production and is used by the dev harness.
    """
    kwargs = dict(kwargs or {})
    theme = kwargs.get("skin") or "gs_clean"
    if theme not in TABLE_THEMES:
        theme = "gs_clean"

    pref_key = f"table_studio_prefs_{user_id or 'anon'}"
    sheets_key = f"table_studio_sheets_{user_id or 'anon'}"

    table_id = _compute_table_id(model)
    name = table_name or f"table_{table_id}"

    html_path: Optional[Path] = None
    if write_local:
        if save_as:
            html_path = Path(save_as)
        elif session_path:
            html_path = Path(session_path) / TABLE_MODEL_PREFIX / f"{name}_editor.html"

    result = wrap_table_interactive(
        model=model,
        kwargs=kwargs,
        theme=theme,
        title=None,
        output_path=html_path,
        filename_base=name,
        pref_key=pref_key,
        sheets_key=sheets_key,
        style_sheets=style_sheets,
        active_style_sheet=active_style_sheet,
        png_path=png_path,
        df_name=df_name,
    )

    return PrismInteractiveTableResult(
        editor_html=result.html,
        editor_html_path=result.html_path,
        editor_url=None,  # populated by the caller after S3 upload
        table_id=result.table_id,
        theme=result.theme,
        n_rows=result.n_rows,
        n_cols=result.n_cols,
        knob_names=result.knob_names,
        active_style_sheet=active_style_sheet,
        applied_style_sheet_id=active_style_sheet,
    )


# =============================================================================
# SAMPLES + CLI
# =============================================================================


def _sample_model() -> Dict[str, Any]:
    """A hand-built cell model so the CLI demo runs with no pandas / PIL.

    Deliberately hand-built rather than produced through ``make_table``:
    this module must stay importable and demonstrable on its own, which is
    the whole point of it being a separate file.
    """
    cols = [
        ("Economy", "text", "left", None, 132),
        ("GDP YoY (%)", "num", "right", "pct_signed", 104),
        ("CPI YoY (%)", "num", "right", "pct", 100),
        ("Policy Rate (%)", "num", "right", "pct2", 122),
        ("3M Chg (bp)", "num", "right", "bp_signed", 104),
    ]
    data = [
        ("United States", 2.8, 3.1, 4.75, -75.0),
        ("Euro Area", 0.9, 2.4, 3.25, -60.0),
        ("United Kingdom", 1.1, 3.9, 4.50, -50.0),
        ("Japan", 0.7, 2.8, 0.50, 25.0),
        ("China", 4.9, 0.3, 3.10, -20.0),
        ("India", 6.8, 5.4, 6.50, 0.0),
    ]
    theme = {k: v for k, v in TABLE_THEMES["gs_clean"].items() if k != "label"}
    theme.update({
        "accent_color": "#C00000",
        "title_font_size": 22, "subtitle_font_size": 13,
        "header_font_size": 14, "body_font_size": 13, "caption_font_size": 11,
        "font_family": "Arial, Helvetica, sans-serif",
    })
    widths = [c[4] for c in cols]
    rows = []
    for r, rec in enumerate(data):
        cells = []
        for c, (name, kind, align, fmt, _w) in enumerate(cols):
            v = rec[c]
            cells.append({
                "c": c, "kind": "text", "raw": v,
                "text": str(v), "lines": [str(v)],
                "bg": None, "fg": "#000000", "indent": 0,
            })
        rows.append({"r": r, "h": 26, "kind": "normal", "group": None,
                     "row_bg": None, "cells": cells})
    return {
        "canvas": {"w": sum(widths) + 24, "h": 300},
        "theme": theme,
        "geom": {"table_x": 12, "table_w": sum(widths), "header_h": 23,
                 "group_band_h": 24, "col_widths": widths, "row_default_h": 25,
                 "body_top_y": 78},
        "title": {"lines": ["Global Macro Snapshot"],
                  "subtitle": ["Sample model shipped with the module"],
                  "caption": ["Source: chart_functions_studio_tables demo"]},
        "header_levels": [],
        "columns": [{"name": n, "kind": k, "align": a, "fmt": f,
                     "width": w, "wrap": False,
                     "numeric": k == "num", "minibar_src": None}
                    for (n, k, a, f, w) in cols],
        "rows": rows,
    }


def _sample_kwargs() -> Dict[str, Any]:
    return {
        "title": "Global Macro Snapshot",
        "subtitle": "Sample model shipped with the module",
        "caption": "Source: chart_functions_studio_tables demo",
        "column_formats": {"GDP YoY (%)": "pct_signed", "CPI YoY (%)": "pct",
                           "Policy Rate (%)": "pct2", "3M Chg (bp)": "bp_signed"},
        "column_color_modes": {"GDP YoY (%)": "rwg", "CPI YoY (%)": "bw"},
        "signed_columns": ["3M Chg (bp)"],
        "row_groups": [["Developed Markets", 4], ["Emerging Markets", 2]],
        "row_bands": True,
        "skin": "gs_clean",
        "target_html_width": 720,
    }


def _cmd_demo(args: argparse.Namespace) -> None:
    out = Path(args.output or "table_studio_demo.html")
    result = wrap_table_interactive(
        model=_sample_model(), kwargs=_sample_kwargs(),
        output_path=out, filename_base="table_studio_demo",
    )
    print(f"  table_id : {result.table_id}")
    print(f"  shape    : {result.n_rows} rows x {result.n_cols} cols")
    print(f"  bytes    : {len(result.html):,}")
    print(f"  written  : {result.html_path}")
    if args.open:
        webbrowser.open(f"file://{Path(result.html_path).resolve()}")


def _cmd_wrap(args: argparse.Namespace) -> None:
    payload = json.loads(Path(args.model).read_text(encoding="utf-8"))
    model = payload.get("model", payload)
    kwargs = payload.get("kwargs", {})
    out = Path(args.output or (Path(args.model).stem + "_editor.html"))
    result = wrap_table_interactive(model=model, kwargs=kwargs, output_path=out)
    print(f"  table_id : {result.table_id}")
    print(f"  written  : {result.html_path}")
    if args.open:
        webbrowser.open(f"file://{Path(result.html_path).resolve()}")


def _cmd_list(args: argparse.Namespace) -> None:
    what = args.what
    if what == "formats":
        print("\n  Number formats")
        for f in NUMBER_FORMATS:
            hint = f["hint"] or "(auto)"
            print(f"    {hint:<16} {f['label']}")
        print("\n  Date formats")
        for f in DATE_FORMATS:
            print(f"    {f['hint']:<16} {f['label']:<12} {f['strftime']}")
    elif what == "themes":
        print()
        for k, v in TABLE_THEMES.items():
            print(f"    {k:<12} {v['label']}")
    elif what == "knobs":
        print()
        for k in TABLE_KNOBS:
            kw = f"-> {k['kwarg']}" if k.get("kwarg") else ""
            print(f"    [{k['group']:<7}] {k['name']:<20} {k['type']:<9} {kw}")
    elif what == "modes":
        print()
        for c in COLOR_MODES:
            print(f"    {c['mode'] or '(none)':<12} {c['note']}")
    print()


def _cmd_info(args: argparse.Namespace) -> None:
    payload = json.loads(Path(args.model).read_text(encoding="utf-8"))
    model = payload.get("model", payload)
    print(f"  table_id  : {_compute_table_id(model)}")
    print(f"  rows      : {len(model.get('rows', []))}")
    print(f"  columns   : {len(model.get('columns', []))}")
    print(f"  canvas    : {model.get('canvas')}")
    print("  column kinds:")
    for c in model.get("columns", []):
        print(f"    {c['name']:<24} {c.get('kind'):<9} fmt={c.get('fmt')}")


def _menu() -> None:
    while True:
        print("\n" + "=" * 62)
        print(f"  chart_functions_studio_tables v{__version__}")
        print(f"  TABLE_STUDIO_ENABLED = {TABLE_STUDIO_ENABLED}")
        print("=" * 62)
        print("  1. Build the demo editor and open it")
        print("  2. Build the demo editor (no browser)")
        print("  3. List number / date formats")
        print("  4. List themes")
        print("  5. List knobs")
        print("  6. List colour modes")
        print("  7. Wrap a model JSON file")
        print("  q. Quit")
        choice = input("\n  > ").strip().lower()
        ns = argparse.Namespace(output=None, open=True, what=None, model=None)
        if choice == "1":
            _cmd_demo(ns)
        elif choice == "2":
            ns.open = False
            _cmd_demo(ns)
        elif choice in ("3", "4", "5", "6"):
            ns.what = {"3": "formats", "4": "themes",
                       "5": "knobs", "6": "modes"}[choice]
            _cmd_list(ns)
        elif choice == "7":
            path = input("  Path to model JSON: ").strip()
            if path:
                ns.model = path
                _cmd_wrap(ns)
        elif choice in ("q", "quit", "exit"):
            return
        else:
            print("  Unrecognised option.")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="chart_functions_studio_tables",
        description="Interactive HTML editor for PRISM static tables.")
    sub = ap.add_subparsers(dest="cmd")

    d = sub.add_parser("demo", help="Build a demo editor from the bundled model.")
    d.add_argument("-o", "--output")
    d.add_argument("--open", action="store_true")
    d.set_defaults(fn=_cmd_demo)

    w = sub.add_parser("wrap", help="Wrap a model JSON file into an editor.")
    w.add_argument("model")
    w.add_argument("-o", "--output")
    w.add_argument("--open", action="store_true")
    w.set_defaults(fn=_cmd_wrap)

    l = sub.add_parser("list", help="List formats / themes / knobs / modes.")
    l.add_argument("what", choices=["formats", "themes", "knobs", "modes"])
    l.set_defaults(fn=_cmd_list)

    i = sub.add_parser("info", help="Summarise a model JSON file.")
    i.add_argument("model")
    i.set_defaults(fn=_cmd_info)

    args = ap.parse_args()
    if not args.cmd:
        _menu()
        return
    args.fn(args)


if __name__ == "__main__":
    main()
