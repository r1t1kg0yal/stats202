#!/usr/bin/env python3
"""
echart_studio -- self-contained ECharts producer + single-chart editor.

PRODUCES ECharts "option" JSON from PRISM-style DataFrame + chart_type +
mapping inputs. Optionally wraps the option into a single-file interactive
HTML editor (knob cards, spec sheets, raw-JSON escape hatch).

Design rules:
    * This module uses stdlib + pandas for DataFrame input; the installed
      ``dashboards`` package also requires numpy in compiler/runtime paths.
    * Emitted HTML inlines echarts.js (read once at render time from
      `web/backend_django/news/static/js/echarts.js`; the retained legacy
      `mysite/news/static/js/echarts.js` candidate is absent from the
      2026-07-11 production checkout; see
      `dashboards/rendering.py::_get_echarts_js`)
      so the dashboard is self-contained when downloaded,
      attached to email, or served from S3 via a presigned URL.
    * No fallbacks. Unknown theme/palette/preset/chart_type raises ValueError.
    * Zero dependency on chart_studio, chart_functions, or Altair.

Library usage
-------------

    
    r = make_echart(
        df=df,
        chart_type="sankey",
        mapping={"source": "src", "target": "tgt", "value": "v"},
        title="Trade flows", theme="gs_clean", dimensions="wide",
        session_path=SP, chart_name="trade_flows",
    )
    # r.option, r.json_path, r.html_path, r.chart_id

CLI usage
---------

    python echart_studio.py                      # interactive menu
    python echart_studio.py wrap spec.json --open
    python echart_studio.py demo --matrix
    python echart_studio.py list types|themes|palettes|dimensions|knobs
    python echart_studio.py info spec.json
    python echart_studio.py test
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from config import (
    THEMES, PALETTES, DIMENSION_PRESETS, TYPOGRAPHY_OVERRIDES,
    get_theme, list_themes, resolve_theme,
    get_palette, list_palettes, palette_colors,
    get_dimension_preset, get_typography_override, list_dimensions,
    MAX_DASHBOARD_DECIMALS, clamp_decimals,
)
from rendering import render_editor_html


__version__ = "0.1.0"

# =============================================================================
# BUILDER CONTEXT + PER-TYPE BUILDERS
# =============================================================================

@dataclass
class BuilderContext:
    """Collected context passed to each chart builder."""
    chart_type: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    theme_name: str = "gs_clean"
    theme_colors: List[str] = field(default_factory=list)
    palette_name: str = "gs_primary"
    palette_colors: List[str] = field(default_factory=list)
    palette_kind: str = "categorical"
    dimension_preset: str = "wide"
    width: int = 700
    height: int = 350
    typography: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

def _df_or_none(df):
    if df is None:
        return None
    try:
        import pandas as pd
        if isinstance(df, pd.DataFrame):
            return df
    except Exception:
        pass
    return None


def _format_datetime_series(ser):
    """Convert a datetime64 Series to ISO-8601 strings, preserving sub-day
    component only when it carries information.

    Output formats (matched to what live PRISM emits and what ECharts
    parses on the JS side via ``Date.parse``):

      * date-only (every value is calendar-day-aligned)  -> ``"%Y-%m-%d"``
      * sub-day, tz-naive                                -> ``"%Y-%m-%d %H:%M:%S"``
      * sub-day, tz-aware                                -> ISO with colon-tz,
                                                            second-precision
                                                            e.g. ``"2026-04-27 06:38:00-04:00"``

    Sub-second precision is always stripped before emission. ECharts'
    time-axis renders unaligned-tick labels with ``{HH}:{mm}:{ss} {SSS}``
    granularity, so a stray microsecond on the leftmost data point
    pollutes the axis with ``"03:16:08 892"``-style labels at the
    boundary. Strip ms/ns at the formatter so this never reaches the
    DOM.

    "As-of" stamps are coerced to date-only. When every row in the
    series shares an identical (hour, minute, second, microsecond,
    nanosecond) tuple, the time component is decorative -- typical
    examples: EOD data tagged at 16:00 NY close, daily Haver pulls
    timestamped at the pull moment. Such a stamp produces no
    chart-relevant signal but does cause ECharts to surface
    ``"16:00:00"`` at the axis boundaries because the data points
    don't fall on midnight tick lines. Treating these as date-only
    fixes the label without changing the data's economic meaning.

    NaT values are emitted as ``None`` (so JSON serialization keeps
    them out of the data; the chart code's existing
    ``isNaN(d.getTime())`` checks handle them).

    The asymmetry vs ``%z`` (no colon) is deliberate -- PRISM live
    manifests use the colon form, and matching it keeps staging /
    PRISM byte-identical on this surface."""
    import pandas as pd
    if not pd.api.types.is_datetime64_any_dtype(ser):
        return ser
    valid = ser.dropna()
    if len(valid) == 0:
        return ser.dt.strftime("%Y-%m-%d")
    has_sub_day = bool(((valid.dt.hour != 0)
                          | (valid.dt.minute != 0)
                          | (valid.dt.second != 0)
                          | (valid.dt.microsecond != 0)
                          | (valid.dt.nanosecond != 0)).any())
    if not has_sub_day:
        return ser.dt.strftime("%Y-%m-%d")
    # As-of-stamp coercion: if every row shares the exact same sub-day
    # component, the time is decorative. Drop it so ECharts renders
    # clean date labels.
    h, m, s = valid.dt.hour, valid.dt.minute, valid.dt.second
    us, ns = valid.dt.microsecond, valid.dt.nanosecond
    if (h.nunique() == 1 and m.nunique() == 1 and s.nunique() == 1
            and us.nunique() == 1 and ns.nunique() == 1):
        return ser.dt.strftime("%Y-%m-%d")
    # Real sub-day variation: emit second-precision strings. Strip
    # microsecond / nanosecond precision so ECharts axis labels never
    # surface ".892"-style millisecond tails on the boundary tick.
    truncated = ser.dt.floor("s")
    if ser.dt.tz is not None:
        return truncated.apply(
            lambda x: None if pd.isna(x) else x.isoformat(sep=' '))
    return truncated.dt.strftime("%Y-%m-%d %H:%M:%S")


def _format_datetime_value(v):
    """Per-value version of ``_format_datetime_series``. Returns the
    input unchanged when it isn't a ``pd.Timestamp``; returns ``None``
    on NaT.

    Sub-second precision is always stripped before emission (see
    :func:`_format_datetime_series` for rationale). The "as-of stamp
    everywhere" coercion can't apply at the per-value level (no peer
    rows to compare), so this function preserves a non-midnight time
    component as long as it survives ``floor('s')``."""
    import pandas as pd
    if not isinstance(v, pd.Timestamp):
        return v
    if pd.isna(v):
        return None
    has_sub_day = bool(v.hour or v.minute or v.second
                          or v.microsecond or v.nanosecond)
    if not has_sub_day:
        return v.strftime("%Y-%m-%d")
    truncated = v.floor("s")
    if truncated.tz is not None:
        return truncated.isoformat(sep=' ')
    return truncated.strftime("%Y-%m-%d %H:%M:%S")


def _rows(df, cols: Sequence[str]) -> List[List[Any]]:
    """Return df[cols].values as a list of plain Python rows."""
    import pandas as pd
    sub = df[list(cols)].copy()
    for c in cols:
        if pd.api.types.is_datetime64_any_dtype(sub[c]):
            sub[c] = _format_datetime_series(sub[c])
    rows = []
    for _, r in sub.iterrows():
        row = []
        for v in r:
            if v is None or (isinstance(v, float) and v != v):
                row.append(None)
            else:
                row.append(v.item() if hasattr(v, "item") else v)
        rows.append(row)
    return rows


def _unique(values: Sequence[Any]) -> List[Any]:
    seen = []
    out = []
    for v in values:
        if v in seen:
            continue
        seen.append(v)
        out.append(v)
    return out


def _ensure_columns(df, cols: Sequence[str], builder: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"{builder}: mapping references columns not present in df: {missing}. "
            f"Available: {list(df.columns)}"
        )


def _col_to_list(df, col: str) -> List[Any]:
    import pandas as pd
    ser = df[col]
    if pd.api.types.is_datetime64_any_dtype(ser):
        ser = _format_datetime_series(ser)
    out = []
    for v in ser:
        if v is None or (isinstance(v, float) and v != v):
            out.append(None)
        else:
            out.append(v.item() if hasattr(v, "item") else v)
    return out


# ---------------------------------------------------------------------------
# Shared scaffolding
# ---------------------------------------------------------------------------

def _base_option(ctx: BuilderContext) -> Dict[str, Any]:
    """Return the shared base option with title/tooltip/grid/legend scaffolding."""
    opt: Dict[str, Any] = {
        "title": {
            "text": ctx.title or "",
            "subtext": ctx.subtitle or "",
            "left": "left",
        },
        "tooltip": {"show": True, "trigger": "axis",
                     "axisPointer": {"type": "cross"}},
        # Row layout at the top of the frame:
        #   Row 1 (y=0..30):   title (left) + subtitle + toolbox (right)
        #   Row 2 (y=40..~60): legend (right-aligned, full width)
        #   Grid starts at y=80
        # Keeping the legend on its own row avoids every width-dependent
        # collision with either the title or the toolbox.
        # Legend type: "plain" (wrap to multiple rows) instead of
        # "scroll" (paginate with arrows) -- the prior "scroll"
        # default silently hid 2/3 of series in static-render
        # contexts (CC4 in the 2026-05-11 audit). The grid.top is
        # auto-bumped by `_grow_grid_for_legend()` when legend wraps.
        "legend": {"show": True, "top": 42, "right": 10,
                    "orient": "horizontal", "type": "plain"},
        "grid": {"top": 80, "right": 20, "bottom": 84, "left": 76,
                  "containLabel": True},
        "toolbox": {
            "show": True,
            "top": 8,
            "right": 10,
            "itemSize": 14,
            "itemGap": 8,
            "feature": {
                "saveAsImage": {"show": True, "title": "Save"},
                "dataZoom": {"show": True, "title": {"zoom": "Zoom", "back": "Reset zoom"}},
                "restore": {"show": True, "title": "Restore"},
            },
        },
        "animation": True,
        "animationDuration": 600,
    }
    if ctx.palette_colors and ctx.palette_kind == "categorical":
        opt["color"] = list(ctx.palette_colors)
    if ctx.typography.get("titleSize") is not None:
        opt["title"].setdefault("textStyle", {})["fontSize"] = ctx.typography["titleSize"]
    if ctx.typography.get("labelSize") is not None:
        opt["textStyle"] = {"fontSize": ctx.typography["labelSize"]}
    return opt


def _apply_typography_to_axes(opt: Dict[str, Any], ctx: BuilderContext):
    ts = ctx.typography
    if not ts:
        return
    for axis_key in ("xAxis", "yAxis"):
        axes = opt.get(axis_key)
        if axes is None:
            continue
        if isinstance(axes, dict):
            axes = [axes]
            opt[axis_key] = axes
        for ax in axes:
            al = ax.setdefault("axisLabel", {})
            if ts.get("labelSize") is not None:
                al["fontSize"] = ts["labelSize"]
            nt = ax.setdefault("nameTextStyle", {})
            if ts.get("axisTitleSize") is not None:
                nt["fontSize"] = ts["axisTitleSize"]


# JS body for the default value-axis tick-label formatter. Mirrors
# ECharts' "nice" default (no thousands separators on integers,
# trailing zeros stripped on decimals) but caps fractional digits at
# ``MAX_DASHBOARD_DECIMALS`` so a tightly-zoomed value axis can never
# render a tick like "0.001234". Generated with a Python f-string so the
# cap is single-source-of-truth (config.MAX_DASHBOARD_DECIMALS).
_DEFAULT_VALUE_AXIS_FORMATTER_JS: str = (
    "function(v){"
    "  if (v == null) return '';"
    "  var n = +v;"
    "  if (isNaN(n)) return String(v);"
    "  var a = Math.abs(n);"
    "  if (a === 0) return '0';"
    f" if (a >= 1 && Math.round(n) === n) return n.toString();"
    f" var s = n.toFixed({MAX_DASHBOARD_DECIMALS});"
    "  if (s.indexOf('.') >= 0) {"
    "    s = s.replace(/0+$/, '').replace(/\\.$/, '');"
    "  }"
    "  return s;"
    "}"
)


def _install_default_axis_decimal_cap(opt: Dict[str, Any]) -> None:
    """Install a default ``axisLabel.formatter`` on every value/log axis
    that doesn't already have one, capping rendered tick precision at
    ``MAX_DASHBOARD_DECIMALS``.

    Idempotent: if a builder, preset, or user-supplied option already
    set an ``axisLabel.formatter``, we leave it alone -- the assumption
    is the explicit formatter knows what it's doing (and the JS-runtime
    layer caps any user-supplied ``decimals``-style options through
    ``__capDec`` regardless). Category axes never need the cap because
    they don't render numeric ticks.

    This is called once per chart at the tail of ``make_echart`` and
    once per chart-widget after dashboards' ``_apply_post_build_polish``
    so dashboards inherit the cap as well.
    """
    for axis_key in ("xAxis", "yAxis"):
        axes = opt.get(axis_key)
        if axes is None:
            continue
        if isinstance(axes, dict):
            axis_list = [axes]
        elif isinstance(axes, list):
            axis_list = axes
        else:
            continue
        for ax in axis_list:
            if not isinstance(ax, dict):
                continue
            ax_type = ax.get("type")
            if ax_type not in ("value", "log"):
                continue
            label = ax.get("axisLabel")
            if not isinstance(label, dict):
                label = {}
                ax["axisLabel"] = label
            if "formatter" in label and label.get("formatter") not in (
                None, "", False,
            ):
                continue
            label["formatter"] = _DEFAULT_VALUE_AXIS_FORMATTER_JS


# JS body for the default tooltip ``valueFormatter``. Mirrors the value-
# axis tick formatter above so a crosshair / axis-trigger tooltip cannot
# render a number to more than ``MAX_DASHBOARD_DECIMALS`` digits. ECharts
# calls ``valueFormatter`` per-value when no per-tooltip ``formatter`` is
# set; if a chart type installs its own ``tooltip.formatter`` (custom HTML
# template), ECharts ignores ``valueFormatter`` and the formatter's own
# ``toFixed(...)`` literals (which are also bounded by the cap, see
# ``rendering.py``'s ``__capDec``) take over.
_DEFAULT_TOOLTIP_VALUE_FORMATTER_JS: str = (
    "function(v){"
    "  if (v == null) return '';"
    "  if (typeof v === 'string') return v;"
    "  if (Array.isArray(v)) {"
    "    return v.map(function(x){"
    "      if (x == null) return '';"
    "      var nx = +x;"
    "      if (isNaN(nx)) return String(x);"
    "      var sx = nx.toFixed(" + str(MAX_DASHBOARD_DECIMALS) + ");"
    "      if (sx.indexOf('.') >= 0) {"
    "        sx = sx.replace(/0+$/, '').replace(/\\.$/, '');"
    "      }"
    "      return sx;"
    "    }).join(', ');"
    "  }"
    "  var n = +v;"
    "  if (isNaN(n)) return String(v);"
    "  var s = n.toFixed(" + str(MAX_DASHBOARD_DECIMALS) + ");"
    "  if (s.indexOf('.') >= 0) {"
    "    s = s.replace(/0+$/, '').replace(/\\.$/, '');"
    "  }"
    "  return s;"
    "}"
)


def _install_default_tooltip_decimal_cap(opt: Dict[str, Any]) -> None:
    """Install a default tooltip ``valueFormatter`` capping rendered
    numeric precision at ``MAX_DASHBOARD_DECIMALS``.

    Idempotent and conservative:

    * Skips if ``opt.tooltip`` is missing, falsy, or not a dict.
    * Skips if a custom ``tooltip.formatter`` (string or function) is
      already set -- those write the entire tooltip HTML themselves,
      and any ``toFixed`` literals inside them are already bounded by
      the cap (every ``toFixed`` literal authored on the Python side
      uses 0/1/2 explicitly).
    * Skips if a custom ``tooltip.valueFormatter`` is already set --
      the caller chose its own per-value formatter (see e.g. the
      ``tooltip.decimals`` sugar in ``echart_dashboard._lower_chart_widget``
      and the runtime transform formatter in ``rendering.py``).

    Otherwise installs the default formatter that:

    * Returns strings unchanged (ECharts sometimes hands the formatter
      a category name).
    * Maps numeric arrays element-wise (scatter/heatmap raw values).
    * Caps decimals at the global cap and strips trailing zeros so a
      whole number renders as ``"4"`` not ``"4.00"``.

    Called once per chart at the tail of ``make_echart`` (after annotations
    + axis-cap pass), and once per chart-widget at the tail of
    ``echart_dashboard._lower_chart_widget``, so dashboards inherit the
    cap as well. The runtime mirror in ``rendering.py``'s
    ``materializeOption`` re-applies the same guard at render time so a
    spec hand-edited in the editor or coming through a non-standard path
    still cannot leak raw 12-digit floats into the tooltip.
    """
    tt = opt.get("tooltip")
    if not isinstance(tt, dict):
        return
    fmt = tt.get("formatter")
    if fmt not in (None, "", False):
        return
    vfmt = tt.get("valueFormatter")
    if vfmt not in (None, "", False):
        return
    tt["valueFormatter"] = _DEFAULT_TOOLTIP_VALUE_FORMATTER_JS


# ---------------------------------------------------------------------------
# Axis title / sort / dash helpers (used by multiple XY builders)
# ---------------------------------------------------------------------------

# Approximate average pixel width of a single character at a given font
# size for the GS Sans / Helvetica stack. 0.62 of font_size is a
# conservative middle ground for proportional fonts: digits are
# narrower (~0.55), uppercase wider (~0.7), mixed-case prose averages
# 0.6-0.65. Used purely for layout pre-sizing; ECharts still measures
# at render time, so an over-estimate just means a touch more padding.
_CHAR_W_RATIO = 0.62

# Default cap for category-axis labels on the LEFT (yAxis horizontal
# bar / bullet) or BOTTOM (xAxis with very long category names). Beyond
# this, labels are truncated with an ellipsis so the chart stays
# readable. Override via ``mapping.category_label_max_px``.
_CATEGORY_LABEL_CAP_PX = 220

# Pixel cost of the rotated axis title's bounding box (font_size + a
# couple px for stroke). Empirically ECharts allocates roughly the
# font size plus ~6px slack for a rotated nameTextStyle.
_ROTATED_TITLE_THICKNESS_PX = 18

# Padding (px) between the longest tick label and the axis title.
_TITLE_LABEL_PADDING_PX = 8


def _estimate_text_px(s: Any, font_size: int = 12) -> int:
    """Rough pixel-width estimate for a text label at the given font size.

    Used to size grid margins / nameGap so axis titles never overlap
    long tick labels. Overestimates slightly (we'd rather pad than
    clip), and returns 0 for empty input.
    """
    if s is None:
        return 0
    text = str(s)
    if not text:
        return 0
    return int(round(len(text) * font_size * _CHAR_W_RATIO))


def _label_font_size(opt: Dict[str, Any], axis_key: str = "yAxis",
                      default: int = 12) -> int:
    """Resolve the effective axisLabel.fontSize for an axis. Falls back
    to opt.textStyle.fontSize and finally `default`. Lists pick element 0."""
    ax = opt.get(axis_key)
    if isinstance(ax, list):
        ax = ax[0] if ax else None
    if isinstance(ax, dict):
        al = ax.get("axisLabel") or {}
        fs = al.get("fontSize")
        if isinstance(fs, (int, float)) and fs > 0:
            return int(fs)
    ts = opt.get("textStyle") or {}
    fs = ts.get("fontSize")
    if isinstance(fs, (int, float)) and fs > 0:
        return int(fs)
    return default


def _layout_long_category_axis(
    opt: Dict[str, Any],
    axis_key: str,
    *,
    cap_px: int = _CATEGORY_LABEL_CAP_PX,
    truncate: bool = True,
) -> int:
    """Estimate the longest category label on `axis_key`, optionally
    apply ECharts label truncation at `cap_px`, and return the effective
    label-region width in pixels. Returns 0 when the axis is missing,
    not categorical, or has no `data`.

    Truncation is applied as ``axisLabel.width`` + ``overflow: 'truncate'``
    so over-long labels render as ``"long la..."`` while the tooltip /
    underlying value remain intact.
    """
    ax = opt.get(axis_key)
    if isinstance(ax, list):
        ax = ax[0] if ax else None
    if not isinstance(ax, dict):
        return 0
    if ax.get("type") != "category":
        return 0
    data = ax.get("data") or []
    if not data:
        return 0
    font_size = _label_font_size(opt, axis_key)
    raw_max = max(_estimate_text_px(v, font_size) for v in data)
    if truncate and raw_max > cap_px:
        al = ax.setdefault("axisLabel", {})
        al.setdefault("width", cap_px)
        al.setdefault("overflow", "truncate")
        al.setdefault("ellipsis", "...")
        return cap_px
    return raw_max


def _x_category_density_overflow(
    opt: Dict[str, Any], inner_width_px: int
) -> bool:
    """Return True when a horizontal category axis has more total label
    width than fits in the inner plot width (i.e. ECharts will silently
    drop labels via the default `interval: 'auto'`)."""
    ax = opt.get("xAxis")
    if isinstance(ax, list):
        ax = ax[0] if ax else None
    if not isinstance(ax, dict):
        return False
    if ax.get("type") != "category":
        return False
    data = ax.get("data") or []
    if len(data) < 2:
        return False
    font_size = _label_font_size(opt, "xAxis")
    total = sum(_estimate_text_px(v, font_size) + 12 for v in data)
    return total > max(inner_width_px, 1)


_TEMPORAL_CATEGORY_LABEL_RE = re.compile(
    r"^\d{4}(?:[-/]\d{2}(?:[-/]\d{2})?)?"
    r"(?:[ T]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?)?$"
)


def _looks_like_temporal_category_labels(data: Sequence[Any]) -> bool:
    """Return True when at least 80% of category labels are ISO-like dates."""
    labels = [
        str(value).strip()
        for value in data
        if value is not None and str(value).strip()
    ]
    if len(labels) < 2:
        return False
    matches = sum(
        bool(_TEMPORAL_CATEGORY_LABEL_RE.fullmatch(label))
        for label in labels
    )
    return matches / len(labels) >= 0.8


def _autorotate_x_category_labels(opt: Dict[str, Any],
                                    ctx: "BuilderContext",
                                    rotate_deg: int = 30,
                                    max_n: int = 30) -> None:
    """Keep a horizontal category axis readable at every rendered width.

    ECharts' default ``axisLabel.interval = "auto"`` is responsive: it
    recomputes the visible tick cadence whenever the chart resizes. Never
    replace that behavior with ``interval = 0`` for a dense axis; forcing
    every label turns date-heavy bars into an unreadable black band.

    When labels overflow:

      * every axis keeps automatic thinning plus ``hideOverlap``;
      * up to ``max_n`` categories may rotate mildly (30 degrees by
        default) when labels are not short codes;
      * larger category sets stay horizontal unless labels are genuinely
        long, in which case they use the same mild rotation;
      * very long labels are width-capped and truncated, so automatic
        thinning can retain several useful samples instead of only one or
        two full-width labels.

    Explicit author choices for ``rotate`` or ``interval`` are preserved.
    """
    ax = opt.get("xAxis")
    if isinstance(ax, list):
        ax = ax[0] if ax else None
    if not isinstance(ax, dict):
        return
    if ax.get("type") != "category":
        return
    al = ax.setdefault("axisLabel", {})
    al.setdefault("hideOverlap", True)
    if "rotate" in al or "interval" in al:
        return
    data = ax.get("data") or []
    if len(data) < 2:
        return
    avg_len = sum(len(str(v)) for v in data) / len(data)
    grid = opt.get("grid") or {}
    chart_w = max(int(getattr(ctx, "width", 700) or 700), 200)
    inner_w = chart_w - int(grid.get("left", 76) or 0) - int(grid.get("right", 20) or 0)

    if not _x_category_density_overflow(opt, inner_w):
        return

    # Make the responsive default explicit for inspection and regression
    # tests. ECharts recalculates this cadence against the live plot width.
    al["interval"] = "auto"
    n = len(data)

    # Dense ticker/tenor/category-code axes are clearest horizontally.
    # At high counts, only genuinely long semantic labels rotate, and then
    # only mildly; date-like labels remain horizontal.
    if avg_len < 5 or n > max_n:
        if (
            avg_len >= 12
            and not _looks_like_temporal_category_labels(data)
        ):
            al["rotate"] = rotate_deg
            al.setdefault("width", 96)
            al.setdefault("overflow", "truncate")
            al.setdefault("ellipsis", "...")
        return

    # A manageable set of longer labels benefits from mild rotation.
    al["rotate"] = rotate_deg
    al.setdefault("width", 120)
    al.setdefault("overflow", "truncate")
    al.setdefault("ellipsis", "...")


def _bottom_label_lift_px(opt: Dict[str, Any]) -> int:
    """Vertical pixels consumed by the xAxis tick labels (height for
    horizontal labels, width * sin(rotate) for rotated labels). Used
    to size the xAxis title's nameGap and grid.bottom."""
    import math
    ax = opt.get("xAxis")
    if isinstance(ax, list):
        ax = ax[0] if ax else None
    if not isinstance(ax, dict):
        return 0
    if ax.get("type") != "category":
        font_size = _label_font_size(opt, "xAxis")
        return int(font_size + 4)
    al = ax.get("axisLabel") or {}
    rotate = int(al.get("rotate") or 0)
    font_size = _label_font_size(opt, "xAxis")
    if rotate == 0:
        return int(font_size + 4)
    data = ax.get("data") or []
    raw_max = max((_estimate_text_px(v, font_size) for v in data),
                   default=0)
    cap = al.get("width")
    if isinstance(cap, (int, float)) and cap > 0:
        raw_max = min(raw_max, int(cap))
    return int(round(raw_max * abs(math.sin(math.radians(rotate))))) + 4


def _apply_axis_titles(opt: Dict[str, Any],
                        mapping: Dict[str, Any],
                        horizontal: bool = False,
                        chart_width: Optional[int] = None) -> None:
    """Set yAxis.name / xAxis.name from mapping['y_title'] / ['x_title']
    and size grid margins / nameGap so titles never overlap tick labels.

    Layout pipeline:
      1. For each category axis, optionally truncate over-long labels
         (via ``_layout_long_category_axis``) so the label region has
         a known max width.
      2. Compute nameGap for each axis title based on the actual label
         dimension (label width for left/right yAxis, label height-
         after-rotation for bottom xAxis).
      3. Bump grid.left / grid.right / grid.bottom to make sure the
         rotated axis title doesn't get clipped at the canvas edge.

    For horizontal=True, y_title applies to the value axis (xAxis on screen)
    and x_title applies to the category axis (yAxis on screen).

    Override per-spec with ``mapping.y_title_gap`` / ``mapping.x_title_gap``
    / ``mapping.y_title_right_gap`` / ``mapping.category_label_max_px``.
    """
    y_title = mapping.get("y_title")
    x_title = mapping.get("x_title")
    y_title_right = mapping.get("y_title_right")
    user_y_gap = mapping.get("y_title_gap")
    user_x_gap = mapping.get("x_title_gap")
    y_gap_right = mapping.get("y_title_right_gap", 52)
    cap_px = int(mapping.get("category_label_max_px",
                              _CATEGORY_LABEL_CAP_PX))

    def _set(axis_key: str, name: str, gap: int,
              idx: int = 0) -> None:
        ax = opt.get(axis_key)
        if isinstance(ax, list):
            if idx < len(ax):
                ax[idx]["name"] = name
                ax[idx]["nameLocation"] = "middle"
                ax[idx]["nameGap"] = gap
        elif isinstance(ax, dict):
            ax["name"] = name
            ax["nameLocation"] = "middle"
            ax["nameGap"] = gap

    grid = opt.get("grid") if isinstance(opt.get("grid"), dict) else None

    # ---- size yAxis nameGap from category labels (regardless of orientation)
    # If the yAxis is type=category, its tick labels are wider than the
    # default 56 px gap can accommodate. Truncate over-long labels and
    # size nameGap to clear the longest one.
    y_label_room_px = _layout_long_category_axis(
        opt, "yAxis", cap_px=cap_px, truncate=True
    )
    y_cat_gap = (y_label_room_px + _TITLE_LABEL_PADDING_PX +
                 _ROTATED_TITLE_THICKNESS_PX) if y_label_room_px else 0

    # ---- size yAxis nameGap from VALUE-label widths (single axis case)
    # When the yAxis is a value/log axis (line chart, vertical bar, ...),
    # wide tick labels like "1,234,567" or "470.0%" can poke past the
    # default 56 px nameGap and overlap the rotated axis title. Estimate
    # the longest formatted label and size the gap to clear it.
    y_value_gap = 0
    ya_for_value = opt.get("yAxis") if not horizontal else opt.get("xAxis")
    if isinstance(ya_for_value, dict) and ya_for_value.get("type") in (
        "value", "log"
    ):
        font_size = _label_font_size(
            opt, "yAxis" if not horizontal else "xAxis", default=12
        )
        label_w = _estimate_value_axis_label_width(
            opt, 0, ya_for_value, font_size=font_size
        )
        if label_w:
            y_value_gap = (label_w + _TITLE_LABEL_PADDING_PX +
                            _ROTATED_TITLE_THICKNESS_PX)

    # ---- size xAxis nameGap from category-label height (rotation-aware)
    x_label_lift_px = _bottom_label_lift_px(opt)
    x_cat_gap = (x_label_lift_px + _TITLE_LABEL_PADDING_PX +
                  _ROTATED_TITLE_THICKNESS_PX)

    # ---- resolve final per-axis gaps -------------------------------------
    if horizontal:
        # category axis is yAxis; value axis is xAxis.
        # The "y" mapping title goes on the BOTTOM xAxis; bottom labels
        # are horizontal text, so y_value_gap (which assumes a rotated
        # title beside vertical labels) doesn't apply here -- the
        # baseline x_cat_gap already accounts for label height + title.
        x_gap = user_x_gap if user_x_gap is not None else max(y_cat_gap, 56)
        y_gap = user_y_gap if user_y_gap is not None else max(x_cat_gap, 40)

        if y_title:
            _set("xAxis", y_title, y_gap)
        if x_title:
            _set("yAxis", x_title, x_gap)
    else:
        # category axis is xAxis (or none); yAxis is value (or also category
        # in heatmap).
        x_gap = user_x_gap if user_x_gap is not None else max(x_cat_gap, 40)
        y_gap = (user_y_gap if user_y_gap is not None
                 else max(y_cat_gap, y_value_gap, 56))

        if y_title:
            _set("yAxis", y_title, y_gap)
        if x_title:
            _set("xAxis", x_title, x_gap)

    if y_title_right:
        _set("yAxis", y_title_right, y_gap_right, idx=1)

    # ---- N-axis support: leave per-axis ``name`` already set by
    # _materialize_axis_spec / _layout_multi_axis_dynamic alone. We only
    # ensure nameLocation/nameGap defaults exist (setdefault, so the
    # dynamic layout's per-axis values are preserved). Pre-data callers
    # that didn't run _layout_multi_axis_dynamic still get a sensible
    # gap from the offset-aware fallback.
    yaxes = opt.get("yAxis")
    if isinstance(yaxes, list) and len(yaxes) > 0:
        for ax in yaxes:
            if not isinstance(ax, dict):
                continue
            if ax.get("name"):
                ax.setdefault("nameLocation", "middle")
                ax.setdefault("nameGap", max(40, 40 + int(ax.get("offset") or 0)))

    # ---- size grid margins to fit titles + labels -----------------------
    # ECharts positions axis names OUTSIDE the grid box and below /
    # left of the label region. Empirically, with containLabel: True,
    # the bottom margin needed for a non-clipped xAxis name is roughly
    # ``nameGap + 80`` (varies 60-90 across font sizes / rotations);
    # the left margin needs the rotated title bounding box plus a
    # small canvas pad. Without an axis title, we still need to clear
    # rotated labels.
    if grid is not None:
        # Resolve which mapping title corresponds to which screen axis.
        # bottom_axis_title: the axis name shown at the BOTTOM of the
        #   chart (xAxis name in screen orientation).
        # left_axis_title:   the axis name shown on the LEFT of the
        #   chart (yAxis name in screen orientation).
        bottom_axis_title = y_title if horizontal else x_title
        left_axis_title = x_title if horizontal else y_title
        bottom_axis_gap = y_gap if horizontal else x_gap

        if bottom_axis_title:
            need_bottom = int(bottom_axis_gap) + 80
            grid["bottom"] = max(int(grid.get("bottom", 84)),
                                  need_bottom, 100)
        elif x_label_lift_px > 30:
            grid["bottom"] = max(int(grid.get("bottom", 84)),
                                  x_label_lift_px + 30)
        if left_axis_title:
            need_left = _ROTATED_TITLE_THICKNESS_PX + 16
            grid["left"] = max(int(grid.get("left", 76)), need_left)
        if y_title_right:
            grid["right"] = max(int(grid.get("right", 20)), 76)
        # For multi-axis charts (>= 3 axes), make sure grid.left and
        # grid.right clear every offset axis. _grid_margins_for_axes
        # already ran inside the builder; this is a safety net for
        # callers who passed mapping.axes with explicit offsets that
        # exceed the default 76 px reservation.
        if isinstance(yaxes, list) and len(yaxes) >= 3:
            max_left_off = max(
                (int(a.get("offset") or 0) for a in yaxes
                 if isinstance(a, dict) and a.get("position") == "left"),
                default=0,
            )
            max_right_off = max(
                (int(a.get("offset") or 0) for a in yaxes
                 if isinstance(a, dict) and a.get("position") == "right"),
                default=0,
            )
            if max_left_off > 0:
                grid["left"] = max(int(grid.get("left", 76)),
                                     max_left_off + 72)
            if max_right_off > 0:
                grid["right"] = max(int(grid.get("right", 20)),
                                      max_right_off + 72)


