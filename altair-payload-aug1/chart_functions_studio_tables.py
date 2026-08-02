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

    ``kwargs`` is the ORIGINAL ``make_table`` call, JSON-safe. It is the
    studio's live state: every gesture mutates a kwarg, and the Code tab
    serialises those kwargs straight back to a runnable ``make_table(...)``
    call. Unlike the chart studio -- whose state is a mutated Vega-Lite
    spec with no inverse -- the round-trip here is an identity.

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
# PALETTES -- ported verbatim from chart_functions._TABLE_PALETTES
#
# Shipped into the template so the browser resolves colour scales with the
# same maths the engine used, which is what lets a colour-mode change apply
# live instead of round-tripping to Python.
# =============================================================================

TABLE_PALETTES: Dict[str, Dict[str, Any]] = {
    "bw":      {"kind": "sequential", "end": "#5C92CB", "max_i": 0.70},
    "wb":      {"kind": "sequential", "end": "#5C92CB", "max_i": 0.70},
    "wb_full": {"kind": "sequential", "end": "#003359", "max_i": 0.65},
    "wg":      {"kind": "sequential", "end": "#3C9A4E", "max_i": 0.65},
    "wr":      {"kind": "sequential", "end": "#C00000", "max_i": 0.55},
    "wo":      {"kind": "sequential", "end": "#E8A33D", "max_i": 0.65},
    "wgrey":   {"kind": "sequential", "end": "#5B5B5B", "max_i": 0.55},
    "rwg":     {"kind": "diverging", "neg": "#C00000", "pos": "#3C9A4E", "max_i": 0.65},
    "rwb":     {"kind": "diverging", "neg": "#C00000", "pos": "#003359", "max_i": 0.65},
    "bwr":     {"kind": "diverging", "neg": "#003359", "pos": "#C00000", "max_i": 0.65},
    "owb":     {"kind": "diverging", "neg": "#E8A33D", "pos": "#003359", "max_i": 0.65},
}

RAG_COLORS = {"red": "#F4D6D6", "amber": "#FCE9CC", "green": "#D8EED8"}


# =============================================================================
# THEMES
#
# ``gs_clean`` is byte-identical to chart_functions._TABLE_THEME. The other
# three exist because the chart studio has four and a table studio that
# offered one would look broken beside it. They are applied browser-side and
# serialise into the regenerated call as ``skin=``.
# =============================================================================