def _apply_x_sort(opt: Dict[str, Any],
                   mapping: Dict[str, Any],
                   axis_key: str = "xAxis") -> None:
    """If mapping['x_sort'] is an explicit list of category values, apply it
    to the named axis (xAxis by default, yAxis for horizontal bars).

    If the axis has no pre-populated category data (auto-inferred from
    series), the sort list itself becomes the category order. This avoids
    wiping out data when no existing categories are declared.
    """
    order = mapping.get("x_sort")
    if not order or not isinstance(order, (list, tuple)):
        return
    ax = opt.get(axis_key)
    if isinstance(ax, list):
        ax = ax[0] if ax else None
    if not isinstance(ax, dict):
        return
    if ax.get("type") != "category":
        return
    existing = ax.get("data") or []
    if not existing:
        ax["data"] = list(order)
        return
    ordered = [v for v in order if v in existing]
    extras = [v for v in existing if v not in order]
    ax["data"] = ordered + extras


def _style_to_dash(style: Optional[str]) -> Optional[str]:
    """Map PRISM style keyword -> ECharts lineStyle.type."""
    if not style:
        return None
    m = {"solid": "solid", "dashed": "dashed", "dotted": "dotted"}
    return m.get(str(style).lower())


def _dash_type(dash: Any, style: Optional[str] = None) -> Any:
    """Resolve a dash spec to an ECharts lineStyle.type value.

    Accepts:
        None                  -> 'solid' (or style keyword if provided)
        'solid'|'dashed'|'dotted' -> same
        [dashOn, dashOff, ...]    -> list passed through (ECharts native)
    """
    if isinstance(dash, list) and dash:
        return dash
    if isinstance(dash, str):
        return dash
    styled = _style_to_dash(style)
    return styled or "solid"


# ---------------------------------------------------------------------------
# Annotations (hline, vline, band, arrow, point)
# ---------------------------------------------------------------------------

_ANNOTATION_TYPES = {"hline", "vline", "band", "arrow", "point"}


_DICT_OF_CLASSES_KEYS = frozenset({
    "event_lines", "v_lines", "vlines",
    "h_lines", "hlines",
    "x_bands", "y_bands", "bands",
    "points", "arrows",
})


def _normalize_annotations(
    raw: Any,
) -> List[Dict[str, Any]]:
    """Accept BOTH the canonical flat list-of-typed-dicts shape AND
    the dict-of-classes shape some authors prefer:

        canonical (the engine's native form):
            [{"type": "vline", "x": "2026-04-22", "label": "FOMC"},
             {"type": "band", "x1": "2026-03-01", "x2": "2026-04-01"},
             {"type": "hline", "y": 4.5, "label": "Target"}]

        dict-of-classes (sugar; folded to canonical here):
            {"event_lines": [{"x": "2026-04-22", "label": "FOMC"}],
             "x_bands":     [{"x_from": "2026-03-01",
                              "x_to":   "2026-04-01"}],
             "h_lines":     [{"y": 4.5, "label": "Target"}],
             "v_lines":     [...],   # also accepted as alias for vlines
             "y_bands":     [{"y_from": 0, "y_to": 1, "label": "Q"}]}

    Mapping (sugar -> canonical):
        event_lines / v_lines / vlines  -> type=vline,  x=x
        h_lines / hlines                -> type=hline,  y=y
        x_bands                         -> type=band, x1=x_from, x2=x_to
        y_bands / bands                 -> type=band, y1=y_from, y2=y_to
        points                          -> type=point
        arrows                          -> type=arrow

    Items that don't carry the required positional key (e.g. an
    event_line missing ``x``) are skipped silently rather than
    silently emitting a broken markLine entry.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        # Same contract as the dict-of-classes branch below: silently
        # skip items missing the required positional key for their
        # type, rather than letting them through to _apply_annotations
        # where they produce a broken markLine entry (no `coord`, no
        # `yAxis`/`xAxis`) that crashes ECharts' renderSeries with
        # `Cannot read properties of undefined (reading 'coord')`.
        # Also accept author-friendly aliases (`value`, `at`, `x_value`,
        # `y_value`) and fold them to the canonical positional key.
        cleaned: List[Dict[str, Any]] = []
        for a in raw:
            if not isinstance(a, dict):
                continue
            t = str(a.get("type", "")).lower()
            ann = dict(a)
            if t == "hline":
                if "y" not in ann:
                    for alias in ("value", "y_value", "at"):
                        if alias in ann:
                            ann["y"] = ann.pop(alias)
                            break
                if ann.get("y") is None:
                    continue
            elif t == "vline":
                if "x" not in ann:
                    for alias in ("value", "x_value", "at"):
                        if alias in ann:
                            ann["x"] = ann.pop(alias)
                            break
                if ann.get("x") is None:
                    continue
            elif t == "band":
                has_x_band = ann.get("x1") is not None and ann.get("x2") is not None
                has_y_band = ann.get("y1") is not None and ann.get("y2") is not None
                if not (has_x_band or has_y_band):
                    continue
            elif t == "arrow":
                if any(ann.get(k) is None for k in ("x1", "y1", "x2", "y2")):
                    continue
            elif t == "point":
                if ann.get("x") is None or ann.get("y") is None:
                    continue
            cleaned.append(ann)
        return cleaned
    if not isinstance(raw, dict):
        return []
    out: List[Dict[str, Any]] = []
    for key, items in raw.items():
        if key not in _DICT_OF_CLASSES_KEYS:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            ann = dict(item)
            if key in ("event_lines", "v_lines", "vlines"):
                if "x" not in ann:
                    continue
                ann["type"] = "vline"
            elif key in ("h_lines", "hlines"):
                if "y" not in ann:
                    continue
                ann["type"] = "hline"
            elif key == "x_bands":
                x1 = ann.pop("x_from", ann.get("x1"))
                x2 = ann.pop("x_to",   ann.get("x2"))
                if x1 is None or x2 is None:
                    continue
                ann["x1"] = x1
                ann["x2"] = x2
                ann["type"] = "band"
            elif key in ("y_bands", "bands"):
                y1 = ann.pop("y_from", ann.get("y1"))
                y2 = ann.pop("y_to",   ann.get("y2"))
                if y1 is None or y2 is None:
                    continue
                ann["y1"] = y1
                ann["y2"] = y2
                ann["type"] = "band"
            elif key == "points":
                ann["type"] = "point"
            elif key == "arrows":
                ann["type"] = "arrow"
            out.append(ann)
    return out


def _apply_annotations(opt: Dict[str, Any],
                        annotations: Optional[List[Dict[str, Any]]]) -> None:
    """Attach annotations via markLine/markArea/markPoint.

    Horizontal lines attach to a series on their selected y-axis; the
    remaining annotation types attach to the primary series.

    All annotations are dicts with a 'type' key:
        hline  -> horizontal rule at y (axis='left'|'right' for dual-axis)
        vline  -> vertical rule at x
        band   -> shaded band (x1,x2) vertical or (y1,y2) horizontal
        arrow  -> directional line from (x1,y1) to (x2,y2)
        point  -> point marker at (x,y) with label

    Common keys: label, color, style ('solid'|'dashed'|'dotted'),
    stroke_dash (explicit list or string), stroke_width, label_color,
    label_position, opacity, head_size, font_size.

    Unknown 'type' values are silently skipped. Annotations on charts
    without xAxis/yAxis (pie, sankey, treemap, etc.) will be ignored by
    ECharts at render time (no axis to anchor to).
    """
    if not annotations:
        return
    series = opt.get("series")
    if not series:
        return
    if isinstance(series, dict):
        series = [series]
        opt["series"] = series
    primary = series[0]

    ml_data: List[Any] = []
    hline_data_by_axis: Dict[int, List[Any]] = {}
    ma_data: List[List[Dict[str, Any]]] = []
    mp_data: List[Dict[str, Any]] = []

    def _hline_axis_index(annotation: Dict[str, Any]) -> int:
        axis_selector = annotation.get("axis")
        if (isinstance(axis_selector, int)
                and not isinstance(axis_selector, bool)
                and axis_selector > 0):
            return int(axis_selector)
        if (isinstance(axis_selector, str)
                and axis_selector.lower() == "right"):
            return 1
        return 0

    # Pre-pass: count vlines so the per-vline branch below can stagger
    # / shrink / rotate labels when the count is high enough that
    # default top-end placement would produce a vertical pile-up of
    # labels along the chart top.
    vline_count = sum(
        1 for a in (annotations or [])
        if isinstance(a, dict) and str(a.get("type", "")).lower() == "vline"
    )
    vline_idx = 0  # incremented as we process vlines below

    for a in annotations or []:
        if not isinstance(a, dict):
            continue
        t = str(a.get("type", "")).lower()
        if t not in _ANNOTATION_TYPES:
            continue
        label = a.get("label")
        color = a.get("color", "#666666")
        stroke_width = a.get("stroke_width", 1.5)
        dash_val = _dash_type(a.get("stroke_dash"),
                               a.get("style", "dashed" if t in ("hline", "vline") else "solid"))
        label_color = a.get("label_color", color)
        opacity = a.get("opacity", 0.3)

        if t == "hline":
            d: Dict[str, Any] = {"yAxis": a.get("y")}
            # axis= can be:
            #   "left"  -> yAxisIndex 0 (default)
            #   "right" -> yAxisIndex 1 (legacy 2-axis convenience)
            #   int     -> explicit axis index for N-axis charts
            axis_index = _hline_axis_index(a)
            if axis_index > 0:
                d["yAxisIndex"] = axis_index
            if label is not None:
                d["name"] = str(label)
            d["lineStyle"] = {"color": color, "width": stroke_width,
                                "type": dash_val}
            d["label"] = ({"show": True, "formatter": str(label),
                             "color": label_color,
                             "position": a.get("label_position", "insideEndTop")}
                          if label is not None else {"show": False})
            hline_data_by_axis.setdefault(axis_index, []).append(d)

        elif t == "vline":
            d = {"xAxis": a.get("x")}
            if label is not None:
                d["name"] = str(label)
            d["lineStyle"] = {"color": color, "width": stroke_width,
                                "type": dash_val}
            # Label stagger / shrink: when many vlines exist on the
            # same chart, default top-end placement produces an
            # unreadable horizontal pile-up of labels. Apply
            # progressive mitigations as count rises.
            if label is not None:
                lbl_cfg: Dict[str, Any] = {
                    "show": True, "formatter": str(label),
                    "color": label_color,
                    "position": a.get("label_position", "end"),
                }
                if vline_count >= 4:
                    # Stagger between top end and bottom-start to
                    # split labels into two rows.
                    if "label_position" not in a:
                        lbl_cfg["position"] = (
                            "end" if (vline_idx % 2 == 0) else "start"
                        )
                    lbl_cfg["fontSize"] = 9
                if vline_count >= 8:
                    # Rotate 90 degrees so labels stack vertically
                    # and don't compete for horizontal space.
                    lbl_cfg["rotate"] = 90
                    lbl_cfg["fontSize"] = 8
                    lbl_cfg["distance"] = 6
                    # Truncate long labels so rotated text doesn't
                    # spill out of the chart frame.
                    if isinstance(label, str) and len(label) > 12:
                        truncated = label[:11] + "..."
                        lbl_cfg["formatter"] = truncated
                d["label"] = lbl_cfg
            else:
                d["label"] = {"show": False}
            ml_data.append(d)
            vline_idx += 1

        elif t == "band":
            if "x1" in a and "x2" in a:
                left: Dict[str, Any] = {"xAxis": a["x1"]}
                right: Dict[str, Any] = {"xAxis": a["x2"]}
            elif "y1" in a and "y2" in a:
                left = {"yAxis": a["y1"]}
                right = {"yAxis": a["y2"]}
            else:
                continue
            if label is not None:
                left["name"] = str(label)
            left["itemStyle"] = {"color": color, "opacity": opacity}
            if label is not None:
                left["label"] = {"show": True, "formatter": str(label),
                                  "color": label_color,
                                  "position": a.get("label_position", "insideTop")}
            ma_data.append([left, right])

        elif t == "arrow":
            d1: Dict[str, Any] = {"coord": [a.get("x1"), a.get("y1")]}
            d2: Dict[str, Any] = {"coord": [a.get("x2"), a.get("y2")]}
            d1["symbol"] = "none"
            d2["symbol"] = a.get("head_type", "arrow") if a.get("head_type", "arrow") != "none" else "none"
            d2["symbolSize"] = a.get("head_size", 10)
            d1["lineStyle"] = {"color": color, "width": stroke_width,
                                "type": dash_val}
            if label is not None:
                d1["label"] = {"show": True, "formatter": str(label),
                                "color": label_color,
                                "position": a.get("label_position", "middle")}
            else:
                d1["label"] = {"show": False}
            ml_data.append([d1, d2])

        elif t == "point":
            d = {"coord": [a.get("x"), a.get("y")]}
            d["symbol"] = a.get("symbol", "circle")
            d["symbolSize"] = a.get("symbol_size", 10)
            d["itemStyle"] = {"color": color}
            if label is not None:
                d["label"] = {"show": True, "formatter": str(label),
                                "color": label_color,
                                "fontSize": a.get("font_size", 11),
                                "position": a.get("label_position", "top")}
            else:
                d["label"] = {"show": False}
            mp_data.append(d)

    def _attach_mark_lines(
        target_series: Dict[str, Any],
        data: List[Any],
    ) -> None:
        existing = target_series.setdefault("markLine", {})
        existing.setdefault("symbol", ["none", "none"])
        existing.setdefault("silent", False)
        existing.setdefault("animation", False)
        existing.setdefault("data", []).extend(data)

    if ml_data:
        _attach_mark_lines(primary, ml_data)
    for axis_index, axis_hlines in hline_data_by_axis.items():
        target_series = next(
            (
                item for item in series
                if isinstance(item, dict)
                and (
                    item.get("yAxisIndex", 0)
                    if not isinstance(item.get("yAxisIndex", 0), bool)
                    else 0
                ) == axis_index
            ),
            None,
        )
        if target_series is not None:
            _attach_mark_lines(target_series, axis_hlines)
    if ma_data:
        existing = primary.setdefault("markArea", {})
        existing.setdefault("silent", True)
        existing.setdefault("animation", False)
        existing.setdefault("data", []).extend(ma_data)
    if mp_data:
        existing = primary.setdefault("markPoint", {})
        existing.setdefault("animation", False)
        existing.setdefault("data", []).extend(mp_data)

    # Auto-extend axis range to include reference lines that fall outside
    # the data span. Bounds must be compared with the plotted data before
    # they are written: deriving both bounds from the annotation alone
    # turns an in-range zero line into yAxis=[-1, 1] and clips an otherwise
    # healthy series (for example, a -109..+90 bp curve).
    h_y_values: Dict[int, List[float]] = {}
    v_x_values: List[Any] = []
    for a in annotations or []:
        if not isinstance(a, dict):
            continue
        t = str(a.get("type", "")).lower()
        if t == "hline":
            try:
                y_value = float(a.get("y"))
            except (TypeError, ValueError):
                pass
            else:
                if not math.isfinite(y_value):
                    continue
                axis_index = _hline_axis_index(a)
                h_y_values.setdefault(axis_index, []).append(y_value)
        elif t == "vline":
            x_val = a.get("x")
            if x_val is not None:
                v_x_values.append(x_val)

    if h_y_values:
        raw_y_axes = opt.get("yAxis")
        y_axes = (
            raw_y_axes if isinstance(raw_y_axes, list)
            else ([raw_y_axes] if isinstance(raw_y_axes, dict) else [])
        )
        raw_x_axes = opt.get("xAxis")
        x_axes = (
            raw_x_axes if isinstance(raw_x_axes, list)
            else ([raw_x_axes] if isinstance(raw_x_axes, dict) else [])
        )
        x_axis_type = (
            x_axes[0].get("type")
            if x_axes and isinstance(x_axes[0], dict) else None
        )

        def _finite_values_for_axis(axis_index: int) -> List[float]:
            values: List[float] = []

            def _append(value: Any) -> None:
                if value is None or isinstance(value, bool):
                    return
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    return
                if math.isfinite(number):
                    values.append(number)

            for item in series:
                if not isinstance(item, dict):
                    continue
                item_axis = item.get("yAxisIndex", 0)
                if isinstance(item_axis, bool):
                    item_axis = 0
                try:
                    item_axis = int(item_axis)
                except (TypeError, ValueError):
                    item_axis = 0
                if item_axis != axis_index:
                    continue
                series_type = str(item.get("type", "")).lower()
                data = item.get("data")
                if not isinstance(data, list):
                    continue
                for point in data:
                    raw_value = (
                        point.get("value")
                        if isinstance(point, dict) else point
                    )
                    if not isinstance(raw_value, (list, tuple)):
                        _append(raw_value)
                        continue
                    if series_type == "candlestick":
                        candidates = (
                            raw_value[1:]
                            if x_axis_type == "time" else raw_value
                        )
                        for candidate in candidates:
                            _append(candidate)
                    elif series_type == "boxplot":
                        for candidate in raw_value:
                            _append(candidate)
                    elif len(raw_value) >= 2:
                        _append(raw_value[1])
                    elif raw_value:
                        _append(raw_value[0])
            return values

        for axis_index, annotation_values in h_y_values.items():
            if axis_index >= len(y_axes):
                continue
            axis = y_axes[axis_index]
            if not isinstance(axis, dict) or axis.get("type") == "category":
                continue
            data_values = _finite_values_for_axis(axis_index)
            if not data_values:
                continue

            annotation_min = min(annotation_values)
            annotation_max = max(annotation_values)
            existing_min = axis.get("min")
            existing_max = axis.get("max")
            comparison_min = (
                float(existing_min)
                if isinstance(existing_min, (int, float))
                and not isinstance(existing_min, bool)
                else min(data_values)
            )
            comparison_max = (
                float(existing_max)
                if isinstance(existing_max, (int, float))
                and not isinstance(existing_max, bool)
                else max(data_values)
            )

            if annotation_min < comparison_min:
                pad = abs(annotation_min) * 0.05 + 1.0
                axis["min"] = float(annotation_min - pad)
            if annotation_max > comparison_max:
                pad = abs(annotation_max) * 0.05 + 1.0
                axis["max"] = float(annotation_max + pad)


def _time_axis_if_needed(df, col: str) -> Dict[str, Any]:
    import pandas as pd
    if df is None or col not in df.columns:
        return {"type": "category", "axisLabel": {"hideOverlap": True}}
    ser = df[col]
    if pd.api.types.is_datetime64_any_dtype(ser):
        # showMinLabel / showMaxLabel default True forces ECharts to
        # render day-number labels at the chart edges, producing "23"
        # / "22" stub labels next to the natural month labels (e.g.
        # "23 Sep ... Apr 22"). Disable the forced edge labels and
        # let the natural label cadence -- which the auto-formatter
        # already chooses sensibly for the data range -- own the
        # tick set. (Round 2 hardening, 2026-05-11 evening.)
        return {"type": "time",
                "axisLabel": {"hideOverlap": True,
                              "showMinLabel": False,
                              "showMaxLabel": False}}
    if pd.api.types.is_numeric_dtype(ser):
        return {"type": "value", "axisLabel": {"hideOverlap": True}}
    return {"type": "category", "axisLabel": {"hideOverlap": True}}


# ---------------------------------------------------------------------------
# Multi-axis resolver (line / multi_line / area)
# ---------------------------------------------------------------------------
#
# The canonical multi-axis API is ``mapping.axes`` -- a list of axis spec
# dicts that lets authors define any number of independent y-axes on
# either side of the chart, each with its own scale, inversion, log
# toggle, range bounds, and tick formatter:
#
#     mapping = {
#         "x": "date",
#         "y": ["spx", "ust", "dxy", "wti"],
#         "axes": [
#             {"side": "left",  "title": "SPX",       "series": ["spx"]},
#             {"side": "right", "title": "UST 10Y",   "series": ["ust"],
#              "invert": True},
#             {"side": "left",  "title": "DXY",       "series": ["dxy"]},
#             {"side": "right", "title": "WTI",       "series": ["wti"]},
#         ],
#     }
#
# ECharts itself supports any number of yAxis entries via ``offset``
# (px-from-inner-edge) on each axis; the resolver auto-stacks axes on
# each side so the per-axis tick label regions don't collide.
#
# Backward compat: when ``mapping.axes`` is absent, the resolver builds
# the equivalent 1- or 2-axis spec from ``mapping.dual_axis_series``,
# ``mapping.invert_y``, ``mapping.invert_right_axis``, ``y_title``, and
# ``y_title_right``. Existing callers that don't know about the new
# API see no behavior change.

# Default px between consecutive axes on the same side. Needs to clear
# the previous axis' tick labels (~50-60 px for 4-5 digits at fontSize
# 12) AND leave a comfortable gap before the next axis starts so the
# stacked numbers don't read as one cramped block. 80 is a good
# default for typical financial-data magnitudes; override via
# ``mapping.axis_offset_step`` for tight or extra-wide labels.
_AXIS_OFFSET_STEP_PX = 80


def _resolve_axis_specs(
    mapping: Dict[str, Any],
    series_names: Sequence[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Resolve ``mapping.axes`` (or backward-compat fallbacks) into a
    normalized list of axis spec dicts plus a series-name -> axis-index
    map.

    Each returned axis spec has these fields filled in (with sensible
    defaults):
        title, side, invert, log, scale, min, max, format,
        position (= side), offset

    The series_to_axis dict maps every series name to exactly one axis
    index; series not explicitly assigned land on axis 0.
    """
    raw_axes = mapping.get("axes")
    offset_step = int(
        mapping.get("axis_offset_step", _AXIS_OFFSET_STEP_PX)
    )

    if not isinstance(raw_axes, (list, tuple)) or not raw_axes:
        # Backward-compat path: synthesize 1- or 2-axis spec from the
        # legacy dual_axis_series / invert_y / invert_right_axis keys.
        invert_left = bool(mapping.get("invert_y"))
        invert_right = bool(mapping.get("invert_right_axis"))
        y_log = bool(mapping.get("y_log"))
        y_title = mapping.get("y_title") or ""
        y_title_right = mapping.get("y_title_right") or ""

        dual = mapping.get("dual_axis_series")
        if dual:
            if not isinstance(dual, (list, tuple)):
                dual = [dual]
            right_set = {str(v) for v in dual}
            left_series = [n for n in series_names if str(n) not in right_set]
            right_series = [n for n in series_names if str(n) in right_set]
            axes: List[Dict[str, Any]] = [
                {"side": "left", "title": y_title,
                  "series": list(left_series),
                  "invert": invert_left, "log": y_log,
                  "_offset_explicit": False},
                {"side": "right", "title": y_title_right,
                  "series": list(right_series),
                  "invert": invert_right, "log": y_log,
                  "_offset_explicit": False},
            ]
        else:
            axes = [
                {"side": "left", "title": y_title,
                  "series": list(series_names),
                  "invert": invert_left, "log": y_log,
                  "_offset_explicit": False},
            ]
    else:
        axes = []
        seen_series: List[str] = []
        for i, raw in enumerate(raw_axes):
            if not isinstance(raw, dict):
                raise ValueError(
                    f"axes[{i}]: expected dict, got {type(raw).__name__}"
                )
            side_raw = (raw.get("side") or raw.get("position") or "left")
            side = str(side_raw).lower()
            if side not in ("left", "right"):
                raise ValueError(
                    f"axes[{i}].side: expected 'left' or 'right', "
                    f"got {side_raw!r}"
                )
            ser_raw = raw.get("series") or []
            if isinstance(ser_raw, str):
                ser_list = [ser_raw]
            elif isinstance(ser_raw, (list, tuple)):
                ser_list = [str(s) for s in ser_raw]
            else:
                raise ValueError(
                    f"axes[{i}].series: expected list of strings, "
                    f"got {type(ser_raw).__name__}"
                )
            for s in ser_list:
                if s in seen_series:
                    raise ValueError(
                        f"axes[{i}].series: '{s}' is already assigned "
                        f"to another axis; each series belongs to "
                        f"exactly one axis."
                    )
                seen_series.append(s)
            axes.append({
                "side": side,
                "title": str(raw.get("title") or raw.get("name") or ""),
                "series": ser_list,
                "invert": bool(raw.get("invert", False)),
                "log": bool(raw.get("log", False)),
                "scale": bool(raw.get("scale", True)),
                "min": raw.get("min"),
                "max": raw.get("max"),
                "format": raw.get("format"),
                "offset": raw.get("offset"),  # may be None -> auto
                # Track whether the author pinned this offset explicitly;
                # the post-data layout pass uses this to leave hand-tuned
                # values alone while it recomputes the auto-stack ones.
                "_offset_explicit": raw.get("offset") is not None,
                # Explicit color override; otherwise the builder
                # auto-color-codes single-series axes from the palette.
                "color": raw.get("color"),
            })
        # Author may omit some series from axes[*].series; sweep them
        # onto axis 0 so the chart still renders without surprise NaN.
        for s in series_names:
            if str(s) not in seen_series:
                axes[0]["series"].append(str(s))

    # ---- compute auto offsets for axes that didn't pin one --------------
    # On each side, the FIRST axis sits at offset 0 (the canvas edge);
    # the 2nd at +offset_step, the 3rd at +2*offset_step, etc. This is
    # an INITIAL pass; the post-data ``_layout_multi_axis_dynamic`` may
    # widen the step once it knows the actual tick label widths.
    next_offset = {"left": 0, "right": 0}
    for ax in axes:
        if ax.get("offset") is None:
            ax["offset"] = next_offset[ax["side"]]
        next_offset[ax["side"]] = max(
            next_offset[ax["side"]],
            int(ax["offset"]) + offset_step,
        )

    # ---- build the series_name -> axis_index map ------------------------
    series_to_axis: Dict[str, int] = {}
    for idx, ax in enumerate(axes):
        for s in ax["series"]:
            series_to_axis[str(s)] = idx
    # Fallback for any unassigned name (shouldn't happen given the sweep
    # above, but defensive against subclasses / edge cases).
    for s in series_names:
        series_to_axis.setdefault(str(s), 0)

    return axes, series_to_axis


_AXIS_FORMAT_PRESETS: Dict[str, str] = {
    "percent": "function(v){ return (v*100).toFixed(1) + '%'; }",
    "bp":      "function(v){ return v.toFixed(0) + ' bp'; }",
    "usd":     "function(v){ return '$' + v.toLocaleString(); }",
    "compact": (
        "function(v){"
        " var a = Math.abs(v);"
        " if (a >= 1e12) return (v/1e12).toFixed(1) + 'T';"
        " if (a >= 1e9)  return (v/1e9).toFixed(1) + 'B';"
        " if (a >= 1e6)  return (v/1e6).toFixed(1) + 'M';"
        " if (a >= 1e3)  return (v/1e3).toFixed(1) + 'K';"
        " return v.toString();"
        "}"
    ),
}


def _format_value_for_width_est(v: float, fmt_preset: Optional[str]) -> str:
    """Approximate the string ECharts would render for value ``v`` given
    the axis format preset. Used purely for label-width estimation in
    layout sizing -- the actual formatting still happens at render time
    via the JS formatter strings in ``_AXIS_FORMAT_PRESETS``.

    Mirrors the JS bodies above so the Python estimate is character-
    accurate for known presets; falls back to a magnitude-based
    heuristic that overestimates slightly (one or two extra decimals
    of headroom) so the layout pad is generous rather than tight.
    """
    if not isinstance(v, (int, float)) or (isinstance(v, float) and v != v):
        return ""
    if fmt_preset == "percent":
        # JS: (v*100).toFixed(1) + '%' -> "470.0%"
        return f"{v * 100:.1f}%"
    if fmt_preset == "bp":
        return f"{v:.0f} bp"
    if fmt_preset == "usd":
        if abs(v) >= 1:
            return "$" + f"{int(round(v)):,}"
        return f"${v:.2f}"
    if fmt_preset == "compact":
        a = abs(v)
        if a >= 1e12:
            return f"{v/1e12:.1f}T"
        if a >= 1e9:
            return f"{v/1e9:.1f}B"
        if a >= 1e6:
            return f"{v/1e6:.1f}M"
        if a >= 1e3:
            return f"{v/1e3:.1f}K"
        # JS toString() branch -- estimate as a 1-decimal float.
        return f"{v:.1f}"
    # No preset: ECharts default formatting picks "nice" numbers via
    # JS `.toString()`, which doesn't add commas. Overestimate slightly
    # by including one extra decimal place when plausible -- that's
    # cheaper than underrunning and clipping a real label.
    a = abs(v)
    if a == 0:
        return "0"
    if a < 0.01:
        return f"{v:.4f}"
    if a < 1:
        return f"{v:.3f}"
    if a < 10:
        return f"{v:.2f}"
    if a < 100:
        return f"{v:.1f}"
    if a < 1000:
        return f"{v:.1f}"
    # >= 1000: ECharts's default `{value}` template renders integers
    # without thousands separators (`5009`, not `5,009`). We mirror
    # that here so the layout matches the actual rendered width.
    return f"{int(round(v))}"


def _detect_format_preset_from_formatter(formatter: Any) -> Optional[str]:
    """Best-effort identification of the ``_AXIS_FORMAT_PRESETS`` preset
    that produced the given formatter string. Falls back to ``None``
    for custom user-supplied formatters; the caller then uses the
    magnitude-based heuristic for label-width estimation.
    """
    if not isinstance(formatter, str) or not formatter:
        return None
    for preset_name, preset_str in _AXIS_FORMAT_PRESETS.items():
        if formatter == preset_str:
            return preset_name
    return None


def _estimate_value_axis_label_width(
    opt: Dict[str, Any],
    axis_idx: int,
    axis_dict: Dict[str, Any],
    fmt_preset: Optional[str] = None,
    *,
    font_size: int = 12,
) -> int:
    """Estimate the longest tick label width (px) for a value y-axis.

    Walks ``opt['series']`` for entries mapped to ``axis_idx`` (via
    ``yAxisIndex``; the implicit axis 0 has no key), gathers numeric
    samples, and returns the max pixel width of the formatted extremes.

    ``fmt_preset`` lets callers that know the preset name pass it in
    directly (e.g. multi-axis specs with a stored ``format`` field);
    if ``None``, we sniff the axis's own ``axisLabel.formatter`` and
    fall back to the magnitude-based heuristic for unknown formatters.

    Returns 0 for non-value axes (category labels are sized via
    ``_layout_long_category_axis``).
    """
    if axis_dict.get("type") not in ("value", "log"):
        return 0

    if fmt_preset is None:
        fmt_preset = _detect_format_preset_from_formatter(
            (axis_dict.get("axisLabel") or {}).get("formatter")
        )

    series = opt.get("series") or []
    values: List[float] = []
    for s in series:
        if not isinstance(s, dict):
            continue
        s_axis = int(s.get("yAxisIndex", 0) or 0)
        if s_axis != int(axis_idx):
            continue
        for row in s.get("data") or []:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                v = row[1]
            elif isinstance(row, dict):
                vv = row.get("value")
                if isinstance(vv, (list, tuple)) and len(vv) >= 2:
                    v = vv[1]
                else:
                    v = vv
            else:
                v = row
            if isinstance(v, (int, float)) and not (
                isinstance(v, float) and v != v
            ):
                values.append(float(v))

    explicit_min = axis_dict.get("min")
    explicit_max = axis_dict.get("max")
    if isinstance(explicit_min, (int, float)):
        values.append(float(explicit_min))
    if isinstance(explicit_max, (int, float)):
        values.append(float(explicit_max))

    if not values:
        # No data: assume a 6-char fallback so the label band is sized
        # for typical financial magnitudes rather than zero.
        return _estimate_text_px("12345.6", font_size)

    vmin, vmax = min(values), max(values)
    candidates = [vmin, vmax]
    if vmin < 0 < vmax:
        candidates.append(min(abs(vmin), abs(vmax)))

    return max(
        _estimate_text_px(_format_value_for_width_est(v, fmt_preset), font_size)
        for v in candidates
    )


def _value_axis_name_gap(
    label_width_px: int,
    *,
    base: int = 40,
) -> int:
    """Compute the perpendicular distance (nameGap) between a value
    axis line and its rotated axis name so the name clears the longest
    tick label with breathing room.

    nameGap is measured from the axis LINE (not from the label
    region's outer edge), so the formula adds the label width plus
    standard padding plus the rotated text bounding-box thickness.

    ``base`` floors the result so axes with empty labels still get a
    sensible gap (40 for offset axes, 56 for single-axis charts).
    """
    return max(
        base,
        int(label_width_px) + _TITLE_LABEL_PADDING_PX + _ROTATED_TITLE_THICKNESS_PX,
    )


def _materialize_axis_spec(spec: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """Convert a normalized axis spec into the ECharts yAxis dict.

    Color-coding (axis line / ticks / labels / name to match the
    associated series color) is applied later in ``build_line`` once
    the series-name -> palette-color map is known; this helper just
    handles the structural fields.
    """
    ax_type = "log" if spec["log"] else "value"
    ax: Dict[str, Any] = {
        "type": ax_type,
        "name": spec["title"] or "",
        "position": spec["side"],
        "inverse": bool(spec["invert"]),
        "scale": (not spec["log"]) and bool(spec.get("scale", True)),
        "axisLabel": {"hideOverlap": True},
        "offset": int(spec["offset"]),
    }
    # Only the first axis on the chart shows the gridline; the rest
    # would just clutter the plot area with overlapping splitLines.
    if idx > 0:
        ax["splitLine"] = {"show": False}
    if spec.get("min") is not None:
        ax["min"] = spec["min"]
    if spec.get("max") is not None:
        ax["max"] = spec["max"]
    fmt = spec.get("format")
    if isinstance(fmt, str) and fmt:
        fmt_str = _AXIS_FORMAT_PRESETS.get(fmt, fmt)
        ax["axisLabel"]["formatter"] = fmt_str
    return ax


def _color_code_axis(ax: Dict[str, Any], color: str) -> None:
    """Tint the axis line, ticks, label color, and rotated name color
    to match the series color it carries. Skips if ``color`` is empty.
    """
    if not color:
        return
    ax["axisLine"] = {"show": True, "lineStyle": {"color": color, "width": 1.5}}
    ax["axisTick"] = {"lineStyle": {"color": color}}
    label = ax.get("axisLabel") or {}
    label["color"] = color
    ax["axisLabel"] = label
    name_style = ax.get("nameTextStyle") or {}
    name_style["color"] = color
    name_style.setdefault("fontWeight", "bold")
    ax["nameTextStyle"] = name_style


def _series_name_to_color(
    series_names: Sequence[str], ctx: BuilderContext
) -> Dict[str, str]:
    """Map each series name to the palette color ECharts will assign it.
    Returns an empty dict when the active palette isn't categorical
    (e.g. heatmap palettes go through visualMap, not series colors).
    """
    if ctx.palette_kind != "categorical" or not ctx.palette_colors:
        return {}
    palette = list(ctx.palette_colors)
    return {
        str(name): palette[i % len(palette)]
        for i, name in enumerate(series_names)
    }


def _apply_axis_color_coding(
    materialized: List[Dict[str, Any]],
    axis_specs: Sequence[Dict[str, Any]],
    name_to_color: Dict[str, str],
    *,
    enabled: bool,
) -> None:
    """Walk each axis and (if enabled and the axis carries a single
    series with a known color) recolor its line / labels / name to
    match the series. Axes carrying 2+ series can opt in via
    ``axes[i].color``; we don't auto-pick one of N colors.
    """
    if not enabled:
        return
    for spec, ax in zip(axis_specs, materialized):
        explicit = spec.get("color")
        if isinstance(explicit, str) and explicit:
            _color_code_axis(ax, explicit)
            continue
        if explicit is False:
            # Author opted out for this axis specifically.
            continue
        ser_list = spec.get("series") or []
        if len(ser_list) == 1:
            color = name_to_color.get(str(ser_list[0]))
            if color:
                _color_code_axis(ax, color)


def _grid_margins_for_axes(
    axes: Sequence[Dict[str, Any]],
    *,
    label_band_px: int = 70,
    label_widths: Optional[Sequence[int]] = None,
) -> Tuple[int, int]:
    """Compute (left_margin, right_margin) px needed to clear all
    offset axes plus their tick-label region.

    When ``label_widths`` is provided we size each axis's band to
    exactly ``label_width + title_pad`` (rotated title thickness +
    padding), floored at 35 px so 1-2 char labels still leave visible
    breathing room. Axes with an empty ``name`` skip the title
    reservation (no rotated title will render there).

    When ``label_widths`` is absent (initial pre-data pass) we fall
    back to the conservative flat band (``label_band_px``, default
    70 px covers ~5-digit numbers at fontSize 12).
    """
    max_left = 0
    max_right = 0
    title_pad = _ROTATED_TITLE_THICKNESS_PX + _TITLE_LABEL_PADDING_PX
    for i, ax in enumerate(axes):
        off = int(ax.get("offset") or 0)
        has_name = bool(ax.get("name"))
        pad = title_pad if has_name else 8
        if label_widths is not None and i < len(label_widths):
            band = max(35, int(label_widths[i]) + pad)
        else:
            band = label_band_px
        if ax.get("side") == "right":
            max_right = max(max_right, off + band)
        else:
            max_left = max(max_left, off + band)
    return max_left, max_right


def _layout_multi_axis_dynamic(
    opt: Dict[str, Any],
    axis_specs: Sequence[Dict[str, Any]],
    mapping: Dict[str, Any],
) -> List[int]:
    """Recompute multi-axis offsets, nameGaps, and grid margins from the
    actual rendered tick-label widths so adjacent axes never overlap
    their tick labels with the inner axis's rotated name.

    Layout invariants (per side):
      * The first axis on each side sits at offset 0 (canvas inner edge).
      * Each subsequent axis sits at the previous axis's offset PLUS a
        per-pair step large enough to clear the inner axis's rotated
        name (= its nameGap + half of the rotated text bounding box +
        breathing room). The user's ``mapping.axis_offset_step`` floors
        the step so authors can still widen the layout manually.
      * Per-axis nameGap = max(40, label_width + padding + title
        thickness). We do NOT add ``offset`` to nameGap -- ECharts
        already shifts the whole axis (line + labels + name) by
        ``offset``, so adding it again pushes the name too far out.

    Returns the per-axis label widths so the caller can use them for
    grid-margin sizing.
    """
    yaxes = opt.get("yAxis")
    if not isinstance(yaxes, list) or len(yaxes) < 2:
        return []

    # Only treat ``axis_offset_step`` as a step FLOOR when the author
    # set it explicitly; otherwise let the computed step (driven by
    # actual label widths + rotated-title clearance) win. The old
    # behaviour -- defaulting to 80 and flooring unconditionally --
    # wasted 10-30 px per axis on small-label configs, which compounds
    # to 40-60 px of dead space per side on a 4-axis tile.
    _os_raw = mapping.get("axis_offset_step")
    user_step_explicit = _os_raw is not None
    user_step = int(_os_raw) if user_step_explicit else 0
    font_size = _label_font_size(opt, "yAxis", default=12)

    # Per-axis estimated label widths and rotated-name nameGaps.
    # Axes with an empty ``name`` skip the title-based padding because
    # no rotated title will render; clearance only needs to cover the
    # tick labels themselves.
    label_widths: List[int] = []
    name_gaps: List[int] = []
    has_names: List[bool] = []
    for i, ax in enumerate(yaxes):
        if not isinstance(ax, dict):
            label_widths.append(0)
            name_gaps.append(40)
            has_names.append(False)
            continue
        spec = axis_specs[i] if i < len(axis_specs) else {}
        fmt = spec.get("format") if isinstance(spec, dict) else None
        w = _estimate_value_axis_label_width(opt, i, ax, fmt,
                                              font_size=font_size)
        label_widths.append(w)
        name_gaps.append(_value_axis_name_gap(w))
        has_names.append(bool(ax.get("name")))

    breathing = 14
    half_thick = _ROTATED_TITLE_THICKNESS_PX // 2

    for side in ("left", "right"):
        side_indices = [
            i for i, ax in enumerate(yaxes)
            if isinstance(ax, dict) and ax.get("position") == side
        ]
        if not side_indices:
            continue

        # First axis on each side anchors at offset=0 (unless author pinned).
        first_i = side_indices[0]
        first_spec = axis_specs[first_i] if first_i < len(axis_specs) else {}
        if not (isinstance(first_spec, dict)
                 and first_spec.get("_offset_explicit")):
            yaxes[first_i]["offset"] = 0

        cumulative = int(yaxes[first_i].get("offset") or 0)
        for k in range(1, len(side_indices)):
            i = side_indices[k]
            inner_i = side_indices[k - 1]
            spec = axis_specs[i] if i < len(axis_specs) else {}
            # Step needs to clear the INNER axis's labels plus (if it
            # has a rotated name) the rotated-title clearance, plus
            # breathing room before the outer axis line. When the
            # inner axis has no name, only the labels need clearing;
            # the step collapses to ``label_width + breathing`` which
            # is ~30 px tighter per stacked pair than when a title
            # is present.
            if has_names[inner_i]:
                computed_step = (name_gaps[inner_i]
                                  + half_thick + breathing)
            else:
                computed_step = label_widths[inner_i] + breathing + 8
            step = (max(user_step, computed_step)
                    if user_step_explicit else computed_step)
            cumulative += step
            if isinstance(spec, dict) and spec.get("_offset_explicit"):
                # Honor the author's pinned offset; don't override.
                cumulative = int(yaxes[i].get("offset") or cumulative)
            else:
                yaxes[i]["offset"] = cumulative

    # Apply per-axis nameGap (no offset addition; ECharts shifts the
    # axis line by ``offset`` and nameGap is measured FROM the line).
    for i, ax in enumerate(yaxes):
        if not isinstance(ax, dict):
            continue
        if ax.get("name"):
            ax["nameLocation"] = "middle"
            ax["nameGap"] = name_gaps[i]

    return label_widths


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _enumerate_series_names(
    df, mapping: Dict[str, Any]
) -> List[str]:
    """Pre-compute the series names that ``build_line`` will emit, so the
    multi-axis resolver can map names to axes before the series objects
    are constructed.
    """
    y = mapping.get("y")
    color = mapping.get("color")
    sd_col = mapping.get("strokeDash")

    if df is None:
        return [str(mapping.get("name", "series"))]

    if isinstance(y, (list, tuple)):
        return [str(c) for c in y]

    if color and color in df.columns:
        groups = _unique(_col_to_list(df, color))
        if sd_col is not None and sd_col in df.columns:
            sd_legend_on = bool(mapping.get("strokeDashLegend"))
            sd_domain = _unique(_col_to_list(df, sd_col))
            if sd_legend_on:
                # Cross-product names: "{group} \u2014 {sd_val}" per pair
                # that has at least one row in df.
                out: List[str] = []
                for cg in groups:
                    for sd_val in sd_domain:
                        sub = df[(df[color] == cg) & (df[sd_col] == sd_val)]
                        if len(sub):
                            out.append(f"{cg} \u2014 {sd_val}")
                return out
            return [str(g) for g in groups]
        return [str(g) for g in groups]
    return [str(y)]


def build_line(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    x = mapping.get("x"); y = mapping.get("y"); color = mapping.get("color")
    if not x or not y:
        raise ValueError("line: mapping requires 'x' and 'y'")

    opt = _base_option(ctx)
    x_axis = _time_axis_if_needed(df, x) if df is not None else {"type": "category"}
    x_type_override = mapping.get("x_type")
    if x_type_override in ("category", "value", "time", "ordinal"):
        x_axis["type"] = "category" if x_type_override == "ordinal" else x_type_override
    x_axis.setdefault("name", "")
    opt["xAxis"] = x_axis

    x_log = bool(mapping.get("x_log"))
    if x_log and opt["xAxis"].get("type") in ("value", "log"):
        opt["xAxis"]["type"] = "log"

    # ---- Resolve y-axes (1, 2, or N) via the multi-axis resolver -------
    series_names = _enumerate_series_names(df, mapping)
    axis_specs, series_to_axis = _resolve_axis_specs(mapping, series_names)
    materialized = [_materialize_axis_spec(s, i)
                     for i, s in enumerate(axis_specs)]

    # Color-code single-series axes so the rotated name, tick labels,
    # and axis line all match the series line color (Bloomberg-style).
    # Only kicks in for >=2 axes; a single-axis chart inherits the
    # default neutral styling so the chart doesn't read as monochrome.
    name_to_color = _series_name_to_color(series_names, ctx)
    color_coding_on = bool(mapping.get("axis_color_coding", True))
    if len(materialized) >= 2:
        _apply_axis_color_coding(
            materialized, axis_specs, name_to_color,
            enabled=color_coding_on,
        )

    # When 3+ axes are color-coded AND the series appear in the legend
    # (always true for multi_line), the rotated axis titles are
    # redundant with the legend row. A 4-axis chart at w:6 would
    # otherwise burn ~72 px on rotated titles (~18 px per axis) and
    # leave the plot at ~45 % of tile width. Author can opt back in
    # via ``mapping.axis_title_style = "rotated"``.
    title_style = str(mapping.get("axis_title_style") or "auto").lower()
    if (title_style == "auto"
            and len(materialized) >= 3
            and color_coding_on):
        for ax, spec in zip(materialized, axis_specs):
            ser_list = spec.get("series") or []
            if len(ser_list) == 1 and name_to_color.get(str(ser_list[0])):
                ax["name"] = ""
    elif title_style == "none":
        for ax in materialized:
            ax["name"] = ""

    if len(materialized) == 1:
        # Preserve the single-axis "yAxis: dict" shape (some downstream
        # paths -- y_format helper, layout sizers -- handle dicts and
        # lists differently and we'd rather not perturb the simple case).
        opt["yAxis"] = materialized[0]
    else:
        opt["yAxis"] = materialized
        # Capture the user-set grid.left/right floor BEFORE the initial
        # (conservative) pass inflates them. Both the initial pass and
        # the later ``_layout_multi_axis_dynamic`` pass use this floor
        # via ``max()``; without capturing here, the initial over-
        # reservation would cap the refined pass and dead space would
        # stick for the lifetime of the chart.
        _grid_left_floor = int(opt["grid"].get("left") or 76)
        _grid_right_floor = int(opt["grid"].get("right") or 20)
        # Initial grid sizing using the auto-stacked offsets from
        # _resolve_axis_specs. The post-data ``_layout_multi_axis_dynamic``
        # below will refine these once it has actual label widths.
        left_pad, right_pad = _grid_margins_for_axes(axis_specs)
        opt["grid"]["left"] = max(_grid_left_floor, left_pad + 16)
        opt["grid"]["right"] = max(_grid_right_floor, right_pad + 16)
        # Stash floors on opt so the refined pass picks them up without
        # having to thread them through the call signature.
        opt.setdefault("_qc_layout", {})["grid_left_floor"] = _grid_left_floor
        opt["_qc_layout"]["grid_right_floor"] = _grid_right_floor

    sd_col = mapping.get("strokeDash")
    sd_scale = mapping.get("strokeDashScale") or {}

    def _auto_dash_for(n: int, pos: int) -> Any:
        patterns = ["solid", "dashed", "dotted", [10, 5], [4, 4], [2, 2]]
        return patterns[pos % len(patterns)]

    def _dash_for(value: Any, domain: Sequence[Any]) -> Any:
        if sd_scale.get("domain") and sd_scale.get("range"):
            dom = list(sd_scale["domain"])
            rng = list(sd_scale["range"])
            if value in dom:
                idx = dom.index(value)
                if idx < len(rng):
                    return rng[idx]
        if value in list(domain):
            return _auto_dash_for(len(domain), list(domain).index(value))
        return "solid"

    series: List[Dict[str, Any]] = []
    legend_names: List[str] = []

    # Dense time-series (more than ~30 points) look cluttered with a dot
    # on every point; keep the symbol hidden by default and let ECharts
    # expose it on hover via emphasis.
    n_points = len(df) if df is not None else 0
    show_symbol_default = mapping.get("show_symbol")
    if show_symbol_default is None:
        show_symbol_default = n_points <= 30

    def _series_entry(name: str, data: Any,
                        dash: Any = None) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "type": "line", "name": name, "data": data,
            "showSymbol": bool(show_symbol_default),
            "symbolSize": 6,
            "emphasis": {"focus": "series", "scale": True},
            "lineStyle": {"width": 2},
        }
        if dash is not None:
            entry["lineStyle"]["type"] = dash
        axis_idx = series_to_axis.get(str(name), 0)
        if axis_idx > 0:
            entry["yAxisIndex"] = axis_idx
        return entry

    if df is None:
        data = mapping.get("data", [])
        name = mapping.get("name", "series")
        legend_names.append(name)
        series.append(_series_entry(name, data))
    else:
        _ensure_columns(df, [x], "line")
        if isinstance(y, (list, tuple)):
            _ensure_columns(df, list(y), "line")
            for i, col in enumerate(y):
                rows = _rows(df, [x, col])
                legend_names.append(col)
                dash = _auto_dash_for(len(y), i) if sd_col is None else None
                if sd_col is None:
                    dash = None  # default: solid for simple wide-form
                series.append(_series_entry(col, rows, dash=dash))
        elif color:
            _ensure_columns(df, [y, color], "line")
            if sd_col is not None:
                _ensure_columns(df, [sd_col], "line")
            color_groups = _unique(_col_to_list(df, color))
            palette_list = list(ctx.palette_colors) if ctx.palette_kind == "categorical" else []

            if sd_col is not None:
                sd_domain = _unique(_col_to_list(df, sd_col))
                sd_legend_on = bool(mapping.get("strokeDashLegend"))
                for ci, cg in enumerate(color_groups):
                    color_hex = palette_list[ci % len(palette_list)] if palette_list else None
                    for sd_val in sd_domain:
                        sub = df[(df[color] == cg) & (df[sd_col] == sd_val)]
                        if len(sub) == 0:
                            continue
                        rows = _rows(sub, [x, y])
                        name = f"{cg} \u2014 {sd_val}"
                        dash = _dash_for(sd_val, sd_domain)
                        entry = _series_entry(name, rows, dash=dash)
                        if color_hex is not None:
                            entry.setdefault("lineStyle", {})["color"] = color_hex
                            entry["itemStyle"] = {"color": color_hex}
                        series.append(entry)
                        if sd_legend_on:
                            legend_names.append(name)
                if not sd_legend_on:
                    legend_names.extend([str(g) for g in color_groups])
            else:
                for i, g in enumerate(color_groups):
                    sub = df[df[color] == g]
                    rows = _rows(sub, [x, y])
                    name = str(g)
                    legend_names.append(name)
                    series.append(_series_entry(name, rows))
        else:
            _ensure_columns(df, [y], "line")
            rows = _rows(df, [x, y])
            legend_names.append(str(y))
            series.append(_series_entry(str(y), rows))

    opt["series"] = series
    opt["legend"]["data"] = legend_names

    # Multi-axis charts: refine offsets / nameGaps now that the actual
    # series data is in opt and we can measure label widths instead of
    # relying on the conservative default step from _resolve_axis_specs.
    if isinstance(opt.get("yAxis"), list) and len(opt["yAxis"]) >= 2:
        label_widths = _layout_multi_axis_dynamic(opt, axis_specs, mapping)
        # Re-size grid margins using the per-axis label widths so we
        # reserve exactly enough room for each axis (rather than the
        # flat 70 px label_band fallback).
        left_pad, right_pad = _grid_margins_for_axes(
            axis_specs, label_widths=label_widths
        )
        # Use the ORIGINAL grid.left/right floor (captured before the
        # initial conservative pass). Without this, the initial pass's
        # over-reservation would cap the refined pass via max().
        qc_layout = opt.pop("_qc_layout", {})
        left_floor = int(qc_layout.get("grid_left_floor", 76))
        right_floor = int(qc_layout.get("grid_right_floor", 20))
        opt["grid"]["left"] = max(left_floor, left_pad + 16)
        opt["grid"]["right"] = max(right_floor, right_pad + 16)

    _apply_axis_titles(opt, mapping, horizontal=False)
    _apply_x_sort(opt, mapping, axis_key="xAxis")
    _apply_typography_to_axes(opt, ctx)
    return opt


def _grow_grid_for_legend(opt: Dict[str, Any], chart_width: int) -> None:
    """Push grid.top down when the legend wraps to multiple rows.

    The base option assumes a single 24-px legend row at top=42 and
    grid.top=80. With `legend.type="plain"` (no pagination), legends
    with many items wrap to multiple rows and would otherwise overlap
    the chart canvas. Estimate row count from the number of legend
    items + their average label length, and bump grid.top to clear.
    """
    legend = opt.get("legend") or {}
    if not legend.get("show", True):
        return
    items = legend.get("data") or []
    if not items:
        return
    # Estimate width per item: 14 px swatch + 4 px gap + 6.5 px/char
    # + 24 px right padding between items.
    avg_chars = sum(len(str(s)) for s in items) / max(1, len(items))
    px_per_item = 14 + 4 + (avg_chars * 6.5) + 24
    usable_w = max(200, int(chart_width) - 80)
    items_per_row = max(1, int(usable_w // px_per_item))
    rows = (len(items) + items_per_row - 1) // items_per_row
    if rows <= 1:
        return
    legend_row_h = 18
    extra = (rows - 1) * legend_row_h
    grid = opt.setdefault("grid", {})
    cur_top = grid.get("top", 80)
    if isinstance(cur_top, (int, float)):
        grid["top"] = int(cur_top) + extra


def _value_label_formatter(decimals: int) -> str:
    """JS formatter string for a bar / line / area value label.
    Handles None / NaN gracefully (returns '') and rounds to the
    requested decimals. Centralised here so every chart_type that
    enables show_values via this engine pass produces identical
    label formatting."""
    d = max(0, int(decimals))
    return (
        "function(p){"
        " var v = (p && p.data && typeof p.data === 'object' "
        " && 'value' in p.data) ? p.data.value : p.data;"
        " if (Array.isArray(v)) v = v[v.length - 1];"
        " if (v == null || (typeof v === 'number' && isNaN(v)))"
        "   return '';"
        f" return Number(v).toFixed({d});"
        "}"
    )


def build_bar(df, mapping: Dict[str, Any], ctx: BuilderContext, horizontal: bool = False) -> Dict[str, Any]:
    x = mapping.get("x"); y = mapping.get("y")
    # ``series`` is accepted as an alias for ``color`` (CC1 in the
    # 2026-05-11 audit -- the long-form grouped-bar shape that authors
    # naturally reach for: x=category, y=value_col, series=group_col).
    color = mapping.get("color") or mapping.get("series")
    if not x or not y:
        raise ValueError("bar: mapping requires 'x' and 'y'")

    # ``stack`` accepts truthy / falsy / a stack-group name. The
    # historical default was True (everything stacks); the audit
    # surfaced that grouped-bar authors reach for `series=...` and
    # expect side-by-side bars by default (NOT stacked). When `series`
    # is in play AND the author did not explicitly set `stack`, default
    # to grouped (stack=False) so the legend's per-group colors line
    # up with discrete bars rather than a single tall stack.
    if "stack" in mapping:
        stack_flag = mapping["stack"]
    elif color and "color" not in mapping and "series" in mapping:
        stack_flag = False
    else:
        stack_flag = True
    invert_y = bool(mapping.get("invert_y"))
    y_log = bool(mapping.get("y_log"))
    value_axis_type = "log" if y_log else "value"

    opt = _base_option(ctx)

    if horizontal:
        opt["xAxis"] = {"type": value_axis_type, "name": "",
                          "inverse": invert_y}
        opt["yAxis"] = {"type": "category", "name": "", "data": []}
        value_col = x
        category_col = y
    else:
        opt["xAxis"] = {"type": "category", "name": "", "data": []}
        opt["yAxis"] = {"type": value_axis_type, "name": "",
                          "inverse": invert_y}
        value_col = y
        category_col = x
    opt["tooltip"]["axisPointer"] = {"type": "shadow"}

    series: List[Dict[str, Any]] = []
    legend_names: List[str] = []

    # show_values (CC1 in the 2026-05-11 audit): when truthy, render
    # the value above each bar (or to the right for horizontal). The
    # decimals follow mapping.value_decimals (default 1 for compact
    # readability).
    #
    # Density-stagger guard (round 2 of the hardening pass, 2026-05-11
    # evening): when the x-axis category count is high enough that
    # labels would overlap horizontally, we apply two mitigations:
    #
    #   1. Density cap -- if cell width per bar < label width, drop
    #      labels entirely (mirror of the heatmap CC10 cell-fit guard).
    #      Authors who explicitly set value_decimals=0 get a relaxed
    #      threshold because the labels are narrower.
    #
    #   2. Stagger -- when not capped, alternate the label position
    #      between "top" and "bottom" (or "right"/"left" for horizontal)
    #      so adjacent labels don't pile up at the same y-coordinate.
    #      ECharts supports this via per-data-point label dicts but at
    #      the series level we use a JS formatter that keys off the
    #      data index. Simpler: set series-level alternating positions
    #      via two separate series passes is overkill; we use distance
    #      offset on the label which staggers visually without splitting
    #      the series. ECharts honors `label.distance` per cell; we
    #      stagger via a positive/negative offset baked into the
    #      formatter -- but the cleanest path is per-series alternation.
    #      Implemented here via per-bar label data on the series.
    show_values = bool(mapping.get("show_values"))
    value_decimals = mapping.get("value_decimals")
    if value_decimals is None:
        value_decimals = 1
    # Three-regime label policy: when the user explicitly asks for
    # value labels, we always render them, but at moderate density
    # we stagger adjacent labels above/below to break the horizontal
    # pile-up and at extreme density we shrink the font.
    n_cats = 0
    n_series_groups = 1
    if df is not None and category_col in df.columns:
        n_cats = len(_unique(_col_to_list(df, category_col)))
        if color and color in df.columns:
            n_series_groups = len(_unique(_col_to_list(df, color)))
    chart_w_for_density = int(getattr(ctx, "width", 700) or 700)
    bars_per_axis_pos = (n_cats * n_series_groups
                         if not stack_flag else n_cats)
    cell_w_estimate = (chart_w_for_density - 100) / max(1, bars_per_axis_pos)
    label_w_estimate = max(int(value_decimals) + 4, 4) * 6.5
    label_font = 10
    if cell_w_estimate < label_w_estimate * 0.6:
        label_font = 8
    elif cell_w_estimate < label_w_estimate:
        label_font = 9
    label_block: Optional[Dict[str, Any]] = None
    if show_values:
        label_position = ("right" if horizontal else "top")
        label_block = {
            "show": True,
            "position": label_position,
            "fontSize": label_font,
            "formatter": _value_label_formatter(int(value_decimals)),
        }
    # Stagger threshold: if the per-bar cell is narrower than 1.6x
    # the label width, alternate adjacent labels top/bottom so the
    # available label space doubles. The non-grouped, non-horizontal
    # case is the only one where stagger is unambiguous; grouped
    # bars already share the slot among multiple series.
    stagger_labels = (
        show_values
        and not horizontal
        and not color
        and bars_per_axis_pos >= 6
        and cell_w_estimate < (label_w_estimate * 1.6)
    )

    if df is None:
        data = mapping.get("data", [])
        name = mapping.get("name", "series")
        legend_names.append(name)
        if horizontal:
            opt["yAxis"]["data"] = [row[0] for row in data]
            vals = [row[1] for row in data]
        else:
            opt["xAxis"]["data"] = [row[0] for row in data]
            vals = [row[1] for row in data]
        s = {"type": "bar", "name": name, "data": vals}
        if label_block:
            s["label"] = label_block
        series.append(s)
    else:
        _ensure_columns(df, [x, y], "bar")
        if color:
            _ensure_columns(df, [color], "bar")
            cat_order = _unique(_col_to_list(df, category_col))
            if horizontal:
                opt["yAxis"]["data"] = list(cat_order)
            else:
                opt["xAxis"]["data"] = list(cat_order)
            groups = _unique(_col_to_list(df, color))
            stack_name = "total" if stack_flag else None
            for g in groups:
                sub = df[df[color] == g]
                lookup = dict(zip(_col_to_list(sub, category_col), _col_to_list(sub, value_col)))
                vals = [lookup.get(c) for c in cat_order]
                legend_names.append(str(g))
                s = {"type": "bar", "name": str(g), "data": vals,
                      "emphasis": {"focus": "series"}}
                if stack_name is not None:
                    s["stack"] = stack_name
                if label_block:
                    s["label"] = label_block
                series.append(s)
        else:
            cats = _col_to_list(df, category_col)
            vals = _col_to_list(df, value_col)
            if horizontal:
                opt["yAxis"]["data"] = cats
            else:
                opt["xAxis"]["data"] = cats
            legend_names.append(str(value_col))
            s = {"type": "bar", "name": str(value_col), "data": vals}
            if label_block:
                if stagger_labels:
                    # Per-cell label data: alternate top/bottom so
                    # neighbouring labels don't collide horizontally.
                    s["data"] = [
                        {
                            "value": v,
                            "label": {
                                **label_block,
                                "position": ("bottom" if (i % 2)
                                              else "top"),
                            },
                        }
                        for i, v in enumerate(vals)
                    ]
                else:
                    s["label"] = label_block
            series.append(s)

    opt["series"] = series
    opt["legend"]["data"] = legend_names

    if not horizontal:
        _autorotate_x_category_labels(opt, ctx)
    _apply_axis_titles(opt, mapping, horizontal=horizontal,
                        chart_width=ctx.width)
    _apply_x_sort(opt, mapping,
                    axis_key="yAxis" if horizontal else "xAxis")
    _apply_typography_to_axes(opt, ctx)
    return opt


def _linreg(xs: List[float], ys: List[float]) -> Optional[Tuple[float, float]]:
    """Simple OLS linear regression. Returns (slope, intercept) or None on
    degenerate input (fewer than 2 numeric points, or zero x-variance).
    """
    pts = [(a, b) for a, b in zip(xs, ys)
           if a is not None and b is not None
           and not (isinstance(a, float) and a != a)
           and not (isinstance(b, float) and b != b)]
    if len(pts) < 2:
        return None
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


# ---------------------------------------------------------------------------
# Shared analytics helpers (per-column transforms, regression stats)
#
# Used by build_correlation_matrix and build_scatter_studio in this module,
# and mirrored by _ccColumnTransform / _ccRegStats on the JS side
# (rendering.py). Keeping the names + semantics aligned lets compile-time
# previews and runtime studio drawers report identical numbers.
# ---------------------------------------------------------------------------

# Approximation of the calendar year span used for YoY transforms.
# Same convention as the JS-side _ccFindYearAgo. We don't try to be
# clock-perfect (no leap seconds, no business-day calendar) -- the
# nearest row at-or-before t-365d is fine for chart display.
_YEAR_SECONDS = 365 * 86400


def _is_finite(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return False
    if isinstance(v, float) and v != v:  # NaN
        return False
    if isinstance(v, float) and (v == float("inf") or v == float("-inf")):
        return False
    return isinstance(v, (int, float))


def _to_epoch_seconds(v: Any) -> Optional[float]:
    """Best-effort epoch-seconds parse for transform order keys.

    Accepts: pandas Timestamp / datetime / 'YYYY-MM-DD' / numeric.
    Returns None for unparseable cells so a single bad row degrades
    gracefully (its YoY value just becomes None).
    """
    if v is None:
        return None
    if isinstance(v, (int, float)) and _is_finite(v):
        return float(v)
    try:
        import pandas as pd
        ts = pd.to_datetime(v, errors="coerce")
        if pd.isna(ts):
            return None
        return float(ts.timestamp())
    except Exception:
        return None


def _rolling_mean_std(values: List[Optional[float]],
                        n: int) -> Tuple[List[Optional[float]],
                                          List[Optional[float]]]:
    """Compute rolling mean + sample-stdev of a value series with window n.
    Returns aligned (mean, std) lists. Population stdev uses (k-1) so the
    z-scores match what most analysts expect; falls back to None when
    the rolling window contains < 2 finite points.
    """
    means: List[Optional[float]] = [None] * len(values)
    stds:  List[Optional[float]] = [None] * len(values)
    if n < 2:
        return means, stds
    queue: List[float] = []
    sum_x = 0.0
    sum_xx = 0.0
    cnt = 0
    for i, v in enumerate(values):
        if _is_finite(v):
            f = float(v)
            queue.append(f); sum_x += f; sum_xx += f * f; cnt += 1
        else:
            queue.append(float("nan"))
        if len(queue) > n:
            old = queue.pop(0)
            if old == old:  # not NaN
                sum_x -= old; sum_xx -= old * old; cnt -= 1
        if len(queue) == n and cnt >= 2:
            m = sum_x / cnt
            var = max(0.0, (sum_xx - cnt * m * m) / (cnt - 1))
            means[i] = m
            stds[i] = var ** 0.5 if var > 0 else 0.0
    return means, stds


def _compute_transform(values: Sequence[Any],
                        times: Optional[Sequence[Any]],
                        transform: str) -> List[Optional[float]]:
    """Apply a per-column transform to a numeric series.

    Mirrors the JS-side _ccColumnTransform. ``times`` is a parallel list
    of order keys (timestamps, ints, ...); only required for the order-
    aware transforms (change / pct_change / yoy_pct / rolling_zscore_*).
    Returns a list of floats with None for rows where the transform is
    undefined (first row of pct_change, ln of non-positive, ...).
    """
    name = (transform or "raw").strip()
    n = len(values)
    if n == 0:
        return []
    raw: List[Optional[float]] = [
        float(v) if _is_finite(v) else None for v in values
    ]

    if name == "raw":
        return raw
    if name == "log":
        out: List[Optional[float]] = []
        import math
        for v in raw:
            out.append(math.log(v) if (v is not None and v > 0) else None)
        return out
    if name == "rank_pct":
        # Percentile rank in [0, 100]. Ties get the average rank.
        finite_idx = [i for i, v in enumerate(raw) if v is not None]
        finite_vals = sorted(((raw[i], i) for i in finite_idx),
                              key=lambda p: p[0])
        out2: List[Optional[float]] = [None] * n
        m = len(finite_vals)
        if m == 0:
            return out2
        # Average-rank handling: walk groups of equal values.
        i = 0
        while i < m:
            j = i
            while j + 1 < m and finite_vals[j + 1][0] == finite_vals[i][0]:
                j += 1
            # Indices i..j share the same value; assign the midpoint rank.
            avg_rank = (i + j) / 2.0  # 0-indexed
            pct = 100.0 * avg_rank / max(1, m - 1) if m > 1 else 50.0
            for k in range(i, j + 1):
                _, orig = finite_vals[k]
                out2[orig] = pct
            i = j + 1
        return out2
    if name == "zscore":
        finite = [v for v in raw if v is not None]
        if len(finite) < 2:
            return [None] * n
        mean = sum(finite) / len(finite)
        var = sum((v - mean) ** 2 for v in finite) / (len(finite) - 1)
        std = var ** 0.5 if var > 0 else 0.0
        if std == 0.0:
            return [None] * n
        return [None if v is None else (v - mean) / std for v in raw]

    # Order-aware transforms below.
    if name in ("change", "pct_change", "yoy_pct", "yoy_change") or \
            name.startswith("rolling_zscore_"):
        if times is None or len(times) != n:
            # No order column -> fall back to row order.
            time_list = [float(i) for i in range(n)]
        else:
            time_list = [_to_epoch_seconds(t) for t in times]

        if name in ("change", "pct_change"):
            out3: List[Optional[float]] = [None] * n
            for i in range(1, n):
                a, b = raw[i], raw[i - 1]
                if a is None or b is None:
                    continue
                if name == "change":
                    out3[i] = a - b
                else:
                    if b == 0:
                        continue
                    out3[i] = (a - b) / b * 100.0
            return out3

        if name in ("yoy_change", "yoy_pct"):
            out4: List[Optional[float]] = [None] * n
            # For each i, find largest j<i with time[j] <= time[i] - 365d.
            for i in range(n):
                ti = time_list[i] if time_list else None
                if ti is None or raw[i] is None:
                    continue
                target = ti - _YEAR_SECONDS
                lo, hi = 0, i
                best = -1
                while lo <= hi:
                    mid = (lo + hi) // 2
                    tm = time_list[mid]
                    if tm is None:
                        hi = mid - 1; continue
                    if tm <= target:
                        best = mid; lo = mid + 1
                    else:
                        hi = mid - 1
                if best < 0:
                    continue
                a, b = raw[i], raw[best]
                if a is None or b is None:
                    continue
                if name == "yoy_change":
                    out4[i] = a - b
                else:
                    if b == 0:
                        continue
                    out4[i] = (a - b) / b * 100.0
            return out4

        if name.startswith("rolling_zscore_"):
            try:
                window = int(name.split("_")[-1])
            except Exception:
                window = 252
            window = max(2, window)
            means, stds = _rolling_mean_std(raw, window)
            out5: List[Optional[float]] = [None] * n
            for i in range(n):
                v, m, s = raw[i], means[i], stds[i]
                if v is None or m is None or s is None or s == 0.0:
                    continue
                out5[i] = (v - m) / s
            return out5

    # Index = 100 (anchored at first non-null non-zero value).
    if name == "index100":
        anchor = None
        for v in raw:
            if v is not None and v != 0:
                anchor = v
                break
        if anchor is None:
            return list(raw)
        return [None if v is None else (v / anchor) * 100.0 for v in raw]

    raise ValueError(
        f"_compute_transform: unknown transform '{transform}'. "
        f"Supported: raw, log, change, pct_change, yoy_change, yoy_pct, "
        f"zscore, rolling_zscore_<N>, rank_pct, index100"
    )


# Suffix appended to formatted values for tooltip / axis title hints.
_TRANSFORM_AXIS_SUFFIX = {
    "raw": "",
    "log": " (ln)",
    "change": " (Δ)",
    "pct_change": " (%Δ)",
    "yoy_change": " (YoY Δ)",
    "yoy_pct": " (YoY %)",
    "zscore": " (z)",
    "rank_pct": " (pct rank)",
    "index100": " (index=100)",
}


def _transform_axis_suffix(name: str) -> str:
    if name and name.startswith("rolling_zscore_"):
        try:
            return f" (z, {int(name.split('_')[-1])}d)"
        except Exception:
            return " (rolling z)"
    return _TRANSFORM_AXIS_SUFFIX.get(name or "raw", "")


def _compute_regression_stats(xs: Sequence[Any],
                                ys: Sequence[Any]) -> Optional[Dict[str, Any]]:
    """OLS regression statistics for use by both correlation_matrix
    (per-pair sanity) and scatter_studio (drawn stats strip).

    Returns a dict with: n, slope, intercept, r, r2, rmse, se_slope,
    se_intercept, t_slope, p_slope. None when degenerate (n<2 or
    Sxx==0); the caller decides how to display the empty state.

    p_slope uses a normal-approximation tail (2*(1-Φ(|t|))) -- adequate
    for the display strip; we are not running econometric tests here.
    """
    pts: List[Tuple[float, float]] = []
    for a, b in zip(xs, ys):
        if not (_is_finite(a) and _is_finite(b)):
            continue
        pts.append((float(a), float(b)))
    n = len(pts)
    if n < 2:
        return None
    mean_x = sum(p[0] for p in pts) / n
    mean_y = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mean_x) ** 2 for p in pts)
    syy = sum((p[1] - mean_y) ** 2 for p in pts)
    sxy = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pts)
    if sxx <= 0:
        return {"n": n, "slope": None, "intercept": None, "r": None,
                "r2": None, "rmse": None, "se_slope": None,
                "se_intercept": None, "t_slope": None, "p_slope": None,
                "degenerate": "x_zero_variance"}
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    r = sxy / ((sxx * syy) ** 0.5) if syy > 0 else 0.0
    # Residual sum of squares.
    rss = sum((p[1] - (slope * p[0] + intercept)) ** 2 for p in pts)
    df = max(1, n - 2)
    rmse = (rss / df) ** 0.5
    se_slope = rmse / (sxx ** 0.5)
    # SE(intercept) = RMSE * sqrt(1/n + mean_x^2 / Sxx)
    se_intercept = rmse * (1.0 / n + (mean_x ** 2) / sxx) ** 0.5
    t_slope = slope / se_slope if se_slope > 0 else None
    p_slope = _two_sided_p(t_slope) if t_slope is not None else None
    return {"n": n, "slope": slope, "intercept": intercept,
            "r": r, "r2": r * r, "rmse": rmse,
            "se_slope": se_slope, "se_intercept": se_intercept,
            "t_slope": t_slope, "p_slope": p_slope}


def _two_sided_p(t: float) -> float:
    """Two-sided p-value via the normal approximation. For modest n (n>=30)
    this is within a couple of percentage points of the true t-distribution
    p-value; for small n we accept a slight conservative bias.
    """
    import math
    # 1 - Φ(|t|) using erfc:  P(Z>x) = 0.5 * erfc(x/sqrt(2))
    abs_t = abs(t)
    return float(math.erfc(abs_t / (2 ** 0.5)))


def _trendline_series(name: str, xs: List[float], ys: List[float],
                        color_hex: Optional[str] = None,
                        y_axis_index: int = 0) -> Optional[Dict[str, Any]]:
    reg = _linreg(xs, ys)
    if reg is None:
        return None
    slope, intercept = reg
    xmin = min(v for v in xs if v is not None)
    xmax = max(v for v in xs if v is not None)
    data = [[xmin, slope * xmin + intercept],
            [xmax, slope * xmax + intercept]]
    entry: Dict[str, Any] = {
        "type": "line", "name": name, "data": data,
        "showSymbol": False, "smooth": False,
        "lineStyle": {"type": "dashed", "width": 1.5,
                        "color": color_hex} if color_hex else
                      {"type": "dashed", "width": 1.5},
        "emphasis": {"focus": "none"},
        "tooltip": {"show": False},
        "silent": True,
    }
    if y_axis_index:
        entry["yAxisIndex"] = y_axis_index
    return entry


_SCATTER_SIZE_PX_MIN_DEFAULT = 6
_SCATTER_SIZE_PX_MAX_DEFAULT = 28


def _resolve_size_scale(
    df, size_col: str, mapping: Dict[str, Any],
) -> Tuple[float, float, float, float]:
    """Compute the data-space (val_lo, val_hi) and pixel-space (px_min, px_max)
    extents for a scatter ``size`` mapping.

    The data-space range defaults to robust 5th/95th percentile of the
    finite numeric values in ``df[size_col]`` so a single outlier can't
    crush the rest of the points into one pixel. Authors can pin the
    range explicitly via ``mapping.size_lo`` / ``mapping.size_hi`` (in
    data units) or override the pixel range via ``mapping.size_min`` /
    ``mapping.size_max`` (in CSS pixels).

    When the column is constant or has fewer than two finite values,
    ``val_lo == val_hi`` and the caller emits a constant pixel size.
    """
    import math

    raw = _col_to_list(df, size_col)
    nums: List[float] = []
    for v in raw:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isnan(f) or math.isinf(f):
            continue
        nums.append(f)

    px_min = float(mapping.get("size_min", _SCATTER_SIZE_PX_MIN_DEFAULT))
    px_max = float(mapping.get("size_max", _SCATTER_SIZE_PX_MAX_DEFAULT))
    if px_max < px_min:
        px_min, px_max = px_max, px_min
    if px_min < 1:
        px_min = 1.0

    has_lo_pin = "size_lo" in mapping and mapping["size_lo"] is not None
    has_hi_pin = "size_hi" in mapping and mapping["size_hi"] is not None
    if has_lo_pin or has_hi_pin:
        default_lo = float(min(nums)) if nums else 0.0
        default_hi = float(max(nums)) if nums else 1.0
        val_lo = float(mapping["size_lo"]) if has_lo_pin else default_lo
        val_hi = float(mapping["size_hi"]) if has_hi_pin else default_hi
    elif len(nums) < 2:
        v = float(nums[0]) if nums else 0.0
        val_lo = val_hi = v
    else:
        ns = sorted(nums)
        n = len(ns)
        lo_i = max(0, min(n - 1, int(round(n * 0.05))))
        hi_i = max(0, min(n - 1, int(round(n * 0.95))))
        val_lo = float(ns[lo_i])
        val_hi = float(ns[hi_i])
        if val_hi <= val_lo:
            val_lo = float(ns[0])
            val_hi = float(ns[-1])

    return val_lo, val_hi, px_min, px_max


def _scatter_size_formula(
    val_lo: float, val_hi: float, px_min: float, px_max: float,
) -> Union[str, float]:
    """Emit the ``symbolSize`` value for a scatter series with a size column.

    Returns a constant pixel size (rounded mid of the px range) when the
    data-space extents are degenerate. Otherwise returns a JS function
    string that linearly interpolates ``val[2]`` from
    ``[val_lo, val_hi]`` onto ``[px_min, px_max]`` with both ends
    clamped. NaN / null values fall back to ``px_min``.
    """
    val_lo = float(val_lo)
    val_hi = float(val_hi)
    px_min = float(px_min)
    px_max = float(px_max)
    if val_hi <= val_lo:
        return float(round((px_min + px_max) / 2.0, 3))
    return (
        "function(val){"
        f"var v = val && val[2]; var lo = {val_lo}; var hi = {val_hi};"
        f"var pmin = {px_min}; var pmax = {px_max};"
        "if (v === null || v === undefined || isNaN(v)) return pmin;"
        "var t = (v - lo) / (hi - lo);"
        "if (t < 0) t = 0; if (t > 1) t = 1;"
        "return pmin + t * (pmax - pmin);"
        "}"
    )


def build_scatter(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    x = mapping.get("x"); y = mapping.get("y")
    color = mapping.get("color")
    size = mapping.get("size")
    trendline = bool(mapping.get("trendline"))
    trendlines = bool(mapping.get("trendlines"))
    if not x or not y:
        raise ValueError("scatter: mapping requires 'x' and 'y'")

    invert_y = bool(mapping.get("invert_y"))
    y_log = bool(mapping.get("y_log"))
    x_log = bool(mapping.get("x_log"))
    y_type = "log" if y_log else "value"
    x_type = ("log" if x_log else
                (_time_axis_if_needed(df, x)["type"] if df is not None else "value"))

    opt = _base_option(ctx)
    opt["tooltip"]["trigger"] = "item"
    opt["xAxis"] = {"type": x_type, "name": ""}
    opt["yAxis"] = {"type": y_type, "name": "", "inverse": invert_y}

    series: List[Dict[str, Any]] = []
    legend_names: List[str] = []

    if df is None:
        data = mapping.get("data", [])
        legend_names.append("series")
        series.append({"type": "scatter", "name": "series", "data": data,
                        "symbolSize": 10})
    else:
        _ensure_columns(df, [x, y], "scatter")
        cols = [x, y]
        size_formula: Union[str, float] = 10
        if size:
            _ensure_columns(df, [size], "scatter")
            val_lo, val_hi, px_min, px_max = _resolve_size_scale(
                df, size, mapping
            )
            size_formula = _scatter_size_formula(
                val_lo, val_hi, px_min, px_max
            )
        if color:
            _ensure_columns(df, [color], "scatter")
            groups = _unique(_col_to_list(df, color))
            palette = list(ctx.palette_colors) if ctx.palette_kind == "categorical" else []
            for gi, g in enumerate(groups):
                sub = df[df[color] == g]
                rows = _rows(sub, cols + ([size] if size else []))
                legend_names.append(str(g))
                s = {"type": "scatter", "name": str(g), "data": rows,
                      "emphasis": {"focus": "series"}}
                if size:
                    s["symbolSize"] = size_formula
                else:
                    s["symbolSize"] = 10
                series.append(s)
                if trendlines:
                    xs = [r[0] for r in rows if isinstance(r[0], (int, float))]
                    ys = [r[1] for r in rows if isinstance(r[1], (int, float))]
                    group_color = palette[gi % len(palette)] if palette else None
                    tl = _trendline_series(f"{g} trend", xs, ys,
                                              color_hex=group_color)
                    if tl is not None:
                        series.append(tl)
        else:
            rows = _rows(df, cols + ([size] if size else []))
            legend_names.append(str(y))
            s = {"type": "scatter", "name": str(y), "data": rows,
                  "symbolSize": 10}
            if size:
                s["symbolSize"] = size_formula
            series.append(s)

        if trendline and not trendlines:
            rows = _rows(df, [x, y])
            xs = [r[0] for r in rows if isinstance(r[0], (int, float))]
            ys = [r[1] for r in rows if isinstance(r[1], (int, float))]
            tl = _trendline_series("trend", xs, ys)
            if tl is not None:
                series.append(tl)
                legend_names.append("trend")

    opt["series"] = series
    opt["legend"]["data"] = legend_names

    _apply_axis_titles(opt, mapping, horizontal=False)
    _apply_typography_to_axes(opt, ctx)
    return opt


# Default transform menu the studio drawer offers when the spec doesn't
# pin a curated list. Mirrors the JS _ccStudioTransformOptions list.
_DEFAULT_STUDIO_TRANSFORMS: List[str] = [
    "raw", "log", "change", "pct_change", "yoy_pct",
    "zscore", "rolling_zscore_252", "rank_pct",
]


def _studio_resolve_defaults(
    df, mapping: Dict[str, Any]
) -> Dict[str, Any]:
    """Resolve the initial X/Y/color/size column choices for a scatter
    studio. Returns a dict the builder + the JS runtime both consume.
    Falls back to the first numeric columns when the author didn't pin
    explicit defaults; never invents columns that aren't in the dataset.
    """
    import pandas as pd
    cols = list(df.columns) if df is not None else []
    numeric_cols = [
        c for c in cols
        if df is not None and pd.api.types.is_numeric_dtype(df[c])
    ]

    def _norm_list(key: str) -> Optional[List[str]]:
        raw = mapping.get(key)
        if raw is None:
            return None
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, (list, tuple)):
            out = [str(c) for c in raw if isinstance(c, str)]
            return out or None
        return None

    x_cols = _norm_list("x_columns") or numeric_cols
    y_cols = _norm_list("y_columns") or numeric_cols
    color_cols = _norm_list("color_columns") or []
    size_cols = _norm_list("size_columns") or []

    def _pick(default_key: str, lst: List[str], fallback: Optional[str]):
        v = mapping.get(default_key)
        if isinstance(v, str) and (not lst or v in lst):
            return v
        if fallback and (not lst or fallback in lst):
            return fallback
        return lst[0] if lst else None

    x_default = _pick("x_default", x_cols,
                        x_cols[0] if x_cols else None)
    # Prefer a different column for y_default than x_default when one
    # is available -- a chart of x against itself is a degenerate
    # diagonal that's almost certainly not what the author wants.
    y_fallback = None
    if y_cols:
        y_fallback = next(
            (c for c in y_cols if c != x_default), y_cols[0]
        )
    y_default = _pick("y_default", y_cols, y_fallback)
    color_default = _pick("color_default", color_cols,
                            None) if color_cols else None
    size_default = _pick("size_default", size_cols,
                           None) if size_cols else None

    return {
        "x_columns": list(x_cols),
        "y_columns": list(y_cols),
        "color_columns": list(color_cols),
        "size_columns": list(size_cols),
        "x_default": x_default,
        "y_default": y_default,
        "color_default": color_default,
        "size_default": size_default,
    }


def build_scatter_studio(df, mapping: Dict[str, Any],
                           ctx: BuilderContext) -> Dict[str, Any]:
    """Exploratory scatter widget: viewer picks X / Y / color / size /
    per-axis transform / window / regression at runtime via the per-
    chart controls drawer. The Python builder produces a sensible
    initial render against the author's defaults; the JS-side studio
    rebuilds the option whenever the viewer changes a knob.

    Mapping keys (all optional unless noted):
        x_columns / y_columns          numeric column whitelists for the
                                          axis dropdowns. Default: every
                                          numeric column in the dataset.
        color_columns                  optional categorical group
                                          dropdown. Default: empty
                                          (no color group selector).
        size_columns                   optional bubble-size dropdown.
        x_default / y_default          initial axis columns. Default:
                                          first / second numeric columns.
        color_default / size_default   initial color / size selections.
        order_by                       sort key for order-aware
                                          transforms (pct_change /
                                          yoy_pct / rolling_zscore_*).
                                          Default: first datetime-like
                                          column in df, else row order.
        label_column                   row label used by click_popup
                                          and tooltip rows. Default:
                                          ``order_by`` if present.
        x_transform_default / y_transform_default
                                          initial transforms (default
                                          'raw').

    studio block on the spec (sibling to ``mapping``, optional):
        transforms                     curated list of transform names
                                          to expose; default is the
                                          full set.
        regression                     list of regression options; one
                                          of {'off', 'ols',
                                          'ols_per_group'}. Default
                                          ['off', 'ols', 'ols_per_group'].
        windows                        list of window options. Default
                                          ['all', '252d', '504d', '5y'].
        outliers                       list of outlier-filter options.
                                          Default ['off', 'iqr_3', 'z_4'].
        show_stats                     bool (default true) -- whether to
                                          display the regression stats
                                          strip below the canvas.

    The builder embeds a ``_studio`` block in the returned option. The
    runtime JS keys off ``opt._studio`` to wire the drawer dropdowns
    and recompute the option on every drawer change.
    """
    if df is None:
        raise ValueError("scatter_studio: DataFrame is required")

    # CC1 in the 2026-05-11 audit: accept the simple-mapping aliases
    # authors naturally reach for (`size=<col>`, `label=<col>`,
    # `regression=True`) as sugar for the explicit
    # studio-block / *_default plumbing the builder uses internally.
    # Authors who already pass the long form are unaffected.
    mapping = dict(mapping)
    if "size" in mapping and not mapping.get("size_default"):
        mapping["size_default"] = mapping["size"]
        if not mapping.get("size_columns"):
            mapping["size_columns"] = [mapping["size"]]
    if "label" in mapping and not mapping.get("label_column"):
        mapping["label_column"] = mapping["label"]
    if "color" in mapping and not mapping.get("color_default"):
        mapping["color_default"] = mapping["color"]
        if not mapping.get("color_columns"):
            mapping["color_columns"] = [mapping["color"]]
    if mapping.get("regression") is True:
        studio_cfg = dict(mapping.get("studio") or {})
        studio_cfg.setdefault("regression_default", "ols")
        mapping["studio"] = studio_cfg

    resolved = _studio_resolve_defaults(df, mapping)
    if not resolved["x_columns"]:
        raise ValueError(
            "scatter_studio: no numeric columns available to plot. "
            "Provide x_columns explicitly or ensure the dataset has "
            "at least one numeric column."
        )
    if not resolved["y_columns"]:
        raise ValueError(
            "scatter_studio: y_columns whitelist resolved to empty"
        )
    x_default = resolved["x_default"]
    y_default = resolved["y_default"]

    # Validate that every whitelisted column actually exists in df.
    all_refs = (resolved["x_columns"] + resolved["y_columns"]
                + resolved["color_columns"] + resolved["size_columns"])
    _ensure_columns(df, _unique([c for c in all_refs if c]),
                      "scatter_studio")

    # Resolve order_by for time-aware transforms.
    order_by = mapping.get("order_by")
    if order_by and order_by not in df.columns:
        raise ValueError(
            f"scatter_studio: order_by='{order_by}' is not a column in "
            f"the dataset (columns: {list(df.columns)})"
        )
    if order_by is None:
        import pandas as pd
        for c in df.columns:
            try:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    order_by = c
                    break
            except Exception:
                continue

    label_col = mapping.get("label_column") or order_by

    x_transform = (mapping.get("x_transform_default") or "raw").lower()
    y_transform = (mapping.get("y_transform_default") or "raw").lower()

    studio_cfg = mapping.get("studio") or {}
    transforms = studio_cfg.get("transforms") or _DEFAULT_STUDIO_TRANSFORMS
    transforms = [t for t in transforms if isinstance(t, str)]
    if "raw" not in transforms:
        transforms = ["raw"] + transforms

    regression_opts = studio_cfg.get("regression") or [
        "off", "ols", "ols_per_group"
    ]
    regression_default = studio_cfg.get("regression_default") or "off"
    if regression_default not in regression_opts:
        regression_default = regression_opts[0] if regression_opts else "off"

    window_opts = studio_cfg.get("windows") or ["all", "252d", "504d", "5y"]
    window_default = studio_cfg.get("window_default") or "all"
    if window_default not in window_opts:
        window_default = "all"

    outlier_opts = studio_cfg.get("outliers") or ["off", "iqr_3", "z_4"]
    outlier_default = studio_cfg.get("outlier_default") or "off"
    if outlier_default not in outlier_opts:
        outlier_default = "off"

    show_stats = studio_cfg.get("show_stats", True)

    # ------------------------------------------------------------------
    # Compile-time render: produce a scatter option from the defaults so
    # the chart looks reasonable BEFORE the viewer touches the drawer.
    # The JS side will rebuild this option on every drawer change.
    # ------------------------------------------------------------------
    inner_mapping: Dict[str, Any] = {
        "x": x_default, "y": y_default,
    }
    # Compute transformed series for the initial render.
    def _series_for_initial() -> Tuple[List[Any], List[Any]]:
        if order_by and order_by in df.columns:
            sorted_df = df.sort_values(order_by, kind="mergesort")
            time_seq = _col_to_list(sorted_df, order_by)
            data_df = sorted_df
        else:
            time_seq = None
            data_df = df
        x_raw = _col_to_list(data_df, x_default)
        y_raw = _col_to_list(data_df, y_default)
        x_t = _compute_transform(x_raw, time_seq, x_transform)
        y_t = _compute_transform(y_raw, time_seq, y_transform)
        if resolved["color_default"]:
            cvals = _col_to_list(data_df, resolved["color_default"])
        else:
            cvals = [None] * len(x_t)
        if resolved["size_default"]:
            sz = _col_to_list(data_df, resolved["size_default"])
        else:
            sz = [None] * len(x_t)
        return x_t, y_t, cvals, sz

    x_vals, y_vals, c_vals, s_vals = _series_for_initial()

    # Build series list -- one per group when color_default is set.
    palette_list = list(ctx.palette_colors) if ctx.palette_kind == "categorical" else []
    series: List[Dict[str, Any]] = []
    legend_names: List[str] = []
    if resolved["color_default"]:
        groups = _unique([g for g in c_vals if g is not None])
        for gi, g in enumerate(groups):
            rows: List[List[Any]] = []
            for xv, yv, cv, sz in zip(x_vals, y_vals, c_vals, s_vals):
                if cv != g:
                    continue
                if xv is None or yv is None:
                    continue
                row = [xv, yv]
                if resolved["size_default"]:
                    row.append(sz)
                rows.append(row)
            color_hex = palette_list[gi % len(palette_list)] if palette_list else None
            entry: Dict[str, Any] = {
                "type": "scatter", "name": str(g), "data": rows,
                "symbolSize": 10,
            }
            if resolved["size_default"]:
                entry["symbolSize"] = (
                    "function(val){ return Math.sqrt(Math.abs(val[2] || 1)) * 4; }"
                )
            if color_hex:
                entry["itemStyle"] = {"color": color_hex}
            series.append(entry)
            legend_names.append(str(g))
    else:
        rows: List[List[Any]] = []
        for xv, yv, sz in zip(x_vals, y_vals, s_vals):
            if xv is None or yv is None:
                continue
            row = [xv, yv]
            if resolved["size_default"]:
                row.append(sz)
            rows.append(row)
        entry = {
            "type": "scatter", "name": str(y_default), "data": rows,
            "symbolSize": 10,
        }
        if resolved["size_default"]:
            entry["symbolSize"] = (
                "function(val){ return Math.sqrt(Math.abs(val[2] || 1)) * 4; }"
            )
        series.append(entry)
        legend_names.append(str(y_default))

    opt = _base_option(ctx)
    opt["tooltip"]["trigger"] = "item"
    x_suffix = _transform_axis_suffix(x_transform)
    y_suffix = _transform_axis_suffix(y_transform)
    # Center axis names below / left of the axis line so they don't get
    # clipped by the default 20 px grid margins (ECharts puts xAxis.name
    # at the end of the axis by default, which truncates "us_10y" to
    # "y" inside a tight grid). 'middle' + nameGap gives a stable layout.
    opt["xAxis"] = {"type": "value",
                      "name": (x_default or "") + x_suffix,
                      "nameLocation": "middle",
                      "nameGap": 28,
                      "scale": True}
    opt["yAxis"] = {"type": "value",
                      "name": (y_default or "") + y_suffix,
                      "nameLocation": "middle",
                      "nameGap": 48,
                      "scale": True}
    opt["series"] = series
    opt["legend"]["data"] = legend_names
    # Studio chart needs more bottom padding to clear the axis-name strip
    # we add below.
    opt["grid"]["bottom"] = max(int(opt["grid"].get("bottom", 84)), 60)

    _apply_typography_to_axes(opt, ctx)

    # ------------------------------------------------------------------
    # Embed the studio config so the runtime drawer can wire dropdowns
    # and recompute the option on every change. ECharts ignores
    # unknown top-level fields; the JS side reads opt._studio off
    # SPECS[cid] (which preserves the field verbatim).
    # ------------------------------------------------------------------
    opt["_studio"] = {
        "x_columns":      resolved["x_columns"],
        "y_columns":      resolved["y_columns"],
        "color_columns":  resolved["color_columns"],
        "size_columns":   resolved["size_columns"],
        "x_default":      x_default,
        "y_default":      y_default,
        "color_default":  resolved["color_default"],
        "size_default":   resolved["size_default"],
        "order_by":       order_by,
        "label_column":   label_col,
        "transforms":     list(transforms),
        "x_transform_default": x_transform,
        "y_transform_default": y_transform,
        "regression_options":  list(regression_opts),
        "regression_default":  regression_default,
        "window_options":      list(window_opts),
        "window_default":      window_default,
        "outlier_options":     list(outlier_opts),
        "outlier_default":     outlier_default,
        "show_stats":          bool(show_stats),
    }
    return opt


def build_area(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    opt = build_line(df, mapping, ctx)
    for s in opt["series"]:
        s["areaStyle"] = {"opacity": 0.45}
        s["stack"] = "total"
        s["emphasis"] = {"focus": "series"}
        s["showSymbol"] = False
    return opt


# =============================================================================
# Heatmap shared helpers (color resolution, label formatting, auto-contrast)
# =============================================================================
#
# Heatmap-style charts (`heatmap`, `correlation_matrix`, `calendar_heatmap`)
# share three concerns that benefit from one source of truth:
#
#   1. Color stops -- author can override via mapping.colors (raw list) or
#      mapping.color_palette (palette name). Otherwise the ctx-resolved
#      palette is used. Final fallback is a sky-to-navy ramp.
#   2. Visual-map range -- the visualMap min/max can be pinned via
#      mapping.value_min / mapping.value_max so cell colors stay
#      interpretable across reruns with different data spreads.
#   3. Cell labels -- values shown on each cell with auto black/white
#      contrast text against the cell's resolved background color.
#
# Auto-contrast is implemented via ECharts rich-text styling:
# ``label.rich`` defines two named styles (``l`` for light backgrounds
# / dark text and ``d`` for dark backgrounds / light text), and the
# formatter is a JS function that picks the style per-cell based on
# the WCAG sRGB relative luminance of ``params.color`` (the cell's
# visualMap-resolved color). This works because ECharts evaluates the
# label.formatter dynamically per-cell and rich-text style names are
# resolved on the spot. ECharts heatmap series do NOT evaluate
# ``label.color`` as a callback -- that path is static-only -- which
# is why we route the conditional color through rich text instead.
#
# The rendering path revives ``function(...)`` strings into real JS
# functions before ``setOption()``.

# Names of the rich-text styles used by the auto-contrast formatter.
_HEATMAP_RICH_LIGHT = "l"   # light bg -> dark text
_HEATMAP_RICH_DARK = "d"    # dark bg  -> light text


def _heatmap_auto_contrast_formatter(decimals: int, value_idx: int = 2) -> str:
    """JS formatter that returns rich-text wrapped values with the
    appropriate ``{l|...}`` / ``{d|...}`` style based on the cell's
    background luminance. Use together with ``label.rich`` defining
    ``l`` and ``d`` styles.

    Handles ``[xIdx, yIdx, val]`` arrays (regular heatmap), ``[date,
    val]`` arrays (calendar_heatmap via ``value_idx=1``), and
    ``{value: [...]}`` cell-data wrappers.

    ``decimals`` is clamped to ``MAX_DASHBOARD_DECIMALS`` so callers
    that thread an oversized ``value_decimals`` still produce a
    formatter capped at 2 decimals.
    """
    decimals = clamp_decimals(decimals, default=decimals)
    return (
        "function(p){"
        "var v=null;var d=p&&p.data;"
        "if(d!=null&&d.value!=null){"
        f"v=Array.isArray(d.value)?d.value[{value_idx}]:d.value;"
        "}else if(Array.isArray(d)){"
        f"v=d[{value_idx}];"
        "}else if(d!=null){v=d;}"
        "if(v==null||isNaN(+v))return '';"
        "var c=p&&p.color;var r=128,g=128,b=128;"
        "if(typeof c==='string'){"
        "if(c.charAt(0)==='#'){"
        "if(c.length===4){r=parseInt(c.charAt(1)+c.charAt(1),16);"
        "g=parseInt(c.charAt(2)+c.charAt(2),16);"
        "b=parseInt(c.charAt(3)+c.charAt(3),16);}"
        "else if(c.length>=7){r=parseInt(c.substr(1,2),16);"
        "g=parseInt(c.substr(3,2),16);b=parseInt(c.substr(5,2),16);}"
        "}else if(c.indexOf('rgb')===0){"
        "var m=c.match(/[\\d\\.]+/g);"
        "if(m&&m.length>=3){r=+m[0];g=+m[1];b=+m[2];}}"
        "}"
        "function _L(x){x/=255;return x<=0.03928?x/12.92:"
        "Math.pow((x+0.055)/1.055,2.4);}"
        "var L=0.2126*_L(r)+0.7152*_L(g)+0.0722*_L(b);"
        f"var s=L>0.5?'{_HEATMAP_RICH_LIGHT}':'{_HEATMAP_RICH_DARK}';"
        f"return '{{'+s+'|'+(+v).toFixed({int(decimals)})+'}}';"
        "}"
    )


def _resolve_heatmap_colors(
    mapping: Dict[str, Any],
    ctx: BuilderContext,
    *,
    fallback: Optional[List[str]] = None,
) -> List[str]:
    """Resolve color stops for a heatmap-style visualMap.

    Resolution order (first match wins):
        1. ``mapping.colors`` -- explicit list of hex / rgb strings
        2. ``mapping.color_palette`` -- palette name from PALETTES
        3. ``mapping.color_scale`` (``sequential`` | ``diverging``)
           when no palette resolves -- maps to gs_blues / gs_diverging
        4. ``ctx.palette_colors`` when ctx.palette_kind != categorical
        5. ``fallback`` if provided, else a sky-to-navy default
    """
    raw_colors = mapping.get("colors")
    if isinstance(raw_colors, (list, tuple)) and len(raw_colors) >= 2:
        return [str(c) for c in raw_colors]

    palette_name = mapping.get("color_palette") or mapping.get("colors_palette")
    if isinstance(palette_name, str) and palette_name:
        cols = palette_colors_safe(palette_name)
        if cols:
            return list(cols)

    color_scale = (mapping.get("color_scale") or "").lower()
    if color_scale == "diverging":
        cols = palette_colors_safe("gs_diverging")
        if cols:
            return list(cols)
    if color_scale == "sequential":
        cols = palette_colors_safe("gs_blues")
        if cols:
            return list(cols)

    if ctx.palette_colors and ctx.palette_kind != "categorical":
        return list(ctx.palette_colors)

    if fallback:
        return list(fallback)
    return ["#F5F8FC", "#9BB4D4", "#305890", "#002F6C"]


def _resolve_heatmap_value_range(
    mapping: Dict[str, Any],
    vals: Sequence[Any],
    *,
    diverging_around_zero: bool = False,
) -> Tuple[float, float]:
    """Resolve the visualMap [min, max] for a heatmap.

    Honors ``mapping.value_min`` / ``mapping.value_max`` overrides; falls
    back to data extremes (or 0..1 when no finite values exist). When
    ``diverging_around_zero`` is true (auto-mode for cross-zero data),
    pads the range symmetrically so the diverging palette anchors at 0.
    """
    finite = [float(v) for v in vals if _is_finite(v)]
    if finite:
        v_min, v_max = min(finite), max(finite)
    else:
        v_min, v_max = 0.0, 1.0
    if v_min == v_max:
        # Avoid a degenerate visualMap that paints every cell the same
        # color (and breaks calculable). Pad by 1 in both directions.
        v_min -= 1.0
        v_max += 1.0
    if diverging_around_zero:
        m = max(abs(v_min), abs(v_max))
        v_min, v_max = -m, m

    user_min = mapping.get("value_min")
    user_max = mapping.get("value_max")
    if isinstance(user_min, (int, float)):
        v_min = float(user_min)
    if isinstance(user_max, (int, float)):
        v_max = float(user_max)
    return v_min, v_max


def _auto_value_decimals(vals: Sequence[Any]) -> int:
    """Pick a sensible default decimal count for heatmap cell labels
    based on the magnitude of the values. Large counts -> 0 decimals;
    sub-unit values lose precision but stay within the global
    ``MAX_DASHBOARD_DECIMALS`` cap (any "natural" 3rd decimal would
    silently get rounded off downstream anyway, so we surface the cap
    here instead of pretending we have more precision).
    """
    finite = [abs(float(v)) for v in vals if _is_finite(v)]
    if not finite:
        return 1
    m = max(finite)
    if m >= 100:
        return 0
    if m >= 10:
        return 1
    return clamp_decimals(2, default=2)


def _heatmap_value_formatter(decimals: int, value_idx: int = 2) -> str:
    """Return a JS function string that formats a heatmap cell label.

    Handles both ``[xIdx, yIdx, value]`` arrays (regular heatmap) and
    ``[date, value]`` arrays (calendar_heatmap) via the configurable
    ``value_idx``. Resilient to ``{value: [...]}`` cell-data wrappers.
    Returns an empty string for null / NaN values so blank cells look
    intentionally empty rather than printing ``"NaN"``.

    ``decimals`` is clamped to ``MAX_DASHBOARD_DECIMALS``.
    """
    decimals = clamp_decimals(decimals, default=decimals)
    return (
        "function(p){"
        "var v=null;var d=p&&p.data;"
        "if(d!=null&&d.value!=null){"
        f"v=Array.isArray(d.value)?d.value[{value_idx}]:d.value;"
        "}else if(Array.isArray(d)){"
        f"v=d[{value_idx}];"
        "}else if(d!=null){v=d;}"
        "if(v==null||isNaN(+v))return '';"
        f"return (+v).toFixed({int(decimals)});"
        "}"
    )


def _heatmap_cells_fit_labels(
    n_x: int,
    n_y: int,
    vals: Sequence[Any],
    decimals: int,
    font_size: int,
    chart_width: int,
    chart_height: int,
) -> bool:
    """Return True iff cell area is large enough to legibly hold the
    formatted value labels at the given font size. Conservative
    estimate: assumes monospace-ish 0.55 em char width.

    Used as a cell-fit guard inside ``build_heatmap`` and
    ``build_correlation_matrix`` so dense matrices auto-disable
    ``show_values`` (CC10 in the 2026-05-11 ugliness audit). Authors
    that explicitly set ``mapping.show_values=True`` bypass this guard
    -- the guard only applies to the engine default.
    """
    if n_x <= 0 or n_y <= 0 or chart_width <= 0:
        return True
    sample_w = max(int(decimals) + 4, 5)
    if vals:
        try:
            sample_w = max(
                len(f"{float(v):.{int(decimals)}f}")
                for v in vals[:64] if _is_finite(v)
            )
        except Exception:
            pass
    # Subtract chrome reservation (visualMap, axis labels, padding)
    usable_w = max(120, int(chart_width) - 96)
    usable_h = max(80, int(chart_height or chart_width // 2) - 60)
    cell_w = usable_w / max(1, n_x)
    cell_h = usable_h / max(1, n_y)
    label_w_px = sample_w * font_size * 0.55
    label_h_px = font_size * 1.25
    return cell_w >= label_w_px and cell_h >= label_h_px


def _resolve_heatmap_label_block(
    mapping: Dict[str, Any],
    vals: Sequence[Any],
    *,
    show_values_default: bool,
    value_idx: int = 2,
) -> Dict[str, Any]:
    """Return the ``series.label`` config dict honoring mapping options:

    - ``show_values`` (bool)            -- toggle cell values; default
                                            comes from caller context.
    - ``value_decimals`` (int)          -- decimals for the formatter;
                                            auto-picked from data range.
    - ``value_formatter`` (str)         -- explicit JS formatter wins
                                            over the built-in.
    - ``value_label_color`` (str|bool)  -- ``"auto"`` (default) for
                                            black/white contrast text,
                                            any hex / rgb string for a
                                            fixed color, or ``False`` /
                                            ``None`` to use the ECharts
                                            default (white).
    - ``value_label_size`` (int)        -- font size override.

    Auto-contrast goes through rich-text styles (``label.rich``) since
    ECharts heatmap doesn't evaluate ``label.color`` as a callback.
    The formatter returns ``{l|VALUE}`` for light cells (dark text) and
    ``{d|VALUE}`` for dark cells (light text); ``label.rich`` defines
    those two styles with the right color.
    """
    show_values = bool(mapping.get("show_values", show_values_default))
    font_size = int(mapping.get("value_label_size", 11))
    label_block: Dict[str, Any] = {
        "show": show_values,
        "fontSize": font_size,
    }
    if not show_values:
        return label_block

    raw_decimals = mapping.get("value_decimals")
    if raw_decimals is None:
        decimals = _auto_value_decimals(vals)
    else:
        decimals = clamp_decimals(raw_decimals, default=raw_decimals)

    custom_fmt = mapping.get("value_formatter")
    label_color = mapping.get("value_label_color", "auto")
    auto_contrast = (
        label_color is None
        or label_color is True
        or (isinstance(label_color, str) and label_color.lower() == "auto")
    )

    if isinstance(custom_fmt, str) and custom_fmt.strip():
        # Author-supplied formatter wins over the built-in. Auto-contrast
        # is suppressed because we can't safely re-wrap their output.
        label_block["formatter"] = custom_fmt
        if isinstance(label_color, str) and label_color and not auto_contrast:
            label_block["color"] = label_color
        return label_block

    if auto_contrast:
        label_block["formatter"] = _heatmap_auto_contrast_formatter(
            int(decimals), value_idx=value_idx
        )
        label_block["rich"] = {
            _HEATMAP_RICH_LIGHT: {"color": "#111", "fontSize": font_size},
            _HEATMAP_RICH_DARK: {"color": "#fff", "fontSize": font_size},
        }
    else:
        label_block["formatter"] = _heatmap_value_formatter(
            int(decimals), value_idx=value_idx
        )
        if label_color is False or label_color is None:
            # Leave label.color unset -- ECharts default applies.
            pass
        elif isinstance(label_color, str) and label_color:
            label_block["color"] = label_color
    return label_block


def build_heatmap(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    """Render a categorical heatmap from a long-form DataFrame.

    Mapping keys:
        x, y               required category columns
        value              required numeric column
        x_title, y_title   axis titles
        show_values        bool, default True -- print cell values
        value_decimals     int, default auto-picked from data magnitude
        value_formatter    explicit JS formatter (overrides default)
        value_label_color  ``"auto"`` (default) for B/W contrast text,
                           any hex / rgb string for a fixed color, or
                           ``False`` to leave to the ECharts default.
        value_label_size   int, default 11
        colors             explicit list of color stops, e.g.
                           ``["#fff", "#08306b"]``
        color_palette      palette name (looked up in PALETTES)
        color_scale        ``sequential`` | ``diverging`` | ``auto`` --
                           ``auto`` flips to a diverging palette
                           anchored at 0 when the data crosses zero.
        value_min, value_max  pin the visualMap range explicitly.
    """
    x = mapping.get("x"); y = mapping.get("y"); val = mapping.get("value")
    if not x or not y or not val:
        raise ValueError("heatmap: mapping requires 'x', 'y', and 'value'")
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item", "position": "top"}
    opt["legend"]["show"] = False

    if df is None:
        raise ValueError("heatmap: DataFrame is required")
    _ensure_columns(df, [x, y, val], "heatmap")

    x_cats = _unique(_col_to_list(df, x))
    y_cats = _unique(_col_to_list(df, y))
    x_idx = {v: i for i, v in enumerate(x_cats)}
    y_idx = {v: i for i, v in enumerate(y_cats)}

    cells: List[List[Any]] = []
    vals: List[Any] = []
    for xv, yv, z in zip(_col_to_list(df, x), _col_to_list(df, y), _col_to_list(df, val)):
        if xv is None or yv is None:
            continue
        cells.append([x_idx[xv], y_idx[yv], z])
        if z is not None:
            vals.append(z)

    opt["xAxis"] = {"type": "category", "data": list(x_cats), "splitArea": {"show": True}}
    opt["yAxis"] = {"type": "category", "data": list(y_cats), "splitArea": {"show": True}}

    color_scale = (mapping.get("color_scale") or "").lower()
    crosses_zero = bool(vals) and (min(
        (float(v) for v in vals if _is_finite(v)), default=0.0
    ) < 0.0 < max(
        (float(v) for v in vals if _is_finite(v)), default=0.0
    ))
    auto_diverging = color_scale == "auto" and crosses_zero
    if auto_diverging and not mapping.get("color_palette") and not mapping.get("colors"):
        # Auto mode w/o explicit colors: use the diverging palette so
        # cells reading as "above zero" / "below zero" are unambiguous.
        seq_colors = palette_colors_safe("gs_diverging") or [
            "#8C1D40", "#E0A458", "#F4F4F4", "#7399C6", "#1a365d"
        ]
    else:
        seq_colors = _resolve_heatmap_colors(mapping, ctx)

    diverging_zero = (
        color_scale == "diverging"
        or auto_diverging
        or (
            mapping.get("color_palette") == "gs_diverging"
            and crosses_zero
        )
    )
    v_min, v_max = _resolve_heatmap_value_range(
        mapping, vals, diverging_around_zero=diverging_zero
    )

    opt["visualMap"] = [{
        "min": v_min,
        "max": v_max,
        "calculable": True,
        "orient": "vertical",
        "right": 10,
        "top": "center",
        "inRange": {"color": list(seq_colors)},
    }]
    # The vertical visualMap legend on the right (~36 px wide + ticks)
    # needs grid clearance, otherwise the rightmost cell column is
    # half-covered. A 76 px grid.right is the empirically-derived
    # minimum for the default styling.
    opt["grid"]["right"] = max(int(opt["grid"].get("right", 20)), 76)

    # Cell-fit guard (CC10): when cells are too small to legibly hold
    # value labels, auto-disable show_values UNLESS the user explicitly
    # asked for them. Authors who set mapping.show_values=True bypass
    # the guard.
    show_values_default = True
    if "show_values" not in mapping:
        font_size = int(mapping.get("value_label_size", 11))
        raw_decimals = mapping.get("value_decimals")
        decimals_for_check = (
            _auto_value_decimals(vals) if raw_decimals is None
            else clamp_decimals(raw_decimals, default=raw_decimals)
        )
        if not _heatmap_cells_fit_labels(
            len(x_cats), len(y_cats), vals,
            int(decimals_for_check), font_size,
            int(getattr(ctx, "width", 700) or 700),
            int(getattr(ctx, "height", 350) or 350),
        ):
            show_values_default = False

    label_block = _resolve_heatmap_label_block(
        mapping, vals, show_values_default=show_values_default,
        value_idx=2,
    )
    cell_data = [{"value": [c[0], c[1], c[2]]} for c in cells]
    opt["series"] = [{
        "name": str(val), "type": "heatmap", "data": cell_data,
        "label": label_block,
        "emphasis": {"itemStyle": {"shadowBlur": 6, "shadowColor": "rgba(0,0,0,0.3)"}},
    }]
    # Long y-category labels would push the heatmap matrix far to the
    # right; truncation keeps the plot area stable.
    _layout_long_category_axis(opt, "yAxis")
    _autorotate_x_category_labels(opt, ctx)
    _apply_axis_titles(opt, mapping, horizontal=False,
                        chart_width=ctx.width)
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_geo_map(df, mapping: Dict[str, Any],
                  ctx: BuilderContext) -> Dict[str, Any]:
    """Build a choropleth against an explicitly registered GeoJSON asset."""
    region = mapping.get("region")
    value = mapping.get("value")
    map_name = mapping.get("map")
    if not region or not value or not map_name:
        raise ValueError(
            "geo_map: mapping requires 'region', 'value', and 'map'"
        )
    if df is None:
        raise ValueError("geo_map: DataFrame is required")
    _ensure_columns(df, [region, value], "geo_map")
    aliases = mapping.get("_region_aliases")
    aliases = aliases if isinstance(aliases, dict) else {}
    data = []
    values = []
    for name, raw_value in zip(
        _col_to_list(df, region), _col_to_list(df, value)
    ):
        if name is None or raw_value is None:
            continue
        resolved_name = aliases.get(str(name), str(name))
        data.append({"name": resolved_name, "value": raw_value})
        if _is_finite(raw_value):
            values.append(float(raw_value))
    value_min = mapping.get(
        "value_min", min(values) if values else 0
    )
    value_max = mapping.get(
        "value_max", max(values) if values else 1
    )
    if value_min == value_max:
        value_max = value_min + 1
    palette = (
        list(ctx.palette_colors)
        if ctx.palette_kind in ("sequential", "diverging")
        else palette_colors_safe("gs_blues")
    )
    opt = _base_option(ctx)
    opt.pop("xAxis", None)
    opt.pop("yAxis", None)
    opt.pop("grid", None)
    opt["legend"]["show"] = False
    opt["tooltip"] = {
        "show": True,
        "trigger": "item",
        "formatter": "{b}: {c}",
    }
    opt["visualMap"] = {
        "min": value_min,
        "max": value_max,
        "calculable": True,
        "orient": mapping.get("visual_map_orient", "vertical"),
        "left": mapping.get("visual_map_left", "left"),
        "bottom": mapping.get("visual_map_bottom", 20),
        "inRange": {"color": palette},
    }
    opt["series"] = [{
        "type": "map",
        "map": str(map_name),
        "name": mapping.get("series_name", str(value)),
        "data": data,
        "roam": bool(mapping.get("roam", False)),
        "selectedMode": mapping.get("selected_mode", False),
        "emphasis": {"label": {"show": True}},
        "itemStyle": {
            "borderColor": resolve_theme(ctx.theme_name)["semantic"]["surface"],
            "borderWidth": 0.6,
        },
    }]
    return opt


def _corr_window_days(window: str) -> Optional[int]:
    """Parse a window token like '63d' / 'all'. Returns the day count
    or None when the token is 'all' / unparseable."""
    if not isinstance(window, str) or window == "all":
        return None
    if window.endswith("d") and window[:-1].isdigit():
        return int(window[:-1])
    return None


def _corr_window_label(window: str) -> str:
    """Human-readable label for a window token. Mirrors the JS
    counterpart so subtitle text matches before and after a runtime
    Window change."""
    n = _corr_window_days(window)
    if n is None:
        return "Full sample"
    return f"{n}-day rolling"


_TRANSFORM_SHORT_LABELS = {
    "raw":                "Raw",
    "log":                "log",
    "change":             "\u0394",
    "pct_change":         "%\u0394",
    "log_change":         "log \u0394",
    "yoy_change":         "YoY \u0394",
    "yoy_pct":            "YoY %",
    "yoy_log":            "YoY log \u0394",
    "annualized_change":  "ann. \u0394",
    "zscore":             "z-score",
    "rank_pct":           "pct rank",
    "ytd":                "YTD \u0394",
    "index100":           "Index=100",
}


def _transform_short_label(name: str) -> str:
    """Mirror of the JS ``_ccTransformLabelShort`` so compile-time
    subtitles match runtime subtitles after a Transform change."""
    if not name or name == "raw":
        return "Raw"
    if name.startswith("rolling_zscore_"):
        try:
            w = int(name.rsplit("_", 1)[-1])
            return f"Rolling z ({w}d)"
        except ValueError:
            return name
    return _TRANSFORM_SHORT_LABELS.get(name, name)


def _corr_subtitle(method: str, transform: str, window: str,
                    as_of: Optional[str]) -> str:
    """Compose the auto-stamped subtitle line.

    Format: ``Pearson \u00B7 %\u0394 \u00B7 63-day rolling \u00B7 as of 2026-04-22``.
    Mirrors the JS-side ``_ccCorrSubtitle`` so compile-time and
    runtime renders are byte-identical for the same state.
    """
    parts: List[str] = []
    m = (method or "pearson").lower()
    parts.append("Spearman" if m == "spearman" else "Pearson")
    if transform and transform != "raw":
        parts.append(_transform_short_label(transform))
    if as_of:
        parts.append(_corr_window_label(window).lower())
        parts.append(f"as of {as_of}")
    elif window and window != "all":
        parts.append(_corr_window_label(window).lower())
    return " \u00B7 ".join(parts)


_MS_PER_DAY = 24 * 3600 * 1000


def _corr_apply_window(
    transformed: Dict[str, List[Optional[float]]],
    times_ms: Optional[List[Optional[int]]],
    window: str,
) -> Dict[str, List[Optional[float]]]:
    """Mask values outside the last-N-day window with None. Mirrors the
    JS-side ``_ccCorrApplyWindow`` so compile-time and runtime
    correlations agree byte-for-byte for the same (transform, window).
    """
    n_days = _corr_window_days(window)
    if n_days is None or times_ms is None:
        return transformed
    last_t: Optional[int] = None
    for t in reversed(times_ms):
        if t is not None:
            last_t = t
            break
    if last_t is None:
        return transformed
    cutoff = last_t - n_days * _MS_PER_DAY
    out: Dict[str, List[Optional[float]]] = {}
    for col, values in transformed.items():
        masked: List[Optional[float]] = []
        for v, t in zip(values, times_ms or []):
            if t is None or t < cutoff:
                masked.append(None)
            else:
                masked.append(v)
        out[col] = masked
    return out


def build_correlation_matrix(df, mapping: Dict[str, Any],
                              ctx: BuilderContext) -> Dict[str, Any]:
    """N-by-N correlation heatmap from a column list.

    Internally produces an ECharts heatmap option with a diverging
    visualMap pinned to [-1, 1] so the cell colors are interpretable
    without external context. Cell values are printed when
    ``mapping.show_values`` is true (default), with auto black/white
    contrast text against each cell's background color.

    The builder also embeds an ``_corr_runtime`` sidecar block on the
    option (raw per-column values + epoch-ms times) so the dashboard
    runtime drawer can re-correlate any time window or pre-transform
    on the client without round-tripping through PRISM. Mapping
    ``transform`` becomes the *initial* drawer state, not a pin.

    Mapping keys:
        columns           list of numeric columns to correlate (required, >=2)
        method            'pearson' (default) | 'spearman'
        transform         initial per-column pre-transform shown in the
                          drawer ('raw' | 'log' | 'pct_change' | 'yoy_pct'
                          | 'zscore' | 'rank_pct' | ...). Default 'raw'.
                          Order-aware transforms use ``order_by`` (default
                          first datetime-like column in df, else row order).
        order_by          column name used as the sort key for order-aware
                          transforms and for runtime windowing. Optional;
                          when omitted the builder picks the first
                          datetime-like column. When neither path
                          resolves a time column the runtime drawer
                          hides the Window dropdown and order-aware
                          transforms.
        min_periods       minimum overlapping non-null pairs required to
                          report a correlation; falls back to 5 when
                          omitted. Cells below the threshold render as
                          NaN (greyed in the heatmap).
        window            initial rolling window shown in the drawer.
                          One of ``window_options`` (default 'all').
        window_options    list of window choices the drawer offers.
                          Default
                          ``['all', '21d', '63d', '126d', '252d',
                          '504d', '1260d']``. Each entry is either
                          ``'all'`` or ``'<int>d'``.
        transforms        curated list of transform names the drawer
                          offers. Default: the full studio transform
                          set. ``raw`` is always prepended.
        show_values       bool, default True
        value_decimals    int, default 2
        value_label_color ``"auto"`` (default) for B/W contrast text,
                          any hex / rgb string for a fixed color, or
                          ``False`` to use ECharts' default.
        value_label_size  int, default 11
        colors            explicit list of color stops (overrides palette)
        color_palette     palette name (default ``gs_diverging``)

    The builder is robust to NaN values within columns (missing pairs
    are dropped per-cell). Both diagonal and off-diagonal values are
    printed by default; flip ``show_values=False`` for compact dense
    matrices.
    """
    cols = mapping.get("columns")
    if not isinstance(cols, (list, tuple)) or len(cols) < 2:
        raise ValueError(
            "correlation_matrix: mapping requires 'columns' with at "
            "least 2 numeric column names"
        )
    if df is None:
        raise ValueError("correlation_matrix: DataFrame is required")
    _ensure_columns(df, list(cols), "correlation_matrix")

    method = (mapping.get("method") or "pearson").lower()
    if method not in ("pearson", "spearman"):
        raise ValueError(
            f"correlation_matrix: method must be 'pearson' or "
            f"'spearman' (got '{method}')"
        )
    transform = (mapping.get("transform") or "raw").lower()
    show_values = bool(mapping.get("show_values", True))
    decimals = clamp_decimals(mapping.get("value_decimals"), default=2)
    min_periods = int(mapping.get("min_periods", 5))

    # Runtime-drawer presets (Transform / Window / Method).
    default_windows = ["all", "21d", "63d", "126d", "252d", "504d", "1260d"]
    raw_windows = mapping.get("window_options")
    if raw_windows is None:
        window_options = list(default_windows)
    elif isinstance(raw_windows, (list, tuple)):
        window_options = []
        for w in raw_windows:
            if not isinstance(w, str):
                raise ValueError(
                    f"correlation_matrix: window_options entries must be "
                    f"strings (got {type(w).__name__})"
                )
            if w != "all" and not (w.endswith("d") and w[:-1].isdigit()):
                raise ValueError(
                    f"correlation_matrix: window_options entry '{w}' must "
                    f"be 'all' or '<int>d' (e.g. '63d', '252d')"
                )
            window_options.append(w)
        if not window_options:
            window_options = list(default_windows)
        if "all" not in window_options:
            window_options = ["all"] + window_options
    else:
        raise ValueError(
            "correlation_matrix: window_options must be a list of strings"
        )
    window_default = (mapping.get("window") or "all").lower()
    if window_default not in window_options:
        raise ValueError(
            f"correlation_matrix: window='{window_default}' must be one "
            f"of window_options={window_options}"
        )

    raw_transforms = mapping.get("transforms")
    if raw_transforms is None:
        runtime_transforms = list(_DEFAULT_STUDIO_TRANSFORMS)
    elif isinstance(raw_transforms, (list, tuple)):
        runtime_transforms = [t for t in raw_transforms if isinstance(t, str)]
        if not runtime_transforms:
            runtime_transforms = list(_DEFAULT_STUDIO_TRANSFORMS)
    else:
        raise ValueError(
            "correlation_matrix: transforms must be a list of strings"
        )
    if "raw" not in runtime_transforms:
        runtime_transforms = ["raw"] + runtime_transforms
    if transform not in runtime_transforms:
        runtime_transforms.append(transform)

    # Resolve the order column unconditionally so the runtime drawer
    # can window any transform (not only order-aware ones). When the
    # author hasn't pinned ``order_by`` we still try to auto-detect a
    # datetime-like column; only an order-aware *initial* transform
    # raises if nothing resolves -- everything else falls back to row
    # order with the runtime Window dropdown hidden.
    order_by = mapping.get("order_by")
    import pandas as pd
    time_col: Optional[str] = None
    if order_by and order_by in df.columns:
        time_col = order_by
    elif order_by is None:
        for c in df.columns:
            try:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    time_col = c
                    break
            except Exception:
                continue
    if time_col:
        sorted_df = df.sort_values(time_col, kind="mergesort")
        time_seq = _col_to_list(sorted_df, time_col)
        data_df = sorted_df
    else:
        if (transform in ("change", "pct_change", "yoy_change", "yoy_pct")
                or transform.startswith("rolling_zscore_")):
            raise ValueError(
                f"correlation_matrix: transform '{transform}' is "
                f"order-aware; provide mapping.order_by pointing to "
                f"a date/time column (available columns: "
                f"{list(df.columns)})."
            )
        time_seq = None
        data_df = df

    # Capture raw per-column values BEFORE transform so the runtime
    # drawer can re-correlate against any transform / window the user
    # picks. Stored as plain Python floats (None for NaN/missing) for
    # JSON serialisation.
    raw_values: Dict[str, List[Optional[float]]] = {}
    for c in cols:
        raw_values[str(c)] = _col_to_list(data_df, c)

    # Convert sorted time column to epoch-ms (None for NaT) for the
    # JS payload AND for compile-time windowing. Match _ccParseT on
    # the JS side, which expects ms-since-epoch.
    times_ms: Optional[List[Optional[int]]] = None
    as_of_iso: Optional[str] = None
    if time_seq is not None:
        times_ms = []
        last_valid: Optional[Any] = None
        for t in time_seq:
            if t is None:
                times_ms.append(None)
                continue
            try:
                ts = pd.Timestamp(t)
            except (ValueError, TypeError):
                times_ms.append(None)
                continue
            if pd.isna(ts):
                times_ms.append(None)
            else:
                times_ms.append(int(ts.value // 1_000_000))
                last_valid = ts
        if last_valid is not None:
            as_of_iso = last_valid.strftime("%Y-%m-%d")

    # Apply per-column transform for the first-paint matrix.
    transformed: Dict[str, List[Optional[float]]] = {}
    for c in cols:
        transformed[str(c)] = _compute_transform(raw_values[str(c)],
                                                    time_seq, transform)

    # Apply window slicing for the first-paint matrix. The transform
    # ran on the full history (so rolling_zscore_252 and YoY have
    # their full lookback) but the correlation only looks at the last
    # N obs. JS mirrors this: transform then window then correlate.
    sliced = _corr_apply_window(transformed, times_ms, window_default)

    # Compute correlation matrix.
    n_cols = len(cols)
    cells: List[List[Any]] = []
    cell_text: Dict[Tuple[int, int], Optional[float]] = {}
    for i, ci in enumerate(cols):
        for j, cj in enumerate(cols):
            r = _corr(sliced[str(ci)], sliced[str(cj)],
                       method=method, min_periods=min_periods)
            # ECharts heatmap cells: [xIndex, yIndex, value] where the
            # y axis is reversed so reading top-to-bottom matches the
            # matrix convention (i.e. row 0 at the top).
            y_idx = (n_cols - 1) - j
            cells.append([i, y_idx, r])
            cell_text[(i, y_idx)] = r

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item", "position": "top"}
    opt["legend"]["show"] = False

    cat_x = [str(c) for c in cols]
    cat_y = list(reversed(cat_x))
    # interval=0 forces every column label to render -- the default
    # auto-thinning would drop most labels on N>=5 matrices, leaving
    # only the first and last visible (which is useless for an N x N
    # correlation grid where the user needs to read off pairs).
    opt["xAxis"] = {"type": "category", "data": cat_x,
                      "splitArea": {"show": True},
                      "axisLabel": {"hideOverlap": False,
                                      "interval": 0,
                                      "rotate": 30 if any(len(s) > 4 for s in cat_x) else 0}}
    opt["yAxis"] = {"type": "category", "data": cat_y,
                      "splitArea": {"show": True},
                      "axisLabel": {"interval": 0}}

    # Always use the diverging palette around 0 with [-1, 1] bounds so
    # cell colors are interpretable independent of the data spread.
    # Author can still override via mapping.colors / mapping.color_palette.
    div_colors = _resolve_heatmap_colors(
        mapping, ctx,
        fallback=palette_colors_safe("gs_diverging") or [
            "#8C1D40", "#E0A458", "#F4F4F4", "#7399C6", "#1a365d"
        ],
    )
    opt["visualMap"] = [{
        "min": -1, "max": 1,
        "calculable": True,
        "orient": "vertical",
        "right": 10,
        "top": "center",
        "precision": 2,
        "inRange": {"color": list(div_colors)},
    }]
    opt["grid"]["right"] = max(int(opt["grid"].get("right", 20)), 76)

    # Auto-contrast text for cell labels: each cell prints with a
    # black or white label depending on the cell's resolved color.
    # Fixed decimals (mapping.value_decimals) wins over the auto pick.
    cell_vals_for_decimals = [c[2] for c in cells if c[2] is not None]
    # Cell-fit guard (CC10): auto-disable cell labels when the matrix
    # is too dense for them to fit. Authors who explicitly set
    # mapping.show_values=True bypass the guard.
    show_values_for_block = show_values
    if "show_values" not in mapping:
        font_size = int(mapping.get("value_label_size", 11))
        if not _heatmap_cells_fit_labels(
            len(cat_x), len(cat_y), cell_vals_for_decimals,
            int(decimals), font_size,
            int(getattr(ctx, "width", 700) or 700),
            int(getattr(ctx, "height", 350) or 350),
        ):
            show_values_for_block = False
    label_mapping = dict(mapping)
    label_mapping.setdefault("value_decimals", decimals)
    label_mapping["show_values"] = show_values_for_block
    label_block = _resolve_heatmap_label_block(
        label_mapping, cell_vals_for_decimals,
        show_values_default=True, value_idx=2,
    )
    cell_data = [
        {"value": [c[0], c[1], c[2]]}
        for c in cells
    ]
    opt["series"] = [{
        "name": "correlation",
        "type": "heatmap",
        "data": cell_data,
        "label": label_block,
        "emphasis": {
            "itemStyle": {"shadowBlur": 6,
                            "shadowColor": "rgba(0,0,0,0.3)"}
        },
    }]

    # Tooltip: "{rowName} x {colName}: r=0.xx" for clarity.
    opt["tooltip"]["formatter"] = (
        "function(p){var v=(p.data && p.data.value) || p.data || []; "
        "var x=v[0], y=v[1], r=v[2]; "
        "var xs=" + json.dumps(cat_x) + "; "
        "var ys=" + json.dumps(cat_y) + "; "
        "var rn = ys[y] || ''; var cn = xs[x] || ''; "
        "if (r == null || isNaN(+r)) "
        "return rn + ' x ' + cn + ': insufficient overlap'; "
        f"return rn + ' x ' + cn + ': r=' + (+r).toFixed({decimals}); }}"
    )

    # Title: leave whatever ``_base_option(ctx)`` already set. The
    # dashboard pipeline blanks it when the widget tile owns the
    # title; rewriting it at runtime would cause double headlines.
    # Standalone ``make_echart`` renders preserve ctx.title as-is.

    # Subtitle: pack method + transform + window + as_of so the user
    # always knows what they're looking at. Author-supplied subtitle
    # (ctx.subtitle) wins. JS rewrites this on every drawer change.
    if not ctx.subtitle:
        opt["title"]["subtext"] = _corr_subtitle(
            method, transform, window_default, as_of_iso
        )

    # Embed the runtime sidecar block so the dashboard drawer can
    # re-correlate on Transform / Window / Method change. JS reads
    # this off SPECS[cid]._corr_runtime.
    opt["_corr_runtime"] = {
        "columns":            [str(c) for c in cols],
        "values":             {str(c): raw_values[str(c)] for c in cols},
        "times":              times_ms,
        "method":             method,
        "min_periods":        int(min_periods),
        "decimals":           int(decimals),
        "transform_default":  transform,
        "transforms":         list(runtime_transforms),
        "window_default":     window_default,
        "window_options":     list(window_options),
        "as_of":              as_of_iso,
        "subtitle_author":    ctx.subtitle or "",
    }

    _layout_long_category_axis(opt, "yAxis")
    _autorotate_x_category_labels(opt, ctx)
    _apply_typography_to_axes(opt, ctx)
    return opt


def palette_colors_safe(name: str) -> Optional[List[str]]:
    """Best-effort palette-color lookup that returns None on unknown name
    instead of raising. Avoids tying correlation_matrix to a specific
    set of palette names.
    """
    try:
        return list(get_palette(name)["colors"])
    except Exception:
        return None


def _corr(xs: Sequence[Optional[float]],
            ys: Sequence[Optional[float]],
            method: str = "pearson",
            min_periods: int = 5) -> Optional[float]:
    """Compute correlation between two equal-length value sequences.

    NaN-tolerant: pairs where either value is None / NaN are dropped.
    Returns None when the count of overlapping finite pairs is below
    ``min_periods`` -- callers (the heatmap builder) render that as a
    blank cell instead of producing a meaningless number.
    """
    pairs: List[Tuple[float, float]] = []
    for a, b in zip(xs, ys):
        if not (_is_finite(a) and _is_finite(b)):
            continue
        pairs.append((float(a), float(b)))
    n = len(pairs)
    if n < max(2, min_periods):
        return None

    if method == "spearman":
        # Replace each value with its average rank, then Pearson on ranks.
        def _ranks(vals: List[float]) -> List[float]:
            order = sorted(range(len(vals)), key=lambda i: vals[i])
            ranks = [0.0] * len(vals)
            i = 0
            while i < len(order):
                j = i
                while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                    j += 1
                avg_rank = (i + j) / 2.0 + 1.0
                for k in range(i, j + 1):
                    ranks[order[k]] = avg_rank
                i = j + 1
            return ranks
        rx = _ranks([p[0] for p in pairs])
        ry = _ranks([p[1] for p in pairs])
        pairs = list(zip(rx, ry))

    mean_x = sum(p[0] for p in pairs) / n
    mean_y = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mean_x) ** 2 for p in pairs)
    syy = sum((p[1] - mean_y) ** 2 for p in pairs)
    sxy = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pairs)
    if sxx <= 0 or syy <= 0:
        # One of the columns is constant on the overlap; correlation
        # is undefined. The diagonal is the canonical example.
        if sxx == 0 and syy == 0:
            return 1.0  # both constant, treat diagonal-style as 1
        return None
    return sxy / ((sxx * syy) ** 0.5)


def build_pie(df, mapping: Dict[str, Any], ctx: BuilderContext, donut: bool = False) -> Dict[str, Any]:
    cat = mapping.get("category"); val = mapping.get("value")
    if not cat or not val:
        raise ValueError("pie: mapping requires 'category' and 'value'")
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item",
                       "formatter": "{b}: {c} ({d}%)"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    if df is None:
        raise ValueError("pie: DataFrame is required")
    _ensure_columns(df, [cat, val], "pie")

    data = [{"name": str(n), "value": v}
            for n, v in zip(_col_to_list(df, cat), _col_to_list(df, val))
            if n is not None and v is not None]

    # Reserve vertical space for the legend. The pie's vertical anchor
    # depends on where the legend will sit (which the polish pass
    # applies via mapping.legend_position). build_pie peeks at the
    # same input so the geometry is correct on first paint:
    #
    #   legend_position="top"    -> center 58 % (legend at top)
    #   legend_position="bottom" -> center shifted up to clear legend
    #                               rows (42 % for 1 row, 32 % for 2,
    #                               24 % for 3+ wrapping rows)
    #   legend_position="none"   -> center 50 % (no legend to clear)
    #   (unset)                  -> default-top behaviour
    #
    # The polish pass's own ``setdefault("center", ...)`` is a no-op
    # once build_pie has set center here; that is intentional -- the
    # two sides of the split agree on the same anchor.
    legend_pos = str(mapping.get("legend_position") or "").lower()
    n_slices = len(data)
    if legend_pos == "none" or mapping.get("legend_show") is False:
        center = ["50%", "50%"]
    elif legend_pos == "bottom":
        # Legend rows wrap when items exceed ~6-8 per row (plain mode
        # + itemGap 14). Estimate rows so center scales with legend
        # footprint. Values tuned so the pie bottom clears the legend
        # row(s) with ~15-20 px breathing room -- earlier 42/32/22
        # values left too much dead space between pie and legend for
        # 1-row cases (most common).
        est_rows = 1 if n_slices <= 6 else (2 if n_slices <= 14 else 3)
        shift_pct = 50 - (est_rows - 1) * 8  # 50 / 42 / 34
        center = ["50%", f"{shift_pct}%"]
    else:
        center = ["50%", "58%"]

    radius: Any = ["40%", "68%"] if donut else "68%"

    opt["series"] = [{
        "name": str(val), "type": "pie", "radius": radius,
        "center": center,
        "data": data,
        "label": {"show": True, "formatter": "{b}: {d}%"},
        "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)"}},
    }]
    opt["legend"]["data"] = [d["name"] for d in data]
    return opt


def build_boxplot(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    x = mapping.get("x"); y = mapping.get("y")
    if not x or not y:
        raise ValueError("boxplot: mapping requires 'x' (category) and 'y' (values)")
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}

    if df is None:
        raise ValueError("boxplot: DataFrame is required")
    _ensure_columns(df, [x, y], "boxplot")

    groups = _unique(_col_to_list(df, x))
    box_data: List[List[float]] = []
    outliers: List[List[Any]] = []
    for i, g in enumerate(groups):
        vals = sorted(v for v in _col_to_list(df[df[x] == g], y)
                       if v is not None and not (isinstance(v, float) and v != v))
        if not vals:
            box_data.append([0, 0, 0, 0, 0])
            continue
        n = len(vals)

        def q(p):
            idx = p * (n - 1)
            lo = int(idx)
            hi = min(n - 1, lo + 1)
            frac = idx - lo
            return vals[lo] + (vals[hi] - vals[lo]) * frac

        q1 = q(0.25); q2 = q(0.5); q3 = q(0.75)
        iqr = q3 - q1
        whisk_lo = q1 - 1.5 * iqr
        whisk_hi = q3 + 1.5 * iqr
        in_vals = [v for v in vals if whisk_lo <= v <= whisk_hi]
        out_vals = [v for v in vals if v < whisk_lo or v > whisk_hi]
        lo = min(in_vals) if in_vals else q1
        hi = max(in_vals) if in_vals else q3
        box_data.append([lo, q1, q2, q3, hi])
        for ov in out_vals:
            outliers.append([i, ov])

    opt["xAxis"] = {"type": "category", "data": [str(g) for g in groups]}
    opt["yAxis"] = {"type": "value", "splitLine": {"show": True}}
    opt["series"] = [
        {"name": str(y), "type": "boxplot", "data": box_data},
        {"name": "outliers", "type": "scatter", "data": outliers,
          "symbolSize": 6, "emphasis": {"focus": "series"}},
    ]
    opt["legend"]["data"] = [str(y), "outliers"]
    _autorotate_x_category_labels(opt, ctx)
    _apply_axis_titles(opt, mapping, horizontal=False, chart_width=ctx.width)
    _apply_typography_to_axes(opt, ctx)
    return opt


# ---------------------------------------------------------------------------
# ECharts-native builders (phase 2 types)
# ---------------------------------------------------------------------------

def build_sankey(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    s = mapping.get("source"); t = mapping.get("target"); v = mapping.get("value")
    if not s or not t or not v:
        raise ValueError("sankey: mapping requires 'source', 'target', 'value'")
    if df is None:
        raise ValueError("sankey: DataFrame is required")
    _ensure_columns(df, [s, t, v], "sankey")

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    nodes = _unique(_col_to_list(df, s) + _col_to_list(df, t))
    links = [{"source": str(sv), "target": str(tv), "value": vv}
             for sv, tv, vv in zip(_col_to_list(df, s),
                                     _col_to_list(df, t),
                                     _col_to_list(df, v))
             if sv is not None and tv is not None and vv is not None]
    opt["series"] = [{
        "type": "sankey", "data": [{"name": str(n)} for n in nodes],
        "links": links,
        "emphasis": {"focus": "adjacency"},
        "lineStyle": {"color": "source", "curveness": 0.5, "opacity": 0.5},
        "label": {"show": True},
    }]
    return opt


def build_treemap(df, mapping: Dict[str, Any], ctx: BuilderContext,
                   is_sunburst: bool = False) -> Dict[str, Any]:
    path = mapping.get("path")
    name_col = mapping.get("name")
    parent_col = mapping.get("parent")
    val_col = mapping.get("value")

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    if df is None:
        raise ValueError("treemap: DataFrame is required")

    if path:
        _ensure_columns(df, list(path) + [val_col] if val_col else list(path), "treemap")
        data = _hierarchy_from_path(df, path, val_col)
    elif name_col and parent_col and val_col:
        _ensure_columns(df, [name_col, parent_col, val_col], "treemap")
        data = _hierarchy_from_parent(df, name_col, parent_col, val_col)
    else:
        raise ValueError(
            "treemap/sunburst: mapping requires either 'path' (list) + 'value' "
            "OR 'name' + 'parent' + 'value'"
        )

    stype = "sunburst" if is_sunburst else "treemap"
    series = {"type": stype, "data": data}
    if is_sunburst:
        series["radius"] = ["0%", "55%"]
        series["center"] = ["50%", "55%"]
        series["top"] = 90
        series["bottom"] = 30
        series["left"] = 30
        series["right"] = 30
    else:
        series["top"] = 90
        series["bottom"] = 30
        series["left"] = 30
        series["right"] = 30
    opt["series"] = [series]
    return opt


def _hierarchy_from_path(df, path: Sequence[str], val_col: Optional[str]) -> List[Dict[str, Any]]:
    root: Dict[str, Any] = {"name": "root", "children": []}
    path_cols = list(path)
    for _, row in df.iterrows():
        node = root
        for level, pcol in enumerate(path_cols):
            label = row[pcol]
            if label is None:
                break
            label = str(label)
            existing = next((c for c in node["children"] if c["name"] == label), None)
            is_leaf = level == len(path_cols) - 1
            if existing is None:
                new_node: Dict[str, Any] = {"name": label}
                if is_leaf:
                    new_node["value"] = row[val_col] if val_col else 1
                else:
                    new_node["children"] = []
                node["children"].append(new_node)
                existing = new_node
            elif is_leaf and val_col is not None:
                existing["value"] = (existing.get("value", 0) or 0) + (row[val_col] or 0)
            node = existing if "children" in existing else node
            if is_leaf:
                break
    return root["children"]


def _hierarchy_from_parent(df, name_col: str, parent_col: str,
                             val_col: str) -> List[Dict[str, Any]]:
    by_name: Dict[Any, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        n = row[name_col]
        if n is None:
            continue
        by_name.setdefault(str(n), {"name": str(n), "children": []})
        if row[val_col] is not None:
            by_name[str(n)]["value"] = row[val_col]
    roots: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        n = row[name_col]
        if n is None:
            continue
        p = row[parent_col]
        if p is None or p == "" or str(p) == str(n):
            roots.append(by_name[str(n)])
        else:
            parent = by_name.setdefault(str(p), {"name": str(p), "children": []})
            parent.setdefault("children", []).append(by_name[str(n)])
    for node in by_name.values():
        if not node.get("children"):
            node.pop("children", None)
    return roots


def build_graph(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    nodes = mapping.get("nodes")
    edges = mapping.get("edges")
    src = mapping.get("source"); tgt = mapping.get("target"); val = mapping.get("value")
    node_id = mapping.get("node_id"); node_label = mapping.get("node_label")
    node_size = mapping.get("node_size"); node_cat = mapping.get("node_category")

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    node_list: List[Dict[str, Any]] = []
    edge_list: List[Dict[str, Any]] = []

    if nodes is not None and edges is not None:
        node_list = list(nodes)
        edge_list = list(edges)
    elif df is not None and src and tgt:
        _ensure_columns(df, [src, tgt], "graph")
        ids = _unique(_col_to_list(df, src) + _col_to_list(df, tgt))
        node_list = [{"id": str(i), "name": str(i)} for i in ids]
        for a, b, vv in zip(_col_to_list(df, src), _col_to_list(df, tgt),
                             _col_to_list(df, val) if val else [None] * len(df)):
            if a is None or b is None:
                continue
            # Skip self-loops (src == tgt). A common convention is to
            # use a self-edge with value=0 to declare a node's category
            # when it only appears on the target side of real edges;
            # we don't want that ghost edge rendered.
            if a == b:
                continue
            if vv is not None:
                try:
                    if float(vv) == 0:
                        continue
                except (TypeError, ValueError):
                    pass
            e = {"source": str(a), "target": str(b)}
            if vv is not None:
                e["value"] = vv
            edge_list.append(e)
    else:
        raise ValueError(
            "graph: provide either mapping.nodes + mapping.edges, or a df with "
            "source+target column names in mapping."
        )

    categories = None
    if node_cat is not None and df is not None and node_cat in df.columns:
        cats = _unique(_col_to_list(df, node_cat))
        categories = [{"name": str(c)} for c in cats]
        cat_idx = {c: i for i, c in enumerate(cats)}
        # Build the node -> category lookup by scanning every edge
        # endpoint for which the row's category applies. The edge's
        # category field is interpreted as the source node's category,
        # so we fill sources first and then propagate from tgt only
        # when a node was never seen on the src side. Users can also
        # encode explicit per-node categories via self-edges (src==tgt).
        lookup_cat: Dict[Any, Any] = {}
        src_list = _col_to_list(df, node_id or src)
        tgt_list = _col_to_list(df, tgt)
        cat_list = _col_to_list(df, node_cat)
        for s_val, t_val, c_val in zip(src_list, tgt_list, cat_list):
            if c_val is None:
                continue
            if s_val is not None and s_val == t_val:
                # self-edge: assigns the node's own category
                lookup_cat[s_val] = c_val
                continue
            if s_val is not None and s_val not in lookup_cat:
                lookup_cat[s_val] = c_val
        # Second pass for nodes that only show up as targets -- they
        # inherit the category of their first incoming edge.
        tgt_fallback: Dict[Any, Any] = {}
        for s_val, t_val, c_val in zip(src_list, tgt_list, cat_list):
            if t_val is None or t_val in lookup_cat:
                continue
            if c_val is None:
                continue
            tgt_fallback.setdefault(t_val, c_val)
        for k, v in tgt_fallback.items():
            lookup_cat.setdefault(k, v)
        for n in node_list:
            key = n.get("id") or n.get("name")
            if key in lookup_cat:
                n["category"] = cat_idx[lookup_cat[key]]

    series = {
        "type": "graph", "layout": "force",
        "data": node_list, "edges": edge_list,
        "roam": True, "draggable": True,
        "label": {"show": True, "position": "right",
                    "distance": 4, "fontSize": 11},
        "symbolSize": 28,
        "force": {"repulsion": 800, "edgeLength": 120,
                    "gravity": 0.08, "layoutAnimation": True},
        "lineStyle": {"opacity": 0.6, "width": 1.2,
                       "curveness": 0.1},
        "emphasis": {"focus": "adjacency",
                      "lineStyle": {"width": 2.5}},
    }
    if categories:
        series["categories"] = categories
    opt["series"] = [series]
    return opt


def build_candlestick(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    x = mapping.get("x")
    o = mapping.get("open"); c = mapping.get("close")
    lo = mapping.get("low"); hi = mapping.get("high")
    if not all([x, o, c, lo, hi]):
        raise ValueError(
            "candlestick: mapping requires 'x', 'open', 'close', 'low', 'high'"
        )
    if df is None:
        raise ValueError("candlestick: DataFrame is required")
    _ensure_columns(df, [x, o, c, lo, hi], "candlestick")
    opt = _base_option(ctx)
    opt["xAxis"] = {"type": _time_axis_if_needed(df, x)["type"]}
    opt["yAxis"] = {"type": "value", "scale": True}
    ohlc = []
    dates = _col_to_list(df, x)
    if opt["xAxis"]["type"] == "category":
        opt["xAxis"]["data"] = [str(d) for d in dates]
    oo = _col_to_list(df, o); cc = _col_to_list(df, c)
    ll = _col_to_list(df, lo); hh = _col_to_list(df, hi)
    for i in range(len(dates)):
        if opt["xAxis"]["type"] == "category":
            ohlc.append([oo[i], cc[i], ll[i], hh[i]])
        else:
            ohlc.append([dates[i], oo[i], cc[i], ll[i], hh[i]])
    opt["series"] = [{"type": "candlestick", "name": "OHLC", "data": ohlc}]
    opt["legend"]["data"] = ["OHLC"]
    opt["dataZoom"] = [{"type": "inside"}, {"type": "slider"}]
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_radar(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    category = mapping.get("category")
    value = mapping.get("value")
    series_col = mapping.get("series")
    if not category or not value:
        raise ValueError("radar: mapping requires 'category' (dimension) and 'value'")
    if df is None:
        raise ValueError("radar: DataFrame is required")
    _ensure_columns(df, [category, value] + ([series_col] if series_col else []), "radar")

    opt = _base_option(ctx)
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)
    opt["tooltip"] = {"show": True, "trigger": "item"}

    dims = _unique(_col_to_list(df, category))
    max_val = max((v for v in _col_to_list(df, value) if v is not None), default=1)
    opt["radar"] = {
        "indicator": [{"name": str(d), "max": max_val * 1.2} for d in dims],
        "shape": "polygon", "splitNumber": 5,
        # Match the pie/donut shift so the top indicator label does not
        # collide with the row-2 legend.
        "center": ["50%", "58%"],
        "radius": "62%",
    }

    data: List[Dict[str, Any]] = []
    if series_col:
        groups = _unique(_col_to_list(df, series_col))
        for g in groups:
            sub = df[df[series_col] == g]
            lookup = dict(zip(_col_to_list(sub, category), _col_to_list(sub, value)))
            vals = [lookup.get(d, 0) for d in dims]
            data.append({"name": str(g), "value": vals})
    else:
        lookup = dict(zip(_col_to_list(df, category), _col_to_list(df, value)))
        vals = [lookup.get(d, 0) for d in dims]
        data.append({"name": str(value), "value": vals})

    opt["series"] = [{"type": "radar", "data": data,
                       "areaStyle": {"opacity": 0.3}}]
    opt["legend"]["data"] = [d["name"] for d in data]
    return opt


def build_gauge(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    import math

    val = mapping.get("value")
    name = mapping.get("name", "value")

    def _resolve_bound(key: str, default: float) -> float:
        raw = mapping.get(key, default)
        if df is not None and isinstance(raw, str) and raw in df.columns:
            values = _col_to_list(df, raw)
            raw = values[-1] if values else None
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"gauge: {key} must be a finite number or numeric column"
            ) from exc

    mn = _resolve_bound("min", 0)
    mx = _resolve_bound("max", 100)
    if not math.isfinite(mn) or not math.isfinite(mx) or mn >= mx:
        raise ValueError(
            f"gauge: min/max must be finite with min < max "
            f"(got min={mn!r}, max={mx!r})"
        )
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)
    opt["legend"]["show"] = False

    if isinstance(val, (int, float)):
        value = float(val)
    elif df is not None and isinstance(val, str):
        _ensure_columns(df, [val], "gauge")
        series = _col_to_list(df, val)
        value = float(series[-1]) if series else 0.0
    else:
        raise ValueError("gauge: mapping.value must be a number or column name")
    if not math.isfinite(value):
        raise ValueError(f"gauge: value must be finite (got {value!r})")
    if not mn <= value <= mx:
        raise ValueError(
            f"gauge: value {value:g} lies outside [{mn:g}, {mx:g}]"
        )

    decimals = clamp_decimals(
        mapping.get("value_decimals", 2)
    )
    detail_formatter = (
        "function(v){"
        " var n=Number(v);"
        " if (!Number.isFinite(n)) return '--';"
        f" var s=n.toFixed({decimals});"
        " return s.replace(/\\.?0+$/, '');"
        "}"
    )

    opt["series"] = [{
        "type": "gauge", "name": str(name),
        "min": mn, "max": mx, "splitNumber": 10,
        "progress": {"show": True, "width": 14},
        "axisLine": {"lineStyle": {"width": 14}},
        "pointer": {"show": True, "length": "60%", "width": 6},
        "title": {"show": True, "fontSize": 14},
        "detail": {"valueAnimation": True, "formatter": detail_formatter,
                    "fontSize": 28},
        "data": [{"value": value, "name": str(name)}],
    }]
    return opt


def build_calendar_heatmap(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    """Year-grid heatmap of a single value column over time.

    Mapping keys:
        date, value        required
        year               4-digit string; defaults to the latest year present
        show_values        bool, default False -- calendar cells are tiny,
                           but enable when cell size is large enough
        value_decimals     int, default auto-picked from data magnitude
        value_label_color  ``"auto"`` for B/W contrast text, hex / rgb,
                           or ``False`` to use the ECharts default
        colors             explicit list of color stops (overrides palette)
        color_palette      palette name (looked up in PALETTES)
        color_scale        ``sequential`` | ``diverging`` | ``auto``
        value_min, value_max  pin the visualMap range
    """
    date_col = mapping.get("date"); val_col = mapping.get("value")
    if not date_col or not val_col:
        raise ValueError("calendar_heatmap: mapping requires 'date' and 'value'")
    if df is None:
        raise ValueError("calendar_heatmap: DataFrame is required")
    _ensure_columns(df, [date_col, val_col], "calendar_heatmap")

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)
    opt["legend"]["show"] = False

    dates = _col_to_list(df, date_col)
    vals = _col_to_list(df, val_col)
    pairs = [[str(d), v] for d, v in zip(dates, vals) if d is not None]
    cell_vals = [p[1] for p in pairs if p[1] is not None]

    years = sorted({str(p[0])[:4] for p in pairs})
    raw_year = mapping.get("year", years[-1] if years else "2025")
    # CC1 in the 2026-05-11 audit: when the author passes a LIST of
    # years (e.g. [2024, 2025, 2026]), convert to an ECharts-native
    # date range ["YYYY-01-01", "YYYY-12-31"] spanning the full set.
    # ECharts calendar.range accepts a 2-array of date strings; passing
    # a 3-array silently falls back to year=1969 (epoch) with no data.
    if isinstance(raw_year, (list, tuple)):
        year_strs = [str(y)[:4] for y in raw_year if y is not None]
        if year_strs:
            year_strs.sort()
            year = [f"{year_strs[0]}-01-01",
                    f"{year_strs[-1]}-12-31"]
        else:
            year = years[-1] if years else "2025"
    else:
        year = raw_year

    color_scale = (mapping.get("color_scale") or "").lower()
    crosses_zero = bool(cell_vals) and (
        min((float(v) for v in cell_vals if _is_finite(v)), default=0.0) < 0.0
        < max((float(v) for v in cell_vals if _is_finite(v)), default=0.0)
    )
    auto_diverging = color_scale == "auto" and crosses_zero
    if auto_diverging and not mapping.get("color_palette") and not mapping.get("colors"):
        seq_colors = palette_colors_safe("gs_diverging") or [
            "#8C1D40", "#E0A458", "#F4F4F4", "#7399C6", "#1a365d"
        ]
    else:
        seq_colors = _resolve_heatmap_colors(
            mapping, ctx,
            fallback=["#F5F8FC", "#9BB4D4", "#305890", "#002F6C"],
        )

    diverging_zero = (
        color_scale == "diverging"
        or auto_diverging
        or (mapping.get("color_palette") == "gs_diverging" and crosses_zero)
    )
    v_min, v_max = _resolve_heatmap_value_range(
        mapping, cell_vals, diverging_around_zero=diverging_zero
    )

    opt["visualMap"] = [{
        "min": v_min, "max": v_max, "calculable": True,
        "orient": "horizontal", "left": "center", "top": "top",
        "inRange": {"color": list(seq_colors)},
    }]
    # Multi-year ranges silently overlap month labels when packed
    # into a single horizontal calendar (ECharts has no `interval`
    # option on monthLabel; the labels just collide). Render one
    # calendar pad per year, stacked vertically, with the year label
    # on the left so the date context is unambiguous. Series gets
    # ``calendarIndex`` to point at its calendar.
    n_years = 1
    year_starts: List[int] = []
    if isinstance(year, list) and len(year) == 2:
        try:
            y0 = int(year[0][:4])
            y1 = int(year[1][:4])
            n_years = max(1, y1 - y0 + 1)
            year_starts = list(range(y0, y1 + 1))
        except Exception:
            n_years = 1
    if n_years >= 2 and year_starts:
        # Per-year calendar pads, stacked vertically.
        cal_h = 70
        cal_top0 = 80
        opt["calendar"] = [
            {
                "range": str(yr),
                "cellSize": ["auto", 14],
                "orient": "horizontal",
                "top": cal_top0 + i * cal_h,
                "left": 60, "right": 30,
                "monthLabel": {"fontSize": 10, "color": "#666"},
                "yearLabel": {"show": True, "fontSize": 11,
                                "margin": 18},
                "dayLabel": {"fontSize": 9},
            }
            for i, yr in enumerate(year_starts)
        ]
    else:
        opt["calendar"] = {
            "range": year, "cellSize": ["auto", 16],
            "orient": "horizontal",
            "monthLabel": {"fontSize": 11},
            "yearLabel": {"show": True, "fontSize": 11},
        }

    # Calendar cells are typically too small to comfortably print
    # values, so labels default off; authors with large cellSize can
    # opt in via mapping.show_values=True.
    label_block = _resolve_heatmap_label_block(
        mapping, cell_vals, show_values_default=False, value_idx=1
    )
    if isinstance(opt["calendar"], list):
        # Multi-year stacked pads -- one heatmap series per pad,
        # filtered to that year's data via simple string prefix.
        opt["series"] = [
            {
                "type": "heatmap", "coordinateSystem": "calendar",
                "calendarIndex": i,
                "data": [p for p in pairs
                         if str(p[0]).startswith(str(yr))],
                "name": f"{val_col} {yr}",
                "label": label_block,
            }
            for i, yr in enumerate(year_starts)
        ]
    else:
        opt["series"] = [{
            "type": "heatmap", "coordinateSystem": "calendar",
            "data": pairs, "name": str(val_col),
            "label": label_block,
        }]
    return opt


def build_funnel(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    cat = mapping.get("category"); val = mapping.get("value")
    if not cat or not val:
        raise ValueError("funnel: mapping requires 'category' and 'value'")
    if df is None:
        raise ValueError("funnel: DataFrame is required")
    _ensure_columns(df, [cat, val], "funnel")
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    data = [{"name": str(n), "value": v}
            for n, v in zip(_col_to_list(df, cat), _col_to_list(df, val))
            if n is not None and v is not None]
    vals = [d["value"] for d in data]
    opt["series"] = [{
        "type": "funnel", "data": data,
        "sort": "descending", "gap": 2,
        # Reserve space above for title + row-2 legend.
        "top": 80, "bottom": 20,
        # Default `min: 0` so the smallest segment still has visible
        # width. Setting min=min(vals) makes the bottom segment a
        # zero-width point.
        "min": mapping.get("min", 0),
        "max": mapping.get("max", max(vals) if vals else 100),
        "label": {"show": True, "position": "inside"},
    }]
    opt["legend"]["data"] = [d["name"] for d in data]
    return opt


def build_parallel(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    dims = mapping.get("dims")
    color = mapping.get("color")
    if not dims or not isinstance(dims, (list, tuple)):
        raise ValueError("parallel_coords: mapping requires 'dims' (list of column names)")
    if df is None:
        raise ValueError("parallel_coords: DataFrame is required")
    _ensure_columns(df, list(dims) + ([color] if color else []), "parallel_coords")

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    axes = [{"dim": i, "name": str(d)} for i, d in enumerate(dims)]
    opt["parallelAxis"] = axes
    opt["parallel"] = {"left": "6%", "right": "6%", "top": 80, "bottom": 80}

    rows = _rows(df, list(dims))
    series: List[Dict[str, Any]] = []
    legend_names: List[str] = []
    if color:
        groups = _unique(_col_to_list(df, color))
        cols_order = list(dims)
        for g in groups:
            sub = df[df[color] == g]
            gdata = _rows(sub, cols_order)
            legend_names.append(str(g))
            series.append({"type": "parallel", "name": str(g), "data": gdata,
                            "lineStyle": {"opacity": 0.45, "width": 1.0}})
    else:
        legend_names.append("series")
        series.append({"type": "parallel", "name": "series", "data": rows,
                        "lineStyle": {"opacity": 0.45, "width": 1.0}})
    opt["series"] = series
    opt["legend"]["data"] = legend_names
    return opt


def build_tree(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    name_col = mapping.get("name") or mapping.get("node")
    parent_col = mapping.get("parent")
    if not name_col or not parent_col:
        raise ValueError("tree: mapping requires 'name' and 'parent'")
    if df is None:
        raise ValueError("tree: DataFrame is required")
    _ensure_columns(df, [name_col, parent_col], "tree")
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    data = _hierarchy_from_parent(df, name_col, parent_col,
                                    mapping.get("value") or name_col)
    root = data[0] if len(data) == 1 else {"name": "root", "children": data}
    opt["series"] = [{
        "type": "tree", "data": [root], "top": "5%", "bottom": "5%",
        "left": "10%", "right": "10%",
        "layout": "orthogonal", "orient": "LR",
        "symbol": "emptyCircle", "symbolSize": 7,
        "initialTreeDepth": -1,
        "roam": True, "expandAndCollapse": True,
        "label": {"position": "left", "verticalAlign": "middle", "align": "right"},
        "leaves": {"label": {"position": "right", "verticalAlign": "middle", "align": "left"}},
    }]
    return opt


def build_histogram(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    """Bin a numeric column and render as a bar chart.

    Mapping keys:
        x       column to bin (required)
        bins    int or list of edges (default 20)
        density boolean: normalize counts to densities (default False)
        y_title, x_title: axis labels
    """
    x = mapping.get("x")
    if not x:
        raise ValueError("histogram: mapping requires 'x' (numeric column)")
    if df is None:
        raise ValueError("histogram: DataFrame is required")
    _ensure_columns(df, [x], "histogram")

    vals = [v for v in _col_to_list(df, x)
            if v is not None and not (isinstance(v, float) and v != v)]
    if not vals:
        raise ValueError(f"histogram: column '{x}' is empty")

    bins = mapping.get("bins", 20)
    if isinstance(bins, (list, tuple)):
        edges = list(bins)
    else:
        nb = max(1, int(bins))
        lo, hi = min(vals), max(vals)
        if lo == hi:
            hi = lo + 1.0
        step = (hi - lo) / nb
        edges = [lo + i * step for i in range(nb + 1)]

    counts = [0] * (len(edges) - 1)
    for v in vals:
        for i in range(len(edges) - 1):
            if v >= edges[i] and (v < edges[i + 1] or (i == len(edges) - 2 and v == edges[-1])):
                counts[i] += 1
                break

    if mapping.get("density"):
        total = sum(counts)
        if total > 0:
            widths = [edges[i + 1] - edges[i] for i in range(len(counts))]
            counts = [c / (total * w) if w > 0 else 0 for c, w in zip(counts, widths)]

    mids = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]
    # Short labels -- just the lower edge of each bin, rounded. The
    # verbose "a\u2013b" form was legible at 5 bins but unreadable at 30+.
    labels = [f"{edges[i]:.1f}" for i in range(len(counts))]

    opt = _base_option(ctx)
    opt["tooltip"]["axisPointer"] = {"type": "shadow"}
    # Auto-thin labels: show at most ~8 so the axis stays readable.
    # interval=0 means show every, N means skip N.
    interval = max(0, (len(labels) // 8) - 1)
    opt["xAxis"] = {"type": "category", "data": labels,
                      "axisLabel": {"interval": interval,
                                      "rotate": 0}}
    opt["yAxis"] = {"type": "value",
                      "name": "Density" if mapping.get("density") else "Count"}
    opt["series"] = [{
        "type": "bar", "name": str(x), "data": counts,
        "barCategoryGap": "2%",
    }]
    opt["legend"]["data"] = [str(x)]

    _apply_axis_titles(opt, mapping, horizontal=False)
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_bullet(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    """Rates-RV style bullet: for each category, draw the (low, high) range
    as a pill and place a marker at the current value.

    Mapping keys:
        y       category column (required)
        x       current-value column (required)
        x_low   range-low column (required)
        x_high  range-high column (required)
        color_by column used to color the current-value dot
                 (values are interpreted as z-scores unless color_mode='palette')
        color_mode 'zscore' (default) | 'palette'
        label   optional column to annotate each row with
    """
    yc = mapping.get("y"); xc = mapping.get("x")
    low_c = mapping.get("x_low"); high_c = mapping.get("x_high")
    cb = mapping.get("color_by"); lbl_c = mapping.get("label")
    if not (yc and xc and low_c and high_c):
        raise ValueError(
            "bullet: mapping requires 'y' (category), 'x' (current), "
            "'x_low' (range_low), 'x_high' (range_high)"
        )
    if df is None:
        raise ValueError("bullet: DataFrame is required")
    need = [yc, xc, low_c, high_c] + ([cb] if cb else []) + ([lbl_c] if lbl_c else [])
    _ensure_columns(df, need, "bullet")

    categories = [str(v) for v in _col_to_list(df, yc)]
    lows = _col_to_list(df, low_c)
    highs = _col_to_list(df, high_c)
    currents = _col_to_list(df, xc)
    color_vals = _col_to_list(df, cb) if cb else [None] * len(categories)
    label_vals = _col_to_list(df, lbl_c) if lbl_c else [None] * len(categories)

    mode = mapping.get("color_mode", "zscore")

    def _z_color(z: Optional[float]) -> str:
        if z is None:
            return "#718096"
        if z >= 1.5:  return "#c53030"
        if z >= 1.0:  return "#dd6b20"
        if z >= 0.5:  return "#ecc94b"
        if z <= -1.5: return "#2b6cb0"
        if z <= -1.0: return "#3182ce"
        if z <= -0.5: return "#63b3ed"
        return "#718096"

    palette = list(ctx.palette_colors) if ctx.palette_kind == "categorical" else []

    items: List[List[Any]] = []
    for i, (cat, lo, hi, cur, cv, lbl) in enumerate(
        zip(categories, lows, highs, currents, color_vals, label_vals)
    ):
        if mode == "zscore":
            dot_color = _z_color(cv if isinstance(cv, (int, float)) else None)
        else:
            if palette:
                dot_color = palette[i % len(palette)]
            else:
                dot_color = "#002F6C"
        items.append([lo, hi, cur, dot_color,
                       str(lbl) if lbl is not None else ""])

    render_js = """function(params, api) {
  var catIdx = params.dataIndex;
  var yCenter = api.coord([0, catIdx])[1];
  var xLo = api.coord([api.value(0), catIdx])[0];
  var xHi = api.coord([api.value(1), catIdx])[0];
  var xCur = api.coord([api.value(2), catIdx])[0];
  var dotColor = api.value(3) || '#002F6C';
  var label = api.value(4) || '';
  return {
    type: 'group',
    children: [
      { type: 'rect',
        shape: { x: Math.min(xLo, xHi), y: yCenter - 8,
                 width: Math.abs(xHi - xLo), height: 16, r: 4 },
        style: { fill: '#e2e8f0', opacity: 0.85 } },
      { type: 'line',
        shape: { x1: xLo, y1: yCenter - 4, x2: xLo, y2: yCenter + 4 },
        style: { stroke: '#a0aec0', lineWidth: 2 } },
      { type: 'line',
        shape: { x1: xHi, y1: yCenter - 4, x2: xHi, y2: yCenter + 4 },
        style: { stroke: '#a0aec0', lineWidth: 2 } },
      { type: 'circle',
        shape: { cx: xCur, cy: yCenter, r: 7 },
        style: { fill: dotColor, stroke: '#fff', lineWidth: 1.5 } },
      label ? { type: 'text',
        style: { text: label, fill: '#2d3748', fontSize: 11,
                   textAlign: 'left', textVerticalAlign: 'middle',
                   x: xHi + 8, y: yCenter } } : null,
    ].filter(function(c){ return c != null; })
  };
}"""

    opt = _base_option(ctx)
    opt["tooltip"] = {
        "show": True, "trigger": "item",
        "formatter": "function(p){ return p.name + ': ' + p.value[2] + "
                       "' (range ' + p.value[0] + ', ' + p.value[1] + ')'; }",
    }
    opt["legend"]["show"] = False

    all_vals: List[float] = []
    for lo, hi, cur in zip(lows, highs, currents):
        for v in (lo, hi, cur):
            if isinstance(v, (int, float)):
                all_vals.append(float(v))
    if all_vals:
        vmin = min(all_vals)
        vmax = max(all_vals)
        pad = (vmax - vmin) * 0.05 or 1.0
    else:
        vmin, vmax, pad = 0.0, 1.0, 0.1

    opt["xAxis"] = {"type": "value",
                      "min": vmin - pad, "max": vmax + pad,
                      "splitLine": {"show": True}}
    opt["yAxis"] = {"type": "category", "data": categories,
                      "axisLine": {"show": False},
                      "axisTick": {"show": False}}
    opt["grid"]["right"] = 80

    opt["series"] = [{
        "type": "custom", "name": "bullet",
        "renderItem": render_js,
        "encode": {"x": [0, 1, 2], "y": None, "tooltip": [0, 1, 2]},
        "data": items,
    }]

    _apply_axis_titles(opt, mapping, horizontal=True)
    _apply_typography_to_axes(opt, ctx)
    return opt


# =============================================================================
# KNOB REGISTRY (for the single-chart editor HTML)
#
# A "knob" is a single editable parameter surfaced in the editor UI. Each
# knob is a dict with type, UI metadata, and either a dotted option path or
# the name of a JS apply function in editor_html.py.
# =============================================================================

UNIVERSAL_KNOBS: List[Dict[str, Any]] = [
    # Title
    {"name": "titleText", "label": "Title", "type": "text", "default": "",
     "group": "Title", "apply": "setTitleText", "essential": True},
    {"name": "subtitleText", "label": "Subtitle", "type": "text", "default": "",
     "group": "Title", "apply": "setSubtitleText"},
    {"name": "titleSize", "label": "Title size", "type": "range",
     "min": 8, "max": 40, "step": 1, "default": 18,
     "group": "Title", "path": "title.textStyle.fontSize", "essential": True},
    {"name": "titleColor", "label": "Title color", "type": "color", "default": "#000000",
     "group": "Title", "path": "title.textStyle.color"},
    {"name": "titleWeight", "label": "Title weight", "type": "select",
     "options": ["normal", "bold", "bolder"], "default": "bold",
     "group": "Title", "path": "title.textStyle.fontWeight"},
    {"name": "titleLeft", "label": "Title align", "type": "select",
     "options": ["left", "center", "right"], "default": "left",
     "group": "Title", "path": "title.left"},
    {"name": "subtitleSize", "label": "Subtitle size", "type": "range",
     "min": 6, "max": 28, "step": 1, "default": 12,
     "group": "Title", "path": "title.subtextStyle.fontSize"},
    {"name": "subtitleColor", "label": "Subtitle color", "type": "color", "default": "#333333",
     "group": "Title", "path": "title.subtextStyle.color"},

    # Typography
    {"name": "fontFamily", "label": "Font family", "type": "select",
     "options": ["Liberation Sans, Arial, sans-serif",
                  "Arial, sans-serif",
                  "Helvetica, Arial, sans-serif",
                  "Georgia, 'Times New Roman', serif",
                  "'Courier New', monospace"],
     "default": "Liberation Sans, Arial, sans-serif",
     "group": "Typography", "path": "textStyle.fontFamily"},
    {"name": "labelSize", "label": "Axis label size", "type": "range",
     "min": 6, "max": 24, "step": 1, "default": 12,
     "group": "Typography", "apply": "setAxisLabelSize"},
    {"name": "axisTitleSize", "label": "Axis title size", "type": "range",
     "min": 6, "max": 24, "step": 1, "default": 12,
     "group": "Typography", "apply": "setAxisNameSize"},
    {"name": "legendLabelSize", "label": "Legend label size", "type": "range",
     "min": 6, "max": 24, "step": 1, "default": 12,
     "group": "Typography", "path": "legend.textStyle.fontSize"},

    # Background
    {"name": "backgroundColor", "label": "Background", "type": "color", "default": "#ffffff",
     "group": "Layout", "path": "backgroundColor", "essential": True},

    # Grid
    {"name": "gridTop", "label": "Grid top", "type": "range",
     "min": 0, "max": 200, "step": 2, "default": 60,
     "group": "Grid", "path": "grid.top"},
    {"name": "gridRight", "label": "Grid right", "type": "range",
     "min": 0, "max": 200, "step": 2, "default": 20,
     "group": "Grid", "path": "grid.right"},
    {"name": "gridBottom", "label": "Grid bottom", "type": "range",
     "min": 0, "max": 200, "step": 2, "default": 60,
     "group": "Grid", "path": "grid.bottom"},
    {"name": "gridLeft", "label": "Grid left", "type": "range",
     "min": 0, "max": 200, "step": 2, "default": 60,
     "group": "Grid", "path": "grid.left"},
    {"name": "gridContainLabel", "label": "Contain axis labels", "type": "checkbox", "default": True,
     "group": "Grid", "path": "grid.containLabel"},

    # Legend
    {"name": "legendShow", "label": "Show legend", "type": "checkbox", "default": True,
     "group": "Legend", "path": "legend.show", "essential": True},
    {"name": "legendOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "group": "Legend", "path": "legend.orient", "essential": True},
    {"name": "legendPosition", "label": "Position", "type": "select",
     "options": ["top", "bottom", "left", "right", "top-left", "top-right",
                  "bottom-left", "bottom-right"], "default": "top",
     "group": "Legend", "apply": "setLegendPosition"},
    {"name": "legendItemGap", "label": "Item gap", "type": "range",
     "min": 0, "max": 40, "step": 1, "default": 10,
     "group": "Legend", "path": "legend.itemGap"},
    {"name": "legendItemWidth", "label": "Symbol width", "type": "range",
     "min": 5, "max": 40, "step": 1, "default": 20,
     "group": "Legend", "path": "legend.itemWidth"},
    {"name": "legendItemHeight", "label": "Symbol height", "type": "range",
     "min": 5, "max": 40, "step": 1, "default": 14,
     "group": "Legend", "path": "legend.itemHeight"},
    {"name": "legendIcon", "label": "Icon shape", "type": "select",
     "options": ["circle", "rect", "roundRect", "triangle", "diamond", "pin", "arrow", "none"],
     "default": "circle",
     "group": "Legend", "path": "legend.icon"},

    # Tooltip
    {"name": "tooltipShow", "label": "Show tooltip", "type": "checkbox", "default": True,
     "group": "Tooltip", "path": "tooltip.show", "essential": True},
    {"name": "tooltipTrigger", "label": "Trigger", "type": "select",
     "options": ["item", "axis", "none"], "default": "axis",
     "group": "Tooltip", "path": "tooltip.trigger"},
    {"name": "axisPointerType", "label": "Axis pointer", "type": "select",
     "options": ["line", "shadow", "cross", "none"], "default": "cross",
     "group": "Tooltip", "path": "tooltip.axisPointer.type"},
    {"name": "tooltipBackground", "label": "Background", "type": "color", "default": "#ffffff",
     "group": "Tooltip", "path": "tooltip.backgroundColor"},
    {"name": "tooltipBorderColor", "label": "Border color", "type": "color", "default": "#cccccc",
     "group": "Tooltip", "path": "tooltip.borderColor"},

    # Toolbox
    {"name": "toolboxShow", "label": "Show toolbox", "type": "checkbox", "default": True,
     "group": "Toolbox", "path": "toolbox.show"},
    {"name": "toolboxSaveAsImage", "label": "Save image btn", "type": "checkbox", "default": True,
     "group": "Toolbox", "apply": "setToolboxSaveAsImage"},
    {"name": "toolboxDataZoom", "label": "Data zoom btn", "type": "checkbox", "default": True,
     "group": "Toolbox", "apply": "setToolboxDataZoom"},
    {"name": "toolboxRestore", "label": "Restore btn", "type": "checkbox", "default": True,
     "group": "Toolbox", "apply": "setToolboxRestore"},
    {"name": "toolboxDataView", "label": "Data view btn", "type": "checkbox", "default": False,
     "group": "Toolbox", "apply": "setToolboxDataView"},
    {"name": "toolboxMagicType", "label": "Magic type btn", "type": "checkbox", "default": False,
     "group": "Toolbox", "apply": "setToolboxMagicType"},
    {"name": "toolboxBrush", "label": "Brush btn", "type": "checkbox", "default": False,
     "group": "Toolbox", "apply": "setToolboxBrush"},
    {"name": "toolboxOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "group": "Toolbox", "path": "toolbox.orient"},

    # Data zoom
    {"name": "dataZoomShow", "label": "Show dataZoom", "type": "checkbox", "default": False,
     "group": "DataZoom", "apply": "setDataZoomShow"},
    {"name": "dataZoomInside", "label": "Inside (scroll/pinch)", "type": "checkbox", "default": False,
     "group": "DataZoom", "apply": "setDataZoomInside"},
    {"name": "dataZoomStart", "label": "Start %", "type": "range",
     "min": 0, "max": 100, "step": 1, "default": 0,
     "group": "DataZoom", "apply": "setDataZoomStart"},
    {"name": "dataZoomEnd", "label": "End %", "type": "range",
     "min": 0, "max": 100, "step": 1, "default": 100,
     "group": "DataZoom", "apply": "setDataZoomEnd"},
    {"name": "dataZoomOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "group": "DataZoom", "apply": "setDataZoomOrient"},

    # Axis pointer (global)
    {"name": "axisPointerShow", "label": "Axis pointer", "type": "checkbox", "default": True,
     "group": "Interactivity", "path": "axisPointer.show"},
    {"name": "axisPointerLineType", "label": "Pointer line", "type": "select",
     "options": ["solid", "dashed", "dotted"], "default": "solid",
     "group": "Interactivity", "path": "axisPointer.lineStyle.type"},

    # Animation
    {"name": "animation", "label": "Animation", "type": "checkbox", "default": True,
     "group": "Interactivity", "path": "animation"},
    {"name": "animationDuration", "label": "Animation ms", "type": "range",
     "min": 0, "max": 3000, "step": 100, "default": 1000,
     "group": "Interactivity", "path": "animationDuration"},
]


def _axis_knobs(axis: str) -> List[Dict[str, Any]]:
    """Return a set of axis knobs for 'x' or 'y'."""
    X = "x" if axis == "x" else "y"
    group = "XAxis" if axis == "x" else "YAxis"
    base = f"{axis}Axis[0]"
    prefix = X
    return [
        {"name": f"{prefix}AxisType", "label": "Type", "type": "select",
         "options": ["value", "category", "time", "log"], "default": "value",
         "group": group, "path": f"{base}.type"},
        {"name": f"{prefix}AxisName", "label": "Title", "type": "text", "default": "",
         "group": group, "path": f"{base}.name"},
        {"name": f"{prefix}AxisNameLocation", "label": "Title location", "type": "select",
         "options": ["start", "middle", "center", "end"], "default": "middle" if axis == "y" else "middle",
         "group": group, "path": f"{base}.nameLocation"},
        {"name": f"{prefix}AxisNameGap", "label": "Title gap", "type": "range",
         "min": 0, "max": 100, "step": 1, "default": 30,
         "group": group, "path": f"{base}.nameGap"},
        {"name": f"{prefix}AxisNameRotate", "label": "Title rotate", "type": "range",
         "min": -90, "max": 90, "step": 5, "default": 0,
         "group": group, "path": f"{base}.nameRotate"},
        {"name": f"{prefix}LabelShow", "label": "Show labels", "type": "checkbox", "default": True,
         "group": group, "path": f"{base}.axisLabel.show"},
        {"name": f"{prefix}LabelRotate", "label": "Label rotate", "type": "range",
         "min": -90, "max": 90, "step": 5, "default": 0,
         "group": group, "path": f"{base}.axisLabel.rotate"},
        {"name": f"{prefix}LabelSize", "label": "Label size", "type": "range",
         "min": 6, "max": 20, "step": 1, "default": 12,
         "group": group, "path": f"{base}.axisLabel.fontSize"},
        {"name": f"{prefix}LabelColor", "label": "Label color", "type": "color", "default": "#000000",
         "group": group, "path": f"{base}.axisLabel.color"},
        {"name": f"{prefix}LabelFormat", "label": "Label format", "type": "text", "default": "",
         "group": group, "apply": f"set{X.upper()}AxisLabelFormat"},
        {"name": f"{prefix}LineShow", "label": "Show axis line", "type": "checkbox", "default": True,
         "group": group, "path": f"{base}.axisLine.show"},
        {"name": f"{prefix}TickShow", "label": "Show ticks", "type": "checkbox", "default": True,
         "group": group, "path": f"{base}.axisTick.show"},
        {"name": f"{prefix}SplitLine", "label": "Grid lines", "type": "checkbox",
         "default": axis == "y",
         "group": group, "path": f"{base}.splitLine.show"},
        {"name": f"{prefix}SplitLineColor", "label": "Grid color", "type": "color",
         "default": "#E6E6E6",
         "group": group, "apply": f"set{X.upper()}SplitLineColor"},
        {"name": f"{prefix}Min", "label": "Min", "type": "text", "default": "",
         "group": group, "apply": f"set{X.upper()}Min"},
        {"name": f"{prefix}Max", "label": "Max", "type": "text", "default": "",
         "group": group, "apply": f"set{X.upper()}Max"},
        {"name": f"{prefix}Inverse", "label": "Invert", "type": "checkbox", "default": False,
         "group": group, "path": f"{base}.inverse"},
        {"name": f"{prefix}BoundaryGap", "label": "Boundary gap", "type": "select",
         "options": ["default", "true", "false"], "default": "default",
         "group": group, "apply": f"set{X.upper()}BoundaryGap"},
        {"name": f"{prefix}LogBase", "label": "Log base", "type": "range",
         "min": 2, "max": 10, "step": 1, "default": 10,
         "group": group, "path": f"{base}.logBase"},
    ]


XAXIS_KNOBS = _axis_knobs("x")
YAXIS_KNOBS = _axis_knobs("y")


# -- Per-chart-type knobs --

LINE_KNOBS: List[Dict[str, Any]] = [
    {"name": "lineWidth", "label": "Line width", "type": "range",
     "min": 0.5, "max": 10, "step": 0.5, "default": 2,
     "group": "Mark", "apply": "setLineWidth", "essential": True},
    {"name": "lineSmooth", "label": "Smooth", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setLineSmooth"},
    {"name": "lineStep", "label": "Step", "type": "select",
     "options": ["none", "start", "middle", "end"], "default": "none",
     "group": "Mark", "apply": "setLineStep"},
    {"name": "lineConnectNulls", "label": "Connect nulls", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setLineConnectNulls"},
    {"name": "lineShowSymbol", "label": "Show symbols", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setLineShowSymbol"},
    {"name": "lineSymbolSize", "label": "Symbol size", "type": "range",
     "min": 2, "max": 20, "step": 1, "default": 6,
     "group": "Mark", "apply": "setLineSymbolSize"},
    {"name": "lineAreaFill", "label": "Fill area", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setLineAreaFill"},
    {"name": "lineAreaOpacity", "label": "Area opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.3,
     "group": "Mark", "apply": "setLineAreaOpacity"},
    {"name": "lineStack", "label": "Stack", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setLineStack"},
    {"name": "lineStyleType", "label": "Line style", "type": "select",
     "options": ["solid", "dashed", "dotted"], "default": "solid",
     "group": "Mark", "apply": "setLineStyleType"},
]

BAR_KNOBS: List[Dict[str, Any]] = [
    {"name": "barWidth", "label": "Bar width", "type": "text", "default": "",
     "group": "Mark", "apply": "setBarWidth"},
    {"name": "barMaxWidth", "label": "Max bar width", "type": "text", "default": "",
     "group": "Mark", "apply": "setBarMaxWidth"},
    {"name": "barCategoryGap", "label": "Category gap", "type": "text", "default": "20%",
     "group": "Mark", "apply": "setBarCategoryGap"},
    {"name": "barGap", "label": "Bar gap (within category)", "type": "text", "default": "30%",
     "group": "Mark", "apply": "setBarGap"},
    {"name": "barBorderRadius", "label": "Corner radius", "type": "range",
     "min": 0, "max": 20, "step": 1, "default": 0,
     "group": "Mark", "apply": "setBarBorderRadius"},
    {"name": "barOpacity", "label": "Opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 1.0,
     "group": "Mark", "apply": "setBarOpacity"},
    {"name": "barStack", "label": "Stack", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setBarStack"},
    {"name": "barLabelShow", "label": "Value labels", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setBarLabelShow"},
    {"name": "barLabelPosition", "label": "Label position", "type": "select",
     "options": ["top", "inside", "insideTop", "insideBottom", "bottom"], "default": "top",
     "group": "Mark", "apply": "setBarLabelPosition"},
]

SCATTER_KNOBS: List[Dict[str, Any]] = [
    {"name": "scatterSymbolSize", "label": "Symbol size", "type": "range",
     "min": 2, "max": 60, "step": 1, "default": 10,
     "group": "Mark", "apply": "setScatterSymbolSize", "essential": True},
    {"name": "scatterSymbol", "label": "Symbol", "type": "select",
     "options": ["circle", "rect", "roundRect", "triangle", "diamond", "pin", "arrow"],
     "default": "circle",
     "group": "Mark", "apply": "setScatterSymbol"},
    {"name": "scatterOpacity", "label": "Opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.8,
     "group": "Mark", "apply": "setScatterOpacity"},
    {"name": "scatterBorderWidth", "label": "Border width", "type": "range",
     "min": 0, "max": 6, "step": 0.5, "default": 0,
     "group": "Mark", "apply": "setScatterBorderWidth"},
]

AREA_KNOBS: List[Dict[str, Any]] = [
    {"name": "areaOpacity", "label": "Area opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.6,
     "group": "Mark", "apply": "setAreaOpacity"},
    {"name": "areaStack", "label": "Stack", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setAreaStack"},
    {"name": "areaLineWidth", "label": "Border width", "type": "range",
     "min": 0, "max": 5, "step": 0.5, "default": 1.0,
     "group": "Mark", "apply": "setAreaLineWidth"},
    {"name": "areaSmooth", "label": "Smooth", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setAreaSmooth"},
]

HEATMAP_KNOBS: List[Dict[str, Any]] = [
    {"name": "heatmapShowLabels", "label": "Cell labels", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setHeatmapShowLabels"},
    {"name": "heatmapAutoContrast", "label": "Auto-contrast text", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setHeatmapAutoContrast"},
    {"name": "heatmapBorderWidth", "label": "Cell border", "type": "range",
     "min": 0, "max": 4, "step": 0.5, "default": 0,
     "group": "Mark", "apply": "setHeatmapBorderWidth"},
    {"name": "visualMapShow", "label": "Show visual map", "type": "checkbox", "default": True,
     "group": "VisualMap", "path": "visualMap[0].show"},
    {"name": "visualMapOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "vertical",
     "group": "VisualMap", "path": "visualMap[0].orient"},
    {"name": "visualMapCalculable", "label": "Calculable", "type": "checkbox", "default": True,
     "group": "VisualMap", "path": "visualMap[0].calculable"},
]

PIE_KNOBS: List[Dict[str, Any]] = [
    {"name": "pieInnerRadius", "label": "Inner radius", "type": "text", "default": "0%",
     "group": "Mark", "apply": "setPieInnerRadius"},
    {"name": "pieOuterRadius", "label": "Outer radius", "type": "text", "default": "75%",
     "group": "Mark", "apply": "setPieOuterRadius"},
    {"name": "pieRoseType", "label": "Rose type", "type": "select",
     "options": ["none", "radius", "area"], "default": "none",
     "group": "Mark", "apply": "setPieRoseType"},
    {"name": "pieLabelShow", "label": "Labels", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setPieLabelShow"},
    {"name": "pieLabelPosition", "label": "Label position", "type": "select",
     "options": ["outside", "inside", "center"], "default": "outside",
     "group": "Mark", "apply": "setPieLabelPosition"},
    {"name": "pieLabelLine", "label": "Label leader line", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setPieLabelLine"},
    {"name": "pieBorderRadius", "label": "Slice corner radius", "type": "range",
     "min": 0, "max": 20, "step": 1, "default": 0,
     "group": "Mark", "apply": "setPieBorderRadius"},
]

BOXPLOT_KNOBS: List[Dict[str, Any]] = [
    {"name": "boxBorderWidth", "label": "Border width", "type": "range",
     "min": 0.5, "max": 4, "step": 0.5, "default": 1.0,
     "group": "Mark", "apply": "setBoxBorderWidth"},
    {"name": "boxItemWidth", "label": "Box width", "type": "range",
     "min": 4, "max": 60, "step": 1, "default": 20,
     "group": "Mark", "apply": "setBoxItemWidth"},
]

SANKEY_KNOBS: List[Dict[str, Any]] = [
    {"name": "sankeyNodeWidth", "label": "Node width", "type": "range",
     "min": 5, "max": 40, "step": 1, "default": 20,
     "group": "Mark", "apply": "setSankeyNodeWidth"},
    {"name": "sankeyNodeGap", "label": "Node gap", "type": "range",
     "min": 2, "max": 40, "step": 1, "default": 8,
     "group": "Mark", "apply": "setSankeyNodeGap"},
    {"name": "sankeyOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "group": "Mark", "apply": "setSankeyOrient"},
    {"name": "sankeyLinkOpacity", "label": "Link opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.5,
     "group": "Mark", "apply": "setSankeyLinkOpacity"},
    {"name": "sankeyLinkCurveness", "label": "Link curveness", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.5,
     "group": "Mark", "apply": "setSankeyLinkCurveness"},
    {"name": "sankeyDraggable", "label": "Draggable nodes", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setSankeyDraggable"},
]

TREEMAP_KNOBS: List[Dict[str, Any]] = [
    {"name": "treemapLeafDepth", "label": "Leaf depth", "type": "range",
     "min": 1, "max": 8, "step": 1, "default": 1,
     "group": "Mark", "apply": "setTreemapLeafDepth"},
    {"name": "treemapRoam", "label": "Roam", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setTreemapRoam"},
    {"name": "treemapNodeClick", "label": "Node click", "type": "select",
     "options": ["zoomToNode", "link", "false"], "default": "zoomToNode",
     "group": "Mark", "apply": "setTreemapNodeClick"},
]

SUNBURST_KNOBS: List[Dict[str, Any]] = [
    {"name": "sunburstInnerRadius", "label": "Inner radius", "type": "text", "default": "0%",
     "group": "Mark", "apply": "setSunburstInnerRadius"},
    {"name": "sunburstOuterRadius", "label": "Outer radius", "type": "text", "default": "90%",
     "group": "Mark", "apply": "setSunburstOuterRadius"},
    {"name": "sunburstHighlightPolicy", "label": "Highlight", "type": "select",
     "options": ["descendant", "ancestor", "self", "none"], "default": "descendant",
     "group": "Mark", "apply": "setSunburstHighlightPolicy"},
]

GRAPH_KNOBS: List[Dict[str, Any]] = [
    {"name": "graphLayout", "label": "Layout", "type": "select",
     "options": ["none", "force", "circular"], "default": "force",
     "group": "Mark", "apply": "setGraphLayout"},
    {"name": "graphRoam", "label": "Roam", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setGraphRoam"},
    {"name": "graphRepulsion", "label": "Repulsion (force)", "type": "range",
     "min": 20, "max": 2000, "step": 20, "default": 200,
     "group": "Mark", "apply": "setGraphRepulsion"},
    {"name": "graphEdgeLength", "label": "Edge length (force)", "type": "range",
     "min": 10, "max": 400, "step": 10, "default": 80,
     "group": "Mark", "apply": "setGraphEdgeLength"},
    {"name": "graphEdgeSymbol", "label": "Edge symbol", "type": "select",
     "options": ["none", "arrow", "circle"], "default": "none",
     "group": "Mark", "apply": "setGraphEdgeSymbol"},
    {"name": "graphDraggable", "label": "Draggable", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setGraphDraggable"},
]

CANDLE_KNOBS: List[Dict[str, Any]] = [
    {"name": "candleBullColor", "label": "Bull color", "type": "color", "default": "#c23531",
     "group": "Mark", "apply": "setCandleBullColor"},
    {"name": "candleBearColor", "label": "Bear color", "type": "color", "default": "#314656",
     "group": "Mark", "apply": "setCandleBearColor"},
    {"name": "candleBorderBull", "label": "Border bull", "type": "color", "default": "#c23531",
     "group": "Mark", "apply": "setCandleBorderBull"},
    {"name": "candleBorderBear", "label": "Border bear", "type": "color", "default": "#314656",
     "group": "Mark", "apply": "setCandleBorderBear"},
]

RADAR_KNOBS: List[Dict[str, Any]] = [
    {"name": "radarShape", "label": "Shape", "type": "select",
     "options": ["polygon", "circle"], "default": "polygon",
     "group": "Mark", "apply": "setRadarShape"},
    {"name": "radarSplitNumber", "label": "Split number", "type": "range",
     "min": 2, "max": 10, "step": 1, "default": 5,
     "group": "Mark", "apply": "setRadarSplitNumber"},
    {"name": "radarAreaOpacity", "label": "Area opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.3,
     "group": "Mark", "apply": "setRadarAreaOpacity"},
]

GAUGE_KNOBS: List[Dict[str, Any]] = [
    {"name": "gaugeMin", "label": "Min", "type": "number", "default": 0,
     "group": "Mark", "apply": "setGaugeMin"},
    {"name": "gaugeMax", "label": "Max", "type": "number", "default": 100,
     "group": "Mark", "apply": "setGaugeMax"},
    {"name": "gaugeSplitNumber", "label": "Split number", "type": "range",
     "min": 2, "max": 20, "step": 1, "default": 10,
     "group": "Mark", "apply": "setGaugeSplitNumber"},
    {"name": "gaugeStartAngle", "label": "Start angle", "type": "range",
     "min": -180, "max": 360, "step": 5, "default": 225,
     "group": "Mark", "apply": "setGaugeStartAngle"},
    {"name": "gaugeEndAngle", "label": "End angle", "type": "range",
     "min": -180, "max": 360, "step": 5, "default": -45,
     "group": "Mark", "apply": "setGaugeEndAngle"},
]

CALENDAR_KNOBS: List[Dict[str, Any]] = [
    {"name": "calendarOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "group": "Mark", "apply": "setCalendarOrient"},
    {"name": "calendarCellSize", "label": "Cell size", "type": "range",
     "min": 8, "max": 40, "step": 1, "default": 16,
     "group": "Mark", "apply": "setCalendarCellSize"},
    {"name": "calendarYearLabel", "label": "Year label", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setCalendarYearLabel"},
]

PARALLEL_KNOBS: List[Dict[str, Any]] = [
    {"name": "parallelLineOpacity", "label": "Line opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.45,
     "group": "Mark", "apply": "setParallelLineOpacity"},
    {"name": "parallelLineWidth", "label": "Line width", "type": "range",
     "min": 0.5, "max": 5, "step": 0.5, "default": 1.0,
     "group": "Mark", "apply": "setParallelLineWidth"},
    {"name": "parallelLayoutHorizontal", "label": "Horizontal", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setParallelLayoutHorizontal"},
]

FUNNEL_KNOBS: List[Dict[str, Any]] = [
    {"name": "funnelSort", "label": "Sort", "type": "select",
     "options": ["descending", "ascending", "none"], "default": "descending",
     "group": "Mark", "apply": "setFunnelSort"},
    {"name": "funnelGap", "label": "Gap", "type": "range",
     "min": 0, "max": 20, "step": 1, "default": 2,
     "group": "Mark", "apply": "setFunnelGap"},
    {"name": "funnelMin", "label": "Min", "type": "number", "default": 0,
     "group": "Mark", "apply": "setFunnelMin"},
    {"name": "funnelMax", "label": "Max", "type": "number", "default": 100,
     "group": "Mark", "apply": "setFunnelMax"},
    {"name": "funnelLabelShow", "label": "Labels", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setFunnelLabelShow"},
]

TREE_KNOBS: List[Dict[str, Any]] = [
    {"name": "treeOrient", "label": "Orient", "type": "select",
     "options": ["LR", "RL", "TB", "BT", "radial"], "default": "LR",
     "group": "Mark", "apply": "setTreeOrient"},
    {"name": "treeSymbolSize", "label": "Symbol size", "type": "range",
     "min": 4, "max": 30, "step": 1, "default": 7,
     "group": "Mark", "apply": "setTreeSymbolSize"},
    {"name": "treeRoam", "label": "Roam", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setTreeRoam"},
]


MARK_KNOB_MAP: Dict[str, List[Dict[str, Any]]] = {
    "line":             LINE_KNOBS,
    "multi_line":       LINE_KNOBS,
    "bar":              BAR_KNOBS,
    "bar_horizontal":   BAR_KNOBS,
    "scatter":          SCATTER_KNOBS,
    "scatter_multi":    SCATTER_KNOBS,
    "scatter_studio":   SCATTER_KNOBS,
    "area":             AREA_KNOBS,
    "heatmap":          HEATMAP_KNOBS,
    "correlation_matrix": HEATMAP_KNOBS,
    "pie":              PIE_KNOBS,
    "donut":            PIE_KNOBS,
    "boxplot":          BOXPLOT_KNOBS,
    "sankey":           SANKEY_KNOBS,
    "treemap":          TREEMAP_KNOBS,
    "sunburst":         SUNBURST_KNOBS,
    "graph":            GRAPH_KNOBS,
    "candlestick":      CANDLE_KNOBS,
    "radar":            RADAR_KNOBS,
    "gauge":            GAUGE_KNOBS,
    "calendar_heatmap": CALENDAR_KNOBS,
    "parallel_coords":  PARALLEL_KNOBS,
    "funnel":           FUNNEL_KNOBS,
    "tree":             TREE_KNOBS,
    "raw":              [],
}


# Subset of universal knobs that get duplicated into Essentials for quick access.
ESSENTIAL_NAMES = {
    "titleText", "titleSize",
    "backgroundColor",
    "legendShow", "legendOrient",
    "tooltipShow",
}


def knobs_for(chart_type: str) -> List[Dict[str, Any]]:
    """Return the full knob list for a chart type: universal + axes + mark."""
    if chart_type not in MARK_KNOB_MAP:
        raise ValueError(
            f"Unknown chart_type '{chart_type}'. "
            f"Available: {', '.join(sorted(MARK_KNOB_MAP.keys()))}"
        )
    mark = MARK_KNOB_MAP[chart_type]
    if chart_type in ("pie", "donut", "radar", "gauge", "sankey", "treemap",
                       "sunburst", "graph", "calendar_heatmap", "funnel",
                       "parallel_coords", "tree", "correlation_matrix"):
        axes: List[Dict[str, Any]] = []
    else:
        axes = XAXIS_KNOBS + YAXIS_KNOBS
    return list(UNIVERSAL_KNOBS) + list(axes) + list(mark)


def essentials(chart_type: str) -> List[Dict[str, Any]]:
    """Return an 'Essentials' card subset."""
    all_knobs = knobs_for(chart_type)
    out: List[Dict[str, Any]] = []
    for k in all_knobs:
        if k.get("essential") or k["name"] in ESSENTIAL_NAMES:
            out.append(k)
    return out


def list_chart_types() -> List[str]:
    return sorted(MARK_KNOB_MAP.keys())


def knob_count(chart_type: str) -> Tuple[int, int, int]:
    """Return (universal, axes, mark) knob counts for a type."""
    if chart_type not in MARK_KNOB_MAP:
        raise ValueError(f"Unknown chart_type '{chart_type}'")
    universal = len(UNIVERSAL_KNOBS)
    has_axes = chart_type not in ("pie", "donut", "radar", "gauge", "sankey",
                                    "treemap", "sunburst", "graph",
                                    "calendar_heatmap", "funnel",
                                    "parallel_coords", "tree")
    axes = (len(XAXIS_KNOBS) + len(YAXIS_KNOBS)) if has_axes else 0
    mark = len(MARK_KNOB_MAP[chart_type])
    return universal, axes, mark



# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class EChartResult:
    """Result of make_echart() / wrap_echart().

    Mirrors PRISM's ChartResult shape so it plugs into existing handlers
    including check_charts_quality() which reads `.png_path`.
    """
    option: Dict[str, Any]
    chart_id: str
    chart_type: str
    theme: str
    palette: str
    dimension_preset: str
    width: int
    height: int
    json_path: Optional[str] = None
    html_path: Optional[str] = None
    html: Optional[str] = None
    png_path: Optional[str] = None
    download_url: Optional[str] = None
    editor_download_url: Optional[str] = None
    editor_html_path: Optional[str] = None
    editor_chart_id: Optional[str] = None
    success: bool = True
    success_bool: bool = True  # legacy alias
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    knob_names: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.success_bool = self.success
        if self.html_path and not self.editor_html_path:
            self.editor_html_path = self.html_path
        if self.chart_id and not self.editor_chart_id:
            self.editor_chart_id = self.chart_id

    def save_png(
        self,
        path: Union[str, Path],
        *,
        scale: int = 2,
        width: Optional[int] = None,
        height: Optional[int] = None,
        background: str = "#ffffff",
    ) -> Path:
        """Render this chart's option to PNG via headless Chrome and record
        the absolute path on self.png_path for downstream consumers (e.g.
        check_charts_quality).

        Requires a system Chrome/Chromium binary. Raises RuntimeError if
        Chrome is unavailable.
        """
        from rendering import save_chart_png
        p = save_chart_png(
            self.option, path,
            width=int(width if width is not None else self.width),
            height=int(height if height is not None else self.height),
            theme=self.theme,
            scale=scale,
            background=background,
        )
        self.png_path = str(p)
        return p


@dataclass
class EChartSpecSheet:
    """Named bundle of user preferences -- saved via the editor, applied on
    load. Stores styling only (title/subtitle text are chart-specific content,
    not user prefs)."""
    spec_sheet_id: str
    name: str
    description: str = ""
    owner: str = ""
    scope: str = "global"
    base_theme: str = "gs_clean"
    base_palette: str = "gs_primary"
    base_dimension_preset: str = "wide"
    overrides: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def new(cls, name: str, **kwargs) -> "EChartSpecSheet":
        now = datetime.now(timezone.utc).isoformat()
        slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "sheet"
        return cls(
            spec_sheet_id=kwargs.pop("spec_sheet_id", slug),
            name=name, created_at=now, updated_at=now, **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EChartSpecSheet":
        return cls(**d)

    @classmethod
    def from_json(cls, s: str) -> "EChartSpecSheet":
        return cls.from_dict(json.loads(s))


# =============================================================================
# CORE HELPERS
# =============================================================================


def _compute_chart_id(option: Dict[str, Any]) -> str:
    canonical = json.dumps(option, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(canonical).hexdigest()[:12]


def _slug(s: Optional[str]) -> str:
    if not s:
        return "chart"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return slug or "chart"


def _coerce_option(option: Any) -> Dict[str, Any]:
    if isinstance(option, dict):
        return option
    if isinstance(option, str):
        return json.loads(option)
    raise TypeError(
        f"Cannot coerce {type(option).__name__} to ECharts option dict. "
        "Pass a dict or JSON string."
    )


def validate_option(option: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Minimal structural check on an ECharts option. Returns (ok, warnings).

    ok is True only when the option is a dict containing a non-empty `series`
    entry whose members each have a `type` field.
    """
    warnings: List[str] = []
    if not isinstance(option, dict):
        return False, ["option must be a dict"]
    series = option.get("series")
    if series is None:
        warnings.append("option has no 'series'")
        return False, warnings
    if isinstance(series, dict):
        if "type" not in series:
            warnings.append("option.series missing 'type'")
            return False, warnings
        return True, warnings
    if isinstance(series, list):
        if not series:
            warnings.append("option.series is empty")
            return False, warnings
        for i, s in enumerate(series):
            if not isinstance(s, dict):
                warnings.append(f"option.series[{i}] is not a dict")
                return False, warnings
            if "type" not in s:
                warnings.append(f"option.series[{i}] missing 'type'")
                return False, warnings
        return True, warnings
    warnings.append("option.series must be a dict or list")
    return False, warnings


# =============================================================================
# BUILDER DISPATCH
# =============================================================================


def build_waterfall(df, mapping: Dict[str, Any],
                       ctx: BuilderContext) -> Dict[str, Any]:
    """Waterfall (decomposition) chart.

    Each row is either an incremental delta or a full-height total.
    Implementation uses a hidden "base" stacked bar plus a colored
    "delta" bar; ECharts' built-in stacking gives us the up-from /
    down-from-previous-running-total semantics for free.

    Mapping:
        x         category column (required)
        y         signed delta value column (required)
        is_total  optional column whose truthy cells render as
                  full-height totals from zero (e.g. opening / closing
                  bars of a P&L bridge)
        pos_color / neg_color / total_color hex overrides
        label_format echarts function string for cell labels
    """
    xc = mapping.get("x"); yc = mapping.get("y")
    if not xc or not yc:
        raise ValueError("waterfall: mapping requires 'x' and 'y'")
    if df is None:
        raise ValueError("waterfall: DataFrame is required")
    total_c = mapping.get("is_total")
    need = [xc, yc] + ([total_c] if total_c else [])
    _ensure_columns(df, need, "waterfall")

    cats = [str(v) for v in _col_to_list(df, xc)]
    vals = _col_to_list(df, yc)
    is_total = (
        [bool(v) for v in _col_to_list(df, total_c)]
        if total_c else [False] * len(cats)
    )
    pos_color = mapping.get("pos_color") or "#2F855A"
    neg_color = mapping.get("neg_color") or "#C53030"
    total_color = mapping.get("total_color") or "#003359"

    base: List[Optional[float]] = []
    deltas: List[Dict[str, Any]] = []
    running = 0.0
    for v, total in zip(vals, is_total):
        try:
            num = float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            num = 0.0
        if total:
            base.append(0.0)
            color = total_color
            deltas.append({"value": num,
                            "itemStyle": {"color": color}})
            running = num
        else:
            color = pos_color if num >= 0 else neg_color
            if num >= 0:
                base.append(running)
                deltas.append({"value": num,
                                "itemStyle": {"color": color}})
                running += num
            else:
                # Negative delta: stack downward by setting base to
                # running+num and rendering |num| as the bar height.
                base.append(running + num)
                deltas.append({"value": -num,
                                "itemStyle": {"color": color}})
                running += num

    # Per-bar label values track the SIGNED delta for readability,
    # not the absolute value used in the stacked bar height.
    label_vals = []
    for v, total in zip(vals, is_total):
        try:
            label_vals.append(float(v) if v is not None else 0.0)
        except (TypeError, ValueError):
            label_vals.append(0.0)

    label_fmt = mapping.get("label_format") or (
        "function(p){var i=p.dataIndex;var lv=p.value;"
        "if(lv == null) return '';"
        "var sign = lv > 0 ? '+' : (lv < 0 ? '-' : '');"
        "var v = Math.abs(lv);"
        "var s = v >= 1000 ? v.toFixed(0) : (v >= 10 ? v.toFixed(1) : v.toFixed(2));"
        "return sign + s;}"
    )

    opt = _base_option(ctx)
    opt["xAxis"] = {"type": "category", "data": cats, "name": ""}
    opt["yAxis"] = {"type": "value", "name": "",
                     "splitLine": {"show": True}}
    opt["legend"]["show"] = False
    opt["tooltip"]["axisPointer"] = {"type": "shadow"}
    opt["series"] = [
        # Invisible base bar that lifts the visible delta to its
        # running-total starting point.
        {"name": "base", "type": "bar", "stack": "total",
          "data": [{"value": b, "itemStyle":
                     {"color": "rgba(0,0,0,0)",
                      "borderColor": "rgba(0,0,0,0)"}}
                     for b in base],
          "tooltip": {"show": False},
          "silent": True,
          "label": {"show": False}},
        {"name": "delta", "type": "bar", "stack": "total",
          "data": deltas,
          "label": {"show": True, "position": "top",
                     "formatter": label_fmt,
                     "fontSize": 11},
          # Override formatter values to use the signed deltas, not the
          # absolute bar heights -- ECharts passes the bar's own value
          # to formatter callbacks, but the stack uses absolutes for
          # negatives. We attach `value` as the signed value via
          # post-build polish (see waterfall_label_signed_values).
          },
    ]
    # Tag deltas with their signed label_value for the formatter.
    for d, sv in zip(deltas, label_vals):
        d["label_value"] = sv
    # Patch the data to expose `value` as the signed delta to the
    # label formatter (ECharts reads `params.value` from
    # data[i].value -- so we replace the absolute stack-height with
    # the signed delta and let `_label_value` carry the absolute via
    # a separate channel in the tooltip).
    # Simplest: change the formatter to compute from dataIndex.
    label_fmt_signed = (
        "function(p){var arr = " + json.dumps(label_vals) + ";"
        "var lv = arr[p.dataIndex];"
        "if(lv == null || lv === 0) return '';"
        "var sign = lv > 0 ? '+' : '-';"
        "var v = Math.abs(lv);"
        "var s = v >= 1000 ? v.toFixed(0) : (v >= 10 ? v.toFixed(1) : v.toFixed(2));"
        "return sign + s;}"
    )
    opt["series"][1]["label"]["formatter"] = label_fmt_signed
    # Tooltip should also use the signed delta:
    opt["tooltip"]["formatter"] = (
        "function(params){var arr=" + json.dumps(label_vals) + ";"
        "var p = Array.isArray(params) ? params[params.length-1] : params;"
        "var lv = arr[p.dataIndex];"
        "var sign = lv > 0 ? '+' : (lv < 0 ? '-' : '');"
        "var v = Math.abs(lv);"
        "var s = v >= 1000 ? v.toFixed(0) : (v >= 10 ? v.toFixed(1) : v.toFixed(2));"
        "return p.name + ': ' + sign + s;}"
    )
    _autorotate_x_category_labels(opt, ctx)
    _apply_axis_titles(opt, mapping, horizontal=False, chart_width=ctx.width)
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_slope(df, mapping: Dict[str, Any],
                  ctx: BuilderContext) -> Dict[str, Any]:
    """Slope chart: two snapshots joined by sloped lines per category.

    Mapping:
        x       snapshot column (must have exactly 2 distinct values)
        y       numeric value column
        color   per-line category column
        x_sort  optional explicit ordering of the two snapshot values
    """
    xc = mapping.get("x"); yc = mapping.get("y")
    cc = mapping.get("color")
    if not (xc and yc and cc):
        raise ValueError(
            "slope: mapping requires 'x' (snapshot), 'y' (value), "
            "'color' (per-line category)"
        )
    if df is None:
        raise ValueError("slope: DataFrame is required")
    _ensure_columns(df, [xc, yc, cc], "slope")

    # Determine snapshot order: x_sort wins; otherwise first-seen order.
    explicit = mapping.get("x_sort")
    seen: List[Any] = []
    if isinstance(explicit, (list, tuple)) and len(explicit) >= 2:
        for v in explicit:
            if v not in seen:
                seen.append(v)
    else:
        for v in _col_to_list(df, xc):
            if v not in seen:
                seen.append(v)
    if len(seen) < 2:
        raise ValueError(
            f"slope: x column '{xc}' has only {len(seen)} distinct "
            f"value(s); needs >= 2 (left + right snapshots)"
        )
    snap_left, snap_right = seen[0], seen[1]
    snap_labels = [str(snap_left), str(snap_right)]

    # Group by category and pick left + right values.
    cat_order = _unique(_col_to_list(df, cc))
    series: List[Dict[str, Any]] = []
    palette = list(ctx.palette_colors) if ctx.palette_kind == "categorical" else []
    for i, cat in enumerate(cat_order):
        sub = df[df[cc] == cat]
        lookup = dict(zip(_col_to_list(sub, xc),
                            _col_to_list(sub, yc)))
        lv = lookup.get(snap_left)
        rv = lookup.get(snap_right)
        # Skip categories missing one of the two snapshots.
        if lv is None or rv is None:
            continue
        color = palette[i % len(palette)] if palette else "#002F6C"
        series.append({
            "type": "line", "name": str(cat),
            "data": [lv, rv],
            "symbol": "circle", "symbolSize": 8,
            "lineStyle": {"width": 2, "color": color},
            "itemStyle": {"color": color},
            "label": {"show": True,
                       "position": "right",
                       "formatter": (
                           "function(p){return p.dataIndex===1 ? "
                           "'  ' + p.seriesName : '';}"
                       ),
                       "fontSize": 11},
            "endLabel": {"show": False},
            "emphasis": {"focus": "series"},
        })

    opt = _base_option(ctx)
    opt["xAxis"] = {"type": "category", "data": snap_labels,
                     "boundaryGap": False, "name": "",
                     "axisLine": {"show": True},
                     "splitLine": {"show": False},
                     "axisTick": {"show": True}}
    opt["yAxis"] = {"type": "value", "name": "",
                     "splitLine": {"show": True}}
    opt["legend"]["show"] = False
    # Add right padding so the per-line labels don't get clipped.
    opt["grid"]["right"] = 140
    opt["series"] = series
    opt["tooltip"]["axisPointer"] = {"type": "shadow"}
    _apply_axis_titles(opt, mapping, horizontal=False, chart_width=ctx.width)
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_fan_cone(df, mapping: Dict[str, Any],
                      ctx: BuilderContext) -> Dict[str, Any]:
    """Fan / cone forecast chart: a central path plus N stacked
    confidence bands rendered as shaded ribbons.

    Mapping:
        x         time column (required)
        y         central path column (required)
        bands     list of {lower, upper, label?, color?, opacity?}
                  pairs (required). Outer bands rendered first so
                  inner bands sit on top.
        line_color override for the central path
    """
    xc = mapping.get("x"); yc = mapping.get("y")
    bands = mapping.get("bands")
    if not (xc and yc):
        raise ValueError(
            "fan_cone: mapping requires 'x' (time) and 'y' (central path)"
        )
    if not isinstance(bands, (list, tuple)) or not bands:
        raise ValueError(
            "fan_cone: mapping.bands must be a non-empty list of "
            "{lower, upper, label?} dicts"
        )
    if df is None:
        raise ValueError("fan_cone: DataFrame is required")

    band_cols: List[str] = []
    for band in bands:
        if not isinstance(band, dict):
            raise ValueError(
                "fan_cone: each band must be a dict {lower, upper, ...}"
            )
        lo = band.get("lower"); hi = band.get("upper")
        if not (isinstance(lo, str) and isinstance(hi, str)):
            raise ValueError(
                "fan_cone: each band dict needs string 'lower' and "
                "'upper' column names"
            )
        band_cols.extend([lo, hi])
    _ensure_columns(df, [xc, yc] + band_cols, "fan_cone")

    x_vals = _col_to_list(df, xc)
    central = _col_to_list(df, yc)

    # Default band colors: navy with declining opacity for outer -> inner
    palette_color = (
        list(ctx.palette_colors)[0] if ctx.palette_colors else "#003359"
    )
    n_bands = len(bands)
    series: List[Dict[str, Any]] = []
    for i, band in enumerate(bands):
        lo_col = band["lower"]; hi_col = band["upper"]
        lo_vals = _col_to_list(df, lo_col)
        hi_vals = _col_to_list(df, hi_col)
        opacity = float(band.get("opacity",
                                    0.10 + (0.20 * i / max(1, n_bands - 1))))
        color = band.get("color") or palette_color
        label = band.get("label") or f"{lo_col}-{hi_col}"

        # ECharts trick: two stacked-area series. The first is the
        # lower bound (transparent fill), the second is the difference
        # (upper - lower) stacked on top with the band's color/opacity.
        diff = []
        for lo, hi in zip(lo_vals, hi_vals):
            if lo is None or hi is None:
                diff.append(None)
            else:
                try:
                    diff.append(float(hi) - float(lo))
                except (TypeError, ValueError):
                    diff.append(None)

        stack_name = f"_band_{i}"
        series.append({
            "name": f"_lower_{i}", "type": "line",
            "data": list(zip(x_vals, lo_vals)),
            "stack": stack_name,
            "symbol": "none", "lineStyle": {"opacity": 0},
            "areaStyle": {"opacity": 0, "color": "rgba(0,0,0,0)"},
            "tooltip": {"show": False}, "silent": True,
            "_band_internal": True,
        })
        series.append({
            "name": label, "type": "line",
            "data": list(zip(x_vals, diff)),
            "stack": stack_name,
            "symbol": "none",
            "lineStyle": {"opacity": 0},
            "areaStyle": {"opacity": opacity, "color": color},
            "tooltip": {"show": False},
            "_band_internal": False,
        })

    line_color = mapping.get("line_color") or palette_color
    series.append({
        "name": str(yc), "type": "line",
        "data": list(zip(x_vals, central)),
        "symbol": "none", "smooth": False,
        "lineStyle": {"width": 2, "color": line_color},
        "z": 10,
    })

    opt = _base_option(ctx)
    # Prefer time axis when x looks like timestamps; the dashboard
    # filter rewire path also keys off time-typed x axes.
    opt["xAxis"] = _time_axis_if_needed(df, xc) if xc else {"type": "category"}
    opt["xAxis"]["name"] = ""
    opt["yAxis"] = {"type": "value", "name": "",
                     "splitLine": {"show": True}}
    opt["legend"]["data"] = [b.get("label") or
                               f"{b['lower']}-{b['upper']}"
                               for b in bands] + [str(yc)]
    # Hide internal lower-bound helper series from the legend.
    opt["legend"]["selector"] = False
    opt["series"] = series
    opt["tooltip"] = {"trigger": "axis",
                        "axisPointer": {"type": "cross"}}
    _apply_axis_titles(opt, mapping, horizontal=False, chart_width=ctx.width)
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_marimekko(df, mapping: Dict[str, Any],
                       ctx: BuilderContext) -> Dict[str, Any]:
    """Marimekko / mosaic: 2D categorical proportions.

    Each x-category is rendered as a column whose width is proportional
    to its share of total value; within a column, y-categories are
    stacked at heights proportional to their share of that column's
    total. The result is a single rectangle of unit area where every
    cell's area equals its share of the grand total.

    Mapping:
        x        column-axis category column (required)
        y        row-axis category column (required)
        value    cell magnitude column (required)
        order_x  optional explicit x-category order (list)
        order_y  optional explicit y-category order (list)
    """
    xc = mapping.get("x"); yc = mapping.get("y")
    vc = mapping.get("value")
    if not (xc and yc and vc):
        raise ValueError(
            "marimekko: mapping requires 'x' (column category), "
            "'y' (row category), 'value' (numeric magnitude)"
        )
    if df is None:
        raise ValueError("marimekko: DataFrame is required")
    _ensure_columns(df, [xc, yc, vc], "marimekko")

    x_order = mapping.get("order_x") or _unique(_col_to_list(df, xc))
    y_order = mapping.get("order_y") or _unique(_col_to_list(df, yc))

    # Build a 2D matrix value[y][x] in the requested order
    xs_raw = _col_to_list(df, xc)
    ys_raw = _col_to_list(df, yc)
    vs_raw = _col_to_list(df, vc)
    grid: Dict[Tuple[Any, Any], float] = {}
    for x, y, v in zip(xs_raw, ys_raw, vs_raw):
        try:
            num = float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            num = 0.0
        grid[(x, y)] = grid.get((x, y), 0.0) + num

    col_totals = []
    for x in x_order:
        col_totals.append(sum(grid.get((x, y), 0.0) for y in y_order))
    grand_total = sum(col_totals) or 1.0

    # Compute rectangle layout: each column starts at running x_offset;
    # each cell within a column starts at running y_offset (top-down).
    # We represent each cell as a custom-rendered rect with absolute
    # data values; render_js converts to pixel coords.
    items: List[Dict[str, Any]] = []
    palette = list(ctx.palette_colors) if ctx.palette_kind == "categorical" else []
    x_offset = 0.0
    for xi, (x, col_t) in enumerate(zip(x_order, col_totals)):
        col_share = col_t / grand_total
        y_offset = 0.0
        for yi, y in enumerate(y_order):
            v = grid.get((x, y), 0.0)
            row_share = (v / col_t) if col_t > 0 else 0.0
            color = (palette[yi % len(palette)] if palette
                       else "#003359")
            items.append({
                "name": f"{y} | {x}",
                "value": [x_offset, y_offset, col_share, row_share, v,
                            str(x), str(y)],
                "itemStyle": {"color": color, "borderColor": "#fff",
                                "borderWidth": 1},
            })
            y_offset += row_share
        x_offset += col_share

    render_js = """function(params, api){
  var x0 = api.value(0); var y0 = api.value(1);
  var w = api.value(2);  var h = api.value(3);
  var p0 = api.coord([x0, y0]);
  var p1 = api.coord([x0 + w, y0 + h]);
  var rectShape = echarts.graphic.clipRectByRect({
    x: Math.min(p0[0], p1[0]),
    y: Math.min(p0[1], p1[1]),
    width: Math.abs(p1[0] - p0[0]),
    height: Math.abs(p1[1] - p0[1])
  }, {
    x: api.coord([0, 0])[0], y: api.coord([1, 1])[1],
    width: api.coord([1, 0])[0] - api.coord([0, 0])[0],
    height: api.coord([0, 0])[1] - api.coord([1, 1])[1]
  });
  return rectShape && {
    type: 'rect',
    transition: ['shape'],
    shape: rectShape,
    style: api.style({stroke: '#fff', lineWidth: 1})
  };
}"""

    tooltip_js = (
        "function(p){"
        "var v = p.value; var pct_col = (v[2]*100).toFixed(1);"
        "var pct_row = (v[3]*100).toFixed(1);"
        "var raw = v[4];"
        "var s = raw >= 1000 ? raw.toFixed(0) : "
        "(raw >= 10 ? raw.toFixed(1) : raw.toFixed(2));"
        "return v[6] + ' / ' + v[5] + '<br/>' "
        "+ 'value ' + s + ' &middot; ' + pct_col + '% of column' "
        "+ ' &middot; ' + pct_row + '% of cell row';}"
    )

    opt = _base_option(ctx)
    opt["xAxis"] = {"type": "value", "min": 0, "max": 1,
                     "show": False}
    opt["yAxis"] = {"type": "value", "min": 0, "max": 1,
                     "show": False, "inverse": False}
    opt["grid"] = {"top": 80, "right": 20, "bottom": 60, "left": 76,
                    "containLabel": False}
    opt["legend"] = {"show": True, "top": 42, "left": "center",
                       "data": [str(y) for y in y_order]}
    opt["tooltip"] = {"trigger": "item", "formatter": tooltip_js}
    opt["series"] = [{
        "type": "custom",
        "renderItem": render_js,
        "data": items,
        "encode": {"x": [0, 2], "y": [1, 3],
                     "tooltip": [4, 5, 6]},
        # One legend entry per y-category. We emit a phantom dataset
        # for legend grouping by mapping each item's `name` to the
        # y-category prefix; ECharts picks up legendHoverLink that way.
    }]
    # Add a tiny x-axis label strip below the canvas listing the column
    # categories with their shares.
    cat_label_strip = " | ".join(
        f"{x} {(t/grand_total)*100:.0f}%"
        for x, t in zip(x_order, col_totals)
    )
    opt["graphic"] = [{
        "type": "text", "left": "center", "bottom": 14,
        "style": {"text": cat_label_strip,
                    "fill": "#4a5568",
                    "fontSize": 11},
    }]
    return opt


# Dispatch table: chart_type -> callable(df, mapping, ctx) -> dict.
# The bijection between this dict's keys and ``CHART_TYPES`` in
# echart_dashboard.py is pinned by
# ``test_chart_type_dispatch_covers_valid_chart_types`` in dev/tests.py.
#
# Most entries are direct references to a build_<kind> function.
# Three groups need a kwarg dispatch (``functools.partial``) because
# two chart types share one underlying builder distinguished by a
# boolean flag:
#   * bar / bar_horizontal share ``build_bar`` (horizontal flag)
#   * pie / donut          share ``build_pie`` (donut flag)
#   * treemap / sunburst   share ``build_treemap`` (is_sunburst flag)
# Three further entries are aliases (different chart_type, same builder):
#   * multi_line     -> build_line
#   * scatter_multi  -> build_scatter
#   * parallel_coords -> build_parallel
_BUILDER_DISPATCH = {
    "line":               build_line,
    "multi_line":         build_line,
    "bar":                partial(build_bar, horizontal=False),
    "bar_horizontal":     partial(build_bar, horizontal=True),
    "scatter":            build_scatter,
    "scatter_multi":      build_scatter,
    "scatter_studio":     build_scatter_studio,
    "area":               build_area,
    "heatmap":            build_heatmap,
    "geo_map":            build_geo_map,
    "correlation_matrix": build_correlation_matrix,
    "pie":                partial(build_pie, donut=False),
    "donut":              partial(build_pie, donut=True),
    "boxplot":            build_boxplot,
    "histogram":          build_histogram,
    "bullet":             build_bullet,
    "sankey":             build_sankey,
    "treemap":            partial(build_treemap, is_sunburst=False),
    "sunburst":           partial(build_treemap, is_sunburst=True),
    "graph":              build_graph,
    "candlestick":        build_candlestick,
    "radar":              build_radar,
    "gauge":              build_gauge,
    "calendar_heatmap":   build_calendar_heatmap,
    "funnel":             build_funnel,
    "parallel_coords":    build_parallel,
    "tree":               build_tree,
    "waterfall":          build_waterfall,
    "slope":              build_slope,
    "fan_cone":           build_fan_cone,
    "marimekko":          build_marimekko,
}


def _build_context(
    chart_type: str,
    theme: str,
    palette: Optional[str],
    dimensions: str,
    title: Optional[str],
    subtitle: Optional[str],
) -> BuilderContext:
    theme_obj = get_theme(theme)
    palette_name = palette or theme_obj["palette"]
    palette_obj = get_palette(palette_name)
    dim = get_dimension_preset(dimensions)
    typography = get_typography_override(dimensions)

    return BuilderContext(
        chart_type=chart_type,
        title=title,
        subtitle=subtitle,
        theme_name=theme,
        theme_colors=list(theme_obj["echarts"].get("color", [])),
        palette_name=palette_name,
        palette_colors=list(palette_obj["colors"]),
        palette_kind=palette_obj["kind"],
        dimension_preset=dimensions,
        width=dim["width"],
        height=dim["height"],
        typography=typography,
    )


# =============================================================================
# PUBLIC API
# =============================================================================


def make_echart(
    df: Any = None,
    chart_type: str = "line",
    mapping: Optional[Dict[str, Any]] = None,
    option: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    theme: str = "gs_clean",
    palette: Optional[str] = None,
    dimensions: str = "wide",
    annotations: Optional[List[Dict[str, Any]]] = None,
    session_path: Optional[Union[str, Path]] = None,
    chart_name: Optional[str] = None,
    save_as: Optional[str] = None,
    write_html: bool = True,
    write_json: bool = True,
    save_png: bool = False,
    png_scale: int = 2,
    spec_sheets: Optional[Dict[str, Dict[str, Any]]] = None,
    active_spec_sheet: Optional[str] = None,
    user_id: Optional[str] = None,
) -> EChartResult:
    """Produce an ECharts option from a DataFrame and mapping.

    Two paths:
        (a) df + chart_type + mapping     ->  builder produces option
        (b) option=...                    ->  passthrough (raw ECharts option)

    Annotations (hline, vline, band, arrow, point) are attached as markLine/
    markArea/markPoint on the primary series after the builder runs.

    When session_path is supplied, writes {session_path}/echarts/{name}.json
    and (if write_html) {session_path}/echarts/{name}.html.
    """
    if chart_type not in _BUILDER_DISPATCH and chart_type != "raw":
        raise ValueError(
            f"Unknown chart_type '{chart_type}'. "
            f"Available: {', '.join(sorted(list(_BUILDER_DISPATCH.keys()) + ['raw']))}"
        )

    ctx = _build_context(chart_type if chart_type != "raw" else "line",
                           theme, palette, dimensions, title, subtitle)

    if option is not None:
        opt = _coerce_option(option)
        opt = copy.deepcopy(opt)
        if title is not None:
            opt.setdefault("title", {})["text"] = title
        if subtitle is not None:
            opt.setdefault("title", {})["subtext"] = subtitle
        if ctx.palette_colors and ctx.palette_kind == "categorical" and "color" not in opt:
            opt["color"] = list(ctx.palette_colors)
    else:
        if mapping is None:
            raise ValueError("make_echart: either 'option' or 'mapping' must be given.")
        builder = _BUILDER_DISPATCH.get(chart_type)
        if builder is None:
            raise ValueError(f"No builder for chart_type '{chart_type}'.")
        opt = builder(df, dict(mapping), ctx)

    mapping_annotations = (mapping or {}).get("annotations") if mapping else None
    combined_annotations: List[Dict[str, Any]] = []
    combined_annotations.extend(_normalize_annotations(mapping_annotations))
    combined_annotations.extend(_normalize_annotations(annotations))
    if combined_annotations:
        _apply_annotations(opt, combined_annotations)

    # Bump grid.top when legend wraps to multiple rows so the chart
    # canvas isn't shoved beneath a wrapped legend.
    _grow_grid_for_legend(opt, ctx.width)

    _install_default_axis_decimal_cap(opt)
    _install_default_tooltip_decimal_cap(opt)

    ok, warnings = validate_option(opt)
    chart_id = _compute_chart_id(opt)

    knob_defs = knobs_for(chart_type) if chart_type in MARK_KNOB_MAP else []
    knob_names = [k["name"] for k in knob_defs]

    # Paths
    json_path: Optional[Path] = None
    html_path: Optional[Path] = None
    html: Optional[str] = None
    if save_as:
        p = Path(save_as)
        json_path = p.with_suffix(".json")
        html_path = p.with_suffix(".html") if write_html else None
    elif session_path:
        sp = Path(session_path)
        name = chart_name or f"chart_{chart_id}"
        out = sp / "echarts"
        out.mkdir(parents=True, exist_ok=True)
        json_path = out / f"{_slug(name)}.json"
        html_path = (out / f"{_slug(name)}.html") if write_html else None

    if json_path and write_json:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(opt, indent=2, default=str), encoding="utf-8")

    if html_path and write_html:
        html = render_editor_html(
            option=opt,
            chart_id=chart_id,
            chart_type=chart_type,
            theme=theme,
            palette=ctx.palette_name,
            dimension_preset=dimensions,
            knob_defs=knob_defs,
            spec_sheets=spec_sheets or {},
            active_spec_sheet=active_spec_sheet,
            user_id=user_id,
            filename_base=_slug(chart_name or (title or "chart")),
        )
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

    result = EChartResult(
        option=opt,
        chart_id=chart_id,
        chart_type=chart_type,
        theme=theme,
        palette=ctx.palette_name,
        dimension_preset=dimensions,
        width=ctx.width,
        height=ctx.height,
        json_path=str(json_path) if json_path else None,
        html_path=str(html_path) if html_path else None,
        html=html,
        success=ok,
        warnings=list(warnings),
        knob_names=knob_names,
    )

    if save_png:
        png_path: Optional[Path] = None
        if save_as:
            png_path = Path(save_as).with_suffix(".png")
        elif session_path:
            sp = Path(session_path)
            name = chart_name or f"chart_{chart_id}"
            png_path = sp / "echarts" / f"{_slug(name)}.png"
        if png_path is not None:
            try:
                result.save_png(png_path, scale=int(png_scale))
            except Exception as e:  # noqa: BLE001
                result.warnings.append(f"PNG export failed: {e}")
        else:
            result.warnings.append(
                "save_png=True but neither session_path nor save_as provided"
            )

    return result


def wrap_echart(
    option: Any,
    chart_type: Optional[str] = None,
    theme: str = "gs_clean",
    palette: Optional[str] = None,
    dimensions: str = "wide",
    title: Optional[str] = None,
    output_path: Optional[Union[str, Path]] = None,
    spec_sheets: Optional[Dict[str, Dict[str, Any]]] = None,
    active_spec_sheet: Optional[str] = None,
    user_id: Optional[str] = None,
) -> EChartResult:
    """Wrap a pre-built ECharts option dict into the interactive editor HTML.

    Use this when the caller has already produced an option (e.g. from a
    pre-existing JSON asset or hand-rolled dict) and just wants the editor
    wrapper.
    """
    opt = _coerce_option(option)
    inferred = chart_type or _infer_chart_type(opt)
    ctx = _build_context(inferred if inferred in MARK_KNOB_MAP else "line",
                           theme, palette, dimensions, title, None)

    if title is not None:
        opt.setdefault("title", {})["text"] = title

    chart_id = _compute_chart_id(opt)
    knob_defs = knobs_for(inferred) if inferred in MARK_KNOB_MAP else []
    html = render_editor_html(
        option=opt, chart_id=chart_id, chart_type=inferred,
        theme=theme, palette=ctx.palette_name, dimension_preset=dimensions,
        knob_defs=knob_defs,
        spec_sheets=spec_sheets or {}, active_spec_sheet=active_spec_sheet,
        user_id=user_id, filename_base=_slug(title or "chart"),
    )
    html_path: Optional[Path] = None
    if output_path:
        html_path = Path(output_path)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

    ok, warnings = validate_option(opt)
    return EChartResult(
        option=opt,
        chart_id=chart_id,
        chart_type=inferred,
        theme=theme,
        palette=ctx.palette_name,
        dimension_preset=dimensions,
        width=ctx.width,
        height=ctx.height,
        html=html,
        html_path=str(html_path) if html_path else None,
        success=ok,
        warnings=list(warnings),
        knob_names=[k["name"] for k in knob_defs],
    )


def _infer_chart_type(option: Dict[str, Any]) -> str:
    """Best-effort detect chart type from option.series[0].type."""
    series = option.get("series")
    if isinstance(series, dict):
        series = [series]
    if isinstance(series, list) and series:
        t = series[0].get("type", "line")
        if t == "pie":
            first = series[0]
            r = first.get("radius")
            if isinstance(r, (list, tuple)) and len(r) == 2 and str(r[0]).strip() != "0%":
                return "donut"
            return "pie"
        mapping = {
            "line": "line", "bar": "bar", "scatter": "scatter",
            "effectScatter": "scatter", "sankey": "sankey", "treemap": "treemap",
            "sunburst": "sunburst", "graph": "graph", "candlestick": "candlestick",
            "radar": "radar", "gauge": "gauge", "heatmap": "heatmap",
            "boxplot": "boxplot", "funnel": "funnel", "parallel": "parallel_coords",
            "tree": "tree",
        }
        return mapping.get(t, "line")
    return "line"


# =============================================================================
# MODULE-LEVEL LISTING HELPERS (for CLI)
# =============================================================================


def info_option(option: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a raw option dict for the CLI 'info' command."""
    chart_type = _infer_chart_type(option)
    series = option.get("series")
    if isinstance(series, dict):
        series = [series]
    series_count = len(series) if isinstance(series, list) else 0
    has_x = "xAxis" in option
    has_y = "yAxis" in option
    has_grid = "grid" in option
    has_visual_map = "visualMap" in option
    return {
        "chart_type": chart_type,
        "series_count": series_count,
        "has_xAxis": has_x,
        "has_yAxis": has_y,
        "has_grid": has_grid,
        "has_visualMap": has_visual_map,
        "has_tooltip": "tooltip" in option,
        "has_legend": "legend" in option,
    }