TABLE_THEMES: Dict[str, Dict[str, Any]] = {
    "gs_clean": {
        "label": "GS Clean",
        "primary_color": "#003359", "secondary_color": "#94C7DD",
        "background_color": "#FFFFFF", "row_band_color": "#F7F7F7",
        "subtotal_band": "#EFEFEF", "total_band": "#003359",
        "border_color": "#1F1F1F", "muted_text": "#5B5B5B",
        "header_text": "#FFFFFF", "body_text": "#000000",
        "positive_text": "#0E7A28", "negative_text": "#C00000",
        "highlight_color": "#E8F0F7",
    },
    "mono": {
        "label": "Monochrome",
        "primary_color": "#1F1F1F", "secondary_color": "#5B5B5B",
        "background_color": "#FFFFFF", "row_band_color": "#F4F4F4",
        "subtotal_band": "#E8E8E8", "total_band": "#1F1F1F",
        "border_color": "#1F1F1F", "muted_text": "#5B5B5B",
        "header_text": "#FFFFFF", "body_text": "#000000",
        "positive_text": "#1F1F1F", "negative_text": "#1F1F1F",
        "highlight_color": "#EDEDED",
    },
    "print": {
        "label": "Print",
        "primary_color": "#000000", "secondary_color": "#444444",
        "background_color": "#FFFFFF", "row_band_color": "#FFFFFF",
        "subtotal_band": "#F2F2F2", "total_band": "#000000",
        "border_color": "#000000", "muted_text": "#333333",
        "header_text": "#FFFFFF", "body_text": "#000000",
        "positive_text": "#000000", "negative_text": "#000000",
        "highlight_color": "#F2F2F2",
    },
    "slate": {
        "label": "Slate",
        "primary_color": "#22303C", "secondary_color": "#4A6274",
        "background_color": "#FFFFFF", "row_band_color": "#F5F7F9",
        "subtotal_band": "#E9EEF2", "total_band": "#22303C",
        "border_color": "#22303C", "muted_text": "#5A6B79",
        "header_text": "#FFFFFF", "body_text": "#12181F",
        "positive_text": "#0E7A28", "negative_text": "#B3261E",
        "highlight_color": "#EAF1F7",
    },
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
  <b>double-click</b> to retype &middot; <b>drag</b> the table's edge or a
  header edge to resize</p>

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
//   K -- the make_table kwargs. THIS is the studio's state; every gesture
//        writes here and the Code tab serialises it straight back to Python.
//   M -- the cell model. Derived: rebuilt from K + the raw values on
//        every change.
// ===========================================================================
const clone = (o) => JSON.parse(JSON.stringify(o));

let K = clone(BASE_KWARGS);
let M = clone(BASE_MODEL);
const RAW_W = BASE_MODEL.geom.col_widths.slice();
const BASE_THEME = clone(BASE_MODEL.theme);
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
function pushUndo(label) {
  const entry = { K: clone(K), label: label || "edit" };
  _undo.push(entry);
  if (_undo.length > 60) _undo.shift();
  syncUndoButton();
  return entry;
}

// ===========================================================================
// COLOUR MATHS -- ports of chart_functions._tbl_* so a colour-mode change
// resolves live instead of needing a Python round-trip.
// ===========================================================================
function hex2rgb(h) {
  h = String(h || "#000000").replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16),
          parseInt(h.slice(4, 6), 16)];
}
function rgb2hex(r, g, b) {
  const c = (n) => Math.max(0, Math.min(255, Math.round(n)))
                     .toString(16).padStart(2, "0").toUpperCase();
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

  // A column is pristine while nothing that could change where its text
  // breaks has moved. While it is, the engine's own wrapped lines are used
  // verbatim rather than being re-measured in the browser.
  const fontPristine = bodyFs === BASE_THEME.body_font_size;
  const pristine = (ci) => fontPristine
    && M.columns[ci].fmt === M.columns[ci].fmt0
    && !((K.column_widths || {})[M.columns[ci].name]);

  // --- widths ---
  M.geom.col_widths = M.columns.map((col, ci) =>
    (K.column_widths || {})[col.name] || RAW_W[ci]);

  // --- per-column derived config ---
  M.columns.forEach((col, ci) => {
    col.fmt   = (K.column_formats || {})[col.name] ?? col.fmt0 ?? null;
    col.align = (K.column_aligns  || {})[col.name] || col.align0;
    col.width = M.geom.col_widths[ci];
  });

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
      const w = td.querySelector(".cw"); if (!w) return;
      const ln = w.querySelector(".ln"); if (!ln) return;
      beginEdit(ln, (txt) => {
        pushUndo("cell text");
        K.value_overrides = K.value_overrides || {};
        K.value_overrides[ck(r, c)] = txt;
        redraw("value_overrides[" + r + ", " + JSON.stringify(M.columns[c].name) + "]");
      });
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
      K = _undo.pop().K;
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

function renameColumn(oldName, newName) {
  const ci = colByName(oldName);
  if (ci >= 0) M.columns[ci].name = newName;
  const remap = (obj) => {
    if (!obj || !(oldName in obj)) return obj;
    obj[newName] = obj[oldName]; delete obj[oldName]; return obj;
  };
  ["column_formats", "column_aligns", "column_color_modes", "rag_thresholds",
   "column_widths", "minibar_columns"].forEach((k) => { if (K[k]) remap(K[k]); });
  ["highlight_columns", "signed_columns"].forEach((k) => {
    if (K[k]) K[k] = K[k].map((n) => (n === oldName ? newName : n));
  });
  (K.heatmap_groups || []).forEach((g) => {
    g.columns = (g.columns || []).map((n) => (n === oldName ? newName : n));
  });
  K.column_renames = K.column_renames || {};
  K.column_renames[oldName] = newName;
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
    mRow(m, "Edit this value\u2026", "double-click", () => {
      const td = document.querySelector('#ptTable td[data-r="' + r + '"][data-c="' + c + '"]');
      const ln = td && td.querySelector(".ln");
      if (ln) beginEdit(ln, (txt) => {
        pushUndo("cell text");
        K.value_overrides = K.value_overrides || {};
        K.value_overrides[ck(r, c)] = txt;
        redraw("value_overrides set");
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
        if (hasBar) delete K.minibar_columns[col.name];
        else K.minibar_columns[col.name] = col.name;
        M.rows.forEach((row) => {
          const cell = row.cells[ci];
          if (hasBar) { cell.kind = "text"; cell.bar = null; }
          else {
            const pool = columnNumbers(ci);
            const mx = pool.length ? Math.max(...pool.map(Math.abs)) : 0;
            cell.kind = "minibar";
            cell.bar = { v: typeof cell.raw === "number" ? cell.raw : 0, max: mx };
          }
        });
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
    mRow(m, "Reset width to engine default", String(RAW_W[ci]) + "px", () => {
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

  const renames = K.column_renames || {};
  if (Object.keys(renames).length) {
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

function generateDataCode() {
  const cols = M.columns.map((c) => c.name);
  const L = ["import pandas as pd", "", DF_NAME + " = pd.DataFrame({"];
  cols.forEach((name, ci) => {
    const isInt = M.columns[ci].int_dtype;
    const vals = M.rows.map((row) => {
      const raw = row.cells[ci] ? row.cells[ci].raw : null;
      if (raw == null) return "None";
      if (typeof raw === "object" && raw.__date__)
        return '"' + raw.__date__.slice(0, 10) + '"';
      // Whole floats stringify without their decimal point, which would
      // rebuild a float column as an int one.
      if (typeof raw === "number")
        return (!isInt && Number.isInteger(raw)) ? raw.toFixed(1) : String(raw);
      return '"' + String(raw).replace(/"/g, '\\"') + '"';
    });
    L.push("    " + pyLit(name) + ": [" + vals.join(", ") + "],");
  });
  L.push("})");
  const dateCols = M.columns.filter((c) => c.kind === "date").map((c) => c.name);
  dateCols.forEach((n) => {
    L.push(DF_NAME + "[" + pyLit(n) + "] = pd.to_datetime(" + DF_NAME + "[" + pyLit(n) + "])");
  });
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
  K = clone(BASE_KWARGS); M = clone(BASE_MODEL);
  selection = []; colSelection = [];
  syncKnobs(); redraw("Reset to the original make_table call");
};
document.getElementById("btnUndo").onclick = () => {
  const s = _undo.pop();
  if (!s) return;
  K = s.K;
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
  + "for background and text colour, a header for format / colour mode / "
  + "alignment, the background for theme and size. <b>Shift-click</b> several "
  + "headers then right-click one to build a shared heatmap scale. "
  + "<b>Drag</b> across cells to select a range, a header edge to resize one "
  + "column, or the table's own right / bottom / corner handle to resize the "
  + "whole thing. <b>Double-click</b> any text to retype it. Everything you change is "
  + "reflected in the Code tab as a runnable make_table(...) call.";

// Snapshot what the engine itself decided, on both the live model and the
// reset baseline. Two purposes: a cleared override falls back to make_table's
// own choice rather than to nothing, and an untouched cell keeps the exact
// text, line breaks and row height PIL produced instead of being re-measured
// with whatever font the browser happens to have.
[M, BASE_MODEL].forEach((model) => {
  model.columns.forEach((c) => { c.fmt0 = c.fmt; c.align0 = c.align; });
  model.rows.forEach((row) => {
    row.h0 = row.h;
    row.cells.forEach((cell) => {
      cell.text0 = cell.text;
      cell.lines0 = cell.lines;
    });
  });
});

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
