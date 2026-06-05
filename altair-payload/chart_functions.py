"""
chart_functions.py
==================

Vega/Altair chart engine for PRISM. Single-file consolidation of the
``vega_charts`` package, exposing TWO public APIs that share one
rendering pipeline:

  * **v1 surface** (legacy / verbose, currently the canonical
    PRISM-facing API): ``make_chart()``, the composite layout helpers
    (``make_2pack_horizontal``, ``make_2pack_vertical``,
    ``make_3pack_triangle``, ``make_4pack_grid``, ``make_6pack_grid``),
    ``ChartSpec``, ``check_charts_quality``.
  * **v2 surface** (cleaner builder API, opt-in): the ``Chart`` class
    for both standalone and composite use, and ``render_grid`` for
    one-call composites. Auto QC + cleanup + URL printing are
    absorbed into the render path; flat kwargs replace the v1
    ``mapping={...}`` dict; ``s3_manager`` / ``session_path`` resolve
    automatically from the calling frame.

Both surfaces produce byte-identical output for equivalent inputs --
v2 simply translates flat kwargs into v1's mapping dict and delegates
to ``make_chart`` / ``make_composite``. The two coexist so PRISM can
A/B-test either skill module (``chart_context.md`` for v1,
``chart_context_v2.md`` for v2) against the same drag-and-drop
engine.

Annotation primitives (``VLine``, ``HLine``, ``Segment``, ``Band``,
``Arrow``, ``PointLabel``, ``PointHighlight``, ``Callout``,
``LastValueLabel``, ``Trendline``, ``PlotText``), result types
(``ChartResult``, ``CompositeResult``, ``DataProfile``), and
``profile_df`` are shared between the two surfaces.

PRISM-coupled helpers (S3, presigned URLs, Gemini vision QC) are
imported from ``ai_development.mcp.utils.*`` -- the same paths
PRISM uses in production. In this staging repo the same import paths
resolve to the colocated ``ai_development/`` stub package, which
provides filesystem-backed / no-op equivalents sufficient for local
development. This file is the canonical PRISM-bound payload; nothing
under ``ai_development/`` ships with it.

Usage (v1)::

    from chart_functions import make_chart, profile_df, ChartResult
    from chart_functions import VLine, HLine, Segment, Band, Arrow
    from chart_functions import PointLabel, PointHighlight, Callout
    from chart_functions import LastValueLabel, Trendline, PlotText
    from chart_functions import ChartSpec, make_2pack_horizontal

Usage (v2)::

    from chart_functions import Chart, render_grid
    from chart_functions import VLine, HLine, Band, Arrow

This module is built up in stages; see the section banners
(``MODULE: ...``) for the layout. The v2 surface lives at the bottom,
right before ``__all__``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard library
# ---------------------------------------------------------------------------
import concurrent.futures
import copy
import hashlib
import io
import json
import colorsys
import difflib
import functools
import logging
import math
import os
import re
import sys
import traceback
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Set, Tuple, Union

# ---------------------------------------------------------------------------
# Third-party
# ---------------------------------------------------------------------------
import altair as alt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# PRISM utilities -- imported from ``ai_development.mcp.utils.*``.
# In PRISM these resolve to the production implementations. In this
# staging repo they resolve to the local stub package at
# ``projects/altair/ai_development/`` which provides filesystem-backed /
# no-op equivalents.
# ---------------------------------------------------------------------------
from ai_development.mcp.utils.download_links import generate_presigned_download_url
from ai_development.mcp.utils.unit_helper_functions import guess_units_from_name
from ai_development.mcp.utils.vision_functions import check_chart_quality
from ai_development.mcp.utils.chart_functions_studio import (
    GS_PRIMARY, MONO_BLUE, MONO_GREY, VIVID, TABLEAU, OKABE_ITO, PASTEL,
)

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(levelname)s %(name)s.%(funcName)s: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ===========================================================================
# MODULE: TYPE ALIASES
# ===========================================================================

ChartType = Literal[
    "scatter",          # Scatter plot with optional trendline
    "scatter_multi",    # Scatter with multiple groups/clusters and trendlines
    "bar",              # Vertical bar chart (grouped or stacked)
    "bar_horizontal",   # Horizontal bar chart
    "bullet",           # Range dot plot / percentile position chart
    "waterfall",        # Waterfall / decomposition / attribution chart
    "heatmap",          # 2D heatmap / correlation matrix
    "histogram",        # Distribution histogram
    "boxplot",          # Box and whisker plot
    "area",             # Stacked or layered area chart
    "donut",            # Donut/pie chart (use sparingly)
    "multi_line",       # Multiple time series with potential dual y-axis
    "timeseries",       # Single-series time series (alias path inside multi_line)
]

IntentType = Literal["explore", "publish", "monitor"]

DimensionPreset = Literal[
    "wide",          # 700x350 - Landscape, good for time series
    "square",        # 450x450 - Equal dimensions
    "tall",          # 400x550 - Portrait orientation
    "compact",       # 400x300 - Small footprint
    "presentation",  # 900x500 - Large, for slides
    "thumbnail",     # 300x200 - Very small preview
    "teams",         # 420x210 - Required for Teams medium thumbnails
    "page_grid",     # facet-grid only -- auto-sized per (rows, cols)
]


# ===========================================================================
# MODULE: CONSTANTS
# ===========================================================================

# Disable Altair's max rows limit globally so big DataFrames don't trip the
# default 5000-row guard. Auto-downsampling is handled by
# ``_auto_downsample_timeseries`` in chart_functions.py itself.
alt.data_transformers.disable_max_rows()

# Cardinality guard rails. ``MAX_COLOR_CARDINALITY`` is tied to the
# default categorical palette (``GS_PRIMARY["colors"]``) which has 10
# slots. Above 10 unique values, slot 10 cycles back to slot 0 and slot
# 11 to slot 1, producing duplicate hues that read as "two slices the
# same colour" -- the canonical failure mode flagged in the 2026-05-16
# triage report. The cap is enforced HARD because the alternative
# (silently ship an unreadable chart) is the worst outcome.
MAX_COLOR_CARDINALITY = 10          # Max unique values in a color encoding
MAX_FACET_CARDINALITY = 16          # Max facets in a small-multiples chart
MAX_ROWS_INTERACTIVE = 50_000       # Above this, warn (do not block)

# Auto-downsample thresholds for time-series rendering.
MAX_ROWS_BEFORE_DOWNSAMPLE = 5_000  # Trigger downsample above this
DOWNSAMPLE_TARGET_ROWS = 2_000      # Aim for this row count post-downsample

# Grouped-bar (stack=False + color) cell-budget readability guards.
# Vega-Lite renders grouped bars via column / row faceting on Altair
# 4.x; total outer footprint = n_categories * facet_size + (n-1) *
# inter_facet_spacing. Both terms can blow past a composite cell's
# input width / height budget. The math below subtracts the spacing
# overhead from the budget BEFORE dividing by n_categories so the
# rendered chart actually fits inside its cell; the readability
# threshold rejects the unreadable-blur extreme (e.g. 60+ x-cats in a
# 280px composite cell) with a ValidationError pointing the LLM at
# stack=True or fewer categories. Migrating to Altair 5+ ``xOffset``
# would obsolete the faceting workaround entirely; until PRISM
# upgrades, this guard stays load-bearing.
_MIN_GROUPED_BAR_PER_BAR_PX = 3
# Inter-facet gap between x-category groups in vertical grouped bars
# (column-facet path). Kept small so composite cell-budget math still
# fits, but large enough to read as deliberate whitespace between
# groups rather than a continuous bar strip.
_GROUPED_BAR_FACET_SPACING_PX = 6
# Band-scale padding on the inner (color) x-axis within each facet.
# paddingOuter is what creates the visible gutter at group boundaries;
# paddingInner stays tight so bars within a group remain adjacent.
_GROUPED_BAR_INNER_X_PADDING_OUTER = 0.14
_GROUPED_BAR_INNER_X_PADDING_INNER = 0.02
_FACET_LABEL_MIN_PITCH_PX = 28     # min horizontal pitch between visible facet labels


def _facet_label_thinning_expr(
    label_values: List[Any],
    total_strip_px: int,
) -> Optional[str]:
    """Build a Vega-Lite ``labelExpr`` that hides facet-header labels
    when the per-facet pitch drops below readability.

    Column / row faceting renders one label per facet. Vega-Lite's
    standard ``labelOverlap='greedy'`` axis trick does not apply to
    facet headers -- they are per-facet, not per-axis. Without
    thinning, e.g. n=17 facets in a 280px cell pack labels at ~14px
    pitch and they collide visibly even when rotated. This helper
    picks an evenly-spaced visible subset (target pitch
    ``_FACET_LABEL_MIN_PITCH_PX``) and emits a Vega expression that
    returns the value for visible labels and an empty string for
    hidden ones.

    Returns ``None`` (no thinning needed) when every label fits at
    >= ``_FACET_LABEL_MIN_PITCH_PX`` of pitch, in which case the
    caller should leave ``labelExpr`` unset.
    """
    n = len(label_values)
    if n == 0:
        return None
    pitch = total_strip_px / n
    if pitch >= _FACET_LABEL_MIN_PITCH_PX:
        return None

    max_visible = max(2, total_strip_px // _FACET_LABEL_MIN_PITCH_PX)
    if max_visible >= n:
        return None

    # Pick evenly-spaced indices so the visible labels span the full
    # range (first + last always shown, middles distributed).
    if max_visible == 1:
        visible_idx = {0}
    else:
        step = (n - 1) / (max_visible - 1)
        visible_idx = {int(round(i * step)) for i in range(max_visible)}
    visible_idx = {i for i in visible_idx if 0 <= i < n}
    visible_str = [str(label_values[i]) for i in sorted(visible_idx)]

    # Escape single quotes inside labels so the JS literal stays valid.
    def _esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("'", "\\'")
    js_array = "[" + ",".join(f"'{_esc(s)}'" for s in visible_str) + "]"
    # ``datum.value`` is the NATIVE type (integer for numeric facets,
    # string for nominal labels). Cast both sides to string via
    # toString() so the comparison is type-safe regardless of input.
    return (
        f"indexof({js_array}, toString(datum.value)) >= 0 "
        f"? toString(datum.value) : ''"
    )

# Characters that break Vega-Lite field resolution (JS accessor syntax).
# Column names containing these silently render to empty charts.
_VEGA_LITE_UNSAFE_CHARS = re.compile(r'[.\[\]"\\\n\t!]')

# Canonical tenor ordering for rates / fixed-income profile charts.
TENOR_ORDER = [
    "1M", "2M", "3M", "6M", "9M",
    "1Y", "2Y", "3Y", "4Y", "5Y", "6Y", "7Y", "8Y", "9Y", "10Y",
    "12Y", "15Y", "20Y", "25Y", "30Y", "40Y", "50Y",
]

# Dimension presets in pixels.
DIMENSION_PRESETS: Dict[str, Tuple[int, int]] = {
    "wide": (700, 350),
    "square": (450, 450),
    "tall": (400, 550),
    "compact": (400, 300),
    "presentation": (900, 500),
    "thumbnail": (300, 200),
    "teams": (420, 210),
    # ``page_grid`` is a sentinel: actual panel dims are derived from
    # the facet grid shape (rows, cols) at render time. The tuple here
    # is the USABLE composite outer area on US Letter portrait
    # (~1200 x 1600 px) that ``_resolve_facet_panel_dims`` divides up.
    # Sized so a 5x4 grid lands at ~260x280 per panel after default
    # 50px inter-panel spacing -- intentionally airy so the small-
    # multiples grid reads as a print-paper layout, not a packed
    # dashboard.
    "page_grid": (1200, 1600),
}


# ---------------------------------------------------------------------------
# Facet-grid (small-multiples) constants
# ---------------------------------------------------------------------------

# Chart types that support ``mapping['facet']``. Single-distribution and
# matrix shapes are rejected because their natural expression is a single
# canvas rather than a panel grid.
_FACET_VALID_CHART_TYPES: frozenset = frozenset({
    "multi_line", "timeseries",
    "scatter", "scatter_multi",
    "bar", "bar_horizontal",
    "area",
    "histogram",
})

# Minimum panel count for facet mode. Set to 7 so the facet range begins
# exactly where pack composites end (make_*pack_* tops out at 6 cells),
# leaving NO dead zone: <=6 entities -> composite, >=7 -> facet grid. This
# closes the 7-11 gap (Mag-7, 11 GICS sectors, G10 FX) that previously had
# no native multi-panel shape and forced manual splits. Below 7, a composite
# is the right call (2-4 panels are arguments, not cross-sectional grids).
_FACET_MIN_PANELS: int = 7

# Hard cap on grid size. Beyond 6x6, per-panel readability collapses;
# PRISM should aggregate or switch to a heatmap.
_FACET_HARD_CAP: int = 36

# Soft warning threshold. 25-35 panels render but emit a warning
# nudging PRISM to consider aggregation.
_FACET_SOFT_WARN_THRESHOLD: int = 25

# Default spacing between facet panels (px). Wider than make_*pack_*
# composites because facet grids on letter portrait want real breathing
# room between panels -- inter-panel whitespace is what makes a 5x4
# country grid scan as small-multiples rather than as a busy mosaic.
_FACET_DEFAULT_SPACING: int = 50

# Title / subtitle text-budget calibration. Used by
# ``_validate_and_wrap_text`` to compute (a) how many chars fit on one
# line of a given chart-area width and (b) the hard total-length cap
# above which the engine refuses to render. Each slot has its own font
# size; chars-per-line uses the same ``font_size * 0.55`` heuristic as
# ``_wrap_text_to_width`` so pre-wrapped ``\\n`` breaks fit inside the
# plot width without Vega-Lite ``title.limit`` (which ellipsis-truncates).
#
# The four composite-specific slot kinds give the composite a real
# typographic hierarchy: a larger composite super-title (32px), a
# medium super-subtitle (22px), a notably smaller per-chart title
# (18px) so the per-panel headers defer to the composite header above
# them, and the 12px per-chart subtitle. ``make_chart``'s standalone
# title still uses the generic ``"title"`` slot at the skin's default
# 26px.
_SUBCHART_TITLE_FONT_SIZE: int = 18
_SUBCHART_SUBTITLE_FONT_SIZE: int = 12
_TEXT_CHAR_WIDTH_RATIO: float = 0.55
_TEXT_FONT_SIZE: Dict[str, int] = {
    # Generic single-chart slots (make_chart standalone, 26px / 14px).
    "title":    26,
    "subtitle": 14,
    # Composite-specific slots.
    "composite_super_title":    32,
    "composite_super_subtitle": 22,
    "subchart_title":           _SUBCHART_TITLE_FONT_SIZE,
    "subchart_subtitle":        _SUBCHART_SUBTITLE_FONT_SIZE,
}
# Hard cap on the number of wrapped lines a single title or subtitle
# slot may produce. Anything that would wrap to more than this is
# rejected with a helpful ValueError. Two lines is the convention
# financial-report titles use: title-on-line-1, qualifier-on-line-2.
_TEXT_LINE_CAP: int = 2

# ``AVAILABLE_SKINS`` is defined later (Stage: SKINS) once the GS_CLEAN
# config dict is constructed.


# ===========================================================================
# MODULE: SMALL HELPERS
# ===========================================================================

def _safe_legend_kwargs(**kwargs: Any) -> Dict[str, Any]:
    """Filter out ``None`` values before passing to ``alt.Legend()``.

    Altair's Vega-Lite schema validation rejects ``None`` as a valid value
    for legend parameters such as ``clipHeight``. This helper strips them
    out so we don't trip ``SchemaValidationError``. A small allow-list of
    keys (``title``) keeps ``None`` because that explicitly hides the
    legend title.
    """
    allow_none_keys = {"title"}
    return {k: v for k, v in kwargs.items() if v is not None or k in allow_none_keys}


def _check_chart_quality_safe(png_s3_path: str, s3_manager: Any) -> bool:
    """Fail-open wrapper around the Gemini Flash chart-quality gate.

    Pulls the chart PNG via ``s3_manager`` and forwards the bytes to
    ``check_chart_quality``. Returns ``True`` (chart passes) when the
    quality check succeeds and the verdict is acceptable, OR when any
    infrastructure error occurs (fail-open). Returns ``False`` only when
    the quality check explicitly flags the chart as bad.

    Args:
        png_s3_path: S3 path to the chart PNG file.
        s3_manager: S3BucketManager instance for reading the PNG bytes.

    Returns:
        True if the chart should be kept, False if it should be suppressed.
    """
    try:
        png_bytes = s3_manager.get(png_s3_path)
        result = check_chart_quality(png_bytes)
        if result.get("passed", True):
            return True
        reason = result.get("reason", "unknown")
        logger.info(
            "[QualityGate] Chart FAILED quality check: %s -- %s",
            reason,
            png_s3_path,
        )
        return False
    except Exception as exc:  # noqa: BLE001 - explicit fail-open
        logger.warning(
            "[QualityGate] Quality check error (fail-open, chart passes): %s",
            exc,
        )
        return True


# ===========================================================================
# MODULE: VALIDATORS
# ===========================================================================

class ValidationError(Exception):
    """Base validation error for chart functions.

    Note:
        ``ValidationError`` (and its subclasses) signals an input problem
        the engine cannot render. The public entry points (``make_chart``,
        ``make_table``, and the composite helpers) re-raise it via
        ``_raise_on_failure`` so the failure bubbles out of
        ``execute_analysis_script`` and PRISM surfaces it to the LLM,
        instead of being swallowed inside a ``success=False`` result.
        The internal builders still *return* ``success=False`` for the
        recovery / panel-aggregation paths that inspect it; only the
        public boundary converts that into a raise.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.context = context or {}


def _raise_on_failure(func: Callable) -> Callable:
    """Wrap a public chart/table builder so a failed result *raises*.

    PRISM runs chart code inside ``execute_analysis_script``. That sandbox
    only surfaces a failure to the LLM when the script raises -- a returned
    ``ChartResult(success=False)`` / ``CompositeResult(success=False)`` /
    ``TableResult(success=False)`` is never inspected post-exec and is
    silently discarded when the namespace is torn down (the swallowed-error
    path). Wrapping the public builders so a ``success=False`` result raises
    routes the failure onto the sandbox's ``script_execution`` stage, where
    it becomes an LLM-visible error (matching the
    ``compile_dashboard(strict=True)`` fail-loud precedent).

    The raised type is the base ``ValidationError`` deliberately: PRISM's
    ``_map_error_to_hint_key`` routes to the chart-specific hint by *type*
    when the exception's class name contains ``validation`` -- which the
    base name does (the typed ``*TooLongError`` subclasses do NOT, so the
    gate raises a fresh base ``ValidationError`` rather than re-raising the
    original instance). The engine's ``error_message`` strings already carry
    the mapping / column / field vocabulary the hint also keys on.

    Internal callers that need the inspectable ``success=False`` return
    (``make_chart``'s auto-recovery recursion, composite panel aggregation,
    ``Chart.preview`` / ``Chart.render``) call the undecorated
    implementation directly and are unaffected.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = func(*args, **kwargs)
        if getattr(result, "success", True) is False:
            raise ValidationError(
                getattr(result, "error_message", None)
                or f"{getattr(func, '__name__', 'chart build')} failed"
            )
        return result

    return wrapper


class YAxisLabelTooLongError(ValidationError):
    """Raised when a y-axis label exceeds the configured character limit."""

    def __init__(
        self,
        message: str,
        y_title: Optional[str] = None,
        mapping: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Skip ValidationError.__init__ to avoid duplicate context handling.
        Exception.__init__(self, message)
        self.context = {"y_title": y_title, "mapping": mapping}


class LvlSeriesNameTooLongError(ValidationError):
    """Raised when a ``multi_line`` / ``timeseries`` series name exceeds the
    LastValueLabel character limit.

    Mirrors ``YAxisLabelTooLongError``: rather than silently truncate the
    end-of-line label with an ellipsis (which produces unreadable output
    like ``"United S\u2026 4.31"``), the engine fails up-front so PRISM
    rewrites the series identifier into something that fits the chart.
    """

    def __init__(
        self,
        message: str,
        offending_names: Optional[List[str]] = None,
        mapping: Optional[Dict[str, Any]] = None,
    ) -> None:
        Exception.__init__(self, message)
        self.context = {
            "offending_names": list(offending_names or []),
            "mapping": mapping,
        }


class LegendLabelTooLongError(ValidationError):
    """Raised when a colour-legend series name exceeds the pixel budget.

    Vega-Lite treats ``legend.labelLimit`` as a hard ellipsis truncate --
    there is no wrap. The engine computes the budget as 25%% of
    ``chart_width`` (``_LEGEND_MAX_WIDTH_FRAC``) and fails up-front when
    any ``color``-column value would be clipped, so PRISM shortens names
    in the DataFrame before calling ``make_chart()`` / composites.
    """

    def __init__(
        self,
        message: str,
        offending_names: Optional[List[str]] = None,
        color_field: Optional[str] = None,
        mapping: Optional[Dict[str, Any]] = None,
        max_chars: Optional[int] = None,
        chart_width: Optional[int] = None,
    ) -> None:
        Exception.__init__(self, message)
        self.context = {
            "offending_names": list(offending_names or []),
            "color_field": color_field,
            "mapping": mapping,
            "max_chars": max_chars,
            "chart_width": chart_width,
        }


class HeatmapRowLabelTooLongError(ValidationError):
    """Raised when heatmap row labels cannot stay horizontal without truncation.

    Heatmap y-axis (row) labels are NEVER rotated to -45 deg and NEVER
    ellipsis-truncated via Vega-Lite ``labelLimit``. When the longest row
    label exceeds the validated left-gutter pixel budget (or the row band
    is too tight for the axis font size), the engine fails up-front so
    PRISM shortens labels in the DataFrame before ``make_chart()`` /
    ``make_*pack_*()``.
    """

    def __init__(
        self,
        message: str,
        offending_labels: Optional[List[str]] = None,
        y_field: Optional[str] = None,
        mapping: Optional[Dict[str, Any]] = None,
        max_chars: Optional[int] = None,
        chart_height: Optional[int] = None,
    ) -> None:
        Exception.__init__(self, message)
        self.context = {
            "offending_labels": list(offending_labels or []),
            "y_field": y_field,
            "mapping": mapping,
            "max_chars": max_chars,
            "chart_height": chart_height,
        }


class BarCategoryLabelTooLongError(ValidationError):
    """Raised when bar chart category labels exceed the configured cap.

    Mirrors ``YAxisLabelTooLongError`` / ``LvlSeriesNameTooLongError``:
    rather than silently truncate (vertical / horizontal labelLimit
    ellipsis) or catastrophically collide (grouped-bar y-axis rotated-90
    overlap), the engine fails up-front so PRISM rewrites the category
    labels into a form that renders cleanly in every bar context.

    Applies to all bar chart types: plain vertical, plain horizontal,
    grouped (``color`` + ``stack=False``), stacked (``color`` +
    ``stack=True``), and composite cells of all of the above. Same cap
    regardless of orientation so PRISM has a single rule to follow.
    """

    def __init__(
        self,
        message: str,
        offending_labels: Optional[List[str]] = None,
        category_field: Optional[str] = None,
        mapping: Optional[Dict[str, Any]] = None,
    ) -> None:
        Exception.__init__(self, message)
        self.context = {
            "offending_labels": list(offending_labels or []),
            "category_field": category_field,
            "mapping": mapping,
        }


# ---------------------------------------------------------------------------
# No-truncation policy (global Altair engine principle)
# ---------------------------------------------------------------------------
# Vega-Lite ``labelLimit`` enforces hard ellipsis truncation on axis and
# legend text. The engine NEVER relies on that silent path: every nominal
# label surface (bar categories, heatmap rows, legend series names, LVL
# names, y-axis titles) is validated up-front and raises a typed
# ``*TooLongError`` so PRISM shortens labels in the DataFrame. After
# validation passes, per-axis ``labelLimit`` is set to the exact validated
# pixel budget so inherited config defaults cannot re-truncate.

_AXIS_LABEL_CHAR_WIDTH_RATIO = 0.55  # matches ``_wrap_text_to_width`` heuristic

# Soft cap on y-axis label length. The PRISM style guide says ~16 chars is
# the visual sweet spot; we hard-fail past 24 to surface obvious abuses
# (raw column names, generated tokens) without being too pedantic about
# borderline-long human labels.
_Y_AXIS_LABEL_MAX_CHARS = 24

# Left-gutter fraction of chart width reserved for heatmap row labels.
_HEATMAP_ROW_GUTTER_FRAC_STANDALONE = 0.38
_HEATMAP_ROW_GUTTER_FRAC_COMPOSITE = 0.28
_HEATMAP_ROW_LABEL_VERTICAL_PAD_PX = 4
# Absolute char ceiling for heatmap row labels -- aligned with bar
# category cap so PRISM has one abbreviation discipline across matrix
# and bar charts. Gutter math may allow more in wide canvases; this cap
# still wins so labels stay efficient.
_HEATMAP_ROW_LABEL_MAX_CHARS = 15

# Hard cap on per-series name length for ``LastValueLabel`` on
# ``multi_line`` / ``timeseries``. End-of-line labels paint INSIDE the
# canvas margin reserve; long names either devour the plot region or get
# silently truncated (the prior 25% cap behaviour, retired 2026-05-12 in
# favour of loud failure). Cap matches the y-axis sibling (24) plus one
# char because series names tend to need slightly more room than axis
# titles (``"S&P 500 Energy"`` 14 vs ``"Energy ($/bbl)"`` 14 -- the
# series carries the entity, the y-title carries the unit).
_LVL_SERIES_NAME_MAX_CHARS = 25

# Hard cap on bar-chart category label length. Long labels surface
# multiple failure modes that no labelLimit / labelOverlap setting can
# fix cleanly:
#   - Vertical bar at angle -45 with default labelLimit ~180 px truncates
#     mid-label at ~17 chars (A03 in the audit).
#   - Horizontal bar's labelLimit cap (max(180, min(width*0.45, ...))) is
#     plot-region-protective, not label-aware: 22+ ch labels truncate at
#     width=700 (B04), 14+ ch labels truncate at composite width=350
#     (D04 / E05).
#   - Grouped bar (``color`` + ``stack=False``) inside the horizontal
#     handler renders y-axis category labels rotated 90 deg and stacked
#     on the same anchor, overlapping into illegible noise (F03 / F04 /
#     F05 / H01). This is an underlying rendering bug in the column-
#     faceted bar_horizontal path; the cap prevents the caller from ever
#     exercising it.
# 15 ch is the largest cap that keeps EVERY bar context (vertical /
# horizontal / grouped / stacked / single / composite) rendering cleanly
# without truncation or collision. Verified by the long-label audit
# gallery at projects/altair/dev/build_long_label_audit.py (42 cards;
# every CLEAN render has max_len <= 15; every TRUNC / COLLIDE has
# max_len > 15).
_BAR_CATEGORY_LABEL_MAX_CHARS = 15

# Minimum distinct (x, y) coordinates that fall inside the visible plot
# region for a scatter to read as a relationship rather than an anecdote.
# Enforced by ``_build_scatter`` before chart construction; sparse scatters
# raise ``ValidationError`` so the caller expands the data window,
# aggregates to denser distinct points, or picks a chart type that suits
# sparse data instead of shipping a misleading chart. Inherited by
# ``_build_scatter_multi`` because it dispatches through ``_build_scatter``
# on the full DataFrame (chart-level total, not per-color group).
_MIN_SCATTER_VISIBLE_DOTS = 8

# Relaxed scatter floor for NAMED cross-sections. When each dot carries a
# categorical (non-gradient) ``color`` identity -- a legend names every point
# (e.g. a G7 deficit-vs-yield scatter coloured by country) -- the chart reads
# as a labelled cross-section, not an anonymous cloud, so the dot floor drops.
# This unblocks the recurring 6-7-entity cross-asset universes (G6/G7, Mag-7)
# that fall below the anonymous-scatter floor. Below this even a labelled
# scatter is too sparse to read as a relationship.
_MIN_SCATTER_LABELED_DOTS = 4

# Minimum fraction of the visible y-axis span that any single series in a
# multi-series single-y-axis time-series chart (``multi_line`` /
# ``timeseries``) must occupy to read as anything other than a flat line.
# Below this threshold ``_validate_y_scale_homogeneity`` raises
# ``ValidationError`` with the three reshape options (2-pack composite,
# dual-axis, normalize). Catches the canonical "gold + WTI" failure mode
# where a high-magnitude series dominates the y-axis domain and the
# others collapse to flat horizontal rails near zero.
_MIN_SERIES_VERTICAL_SHARE = 0.10

# Companion gate to ``_MIN_SERIES_VERTICAL_SHARE``. Catches the case
# where every series has visible per-series variation (each clears the
# 10% flatness floor) but the series sit at level bands so far apart
# that the chart still reads as flat-ish horizontal rails separated by
# empty whitespace. Triggered when the largest gap between any two
# adjacent (sorted-by-mean) series's means exceeds this multiple of the
# largest individual series's span. Canonical example: corporate
# saving (~2.5%) vs investment (~9.9%) of GDP -- each spans ~0.8 pp,
# gap ~7.4 pp, ratio ~9x; FCI tenor contributions clustered at 10 / 30 /
# 60 bp with span ~7 each -- ratio ~4x.
_LEVEL_DISPARITY_RATIO_THRESHOLD = 3.0


def _axis_label_px_per_char(label_font_size: int) -> float:
    """Average horizontal pixels per character for axis tick labels."""
    return max(1.0, label_font_size * _AXIS_LABEL_CHAR_WIDTH_RATIO)


def _axis_label_pixel_budget(label: str, label_font_size: int) -> float:
    """Pixel width a single axis label string needs (no ellipsis room)."""
    return len(str(label)) * _axis_label_px_per_char(label_font_size) + 8


def _heatmap_axis_label_font_size(skin_config: Dict[str, Any]) -> int:
    """Resolve heatmap axis tick label font size from the active skin."""
    axis_cfg = skin_config.get("config", {}).get("axis", {})
    return int(
        axis_cfg.get("labelFontSize")
        or skin_config.get("axis_config", {}).get("labelFontSize")
        or skin_config.get("label_font_size")
        or 18
    )


def _validate_y_axis_label(y_title: Optional[str], mapping: Dict[str, Any]) -> None:
    """Validate y-axis label length. Raises if it exceeds the configured cap."""
    if y_title and len(y_title) > _Y_AXIS_LABEL_MAX_CHARS:
        raise YAxisLabelTooLongError(
            (
                f"Y-axis label '{y_title}' is {len(y_title)} characters "
                f"(max {_Y_AXIS_LABEL_MAX_CHARS}). Use a shorter y_title in mapping. "
                f"Example: mapping={{'y': '{mapping.get('y', 'value')}', "
                "'y_title': 'Shorter Label'}}"
            ),
            y_title=y_title,
            mapping=mapping,
        )


def _suggest_bar_label_abbreviations(label: str) -> str:
    """Produce 1-2 abbreviation suggestions for an over-cap bar category label.

    Strategy:
      1. Acronym from word initials (e.g. 'Information Technology' -> 'IT').
      2. First word + acronymised rest (e.g. 'Manufacturing PMI Composite'
         -> 'Mfg PMI').
    Returns both joined with ' / '; falls back to a hard truncation when
    neither acronym strategy stays under the cap.
    """
    cap = _BAR_CATEGORY_LABEL_MAX_CHARS
    words = label.split()

    initials = "".join(w[0].upper() for w in words if w and w[0].isalpha())
    if 2 <= len(initials) <= cap:
        first_suggestion = initials
    else:
        first_suggestion = label[:cap]

    if len(words) >= 2:
        first_word = words[0]
        rest_initials = "".join(
            w[0].upper() for w in words[1:] if w and w[0].isalpha()
        )
        candidate = f"{first_word} {rest_initials}".strip()
        second_suggestion = (
            candidate if len(candidate) <= cap else label[:cap]
        )
    else:
        second_suggestion = label[:cap]

    if first_suggestion == second_suggestion:
        return f"'{first_suggestion}'"
    return f"'{first_suggestion}' / '{second_suggestion}'"


def _validate_bar_category_labels(
    labels: List[str],
    category_field: str,
    mapping: Dict[str, Any],
) -> None:
    """Validate bar chart category label lengths. Raises if any label exceeds
    the configured cap (15 chars).

    Applies to all bar chart types -- plain vertical, plain horizontal,
    grouped (``color`` + ``stack=False``), stacked (``color`` +
    ``stack=True``), and composite cells. Same cap regardless of
    orientation, called from the top of ``_build_bar`` (for nominal x)
    and ``_build_bar_horizontal`` (for nominal y).
    """
    str_labels = [str(label) for label in labels]
    offenders = sorted(
        {label for label in str_labels if len(label) > _BAR_CATEGORY_LABEL_MAX_CHARS},
        key=lambda s: -len(s),
    )
    if not offenders:
        return

    max_len = max(len(label) for label in str_labels)
    n_offenders = len(offenders)
    # Cap the offender list shown in the message so we don't dump 50
    # labels into the error. 5 covers any practical bar chart.
    shown_offenders = offenders[:5]

    offender_block = "\n".join(
        f"  - '{label}' ({len(label)} ch)" for label in shown_offenders
    )
    suggestion_block = "\n".join(
        f"  '{label}' -> {_suggest_bar_label_abbreviations(label)}"
        for label in shown_offenders[:3]
    )

    raise BarCategoryLabelTooLongError(
        (
            f"Bar category labels in field '{category_field}' exceed the "
            f"{_BAR_CATEGORY_LABEL_MAX_CHARS}-character cap "
            f"({n_offenders} offender(s), longest is {max_len} ch). "
            f"Shorten the labels in the DataFrame before make_chart().\n"
            f"Offenders ({len(shown_offenders)} of {n_offenders} shown, longest first):\n"
            f"{offender_block}\n"
            f"Suggested abbreviations:\n"
            f"{suggestion_block}"
        ),
        offending_labels=offenders,
        category_field=category_field,
        mapping=mapping,
    )


def _get_field(mapping: Dict[str, Any], key: str) -> Optional[str]:
    """Extract a field name from a mapping dict, accepting either ``str`` or
    ``{'field': '...'}`` value forms. Returns ``None`` if the key is absent
    or the value is not in a recognized shape.
    """
    if not mapping or key not in mapping:
        return None
    val = mapping[key]
    if isinstance(val, str):
        return val
    if isinstance(val, dict) and "field" in val:
        return val["field"]
    return None


def _extract_fields(mapping: Dict[str, Any]) -> List[str]:
    """Collect every column name referenced by an encoding key in mapping.

    Walks the standard encoding keys (``x``, ``y``, ``color``, ``size``,
    ``facet``, ``theta``, ``value``, ``z``) and returns the union of column
    names they reference. List-valued ``y`` (auto-melt shortcut) is expanded.
    """
    fields: List[str] = []
    for key in ("x", "y", "color", "size", "facet", "theta", "value", "z"):
        if key not in mapping:
            continue
        val = mapping[key]
        if isinstance(val, str):
            fields.append(val)
        elif isinstance(val, list):
            fields.extend(v for v in val if isinstance(v, str))
        elif isinstance(val, dict) and "field" in val:
            fields.append(val["field"])
    return fields


def _sanitize_column_names(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Rename DataFrame columns to remove Vega-Lite-incompatible characters.

    Vega-Lite uses JavaScript dot notation to resolve field references.
    Column names containing ``.``, ``[``, ``]``, ``\\``, newline, tab, or
    ``!`` cause silent rendering failures where the chart renders
    structurally but with zero data points.

    The function:
      1. Detects columns with unsafe characters.
      2. Renames them (replacing unsafe chars with underscores).
      3. Updates the mapping dict to reference the new names.
      4. Preserves display labels (``y_title``, ``x_title``) unchanged.

    Args:
        df: Input DataFrame (not mutated; a copy is returned if changes
            are needed).
        mapping: Column mapping dict (not mutated; a copy is returned if
            changes are needed).

    Returns:
        Tuple of ``(sanitized_df, sanitized_mapping)``.
    """
    rename_map: Dict[str, str] = {}
    for col in df.columns:
        if isinstance(col, str) and _VEGA_LITE_UNSAFE_CHARS.search(col):
            safe_name = _VEGA_LITE_UNSAFE_CHARS.sub("_", col)
            # Avoid collisions with any pre-existing column.
            while safe_name in df.columns and safe_name != col:
                safe_name = safe_name + "_"
            rename_map[col] = safe_name

    if not rename_map:
        return df, mapping

    df = df.rename(columns=rename_map)

    mapping = dict(mapping)
    for key in (
        "y", "x", "color", "size", "facet", "theta", "value", "z",
        "x_low", "x_high", "color_by", "label",
    ):
        if key in mapping:
            val = mapping[key]
            if isinstance(val, str) and val in rename_map:
                mapping[key] = rename_map[val]
            elif isinstance(val, list):
                mapping[key] = [
                    rename_map.get(v, v) if isinstance(v, str) else v
                    for v in val
                ]

    if "dual_axis_series" in mapping and isinstance(mapping["dual_axis_series"], list):
        mapping["dual_axis_series"] = [
            rename_map.get(s, s) for s in mapping["dual_axis_series"]
        ]

    logger.info("[make_chart] Sanitized column names: %s", rename_map)
    return df, mapping


# Canonical timezone for intraday market data. Naive datetimes are
# interpreted as US/Eastern wall clock unless ``mapping['x_timezone']``
# requests a different display timezone.
_DEFAULT_INTRADAY_TZ = "America/New_York"
_X_TIMEZONE_ALIASES: Dict[str, str] = {
    "ET": "America/New_York",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "US/Eastern": "America/New_York",
    "EASTERN": "America/New_York",
    "UTC": "UTC",
    "GMT": "UTC",
    "LON": "Europe/London",
    "LONDON": "Europe/London",
    "TOKYO": "Asia/Tokyo",
    "HKT": "Asia/Hong_Kong",
}


def _resolve_x_timezone(mapping: Dict[str, Any]) -> str:
    """Display timezone for intraday temporal x-axis labels.

    Defaults to US/Eastern. Accepts IANA names or common aliases
    (``ET``, ``UTC``, ``LON``, ...). PRISM sets ``mapping['x_timezone']``
    when the user asks for a non-ET clock.
    """
    raw = mapping.get("x_timezone") or mapping.get("timezone")
    if not raw:
        return _DEFAULT_INTRADAY_TZ
    key = str(raw).strip()
    return _X_TIMEZONE_ALIASES.get(key.upper(), key)


def _to_et_naive_wall_clock(series: pd.Series) -> pd.Series:
    """Coerce any datetime series to tz-naive US/Eastern wall clock."""
    s = pd.to_datetime(series, errors="coerce")
    if getattr(s.dt, "tz", None) is not None:
        return s.dt.tz_convert(_DEFAULT_INTRADAY_TZ).dt.tz_localize(None)
    return s.dt.tz_localize(
        _DEFAULT_INTRADAY_TZ,
        ambiguous="infer",
        nonexistent="shift_forward",
    ).dt.tz_localize(None)


def _convert_wall_clock_timezone(
    series: pd.Series,
    *,
    source_tz: str,
    target_tz: str,
) -> pd.Series:
    """Re-express a tz-naive wall-clock series from ``source_tz`` to ``target_tz``."""
    if source_tz == target_tz:
        return series
    s = pd.to_datetime(series, errors="coerce")
    localized = s.dt.tz_localize(
        source_tz,
        ambiguous="infer",
        nonexistent="shift_forward",
    )
    return localized.dt.tz_convert(target_tz).dt.tz_localize(None)


def _intraday_label_expr(*, single_session: bool) -> str:
    """Vega ``labelExpr`` for intraday axes.

    Date appears in exactly two situations:
      1. **Midnight** (``00:00:00``) on multi-day spans → ``May 28``
      2. **Single-session** (one calendar day, no midnight in range) →
         date on the leftmost tick only → ``May 27``

    Every other tick is ``HH:MM`` only. No date+time combos; no date at
    non-midnight hours on multi-day charts.
    """
    if single_session:
        return (
            "(datum.index === 0) "
            "? timeFormat(datum.value, '%b %d') "
            ": timeFormat(datum.value, '%H:%M')"
        )
    return (
        "(hours(datum.value) === 0 && minutes(datum.value) === 0 "
        "&& seconds(datum.value) === 0) "
        "? timeFormat(datum.value, '%b %d') "
        ": timeFormat(datum.value, '%H:%M')"
    )


def _is_intraday_datetime_series(date_series: pd.Series) -> bool:
    """True when ``date_series`` has sub-daily sample cadence (minute bars, etc.).

    Uses the same median-gap heuristic as ``determine_date_format`` so every
    caller agrees on what counts as intraday.
    """
    if len(date_series) < 2:
        return False
    if not pd.api.types.is_datetime64_any_dtype(date_series):
        return False
    min_date = date_series.min()
    max_date = date_series.max()
    if pd.isna(min_date) or pd.isna(max_date):
        return False
    span_hours = (max_date - min_date).total_seconds() / 3600
    if span_hours > 5 * 24:
        return False
    date_diffs = _unique_sorted_diffs(date_series)
    if len(date_diffs) == 0:
        return False
    median_diff_seconds = float(date_diffs.dt.total_seconds().median())
    return median_diff_seconds < 20 * 3600


def _normalize_intraday_x_column(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    chart_type: str,
) -> pd.DataFrame:
    """Make intraday x-columns plot-ready regardless of upstream formatting.

    The engine absorbs ~95% of PRISM-side datetime hygiene (Principle #7):

      - ``datetime64[ns, UTC-04:00]`` / any tz-aware -> US/Eastern wall
        clock (naive), unless ``mapping['x_timezone']`` requests another
        display timezone
      - tz-naive timestamps -> assumed US/Eastern wall clock
      - ISO / slash / space-separated strings -> datetime, then ET
      - unix-epoch integers (ms or s)
      - common column aliases when ``mapping['x']`` is missing: ``date``,
        ``timestamp``, ``datetime``, ``time``

    Skipped when ``mapping['x_type'] == 'ordinal'`` -- caller owns labels.
    """
    if mapping.get("x_type") == "ordinal":
        return df

    x_field = _get_field(mapping, "x")
    if not x_field or x_field not in df.columns:
        for alias in ("date", "timestamp", "datetime", "time", "Date", "TIME"):
            if alias in df.columns and (
                pd.api.types.is_datetime64_any_dtype(df[alias])
                or df[alias].dtype == object
            ):
                mapping["x"] = alias
                x_field = alias
                break
        else:
            return df

    series = df[x_field]
    if not (
        pd.api.types.is_datetime64_any_dtype(series)
        or pd.api.types.is_numeric_dtype(series)
        or series.dtype == object
        or pd.api.types.is_string_dtype(series)
    ):
        return df

    df = df.copy()
    display_tz = _resolve_x_timezone(mapping)

    if pd.api.types.is_datetime64_any_dtype(series):
        converted = _to_et_naive_wall_clock(series)
    elif pd.api.types.is_numeric_dtype(series):
        sample = pd.to_numeric(series.dropna().head(20), errors="coerce")
        if len(sample) and sample.median() > 1e11:
            converted = pd.to_datetime(series, unit="ms", errors="coerce")
        elif len(sample) and sample.median() > 1e8:
            converted = pd.to_datetime(series, unit="s", errors="coerce")
        else:
            return df
        converted = _to_et_naive_wall_clock(converted)
    else:
        import warnings as _warnings

        converted = None
        for fmt in (
            None,
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%m/%d %H:%M",
            "%m/%d/%Y %H:%M",
            "%m/%d/%y %H:%M",
            "%d/%m/%Y %H:%M",
        ):
            try:
                with _warnings.catch_warnings():
                    _warnings.simplefilter("ignore")
                    if fmt is None:
                        converted = pd.to_datetime(series, errors="raise", utc=False)
                    else:
                        converted = pd.to_datetime(
                            series, format=fmt, errors="raise",
                        )
                break
            except (ValueError, TypeError):
                continue
        if converted is None:
            return df
        converted = _to_et_naive_wall_clock(converted)

    if display_tz != _DEFAULT_INTRADAY_TZ:
        converted = _convert_wall_clock_timezone(
            converted,
            source_tz=_DEFAULT_INTRADAY_TZ,
            target_tz=display_tz,
        )

    df[x_field] = converted
    logger.info(
        "[chart_functions] Normalized x_field=%r to intraday wall clock "
        "(display_tz=%r, chart_type=%s).",
        x_field, display_tz, chart_type,
    )
    return df


def _coerce_string_x_to_datetime(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    chart_type: str,
) -> pd.DataFrame:
    """Auto-coerce a string x-axis to datetime for time-series chart types.

    PRISM commonly passes ISO-style date strings (``"2023-01-01"``,
    ``"Jan 2023"``, ``"2023"``) without first calling ``pd.to_datetime``.
    Without coercion, ``_dispatch_builder`` routes ``multi_line`` /
    ``timeseries`` to ``_build_profile_line`` (the ordinal-x builder
    intended for yield-curve tenors like ``"1Y"`` / ``"10Y"``), which
    treats the strings as ordinal categories and produces verbose
    ``2023-01-01`` tick labels rotated -45 degrees.

    The fix is wrapper-side absorption (Principle #7): try to parse the
    column as datetime; if it succeeds, return a fresh copy with the
    column converted; otherwise return the input unchanged. The dispatcher
    then routes correctly to ``_build_multi_line`` / ``_build_timeseries``
    and the date axis gets the smart format (``"%b %y"``, ``"%Y"``,
    ``"%d %b"``) and horizontal labels.

    Skipped when:
      - chart_type is not ``multi_line`` / ``timeseries`` (only these
        dispatch on x dtype)
      - ``mapping['x_type'] == 'ordinal'`` (explicit caller override wins;
        e.g. tenor strings labelled as dates intentionally)
      - x column is already datetime or numeric
      - parsing raises (yield-curve tenors, ratings, regions, etc.)
    """
    if chart_type not in {"multi_line", "timeseries"}:
        return df
    if mapping.get("x_type") == "ordinal":
        return df

    x_field = _get_field(mapping, "x")
    if not x_field or x_field not in df.columns:
        return df

    x_series = df[x_field]
    if (
        pd.api.types.is_datetime64_any_dtype(x_series)
        or pd.api.types.is_numeric_dtype(x_series)
    ):
        return df

    try:
        import warnings as _warnings
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            converted = pd.to_datetime(x_series, errors="raise")
    except (ValueError, TypeError):
        return df

    df = df.copy()
    df[x_field] = converted
    logger.info(
        "[chart_functions] Auto-coerced x_field=%r from %s to datetime "
        "for chart_type=%s.",
        x_field, x_series.dtype, chart_type,
    )
    return df


def validate_plot_ready_df(
    df: pd.DataFrame,
    chart_type: str,
    mapping: Dict[str, Any],
) -> List[str]:
    """Validate that a DataFrame is ready for plotting.

    Catches the most common failure modes before they reach Vega-Lite,
    where they would produce silently empty / mis-rendered charts:
      - empty DataFrames
      - missing columns referenced by the mapping
      - all-NaN columns
      - non-datetime x for ``timeseries`` charts
      - non-numeric y for chart types that require it
      - excessive cardinality on color / facet columns
      - negative values on donut / pie charts

    Args:
        df: DataFrame to validate.
        chart_type: Type of chart being created (``ChartType``).
        mapping: Column mapping for the chart.

    Returns:
        A list of warning messages (non-fatal issues) accumulated during
        validation.

    Raises:
        ValidationError: If the DataFrame has a fatal issue that would
            prevent the chart from rendering.
    """
    logger.debug("[validate_plot_ready_df] START: chart_type=%s", chart_type)
    logger.debug(
        "[validate_plot_ready_df] df.shape=%s, columns=%s",
        df.shape,
        list(df.columns),
    )
    logger.debug("[validate_plot_ready_df] mapping=%s", mapping)

    warnings: List[str] = []

    # ---- empty DataFrame ----------------------------------------------------
    if len(df) == 0:
        logger.error("[validate_plot_ready_df] EMPTY DATAFRAME!")
        raise ValidationError("DataFrame is empty. Cannot create chart from empty data.")

    fields_to_check = _extract_fields(mapping)
    logger.debug("[validate_plot_ready_df] Fields to check: %s", fields_to_check)

    # ---- missing columns ----------------------------------------------------
    missing_cols = [f for f in fields_to_check if f not in df.columns]
    if missing_cols:
        logger.error("[validate_plot_ready_df] MISSING COLUMNS: %s", missing_cols)
        logger.error("[validate_plot_ready_df] Available columns: %s", list(df.columns))

        # Detect the specific reset_index/melt ordering bug. Common LLM
        # error: melt was called BEFORE renaming columns, so the original
        # index name (e.g. 'datetime') is still attached.
        datetime_cols = [
            col for col in df.columns
            if pd.api.types.is_datetime64_any_dtype(df[col])
        ]
        index_like_cols = [
            col for col in df.columns
            if (
                col in {"index", "Time", "DATE", "Date", "time", "Unnamed: 0"}
                or (isinstance(col, str) and "date" in col.lower())
            )
        ]
        potential_date_cols = list({*datetime_cols, *index_like_cols})

        if "date" in missing_cols and potential_date_cols:
            raise ValidationError(
                f"Missing column 'date' in DataFrame. "
                f"Available columns: {list(df.columns)}\n\n"
                f"LIKELY CAUSE: melt(id_vars=['date']) was called BEFORE renaming columns. "
                f"After reset_index(), the first column has the ORIGINAL index name, not 'date'.\n"
                f"Potential date columns found: {potential_date_cols}\n"
                f"FIX: Rename columns BEFORE calling melt():\n"
                f"  df = df.reset_index()\n"
                f"  df.columns = ['date', 'col1', 'col2']  # Rename FIRST\n"
                f"  df_long = df.melt(id_vars=['date'], ...)  # NOW 'date' exists"
            )

        # Detect missing color field for multi_line / area (long-format API).
        common_color_fields = {"series", "indicator", "category", "group", "variable"}
        if (
            chart_type in {"multi_line", "area"}
            and any(col in common_color_fields for col in missing_cols)
        ):
            raise ValidationError(
                f"Missing columns in DataFrame: {missing_cols}. "
                f"Available columns: {list(df.columns)}\n\n"
                f"TIP: For multi_line charts with a 'color' mapping, you need long-format "
                f"data with a column to distinguish series. Either:\n"
                f"  1. Melt: df.melt(id_vars=['date'], value_vars=[...], "
                f"var_name='series', value_name='value')\n"
                f"  2. Use mapping={{'y': ['col1', 'col2']}} to auto-melt wide-format data."
            )

        raise ValidationError(
            f"Missing columns in DataFrame: {missing_cols}. "
            f"Available columns: {list(df.columns)}"
        )

    # ---- all-NaN columns / sparse columns ----------------------------------
    for field_name in fields_to_check:
        if field_name in df.columns:
            non_null_count = df[field_name].notna().sum()
            total_count = len(df)
            if non_null_count == 0:
                raise ValidationError(
                    f"Column '{field_name}' has no valid (non-null) values. "
                    f"All ({total_count}) rows are NaN/None. "
                    f"This would result in an empty chart. "
                    f"Check your data source or fillna() before plotting."
                )
            if (
                non_null_count < 2
                and chart_type in {"timeseries", "multi_line", "scatter", "area", "scatter_multi"}
            ):
                raise ValidationError(
                    f"Column '{field_name}' has only {non_null_count} valid value(s). "
                    f"Chart type '{chart_type}' requires at least 2 data points. "
                    f"Check your data filtering."
                )

    # ---- empty column count (e.g. .assign() on a Series) -------------------
    if len(df.columns) == 0:
        raise ValidationError(
            "DataFrame has no columns. This often occurs when using .assign() on a Series "
            "instead of a DataFrame. Use df[['column']].assign() instead."
        )

    # ---- type validation per chart type ------------------------------------
    if chart_type == "timeseries":
        x_field = _get_field(mapping, "x")
        if x_field and not pd.api.types.is_datetime64_any_dtype(df[x_field]):
            raise ValidationError(
                f"For timeseries charts, x-axis column '{x_field}' must be datetime. "
                f"Current type: {df[x_field].dtype}. "
                f"Convert with: df['{x_field}'] = pd.to_datetime(df['{x_field}'])"
            )

    if chart_type in {"timeseries", "scatter", "bar", "area", "histogram", "boxplot"}:
        y_field = _get_field(mapping, "y")
        if y_field and y_field in df.columns and not pd.api.types.is_numeric_dtype(df[y_field]):
            raise ValidationError(
                f"Column '{y_field}' must be numeric for {chart_type} charts. "
                f"Current type: {df[y_field].dtype}. "
                f"Convert with: df['{y_field}'] = pd.to_numeric(df['{y_field}'], errors='coerce')"
            )

    # ---- cardinality guards ------------------------------------------------
    # Color cardinality is a HARD error: the default GS_PRIMARY palette has
    # MAX_COLOR_CARDINALITY (=10) colors. Beyond that, hues repeat and the
    # chart becomes visually ambiguous (two series render as the same color).
    # Reject up-front rather than silently produce an unreadable chart.
    #
    # TEMPORAL / NUMERIC color columns are also exempt because the engine
    # auto-switches them to a sequential gradient palette (viridis / turbo /
    # etc.) where every point gets a unique color from a continuous scale --
    # the 12-color cap doesn't apply and "many distinct values" is the
    # whole point (phase-space plots show evolution by gradient).
    color_field = _get_field(mapping, "color")
    if (
        color_field
        and color_field in df.columns
        and chart_type not in {"donut"}
    ):
        color_series = df[color_field]
        is_gradient_color = (
            pd.api.types.is_datetime64_any_dtype(color_series)
            or (
                pd.api.types.is_numeric_dtype(color_series)
                and not pd.api.types.is_bool_dtype(color_series)
            )
        )
        if not is_gradient_color:
            cardinality = color_series.nunique()
            if cardinality > MAX_COLOR_CARDINALITY:
                raise ValidationError(
                    f"Color column '{color_field}' has {cardinality} unique values, "
                    f"exceeding MAX_COLOR_CARDINALITY={MAX_COLOR_CARDINALITY}. "
                    f"The GS palette only has {MAX_COLOR_CARDINALITY} colors; "
                    f"beyond this point series repeat hues and become indistinguishable. "
                    f"Filter to top-{MAX_COLOR_CARDINALITY} categories first, e.g. "
                    f"`df = top_k_categories(df, '{color_field}', k={MAX_COLOR_CARDINALITY})`."
                )
    # Donut: same cap, but enforced separately below in the chart-specific
    # block so the suggested fix points at the right column.

    facet_field = _get_field(mapping, "facet")
    if facet_field and facet_field in df.columns:
        cardinality = df[facet_field].nunique()
        if cardinality > MAX_FACET_CARDINALITY:
            raise ValidationError(
                f"Facet column '{facet_field}' has {cardinality} unique values "
                f"(max allowed: {MAX_FACET_CARDINALITY}). "
                f"Filter to fewer categories before plotting."
            )

    # ---- soft warnings -----------------------------------------------------
    if len(df) > MAX_ROWS_INTERACTIVE:
        warnings.append(
            f"DataFrame has {len(df)} rows (>{MAX_ROWS_INTERACTIVE}). "
            f"Consider sampling or aggregating for better performance. "
            f"Example: df.sample(n={MAX_ROWS_INTERACTIVE}, random_state=42)"
        )

    for field_name in fields_to_check:
        if field_name in df.columns:
            missing_pct = df[field_name].isna().mean() * 100
            if missing_pct > 50:
                warnings.append(
                    f"Column '{field_name}' has {missing_pct:.1f}% missing values. "
                    f"Consider filling or filtering: df['{field_name}'].fillna(...) "
                    f"or df.dropna(subset=['{field_name}'])"
                )

    # ---- chart-specific validations ----------------------------------------
    if chart_type == "heatmap":
        x_field = _get_field(mapping, "x")
        y_field = _get_field(mapping, "y")
        if x_field and y_field and x_field in df.columns and y_field in df.columns:
            x_card = df[x_field].nunique()
            y_card = df[y_field].nunique()
            if x_card * y_card > 500:
                warnings.append(
                    f"Heatmap grid size ({x_card}x{y_card}={x_card * y_card} cells) is large. "
                    f"Consider aggregating or filtering for readability."
                )

    if chart_type == "donut":
        theta_field = (
            _get_field(mapping, "theta")
            or _get_field(mapping, "value")
            or _get_field(mapping, "y")
        )
        if theta_field and theta_field in df.columns and (df[theta_field] < 0).any():
            raise ValidationError(
                f"Donut/pie charts require non-negative values. "
                f"Column '{theta_field}' contains negative values."
            )

        # Donut slice cap: the categorical palette has MAX_COLOR_CARDINALITY
        # distinct hues. With more slices than that, neighboring slices end
        # up in the same hue (e.g. "Tech" and "Comm. Services" both dark
        # blue), making the chart unreadable. Reject up-front.
        color_field_donut = _get_field(mapping, "color")
        if color_field_donut and color_field_donut in df.columns:
            slice_card = df[color_field_donut].nunique()
            if slice_card > MAX_COLOR_CARDINALITY:
                raise ValidationError(
                    f"Donut has {slice_card} slices, exceeding "
                    f"MAX_COLOR_CARDINALITY={MAX_COLOR_CARDINALITY}. "
                    f"With more slices than colors, hues repeat and adjacent "
                    f"slices become visually indistinguishable. "
                    f"Aggregate the smallest slices into 'Other' first, e.g. "
                    f"`df = top_k_categories(df, '{color_field_donut}', "
                    f"k={MAX_COLOR_CARDINALITY - 1}, value_col='{theta_field}')`."
                )

    logger.debug("[validate_plot_ready_df] PASSED with %d warnings", len(warnings))
    return warnings


def _validate_encoding_data(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    chart_type: str,
) -> List[str]:
    """Validate that encoding fields have plottable data.

    Catches the case where data exists but is not plottable:
      - all values in x or y are NaN
      - no valid (x, y) pairs exist (both non-null in same row)
      - insufficient data points for the chart type
    """
    warnings: List[str] = []

    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")

    fields_to_check = [f for f in (x_field, y_field) if f and f in df.columns]
    for field_name in fields_to_check:
        non_null_count = df[field_name].notna().sum()
        if non_null_count == 0:
            raise ValidationError(
                f"Column '{field_name}' has no valid (non-null) values. "
                f"All {len(df)} rows are NaN/None. The chart would render empty. "
                f"Check your data transformations or use df['{field_name}'].fillna(...)."
            )
        if non_null_count < 2 and chart_type in {
            "timeseries", "multi_line", "scatter", "area", "scatter_multi",
        }:
            warnings.append(
                f"Column '{field_name}' has only {non_null_count} valid value(s). "
                f"Chart may not render meaningfully for '{chart_type}' type."
            )

    if x_field and y_field and x_field in df.columns and y_field in df.columns:
        valid_pairs = df[[x_field, y_field]].dropna()
        if len(valid_pairs) == 0:
            raise ValidationError(
                f"No valid (x, y) pairs found for chart type '{chart_type}'. "
                f"Columns '{x_field}' and '{y_field}' have no rows where both are non-null. "
                f"'{x_field}' has {df[x_field].notna().sum()} non-null values, "
                f"'{y_field}' has {df[y_field].notna().sum()} non-null values, "
                f"but they don't overlap. Check your data alignment."
            )
        if len(valid_pairs) < 2 and chart_type in {"scatter", "multi_line", "area"}:
            raise ValidationError(
                f"Only {len(valid_pairs)} valid data point(s) for '{chart_type}' chart. "
                f"Need at least 2 points to draw a line/trend. "
                f"Check your data filtering and ensure sufficient non-null values."
            )

    return warnings


def _validate_chart_data_integrity(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    chart_type: str,
) -> None:
    """Deep validation that data will produce a visible chart.

    This is the critical check that prevents silent empty charts.
    Called BEFORE building the Altair chart spec.

    Raises:
        ValidationError: If data would produce an empty / invisible chart.
    """
    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    color_field = _get_field(mapping, "color")

    # Validation 1: x-y pairs exist and are plottable.
    if x_field and y_field and x_field in df.columns and y_field in df.columns:
        valid_mask = df[x_field].notna() & df[y_field].notna()
        valid_count = int(valid_mask.sum())

        if valid_count == 0:
            raise ValidationError(
                f"CHART DATA INTEGRITY ERROR: No valid (x, y) pairs found.\n"
                f"Column '{x_field}' has {df[x_field].notna().sum()} non-null values.\n"
                f"Column '{y_field}' has {df[y_field].notna().sum()} non-null values.\n"
                f"But there are 0 rows where BOTH are non-null.\n"
                f"This would produce an empty chart. Check data alignment."
            )

        if valid_count < 2 and chart_type in {"multi_line", "area", "scatter"}:
            raise ValidationError(
                f"CHART DATA INTEGRITY ERROR: Only {valid_count} valid data point(s).\n"
                f"Chart type '{chart_type}' requires at least 2 points to draw.\n"
                f"Check your data filtering."
            )

    # Validation 2: For multi_line, verify color groups have data.
    if chart_type == "multi_line" and color_field and color_field in df.columns:
        empty_groups: List[str] = []
        for group_name, group_df in df.groupby(color_field):
            if y_field and y_field in group_df.columns:
                valid_in_group = int(group_df[y_field].notna().sum())
                if valid_in_group < 2:
                    empty_groups.append(f"{group_name} ({valid_in_group} valid points)")
        if empty_groups:
            raise ValidationError(
                f"CHART DATA INTEGRITY ERROR: Some color groups have insufficient data.\n"
                f"Groups with <2 valid points: {'; '.join(empty_groups)}\n"
                f"Each line in a multi_line chart needs at least 2 points.\n"
                f"Check your data or filter out empty groups."
            )

    # Validation 3: datetime conversion for x-axis must succeed.
    if x_field and x_field in df.columns and pd.api.types.is_datetime64_any_dtype(df[x_field]):
        try:
            test_values = df[x_field].dropna().head(5)
            for val in test_values:
                _ = val.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception as exc:  # noqa: BLE001 - surface as ValidationError
            raise ValidationError(
                f"CHART DATA INTEGRITY ERROR: Datetime conversion will fail.\n"
                f"Column '{x_field}' has datetime values that cannot be formatted.\n"
                f"Error: {exc}\n"
                f"Check for timezone issues or invalid datetime values."
            ) from exc

    # Validation 4: y values are finite (not inf).
    if y_field and y_field in df.columns and pd.api.types.is_numeric_dtype(df[y_field]):
        inf_count = int(np.isinf(df[y_field].dropna()).sum())
        if inf_count > 0:
            raise ValidationError(
                f"CHART DATA INTEGRITY ERROR: y-axis contains {inf_count} infinite values.\n"
                f"Column '{y_field}' has inf values that cannot be plotted.\n"
                f"Use df[y_field].replace([np.inf, -np.inf], np.nan) to remove them."
            )

    # Validation 5: y-axis scale homogeneity for single-axis multi-series
    # time-series charts. Catches the canonical "gold + WTI" pattern where
    # one series compresses to a flat line because its span is a tiny
    # fraction of the dominant series's range.
    _validate_y_scale_homogeneity(df, mapping, chart_type)

    # Validation 6: y-axis level disparity for single-axis multi-series
    # time-series charts. Catches the case where every series clears the
    # flatness floor (Validation 5 passes) but the series sit at bands
    # far enough apart that the chart still reads as flat horizontal
    # rails separated by empty whitespace. Canonical example: FCI tenor
    # contributions at 10 / 30 / 60 bp with per-series spans of ~7 each.
    _validate_y_level_disparity(df, mapping, chart_type)


def _validate_y_scale_homogeneity(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    chart_type: str,
) -> None:
    """Reject multi-series single-y-axis charts where the level / range
    mix would compress one or more series below
    ``_MIN_SERIES_VERTICAL_SHARE`` of the visible y-axis space.

    Canonical failure mode: plotting series with disparate magnitudes
    (gold $2000 + WTI $70; equity index + 2Y yield) or disparate levels
    with small variations (FCI components clustered at 30 / 60 / 10) on
    a shared linear y-axis. The high-magnitude (or high-level) series
    sets the axis domain and the others collapse to flat horizontal
    rails near their own level, defeating the chart's purpose.

    The error message routes the LLM toward three reshape options:
      (a) split into a 2-panel composite (``make_2pack_horizontal`` /
          ``make_2pack_vertical``) so each series gets its own y-axis;
      (b) keep on one chart but route the smallest-scale series to a
          right axis via ``mapping['dual_axis_series']=[...]``;
      (c) z-score-normalize or rebase-to-100 every series so all
          variations show on a comparable dimensional scale.

    Scope:
      - Applies to ``multi_line`` and ``timeseries`` (the canonical
        single-y-axis time-series shapes). ``area`` is intentionally
        excluded because it is always stacked-additive (each series's
        vertical share IS its share of the stack, by design). ``bar`` /
        ``boxplot`` / etc. use different visual paradigms where this
        flatness heuristic does not transfer cleanly.
      - Skipped when ``mapping['dual_axis_series']`` is set (caller has
        already split series across two axes -- no single-axis flatness
        conflict).
      - Skipped when fewer than 2 distinct series are present (one
        series defines its own scale -- nothing to flatten against).
      - Skipped when the global y span is zero (all values equal --
        flatness has no meaning).
    """
    if chart_type not in {"multi_line", "timeseries"}:
        return
    if mapping.get("dual_axis_series"):
        return

    color_field = _get_field(mapping, "color")
    y_field = _get_field(mapping, "y")
    if not (color_field and y_field):
        return
    if color_field not in df.columns or y_field not in df.columns:
        return
    if not pd.api.types.is_numeric_dtype(df[y_field]):
        return

    series_names = list(df[color_field].dropna().unique())
    if len(series_names) < 2:
        return

    # Per-series spans + global min/max across all series.
    series_spans: Dict[str, Tuple[float, float, float]] = {}
    global_min = float("inf")
    global_max = float("-inf")
    for name in series_names:
        s = pd.to_numeric(
            df.loc[df[color_field] == name, y_field], errors="coerce"
        ).dropna()
        if len(s) == 0:
            continue
        s_min, s_max = float(s.min()), float(s.max())
        series_spans[str(name)] = (s_min, s_max, s_max - s_min)
        global_min = min(global_min, s_min)
        global_max = max(global_max, s_max)

    if len(series_spans) < 2:
        return  # Only one series had any valid numeric values.
    global_span = global_max - global_min
    if global_span <= 0:
        return  # All values identical across all series; flatness has no meaning.

    flat_series: List[Tuple[str, float, float]] = []
    for name, (_smin, _smax, s_span) in series_spans.items():
        share = s_span / global_span
        if share < _MIN_SERIES_VERTICAL_SHARE:
            flat_series.append((name, s_span, share))

    if not flat_series:
        return

    # Smallest-share first -- stable + actionable error messages.
    flat_series.sort(key=lambda t: t[2])
    flat_desc = "; ".join(
        f"'{name}' span={s_span:.4g} ({share * 100:.1f}% of y-axis)"
        for name, s_span, share in flat_series
    )
    full_desc = "; ".join(
        f"'{name}' [{s_min:.4g} .. {s_max:.4g}] span={s_max - s_min:.4g}"
        for name, (s_min, s_max, _) in sorted(series_spans.items())
    )
    smallest = flat_series[0][0]
    threshold_pct = int(_MIN_SERIES_VERTICAL_SHARE * 100)

    raise ValidationError(
        f"Y-AXIS SCALE MISMATCH: {len(flat_series)} of {len(series_spans)} "
        f"series would compress below {threshold_pct}% of the visible "
        f"y-axis span (would read as flat horizontal rails at different "
        f"levels). Flat: {flat_desc}. All series: {full_desc}. Global "
        f"y-axis span: {global_span:.4g} [{global_min:.4g} .. "
        f"{global_max:.4g}]. Four reshape options:\n"
        f"  (a) Split into a 2-panel composite -- "
        f"`make_2pack_horizontal(...)` or `make_2pack_vertical(...)` -- "
        f"so each series gets its own y-axis (canonical fix for "
        f"two-series scale mismatches like gold + WTI).\n"
        f"  (b) Route the smallest-scale series to a right axis: "
        f"`mapping['dual_axis_series']=['{smallest}']` plus "
        f"`mapping['y_title_right']='...'`. Best when the argument is "
        f"co-movement of two series with different magnitudes.\n"
        f"  (c) Z-score-normalize or rebase-to-100 every series before "
        f"plotting so all variations share a dimensional scale (loses "
        f"absolute level but preserves co-movement; best for 3+ series).\n"
        f"  (d) Small-multiples / facet -- one panel per series, each "
        f"with its own y-axis: `mapping['facet']='{color_field}'` (and "
        f"drop `color`). Best when the argument is the SHAPE of each "
        f"series (component decomposition, regional comparison) rather "
        f"than co-movement. See `chart_context_grids.md` for the full "
        f"facet surface."
    )


def _validate_y_level_disparity(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    chart_type: str,
) -> None:
    """Reject multi-series single-y-axis charts where every series has
    visible variation but the gap between adjacent (sorted-by-mean)
    series's means exceeds ``_LEVEL_DISPARITY_RATIO_THRESHOLD`` times
    the largest individual span.

    Companion to ``_validate_y_scale_homogeneity``. The flatness gate
    catches "one series collapses to a flat rail because its span is a
    tiny fraction of the global span" (gold + WTI). This gate catches
    the visually-similar case where every series clears the flatness
    floor but the series sit at bands far enough apart that the chart
    still reads as flat horizontal rails separated by empty whitespace.

    Canonical examples:
      - corporate saving (~2.5%) + investment (~9.9%) of GDP -- each
        spans ~0.8 pp, gap ~7.4 pp, ratio ~9x.
      - FCI tenor contributions at 10 / 30 / 60 bp with per-series
        spans of ~7 each -- ratio 30 / 7 ~4x.

    Scope mirrors ``_validate_y_scale_homogeneity`` exactly:
      - Applies to ``multi_line`` and ``timeseries`` only.
      - Skipped when ``mapping['dual_axis_series']`` is set.
      - Skipped when fewer than 2 distinct series are present.
      - Skipped when global y span is zero.
    """
    if chart_type not in {"multi_line", "timeseries"}:
        return
    if mapping.get("dual_axis_series"):
        return

    color_field = _get_field(mapping, "color")
    y_field = _get_field(mapping, "y")
    if not (color_field and y_field):
        return
    if color_field not in df.columns or y_field not in df.columns:
        return
    if not pd.api.types.is_numeric_dtype(df[y_field]):
        return

    series_names = list(df[color_field].dropna().unique())
    if len(series_names) < 2:
        return

    # Per-series mean + span; collect side-by-side.
    series_stats: Dict[str, Tuple[float, float]] = {}
    for name in series_names:
        s = pd.to_numeric(
            df.loc[df[color_field] == name, y_field], errors="coerce"
        ).dropna()
        if len(s) == 0:
            continue
        series_stats[str(name)] = (float(s.mean()), float(s.max() - s.min()))

    if len(series_stats) < 2:
        return

    largest_span = max(span for _mean, span in series_stats.values())
    if largest_span <= 0:
        return  # All series flat; flatness gate (Validation 5) will catch.

    # Sort by mean; find the largest adjacent-pair gap.
    sorted_by_mean = sorted(series_stats.items(), key=lambda kv: kv[1][0])
    gaps: List[Tuple[str, str, float]] = []
    for (name_lo, (mean_lo, _)), (name_hi, (mean_hi, _)) in zip(
        sorted_by_mean[:-1], sorted_by_mean[1:]
    ):
        gaps.append((name_lo, name_hi, mean_hi - mean_lo))
    largest_gap_pair = max(gaps, key=lambda g: g[2])
    name_lo, name_hi, max_gap = largest_gap_pair

    ratio = max_gap / largest_span
    if ratio <= _LEVEL_DISPARITY_RATIO_THRESHOLD:
        return

    # Pick the side of the largest gap with the smaller mean as the
    # default ``dual_axis_series`` payload. Either side works; smaller-
    # mean side is the more conventional "right axis = lower-level
    # secondary" convention.
    full_desc = "; ".join(
        f"'{name}' mean={mean:.4g} span={span:.4g}"
        for name, (mean, span) in sorted(
            series_stats.items(), key=lambda kv: kv[1][0]
        )
    )

    mean_lo = series_stats[name_lo][0]
    mean_hi = series_stats[name_hi][0]

    raise ValidationError(
        f"Y-AXIS LEVEL DISPARITY: {len(series_stats)} series each have "
        f"visible variation but sit at bands far enough apart that the "
        f"chart will read as flat horizontal rails separated by empty "
        f"whitespace. Largest mean gap: '{name_lo}' "
        f"(mean {mean_lo:.4g}) vs '{name_hi}' (mean {mean_hi:.4g}); "
        f"gap={max_gap:.4g}, largest individual span={largest_span:.4g}, "
        f"ratio={ratio:.2f}x (rejection threshold: "
        f"{_LEVEL_DISPARITY_RATIO_THRESHOLD:.0f}x). All series: "
        f"{full_desc}. Four reshape options:\n"
        f"  (a) Split into a 2-panel composite -- "
        f"`make_2pack_horizontal(...)` or `make_2pack_vertical(...)` -- "
        f"so each series gets its own y-axis (canonical fix for "
        f"two-series level disparities like saving + investment).\n"
        f"  (b) Route the lower-level series to a right axis: "
        f"`mapping['dual_axis_series']=['{name_lo}']` plus "
        f"`mapping['y_title_right']='...'`. Best when the argument is "
        f"co-movement of two series with different levels.\n"
        f"  (c) Z-score-normalize or rebase-to-100 every series before "
        f"plotting so all variations share a dimensional scale (loses "
        f"absolute level but preserves co-movement; best for 3+ series).\n"
        f"  (d) Small-multiples / facet -- one panel per series, each "
        f"with its own y-axis: `mapping['facet']='{color_field}'` (and "
        f"drop `color`). Best when the argument is the SHAPE of each "
        f"series (component decomposition, regional comparison) rather "
        f"than co-movement. See `chart_context_grids.md` for the full "
        f"facet surface."
    )


def _group_scale_ok(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    chart_type: str,
    names: List[str],
) -> bool:
    """True when a subset of series clears BOTH y-scale gates on its own axis.

    Used by the dual-axis auto-recovery to verify that a proposed magnitude
    cluster (the set destined for one axis) is internally compatible -- i.e.
    no member compresses into a flat rail relative to the others in the
    group. A single-series group trivially passes (one series defines its
    own scale).
    """
    if len(names) < 2:
        return True
    wanted = {str(n) for n in names}
    color_field = _get_field(mapping, "color")
    if not color_field or color_field not in df.columns:
        return False
    sub = df[df[color_field].astype(str).isin(wanted)]
    try:
        _validate_y_scale_homogeneity(sub, mapping, chart_type)
        _validate_y_level_disparity(sub, mapping, chart_type)
    except ValidationError:
        return False
    return True


def _maybe_auto_recover_y_scale(
    exc: "ValidationError",
    df: pd.DataFrame,
    chart_type: str,
    mapping: Dict[str, Any],
    *,
    depth: int,
) -> Optional[Tuple[Dict[str, Any], str]]:
    """Detect a y-scale rejection and propose a dual-axis fix.

    The two y-scale gates (``_validate_y_scale_homogeneity``,
    ``_validate_y_level_disparity``) reject single-axis multi-series
    time-series charts whose level / range mix would compress one or
    more series into flat horizontal rails. When the series fall into
    exactly TWO magnitude clusters, the canonical fix is unambiguous:
    put each cluster on its own y-axis. The engine does this in-line so
    PRISM isn't punished for a deterministic shape problem.

    The split is found by sorting series by ``|mean|`` and cutting at the
    largest magnitude gap, then VERIFYING that both resulting clusters
    independently clear the y-scale gates (a dual axis only has two
    scales to give). The 2-series case is the degenerate version (the
    low cluster is the single smaller series). When no 2-cluster split
    resolves the mismatch -- i.e. 3+ irreconcilable magnitude tiers --
    the function returns ``None`` so the editorial choice (2-pack /
    z-score / facet) stays with PRISM. The rejection message names all
    four options.

    Returns:
        ``(new_mapping, recovery_message)`` if the rejection qualifies for
        auto-recovery, otherwise ``None``. The caller is responsible for
        re-invoking ``make_chart`` with the new mapping and incrementing
        ``_auto_recover_depth`` to break the cycle.
    """
    if depth > 0:
        return None
    if chart_type not in {"multi_line", "timeseries"}:
        return None
    if mapping.get("dual_axis_series"):
        return None
    msg = str(exc)
    if not (
        msg.startswith("Y-AXIS SCALE MISMATCH")
        or msg.startswith("Y-AXIS LEVEL DISPARITY")
    ):
        return None

    color_field = _get_field(mapping, "color")
    y_field = _get_field(mapping, "y")
    if not (color_field and y_field):
        return None
    if color_field not in df.columns or y_field not in df.columns:
        return None
    if not pd.api.types.is_numeric_dtype(df[y_field]):
        return None

    series_names = [
        str(name) for name in df[color_field].dropna().unique()
    ]
    if len(series_names) < 2:
        return None

    # Compute |mean| per series. Skip auto-recovery when ANY series is
    # constant (span == 0); a constant series is a horizontal threshold
    # semantically, and the better fix is `HLine(y=<const>)` not a flat
    # right-axis line. The rejection message already routes the LLM toward
    # HLine via the standard "(b) dual-axis" suggestion.
    means: Dict[str, float] = {}
    for name in series_names:
        s = pd.to_numeric(
            df.loc[df[color_field].astype(str) == name, y_field],
            errors="coerce",
        ).dropna()
        if len(s) == 0:
            return None
        if float(s.max() - s.min()) <= 0:
            return None  # one series is constant -- defer to caller
        means[name] = float(abs(s.mean()))

    # Find the cleanest split into a low-magnitude cluster (-> right axis)
    # and a high-magnitude cluster (left axis). Sort by |mean|, then try
    # split points ordered by the size of the magnitude gap between
    # neighbours; accept the first split where BOTH clusters independently
    # clear the y-scale gates. 3+ irreconcilable tiers leave no valid
    # 2-cluster split -> return None so PRISM picks the reshape.
    ordered = sorted(series_names, key=lambda n: means[n])
    candidate_splits = sorted(
        range(1, len(ordered)),
        key=lambda k: means[ordered[k]] / max(means[ordered[k - 1]], 1e-12),
        reverse=True,
    )
    right_group: Optional[List[str]] = None
    for k in candidate_splits:
        low, high = ordered[:k], ordered[k:]
        if (
            _group_scale_ok(df, mapping, chart_type, low)
            and _group_scale_ok(df, mapping, chart_type, high)
        ):
            right_group = low
            break
    if not right_group:
        return None

    new_mapping = dict(mapping)
    new_mapping["dual_axis_series"] = list(right_group)
    if not new_mapping.get("y_title_right"):
        new_mapping["y_title_right"] = (
            right_group[0] if len(right_group) == 1 else "Right axis"
        )

    gate = (
        "scale-mismatch" if msg.startswith("Y-AXIS SCALE MISMATCH")
        else "level-disparity"
    )
    routed = (
        f"'{right_group[0]}'" if len(right_group) == 1
        else f"the smaller-magnitude group {right_group}"
    )
    recovery_message = (
        f"AUTO-RECOVERED: y-axis {gate} gate rejected the single-axis "
        f"chart. Engine routed {routed} to the right axis "
        f"(dual_axis_series={right_group}) and re-rendered. Override by "
        f"setting dual_axis_series explicitly or switching chart shape "
        f"(e.g. make_2pack_horizontal)."
    )
    return new_mapping, recovery_message


# ===========================================================================
# MODULE: LABEL FORMATTING
# ===========================================================================

# Common abbreviations that should retain their canonical capitalization
# rather than being .title()-cased (which would produce 'Yoy', 'Gdp', etc.).
_LABEL_ABBREVIATIONS: Dict[str, str] = {
    "yoy": "YoY", "qoq": "QoQ", "mom": "MoM",
    "gdp": "GDP", "cpi": "CPI", "pce": "PCE", "ppi": "PPI",
    "nfp": "NFP", "fomc": "FOMC", "fed": "Fed",
    "ecb": "ECB", "boj": "BoJ", "boe": "BoE",
    "us": "US", "uk": "UK", "eu": "EU", "fx": "FX",
    "bp": "bp", "bps": "bps",
    "pct": "%", "percent": "%",
}


def _format_label(raw_label: str, mapping: Dict[str, Any], key: str) -> str:
    """Format a raw column name into a human-readable axis/legend label.

    Priority:
      1. Explicit ``mapping[f'{key}_title']`` overrides everything.
      2. Otherwise, auto-format the raw column name:
         underscores -> spaces, title-case, preserve abbreviations,
         and append a guessed-units suffix when detectable.

    Args:
        raw_label: The raw column name (e.g. ``'Canada_YOY_growth'``).
        mapping: The chart mapping dictionary.
        key: The mapping key to check for an explicit title (e.g. ``'y'``).

    Returns:
        Human-readable label string.
    """
    title_key = f"{key}_title"
    if title_key in mapping and mapping[title_key]:
        return mapping[title_key]

    if not raw_label:
        return ""

    formatted = raw_label.replace("_", " ")
    words = formatted.split()
    result_words: List[str] = []
    for word in words:
        lower_word = word.lower()
        if lower_word in _LABEL_ABBREVIATIONS:
            result_words.append(_LABEL_ABBREVIATIONS[lower_word])
        else:
            result_words.append(word.title())
    formatted_label = " ".join(result_words)

    guessed_units = guess_units_from_name(raw_label)
    if guessed_units and guessed_units not in formatted_label:
        formatted_label = f"{formatted_label} ({guessed_units})"

    return formatted_label


# ===========================================================================
# MODULE: ANNOTATIONS
# ===========================================================================

# Style aliases recognized by VLine / HLine ``style=`` kwarg.
_LINE_STYLE_DASH: Dict[str, List[int]] = {
    "solid": [],
    "dashed": [4, 4],
    "dotted": [1, 2],
}


# Threshold values that are universally understood by macro/rates
# professionals and therefore add visual noise rather than analytical
# value when annotated. ``render_annotations`` silently drops HLines at
# these levels and warns via the logger.
_OBVIOUS_HLINE_THRESHOLDS: Dict[float, str] = {
    0.0: "zero line (visually obvious on any chart)",
    50.0: "PMI/ISM expansion-contraction threshold (universally known)",
    2.0: "Fed 2% inflation target (universally known)",
}


# Fraction of the data's x-range from the right edge inside which any
# ``VLine`` annotation is auto-rejected. The chart's right edge IS the
# latest x value -- a marker placed in the right-most 5% of the data
# (e.g. a "Today" / "Now" / latest-event VLine) reads as the chart edge
# itself rather than as an event, adding clutter without information.
# ``render_annotations`` silently drops these and warns via the logger.
_VLINE_RIGHT_EDGE_REJECT_FRAC: float = 0.05


def _resolve_axis_type(df: pd.DataFrame, col: str) -> str:
    """Infer the right Vega-Lite axis type for a column.

    - ``temporal`` if the column is datetime-typed.
    - ``quantitative`` if numeric.
    - ``nominal`` otherwise (string categories, e.g. yield-curve tenors).

    Returns ``"quantitative"`` if ``col`` is missing from ``df``.
    """
    if col not in df.columns:
        return "quantitative"
    if pd.api.types.is_datetime64_any_dtype(df[col]):
        return "temporal"
    if pd.api.types.is_numeric_dtype(df[col]):
        return "quantitative"
    return "nominal"


def _profile_x_axis_type(df: pd.DataFrame, x_field: Optional[str]) -> str:
    """The Vega-Lite x-axis type a profile / yield-curve line uses.

    The SINGLE authority for the profile-line x encoding type.
    ``_build_profile_line`` builds its base layer from it, and the
    line-family builders publish it into ``mapping['_x_axis_type']`` so
    every annotation layer (LastValueLabel, VLine, HLine, Band, ...)
    inherits the SAME type via ``_annotation_x_axis_type``.

    The defect this prevents: when the base line layer and an annotation
    layer disagree on the x type for the same field (e.g. base
    ``ordinal`` vs an end-of-line label layer ``quantitative`` for a
    numeric tenor column), Vega-Lite resolves them onto INDEPENDENT x
    scales and paints a second, spurious x-axis (titled with the raw
    field name) while the line collapses into a thin strip.

    Decision (the historical inline rule from ``_build_profile_line``):
      - numeric with > 15 distinct values -> ``quantitative`` (let
        Vega-Lite auto-thin a continuous axis; a categorical axis would
        overcrowd).
      - everything else (low-cardinality numeric tenors like
        0.25/2/5/10/30, or string tenors like ``"2Y"``) -> ``ordinal``
        (evenly-spaced categories, the rates / vol-smile house style).
    """
    if x_field is None or x_field not in df.columns:
        return "ordinal"
    series = df[x_field]
    if pd.api.types.is_numeric_dtype(series) and series.nunique() > 15:
        return "quantitative"
    return "ordinal"


def _annotation_x_axis_type(
    df: pd.DataFrame, x_col: str, mapping: Dict[str, Any],
) -> str:
    """Resolve an annotation layer's x-axis type.

    Prefers the base builder's PUBLISHED x-axis type
    (``mapping['_x_axis_type']``, set by the line-family builders --
    ``_build_profile_line`` / ``_build_timeseries`` /
    ``_build_multi_line_dual_axis``) so an annotation layer can never
    disagree with the base layer's x encoding and trigger the
    duplicate-axis defect. Non-line chart types never publish a type, so
    their annotations resolve from the column dtype exactly as before.
    """
    published = mapping.get("_x_axis_type")
    if published:
        return published
    return _resolve_axis_type(df, x_col)


def _resolve_x_sort_for_annotation(
    df: pd.DataFrame, mapping: Dict[str, Any], x_col: str,
) -> Optional[List[str]]:
    """Pick the same x-axis sort the base chart uses.

    Returns:
      - ``None`` for numeric / temporal x (Vega-Lite's natural sort
        works without help).
      - A list of strings when an explicit ``mapping['x_sort']`` or a
        tenor sort (``["1M", "3M", "1Y"]``) applies.
      - ``None`` for a generic nominal axis -- callers should NOT
        pass a sort to alt.X in that case but should ALSO ensure the
        layered annotation doesn't accidentally introduce ascending
        sort. Helpers like ``_apply_nominal_sort_kwargs`` handle the
        explicit ``sort: null`` plumbing for nominal axes.
    """
    if x_col not in df.columns:
        return None
    if pd.api.types.is_numeric_dtype(df[x_col]) or pd.api.types.is_datetime64_any_dtype(
        df[x_col]
    ):
        return None
    explicit = mapping.get("x_sort")
    if explicit:
        return list(explicit)
    return _infer_tenor_sort(df[x_col].unique())


def _last_row_at_max_x(
    df: pd.DataFrame,
    x_col: str,
    color_col: Optional[str] = None,
) -> pd.DataFrame:
    """Return one row per series at the latest x position.

    For datetime / numeric x, uses ``idxmax``. For ordinal / string x
    (e.g. ``05/27 03:00`` labels), ``idxmax`` raises on object dtype --
    fall back to the last row per group in data order, which matches
    chronologically-sorted intraday frames.
    """
    if color_col and color_col in df.columns:
        if (
            pd.api.types.is_datetime64_any_dtype(df[x_col])
            or pd.api.types.is_numeric_dtype(df[x_col])
        ):
            last_idx = df.groupby(color_col)[x_col].idxmax()
            return df.loc[last_idx].reset_index(drop=True)
        return df.groupby(color_col, sort=False).tail(1).reset_index(drop=True)

    if (
        pd.api.types.is_datetime64_any_dtype(df[x_col])
        or pd.api.types.is_numeric_dtype(df[x_col])
    ):
        return df.loc[[df[x_col].idxmax()]].reset_index(drop=True)
    return df.tail(1).reset_index(drop=True)


def _apply_nominal_axis_sort(
    kwargs: Dict[str, Any],
    df: pd.DataFrame,
    field: str,
    explicit_sort: Optional[List[str]],
) -> None:
    """Mutate ``kwargs`` so a layered annotation's nominal axis sort
    matches the base chart's data-order rendering.

    Three cases:
      1. ``explicit_sort`` is a non-empty list (explicit user order or
         tenor pattern): apply it as-is.
      2. ``field`` is nominal in ``df``: emit ``sort=None`` so the
         spec carries ``"sort": null``, preserving the data's natural
         row order. This is required because Vega-Lite's default for
         nominal/ordinal fields without an explicit sort is ascending
         (alphabetical), and that propagates through layer-merge,
         flipping a heatmap's axis order when an annotation lands on
         top of it.
      3. Otherwise (numeric / temporal / missing field): leave
         ``kwargs`` unchanged.
    """
    if explicit_sort:
        kwargs["sort"] = list(explicit_sort)
        return
    if field in df.columns and not (
        pd.api.types.is_numeric_dtype(df[field])
        or pd.api.types.is_datetime64_any_dtype(df[field])
    ):
        kwargs["sort"] = None


def _to_numeric_x(val: Any) -> float:
    """Coerce an arbitrary x-axis value (timestamp / number / string-date)
    to a float for distance comparisons. Falls back to 0.0 on failure.

    Priority:
      1. ``Timestamp``/``datetime`` -> ``.timestamp()`` (seconds-since-epoch).
      2. Already-numeric -> ``float(val)`` directly (don't reinterpret as ns).
      3. String / other -> ``pd.Timestamp(val).timestamp()``.
      4. Fallback to ``float(val)`` then ``0.0``.
    """
    if val is None:
        return 0.0
    if hasattr(val, "timestamp") and callable(getattr(val, "timestamp")):
        try:
            return float(val.timestamp())
        except Exception:  # noqa: BLE001
            pass
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    try:
        return float(pd.Timestamp(val).timestamp())
    except Exception:  # noqa: BLE001
        pass
    try:
        return float(val)
    except Exception:  # noqa: BLE001
        return 0.0


@dataclass
class Annotation:
    """Base annotation. Subclasses implement ``to_layer``."""

    label: Optional[str] = None
    label_color: Optional[str] = None

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        raise NotImplementedError


@dataclass
class VLine(Annotation):
    """Vertical reference line at an x value.

    Renders as a dashed rule (by default) spanning the full y-axis,
    with an optional label that auto-staggers when multiple VLines
    cluster together.
    """

    x: Any = None
    color: str = "#666666"
    stroke_width: float = 1.5
    stroke_dash: List[int] = field(default_factory=lambda: [4, 4])
    style: Optional[str] = None  # 'solid' | 'dashed' | 'dotted'

    def __post_init__(self) -> None:
        if self.style is not None and self.style in _LINE_STYLE_DASH:
            self.stroke_dash = list(_LINE_STYLE_DASH[self.style])

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        x_col_user = mapping.get("x", "x")
        x_col = x_col_user if x_col_user in df.columns else "x"
        x_type = _annotation_x_axis_type(df, x_col, mapping)
        x_sort = _resolve_x_sort_for_annotation(df, mapping, x_col)
        y_field_user = (
            mapping.get("y") if isinstance(mapping.get("y"), str) else None
        )
        y_field = y_field_user if y_field_user else "y"

        x_kwargs: Dict[str, Any] = {"type": x_type}
        _apply_nominal_axis_sort(x_kwargs, df, x_col, x_sort)

        line_df = pd.DataFrame({x_col: [self.x]})
        line = (
            alt.Chart(line_df)
            .mark_rule(
                color=self.color,
                strokeWidth=self.stroke_width,
                strokeDash=self.stroke_dash,
            )
            .encode(x=alt.X(x_col, **x_kwargs))
        )

        if not self.label:
            return line

        # If the base chart has a numeric y-axis, anchor the label to the
        # data's max so it sits near the top inside the plot. If y is
        # nominal (e.g. horizontal-bar's category axis), pin the label to
        # the top of the chart frame using a screen-coordinate y value.
        #
        # On a dual-axis chart, ``df[y_field_user]`` contains BOTH sides'
        # values stacked together (long format), so ``.max()`` picks up
        # whichever axis has the larger numeric range (typically the
        # right axis: e.g. WTI at ~$100 dominates a 2s10s spread peaking
        # at ~+50 bp). After ``render_annotations`` reroutes the label
        # encoding through the LEFT scale, that out-of-range y position
        # falls above the visible plot. Anchor to the LEFT axis's
        # configured top instead, with a 5% headroom margin so the
        # ``dy=-10`` offset (label drawn 10px above y_pos) still lands
        # INSIDE the plot frame rather than colliding with the title
        # band above.
        if (
            y_field_user
            and y_field_user in df.columns
            and pd.api.types.is_numeric_dtype(df[y_field_user])
        ):
            dual_cfg = mapping.get("dual_axis_config") or {}
            left_domain = dual_cfg.get("y_domain_left")
            if left_domain is not None:
                lo = float(min(left_domain[0], left_domain[1]))
                hi = float(max(left_domain[0], left_domain[1]))
                y_pos = hi - (hi - lo) * 0.05
            else:
                y_pos = float(df[y_field_user].max())
            label_df = pd.DataFrame({x_col: [self.x], y_field: [y_pos]})
            text = (
                alt.Chart(label_df)
                .mark_text(
                    align="left",
                    dx=5,
                    dy=-10,
                    fontSize=10,
                    color=self.label_color or self.color,
                )
                .encode(
                    x=alt.X(x_col, **x_kwargs),
                    y=alt.Y(f"{y_field}:Q"),
                    text=alt.value(self.label),
                )
            )
        else:
            label_df = pd.DataFrame({x_col: [self.x]})
            text = (
                alt.Chart(label_df)
                .mark_text(
                    align="left",
                    baseline="top",
                    dx=5,
                    dy=4,
                    fontSize=10,
                    color=self.label_color or self.color,
                )
                .encode(
                    x=alt.X(x_col, **x_kwargs),
                    y=alt.value(0),
                    text=alt.value(self.label),
                )
            )
        return line + text


@dataclass
class HLine(Annotation):
    """Horizontal reference line at a y value (left or right axis).

    Labels render slightly *above* the line with a white halo so they
    sit cleanly off the dashed rule rather than reading as a strikethrough.
    When the line is near the top of the plot, ``render_annotations``
    flips the label below the line (positive ``_label_dy``).
    """

    y: float = 0.0
    axis: Literal["left", "right"] = "left"
    color: str = "#666666"
    stroke_width: float = 1.5
    stroke_dash: List[int] = field(default_factory=lambda: [4, 4])
    style: Optional[str] = None
    # Internal: default dy lifts the label off the line. ``render_annotations``
    # may add a positive bump (e.g. +18) to flip below the line near the top
    # boundary so the label doesn't fall outside the plot area.
    _label_dy: int = field(default=-8, repr=False)
    # Halo rendered behind the label text so the label is legible whether
    # it sits above or below the dashed rule. Set ``halo=False`` to opt out.
    halo: bool = True
    halo_color: str = "#FFFFFF"
    halo_width: float = 4.0

    def __post_init__(self) -> None:
        if self.style is not None and self.style in _LINE_STYLE_DASH:
            self.stroke_dash = list(_LINE_STYLE_DASH[self.style])

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        # Use the base chart's y field so the line renders on the same
        # scale and Vega-Lite's shared-axis resolution doesn't override
        # the base chart's axis title with our own (null) one.
        y_field = mapping.get("y") if isinstance(mapping.get("y"), str) else None
        col_name = y_field if y_field else "y"
        line_df = pd.DataFrame({col_name: [self.y]})
        line = (
            alt.Chart(line_df)
            .mark_rule(
                color=self.color,
                strokeWidth=self.stroke_width,
                strokeDash=self.stroke_dash,
                clip=True,
            )
            .encode(y=alt.Y(f"{col_name}:Q"))
        )

        if not self.label:
            return line

        text_color = self.label_color or self.color
        layers: List[alt.Chart] = [line]

        # Class 3 absorption: when ``make_chart`` stashes a right-edge
        # anchor x in ``mapping`` (bar charts), route the label to the
        # right side of the bar zone using ``align='right'`` against the
        # rightmost x category. Otherwise default behaviour:
        # ``align='left', dx=5`` (anchor floats near the plot horizontal
        # midpoint by Vega-Lite default).
        anchor_x = mapping.get("_anno_label_anchor_right_x")
        x_field_user = mapping.get("x") if isinstance(mapping.get("x"), str) else None
        if (
            anchor_x is not None
            and x_field_user
            and x_field_user in df.columns
        ):
            label_df = pd.DataFrame({col_name: [self.y], x_field_user: [anchor_x]})
            x_type = _annotation_x_axis_type(df, x_field_user, mapping)
            label_align = "right"
            label_dx = -5
            label_x_enc = alt.X(x_field_user, type=x_type)
        else:
            label_df = line_df
            label_align = "left"
            label_dx = 5
            label_x_enc = None

        text_encode_kwargs: Dict[str, Any] = {
            "y": alt.Y(f"{col_name}:Q"),
            "text": alt.value(self.label),
        }
        if label_x_enc is not None:
            text_encode_kwargs["x"] = label_x_enc

        if self.halo:
            halo_layer = (
                alt.Chart(label_df)
                .mark_text(
                    align=label_align,
                    dx=label_dx,
                    dy=self._label_dy,
                    fontSize=10,
                    stroke=self.halo_color,
                    strokeWidth=self.halo_width,
                    strokeJoin="round",
                    strokeOpacity=1.0,
                    color=self.halo_color,
                )
                .encode(**text_encode_kwargs)
            )
            layers.append(halo_layer)

        text = (
            alt.Chart(label_df)
            .mark_text(
                align=label_align,
                dx=label_dx,
                dy=self._label_dy,
                fontSize=10,
                color=text_color,
            )
            .encode(**text_encode_kwargs)
        )
        layers.append(text)
        return alt.layer(*layers)


@dataclass
class Band(Annotation):
    """Shaded vertical (x1..x2) or horizontal (y1..y2) band.

    On a dual-axis chart, ``axis='right'`` routes a horizontal band's
    y values against the right scale (default ``'left'``). Vertical
    bands ignore ``axis`` -- they have no y values to anchor.
    """

    x1: Optional[Any] = None
    x2: Optional[Any] = None
    y1: Optional[float] = None
    y2: Optional[float] = None
    color: str = "#CCCCCC"
    opacity: float = 0.3
    axis: Literal["left", "right"] = "left"

    # Aliases for common LLM mistakes; kept out of repr.
    x_start: Optional[Any] = field(default=None, repr=False)
    x_end: Optional[Any] = field(default=None, repr=False)
    y_start: Optional[float] = field(default=None, repr=False)
    y_end: Optional[float] = field(default=None, repr=False)
    start_x: Optional[Any] = field(default=None, repr=False)
    end_x: Optional[Any] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.x1 is None:
            self.x1 = self.x_start if self.x_start is not None else self.start_x
        if self.x2 is None:
            self.x2 = self.x_end if self.x_end is not None else self.end_x
        if self.y1 is None:
            self.y1 = self.y_start
        if self.y2 is None:
            self.y2 = self.y_end

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        # Use the base chart's actual x/y field names so the band aligns
        # with the existing scales without overriding their axes.
        x_field_user = mapping.get("x", "x")
        x_field = x_field_user if x_field_user in df.columns else "x"
        y_field_user = (
            mapping.get("y") if isinstance(mapping.get("y"), str) else None
        )
        y_field = y_field_user if y_field_user else "y"

        if self.x1 is not None and self.x2 is not None:
            x_type = _annotation_x_axis_type(df, x_field, mapping)
            band_df = pd.DataFrame({x_field: [self.x1], "_x2": [self.x2]})
            band = (
                alt.Chart(band_df)
                .mark_rect(color=self.color, opacity=self.opacity)
                .encode(
                    x=alt.X(x_field, type=x_type),
                    x2=alt.X2("_x2"),
                )
            )
            if not self.label:
                return band

            mid_x = self.x1
            try:
                if isinstance(self.x1, (int, float)) and isinstance(self.x2, (int, float)):
                    mid_x = (self.x1 + self.x2) / 2
            except Exception:  # noqa: BLE001
                mid_x = self.x1
            label_df = pd.DataFrame({x_field: [mid_x]})
            label_color = self.label_color or "#666666"
            halo_layer = (
                alt.Chart(label_df)
                .mark_text(
                    fontSize=9,
                    stroke="#FFFFFF",
                    strokeWidth=4.0,
                    strokeJoin="round",
                    strokeOpacity=1.0,
                    color="#FFFFFF",
                    dy=-10,
                )
                .encode(
                    x=alt.X(x_field, type=x_type),
                    text=alt.value(self.label),
                )
            )
            text = (
                alt.Chart(label_df)
                .mark_text(
                    fontSize=9,
                    color=label_color,
                    dy=-10,
                )
                .encode(
                    x=alt.X(x_field, type=x_type),
                    text=alt.value(self.label),
                )
            )
            return band + halo_layer + text

        if self.y1 is not None and self.y2 is not None:
            band_df = pd.DataFrame({y_field: [self.y1], "_y2": [self.y2]})
            band = (
                alt.Chart(band_df)
                .mark_rect(color=self.color, opacity=self.opacity)
                .encode(
                    y=alt.Y(f"{y_field}:Q"),
                    y2=alt.Y2("_y2:Q"),
                )
            )
            if not self.label:
                return band

            mid_y = (self.y1 + self.y2) / 2
            label_color = self.label_color or "#666666"

            # Class 3 absorption (mirrors HLine.to_layer): when
            # ``make_chart`` stashes a right-edge anchor x in
            # ``mapping`` (bar charts), route the band label to the
            # right side using ``align='right'``. Otherwise keep the
            # legacy default (no x encoding, label floats near
            # horizontal midpoint via Vega-Lite).
            anchor_x = mapping.get("_anno_label_anchor_right_x")
            x_field_user = (
                mapping.get("x") if isinstance(mapping.get("x"), str) else None
            )
            if (
                anchor_x is not None
                and x_field_user
                and x_field_user in df.columns
            ):
                label_df = pd.DataFrame(
                    {y_field: [mid_y], x_field_user: [anchor_x]}
                )
                x_type = _annotation_x_axis_type(df, x_field_user, mapping)
                label_align = "right"
                label_dx = -5
                label_x_enc = alt.X(x_field_user, type=x_type)
            else:
                label_df = pd.DataFrame({y_field: [mid_y]})
                label_align = "left"
                label_dx = 10
                label_x_enc = None

            text_encode_kwargs: Dict[str, Any] = {
                "y": alt.Y(f"{y_field}:Q"),
                "text": alt.value(self.label),
            }
            if label_x_enc is not None:
                text_encode_kwargs["x"] = label_x_enc

            halo_layer = (
                alt.Chart(label_df)
                .mark_text(
                    fontSize=9,
                    stroke="#FFFFFF",
                    strokeWidth=4.0,
                    strokeJoin="round",
                    strokeOpacity=1.0,
                    color="#FFFFFF",
                    align=label_align,
                    dx=label_dx,
                )
                .encode(**text_encode_kwargs)
            )
            text = (
                alt.Chart(label_df)
                .mark_text(
                    fontSize=9,
                    color=label_color,
                    align=label_align,
                    dx=label_dx,
                )
                .encode(**text_encode_kwargs)
            )
            return band + halo_layer + text

        raise ValueError("Band requires either (x1, x2) or (y1, y2)")


@dataclass
class PointLabel(Annotation):
    """Floating text label anchored to a single (x, y) data coordinate.

    Renders with a white halo behind the text so the label stays legible
    when it sits on top of a chart line or dense scatter cloud. Set
    ``halo=False`` to opt out (e.g. when placing labels in clearly empty
    space).

    On a dual-axis chart, ``axis='right'`` interprets ``y`` in
    right-axis units (default ``'left'``).
    """

    x: Any = None
    y: float = 0.0
    dx: int = 5
    dy: int = -10
    font_size: int = 10
    align: Literal["left", "center", "right"] = "left"
    halo: bool = True
    halo_color: str = "#FFFFFF"
    halo_width: float = 4.0
    axis: Literal["left", "right"] = "left"

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        if not self.label:
            return alt.Chart(pd.DataFrame({"_": []})).mark_point()

        x_col_user = mapping.get("x", "x")
        x_col = x_col_user if x_col_user in df.columns else "x"
        x_type = _annotation_x_axis_type(df, x_col, mapping)
        x_sort = _resolve_x_sort_for_annotation(df, mapping, x_col)
        y_field_user = (
            mapping.get("y") if isinstance(mapping.get("y"), str) else None
        )
        y_field = y_field_user if y_field_user else "y"
        label_df = pd.DataFrame({x_col: [self.x], y_field: [self.y]})
        x_kwargs: Dict[str, Any] = {"type": x_type}
        _apply_nominal_axis_sort(x_kwargs, df, x_col, x_sort)

        text_color = self.label_color or skin.get("primary_color", "#333333")
        layers: List[alt.Chart] = []

        if self.halo:
            halo_layer = (
                alt.Chart(label_df)
                .mark_text(
                    align=self.align,
                    dx=self.dx,
                    dy=self.dy,
                    fontSize=self.font_size,
                    stroke=self.halo_color,
                    strokeWidth=self.halo_width,
                    strokeJoin="round",
                    strokeOpacity=1.0,
                    color=self.halo_color,
                )
                .encode(
                    x=alt.X(x_col, **x_kwargs),
                    y=alt.Y(f"{y_field}:Q"),
                    text=alt.value(self.label),
                )
            )
            layers.append(halo_layer)

        text_layer = (
            alt.Chart(label_df)
            .mark_text(
                align=self.align,
                dx=self.dx,
                dy=self.dy,
                fontSize=self.font_size,
                color=text_color,
            )
            .encode(
                x=alt.X(x_col, **x_kwargs),
                y=alt.Y(f"{y_field}:Q"),
                text=alt.value(self.label),
            )
        )
        layers.append(text_layer)
        return alt.layer(*layers) if len(layers) > 1 else layers[0]


@dataclass
class Arrow(Annotation):
    """Straight-line arrow from (x1, y1) to (x2, y2) with optional label.

    The arrowhead is rendered as an Altair triangle ``mark_point`` rotated
    to a pixel-approximate angle (axes have different units, so rotation is
    computed in normalized [0, 1] space with an aspect-ratio correction).
    Curved arrows are deprecated and silently rendered straight.

    On a dual-axis chart, ``axis='right'`` interprets ``y1`` and ``y2``
    in right-axis units (default ``'left'``).
    """

    x1: Any = None
    y1: float = 0.0
    x2: Any = None
    y2: float = 0.0

    color: str = "#333333"
    stroke_width: float = 1.5
    stroke_dash: Optional[List[int]] = None
    curved: bool = False  # Deprecated: arrows always render straight.

    head_size: int = 8
    head_type: Literal["triangle", "none"] = "triangle"

    label_position: Literal["start", "middle", "end"] = "middle"
    label_offset_x: int = 5
    label_offset_y: int = -10

    axis: Literal["left", "right"] = "left"

    # Aliases.
    x_start: Optional[Any] = field(default=None, repr=False)
    x_end: Optional[Any] = field(default=None, repr=False)
    y_start: Optional[float] = field(default=None, repr=False)
    y_end: Optional[float] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.x1 is None and self.x_start is not None:
            self.x1 = self.x_start
        if self.x2 is None and self.x_end is not None:
            self.x2 = self.x_end
        if self.y1 == 0 and self.y_start is not None:
            self.y1 = self.y_start
        if self.y2 == 0 and self.y_end is not None:
            self.y2 = self.y_end

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        if self.curved:
            logger.warning(
                "[Arrow] curved=True is deprecated and ignored; rendering as straight arrow."
            )

        x_col_user = mapping.get("x", "x")
        x_col = x_col_user if x_col_user in df.columns else "x"
        x_type = _annotation_x_axis_type(df, x_col, mapping)
        y_field_user = (
            mapping.get("y") if isinstance(mapping.get("y"), str) else None
        )
        y_field = y_field_user if y_field_user else "y"

        line_df = pd.DataFrame(
            {x_col: [self.x1], y_field: [self.y1], "_x2": [self.x2], "_y2": [self.y2]}
        )
        mark_kwargs: Dict[str, Any] = {
            "color": self.color,
            "strokeWidth": self.stroke_width,
        }
        if self.stroke_dash:
            mark_kwargs["strokeDash"] = self.stroke_dash
        line = (
            alt.Chart(line_df)
            .mark_rule(**mark_kwargs)
            .encode(
                x=alt.X(x_col, type=x_type),
                y=alt.Y(f"{y_field}:Q"),
                x2=alt.X2("_x2"),
                y2=alt.Y2("_y2"),
            )
        )

        layers: List[alt.Chart] = [line]

        if self.head_type == "triangle":
            angle = self._compute_arrowhead_angle(df, x_col)
            head_df = pd.DataFrame({x_col: [self.x2], y_field: [self.y2]})
            head = (
                alt.Chart(head_df)
                .mark_point(
                    shape="triangle",
                    size=self.head_size * 15,
                    color=self.color,
                    filled=True,
                    opacity=1.0,
                    angle=angle,
                )
                .encode(
                    x=alt.X(x_col, type=x_type),
                    y=alt.Y(f"{y_field}:Q"),
                )
            )
            layers.append(head)

        if self.label:
            layers.append(self._label_layer(x_type, x_col, y_field))

        if len(layers) == 1:
            return layers[0]
        return alt.layer(*layers)

    # ---- helpers --------------------------------------------------------

    def _compute_arrowhead_angle(self, df: pd.DataFrame, x_col: str) -> float:
        """Approximate the arrowhead rotation in pixel space.

        x and y axes have different units (e.g. timestamps vs basis
        points), so a naive ``atan2(dy, dx)`` in data space is meaningless.
        Normalize both to [0, 1] of their visible extent, apply a default
        2:1 aspect-ratio correction (the 'wide' preset), then convert
        from math angle to Vega-Lite's clockwise-from-up convention.
        """
        x1n = _to_numeric_x(self.x1)
        x2n = _to_numeric_x(self.x2)

        if x_col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[x_col]):
                x_min = df[x_col].min().timestamp()
                x_max = df[x_col].max().timestamp()
            elif pd.api.types.is_numeric_dtype(df[x_col]):
                x_min = float(df[x_col].min())
                x_max = float(df[x_col].max())
            else:
                x_min, x_max = 0.0, 1.0
        else:
            x_min, x_max = 0.0, 1.0

        numeric_df = df.select_dtypes(include="number")
        if not numeric_df.empty:
            y_min = float(numeric_df.min().min())
            y_max = float(numeric_df.max().max())
        else:
            y_min, y_max = 0.0, 1.0

        x_range = (x_max - x_min) if x_max != x_min else 1.0
        y_range = (y_max - y_min) if y_max != y_min else 1.0

        dx_norm = (x2n - x1n) / x_range
        dy_norm = (self.y2 - self.y1) / y_range
        aspect_ratio = 2.0
        dx_pixel = dx_norm * aspect_ratio
        dy_pixel = dy_norm

        math_angle = float(np.degrees(np.arctan2(dy_pixel, dx_pixel)))
        return (90.0 - math_angle) % 360.0

    def _label_layer(self, x_type: str, x_col: str, y_field: str) -> alt.Chart:
        if self.label_position == "start":
            label_x, label_y = self.x1, self.y1
        elif self.label_position == "end":
            label_x, label_y = self.x2, self.y2
        else:  # middle
            if hasattr(self.x1, "timestamp") and hasattr(self.x2, "timestamp"):
                mid_ts = (self.x1.timestamp() + self.x2.timestamp()) / 2.0
                label_x = pd.Timestamp(mid_ts, unit="s")
            elif isinstance(self.x1, (int, float)) and isinstance(self.x2, (int, float)):
                label_x = (self.x1 + self.x2) / 2.0
            else:
                label_x = self.x1
            label_y = (self.y1 + self.y2) / 2.0

        label_df = pd.DataFrame({x_col: [label_x], y_field: [label_y]})
        return (
            alt.Chart(label_df)
            .mark_text(
                align="left",
                dx=self.label_offset_x,
                dy=self.label_offset_y,
                fontSize=10,
                color=self.label_color or self.color,
                fontWeight="bold",
            )
            .encode(
                x=alt.X(x_col, type=x_type),
                y=alt.Y(f"{y_field}:Q"),
                text=alt.value(self.label),
            )
        )


@dataclass
class Trendline(Annotation):
    """Regression trendline overlaid on a scatter chart."""

    method: Literal["linear", "exp", "log", "pow", "poly", "quad"] = "linear"
    color: str = "#888888"
    stroke_width: float = 1.5
    stroke_dash: List[int] = field(default_factory=lambda: [6, 3])

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        x_field = mapping["x"] if isinstance(mapping["x"], str) else mapping["x"]["field"]
        y_field = mapping["y"] if isinstance(mapping["y"], str) else mapping["y"]["field"]

        method = self.method
        order: Optional[int] = None
        if self.method == "quad":
            method = "poly"
            order = 2
        elif self.method == "poly":
            order = 3

        regression_kwargs: Dict[str, Any] = {"method": method}
        if order is not None:
            regression_kwargs["order"] = order

        trend = (
            alt.Chart(df)
            .transform_regression(x_field, y_field, **regression_kwargs)
            .mark_line(
                color=self.color,
                strokeWidth=self.stroke_width,
                strokeDash=self.stroke_dash,
            )
            .encode(
                x=alt.X(f"{x_field}:Q"),
                y=alt.Y(f"{y_field}:Q"),
            )
        )

        if not self.label:
            return trend

        trend_label = (
            alt.Chart(df.tail(1))
            .mark_text(
                align="left",
                dx=5,
                fontSize=9,
                color=self.label_color or self.color,
            )
            .encode(
                x=alt.X(f"{x_field}:Q"),
                y=alt.Y(f"{y_field}:Q"),
                text=alt.value(self.label),
            )
        )
        return trend + trend_label


@dataclass
class Segment(Annotation):
    """Finite line segment between (x1, y1) and (x2, y2).

    Unlike ``HLine`` / ``VLine`` (which span the full axis), ``Segment``
    draws a rule from a specific start point to a specific end point.
    Three common patterns:

    * **Horizontal segment** (``y1 == y2``): a windowed average / regime
      baseline only over the relevant window
      (e.g. ``"2015-2019 average = 2.0%"``). Cleaner than HLine when
      the baseline doesn't apply over the whole chart.
    * **Vertical segment** (``x1 == x2``): a finite event mark that
      doesn't intrude on the y-axis (e.g. a small spike at the bottom
      of the plot).
    * **Diagonal**: an ad-hoc connector between two specific points
      (peak-to-trough, mean-to-current, etc.). For an arrow with a
      head, use ``Arrow`` instead.

    Optional ``axis='right'`` routes the segment to the right axis on
    a dual-axis chart, mirroring ``HLine``'s behavior.
    """

    x1: Any = None
    x2: Any = None
    y1: float = 0.0
    y2: float = 0.0

    color: str = "#666666"
    stroke_width: float = 1.5
    stroke_dash: List[int] = field(default_factory=lambda: [4, 4])
    style: Optional[str] = None
    axis: Literal["left", "right"] = "left"

    label_position: Literal["start", "middle", "end"] = "end"
    label_offset_x: int = 5
    label_offset_y: int = -5

    x_start: Optional[Any] = field(default=None, repr=False)
    x_end: Optional[Any] = field(default=None, repr=False)
    y_start: Optional[float] = field(default=None, repr=False)
    y_end: Optional[float] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.style is not None and self.style in _LINE_STYLE_DASH:
            self.stroke_dash = list(_LINE_STYLE_DASH[self.style])
        if self.x1 is None and self.x_start is not None:
            self.x1 = self.x_start
        if self.x2 is None and self.x_end is not None:
            self.x2 = self.x_end
        if self.y1 == 0.0 and self.y_start is not None:
            self.y1 = self.y_start
        if self.y2 == 0.0 and self.y_end is not None:
            self.y2 = self.y_end

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        if self.x1 is None or self.x2 is None:
            raise ValueError("Segment requires x1 and x2")

        x_col_user = mapping.get("x", "x")
        x_col = x_col_user if x_col_user in df.columns else "x"
        x_type = _annotation_x_axis_type(df, x_col, mapping)
        x_sort = _resolve_x_sort_for_annotation(df, mapping, x_col)
        y_field_user = (
            mapping.get("y") if isinstance(mapping.get("y"), str) else None
        )
        y_field = y_field_user if y_field_user else "y"

        if x_type in ("nominal", "ordinal"):
            logger.warning(
                "[Segment] x-axis is categorical (nominal/ordinal, e.g. "
                "tenor strings or a low-cardinality numeric profile axis); "
                "ranged rules with x/x2 do not render reliably on band "
                "scales. Skipping Segment line; label (if any) will still "
                "render at the configured anchor point."
            )
            if not self.label:
                return alt.Chart(pd.DataFrame({"_": []})).mark_point()
            return self._label_layer(x_col, x_type, x_sort, y_field)

        line_df = pd.DataFrame(
            {x_col: [self.x1], y_field: [self.y1],
             "_x2": [self.x2], "_y2": [self.y2]}
        )

        x_kwargs: Dict[str, Any] = {"type": x_type}
        _apply_nominal_axis_sort(x_kwargs, df, x_col, x_sort)

        line = (
            alt.Chart(line_df)
            .mark_rule(
                color=self.color,
                strokeWidth=self.stroke_width,
                strokeDash=self.stroke_dash,
                clip=True,
            )
            .encode(
                x=alt.X(x_col, **x_kwargs),
                y=alt.Y(f"{y_field}:Q"),
                x2=alt.X2("_x2"),
                y2=alt.Y2("_y2"),
            )
        )

        if not self.label:
            return line

        layers: List[alt.Chart] = [line]
        layers.append(self._label_layer(x_col, x_type, x_sort, y_field))
        return alt.layer(*layers)

    def _label_layer(
        self,
        x_col: str,
        x_type: str,
        x_sort: Optional[List[Any]],
        y_field: str,
    ) -> alt.Chart:
        if self.label_position == "start":
            label_x, label_y = self.x1, self.y1
            align = "left"
        elif self.label_position == "middle":
            if hasattr(self.x1, "timestamp") and hasattr(self.x2, "timestamp"):
                mid_ts = (self.x1.timestamp() + self.x2.timestamp()) / 2.0
                label_x = pd.Timestamp(mid_ts, unit="s")
            elif isinstance(self.x1, (int, float)) and isinstance(self.x2, (int, float)):
                label_x = (self.x1 + self.x2) / 2.0
            else:
                label_x = self.x1
            label_y = (self.y1 + self.y2) / 2.0
            align = "center"
        else:
            label_x, label_y = self.x2, self.y2
            align = "left"

        label_df = pd.DataFrame({x_col: [label_x], y_field: [label_y]})
        x_kwargs: Dict[str, Any] = {"type": x_type}
        if x_sort is not None:
            x_kwargs["sort"] = x_sort
        return (
            alt.Chart(label_df)
            .mark_text(
                align=align,
                dx=self.label_offset_x,
                dy=self.label_offset_y,
                fontSize=10,
                color=self.label_color or self.color,
            )
            .encode(
                x=alt.X(x_col, **x_kwargs),
                y=alt.Y(f"{y_field}:Q"),
                text=alt.value(self.label),
            )
        )


@dataclass
class PointHighlight(Annotation):
    """Filled marker (circle by default) at a specific ``(x, y)`` point.

    Use to draw the eye to a specific data coordinate: the latest
    observation, a peak/trough, an outlier, an event location. Often
    combined with ``Callout`` or ``PointLabel`` for a "labeled marker"
    effect.

    Different from ``PointLabel`` -- ``PointLabel`` is a floating text
    annotation, ``PointHighlight`` is a visual marker. They compose.
    """

    x: Any = None
    y: float = 0.0

    color: str = "#C00000"
    size: int = 100
    opacity: float = 1.0
    shape: Literal[
        "circle", "square", "diamond", "triangle",
        "triangle-up", "triangle-down", "cross", "stroke",
    ] = "circle"
    filled: bool = True
    stroke_color: Optional[str] = None
    stroke_width: float = 0.0
    axis: Literal["left", "right"] = "left"

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        x_col_user = mapping.get("x", "x")
        x_col = x_col_user if x_col_user in df.columns else "x"
        x_type = _annotation_x_axis_type(df, x_col, mapping)
        x_sort = _resolve_x_sort_for_annotation(df, mapping, x_col)
        y_field_user = (
            mapping.get("y") if isinstance(mapping.get("y"), str) else None
        )
        y_field = y_field_user if y_field_user else "y"

        point_df = pd.DataFrame({x_col: [self.x], y_field: [self.y]})

        x_kwargs: Dict[str, Any] = {"type": x_type}
        _apply_nominal_axis_sort(x_kwargs, df, x_col, x_sort)

        mark_kwargs: Dict[str, Any] = {
            "shape": self.shape,
            "size": self.size,
            "color": self.color,
            "filled": self.filled,
            "opacity": self.opacity,
        }
        if self.stroke_color is not None:
            mark_kwargs["stroke"] = self.stroke_color
        if self.stroke_width > 0.0:
            mark_kwargs["strokeWidth"] = self.stroke_width

        layer = (
            alt.Chart(point_df)
            .mark_point(**mark_kwargs)
            .encode(
                x=alt.X(x_col, **x_kwargs),
                y=alt.Y(f"{y_field}:Q"),
            )
        )

        if not self.label:
            return layer

        text = (
            alt.Chart(point_df)
            .mark_text(
                align="left",
                dx=8,
                dy=-10,
                fontSize=10,
                fontWeight="bold",
                color=self.label_color or self.color,
            )
            .encode(
                x=alt.X(x_col, **x_kwargs),
                y=alt.Y(f"{y_field}:Q"),
                text=alt.value(self.label),
            )
        )
        return layer + text


@dataclass
class Callout(Annotation):
    """Text annotation with a halo or filled box behind it for legibility.

    ``PointLabel`` text can disappear against axis ticks or dense data.
    ``Callout`` solves that with one of two backgrounds:

    * ``background='halo'`` (default): a thicker, lighter-colored copy
      of the text rendered behind the foreground text -- the
      stroke-outline trick. No box, just a clean halo. Best for most
      cases.
    * ``background='box'``: a filled rectangle behind the text. Use
      when the halo trick doesn't pop enough (e.g. very busy chart).
    * ``background='none'``: behaves like ``PointLabel``.
    """

    x: Any = None
    y: float = 0.0

    background: Literal["halo", "box", "none"] = "halo"
    background_color: str = "#FFFFFF"
    halo_width: float = 4.0
    box_padding_x: int = 6
    box_padding_y: int = 4
    box_opacity: float = 0.85
    box_corner_radius: int = 2
    # Border around the filled box. A subtle ~1px gray stroke is the
    # default so a white-fill box stays visible against the chart's
    # white plot area (otherwise ``background_color="#FFFFFF"`` renders
    # invisibly). Pass ``box_stroke=None`` to disable.
    box_stroke: Optional[str] = "#999999"
    box_stroke_width: float = 1.0

    color: str = "#333333"
    dx: int = 8
    dy: int = -10
    font_size: int = 10
    font_weight: Literal["normal", "bold"] = "normal"
    align: Literal["left", "center", "right"] = "left"
    axis: Literal["left", "right"] = "left"

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        if not self.label:
            return alt.Chart(pd.DataFrame({"_": []})).mark_point()

        # Class 9 absorption (per dev/scratch/_collision_audit_*/inventory.md):
        # clamp dx so the label stays inside the plot frame. Without this a
        # caller passing dx=200 would render the label far off-canvas (D4
        # of demo 21 was the canonical repro). The published 0-60 range
        # is the safe-default cited in chart_context.md; cap absolute dx
        # at 80 (the existing warning threshold) for chart widths >= 600
        # and tighter for smaller charts. Smaller charts (compact /
        # thumbnail) can't afford the same offset because the plot region
        # itself is narrower.
        chart_width_px = int(mapping.get("_chart_width_px") or 700)
        if chart_width_px >= 800:
            max_dx = 90
        elif chart_width_px >= 500:
            max_dx = 80
        elif chart_width_px >= 350:
            max_dx = 60
        else:
            max_dx = 40
        if abs(self.dx) > max_dx:
            clamped_dx = max_dx if self.dx > 0 else -max_dx
            logger.warning(
                "[Callout] dx=%d clamped to %d (max=+/-%d for %dpx chart "
                "width). Reduce dx or place the Callout further from the "
                "edge to avoid losing the offset.",
                self.dx, clamped_dx, max_dx, chart_width_px,
            )
            self.dx = clamped_dx  # mutate so downstream layers see the clamp

        x_col_user = mapping.get("x", "x")
        x_col = x_col_user if x_col_user in df.columns else "x"
        x_type = _annotation_x_axis_type(df, x_col, mapping)
        x_sort = _resolve_x_sort_for_annotation(df, mapping, x_col)
        y_field_user = (
            mapping.get("y") if isinstance(mapping.get("y"), str) else None
        )
        y_field = y_field_user if y_field_user else "y"
        label_df = pd.DataFrame({x_col: [self.x], y_field: [self.y]})

        x_kwargs: Dict[str, Any] = {"type": x_type}
        _apply_nominal_axis_sort(x_kwargs, df, x_col, x_sort)

        # Resolve the y-axis type the same way x is resolved so a Callout
        # at a string y (e.g. heatmap with sector labels on the y-axis)
        # encodes against the right scale instead of force-quantitative
        # which would render the callout off the chart.
        y_type = (
            _resolve_axis_type(df, y_field) if y_field in df.columns else "quantitative"
        )
        y_kwargs: Dict[str, Any] = {"type": y_type}
        explicit_y_sort = (
            list(mapping.get("y_sort")) if mapping.get("y_sort") else None
        )
        _apply_nominal_axis_sort(y_kwargs, df, y_field, explicit_y_sort)

        text_color = self.label_color or self.color

        # Wrap any label longer than a sane budget. Without this, a
        # 200-char Callout renders as a single string that stretches the
        # chart canvas off-screen (Vega-Lite has no auto-wrap on
        # mark_text and grows the parent layout to fit). Use a 60-char
        # / ~330px budget for halo / none, slightly tighter for box
        # because the box draws padding on both sides.
        wrap_budget_px = 280 if self.background == "box" else 330
        wrapped_label = _wrap_text_to_width(
            self.label, wrap_budget_px, self.font_size,
        )

        layers: List[alt.Chart] = []

        if self.background == "halo":
            halo_layer = (
                alt.Chart(label_df)
                .mark_text(
                    align=self.align,
                    baseline="middle",
                    dx=self.dx,
                    dy=self.dy,
                    fontSize=self.font_size,
                    fontWeight=self.font_weight,
                    stroke=self.background_color,
                    strokeWidth=self.halo_width,
                    strokeJoin="round",
                    strokeOpacity=1.0,
                    color=self.background_color,
                    lineBreak="\n",
                )
                .encode(
                    x=alt.X(x_col, **x_kwargs),
                    y=alt.Y(y_field, **y_kwargs),
                    text=alt.value(wrapped_label),
                )
            )
            layers.append(halo_layer)
        elif self.background == "box":
            char_width_px = max(1, int(round(self.font_size * 0.55)))
            wrapped_lines = wrapped_label.split("\n")
            longest_line_len = max((len(ln) for ln in wrapped_lines), default=0)
            text_width_px = (
                char_width_px * longest_line_len + 2 * self.box_padding_x
            )
            text_height_px = (
                self.font_size * len(wrapped_lines) + 2 * self.box_padding_y
            )
            rect_kwargs: Dict[str, Any] = dict(
                color=self.background_color,
                opacity=self.box_opacity,
                cornerRadius=self.box_corner_radius,
                width=text_width_px,
                height=text_height_px,
                align=self.align,
                baseline="middle",
                xOffset=self.dx - self.box_padding_x
                if self.align == "left"
                else (
                    self.dx
                    if self.align == "center"
                    else self.dx + self.box_padding_x
                ),
                yOffset=self.dy,
            )
            if self.box_stroke is not None:
                rect_kwargs["stroke"] = self.box_stroke
                rect_kwargs["strokeWidth"] = self.box_stroke_width
                rect_kwargs["strokeOpacity"] = 1.0
            box = (
                alt.Chart(label_df)
                .mark_rect(**rect_kwargs)
                .encode(
                    x=alt.X(x_col, **x_kwargs),
                    y=alt.Y(y_field, **y_kwargs),
                )
            )
            layers.append(box)

        text_layer = (
            alt.Chart(label_df)
            .mark_text(
                align=self.align,
                baseline="middle",
                dx=self.dx,
                dy=self.dy,
                fontSize=self.font_size,
                fontWeight=self.font_weight,
                color=text_color,
                lineBreak="\n",
            )
            .encode(
                x=alt.X(x_col, **x_kwargs),
                y=alt.Y(y_field, **y_kwargs),
                text=alt.value(wrapped_label),
            )
        )
        layers.append(text_layer)

        if len(layers) == 1:
            return layers[0]
        return alt.layer(*layers)


@dataclass
class LastValueLabel(Annotation):
    """Direct end-of-line labeling for ``multi_line`` charts.

    Replaces the legend with text labels at the right-hand edge of each
    series, in that series' own color (FT/Bloomberg house style).
    Removes the "which line is which?" lookup tax.

    Behavior:

    * On a ``multi_line`` chart with a ``color`` column, each series
      gets a text label at its last data point (the row with ``max(x)``
      for that series), drawn in the line's hex.
    * On a single-series ``multi_line`` (no color column, ``y`` is a
      single string), one label is drawn at the line's end.
    * On a wide-format chart auto-melted into long format, each
      original column appears as its own labeled series.
    * On a dual-axis chart, ``LastValueLabel`` is suppressed (the
      annotation is dropped with a non-fatal warning and the normal
      color legend renders instead). For end-of-line labels alongside
      two y-scales, build a single-axis chart per series and combine
      via ``make_2pack_vertical()``.

    Labels are the series identity only -- the numeric value is not
    rendered. The ``label`` field on the base ``Annotation`` is ignored
    on multi-series; on single-series it overrides the y-field name.

    Text-only: there is no endpoint dot. The line itself extending into
    the label margin plays that anchoring role.
    """

    dx: int = 6
    font_size: int = 15
    font_weight: Literal["normal", "bold"] = "normal"
    include_right_axis: bool = False
    """Obsolete since 2026-05-05 -- LastValueLabel is now stripped on
    dual-axis charts in ``make_chart`` before ``to_layer`` runs. Field
    retained so existing call sites remain valid (pass-through is a
    no-op on dual-axis; on single-axis the kwarg has never had any
    effect). Will be removed in a future release."""

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        x_col_user = mapping.get("x", "x")
        x_col = x_col_user if x_col_user in df.columns else "x"
        if x_col not in df.columns:
            logger.warning(
                "[LastValueLabel] x column '%s' not in DataFrame; skipping.",
                x_col,
            )
            return alt.Chart(pd.DataFrame({"_": []})).mark_point()

        x_type = _annotation_x_axis_type(df, x_col, mapping)
        x_sort = _resolve_x_sort_for_annotation(df, mapping, x_col)

        y_field_user = mapping.get("y") if isinstance(mapping.get("y"), str) else None
        y_field = y_field_user if y_field_user else "y"

        color_field = mapping.get("color")
        dual_axis_series = list(mapping.get("dual_axis_series") or [])
        is_dual_axis = bool(dual_axis_series)

        # Defensive backstop: ``make_chart`` strips LastValueLabel on
        # dual-axis BEFORE annotation rendering runs (see the
        # "LastValueLabel on dual-axis: prohibited" block in
        # ``make_chart``), so this branch should never execute. If it
        # does, something has bypassed the strip -- log loudly and
        # skip rendering rather than producing a misshapen layer.
        if is_dual_axis:
            logger.error(
                "[LastValueLabel] reached to_layer on a dual-axis chart "
                "-- the make_chart-level strip should have removed this "
                "annotation. Skipping render."
            )
            return alt.Chart(pd.DataFrame({"_": []})).mark_point()

        if (
            not (color_field and color_field in df.columns)
            and y_field in df.columns
        ):
            return self._build_single_series_layer(
                df, x_col, x_type, x_sort, y_field,
                mapping=mapping, skin=skin,
            )

        if not (color_field and color_field in df.columns):
            logger.warning(
                "[LastValueLabel] no color column and no string y; skipping."
            )
            return alt.Chart(pd.DataFrame({"_": []})).mark_point()

        df_use = df.copy()

        df_clean = df_use.dropna(subset=[x_col, y_field]).reset_index(drop=True)
        if df_clean.empty:
            return alt.Chart(pd.DataFrame({"_": []})).mark_point()

        last_rows = _last_row_at_max_x(df_clean, x_col, color_field)

        # Series names are pre-validated by ``_validate_lvl_series_names``
        # so no per-label truncation is needed -- whatever is in the color
        # column is guaranteed to pass ``_validate_lvl_series_names``.
        last_rows["_label"] = last_rows[color_field].astype(str)

        x_kwargs: Dict[str, Any] = {"type": x_type}
        _apply_nominal_axis_sort(x_kwargs, df, x_col, x_sort)

        # Per-row precomputed label colors. Source palette is
        # ``skin['label_color_scheme']`` (falling back to
        # ``skin['color_scheme']`` then GS_CLEAN's color_scheme so
        # custom skins without a label palette keep today's
        # match-line-exactly behaviour). For GS_CLEAN the label
        # palette is GS_PRIMARY's ``label_colors``: identical to the
        # line palette for the dark slots (navy / red / cobalt /
        # purple / orange / teal) and a darker HSL-derived hex
        # (L * 0.55, hue/sat preserved) for the readability-weak
        # slots (light blue / mid blue / grey / olive). Vega-Lite
        # defaults to ``shared`` color-scale resolution across
        # layers, so any ``alt.Scale`` declared on the LVL inner
        # layer is silently overridden by the base line chart's
        # palette. ``resolve_scale(color='independent')`` would also
        # break legitimate shared-color encodings on other
        # annotation types (Trendline, etc.). Instead, materialize
        # the literal label hex per row and encode with
        # ``scale=None`` so Vega-Lite uses the hex values directly
        # and bypasses scale merging entirely. Slot index follows
        # the sorted-unique convention Vega-Lite applies by default
        # to nominal color domains, so the LVL slot-to-series
        # mapping matches the line layer's mapping one-to-one.
        scheme = skin.get(
            "label_color_scheme",
            skin.get("color_scheme", GS_CLEAN["color_scheme"]),
        )
        unique_series = sorted(last_rows[color_field].astype(str).unique())
        series_to_color: Dict[str, str] = {
            s: scheme[i % len(scheme)]
            for i, s in enumerate(unique_series)
        }
        last_rows["_label_color"] = (
            last_rows[color_field].astype(str).map(series_to_color)
        )

        # Route each series to the correct axis. On a dual-axis chart the
        # layered chart resolves y as ``independent``; LVL emits one
        # sublayer per side, each pinned to its own y-domain (right side
        # may be inverted via ``y_domain_right=[max, min]``). Without
        # this split, right-axis values get plotted on the left scale's
        # domain and land far outside the visible plot area.
        dual_cfg = mapping.get("dual_axis_config") or {}

        if is_dual_axis:
            is_right_series = (
                last_rows[color_field].astype(str).isin(dual_axis_series)
            )
            side_groups: List[Tuple[str, pd.DataFrame, Optional[List[float]]]] = [
                ("left", last_rows[~is_right_series].copy(),
                 dual_cfg.get("y_domain_left")),
                ("right", last_rows[is_right_series].copy(),
                 dual_cfg.get("y_domain_right")),
            ]
        else:
            side_groups = [("left", last_rows, None)]

        # Actual plot-region pixel height for this chart. ``mapping`` is
        # the per-render copy that ``render_annotations`` populates with
        # ``_chart_height_px`` before dispatching to ``to_layer``. Falls
        # back to the ``wide`` preset (350 px) so existing standalone
        # callers that bypass ``render_annotations`` (none in production
        # today; ``make_chart`` always routes through it) still work.
        chart_height_px = int(
            mapping.get("_chart_height_px") or 350  # type: ignore[arg-type]
        )

        layers: List[alt.Chart] = []

        for side_name, rows, y_scale_domain in side_groups:
            if rows.empty:
                continue

            # The y-domain that ``_stagger_lvl_text_y`` uses to convert
            # data->pixels MUST match the chart's actual y-axis domain.
            # Pre-2026-05-10 the algorithm built this domain from the
            # per-series END VALUES only, which on a chart where lines
            # bunch at the end becomes a tiny interval (e.g. 99.9 ..
            # 100.0). The pixel<->data conversion then thought 0.1 pts
            # of y was huge -- so the staggering decided no overlap
            # existed and labels piled on top of each other. Fix: use
            # the full chart's y-axis domain.
            if y_scale_domain is not None:
                # Dual-axis path (dead branch today; LVL is stripped on
                # dual-axis upstream). Honour the explicit per-side
                # domain so the math is correct if this path is ever
                # reached.
                raw = list(y_scale_domain)
                y_axis_domain: Tuple[float, float] = (min(raw), max(raw))
            else:
                # Single-axis path: derive the same domain
                # ``_build_timeseries`` uses for the rendered y-axis.
                y_axis_domain = calculate_y_axis_domain(
                    df_clean[y_field],
                    handle_outliers=False,
                    prevent_zero_start=True,
                )

            rows = _stagger_lvl_text_y(
                rows.reset_index(drop=True),
                y_field=y_field,
                label_col="_label",
                font_size=self.font_size,
                y_domain=y_axis_domain,
                chart_height_px=chart_height_px,
            )

            # Per-side y-encoding: pin to this side's domain (potentially
            # inverted) and suppress the layer's own axis decorations so
            # only the base chart's axes remain visible.
            y_kwargs: Dict[str, Any] = {}
            if y_scale_domain is not None:
                y_kwargs["scale"] = alt.Scale(domain=list(y_scale_domain))
                y_kwargs["axis"] = alt.Axis(
                    orient=("right" if side_name == "right" else "left"),
                    title=None, labels=False, ticks=False, domain=False,
                )

            text_chart = (
                alt.Chart(rows)
                .mark_text(
                    align="left",
                    baseline="middle",
                    dx=self.dx,
                    dy=0,
                    fontSize=self.font_size,
                    fontWeight=self.font_weight,
                )
                .encode(
                    x=alt.X(x_col, **x_kwargs),
                    y=alt.Y("_y_text:Q", **y_kwargs),
                    text=alt.Text("_label:N"),
                    color=(
                        alt.value(self.label_color)
                        if self.label_color
                        else alt.Color(
                            "_label_color:N", scale=None, legend=None,
                        )
                    ),
                )
            )
            layers.append(text_chart)

        if not layers:
            return alt.Chart(pd.DataFrame({"_": []})).mark_point()
        if len(layers) == 1:
            return layers[0]
        return alt.layer(*layers)

    def _build_single_series_layer(
        self,
        df: pd.DataFrame,
        x_col: str,
        x_type: str,
        x_sort: Optional[List[Any]],
        y_field: str,
        mapping: Optional[Dict[str, Any]] = None,
        skin: Optional[Dict[str, Any]] = None,
    ) -> alt.Chart:
        df_clean = df.dropna(subset=[x_col, y_field]).reset_index(drop=True)
        if df_clean.empty:
            return alt.Chart(pd.DataFrame({"_": []})).mark_point()
        last_row = _last_row_at_max_x(df_clean, x_col).iloc[0]
        last_x = last_row[x_col]
        last_y = float(last_row[y_field])

        # Prefer an explicit mapping['y_title'] over the raw column name
        # so a single-series LVL doesn't leak something like "cpi_yoy_pct".
        # If neither label nor y_title is given, fall back to a humanized
        # version of y_field (snake_case -> Title Case) instead of raw.
        mapping = mapping or {}
        y_title = mapping.get("y_title") if isinstance(mapping, dict) else None
        if self.label:
            label_root = self.label
        elif y_title and isinstance(y_title, str):
            label_root = y_title
        else:
            label_root = y_field.replace("_", " ").strip().title()

        # Series name pre-validated by ``_validate_lvl_series_names``;
        # no truncation needed here.
        label_text = label_root

        end_df = pd.DataFrame({x_col: [last_x], y_field: [last_y]})

        x_kwargs: Dict[str, Any] = {"type": x_type}
        if x_sort is not None:
            x_kwargs["sort"] = x_sort

        layers: List[alt.Chart] = []
        # Default to the same color the single-series line itself renders
        # in (skin.primary_color), so the LVL label and the line share
        # the same hex by construction. Explicit ``label_color`` on the
        # annotation still wins.
        line_color = (
            skin.get("primary_color", "#003359") if skin else "#003359"
        )
        color = self.label_color or line_color

        text_chart = (
            alt.Chart(end_df)
            .mark_text(
                align="left",
                baseline="middle",
                dx=self.dx,
                dy=0,
                fontSize=self.font_size,
                fontWeight=self.font_weight,
                color=color,
            )
            .encode(
                x=alt.X(x_col, **x_kwargs),
                y=alt.Y(f"{y_field}:Q"),
                text=alt.value(label_text),
            )
        )
        layers.append(text_chart)

        if len(layers) == 1:
            return layers[0]
        return alt.layer(*layers)


# PlotText panel-slot priority for ``position='auto'``. Right wins
# first because narrative panels conventionally sit on the right
# (FT / Bloomberg side-rail style) and a side panel preserves the
# chart's vertical real estate; bottom takes second priority (caption
# slot) because it doesn't compete with legends; left takes third
# (less common but supported when both right + bottom are taken).
_PLOTTEXT_AUTO_PRIORITY: List[str] = ["right", "bottom", "left"]

# Valid ``PlotText.position`` values after the 2026-05-10 outside-only
# rewire. Inside-corner anchors (top-* / middle-* / bottom-* with
# left|center|right suffix) and the bare ``"top"`` value are no
# longer supported -- PlotText now renders OUTSIDE the plot region
# only, routed through the existing text-panel system
# (``caption`` / ``side_left`` / ``side_right`` on ``make_chart`` /
# ``ChartSpec``).
_PLOTTEXT_VALID_POSITIONS: frozenset = frozenset({
    "auto", "left", "right", "bottom",
})

_PLOTTEXT_LEGACY_POSITIONS: frozenset = frozenset({
    "top", "top-left", "top-center", "top-right",
    "middle-left", "middle-center", "middle-right",
    "bottom-left", "bottom-center", "bottom-right",
})

# Hard word cap on ``PlotText.text``. Engine raises above this; the
# skill (``chart_context.md`` §8.3) advertises a tighter SOFT limit
# of 8 words so PRISM has a 2-word safety buffer before the engine
# refuses to render. The intent is "one-line takeaway", not "full
# sentence" -- a side panel that wraps to 6+ lines crowds the chart
# and undermines the visual hierarchy.
PLOTTEXT_HARD_WORD_CAP: int = 10
PLOTTEXT_SOFT_WORD_CAP: int = 8


def _validate_plottext_position(pos: str) -> None:
    """Raise a clear ``ValidationError`` for legacy inside-anchor positions.

    PlotText was repositioned (2026-05-10) from inside-the-plot corner
    anchors to outside-the-plot panels. The four valid values are
    ``"auto"`` (default; first free side, right-first priority),
    ``"left"``, ``"right"``, and ``"bottom"`` -- each maps to the
    existing text-panel system (``side_left`` / ``side_right`` /
    ``caption``).
    """
    if pos in _PLOTTEXT_VALID_POSITIONS:
        return
    if pos in _PLOTTEXT_LEGACY_POSITIONS:
        raise ValidationError(
            f"PlotText.position={pos!r} is no longer supported. "
            "PlotText now renders OUTSIDE the plot region only; the "
            "9 inside-corner anchors (top-*/middle-*/bottom-*) and "
            "the bare 'top' value were removed in the 2026-05-10 "
            "outside-only rewire so narrative text can never collide "
            "with bars / lines / data labels. Valid positions: "
            f"{sorted(_PLOTTEXT_VALID_POSITIONS)}. Migration: any "
            "top-* / middle-* -> use 'right' (default) for a side "
            "panel; bottom-* -> use 'bottom' for a caption."
        )
    raise ValidationError(
        f"PlotText.position={pos!r} is not a recognised value. "
        f"Valid: {sorted(_PLOTTEXT_VALID_POSITIONS)}."
    )


def _count_words(text: str) -> int:
    """Whitespace-split word count (no punctuation stripping)."""
    if not text:
        return 0
    return len([w for w in text.split() if w.strip()])


def _validate_plottext_text(text: str) -> None:
    """Raise ``ValidationError`` when ``PlotText.text`` exceeds the engine
    hard word cap (``PLOTTEXT_HARD_WORD_CAP``).

    The skill (``chart_context.md`` §8.3) advertises a tighter soft
    cap (``PLOTTEXT_SOFT_WORD_CAP``) so PRISM has a 2-word buffer.
    Anything past the hard cap raises with a message naming both
    limits so the LLM can fix the call site without guessing.
    """
    if not text:
        return
    n_words = _count_words(text)
    if n_words > PLOTTEXT_HARD_WORD_CAP:
        raise ValidationError(
            f"PlotText.text has {n_words} words; engine hard cap "
            f"is {PLOTTEXT_HARD_WORD_CAP} words. The skill "
            f"(chart_context.md §8.3) recommends a "
            f"{PLOTTEXT_SOFT_WORD_CAP}-word SOFT limit so the "
            f"narrative panel stays one-line tight and doesn't crowd "
            f"the chart. Tighten the takeaway -- PlotText is for "
            f"a single insight, not a full sentence. If you need "
            f"more, route via "
            f"`make_chart(caption=..., side_right=..., side_left=...)` "
            f"directly (those kwargs have no word cap). Got: {text!r}"
        )


@dataclass
class PlotText(Annotation):
    """Free-form narrative text rendered OUTSIDE the plot region.

    PlotText panels are routed through the existing text-panel system
    (``side_left`` / ``side_right`` / ``caption``) and live to the
    side or below the chart -- they never sit inside the plot area.
    Because the panel is OUTSIDE the plot box by construction,
    PlotText cannot collide with bars, lines, axis labels, or data
    annotations.

    Position enum maps to slot:

    | position    | resolves to                                        |
    |-------------|----------------------------------------------------|
    | ``"right"`` | ``side_right``  (auto-fit width, default)          |
    | ``"left"``  | ``side_left``   (auto-fit width)                   |
    | ``"bottom"``| ``caption``     (full chart width, below)          |
    | ``"auto"``  | first free slot in priority right -> bottom -> left |

    Conflicts: an explicit ``make_chart(side_right=..., side_left=..., 
    caption=...)`` kwarg always wins. A PlotText that targets the
    same slot is rerouted to the next available position with a
    warning. If all 3 slots are occupied, the PlotText is dropped
    with a warning.

    Word cap: ``text`` MUST be at most ``PLOTTEXT_HARD_WORD_CAP``
    words (currently 10). Past that the engine raises
    ``ValidationError`` at construction. The skill
    (``chart_context.md`` §8.3) advertises a tighter SOFT limit of
    ``PLOTTEXT_SOFT_WORD_CAP`` words (currently 8) so PRISM has a
    2-word safety buffer. The intent is "one-line takeaway", not
    "full sentence" -- for longer narratives use the
    ``make_chart(caption=..., side_right=..., side_left=...)`` kwargs
    directly (they have no word cap).

    The 2026-05-10 rewire removed the 9 inside-corner anchors that
    PlotText used to support (``top-*`` / ``middle-*`` / ``bottom-*``).
    Passing any legacy position raises a ``ValidationError`` with a
    migration hint.

    The base ``label`` / ``label_color`` fields are unused -- the
    payload is in ``text`` and the colour is in ``color``.
    """

    text: str = ""
    position: Literal["auto", "left", "right", "bottom"] = "auto"
    # Defaults mirror ``_TEXT_PANEL_DEFAULTS`` so a bare
    # ``PlotText(text="...")`` produces the same visual as a bare
    # ``make_chart(side_right="...")``. See the readability tuning
    # block on _TEXT_PANEL_DEFAULTS for the rationale on the 12 / #555
    # values.
    font_size: int = 12
    color: str = "#555555"
    italic: bool = False
    align: Optional[Literal["left", "center", "right"]] = None
    width_pct: Optional[float] = None

    def __post_init__(self) -> None:
        # Validate eagerly so legacy position values + over-cap text
        # raise at construction time rather than at render time.
        # Catches the canonical migration mistake
        # (``position='top-right'``) and the canonical word-budget
        # violation (paragraph-length ``text``) before the
        # annotations list is even passed to make_chart.
        _validate_plottext_position(self.position)
        _validate_plottext_text(self.text)

    def to_layer(
        self,
        base: alt.Chart,
        df: pd.DataFrame,
        mapping: Dict[str, Any],
        skin: Dict[str, Any],
    ) -> alt.Chart:
        # Defensive: PlotText is routed to side panels via
        # ``_route_plottext_to_panels`` BEFORE ``render_annotations``
        # runs, so this method should never be reached. If it is, the
        # routing helper was bypassed -- raise so the caller sees it.
        raise RuntimeError(
            "PlotText.to_layer() should never be called; PlotText is "
            "routed to outside text panels via "
            "_route_plottext_to_panels before the annotation layer "
            "pass. If you see this, the routing helper was bypassed."
        )


# ---------------------------------------------------------------------------
# PlotText -> outside-panel routing
# ---------------------------------------------------------------------------

# Map a PlotText.position value to the text-panel slot key used by
# _apply_text_panels_to_spec / _wrap_with_text_panels. Slots are
# left/right/caption (no top slot exists in the panel system today).
_PLOTTEXT_POSITION_TO_SLOT: Dict[str, str] = {
    "right": "right",
    "left": "left",
    "bottom": "caption",
}


def _route_plottext_to_panels(
    annotations: Optional[List["Annotation"]],
    *,
    explicit_caption: Union[str, Dict[str, Any], None],
    explicit_side_left: Union[str, Dict[str, Any], None],
    explicit_side_right: Union[str, Dict[str, Any], None],
) -> Tuple[
    List["Annotation"],
    Union[str, Dict[str, Any], None],
    Union[str, Dict[str, Any], None],
    Union[str, Dict[str, Any], None],
    List[str],
]:
    """Pull ``PlotText`` annotations out of the annotation list and
    route them to the existing outside-the-plot text-panel system.

    Returns a 5-tuple:
      ``(filtered_annotations, caption, side_left, side_right, warnings)``

    The filtered annotation list has every ``PlotText`` removed.
    ``caption`` / ``side_left`` / ``side_right`` reflect any explicit
    kwargs passed in PLUS any new panels routed in from PlotText
    instances. ``warnings`` is a list of human-readable warning strings
    that the caller should append to its ``result.warnings`` so PRISM
    sees the routing decisions.

    Resolution rules (per the 2026-05-10 design decision):

    * Explicit kwargs always win. A ``PlotText(position='right')``
      whose target slot is already filled by ``side_right=`` is
      rerouted to the next available slot in priority order
      (right -> bottom -> left).
    * ``position='auto'`` resolves to the first free slot in the same
      priority order.
    * If all 3 slots are occupied (by explicit kwargs and earlier
      routed PlotTexts), the PlotText is dropped silently except for
      a warning surfaced to the caller.
    * Empty-text PlotTexts are dropped silently (no warning).
    """
    if not annotations:
        return (
            list(annotations) if annotations else [],
            explicit_caption, explicit_side_left, explicit_side_right,
            [],
        )

    keep: List[Annotation] = []
    plottexts: List[PlotText] = []
    for a in annotations:
        if isinstance(a, PlotText):
            plottexts.append(a)
        else:
            keep.append(a)

    if not plottexts:
        return (
            keep, explicit_caption, explicit_side_left,
            explicit_side_right, [],
        )

    slot_to_value: Dict[str, Any] = {
        "caption": explicit_caption,
        "left": explicit_side_left,
        "right": explicit_side_right,
    }
    slot_source: Dict[str, str] = {}
    if explicit_caption is not None:
        slot_source["caption"] = "make_chart(caption=...) kwarg"
    if explicit_side_left is not None:
        slot_source["left"] = "make_chart(side_left=...) kwarg"
    if explicit_side_right is not None:
        slot_source["right"] = "make_chart(side_right=...) kwarg"

    warnings_out: List[str] = []

    def _build_cfg_from_plottext(pt: PlotText) -> Dict[str, Any]:
        cfg = dict(_TEXT_PANEL_DEFAULTS)
        cfg["text"] = pt.text
        cfg["font_size"] = int(pt.font_size)
        cfg["color"] = pt.color
        cfg["italic"] = bool(pt.italic)
        if pt.align is not None:
            cfg["align"] = pt.align
        if pt.width_pct is not None:
            cfg["width_pct"] = pt.width_pct
        return cfg

    for pt in plottexts:
        if not pt.text or not pt.text.strip():
            continue

        if pt.position == "auto":
            try_order = list(_PLOTTEXT_AUTO_PRIORITY)
        else:
            # Explicit position; try requested first, then walk the
            # priority order skipping the requested slot for the
            # conflict-fallback path.
            try_order = [pt.position] + [
                p for p in _PLOTTEXT_AUTO_PRIORITY if p != pt.position
            ]

        landed: Optional[str] = None
        for pos in try_order:
            slot = _PLOTTEXT_POSITION_TO_SLOT[pos]
            if slot_to_value[slot] is None:
                cfg = _build_cfg_from_plottext(pt)
                slot_to_value[slot] = cfg
                preview = pt.text[:30].replace("\n", " ")
                if len(pt.text) > 30:
                    preview = preview + "..."
                slot_source[slot] = (
                    f"PlotText(position={pos!r}, text={preview!r})"
                )
                if pt.position not in {"auto", pos}:
                    occupant = slot_source.get(
                        _PLOTTEXT_POSITION_TO_SLOT[pt.position],
                        "another caller",
                    )
                    warnings_out.append(
                        f"[PlotText] requested position="
                        f"{pt.position!r} already taken by {occupant}; "
                        f"rerouted to position={pos!r}."
                    )
                landed = pos
                break

        if landed is None:
            preview = pt.text[:50].replace("\n", " ")
            if len(pt.text) > 50:
                preview = preview + "..."
            warnings_out.append(
                f"[PlotText] all 3 panel slots (right/bottom/left) "
                f"occupied; dropped PlotText(text={preview!r}). "
                "Slot occupants: " + ", ".join(
                    f"{k}={v}" for k, v in sorted(slot_source.items())
                )
            )

    return (
        keep,
        slot_to_value["caption"],
        slot_to_value["left"],
        slot_to_value["right"],
        warnings_out,
    )


# ---------------------------------------------------------------------------
# Auto-stagger: detect collisions between Band/VLine labels on the x-axis
# ---------------------------------------------------------------------------

def _auto_stagger_band_labels(
    annotations: List[Annotation],
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    clamped_domain: Optional[List[float]],
) -> List[Annotation]:
    """Convert colliding labeled vertical bands into label-less Bands +
    staggered PointLabels.

    Walks the labeled vertical bands sorted by midpoint, estimates whether
    adjacent labels would visually overlap (using a 7px-per-character /
    14px-padding heuristic over the chart's pixel width). If any pair
    would collide, *all* labeled bands in the group are converted: their
    labels are stripped and replaced with PointLabels at alternating
    high/low y positions so adjacent labels never share a row.
    """
    labeled_bands: List[Tuple[int, Band]] = [
        (i, ann)
        for i, ann in enumerate(annotations)
        if isinstance(ann, Band)
        and ann.label
        and ann.x1 is not None
        and ann.x2 is not None
    ]
    if len(labeled_bands) < 2:
        return annotations

    band_mids: List[Tuple[int, Band, float]] = []
    for idx, band in labeled_bands:
        mid = (_to_numeric_x(band.x1) + _to_numeric_x(band.x2)) / 2.0
        band_mids.append((idx, band, mid))
    band_mids.sort(key=lambda t: t[2])

    x_col = mapping.get("x", "x")
    if x_col in df.columns and len(df) > 1:
        if pd.api.types.is_datetime64_any_dtype(df[x_col]):
            x_min_num = df[x_col].min().timestamp()
            x_max_num = df[x_col].max().timestamp()
        elif pd.api.types.is_numeric_dtype(df[x_col]):
            x_min_num = float(df[x_col].min())
            x_max_num = float(df[x_col].max())
        else:
            x_min_num, x_max_num = 0.0, 1.0
    else:
        x_min_num, x_max_num = 0.0, 1.0

    x_span = (x_max_num - x_min_num) if x_max_num != x_min_num else 1.0
    chart_width_px = 700
    char_width_px = 7
    padding_px = 14

    collision = False
    for i in range(len(band_mids) - 1):
        _, band_a, mid_a = band_mids[i]
        _, band_b, mid_b = band_mids[i + 1]
        px_dist = abs(mid_b - mid_a) / x_span * chart_width_px
        half_a = len(band_a.label or "") * char_width_px / 2.0
        half_b = len(band_b.label or "") * char_width_px / 2.0
        if px_dist < (half_a + half_b + padding_px):
            collision = True
            break

    if not collision:
        return annotations

    # Pick high/low stagger heights from the visible y range.
    if clamped_domain is not None:
        y_lo, y_hi = clamped_domain
        y_range = y_hi - y_lo
        stagger_high = y_hi - y_range * 0.05
        stagger_low = y_hi - y_range * 0.15
    else:
        y_field = mapping.get("y")
        if (
            y_field
            and y_field in df.columns
            and pd.api.types.is_numeric_dtype(df[y_field])
        ):
            y_max = float(df[y_field].max())
            y_min = float(df[y_field].min())
            y_range = (y_max - y_min) if y_max != y_min else (abs(y_max) or 10.0)
            stagger_high = y_max + y_range * 0.05
            stagger_low = y_max - y_range * 0.05
        else:
            stagger_high = 100.0
            stagger_low = 90.0

    band_idx_set = {idx for idx, _, _ in band_mids}
    stagger_map: Dict[int, float] = {}
    for rank, (orig_idx, _band, _mid) in enumerate(band_mids):
        stagger_map[orig_idx] = stagger_high if rank % 2 == 0 else stagger_low

    new_annotations: List[Annotation] = []
    for idx, ann in enumerate(annotations):
        if idx not in band_idx_set:
            new_annotations.append(ann)
            continue

        band = ann  # type: ignore[assignment]
        # Add the band without its label.
        new_annotations.append(
            Band(
                x1=band.x1,
                x2=band.x2,
                y1=band.y1,
                y2=band.y2,
                color=band.color,
                opacity=band.opacity,
            )
        )
        # Replace the label with a PointLabel at the staggered height.
        x1n = _to_numeric_x(band.x1)
        x2n = _to_numeric_x(band.x2)
        mid_num = (x1n + x2n) / 2.0
        if hasattr(band.x1, "timestamp") or isinstance(band.x1, str):
            try:
                mid_x: Any = pd.Timestamp(mid_num, unit="s")
            except Exception:  # noqa: BLE001
                mid_x = band.x1
        else:
            mid_x = mid_num

        new_annotations.append(
            PointLabel(
                x=mid_x,
                y=stagger_map[idx],
                label=band.label,
                font_size=9,
                dy=0,
                dx=0,
                align="center",
                label_color=band.label_color or "#333333",
            )
        )

    return new_annotations


def _compute_bar_value_suppression(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    annotations: Optional[List["Annotation"]],
) -> Tuple[set, Optional[Tuple[float, float]]]:
    """Decide which bar value labels should be suppressed.

    Class-1 (Bar_value_label_vs_Callout) and class-4
    (Stacked_bar_value_label_in_Band) of the 2026-05-10 collision
    audit (`projects/altair/dev/scratch/_collision_audit_2026-05-10_1955`).

    Returns ``(x_set_to_suppress, y_range_to_suppress)``:
      - ``x_set_to_suppress`` -- x-values where bar value labels should
        not be emitted because a Callout / PointLabel / Arrow is
        anchored to the same x. The annotation's text takes priority;
        the redundant numeric bar value would just collide.
      - ``y_range_to_suppress`` -- ``(y_lo, y_hi)`` band of the union
        of all labelled Bands. Stacked-bar TOTAL value labels whose y
        falls in this range are suppressed (they would render inside
        the Band's coloured fill and fight with the Band's own label).

    The per-bar single-series value labels DO NOT use the y-range
    filter -- a non-stacked bar's value label sits at the bar's apex
    and is intentionally above the Band's y range when the bar is
    taller than the Band. Class-4 specifically targets the stacked-
    total layer.
    """
    x_set: set = set()
    y_range: Optional[Tuple[float, float]] = None
    if not annotations:
        return x_set, y_range

    x_field = mapping.get("x")
    if not isinstance(x_field, str) or x_field not in df.columns:
        return x_set, y_range

    # Class 1: collect x positions of label-bearing Callout / PointLabel /
    # Arrow / PointHighlight annotations. Arrow uses x2 (head) for the
    # label anchor; the others use x.
    for ann in annotations:
        ann_x: Any = None
        if isinstance(ann, (Callout, PointLabel, PointHighlight)):
            ann_x = getattr(ann, "x", None)
        elif isinstance(ann, Arrow):
            ann_x = getattr(ann, "x2", None) or getattr(ann, "x", None)
        else:
            continue
        if ann_x is None:
            continue
        # Coerce datetime-like to pandas Timestamp so it matches the
        # bar's x_field values when we filter df later. Strings stay as
        # strings; numerics stay numeric.
        try:
            if hasattr(ann_x, "timestamp") or isinstance(ann_x, str):
                # Try datetime conversion; fall back to raw string.
                try:
                    ts = pd.Timestamp(ann_x)
                    if pd.api.types.is_datetime64_any_dtype(df[x_field]):
                        ann_x = ts
                except (TypeError, ValueError):
                    pass
        except Exception:  # noqa: BLE001
            pass
        x_set.add(ann_x)

    # Class 4: union of labelled Band y-ranges.
    for ann in annotations:
        if not isinstance(ann, Band):
            continue
        if not ann.label:
            continue
        if ann.y1 is None or ann.y2 is None:
            continue
        try:
            y_lo = float(min(ann.y1, ann.y2))
            y_hi = float(max(ann.y1, ann.y2))
        except (TypeError, ValueError):
            continue
        if y_range is None:
            y_range = (y_lo, y_hi)
        else:
            y_range = (min(y_range[0], y_lo), max(y_range[1], y_hi))

    return x_set, y_range


def _dedup_vlines_by_x(
    annotations: List[Annotation],
    df: pd.DataFrame,
    mapping: Dict[str, Any],
) -> List[Annotation]:
    """Dedup VLines that share an x within a small tolerance.

    Two or more VLines anchored to the same date / numeric x render as a
    single rule (because the dashes overlap pixel-perfectly), but the
    engine renders BOTH rule layers. The result reads as one line with
    the existing ``_auto_stagger_vline_labels`` ladder of stacked
    labels, but the duplication is silent -- the LLM never knows two
    events were collapsed into one.

    Algorithm: group VLines by x with tolerance:
      - datetime: 1 day,
      - numeric: 0.5%% of x-range,
      - other: exact-string equality.
    For each group of 2+, keep the first VLine, concat its label with
    the others (" / " separator), drop the rest. ``logger.info`` echoes
    the merge so QC traces show the dedup clearly. Surface the dedup in
    ``mapping['_warnings']`` for the LLM if a warnings collector is
    present.

    This pass MUST run before ``_drop_right_edge_vlines`` and
    ``_auto_stagger_vline_labels`` so survivors of the dedup get the
    same downstream treatment a single user-supplied VLine would.
    """
    if not annotations:
        return annotations
    vlines = [
        (i, ann) for i, ann in enumerate(annotations) if isinstance(ann, VLine)
    ]
    if len(vlines) < 2:
        return annotations

    x_col = mapping.get("x", "x")
    is_dt = (
        x_col in df.columns
        and pd.api.types.is_datetime64_any_dtype(df[x_col])
    )
    is_num = (
        x_col in df.columns
        and pd.api.types.is_numeric_dtype(df[x_col])
    )

    # Tolerance: 1 day for datetime; 0.5%% of x-range for numeric.
    if is_dt:
        try:
            tol = pd.Timedelta(days=1)
        except Exception:  # noqa: BLE001
            tol = pd.Timedelta(0)
    elif is_num and len(df) > 0:
        try:
            x_range = float(df[x_col].max()) - float(df[x_col].min())
            tol = max(x_range * 0.005, 1e-9)
        except Exception:  # noqa: BLE001
            tol = 0.0
    else:
        tol = None

    def _close(a: Any, b: Any) -> bool:
        if tol is None:
            return str(a) == str(b)
        try:
            if is_dt:
                return abs(pd.Timestamp(a) - pd.Timestamp(b)) <= tol
            if is_num:
                return abs(float(a) - float(b)) <= tol
        except (TypeError, ValueError):
            return str(a) == str(b)
        return False

    # Greedy single-pass clustering. Keep the FIRST occurrence as the
    # cluster representative; subsequent duplicates merge into it.
    cluster_rep: Dict[int, int] = {}  # idx -> rep_idx
    for i, (_, vi) in enumerate(vlines):
        rep = None
        for j in range(i):
            rep_idx = cluster_rep[vlines[j][0]]
            rep_ann = annotations[rep_idx]
            if isinstance(rep_ann, VLine) and _close(rep_ann.x, vi.x):
                rep = rep_idx
                break
        cluster_rep[vlines[i][0]] = rep if rep is not None else vlines[i][0]

    # Collect duplicates per representative.
    dup_labels_by_rep: Dict[int, List[str]] = {}
    indices_to_drop: set = set()
    for orig_idx, rep_idx in cluster_rep.items():
        if rep_idx == orig_idx:
            continue
        ann = annotations[orig_idx]
        if isinstance(ann, VLine) and ann.label:
            dup_labels_by_rep.setdefault(rep_idx, []).append(ann.label)
        indices_to_drop.add(orig_idx)

    if not indices_to_drop:
        return annotations

    new_annotations: List[Annotation] = []
    for i, ann in enumerate(annotations):
        if i in indices_to_drop:
            continue
        if i in dup_labels_by_rep and isinstance(ann, VLine):
            existing = ann.label or ""
            extra = dup_labels_by_rep[i]
            merged_parts = [s for s in [existing, *extra] if s]
            merged = " / ".join(merged_parts)
            logger.info(
                "[_dedup_vlines_by_x] Merged %d VLines at x=%s into one "
                "rule with label %r",
                len(extra) + 1, ann.x, merged,
            )
            # VLine is a dataclass with label inherited from Annotation.
            # Build a copy of the rep with the merged label.
            new_annotations.append(
                VLine(
                    x=ann.x,
                    label=merged,
                    color=ann.color,
                    label_color=ann.label_color,
                    style=ann.style,
                    stroke_dash=list(ann.stroke_dash),
                    stroke_width=ann.stroke_width,
                )
            )
        else:
            new_annotations.append(ann)
    return new_annotations


def _drop_right_edge_vlines(
    annotations: List[Annotation],
    df: pd.DataFrame,
    mapping: Dict[str, Any],
) -> List[Annotation]:
    """Drop ``VLine`` annotations whose ``x`` falls in the right-most
    ``_VLINE_RIGHT_EDGE_REJECT_FRAC`` (5%) of the data's x-range.

    Runs BEFORE ``_auto_stagger_vline_labels`` so a clustered labeled
    VLine in the right-edge zone never has its label extracted into a
    surviving ``PointLabel`` -- both the line AND the label drop
    together. The chart's right edge IS the latest x value, so a
    marker placed there reads as the chart edge itself rather than as
    an event. Pure deterministic reject; the LEFT edge is unchanged
    because the user typically picks a meaningful start date.

    Datetime and numeric x-axes are filtered. Nominal x-axes (e.g.
    yield-curve tenors) fall through unchanged -- the same shape as
    the existing VLine out-of-range filter inside
    ``render_annotations``.
    """
    if not annotations:
        return annotations
    if not any(isinstance(a, VLine) for a in annotations):
        return annotations

    x_col = mapping.get("x", "x")
    if x_col not in df.columns or len(df) == 0:
        return annotations

    is_dt = pd.api.types.is_datetime64_any_dtype(df[x_col])
    is_num = pd.api.types.is_numeric_dtype(df[x_col])
    if not (is_dt or is_num):
        return annotations

    try:
        if is_dt:
            x_min = df[x_col].min()
            x_max = df[x_col].max()
            x_range = x_max - x_min
            right_band = (
                x_range * _VLINE_RIGHT_EDGE_REJECT_FRAC
                if x_range.total_seconds() > 0
                else pd.Timedelta(0)
            )
        else:
            x_min = float(df[x_col].min())
            x_max = float(df[x_col].max())
            x_range = x_max - x_min
            right_band = (
                x_range * _VLINE_RIGHT_EDGE_REJECT_FRAC
                if x_range > 0
                else 0.0
            )
        threshold = x_max - right_band
    except Exception:  # noqa: BLE001
        return annotations

    kept: List[Annotation] = []
    for ann in annotations:
        if not isinstance(ann, VLine):
            kept.append(ann)
            continue
        try:
            vline_val = pd.Timestamp(ann.x) if is_dt else float(ann.x)
        except (TypeError, ValueError):
            kept.append(ann)
            continue
        if vline_val >= threshold:
            logger.warning(
                "Suppressed VLine at x=%s: in the right-most %d%% of "
                "the data range [%s, %s]. The chart's right edge IS "
                "the latest x value, so a marker there reads as the "
                "chart edge itself rather than as an event. Move the "
                "annotation earlier or call the date / value out in "
                "the title / subtitle.",
                ann.x,
                int(_VLINE_RIGHT_EDGE_REJECT_FRAC * 100),
                x_min, x_max,
            )
            continue
        kept.append(ann)
    return kept


def _auto_stagger_vline_labels(
    annotations: List[Annotation],
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    clamped_domain: Optional[List[float]],
    chart_width_px: int = 700,
) -> List[Annotation]:
    """Detect VLine label collisions and convert each colliding cluster's
    labels to PointLabel annotations at staggered y heights.

    Mirrors ``_auto_stagger_band_labels``: groups labeled VLines whose
    label boxes would overlap horizontally, then re-renders each cluster
    with the labels stripped from the VLines and a PointLabel placed at
    the corresponding x and a rotating high/mid/low y position.

    ``chart_width_px`` defaults to the ``wide`` preset width (700px)
    for standalone use. ``render_annotations`` passes the real
    per-panel pixel width when known (composites with 300-400px cells
    rely on this so the cluster detection's pixel-distance check uses
    the panel's actual horizontal budget, not the standalone default).
    """
    labeled_vlines: List[Tuple[int, VLine]] = [
        (i, ann)
        for i, ann in enumerate(annotations)
        if isinstance(ann, VLine) and ann.label
    ]
    if len(labeled_vlines) < 2:
        return annotations

    labeled_vlines.sort(key=lambda pair: _to_numeric_x(pair[1].x))

    x_col = mapping.get("x", "x")
    if x_col in df.columns and len(df) > 1:
        if pd.api.types.is_datetime64_any_dtype(df[x_col]):
            x_min_num = df[x_col].min().timestamp()
            x_max_num = df[x_col].max().timestamp()
        elif pd.api.types.is_numeric_dtype(df[x_col]):
            x_min_num = float(df[x_col].min())
            x_max_num = float(df[x_col].max())
        else:
            x_min_num, x_max_num = 0.0, 1.0
    else:
        x_min_num, x_max_num = 0.0, 1.0
    x_span = (x_max_num - x_min_num) if x_max_num != x_min_num else 1.0
    char_width_px = 7
    min_gap_px = 14

    # Cluster colliding VLines.
    groups: List[List[Tuple[int, VLine]]] = []
    current: List[Tuple[int, VLine]] = [labeled_vlines[0]]
    for j in range(1, len(labeled_vlines)):
        prev = current[-1][1]
        curr = labeled_vlines[j][1]
        prev_x = _to_numeric_x(prev.x)
        curr_x = _to_numeric_x(curr.x)
        px_dist = abs(curr_x - prev_x) / x_span * chart_width_px
        half_prev = len(prev.label or "") * char_width_px / 2.0
        half_curr = len(curr.label or "") * char_width_px / 2.0
        if px_dist < (half_prev + half_curr + min_gap_px):
            current.append(labeled_vlines[j])
        else:
            if len(current) > 1:
                groups.append(current)
            current = [labeled_vlines[j]]
    if len(current) > 1:
        groups.append(current)

    if not groups:
        return annotations

    # Pick the y-range the cluster's PointLabels will be staggered
    # within. On a dual-axis chart, ``clamped_domain`` and
    # ``df[y_field]`` both span the MERGED range (LEFT + RIGHT) -- using
    # those would land cluster labels in the right-axis range, which
    # the dual-axis annotation rewriter then forces onto the LEFT
    # scale, pushing them above the visible plot. Honor
    # ``mapping['dual_axis_config']['y_domain_left']`` first so the
    # stagger ladder lives entirely inside the LEFT axis's visible
    # range (where the labels will actually be encoded).
    dual_cfg = mapping.get("dual_axis_config") or {}
    left_domain = dual_cfg.get("y_domain_left")
    if left_domain is not None:
        y_lo = float(min(left_domain[0], left_domain[1]))
        y_hi = float(max(left_domain[0], left_domain[1]))
        y_range = (y_hi - y_lo) if y_hi != y_lo else 1.0
    elif clamped_domain is not None:
        y_hi = float(clamped_domain[1])
        y_lo = float(clamped_domain[0])
        y_range = y_hi - y_lo
    else:
        y_field = mapping.get("y")
        if y_field and y_field in df.columns:
            y_vals = pd.to_numeric(df[y_field], errors="coerce").dropna()
            if len(y_vals) > 0:
                y_hi = float(y_vals.max())
                y_lo = float(y_vals.min())
                y_range = (y_hi - y_lo) if y_hi != y_lo else 1.0
            else:
                y_hi, y_lo, y_range = 100.0, 0.0, 100.0
        else:
            y_hi, y_lo, y_range = 100.0, 0.0, 100.0

    new_annotations = list(annotations)
    indices_to_strip: set = set()
    extra_point_labels: List[PointLabel] = []
    for group in groups:
        # Build a per-cluster stagger ladder sized to the cluster: with 5
        # close VLines we want 5 distinct y rows, not just 3 cycling
        # positions. Distribute evenly between 5%% and (5 + 7*N)%% from
        # the top so labels never share a y row within a cluster.
        n_in_cluster = len(group)
        cluster_positions = [
            y_hi - y_range * (0.05 + 0.07 * k)
            for k in range(n_in_cluster)
        ]
        for k, (orig_idx, vline) in enumerate(group):
            indices_to_strip.add(orig_idx)
            extra_point_labels.append(
                PointLabel(
                    x=vline.x,
                    y=cluster_positions[k],
                    label=vline.label,
                    font_size=9,
                    align="center",
                    dx=0,
                    dy=0,
                    label_color=vline.label_color or "#333333",
                )
            )

    # Strip labels from clustered VLines.
    for idx in indices_to_strip:
        ann = new_annotations[idx]
        if isinstance(ann, VLine):
            new_annotations[idx] = VLine(
                x=ann.x,
                color=ann.color,
                stroke_width=ann.stroke_width,
                stroke_dash=ann.stroke_dash,
            )

    new_annotations.extend(extra_point_labels)
    return new_annotations


# ---------------------------------------------------------------------------
# Inter-type stagger: when a labeled HLine sits inside a labeled Band's
# y-range, both labels naturally land in the same y-pixel region (Band
# label centered on the band, HLine label just above the rule). Flip
# the HLine label below its rule to dodge the band label.
# ---------------------------------------------------------------------------

def _flip_hline_label_inside_band(
    annotations: List[Annotation],
) -> List[Annotation]:
    """For each HLine sitting inside a labelled Band's y-range, flip its
    label below the rule so it doesn't collide with the band's label.

    Pre-existing top-of-plot logic in ``render_annotations`` may have
    already moved an HLine's label below the rule; in that case we
    leave it alone. The flip is guaranteed only for HLines whose
    label currently anchors above the rule (negative ``_label_dy``).
    """
    band_ranges: List[Tuple[float, float]] = []
    for ann in annotations:
        if (
            isinstance(ann, Band)
            and ann.label
            and ann.y1 is not None
            and ann.y2 is not None
        ):
            try:
                band_ranges.append(
                    (
                        min(float(ann.y1), float(ann.y2)),
                        max(float(ann.y1), float(ann.y2)),
                    )
                )
            except (TypeError, ValueError):
                continue
    if not band_ranges:
        return annotations
    new_annotations = list(annotations)
    for ann in new_annotations:
        if not (isinstance(ann, HLine) and ann.label):
            continue
        try:
            hy = float(ann.y)
        except (TypeError, ValueError):
            continue
        for lo, hi in band_ranges:
            if lo <= hy <= hi:
                if ann._label_dy < 0:
                    ann._label_dy = 14
                break
    return new_annotations


# ---------------------------------------------------------------------------
# Auto-stagger: dedupe and spread Callouts that share or nearly share a data
# coordinate. Without this two Callouts at the same (x, y) paint as a single
# illegible pile because z-order overwrites the first label with the second.
# ---------------------------------------------------------------------------

def _auto_stagger_pointlabels(
    annotations: List[Annotation],
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    chart_width_px: int = 700,
) -> List[Annotation]:
    """Stagger 2+ PointLabels whose x values cluster close together.

    Each PointLabel paints at ``(x, y) + (dx, dy)`` pixels. With the
    default ``dy=-10``, two PointLabels at nearby x-values render their
    labels side-by-side just above the line and overlap when they don't
    fit in the available horizontal pitch. This handler detects
    consecutive PointLabels whose x-values are within an estimated
    label width of each other and alternates their ``dy`` so adjacent
    labels stack above-then-below-then-above their points.

    Behaviour:
      - Pairs / clusters that share an exact ``(x, y)`` are handled by
        ``_auto_stagger_callouts`` (which already dedups PointLabel +
        Callout collisions); this handler only acts on horizontal
        clusters where the x values differ but pack close.
      - When the PointLabel carries an explicit non-default ``dy``,
        respect the caller's intent and skip staggering -- the caller
        is positioning labels deliberately.
      - The data-to-pixel x conversion uses the visible x-range
        spanned by ``df[x_field]``; a chart-width estimate of 700px
        (the ``wide`` preset width) is used as a default when the
        annotation pipeline doesn't carry the real plot width. The
        result is conservative -- if anything we'll stagger labels
        that don't quite need it, never miss labels that do.
    """
    if not annotations:
        return annotations

    x_field = mapping.get("x") if isinstance(mapping.get("x"), str) else None
    if not x_field or x_field not in df.columns:
        return annotations

    # Index PointLabels with index + numeric-or-datetime x sort key.
    point_indices: List[Tuple[int, float]] = []
    for idx, ann in enumerate(annotations):
        if not isinstance(ann, PointLabel) or not ann.label:
            continue
        # Skip annotations whose dy is not the default (-10) -- caller
        # is positioning intentionally.
        if ann.dy != -10:
            continue
        try:
            x_num = _to_numeric_x(ann.x)
        except Exception:  # noqa: BLE001
            continue
        point_indices.append((idx, x_num))

    if len(point_indices) < 2:
        return annotations

    # Sort by x; collect the visible x-range from the DataFrame for the
    # data-to-pixel conversion.
    point_indices.sort(key=lambda t: t[1])
    try:
        x_min = _to_numeric_x(df[x_field].min())
        x_max = _to_numeric_x(df[x_field].max())
    except Exception:  # noqa: BLE001
        return annotations
    x_span = float(x_max - x_min)
    if x_span <= 0:
        return annotations

    # Estimated PointLabel pixel width: label_chars * font_size * 0.6.
    # Use the longest label in the candidate set so adjacent labels of
    # different lengths don't collide when one is much wider.
    max_chars = max(
        len(annotations[idx].label)  # type: ignore[union-attr]
        for idx, _ in point_indices
    )
    sample_font_size = annotations[point_indices[0][0]].font_size  # type: ignore[union-attr]
    label_pixel_w = max_chars * sample_font_size * 0.6 + 6
    # Pixel-per-data-unit conversion uses the panel's real width when
    # the caller threaded one through (composites do); otherwise the
    # ``wide`` preset (700px).
    px_per_x = float(chart_width_px) / x_span

    # Greedily build clusters: any consecutive pair whose pixel gap is
    # smaller than the label pixel width sits in the same cluster.
    clusters: List[List[int]] = []
    current: List[int] = []
    last_x_pixel: Optional[float] = None
    for idx, x_num in point_indices:
        x_pixel = (x_num - x_min) * px_per_x
        if last_x_pixel is None or (x_pixel - last_x_pixel) >= label_pixel_w:
            if len(current) >= 2:
                clusters.append(current)
            current = [idx]
        else:
            current.append(idx)
        last_x_pixel = x_pixel
    if len(current) >= 2:
        clusters.append(current)

    if not clusters:
        return annotations

    # Stagger each cluster: alternate above (-10, -24, -38, ...) and
    # below (+14, +28, +42, ...) of the anchor point. This mirrors
    # _auto_stagger_callouts' dy stair-step but with the alternating
    # pattern so the labels visually fan out from each point.
    for cluster in clusters:
        for k, idx in enumerate(cluster):
            ann = annotations[idx]
            if not isinstance(ann, PointLabel):
                continue
            level = k // 2
            if k % 2 == 0:
                ann.dy = -10 - level * 14
            else:
                ann.dy = 14 + level * 14
        logger.info(
            "[render_annotations] Staggered %d PointLabel(s) clustered at "
            "x-pixel pitch < %.1fpx (max label %d chars).",
            len(cluster), label_pixel_w, max_chars,
        )

    return annotations


def _auto_stagger_callouts(
    annotations: List[Annotation],
    df: Optional[pd.DataFrame] = None,
    mapping: Optional[Dict[str, Any]] = None,
    chart_height_px: int = 350,
) -> List[Annotation]:
    """Dedupe and stagger overlapping Callouts.

    Behaviour:
      - Two or more Callouts at the same ``x`` whose ``y`` values land
        within a per-Callout pixel pitch of each other form a *cluster*
        (the cluster is the loosened dedup unit -- callers no longer
        need to pin every Callout to a byte-identical ``y`` to trigger
        the stack handler).
      - Within each cluster, two Callouts with the same ``label`` are
        deduped to one (keep the first, log a warning on subsequent
        ones); two or more Callouts with distinct labels keep all but
        stagger their ``dy`` so they form a readable vertical stack.
      - PointLabel + Callout at the same ``(x, y)`` is treated as a
        special-case dedup -- the Callout's label is kept (Callout has
        a halo for legibility) and the PointLabel is dropped.

    The per-Callout x/y coordinates are unchanged; only ``dy`` is
    rewritten to spread overlapping labels.

    ``df`` and ``mapping`` are used only to derive the data-y range,
    which feeds the y-pixel pitch test used to detect a cluster. When
    not supplied (callers that pre-date the loosened dedup) the
    function falls back to the previous strict-equality behaviour.
    ``chart_height_px`` defaults to a conservative ``wide``-preset
    height (350px) when the annotation pipeline doesn't thread the
    real plot height through.
    """
    if not annotations:
        return annotations

    new_annotations = list(annotations)

    # ----- y-pixel-per-y-data conversion --------------------------------
    # When df + mapping describe a numeric y-axis, derive the pixel
    # pitch used to test whether two Callouts share a cluster. Without
    # them, fall back to ``y_pitch_data = 0`` so the cluster test
    # degenerates to the previous strict-equality behaviour.
    y_pitch_data: float = 0.0
    callout_pixel_pitch_px = 18.0  # ~callout halo height + small gap
    if df is not None and mapping is not None:
        y_field = mapping.get("y")
        if y_field and y_field in df.columns:
            y_vals = pd.to_numeric(df[y_field], errors="coerce").dropna()
            if len(y_vals) > 0:
                y_lo = float(y_vals.min())
                y_hi = float(y_vals.max())
                y_range = (y_hi - y_lo) if y_hi != y_lo else 1.0
                # data-units required to span ``callout_pixel_pitch_px``
                # in the plot region.
                y_pitch_data = (callout_pixel_pitch_px / chart_height_px) * y_range

    # ----- group Callouts by exact x; within each x-group, cluster by y -
    callout_by_x: Dict[Any, List[int]] = {}
    for idx, ann in enumerate(new_annotations):
        if isinstance(ann, Callout) and ann.label:
            callout_by_x.setdefault(ann.x, []).append(idx)

    indices_to_drop: set = set()
    # cluster_keys[(x_key, y_repr)] = list of (idx) -- consumed by the
    # PointLabel co-location pass below.
    callout_keys: set = set()
    for x_key, idxs in callout_by_x.items():
        # Annotate each idx with its numeric y where possible; non-numeric
        # y values (categorical heatmap rows etc.) fall back to the raw
        # value so the cluster test still treats identical category
        # strings as colliding.
        entries: List[Tuple[int, Any, float]] = []
        for idx in idxs:
            ann = new_annotations[idx]
            if not isinstance(ann, Callout):
                continue
            try:
                y_num = float(ann.y) if ann.y is not None else 0.0
                y_key: Any = y_num
            except (TypeError, ValueError):
                y_num = 0.0
                y_key = ann.y
            entries.append((idx, y_key, y_num))
            callout_keys.add((x_key, y_key))
        if len(entries) <= 1:
            continue
        # Sort by numeric y; cluster consecutive entries whose y-gap is
        # within ``y_pitch_data`` (or treat all as one cluster when the
        # pitch is unknown / zero, preserving the legacy behaviour).
        entries.sort(key=lambda t: t[2])
        clusters: List[List[Tuple[int, Any, float]]] = []
        current: List[Tuple[int, Any, float]] = [entries[0]]
        for j in range(1, len(entries)):
            prev_y = current[-1][2]
            curr_y = entries[j][2]
            gap = abs(curr_y - prev_y)
            if y_pitch_data == 0 or gap < y_pitch_data:
                current.append(entries[j])
            else:
                if len(current) >= 2:
                    clusters.append(current)
                current = [entries[j]]
        if len(current) >= 2:
            clusters.append(current)
        # For each cluster: dedup same-label, then stagger remaining dy.
        for cluster in clusters:
            seen_labels: Dict[str, int] = {}
            survivors: List[int] = []
            for idx, _y_key, _y_num in cluster:
                ann = new_annotations[idx]
                if not isinstance(ann, Callout):
                    continue
                if ann.label in seen_labels:
                    logger.warning(
                        "[render_annotations] Dropping duplicate Callout "
                        "at (x=%s, y=%s) with same label %r already at "
                        "index %d (cluster size %d).",
                        ann.x, ann.y, ann.label, seen_labels[ann.label],
                        len(cluster),
                    )
                    indices_to_drop.add(idx)
                else:
                    seen_labels[ann.label] = idx
                    survivors.append(idx)
            if len(survivors) >= 2:
                base_dy = float(new_annotations[survivors[0]].dy)  # type: ignore[union-attr]
                spacing = 14
                for k, idx in enumerate(survivors):
                    ann = new_annotations[idx]
                    if isinstance(ann, Callout):
                        ann.dy = int(base_dy - k * spacing)
                logger.info(
                    "[render_annotations] Staggered %d Callout(s) "
                    "clustered at x=%s within %.4f y-units "
                    "(~%.1fpx pitch).",
                    len(survivors), x_key, y_pitch_data,
                    callout_pixel_pitch_px,
                )

    # PointLabel + Callout at the same coordinate: drop PointLabel.
    for idx, ann in enumerate(new_annotations):
        if isinstance(ann, PointLabel):
            try:
                y_key: Any = float(ann.y)
            except (TypeError, ValueError):
                y_key = ann.y
            key = (ann.x, y_key)
            if key in callout_keys:
                logger.warning(
                    "[render_annotations] Dropping PointLabel at (x=%s, "
                    "y=%s) -- a Callout occupies the same coordinate.",
                    ann.x, ann.y,
                )
                indices_to_drop.add(idx)

    if not indices_to_drop:
        return new_annotations
    return [
        ann for i, ann in enumerate(new_annotations) if i not in indices_to_drop
    ]


# ---------------------------------------------------------------------------
# Auto-stagger: spread HLine label dy positions when 2+ rules sit close enough
# in y-pixel space that their labels would collide.
# ---------------------------------------------------------------------------

def _auto_stagger_hline_labels(
    annotations: List[Annotation],
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    clamped_domain: Optional[List[float]],
    chart_height_px: int = 350,
) -> List[Annotation]:
    """Stagger HLine label dy when multiple labelled HLines cluster in y.

    Mirrors ``_auto_stagger_vline_labels`` (x-axis) for the y-axis. With
    2+ HLines whose rules are within one label-row of each other, the
    default ``dy=-8`` (label above the rule) puts all labels at near-
    identical pixel positions and they paint as a single smudge.

    Algorithm: convert rule-y values to pixel-y coordinates (using the
    plot's clamped domain and approx chart height), then walk the
    cluster top-down setting each label's pixel row at most
    ``label_height_px`` above the previous label. The required ``dy``
    to achieve that pixel row is computed back from the rule's own
    pixel-y. This handles the case where consecutive rules are already
    close (a flat ladder ``[-8, -22, -36]`` would still collide because
    the rules themselves only differ by a few pixels).
    """
    labeled: List[Tuple[int, HLine]] = [
        (i, ann)
        for i, ann in enumerate(annotations)
        if isinstance(ann, HLine) and ann.label
    ]
    if len(labeled) < 2:
        return annotations

    if clamped_domain is None:
        y_field = mapping.get("y")
        if (
            y_field
            and y_field in df.columns
            and pd.api.types.is_numeric_dtype(df[y_field])
        ):
            y_min = float(df[y_field].min())
            y_max = float(df[y_field].max())
        else:
            return annotations
    else:
        y_min, y_max = float(clamped_domain[0]), float(clamped_domain[1])
    y_range = y_max - y_min if y_max > y_min else 1.0

    labeled.sort(key=lambda pair: -float(pair[1].y))

    # Pitch ladder uses 1.5 * HLine label fontSize (10px) so adjacent
    # rows have a comfortable half-line-height gap rather than the
    # previous tight 14px (which was visually flush). Bumped per the
    # collision audit's C02 finding.
    hline_label_fontsize = 10
    label_height_px = int(hline_label_fontsize * 1.5)
    min_gap_y = label_height_px / max(chart_height_px, 1) * y_range

    groups: List[List[Tuple[int, HLine]]] = []
    current: List[Tuple[int, HLine]] = [labeled[0]]
    for j in range(1, len(labeled)):
        prev_y = float(current[-1][1].y)
        curr_y = float(labeled[j][1].y)
        if abs(prev_y - curr_y) < min_gap_y * 1.6:
            current.append(labeled[j])
        else:
            if len(current) > 1:
                groups.append(current)
            current = [labeled[j]]
    if len(current) > 1:
        groups.append(current)

    if not groups:
        return annotations

    px_per_unit = chart_height_px / y_range

    new_annotations = list(annotations)
    for group in groups:
        # Pixel positions for each rule (0 = top of plot, larger = lower).
        rule_pixel = [(y_max - float(hl[1].y)) * px_per_unit for hl in group]

        # Top label sits 8 px above its rule. Each subsequent label is
        # placed at most ``label_height_px`` pixels above the previous
        # label to avoid vertical overlap.
        label_pixel: List[float] = [rule_pixel[0] - 8.0]
        for i in range(1, len(group)):
            forced_above_prev = label_pixel[i - 1] - label_height_px
            natural_above_rule = rule_pixel[i] - 8.0
            label_pixel.append(min(forced_above_prev, natural_above_rule))

        # If the topmost label has been pushed off the chart top (pixel
        # 0 = chart top), re-anchor by flipping the cluster's bottom-
        # most label below its rule and walking the labels DOWN instead.
        if label_pixel[0] < 4:
            label_pixel = [rule_pixel[-1] + 12.0]
            for i in range(1, len(group)):
                idx = len(group) - 1 - i
                forced_below_prev = label_pixel[-1] + label_height_px
                natural_below_rule = rule_pixel[idx] + 12.0
                label_pixel.append(max(forced_below_prev, natural_below_rule))
            label_pixel.reverse()

        for k, (orig_idx, _) in enumerate(group):
            ann = new_annotations[orig_idx]
            if isinstance(ann, HLine):
                # dy is text-relative-to-rule in pixels. Negative = up.
                ann._label_dy = int(round(label_pixel[k] - rule_pixel[k]))
    return new_annotations


# ---------------------------------------------------------------------------
# Auto-stagger: spread LastValueLabel text positions vertically so 2+ series
# ending at near-identical y values don't paint as a single illegible smudge.
# ---------------------------------------------------------------------------

def _collect_lvl_series_labels(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
) -> List[str]:
    """Return the series-name labels that ``LastValueLabel`` will paint.

    Mirrors the resolution order in ``LastValueLabel.to_layer``:
    * ``mapping['color']`` column values (multi-series with explicit
      color), OR
    * wide-format ``mapping['y']`` list entries (auto-melted to long
      form internally), OR
    * the single y field name as a fallback.

    Returns an empty list when none of the above applies (e.g. heatmap),
    in which case the LVL renderer would no-op anyway.
    """
    color_field = mapping.get("color")
    y_field = mapping.get("y")
    if color_field and color_field in df.columns:
        return [str(s) for s in df[color_field].dropna().unique()]
    if isinstance(y_field, list):
        return [str(c) for c in y_field if c is not None]
    if isinstance(y_field, str):
        return [y_field]
    return []


def _validate_lvl_series_names(
    annotations: Optional[List["Annotation"]],
    df: pd.DataFrame,
    mapping: Dict[str, Any],
) -> None:
    """Raise ``LvlSeriesNameTooLongError`` when any series name destined for
    ``LastValueLabel`` rendering exceeds ``_LVL_SERIES_NAME_MAX_CHARS``.

    Skips silently when no LVL is in the annotation list (no validation
    needed if the labels aren't going to render).
    """
    if not annotations:
        return
    if not any(isinstance(a, LastValueLabel) for a in annotations):
        return
    labels = _collect_lvl_series_labels(df, mapping)
    offenders = [s for s in labels if len(s) > _LVL_SERIES_NAME_MAX_CHARS]
    if not offenders:
        return
    sample = ", ".join(f"{s!r} ({len(s)} chars)" for s in offenders[:3])
    if len(offenders) > 3:
        sample += f", ... ({len(offenders) - 3} more)"
    raise LvlSeriesNameTooLongError(
        (
            f"LastValueLabel cannot render series names longer than "
            f"{_LVL_SERIES_NAME_MAX_CHARS} characters: {sample}. "
            f"multi_line / timeseries charts default to end-of-line "
            f"labelling (chart_context.md \u00a76.1); long names devour "
            f"the plot region. Rename the series in the DataFrame to "
            f"fit the cap (e.g. 'United States Equities Index 500' "
            f"\u2192 'S&P 500') before calling make_chart()."
        ),
        offending_names=offenders,
        mapping=mapping,
    )


def _should_auto_inject_lvl(
    chart_type: str,
    mapping: Dict[str, Any],
    annotations: Optional[List["Annotation"]],
) -> bool:
    """Decide whether ``make_chart`` should auto-inject a default
    ``LastValueLabel`` annotation.

    ``multi_line`` and ``timeseries`` charts default to end-of-line
    labelling (FT / Bloomberg house style) instead of a colour legend.
    The legend forces a lookup-tax between hex swatch and series name;
    LVL paints the series name right at the line's end, in the line's
    own colour. The downstream legend-suppression branch inside
    ``render_annotations`` turns the colour legend off automatically
    once any ``LastValueLabel`` is in the annotation list.

    Returns True only when ALL of the following hold:

    * ``chart_type`` is line-shaped (``multi_line`` / ``timeseries``).
    * Not dual-axis -- LVL collides with the right y-axis; colour legend
      identifies series instead.
    * Caller has not already added a ``LastValueLabel`` annotation --
      the explicit annotation always wins.
    * Caller has not set ``mapping['legend'] = True`` -- this is the
      internal QC fallback for post-render label-collision cases
      (NOT part of the PRISM-facing surface; omitted from
      ``chart_context.md``).
    """
    if chart_type not in {"multi_line", "timeseries"}:
        return False
    if mapping.get("dual_axis_series"):
        return False
    if mapping.get("legend") is True:
        return False
    if annotations and any(isinstance(a, LastValueLabel) for a in annotations):
        return False
    return True


def _strip_dual_axis_lvl_annotations(
    annotations: Optional[List["Annotation"]],
    mapping: Dict[str, Any],
) -> Tuple[Optional[List["Annotation"]], int]:
    """Drop ``LastValueLabel`` on dual-axis charts.

    End-of-line labels paint past the last x point and collide with the
    right-hand y-axis scale / ticks. Dual-axis charts use the colour legend
    for series identification instead.
    """
    if not annotations or not mapping.get("dual_axis_series"):
        return annotations, 0
    kept = [a for a in annotations if not isinstance(a, LastValueLabel)]
    removed = len(annotations) - len(kept)
    return (kept or None), removed


def _strip_lvl_annotations(
    annotations: Optional[List["Annotation"]],
) -> Optional[List["Annotation"]]:
    """Silently remove all ``LastValueLabel`` annotations.

    Facet grids prohibit end-of-line labels -- panel density and shared-
    axis comparison make LVL collide or steal margin. PRISM may pass
    explicit LVL annotations; the engine drops them without warning in
    facet multipanel contexts.
    """
    if not annotations:
        return annotations
    stripped = [a for a in annotations if not isinstance(a, LastValueLabel)]
    return stripped or None


def _values_match_for_endpoint(a: Any, b: Any) -> bool:
    """Tolerant equality for endpoint coordinate matching.

    Handles the type-mix the chart engine sees in practice: pandas
    Timestamp / numpy datetime64 / Python datetime / int / float / str.
    Direct equality is tried first (covers the dominant case where both
    values came from the same DataFrame cell); numeric and timestamp
    coercion fall through as backstops.
    """
    if a is None or b is None:
        return a is b
    try:
        if a == b:
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        if float(a) == float(b):
            return True
    except (TypeError, ValueError):
        pass
    try:
        if pd.Timestamp(a) == pd.Timestamp(b):
            return True
    except (TypeError, ValueError, OverflowError):
        pass
    return False


def _strip_endpoint_annotations_redundant_to_lvl(
    df: pd.DataFrame,
    chart_type: str,
    mapping: Dict[str, Any],
    annotations: Optional[List["Annotation"]],
) -> Optional[List["Annotation"]]:
    """Silently drop ``Callout`` / ``PointLabel`` / ``PointHighlight``
    placed at the endpoint of any series when an LVL is in the
    annotation list.

    PRISM commonly hand-rolls a ``Callout(x=last_x, y=last_y, label=...)``
    or ``PointHighlight(x=last_x, y=last_y, ...)`` to "highlight the
    latest value" on a ``multi_line`` / ``timeseries`` chart. The engine
    auto-injects (or accepts an explicit) ``LastValueLabel`` for the
    same series, which paints the series name at the right edge of the
    line. The two annotations stack visually -- the auto-LVL plus
    PRISM's hand-rolled label crowd the same pixel column at the line's
    end.

    Per design principle #7 (engines absorb friction), the engine
    silently drops the redundant endpoint annotation. No ``warnings``
    entry is appended -- the strip is invisible to PRISM. The dropped
    annotation is logged at DEBUG only.

    Conditions for stripping (all must hold):
    * Chart is ``multi_line`` / ``timeseries``.
    * Not dual-axis (LVL doesn't fire there anyway).
    * The annotation list contains at least one ``LastValueLabel`` --
      this is what's redundant with PRISM's hand-rolled label.
    * The annotation's ``(x, y)`` coordinate matches the latest data
      point of one of the chart's series (per-series in long format,
      per-y-column in wide auto-melt, single point otherwise).
    """
    if chart_type not in {"multi_line", "timeseries"}:
        return annotations
    if not annotations:
        return annotations
    if not any(isinstance(a, LastValueLabel) for a in annotations):
        return annotations
    if mapping.get("dual_axis_series"):
        return annotations

    x_field = mapping.get("x")
    y_field = mapping.get("y")
    if not x_field or x_field not in df.columns:
        return annotations

    color_col = mapping.get("color")
    endpoint_coords: List[Tuple[Any, Any]] = []
    try:
        if isinstance(y_field, list):
            sorted_df = df.sort_values(x_field)
            if not sorted_df.empty:
                last_row = sorted_df.iloc[-1]
                last_x = last_row[x_field]
                for col in y_field:
                    if col in sorted_df.columns:
                        endpoint_coords.append((last_x, last_row[col]))
        elif color_col and color_col in df.columns:
            for _, group in df.groupby(color_col, sort=False):
                if x_field in group.columns and y_field in group.columns:
                    last_row = group.sort_values(x_field).iloc[-1]
                    endpoint_coords.append(
                        (last_row[x_field], last_row[y_field])
                    )
        else:
            if y_field in df.columns:
                sorted_df = df.sort_values(x_field)
                if not sorted_df.empty:
                    last_row = sorted_df.iloc[-1]
                    endpoint_coords.append(
                        (last_row[x_field], last_row[y_field])
                    )
    except Exception:  # noqa: BLE001
        return annotations

    if not endpoint_coords:
        return annotations

    surviving: List[Annotation] = []
    for ann in annotations:
        if isinstance(ann, (Callout, PointLabel, PointHighlight)):
            ann_x = getattr(ann, "x", None)
            ann_y = getattr(ann, "y", None)
            if ann_x is not None and ann_y is not None:
                hit = any(
                    _values_match_for_endpoint(ann_x, ep_x)
                    and _values_match_for_endpoint(ann_y, ep_y)
                    for ep_x, ep_y in endpoint_coords
                )
                if hit:
                    logger.debug(
                        "[make_chart] Dropping endpoint %s at (%s, %s) "
                        "(redundant with LastValueLabel)",
                        type(ann).__name__, ann_x, ann_y,
                    )
                    continue
        surviving.append(ann)
    return surviving


def _stagger_lvl_text_y(
    last_rows: pd.DataFrame,
    y_field: str,
    label_col: str,
    font_size: int,
    y_domain: Optional[Tuple[float, float]] = None,
    chart_height_px: int = 350,
) -> pd.DataFrame:
    """Add a ``_y_text`` column with non-colliding y values for label text.

    Mirrors the spirit of ``_auto_stagger_band_labels`` /
    ``_auto_stagger_vline_labels``: detects collisions in pixel space and
    redistributes the colliding positions. The dot stays at the actual y
    (one dot per series); only the *text mark* uses the staggered y. The
    visual contract is "label color matches series color, label sits near
    the line's end" -- the small vertical drift is acceptable because each
    label remains paired by colour to its line.

    Args:
        last_rows: DataFrame with one row per series (already grouped).
        y_field: Column holding the actual end-of-line y value.
        label_col: Column holding the label string (used for length-based
            sanity logging only).
        font_size: Font size of the label text in points (used as the
            vertical line-height proxy).
        y_domain: Optional (y_min, y_max) of the plot's visible y-axis.
            When omitted the function uses the data's own min/max with a
            5%% pad.
        chart_height_px: Approximate plot-region height in pixels. The
            default (350) matches the most common preset (``wide``).

    Returns:
        ``last_rows`` with a new ``_y_text`` column.
    """
    if last_rows.empty:
        last_rows = last_rows.copy()
        last_rows["_y_text"] = []
        return last_rows

    df_out = last_rows.copy()

    if y_domain is None:
        y_vals = pd.to_numeric(df_out[y_field], errors="coerce").dropna()
        if y_vals.empty:
            df_out["_y_text"] = df_out[y_field]
            return df_out
        y_min = float(y_vals.min())
        y_max = float(y_vals.max())
        y_pad = (y_max - y_min) * 0.05 if y_max > y_min else max(abs(y_max), 1.0) * 0.1
        y_domain = (y_min - y_pad, y_max + y_pad)

    y_lo, y_hi = float(y_domain[0]), float(y_domain[1])
    if y_hi <= y_lo:
        df_out["_y_text"] = df_out[y_field]
        return df_out
    y_range = y_hi - y_lo

    # Line height in y-data units. font_size pt -> ~ 1.4 * font_size px.
    line_height_px = max(1.0, font_size * 1.4)
    line_height_y = line_height_px / max(chart_height_px, 1) * y_range

    sort_idx = df_out[y_field].astype(float).sort_values(ascending=False).index
    y_text = df_out[y_field].astype(float).copy()

    sorted_vals = y_text.loc[sort_idx].tolist()
    n = len(sorted_vals)

    # Top-down pass: push each label below the previous one if needed.
    for i in range(1, n):
        if sorted_vals[i - 1] - sorted_vals[i] < line_height_y:
            sorted_vals[i] = sorted_vals[i - 1] - line_height_y

    # Bottom check: if the last label has slid below the visible domain,
    # do a bottom-up compress pass anchored at y_lo + 1 line.
    if sorted_vals[-1] < y_lo:
        sorted_vals[-1] = y_lo + line_height_y * 0.5
        for i in range(n - 2, -1, -1):
            if sorted_vals[i] - sorted_vals[i + 1] < line_height_y:
                sorted_vals[i] = sorted_vals[i + 1] + line_height_y

    # Top check after compress: if the top label is above y_hi, the
    # cluster exceeds the available vertical room. Compress to fit.
    if sorted_vals[0] > y_hi:
        sorted_vals[0] = y_hi - line_height_y * 0.5
        for i in range(1, n):
            min_gap = line_height_y if (i < n - 1) else (line_height_y * 0.5)
            if sorted_vals[i - 1] - sorted_vals[i] < min_gap:
                sorted_vals[i] = sorted_vals[i - 1] - min_gap

    for i, idx_val in enumerate(sort_idx):
        y_text.loc[idx_val] = sorted_vals[i]

    df_out["_y_text"] = y_text.astype(float).values
    return df_out


# ---------------------------------------------------------------------------
# render_annotations: layer annotations on top of a base chart
# ---------------------------------------------------------------------------

def _rewrite_y_encodings_for_dual_axis(
    layer: alt.Chart,
    domain: List[float],
    orient: str,
) -> alt.Chart:
    """Force every field-based y encoding inside ``layer`` to use the
    chosen dual-axis side's scale with a hidden axis.

    Why this exists. The dual-axis builder produces a ``LayerChart`` with
    ``resolve_scale(y='independent')`` so each side keeps its own y
    domain. When ``render_annotations`` splices an annotation layer into
    that LayerChart and the annotation's ``to_layer()`` emits a y
    encoding against the user's ``mapping['y']`` (typically
    ``"value"``), Vega-Lite gives that new field its own scale --
    rendering a third y-axis on the LEFT, with the field name
    ("value") as the axis title. The same root cause appears for every
    annotation whose ``to_layer()`` output carries a field-based y
    encoding (VLine label, Arrow body / head / label, PointLabel halo
    + text, Band(y1,y2) rect + halo + text, plus PointHighlight /
    Callout when ``axis='left'``).

    The fix mirrors the pattern already in place inside
    ``LastValueLabel.to_layer`` (and the dedicated dual-axis branches
    for HLine / Segment / PointHighlight axis='right' / Callout
    axis='right'): pin the layer's y scale to the chosen side's domain
    and suppress its axis rendering. The data column name does not
    have to be renamed -- ``resolve_scale(y='independent')`` already
    isolates this layer's scale, and an explicit ``domain=...``
    plus ``labels=False / ticks=False / domain=False / title=None``
    leaves the layer positioned but invisible as an axis.

    Implementation walks the alt.Chart object directly (recursing into
    LayerCharts) and re-encodes each leaf chart's y channel via
    ``chart.encode(y=alt.Y(...))``. We deliberately avoid the
    ``to_dict()`` + ``from_dict()`` round-trip because Altair's
    ``LayerChart.from_dict`` adds top-only attributes (``$schema``,
    ``datasets``) that ``add_layers`` then refuses to splice as a
    sub-spec.

    Pixel-positioned y encodings (``y=alt.value(N)``, used by VLine's
    nominal-y branch) carry no ``field`` and are left untouched.

    Args:
        layer: alt.Chart returned by an annotation's ``to_layer()``.
        domain: ``[lo, hi]`` from ``mapping['dual_axis_config']``
            (``y_domain_left`` for left-axis annotations,
            ``y_domain_right`` for right-axis).
        orient: ``"left"`` or ``"right"`` -- only affects which side
            the (hidden) axis is anchored to.

    Returns:
        Rewritten chart (LayerChart or Chart). Falls back to the input
        layer on any failure -- the rewrite is best-effort and never
        blocks rendering.
    """
    scale = alt.Scale(domain=[float(domain[0]), float(domain[1])])
    axis = alt.Axis(
        orient=orient,
        title=None,
        labels=False,
        ticks=False,
        domain=False,
        grid=False,
    )

    def _has_field_y(chart: alt.Chart) -> Optional[str]:
        """Return the y field name if ``chart`` has a field-based y
        encoding, else ``None``. Skips pixel-positioned (``alt.value``)
        and absent encodings.

        Resolves via ``y_enc.to_dict()`` rather than ``y_enc.field``
        because altair stores ``alt.Y('value:Q')`` as a ``shorthand``
        attribute, leaving ``field`` as ``Undefined`` until the
        shorthand is parsed at serialization time. Reading ``field``
        directly is the wrong probe -- ``to_dict()`` is the canonical
        evaluation hook.
        """
        enc = getattr(chart, "encoding", None)
        if enc is None or enc is alt.Undefined:
            return None
        y_enc = getattr(enc, "y", None)
        if y_enc is None or y_enc is alt.Undefined:
            return None
        try:
            y_dict = y_enc.to_dict()
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(y_dict, dict):
            return None
        field = y_dict.get("field")
        if isinstance(field, str) and field:
            return field
        return None

    def _walk(chart: alt.Chart) -> alt.Chart:
        # LayerChart: recurse into each child; rebuild via `.copy()` so
        # we keep resolve_scale, properties, etc.
        if isinstance(chart, alt.LayerChart):
            try:
                sub_layers = [_walk(sub) for sub in chart.layer]
                rebuilt = chart.copy(deep=False)
                rebuilt.layer = sub_layers
                return rebuilt
            except Exception:  # noqa: BLE001
                return chart

        # Leaf Chart with a field-based y encoding: re-encode y to add
        # the explicit scale + hidden axis, leaving every other encoding
        # (x, x2, y2, color, text, ...) untouched. ``chart.encode(y=...)``
        # is the canonical altair way to update a single encoding
        # channel without disturbing the rest.
        field = _has_field_y(chart)
        if field is None:
            return chart
        try:
            return chart.encode(
                y=alt.Y(
                    f"{field}:Q", scale=scale, axis=axis,
                )
            )
        except Exception:  # noqa: BLE001
            return chart

    try:
        return _walk(layer)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[render_annotations] dual-axis y-encoding rewrite failed: %s",
            exc,
        )
        return layer


def render_annotations(
    chart: alt.Chart,
    annotations: List[Annotation],
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    chart_type: Optional[str] = None,
    chart_width: Optional[int] = None,
    chart_height: Optional[int] = None,
) -> alt.Chart:
    """Render every annotation and combine with the base chart.

    Steps:
      1. Compute the data's y-domain and (for non-dual-axis charts)
         re-encode the base chart with that explicit domain so an
         out-of-range HLine at y=2.0 cannot stretch the y-axis.
      2. Auto-stagger colliding Band / VLine labels.
      3. Drop HLines at universally-known thresholds (zero, PMI 50, Fed 2%).
      4. Drop VLines / HLines that fall outside the visible data range.
         (Right-edge VLines in the right-most 5% of the data range run
         through ``_drop_right_edge_vlines`` upstream, BEFORE the
         auto-stagger pass, so a clustered labeled VLine in the
         right-edge zone doesn't have its label extracted into a
         surviving ``PointLabel``.)
      5. Encode dual-axis HLines / Segments / PointHighlights / Callouts
         against the correct y field (left or right).
      6. ``PlotText`` annotations are layered using ``alt.value(px)``
         positioning relative to the inner plot region, so they require
         the chart's pixel ``chart_width`` / ``chart_height``.
      7. Layer everything together.

    Args:
        chart: Base chart to annotate.
        annotations: List of annotation objects.
        df: Original DataFrame.
        mapping: Column mapping.
        skin_config: Active skin configuration dict.
        chart_type: Echoed chart type (drives a couple of routing decisions).
        chart_width / chart_height: Plot-region pixel dimensions.
            Required for ``PlotText`` so it can position via absolute
            pixel offsets; ignored for every other annotation type.

    Returns:
        Chart with annotations layered on top.
    """
    if not annotations:
        return chart

    # On a heatmap, every cell carries its own value label. A halo-style
    # Callout overlapped by that cell label produces unreadable mud
    # (vision audit 22/C1). Force ``background='box'`` for any Callout
    # on a heatmap so the opaque white rectangle masks the cell label
    # underneath, leaving only the callout's own text visible.
    if chart_type == "heatmap":
        annotations = [
            (
                replace(a, background="box")
                if isinstance(a, Callout) and a.background == "halo"
                else a
            )
            for a in annotations
        ]

    # Chart types without a meaningful Cartesian y-axis. ``donut`` / ``pie``
    # have no axes at all -- every rule-style annotation pins against a
    # phantom axis and produces a bizarre stray frame around an
    # otherwise-correct chart. ``bullet`` has a quantitative x but a
    # categorical y (one row per measure) -- HLine and Band(y1,y2)
    # don't make sense here while VLine and Band(x1,x2) do, but the
    # current Callout / PointHighlight / PointLabel paths assume a
    # numeric y-axis so they break too. ``profile`` (yield curve, vol
    # smile) is intentionally NOT in this list: it has both Cartesian
    # axes and the existing annotations work.
    _NON_CARTESIAN_CHART_TYPES = {"donut", "pie", "bullet"}
    _RULE_ANNOTATIONS = (HLine, VLine, Band, Callout, PointHighlight, PointLabel)
    if chart_type in _NON_CARTESIAN_CHART_TYPES:
        suppressed = [
            type(a).__name__ for a in annotations
            if isinstance(a, _RULE_ANNOTATIONS)
        ]
        if suppressed:
            logger.warning(
                "[render_annotations] Suppressing %d rule-style "
                "annotation(s) on '%s' chart (no Cartesian y-axis): %s",
                len(suppressed), chart_type, suppressed,
            )
        annotations = [
            a for a in annotations if not isinstance(a, _RULE_ANNOTATIONS)
        ]
        if not annotations:
            return chart

    is_dual_axis = bool(mapping.get("dual_axis_series"))
    dual_axis_config: Dict[str, Any] = mapping.get("dual_axis_config") or {}

    # ---- Trendline on dual-axis: declared unsupported, drop silently ----
    # Trendline.to_layer wires a transform_regression against the
    # ORIGINAL ``mapping['x']`` / ``mapping['y']`` field names, which on
    # dual-axis no longer exist as columns (the builder renamed them to
    # safe per-side fields). The resulting spec passes Altair's
    # validators but explodes inside Vega-Lite at PNG render time
    # (``Cannot read properties of undefined (reading 'marktype')``).
    # Skill ``chart_context.md`` §9.3 already routes PRISM toward
    # building per-series single-axis charts and combining via
    # ``make_2pack_vertical()``; the engine matches that contract by
    # dropping the annotation cleanly with a logger warning rather
    # than crashing the render.
    if is_dual_axis:
        trendlines = [a for a in annotations if isinstance(a, Trendline)]
        if trendlines:
            logger.warning(
                "[render_annotations] Suppressed %d Trendline annotation"
                "(s) on a dual-axis chart -- Trendline is not supported "
                "on dual-axis ``multi_line``. Build a single-axis chart "
                "per series and combine via ``make_2pack_vertical()`` "
                "instead.",
                len(trendlines),
            )
            annotations = [a for a in annotations if not isinstance(a, Trendline)]
            if not annotations:
                return chart

    # ---- horizontal-layout detection -----------------------------------
    # On horizontal-bar (and any chart whose value axis is x and whose
    # category axis is y), an ``HLine`` is semantically a "threshold on
    # the value axis" -- which renders as a vertical rule. Swap HLines
    # for VLines and Band(y1,y2) for Band(x1,x2) so they encode against
    # the right scale.
    _y_field_check = mapping.get("y")
    _x_field_check = mapping.get("x")
    is_horizontal_layout = (
        not is_dual_axis
        and isinstance(_y_field_check, str)
        and isinstance(_x_field_check, str)
        and _y_field_check in df.columns
        and _x_field_check in df.columns
        and not pd.api.types.is_numeric_dtype(df[_y_field_check])
        and pd.api.types.is_numeric_dtype(df[_x_field_check])
    )
    if is_horizontal_layout:
        rotated: List[Annotation] = []
        for ann in annotations:
            if isinstance(ann, HLine):
                rotated.append(VLine(
                    x=ann.y, label=ann.label, color=ann.color,
                    stroke_width=ann.stroke_width,
                    stroke_dash=list(ann.stroke_dash),
                    style=ann.style, label_color=ann.label_color,
                ))
            elif isinstance(ann, Band) and ann.y1 is not None and ann.y2 is not None:
                rotated.append(Band(
                    x1=ann.y1, x2=ann.y2,
                    label=ann.label, color=ann.color, opacity=ann.opacity,
                    label_color=ann.label_color,
                ))
            else:
                rotated.append(ann)
        annotations = rotated

    # ---- compute y-domain & re-encode base chart (single-axis only) ----
    clamped_domain: Optional[List[float]] = None
    y_field = mapping.get("y")
    if (
        y_field
        and y_field in df.columns
        and pd.api.types.is_numeric_dtype(df[y_field])
    ):
        v_min = float(df[y_field].min())
        v_max = float(df[y_field].max())

        # Stacked charts (bar / area with a color column and stack != False)
        # render bars whose visible top is the SUM of stacked values per
        # x-category, not the max single value. Without this, an HLine
        # annotation re-encodes the y-axis to ``[v_min, v_max]`` based on
        # the raw column, clipping stacked totals (e.g. NA = 100 + 50 = 150
        # gets clamped at the raw max of 100). Compute positive- and
        # negative-stack sums separately so mixed-sign stacks (gains +
        # losses on the same bar) also render correctly.
        #
        # CRITICAL: only stacking chart types should hit this path.
        # ``multi_line`` and ``timeseries`` also have ``color`` set but the
        # series overlay (they don't sum), so the stacked-total math would
        # incorrectly inflate v_max to the per-x sum across series. That
        # manifested as squashed indexed-performance charts where adding any
        # annotation (e.g. ``HLine(y=100)``) re-stretched the y-axis to
        # ``[~v_min - 0.18*range, ~v_max + 1.0*range]`` and pushed all the
        # actual lines into the bottom third.
        x_field = mapping.get("x")
        color_field = mapping.get("color")
        stacking_chart_types = {"bar", "bar_horizontal", "area"}
        is_stacked = (
            chart_type in stacking_chart_types
            and color_field
            and color_field in df.columns
            and mapping.get("stack") is not False
            and isinstance(x_field, str)
            and x_field in df.columns
            and x_field != y_field
        )
        if is_stacked:
            try:
                pos = df[df[y_field] > 0]
                neg = df[df[y_field] < 0]
                if len(pos) > 0:
                    v_max = max(v_max, float(
                        pos.groupby(x_field)[y_field].sum().max()
                    ))
                if len(neg) > 0:
                    v_min = min(v_min, float(
                        neg.groupby(x_field)[y_field].sum().min()
                    ))
            except Exception:  # noqa: BLE001
                pass
            v_range = v_max - v_min
            padding_y = (
                v_range * 0.10
                if v_range > 0
                else (abs(v_max) * 0.10 if v_max != 0 else 1.0)
            )
            clamped_domain = [v_min - padding_y, v_max + padding_y]
        else:
            # Non-stacking single-axis charts re-use the same auto-domain
            # logic as the original ``_build_timeseries`` path so adding an
            # annotation doesn't loosen the y-axis. (Without this, the
            # 10% padding below stretched to nice tick boundaries via
            # Vega-Lite, dragging zero into view on indexed-performance
            # charts whose data starts well above zero.)
            d_lo, d_hi = calculate_y_axis_domain(
                df[y_field], handle_outliers=False, prevent_zero_start=True,
            )
            clamped_domain = [float(d_lo), float(d_hi)]

        if not is_dual_axis:
            y_title_override = mapping.get("y_title")
            y_display = (
                y_title_override
                if y_title_override
                else _format_label(y_field, mapping, "y")
            )
            chart = chart.encode(
                y=alt.Y(
                    y_field,
                    type="quantitative",
                    scale=alt.Scale(domain=clamped_domain),
                    title=y_display,
                )
            )

    # ---- legend suppression when LastValueLabel is present --------------
    # ``LastValueLabel`` puts the series name at the end of each line, so
    # the matching legend would be redundant. Re-encode the base chart's
    # color channel with ``legend=None``, preserving the active skin's
    # categorical palette via ``_get_color_scale``. Dual-axis charts
    # never reach this branch with LVL because ``make_chart`` strips
    # LVL annotations on dual-axis before render_annotations runs;
    # ``not is_dual_axis`` is kept as a defensive backstop.
    if any(isinstance(a, LastValueLabel) for a in annotations):
        color_field = mapping.get("color")
        if (
            color_field
            and color_field in df.columns
            and not is_dual_axis
            and not isinstance(chart, alt.LayerChart)
        ):
            try:
                chart = chart.encode(
                    color=alt.Color(
                        f"{color_field}:N",
                        scale=_resolve_categorical_color_scale(
                            mapping, skin_config, color_field, df,
                        ),
                        legend=None,
                    )
                )
            except Exception:  # noqa: BLE001
                pass

    layers: List[alt.Chart] = [chart]

    # ---- VLine same-x dedup (runs BEFORE right-edge reject + stagger so
    # ----  duplicates collapse to a single rule before downstream passes
    # ----  treat the survivors) ------------------------------------------
    annotations = _dedup_vlines_by_x(annotations, df, mapping)

    # ---- right-edge VLine reject (runs BEFORE staggering so a clustered
    # ----  labeled VLine in the right-edge zone doesn't have its label
    # ----  extracted into a surviving PointLabel) -----------------------
    annotations = _drop_right_edge_vlines(annotations, df, mapping)

    # ---- auto-stagger ---------------------------------------------------
    # ``chart_width`` is the per-panel plot width passed by the caller
    # (real cell width in composites, the standalone preset elsewhere);
    # default to the ``wide`` preset (700px) when the caller hasn't
    # threaded one through.
    panel_width_px = int(chart_width) if chart_width else 700
    panel_height_px = int(chart_height) if chart_height else 350
    annotations = _auto_stagger_band_labels(annotations, df, mapping, clamped_domain)
    annotations = _auto_stagger_vline_labels(
        annotations, df, mapping, clamped_domain, chart_width_px=panel_width_px
    )
    annotations = _auto_stagger_hline_labels(
        annotations, df, mapping, clamped_domain, chart_height_px=panel_height_px
    )
    annotations = _auto_stagger_pointlabels(
        annotations, df, mapping, chart_width_px=panel_width_px
    )
    annotations = _auto_stagger_callouts(
        annotations, df=df, mapping=mapping, chart_height_px=panel_height_px
    )
    annotations = _flip_hline_label_inside_band(annotations)

    for annotation in annotations:
        # ---- drop universally-obvious HLines (context-aware) ----------
        # Only the canonical regime thresholds (y=50 for PMI / ISM /
        # diffusion, y=2.0 for Fed inflation target) are "obvious" --
        # and only when the chart's y-axis is actually plotting that
        # series. Gate every suppression on y_title keywords so a
        # legitimate y=50 line on a revenue chart or a y=2 line on a
        # yield chart passes through unchanged.
        if isinstance(annotation, HLine):
            try:
                hline_val = float(annotation.y)
            except (TypeError, ValueError):
                hline_val = None
            label_lower = (annotation.label or "").lower()
            y_title_lower = (mapping.get("y_title") or "").lower()
            # y=50 + PMI/ISM context -- but only suppress when the label
            # references the canonical expansion-contraction concept.
            # A user passing label='Q1 capacity threshold' on a PMI
            # chart obviously wants it shown.
            if (
                hline_val == 50.0
                and any(
                    k in y_title_lower
                    for k in ("pmi", "ism", "diffusion")
                )
                and any(
                    k in label_lower
                    for k in (
                        "expansion", "contraction", "neutral",
                        "50 line", "50-line", "boom", "bust",
                    )
                )
            ):
                logger.warning(
                    "Suppressed HLine(y=50) on PMI/ISM/diffusion: "
                    "expansion-contraction threshold is universally "
                    "known."
                )
                continue
            # y=2 + CPI/inflation context -- but only when the label
            # mentions Fed / target / 2% explicitly. A custom 2% line
            # (e.g. label='Q1 target') passes through.
            if (
                hline_val == 2.0
                and any(
                    k in y_title_lower
                    for k in (
                        "cpi", "core pce", "inflation", "yoy",
                    )
                )
                and any(
                    k in label_lower
                    for k in (
                        "fed", "ecb", "boe", "policy target",
                        "2% target", "2 pct target",
                    )
                )
            ):
                logger.warning(
                    "Suppressed HLine(y=2) on inflation chart: "
                    "Fed 2%% target is universally known."
                )
                continue

        # ---- drop identity-line / "45 degree" Segments on scatter -------
        # Common PRISM anti-pattern: passing
        # ``Segment(x1=v, y1=v, x2=w, y2=w)`` to draw a "y = x" reference
        # on a macro / rates scatter. The axes are typically in different
        # units (basis points vs %, dollars vs index points), so the line
        # has no analytical meaning AND the endpoints often extend outside
        # the data range, stretching the chart frame and creating large
        # blocks of whitespace. Drop the segment and any label silently;
        # if a regression line is wanted, use ``Trendline`` (or
        # ``mapping['trendline']=True``) instead.
        if (
            isinstance(annotation, Segment)
            and chart_type in {"scatter", "scatter_multi"}
        ):
            try:
                seg_x1 = _to_numeric_x(annotation.x1)
                seg_x2 = _to_numeric_x(annotation.x2)
                seg_y1 = float(annotation.y1)
                seg_y2 = float(annotation.y2)
            except (TypeError, ValueError):
                seg_x1 = seg_x2 = seg_y1 = seg_y2 = None
            if (
                seg_x1 is not None and seg_x2 is not None
                and seg_y1 is not None and seg_y2 is not None
                and seg_x1 == seg_y1 and seg_x2 == seg_y2
            ):
                logger.warning(
                    "Suppressed identity-line Segment on %s (x1==y1, "
                    "x2==y2)%s: a 'y=x' reference line on a macro / "
                    "rates scatter has no analytical meaning -- the axes "
                    "are typically in different units. Use Trendline "
                    "(or mapping['trendline']=True) for a regression "
                    "overlay instead.",
                    chart_type,
                    f" with label {annotation.label!r}" if annotation.label else "",
                )
                continue

        # ---- drop Segments whose y-endpoints fall outside the visible
        # y-axis domain (mirrors the HLine out-of-range filter below and
        # the existing dual-axis Segment check). Without this, Vega-Lite's
        # shared y-scale takes the union of the base data range and the
        # Segment's line_df y values, stretching the chart frame to
        # include the offending endpoint and producing large blocks of
        # whitespace. ``mark_rule(clip=True)`` clips PIXELS but does not
        # remove the data point from the scale-resolution union, so an
        # explicit drop is required.
        if (
            isinstance(annotation, Segment)
            and not is_dual_axis
            and clamped_domain is not None
        ):
            try:
                seg_y1 = float(annotation.y1)
                seg_y2 = float(annotation.y2)
            except (TypeError, ValueError):
                seg_y1 = seg_y2 = None
            if seg_y1 is not None and seg_y2 is not None:
                lo, hi = clamped_domain[0], clamped_domain[1]
                out_y1 = seg_y1 < lo or seg_y1 > hi
                out_y2 = seg_y2 < lo or seg_y2 > hi
                if out_y1 or out_y2:
                    which = (
                        "both endpoints" if (out_y1 and out_y2) else "one endpoint"
                    )
                    logger.warning(
                        "Suppressed Segment with %s outside the visible "
                        "y-axis domain [%g, %g]: y1=%g, y2=%g. Endpoints "
                        "outside the data range stretch the chart frame "
                        "and create whitespace; use Segment endpoints "
                        "inside the y range or rely on HLine for "
                        "full-axis horizontal lines.",
                        which, lo, hi, seg_y1, seg_y2,
                    )
                    continue

        # ---- helper: which y-domain governs this annotation's bounds ----
        # On a dual-axis chart, ``clamped_domain`` is the MERGED y-range
        # (LEFT data + RIGHT data stacked together in long format). An
        # annotation tagged ``axis='right'`` whose y values fall above
        # the LEFT range but inside the RIGHT range should NOT be
        # dropped; conversely, ``axis='left'`` values inside the merged
        # range but above the LEFT range alone should be dropped.
        # This helper picks the per-side domain when the chart is
        # dual-axis and ``dual_axis_config`` is populated, else falls
        # back to ``clamped_domain``.
        def _ann_y_domain() -> Optional[List[float]]:
            if is_dual_axis and dual_axis_config:
                ax = getattr(annotation, "axis", "left")
                side_key = (
                    "y_domain_right" if ax == "right" else "y_domain_left"
                )
                d = dual_axis_config.get(side_key)
                if d is not None:
                    return [
                        float(min(d[0], d[1])),
                        float(max(d[0], d[1])),
                    ]
            return clamped_domain

        # ---- out-of-range filtering: HLine ------------------------------
        if isinstance(annotation, HLine):
            if annotation.axis == "right" and dual_axis_config:
                right_domain = dual_axis_config.get("y_domain_right")
                if right_domain is not None:
                    lo = min(right_domain[0], right_domain[1])
                    hi = max(right_domain[0], right_domain[1])
                    if annotation.y < lo or annotation.y > hi:
                        continue
            elif clamped_domain is not None:
                if annotation.y < clamped_domain[0] or annotation.y > clamped_domain[1]:
                    continue

        # ---- out-of-range filtering: VLine ------------------------------
        # The right-most 5% reject for VLine runs upstream in
        # ``_drop_right_edge_vlines`` (called BEFORE the auto-stagger
        # pass) so that a clustered labeled VLine in the right-edge zone
        # doesn't have its label extracted into a surviving PointLabel.
        # This block keeps the OUT-OF-RANGE drop only -- VLines whose x
        # sits outside the data range plus 10% padding would stretch the
        # x scale and create whitespace.
        if isinstance(annotation, VLine):
            x_col = mapping.get("x", "x")
            if x_col in df.columns:
                try:
                    if pd.api.types.is_datetime64_any_dtype(df[x_col]):
                        vline_val = pd.Timestamp(annotation.x)
                        x_min_val = df[x_col].min()
                        x_max_val = df[x_col].max()
                        x_range_td = x_max_val - x_min_val
                        x_pad_td = (
                            x_range_td * 0.10
                            if x_range_td.total_seconds() > 0
                            else pd.Timedelta(days=1)
                        )
                        if (
                            vline_val < (x_min_val - x_pad_td)
                            or vline_val > (x_max_val + x_pad_td)
                        ):
                            continue
                    elif pd.api.types.is_numeric_dtype(df[x_col]):
                        vline_val = float(annotation.x)
                        x_min_val = float(df[x_col].min())
                        x_max_val = float(df[x_col].max())
                        x_range_val = x_max_val - x_min_val
                        x_pad_val = (
                            x_range_val * 0.10
                            if x_range_val > 0
                            else (abs(x_max_val) * 0.10 if x_max_val != 0 else 1.0)
                        )
                        if (
                            vline_val < (x_min_val - x_pad_val)
                            or vline_val > (x_max_val + x_pad_val)
                        ):
                            continue
                except Exception:  # noqa: BLE001
                    # If we can't parse, fall through and let it render.
                    pass

        # ---- out-of-range filtering: Band -------------------------------
        # A Band whose edges extend beyond the visible plot domain forces
        # Vega-Lite's shared scale to grow to include the offending edge,
        # stretching the chart canvas (often pushing the title up to make
        # room for the over-extended shaded zone). For HORIZONTAL bands
        # (y1, y2 set) the strict rule mirrors Segment / HLine: drop if
        # EITHER edge falls outside the y-axis domain. For VERTICAL bands
        # (x1, x2 set) keep the looser "entirely outside" rule -- vertical
        # bands intentionally extending past the data on x are a
        # legitimate pattern (forecast / forward window).
        if isinstance(annotation, Band):
            band_y_drop = False
            band_y_reason = ""
            band_y_domain = _ann_y_domain()
            if (
                annotation.y1 is not None
                and annotation.y2 is not None
                and band_y_domain is not None
            ):
                try:
                    y1_val = float(annotation.y1)
                    y2_val = float(annotation.y2)
                    lo, hi = band_y_domain[0], band_y_domain[1]
                    # 10% padding tolerance (mirrors Callout / PointLabel /
                    # PointHighlight) so a band edge marginally beyond the
                    # data's natural padding doesn't fire on visually-fine
                    # cases. Segment uses strict bounds because Segment is
                    # a line (clipping changes meaning); Band / Arrow get
                    # the same point-style 10% tolerance.
                    domain_range = hi - lo
                    pad_y = domain_range * 0.10 if domain_range > 0 else 1.0
                    out_y1 = y1_val < (lo - pad_y) or y1_val > (hi + pad_y)
                    out_y2 = y2_val < (lo - pad_y) or y2_val > (hi + pad_y)
                    if out_y1 or out_y2:
                        band_y_drop = True
                        which = (
                            "both edges" if (out_y1 and out_y2) else "one edge"
                        )
                        band_y_reason = (
                            f"horizontal Band with {which} outside the visible "
                            f"y-axis domain [{lo:g}, {hi:g}] (10% tolerance): "
                            f"y1={y1_val:g}, y2={y2_val:g}"
                        )
                except (TypeError, ValueError):
                    pass
            band_x_drop = False
            band_x_reason = ""
            if (
                annotation.x1 is not None
                and annotation.x2 is not None
            ):
                x_col = mapping.get("x", "x")
                if x_col in df.columns:
                    try:
                        if pd.api.types.is_datetime64_any_dtype(df[x_col]):
                            x1_val = pd.Timestamp(annotation.x1)
                            x2_val = pd.Timestamp(annotation.x2)
                            x_min_val = df[x_col].min()
                            x_max_val = df[x_col].max()
                            band_lo_x = min(x1_val, x2_val)
                            band_hi_x = max(x1_val, x2_val)
                            if (
                                band_hi_x < x_min_val
                                or band_lo_x > x_max_val
                            ):
                                band_x_drop = True
                                band_x_reason = (
                                    f"vertical Band entirely outside the "
                                    f"visible x range: x1={annotation.x1}, "
                                    f"x2={annotation.x2}"
                                )
                        elif pd.api.types.is_numeric_dtype(df[x_col]):
                            x1_val = float(annotation.x1)
                            x2_val = float(annotation.x2)
                            x_min_val = float(df[x_col].min())
                            x_max_val = float(df[x_col].max())
                            band_lo_x = min(x1_val, x2_val)
                            band_hi_x = max(x1_val, x2_val)
                            if (
                                band_hi_x < x_min_val
                                or band_lo_x > x_max_val
                            ):
                                band_x_drop = True
                                band_x_reason = (
                                    f"vertical Band entirely outside the "
                                    f"visible x range: x1={x1_val:g}, "
                                    f"x2={x2_val:g}"
                                )
                    except (TypeError, ValueError):
                        pass
            if band_y_drop or band_x_drop:
                reason = band_y_reason or band_x_reason
                logger.warning(
                    "Suppressed %s. Out-of-range Band edges stretch the "
                    "chart frame and push the title up; clamp band "
                    "endpoints to the visible data range, or use HLine / "
                    "VLine for full-axis rules.",
                    reason,
                )
                continue

        # ---- out-of-range filtering: Callout ----------------------------
        # Off-data Callouts (e.g. x in the future, y far above data)
        # stretch the canvas the same way an off-data Band does. Suppress
        # when EITHER coordinate falls clearly outside the plot domain.
        if isinstance(annotation, Callout):
            callout_outside = False
            callout_y_domain = _ann_y_domain()
            if callout_y_domain is not None and annotation.y is not None:
                try:
                    cy = float(annotation.y)
                    domain_range = callout_y_domain[1] - callout_y_domain[0]
                    pad_y = domain_range * 0.10 if domain_range > 0 else 1.0
                    if (
                        cy < (callout_y_domain[0] - pad_y)
                        or cy > (callout_y_domain[1] + pad_y)
                    ):
                        callout_outside = True
                except (TypeError, ValueError):
                    pass
            if not callout_outside and annotation.x is not None:
                x_col = mapping.get("x", "x")
                if x_col in df.columns:
                    try:
                        if pd.api.types.is_datetime64_any_dtype(df[x_col]):
                            cx = pd.Timestamp(annotation.x)
                            x_min_val = df[x_col].min()
                            x_max_val = df[x_col].max()
                            x_range_td = x_max_val - x_min_val
                            x_pad_td = (
                                x_range_td * 0.10
                                if x_range_td.total_seconds() > 0
                                else pd.Timedelta(days=1)
                            )
                            if (
                                cx < (x_min_val - x_pad_td)
                                or cx > (x_max_val + x_pad_td)
                            ):
                                callout_outside = True
                        elif pd.api.types.is_numeric_dtype(df[x_col]):
                            cx = float(annotation.x)
                            x_min_val = float(df[x_col].min())
                            x_max_val = float(df[x_col].max())
                            x_range_val = x_max_val - x_min_val
                            x_pad_val = (
                                x_range_val * 0.10
                                if x_range_val > 0
                                else (
                                    abs(x_max_val) * 0.10
                                    if x_max_val != 0 else 1.0
                                )
                            )
                            if (
                                cx < (x_min_val - x_pad_val)
                                or cx > (x_max_val + x_pad_val)
                            ):
                                callout_outside = True
                    except (TypeError, ValueError):
                        pass
            if callout_outside:
                logger.warning(
                    "[render_annotations] Suppressing Callout outside "
                    "the visible data range: x=%s y=%s label=%r",
                    annotation.x, annotation.y, annotation.label,
                )
                continue

        # ---- out-of-range filtering: Arrow ------------------------------
        # An Arrow with either endpoint outside the visible y-axis domain
        # forces Vega-Lite's shared y-scale to expand and include the
        # offending coordinate, stretching the chart frame and pushing
        # the title up. 10% padding tolerance (mirrors Callout / Band)
        # avoids firing on annotations that just nudge past the data's
        # natural padding. Single-axis only (Arrow has no `axis` field).
        if isinstance(annotation, Arrow):
            arrow_y_domain = _ann_y_domain()
            try:
                arr_y1 = float(annotation.y1)
                arr_y2 = float(annotation.y2)
            except (TypeError, ValueError):
                arr_y1 = arr_y2 = None
            if (
                arr_y1 is not None
                and arr_y2 is not None
                and arrow_y_domain is not None
            ):
                lo, hi = arrow_y_domain[0], arrow_y_domain[1]
                domain_range = hi - lo
                pad_y = domain_range * 0.10 if domain_range > 0 else 1.0
                out_y1 = arr_y1 < (lo - pad_y) or arr_y1 > (hi + pad_y)
                out_y2 = arr_y2 < (lo - pad_y) or arr_y2 > (hi + pad_y)
                if out_y1 or out_y2:
                    which = (
                        "both endpoints" if (out_y1 and out_y2) else "one endpoint"
                    )
                    logger.warning(
                        "Suppressed Arrow with %s outside the visible "
                        "y-axis domain [%g, %g] (10%% tolerance): y1=%g, "
                        "y2=%g. Endpoints outside the data range stretch "
                        "the chart frame and push the title up; clamp "
                        "Arrow endpoints to the visible y range.",
                        which, lo, hi, arr_y1, arr_y2,
                    )
                    continue

        # ---- out-of-range filtering: PointLabel -------------------------
        # PointLabel pins floating text to a (x, y) data coordinate; if
        # the data coord falls outside the visible plot domain the chart
        # canvas grows to include it (the dx/dy pixel offsets do NOT
        # extend the frame, only the underlying x/y data coord does).
        # Mirrors Callout's 10%-padding rule for off-data points.
        if isinstance(annotation, PointLabel):
            pl_outside = False
            pl_y_domain = _ann_y_domain()
            if pl_y_domain is not None and annotation.y is not None:
                try:
                    py = float(annotation.y)
                    domain_range = pl_y_domain[1] - pl_y_domain[0]
                    pad_y = domain_range * 0.10 if domain_range > 0 else 1.0
                    if (
                        py < (pl_y_domain[0] - pad_y)
                        or py > (pl_y_domain[1] + pad_y)
                    ):
                        pl_outside = True
                except (TypeError, ValueError):
                    pass
            if not pl_outside and annotation.x is not None:
                x_col = mapping.get("x", "x")
                if x_col in df.columns:
                    try:
                        if pd.api.types.is_datetime64_any_dtype(df[x_col]):
                            px = pd.Timestamp(annotation.x)
                            x_min_val = df[x_col].min()
                            x_max_val = df[x_col].max()
                            x_range_td = x_max_val - x_min_val
                            x_pad_td = (
                                x_range_td * 0.10
                                if x_range_td.total_seconds() > 0
                                else pd.Timedelta(days=1)
                            )
                            if (
                                px < (x_min_val - x_pad_td)
                                or px > (x_max_val + x_pad_td)
                            ):
                                pl_outside = True
                        elif pd.api.types.is_numeric_dtype(df[x_col]):
                            px = float(annotation.x)
                            x_min_val = float(df[x_col].min())
                            x_max_val = float(df[x_col].max())
                            x_range_val = x_max_val - x_min_val
                            x_pad_val = (
                                x_range_val * 0.10
                                if x_range_val > 0
                                else (
                                    abs(x_max_val) * 0.10
                                    if x_max_val != 0 else 1.0
                                )
                            )
                            if (
                                px < (x_min_val - x_pad_val)
                                or px > (x_max_val + x_pad_val)
                            ):
                                pl_outside = True
                    except (TypeError, ValueError):
                        pass
            if pl_outside:
                logger.warning(
                    "Suppressed PointLabel outside the visible data "
                    "range: x=%s y=%s label=%r. Off-data points stretch "
                    "the chart frame.",
                    annotation.x, annotation.y, annotation.label,
                )
                continue

        # ---- out-of-range filtering: PointHighlight ---------------------
        # PointHighlight pins a filled marker at a (x, y) data coord with
        # optional axis='right' for dual-axis routing. Drop when the
        # coord falls outside the visible domain (10% padding, mirrors
        # Callout / PointLabel) so an off-data marker can't stretch the
        # chart frame.
        if isinstance(annotation, PointHighlight):
            ph_outside = False
            ph_y_domain = _ann_y_domain()
            if annotation.y is not None and ph_y_domain is not None:
                try:
                    pyv = float(annotation.y)
                    lo, hi = ph_y_domain[0], ph_y_domain[1]
                    pad_y = (
                        (hi - lo) * 0.10
                        if hi > lo
                        else max(abs(hi), 1.0) * 0.10
                    )
                    if pyv < (lo - pad_y) or pyv > (hi + pad_y):
                        ph_outside = True
                except (TypeError, ValueError):
                    pass
            if not ph_outside and annotation.x is not None:
                x_col = mapping.get("x", "x")
                if x_col in df.columns:
                    try:
                        if pd.api.types.is_datetime64_any_dtype(df[x_col]):
                            pxv = pd.Timestamp(annotation.x)
                            x_min_val = df[x_col].min()
                            x_max_val = df[x_col].max()
                            x_range_td = x_max_val - x_min_val
                            x_pad_td = (
                                x_range_td * 0.10
                                if x_range_td.total_seconds() > 0
                                else pd.Timedelta(days=1)
                            )
                            if (
                                pxv < (x_min_val - x_pad_td)
                                or pxv > (x_max_val + x_pad_td)
                            ):
                                ph_outside = True
                        elif pd.api.types.is_numeric_dtype(df[x_col]):
                            pxv = float(annotation.x)
                            x_min_val = float(df[x_col].min())
                            x_max_val = float(df[x_col].max())
                            x_range_val = x_max_val - x_min_val
                            x_pad_val = (
                                x_range_val * 0.10
                                if x_range_val > 0
                                else (
                                    abs(x_max_val) * 0.10
                                    if x_max_val != 0 else 1.0
                                )
                            )
                            if (
                                pxv < (x_min_val - x_pad_val)
                                or pxv > (x_max_val + x_pad_val)
                            ):
                                ph_outside = True
                    except (TypeError, ValueError):
                        pass
            if ph_outside:
                logger.warning(
                    "Suppressed PointHighlight outside the visible data "
                    "range: x=%s y=%s axis=%s. Off-data markers stretch "
                    "the chart frame.",
                    annotation.x, annotation.y, annotation.axis,
                )
                continue

        # ---- dual-axis HLine encoded against right y-field --------------
        if isinstance(annotation, HLine) and is_dual_axis and dual_axis_config:
            y_field_name = (
                dual_axis_config.get("y_field_right")
                if annotation.axis == "right"
                else dual_axis_config.get("y_field_left")
            )
            domain = (
                dual_axis_config.get("y_domain_right")
                if annotation.axis == "right"
                else dual_axis_config.get("y_domain_left")
            )
            if y_field_name:
                if domain is not None:
                    lo = min(domain[0], domain[1])
                    hi = max(domain[0], domain[1])
                    if annotation.y < lo or annotation.y > hi:
                        continue

                # Boundary-aware label dy on the left axis: when the line
                # sits near the top of the plot, flip the label *below* the
                # rule so it stays inside the chart frame instead of clipping
                # against the title band.
                if annotation.axis == "left" and clamped_domain is not None:
                    domain_range = clamped_domain[1] - clamped_domain[0]
                    if annotation.y > (clamped_domain[1] - domain_range * 0.10):
                        annotation._label_dy = 12

                # When this HLine is appended back into the inner dual-axis
                # LayerChart with ``resolve_scale(y='independent')``, each
                # layer would otherwise compute its own scale from its own
                # data (a single value), placing the rule somewhere bogus.
                # Encode the HLine with the EXACT same scale domain and
                # orient as the side it belongs to so it aligns with that
                # axis's tick positions exactly.
                axis_orient = "right" if annotation.axis == "right" else "left"
                hline_scale = (
                    alt.Scale(domain=list(domain))
                    if domain is not None
                    else alt.Scale()
                )
                line_df = pd.DataFrame({y_field_name: [annotation.y]})
                hline_layer = (
                    alt.Chart(line_df)
                    .mark_rule(
                        color=annotation.color,
                        strokeWidth=annotation.stroke_width,
                        strokeDash=annotation.stroke_dash,
                        clip=True,
                    )
                    .encode(
                        y=alt.Y(
                            f"{y_field_name}:Q",
                            scale=hline_scale,
                            axis=alt.Axis(
                                orient=axis_orient, title=None,
                                labels=False, ticks=False, domain=False,
                            ),
                        )
                    )
                )
                if annotation.label:
                    text_color = annotation.label_color or annotation.color
                    text_y_enc = alt.Y(
                        f"{y_field_name}:Q",
                        scale=hline_scale,
                        axis=alt.Axis(
                            orient=axis_orient, title=None,
                            labels=False, ticks=False, domain=False,
                        ),
                    )
                    if getattr(annotation, "halo", True):
                        halo_layer = (
                            alt.Chart(line_df)
                            .mark_text(
                                align="left",
                                dx=5,
                                dy=annotation._label_dy,
                                fontSize=10,
                                stroke=getattr(annotation, "halo_color", "#FFFFFF"),
                                strokeWidth=getattr(annotation, "halo_width", 4.0),
                                strokeJoin="round",
                                strokeOpacity=1.0,
                                color=getattr(annotation, "halo_color", "#FFFFFF"),
                            )
                            .encode(
                                y=text_y_enc,
                                text=alt.value(annotation.label),
                            )
                        )
                        hline_layer = hline_layer + halo_layer
                    text_layer = (
                        alt.Chart(line_df)
                        .mark_text(
                            align="left",
                            dx=5,
                            dy=annotation._label_dy,
                            fontSize=10,
                            color=text_color,
                        )
                        .encode(
                            y=text_y_enc,
                            text=alt.value(annotation.label),
                        )
                    )
                    hline_layer = hline_layer + text_layer
                layers.append(hline_layer)
                continue

        # ---- HLine label boundary awareness on single-axis charts -------
        # When the rule sits near the top of the plot, flip the label below
        # the line so it doesn't clip against the title band; the default
        # (-8) is "just above the line".
        if isinstance(annotation, HLine) and clamped_domain is not None:
            domain_range = clamped_domain[1] - clamped_domain[0]
            if annotation.y > (clamped_domain[1] - domain_range * 0.10):
                annotation._label_dy = 12

        # ---- dual-axis Segment routed to the right scale ----------------
        # Segment behaves like a (possibly diagonal) HLine: when it's
        # tagged ``axis='right'`` on a dual-axis chart, encode both
        # endpoints against the right y-field/scale so the segment sits
        # on the correct axis.
        if isinstance(annotation, Segment) and is_dual_axis and dual_axis_config:
            y_field_name = (
                dual_axis_config.get("y_field_right")
                if annotation.axis == "right"
                else dual_axis_config.get("y_field_left")
            )
            domain = (
                dual_axis_config.get("y_domain_right")
                if annotation.axis == "right"
                else dual_axis_config.get("y_domain_left")
            )
            if y_field_name and annotation.x1 is not None and annotation.x2 is not None:
                if domain is not None:
                    lo = min(domain[0], domain[1])
                    hi = max(domain[0], domain[1])
                    if (
                        annotation.y1 < lo or annotation.y1 > hi
                        or annotation.y2 < lo or annotation.y2 > hi
                    ):
                        continue
                axis_orient = "right" if annotation.axis == "right" else "left"
                seg_scale = (
                    alt.Scale(domain=list(domain))
                    if domain is not None
                    else alt.Scale()
                )
                x_col_user = mapping.get("x", "x")
                x_col = x_col_user if x_col_user in df.columns else "x"
                x_type = (
                    "temporal"
                    if x_col in df.columns
                    and pd.api.types.is_datetime64_any_dtype(df[x_col])
                    else "quantitative"
                )
                seg_df = pd.DataFrame({
                    x_col: [annotation.x1],
                    y_field_name: [annotation.y1],
                    "_x2": [annotation.x2],
                    "_y2": [annotation.y2],
                })
                seg_layer = (
                    alt.Chart(seg_df)
                    .mark_rule(
                        color=annotation.color,
                        strokeWidth=annotation.stroke_width,
                        strokeDash=annotation.stroke_dash,
                        clip=True,
                    )
                    .encode(
                        x=alt.X(x_col, type=x_type),
                        y=alt.Y(
                            f"{y_field_name}:Q",
                            scale=seg_scale,
                            axis=alt.Axis(
                                orient=axis_orient, title=None,
                                labels=False, ticks=False, domain=False,
                            ),
                        ),
                        x2=alt.X2("_x2"),
                        y2=alt.Y2("_y2"),
                    )
                )
                if annotation.label:
                    if annotation.label_position == "start":
                        lx, ly = annotation.x1, annotation.y1
                    elif annotation.label_position == "middle":
                        if hasattr(annotation.x1, "timestamp") and hasattr(annotation.x2, "timestamp"):
                            mid_ts = (annotation.x1.timestamp() + annotation.x2.timestamp()) / 2.0
                            lx = pd.Timestamp(mid_ts, unit="s")
                        elif isinstance(annotation.x1, (int, float)) and isinstance(annotation.x2, (int, float)):
                            lx = (annotation.x1 + annotation.x2) / 2.0
                        else:
                            lx = annotation.x1
                        ly = (annotation.y1 + annotation.y2) / 2.0
                    else:
                        lx, ly = annotation.x2, annotation.y2
                    label_df = pd.DataFrame({x_col: [lx], y_field_name: [ly]})
                    text_layer = (
                        alt.Chart(label_df)
                        .mark_text(
                            align="left",
                            dx=annotation.label_offset_x,
                            dy=annotation.label_offset_y,
                            fontSize=10,
                            color=annotation.label_color or annotation.color,
                        )
                        .encode(
                            x=alt.X(x_col, type=x_type),
                            y=alt.Y(
                                f"{y_field_name}:Q",
                                scale=seg_scale,
                                axis=alt.Axis(
                                    orient=axis_orient, title=None,
                                    labels=False, ticks=False, domain=False,
                                ),
                            ),
                            text=alt.value(annotation.label),
                        )
                    )
                    seg_layer = seg_layer + text_layer
                layers.append(seg_layer)
                continue

        # ---- dual-axis PointHighlight / Callout routed to right scale ---
        if (
            isinstance(annotation, (PointHighlight, Callout))
            and is_dual_axis
            and dual_axis_config
            and getattr(annotation, "axis", "left") == "right"
        ):
            y_field_name = dual_axis_config.get("y_field_right")
            domain = dual_axis_config.get("y_domain_right")
            if y_field_name:
                if domain is not None:
                    lo = min(domain[0], domain[1])
                    hi = max(domain[0], domain[1])
                    if annotation.y < lo or annotation.y > hi:
                        continue
                seg_scale = (
                    alt.Scale(domain=list(domain))
                    if domain is not None
                    else alt.Scale()
                )
                x_col_user = mapping.get("x", "x")
                x_col = x_col_user if x_col_user in df.columns else "x"
                x_type = (
                    "temporal"
                    if x_col in df.columns
                    and pd.api.types.is_datetime64_any_dtype(df[x_col])
                    else "quantitative"
                )
                pt_df = pd.DataFrame({x_col: [annotation.x], y_field_name: [annotation.y]})

                if isinstance(annotation, PointHighlight):
                    mark_kwargs: Dict[str, Any] = {
                        "shape": annotation.shape,
                        "size": annotation.size,
                        "color": annotation.color,
                        "filled": annotation.filled,
                        "opacity": annotation.opacity,
                    }
                    if annotation.stroke_color is not None:
                        mark_kwargs["stroke"] = annotation.stroke_color
                    if annotation.stroke_width > 0.0:
                        mark_kwargs["strokeWidth"] = annotation.stroke_width
                    pt_layer = (
                        alt.Chart(pt_df)
                        .mark_point(**mark_kwargs)
                        .encode(
                            x=alt.X(x_col, type=x_type),
                            y=alt.Y(
                                f"{y_field_name}:Q",
                                scale=seg_scale,
                                axis=alt.Axis(
                                    orient="right", title=None,
                                    labels=False, ticks=False, domain=False,
                                ),
                            ),
                        )
                    )
                    if annotation.label:
                        text_layer = (
                            alt.Chart(pt_df)
                            .mark_text(
                                align="left", dx=8, dy=-10, fontSize=10,
                                fontWeight="bold",
                                color=annotation.label_color or annotation.color,
                            )
                            .encode(
                                x=alt.X(x_col, type=x_type),
                                y=alt.Y(
                                    f"{y_field_name}:Q",
                                    scale=seg_scale,
                                    axis=alt.Axis(
                                        orient="right", title=None,
                                        labels=False, ticks=False, domain=False,
                                    ),
                                ),
                                text=alt.value(annotation.label),
                            )
                        )
                        pt_layer = pt_layer + text_layer
                    layers.append(pt_layer)
                    continue

                if isinstance(annotation, Callout):
                    text_color = annotation.label_color or annotation.color
                    sub_layers: List[alt.Chart] = []
                    if annotation.background == "halo":
                        halo_layer = (
                            alt.Chart(pt_df)
                            .mark_text(
                                align=annotation.align,
                                baseline="middle",
                                dx=annotation.dx,
                                dy=annotation.dy,
                                fontSize=annotation.font_size,
                                fontWeight=annotation.font_weight,
                                stroke=annotation.background_color,
                                strokeWidth=annotation.halo_width,
                                strokeJoin="round",
                                strokeOpacity=1.0,
                                color=annotation.background_color,
                            )
                            .encode(
                                x=alt.X(x_col, type=x_type),
                                y=alt.Y(
                                    f"{y_field_name}:Q",
                                    scale=seg_scale,
                                    axis=alt.Axis(
                                        orient="right", title=None,
                                        labels=False, ticks=False, domain=False,
                                    ),
                                ),
                                text=alt.value(annotation.label),
                            )
                        )
                        sub_layers.append(halo_layer)
                    text_layer = (
                        alt.Chart(pt_df)
                        .mark_text(
                            align=annotation.align,
                            baseline="middle",
                            dx=annotation.dx,
                            dy=annotation.dy,
                            fontSize=annotation.font_size,
                            fontWeight=annotation.font_weight,
                            color=text_color,
                        )
                        .encode(
                            x=alt.X(x_col, type=x_type),
                            y=alt.Y(
                                f"{y_field_name}:Q",
                                scale=seg_scale,
                                axis=alt.Axis(
                                    orient="right", title=None,
                                    labels=False, ticks=False, domain=False,
                                ),
                            ),
                            text=alt.value(annotation.label),
                        )
                    )
                    sub_layers.append(text_layer)
                    layers.append(sub_layers[0] if len(sub_layers) == 1 else alt.layer(*sub_layers))
                    continue

        # ---- PlotText: routed to OUTSIDE text panels (defensive skip) ---
        # Per the 2026-05-10 outside-only rewire, every PlotText is
        # pulled out of the annotations list by
        # ``_route_plottext_to_panels`` BEFORE this layer pass runs
        # (see the call sites in ``make_chart`` and
        # ``_build_single_chart``). If a PlotText slips through to
        # here, the routing helper was bypassed -- log and skip
        # silently so we don't attempt to render the now-removed
        # inside-anchor layer.
        if isinstance(annotation, PlotText):
            logger.warning(
                "[render_annotations] PlotText reached the layer pass; "
                "should have been routed to outside text panels by "
                "_route_plottext_to_panels. Dropping silently. text=%r",
                annotation.text[:50],
            )
            continue

        # ---- default: delegate to the annotation's own to_layer() -------
        # Stash the actual plot-region pixel dimensions in a SHALLOW COPY
        # of mapping so annotations whose layout depends on pixel space
        # (today: LastValueLabel's bunching detection in to_layer) can
        # convert data->pixels correctly. Annotations that don't need
        # this just ignore the keys. We copy rather than mutate so the
        # caller's mapping dict is never modified out from under them.
        annotation_mapping: Dict[str, Any] = dict(mapping)
        if chart_width is not None:
            annotation_mapping["_chart_width_px"] = chart_width
        if chart_height is not None:
            annotation_mapping["_chart_height_px"] = chart_height
        layer = annotation.to_layer(chart, df, annotation_mapping, skin_config)

        # Dual-axis safety net. Annotations that did not take a
        # dedicated branch above (HLine, Segment, PointHighlight /
        # Callout when axis='right') will have y encodings against the
        # user's ``mapping['y']`` (typically ``"value"``). Splicing
        # those into the dual-axis ``LayerChart`` -- which uses
        # ``resolve_scale(y='independent')`` -- creates an extra,
        # phantom y-axis on the left titled with the field name. Force
        # every field-based y encoding to ride the chosen side's scale
        # with a hidden axis so the layer aligns with the dual-axis
        # side without painting its own axis. ``axis`` defaults to
        # ``"left"`` for annotations without an axis attr (VLine /
        # Arrow / PointLabel / Band(y1, y2)); honors the explicit
        # ``axis`` value on PointHighlight / Callout when
        # ``axis='left'`` (the right-axis case is already handled in
        # the dedicated branch above and ``continue``s past here).
        # ``LastValueLabel`` is excluded as a defensive backstop --
        # ``make_chart`` strips LVL on dual-axis before annotations
        # render, so this isinstance check should never be true here.
        if (
            is_dual_axis
            and dual_axis_config
            and not isinstance(annotation, LastValueLabel)
        ):
            annotation_axis = getattr(annotation, "axis", "left")
            side_domain_key = (
                "y_domain_right" if annotation_axis == "right"
                else "y_domain_left"
            )
            side_domain = dual_axis_config.get(side_domain_key)
            if side_domain is not None:
                side_orient = (
                    "right" if annotation_axis == "right" else "left"
                )
                layer = _rewrite_y_encodings_for_dual_axis(
                    layer, side_domain, side_orient,
                )

        layers.append(layer)

    if len(layers) == 1:
        return layers[0]

    # Special case: when the base chart is itself a LayerChart with a
    # ``resolve_scale`` (dual-axis pattern), wrapping it in an outer
    # ``alt.layer(...)`` collapses both y-axes onto a shared scale. Splice
    # the annotation layers DIRECTLY into the existing inner layer list
    # so the original ``resolve_scale(y='independent')`` keeps applying.
    if (
        is_dual_axis
        and isinstance(chart, alt.LayerChart)
        and getattr(chart, "layer", None) is not None
        and len(layers) > 1
    ):
        try:
            return chart.copy().add_layers(*layers[1:])
        except (AttributeError, TypeError):
            pass
        # Manual fallback for altair versions without ``add_layers``.
        try:
            spec = chart.to_dict()
            extra_specs = [l.to_dict() for l in layers[1:]]
            spec_layers = list(spec.get("layer", []))
            spec_layers.extend(extra_specs)
            spec["layer"] = spec_layers
            return alt.LayerChart.from_dict(spec)
        except Exception:  # noqa: BLE001
            pass
    return alt.layer(*layers)


# ===========================================================================
# MODULE: BEAUTIFY (axis configuration & date formatting)
# ===========================================================================

@dataclass
class AxisConfig:
    """Resolved axis configuration produced by ``get_axis_beautification``."""

    label_angle: int = 0
    label_limit: int = 200
    tick_count: Optional[int] = None
    # When set, used as the temporal ``tickCount`` instead of an int.
    # Shape: ``{"interval": "month", "step": 6}``.
    tick_step: Optional[Dict[str, Any]] = None
    format: Optional[str] = None
    # Vega expression for per-tick label formatting. When set, takes
    # precedence over ``format`` and lets us produce conditional
    # labels (e.g. show date at midnight ticks, time-of-day at other
    # ticks on a multi-day intraday axis). See ``determine_date_format``.
    label_expr: Optional[str] = None
    title: Optional[str] = None
    domain_min: Optional[float] = None
    domain_max: Optional[float] = None
    scale_type: str = "linear"  # 'linear', 'log', 'sqrt'
    # Explicit subset of axis values whose ticks/labels should render.
    # Used to thin a dense ordinal x-axis (profile / yield-curve charts)
    # so labels stop colliding without dropping any of the plotted data.
    tick_values: Optional[List[Any]] = None
    # When set, forces a Vega-Lite ``labelOverlap`` strategy even on
    # nominal / ordinal axes (which the renderer leaves un-thinned by
    # default). ``'greedy'`` drops residual colliding labels.
    label_overlap: Optional[str] = None


@dataclass
class DateFormatConfig:
    """A date-axis format chosen by ``determine_date_format``.

    ``tick_count`` is used as a plain number-of-ticks hint to
    Vega-Lite. ``tick_step`` (when set) is used INSTEAD as an explicit
    temporal interval/step pair like ``{"interval": "month", "step":
    6}`` so Vega-Lite snaps to readable boundaries (semi-annual,
    annual, etc.) rather than picking 6 quarterly ticks for a 17-month
    span when we asked for 4.
    """

    format: Optional[str]
    tick_count: Optional[int]
    label_angle: Optional[int]
    description: str
    tick_step: Optional[Dict[str, Any]] = None
    # Optional Vega expression for conditional per-tick formatting
    # (e.g. multi-day intraday axes that show date at midnight and
    # time elsewhere). When present, the renderer uses this instead
    # of ``format``.
    label_expr: Optional[str] = None


# Static date-format presets keyed by intent. ``determine_date_format`` may
# return one of these directly or build a new ``DateFormatConfig`` with a
# dynamically computed ``label_angle``. ``label_angle=None`` means "let
# the resolver pick the smallest step that fits at angle=0".
#
# House style (NO DIAGONAL TICK LABELS for time-series x-axes -- the
# engine guarantees horizontal labels by coarsening the tick step before
# rotating). Per-bucket conventions:
#
#   - Annual+ stride (every 12+ months): bare ``%Y`` ("2024"). Every
#     tick lands on January, so the "Jan-" prefix is noise.
#   - Sub-annual month-aligned stride (1 / 3 / 6 month step): ``%b %y``
#     ("Mar 24"). Day is dropped because monthly ticks always land on
#     day 1 -- "01 " is noise. House separator is a SPACE (not the
#     hyphen used previously) for visual consistency with the daily
#     formats below.
#   - Sub-monthly stride (week / day): ``%d %b`` ("06 Mar"). Year is
#     dropped because spans <= ~30 days rarely cross calendar years and
#     the chart title / context carries the year anchor. Day is informative
#     (Mondays for ISO-weekly ticks, arbitrary dates for daily ticks).
#   - Intraday: conditional labelExpr -- date at midnight (multi-day)
#     or leftmost tick only (single-session); ``HH:MM`` elsewhere.
#     Default clock ET; ``x_timezone`` override.
#
# Always abbreviate months (``%b`` -> "Jan"), never full month names
# (``%B``), and always 2-digit year (``%y``) when paired with a month.
DATE_FORMAT_PRESETS: Dict[str, DateFormatConfig] = {
    "quarterly": DateFormatConfig(
        format="%b %y",
        tick_count=None,
        label_angle=None,
        description="Semi-annual ticks (span 2-10 years)",
    ),
    "years_few": DateFormatConfig(
        format="%b %y",
        tick_count=None,
        label_angle=None,
        description="Show month-year (span 3-10 years)",
    ),
    "year_month": DateFormatConfig(
        format="%b %y",
        tick_count=12,
        label_angle=None,
        description="Show month and year (span 1-3 years)",
    ),
    "month_year": DateFormatConfig(
        format="%b %y",
        tick_count=None,
        label_angle=None,
        description="Show abbreviated month/year (span 6-12 months)",
    ),
    "month_day": DateFormatConfig(
        format="%d %b",
        tick_count=None,
        label_angle=None,
        description="Show month and day (span 1-6 months)",
    ),
    "day_month": DateFormatConfig(
        format="%d %b",
        tick_count=None,
        label_angle=None,
        description="Show day and month (span < 1 month)",
    ),
    "daily": DateFormatConfig(
        format="%d %b",
        tick_count=None,
        label_angle=None,
        description="Short date (span < 2 weeks)",
    ),
}


def calculate_optimal_label_angle(
    labels: List[str],
    chart_width: int,
    estimated_tick_count: Optional[int] = None,
) -> int:
    """Pick a tick-label rotation angle that avoids horizontal collisions.

    Vega-Lite typically renders ~5-10 ticks regardless of data density, so
    when an explicit ``estimated_tick_count`` is provided we use that for
    spacing math (rather than ``len(labels)``, which over-counts).

    Returns:
        ``0`` (horizontal), ``-45``, or ``-90``.
    """
    if not labels:
        return 0

    max_label_len = max(len(str(l)) for l in labels)
    effective_label_count = estimated_tick_count or min(len(labels), 10)
    space_per_label = chart_width / max(effective_label_count, 1)

    needed_horizontal = max_label_len * 8 + 12
    if needed_horizontal <= space_per_label:
        return 0
    
    # At -45 degrees, parallel labels need ~20px of horizontal pitch to avoid
    # overlapping perpendicularly (assuming ~14px font height).
    if space_per_label >= 20:
        return -45
        
    return -90


# Profile (ordinal-x) tick-label collision avoidance. House rule for
# yield curves / forward curves / vol smiles / cross-sectional profiles:
# tick labels are NEVER vertical -- only horizontal (0) or diagonal (-45).
# When even -45 would collide, the visible tick labels are thinned to an
# evenly-spaced subset (the plotted line keeps every knot point; only the
# label frequency drops).
_PROFILE_LABEL_CHAR_PX = 8          # per-char width at the skin label font
_PROFILE_LABEL_PAD_PX = 12          # inter-label padding when horizontal
_PROFILE_MIN_PITCH_45_PX = 22       # min horizontal pitch for non-overlapping -45 labels
_PROFILE_MIN_HORIZONTAL_TICKS = 8   # keep horizontal while >= this many fit; else rotate to -45
# Heatmap column labels are sparser than profile lines: 2x pitch -> ~half the
# tick count at -45 (intraday 15-min grids stay legible on 700px wide).
_HEATMAP_MIN_PITCH_45_PX = _PROFILE_MIN_PITCH_45_PX * 2


def _evenly_spaced_subset(values: List[Any], k: int) -> List[Any]:
    """Pick ``k`` evenly-spaced items from ``values`` (first + last kept)."""
    n = len(values)
    if k >= n:
        return list(values)
    if k <= 1:
        return [values[0]]
    step = (n - 1) / (k - 1)
    idx = sorted({int(round(i * step)) for i in range(k)})
    return [values[i] for i in idx if 0 <= i < n]


def _resolve_profile_x_order(
    df: pd.DataFrame,
    x_field: str,
    mapping: Dict[str, Any],
) -> List[Any]:
    """Return the profile x categories in display order (actual values).

    Mirrors ``_build_profile_line``'s sort resolution (explicit
    ``mapping['x_sort']`` -> tenor ladder -> relative-time -> ascending)
    but keeps the ORIGINAL data values so an ``axis.values`` subset built
    from this order matches the rendered ordinal domain exactly.
    """
    uniques = [v for v in df[x_field].unique()]
    explicit = mapping.get("x_sort")
    if explicit:
        rank = {v: i for i, v in enumerate(explicit)}
        return sorted(uniques, key=lambda v: rank.get(v, len(rank)))
    if _infer_tenor_sort(uniques) is not None:
        return sorted(uniques, key=lambda v: _tenor_sort_key(str(v).strip().upper()))
    if _infer_relative_time_sort(uniques) is not None:
        return sorted(uniques, key=lambda v: _relative_time_sort_key(v))
    return sorted(uniques, key=lambda v: str(v))


def _profile_ordinal_axis_plan(
    ordered_vals: List[Any],
    chart_width: int,
) -> Tuple[int, Optional[List[Any]]]:
    """Decide ``(label_angle, tick_values)`` for a profile/yield-curve ordinal x.

    House rule: labels are NEVER vertical -- only horizontal (``0``) or
    diagonal (``-45``). Frequency is reduced (an evenly-spaced subset of
    tick labels is shown) only when labels would otherwise collide.

    Ladder:
      1. Every label fits horizontally          -> ``0``, keep all.
      2. A useful number fits horizontally       -> ``0``, thin to fit.
      3. Labels too wide for a useful 0-deg axis  -> ``-45``, keep all.
      4. Even -45 collides                        -> ``-45``, thin to fit.

    Returns ``(angle, values)`` where ``values`` is ``None`` to keep every
    tick label, else the subset of x values whose labels should render.
    """
    vals = [str(v) for v in ordered_vals]
    n = len(vals)
    if n == 0:
        return 0, None
    max_len = max(len(v) for v in vals)
    needed_h = max_len * _PROFILE_LABEL_CHAR_PX + _PROFILE_LABEL_PAD_PX

    horiz_capacity = max(1, int(chart_width // needed_h))
    diag_capacity = max(1, int(chart_width // _PROFILE_MIN_PITCH_45_PX))

    if horiz_capacity >= n:
        return 0, None
    if horiz_capacity >= _PROFILE_MIN_HORIZONTAL_TICKS:
        return 0, _evenly_spaced_subset(ordered_vals, horiz_capacity)
    if diag_capacity >= n:
        return -45, None
    return -45, _evenly_spaced_subset(ordered_vals, diag_capacity)


def detect_label_collision(
    labels: List[str],
    chart_width: int,
    char_width_px: int = 7,
    padding_px: int = 10,
) -> bool:
    """Heuristic check: would these labels collide horizontally?"""
    if len(labels) <= 1:
        return False
    space_per_label = chart_width / len(labels)
    max_label_width = max(len(str(l)) * char_width_px for l in labels)
    return max_label_width + padding_px > space_per_label


def _temporal_tick_step(interval: str, step: int) -> Dict[str, Any]:
    """Build a Vega-Lite ``TimeIntervalStep`` that the renderer actually honours.

    Vega-Lite has a quirk where ``{"interval": "month", "step": N}`` with
    ``N >= 12`` is silently ignored: the tick generator falls back to
    default annual ticks (one per January), producing a wall of crammed
    labels even on a 10-year axis where we asked for ``step: 24``.

    The fix: any month-step >= 12 must be expressed as a year-step. For
    multiples of 12 (the normal case from our ``_step_for_target`` nice
    ladder), that's ``year / (N // 12)``. For non-multiples we round to
    the nearest integer year so behaviour is well-defined for callers
    that bypass the ladder.

    All other intervals (``year``, ``week``, ``day``, ``hour``, ...)
    and sub-12 month steps pass through unchanged.
    """
    if interval == "month" and step >= 12:
        years = max(1, int(round(step / 12)))
        return {"interval": "year", "step": years}
    return {"interval": interval, "step": step}


# Skin axis label font size assumed by tick-spacing math. Matches GS_CLEAN's
# ``config.axis.labelFontSize`` (19). If a smaller skin is introduced, pass
# its label font size into ``_max_ticks_for_width`` so the per-label width
# estimate matches reality.
_DEFAULT_AXIS_LABEL_FONT_SIZE = 18

# Minimum y-axis tick label size for horizontal bars when categories
# outrun cell height (composite sub-charts, dense standalone charts).
_BAR_HORIZONTAL_Y_LABEL_FONT_MIN = 8


def _bar_horizontal_y_label_font_size(
    chart_height: int,
    n_categories: int,
    base_font_size: int = _DEFAULT_AXIS_LABEL_FONT_SIZE,
) -> int:
    """Shrink horizontal-bar y-axis tick labels when rows are packed tight.

    Composite sub-charts (~280px tall) with 18-20 categories leave ~12-14
    px per row at the default 18pt skin label size, which guarantees
    vertical overlap. Scale font size down from ``base_font_size`` so
    each label fits its row budget; floor at
    ``_BAR_HORIZONTAL_Y_LABEL_FONT_MIN``.
    """
    if n_categories <= 0:
        return base_font_size
    # Reserve chrome: sub-chart title, x-axis title, x tick labels.
    usable = max(int(chart_height - 48), int(chart_height * 0.78))
    px_per_row = usable / n_categories
    # One horizontal label row ~= font_size * 1.2 line height + 2px gap.
    fit_font = int((px_per_row - 2) / 1.2)
    if fit_font >= base_font_size:
        return base_font_size
    return max(_BAR_HORIZONTAL_Y_LABEL_FONT_MIN, fit_font)


def _max_ticks_for_width(
    chart_width: int,
    sample_label: str,
    label_angle: int,
    label_font_size: int = _DEFAULT_AXIS_LABEL_FONT_SIZE,
) -> int:
    """Estimate how many ticks comfortably fit inside ``chart_width``.

    Used to cap ``tick_count`` so narrow composite sub-charts don't try
    to draw 12 monthly labels in 300px (which forces 90-deg rotation
    and a wall of crammed labels) AND so wide charts don't render 6+
    quarterly labels squeezed against each other.

    Per-character width scales linearly with ``label_font_size`` because
    Liberation Sans averages ~0.6 * font_size per character at common
    sizes (verified at 14pt and 18pt). The hardcoded ``8 px / char``
    used previously was calibrated for a ~13-14pt axis font and badly
    underestimates the real width at the GS skin's 18pt labels (e.g.
    "Apr-25" is ~66 px wide at 18pt, not the ~48 px the old formula
    implied), causing the engine to ask Vega-Lite for too many ticks.

    Per-label footprint includes generous breathing room (a label feels
    cluttered when neighbours are within ~1.5 character widths even if
    not technically overlapping):

      - Horizontal label  -> ``len * char_w + breathing``.
      - 45-deg label      -> ``len * char_w * 0.7 + breathing``.
      - 90-deg label      -> ``font_size + breathing`` (ascender height).
    """
    n = max(len(str(sample_label)), 1)
    char_w = label_font_size * 0.6
    breathing = max(label_font_size * 1.5, 24)
    if label_angle == 0:
        per = n * char_w + breathing
    elif abs(label_angle) >= 90:
        per = label_font_size + breathing * 0.5
    else:
        per = n * char_w * 0.7 + breathing * 0.6
    return max(int(chart_width // per), 2)


def _pick_tick_count_and_angle(
    chart_width: int,
    sample_label: str,
    desired_max: int,
    desired_min: int = 4,
) -> Tuple[int, int]:
    """Pick (tick_count, label_angle) that prioritises readability.

    Strategy: prefer fewer horizontal labels over many rotated ones.
      1. If at least ``desired_min`` ticks fit horizontally (0-deg),
         pick ``min(desired_max, max_horizontal_ticks)`` and 0 angle.
      2. Else, try 45-deg with up to ``desired_max`` ticks.
      3. Else, fall back to 90-deg with up to ``desired_max`` ticks.

    Returns ``(tick_count, label_angle)``.
    """
    horizontal_max = _max_ticks_for_width(chart_width, sample_label, 0)
    if horizontal_max >= desired_min:
        return min(desired_max, horizontal_max), 0
    diag_max = _max_ticks_for_width(chart_width, sample_label, -45)
    if diag_max >= desired_min:
        return min(desired_max, diag_max), -45
    vertical_max = _max_ticks_for_width(chart_width, sample_label, -90)
    return min(desired_max, vertical_max), -90


def _count_calendar_ticks_in_range(
    min_date: pd.Timestamp,
    max_date: pd.Timestamp,
    tick_step: Optional[Dict[str, Any]],
    tick_count: Optional[Any],
) -> int:
    """Count how many Vega-Lite calendar-aligned tick boundaries land in
    ``[min_date, max_date]``.

    Vega-Lite anchors tick placement to the calendar, not to the data:
    ``{"interval": "year", "step": 1}`` puts ticks at every Jan 1;
    ``{"interval": "month", "step": 6}`` at every Jan and Jul;
    ``{"interval": "year", "step": 2}`` at every other Jan 1
    (years divisible by 2). This helper mirrors that anchoring so the
    engine can verify the chosen tick_step actually produces enough
    visible ticks BEFORE handing the spec to Vega-Lite.

    Best-effort for non-tick_step configs: returns the soft
    ``tick_count`` hint or a coarse estimate.
    """
    if tick_step is None:
        if isinstance(tick_count, int):
            return tick_count
        return 2

    interval = tick_step.get("interval") if isinstance(tick_step, dict) else None
    step = tick_step.get("step", 1) if isinstance(tick_step, dict) else 1
    try:
        step = int(step)
    except (TypeError, ValueError):
        step = 1
    if step < 1:
        step = 1

    if interval == "year":
        count = 0
        for year in range(min_date.year, max_date.year + 1):
            if year % step != 0:
                continue
            tick = pd.Timestamp(year=year, month=1, day=1)
            if min_date <= tick <= max_date:
                count += 1
        return count

    if interval == "month":
        count = 0
        for year in range(min_date.year, max_date.year + 2):
            for month in range(1, 13):
                if (month - 1) % step != 0:
                    continue
                tick = pd.Timestamp(year=year, month=month, day=1)
                if min_date <= tick <= max_date:
                    count += 1
        return count

    if interval == "week":
        # Vega-Lite anchors weekly ticks to ISO week boundaries
        # (Monday). Approximate count by integer division.
        span_days = (max_date - min_date).days
        return max(int(span_days / (7 * step)), 1)

    if interval == "day":
        span_days = (max_date - min_date).days
        return max(int(span_days / step) + 1, 1)

    if interval == "hour":
        span_hours = (max_date - min_date).total_seconds() / 3600
        return max(int(span_hours / step) + 1, 1)

    if interval == "minute":
        span_min = (max_date - min_date).total_seconds() / 60
        return max(int(span_min / step) + 1, 1)

    if interval == "second":
        span_sec = (max_date - min_date).total_seconds()
        return max(int(span_sec / step) + 1, 1)

    return 2


# Coarsening ladder for "drop one notch finer" when a chosen step
# would yield too few calendar-aligned ticks in the data range.
# Higher rungs first, finer rungs second; the first rung that lands
# >= ``min_ticks`` boundaries inside the data range wins.
_TICK_STEP_LADDER: List[Tuple[str, int]] = [
    ("year", 10),
    ("year", 5),
    ("year", 2),
    ("year", 1),
    ("month", 6),
    ("month", 3),
    ("month", 1),
    ("week", 2),
    ("week", 1),
    ("day", 7),
    ("day", 3),
    ("day", 1),
]


# Nice ladders for "coarsen the tick step until horizontal labels fit".
# Each branch in ``_determine_date_format_raw`` walks the matching ladder
# upward from its initial step until ``n_ticks <= max_horizontal_ticks``.
# The final entry is the coarsest fallback: if nothing fits even at the
# top of the ladder, the engine returns that step at angle=0 anyway and
# accepts whatever Vega-Lite labelOverlap behaviour kicks in. The
# invariant is "never rotate" -- horizontal-or-bust.
_NICE_MONTH_STEPS: Tuple[int, ...] = (1, 2, 3, 6, 12, 24, 36, 60, 120)
_NICE_YEAR_STEPS: Tuple[int, ...] = (1, 2, 5, 10, 20, 25, 50, 100)
_NICE_DAY_STEPS: Tuple[int, ...] = (1, 2, 7, 14)


def _unique_sorted_diffs(date_series: pd.Series) -> pd.Series:
    """Return the inter-sample diffs of UNIQUE dates in the series.

    On long-format multi-line DataFrames the ``date_series`` argument
    carries duplicate dates (one row per series at the same timestamp).
    Computing ``.diff()`` directly on the raw series gives mostly zeros
    for inter-row gaps and skews the cadence measurement -- median diff
    collapses to 0 and the resulting ``is_intraday = median_diff < 20h``
    check fires on plain daily multi-line data, dispatching the chart
    into the intraday branch with intraday formats. De-duplicate first
    to recover the genuine sample-to-sample stride.
    """
    if len(date_series) == 0:
        return pd.Series([], dtype="timedelta64[ns]")
    unique_sorted = pd.Series(pd.unique(date_series)).sort_values()
    return unique_sorted.diff().dropna()


def _coarsen_month_step_to_fit(
    span_months: float,
    chart_width: int,
    initial_step: int = 1,
) -> Tuple[int, str, str, int]:
    """Pick the smallest month-step from the nice ladder whose ticks fit
    horizontally at ``chart_width``.

    Returns ``(step_months, fmt, sample_label, n_ticks)``. If no step in
    the ladder fits, returns the coarsest step (angle=0 will still be
    enforced by the caller; Vega-Lite's labelOverlap handles any residual
    crowding).
    """
    last: Optional[Tuple[int, str, str, int]] = None
    for step in _NICE_MONTH_STEPS:
        if step < initial_step:
            continue
        fmt = "%Y" if step >= 12 else "%b %y"
        sample = "2025" if step >= 12 else "Mar 25"
        n_ticks = max(int(span_months / step) + 1, 2)
        max_horiz = _max_ticks_for_width(chart_width, sample, 0)
        last = (step, fmt, sample, n_ticks)
        if n_ticks <= max_horiz:
            return last
    if last is None:
        return (max(initial_step, 1), "%b %y", "Mar 25", 2)
    return last


def _format_for_step(
    interval: str, step: int,
) -> Tuple[str, str]:
    """Return ``(format, sample_label)`` for a temporal tick_step.

    Per the house-style rules in ``DATE_FORMAT_PRESETS``:
      - Year-aligned ticks (every Jan) -> bare ``%Y`` ("2025"). Month
        prefix is noise because every tick is January.
      - Sub-annual month-aligned ticks (1 / 3 / 6 month step) -> ``%b %y``
        ("Mar 25"). Day is dropped because monthly ticks always land on
        day 1; house separator is a space.
      - Sub-monthly ticks (week / day) -> ``%d %b`` ("06 Mar"). Year is
        dropped because the chart context carries the year anchor and
        spans this short rarely cross year boundaries.
      - Intraday strides use 24-hour times.
    """
    if interval == "year":
        return ("%Y", "2025")
    if interval == "month" and step >= 12:
        return ("%Y", "2025")
    if interval == "month":
        return ("%b %y", "Mar 25")
    if interval in ("week", "day"):
        return ("%d %b", "06 Mar")
    if interval == "hour":
        return ("%H:%M", "09:30")
    if interval in ("minute", "second"):
        return ("%H:%M:%S", "09:30:00")
    return ("%Y", "2025")


def _ensure_min_temporal_ticks(
    cfg: DateFormatConfig,
    date_series: pd.Series,
    chart_width: int,
    min_ticks: int = 2,
) -> DateFormatConfig:
    """Guarantee the date-format config produces at least ``min_ticks``
    calendar boundaries inside the data range.

    Vega-Lite anchors tick placement to the calendar (Jan 1 for year
    ticks, etc.), so a valid-looking configuration like
    ``{"interval": "year", "step": 1}`` on a 20-month span that
    contains exactly one Jan boundary renders with a single tick on
    the x-axis -- "2026" alone, with no scale anchor. This helper
    counts the actual boundaries in range; if fewer than ``min_ticks``
    land inside, it drops one notch on the coarsening ladder
    (year/2 -> year/1 -> month/6 -> month/3 -> month/1 -> ...) until
    the count is satisfied. The angle is always 0 -- the engine never
    rotates time-series tick labels, period.

    Only applies to configs that already use ``tick_step``; configs
    that use ``tick_count`` (the soft hint) are passed through
    unchanged because Vega-Lite's tick generator handles ``tick_count``
    consistently across all data ranges.
    """
    if cfg.tick_step is None:
        return cfg
    if not isinstance(cfg.tick_step, dict):
        return cfg
    if len(date_series) == 0:
        return cfg

    min_date = date_series.min()
    max_date = date_series.max()
    if pd.isna(min_date) or pd.isna(max_date):
        return cfg

    effective_min = max(1, min(min_ticks, len(date_series)))
    actual = _count_calendar_ticks_in_range(
        min_date, max_date, cfg.tick_step, cfg.tick_count,
    )
    if actual >= effective_min:
        return cfg

    current_interval = cfg.tick_step.get("interval")
    current_step = cfg.tick_step.get("step", 1)
    try:
        current_step = int(current_step)
    except (TypeError, ValueError):
        current_step = 1

    # Find the current rung on the ladder, then walk finer until we hit
    # min_ticks or run out of rungs.
    start_idx = 0
    for i, (iv, st) in enumerate(_TICK_STEP_LADDER):
        if iv == current_interval and st == current_step:
            start_idx = i
            break

    for iv, st in _TICK_STEP_LADDER[start_idx + 1:]:
        candidate_step = {"interval": iv, "step": st}
        candidate_count = _count_calendar_ticks_in_range(
            min_date, max_date, candidate_step, None,
        )
        if candidate_count < effective_min:
            continue

        new_format, sample_label = _format_for_step(iv, st)
        return DateFormatConfig(
            format=new_format,
            tick_count=cfg.tick_count,
            label_angle=0,
            description=(
                f"Coarsening dropped to ({iv} step={st}) for >= "
                f"{effective_min} ticks in range"
            ),
            tick_step=candidate_step,
            label_expr=cfg.label_expr,
        )

    return cfg


def determine_date_format(
    date_series: pd.Series,
    chart_width: int = 600,
) -> DateFormatConfig:
    """Pick an optimal date-axis format based on the time span and width.

    The function dispatches in three layers:
      1. **Intraday** (span < ~5 days with sub-daily granularity):
         24-hour ``%H:%M`` time labels with explicit minute / hour /
         day tick steps. Date prefix (``%b %d``) is added whenever the
         data crosses midnight so adjacent ``00:00`` ticks remain
         unambiguous; full-day strides drop the time component
         entirely.
      2. **Short calendar spans** (≤ 5 days, daily granularity):
         force ``tick_count`` to match the number of calendar days so
         Vega-Lite doesn't place sub-daily ticks that produce duplicate
         date labels (Bug-1 fix).
      3. **Calendar spans** (> 5 days): pick a tick step from a series
         of span buckets (decade ticks, multi-year, sub-annual,
         year-month, month-day, day-month) and coarsen the step until
         the labels fit horizontally at ``chart_width``.

    The engine **never rotates time-series tick labels**. Every branch
    forces ``label_angle = 0`` and uses ``_coarsen_month_step_to_fit``
    (or its per-bucket equivalent) to widen the tick step until the
    labels fit. Final post-processing through ``_ensure_min_temporal_ticks``
    guarantees at least 2 calendar-aligned ticks land inside the data
    range so a 20-month span never collapses to a lone "2026".
    """
    cfg = _determine_date_format_raw(date_series, chart_width)
    return _ensure_min_temporal_ticks(cfg, date_series, chart_width)


def _determine_date_format_raw(
    date_series: pd.Series,
    chart_width: int = 600,
) -> DateFormatConfig:
    """Internal implementation of ``determine_date_format`` -- picks the
    raw format/step from span buckets without the min-ticks guarantee.
    """
    if len(date_series) == 0:
        return DATE_FORMAT_PRESETS["year_month"]

    min_date = date_series.min()
    max_date = date_series.max()
    span_delta = max_date - min_date
    span_days = span_delta.days
    span_hours = span_delta.total_seconds() / 3600

    # ---- INTRADAY DETECTION (must come FIRST) -----------------------------
    # Detect intraday data by inter-sample cadence rather than a fixed
    # "points per day" threshold: any series whose median sample-to-
    # sample gap is sub-daily counts as intraday, which catches both
    # high-frequency (1-min ticks) and sparse (5 hourly readings) cases.
    if span_hours <= 5 * 24 and len(date_series) >= 2:
        date_diffs = _unique_sorted_diffs(date_series)
        if len(date_diffs) > 0:
            median_diff_seconds = float(date_diffs.dt.total_seconds().median())
        else:
            median_diff_seconds = float("inf")
        is_intraday = median_diff_seconds < 20 * 3600

        if is_intraday:
            # Conditional Vega expression for intraday axes: date at
            # midnight (multi-day) or leftmost tick only (single-session).
            # See ``_intraday_label_expr``.
            single_session = date_series.dt.normalize().nunique() == 1
            intraday_label_expr = _intraday_label_expr(
                single_session=single_session,
            )
            sample_label = "May 27" if single_session else "Apr 28"

            def _intraday_format_and_sample(
                stride_s: int,
            ) -> Tuple[Optional[str], Optional[str], str]:
                """Pick format / labelExpr + width-sample for a stride.

                Returns ``(format, label_expr, sample_label)``. Intraday
                always uses ``label_expr``; date only at midnight (multi-day)
                or leftmost tick (single-session).
                """
                if stride_s >= 86400:
                    return ("%b %d", None, "Apr 28")
                if stride_s < 60:
                    return (None, intraday_label_expr, sample_label)
                return (None, intraday_label_expr, sample_label)

            # Initial stride targeting ~5-7 ticks across a clean
            # boundary. Always picks a "nice" interval so adjacent
            # ticks land on uniform stride (10s/30s, 1/5/10/15/30 min,
            # 1/2/3/6/12 h, 1 day) rather than whatever Vega-Lite
            # would auto-snap to from a soft tick_count hint.
            #
            # ``stride_seconds`` is the canonical stride. For spans
            # >= 5 min we work in minute-aligned strides (most common
            # case); for shorter spans we drop to second-aligned.
            span_seconds = span_delta.total_seconds()
            if span_seconds <= 60:
                stride_seconds = 10
            elif span_seconds <= 300:
                stride_seconds = 30
            elif span_hours <= 0.5:
                stride_seconds = 5 * 60
            elif span_hours <= 1:
                stride_seconds = 10 * 60
            elif span_hours <= 2:
                stride_seconds = 15 * 60
            elif span_hours <= 3:
                stride_seconds = 30 * 60
            elif span_hours <= 7:
                stride_seconds = 60 * 60
            elif span_hours <= 14:
                stride_seconds = 120 * 60
            elif span_hours <= 24:
                stride_seconds = 180 * 60
            elif span_hours <= 48:
                stride_seconds = 360 * 60
            elif span_hours <= 72:
                stride_seconds = 720 * 60
            else:
                stride_seconds = 1440 * 60

            fmt, label_expr, sample = _intraday_format_and_sample(
                stride_seconds,
            )

            # Width-aware fitting. The labelExpr design keeps every
            # label short (max 6 chars), so the strategy is: bump
            # stride until labels fit horizontally. Only rotate as a
            # last resort if even the coarsest stride still doesn't
            # fit (extremely narrow composite panels).
            nice_strides_s = [
                10, 30,                                     # seconds
                60, 5 * 60, 10 * 60, 15 * 60, 30 * 60,      # minutes
                60 * 60, 2 * 60 * 60, 3 * 60 * 60,          # hours
                6 * 60 * 60, 12 * 60 * 60,
                86400, 2 * 86400,                           # days
            ]
            n_ticks = max(int(span_seconds / stride_seconds) + 1, 2)
            max_horiz = _max_ticks_for_width(chart_width, sample, 0)
            while (
                n_ticks > max_horiz
                and stride_seconds < nice_strides_s[-1]
            ):
                next_stride = next(
                    (s for s in nice_strides_s if s > stride_seconds),
                    nice_strides_s[-1],
                )
                stride_seconds = next_stride
                fmt, label_expr, sample = _intraday_format_and_sample(
                    stride_seconds,
                )
                n_ticks = max(int(span_seconds / stride_seconds) + 1, 2)
                max_horiz = _max_ticks_for_width(chart_width, sample, 0)

            # ``angle`` is always 0 -- the engine never rotates time-series
            # tick labels. The stride-bumping loop above already pushed the
            # stride to the coarsest viable; if even that doesn't fit
            # horizontally we let Vega-Lite's labelOverlap thin labels
            # rather than rotate.

            if stride_seconds < 60:
                tick_step = {"interval": "second", "step": stride_seconds}
                stride_label = f"{stride_seconds}s"
            elif stride_seconds < 3600:
                tick_step = {
                    "interval": "minute", "step": stride_seconds // 60,
                }
                stride_label = f"{stride_seconds // 60}min"
            elif stride_seconds < 86400:
                tick_step = {
                    "interval": "hour", "step": stride_seconds // 3600,
                }
                stride_label = f"{stride_seconds // 3600}h"
            else:
                tick_step = {
                    "interval": "day", "step": stride_seconds // 86400,
                }
                stride_label = f"{stride_seconds // 86400}d"
            return DateFormatConfig(
                format=fmt,
                # Intraday axes MUST use a plain integer ``tick_count`` hint.
                # Emitting ``tick_step={"interval": "hour", "step": N}`` on
                # ``axis.tickCount`` compiles in Altair but explodes inside
                # vl-convert/Vega at PNG time (``marktype`` / ``every``
                # TypeError). The stride loop above still picks ``fmt`` /
                # ``label_expr``; only the tick *placement* hint changes.
                tick_count=max(n_ticks, 2),
                label_angle=0,
                description=f"Intraday ticks (every {stride_label})",
                tick_step=None,
                label_expr=label_expr,
            )

    # ---- BUG-1 FIX: short daily spans (<= 5 days) -------------------------
    # Format is the day-month preset ("06 Mar"). Year is dropped because
    # the chart context carries the year anchor and a 5-day window almost
    # never crosses a calendar boundary. If the daily ticks don't fit
    # horizontally at the chart width, drop down to every other day.
    if span_days <= 5:
        estimated_ticks = max(span_days, 1)
        max_horiz = _max_ticks_for_width(chart_width, "06 Mar", 0)
        tick_step: Optional[Dict[str, Any]] = None
        if estimated_ticks > max_horiz and estimated_ticks > 2:
            tick_step = {"interval": "day", "step": 2}
            estimated_ticks = max(int(span_days / 2) + 1, 2)
        return DateFormatConfig(
            format="%d %b",
            tick_count=estimated_ticks if tick_step is None else None,
            label_angle=0,
            description="Short span <= 5 days with explicit daily ticks",
            tick_step=tick_step,
        )

    span_years = span_days / 365.25
    span_months = span_days / 30.44

    # ---- > 10 years: year-only --------------------------------------------
    # On multi-decade axes the tick stride is annual or longer, so every
    # tick lands on January and the "Jan-" prefix carries zero
    # information. Drop the month and use bare 4-digit year ("1994",
    # "2024"). An explicit year ``tick_step`` keeps Vega-Lite from
    # placing ticks at fractional-year boundaries that wouldn't render
    # to a clean year label.
    #
    # Stride targets ~5-7 visible ticks across common span buckets:
    #   10-15y -> every 2 years
    #   15-50y -> every 5 years
    #   >50y   -> every 10 years
    # If the chosen stride produces too many labels for the canvas
    # (very narrow chart), bump to the next nicer multiple.
    if span_years > 10:
        if span_years > 50:
            stride_years = 10
        elif span_years > 15:
            stride_years = 5
        else:
            stride_years = 2
        max_horiz = _max_ticks_for_width(chart_width, "2025", 0)
        n_ticks = max(int(span_years / stride_years) + 1, 2)
        # Coarsen the stride until the year ticks fit horizontally. If
        # nothing in the ladder fits (extreme narrow panel), keep the
        # coarsest stride and let labelOverlap thin labels -- never
        # rotate.
        if n_ticks > max_horiz:
            for nice in _NICE_YEAR_STEPS:
                if nice > stride_years:
                    stride_years = nice
                    n_ticks = max(int(span_years / stride_years) + 1, 2)
                    if n_ticks <= max_horiz:
                        break
        return DateFormatConfig(
            format="%Y",
            tick_count=None,
            label_angle=0,
            description=f"Multi-year ticks (every {stride_years} years)",
            tick_step={"interval": "year", "step": stride_years},
        )

    # Tick budgets are deliberately conservative: a clean axis has 4-6
    # labels with generous breathing room; >7 labels in a financial chart
    # starts to look cluttered.
    #
    # We pick an EXPLICIT temporal interval/step (e.g. ``{"interval":
    # "month", "step": 6}``) instead of just a tick count, because
    # Vega-Lite's tickCount is only a soft hint -- if we ask for 4
    # ticks on a 17-month axis it'll still pick quarterly (6 ticks)
    # because that's the next "nice" interval. An explicit step forces
    # Vega-Lite to land on the boundaries we want.
    #
    # Sample labels are used to verify the chosen step actually fits in
    # ``chart_width``; if not, we double the step until it does.

    def _step_for_target(span_months_local: float, target_ticks: int) -> int:
        """Round target month-step up to a nice value (1, 2, 3, 6, 12, 24...)."""
        raw = max(span_months_local / max(target_ticks, 1), 1.0)
        for nice in (1, 2, 3, 6, 12, 24, 36, 60, 120):
            if raw <= nice:
                return nice
        return 120

    def _ticks_for_step(
        span_months_local: float, step_months: int,
    ) -> int:
        return max(int(span_months_local / step_months) + 1, 2)

    # ---- shorter spans: detect data frequency ------------------------------
    if len(date_series) >= 24:
        date_diffs = _unique_sorted_diffs(date_series)
        if len(date_diffs) > 0:
            median_diff_days = date_diffs.dt.days.median()
            # Sub-annual data with sub-10-year span: pick a tick step,
            # then choose format based on whether ticks land annually
            # (every 12+ months -> ``%Y``, "2025") or sub-annually
            # (-> ``%b-%y``, "Apr-25").
            if 2 <= median_diff_days <= 30 and span_years <= 10:
                step_months = _step_for_target(span_months, 5)
                step_months, fmt, sample, n_ticks = _coarsen_month_step_to_fit(
                    span_months, chart_width, initial_step=step_months,
                )
                return DateFormatConfig(
                    format=fmt,
                    tick_count=None,
                    label_angle=0,
                    description=(
                        f"Sub-annual ticks (every {step_months} months)"
                    ),
                    tick_step=_temporal_tick_step("month", step_months),
                )

    # ---- format selection by span ------------------------------------------
    if span_years >= 3:
        if span_years >= 8:
            step_months = 24
        elif span_years >= 4:
            step_months = 12
        else:
            step_months = 6
        step_months, fmt, sample, n_ticks = _coarsen_month_step_to_fit(
            span_months, chart_width, initial_step=step_months,
        )
        return DateFormatConfig(
            format=fmt,
            tick_count=None,
            label_angle=0,
            description=f"Year-month ticks (every {step_months} months)",
            tick_step=_temporal_tick_step("month", step_months),
        )

    if span_years > 1:
        step_months = 6 if span_years <= 2.5 else 12
        step_months, fmt, sample, n_ticks = _coarsen_month_step_to_fit(
            span_months, chart_width, initial_step=step_months,
        )
        return DateFormatConfig(
            format=fmt,
            tick_count=None,
            label_angle=0,
            description=f"Semi-annual to annual ticks (every {step_months} months)",
            tick_step=_temporal_tick_step("month", step_months),
        )

    if span_months > 6:
        # Quarterly for 6-12 month spans. Never bump to semi-annual on
        # this branch -- a calendar-aligned 6-month step on a 9-month
        # span lands on at most ONE calendar boundary inside the range,
        # producing a single isolated tick. If quarterly doesn't fit
        # horizontally at the chart width, drop to annual instead.
        step_months = 3
        max_horiz = _max_ticks_for_width(chart_width, "Mar 25", 0)
        n_ticks = _ticks_for_step(span_months, step_months)
        if n_ticks > max_horiz:
            step_months, fmt, sample, n_ticks = _coarsen_month_step_to_fit(
                span_months, chart_width, initial_step=6,
            )
            return DateFormatConfig(
                format=fmt,
                tick_count=None,
                label_angle=0,
                description=f"Coarsened quarterly ticks (every {step_months} months)",
                tick_step=_temporal_tick_step("month", step_months),
            )
        return DateFormatConfig(
            format="%b %y",
            tick_count=None,
            label_angle=0,
            description=f"Quarterly ticks (every {step_months} months)",
            tick_step=_temporal_tick_step("month", step_months),
        )

    if span_months > 1:
        # 1-6 month spans. Monthly Vega-Lite ticks always land on day 1,
        # so the day prefix is pure noise -- format is "%b %y" ("Mar 24").
        # If 6 monthly ticks don't fit horizontally at the chart width,
        # coarsen to a 2- or 3-month step (still horizontal, fewer labels)
        # rather than rotate.
        step_months, fmt, sample, n_ticks = _coarsen_month_step_to_fit(
            span_months, chart_width, initial_step=1,
        )
        return DateFormatConfig(
            format=fmt,
            tick_count=None,
            label_angle=0,
            description=f"Monthly ticks (every {step_months} month)",
            tick_step=_temporal_tick_step("month", step_months),
        )

    if span_days > 14:
        # 2-4 week spans. Weekly ticks land on Mondays -- arbitrary day
        # numbers, so the day prefix is informative; year is dropped
        # because spans this short rarely cross calendar boundaries and
        # the chart context carries the year anchor. Coarsen to bi-weekly
        # if weekly doesn't fit.
        step_days = 7
        n_ticks = max(int(span_days / step_days) + 1, 2)
        max_horiz = _max_ticks_for_width(chart_width, "06 Mar", 0)
        if n_ticks > max_horiz:
            step_days = 14
            n_ticks = max(int(span_days / step_days) + 1, 2)
        return DateFormatConfig(
            format="%d %b",
            tick_count=None,
            label_angle=0,
            description=f"Weekly ticks (every {step_days} days)",
            tick_step={"interval": "week", "step": max(step_days // 7, 1)},
        )

    # ---- < 2 weeks ---------------------------------------------------------
    # Daily ticks; year dropped (chart context carries it). Force angle=0;
    # the existing _pick_tick_count_and_angle helper would happily rotate
    # so we replace it with a tick-count cap that fits horizontally.
    sample = "06 Mar"
    max_horiz = _max_ticks_for_width(chart_width, sample, 0)
    desired_max = max(min(int(span_days), 7), 4)
    tick_count = max(min(desired_max, max_horiz), 2)
    return DateFormatConfig(
        format="%d %b",
        tick_count=tick_count,
        label_angle=0,
        description="Short date (span < 2 weeks)",
    )


def calculate_y_axis_domain(
    data_series: pd.Series,
    handle_outliers: bool = True,
    include_zero: bool = False,
    padding_pct: float = 0.05,
    prevent_zero_start: bool = True,
) -> Tuple[float, float]:
    """Compute an optimal y-axis domain.

    Default behavior: prevent the y-axis from starting at 0 unless the data
    actually includes values near 0 (avoids flat-line charts where
    variation is invisible because the visible range is dominated by zero).

    Args:
        data_series: Numeric series to compute the domain for.
        handle_outliers: Reserved for future IQR-based clipping (currently
            a no-op; we keep the kwarg for signature stability).
        include_zero: Force the domain to include 0.
        padding_pct: Fractional padding applied to ``(domain_max - domain_min)``.
        prevent_zero_start: When True (default), don't include 0 unless the
            data is within 20% of zero.

    Returns:
        ``(domain_min, domain_max)``.
    """
    clean_data = data_series.dropna()
    if len(clean_data) == 0:
        return (0.0, 1.0)

    data_min = float(clean_data.min())
    data_max = float(clean_data.max())
    data_range = data_max - data_min

    # Constant-series case: data_min == data_max. With a true zero range,
    # the padding math below collapses to ``[constant, constant]`` and the
    # rendered y-axis shows a single tick at the constant value, with the
    # rest of the plot frame empty (looks broken). Synthesize an explicit
    # +/- 5% (or +/- 1.0 for zero) domain so the line renders as a flat
    # rule with reference ticks above and below.
    if data_range == 0:
        if data_max == 0:
            return (-1.0, 1.0)
        magnitude = abs(data_max)
        synthetic_pad = magnitude * 0.05
        return (data_max - synthetic_pad, data_max + synthetic_pad)

    domain_min = data_min
    domain_max = data_max

    # Snap-to-zero: include 0 only when the data is genuinely hugging the
    # floor. Two gates must both fire:
    #   1. Relative-to-range -- domain_min within 20% of the data span. This
    #      catches series like "0.5% to 10% unemployment" where 0 is a useful
    #      reference.
    #   2. Relative-to-magnitude -- domain_min within 5% of the data top. This
    #      rejects the false-positive that breaks indexed-performance charts:
    #      e.g. oil rebased to 700 while gold/copper sit at 100-250. The wide
    #      range makes the 80-floor look "close to zero" relative to range,
    #      but it really isn't close to zero in absolute terms. Without this
    #      gate, the y-axis snaps to [0, 735] and the gold/copper lines get
    #      squashed into the bottom third.
    if prevent_zero_start and domain_min > 0:
        relative_threshold = (
            data_range * 0.2 if data_range > 0 else abs(domain_min) * 0.2
        )
        absolute_threshold = abs(domain_max) * 0.05
        if domain_min <= relative_threshold and domain_min <= absolute_threshold:
            domain_min = 0.0

    padded_range = domain_max - domain_min
    padding = padded_range * padding_pct
    domain_min = domain_min - padding
    domain_max = domain_max + padding

    if include_zero:
        domain_min = min(domain_min, 0.0)
        domain_max = max(domain_max, 0.0)

    return (domain_min, domain_max)


def should_use_log_scale(
    data_series: pd.Series,
    threshold_ratio: float = 100,
) -> bool:
    """Recommend log scale when ``max/min > threshold_ratio`` (positive data only)."""
    clean_data = data_series.dropna()
    if len(clean_data) < 5:
        return False
    if (clean_data <= 0).any():
        return False
    min_val = float(clean_data.min())
    max_val = float(clean_data.max())
    if min_val <= 0:
        return False
    return (max_val / min_val) > threshold_ratio


def wrap_label(label: str, words_per_line: int = 3) -> str:
    """Wrap a label at word boundaries every ``words_per_line`` words."""
    label = str(label)
    words = label.split()
    if len(words) <= words_per_line:
        return label
    lines: List[str] = []
    for i in range(0, len(words), words_per_line):
        lines.append(" ".join(words[i:i + words_per_line]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# NUMBER FORMATTING (catch-all for label/text rounding)
# ---------------------------------------------------------------------------

def _natural_sort_key(value: Any) -> Tuple[Any, ...]:
    """Generate a key that sorts strings with embedded numbers naturally.

    Used by the categorical heatmap path so bin labels like
    ``'0-10%'`` / ``'10-20%'`` / ... / ``'90-100%'`` order numerically
    instead of lexicographically (which would put ``'10-20%'`` before
    ``'2-10%'``). Splits the string into alternating literal / numeric
    chunks; numeric chunks compare as floats, literals as lowercased
    strings. Robust to leading negative numbers, decimals, scientific
    notation, and mixed-case literals.
    """
    s = str(value)
    parts: List[Tuple[int, Any]] = []
    for token in re.split(r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", s):
        if not token:
            continue
        try:
            parts.append((0, float(token)))
        except ValueError:
            parts.append((1, token.lower()))
    return tuple(parts)


# Per-scheme color anchors used by ``_sample_named_scheme`` to synthesize
# an N-step ramp without depending on Vega-Lite's runtime scheme tables.
# Each value is a small list of hex stops sampled uniformly from the
# scheme; we linearly interpolate to land on N colors. The list is
# intentionally small (5-7 stops) because higher resolution adds bytes
# without changing visible output for the typical 5-12 bin range that
# the categorical heatmap path serves.
_SCHEME_ANCHORS: Dict[str, List[str]] = {
    "blues": [
        "#f7fbff", "#deebf7", "#c6dbef", "#9ecae1",
        "#6baed6", "#4292c6", "#2171b5", "#08519c", "#08306b",
    ],
    "greens": [
        "#f7fcf5", "#e5f5e0", "#c7e9c0", "#a1d99b",
        "#74c476", "#41ab5d", "#238b45", "#006d2c", "#00441b",
    ],
    "reds": [
        "#fff5f0", "#fee0d2", "#fcbba1", "#fc9272",
        "#fb6a4a", "#ef3b2c", "#cb181d", "#a50f15", "#67000d",
    ],
    "oranges": [
        "#fff5eb", "#fee6ce", "#fdd0a2", "#fdae6b",
        "#fd8d3c", "#f16913", "#d94801", "#a63603", "#7f2704",
    ],
    "purples": [
        "#fcfbfd", "#efedf5", "#dadaeb", "#bcbddc",
        "#9e9ac8", "#807dba", "#6a51a3", "#54278f", "#3f007d",
    ],
    "greys": [
        "#ffffff", "#f0f0f0", "#d9d9d9", "#bdbdbd",
        "#969696", "#737373", "#525252", "#252525", "#000000",
    ],
    "viridis": [
        "#440154", "#482878", "#3e4a89", "#31688e",
        "#26828e", "#1f9e89", "#35b779", "#6dcd59",
        "#b4de2c", "#fde725",
    ],
    "plasma": [
        "#0d0887", "#46039f", "#7201a8", "#9c179e",
        "#bd3786", "#d8576b", "#ed7953", "#fb9f3a",
        "#fdca26", "#f0f921",
    ],
    "magma": [
        "#000004", "#1c1044", "#4f127b", "#812581",
        "#b5367a", "#e55063", "#fb8761", "#fec287", "#fcfdbf",
    ],
    "redblue": [
        "#67001f", "#b2182b", "#d6604d", "#f4a582",
        "#fddbc7", "#f7f7f7", "#d1e5f0", "#92c5de",
        "#4393c3", "#2166ac", "#053061",
    ],
    "redyellowblue": [
        "#a50026", "#d73027", "#f46d43", "#fdae61",
        "#fee090", "#ffffbf", "#e0f3f8", "#abd9e9",
        "#74add1", "#4575b4", "#313695",
    ],
    "redyellowgreen": [
        "#a50026", "#d73027", "#f46d43", "#fdae61",
        "#fee08b", "#ffffbf", "#d9ef8b", "#a6d96a",
        "#66bd63", "#1a9850", "#006837",
    ],
    "spectral": [
        "#9e0142", "#d53e4f", "#f46d43", "#fdae61",
        "#fee08b", "#ffffbf", "#e6f598", "#abdda4",
        "#66c2a5", "#3288bd", "#5e4fa2",
    ],
    "browngreen": [
        "#8c510a", "#bf812d", "#dfc27d", "#f6e8c3",
        "#f5f5f5", "#c7eae5", "#80cdc1", "#35978f", "#01665e",
    ],
}


def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _sample_named_scheme(scheme_name: str, n: int) -> List[str]:
    """Return ``n`` hex colors uniformly sampled from a named ramp.

    Used by the categorical heatmap path so a string-binned value column
    (e.g. ``pd.cut(..., labels=['0-10%', ..., '90-100%'])``) renders
    with the same low->high intensity gradient that the numeric path
    produces for a sequential scheme. Falls back to ``'blues'`` when
    ``scheme_name`` isn't in ``_SCHEME_ANCHORS``.

    Sampling is linear interpolation between adjacent anchor stops --
    visually indistinguishable from Vega-Lite's runtime evaluation at
    the bin counts this code path serves (typically 5-12).
    """
    anchors = _SCHEME_ANCHORS.get(scheme_name) or _SCHEME_ANCHORS["blues"]
    if n <= 0:
        return []
    if n == 1:
        return [anchors[len(anchors) // 2]]
    stops = [_hex_to_rgb(h) for h in anchors]
    out: List[str] = []
    last_idx = len(stops) - 1
    for i in range(n):
        t = i / (n - 1)
        pos = t * last_idx
        lo = int(np.floor(pos))
        hi = min(lo + 1, last_idx)
        frac = pos - lo
        r = int(round(stops[lo][0] + (stops[hi][0] - stops[lo][0]) * frac))
        g = int(round(stops[lo][1] + (stops[hi][1] - stops[lo][1]) * frac))
        b = int(round(stops[lo][2] + (stops[hi][2] - stops[lo][2]) * frac))
        out.append(_rgb_to_hex(r, g, b))
    return out


def _smart_number_format(series_or_value: Any) -> str:
    """Pick a Vega-Lite number format string based on magnitude.

    The chart engine is the final catch-all for rounding: any numeric
    column that gets rendered as text on a chart -- bar value labels,
    heatmap cell labels, bullet labels, waterfall labels,
    LastValueLabel value suffixes -- routes through this helper so a
    raw float like ``99.917898193`` never reaches the canvas.

    Magnitude buckets (uses ``|value|.max()`` for a Series, or
    ``|value|`` for a scalar):

    | Magnitude     | Format    | Example         |
    |---------------|-----------|-----------------|
    | ``>= 1000``   | ``,.0f``  | ``2,350``       |
    | ``>= 100``    | ``,.1f``  | ``315.2``       |
    | ``>= 10``     | ``.2f``   | ``35.92``       |
    | ``>= 1``      | ``.2f``   | ``1.08``        |
    | ``>= 0.01``   | ``.3f``   | ``0.085``       |
    | ``< 0.01``    | ``.4f``   | ``0.0012``      |

    Empty / non-numeric inputs fall back to ``".2f"``.
    """
    try:
        if isinstance(series_or_value, pd.Series):
            clean = series_or_value.dropna()
            if len(clean) == 0 or not pd.api.types.is_numeric_dtype(clean):
                return ".2f"
            max_abs = float(clean.abs().max())
        else:
            v = float(series_or_value)
            if pd.isna(v):
                return ".2f"
            max_abs = abs(v)
    except (TypeError, ValueError):
        return ".2f"
    if max_abs >= 1000:
        return ",.0f"
    if max_abs >= 100:
        return ",.1f"
    if max_abs >= 10:
        return ".2f"
    if max_abs >= 1:
        return ".2f"
    if max_abs >= 0.01:
        return ".3f"
    return ".4f"


def _smart_format_value(value: Any) -> str:
    """Format a single numeric value as a string, magnitude-aware.

    Mirrors the ``_smart_number_format`` rules but returns a
    ready-rendered string. Used when a chart layer encodes text
    nominally (Vega-Lite's nominal ``alt.Text`` cannot apply a number
    format) and the column has to be pre-stringified -- e.g. the bullet
    chart's ``mapping['label']`` row, where the user may pass a raw
    float column.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value) if value is not None else ""
    if pd.isna(v):
        return ""
    abs_v = abs(v)
    if abs_v >= 1000:
        return f"{v:,.0f}"
    if abs_v >= 100:
        return f"{v:,.1f}"
    if abs_v >= 10:
        return f"{v:.2f}"
    if abs_v >= 1:
        return f"{v:.2f}"
    if abs_v >= 0.01:
        return f"{v:.3f}"
    return f"{v:.4f}"


def _smart_format_template(series_or_value: Any) -> str:
    """Return a Python ``str.format``-style template for ``_smart_number_format``.

    Yields the magnitude-aware spec wrapped in ``"{:" + spec + "}"`` so
    callers can drop it into ``"{:fmt}".format(value)`` -- e.g.
    the waterfall chart label-template path.
    """
    spec = _smart_number_format(series_or_value)
    return "{:" + spec + "}"


def truncate_label(label: str, max_length: int = 20, suffix: str = "...") -> str:
    """Truncate a label if it exceeds ``max_length``."""
    label = str(label)
    if len(label) <= max_length:
        return label
    return label[: max_length - len(suffix)] + suffix


def _wrap_text_to_width(text: str, width_px: int, font_size: int) -> str:
    """Word-wrap a free-form text block to a target pixel width.

    Used by the text-panel helpers (``_build_text_panel``,
    ``PlotText.build_layer``). Vega-Lite's ``mark_text`` with
    ``lineBreak`` honours explicit ``\\n`` characters but offers no
    width-aware autowrap, so we pre-wrap here.

    Heuristic: average character width is ``~0.55 * font_size`` for
    English at typical body sizes (10-12px). A single token longer
    than ``chars_per_line`` is hard-broken into ``chars_per_line``
    chunks BEFORE wrapping, so a 500-char no-space caption no longer
    overflows the panel and triggers chart-canvas compression.
    Explicit ``\\n`` characters in the input are honoured as paragraph
    breaks, and each paragraph is wrapped independently.
    """
    if not text:
        return ""
    char_w_px = max(1.0, font_size * 0.55)
    chars_per_line = max(1, int(width_px / char_w_px))
    out_lines: List[str] = []
    for paragraph in str(text).split("\n"):
        # First pass: hard-break any token longer than the line width.
        # This is the no-space-overflow safety net -- without it a
        # single 500-char token spills off the panel and pulls the
        # chart's plot region inwards on relayout.
        tokens: List[str] = []
        for raw in paragraph.split():
            if len(raw) > chars_per_line:
                for i in range(0, len(raw), chars_per_line):
                    tokens.append(raw[i : i + chars_per_line])
            else:
                tokens.append(raw)
        if not tokens:
            out_lines.append("")
            continue
        line = tokens[0]
        for word in tokens[1:]:
            if len(line) + 1 + len(word) <= chars_per_line:
                line = f"{line} {word}"
            else:
                out_lines.append(line)
                line = word
        out_lines.append(line)
    return "\n".join(out_lines)


def _chars_per_line(slot_kind: str, width_px: int) -> int:
    """Return the soft chars-per-line budget for ``slot_kind`` at ``width_px``.

    Uses the slot's configured ``_TEXT_FONT_SIZE`` and the same average
    character-width ratio as ``_wrap_text_to_width`` so wrapped titles
    fit the plot band without ``title.limit`` (Vega-Lite truncates with
    an ellipsis when ``limit`` is set).
    """
    font_size = _TEXT_FONT_SIZE.get(slot_kind, _TEXT_FONT_SIZE["title"])
    char_w_px = max(1.0, font_size * _TEXT_CHAR_WIDTH_RATIO)
    return max(20, int(width_px / char_w_px))


def _wrap_text_at_width(text: str, chars_per_line: int) -> List[str]:
    """Pure word-wrap helper: wrap ``text`` to lines of ``chars_per_line``.

    Tokens longer than ``chars_per_line`` are hard-broken at the limit so
    a single non-breaking word (e.g. a URL) cannot blow past the budget.
    Does NOT inspect ``\\n`` -- callers should split on newlines first if
    they want to honour explicit line breaks.
    """
    tokens: List[str] = []
    for raw in str(text).split():
        if len(raw) > chars_per_line:
            for i in range(0, len(raw), chars_per_line):
                tokens.append(raw[i : i + chars_per_line])
        else:
            tokens.append(raw)
    if not tokens:
        return [""]
    out_lines: List[str] = []
    current = tokens[0]
    for word in tokens[1:]:
        if len(current) + 1 + len(word) <= chars_per_line:
            current = f"{current} {word}"
        else:
            out_lines.append(current)
            current = word
    out_lines.append(current)
    return out_lines


def _validate_and_wrap_text(
    text: Optional[str],
    *,
    slot_kind: str,
    width_px: int,
    slot_label: str,
    widening_hint: Optional[str] = None,
) -> Optional[List[str]]:
    """Validate length + auto-wrap a title or subtitle to fit ``width_px``.

    Two-stage policy that pairs a soft-wrap budget with a hard length
    cap, on the philosophy that the engine should absorb friction PRISM
    would otherwise have to pre-format around (Design Principle #7):

      * Below ``_chars_per_line(slot_kind, width_px)``: render single
        line.
      * Above per-line but below ``per_line * _TEXT_LINE_CAP`` total
        chars: word-wrap into 1..2 lines and render multi-line.
      * Above the hard cap, OR contains so many explicit ``\\n`` that the
        wrapped output would be more than ``_TEXT_LINE_CAP`` lines:
        raise ``ValueError`` with a message naming the slot, the limit,
        and concrete suggestions for shortening.

    Explicit ``\\n`` in ``text`` is honoured as a manual line break
    (auto-wrap is skipped for such inputs -- PRISM is taking control of
    the line breaks). The hard total-length cap still applies.

    Args:
        text: The user-provided title or subtitle. ``None`` / empty
            returns ``None``.
        slot_kind: ``"title"`` or ``"subtitle"`` -- selects the per-char
            pixel budget used to compute ``chars_per_line``.
        width_px: Horizontal pixel budget the text needs to fit inside.
            For ``make_chart`` this is the chart's panel width; for a
            sub-chart inside a composite this is the per-panel width
            from ``COMPOSITE_DIMENSIONS``; for a composite super-title
            this is the total chart-area width spanned by the layout.
        slot_label: Human-friendly slot name used in the error message
            (e.g. ``"composite super-title"``).
        widening_hint: Optional extra suggestion appended to the error
            message (e.g. naming a wider ``dimension_preset``).

    Returns:
        ``None`` if ``text`` is empty.
        A 1- or 2-element list of strings otherwise. Callers pass the
        list directly to ``alt.TitleParams(text=...)`` (Vega-Lite
        accepts a list of strings as a multi-line title) or unwrap to a
        single string when ``len(result) == 1``.

    Raises:
        ValueError: when ``text`` exceeds the slot's hard char limit or
            wraps to more than ``_TEXT_LINE_CAP`` lines.
    """
    if not text:
        return None
    s = str(text)
    cpl = _chars_per_line(slot_kind, width_px)
    hard_cap = cpl * _TEXT_LINE_CAP

    if len(s) > hard_cap:
        suggestions = [
            "shorten the text",
            (
                "move detail into the subtitle slot (subtitles get a "
                "wider per-line budget)"
            )
            if slot_kind == "title"
            else "split the subtitle across multiple shorter sentences",
        ]
        if widening_hint:
            suggestions.append(widening_hint)
        raise ValueError(
            f"{slot_label} is {len(s)} characters; the maximum at "
            f"width {width_px}px is {hard_cap} characters "
            f"({cpl} per line, max {_TEXT_LINE_CAP} lines after "
            f"auto-wrap). Try one of: " + "; ".join(suggestions) + "."
        )

    if "\n" in s:
        lines = [seg.strip() for seg in s.split("\n") if seg.strip()]
    else:
        lines = _wrap_text_at_width(s, cpl)

    if len(lines) > _TEXT_LINE_CAP:
        suggestions = [
            "shorten the text",
            "use fewer explicit \\n breaks",
        ]
        if widening_hint:
            suggestions.append(widening_hint)
        raise ValueError(
            f"{slot_label} wraps to {len(lines)} lines at width "
            f"{width_px}px (max {_TEXT_LINE_CAP} lines, "
            f"{cpl} chars per line). Try one of: "
            + "; ".join(suggestions) + "."
        )

    return lines


def _title_text_from_lines(lines: Optional[List[str]]) -> Any:
    """Unwrap a 1-line list to a scalar for Vega-Lite ``title.text``."""
    if not lines:
        return None
    return lines if len(lines) > 1 else lines[0]


def _title_params_from_lines(
    title_lines: List[str],
    *,
    width_px: int,
    subtitle_lines: Optional[List[str]] = None,
    anchor: str = "start",
    font_size: Optional[int] = None,
    subtitle_font_size: Optional[int] = None,
    font: Optional[str] = None,
    offset: Optional[int] = None,
    subtitle_color: Optional[str] = None,
) -> alt.TitleParams:
    """Build ``TitleParams`` for pre-wrapped title / subtitle lines.

    Callers must run ``_validate_and_wrap_text`` first (font-size-aware
    char budget + explicit ``\\n`` / list lines). Do **not** set
    Vega-Lite ``limit`` -- it ellipsis-truncates instead of wrapping.
    ``frame='group'`` anchors the header to the plot band; multi-line
    titles grow vertically only.
    """
    del width_px  # kept for call-site symmetry with ``_validate_and_wrap_text``
    kwargs: Dict[str, Any] = {
        "text": _title_text_from_lines(title_lines),
        "anchor": anchor,
        "frame": "group",
    }
    if font_size is not None:
        kwargs["fontSize"] = font_size
    if font is not None:
        kwargs["font"] = font
    if offset is not None:
        kwargs["offset"] = offset
    if subtitle_lines:
        kwargs["subtitle"] = _title_text_from_lines(subtitle_lines)
        if subtitle_font_size is not None:
            kwargs["subtitleFontSize"] = subtitle_font_size
        if subtitle_color is not None:
            kwargs["subtitleColor"] = subtitle_color
    return alt.TitleParams(**kwargs)


def _title_dict_from_lines(
    title_lines: List[str],
    *,
    width_px: int,
    subtitle_lines: Optional[List[str]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Dict-shaped title block (facet grid / composite super-title paths)."""
    del width_px  # pre-wrap via ``_validate_and_wrap_text``; no ``limit`` key
    block: Dict[str, Any] = {
        "text": _title_text_from_lines(title_lines),
        **extra,
    }
    if subtitle_lines:
        block["subtitle"] = _title_text_from_lines(subtitle_lines)
    return block


def calculate_tick_values(
    data_min: float,
    data_max: float,
    target_ticks: int = 5,
    nice: bool = True,
) -> List[float]:
    """Compute "nice" round tick values across ``[data_min, data_max]``."""
    if data_min == data_max:
        return [data_min]

    data_range = data_max - data_min
    rough_step = data_range / target_ticks

    if nice:
        magnitude = 10 ** np.floor(np.log10(rough_step))
        residual = rough_step / magnitude
        if residual <= 1.5:
            nice_step = 1 * magnitude
        elif residual <= 3:
            nice_step = 2 * magnitude
        elif residual <= 7:
            nice_step = 5 * magnitude
        else:
            nice_step = 10 * magnitude
    else:
        nice_step = rough_step

    tick_start = np.floor(data_min / nice_step) * nice_step
    ticks: List[float] = []
    tick = tick_start
    while tick <= data_max + nice_step / 2:
        if tick >= data_min - nice_step / 2:
            ticks.append(round(float(tick), 10))
        tick += nice_step
    return ticks


def get_axis_beautification(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    chart_type: str,
    chart_width: int = 600,
    chart_height: int = 400,
) -> Dict[str, AxisConfig]:
    """Return an ``{'x': AxisConfig, 'y': AxisConfig}`` plan for the chart.

    The plan covers temporal/quantitative/categorical x detection and,
    for numeric y data, a domain (with zero-start prevention) plus an
    optional ``log`` scale recommendation. Time-series chart types
    (multi_line, area, line) explicitly disable log scale because it's
    almost never appropriate for time-series and breaks rendering when
    the padded domain dips into zero/negative territory.
    """
    configs: Dict[str, AxisConfig] = {}

    # Heatmaps own their axis plan entirely (x angle in {0, -45} plus tick
    # thinning via ``_heatmap_x_axis_plan``; y is always 0 via
    # ``_heatmap_row_label_angle``; spec patched by ``_apply_heatmap_config``).
    # Skipping the plan here prevents ``apply_beautification_to_spec`` from
    # overwriting the builder's clamp with the generic
    # ``calculate_optimal_label_angle`` answer (which can return -90).
    if chart_type == "heatmap":
        return configs

    x_field = mapping.get("x") if isinstance(mapping.get("x"), str) else None
    if x_field and x_field in df.columns:
        x_data = df[x_field]
        if pd.api.types.is_datetime64_any_dtype(x_data):
            date_config = determine_date_format(x_data, chart_width)
            is_intraday = _is_intraday_datetime_series(x_data)
            configs["x"] = AxisConfig(
                label_angle=date_config.label_angle or 0,
                tick_count=date_config.tick_count,
                tick_step=date_config.tick_step,
                format=date_config.format,
                label_expr=date_config.label_expr,
                # ``greedy`` thins the leftmost date anchor on single-session
                # charts; ``parity`` keeps first + last labels visible.
                label_overlap="parity" if is_intraday else None,
            )
        elif pd.api.types.is_numeric_dtype(x_data):
            configs["x"] = AxisConfig(label_angle=0)
        elif chart_type == "boxplot":
            # ``_build_boxplot`` sets labelAngle=-45 on the nominal x axis.
            # Without an explicit plan here, ``apply_beautification_to_spec``
            # overwrites that with ``calculate_optimal_label_angle``, which
            # often returns 0 for short tick strings (e.g. "EUR/USD") even
            # when 9+ pairs collide horizontally on a 700px canvas.
            configs["x"] = AxisConfig(label_angle=-45, label_limit=200)
        elif chart_type in {"multi_line", "timeseries", "line"}:
            # Profile / yield-curve / vol-smile path (non-temporal,
            # non-numeric x routes to ``_build_profile_line``). House
            # rule: tick labels are NEVER vertical -- horizontal or -45
            # only -- and the label frequency is reduced when they would
            # collide. Bars / waterfalls keep their own angle logic below.
            ordered_vals = _resolve_profile_x_order(df, x_field, mapping)
            label_angle, tick_values = _profile_ordinal_axis_plan(
                ordered_vals, chart_width,
            )
            configs["x"] = AxisConfig(
                label_angle=label_angle,
                label_limit=150 if label_angle != 0 else 200,
                tick_values=tick_values,
                label_overlap="greedy",
            )
        else:
            unique_vals = list(x_data.unique())
            # Pass the actual unique-value count as estimated_tick_count
            # so the angle calculation accounts for ALL labels (Vega-Lite
            # renders every nominal tick, no auto-thinning by default).
            # Without this, the helper assumes ``min(n, 10)`` ticks and
            # returns 0 (horizontal) for a chart with 35 short labels,
            # then beautification clobbers the builder's -90 with 0.
            label_angle = calculate_optimal_label_angle(
                [str(v) for v in unique_vals],
                chart_width,
                estimated_tick_count=len(unique_vals),
            )
            if mapping.get("_facet_panel"):
                label_angle = -45
            configs["x"] = AxisConfig(
                label_angle=label_angle,
                label_limit=150 if label_angle != 0 else 200,
            )

    y_field = mapping.get("y") if isinstance(mapping.get("y"), str) else None
    # Bar / waterfall charts set their own y-domain inside the builder
    # (zero=True for standard bars, stacked-total math for stacked bars,
    # cumulative ``_wf_y_*`` for waterfalls). Running
    # ``calculate_y_axis_domain`` on the raw row values produces a domain
    # based on the largest single value, which is wrong for stacked bars
    # (the chart needs room for the *stacked total*) and adds spurious
    # padding that pushes bars off the floor on standard bars.
    skip_y_domain = chart_type in {"bar", "bar_horizontal", "waterfall"}

    if y_field and y_field in df.columns and not skip_y_domain:
        y_data = df[y_field]
        if pd.api.types.is_numeric_dtype(y_data):
            domain_min, domain_max = calculate_y_axis_domain(y_data)

            if chart_type in {"multi_line", "area", "line", "timeseries"}:
                use_log = False
            else:
                use_log = should_use_log_scale(y_data)

            if use_log and domain_min <= 0:
                positive_vals = y_data[y_data > 0]
                if len(positive_vals) > 0:
                    domain_min = float(positive_vals.min()) * 0.5
                else:
                    use_log = False

            configs["y"] = AxisConfig(
                domain_min=domain_min,
                domain_max=domain_max,
                scale_type="log" if use_log else "linear",
            )

    return configs


def apply_beautification_to_spec(
    spec: Dict[str, Any],
    axis_configs: Dict[str, AxisConfig],
) -> Dict[str, Any]:
    """Apply an ``AxisConfig`` plan to a Vega-Lite spec dict.

    Mutates a deep copy of ``spec`` so the original is preserved. Walks
    layers when present, applying x and y configs to each. Critical
    Vega-Lite quirk: temporal axes need ``formatType='time'`` to use
    d3-time-format; without it strftime-style ``%b '%y`` is fed to
    d3-format (the number formatter) and rendering fails on bar charts
    with datetime x-axes.
    """
    spec = copy.deepcopy(spec)

    def update_encoding(obj: Dict[str, Any], allow_title_fallback: bool = True) -> None:
        if "encoding" not in obj:
            return
        enc = obj["encoding"]

        # Value-channel encodings (``{"value": N}`` for absolute pixel
        # positioning, used by ``PlotText`` and similar plot-region
        # anchors) are not data-bound and cannot accept ``axis`` /
        # ``scale`` properties. Detect them via "value" without "field"
        # and skip beautification entirely on those layers.
        x_is_value_only = (
            isinstance(enc.get("x"), dict)
            and "value" in enc["x"]
            and "field" not in enc["x"]
        )
        y_is_value_only = (
            isinstance(enc.get("y"), dict)
            and "value" in enc["y"]
            and "field" not in enc["y"]
        )
        if x_is_value_only and y_is_value_only:
            return

        # ---- x-axis ------------------------------------------------------
        if (
            "x" in enc
            and "x" in axis_configs
            and isinstance(enc["x"], dict)
            and not x_is_value_only
        ):
            x_config = axis_configs["x"]
            if "axis" not in enc["x"]:
                enc["x"]["axis"] = {}
            # Always emit labelAngle even when 0. Vega-Lite's intrinsic
            # default for nominal / ordinal fields is -90, so omitting it
            # produces rotated labels on heatmaps with short categories
            # like NA / EU / APAC even when calculate_optimal_label_angle
            # says they comfortably fit horizontally.
            enc["x"]["axis"]["labelAngle"] = x_config.label_angle
            # ``labelExpr`` takes precedence over ``format`` -- it lets
            # us produce conditional per-tick labels (e.g. date at
            # midnight, time elsewhere) that no static format string
            # can express.
            if x_config.label_expr:
                enc["x"]["axis"]["labelExpr"] = x_config.label_expr
            elif x_config.format:
                enc["x"]["axis"]["format"] = x_config.format
                if enc["x"].get("type") == "temporal":
                    enc["x"]["axis"]["formatType"] = "time"
            # Prefer the explicit interval/step pair when provided
            # (forces Vega-Lite to land on semi-annual / annual /
            # quarterly boundaries instead of guessing). Normalize
            # month-steps that are multiples of 12 into year-steps,
            # since Vega-Lite ignores ``{"interval": "month", "step": N}``
            # for N >= 12 (defense in depth: ``determine_date_format``
            # already does this, but downstream callers may set their
            # own tick_step).
            if x_config.tick_step:
                ts = x_config.tick_step
                if (
                    isinstance(ts, dict)
                    and ts.get("interval") == "month"
                    and isinstance(ts.get("step"), int)
                    and ts["step"] >= 12
                ):
                    ts = _temporal_tick_step("month", ts["step"])
                enc["x"]["axis"]["tickCount"] = ts
            elif x_config.tick_count:
                enc["x"]["axis"]["tickCount"] = x_config.tick_count
            if x_config.label_limit:
                enc["x"]["axis"]["labelLimit"] = x_config.label_limit
            enc["x"]["axis"]["labelFont"] = "Liberation Sans, Arial, sans-serif"
            # Explicit tick-label subset (profile / yield-curve thinning):
            # show ticks/labels only at these values so a dense ordinal
            # axis stops colliding. The plotted line keeps every knot.
            if x_config.tick_values is not None:
                enc["x"]["axis"]["values"] = x_config.tick_values
            # Safety net: even when ``tick_step`` is honoured, a
            # narrow composite sub-chart can still ask for too many
            # ticks. ``labelOverlap='greedy'`` drops every other label
            # until they fit; ``labelSeparation`` adds a minimum gap
            # so neighbouring labels don't visually merge. Applied to
            # temporal / quantitative axes by default, and to any axis
            # whose config explicitly opts in via ``label_overlap``
            # (the profile ordinal path does, since the house rule
            # forbids the vertical fallback that would otherwise let
            # every nominal label render intact).
            if x_config.label_overlap:
                enc["x"]["axis"].setdefault("labelOverlap", x_config.label_overlap)
                enc["x"]["axis"].setdefault("labelSeparation", 8)
            elif enc["x"].get("type") in ("temporal", "quantitative"):
                enc["x"]["axis"].setdefault("labelOverlap", "greedy")
                enc["x"]["axis"].setdefault("labelSeparation", 8)

        # ---- y-axis ------------------------------------------------------
        if (
            "y" in enc
            and "y" in axis_configs
            and isinstance(enc["y"], dict)
            and not y_is_value_only
        ):
            y_config = axis_configs["y"]
            # Preserve any per-layer scale.domain the builder already set
            # (dual-axis builders rely on this to keep left/right domains
            # independent). Only inject a default domain when the layer
            # hasn't carried one in.
            existing_scale = enc["y"].get("scale") or {}
            existing_domain = existing_scale.get("domain")
            if (
                y_config.domain_min is not None
                and y_config.domain_max is not None
                and existing_domain is None
            ):
                if "scale" not in enc["y"]:
                    enc["y"]["scale"] = {}
                enc["y"]["scale"]["domain"] = [y_config.domain_min, y_config.domain_max]
            if y_config.scale_type == "log":
                if "scale" not in enc["y"]:
                    enc["y"]["scale"] = {}
                enc["y"]["scale"]["type"] = "log"

            # y-axis label wrapping (3 words per line).
            #
            # Priority order for picking the title source:
            #   1. ``enc['y']['axis']['title']``   <- already-resolved
            #      title from the builder (e.g. ``alt.Y(field, axis=
            #      alt.Axis(title='Price'))``). Most builders set the
            #      title here.
            #   2. ``enc['y']['title']``           <- shorthand form
            #      (``alt.Y(field, title='...')``).
            #   3. ``enc['y']['field']``           <- raw field name as
            #      a last-resort fallback (only on the base layer; on
            #      annotation layers this would clobber the resolved
            #      title via Vega-Lite's shared-axis merge rules).
            if "axis" not in enc["y"]:
                enc["y"]["axis"] = {}
            axis_title = enc["y"]["axis"].get("title")
            shorthand_title = enc["y"].get("title")
            if axis_title is None and "title" in enc["y"]["axis"]:
                pass
            elif shorthand_title is None and "title" in enc["y"]:
                pass
            else:
                y_title = axis_title or shorthand_title
                if y_title is None:
                    if allow_title_fallback:
                        y_title = enc["y"].get("field", "")
                    else:
                        y_title = None
                if y_title:
                    enc["y"]["axis"]["title"] = wrap_label(
                        str(y_title), words_per_line=3,
                    )

    def walk(obj: Dict[str, Any], allow_title_fallback: bool) -> None:
        # Recurse into nested layer charts so beautification reaches every
        # encoded layer. Without this, a heatmap+Callout produces a
        # 2-level nested LayerChart (top: [base_layer_chart,
        # callout_layer_chart]) where neither child carries an
        # ``encoding`` at its own root, just deeper ``layer`` arrays.
        # The previous shallow walk skipped beautification on every leaf.
        if "layer" in obj:
            for i, sub in enumerate(obj["layer"]):
                walk(sub, allow_title_fallback=(i == 0 and allow_title_fallback))
            return
        update_encoding(obj, allow_title_fallback=allow_title_fallback)

    walk(spec, allow_title_fallback=True)
    return spec


# ---------------------------------------------------------------------------
# Typography overrides (per dimension preset)
# ---------------------------------------------------------------------------
#
# When a chart is rendered into a small canvas (Teams 420x210, thumbnail
# 300x200), the skin's default font sizes (axis 16/18, title 28) overflow
# the available space. ``_apply_typography_overrides`` patches the
# Vega-Lite ``config`` block with smaller sizes scaled for the target
# canvas. Only presets that actually need non-default typography are
# listed; anything else (``wide``, ``square``, ``tall``, ``presentation``)
# uses the skin's defaults unchanged.
#
# Keys are flat ``<group>_<vega-lite-prop>`` so we can iterate without a
# nested-config builder.

TYPOGRAPHY_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "teams": {
        # Reduced sizes for 420x210 canvas (~55-65% of default).
        "title_fontSize": 17,
        "title_subtitleFontSize": 10,
        "axis_labelFontSize": 8,
        "axis_titleFontSize": 9,
        "legend_labelFontSize": 8,
        "legend_titleFontSize": 9,
        "line_strokeWidth": 1.5,
    },
    "thumbnail": {
        # Even smaller for 300x200 canvas.
        "title_fontSize": 14,
        "title_subtitleFontSize": 10,
        "axis_labelFontSize": 7,
        "axis_titleFontSize": 10,
        "legend_labelFontSize": 7,
        "legend_titleFontSize": 10,
        "line_strokeWidth": 1.5,
    },
    "compact": {
        # Default for facet-grid panels in the 220-400px range. Sized
        # for legibility on a printed letter-portrait page where the
        # composite gets viewed at arm's length, not zoomed in --
        # tick labels at 24pt and axis titles at 22pt are large enough
        # to read at print size without zoom. ``axis_tickCount=6``
        # caps y-tick density so 24pt labels don't crowd at small
        # panel heights.
        "title_fontSize": 28,
        "title_subtitleFontSize": 18,
        "axis_labelFontSize": 24,
        "axis_titleFontSize": 22,
        "axis_tickCount": 6,
        "legend_labelFontSize": 18,
        "legend_titleFontSize": 22,
        "line_strokeWidth": 2,
    },
    "facet_grid": {
        # Facet (small-multiples) grids always use this preset regardless
        # of per-panel pixel size. Standalone ``teams`` / ``thumbnail``
        # presets were designed for embed canvases and shrink labels
        # past readability when a 5x4 country grid lands at ~200px
        # cells. Large axis labels + sparse ticks (3) keep dense grids
        # scannable at letter-portrait arm's length.
        "title_fontSize": 28,
        "title_subtitleFontSize": 18,
        "axis_labelFontSize": 24,
        "axis_titleFontSize": 22,
        "axis_tickCount": 3,
        "legend_labelFontSize": 18,
        "legend_titleFontSize": 22,
        "line_strokeWidth": 2,
    },
}


def _apply_typography_overrides(spec: Dict[str, Any], preset: str) -> Dict[str, Any]:
    """Apply typography overrides to a Vega-Lite spec for a dimension preset.

    Modifies the ``config`` block of a Vega-Lite spec to scale font
    sizes appropriately for the target canvas. This keeps text legible
    and proportional on smaller canvases (Teams, thumbnail) without
    requiring per-skin variants.

    Args:
        spec: The Vega-Lite specification dict (typically
            ``chart.to_dict()``).
        preset: Dimension preset name (``teams``, ``thumbnail``, ``compact``).
            Anything not in ``TYPOGRAPHY_OVERRIDES`` returns the spec
            unchanged.

    Returns:
        Modified spec (deep-copied) with typography overrides applied.
    """
    if preset not in TYPOGRAPHY_OVERRIDES:
        return spec

    overrides = TYPOGRAPHY_OVERRIDES[preset]
    spec = copy.deepcopy(spec)

    spec.setdefault("config", {})
    config = spec["config"]

    # Title group.
    config.setdefault("title", {})
    if "title_fontSize" in overrides:
        config["title"]["fontSize"] = overrides["title_fontSize"]
    if "title_subtitleFontSize" in overrides:
        config["title"]["subtitleFontSize"] = overrides["title_subtitleFontSize"]

    # Axis group.
    config.setdefault("axis", {})
    if "axis_labelFontSize" in overrides:
        config["axis"]["labelFontSize"] = overrides["axis_labelFontSize"]
    if "axis_titleFontSize" in overrides:
        config["axis"]["titleFontSize"] = overrides["axis_titleFontSize"]
    if "axis_tickCount" in overrides:
        config["axis"]["tickCount"] = overrides["axis_tickCount"]

    # Legend group.
    config.setdefault("legend", {})
    if "legend_labelFontSize" in overrides:
        config["legend"]["labelFontSize"] = overrides["legend_labelFontSize"]
    if "legend_titleFontSize" in overrides:
        config["legend"]["titleFontSize"] = overrides["legend_titleFontSize"]

    # Mark-level line strokeWidth.
    config.setdefault("line", {})
    if "line_strokeWidth" in overrides:
        config["line"]["strokeWidth"] = overrides["line_strokeWidth"]

    return spec


# ===========================================================================
# MODULE: SKINS (visual style packs)
# ===========================================================================

# Base configuration shared by all skins. Skin overrides merge on top of this.
BASE_CONFIG: Dict[str, Any] = {
    "width": 600,
    "height": 400,
    "axis_config": {
        "labelFontSize": 16,
        "titleFontSize": 18,
        "labelLimit": 200,
        "labelAngle": 0,
    },
    "legend_config": {
        "titleFontSize": 18,
        "labelFontSize": 16,
        "labelLimit": 300,
        "orient": "right",
        "columns": 1,
        "rowPadding": 2,
    },
    "show_points": False,
    "heatmap_labels": True,
}


# Goldman Sachs Clean - the only published PRISM skin today.
#
# Single source of truth for the categorical palette: GS_PRIMARY in
# chart_functions_studio.py.  ``color_scheme`` (and the named anchors
# ``primary_color`` / ``secondary_color`` / ``accent_color``) are
# derived from GS_PRIMARY["colors"] so every consumer of the palette
# stays in lockstep.  ``label_color_scheme`` is the
# parallel per-slot palette LastValueLabel uses -- identical to
# ``color_scheme`` for the dark slots and a darker HSL-derived hex
# for slots that read poorly as 15pt text on white (slots 1, 2, 3, 6).
# Edit GS_PRIMARY there to change any production color; do not
# hardcode hex values here.
#
# Slot order:
#   0 navy (primary), 1 light blue (secondary), 2 mid blue,
#   3 grey, 4 red (accent), 5 cobalt blue, 6 olive green, 7 purple,
#   8 orange, 9 teal.
GS_CLEAN: Dict[str, Any] = {
    **BASE_CONFIG,
    "name": "gs_clean",
    "description": "Clean, professional style. PRISM default. Palette "
                   "follows GS_PRIMARY in chart_functions_studio.py "
                   "(single source of truth). Line strokes use "
                   "``color_scheme``; LastValueLabel labels use "
                   "``label_color_scheme`` -- identical to lines for the "
                   "dark slots, darker HSL-derived hex for the "
                   "readability-weak slots (light blue, mid blue, grey, "
                   "olive).",
    "primary_color":      GS_PRIMARY["colors"][0],   # #003359 navy
    "secondary_color":    GS_PRIMARY["colors"][1],   # #94C7DD light blue
    "accent_color":       GS_PRIMARY["colors"][4],   # #C00000 red (alert)
    "background_color":   "#FFFFFF",
    "trendline_color":    "#999999",
    "color_scheme":       list(GS_PRIMARY["colors"]),
    "label_color_scheme": list(GS_PRIMARY["label_colors"]),
    "heatmap_scheme": "blues",
    "font_family": "Liberation Sans, Arial, sans-serif",
    "title_font_size": 26,
    "label_font_size": 18,
    "mark_config": {
        "line": {"strokeWidth": 2, "interpolate": "linear", "pointSize": 30, "clip": True},
        "point": {"size": 60, "filled": True, "opacity": 0.7},
        "bar": {"cornerRadius": 0, "opacity": 1.0},
        "area": {"opacity": 0.7, "interpolate": "linear", "clip": True},
        "arc": {"innerRadius": 50, "outerRadius": 100, "padAngle": 0.02, "cornerRadius": 3},
        "boxplot": {"size": 40},
    },
    # ----- Vega-Lite-level config block ----------------------------------
    # Sourced from chart_functions_studio.py's gs_clean theme ("Exact match to PRISM
    # GS_CLEAN: navy #003359, Liberation Sans, 26pt title"). Sizes here
    # supersede the OCR'd MD values which had several typos (28pt title,
    # 20pt subtitle, axis labels and titles transposed).
    "config": {
        "view": {"strokeWidth": 0},
        "axis": {
            "grid": False,
            "domainColor": "#000000",
            "tickColor": "#000000",
            "labelColor": "#000000",
            "labelFont": "Liberation Sans, Arial, sans-serif",
            "titleFont": "Liberation Sans, Arial, sans-serif",
            "titleFontWeight": "normal",
            "labelFontWeight": "normal",
            "labelFontSize": 18,   # axis tick labels
            "titleFontSize": 16,   # axis title (e.g. "Yield (%)")
        },
        "legend": {
            "labelFont": "Liberation Sans, Arial, sans-serif",
            "titleFont": "Liberation Sans, Arial, sans-serif",
            "titleFontSize": 14,
            "labelFontSize": 14,
            "labelLimit": 800,
            "rowPadding": 2,
        },
        "title": {
            "font": "Liberation Sans, Arial, sans-serif",
            "fontSize": 26,
            "fontWeight": "bold",
            "color": "#000000",
            "anchor": "start",
            "offset": 4,
            "subtitleFontSize": 14,
            "subtitleFont": "Liberation Sans, Arial, sans-serif",
            "subtitleFontWeight": "normal",
            "subtitleColor": "#333333",
        },
    },
    # Interactive sliders exposed by chart_functions_studio (humans only, not the LLM).
    "interactive_params": {
        "multi_line": [
            {"name": "strokeWidth", "label": "Line Width", "min": 0.5, "max": 5, "step": 0.5, "default": 2},
            {"name": "lineOpacity", "label": "Opacity", "min": 0.3, "max": 1.0, "step": 0.1, "default": 1.0},
        ],
        "scatter": [
            {"name": "pointSize", "label": "Point Size", "min": 20, "max": 200, "step": 10, "default": 60},
            {"name": "pointOpacity", "label": "Opacity", "min": 0.2, "max": 1.0, "step": 0.1, "default": 0.7},
        ],
        "scatter_multi": [
            {"name": "pointSize", "label": "Point Size", "min": 20, "max": 200, "step": 10, "default": 60},
            {"name": "pointOpacity", "label": "Opacity", "min": 0.2, "max": 1.0, "step": 0.1, "default": 0.7},
        ],
        "donut": [
            {"name": "innerRadius", "label": "Inner Radius (0=Pie)", "min": 0, "max": 100, "step": 5, "default": 50},
            {"name": "outerRadius", "label": "Outer Radius", "min": 50, "max": 150, "step": 5, "default": 100},
            {"name": "padAngle", "label": "Slice Gap", "min": 0, "max": 0.1, "step": 0.01, "default": 0.02},
            {"name": "arcCornerRadius", "label": "Corner Radius", "min": 0, "max": 10, "step": 1, "default": 3},
        ],
        "bar": [
            {"name": "barOpacity", "label": "Bar Opacity", "min": 0.5, "max": 1.0, "step": 0.1, "default": 1.0},
            {"name": "cornerRadius", "label": "Corner Radius", "min": 0, "max": 10, "step": 1, "default": 0},
        ],
        "bar_horizontal": [
            {"name": "barOpacity", "label": "Bar Opacity", "min": 0.5, "max": 1.0, "step": 0.1, "default": 1.0},
            {"name": "cornerRadius", "label": "Corner Radius", "min": 0, "max": 10, "step": 1, "default": 0},
        ],
        "bullet": [
            {"name": "markerSize", "label": "Marker Size", "min": 40, "max": 300, "step": 20, "default": 120},
            {"name": "rangeBarHeight", "label": "Range Bar Height", "min": 4, "max": 24, "step": 2, "default": 12},
        ],
        "waterfall": [
            {"name": "barOpacity", "label": "Bar Opacity", "min": 0.5, "max": 1.0, "step": 0.1, "default": 1.0},
            {"name": "cornerRadius", "label": "Corner Radius", "min": 0, "max": 10, "step": 1, "default": 0},
        ],
        "histogram": [
            {"name": "barOpacity", "label": "Bar Opacity", "min": 0.5, "max": 1.0, "step": 0.1, "default": 0.8},
        ],
        "area": [
            {"name": "areaOpacity", "label": "Fill Opacity", "min": 0.2, "max": 1.0, "step": 0.1, "default": 0.7},
        ],
        "heatmap": [
            {"name": "heatmapOpacity", "label": "Cell Opacity", "min": 0.5, "max": 1.0, "step": 0.1, "default": 1.0},
        ],
        "boxplot": [
            {"name": "boxOpacity", "label": "Box Opacity", "min": 0.5, "max": 1.0, "step": 0.1, "default": 1.0},
        ],
    },
}


# Registry of all available skins. Today only ``gs_clean`` is published.
AVAILABLE_SKINS: Dict[str, Dict[str, Any]] = {
    "gs_clean": GS_CLEAN,
}


def get_skin(name: str, intent: str = "explore") -> Dict[str, Any]:
    """Get a deep-copied skin configuration by name, modulated by intent.

    Intent affects layout / interactivity:
      - ``explore`` (default): full interactive params, default dimensions.
      - ``publish``: drop interactive sliders, fixed 700x400 dimensions.
      - ``monitor``: fixed 500x300 dimensions for dashboard tiles.

    Raises:
        ValueError: If ``name`` is not in ``AVAILABLE_SKINS``.
    """
    if name not in AVAILABLE_SKINS:
        raise ValueError(
            f"Unknown skin: {name!r}. Available: {list(AVAILABLE_SKINS.keys())}"
        )

    skin = copy.deepcopy(AVAILABLE_SKINS[name])

    if intent == "publish":
        skin["interactive_params"] = {}
        skin["width"] = 700
        skin["height"] = 400
    elif intent == "monitor":
        skin["width"] = 500
        skin["height"] = 300
    # 'explore' uses defaults.

    return skin


def list_skins() -> List[Dict[str, str]]:
    """List all available skins with one-line descriptions."""
    return [
        {"name": name, "description": skin["description"]}
        for name, skin in AVAILABLE_SKINS.items()
    ]


def _get_color_scale(skin_config: Dict[str, Any]) -> alt.Scale:
    """Build an ``alt.Scale`` from the skin's color scheme."""
    scheme = skin_config.get("color_scheme", GS_CLEAN["color_scheme"])
    return alt.Scale(range=scheme)


# ---------------------------------------------------------------------------
# Categorical palette registry (PRISM-facing color customisation)
# ---------------------------------------------------------------------------
#
# PRISM-friendly aliases for the curated set of categorical palettes
# already defined in ``chart_functions_studio.py``. The skill spoke
# (``chart_context_colors.md``) is the single source of truth for the
# names PRISM is allowed to pass; this table is the engine-side map
# from those names to the actual hex lists. Keep both in lockstep.
#
# Sequential / diverging palettes for heatmaps + scatter phase-space
# gradient continue to flow through Vega-Lite's named-scheme handling
# (``alt.Scheme(...)`` or ``scale.scheme=<name>``); they are not in
# this registry because Vega does the colour generation, not us.

_CATEGORICAL_PALETTES: Dict[str, List[str]] = {
    "gs_primary": list(GS_PRIMARY["colors"]),
    "colorblind": list(OKABE_ITO["colors"]),
    "bold":       list(VIVID["colors"]),
    "mono_navy":  list(MONO_BLUE["colors"]),
    "mono_grey":  list(MONO_GREY["colors"]),
    "business":   list(TABLEAU["colors"]),
    "pastel":     list(PASTEL["colors"]),
}

_HEATMAP_GRADIENT_NAMES: Set[str] = {
    "blues", "greens", "reds", "oranges", "purples", "greys",
    "viridis", "plasma", "magma", "cividis", "turbo", "inferno", "rainbow",
    "redblue", "spectral", "browngreen", "redyellowblue",
    "redyellowgreen", "blueorange",
}


def _validate_color_kwargs(
    mapping: Dict[str, Any], chart_type: str,
    df: Optional[pd.DataFrame] = None,
) -> None:
    """Validate ``mapping['color_scheme']`` and ``mapping['color_map']``.

    Catches typos / off-list palette names + obvious mode mismatches
    (categorical palette on heatmap, gradient ramp on categorical
    chart) at the boundary so PRISM sees an actionable error instead
    of a silently-wrong render.

    ``df`` is optional; when supplied, integer-key ``color_map`` slots
    are also range-checked against the actual category count for the
    color field, so PRISM hears immediately about
    ``color_map={5: '#hex'}`` on a 3-category chart.
    """
    is_heatmap_path = chart_type == "heatmap"

    color_scheme = mapping.get("color_scheme")
    color_range = mapping.get("color_range")
    if color_range is not None:
        if not isinstance(color_range, (list, tuple)) or len(color_range) != 2:
            raise ValidationError(
                "mapping['color_range'] must be a 2-element list of hex "
                "colors [start, end], e.g. ['#DC143C', '#003359']."
            )
        for idx, hex_val in enumerate(color_range):
            if not isinstance(hex_val, str) or not hex_val.startswith("#"):
                raise ValidationError(
                    f"mapping['color_range'][{idx}]={hex_val!r} must be a "
                    f"hex string like '#DC143C'."
                )
        if chart_type not in {"scatter", "scatter_multi"}:
            raise ValidationError(
                "mapping['color_range'] applies to scatter phase-space "
                f"gradients only (chart_type='scatter' / 'scatter_multi'); "
                f"got chart_type={chart_type!r}."
            )
        color_field = _get_field(mapping, "color")
        if df is not None and (
            not color_field
            or color_field not in df.columns
            or not _scatter_color_is_gradient(df, color_field)
        ):
            raise ValidationError(
                "mapping['color_range'] requires mapping['color'] to reference "
                "a temporal or numeric column (phase-space gradient)."
            )

    if color_scheme is not None and not isinstance(color_scheme, str):
        raise ValidationError(
            f"mapping['color_scheme'] must be a string palette name; "
            f"got {type(color_scheme).__name__}."
        )
    if isinstance(color_scheme, str):
        in_cat = color_scheme in _CATEGORICAL_PALETTES
        in_grad = color_scheme in _HEATMAP_GRADIENT_NAMES
        cat_names = sorted(_CATEGORICAL_PALETTES.keys())
        if not in_cat and not in_grad:
            raise ValidationError(
                f"mapping['color_scheme']={color_scheme!r} is not a "
                f"recognised palette. Categorical palettes: {cat_names}. "
                f"Heatmap / gradient palettes: blues, greens, reds, "
                f"viridis, plasma, magma, redblue, spectral, ..."
            )
        if is_heatmap_path and in_cat and not in_grad:
            raise ValidationError(
                f"mapping['color_scheme']={color_scheme!r} is a "
                f"categorical palette but chart_type='heatmap' needs a "
                f"gradient ramp (e.g. 'blues', 'viridis', 'redblue'). "
                f"Use color_scheme='blues' (sequential) or 'redblue' "
                f"(diverging-at-zero)."
            )
        if (not is_heatmap_path) and in_grad and not in_cat:
            color_field = _get_field(mapping, "color")
            if (
                chart_type in {"scatter", "scatter_multi"}
                and df is not None
                and _scatter_color_is_gradient(df, color_field)
            ):
                pass
            else:
                raise ValidationError(
                    f"mapping['color_scheme']={color_scheme!r} is a heatmap / "
                    f"gradient ramp but chart_type='{chart_type}' needs a "
                    f"categorical palette. Pick from {cat_names}, or pass "
                    f"mapping['color_map'] with explicit hex values."
                )

    color_map = mapping.get("color_map")
    if color_map is None:
        return
    if is_heatmap_path:
        raise ValidationError(
            "mapping['color_map'] is for categorical color encodings "
            "(multi_line, scatter_multi, bar+color, area+color, donut). "
            "On heatmap, override the ramp with mapping['color_scheme'] "
            "(e.g. 'blues', 'redblue')."
        )
    if isinstance(color_map, dict):
        for key, hex_val in color_map.items():
            # Booleans are int subclasses in Python; reject them so
            # ``{True: '#hex'}`` doesn't silently mean "slot 1".
            if isinstance(key, bool) or (
                not isinstance(key, str) and not isinstance(key, int)
            ):
                raise ValidationError(
                    f"mapping['color_map'] dict keys must be category "
                    f"strings (e.g. 'US') or positive integer legend slot "
                    f"positions (e.g. 2 for the second colour); got "
                    f"{type(key).__name__} {key!r}."
                )
            if isinstance(key, int) and key < 1:
                raise ValidationError(
                    f"mapping['color_map'] integer keys are 1-indexed "
                    f"legend slot positions; got {key} (must be >= 1; "
                    f"slot 1 is the first colour, slot 2 the second, ...)."
                )
            if not isinstance(hex_val, str) or not hex_val.startswith("#"):
                raise ValidationError(
                    f"mapping['color_map'][{key!r}]={hex_val!r} must be "
                    f"a hex string like '#1A2B3C'."
                )
        # Range-check int keys against the actual category count when
        # we have df + color_field. Surfaces "color_map={5: ...} on a
        # 3-category chart" at the boundary with an actionable message.
        color_field = mapping.get("color")
        if df is not None and color_field and color_field in df.columns:
            n_categories = (
                df[color_field].dropna().astype(str).nunique()
            )
            if n_categories > 0:
                for key in color_map.keys():
                    if isinstance(key, int) and not isinstance(key, bool):
                        if key > n_categories:
                            raise ValidationError(
                                f"mapping['color_map'] integer slot {key} "
                                f"is out of range; the chart's "
                                f"{color_field!r} column has "
                                f"{n_categories} categories (legal slots: "
                                f"1..{n_categories}). Use the named-key "
                                f"form ({{'<category>': '#hex'}}) or pick "
                                f"a slot in range."
                            )
    elif isinstance(color_map, (list, tuple)):
        for hex_val in color_map:
            if not isinstance(hex_val, str) or not hex_val.startswith("#"):
                raise ValidationError(
                    f"mapping['color_map'] entries must be hex strings "
                    f"like '#1A2B3C'; got {hex_val!r}."
                )
    else:
        raise ValidationError(
            f"mapping['color_map'] must be a list of hex strings or a "
            f"dict {{category: hex}}; got {type(color_map).__name__}."
        )


def _resolve_single_series_color(
    mapping: Dict[str, Any], skin_config: Dict[str, Any],
) -> str:
    """Resolve the single-series mark colour honouring PRISM's color kwargs.

    Used for chart paths without a categorical color scale (single-
    series multi_line, area, bar without color, scatter without
    color). When PRISM passes:

      - ``mapping['color_map'] = ['#hex', ...]`` (list): use ``[0]``
      - ``mapping['color_scheme'] = <categorical palette name>``: use
        the palette's slot 0

    Otherwise fall back to ``skin_config['primary_color']`` (the
    skin's brand mark colour). Dict-shape ``color_map`` is ignored on
    single-series paths because there is no category name to match.
    """
    color_map = mapping.get("color_map")
    if isinstance(color_map, (list, tuple)) and len(color_map) > 0:
        first = color_map[0]
        if isinstance(first, str) and first.startswith("#"):
            return first
    color_scheme = mapping.get("color_scheme")
    if isinstance(color_scheme, str) and color_scheme in _CATEGORICAL_PALETTES:
        return _CATEGORICAL_PALETTES[color_scheme][0]
    return skin_config.get("primary_color", "#003359")


def _resolve_categorical_color_scale(
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    color_field: Optional[str] = None,
    df: Optional[pd.DataFrame] = None,
) -> alt.Scale:
    """Resolve the categorical color scale honouring PRISM's color kwargs.

    Priority (highest wins):

      1. ``mapping['color_map']`` dict with two key types, mixable in
         the same dict:
           - **String keys** = category names (e.g. ``'US'``). Pin a
             named category to a specific hex.
           - **Integer keys** = 1-indexed legend slot positions
             (e.g. ``2`` = the second colour the user sees in the
             legend). Pin the Nth slot regardless of category name.
         Any category not pinned by either form falls back to the
         default categorical palette (or the palette named in
         ``mapping['color_scheme']`` when also set). Named-key wins
         over integer-key when both apply to the same slot.
      2. ``mapping['color_map']`` list of hex strings: ``range`` only,
         applied in legend order (Vega-Lite cycles through the list).
      3. ``mapping['color_scheme']`` resolves to a categorical palette
         name in ``_CATEGORICAL_PALETTES``: use that palette as
         ``range``.
      4. Fallback: skin's default categorical palette via
         ``_get_color_scale``.

    ``color_field`` + ``df`` are needed for the dict-shape ``color_map``
    case so we can enumerate categories and fill the missing ones from
    the default palette without leaving Vega-Lite to guess. Integer
    slot positions resolve against legend-sorted order
    (``_resolve_color_sort``) so "slot 2" matches what the user sees in
    the rendered legend, not raw pandas insertion order.
    """
    color_map = mapping.get("color_map")
    color_scheme = mapping.get("color_scheme")

    default_palette = (
        _CATEGORICAL_PALETTES.get(color_scheme, list(GS_PRIMARY["colors"]))
        if isinstance(color_scheme, str)
        else list(GS_PRIMARY["colors"])
    )

    if isinstance(color_map, dict):
        if color_field and df is not None and color_field in df.columns:
            categories = (
                df[color_field].dropna().astype(str).unique().tolist()
            )
        else:
            categories = [k for k in color_map.keys() if isinstance(k, str)]

        sort_order: Optional[List[str]] = None
        if df is not None and color_field and color_field in df.columns:
            sort_order = _resolve_color_sort(
                df, color_field, mapping.get("color_sort"),
            )
        legend_order = sort_order if sort_order is not None else list(categories)

        # Per Design Principle #7: pinning slot K must NOT shift any
        # other slot's colour. Each un-pinned slot keeps the colour it
        # would have under the default palette at THAT slot index, not
        # the next-available palette colour. (The previous "advance a
        # fallback counter only on un-pinned slots" pattern silently
        # collapsed every slot above a pin one position down the
        # palette, defeating the highlight-one intent.)
        cat_to_hex: Dict[str, str] = {}
        for slot_idx, cat in enumerate(legend_order):
            if cat in color_map:
                cat_to_hex[cat] = color_map[cat]
            elif (slot_idx + 1) in color_map:
                cat_to_hex[cat] = color_map[slot_idx + 1]
            else:
                cat_to_hex[cat] = default_palette[
                    slot_idx % len(default_palette)
                ]

        # Emit Scale with domain in pandas insertion order so existing
        # legend / sort behaviour is unchanged; range[i] is the colour
        # decided for categories[i] above.
        range_hexes = [
            cat_to_hex.get(
                cat, default_palette[i % len(default_palette)],
            )
            for i, cat in enumerate(categories)
        ]
        return alt.Scale(domain=categories, range=range_hexes)

    if isinstance(color_map, (list, tuple)):
        return alt.Scale(range=list(color_map))

    if isinstance(color_scheme, str) and color_scheme in _CATEGORICAL_PALETTES:
        return alt.Scale(range=_CATEGORICAL_PALETTES[color_scheme])

    return _get_color_scale(skin_config)


def _validate_opacity_value(value: Any, label: str) -> float:
    """Validate a single opacity in [0.0, 1.0]; return as float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(
            f"{label} must be a number between 0.0 and 1.0; "
            f"got {type(value).__name__} {value!r}."
        )
    opacity = float(value)
    if opacity < 0.0 or opacity > 1.0:
        raise ValidationError(
            f"{label} must be between 0.0 and 1.0; got {opacity}."
        )
    return opacity


def _validate_opacity_kwargs(
    mapping: Dict[str, Any], chart_type: str,
    df: Optional[pd.DataFrame] = None,
) -> None:
    """Validate ``mapping['opacity']`` and ``mapping['opacity_map']``.

    Mirrors ``_validate_color_kwargs`` key shapes (named category strings
    and 1-indexed legend slot integers). ``opacity_map`` targets
    categorical ``mapping['color']`` series on multi_line, area, bar,
    boxplot, donut, scatter, and related chart types; heatmap rejects
    it like ``color_map``.
    """
    opacity = mapping.get("opacity")
    if opacity is not None:
        _validate_opacity_value(opacity, "mapping['opacity']")

    opacity_map = mapping.get("opacity_map")
    if opacity_map is None:
        return

    color_field = mapping.get("color") or mapping.get("category")
    _categorical_opacity_types = {
        "multi_line", "timeseries", "scatter", "scatter_multi",
        "bar", "bar_horizontal", "area", "boxplot", "donut",
        "histogram",
    }
    if chart_type in _categorical_opacity_types and not color_field:
        raise ValidationError(
            "mapping['opacity_map'] needs mapping['color'] (or "
            "'category' on donut) to target per-series transparency. "
            f"chart_type={chart_type!r} has no color/category field. "
            f"Pass mapping['opacity']=<0.0-1.0> for uniform alpha, or "
            f"add mapping['color']='<series_col>'."
        )

    is_heatmap_path = chart_type == "heatmap"
    if is_heatmap_path:
        raise ValidationError(
            "mapping['opacity_map'] is for categorical color encodings "
            "(multi_line, scatter_multi, bar+color, area+color, donut). "
            "On heatmap, override the ramp with mapping['color_scheme'] "
            "or pass mapping['opacity'] for uniform cell alpha."
        )

    if isinstance(opacity_map, dict):
        for key, alpha_val in opacity_map.items():
            if isinstance(key, bool) or (
                not isinstance(key, str) and not isinstance(key, int)
            ):
                raise ValidationError(
                    f"mapping['opacity_map'] dict keys must be category "
                    f"strings (e.g. 'US') or positive integer legend slot "
                    f"positions (e.g. 2 for the second cluster); got "
                    f"{type(key).__name__} {key!r}."
                )
            if isinstance(key, int) and key < 1:
                raise ValidationError(
                    f"mapping['opacity_map'] integer keys are 1-indexed "
                    f"legend slot positions; got {key} (must be >= 1; "
                    f"slot 1 is the first cluster, slot 2 the second, ...)."
                )
            _validate_opacity_value(
                alpha_val, f"mapping['opacity_map'][{key!r}]",
            )
        color_field = mapping.get("color")
        if df is not None and color_field and color_field in df.columns:
            n_categories = (
                df[color_field].dropna().astype(str).nunique()
            )
            if n_categories > 0:
                for key in opacity_map.keys():
                    if isinstance(key, int) and not isinstance(key, bool):
                        if key > n_categories:
                            raise ValidationError(
                                f"mapping['opacity_map'] integer slot {key} "
                                f"is out of range; the chart's "
                                f"{color_field!r} column has "
                                f"{n_categories} categories (legal slots: "
                                f"1..{n_categories}). Use the named-key "
                                f"form ({{'<category>': 0.5}}) or pick a "
                                f"slot in range."
                            )
    elif isinstance(opacity_map, (list, tuple)):
        for alpha_val in opacity_map:
            _validate_opacity_value(
                alpha_val, "mapping['opacity_map'] entry",
            )
    else:
        raise ValidationError(
            f"mapping['opacity_map'] must be a list of opacity values "
            f"(0.0-1.0) or a dict {{category: opacity}}; got "
            f"{type(opacity_map).__name__}."
        )


def _resolve_categorical_opacity_encoding(
    mapping: Dict[str, Any],
    color_field: str,
    df: pd.DataFrame,
    default_opacity: float,
) -> Optional[alt.Opacity]:
    """Per-cluster opacity encoding when ``mapping['opacity_map']`` is set.

  Unpinned categories receive ``default_opacity`` (the auto density
  curve for scatters, or ``mapping['opacity']`` when that scalar is set).
  Returns ``None`` when no ``opacity_map`` — caller keeps mark-level opacity.
    """
    opacity_map = mapping.get("opacity_map")
    if opacity_map is None:
        return None

    categories = df[color_field].dropna().astype(str).unique().tolist()
    sort_order = _resolve_color_sort(
        df, color_field, mapping.get("color_sort"),
    )
    legend_order = sort_order if sort_order is not None else list(categories)

    cat_to_opacity: Dict[str, float] = {}
    if isinstance(opacity_map, dict):
        for slot_idx, cat in enumerate(legend_order):
            if cat in opacity_map:
                cat_to_opacity[cat] = _validate_opacity_value(
                    opacity_map[cat], f"mapping['opacity_map'][{cat!r}]",
                )
            elif (slot_idx + 1) in opacity_map:
                cat_to_opacity[cat] = _validate_opacity_value(
                    opacity_map[slot_idx + 1],
                    f"mapping['opacity_map'][{slot_idx + 1}]",
                )
            else:
                cat_to_opacity[cat] = default_opacity
    else:
        for slot_idx, cat in enumerate(legend_order):
            cat_to_opacity[cat] = _validate_opacity_value(
                opacity_map[slot_idx % len(opacity_map)],
                "mapping['opacity_map'] entry",
            )

    range_opacities = [
        cat_to_opacity.get(cat, default_opacity) for cat in categories
    ]
    return alt.Opacity(
        color_field,
        type="nominal",
        scale=alt.Scale(domain=categories, range=range_opacities),
        legend=None,
    )


def _prepare_categorical_opacity(
    mapping: Dict[str, Any],
    color_field: Optional[str],
    df: pd.DataFrame,
    base_mark_opacity: float,
) -> Tuple[float, Optional[alt.Opacity]]:
    """Resolve mark opacity + optional per-category ``opacity`` encoding.

    Honors ``mapping['opacity']`` (uniform) and ``mapping['opacity_map']``
    (per category / legend slot). When ``opacity_map`` is active the mark
    should use the returned ``1.0`` so the encoded channel controls alpha.
    """
    mark_opacity = base_mark_opacity
    scalar = mapping.get("opacity")
    if scalar is not None:
        mark_opacity = _validate_opacity_value(scalar, "mapping['opacity']")

    if not color_field or color_field not in df.columns:
        return mark_opacity, None
    if mapping.get("opacity_map") is None:
        return mark_opacity, None

    opacity_encoding = _resolve_categorical_opacity_encoding(
        mapping, color_field, df, mark_opacity,
    )
    if opacity_encoding is None:
        return mark_opacity, None
    return 1.0, opacity_encoding


def _categorical_legend(
    opacity_encoding: Optional[alt.Opacity],
    **kwargs: Any,
) -> alt.Legend:
    """Build a color legend; keep swatches opaque when marks use opacity_map."""
    if opacity_encoding is not None:
        kwargs["symbolOpacity"] = 1.0
    kwargs.setdefault("title", None)
    return alt.Legend(**_safe_legend_kwargs(**kwargs))


def _encode_categorical_color_and_opacity(
    chart: alt.Chart,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    color_field: str,
    df: pd.DataFrame,
    *,
    color_sort: Optional[List[str]] = None,
    opacity_encoding: Optional[alt.Opacity] = None,
    legend_kwargs: Optional[Dict[str, Any]] = None,
) -> alt.Chart:
    """Attach categorical ``color`` (+ optional ``opacity``) encodings."""
    legend = _categorical_legend(
        opacity_encoding, **(legend_kwargs or {}),
    )
    chart = chart.encode(
        color=alt.Color(
            color_field,
            type="nominal",
            scale=_resolve_categorical_color_scale(
                mapping, skin_config, color_field, df,
            ),
            sort=color_sort,
            legend=legend,
        ),
    )
    if opacity_encoding is not None:
        chart = chart.encode(opacity=opacity_encoding)
    return chart


def _scatter_multi_color_opacity(n: int) -> float:
    """Point opacity for the categorical multi-color scatter path.

    Scales down with point count so dense clusters stay readable.
    At low n (<= 50) returns the historical 0.85; as n grows, opacity
    drops via a power-law so overlapping dots stack additively into a
    legible density gradient instead of solid color blobs that swallow
    both density and category identity. Floors at 0.20 (any lower and
    individual points become invisible at the default mark size of 60).

    Formula: ``alpha = clamp(0.20, 0.85, 0.85 * (50 / n) ** 0.4)``

    Sample curve:
        n=  50 -> 0.85
        n= 100 -> 0.64
        n= 200 -> 0.49
        n= 500 -> 0.34
        n=1000 -> 0.26
        n=2000 -> 0.20  (floor)

    Single-color and gradient (temporal / numeric ``color_field``)
    scatters intentionally do NOT use this curve -- single-color keeps
    the skin default (0.7) because there is no color-overlap mud to
    avoid, and gradient sits at a static 0.85 because phase-space plots
    are typically dozens of points where the gradient itself encodes
    density via hue.
    """
    if n <= 0:
        return 0.85
    raw = 0.85 * (50.0 / float(n)) ** 0.4
    return max(0.20, min(0.85, raw))


# ===========================================================================
# MODULE: BUILDER HELPERS
# ===========================================================================

# Pre-compiled tenor regex: matches "1M", "10Y", "2.5Y", "30YB" etc.
_TENOR_PATTERN = re.compile(r"^(\d+\.\d+|\d+)[MYWD]B?$", re.IGNORECASE)

# Tenor unit -> approximate days (for sort ordering only).
_TENOR_UNIT_DAYS: Dict[str, float] = {
    "D": 1.0,
    "W": 7.0,
    "M": 30.4375,
    "Y": 365.25,
}


def _tenor_sort_key(tenor: str) -> float:
    """Approximate days-from-now value for sorting tenor strings.

    Treats unrecognized values as ``+inf`` so they sort to the end
    rather than crashing the sort.
    """
    s = str(tenor).strip().upper().rstrip("B")
    match = _TENOR_PATTERN.match(s + ("" if s.endswith(("M", "Y", "W", "D")) else ""))
    if not match:
        return float("inf")
    num = float(match.group(1))
    unit = s[len(match.group(1)):]
    return num * _TENOR_UNIT_DAYS.get(unit, 365.25)


def _infer_tenor_sort(unique_values: Any) -> Optional[List[str]]:
    """If at least 60% of unique x values look like tenors, return them
    in canonical ascending order (1M < 3M < 1Y < 10Y...). Otherwise
    return ``None`` (caller should fall back to default ordering).
    """
    values = [str(v).strip().upper() for v in unique_values]
    if not values:
        return None
    matches = sum(1 for v in values if _TENOR_PATTERN.match(v))
    if matches / max(len(values), 1) > 0.6:
        return sorted(values, key=_tenor_sort_key)
    return None


_RELATIVE_TIME_PATTERN = re.compile(
    r"(?i)^(today|now|spot|current|latest|"
    r"\d+\s*(d|day|days|w|week|weeks|m|mo|month|months|y|yr|year|years)\s*(ago)?)\s*$"
)


def _relative_time_sort_key(label: str) -> float:
    """Return a most-recent-first sort key for relative-time labels.

    'Today' / 'now' / 'spot' sorts first; '1Y ago' or '12M ago' sorts last.
    """
    s = str(label).strip().lower()
    if s in {"today", "now", "spot", "current", "latest"}:
        return 0.0
    m = re.search(r"(\d+)\s*(d|day|days|w|week|weeks|m|mo|month|months|y|yr|year|years)", s)
    if not m:
        return 0.0
    n = int(m.group(1))
    unit = m.group(2)
    if unit.startswith(("y", "yr")):
        days = n * 365.25
    elif unit.startswith(("m", "mo")):
        days = n * 30.44
    elif unit.startswith(("w",)):
        days = n * 7
    else:
        days = n
    return float(days)


def _infer_relative_time_sort(unique_values: Any) -> Optional[List[str]]:
    """Sort 'Today / 3M ago / 6M ago / 1Y ago' style labels with most
    recent first. Returns None if labels don't fit the pattern.
    """
    values = [str(v).strip() for v in unique_values]
    if not values:
        return None
    matches = sum(1 for v in values if _RELATIVE_TIME_PATTERN.match(v))
    if matches / max(len(values), 1) > 0.6:
        return sorted(values, key=_relative_time_sort_key)
    return None


def _resolve_color_sort(
    df: pd.DataFrame,
    color_field: Optional[str],
    explicit_sort: Optional[Any] = None,
) -> Optional[List[str]]:
    """Pick a sensible legend / color sort order.

    Priority:
      1. Explicit ``mapping['color_sort']`` / ``mapping['legend_sort']`` if
         the caller passed one.
      2. Tenor-style labels (1M, 3M, 1Y, 10Y...) -> canonical ladder.
      3. Relative-time labels (Today, 3M ago, ...) -> chronological.
      4. Otherwise preserve the DataFrame's first-seen order.
    """
    if explicit_sort is not None:
        return list(explicit_sort)
    if color_field is None or color_field not in df.columns:
        return None
    seen: List[str] = []
    for v in df[color_field].astype(str):
        if v not in seen:
            seen.append(v)
    if not seen:
        return None
    tenor_sort = _infer_tenor_sort(seen)
    if tenor_sort is not None:
        return tenor_sort
    relative_sort = _infer_relative_time_sort(seen)
    if relative_sort is not None:
        return relative_sort
    return seen


_LEGEND_MAX_WIDTH_FRAC: float = 0.25
"""Cap legend ``labelLimit`` at 25%% of canvas width (Phase 2 stress
probe T5b finding F2). Without this, 35-50 char series names like
"United States Treasury 10-Year Constant Maturity Yield" cause
Vega-Lite to reserve 40-50%% of canvas width for the legend column,
squashing the plot region. Pair with ``_validate_legend_labels`` so
overlong names raise ``LegendLabelTooLongError`` instead of silent
ellipsis truncation."""

_LEGEND_CHAR_WIDTH_PX: int = 7
"""Pixels per character assumed when deriving a char budget from
``labelLimit`` (matches the ``labelLimit // 7`` wrap estimate elsewhere)."""

_COMPOSITE_LEGEND_CELL_WIDTH_PX: int = 320
"""Cell widths at or below this threshold get composite-specific guidance
in ``LegendLabelTooLongError`` (4-pack compact = 280px, 6-pack = 260px)."""


def _legend_label_max_chars(chart_width: int) -> int:
    """Maximum colour-legend label length before Vega-Lite ellipsizes."""
    if chart_width <= 0:
        return 999
    legend_cap_px = int(chart_width * _LEGEND_MAX_WIDTH_FRAC)
    return max(1, legend_cap_px // _LEGEND_CHAR_WIDTH_PX)


def _color_legend_will_render(
    chart_type: str,
    mapping: Dict[str, Any],
    annotations: Optional[List["Annotation"]],
    *,
    suppress_lvl: bool = False,
    df: Optional[pd.DataFrame] = None,
) -> bool:
    """Return True when the categorical colour legend will be visible.

    Standalone ``multi_line`` / ``timeseries`` default to LastValueLabel
    (legend suppressed). Facet grids pass ``suppress_lvl=True`` (no LVL).
    Pack composites use LVL in every cell (``suppress_lvl=False``).
    Dual-axis always uses the colour legend. Scatter phase-space gradient
    (temporal/numeric ``color``) uses a continuous ramp, not a categorical
    legend -- returns False so label-length validation is skipped.
    """
    color_field = _get_field(mapping, "color")
    if not color_field:
        return False
    if (
        chart_type in {"scatter", "scatter_multi"}
        and df is not None
        and _scatter_color_is_gradient(df, color_field)
    ):
        return False
    if chart_type in {"multi_line", "timeseries", "area"}:
        if mapping.get("dual_axis_series"):
            return True
        if suppress_lvl:
            return True
        if mapping.get("legend") is True:
            return True
        if annotations and any(isinstance(a, LastValueLabel) for a in annotations):
            return False
        if _should_auto_inject_lvl(chart_type, mapping, annotations):
            return False
        return True
    return True


def _validate_legend_labels(
    df: pd.DataFrame,
    color_field: str,
    chart_width: int,
    mapping: Dict[str, Any],
    *,
    composite_cell: bool = False,
) -> None:
    """Raise ``LegendLabelTooLongError`` when any legend label exceeds budget."""
    if color_field not in df.columns:
        return
    max_chars = _legend_label_max_chars(chart_width)
    labels = [str(v) for v in df[color_field].unique()]
    offenders = sorted(
        {label for label in labels if len(label) > max_chars},
        key=lambda s: -len(s),
    )
    if not offenders:
        return

    shown = offenders[:5]
    offender_block = "\n".join(
        f"  - '{label}' ({len(label)} ch)" for label in shown
    )
    composite_hint = (
        " Composite cells are narrow -- use super-short series names "
        f"(aim <=6 chars in 4-pack / 6-pack; hard cap {max_chars} ch "
        f"at {chart_width}px cell width)."
        if composite_cell or chart_width <= _COMPOSITE_LEGEND_CELL_WIDTH_PX
        else ""
    )
    raise LegendLabelTooLongError(
        (
            f"Colour-legend labels in field '{color_field}' exceed the "
            f"{max_chars}-character budget for a {chart_width}px-wide "
            f"chart ({len(offenders)} offender(s), longest is "
            f"{max(offenders, key=len)!r}). Vega-Lite truncates legend "
            f"text with an ellipsis -- shorten names in the DataFrame "
            f"before make_chart() / make_*pack_*().{composite_hint}\n"
            f"Offenders ({len(shown)} of {len(offenders)} shown, longest first):\n"
            f"{offender_block}"
        ),
        offending_names=offenders,
        color_field=color_field,
        mapping=mapping,
        max_chars=max_chars,
        chart_width=chart_width,
    )


def _calculate_legend_config(
    df: pd.DataFrame,
    color_field: str,
    base_config: Dict[str, Any],
    chart_width: Optional[int] = None,
) -> Dict[str, Any]:
    """Compute a legend kwargs dict that adapts to label length.

    When labels are short, uses compact ``rowPadding=2`` and explicitly
    omits ``clipHeight`` (Altair rejects ``clipHeight=None``). When
    labels exceed the base ``labelLimit``, increases ``labelLimit`` and
    adds dynamic ``clipHeight`` so wrapped lines don't overlap.

    Class-8-style absorption (F2 from Phase 2 stress probe): when
    ``chart_width`` is supplied, cap the resulting ``labelLimit`` at
    ``_LEGEND_MAX_WIDTH_FRAC`` (25%%) of canvas width so very long
    series names get ellipsis-truncated by Vega-Lite at render time
    instead of consuming half the canvas. The cap is applied to the
    final config returned (works on both the short-labels and
    long-labels branches).
    """
    config = dict(base_config) if base_config else {}
    if color_field not in df.columns:
        return config

    unique_labels = df[color_field].unique()
    max_label_len = (
        max(len(str(label)) for label in unique_labels) if len(unique_labels) > 0 else 0
    )
    chars_before_wrap = config.get("labelLimit", 300) // 7

    if max_label_len > chars_before_wrap:
        config["labelLimit"] = 800
        config["clipHeight"] = 50 + (max_label_len // max(chars_before_wrap, 1)) * 20
        config["rowPadding"] = 8
    else:
        config["labelLimit"] = max(300, max_label_len * 8)
        config.pop("clipHeight", None)
        config["rowPadding"] = 2

    # F2 cap (apply last so it wins on both branches).
    if chart_width is not None and chart_width > 0:
        legend_cap_px = int(chart_width * _LEGEND_MAX_WIDTH_FRAC)
        if config.get("labelLimit", 0) > legend_cap_px:
            logger.info(
                "[_calculate_legend_config] F2 cap fired: labelLimit "
                "%d -> %d (cap %.0f%% of %dpx canvas).",
                config["labelLimit"], legend_cap_px,
                _LEGEND_MAX_WIDTH_FRAC * 100, chart_width,
            )
            config["labelLimit"] = legend_cap_px

    return config


def _safe_field(name: Any) -> Any:
    """Strip control characters from a field name so it survives Vega-Lite
    JS expression parsing. Non-string inputs pass through unchanged.
    """
    if isinstance(name, str):
        return re.sub(r"[\r\n\t]", "", name)
    return name


def _build_tooltip(
    mapping: Dict[str, Any],
    chart_type: str,
    df: pd.DataFrame,
) -> List[alt.Tooltip]:
    """Build a list of ``alt.Tooltip`` encodings appropriate for the chart.

    Always includes x, y, color (if present), and size (if present).
    Chart-specific overrides:
      - ``histogram``: bin tooltip + count
      - ``heatmap``: include the value field
      - ``donut``: category + value
      - ``boxplot``: deferred to Altair's automatic boxplot tooltips
    """
    tooltips: List[alt.Tooltip] = []

    x_field = _safe_field(_get_field(mapping, "x"))
    if x_field and x_field in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[x_field]):
            tooltips.append(
                alt.Tooltip(x_field, type="temporal", format="%b %d, %Y", title="Date")
            )
        elif pd.api.types.is_numeric_dtype(df[x_field]):
            tooltips.append(
                alt.Tooltip(
                    x_field, type="quantitative", format=".2f",
                    title=x_field.replace("_", " ").title(),
                )
            )
        else:
            tooltips.append(
                alt.Tooltip(
                    x_field, type="nominal",
                    title=x_field.replace("_", " ").title(),
                )
            )

    y_field = _safe_field(_get_field(mapping, "y"))
    if y_field and y_field in df.columns and pd.api.types.is_numeric_dtype(df[y_field]):
        y_max = df[y_field].abs().max()
        if pd.notna(y_max) and y_max > 1_000_000:
            fmt = ".0f"
        elif pd.notna(y_max) and y_max > 100:
            fmt = ".1f"
        else:
            fmt = ".2f"
        tooltips.append(
            alt.Tooltip(
                y_field, type="quantitative", format=fmt,
                title=y_field.replace("_", " ").title(),
            )
        )

    color_field = _safe_field(_get_field(mapping, "color"))
    if color_field and color_field in df.columns:
        tooltips.append(alt.Tooltip(color_field, type="nominal", title="Series"))

    size_field = _safe_field(_get_field(mapping, "size"))
    if size_field and size_field in df.columns:
        tooltips.append(
            alt.Tooltip(
                size_field, type="quantitative", format=".2f",
                title=size_field.replace("_", " ").title(),
            )
        )

    if chart_type == "histogram" and x_field:
        tooltips = [
            alt.Tooltip(f"{x_field}:Q", bin=True, title="Bin Range"),
            alt.Tooltip("count()", title="Count", format=","),
        ]
    elif chart_type == "heatmap":
        value_field = _get_field(mapping, "value") or _get_field(mapping, "z")
        if value_field and value_field in df.columns:
            if pd.api.types.is_numeric_dtype(df[value_field]):
                tooltips.append(
                    alt.Tooltip(
                        value_field, type="quantitative",
                        format=".2f", title="Value",
                    )
                )
            else:
                tooltips.append(
                    alt.Tooltip(value_field, type="nominal", title="Value")
                )
    elif chart_type == "donut":
        theta_field = (
            _get_field(mapping, "theta")
            or _get_field(mapping, "value")
            or _get_field(mapping, "y")
        )
        category_field = _get_field(mapping, "color") or _get_field(mapping, "category")
        tooltips = []
        if category_field and category_field in df.columns:
            tooltips.append(alt.Tooltip(category_field, type="nominal", title="Category"))
        if theta_field and theta_field in df.columns:
            tooltips.append(
                alt.Tooltip(theta_field, type="quantitative", format=".1f", title="Value")
            )

    return tooltips


def _force_data_embedding(chart: alt.Chart, df: pd.DataFrame) -> alt.Chart:
    """Force inline Vega-Lite ``data: {values: ...}`` embedding.

    Altair occasionally serializes data as named-dataset references
    (``data: {name: 'data-abc'}`` + ``datasets: {...}``), which doesn't
    survive the static-spec / vl-convert PNG path. Re-attaching via
    ``alt.Data(values=...)`` guarantees the spec carries the data
    inline. Datetime columns are pre-formatted to ISO strings so they
    round-trip through JSON cleanly.
    """
    df_export = df.copy()
    for col in df_export.columns:
        if pd.api.types.is_datetime64_any_dtype(df_export[col]):
            df_export[col] = df_export[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
    return chart.properties(data=alt.Data(values=df_export.to_dict(orient="records")))


def _shorten_legend_labels(
    df: pd.DataFrame,
    color_field: str,
    max_chars: int = 25,
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Shorten long legend labels while preserving meaning.

    Vega-Lite doesn't support text wrapping in legends (it just
    truncates with an ellipsis). When labels are longer than
    ``max_chars`` this helper applies a series of intelligent
    shortening rules:

      1. Strip parenthetical suffixes (``"(YoY %)"``, ``"(Index)"``).
      2. Replace common multi-word phrases with abbreviations
         (``"Year-over-Year"`` -> ``"YoY"``, ``"Quarter-over-Quarter"``
         -> ``"QoQ"``).
      3. Truncate with ellipsis if still too long.

    Returns:
        Tuple of ``(modified_df, label_mapping)`` where ``label_mapping``
        maps **short labels back to full labels** so the tooltip layer
        can show the original on hover. The DataFrame's color column
        is replaced in place with the shortened labels.
    """
    unique_labels = df[color_field].unique()
    label_mapping: Dict[str, str] = {}

    abbreviations = {
        "Year-over-Year": "YoY",
        "Quarter-over-Quarter": "QoQ",
        "Month-over-Month": "MoM",
        "Growth": "Gr",
        "Index": "Idx",
        "Percent": "%",
    }

    for label in unique_labels:
        full = str(label)
        if len(full) <= max_chars:
            label_mapping[full] = full
            continue

        short = re.sub(r"\s*\(.+?\)$", "", full)  # Strip "(YoY %)"
        for full_term, abbrev in abbreviations.items():
            short = short.replace(full_term, abbrev)
        if len(short) > max_chars:
            short = short[: max_chars - 3] + "..."
        label_mapping[short] = full

    df_modified = df.copy()
    reverse_mapping = {v: k for k, v in label_mapping.items()}
    df_modified[color_field] = df_modified[color_field].map(
        lambda x: reverse_mapping.get(str(x), str(x))
    )
    return df_modified, label_mapping


def _get_y_axis(
    skin_config: Dict[str, Any],
    title: Optional[str] = None,
    orient: Optional[str] = None,
) -> alt.Axis:
    """Build a y-axis ``alt.Axis`` with skin-derived defaults.

    Pulls ``orient`` from the skin's ``config.axis.orient`` (defaults
    to ``'left'``).
    """
    axis_config = skin_config.get("config", {}).get("axis", {})
    resolved_orient = orient or axis_config.get("orient", "left")
    return alt.Axis(
        orient=resolved_orient,
        title=title,
    )


def _ensure_data_embedded(
    spec: Dict[str, Any],
    df: pd.DataFrame,
) -> Dict[str, Any]:
    """Ensure data values are directly embedded in the spec.

    Altair sometimes generates specs with ``data: {name: 'data-xxx'}``
    and a separate ``datasets: {'data-xxx': [...]}`` structure. That
    works for interactive rendering but breaks the static-spec /
    vl-convert pipeline (and breaks ``alt.LayerChart.from_dict``
    reconstruction in composites).

    This walks the spec and ensures ``data.values`` is populated:

      - If ``data.name`` references an entry in ``datasets``, embed
        that entry as ``data.values``.
      - Otherwise embed the original DataFrame directly.

    Datetime columns in the DataFrame are pre-stringified to
    ``YYYY-MM-DDTHH:MM:SS`` so JSON round-trips cleanly.
    """
    df_copy = df.copy()
    for col in df_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
            df_copy[col] = df_copy[col].apply(
                lambda x: x.strftime("%Y-%m-%dT%H:%M:%S") if pd.notna(x) else None
            )
    data_values = df_copy.to_dict(orient="records")

    data_obj = spec.get("data")
    if isinstance(data_obj, dict):
        if "name" in data_obj and "values" not in data_obj:
            ds_name = data_obj["name"]
            if "datasets" in spec and ds_name in spec["datasets"]:
                spec["data"] = {"values": spec["datasets"][ds_name]}
            else:
                spec["data"] = {"values": data_values}
        elif "values" not in data_obj and "url" not in data_obj:
            spec["data"] = {"values": data_values}
    else:
        spec["data"] = {"values": data_values}

    return spec


def _ensure_data_in_layers(
    spec: Dict[str, Any],
    df: pd.DataFrame,
) -> Dict[str, Any]:
    """Ensure data is properly embedded in layered chart specs.

    When Altair generates a ``layer`` spec, sub-layers may reference a
    named dataset that lives at the top-level ``datasets`` block.
    During the static-spec round-trip those dataset references can
    fail. This helper:

      - Embeds the DataFrame at the top level if neither layers nor
        the top-level have data.
      - Drops empty ``data`` keys on individual layers (they inherit
        from the top-level).
    """
    if "layer" not in spec:
        return spec

    has_data_in_layers = any(
        isinstance(layer.get("data"), dict) and layer["data"].get("values")
        for layer in spec.get("layer", [])
    )
    has_top_level_data = (
        isinstance(spec.get("data"), dict) and spec["data"].get("values")
    )

    if not has_data_in_layers and not has_top_level_data:
        df_copy = df.copy()
        for col in df_copy.columns:
            if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].apply(
                    lambda x: x.strftime("%Y-%m-%dT%H:%M:%S") if pd.notna(x) else None
                )
        spec["data"] = {"values": df_copy.to_dict(orient="records")}

    for layer in spec.get("layer", []):
        if (
            "data" in layer
            and isinstance(layer["data"], dict)
            and not layer["data"].get("values")
        ):
            del layer["data"]

    return spec


def _validate_spec_has_data(
    spec: Dict[str, Any],
    chart_type: str,
    df: pd.DataFrame,
    mapping: Dict[str, Any],
) -> None:
    """Final pre-PNG validation: confirm the spec actually has plottable data.

    Catches the silent-empty-chart failure mode where validation passed
    upstream but data never propagated to the rendered spec. Walks the
    spec recursively and counts:

      1. Total data records (top-level + datasets + layer-level).
      2. Records with valid (non-null) ``x`` AND ``y`` values.

    Raises:
        ValidationError: If the spec contains no data records, or no
            records with valid x/y pairs (chart would render empty),
            or fewer than 2 records for chart types that need lines
            (timeseries / multi_line / area).
        ValidationError: If layered charts have only annotation layers
            (rule / text / rect) and no data layers.
    """
    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")

    # Dual-axis charts rename the user's y column to per-axis fields
    # (e.g. ``2s10s_bp`` left + ``wti_bbl`` right). The validator accepts a
    # record as ``valid`` if it has any of these alternative y fields.
    dual_cfg = mapping.get("dual_axis_config") or {}
    y_field_alts: List[str] = [f for f in (
        dual_cfg.get("y_field_left"),
        dual_cfg.get("y_field_right"),
    ) if f]
    y_fields_to_check: List[str] = [f for f in [y_field, *y_field_alts] if f]

    def _extract_data_values(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
        values: List[Dict[str, Any]] = []
        if isinstance(obj.get("data"), dict) and "values" in obj["data"]:
            values.extend(obj["data"]["values"])
        if "datasets" in obj:
            for ds in obj["datasets"].values():
                if isinstance(ds, list):
                    values.extend(ds)
        for key in ("layer", "hconcat", "vconcat", "concat"):
            if key in obj and isinstance(obj[key], list):
                for item in obj[key]:
                    values.extend(_extract_data_values(item))
        return values

    all_values = _extract_data_values(spec)

    if x_field and y_fields_to_check:
        null_x = sum(1 for r in all_values if r.get(x_field) is None)
        if all_values and null_x == len(all_values):
            raise ValidationError(
                "SPEC VALIDATION ERROR: All x-axis values are null.\n"
                "This indicates a datetime conversion failure.\n"
                "Check for timezone-aware datetimes or NaT values."
            )

    if not all_values:
        raise ValidationError(
            "SPEC VALIDATION ERROR: No data values found in Vega-Lite spec.\n"
            "The chart would render with an empty body.\n"
            f"DataFrame shape: {df.shape}\n"
            f"Mapping: {mapping}\n"
            "This is likely a data embedding failure."
        )

    if x_field and y_fields_to_check:
        valid_records = sum(
            1 for record in all_values
            if isinstance(record, dict)
            and record.get(x_field) is not None
            and any(record.get(f) is not None for f in y_fields_to_check)
        )
        if valid_records == 0:
            sample = all_values[:3] if all_values else []
            raise ValidationError(
                f"SPEC VALIDATION ERROR: Data values don't contain valid "
                f"x/y pairs.\nLooking for fields: {x_field!r}, "
                f"{y_fields_to_check!r}\n"
                f"Total records in spec: {len(all_values)}\n"
                f"Records with valid x AND y: 0\n"
                f"Sample records: {sample}\n"
                "The chart would render with no visible lines."
            )
        if valid_records < 2 and chart_type in {"timeseries", "multi_line", "area"}:
            raise ValidationError(
                f"SPEC VALIDATION ERROR: Only {valid_records} valid data "
                f"point(s) in spec.\nChart type {chart_type!r} requires at "
                "least 2 points.\nChart may have been filtered during spec "
                "generation."
            )

    # Layered charts: ensure at least one data layer (vs. annotation-only).
    # Heatmaps use ``rect`` for data and ``text`` for cell labels --
    # both should count as data layers (not annotations) when the chart
    # type is heatmap.
    if "layer" in spec:
        if chart_type == "heatmap":
            # Heatmap: skip the data-vs-annotation accounting.
            return
        # Marks that count as DATA layers regardless of whether the layer
        # has its own ``data.values`` -- they may inherit data from the
        # top-level spec (which is what ``_force_data_embedding`` does).
        DATA_MARKS = {"bar", "line", "area", "point", "arc", "rect", "circle", "square"}

        def _count_layers(layer_list: List[Dict[str, Any]]) -> Tuple[int, int]:
            """Recurse through nested LayerChart specs to count data vs
            annotation layers. Bullet, scatter+trendline, and dual-axis
            charts can produce nested layers like ``layer(layer(a, b), c)``.
            """
            data_count = 0
            annotation_count = 0
            for layer in layer_list:
                if "layer" in layer and isinstance(layer["layer"], list):
                    d, a = _count_layers(layer["layer"])
                    data_count += d
                    annotation_count += a
                    continue
                mark = layer.get("mark", {})
                mark_type = mark.get("type") if isinstance(mark, dict) else mark
                layer_data = (
                    layer.get("data", {}).get("values", [])
                    if isinstance(layer.get("data"), dict)
                    else []
                )
                if mark_type in DATA_MARKS:
                    data_count += 1
                elif mark_type in {"rule", "text"}:
                    annotation_count += 1
                elif layer_data:
                    data_count += 1
            return data_count, annotation_count

        data_layer_count, annotation_layer_count = _count_layers(spec["layer"])
        if data_layer_count == 0 and annotation_layer_count > 0:
            raise ValidationError(
                f"SPEC VALIDATION ERROR: Layered chart has no data layers.\n"
                f"Found {annotation_layer_count} annotation layer(s) but 0 "
                "data layers.\nThe chart would render with only annotations "
                "visible.\nCheck that data is being embedded in the correct "
                "layer."
            )


def _apply_heatmap_config(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Apply heatmap-specific configuration overrides.

    Belt-and-suspenders ``grid``/``domain``/``ticks`` suppression on the
    ``config.axis`` block. The skin already disables grid globally, but
    heatmaps are the one chart type where any axis chrome bleeding
    through cells produces white-line artifacts, so we patch the spec
    directly to make the suppression unconditional.

    Returns a deep-copied spec; the input is not mutated.
    """
    spec = copy.deepcopy(spec)
    spec.setdefault("config", {})
    spec["config"].setdefault("axis", {})
    spec["config"]["axis"]["grid"] = False
    spec["config"]["axis"]["domain"] = False
    spec["config"]["axis"]["ticks"] = False
    spec["config"].setdefault("view", {})
    spec["config"]["view"]["strokeWidth"] = 0
    return spec


# ===========================================================================
# MODULE: CHART BUILDERS
# ===========================================================================

def _build_timeseries(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Single-axis time-series line chart.

    Issue #2 fix: explicitly configure single y-axis (left only) to
    prevent spurious +y axis labels. No ``resolve_scale()`` is applied
    on this path.

    Pipeline:
      1. Log entry: shape, mapping, columns, non-null counts, dtypes,
         first/last row samples (silent_failures.md spec).
      2. NaN interpolation for line continuity:
         - Interior NaNs interpolated linearly.
         - Leading NaNs back-filled so the line starts at first valid pt.
         - Trailing NaNs truncated (NOT forward-filled) -- forward-fill
           would draw a misleading flat line into the future.
      3. Datetime coercion of the x column.
      4. Field existence + non-null guards.
      5. Y-axis domain via ``calculate_y_axis_domain``
         (prevent_zero_start=True so flat lines stay visible).
      6. Build chart with skin primary color (single series) or full
         palette + dynamic legend config (multi-series via color).
      7. Force inline data embedding so static-spec PNG render works.
    """
    # ---- LOGGING: entry (silent_failures.md spec) -----------------------
    logger.debug("[_build_timeseries] START")
    logger.debug("[_build_timeseries] df.shape=%s, mapping=%s", df.shape, mapping)
    logger.debug("[_build_timeseries] columns: %s", list(df.columns))

    if len(df) == 0:
        logger.error("[_build_timeseries] EMPTY DATAFRAME - chart will fail!")
        raise ValidationError(
            "DataFrame is empty. Cannot create time-series chart from empty data."
        )

    schema_info = {col: str(dtype) for col, dtype in df.dtypes.items()}
    logger.debug("[_build_timeseries] schema: %s", schema_info)
    logger.debug("[_build_timeseries] non-null: %s", df.notna().sum().to_dict())
    if len(df) > 0:
        logger.debug("[_build_timeseries] first row: %s", df.iloc[0].to_dict())
        logger.debug("[_build_timeseries] last row: %s", df.iloc[-1].to_dict())

    # ---- field extraction + datetime coercion ----------------------------
    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    color_field = _get_field(mapping, "color")
    logger.debug(
        "[_build_timeseries] x_field=%s, y_field=%s, color_field=%s",
        x_field, y_field, color_field,
    )

    if x_field is None:
        raise ValidationError(
            "_build_timeseries requires mapping['x']; got None."
        )
    if y_field is None:
        raise ValidationError(
            "_build_timeseries requires mapping['y']; got None."
        )

    if x_field not in df.columns:
        logger.error(
            "[_build_timeseries] x_field %r not in columns: %s",
            x_field, list(df.columns),
        )
        raise ValidationError(
            f"x_field '{x_field}' not found in DataFrame columns: "
            f"{list(df.columns)}"
        )
    if y_field not in df.columns:
        logger.error(
            "[_build_timeseries] y_field %r not in columns: %s",
            y_field, list(df.columns),
        )
        raise ValidationError(
            f"y_field '{y_field}' not found in DataFrame columns: "
            f"{list(df.columns)}"
        )

    zero_fill = bool(mapping.get("zero_fill"))
    if zero_fill:
        if color_field and color_field in df.columns:
            raise ValidationError(
                "mapping['zero_fill']=True requires a single-series chart; "
                "omit mapping['color'] or melt to one y column."
            )
        if mapping.get("dual_axis_series"):
            raise ValidationError(
                "mapping['zero_fill']=True is incompatible with "
                "dual_axis_series; use a single y-axis line."
            )
        if mapping.get("strokeDash"):
            raise ValidationError(
                "mapping['zero_fill']=True is incompatible with strokeDash."
            )
        if mapping.get("scale_type") == "log":
            raise ValidationError(
                "mapping['zero_fill']=True is incompatible with log y-scale."
            )

    df = df.copy()

    # NaN interpolation for visual continuity. Lines should always be
    # connected; gaps in y create discontinuities. We interpolate
    # interior NaNs, back-fill leading NaNs, and TRUNCATE trailing
    # NaNs (forward-fill would create misleading flat lines).
    def _interp_truncate(s: pd.Series) -> pd.Series:
        if s.isna().all():
            return s
        last_valid_idx = s.last_valid_index()
        s = s.interpolate(method="linear", limit_direction="backward")
        if last_valid_idx is not None:
            s.loc[s.index > last_valid_idx] = np.nan
        return s

    if color_field and color_field in df.columns:
        df[y_field] = df.groupby(color_field)[y_field].transform(_interp_truncate)
        logger.debug(
            "[_build_timeseries] NaN interp/truncate applied per-group "
            "(color=%s)", color_field,
        )
    else:
        df[y_field] = _interp_truncate(df[y_field])
        logger.debug(
            "[_build_timeseries] NaN interp/truncate applied (single series)"
        )

    # FIX RC1: datetime coercion uses the actual mapping field, not 'date'.
    # Allows x columns named 'datetime', 'timestamp', etc.
    # Skip when caller declared ordinal x -- strings like ``05/27 03:00``
    # must not be re-parsed (OutOfBoundsDatetime on ambiguous formats).
    if (
        x_field in df.columns
        and not pd.api.types.is_datetime64_any_dtype(df[x_field])
        and mapping.get("x_type") != "ordinal"
    ):
        df[x_field] = pd.to_datetime(df[x_field])

    # ---- non-null sanity check (final gate before encoding) -------------
    x_non_null = int(df[x_field].notna().sum())
    y_non_null = int(df[y_field].notna().sum())
    logger.debug(
        "[_build_timeseries] non-null counts: x=%d, y=%d",
        x_non_null, y_non_null,
    )
    if x_non_null == 0:
        logger.error(
            "[_build_timeseries] x_field %r has ALL None values!", x_field
        )
        raise ValidationError(
            f"x_field '{x_field}' has no valid values; cannot draw line."
        )
    if y_non_null == 0:
        logger.error(
            "[_build_timeseries] y_field %r has ALL None values!", y_field
        )
        raise ValidationError(
            f"y_field '{y_field}' has no valid values; cannot draw line."
        )

    # ---- y-axis domain (prevent zero-start flattening) ------------------
    fill_baseline = float(mapping.get("zero_fill_baseline", 0)) if zero_fill else None
    y_min, y_max = calculate_y_axis_domain(
        df[y_field],
        handle_outliers=False,
        prevent_zero_start=not zero_fill,
    )
    if zero_fill and fill_baseline is not None:
        y_min = min(y_min, fill_baseline)
        y_max = max(y_max, fill_baseline)
    logger.debug(
        "[_build_timeseries] y-axis domain: [%.4f, %.4f]", y_min, y_max
    )

    # ---- auto log-scale detection --------------------------------------
    # When max/min ratio > 100 and all values are positive, a linear
    # y-axis squashes the early portion of the series against zero. Apply
    # a log scale so order-of-magnitude moves stay readable. Caller can
    # force linear by passing mapping['scale_type'] = 'linear'.
    scale_override = mapping.get("scale_type")
    use_log = (
        scale_override == "log"
        or (scale_override is None and should_use_log_scale(df[y_field]))
    )
    if zero_fill and use_log:
        raise ValidationError(
            "mapping['zero_fill']=True is incompatible with log y-scale."
        )
    if use_log:
        logger.info(
            "[_build_timeseries] auto-applying log y-scale (max/min > 100)"
        )
        # Log scale needs strictly positive bounds; recompute from the data
        # without the linear padding (a negative or zero domain breaks log).
        s = pd.to_numeric(df[y_field], errors="coerce").dropna()
        s_pos = s[s > 0]
        log_min = float(s_pos.min()) if len(s_pos) else 1.0
        log_max = float(s_pos.max()) if len(s_pos) else 10.0
        # Pad the domain by half a decade on each side.
        y_scale = alt.Scale(type="log", domain=[log_min * 0.7, log_max * 1.3])
    else:
        y_scale = alt.Scale(domain=[y_min, y_max])

    # ---- titles ---------------------------------------------------------
    # x_title is always None for time series (date axis is self-evident).
    # Publish the temporal x type so annotation layers inherit it (see
    # ``_annotation_x_axis_type``); a time-series x is always temporal here
    # because the dispatcher routes non-temporal x to ``_build_profile_line``.
    mapping["_x_axis_type"] = "temporal"
    x_axis = alt.Axis(title=None, titleFontWeight="normal")
    y_title = _format_label(y_field, mapping, "y")
    _validate_y_axis_label(y_title, mapping)
    y_axis = alt.Axis(title=y_title, titleFontWeight="normal")

    # ---- chart construction --------------------------------------------
    mark_config = skin_config.get("mark_config", {}).get("line", {})
    primary_color = _resolve_single_series_color(mapping, skin_config)
    tooltips = _build_tooltip(mapping, "multi_line", df)
    line_opacity, opacity_encoding = _prepare_categorical_opacity(
        mapping,
        color_field if (color_field and color_field in df.columns) else None,
        df,
        mark_config.get("opacity", 1.0),
    )

    chart = (
        alt.Chart(df)
        .mark_line(
            strokeWidth=mark_config.get("strokeWidth", 2),
            interpolate=mark_config.get("interpolate", "linear"),
            clip=True,
            color=primary_color,
            opacity=line_opacity,
        )
        .encode(
            x=alt.X(x_field, type="temporal", axis=x_axis),
            y=alt.Y(
                y_field,
                type="quantitative",
                axis=y_axis,
                scale=y_scale,
            ),
            tooltip=tooltips,
        )
        .properties(width=width, height=height)
    )

    if color_field and color_field in df.columns:
        legend_title = _format_label(color_field, mapping, "color")
        base_legend_config = skin_config.get("config", {}).get("legend", {})
        dynamic_legend_cfg = _calculate_legend_config(
            df, color_field, base_legend_config, chart_width=width,
        )
        color_sort = _resolve_color_sort(
            df, color_field, mapping.get("color_sort") or mapping.get("legend_sort"),
        )
        chart = _encode_categorical_color_and_opacity(
            chart,
            mapping,
            skin_config,
            color_field,
            df,
            color_sort=color_sort,
            opacity_encoding=opacity_encoding,
            legend_kwargs={
                "labelLimit": dynamic_legend_cfg.get("labelLimit", 300),
                "rowPadding": dynamic_legend_cfg.get("rowPadding", 2),
                "clipHeight": dynamic_legend_cfg.get("clipHeight"),
            },
        )
        logger.debug(
            "[_build_timeseries] color encoding: %s (title=%r) sort=%s",
            color_field, legend_title, color_sort,
        )

    if zero_fill:
        pos_color = mapping.get("zero_fill_positive", _DEFAULT_ZERO_FILL_POSITIVE)
        neg_color = mapping.get("zero_fill_negative", _DEFAULT_ZERO_FILL_NEGATIVE)
        area_neg, area_pos = _build_baseline_fill_layers(
            df,
            x_field,
            y_field,
            fill_baseline,
            y_scale,
            x_axis,
            y_axis,
            pos_color,
            neg_color,
            width,
            height,
        )
        chart = alt.layer(area_neg, area_pos, chart)
        logger.debug(
            "[_build_timeseries] zero_fill baseline=%.4g pos=%s neg=%s",
            fill_baseline, pos_color, neg_color,
        )

    chart = _force_data_embedding(chart, df)

    # ---- spec sanity logging --------------------------------------------
    final_spec = chart.to_dict()
    logger.debug(
        "[_build_timeseries] spec data type: %s, has values: %s, has datasets: %s",
        type(final_spec.get("data")).__name__,
        "values" in final_spec.get("data", {}) if isinstance(final_spec.get("data"), dict) else False,
        "datasets" in final_spec,
    )
    return chart


def _build_multi_line(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Multi-series time-series chart, with optional dual y-axis support.

    Single-axis path:
      Equivalent to ``_build_timeseries`` plus a per-series strokeDash
      encoding when ``mapping['strokeDash']`` is set.

    Dual-axis path (``mapping['dual_axis_series']`` provided):
      Splits the long-format DataFrame into "left" and "right" subsets,
      computes independent y-domains for each, and layers two charts
      with ``resolve_scale(y="independent")``. Stashes a
      ``dual_axis_config`` dict back into ``mapping`` so
      ``render_annotations`` can encode HLines against the correct axis.
      Honors ``invert_right_axis=True`` for the standard rates pattern
      (up = bullish on both axes).
    """
    dual_axis_series = mapping.get("dual_axis_series") or []
    if not dual_axis_series:
        return _build_multi_line_single_axis(df, mapping, skin_config, width, height)

    return _build_multi_line_dual_axis(df, mapping, skin_config, width, height)


def _build_multi_line_single_axis(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Multi-series multi_line on a single y-axis (with optional strokeDash)."""
    chart = _build_timeseries(df, mapping, skin_config, width, height)

    stroke_dash_field = mapping.get("strokeDash")
    if not stroke_dash_field or stroke_dash_field not in df.columns:
        return chart

    # Build a compact strokeDash scale.
    explicit_scale = mapping.get("strokeDashScale")
    if explicit_scale:
        scale = alt.Scale(
            domain=explicit_scale.get("domain"),
            range=explicit_scale.get("range"),
        )
    else:
        unique_dashes = list(df[stroke_dash_field].unique())
        if len(unique_dashes) == 2:
            dash_range: List[List[int]] = [[1, 0], [6, 4]]
        elif len(unique_dashes) == 3:
            dash_range = [[1, 0], [6, 4], [2, 2]]
        else:
            dash_range = []  # Let Altair auto-assign.
        scale = (
            alt.Scale(domain=unique_dashes, range=dash_range) if dash_range else alt.Scale()
        )

    legend = (
        alt.Legend(title=None)
        if mapping.get("strokeDashLegend", False)
        else None
    )
    # ``stroke_dash_field`` must carry an explicit type suffix here:
    # ``_build_timeseries`` already attached the data to the chart, but
    # Vega-Lite's `strokeDash` channel doesn't auto-infer field type from
    # detached datasets and Altair raises ValueError without the suffix.
    chart = chart.encode(
        strokeDash=alt.StrokeDash(f"{stroke_dash_field}:N", scale=scale, legend=legend)
    )
    return chart


def _build_multi_line_dual_axis(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Two-axis layered line chart (independent left + right y-axes).

    Pipeline:
      1. Validate ``color`` field exists (required: dual-axis splits on
         color).
      2. Coerce x to datetime; coerce color values to strings (so series
         names with mixed types still match the dual_axis_series list).
      3. Validate every series in ``dual_axis_series`` is present in
         ``df[color]``. Trailing whitespace or rename-mismatch is the
         #1 dual-axis failure mode -- error message points the user at
         the likely cause.
      4. Split into ``df_left`` / ``df_right`` and verify both sides have
         data.
      5. Compute independent y-domains for each side; honor
         ``invert_right_axis`` for the standard rates pattern (up = bullish
         on both axes).
      6. Stash ``dual_axis_config`` back into ``mapping`` so
         ``render_annotations`` can encode HLines against the correct axis.
      7. Build two layered charts and ``resolve_scale(y='independent')``.
    """
    logger.debug("[_build_multi_line_dual_axis] START")
    logger.debug(
        "[_build_multi_line_dual_axis] df.shape=%s, mapping=%s",
        df.shape, mapping,
    )

    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    color_field = _get_field(mapping, "color")
    dual_axis_series = list(mapping.get("dual_axis_series") or [])
    invert_right = bool(mapping.get("invert_right_axis"))

    logger.debug(
        "[_build_multi_line_dual_axis] dual_axis_series=%s, invert_right=%s",
        dual_axis_series, invert_right,
    )

    if not color_field:
        raise ValidationError(
            "dual_axis_series requires a 'color' field in mapping for series matching."
        )
    if x_field is None or x_field not in df.columns:
        raise ValidationError(
            f"x_field {x_field!r} not found in DataFrame columns: "
            f"{list(df.columns)}"
        )
    if color_field not in df.columns:
        raise ValidationError(
            f"color_field {color_field!r} not found: {list(df.columns)}"
        )
    if y_field is None or y_field not in df.columns:
        raise ValidationError(
            f"y_field {y_field!r} not found in DataFrame columns: "
            f"{list(df.columns)}"
        )

    df = df.copy()
    if (
        not pd.api.types.is_datetime64_any_dtype(df[x_field])
        and mapping.get("x_type") != "ordinal"
    ):
        df[x_field] = pd.to_datetime(df[x_field])

    # Publish the x type so annotation layers inherit it (see
    # ``_annotation_x_axis_type``). Dual-axis x is temporal unless the
    # caller forced ordinal; mirror that so VLine / HLine / Band labels
    # ride the same x scale as the base layers.
    mapping["_x_axis_type"] = (
        "ordinal" if mapping.get("x_type") == "ordinal" else "temporal"
    )

    # Series-name matching is the #1 dual-axis failure mode. Strip
    # whitespace and coerce to strings so 'Rate' matches 'Rate '.
    df[color_field] = df[color_field].astype(str).str.strip()
    dual_axis_series = [str(s).strip() for s in dual_axis_series]

    series_present = set(df[color_field].unique())
    missing_right = [s for s in dual_axis_series if s not in series_present]
    if missing_right:
        raise ValidationError(
            f"dual_axis_series {missing_right} not found in color column "
            f"{color_field!r}. Available series: {sorted(series_present)}. "
            f"Common causes: trailing whitespace on series names, rename "
            f"mismatch between mapping['dual_axis_series'] and the actual "
            f"DataFrame values."
        )

    df_left = df[~df[color_field].isin(dual_axis_series)].copy()
    df_right = df[df[color_field].isin(dual_axis_series)].copy()
    logger.debug(
        "[_build_multi_line_dual_axis] split: left=%d rows, right=%d rows",
        len(df_left), len(df_right),
    )

    if len(df_left) == 0 or len(df_right) == 0:
        raise ValidationError(
            f"Dual-axis split produced an empty side: "
            f"left={len(df_left)} rows, right={len(df_right)} rows. "
            f"Check dual_axis_series values vs. df[{color_field!r}].unique()."
        )

    # Compute independent y-domains for each side.
    left_min, left_max = calculate_y_axis_domain(
        df_left[y_field], handle_outliers=False, prevent_zero_start=True,
    )
    right_min, right_max = calculate_y_axis_domain(
        df_right[y_field], handle_outliers=False, prevent_zero_start=True,
    )
    right_domain = [right_max, right_min] if invert_right else [right_min, right_max]
    logger.debug(
        "[_build_multi_line_dual_axis] left_domain=[%.4f, %.4f], "
        "right_domain=%s%s",
        left_min, left_max, right_domain,
        " (inverted)" if invert_right else "",
    )

    # ---- titles ----------------------------------------------------------
    mark_config = skin_config.get("mark_config", {}).get("line", {})
    line_opacity, opacity_encoding = _prepare_categorical_opacity(
        mapping, color_field, df, mark_config.get("opacity", 1.0),
    )

    y_title_left = mapping.get("y_title") or _format_label(y_field, mapping, "y")
    y_title_right = mapping.get("y_title_right") or _format_label(
        y_field, mapping, "y"
    )
    _validate_y_axis_label(y_title_left, mapping)
    _validate_y_axis_label(y_title_right, mapping)

    # Rename the y column per-side so each layer's y-encoding references a
    # unique field name. Without this Vega-Lite collapses both layers'
    # axis titles into the shared field name (typically "value"), which
    # is the documented chart_context.md dual-axis limitation. Using
    # distinct field names lets each axis carry its own title cleanly
    # AND lets the static-spec round-trip preserve resolve_scale.
    safe_left_field = re.sub(r"[^A-Za-z0-9_]+", "_", y_title_left).strip("_") or "left_value"
    safe_right_field = re.sub(r"[^A-Za-z0-9_]+", "_", y_title_right).strip("_") or "right_value"
    if safe_left_field == safe_right_field:
        safe_right_field = safe_right_field + "_right"

    df_left = df_left.rename(columns={y_field: safe_left_field})
    df_right = df_right.rename(columns={y_field: safe_right_field})

    # Stash config so render_annotations can route HLines correctly.
    # The right HLine encodes against ``safe_right_field`` (the new
    # right-axis y-field name); the left against ``safe_left_field``.
    mapping["dual_axis_config"] = {
        "y_field_left": safe_left_field,
        "y_field_right": safe_right_field,
        "y_domain_left": [left_min, left_max],
        "y_domain_right": right_domain,
    }

    color_sort_left = _resolve_color_sort(df_left, color_field)
    color_sort_right = _resolve_color_sort(df_right, color_field)

    # ---- left axis chart -------------------------------------------------
    left_chart = (
        alt.Chart(df_left)
        .mark_line(
            strokeWidth=mark_config.get("strokeWidth", 2),
            interpolate=mark_config.get("interpolate", "linear"),
            clip=True,
            opacity=line_opacity,
        )
        .encode(
            x=alt.X(x_field, type="temporal", axis=alt.Axis(title=None)),
            y=alt.Y(
                safe_left_field,
                type="quantitative",
                title=y_title_left,
                axis=alt.Axis(
                    title=y_title_left, orient="left", titleFontWeight="normal",
                ),
                scale=alt.Scale(domain=[left_min, left_max]),
            ),
            tooltip=_build_tooltip(
                {**mapping, "y": safe_left_field}, "multi_line", df_left,
            ),
        )
    )
    left_chart = _encode_categorical_color_and_opacity(
        left_chart,
        mapping,
        skin_config,
        color_field,
        df,
        color_sort=color_sort_left,
        opacity_encoding=opacity_encoding,
    )

    # ---- right axis chart ------------------------------------------------
    right_chart = (
        alt.Chart(df_right)
        .mark_line(
            strokeWidth=mark_config.get("strokeWidth", 2),
            interpolate=mark_config.get("interpolate", "linear"),
            clip=True,
            opacity=line_opacity,
        )
        .encode(
            x=alt.X(x_field, type="temporal", axis=alt.Axis(title=None)),
            y=alt.Y(
                safe_right_field,
                type="quantitative",
                title=y_title_right,
                axis=alt.Axis(
                    title=y_title_right, orient="right",
                    titleFontWeight="normal",
                ),
                scale=alt.Scale(domain=right_domain),
            ),
            tooltip=_build_tooltip(
                {**mapping, "y": safe_right_field}, "multi_line", df_right,
            ),
        )
    )
    right_chart = _encode_categorical_color_and_opacity(
        right_chart,
        mapping,
        skin_config,
        color_field,
        df,
        color_sort=color_sort_right,
        opacity_encoding=opacity_encoding,
        legend_kwargs={},
    )

    # Layer + resolve scales independently so each y-axis keeps its own
    # domain. Without resolve_scale(y='independent') Vega-Lite would
    # share the y-scale across both layers and crush the small-range one.
    layered = alt.layer(left_chart, right_chart).resolve_scale(y="independent")
    layered = layered.properties(width=width, height=height)

    # Note: do NOT call _force_data_embedding on the layered chart.
    # Each layer (alt.Chart(df_left), alt.Chart(df_right)) already
    # carries its own per-side data with the renamed y-fields.
    # Setting top-level data here would clobber that with the original
    # combined ``df``, breaking the per-side renaming.
    logger.debug("[_build_multi_line_dual_axis] DONE")
    return layered


def _build_profile_line(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Line chart with an ordinal/categorical x axis.

    Used for yield curve evolution, vol smiles, forward curves, and any
    chart where the x-axis represents a non-temporal dimension and each
    line is a snapshot/group.

    Detects tenor-like x values (``1M``, ``2Y``, ``10Y``...) and applies
    canonical maturity ordering automatically when ``mapping['x_sort']``
    isn't provided. For high-cardinality numeric x (>15 unique), falls
    back to a quantitative encoding to avoid an overcrowded categorical
    axis.

    Uses ``mark_line(point=True, interpolate='monotone')`` so curve
    snapshots render with smooth bezier-like interpolation and visible
    knot points -- the standard rates / vol-smile presentation.
    """
    logger.debug("[_build_profile_line] START")
    logger.debug(
        "[_build_profile_line] df.shape=%s, mapping=%s", df.shape, mapping,
    )

    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    color_field = _get_field(mapping, "color")

    if x_field is None or x_field not in df.columns:
        logger.error(
            "[_build_profile_line] x_field %r missing; columns=%s",
            x_field, list(df.columns),
        )
        raise ValidationError(
            f"x_field '{x_field}' not found. Available: {list(df.columns)}"
        )
    if y_field is None or y_field not in df.columns:
        logger.error(
            "[_build_profile_line] y_field %r missing; columns=%s",
            y_field, list(df.columns),
        )
        raise ValidationError(
            f"y_field '{y_field}' not found. Available: {list(df.columns)}"
        )

    # Determine x-axis sort order: explicit user override -> tenor sort.
    x_sort = mapping.get("x_sort")
    if x_sort is None:
        x_sort = _infer_tenor_sort(df[x_field].unique())
        if x_sort is not None:
            logger.debug(
                "[_build_profile_line] auto-detected tenor sort: %s", x_sort,
            )

    y_min, y_max = calculate_y_axis_domain(df[y_field], prevent_zero_start=True)
    logger.debug(
        "[_build_profile_line] y-axis domain: [%.4f, %.4f]", y_min, y_max,
    )

    x_title = _format_label(x_field, mapping, "x")
    y_title = _format_label(y_field, mapping, "y")
    _validate_y_axis_label(y_title, mapping)

    mark_config = skin_config.get("mark_config", {}).get("line", {})
    line_opacity, opacity_encoding = _prepare_categorical_opacity(
        mapping,
        color_field if (color_field and color_field in df.columns) else None,
        df,
        mark_config.get("opacity", 1.0),
    )

    # High-cardinality numeric x: use quantitative encoding so Vega-Lite
    # auto-thins ticks. Otherwise (categorical / low-cardinality) use
    # ordinal with the resolved sort order. House rule for profile charts:
    # tick labels are NEVER vertical -- horizontal or -45 only -- and the
    # label frequency is thinned when they would collide. The same plan is
    # re-derived (and is authoritative) in ``get_axis_beautification``;
    # setting it here keeps the builder correct on its own.
    # Single authority for the x type. Publish it into ``mapping`` so the
    # annotation layers ``render_annotations`` adds on top (LastValueLabel,
    # VLine, ...) inherit the SAME type via ``_annotation_x_axis_type``.
    # A mismatch (base ``ordinal`` vs annotation ``quantitative`` for a
    # numeric tenor column) is what paints the spurious second x-axis.
    x_axis_type = _profile_x_axis_type(df, x_field)
    mapping["_x_axis_type"] = x_axis_type
    if x_axis_type == "quantitative":
        x_encoding = alt.X(
            x_field,
            type="quantitative",
            axis=alt.Axis(title=x_title, titleFontWeight="normal"),
        )
        logger.debug(
            "[_build_profile_line] high-cardinality numeric x -> quantitative",
        )
    else:
        x_label_angle, x_tick_values = _profile_ordinal_axis_plan(
            _resolve_profile_x_order(df, x_field, mapping), width,
        )
        x_axis_kwargs: Dict[str, Any] = dict(
            title=x_title,
            titleFontWeight="normal",
            labelAngle=x_label_angle,
            labelOverlap="greedy",
            labelSeparation=8,
        )
        if x_tick_values is not None:
            x_axis_kwargs["values"] = x_tick_values
        x_encoding = alt.X(
            x_field,
            type="ordinal",
            sort=x_sort,
            axis=alt.Axis(**x_axis_kwargs),
        )
        logger.debug(
            "[_build_profile_line] ordinal x: angle=%s, thinned=%s of %d",
            x_label_angle,
            "all" if x_tick_values is None else len(x_tick_values),
            df[x_field].nunique(),
        )

    y_encoding = alt.Y(
        y_field,
        type="quantitative",
        axis=alt.Axis(title=y_title, titleFontWeight="normal"),
        scale=alt.Scale(domain=[y_min, y_max]),
    )

    chart = (
        alt.Chart(df)
        .mark_line(
            strokeWidth=mark_config.get("strokeWidth", 2),
            interpolate="monotone",  # Smooth curves for profile charts.
            clip=True,
            point=True,  # Show knot points on each tenor.
            opacity=line_opacity,
        )
        .encode(
            x=x_encoding,
            y=y_encoding,
            tooltip=_build_tooltip(mapping, "multi_line", df),
        )
        .properties(width=width, height=height)
    )

    if color_field and color_field in df.columns:
        legend_cfg = _calculate_legend_config(
            df, color_field, skin_config.get("config", {}).get("legend", {}),
            chart_width=width,
        )
        color_sort = _resolve_color_sort(
            df, color_field, mapping.get("color_sort") or mapping.get("legend_sort"),
        )
        chart = _encode_categorical_color_and_opacity(
            chart,
            mapping,
            skin_config,
            color_field,
            df,
            color_sort=color_sort,
            opacity_encoding=opacity_encoding,
            legend_kwargs={
                "labelLimit": legend_cfg.get("labelLimit", 300),
                "rowPadding": legend_cfg.get("rowPadding", 2),
                "clipHeight": legend_cfg.get("clipHeight"),
            },
        )
        logger.debug(
            "[_build_profile_line] color encoding: %s (n=%d) sort=%s",
            color_field, df[color_field].nunique(), color_sort,
        )

    chart = _force_data_embedding(chart, df)
    logger.debug("[_build_profile_line] DONE")
    return chart


_DEFAULT_ZERO_FILL_POSITIVE = "#C0392B"
_DEFAULT_ZERO_FILL_NEGATIVE = "#1A8A7A"


def _scatter_color_is_gradient(df: pd.DataFrame, color_field: Optional[str]) -> bool:
    if not color_field or color_field not in df.columns:
        return False
    series = df[color_field]
    return pd.api.types.is_datetime64_any_dtype(series) or (
        pd.api.types.is_numeric_dtype(series)
        and not pd.api.types.is_bool_dtype(series)
    )


def _resolve_scatter_order_field(
    mapping: Dict[str, Any],
    df: pd.DataFrame,
    color_field: Optional[str],
) -> Optional[str]:
    order_field = _get_field(mapping, "order")
    if order_field and order_field in df.columns:
        return order_field
    if _scatter_color_is_gradient(df, color_field):
        return color_field
    return None


def _scatter_gradient_legend(
    df: pd.DataFrame,
    color_field: str,
    color_type: str,
) -> alt.Legend:
    """Gradient legend with only the first and last scale endpoints."""
    series = df[color_field].dropna()
    if series.empty:
        return alt.Legend(title=None)
    lo = series.min()
    hi = series.max()
    if color_type == "temporal":
        lo_label = pd.Timestamp(lo).strftime("%b %d, %Y").replace("'", "\\'")
        hi_label = pd.Timestamp(hi).strftime("%b %d, %Y").replace("'", "\\'")
    else:
        lo_label = f"{float(lo):g}".replace("'", "\\'")
        hi_label = f"{float(hi):g}".replace("'", "\\'")
    if lo == hi:
        return alt.Legend(title=None, values=[0], labelExpr=f"'{lo_label}'")
    return alt.Legend(
        title=None,
        values=[0, 1],
        labelExpr=f"datum.value == 0 ? '{lo_label}' : '{hi_label}'",
    )


def _scatter_gradient_norm_series(series: pd.Series) -> pd.Series:
    """Map a temporal/numeric color column to ``[0, 1]`` for gradient scales.

    Vega-Lite temporal color scales only interpolate between the first two
    entries of a multi-stop ``range``; encoding normalized position as
    quantitative avoids that and uses the full HSV rainbow.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        t = pd.to_datetime(series)
        lo, hi = t.min(), t.max()
        if lo == hi:
            return pd.Series(0.0, index=series.index)
        return ((t - lo) / (hi - lo)).astype(float)
    vals = pd.to_numeric(series, errors="coerce")
    lo, hi = float(vals.min()), float(vals.max())
    if lo == hi:
        return pd.Series(0.0, index=series.index)
    return ((vals - lo) / (hi - lo)).astype(float)


_SCATTER_GRADIENT_DEFAULT_START = "#DC143C"
_SCATTER_GRADIENT_DEFAULT_END = "#1E90FF"
_SCATTER_GRADIENT_N_STOPS = 9


def _hsv_rainbow_stops(
    start_hex: str,
    end_hex: str,
    n_stops: int = _SCATTER_GRADIENT_N_STOPS,
) -> List[str]:
    """Multi-stop ramp through the spectrum between two hex endpoints.

    Interpolates hue along the *longer* arc on the colour wheel so e.g.
    red→blue passes orange, yellow, green rather than a direct RGB blend.
    Saturation and value lerp linearly between endpoint HSV values.
    """
    if n_stops < 2:
        raise ValueError("n_stops must be >= 2")

    r0, g0, b0 = (c / 255.0 for c in _hex_to_rgb(start_hex))
    r1, g1, b1 = (c / 255.0 for c in _hex_to_rgb(end_hex))
    h0, s0, v0 = colorsys.rgb_to_hsv(r0, g0, b0)
    h1, s1, v1 = colorsys.rgb_to_hsv(r1, g1, b1)

    fwd_span = (h1 - h0) if h1 >= h0 else (1.0 - h0) + h1
    bwd_span = (h0 - h1) if h0 >= h1 else h0 + (1.0 - h1)
    span_diff = abs(fwd_span - bwd_span)

    if span_diff > 0.35:
        # Same neighbourhood on the wheel — direct (possibly decreasing) hue.
        h_start, h_end = h0, h1
    elif fwd_span >= bwd_span:
        # Similar arcs (e.g. red→blue) — longer rainbow sweep forward.
        h_start = h0
        h_end = h1 + 1.0 if h1 < h0 else h1
    else:
        h_start = h0 + 1.0
        h_end = h1

    stops: List[str] = []
    for i in range(n_stops):
        t = i / (n_stops - 1)
        h = (h_start + t * (h_end - h_start)) % 1.0
        s = s0 + t * (s1 - s0)
        v = v0 + t * (v1 - v0)
        rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
        stops.append(_rgb_to_hex(int(rr * 255), int(gg * 255), int(bb * 255)))
    return stops


def _scatter_gradient_range_stops(mapping: Dict[str, Any]) -> Optional[List[str]]:
    """HSV rainbow stops for scatter gradients, or None for a named scheme."""
    color_range = mapping.get("color_range")
    if mapping.get("color_scheme") is not None and color_range is None:
        return None
    if color_range is not None:
        start_hex, end_hex = color_range[0], color_range[1]
    else:
        start_hex, end_hex = _SCATTER_GRADIENT_DEFAULT_START, _SCATTER_GRADIENT_DEFAULT_END
    return _hsv_rainbow_stops(start_hex, end_hex)


def _scatter_gradient_color_scale(mapping: Dict[str, Any]) -> alt.Scale:
    """Continuous color scale for scatter phase-space gradient paths.

    Default (no ``color_range`` / ``color_scheme``): red→blue HSV rainbow.
    ``color_range=['#start', '#end']``: same HSV sweep between endpoints.
    Explicit ``color_scheme`` alone selects a Vega-Lite named ramp.
    """
    stops = _scatter_gradient_range_stops(mapping)
    if stops is not None:
        return alt.Scale(domain=[0, 1], range=stops)
    return alt.Scale(scheme=mapping["color_scheme"])


def _scatter_gradient_scale_spec(
    mapping: Dict[str, Any],
) -> Dict[str, Any]:
    """Vega-Lite scale dict for facet gradient legend strips."""
    stops = _scatter_gradient_range_stops(mapping)
    if stops is not None:
        return {"domain": [0, 1], "range": stops}
    return {"scheme": mapping["color_scheme"]}


def _scatter_gradient_scale_uses_norm(scale_spec: Optional[Dict[str, Any]]) -> bool:
    """True when the facet strip must color by normalized position, not raw dates."""
    return (
        isinstance(scale_spec, dict)
        and scale_spec.get("domain") == [0, 1]
        and "range" in scale_spec
    )


def _build_baseline_fill_layers(
    df: pd.DataFrame,
    x_field: str,
    y_field: str,
    baseline: float,
    y_scale: alt.Scale,
    x_axis: alt.Axis,
    y_axis: alt.Axis,
    pos_color: str,
    neg_color: str,
    width: int,
    height: int,
) -> Tuple[alt.Chart, alt.Chart]:
    """Area layers shading above / below a horizontal baseline."""
    y_vals = pd.to_numeric(df[y_field], errors="coerce")
    fill_df = df.copy()
    fill_df["_baseline"] = baseline
    fill_df["_fill_top"] = np.where(y_vals >= baseline, y_vals, baseline)
    fill_df["_fill_bot"] = np.where(y_vals <= baseline, y_vals, baseline)

    shared_x = alt.X(x_field, type="temporal", axis=x_axis)

    area_pos = (
        alt.Chart(fill_df)
        .mark_area(color=pos_color, opacity=0.35, clip=True)
        .encode(
            shared_x,
            y=alt.Y("_fill_top:Q", scale=y_scale, axis=y_axis),
            y2=alt.Y2("_baseline:Q"),
        )
        .properties(width=width, height=height)
    )
    area_neg = (
        alt.Chart(fill_df)
        .mark_area(color=neg_color, opacity=0.35, clip=True)
        .encode(
            shared_x,
            y=alt.Y("_baseline:Q", scale=y_scale, axis=y_axis),
            y2=alt.Y2("_fill_bot:Q"),
        )
        .properties(width=width, height=height)
    )
    return area_neg, area_pos


def _expand_scatter_path_segments(
    df: pd.DataFrame,
    x_field: str,
    y_field: str,
    order_field: str,
    color_field: Optional[str],
) -> pd.DataFrame:
    """One row per consecutive (x, y) pair for gradient path segments.

    Vega-Lite splits ``mark_line`` into one series per unique ``color``
    value. Temporal/numeric phase-space paths have a unique color per
    row, which renders as disconnected dots. ``mark_rule`` segments
    sidestep that by giving each edge its own mark.
    """
    sorted_df = df.sort_values(order_field).reset_index(drop=True)
    grad_norm: Optional[pd.Series] = None
    if color_field and color_field in sorted_df.columns:
        grad_norm = _scatter_gradient_norm_series(sorted_df[color_field])
    rows: List[Dict[str, Any]] = []
    for i in range(len(sorted_df) - 1):
        start = sorted_df.iloc[i]
        end = sorted_df.iloc[i + 1]
        row: Dict[str, Any] = {
            x_field: start[x_field],
            y_field: start[y_field],
            "_seg_x2": end[x_field],
            "_seg_y2": end[y_field],
            "_seg_idx": i,
        }
        if grad_norm is not None:
            row["_grad_norm"] = grad_norm.iloc[i + 1]
        rows.append(row)
    return pd.DataFrame(rows)


def _build_scatter(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
    layers: Optional[List[Dict[str, Any]]] = None,
    outlier_handling: str = "auto",
) -> alt.Chart:
    """Scatter plot with optional trendline overlay.

    Issue #2 fix: explicitly configure single y-axis with
    ``titleFontWeight='normal'``.
    Issue #2b fix: clip points at axis boundaries, with a strategy
    chosen by ``outlier_handling``:
      - ``'auto'`` (default): detect heavy tails on either axis. If the
        body of the data (1st-99th percentile) covers less than 30% of
        the full data range, clip the visible axis to that body plus
        10% padding so the cluster stays readable. Outlier points fall
        outside the visible frame and are not rendered (``clip=True``
        on the mark).
      - ``'expand'``: expand the axis domain with 5% padding so all
        points fit on-canvas (legacy behavior; outliers may compress
        the body).
      - ``'truncate'``: drop points outside ``q1 - 1.5*iqr ..
        q3 + 1.5*iqr`` on both x and y before rendering.

    Detects datetime x natively (no epoch-seconds conversion needed).
    Applies the skin's color scale when ``color`` is mapped. Renders a
    dashed regression line when ``mapping['trendline'] is True``.
    """
    # ---- LOGGING: entry (silent_failures.md spec) -----------------------
    logger.info("[_build_scatter] START: df.shape=%s", df.shape)
    logger.debug("[_build_scatter] columns: %s", list(df.columns))
    logger.debug("[_build_scatter] mapping: %s", mapping)
    logger.debug(
        "[_build_scatter] non-null counts: %s", df.notna().sum().to_dict()
    )

    if len(df) == 0:
        logger.error("[_build_scatter] EMPTY DATAFRAME - chart will fail!")
        raise ValidationError(
            "DataFrame is empty. Cannot create scatter chart from empty data."
        )

    # ---- field extraction ------------------------------------------------
    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    color_field = _get_field(mapping, "color")
    size_field = _get_field(mapping, "size")
    logger.debug(
        "[_build_scatter] x=%s, y=%s, color=%s, size=%s",
        x_field, y_field, color_field, size_field,
    )

    if x_field is None or x_field not in df.columns:
        logger.error(
            "[_build_scatter] x_field %r not in columns: %s",
            x_field, list(df.columns),
        )
        raise ValidationError(
            f"x_field '{x_field}' not found in DataFrame columns. "
            f"Available: {list(df.columns)}"
        )
    if y_field is None or y_field not in df.columns:
        logger.error(
            "[_build_scatter] y_field %r not in columns: %s",
            y_field, list(df.columns),
        )
        raise ValidationError(
            f"y_field '{y_field}' not found in DataFrame columns. "
            f"Available: {list(df.columns)}"
        )

    # ---- non-null validation --------------------------------------------
    x_non_null = int(df[x_field].notna().sum())
    y_non_null = int(df[y_field].notna().sum())
    logger.debug(
        "[_build_scatter] non-null: x=%d, y=%d", x_non_null, y_non_null
    )
    if x_non_null == 0:
        raise ValidationError(
            f"x_field '{x_field}' has no valid values. All {len(df)} rows are NaN/None."
        )
    if y_non_null == 0:
        raise ValidationError(
            f"y_field '{y_field}' has no valid values. All {len(df)} rows are NaN/None."
        )

    valid_pairs = df[[x_field, y_field]].dropna()
    if len(valid_pairs) < 2:
        raise ValidationError(
            f"Only {len(valid_pairs)} valid (x, y) pair(s) found for scatter. "
            f"x has {x_non_null} non-null, y has {y_non_null} non-null, but "
            f"only {len(valid_pairs)} overlap. Need >=2 points to plot."
        )

    # ---- temporal x detection -------------------------------------------
    x_is_temporal = pd.api.types.is_datetime64_any_dtype(df[x_field])
    x_type = "temporal" if x_is_temporal else "quantitative"
    if x_is_temporal:
        logger.debug(
            "[_build_scatter] temporal x-axis detected: %s", x_field,
        )

    # ---- outlier handling ('expand' explicit domain or 'truncate' IQR) --
    if outlier_handling == "truncate":
        q1, q3 = df[y_field].quantile([0.25, 0.75])
        iqr = q3 - q1
        if pd.api.types.is_numeric_dtype(df[x_field]):
            q1_x, q3_x = df[x_field].quantile([0.25, 0.75])
            iqr_x = q3_x - q1_x
            df = df[
                (df[x_field] >= q1_x - 1.5 * iqr_x)
                & (df[x_field] <= q3_x + 1.5 * iqr_x)
                & (df[y_field] >= q1 - 1.5 * iqr)
                & (df[y_field] <= q3 + 1.5 * iqr)
            ].copy()
        else:
            df = df[
                (df[y_field] >= q1 - 1.5 * iqr)
                & (df[y_field] <= q3 + 1.5 * iqr)
            ].copy()
        logger.debug(
            "[_build_scatter] outlier_handling='truncate': %d -> %d rows",
            len(valid_pairs), len(df),
        )

    # ---- explicit axis domains ------------------------------------------
    # 'auto' mode: compute the "body" range using 1st-99th percentiles. If
    # the body covers <30% of the full numeric range on either axis, the
    # axis is heavy-tailed and clipping keeps the cluster legible. Mark is
    # already ``clip=True`` so points outside fall off the canvas.
    def _auto_domain(series: pd.Series) -> List[float]:
        s = pd.to_numeric(series, errors="coerce").dropna()
        s_min = float(s.min())
        s_max = float(s.max())
        full_range = s_max - s_min
        if outlier_handling != "auto" or len(s) < 20 or full_range <= 0:
            pad = full_range * 0.05 if full_range > 0 else max(abs(s_max), 1.0) * 0.05
            return [s_min - pad, s_max + pad]
        p01 = float(s.quantile(0.01))
        p99 = float(s.quantile(0.99))
        body_range = p99 - p01
        if body_range > 0 and body_range / full_range < 0.30:
            margin = body_range * 0.10
            logger.info(
                "[_build_scatter] heavy-tail axis: clipping to [%.4g, %.4g] "
                "(full data range was [%.4g, %.4g])",
                p01 - margin, p99 + margin, s_min, s_max,
            )
            return [p01 - margin, p99 + margin]
        pad = full_range * 0.05
        return [s_min - pad, s_max + pad]

    if x_is_temporal:
        x_domain = None  # Vega-Lite handles temporal domains natively.
    elif pd.api.types.is_numeric_dtype(df[x_field]):
        x_domain = _auto_domain(df[x_field])
    else:
        x_domain = None  # Categorical x: no explicit domain.

    if pd.api.types.is_numeric_dtype(df[y_field]):
        y_domain = _auto_domain(df[y_field])
    else:
        y_min = float(df[y_field].min())
        y_max = float(df[y_field].max())
        y_padding = (y_max - y_min) * 0.05 if y_max != y_min else max(abs(y_max), 1.0) * 0.05
        y_domain = [y_min - y_padding, y_max + y_padding]

    connect_path = bool(mapping.get("connect"))
    if connect_path and mapping.get("trendline"):
        raise ValidationError(
            "scatter mapping['connect']=True is incompatible with trendline=True. "
            "Pick one: a time-ordered path (connect) or a linear regression "
            "(trendline)."
        )

    order_field = (
        _resolve_scatter_order_field(mapping, df, color_field)
        if connect_path
        else None
    )
    if connect_path and not order_field:
        raise ValidationError(
            "scatter mapping['connect']=True requires mapping['order'] "
            "(sequence column) or a temporal/numeric mapping['color'] to "
            "define path order."
        )

    if connect_path:
        df = df.sort_values(order_field).reset_index(drop=True)
        valid_pairs = df[[x_field, y_field]].dropna()
        if len(valid_pairs) < 3:
            raise ValidationError(
                f"Connected scatter needs >=3 valid (x, y) pairs in path "
                f"order; found {len(valid_pairs)}."
            )

    # ---- visible-dot density gate ---------------------------------------
    # A scatter only conveys a relationship when the visible plot region
    # carries enough distinct points. Below ``_MIN_SCATTER_VISIBLE_DOTS``
    # the chart reads as anecdote, not pattern -- reject up-front so the
    # caller expands the data window, aggregates, or picks a non-scatter
    # chart type. Counts DISTINCT (x, y) coordinate pairs inside the
    # visible domain (overplotted coincident points read as one dot).
    visible_pairs = valid_pairs
    if x_domain is not None and pd.api.types.is_numeric_dtype(visible_pairs[x_field]):
        visible_pairs = visible_pairs[
            (visible_pairs[x_field] >= x_domain[0])
            & (visible_pairs[x_field] <= x_domain[1])
        ]
    if y_domain is not None and pd.api.types.is_numeric_dtype(visible_pairs[y_field]):
        visible_pairs = visible_pairs[
            (visible_pairs[y_field] >= y_domain[0])
            & (visible_pairs[y_field] <= y_domain[1])
        ]
    visible_dot_count = int(
        len(visible_pairs.drop_duplicates(subset=[x_field, y_field]))
    )
    logger.debug(
        "[_build_scatter] visible distinct dots: %d (total valid pairs: %d)",
        visible_dot_count, len(valid_pairs),
    )
    # A categorical (non-gradient) colour identity makes each dot a named
    # entity (the legend labels them), so a sparse but labelled cross-section
    # (G7, Mag-7) is legitimate and gets the relaxed floor; anonymous clouds
    # keep the full floor.
    is_named_cross_section = (
        bool(color_field)
        and color_field in df.columns
        and not _scatter_color_is_gradient(df, color_field)
    )
    dot_floor = (
        _MIN_SCATTER_LABELED_DOTS if is_named_cross_section
        else _MIN_SCATTER_VISIBLE_DOTS
    )
    if not connect_path and visible_dot_count < dot_floor:
        relax_hint = (
            ""
            if is_named_cross_section
            else (
                f" If this is a small NAMED cross-section (e.g. a handful of "
                f"countries / names), add a categorical mapping['color'] so "
                f"each dot is identified -- the floor then relaxes to "
                f"{_MIN_SCATTER_LABELED_DOTS}."
            )
        )
        raise ValidationError(
            f"Scatter would render only {visible_dot_count} distinct dot(s) "
            f"inside the visible plot area (need >= {dot_floor} to convey a "
            f"relationship). "
            f"Total valid (x, y) pairs: {len(valid_pairs)}; after deduping "
            f"coincident points and clipping to the visible domain only "
            f"{visible_dot_count} remain. A scatter this sparse reads as "
            f"anecdote, not pattern. Either expand the data window, "
            f"aggregate to denser distinct points, or pick a chart type "
            f"that suits sparse data (e.g. `bar`, `multi_line`), or use "
            f"mapping['connect']=True for a time-ordered phase path."
            f"{relax_hint}"
        )

    # ---- titles ---------------------------------------------------------
    x_title = _format_label(x_field, mapping, "x")
    y_title = _format_label(y_field, mapping, "y")
    _validate_y_axis_label(y_title, mapping)

    # ---- mark + chart construction --------------------------------------
    mark_config = skin_config.get("mark_config", {}).get("point", {})
    primary_color = _resolve_single_series_color(mapping, skin_config)

    # Opacity branches by color-encoding regime. The categorical
    # multi-color path scales opacity DOWN with point count via
    # ``_scatter_multi_color_opacity`` so dense scatters with many
    # overlapping points stack into a legible density gradient instead
    # of solid color blobs that destroy both density signal and
    # category identity. Single-color uses the skin default; gradient
    # (temporal / numeric color) sits at a static 0.85 because
    # phase-space plots are typically sparse enough that opaque dots
    # read fine and the gradient itself carries the density story.
    has_color = bool(color_field) and color_field in df.columns
    if has_color:
        _color_series = df[color_field]
        _is_gradient_color = (
            pd.api.types.is_datetime64_any_dtype(_color_series)
            or (
                pd.api.types.is_numeric_dtype(_color_series)
                and not pd.api.types.is_bool_dtype(_color_series)
            )
        )
    else:
        _is_gradient_color = False

    if has_color and not _is_gradient_color:
        base_opacity = _scatter_multi_color_opacity(len(df))
    elif has_color and _is_gradient_color:
        base_opacity = 0.85
    else:
        base_opacity = mark_config.get("opacity", 1.0)

    opacity_field = (
        color_field
        if (has_color and not _is_gradient_color and color_field)
        else None
    )
    mark_opacity, opacity_encoding = _prepare_categorical_opacity(
        mapping, opacity_field, df, base_opacity,
    )

    x_enc = alt.X(
        x_field,
        type=x_type,
        axis=alt.Axis(title=x_title, titleFontWeight="normal"),
        scale=(
            alt.Scale(domain=x_domain)
            if x_domain is not None
            else alt.Undefined
        ),
    )
    y_enc = alt.Y(
        y_field,
        type="quantitative",
        axis=alt.Axis(title=y_title, titleFontWeight="normal"),
        scale=alt.Scale(domain=y_domain),
    )
    tooltips = _build_tooltip(mapping, "scatter", df)

    if connect_path:
        line_config = skin_config.get("mark_config", {}).get("line", {})
        if pd.api.types.is_datetime64_any_dtype(df[order_field]):
            order_enc: alt.Order = alt.Order(order_field, type="temporal", sort="ascending")
        elif pd.api.types.is_numeric_dtype(df[order_field]):
            order_enc = alt.Order(order_field, type="quantitative", sort="ascending")
        else:
            order_enc = alt.Order(order_field, sort="ascending")

        connect_gradient = has_color and _is_gradient_color
        if connect_gradient:
            # mark_line + temporal/numeric color splits every row into its
            # own series (disconnected dots). Render one mark_rule per edge.
            grad_df = df.copy()
            grad_df["_grad_norm"] = _scatter_gradient_norm_series(
                grad_df[color_field],
            )
            seg_df = _expand_scatter_path_segments(
                grad_df, x_field, y_field, order_field, color_field,
            )
            color_series = df[color_field]
            color_is_temporal = pd.api.types.is_datetime64_any_dtype(color_series)
            color_type = "temporal" if color_is_temporal else "quantitative"
            x2_type = "T" if x_is_temporal else "Q"
            grad_scale = _scatter_gradient_color_scale(mapping)
            segments = (
                alt.Chart(seg_df)
                .mark_rule(
                    strokeWidth=line_config.get("strokeWidth", 2.5),
                    clip=True,
                )
                .encode(
                    x_enc,
                    y_enc,
                    x2=alt.X2(f"_seg_x2:{x2_type}"),
                    y2=alt.Y2("_seg_y2:Q"),
                    color=alt.Color(
                        "_grad_norm:Q",
                        scale=grad_scale,
                        legend=_scatter_gradient_legend(
                            df, color_field, color_type,
                        ),
                    ),
                    order=alt.Order("_seg_idx:Q", sort="ascending"),
                )
                .properties(width=width, height=height)
            )
            vertices = (
                alt.Chart(grad_df)
                .mark_point(
                    size=max(20, mark_config.get("size", 60) // 3),
                    filled=mark_config.get("filled", True),
                    opacity=0.45,
                    clip=True,
                )
                .encode(
                    x_enc,
                    y_enc,
                    color=alt.Color(
                        "_grad_norm:Q",
                        scale=grad_scale,
                        legend=None,
                    ),
                    tooltip=tooltips,
                )
                .properties(width=width, height=height)
            )
            chart = alt.layer(segments, vertices)
            logger.debug(
                "[_build_scatter] connected gradient path: %d segments, order=%r",
                len(seg_df), order_field,
            )
        else:
            chart = (
                alt.Chart(df)
                .mark_line(
                    point={"size": max(30, mark_config.get("size", 60) // 2)},
                    strokeWidth=line_config.get("strokeWidth", 2.5),
                    clip=True,
                    color=primary_color if not has_color else alt.Undefined,
                )
                .encode(
                    x_enc,
                    y_enc,
                    order=order_enc,
                    tooltip=tooltips,
                )
                .properties(width=width, height=height)
            )
            logger.debug(
                "[_build_scatter] connected path: order=%r", order_field,
            )
    else:
        chart = (
            alt.Chart(df)
            .mark_point(
                size=mark_config.get("size", 60),
                filled=mark_config.get("filled", True),
                opacity=mark_opacity,
                color=primary_color,
                clip=True,
            )
            .encode(x_enc, y_enc, tooltip=tooltips)
            .properties(width=width, height=height)
        )

    connect_gradient = connect_path and has_color and _is_gradient_color
    if color_field and color_field in df.columns and not connect_gradient:
        # Auto-detect gradient mode: when the color column is temporal
        # or numeric, use a sequential palette + temporal/quantitative
        # encoding type so phase-space plots show point evolution as a
        # color gradient (e.g. dot color = quarter index, the dots
        # paint a rainbow path from earliest to latest in time).
        # Categorical (object / string) columns keep the existing
        # nominal palette so cluster-by-group scatters are unchanged.
        color_series = df[color_field]
        color_is_temporal = pd.api.types.is_datetime64_any_dtype(color_series)
        color_is_numeric = (
            pd.api.types.is_numeric_dtype(color_series)
            and not pd.api.types.is_bool_dtype(color_series)
        )
        if color_is_temporal or color_is_numeric:
            color_type = "temporal" if color_is_temporal else "quantitative"
            grad_df = df.copy()
            grad_df["_grad_norm"] = _scatter_gradient_norm_series(
                grad_df[color_field],
            )
            grad_scale = _scatter_gradient_color_scale(mapping)
            chart = alt.Chart(grad_df).mark_point(
                size=mark_config.get("size", 60),
                filled=mark_config.get("filled", True),
                opacity=mark_opacity,
                clip=True,
            ).encode(
                x_enc,
                y_enc,
                tooltip=tooltips,
            ).properties(width=width, height=height)
            chart = chart.encode(
                color=alt.Color(
                    "_grad_norm:Q",
                    scale=grad_scale,
                    legend=_scatter_gradient_legend(
                        df, color_field, color_type,
                    ),
                )
            )
            if opacity_encoding is not None:
                chart = chart.encode(opacity=opacity_encoding)
            logger.debug(
                "[_build_scatter] gradient color: field=%r type=%s scale=%s",
                color_field,
                color_type,
                mapping.get("color_range")
                or mapping.get("color_scheme")
                or f"rainbow:{_SCATTER_GRADIENT_DEFAULT_START}→{_SCATTER_GRADIENT_DEFAULT_END}",
            )
        else:
            # Always symbolOpacity=1.0 on the legend for categorical
            # scatters: data points use the density curve (often <0.85)
            # but the color key must stay crisp (pre-opacity_map behaviour).
            chart = _encode_categorical_color_and_opacity(
                chart,
                mapping,
                skin_config,
                color_field,
                df,
                color_sort=_resolve_color_sort(
                    df, color_field, mapping.get("color_sort"),
                ),
                opacity_encoding=opacity_encoding,
                legend_kwargs={"symbolOpacity": 1.0},
            )

    if size_field and size_field in df.columns and not connect_path:
        chart = chart.encode(size=alt.Size(size_field, type="quantitative"))

    if mapping.get("trendline") and not connect_path:
        trend = (
            alt.Chart(df)
            .transform_regression(x_field, y_field, method="linear")
            .mark_line(
                color=skin_config.get("trendline_color", "#999999"),
                strokeWidth=1.5,
                strokeDash=[6, 3],
                clip=True,  # Issue #4: clip trendline at axis bounds.
            )
            .encode(
                x=alt.X(
                    x_field,
                    type=x_type,
                    scale=(
                        alt.Scale(domain=x_domain)
                        if x_domain is not None
                        else alt.Undefined
                    ),
                ),
                y=alt.Y(
                    y_field,
                    type="quantitative",
                    scale=alt.Scale(domain=y_domain),
                ),
            )
        )
        chart = alt.layer(chart, trend)
        logger.debug("[_build_scatter] trendline added")

    if layers:
        chart = _apply_extra_layers(chart, df, layers, skin_config)

    chart = _force_data_embedding(chart, df)
    logger.debug("[_build_scatter] DONE")
    return chart


def _build_scatter_multi(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
    layers: Optional[List[Dict[str, Any]]] = None,
) -> alt.Chart:
    """Scatter with multiple groups (per-color clusters) and optional
    per-group trendlines (``mapping['trendlines'] = True``).

    Builds the base scatter via ``_build_scatter`` (no global trendline)
    then layers a ``transform_regression`` per group when ``trendlines``
    is set. Groups with <2 valid points are silently skipped (a 1-point
    regression is meaningless and would crash Altair).
    """
    logger.debug("[_build_scatter_multi] START: df.shape=%s", df.shape)
    logger.debug("[_build_scatter_multi] mapping: %s", mapping)

    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    color_field = _get_field(mapping, "color")
    if not color_field:
        raise ValidationError(
            "scatter_multi requires a 'color' field in mapping for grouping."
        )
    if color_field not in df.columns:
        raise ValidationError(
            f"color_field '{color_field}' not found in DataFrame columns: "
            f"{list(df.columns)}"
        )

    base = _build_scatter(
        df,
        {**mapping, "trendline": False},
        skin_config,
        width,
        height,
        layers=None,
    )

    if not mapping.get("trendlines"):
        logger.debug(
            "[_build_scatter_multi] no per-group trendlines requested"
        )
        if layers:
            base = _apply_extra_layers(base, df, layers, skin_config)
        return base

    x_is_temporal = pd.api.types.is_datetime64_any_dtype(df[x_field])
    x_type = "temporal" if x_is_temporal else "quantitative"

    trend_layers: List[alt.Chart] = []
    skipped_groups: List[str] = []
    for group_name, group_df in df.groupby(color_field):
        valid = group_df[[x_field, y_field]].dropna()
        if len(valid) < 2:
            skipped_groups.append(str(group_name))
            continue
        trend_layers.append(
            alt.Chart(group_df)
            .transform_regression(
                x_field, y_field, method="linear", groupby=[color_field]
            )
            .mark_line(
                strokeWidth=1.5,
                strokeDash=[6, 3],
                clip=True,  # Issue #4: clip per-group trendline at axis bounds.
            )
            .encode(
                x=alt.X(x_field, type=x_type),
                y=alt.Y(y_field, type="quantitative"),
                color=alt.Color(color_field, type="nominal"),
            )
        )

    if skipped_groups:
        logger.warning(
            "[_build_scatter_multi] skipped %d group(s) with <2 valid "
            "points: %s",
            len(skipped_groups), skipped_groups,
        )

    chart = alt.layer(base, *trend_layers) if trend_layers else base
    if layers:
        chart = _apply_extra_layers(chart, df, layers, skin_config)
    logger.debug("[_build_scatter_multi] DONE: %d trend layers", len(trend_layers))
    return chart


def _build_bar(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Vertical bar chart with Altair 4.x compatibility.

    Pipeline:
      1. Logger.debug entry: shape, columns, mapping, non-null counts.
      2. Field/non-null validation (raises ValidationError on failure).
      3. Detect x type:
         - datetime -> ``temporal`` (Issue-13 fix: prevents 1-category-
           per-datetime-string explosion on large datasets).
         - numeric -> ``quantitative``.
         - other -> ``nominal``, with label wrapping (2 words/line).
      4. Compute optimal label-angle for nominal x.
      5. Y-domain calc:
         - All-positive data far from zero: explicit padded domain
           (``zero=False``) so variation stays visible.
         - Otherwise: ``zero=True`` so bars are anchored.
         - Stacked color bars: independent positive/negative stack
           sums for the y-domain.
      6. Single-series uses skin primary color.
      7. Bar value labels (no color, <=15 bars).
      8. Stacked vs grouped:
         - Stacked (default for color): ``stack='zero'`` on y.
         - Grouped (``stack=False``): column-facet by x with one
           bar per color value within each facet. No global x-axis
           title (replaced by per-facet headers).
    """
    # ---- LOGGING: entry --------------------------------------------------
    logger.info("[_build_bar] START: df.shape=%s", df.shape)
    logger.debug("[_build_bar] columns: %s", list(df.columns))
    logger.debug("[_build_bar] mapping: %s", mapping)
    logger.debug(
        "[_build_bar] non-null counts: %s", df.notna().sum().to_dict()
    )

    if len(df) == 0:
        logger.error("[_build_bar] EMPTY DATAFRAME - chart will fail")
        raise ValidationError(
            "DataFrame is empty. Cannot create bar chart from empty data."
        )

    # ---- field extraction + validation -----------------------------------
    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    color_field = _get_field(mapping, "color")
    stack = mapping.get("stack", True)
    logger.debug(
        "[_build_bar] x_field=%s, y_field=%s, color_field=%s, stack=%s",
        x_field, y_field, color_field, stack,
    )

    if x_field is None or x_field not in df.columns:
        logger.error(
            "[_build_bar] x_field %r not in columns: %s",
            x_field, list(df.columns),
        )
        raise ValidationError(
            f"x_field '{x_field}' not found in DataFrame columns. "
            f"Available: {list(df.columns)}"
        )
    if y_field is None or y_field not in df.columns:
        logger.error(
            "[_build_bar] y_field %r not in columns: %s",
            y_field, list(df.columns),
        )
        raise ValidationError(
            f"y_field '{y_field}' not found in DataFrame columns. "
            f"Available: {list(df.columns)}"
        )
    if color_field and color_field not in df.columns:
        logger.warning(
            "[_build_bar] color_field %r not in columns; proceeding without color",
            color_field,
        )
        color_field = None

    x_non_null = int(df[x_field].notna().sum())
    y_non_null = int(df[y_field].notna().sum())
    if x_non_null == 0:
        raise ValidationError(
            f"x_field '{x_field}' has no valid values. All {len(df)} rows are NaN/None."
        )
    if y_non_null == 0:
        raise ValidationError(
            f"y_field '{y_field}' has no valid values. All {len(df)} rows are NaN/None."
        )

    df = df.copy()
    mark_config = skin_config.get("mark_config", {}).get("bar", {})
    tooltips = _build_tooltip(mapping, "bar", df)

    # ---- Issue #6 fix: grouped bar cardinality guard --------------------
    # When using the Altair 4.x column-facet fallback for grouped bars,
    # the chart degrades to mostly-empty subplots if either dimension
    # is too large. We warn (not error) at >60 cells so the user gets
    # an audible nudge while still letting the chart render.
    if color_field and not stack:
        n_x_categories = df[x_field].nunique()
        n_color_categories = df[color_field].nunique()
        if n_x_categories * n_color_categories > 60:
            logger.warning(
                "[_build_bar] grouped bar configuration may be unusable: "
                "%d x-categories x %d color groups = %d facet cells. "
                "Consider stack=True (stacked) or top_k_categories() "
                "to reduce cardinality.",
                n_x_categories, n_color_categories,
                n_x_categories * n_color_categories,
            )

    # ---- x type detection (Issue-13 fix) --------------------------------
    if pd.api.types.is_datetime64_any_dtype(df[x_field]):
        x_type = "temporal"
        logger.debug(
            "[_build_bar] x %r detected as datetime -> temporal encoding",
            x_field,
        )
    elif pd.api.types.is_numeric_dtype(df[x_field]):
        x_type = "quantitative"
    else:
        x_type = "nominal"
        # Validate category label lengths BEFORE the auto-flip branch:
        # the cap applies regardless of orientation, so we raise here
        # rather than letting auto-flip route long labels into the
        # bar_horizontal handler (which has its own truncation /
        # collision modes for long category labels).
        raw_labels = [str(v) for v in df[x_field].unique()]
        _validate_bar_category_labels(raw_labels, x_field, mapping)
        # Auto-switch to horizontal-bar when category labels are too long
        # to render vertically without ellipsis truncation. Heuristic:
        # average label > 12 chars or any label > 20 chars on a normal-
        # density bar chart (n_bars * 100 > width). Caller can disable via
        # mapping['orientation'] = 'vertical'.
        avg_len = sum(len(l) for l in raw_labels) / max(len(raw_labels), 1)
        max_len = max((len(l) for l in raw_labels), default=0)
        n_bars = len(raw_labels)
        force_orientation = mapping.get("orientation")
        too_long = (
            max_len > 20 or (avg_len > 12 and n_bars * 100 > width)
        )
        if too_long and force_orientation != "vertical":
            logger.info(
                "[_build_bar] long category labels (max=%d, avg=%.1f, "
                "n_bars=%d, width=%d) -> auto-switching to bar_horizontal "
                "for legibility. Pass orientation='vertical' to override.",
                max_len, avg_len, n_bars, width,
            )
            # The horizontal builder expects the category on y and the
            # value on x, so swap them. Also swap x_title and y_title.
            flipped = dict(mapping)
            flipped["x"] = mapping.get("y")
            flipped["y"] = mapping.get("x")
            flipped["x_title"] = mapping.get("y_title")
            flipped["y_title"] = mapping.get("x_title")
            # x_sort -> y_sort in the new orientation (and vice-versa).
            flipped["y_sort"] = mapping.get("x_sort")
            flipped["x_sort"] = mapping.get("y_sort")
            return _build_bar_horizontal(df, flipped, skin_config, width, height)
        # Wrap nominal x labels for horizontal readability.
        df[x_field] = df[x_field].apply(
            lambda v: wrap_label(str(v), words_per_line=2)
        )

    # ---- y-domain calc --------------------------------------------------
    if pd.api.types.is_numeric_dtype(df[y_field]):
        y_min = float(df[y_field].min())
        y_max = float(df[y_field].max())
        y_range = y_max - y_min
        # All-positive data far from zero: explicit padded domain so
        # variation stays visible. Otherwise anchor at zero.
        if y_min > 0 and y_range > 0 and y_min > y_range * 0.5:
            y_scale = alt.Scale(
                domain=[y_min - y_range * 0.1, y_max + y_range * 0.1],
                zero=False,
            )
        else:
            y_scale = alt.Scale(zero=True)
    else:
        y_scale = alt.Scale()

    # ---- titles ---------------------------------------------------------
    x_title = _format_label(x_field, mapping, "x")
    y_title = _format_label(y_field, mapping, "y")
    _validate_y_axis_label(y_title, mapping)

    # ---- optimal label angle for nominal x ------------------------------
    if x_type == "nominal":
        bar_labels = [str(v) for v in df[x_field].unique()]
        # For nominal x Vega-Lite renders every tick (no auto-thinning),
        # so use the actual label count as the tick count to avoid
        # under-estimating collisions.
        bar_label_angle = calculate_optimal_label_angle(
            bar_labels, width, estimated_tick_count=len(bar_labels),
        )
        if mapping.get("_facet_panel"):
            bar_label_angle = -45
    else:
        bar_label_angle = 0

    # ---- high-cardinality / rotated-label x-axis thinning ---------------
    # Two paths trigger greedy thinning:
    #   1. Beyond ~45 nominal bars: even at 0deg the default "render
    #      every tick" produces an unreadable black ribbon.
    #   2. ``-90 deg`` label rotation with ``>= 20`` labels: at
    #      90 deg the relevant collision constraint is label HEIGHT, which
    #      is ``char_count * font_size`` and easily exceeds the per-bar
    #      horizontal space (e.g. 35 6-char tickers in 700px = 20px each
    #      vs 108px label height).
    # Vega-Lite's ``labelOverlap='greedy'`` hides colliding labels and
    # ``labelSeparation`` pads the minimum gap so survivors don't merge.
    needs_thinning_high_n = (
        x_type == "nominal" and df[x_field].nunique() >= 45
    )
    needs_thinning_rotated = (
        x_type == "nominal"
        and bar_label_angle == -90
        and df[x_field].nunique() >= 20
    )
    if needs_thinning_high_n or needs_thinning_rotated:
        bar_x_label_overlap: Any = "greedy"
        bar_x_label_separation: Any = 6
    else:
        bar_x_label_overlap = alt.Undefined
        bar_x_label_separation = alt.Undefined

    primary_color = _resolve_single_series_color(mapping, skin_config)
    bar_opacity, bar_opacity_enc = _prepare_categorical_opacity(
        mapping, color_field, df, mark_config.get("opacity", 1.0),
    )

    # ---- bar width cap for low-cardinality data --------------------------
    # Vega-Lite divides the plot width across all bars, so a single bar
    # spans the entire frame (looks like a chart edge), and 2-3 bars get
    # 200+ px each (visually unbalanced). Cap the per-bar size so very
    # short categorical axes leave breathing room.
    n_unique_x = df[x_field].nunique() if x_type == "nominal" else None
    bar_size_override: Any = alt.Undefined
    if n_unique_x is not None:
        if n_unique_x == 1:
            bar_size_override = min(80, max(40, width // 6))
        elif n_unique_x == 2:
            bar_size_override = min(100, max(50, width // 5))
        elif n_unique_x == 3:
            bar_size_override = min(120, max(60, width // 4))

    # ---- STACKED or single-series path ----------------------------------
    if not color_field or stack:
        chart = (
            alt.Chart(df)
            .mark_bar(
                cornerRadiusTopLeft=mark_config.get("cornerRadius", 0),
                cornerRadiusTopRight=mark_config.get("cornerRadius", 0),
                opacity=bar_opacity,
                clip=True,
                color=primary_color if not color_field else alt.Undefined,
                size=bar_size_override,
            )
            .encode(
                x=alt.X(
                    x_field,
                    type=x_type,
                    sort=mapping.get("x_sort"),
                    title=x_title,
                    axis=alt.Axis(
                        titleFontWeight="normal",
                        labelAngle=bar_label_angle,
                        labelOverlap=bar_x_label_overlap,
                        labelSeparation=bar_x_label_separation,
                    ),
                ),
                y=alt.Y(
                    y_field,
                    type="quantitative",
                    title=y_title,
                    scale=y_scale,
                    axis=alt.Axis(titleFontWeight="normal"),
                    stack=("zero" if (color_field and stack) else None),
                ),
                tooltip=tooltips,
            )
            .properties(width=width, height=height)
        )

        if color_field:
            # ``order=alt.Order(color_field, sort=...)`` MUST use ``:N``
            # shorthand: ``_force_data_embedding`` (a few lines below)
            # swaps ``chart.data`` from a pandas DataFrame to a literal
            # ``alt.Data(values=...)``. At ``to_dict()`` time (called in
            # ``make_chart`` post-build), Vega-Lite walks every channel;
            # any field reference without an inline type prompts dtype
            # introspection on ``chart.data``, which now isn't a
            # DataFrame, and Altair raises:
            #   ValueError: <field> encoding field is specified without
            #   a type; the type cannot be automatically inferred ...
            # ``alt.Color`` here doesn't trip the failure because it
            # already has ``type="nominal"`` explicit; ``alt.Order`` did
            # not, so the bare ``color_field`` was the failure point.
            # The same precedent exists for ``strokeDash`` at
            # ``_build_multi_line_single_axis`` (the only other secondary
            # channel encoded after data embedding) -- see the comment
            # block there. ``alt.Color`` keeps the kwarg form for
            # readability; only ``alt.Order`` had the bug.
            chart = _encode_categorical_color_and_opacity(
                chart,
                mapping,
                skin_config,
                color_field,
                df,
                color_sort=_resolve_color_sort(
                    df, color_field, mapping.get("color_sort"),
                ),
                opacity_encoding=bar_opacity_enc,
            )
            chart = chart.encode(
                order=alt.Order(f"{color_field}:N", sort="ascending"),
            )

        # Value labels on bars (single-series, <=15 bars only).
        # The label layer leaves x/y axis unspecified so Vega-Lite's
        # shared-axis resolution inherits the base bar's axis (title,
        # ticks, format) instead of overriding it with ``title=null``.
        #
        # Mixed-sign anchor split (F4 fix from Phase 2 stress probe):
        # positive bars get labels ABOVE the bar (baseline='bottom',
        # dy=-4 on the y=value anchor); negative bars get labels BELOW
        # the bar (baseline='top', dy=+4 on the y=value anchor). The
        # prior single-mark "label sits at apex inside dark fill for
        # negatives" path produced labels at inconsistent positions
        # along the bar fill (Q5 -1.10 sat near top of its bar; Q1
        # -3.20 sat near bottom; Q3 -2.80 sat mid-bar) and the white-
        # text-inside-dark-fill collided with HLine labels passing
        # through the bar zone. Splitting positive vs negative into
        # two text layers mirrors the natural "outside-the-bar" anchor
        # used everywhere else in the engine and reads consistently.
        # Both layers use dark text (#222222) on the white background.
        #
        # Class 1 absorption (collision sweep 2026-05-10): suppress the
        # value label on bars whose x-position is anchored by a Callout /
        # PointLabel / Arrow annotation. The annotation's text takes
        # priority; the redundant numeric label would just collide.
        suppress_x_set = mapping.get("_suppress_bar_value_at_x") or set()
        if (
            not mapping.get("_facet_panel")
            and not color_field
            and df[x_field].nunique() <= 15
        ):
            df_for_labels = df
            if suppress_x_set:
                # Coerce the comparison values to a set of strings so we
                # match across datetime / numeric / string variants.
                str_suppress = {str(x) for x in suppress_x_set}
                df_for_labels = df[~df[x_field].astype(str).isin(str_suppress)]
                n_dropped = len(df) - len(df_for_labels)
                if n_dropped > 0:
                    logger.info(
                        "[_build_bar] Suppressed %d bar value label(s) at "
                        "annotation-anchored x-position(s).", n_dropped,
                    )

            df_pos = df_for_labels[df_for_labels[y_field] >= 0]
            df_neg = df_for_labels[df_for_labels[y_field] < 0]
            value_fmt = _smart_number_format(df[y_field])

            if len(df_pos) > 0:
                pos_text = (
                    alt.Chart(df_pos)
                    .mark_text(
                        align="center",
                        baseline="bottom",
                        dy=-4,
                        fontSize=11,
                        fontWeight="bold",
                        color="#222222",
                    )
                    .encode(
                        x=alt.X(
                            x_field, type=x_type, sort=mapping.get("x_sort"),
                        ),
                        y=alt.Y(y_field, type="quantitative"),
                        text=alt.Text(
                            y_field, type="quantitative",
                            format=value_fmt,
                        ),
                    )
                    .properties(width=width, height=height)
                )
                chart = chart + pos_text

            if len(df_neg) > 0:
                neg_text = (
                    alt.Chart(df_neg)
                    .mark_text(
                        align="center",
                        baseline="top",
                        dy=4,
                        fontSize=11,
                        fontWeight="bold",
                        color="#222222",
                    )
                    .encode(
                        x=alt.X(
                            x_field, type=x_type, sort=mapping.get("x_sort"),
                        ),
                        y=alt.Y(y_field, type="quantitative"),
                        text=alt.Text(
                            y_field, type="quantitative",
                            format=value_fmt,
                        ),
                    )
                    .properties(width=width, height=height)
                )
                chart = chart + neg_text
        elif not color_field:
            logger.info(
                "[_build_bar] suppressing text labels: %d bars > threshold of 15",
                df[x_field].nunique(),
            )

        # For stacked bars: suppress value labels on mixed-sign data
        # (baseline='bottom' assumes upward growth; mixed-sign creates
        # overlapping/mispositioned labels).
        if color_field and stack:
            has_negative = (df[y_field] < 0).any()
            if not has_negative and pd.api.types.is_numeric_dtype(df[y_field]):
                # Stacked text labels at the top of each stacked total.
                stack_totals = df.groupby(x_field)[y_field].sum().reset_index()

                # Class 1 absorption (annotation-anchored x suppression).
                if suppress_x_set:
                    str_suppress = {str(x) for x in suppress_x_set}
                    stack_totals = stack_totals[
                        ~stack_totals[x_field].astype(str).isin(str_suppress)
                    ]

                # Class 4 absorption (collision sweep 2026-05-10):
                # suppress the stacked-total value label when the total
                # falls inside a labelled Band's y-range. Both labels
                # would render in the same pixel band; the Band's label
                # (the named regime) wins.
                y_range_suppress = mapping.get("_suppress_bar_total_in_y_range")
                if y_range_suppress is not None and len(stack_totals) > 0:
                    y_lo, y_hi = y_range_suppress
                    n_pre = len(stack_totals)
                    stack_totals = stack_totals[
                        (stack_totals[y_field] < y_lo)
                        | (stack_totals[y_field] > y_hi)
                    ]
                    n_dropped = n_pre - len(stack_totals)
                    if n_dropped > 0:
                        logger.info(
                            "[_build_bar] Suppressed %d stacked-bar TOTAL "
                            "value label(s) inside Band y-range "
                            "[%.3f, %.3f].",
                            n_dropped, y_lo, y_hi,
                        )

                stack_text = (
                    alt.Chart(stack_totals)
                    .mark_text(
                        align="center", baseline="bottom",
                        dy=-4, color="#222222",
                        fontSize=11, fontWeight="bold",
                    )
                    .encode(
                        x=alt.X(
                            x_field, type=x_type, sort=mapping.get("x_sort"),
                        ),
                        y=alt.Y(y_field, type="quantitative"),
                        text=alt.Text(
                            y_field, type="quantitative",
                            format=_smart_number_format(stack_totals[y_field]),
                        ),
                    )
                )
                chart = chart + stack_text
            elif has_negative:
                logger.info(
                    "[_build_bar] suppressing stacked text labels (negative values present)"
                )

    else:
        # ---- GROUPED path (color + stack=False): column faceting ---------
        # Each x-category becomes a column facet; color field becomes the
        # x-axis within each facet (with hidden labels), producing
        # side-by-side bars per category.
        #
        # Cell-budget invariant: total outer width is
        # n_x_cats * facet_width + (n_x_cats - 1) * inter_facet_spacing.
        # Letting EITHER term float free of the input ``width`` budget
        # breaks composites -- with a 280px compact_4_grid cell and 17+
        # x-categories the bar would render 3-5x wider than its sibling
        # panels and demolish the 2x2 grid (regression catalysed
        # 2026-05-02 projects/altair/dev/feedback/2026-05-02_4pack_blowout.md).
        # Subtract the spacing overhead from the budget BEFORE dividing
        # by n_x_cats so both terms fit; the inter-facet gap keeps groups
        # visually distinguishable without consuming too much budget.
        # Readability gate rejects the unreadable-blur extreme so the
        # LLM sees a clean ValidationError instead of a tiny-bar cell.
        n_x_cats = df[x_field].nunique()
        n_color_cats = df[color_field].nunique()
        spacing_overhead = max(0, n_x_cats - 1) * _GROUPED_BAR_FACET_SPACING_PX
        usable_width = max(n_x_cats, width - spacing_overhead)
        facet_width = max(1, usable_width // max(n_x_cats, 1))
        per_bar_px = facet_width / max(n_color_cats, 1)
        if per_bar_px < _MIN_GROUPED_BAR_PER_BAR_PX:
            raise ValidationError(
                f"GROUPED BAR CELL-BUDGET ERROR: {n_x_cats} x-categories x "
                f"{n_color_cats} color groups produces ~{per_bar_px:.1f}px "
                f"per bar in a {width}px-wide cell, below the "
                f"{_MIN_GROUPED_BAR_PER_BAR_PX}px readability threshold. "
                f"Use stack=True (stacked bars), reduce x-categories, or "
                f"render this chart standalone (larger width budget) "
                f"instead of inside a composite."
            )
        logger.debug(
            "[_build_bar] grouped via column faceting: n_x_cats=%d, "
            "facet_width=%d, per_bar_px=%.1f, spacing_overhead=%d",
            n_x_cats, facet_width, per_bar_px, spacing_overhead,
        )

        # Stringify any datetime columns for safe spec embedding.
        df_grouped = df.copy()
        for col in df_grouped.columns:
            if pd.api.types.is_datetime64_any_dtype(df_grouped[col]):
                df_grouped[col] = df_grouped[col].dt.strftime("%Y-%m-%dT%H:%M:%S")

        # Per-facet header label angle: use the per-facet width (not the
        # global chart width) so we don't wastefully rotate short labels
        # that would fit horizontally inside one facet column.
        facet_label_angle = calculate_optimal_label_angle(
            [str(v) for v in df_grouped[x_field].unique()],
            facet_width,
            estimated_tick_count=1,
        )

        # Facet-header label thinning: column-faceted bars have one label
        # per facet (Vega-Lite renders them as a row beneath the chart).
        # The standard ``labelOverlap='greedy'`` axis trick doesn't apply
        # to facet headers -- they're per-facet, not per-axis. Without
        # thinning, n=17 in a 280px cell crams 17 labels into ~250px =
        # ~14px/label, so even rotated they collide visibly. Show only
        # every Nth label so visible labels get >= ~28px breathing room.
        # This MUST happen before alt.Header is constructed because
        # Header is immutable after `.encode()` builds the chart.
        total_strip_px = n_x_cats * facet_width + spacing_overhead
        facet_label_expr = _facet_label_thinning_expr(
            list(df_grouped[x_field].unique()),
            total_strip_px=total_strip_px,
        )
        # When thinning fires, re-pick the rotation angle against the
        # SURVIVOR pitch (not the per-facet pitch). Thinning leaves each
        # surviving label ~28px of room -- that is enough for diagonal
        # text but typically not enough for the GS skin's 16pt
        # horizontal axis labels (a 3-char label at 16pt needs ~30px).
        # The prior heuristic clobbered the angle to 0 whenever thinning
        # fired, producing colliding horizontal labels in 4-grid
        # composites with 10+ categories ("XLAXLBXLC...").
        if facet_label_expr is not None:
            survivor_count = max(
                2, total_strip_px // _FACET_LABEL_MIN_PITCH_PX,
            )
            facet_label_angle = calculate_optimal_label_angle(
                [str(v) for v in df_grouped[x_field].unique()],
                chart_width=total_strip_px,
                estimated_tick_count=int(survivor_count),
            )

        # HARDCODED: grouped bar charts NEVER show a global x-axis title.
        # Per-facet header labels replace the axis title.
        header_kwargs: Dict[str, Any] = dict(
            orient="bottom",
            labelAngle=facet_label_angle,
            labelPadding=14,
            labelFontSize=skin_config.get("axis_config", {}).get(
                "labelFontSize", 15,
            ),
        )
        
        # When labels are rotated, align them so they don't overlap the chart
        if facet_label_angle != 0:
            header_kwargs["labelAlign"] = "right"
            header_kwargs["labelBaseline"] = "middle"
        else:
            header_kwargs["labelBaseline"] = "top"
        if facet_label_expr is not None:
            header_kwargs["labelExpr"] = facet_label_expr

        chart = (
            alt.Chart(df_grouped)
            .mark_bar(
                cornerRadiusTopLeft=mark_config.get("cornerRadius", 0),
                cornerRadiusTopRight=mark_config.get("cornerRadius", 0),
                opacity=bar_opacity,
                clip=True,
            )
            .encode(
                column=alt.Column(
                    x_field,
                    type="nominal",
                    title=None,
                    spacing=_GROUPED_BAR_FACET_SPACING_PX,
                    header=alt.Header(**header_kwargs),
                    sort=list(df_grouped[x_field].unique()),
                ),
                x=alt.X(
                    color_field,
                    type="nominal",
                    sort=_resolve_color_sort(df, color_field, mapping.get("color_sort")),
                    scale=alt.Scale(
                        paddingInner=_GROUPED_BAR_INNER_X_PADDING_INNER,
                        paddingOuter=_GROUPED_BAR_INNER_X_PADDING_OUTER,
                    ),
                    axis=alt.Axis(
                        ticks=False, labels=False, title="", domain=False,
                    ),
                ),
                y=alt.Y(
                    y_field,
                    type="quantitative",
                    title=y_title,
                    scale=y_scale,
                    axis=alt.Axis(titleFontWeight="normal", grid=False),
                ),
                tooltip=tooltips,
            )
            .properties(width=facet_width, height=height)
        )
        chart = _encode_categorical_color_and_opacity(
            chart,
            mapping,
            skin_config,
            color_field,
            df,
            color_sort=_resolve_color_sort(
                df, color_field, mapping.get("color_sort"),
            ),
            opacity_encoding=bar_opacity_enc,
        )

    chart = _force_data_embedding(chart, df)
    logger.debug("[_build_bar] DONE")
    return chart


def _build_bar_horizontal(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Horizontal bar chart (categorical y, numeric x).

    Stacked by default when ``color`` is mapped; set
    ``mapping['stack'] = False`` for grouped (Issue #5 fix: row faceting,
    the horizontal equivalent of column faceting in vertical bars).

    Uses ``cornerRadiusTopRight`` / ``cornerRadiusBottomRight`` (right
    side rounded only) so the bars look correct in the horizontal
    orientation.
    """
    logger.debug("[_build_bar_horizontal] START")
    logger.debug(
        "[_build_bar_horizontal] df.shape=%s, mapping=%s", df.shape, mapping,
    )

    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    color_field = _get_field(mapping, "color")
    stack = mapping.get("stack", True)
    logger.debug(
        "[_build_bar_horizontal] x_field=%s, y_field=%s, color_field=%s, stack=%s",
        x_field, y_field, color_field, stack,
    )

    if len(df) == 0:
        logger.error("[_build_bar_horizontal] EMPTY DATAFRAME - chart will fail")
        raise ValidationError(
            "DataFrame is empty. Cannot create horizontal bar chart from empty data."
        )

    if x_field is None or x_field not in df.columns:
        logger.error(
            "[_build_bar_horizontal] x_field %r not in columns: %s",
            x_field, list(df.columns),
        )
        raise ValidationError(
            f"x_field '{x_field}' not found in DataFrame columns: "
            f"{list(df.columns)}"
        )
    if y_field is None or y_field not in df.columns:
        logger.error(
            "[_build_bar_horizontal] y_field %r not in columns: %s",
            y_field, list(df.columns),
        )
        raise ValidationError(
            f"y_field '{y_field}' not found in DataFrame columns: "
            f"{list(df.columns)}"
        )

    x_non_null = int(df[x_field].notna().sum())
    y_non_null = int(df[y_field].notna().sum())
    if x_non_null == 0:
        raise ValidationError(f"x_field '{x_field}' has no valid values.")
    if y_non_null == 0:
        raise ValidationError(f"y_field '{y_field}' has no valid values.")

    # Validate category label lengths. The same cap as _build_bar applies
    # because the failure modes are symmetric: 22+ ch labels truncate at
    # width=700 (B04 / G05 in the audit), 14+ ch labels truncate at
    # composite width=350 (D04 / E05), and grouped horizontal (color +
    # stack=False) collapses long labels into illegible y-axis overlap
    # at any width (F04 / F05 / H01). When _build_bar auto-flipped here,
    # its validation already passed -- this call is a no-op then. When
    # the caller invokes bar_horizontal explicitly, this is the only
    # validation site, so it must live here.
    _validate_bar_category_labels(
        [str(v) for v in df[y_field].unique()],
        category_field=y_field,
        mapping=mapping,
    )

    mark_config = skin_config.get("mark_config", {}).get("bar", {})
    tooltips = _build_tooltip(mapping, "bar_horizontal", df)

    x_title = _format_label(x_field, mapping, "x")
    # Only show a y-axis title when the user explicitly requested one.
    # On horizontal bar the y-axis IS the categorical labels, which
    # already convey the meaning -- a default humanized title like
    # "Category" is redundant and Vega-Lite renders it rotated 90 deg
    # in the negative-x gutter, where it visually overlaps long labels
    # (e.g. "Astoundingly Long Identifier...") and looks like a stray
    # vertical word floating in the chart.
    if mapping.get("y_title"):
        y_title = mapping["y_title"]
    else:
        y_title = None
    _validate_y_axis_label(x_title, mapping)  # x is the value axis here

    primary_color = _resolve_single_series_color(mapping, skin_config)
    bar_opacity, bar_opacity_enc = _prepare_categorical_opacity(
        mapping, color_field, df, mark_config.get("opacity", 1.0),
    )

    # ---- bar height cap for low-cardinality data -----------------------
    # Vega-Lite divides plot height across categories; with one or two
    # rows the bars span the full frame and the chart looks unbalanced.
    n_unique_y = df[y_field].nunique()
    bar_size_override: Any = alt.Undefined
    if n_unique_y == 1:
        bar_size_override = min(60, max(30, height // 6))
    elif n_unique_y == 2:
        bar_size_override = min(80, max(40, height // 5))
    elif n_unique_y == 3:
        bar_size_override = min(100, max(50, height // 4))

    # Compute a generous labelLimit that scales with the longest category
    # label so long names like "Equity Derivatives Strategy" stay legible
    # instead of being silently truncated. The skin's labelFontSize=18
    # means we need ~12 px per character to avoid mid-word truncation.
    label_font_size = (
        skin_config.get("config", {})
        .get("axis", {})
        .get("labelFontSize", 14)
    )
    px_per_char = max(7, int(label_font_size * 0.7))
    longest_y_label = max((len(str(v)) for v in df[y_field].unique()), default=10)
    y_label_limit = max(
        180,
        min(int(width * 0.45), longest_y_label * px_per_char + 16),
    )
    h_y_label_font_size = _bar_horizontal_y_label_font_size(
        height, n_unique_y, label_font_size,
    )

    # ---- high-cardinality y-axis thinning (horizontal bars) -------------
    # Mirror the vertical-bar thinning: beyond ~45 rows the y-axis label
    # column produces an unreadable wall of stacked text.
    if df[y_field].nunique() >= 45:
        h_y_label_overlap: Any = "greedy"
        h_y_label_separation: Any = 4
    elif (
        h_y_label_font_size <= _BAR_HORIZONTAL_Y_LABEL_FONT_MIN + 1
        and n_unique_y >= 15
    ):
        # Still packed after font shrink -- thin every other label.
        h_y_label_overlap = "greedy"
        h_y_label_separation = 2
    else:
        h_y_label_overlap = alt.Undefined
        h_y_label_separation = alt.Undefined

    if not color_field or stack:
        chart = (
            alt.Chart(df)
            .mark_bar(
                cornerRadiusTopRight=mark_config.get("cornerRadius", 0),
                cornerRadiusBottomRight=mark_config.get("cornerRadius", 0),
                opacity=bar_opacity,
                color=primary_color if not color_field else alt.Undefined,
                size=bar_size_override,
            )
            .encode(
                y=alt.Y(
                    y_field,
                    type="nominal",
                    sort=mapping.get("y_sort"),
                    title=y_title,
                    axis=alt.Axis(
                        titleFontWeight="normal", labelLimit=y_label_limit,
                        labelAngle=0,
                        labelFontSize=h_y_label_font_size,
                        labelOverlap=h_y_label_overlap,
                        labelSeparation=h_y_label_separation,
                    ),
                ),
                x=alt.X(
                    x_field,
                    type="quantitative",
                    title=x_title,
                    axis=alt.Axis(titleFontWeight="normal"),
                    stack=("zero" if (color_field and stack) else None),
                ),
                tooltip=tooltips,
            )
            .properties(width=width, height=height)
        )
        if color_field:
            chart = _encode_categorical_color_and_opacity(
                chart,
                mapping,
                skin_config,
                color_field,
                df,
                color_sort=_resolve_color_sort(
                    df, color_field, mapping.get("color_sort"),
                ),
                opacity_encoding=bar_opacity_enc,
            )

        # Horizontal bar value labels (F5 fix from Phase 2 stress probe).
        # The single-series path (no color) gets a value label per bar,
        # mirroring the vertical-bar behaviour. Anchor split:
        #   - Positive x values -> label OUTSIDE the bar to the RIGHT
        #     (align='left', dx=+4 on x=value anchor). Dark text on
        #     white plot background.
        #   - Negative x values -> label INSIDE the bar near the OPEN
        #     end (x=0 side, align='right', dx=-4 on x=value anchor=0).
        #     White text on dark bar fill. Outside-left would land in
        #     the y-axis category-label gutter and visibly collide with
        #     the long y-axis tick text -- inside-at-x=0 sidesteps that
        #     while keeping the value adjacent to the bar boundary the
        #     user reads first.
        if not color_field and df[y_field].nunique() <= 25:
            value_fmt = _smart_number_format(df[x_field])
            value_label_fs = max(8, min(11, h_y_label_font_size + 1))
            df_pos = df[df[x_field] >= 0]
            df_neg = df[df[x_field] < 0].copy()

            if len(df_pos) > 0:
                pos_text = (
                    alt.Chart(df_pos)
                    .mark_text(
                        align="left",
                        baseline="middle",
                        dx=4,
                        fontSize=value_label_fs,
                        fontWeight="bold",
                        color="#222222",
                    )
                    .encode(
                        y=alt.Y(
                            y_field, type="nominal",
                            sort=mapping.get("y_sort"),
                        ),
                        x=alt.X(x_field, type="quantitative"),
                        text=alt.Text(
                            x_field, type="quantitative",
                            format=value_fmt,
                        ),
                    )
                    .properties(width=width, height=height)
                )
                chart = chart + pos_text

            if len(df_neg) > 0:
                # Anchor at x=0 (the open end) and let the original
                # x_field column drive the displayed text. White text
                # on dark fill sidesteps the y-axis gutter collision.
                df_neg["_anchor_x"] = 0.0
                neg_text = (
                    alt.Chart(df_neg)
                    .mark_text(
                        align="right",
                        baseline="middle",
                        dx=-4,
                        fontSize=value_label_fs,
                        fontWeight="bold",
                        color="white",
                    )
                    .encode(
                        y=alt.Y(
                            y_field, type="nominal",
                            sort=mapping.get("y_sort"),
                        ),
                        x=alt.X("_anchor_x", type="quantitative"),
                        text=alt.Text(
                            x_field, type="quantitative",
                            format=value_fmt,
                        ),
                    )
                    .properties(width=width, height=height)
                )
                chart = chart + neg_text
    else:
        # GROUPED via row faceting (horizontal equivalent of column-facet
        # for vertical bars). Each y-category becomes a row facet; the
        # color field drives the y-axis WITHIN each facet (with hidden
        # labels), producing side-by-side bars per category.
        #
        # Cell-budget invariant: total grouped-horizontal-bar HEIGHT is
        # n_y_cats * facet_height + (n_y_cats - 1) * inter_facet_spacing.
        # Same shape of defect as the vertical grouped-bar path.
        # Subtract the spacing overhead from the budget BEFORE dividing
        # by n_y_cats so both terms fit; readability gate rejects the
        # unreadable-blur extreme.
        n_y_cats = df[y_field].nunique()
        n_color_cats = df[color_field].nunique()
        spacing_overhead = max(0, n_y_cats - 1) * _GROUPED_BAR_FACET_SPACING_PX
        usable_height = max(n_y_cats, height - spacing_overhead)
        facet_height = max(1, usable_height // max(n_y_cats, 1))
        per_bar_px = facet_height / max(n_color_cats, 1)
        if per_bar_px < _MIN_GROUPED_BAR_PER_BAR_PX:
            raise ValidationError(
                f"GROUPED HORIZONTAL BAR CELL-BUDGET ERROR: {n_y_cats} "
                f"y-categories x {n_color_cats} color groups produces "
                f"~{per_bar_px:.1f}px per bar in a {height}px-tall cell, "
                f"below the {_MIN_GROUPED_BAR_PER_BAR_PX}px readability "
                f"threshold. Use stack=True (stacked bars), reduce "
                f"y-categories, or render this chart standalone (larger "
                f"height budget) instead of inside a composite."
            )
        logger.debug(
            "[_build_bar_horizontal] grouped via row faceting: n_y_cats=%d, "
            "facet_height=%d, per_bar_px=%.1f, spacing_overhead=%d",
            n_y_cats, facet_height, per_bar_px, spacing_overhead,
        )

        # Row-facet header label thinning (vertical analog of the
        # column-facet thinning in _build_bar). Drops every-Nth label
        # when n_y_cats packs labels too tightly along the height axis.
        row_label_expr = _facet_label_thinning_expr(
            list(df[y_field].unique()),
            total_strip_px=n_y_cats * facet_height + spacing_overhead,
        )
        # Horizontal-bar category labels are NEVER rotated -- always
        # horizontal text adjacent to their row group. Vega-Lite's
        # default row-facet header orientation rotates labels 90 deg
        # (running vertically up the gutter), which is unreadable and
        # was the underlying cause of the F04 / F05 / H01 / H03 / H04
        # collision observed in the pre-cap long-label audit. ``labelAngle=0``
        # forces horizontal text; right-align + middle-baseline anchors
        # the label flush against the bars to its right.
        row_header_kwargs: Dict[str, Any] = dict(
            orient="left",
            labelAngle=0,
            labelAlign="right",
            labelBaseline="middle",
            labelPadding=10,
            labelFontSize=h_y_label_font_size,
        )
        if row_label_expr is not None:
            row_header_kwargs["labelExpr"] = row_label_expr

        chart = (
            alt.Chart(df)
            .mark_bar(
                cornerRadiusTopRight=mark_config.get("cornerRadius", 0),
                cornerRadiusBottomRight=mark_config.get("cornerRadius", 0),
                opacity=bar_opacity,
            )
            .encode(
                row=alt.Row(
                    y_field,
                    type="nominal",
                    title=None,
                    spacing=_GROUPED_BAR_FACET_SPACING_PX,
                    header=alt.Header(**row_header_kwargs),
                    sort=list(df[y_field].unique()),
                ),
                y=alt.Y(
                    color_field,
                    type="nominal",
                    sort=_resolve_color_sort(df, color_field, mapping.get("color_sort")),
                    axis=alt.Axis(
                        ticks=False, labels=False, title="", domain=False,
                    ),
                ),
                x=alt.X(
                    x_field,
                    type="quantitative",
                    title=x_title,
                    axis=alt.Axis(titleFontWeight="normal", grid=False),
                ),
                tooltip=tooltips,
            )
            .properties(width=width, height=facet_height)
        )
        chart = _encode_categorical_color_and_opacity(
            chart,
            mapping,
            skin_config,
            color_field,
            df,
            color_sort=_resolve_color_sort(
                df, color_field, mapping.get("color_sort"),
            ),
            opacity_encoding=bar_opacity_enc,
        )

    chart = _force_data_embedding(chart, df)
    logger.debug("[_build_bar_horizontal] DONE")
    return chart


def _build_area(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Stacked area chart (long-format with color = series).

    Defaults to ``stack='zero'`` when ``color`` is mapped (additive
    composition). Without ``color`` renders a single-series filled
    area at full opacity.
    """
    logger.debug("[_build_area] START: df.shape=%s, mapping=%s", df.shape, mapping)

    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    color_field = _get_field(mapping, "color")

    if x_field is None or x_field not in df.columns:
        raise ValidationError(
            f"x_field '{x_field}' not found in DataFrame columns: {list(df.columns)}"
        )
    if y_field is None or y_field not in df.columns:
        raise ValidationError(
            f"y_field '{y_field}' not found in DataFrame columns: {list(df.columns)}"
        )
    if df[x_field].notna().sum() == 0:
        raise ValidationError(f"x_field '{x_field}' has no valid values.")
    if df[y_field].notna().sum() == 0:
        raise ValidationError(f"y_field '{y_field}' has no valid values.")

    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df[x_field]):
        try:
            df[x_field] = pd.to_datetime(df[x_field])
        except Exception:  # noqa: BLE001 - leave as-is if non-temporal
            pass

    x_title = None  # Time axis is self-evident on area charts.
    y_title = _format_label(y_field, mapping, "y")
    _validate_y_axis_label(y_title, mapping)

    mark_config = skin_config.get("mark_config", {}).get("area", {})
    area_opacity, area_opacity_enc = _prepare_categorical_opacity(
        mapping,
        color_field if (color_field and color_field in df.columns) else None,
        df,
        mark_config.get("opacity", 0.7),
    )

    # For stacked areas, set an explicit scale.domain that covers the
    # per-x stacked sum so the y-axis frame includes the full stack
    # (otherwise axis beautification injects a min/max from the raw
    # series values and only the topmost area is visible).
    if color_field and color_field in df.columns:
        try:
            stack_sum = df.groupby(x_field)[y_field].sum()
            stacked_min = float(min(stack_sum.min(), 0.0))
            stacked_max = float(stack_sum.max())
            pad = (stacked_max - stacked_min) * 0.05
            stacked_scale = alt.Scale(domain=[stacked_min, stacked_max + pad])
        except Exception:  # noqa: BLE001
            stacked_scale = alt.Undefined
    else:
        stacked_scale = alt.Undefined

    chart = (
        alt.Chart(df)
        .mark_area(
            opacity=area_opacity,
            interpolate=mark_config.get("interpolate", "linear"),
            clip=True,
        )
        .encode(
            x=alt.X(
                x_field,
                type=(
                    "temporal"
                    if pd.api.types.is_datetime64_any_dtype(df[x_field])
                    else "quantitative"
                ),
                axis=alt.Axis(title=x_title),
            ),
            y=alt.Y(
                y_field,
                type="quantitative",
                axis=alt.Axis(title=y_title, titleFontWeight="normal"),
                stack="zero" if color_field else None,
                scale=stacked_scale,
            ),
            tooltip=_build_tooltip(mapping, "area", df),
        )
        .properties(width=width, height=height)
    )

    if color_field and color_field in df.columns:
        chart = _encode_categorical_color_and_opacity(
            chart,
            mapping,
            skin_config,
            color_field,
            df,
            color_sort=_resolve_color_sort(
                df, color_field, mapping.get("color_sort"),
            ),
            opacity_encoding=area_opacity_enc,
        )

    chart = _force_data_embedding(chart, df)
    logger.debug("[_build_area] DONE")
    return chart


def _heatmap_axis_labels(
    df: pd.DataFrame,
    field: Optional[str],
    sort_order: Optional[List[Any]],
) -> List[str]:
    """Distinct axis label strings for a heatmap nominal field."""
    if not field or (df is not None and field not in getattr(df, "columns", [])):
        return []
    if sort_order:
        return [str(v) for v in sort_order]
    return [str(v) for v in df[field].dropna().unique().tolist()]


def _heatmap_row_label_plan(
    df: pd.DataFrame,
    y_field: Optional[str],
    sort_order: Optional[List[Any]],
    *,
    chart_width: int,
    chart_height: int,
    label_font_size: int,
    composite_cell: bool,
) -> Tuple[List[str], int, int]:
    """Return (labels, max_chars, label_limit_px) for validated row labels."""
    labels = _heatmap_axis_labels(df, y_field, sort_order)
    if not labels:
        return [], 0, 16
    px_per_char = _axis_label_px_per_char(label_font_size)
    n_rows = max(len(labels), 1)
    per_row_px = chart_height / n_rows
    gutter_frac = (
        _HEATMAP_ROW_GUTTER_FRAC_COMPOSITE
        if composite_cell
        else _HEATMAP_ROW_GUTTER_FRAC_STANDALONE
    )
    gutter_px = chart_width * gutter_frac
    max_chars = max(1, int((gutter_px - 8) / px_per_char))
    max_chars = min(max_chars, _HEATMAP_ROW_LABEL_MAX_CHARS)
    longest_px = max(_axis_label_pixel_budget(s, label_font_size) for s in labels)
    label_limit_px = max(16, int(longest_px))
    return labels, max_chars, label_limit_px


def _heatmap_row_labels_fit_horizontal(
    df: pd.DataFrame,
    field: Optional[str],
    sort_order: Optional[List[Any]],
    *,
    chart_width: int,
    chart_height: int,
    label_font_size: int,
    composite_cell: bool,
) -> Tuple[bool, int, List[str], Optional[str]]:
    """Check whether every row label fits horizontally at angle=0."""
    labels, max_chars, _ = _heatmap_row_label_plan(
        df,
        field,
        sort_order,
        chart_width=chart_width,
        chart_height=chart_height,
        label_font_size=label_font_size,
        composite_cell=composite_cell,
    )
    if not labels:
        return True, 0, [], None
    px_per_char = _axis_label_px_per_char(label_font_size)
    n_rows = max(len(labels), 1)
    per_row_px = chart_height / n_rows
    gutter_frac = (
        _HEATMAP_ROW_GUTTER_FRAC_COMPOSITE
        if composite_cell
        else _HEATMAP_ROW_GUTTER_FRAC_STANDALONE
    )
    gutter_px = chart_width * gutter_frac

    vertical_reason: Optional[str] = None
    if label_font_size + _HEATMAP_ROW_LABEL_VERTICAL_PAD_PX > per_row_px:
        vertical_reason = (
            f"{n_rows} rows in a {chart_height}px-tall cell leave "
            f"~{per_row_px:.0f}px/row, below the "
            f"{label_font_size + _HEATMAP_ROW_LABEL_VERTICAL_PAD_PX}px needed "
            f"for {label_font_size}pt horizontal labels"
        )

    offending = [
        s for s in labels
        if len(s) > max_chars
        or _axis_label_pixel_budget(s, label_font_size) > gutter_px
    ]
    if vertical_reason:
        return False, max_chars, offending or labels, vertical_reason
    if offending:
        return False, max_chars, offending, None
    return True, max_chars, [], None


def _validate_heatmap_row_labels(
    df: pd.DataFrame,
    y_field: Optional[str],
    sort_order: Optional[List[Any]],
    *,
    chart_width: int,
    chart_height: int,
    label_font_size: int,
    mapping: Optional[Dict[str, Any]] = None,
    composite_cell: bool = False,
) -> int:
    """Fail fast when row labels would truncate; return exact ``labelLimit`` px."""
    fits, max_chars, offending, vertical_reason = _heatmap_row_labels_fit_horizontal(
        df,
        y_field,
        sort_order,
        chart_width=chart_width,
        chart_height=chart_height,
        label_font_size=label_font_size,
        composite_cell=composite_cell,
    )
    labels, _, label_limit_px = _heatmap_row_label_plan(
        df,
        y_field,
        sort_order,
        chart_width=chart_width,
        chart_height=chart_height,
        label_font_size=label_font_size,
        composite_cell=composite_cell,
    )
    if fits:
        return label_limit_px

    if not offending:
        longest = max(labels, key=len) if labels else ""
        offending = [longest]
    sample = offending[0]
    n_rows = max(len(labels), 1)
    ctx = "make_*pack_*()" if composite_cell else "make_chart()"
    abbrev_hint = _suggest_bar_label_abbreviations(sample)
    if vertical_reason:
        detail = vertical_reason
    else:
        detail = (
            f"{y_field!r} value {sample!r} ({len(sample)} chars) exceeds the "
            f"~{max_chars}-char left-gutter budget for a "
            f"{chart_width}x{chart_height}px canvas"
        )
    raise HeatmapRowLabelTooLongError(
        f"Heatmap row labels must stay horizontal and cannot be truncated, "
        f"but {detail}. Shorten row labels in the DataFrame before "
        f"{ctx} (max {_HEATMAP_ROW_LABEL_MAX_CHARS} chars; aim <=~{max_chars} "
        f"at {n_rows} rows / {chart_width}px width). "
        f"Try abbreviating {sample!r} -> {abbrev_hint}. "
        f"Offending: {offending[:4]}"
        f"{'...' if len(offending) > 4 else ''}.",
        offending_labels=offending,
        y_field=y_field,
        mapping=mapping,
        max_chars=max_chars,
        chart_height=chart_height,
    )


def _heatmap_x_axis_plan(
    ordered_vals: List[Any],
    chart_width: int,
) -> Tuple[int, Optional[List[Any]]]:
    """Pick heatmap column (x) ``(label_angle, tick_values)``.

    Vertical (90 deg) labels are forbidden on heatmaps. Same horizontal /
    -45 ladder as profile charts, but ``_HEATMAP_MIN_PITCH_45_PX`` is 2x
    the profile pitch so thinned x ticks run at roughly half the frequency
    (better for dense intraday column grids). Every cell still renders.
    """
    vals = [str(v) for v in ordered_vals]
    n = len(vals)
    if n == 0:
        return 0, None
    max_len = max(len(v) for v in vals)
    needed_h = max_len * _PROFILE_LABEL_CHAR_PX + _PROFILE_LABEL_PAD_PX

    horiz_capacity = max(1, int(chart_width // needed_h))
    diag_capacity = max(1, int(chart_width // _HEATMAP_MIN_PITCH_45_PX))

    if horiz_capacity >= n:
        return 0, None
    if horiz_capacity >= _PROFILE_MIN_HORIZONTAL_TICKS:
        return 0, _evenly_spaced_subset(ordered_vals, horiz_capacity)
    if diag_capacity >= n:
        return -45, None
    return -45, _evenly_spaced_subset(ordered_vals, diag_capacity)


def _heatmap_row_label_angle() -> int:
    """Heatmap row (y-axis) labels are always horizontal."""
    return 0


def _build_heatmap(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
    *,
    composite_cell: bool = False,
) -> alt.Chart:
    """2-D heatmap.

    ``mapping['value']`` (or ``mapping['z']``) names the column whose
    magnitude is encoded by cell color. Uses ``mark_rect`` with explicit
    ``stroke=None`` and grid-suppressed axes (Issue #5 fix) to prevent
    white-line artifacts through cells.

    Catches the common LLM mistake of using ``'color'`` instead of
    ``'value'`` -- that would mis-route the intensity field to the color
    encoding without a quantitative scheme. Errors with a helpful
    rewrite suggestion.

    Optional ``mapping['x_sort']`` controls x-axis label order
    (Bug-5 fix; otherwise Vega-Lite's default alphabetical sort applies).
    Cell labels are auto-added when ``skin_config['heatmap_labels']`` is
    truthy, with text color flipping to white on dark cells (value > 0.5
    of normalized scale).
    """
    logger.debug("[_build_heatmap] START: df.shape=%s, mapping=%s", df.shape, mapping)

    if len(df) == 0:
        raise ValidationError(
            "DataFrame is empty. Cannot create heatmap from empty data."
        )

    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    value_field = _get_field(mapping, "value") or _get_field(mapping, "z")

    # Common LLM mistake: 'color' instead of 'value'.
    if value_field is None:
        color_field = _get_field(mapping, "color")
        if color_field:
            raise ValidationError(
                "Heatmap charts use mapping['value'] (not 'color') for the "
                f"intensity field. Change mapping to: "
                f"{{'x': {x_field!r}, 'y': {y_field!r}, 'value': {color_field!r}}}"
            )
        raise ValidationError(
            "Heatmap requires a 'value' (or 'z') key in mapping for the cell "
            "intensity field. Example: "
            "mapping={'x': 'var1', 'y': 'var2', 'value': 'correlation'}"
        )

    if x_field is None or x_field not in df.columns:
        raise ValidationError(
            f"x_field '{x_field}' not found in DataFrame columns: {list(df.columns)}"
        )
    if y_field is None or y_field not in df.columns:
        raise ValidationError(
            f"y_field '{y_field}' not found in DataFrame columns: {list(df.columns)}"
        )
    if value_field not in df.columns:
        raise ValidationError(
            f"value_field '{value_field}' not found in DataFrame columns: "
            f"{list(df.columns)}"
        )

    if df[value_field].notna().sum() == 0:
        raise ValidationError(
            f"value_field '{value_field}' has no valid values. "
            f"All {len(df)} rows are NaN/None."
        )

    grid_size = df[x_field].nunique() * df[y_field].nunique()
    if grid_size > 500:
        logger.warning(
            "[_build_heatmap] large grid size (%d cells) may affect readability",
            grid_size,
        )

    x_title = _format_label(x_field, mapping, "x")
    y_title = _format_label(y_field, mapping, "y")
    _validate_y_axis_label(y_title, mapping)
    x_sort_order = mapping.get("x_sort")
    y_sort_order = mapping.get("y_sort")
    row_label_font_size = _heatmap_axis_label_font_size(skin_config)

    row_label_limit_px = _validate_heatmap_row_labels(
        df,
        y_field,
        y_sort_order,
        chart_width=width,
        chart_height=height,
        label_font_size=row_label_font_size,
        mapping=mapping,
        composite_cell=composite_cell,
    )

    # ---- column (x) axis plan -------------------------------------------
    # Heatmap column labels NEVER render vertical (90 deg). When the x
    # grid is dense (intraday 15-min bars over several sessions), show an
    # evenly-spaced tick subset so labels stay legible at -45.
    x_ordered = _resolve_profile_x_order(df, x_field, mapping)
    x_label_angle, x_tick_values = _heatmap_x_axis_plan(x_ordered, width)
    y_label_angle = _heatmap_row_label_angle()

    # Grid-suppressed axes prevent white-line artifacts on cells.
    # ``labelPadding`` adds breathing room so row labels (e.g. "Tech",
    # "Financials") don't kiss the first column of cells; default
    # Vega-Lite labelPadding is 2px which reads as zero gap on a tight
    # heatmap grid.
    x_axis_kwargs: Dict[str, Any] = dict(
        grid=False, domain=False, ticks=False, title=x_title,
        labelPadding=8, labelAngle=x_label_angle,
    )
    if x_tick_values is not None:
        x_axis_kwargs["values"] = x_tick_values
    x_axis = alt.Axis(**x_axis_kwargs)
    y_axis = alt.Axis(
        grid=False, domain=False, ticks=False, title=y_title,
        labelPadding=8, labelAngle=y_label_angle,
        labelFontSize=row_label_font_size,
        labelLimit=row_label_limit_px,
    )

    # ---- value-column dtype dispatch ------------------------------------
    # Two recipes are supported, dispatched by the value column's dtype:
    #
    #   NUMERIC  -> quantitative color scale (sequential or diverging-
    #               at-zero), labels formatted via _smart_number_format.
    #               Canonical use: correlation matrix, P&L matrix, raw
    #               z-scores.
    #
    #   CATEGORICAL / STRING  -> ordinal color scale indexed by the
    #               column's natural sort order (or `mapping['value_sort']`
    #               override), label is the bin label itself. Canonical
    #               use: pre-binned probability buckets ('0-10%' .. '90-100%')
    #               from `pd.cut(..., labels=str_list)`. The chart_context.md
    #               §6.3 recipe was previously broken because the engine
    #               assumed quantitative; both shapes now work end-to-end.
    value_is_numeric = pd.api.types.is_numeric_dtype(df[value_field])

    if value_is_numeric:
        # ---- color scheme selection (numeric path) ----------------------
        # If the value column crosses zero (correlation matrix, P&L
        # matrix, z-scores), a sequential scheme like "blues" can't
        # distinguish -0.6 from +0.4 because they share a hue family.
        # Detect mixed-sign data and switch to a diverging scheme
        # centered at zero. The skin can override via
        # ``heatmap_scheme`` / ``heatmap_diverging_scheme``, and the
        # caller can force a specific scheme via
        # ``mapping['color_scheme']``.
        v_min_full = float(df[value_field].min())
        v_max_full = float(df[value_field].max())
        is_mixed_sign = v_min_full < 0 and v_max_full > 0
        forced_scheme = mapping.get("color_scheme")
        if forced_scheme:
            scheme = forced_scheme
            scale_kwargs: Dict[str, Any] = {"scheme": scheme}
        elif is_mixed_sign:
            scheme = skin_config.get("heatmap_diverging_scheme", "redblue")
            sym = max(abs(v_min_full), abs(v_max_full))
            scale_kwargs = {
                "scheme": scheme,
                "domain": [-sym, sym],
                "domainMid": 0.0,
            }
        else:
            scheme = skin_config.get("heatmap_scheme", "blues")
            scale_kwargs = {"scheme": scheme}

        color_enc = alt.Color(
            value_field,
            type="quantitative",
            scale=alt.Scale(**scale_kwargs),
            legend=alt.Legend(title=None),
        )

        chart = (
            alt.Chart(df)
            .mark_rect(stroke=None, strokeWidth=0)
            .encode(
                x=alt.X(x_field, type="nominal", axis=x_axis, sort=x_sort_order),
                y=alt.Y(y_field, type="nominal", axis=y_axis, sort=y_sort_order),
                color=color_enc,
                tooltip=_build_tooltip(mapping, "heatmap", df),
            )
            .properties(width=width, height=height)
        )

        # Per-cell pixel-budget check: even when the skin enables
        # heatmap labels, suppress them when the formatted label would
        # not fit horizontally inside its cell. At 10pt, a 5-char value
        # like "-0.43" needs ~30px of horizontal room; in a 35px-wide
        # cell that leaves zero gap, and the labels paint into
        # neighbouring cells producing "-0.43-0.61-0.16" ribbons of
        # text. The check samples the formatted-value widths because
        # raw value magnitudes mislead -- e.g. ".567" reads narrower
        # than "-0.43" despite the same magnitude.
        cell_label_fontsize = 10
        n_x_cells = max(int(df[x_field].nunique()), 1)
        per_cell_w = width / n_x_cells
        value_fmt = _smart_number_format(df[value_field])
        # Convert the vega-lite format spec (".2f" etc) into the
        # equivalent python format spec for an on-screen width probe.
        py_fmt_spec = value_fmt.lstrip(".") if value_fmt else ""
        def _probe_len(v: Any) -> int:
            try:
                if py_fmt_spec:
                    return len(format(float(v), py_fmt_spec))
                return len(str(v))
            except (TypeError, ValueError):
                return len(str(v))
        non_null = df[value_field].dropna()
        if len(non_null) > 0:
            label_chars = max(_probe_len(v) for v in non_null.head(50))
        else:
            label_chars = 5
        label_pixel_budget = label_chars * cell_label_fontsize * 0.6 + 4
        cells_too_narrow = per_cell_w < label_pixel_budget

        if skin_config.get("heatmap_labels", True) and not cells_too_narrow:
            v_min = v_min_full
            v_max = v_max_full
            if is_mixed_sign and not forced_scheme:
                sym_threshold = max(abs(v_min), abs(v_max)) * 0.6
                color_condition = alt.condition(
                    f"abs(datum['{value_field}']) > {sym_threshold}",
                    alt.value("white"),
                    alt.value("#222222"),
                )
            else:
                v_threshold = (v_min + v_max) / 2.0 if v_max != v_min else v_max
                color_condition = alt.condition(
                    alt.datum[value_field] > v_threshold,
                    alt.value("white"),
                    alt.value("#222222"),
                )
            text = (
                alt.Chart(df)
                .mark_text(baseline="middle", fontSize=cell_label_fontsize)
                .encode(
                    x=alt.X(x_field, type="nominal", sort=x_sort_order),
                    y=alt.Y(y_field, type="nominal", sort=y_sort_order),
                    text=alt.Text(
                        value_field, type="quantitative",
                        format=value_fmt,
                    ),
                    color=color_condition,
                )
            )
            chart = alt.layer(chart, text).properties(width=width, height=height)
        elif cells_too_narrow:
            logger.info(
                "[_build_heatmap] suppressing cell labels: per-cell width "
                "%.1fpx < label budget %.1fpx (%d cells x %dpx-wide canvas, "
                "max label %d chars at %dpt). Use a wider canvas or fewer "
                "x-categories to keep labels.",
                per_cell_w, label_pixel_budget, n_x_cells, width,
                label_chars, cell_label_fontsize,
            )
    else:
        # ---- categorical / string path ----------------------------------
        # Treat the value column as ordered bins. Sort order respects an
        # explicit ``mapping['value_sort']`` override; otherwise:
        #   - pandas Categorical with ordered categories -> use them
        #   - everything else -> natural sort by string repr
        # The color scale becomes a SEQUENTIAL palette indexed by the
        # bin order so the visual reads as low->high left-to-right (e.g.
        # the canonical pd.cut '0-10%' .. '90-100%' recipe).
        explicit_sort = mapping.get("value_sort")
        if explicit_sort is not None:
            value_order: List[Any] = [str(v) for v in explicit_sort]
        elif (
            isinstance(df[value_field].dtype, pd.CategoricalDtype)
            and df[value_field].cat.ordered
        ):
            value_order = [str(v) for v in df[value_field].cat.categories]
        else:
            unique_vals = df[value_field].dropna().unique().tolist()
            value_order = sorted(
                {str(v) for v in unique_vals},
                key=_natural_sort_key,
            )

        if len(value_order) > MAX_COLOR_CARDINALITY:
            raise ValidationError(
                f"Heatmap value column '{value_field}' has "
                f"{len(value_order)} distinct categorical bins, exceeding "
                f"MAX_COLOR_CARDINALITY={MAX_COLOR_CARDINALITY}. The "
                f"sequential color ramp loses readability beyond ~12 bins. "
                f"Bin to <=12 categories first, e.g. "
                f"`pd.cut(df['{value_field}'], bins={MAX_COLOR_CARDINALITY}, "
                f"labels=[...])`."
            )

        # Coerce to string so Vega-Lite's nominal scale lines up with
        # the explicit sort domain. Categorical dtype with non-string
        # categories would otherwise mismatch the sort list.
        df = df.copy()
        df[value_field] = df[value_field].astype(str)

        # Build a sequential range of N hex colors out of a vega-lite
        # named scheme. ``mapping['color_scheme']`` overrides; otherwise
        # 'blues' for monotonic bin labels.
        scheme = mapping.get("color_scheme") or skin_config.get(
            "heatmap_scheme", "blues"
        )
        n_bins = max(1, len(value_order))
        bin_colors = _sample_named_scheme(scheme, n_bins)

        color_enc = alt.Color(
            value_field,
            type="nominal",
            scale=alt.Scale(domain=value_order, range=bin_colors),
            sort=value_order,
            legend=alt.Legend(title=None),
        )

        chart = (
            alt.Chart(df)
            .mark_rect(stroke=None, strokeWidth=0)
            .encode(
                x=alt.X(x_field, type="nominal", axis=x_axis, sort=x_sort_order),
                y=alt.Y(y_field, type="nominal", axis=y_axis, sort=y_sort_order),
                color=color_enc,
                tooltip=_build_tooltip(mapping, "heatmap", df),
            )
            .properties(width=width, height=height)
        )

        if skin_config.get("heatmap_labels", True):
            # Dark cells (top half of the sequential ramp) get white
            # text; light cells get near-black. Build an OR-chain of
            # equality checks against the dark-bin labels -- vega-
            # expression supports ``||`` and ``==`` natively without
            # the MemberExpression-style ``[...].indexOf(...)`` that
            # vega-expression's parser rejects as illegal callee type.
            dark_bins = [
                v for i, v in enumerate(value_order)
                if (i + 1) / n_bins > 0.5
            ]
            if dark_bins:
                # Escape any single-quotes inside bin labels so the
                # generated expression stays valid.
                escaped_bins = [v.replace("'", "\\'") for v in dark_bins]
                dark_predicate = " || ".join(
                    f"datum['{value_field}'] == '{v}'" for v in escaped_bins
                )
                color_condition = alt.condition(
                    dark_predicate,
                    alt.value("white"),
                    alt.value("#222222"),
                )
            else:
                color_condition = alt.value("#222222")
            text = (
                alt.Chart(df)
                .mark_text(baseline="middle", fontSize=10)
                .encode(
                    x=alt.X(x_field, type="nominal", sort=x_sort_order),
                    y=alt.Y(y_field, type="nominal", sort=y_sort_order),
                    text=alt.Text(value_field, type="nominal"),
                    color=color_condition,
                )
            )
            chart = alt.layer(chart, text).properties(width=width, height=height)

    chart = _force_data_embedding(chart, df)
    logger.debug("[_build_heatmap] DONE")
    return chart


def _build_histogram(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Distribution histogram for a single numeric column.

    Honors ``mapping['bins']`` (or legacy ``maxbins``) for bin count.
    Adds tooltip showing the bin range and count. When ``color`` is
    mapped, splits the histogram into stacked groups.
    """
    logger.info("[_build_histogram] START: df.shape=%s", df.shape)
    logger.debug("[_build_histogram] mapping: %s", mapping)

    if len(df) == 0:
        raise ValidationError(
            "DataFrame is empty. Cannot create histogram from empty data."
        )

    x_field = _get_field(mapping, "x")
    color_field = _get_field(mapping, "color")
    bins = int(mapping.get("bins", mapping.get("maxbins", 30)))

    if x_field is None or x_field not in df.columns:
        logger.error(
            "[_build_histogram] x_field %r not in columns: %s",
            x_field, list(df.columns),
        )
        raise ValidationError(
            f"x_field '{x_field}' not found in DataFrame columns: "
            f"{list(df.columns)}"
        )
    if df[x_field].notna().sum() == 0:
        raise ValidationError(f"x_field '{x_field}' has no valid values.")

    mark_config = skin_config.get("mark_config", {}).get("bar", {})
    primary_color = _resolve_single_series_color(mapping, skin_config)

    x_title = _format_label(x_field, mapping, "x") or "Value"

    tooltips: List[alt.Tooltip] = [
        alt.Tooltip(x_field, type="quantitative", bin=True, title="Bin Range"),
        alt.Tooltip("count()", title="Count", format=","),
    ]
    if color_field and color_field in df.columns:
        tooltips.append(alt.Tooltip(color_field, type="nominal", title="Group"))

    # ---- heavy-tail outlier handling -----------------------------------
    # If the body of the distribution sits in a small fraction of the
    # data's full numeric range (i.e. one or two extreme values dominate
    # the x-domain), bin between the 1st and 99th percentile and add a
    # subtitle note that the tail is truncated. The user can override
    # via mapping['bin_extent'] = [lo, hi].
    series = pd.to_numeric(df[x_field], errors="coerce").dropna()
    auto_bin_extent: Optional[List[float]] = None
    n_clipped = 0
    if mapping.get("_histogram_bin_extent") is not None:
        be = mapping["_histogram_bin_extent"]
        auto_bin_extent = [float(be[0]), float(be[1])]
    elif mapping.get("bin_extent") is not None:
        be = mapping["bin_extent"]
        auto_bin_extent = [float(be[0]), float(be[1])]
    elif len(series) >= 20:
        x_min = float(series.min())
        x_max = float(series.max())
        full_range = x_max - x_min
        if full_range > 0:
            p01 = float(series.quantile(0.01))
            p99 = float(series.quantile(0.99))
            body_range = p99 - p01
            if body_range > 0 and body_range / full_range < 0.30:
                margin = body_range * 0.10
                auto_bin_extent = [p01 - margin, p99 + margin]
                n_clipped = int(((series < auto_bin_extent[0]) | (series > auto_bin_extent[1])).sum())
                logger.info(
                    "[_build_histogram] heavy-tail detected: clipping x to "
                    "[%.4g, %.4g] (%d outliers excluded)",
                    auto_bin_extent[0], auto_bin_extent[1], n_clipped,
                )

    if auto_bin_extent is not None:
        bin_kwargs = alt.Bin(maxbins=bins, extent=auto_bin_extent)
    else:
        bin_kwargs = alt.Bin(maxbins=bins)

    # Compute explicit tick positions so labels space regularly. Without
    # this, Vega-Lite picks tick positions aligned to BIN BOUNDARIES,
    # producing irregular spacing like ``-34 -28 -24 -20 ... -8 -4 0 2
    # 4 6 8`` (every 4 in the body, every 2 near zero). We pick a "nice"
    # step (1/2/2.5/5/10/...) targeting ~8 labels across the visible
    # domain and emit explicit tick ``values`` so Vega-Lite uses our
    # spacing instead of the bin grid.
    if auto_bin_extent is not None:
        ext_lo, ext_hi = auto_bin_extent
    else:
        ext_lo = float(series.min())
        ext_hi = float(series.max())
    ext_range = max(ext_hi - ext_lo, 1e-9)
    target_ticks = max(6, min(12, int(width / 80)))
    raw_step = ext_range / target_ticks
    nice_steps = [1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000]
    magnitude = 10 ** int(math.floor(math.log10(max(raw_step, 1e-9))))
    step = next(
        (s * magnitude for s in nice_steps if s * magnitude >= raw_step),
        nice_steps[-1] * magnitude,
    )
    # Snap the first tick to a multiple of step at or below ext_lo.
    first_tick = math.floor(ext_lo / step) * step
    last_tick = math.ceil(ext_hi / step) * step
    n_ticks = int(round((last_tick - first_tick) / step)) + 1
    hist_tick_values = [first_tick + i * step for i in range(n_ticks)]
    # Drop ticks outside the actual extent (snap can overshoot).
    hist_tick_values = [
        v for v in hist_tick_values if ext_lo - step / 2 <= v <= ext_hi + step / 2
    ]

    hist_opacity, hist_opacity_enc = _prepare_categorical_opacity(
        mapping,
        color_field if (color_field and color_field in df.columns) else None,
        df,
        mark_config.get("opacity", 0.8),
    )

    chart = (
        alt.Chart(df)
        .mark_bar(
            opacity=hist_opacity,
            cornerRadius=mark_config.get("cornerRadius", 0),
        )
        .encode(
            x=alt.X(
                x_field,
                bin=bin_kwargs,
                type="quantitative",
                title=x_title,
                axis=alt.Axis(
                    titleFontWeight="normal",
                    values=hist_tick_values,
                    labelOverlap="greedy",
                ),
                scale=alt.Scale(domain=auto_bin_extent) if auto_bin_extent else alt.Undefined,
            ),
            y=alt.Y(
                "count()",
                type="quantitative",
                title="Count",
                axis=alt.Axis(titleFontWeight="normal"),
            ),
            tooltip=tooltips,
        )
        .properties(width=width, height=height)
    )

    if color_field and color_field in df.columns:
        chart = _encode_categorical_color_and_opacity(
            chart,
            mapping,
            skin_config,
            color_field,
            df,
            color_sort=_resolve_color_sort(
                df, color_field, mapping.get("color_sort"),
            ),
            opacity_encoding=hist_opacity_enc,
        )
    else:
        chart = chart.encode(color=alt.value(primary_color))

    chart = _force_data_embedding(chart, df)
    logger.debug("[_build_histogram] DONE")
    return chart


def _build_boxplot(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Box plot for cross-sectional distribution comparisons.

    Issue #1 fix: ensures whiskers don't extend beyond chart boundaries
    by computing an explicit y-axis domain that includes all data with
    10% padding, and applying ``clip=True`` to the mark. Boxplot has
    built-in tooltips from Altair (min, Q1, median, Q3, max).
    """
    logger.info("[_build_boxplot] START: df.shape=%s", df.shape)
    logger.debug("[_build_boxplot] mapping: %s", mapping)

    if len(df) == 0:
        raise ValidationError(
            "DataFrame is empty. Cannot create boxplot from empty data."
        )

    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    color_field = _get_field(mapping, "color")

    if y_field is None or y_field not in df.columns:
        logger.error(
            "[_build_boxplot] y_field %r not in columns: %s",
            y_field, list(df.columns),
        )
        raise ValidationError(
            f"y_field '{y_field}' not found in DataFrame columns: "
            f"{list(df.columns)}"
        )
    if df[y_field].notna().sum() == 0:
        raise ValidationError(f"y_field '{y_field}' has no valid values.")

    x_title = _format_label(x_field, mapping, "x") if x_field else None
    y_title = _format_label(y_field, mapping, "y")
    _validate_y_axis_label(y_title, mapping)

    # Compute an outlier-aware y-domain so a single extreme point doesn't
    # flatten the boxes. With Tukey 1.5*IQR whiskers we'd nominally clip at
    # the whisker bounds, but that hides outlier dots from the user
    # entirely (an outlier at the 99.5th percentile gets rendered above
    # the visible y-axis, so the chart looks "clean" but is misleading).
    # Instead, the per-group bounds are widened to include outliers up to
    # the 1st / 99th percentile of the group, capped at the data's true
    # min/max. Boxes still occupy most of the frame; outlier dots remain
    # visible as a signal.
    extent = mapping.get("extent", 1.5)

    def _domain_bounds(series: pd.Series) -> Tuple[float, float]:
        s = series.dropna()
        if len(s) == 0:
            return float("nan"), float("nan")
        s_min = float(s.min())
        s_max = float(s.max())
        q1 = float(s.quantile(0.25))
        q3 = float(s.quantile(0.75))
        iqr = q3 - q1
        if isinstance(extent, (int, float)) and iqr > 0:
            whisker_lo = q1 - extent * iqr
            whisker_hi = q3 + extent * iqr
            # Extend to include outlier dots up to the 1st / 99th percentile
            # of this group, but never beyond the data's true min/max.
            p01 = float(s.quantile(0.01)) if len(s) >= 20 else s_min
            p99 = float(s.quantile(0.99)) if len(s) >= 20 else s_max
            lo = max(s_min, min(whisker_lo, p01))
            hi = min(s_max, max(whisker_hi, p99))
            return lo, hi
        return s_min, s_max

    if x_field and x_field in df.columns:
        bounds_lo: List[float] = []
        bounds_hi: List[float] = []
        for _, group in df.groupby(x_field):
            lo, hi = _domain_bounds(group[y_field])
            if pd.notna(lo) and pd.notna(hi):
                bounds_lo.append(lo)
                bounds_hi.append(hi)
        if bounds_lo and bounds_hi:
            y_min = min(bounds_lo)
            y_max = max(bounds_hi)
        else:
            y_min = float(df[y_field].min())
            y_max = float(df[y_field].max())
    else:
        y_min, y_max = _domain_bounds(df[y_field])

    y_range = y_max - y_min
    y_padding = y_range * 0.15 if y_range > 0 else max(abs(y_max), 1.0) * 0.15
    y_scale = alt.Scale(domain=[y_min - y_padding, y_max + y_padding])

    mark_config = skin_config.get("mark_config", {}).get("boxplot", {})
    primary_color = _resolve_single_series_color(mapping, skin_config)
    box_opacity, box_opacity_enc = _prepare_categorical_opacity(
        mapping,
        color_field if (color_field and color_field in df.columns) else None,
        df,
        mark_config.get("opacity", 1.0),
    )
    encodings: Dict[str, Any] = {
        "y": alt.Y(
            y_field,
            type="quantitative",
            title=y_title,
            scale=y_scale,
            axis=alt.Axis(titleFontWeight="normal"),
        ),
    }
    if x_field and x_field in df.columns:
        encodings["x"] = alt.X(
            x_field,
            type="nominal",
            sort=mapping.get("x_sort"),
            title=x_title,
            axis=alt.Axis(
                titleFontWeight="normal", labelAngle=-45, labelLimit=200,
            ),
        )

    # Tukey-style 1.5*IQR whiskers (the convention) so outliers are
    # plotted as separate dots beyond the whisker, instead of stretching
    # the whisker to the min/max of the column. Boxes use the skin's
    # primary color when no ``color`` encoding is provided so a
    # single-group boxplot in a composite matches the navy used by
    # bars / lines / scatter, instead of inheriting Vega-Lite's
    # default steelblue.
    boxplot_kwargs: Dict[str, Any] = dict(
        extent=extent,
        size=mark_config.get("size", 40),
        clip=True,
        opacity=box_opacity,
    )
    if not (color_field and color_field in df.columns):
        boxplot_kwargs["color"] = primary_color

    chart = (
        alt.Chart(df)
        .mark_boxplot(**boxplot_kwargs)
        .encode(**encodings)
        .properties(width=width, height=height)
    )

    if color_field and color_field in df.columns:
        chart = _encode_categorical_color_and_opacity(
            chart,
            mapping,
            skin_config,
            color_field,
            df,
            color_sort=_resolve_color_sort(
                df, color_field, mapping.get("color_sort"),
            ),
            opacity_encoding=box_opacity_enc,
        )

    chart = _force_data_embedding(chart, df)
    logger.debug("[_build_boxplot] DONE")
    return chart


def _build_donut(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Donut / pie chart.

    ``mapping['theta']`` (or ``value``/``y``) is the magnitude column;
    ``mapping['color']`` (or ``category``) is the slice category.
    Uses ``mark_arc`` with skin-controlled inner/outer radii and pad
    angle. Negative values rejected by ``validate_plot_ready_df``
    upstream (donuts only make sense on non-negative magnitudes).
    """
    logger.debug("[_build_donut] START: df.shape=%s, mapping=%s", df.shape, mapping)

    if len(df) == 0:
        raise ValidationError(
            "DataFrame is empty. Cannot create donut chart from empty data."
        )

    theta_field = (
        _get_field(mapping, "theta")
        or _get_field(mapping, "value")
        or _get_field(mapping, "y")
    )
    category_field = _get_field(mapping, "color") or _get_field(mapping, "category")

    if not theta_field or theta_field not in df.columns:
        raise ValidationError(
            "donut requires a numeric magnitude column "
            "('theta', 'value', or 'y'); none found in mapping or DataFrame."
        )
    if not category_field or category_field not in df.columns:
        raise ValidationError(
            "donut requires a category column ('color' or 'category')."
        )

    mark_config = skin_config.get("mark_config", {}).get("arc", {})

    # Donut sizing strategy:
    # - Chart frame fills the whole canvas (``width`` x ``height``) so
    #   Vega-Lite centers the arc inside it -- previously we forced a
    #   square frame, which left the right-hand strip of a wide canvas
    #   visibly empty.
    # - Inner / outer radii are sized off the SMALLER axis (with extra
    #   headroom for the legend on wide canvases) so the donut never
    #   gets clipped, regardless of canvas aspect ratio.
    # - Inner / outer are derived from the canvas UNCONDITIONALLY -- the
    #   skin's ``mark_config.arc.innerRadius/outerRadius`` (50/100) are
    #   studio-slider seed values, NOT engine-render defaults; using
    #   them here would leave a 200x200 arc adrift in a 450x450 frame.
    side = min(width, height)
    aspect_ratio = width / height if height > 0 else 1.0
    if aspect_ratio > 1.4:
        # Wide frame: leave room on the right for the legend column.
        radius_budget = min(width * 0.55, height) * 0.48
    elif aspect_ratio < 0.7:
        # Tall frame: legend below; size off width (smaller axis).
        radius_budget = min(width, height * 0.55) * 0.48
    else:
        # Roughly square: fill the frame, leaving ~4% margin to keep
        # slice strokes / corner radii off the edge.
        radius_budget = side * 0.48
    outer_radius = radius_budget
    inner_radius = outer_radius * 0.6

    arc_opacity, arc_opacity_enc = _prepare_categorical_opacity(
        mapping, category_field, df, mark_config.get("opacity", 1.0),
    )

    chart = (
        alt.Chart(df)
        .mark_arc(
            innerRadius=inner_radius,
            outerRadius=outer_radius,
            padAngle=mark_config.get("padAngle", 0.02),
            cornerRadius=mark_config.get("cornerRadius", 3),
            opacity=arc_opacity,
        )
        .encode(
            theta=alt.Theta(theta_field, type="quantitative"),
            tooltip=_build_tooltip(mapping, "donut", df),
        )
        .properties(width=width, height=height)
    )
    chart = _encode_categorical_color_and_opacity(
        chart,
        mapping,
        skin_config,
        category_field,
        df,
        color_sort=_resolve_color_sort(
            df, category_field, mapping.get("color_sort"),
        ),
        opacity_encoding=arc_opacity_enc,
        legend_kwargs={"offset": 8},
    )
    return _force_data_embedding(chart, df)


def _build_bullet(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Bullet / range-dot chart for percentile / current-vs-range views.

    Each row gets a horizontal gray range bar (``x_low`` to ``x_high``)
    and a colored diamond marker at the current value. Optional
    ``color_by`` drives marker color via a diverging scale. The function
    auto-detects whether ``color_by`` looks like z-scores (centered on
    zero, |z| <= 3 typical) or percentiles (0-100 with values > 10) and
    chooses the appropriate color domain. Optional ``label`` adds text
    annotation next to each marker.

    Used for: rates RV screens, credit RV dashboards, macro anomaly
    detection.

    Required mapping keys:
      - ``y``: categorical row label column
      - ``x``: current value column
      - ``x_low``: range minimum column
      - ``x_high``: range maximum column

    Optional mapping keys:
      - ``color_by``: numeric column whose magnitude drives marker color
      - ``label``: column whose value is annotated next to the marker
      - ``y_title`` / ``x_title``: axis title overrides
    """
    logger.info("[_build_bullet] START: df.shape=%s", df.shape)
    logger.debug("[_build_bullet] mapping: %s", mapping)

    if len(df) == 0:
        raise ValidationError(
            "DataFrame is empty. Cannot create bullet chart from empty data."
        )

    y_field = _get_field(mapping, "y")
    x_field = _get_field(mapping, "x")
    x_low_field = mapping.get("x_low")
    x_high_field = mapping.get("x_high")
    color_by_field = mapping.get("color_by")
    label_field = mapping.get("label")

    # Field validation.
    for fname, fval in [
        ("y", y_field), ("x", x_field),
        ("x_low", x_low_field), ("x_high", x_high_field),
    ]:
        if fval is None or fval not in df.columns:
            raise ValidationError(
                f"bullet requires mapping['{fname}'] to reference a column "
                f"in df. Got y={y_field!r}, x={x_field!r}, "
                f"x_low={x_low_field!r}, x_high={x_high_field!r}. "
                f"Available: {list(df.columns)}"
            )

    # Non-null sanity check.
    for fname in (y_field, x_field, x_low_field, x_high_field):
        if df[fname].notna().sum() == 0:
            raise ValidationError(
                f"Column '{fname}' has no valid values."
            )

    df = df.copy()
    x_title = _format_label(x_field, mapping, "x")
    # Bullet charts don't need a y-axis title in practice -- the row
    # labels themselves describe what's there. Suppress it unless the
    # caller explicitly passes ``y_title``.
    y_title = (
        mapping["y_title"]
        if mapping.get("y_title")
        else None
    )
    _validate_y_axis_label(y_title, mapping)

    # Preserve user's row order; without explicit sort, Altair sorts
    # categorically (alphabetical) which is rarely what the user wants
    # for a ranking-style view.
    y_sort_order = list(df[y_field])

    # ---- Layer 1: gray range bars (x_low to x_high) ---------------------
    range_bar = (
        alt.Chart(df)
        .mark_bar(height=12, color="#D0D0D0", cornerRadius=3.5)
        .encode(
            x=alt.X(
                x_low_field,
                type="quantitative",
                title=x_title,
                axis=alt.Axis(titleFontWeight="normal"),
            ),
            x2=alt.X2(x_high_field),
            y=alt.Y(
                y_field,
                type="nominal",
                title=y_title,
                sort=y_sort_order,
                axis=alt.Axis(titleFontWeight="normal"),
            ),
        )
        .properties(width=width, height=height)
    )

    # ---- Layer 2: current-value markers ---------------------------------
    marker_size = mapping.get("marker_size", 200)
    primary_color = _resolve_single_series_color(mapping, skin_config)

    if color_by_field and color_by_field in df.columns:
        # Auto-detect: z-score (centered around 0) vs percentile (0-100).
        col_min = float(df[color_by_field].min())
        col_max = float(df[color_by_field].max())
        looks_like_percentile = (
            col_min >= 0 and col_max <= 100 and col_max > 10
        )

        if looks_like_percentile:
            # Map distance-from-50 to color (extremes flagged red).
            df["_bullet_color_val"] = (df[color_by_field] - 50).abs()
            color_enc = alt.Color(
                "_bullet_color_val:Q",
                scale=alt.Scale(
                    domain=[0, 25, 50],
                    range=["#2EB857", "#FFD700", "#DC143C"],
                ),
                legend=alt.Legend(title="Dist. from 50th"),
            )
        else:
            # Z-score: map |z| to color, with [0, 1, 2] domain.
            df["_bullet_color_val"] = df[color_by_field].abs()
            color_enc = alt.Color(
                "_bullet_color_val:Q",
                scale=alt.Scale(
                    domain=[0, 1, 2],
                    range=["#2EB857", "#FFD700", "#DC143C"],
                ),
                legend=alt.Legend(title="|Z-Score|"),
            )

        markers = (
            alt.Chart(df)
            .mark_point(
                size=marker_size,
                filled=True,
                shape="diamond",
                stroke="#333333",
                strokeWidth=0.8,
            )
            .encode(
                x=alt.X(x_field, type="quantitative"),
                y=alt.Y(y_field, type="nominal", sort=y_sort_order),
                color=color_enc,
                tooltip=[
                    alt.Tooltip(y_field, type="nominal", title="Variable"),
                    alt.Tooltip(
                        x_field, type="quantitative", title="Current",
                        format=".1f",
                    ),
                    alt.Tooltip(
                        x_low_field, type="quantitative", title="Range Low",
                        format=".1f",
                    ),
                    alt.Tooltip(
                        x_high_field, type="quantitative", title="Range High",
                        format=".1f",
                    ),
                    alt.Tooltip(
                        color_by_field, type="quantitative",
                        title=color_by_field, format=".2f",
                    ),
                ],
            )
            .properties(width=width, height=height)
        )
    else:
        markers = (
            alt.Chart(df)
            .mark_point(
                size=marker_size,
                filled=True,
                shape="diamond",
                color=primary_color,
                stroke="#333333",
                strokeWidth=0.8,
            )
            .encode(
                x=alt.X(x_field, type="quantitative"),
                y=alt.Y(y_field, type="nominal", sort=y_sort_order),
                tooltip=[
                    alt.Tooltip(y_field, type="nominal", title="Variable"),
                    alt.Tooltip(
                        x_field, type="quantitative", title="Current",
                        format=".1f",
                    ),
                    alt.Tooltip(
                        x_low_field, type="quantitative", title="Range Low",
                        format=".1f",
                    ),
                    alt.Tooltip(
                        x_high_field, type="quantitative", title="Range High",
                        format=".1f",
                    ),
                ],
            )
            .properties(width=width, height=height)
        )

    chart = alt.layer(range_bar, markers)

    # ---- Layer 3: optional text annotations -----------------------------
    if label_field and label_field in df.columns:
        # Catch-all rounding: if the label column is numeric, pre-
        # stringify with magnitude-aware decimals so a raw 99.917898193
        # never lands on the canvas. Pre-formatted string columns
        # (e.g. "+1.4σ") pass through untouched.
        if pd.api.types.is_numeric_dtype(df[label_field]):
            df["_bullet_label_str"] = df[label_field].map(_smart_format_value)
            text_field = "_bullet_label_str"
        else:
            text_field = label_field
        text_layer = (
            alt.Chart(df)
            .mark_text(align="left", dx=12, fontSize=11, color="#555555")
            .encode(
                x=alt.X(x_field, type="quantitative"),
                y=alt.Y(y_field, type="nominal", sort=y_sort_order),
                text=alt.Text(text_field, type="nominal"),
            )
            .properties(width=width, height=height)
        )
        chart = alt.layer(chart, text_layer)

    chart = chart.properties(width=width, height=height)
    chart = _force_data_embedding(chart, df)
    logger.debug("[_build_bullet] DONE")
    return chart


def _build_waterfall(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Waterfall / decomposition / attribution chart.

    Shows a starting value, a series of positive/negative contributions,
    and an ending value. Bars "float" -- each starts where the previous
    one ended. Positive contributions render green, negatives red,
    totals dark blue (skin primary). Total bars are anchored at 0;
    intermediate bars float from the running total.

    Mapping keys:
      - ``x`` (required): category column (bar labels on x-axis).
      - ``y`` (required): value column (contribution amounts).
      - ``type`` (optional): column with ``'total'`` / ``'positive'`` /
        ``'negative'`` per row. If absent, the first and last rows are
        treated as totals and the sign of the value determines pos/neg
        for the rest.
      - ``x_title`` / ``y_title`` (optional): axis title overrides.

    Used for: CPI decomposition, P&L attribution, GDP growth
    decomposition, FCI impulse, and any additive breakdown.

    Pipeline structure:
      Layer 1 (bars): floating mark_bar with y=_wf_y_start, y2=_wf_y_end.
      Layer 2 (connectors): dashed gray rules between adjacent bars.
      Layer 3 (text labels): value annotation on top of each bar.

    All three layers share the SAME ``x_field`` and ``_wf_y_start`` y
    field name so Vega-Lite merges their axes cleanly. Without this,
    layered specs end up with concatenated axis titles.
    """
    logger.info("[_build_waterfall] START: df.shape=%s", df.shape)
    logger.debug("[_build_waterfall] mapping: %s", mapping)

    if len(df) == 0:
        raise ValidationError(
            "DataFrame is empty. Cannot create waterfall chart from empty data."
        )

    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")
    type_field = mapping.get("type")

    for fname, fval in [("x", x_field), ("y", y_field)]:
        if fval is None or fval not in df.columns:
            raise ValidationError(
                f"Required mapping key '{fname}' (value={fval!r}) not found "
                f"in DataFrame columns: {list(df.columns)}"
            )

    df = df.copy()
    df[y_field] = pd.to_numeric(df[y_field], errors="coerce")
    if df[y_field].notna().sum() == 0:
        raise ValidationError(
            f"Column '{y_field}' has no valid numeric values."
        )

    # ---- determine bar types (explicit column or auto-detect) -----------
    if type_field and type_field in df.columns:
        df["_wf_type"] = df[type_field].astype(str).str.lower().str.strip()
    else:
        # First and last rows are totals; intermediates by sign.
        types: List[str] = []
        for i in range(len(df)):
            if i == 0 or i == len(df) - 1:
                types.append("total")
            elif df[y_field].iloc[i] >= 0:
                types.append("positive")
            else:
                types.append("negative")
        df["_wf_type"] = types
        logger.debug(
            "[_build_waterfall] auto-detected types: first/last=total, "
            "rest by sign",
        )

    # F2 fix: validate that intermediate values sum to (last - first).
    # Off by >15% suggests the data is not a true additive decomposition.
    if len(df) >= 3 and df.iloc[0]["_wf_type"] == "total" and df.iloc[-1]["_wf_type"] == "total":
        first_total = float(df[y_field].iloc[0])
        last_total = float(df[y_field].iloc[-1])
        intermediate_sum = float(df[y_field].iloc[1:-1].sum())
        expected_diff = last_total - first_total
        if abs(expected_diff) > 1e-9:
            ratio = intermediate_sum / expected_diff
            if abs(ratio - 1) > 0.15:
                logger.warning(
                    "[_build_waterfall] intermediate values sum to %.2f but "
                    "(last - first) = %.2f. Data may not be a true additive "
                    "decomposition. Consider providing an explicit 'type' "
                    "column with 'total'/'positive'/'negative'.",
                    intermediate_sum, expected_diff,
                )

    # ---- compute floating bar positions ---------------------------------
    y_starts: List[float] = []
    y_ends: List[float] = []
    running = 0.0
    for i in range(len(df)):
        bar_type = df["_wf_type"].iloc[i]
        val = float(df[y_field].iloc[i])
        if bar_type == "total":
            y_starts.append(0.0)
            y_ends.append(val)
            running = val
        else:
            y_starts.append(running)
            running += val
            y_ends.append(running)
    df["_wf_y_start"] = y_starts
    df["_wf_y_end"] = y_ends

    # ---- color by type --------------------------------------------------
    primary_color = _resolve_single_series_color(mapping, skin_config)
    color_map = {
        "total": primary_color,
        "positive": "#2EB857",
        "negative": "#DC143C",
    }
    df["_wf_color"] = df["_wf_type"].map(color_map).fillna(primary_color)

    # ---- titles ---------------------------------------------------------
    x_title = _format_label(x_field, mapping, "x")
    y_title = _format_label(y_field, mapping, "y")
    _validate_y_axis_label(y_title, mapping)

    # Preserve original x order (don't lex-sort).
    x_sort_order = list(df[x_field])

    # Wrap nominal x-labels for readability.
    df[x_field] = df[x_field].apply(lambda v: wrap_label(str(v), words_per_line=2))
    x_sort_order = [wrap_label(str(v), words_per_line=2) for v in x_sort_order]

    mark_config = skin_config.get("mark_config", {}).get("bar", {})

    # ---- Layer 1: floating bars (defines axes) --------------------------
    bars = (
        alt.Chart(df)
        .mark_bar(
            cornerRadiusTopLeft=mark_config.get("cornerRadius", 0),
            cornerRadiusTopRight=mark_config.get("cornerRadius", 0),
            opacity=mark_config.get("opacity", 1.0),
        )
        .encode(
            x=alt.X(
                x_field,
                type="nominal",
                title=x_title,
                sort=x_sort_order,
                axis=alt.Axis(titleFontWeight="normal", labelAngle=0),
            ),
            y=alt.Y(
                "_wf_y_start:Q",
                title=y_title,
                axis=alt.Axis(titleFontWeight="normal"),
            ),
            y2=alt.Y2("_wf_y_end:Q"),
            color=alt.Color("_wf_color:N", scale=None, legend=None),
            tooltip=[
                alt.Tooltip(x_field, type="nominal", title="Category"),
                alt.Tooltip(y_field, type="quantitative", title="Value", format=".1f"),
                alt.Tooltip("_wf_type:N", title="Type"),
                alt.Tooltip("_wf_y_end:Q", title="Running Total", format=".1f"),
            ],
        )
        .properties(width=width, height=height)
    )

    # ---- Layer 2: connector lines between adjacent bars -----------------
    connector_records = []
    for i in range(len(df) - 1):
        connector_records.append({
            x_field: df[x_field].iloc[i],
            "_conn_x2": df[x_field].iloc[i + 1],
            # Same y field name as bars layer (avoid second axis).
            "_wf_y_start": df["_wf_y_end"].iloc[i],
        })
    if connector_records:
        conn_df = pd.DataFrame(connector_records)
        connectors = (
            alt.Chart(conn_df)
            .mark_rule(color="#999999", strokeWidth=1, strokeDash=[3, 3])
            .encode(
                x=alt.X(
                    f"{x_field}:N", sort=x_sort_order, title=None,
                ),
                x2=alt.X2("_conn_x2:N"),
                y=alt.Y("_wf_y_start:Q", title=None),
            )
            .properties(width=width, height=height)
        )
    else:
        connectors = None

    # ---- Layer 3: value labels on top of each bar -----------------------
    df["_wf_label_y"] = df[["_wf_y_start", "_wf_y_end"]].max(axis=1)
    # Magnitude-aware rounding: pick decimals from the y-column's max
    # absolute value so a 2,350 bar reads "2,350" and a 0.085 bar reads
    # "0.085" instead of both forced to a single ".1f".
    _wf_label_template = _smart_format_template(df[y_field])
    df["_wf_label_text"] = df[y_field].apply(
        lambda v: _wf_label_template.format(v) if pd.notna(v) and v >= 0 else (
            f"({_wf_label_template.format(abs(v))})" if pd.notna(v) else ""
        )
    )
    # Rename label_y -> _wf_y_start so this layer shares the same y field
    # name as the bars layer (prevents axis title pollution).
    label_df = df[[x_field, "_wf_label_y", "_wf_label_text"]].copy()
    label_df = label_df.rename(columns={"_wf_label_y": "_wf_y_start"})

    text_labels = (
        alt.Chart(label_df)
        .mark_text(
            align="center",
            baseline="bottom",
            dy=-4,
            fontSize=11,
            fontWeight="bold",
            color="#555555",
        )
        .encode(
            x=alt.X(f"{x_field}:N", sort=x_sort_order, title=None),
            y=alt.Y("_wf_y_start:Q", title=None),
            text=alt.Text("_wf_label_text:N"),
        )
        .properties(width=width, height=height)
    )

    # Use + (alt.layer) instead of resolve_scale -- the latter causes
    # Vega-Lite to concatenate axis titles from all layers even when
    # they share the same field. + with title=None on secondary layers
    # works correctly.
    if connectors is not None:
        chart = bars + connectors + text_labels
    else:
        chart = bars + text_labels

    chart = _force_data_embedding(chart, df)
    logger.debug("[_build_waterfall] DONE")
    return chart


def _build_layer(
    df: pd.DataFrame,
    layer_spec: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
) -> alt.Chart:
    """Build a single overlay layer from a layer specification dict.

    Layer spec format::

        {
            'type': 'line' | 'rule' | 'point' | 'text' | 'regression',
            'data': Optional[DataFrame],     # If None, uses main df
            'x': x_field_name,
            'y': y_field_name,
            'color': Optional[str],
            ...other mark-specific properties (stroke_width, stroke_dash,
            method, font_size, text, dx, dy, size, ...)
        }

    Returns an Altair chart for a single overlay layer; multiple layers
    can be composed by the caller with ``alt.layer(*layers)``. Unknown
    layer types fall through to an empty chart so a typo doesn't abort
    the whole pipeline.
    """
    layer_type = layer_spec.get("type", "line")
    layer_df = layer_spec.get("data", df)

    if layer_type == "line":
        x_field = layer_spec.get("x")
        y_field = layer_spec.get("y")
        color = layer_spec.get("color", skin_config.get("secondary_color", "#666666"))
        return (
            alt.Chart(layer_df)
            .mark_line(
                color=color,
                strokeWidth=layer_spec.get("stroke_width", 1.5),
                strokeDash=layer_spec.get("stroke_dash", []),
            )
            .encode(
                x=alt.X(x_field, type="quantitative"),
                y=alt.Y(y_field, type="quantitative"),
            )
        )

    if layer_type == "regression":
        x_field = layer_spec.get("x")
        y_field = layer_spec.get("y")
        method = layer_spec.get("method", "linear")
        return (
            alt.Chart(layer_df)
            .transform_regression(x_field, y_field, method=method)
            .mark_line(
                color=layer_spec.get(
                    "color", skin_config.get("trendline_color", "#888888")
                ),
                strokeDash=layer_spec.get("stroke_dash", [4, 4]),
            )
            .encode(
                x=alt.X(x_field, type="quantitative"),
                y=alt.Y(y_field, type="quantitative"),
            )
        )

    if layer_type == "rule":
        if "y" in layer_spec and isinstance(layer_spec["y"], (int, float)):
            rule_df = pd.DataFrame({"y": [layer_spec["y"]]})
            return (
                alt.Chart(rule_df)
                .mark_rule(
                    color=layer_spec.get("color", "#666666"),
                    strokeDash=layer_spec.get("stroke_dash", [4, 4]),
                )
                .encode(y="y:Q")
            )
        if "x" in layer_spec:
            rule_df = pd.DataFrame({"x": [layer_spec["x"]]})
            return (
                alt.Chart(rule_df)
                .mark_rule(
                    color=layer_spec.get("color", "#666666"),
                    strokeDash=layer_spec.get("stroke_dash", [4, 4]),
                )
                .encode(x="x:Q")
            )

    if layer_type == "point":
        x_field = layer_spec.get("x")
        y_field = layer_spec.get("y")
        return (
            alt.Chart(layer_df)
            .mark_point(
                size=layer_spec.get("size", 100),
                color=layer_spec.get(
                    "color", skin_config.get("accent_color", "#FF6600")
                ),
                filled=True,
            )
            .encode(
                x=alt.X(x_field, type="quantitative"),
                y=alt.Y(y_field, type="quantitative"),
            )
        )

    if layer_type == "text":
        x_field = layer_spec.get("x")
        y_field = layer_spec.get("y")
        text = layer_spec.get("text", "")
        return (
            alt.Chart(layer_df)
            .mark_text(
                dx=layer_spec.get("dx", 5),
                dy=layer_spec.get("dy", 10),
                fontSize=layer_spec.get("font_size", 10),
                color=layer_spec.get("color", "#333333"),
            )
            .encode(
                x=alt.X(x_field, type="quantitative"),
                y=alt.Y(y_field, type="quantitative"),
                text=alt.value(text),
            )
        )

    # Unknown type -> empty chart so we don't blow up the layered render.
    logger.warning("[_build_layer] Unknown layer type %r; rendering empty.", layer_type)
    return alt.Chart(pd.DataFrame()).mark_point()


def _apply_extra_layers(
    base: alt.Chart,
    df: pd.DataFrame,
    layers: List[Dict[str, Any]],
    skin_config: Dict[str, Any],
) -> alt.Chart:
    """Apply user-supplied ``layers=[...]`` overlays onto a base chart.

    Recognized layer types:
      - ``regression`` / ``trendline``: ``transform_regression`` line.
      - ``rule``: horizontal/vertical reference rule at ``y`` or ``x``.
      - ``point``: scatter overlay (uses ``data`` from the layer dict).
    """
    if not layers:
        return base
    out = base
    for spec in layers:
        layer_type = spec.get("type")
        if layer_type in ("regression", "trendline"):
            method = spec.get("method", "linear")
            x_col = spec.get("x")
            y_col = spec.get("y")
            if x_col and y_col:
                trend = (
                    alt.Chart(df)
                    .transform_regression(x_col, y_col, method=method)
                    .mark_line(
                        color=spec.get(
                            "color", skin_config.get("trendline_color", "#999999")
                        ),
                        strokeWidth=spec.get("stroke_width", 1.5),
                        strokeDash=spec.get("stroke_dash", [6, 3]),
                    )
                    .encode(x=f"{x_col}:Q", y=f"{y_col}:Q")
                )
                out = alt.layer(out, trend)
        elif layer_type == "rule":
            if "y" in spec:
                rule_df = pd.DataFrame({"y": [spec["y"]]})
                rule = (
                    alt.Chart(rule_df)
                    .mark_rule(
                        color=spec.get("color", "#666666"),
                        strokeDash=spec.get("stroke_dash", [4, 4]),
                    )
                    .encode(y="y:Q")
                )
                out = alt.layer(out, rule)
            elif "x" in spec:
                rule_df = pd.DataFrame({"x": [spec["x"]]})
                rule = (
                    alt.Chart(rule_df)
                    .mark_rule(
                        color=spec.get("color", "#666666"),
                        strokeDash=spec.get("stroke_dash", [4, 4]),
                    )
                    .encode(x="x")
                )
                out = alt.layer(out, rule)
        elif layer_type == "point":
            data = spec.get("data")
            if isinstance(data, pd.DataFrame):
                pt = (
                    alt.Chart(data)
                    .mark_point(
                        color=spec.get("color", "#C00000"),
                        size=spec.get("size", 200),
                        filled=True,
                    )
                    .encode(x=f"{spec['x']}:Q", y=f"{spec['y']}:Q")
                )
                out = alt.layer(out, pt)
    return out


# ===========================================================================
# MODULE: PRE-CHART TRANSFORMS (auto-melt, auto-downsample)
# ===========================================================================

def _auto_melt_for_multiline(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Convert wide-format DataFrames to long format for ``multi_line``/``area``.

    Cases handled:
      1. Already long-format (``y`` and ``color`` both exist as columns):
         no-op, returns the inputs unchanged.
      2. ``y`` is a list of column names: melt those columns into a
         long-format frame with ``var_name='series'`` and a value column
         named after ``mapping['y_title']`` (or 'value'). Single-element
         lists short-circuit to a normal single-series chart.
      3. ``y`` and ``color`` neither exist as columns and there are
         >=2 numeric columns besides ``x``: auto-melt all numerics.
      4. ``color`` doesn't exist but there are >=2 numerics: melt those
         numerics with the user's ``color`` field name as the var column.

    Returns:
        ``(df_long, new_mapping)``.

    Raises:
        ValidationError: If the y list references no columns that
            actually exist in the DataFrame.
    """
    try:
        x_field = _get_field(mapping, "x")
        y_field = mapping.get("y")
        color_field = mapping.get("color")

        # Case 0: already long-format -- both y and color exist as columns.
        if isinstance(y_field, str) and y_field in df.columns:
            if color_field and color_field in df.columns:
                return df, mapping

        # Case 1: y is a list of column names.
        if isinstance(y_field, list):
            value_cols = [col for col in y_field if col in df.columns]
            if not value_cols:
                raise ValidationError(
                    f"None of the y columns {y_field} exist in DataFrame. "
                    f"Available: {list(df.columns)}"
                )

            # Single-element list -- skip melt, use the column directly.
            if len(value_cols) == 1:
                new_mapping = dict(mapping)
                new_mapping["y"] = value_cols[0]
                if "color" not in mapping or mapping.get("color") == "series":
                    new_mapping.pop("color", None)
                return df, new_mapping

            preserve_y_name = mapping.get("y_title", "value")
            df_long = df.melt(
                id_vars=[x_field] if x_field else None,
                value_vars=value_cols,
                var_name="series",
                value_name=preserve_y_name,
            )
            # Auto-friendlify underscore column names ("cpi_yoy_pct" ->
            # "CPI YoY %") so the legend doesn't expose raw field names.
            # Names that already look human (contain spaces or %, or are
            # short ALL CAPS) are kept verbatim.
            def _friendly(name: str) -> str:
                s = str(name)
                if " " in s or "%" in s:
                    return s
                if "_" in s:
                    return _format_label(s, {}, "color")
                return s
            friendly_map = {c: _friendly(c) for c in value_cols}
            df_long["series"] = df_long["series"].map(friendly_map)
            new_mapping = dict(mapping)
            new_mapping["y"] = preserve_y_name
            new_mapping["color"] = "series"
            if "y_title" in mapping:
                new_mapping["y_title"] = mapping["y_title"]
            # Preserve user's input order in the legend (instead of
            # whatever ``df.melt`` chose).
            new_mapping.setdefault(
                "color_sort", [friendly_map[c] for c in value_cols]
            )
            return df_long, new_mapping

        # Case 2: y and color don't exist; auto-melt numerics.
        if y_field and isinstance(y_field, str) and y_field not in df.columns:
            if color_field and color_field not in df.columns:
                numeric_cols = [
                    col for col in df.columns
                    if col != x_field and pd.api.types.is_numeric_dtype(df[col])
                ]
                if len(numeric_cols) >= 2:
                    preserve_y_name = mapping.get("y_title", y_field)
                    df_long = df.melt(
                        id_vars=[x_field] if x_field else None,
                        value_vars=numeric_cols,
                        var_name="series",
                        value_name=preserve_y_name,
                    )
                    new_mapping = dict(mapping)
                    new_mapping["y"] = preserve_y_name
                    new_mapping["color"] = "series"
                    return df_long, new_mapping

        # Case 3: color doesn't exist but multiple numerics do.
        if color_field and color_field not in df.columns:
            numeric_cols = [
                col for col in df.columns
                if col != x_field and pd.api.types.is_numeric_dtype(df[col])
            ]
            if len(numeric_cols) >= 2:
                preserve_y_name = mapping.get(
                    "y_title",
                    y_field if y_field and y_field != "value" else "value",
                )
                df_long = df.melt(
                    id_vars=[x_field] if x_field else None,
                    value_vars=numeric_cols,
                    var_name=color_field,
                    value_name=preserve_y_name,
                )
                new_mapping = dict(mapping)
                new_mapping["y"] = preserve_y_name
                return df_long, new_mapping

        # No conversion needed.
        return df, mapping

    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise


def _auto_downsample_timeseries(
    df: pd.DataFrame,
    x_field: str,
    target_rows: int = DOWNSAMPLE_TARGET_ROWS,
) -> Tuple[pd.DataFrame, Optional[str]]:
    """Tier-based time-series downsampling.

    Triggered when ``len(df) > MAX_ROWS_BEFORE_DOWNSAMPLE``. Picks a
    pandas resample frequency based on the data's calendar span:

    ============ ==============
    Span         Frequency
    ============ ==============
    < 1 hour     ``1s``
    < 48 hours   ``1min``
    < 30 days    ``5min``
    < 180 days   ``1H``
    < 2 years    ``1D``
    < 5 years    ``W``
    >= 5 years   ``M``
    ============ ==============

    If after frequency-based resampling the row count is still above
    ``MAX_ROWS_INTERACTIVE``, applies even index sampling (``df.iloc[::step]``).

    Long-format multi-series data (DataFrame with one row per
    ``(date, series)`` and an explicit series identifier column) is
    detected by duplicate timestamps and resampled per series-group so
    no series gets dropped. Without this branch,
    ``df.set_index(date).resample(freq).last()`` would collapse all
    rows in each frequency bucket to a single survivor (the last
    series in insertion order), silently dropping every other series.

    Returns:
        ``(df_downsampled, freq_label)`` where ``freq_label`` is the
        chosen frequency (or ``None`` if no downsampling occurred).
    """
    try:
        if x_field not in df.columns:
            return df, None
        if not pd.api.types.is_datetime64_any_dtype(df[x_field]):
            return df, None
        if len(df) <= MAX_ROWS_BEFORE_DOWNSAMPLE:
            return df, None

        time_range = df[x_field].max() - df[x_field].min()
        date_range_days = time_range.days
        date_range_hours = time_range.total_seconds() / 3600

        if date_range_hours <= 1:
            freq = "1s"
        elif date_range_hours < 48:
            freq = "1min"
        elif date_range_days < 30:
            freq = "5min"
        elif date_range_days < 180:
            freq = "1h"
        elif date_range_days < 730:
            freq = "1D"
        elif date_range_days < 1825:
            freq = "W"
        else:
            freq = "ME"

        # Long-format detection: a date that appears more than once
        # means we have a series identifier column packing multiple
        # rows per timestamp. The naive ``set_index(x).resample.last()``
        # path collapses those rows into a single survivor per bucket,
        # which silently drops every series except whichever one
        # happens to be last in insertion order.
        is_long_format = bool(df[x_field].duplicated().any())

        if is_long_format:
            # Group columns are every non-numeric, non-x column. Typical
            # shapes: ``[date, value, series]`` -> group by ``series``;
            # ``[date, country, sector, value]`` -> group by
            # ``[country, sector]``. Numeric columns are treated as
            # value columns even if they hold integer codes (we'd rather
            # lose a numeric series-id column than collapse the panel).
            group_cols = [
                c for c in df.columns
                if c != x_field
                and not pd.api.types.is_numeric_dtype(df[c])
            ]
            if not group_cols:
                # No string columns means the duplicate dates are not
                # series-keyed; fall through to the standard path.
                is_long_format = False

        if is_long_format:
            def _resample_one(g: pd.DataFrame) -> pd.DataFrame:
                g_indexed = g.set_index(x_field)
                # Resample-then-take-last keeps the most-recent
                # observation in each frequency bucket per series.
                return g_indexed.resample(freq).last().reset_index()

            df_down = (
                df.groupby(group_cols, sort=False, group_keys=False)
                .apply(_resample_one)
                .reset_index(drop=True)
            )
            # Numeric value columns that are all-NaN within a bucket
            # signify an empty bucket for that series; drop those rows.
            value_cols = [
                c for c in df_down.columns
                if c != x_field and c not in group_cols
            ]
            if value_cols:
                df_down = df_down.dropna(how="all", subset=value_cols)
        else:
            df_indexed = df.set_index(x_field)
            df_down = df_indexed.resample(freq).last().reset_index()
            value_cols = [c for c in df_down.columns if c != x_field]
            df_down = df_down.dropna(how="all", subset=value_cols)

        if len(df_down) > MAX_ROWS_INTERACTIVE:
            step = max(1, len(df_down) // target_rows)
            df_down = df_down.iloc[::step].copy()
            freq = f"{freq}+evenly_sampled"

        return df_down, freq

    except Exception as exc:  # noqa: BLE001
        return df, None


# ===========================================================================
# MODULE: UTILS (data prep + scale diagnostics + label utilities)
# ===========================================================================

def prepare_timeseries_df(
    df: pd.DataFrame,
    date_col: str,
    value_cols: List[str],
    *,
    freq: Optional[str] = None,
    fill_method: Optional[str] = None,
    aggregate: str = "mean",
) -> pd.DataFrame:
    """Prepare a DataFrame for time-series plotting.

    Handles the standard time-series prep steps in a single call:

      1. Coerce the date column to datetime.
      2. Melt to long format if multiple value columns are supplied
         (output columns: ``date``, ``value``, ``series``).
      3. Optionally resample to a target frequency, grouping by series.
      4. Optionally fill missing values (``ffill`` / ``bfill`` /
         ``interpolate``).

    Args:
        df: Input DataFrame.
        date_col: Name of the date column.
        value_cols: List of value column names. A single column produces
            a single-series long frame (``series=col_name``).
        freq: Target frequency for resampling (``'D'``, ``'W'``, ``'M'``).
        fill_method: ``'ffill'``, ``'bfill'``, ``'interpolate'``, or None.
        aggregate: Aggregation method for resampling
            (``'mean'``, ``'sum'``, ``'last'``).

    Returns:
        Plot-ready long-format DataFrame with columns
        ``date``, ``value``, ``series``.
    """
    result = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(result[date_col]):
        result[date_col] = pd.to_datetime(result[date_col])

    if len(value_cols) > 1:
        result = pd.melt(
            result,
            id_vars=[date_col],
            value_vars=value_cols,
            var_name="series",
            value_name="value",
        )
        result = result.rename(columns={date_col: "date"})
    else:
        result = result[[date_col, value_cols[0]]].copy()
        result.columns = ["date", "value"]
        result["series"] = value_cols[0]

    if freq:
        result = (
            result.set_index("date")
            .groupby("series")
            .resample(freq)
            .agg({"value": aggregate})
            .reset_index()
        )

    if fill_method:
        if fill_method == "interpolate":
            result["value"] = result.groupby("series")["value"].transform(
                lambda x: x.interpolate()
            )
        else:
            result["value"] = result.groupby("series")["value"].transform(
                lambda x: getattr(x, fill_method)()
            )

    return result


def process_data(
    df: pd.DataFrame,
    date_col: str,
    value_cols: List[str],
    *,
    freq: Optional[str] = None,
    fill_method: Optional[str] = None,
    aggregate: str = "mean",
) -> pd.DataFrame:
    """Alias for ``prepare_timeseries_df`` -- preserved for PRISM
    compatibility (some downstream code imports the older name)."""
    return prepare_timeseries_df(
        df, date_col, value_cols,
        freq=freq, fill_method=fill_method, aggregate=aggregate,
    )


def top_k_categories(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
    k: int = 10,
    other_label: str = "Other",
    method: str = "sum",
) -> pd.DataFrame:
    """Reduce a categorical column to the top-k categories plus 'Other'.

    Useful for capping color/facet cardinality before plotting. The
    long-tail categories are aggregated into a single ``other_label``
    bucket, ranked by ``method`` applied to ``value_col``.

    Args:
        df: Input DataFrame.
        category_col: Column containing category labels.
        value_col: Column to aggregate for ranking.
        k: Number of top categories to keep.
        other_label: Label for the aggregated remainder.
        method: Aggregation method (``'sum'``, ``'mean'``, ``'count'``).

    Returns:
        DataFrame with an additional ``{category_col}_reduced`` column
        containing the top-k labels or ``other_label``.
    """
    category_ranks = (
        df.groupby(category_col)[value_col].agg(method).sort_values(ascending=False)
    )
    top_categories = set(category_ranks.head(k).index)

    result = df.copy()
    result[f"{category_col}_reduced"] = result[category_col].apply(
        lambda x: x if x in top_categories else other_label
    )
    return result


def detect_scale_issues(
    df: pd.DataFrame,
    y_cols: List[str],
) -> Dict[str, Any]:
    """Detect potential scaling issues across multiple y series.

    Identifies when series have very different ranges that would cause
    visual flattening if plotted on a shared axis (e.g. equity index
    in the thousands vs. policy rate in single digits). Returns a
    diagnostic dict with a ``recommendation`` string suggesting
    dual-axis or faceted layouts when the heuristic flags an issue.

    Heuristic:
      - ``range_ratio = max(range) / min(range) > 5`` flags an issue.
      - ``mean_ratio = max(|mean|) / min(|mean|) > 10`` flags an issue.
    """
    if len(y_cols) < 2:
        return {"issue": False}

    ranges: Dict[str, Dict[str, float]] = {}
    for col in y_cols:
        if pd.api.types.is_numeric_dtype(df[col]):
            col_min = float(df[col].min())
            col_max = float(df[col].max())
            ranges[col] = {
                "min": col_min,
                "max": col_max,
                "range": col_max - col_min,
                "mean": float(df[col].mean()),
            }

    if len(ranges) < 2:
        return {"issue": False}

    all_ranges = [r["range"] for r in ranges.values() if r["range"] > 0]
    if not all_ranges:
        return {"issue": False}

    range_ratio = max(all_ranges) / min(all_ranges) if min(all_ranges) > 0 else 1.0
    all_means = [abs(r["mean"]) for r in ranges.values() if r["mean"] != 0]
    mean_ratio = (
        max(all_means) / min(all_means)
        if all_means and min(all_means) > 0
        else 1.0
    )

    has_issue = range_ratio > 5 or mean_ratio > 10
    return {
        "issue": has_issue,
        "range_ratio": range_ratio,
        "mean_ratio": mean_ratio,
        "recommendation": (
            "Use dual y-axis or faceted charts" if has_issue else None
        ),
        "details": ranges,
    }


def smart_label_format(value: float, context: str = "general") -> str:
    """Format a numeric value for display, choosing a sensible style for
    the data context.

    Contexts:
      - ``percent``: ``"12.3%"``
      - ``currency``: ``"$1.2B"``, ``"$3.4M"``, ``"$5.6K"``, ``"$78"``
      - ``large``: same magnitude suffixes without the dollar sign
      - ``general``: scientific notation for very small magnitudes,
        otherwise sensible decimal precision

    Returns the empty string for NaN.
    """
    if pd.isna(value):
        return ""

    if context == "percent":
        return f"{value:.1f}%"

    if context == "currency":
        if abs(value) >= 1e9:
            return f"${value / 1e9:.1f}B"
        if abs(value) >= 1e6:
            return f"${value / 1e6:.1f}M"
        if abs(value) >= 1e3:
            return f"${value / 1e3:.1f}K"
        return f"${value:.0f}"

    if context == "large" or abs(value) >= 1e6:
        if abs(value) >= 1e9:
            return f"{value / 1e9:.1f}B"
        if abs(value) >= 1e6:
            return f"{value / 1e6:.1f}M"
        if abs(value) >= 1e3:
            return f"{value / 1e3:.1f}K"
        return str(value)

    if abs(value) < 0.01:
        return f"{value:.2e}"
    if abs(value) < 1:
        return f"{value:.3f}"
    if abs(value) < 100:
        return f"{value:.2f}"
    return f"{value:.0f}"


def calculate_safe_axis_range(
    data: pd.Series,
    padding_pct: float = 0.05,
    handle_outliers: bool = True,
) -> Tuple[float, float]:
    """Calculate a sensible axis range for a numeric series.

    Variant of ``calculate_y_axis_domain`` that uses 2.5*IQR outlier
    clipping (less aggressive than the standard 1.5*IQR) so a single
    extreme value doesn't crush the visible range. Used by chart
    types that benefit from outlier suppression (scatter, heatmap)
    rather than the strict zero-prevention behavior of
    ``calculate_y_axis_domain``.

    Args:
        data: Numeric series.
        padding_pct: Fractional padding to add on both sides.
        handle_outliers: When True, clip the range with 2.5*IQR.

    Returns:
        ``(min, max)`` tuple suitable for ``alt.Scale(domain=...)``.
    """
    clean_data = data.dropna()
    if len(clean_data) == 0:
        return (0.0, 1.0)

    if handle_outliers and len(clean_data) > 10:
        q1 = clean_data.quantile(0.25)
        q3 = clean_data.quantile(0.75)
        iqr = q3 - q1
        lower = max(float(clean_data.min()), float(q1 - 2.5 * iqr))
        upper = min(float(clean_data.max()), float(q3 + 2.5 * iqr))
    else:
        lower = float(clean_data.min())
        upper = float(clean_data.max())

    range_size = upper - lower
    if range_size == 0:
        range_size = abs(lower) * 0.1 if lower != 0 else 1.0

    padding = range_size * padding_pct
    return (lower - padding, upper + padding)


def generate_chart_filename(
    chart_type: str,
    title: Optional[str] = None,
    timestamp: bool = True,
) -> str:
    """Generate a descriptive chart filename slug (no extension).

    Pattern: ``<chart_type>_<slug-of-title>_<YYYYMMDD_HHMMSS>``

    The title is slugified (alphanumerics + spaces -> underscores)
    and truncated to 30 characters. The timestamp can be suppressed
    for stable / dashboard paths via ``timestamp=False``.
    """
    parts = [chart_type]
    if title:
        clean_title = re.sub(r"[^\w\s]", "", title.lower())
        clean_title = re.sub(r"\s+", "_", clean_title)[:30]
        if clean_title:
            parts.append(clean_title)
    if timestamp:
        parts.append(datetime.now().strftime("%Y%m%d_%H%M%S"))
    return "_".join(parts)


def check_for_outliers(
    df: pd.DataFrame,
    column: str,
    threshold_iqr: float = 3.0,
) -> Dict[str, Any]:
    """Detect outliers in a numeric column using the IQR method.

    Used by the charting layer to decide on axis-scaling strategies
    (clip vs. expand) when a series has a few extreme values that would
    otherwise crush the visible range.

    Returns a dict with::

        {
            "has_outliers": bool,
            "lower_bound": float,
            "upper_bound": float,
            "n_outliers_low": int,
            "n_outliers_high": int,
            "outlier_pct": float,
            "suggested_y_min": float,
            "suggested_y_max": float,
        }

    Returns ``{"has_outliers": False, "reason": ...}`` for non-numeric
    columns or insufficient data (<4 points).
    """
    if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        return {"has_outliers": False, "reason": "not_numeric"}

    data = df[column].dropna()
    if len(data) < 4:
        return {"has_outliers": False, "reason": "insufficient_data"}

    q1 = data.quantile(0.25)
    q3 = data.quantile(0.75)
    iqr = q3 - q1
    lower_bound = float(q1 - threshold_iqr * iqr)
    upper_bound = float(q3 + threshold_iqr * iqr)

    outliers_low = data[data < lower_bound]
    outliers_high = data[data > upper_bound]
    has_outliers = len(outliers_low) > 0 or len(outliers_high) > 0

    return {
        "has_outliers": has_outliers,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "n_outliers_low": int(len(outliers_low)),
        "n_outliers_high": int(len(outliers_high)),
        "outlier_pct": (
            (len(outliers_low) + len(outliers_high)) / len(data) * 100
            if len(data) > 0
            else 0.0
        ),
        "suggested_y_min": (
            max(lower_bound, float(data.min())) if has_outliers else float(data.min())
        ),
        "suggested_y_max": (
            min(upper_bound, float(data.max())) if has_outliers else float(data.max())
        ),
    }


def suggest_chart_type(df: pd.DataFrame, mapping: Dict[str, Any]) -> str:
    """Suggest an appropriate chart type based on data characteristics.

    Used by the LLM as a fallback when the user's intent isn't explicit
    enough to pick a chart type. Heuristics:

      - No x: histogram (single-variable distribution).
      - Datetime x + numeric y: ``multi_line``.
      - Numeric x + numeric y: ``scatter``.
      - Categorical x + numeric y: ``bar``.
      - Otherwise: ``scatter`` (safe default).
    """
    x_field = _get_field(mapping, "x")
    y_field = _get_field(mapping, "y")

    if x_field is None:
        return "histogram"

    x_is_temporal = (
        x_field in df.columns
        and pd.api.types.is_datetime64_any_dtype(df[x_field])
    )
    x_is_numeric = (
        x_field in df.columns
        and not x_is_temporal
        and pd.api.types.is_numeric_dtype(df[x_field])
    )
    y_is_numeric = (
        y_field is not None
        and y_field in df.columns
        and pd.api.types.is_numeric_dtype(df[y_field])
    )

    if x_is_temporal and y_is_numeric:
        return "multi_line"
    if x_is_numeric and y_is_numeric:
        return "scatter"
    if not x_is_numeric and y_is_numeric:
        return "bar"
    return "scatter"


def validate_data(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    chart_type: str,
) -> None:
    """Deep validation that the data will produce a visible chart.

    This is the critical check that prevents silent empty charts.
    Called before building the Altair spec. Mirrors
    ``_validate_chart_data_integrity`` but is exposed as a public-ish
    name PRISM downstream code depends on.

    Raises:
        ValidationError: If the data would produce an empty chart
            (no valid x/y pairs, color groups with insufficient points,
            datetime conversion failures, infinite y values).
    """
    _validate_chart_data_integrity(df, mapping, chart_type)


# ===========================================================================
# MODULE: RESULT TYPES
# ===========================================================================

@dataclass
class ChartResult:
    """Output of ``make_chart()``.

    Always returned (even on failure) so the caller can inspect ``success``,
    ``error_message``, and ``warnings`` without having to wrap calls in
    try/except. Access via dot notation only -- this is a dataclass, not
    a dict.
    """

    png_path: Optional[str] = None
    vegalite_json: Dict[str, Any] = field(default_factory=dict)
    chart_type: str = ""
    skin: str = ""
    success: bool = True
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    audit_trail: List[str] = field(default_factory=list)
    interactive: bool = True
    download_url: Optional[str] = None
    editor_html_path: Optional[str] = None
    editor_download_url: Optional[str] = None
    editor_chart_id: Optional[str] = None

    def __repr__(self) -> str:
        parts = [f"ChartResult(success={self.success}"]
        if self.png_path:
            parts.append(f"png_path={self.png_path}")
        if self.download_url:
            parts.append(f"download_url={self.download_url}")
        if self.error_message:
            parts.append(f"error={self.error_message}")
        if self.warnings:
            parts.append(f"warnings={self.warnings}")
        if self.audit_trail:
            parts.append(f"audit_trail={self.audit_trail}")
        parts.append(f"chart_type={self.chart_type}")
        return ", ".join(parts) + ")"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "png_path": self.png_path,
            "download_url": self.download_url,
            "chart_type": self.chart_type,
            "skin": self.skin,
            "success": self.success,
            "error_message": self.error_message,
            "warnings": self.warnings,
            "audit_trail": self.audit_trail,
            "interactive": self.interactive,
            "editor_html_path": self.editor_html_path,
            "editor_download_url": self.editor_download_url,
            "editor_chart_id": self.editor_chart_id,
        }


@dataclass
class DataProfile:
    """Structured summary of a DataFrame's schema, returned by ``profile_df``."""

    columns: List[str]
    dtypes: Dict[str, str]
    shape: Tuple[int, int]
    temporal_columns: List[str]
    numeric_columns: List[str]
    categorical_columns: List[str]
    cardinality: Dict[str, int]
    missing_pct: Dict[str, float]
    date_range: Optional[Dict[str, Dict[str, str]]] = None
    numeric_stats: Optional[Dict[str, Dict[str, float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "columns": self.columns,
            "dtypes": self.dtypes,
            "shape": list(self.shape),
            "temporal_columns": self.temporal_columns,
            "numeric_columns": self.numeric_columns,
            "categorical_columns": self.categorical_columns,
            "cardinality": self.cardinality,
            "missing_pct": self.missing_pct,
            "date_range": self.date_range,
            "numeric_stats": self.numeric_stats,
        }


def profile_df(df: pd.DataFrame) -> DataProfile:
    """Analyze a DataFrame to help with chart planning.

    Returns column types, cardinality, date coverage, missingness, and
    basic numeric stats. The LLM uses this to choose chart type and
    column mappings before calling ``make_chart()``.
    """
    columns = list(df.columns)
    dtypes = {col: str(df[col].dtype) for col in columns}

    temporal_columns: List[str] = []
    numeric_columns: List[str] = []
    categorical_columns: List[str] = []
    for col in columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            temporal_columns.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            numeric_columns.append(col)
        else:
            categorical_columns.append(col)

    cardinality = {col: int(df[col].nunique()) for col in columns}
    missing_pct = {col: round(float(df[col].isna().mean()) * 100, 2) for col in columns}

    date_range: Optional[Dict[str, Dict[str, str]]] = None
    if temporal_columns:
        date_range = {}
        for col in temporal_columns:
            valid = df[col].dropna()
            if len(valid) > 0:
                date_range[col] = {"min": str(valid.min()), "max": str(valid.max())}

    numeric_stats: Dict[str, Dict[str, float]] = {}
    for col in numeric_columns:
        stats = df[col].describe()
        numeric_stats[col] = {
            "mean": round(float(stats["mean"]), 4),
            "std": round(float(stats["std"]), 4),
            "min": round(float(stats["min"]), 4),
            "max": round(float(stats["max"]), 4),
            "median": round(float(df[col].median()), 4),
        }

    return DataProfile(
        columns=columns,
        dtypes=dtypes,
        shape=df.shape,
        temporal_columns=temporal_columns,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        cardinality=cardinality,
        missing_pct=missing_pct,
        date_range=date_range,
        numeric_stats=numeric_stats or None,
    )


# ===========================================================================
# MODULE: PNG RENDERING
# ===========================================================================

# Distinct-colour ceiling for the indexed-palette step in
# ``_compress_png``. At or below this count the palette holds every colour
# exactly (lossless); above it the image is quantized to this many colours
# (an imperceptible loss on flat vector art).
_PNG_PALETTE_MAX_COLORS = 256


def _compress_png(png_bytes: bytes) -> bytes:
    """Shrink a rendered chart/table PNG without perceptible quality loss.

    ``vl_convert`` (and PIL's default ``save``) emit 32-bit RGBA truecolor
    with weak compression. Charts and tables are flat vector art -- almost
    always well under 256 distinct colours even after anti-aliasing -- so
    storing them as truecolor is hugely wasteful (a 10-megapixel grid that
    uses ~90 colours can weigh several MB). This:

      1. drops the alpha channel when the image is fully opaque (GS-skin
         charts on a solid background always are),
      2. converts to an indexed palette holding the image's colours --
         lossless when the image has <= ``_PNG_PALETTE_MAX_COLORS`` distinct
         colours, otherwise an adaptive quantization to that many colours,
      3. re-encodes with ``optimize=True`` (maximum zlib effort).

    Typical reduction is 5-13x. The smaller of the optimized and original
    bytes is returned so a pathological tiny input can never inflate.
    """
    im = Image.open(io.BytesIO(png_bytes))
    im.load()

    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        opaque = rgba.getchannel("A").getextrema()[0] == 255
        base = rgba.convert("RGB") if opaque else rgba
    else:
        base = im.convert("RGB")

    distinct = base.getcolors(maxcolors=_PNG_PALETTE_MAX_COLORS)
    n_colors = len(distinct) if distinct is not None else _PNG_PALETTE_MAX_COLORS
    # MAXCOVERAGE/MEDIANCUT cannot quantize an alpha channel; FASTOCTREE can.
    method = Image.FASTOCTREE if base.mode == "RGBA" else Image.MAXCOVERAGE
    palette = base.quantize(colors=max(n_colors, 2), method=method, dither=Image.NONE)

    buf = io.BytesIO()
    palette.save(buf, format="PNG", optimize=True)
    out = buf.getvalue()
    return out if len(out) < len(png_bytes) else png_bytes


def _render_chart_to_png(
    chart_or_spec: Any,
    scale: float = 2.0,
) -> bytes:
    """Render an Altair chart or Vega-Lite spec dict to PNG bytes.

    Tries ``vl-convert-python`` first (no Selenium dependency). When the
    package isn't installed, falls back to ``altair_saver``-style
    ``chart.save()`` via a temporary file.
    """
    try:
        import vl_convert as vlc  # type: ignore[import-not-found]

        try:
            vlc.register_font_directory("/usr/share/fonts/liberation/")
        except Exception:  # noqa: BLE001 - non-fatal: macOS / dev machines
            pass

        if isinstance(chart_or_spec, alt.Chart) or isinstance(
            chart_or_spec, (alt.LayerChart, alt.HConcatChart, alt.VConcatChart)
        ):
            spec = chart_or_spec.to_dict()
        elif isinstance(chart_or_spec, dict):
            spec = chart_or_spec
        else:
            spec = chart_or_spec.to_dict()  # last-resort duck typing

        return _compress_png(vlc.vegalite_to_png(vl_spec=spec, scale=scale))

    except ImportError:
        # vl-convert not installed -- fall back to altair's own save().
        if not hasattr(chart_or_spec, "save"):
            raise
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            chart_or_spec.save(tmp_path, scale_factor=scale)
            with open(tmp_path, "rb") as f:
                return _compress_png(f.read())
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ===========================================================================
# MODULE: make_chart() -- the public entry point
# ===========================================================================

# Chart-type -> _build_<type> dispatch table. Keeps ``make_chart`` linear
# instead of a giant if/elif ladder. ``timeseries`` and ``multi_line``
# share the multi_line builder; ``multi_line`` does its own dispatch
# between single-axis, dual-axis, and profile (ordinal x) modes.
_BUILDER_DISPATCH: Dict[str, Any] = {}  # populated below after defs.


def _generate_filename(
    title: Optional[str],
    chart_type: str,
    filename_prefix: Optional[str],
    filename_suffix: Optional[str],
) -> str:
    """Produce a slug-style base filename (no extension) for the chart.

    Pattern: ``YYYYMMDD_HHMMSS_<prefix>_<title>_<suffix>_<chart_type>``
    Empty parts are dropped. Title is slugified (alphanumerics + hyphens).
    """
    parts: List[str] = [datetime.now().strftime("%Y%m%d_%H%M%S")]
    if filename_prefix:
        parts.append(re.sub(r"[^A-Za-z0-9_-]+", "_", filename_prefix).strip("_"))
    if title:
        slug = re.sub(r"[^A-Za-z0-9_-]+", "_", title.lower()).strip("_")
        if slug:
            parts.append(slug[:60])
    if filename_suffix:
        parts.append(re.sub(r"[^A-Za-z0-9_-]+", "_", filename_suffix).strip("_"))
    parts.append(chart_type)
    return "_".join(p for p in parts if p)


def _make_chart(
    df: pd.DataFrame,
    chart_type: ChartType,
    mapping: Dict[str, Any],
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    skin: str = "gs_clean",
    intent: IntentType = "explore",
    dimensions: Optional[DimensionPreset] = None,
    annotations: Optional[List[Annotation]] = None,
    output_dir: str = "",
    filename_prefix: Optional[str] = None,
    filename_suffix: Optional[str] = None,
    session_path: Optional[str] = None,
    s3_manager: Optional[Any] = None,
    save_as: Optional[str] = None,
    interactive: bool = True,
    auto_beautify: bool = True,
    layers: Optional[List[Dict[str, Any]]] = None,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    x_title: Optional[str] = None,
    y_title: Optional[str] = None,
    y_title_right: Optional[str] = None,
    user_id: Optional[str] = None,
    caption: Union[str, Dict[str, Any], None] = None,
    side_left: Union[str, Dict[str, Any], None] = None,
    side_right: Union[str, Dict[str, Any], None] = None,
    facet_cols: Optional[int] = None,
    share_x: bool = False,
    share_y: bool = False,
    share_color: bool = False,
    same_scale: bool = False,
    edge_only_ticks: bool = False,
    edge_only_axis_titles: bool = False,
    _auto_recover_depth: int = 0,
) -> ChartResult:
    """Create a single chart from a DataFrame.

    This is the only chart-creation entry point the LLM should call.
    All styling is controlled by ``skin`` (developer-controlled). Canvas
    size is engine-decided per ``chart_type`` (see ``_AUTO_DIMENSIONS``);
    PRISM never picks a dimension preset. Annotations are passed in
    structured form via ``annotations=[VLine(...), HLine(...), ...]``.

    Args:
        df: Plot-ready DataFrame.
        chart_type: One of the supported chart types
            (``multi_line``, ``scatter``, ``bar``, ...).
        mapping: Column mappings (``x``, ``y``, ``color``, ...).
        title: Chart title (required for production charts).
        subtitle: Chart subtitle (never use for source attribution).
        skin: Visual style. Today only ``gs_clean`` is published.
        intent: ``explore`` (default), ``publish``, or ``monitor``.
        annotations: Optional list of structured annotations.
        output_dir: Local-mode output directory (PRISM uses ``session_path``).
        filename_prefix / filename_suffix: Components of the output
            filename slug.
        session_path: PRISM S3 session folder path.
        s3_manager: PRISM S3 bucket manager (``put`` / ``get`` / ``delete``).
            Falls back to a local-FS-backed manager for standalone runs.
        save_as: Fixed S3 path (relative to ``session_path``); overwrites
            on refresh, no timestamp prefix. Use for dashboard charts.
        interactive: Reserved for future interactive HTML companion.
        auto_beautify: When True (default), apply axis-config beautification
            (date format, label angle, y-domain, log scale recommendation).
        layers: Optional list of extra overlay layers (regression, rule,
            point) layered on top of the base chart.
        x_label / y_label: Convenience aliases for ``mapping['x_title']`` /
            ``mapping['y_title']``.
        x_title / y_title / y_title_right: Canonical axis-title kwargs at
            top-level. Equivalent to setting ``mapping['x_title']`` /
            ``mapping['y_title']`` / ``mapping['y_title_right']``;
            mapping[...] wins when both are set.
        user_id: Optional Kerberos ID resolved from the runtime context.
        caption: Below-chart caption text (str) or style-override dict
            (``{"text": ..., "italic": True, "font_size": 10, ...}``).
            Auto-wraps to chart width.
        side_left / side_right: Side narrative panels flanking the chart
            (str or dict). Sit OUTSIDE the plot region and stretch to
            chart height. Useful for paragraphs of running commentary
            on a single chart or as part of a composite pack.
        facet_cols: When ``mapping['facet']`` is set, the number of
            columns in the panel grid. Rows derived as
            ``ceil(n_panels / facet_cols)``. Default is near-square.
        share_x / share_y: When ``mapping['facet']`` is set, opt INTO
            shared x / y axis ranges across panels (default
            independent, matching ``make_*pack_*``).
        share_color: When ``mapping['facet']`` is set, opt INTO a
            single shared color domain + a single composite-level
            legend (default per-panel legends).
        same_scale: Smart "force same scale" toggle. When True, the
            engine routes to the right share_* combination per
            chart_type: time-series and bar charts share y;
            scatter / scatter_multi share both x AND y;
            histograms share x. Equivalent to setting share_x /
            share_y by hand for each chart_type but cheaper.
        edge_only_ticks: When ``mapping['facet']`` is set, suppress
            tick labels on inner panels -- only the bottom row keeps
            x-tick labels and only the leftmost column keeps y-tick
            labels. Tick MARKS still render so panel boundaries stay
            aligned across the grid. Default False.
        edge_only_axis_titles: Same as ``edge_only_ticks`` but for
            axis titles. Default False.

    Returns:
        ``ChartResult`` (always returned, even on failure -- check
        ``result.success`` and ``result.error_message``). When
        ``mapping['facet']`` is set, the result represents the whole
        composite grid -- ``chart_type`` carries a ``_facet`` suffix
        and ``vegalite_json`` is the composite Vega-Lite spec.

        ``warnings`` carries fail-soft annotations the caller may want
        to surface (data-quality issues, dropped annotations,
        validation softeners). ``audit_trail`` carries informational
        engine decisions where the chart is fine but the engine made
        a routing call (auto-recovered to dual-axis, auto-downsampled,
        alias resolution). PRISM should NOT surface ``audit_trail``
        entries as failures.
    """
    warnings: List[str] = []
    audit_trail: List[str] = []

    # ---- Argument normalization ----------------------------------------
    if chart_type not in (
        "scatter", "scatter_multi", "bar", "bar_horizontal", "bullet",
        "waterfall", "heatmap", "histogram", "boxplot", "area", "donut",
        "multi_line", "timeseries",
    ):
        return ChartResult(
            chart_type=chart_type,
            skin=skin,
            success=False,
            error_message=(
                f"Unknown chart_type {chart_type!r}. "
                f"Valid options: multi_line, scatter, scatter_multi, bar, "
                f"bar_horizontal, bullet, waterfall, heatmap, histogram, "
                f"boxplot, area, donut."
            ),
        )

    if skin not in AVAILABLE_SKINS:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=(
                f"Unknown skin {skin!r}. Available: {list(AVAILABLE_SKINS.keys())}"
            ),
        )

    mapping = dict(mapping)
    # Top-level axis-title kwargs route into mapping. Both the
    # ``x_label``/``y_label`` aliases (legacy) and the canonical
    # ``x_title``/``y_title``/``y_title_right`` names are accepted at
    # the call site for ergonomics; mapping[...] wins when both are
    # set so the more-specific call site (mapping) overrides the
    # convenience kwarg.
    for kwarg_val, mapping_key in (
        (x_label, "x_title"),
        (y_label, "y_title"),
        (x_title, "x_title"),
        (y_title, "y_title"),
        (y_title_right, "y_title_right"),
    ):
        if kwarg_val is not None and mapping_key not in mapping:
            mapping[mapping_key] = kwarg_val

    if s3_manager is None:
        raise ValueError(
            "make_chart() requires an s3_manager. PRISM injects one via the "
            "code sandbox; for local dev, instantiate "
            "ai_development.core.s3_bucket_manager.S3BucketManager and pass it "
            "explicitly."
        )
    use_s3 = bool(session_path) or save_as is not None

    logger.info(
        "[make_chart] START: chart_type=%s, df.shape=%s, title=%r",
        chart_type, df.shape, title,
    )
    logger.debug("[make_chart] mapping: %s", mapping)
    logger.debug("[make_chart] columns: %s", list(df.columns))

    # ---- Facet (small-multiples) early branch ---------------------------
    # When the caller sets ``mapping['facet']``, dispatch entirely into
    # ``_render_facet_grid``. The facet flow handles its own auto-melt,
    # validation, panel build, layout, PNG render, and S3 upload, then
    # returns a ``ChartResult`` with ``chart_type=<base>_facet``.
    if "facet" in mapping:
        # Histogram facets always share x so bin ranges are comparable
        # across panels (return distributions, etc.). Independent
        # per-panel x scales are never meaningful for facet histograms.
        if chart_type == "histogram":
            share_x = True
        # Smart-route ``same_scale=True`` per chart_type.
        if same_scale:
            if chart_type in {"scatter", "scatter_multi"}:
                share_x = True
                share_y = True
            elif chart_type in {"histogram"}:
                share_x = True
            else:  # multi_line / timeseries / area / bar / bar_horizontal
                share_y = True
        return _render_facet_grid(
            df=df, chart_type=chart_type, mapping=mapping,
            title=title, subtitle=subtitle,
            skin=skin, intent=intent,
            dimensions=dimensions,
            annotations=annotations,
            output_dir=output_dir,
            filename_prefix=filename_prefix,
            filename_suffix=filename_suffix,
            session_path=session_path,
            s3_manager=s3_manager,
            save_as=save_as,
            interactive=interactive,
            auto_beautify=auto_beautify,
            layers=layers,
            user_id=user_id,
            facet_cols=facet_cols,
            share_x=share_x, share_y=share_y, share_color=share_color,
            edge_only_ticks=edge_only_ticks,
            edge_only_axis_titles=edge_only_axis_titles,
        )

    # ---- Reject page_grid for non-facet calls ---------------------------
    if dimensions == "page_grid":
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=(
                "dimension_preset='page_grid' is only valid in facet mode. "
                "Either set mapping['facet']='<col>' to use the facet grid, "
                "or pick a different preset (wide / square / compact / ...)."
            ),
        )

    # ---- Validate color customisation kwargs ----------------------------
    # Surfaces typo / off-list palette names at the boundary so PRISM
    # sees an actionable error instead of a silently-rendered default.
    # Passing ``df`` lets the validator range-check integer-slot
    # ``color_map`` keys against the actual category count.
    try:
        _validate_color_kwargs(mapping, chart_type, df)
        _validate_opacity_kwargs(mapping, chart_type, df)
    except ValidationError as exc:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=str(exc), warnings=warnings,
            audit_trail=audit_trail,
        )

    # ---- Auto-melt for multi_line / area --------------------------------
    if chart_type in {"multi_line", "area"}:
        try:
            df, mapping = _auto_melt_for_multiline(df, mapping)
        except ValidationError as exc:
            return ChartResult(
                chart_type=chart_type, skin=skin, success=False,
                error_message=f"Auto-melt failed: {exc}",
            )

    # ---- Auto-coerce string x-axis to datetime (multi_line / timeseries)
    # PRISM may pass ISO date strings without first calling pd.to_datetime.
    # Without this, the dispatcher routes string-dated series to
    # _build_profile_line (the ordinal-x builder) which produces verbose
    # "2023-01-01" tick labels rotated -45 degrees instead of the smart
    # date-aware format ("Jan 23", "%Y") and horizontal labels.
    df = _normalize_intraday_x_column(df, mapping, chart_type)
    df = _coerce_string_x_to_datetime(df, mapping, chart_type)

    # ---- Heatmap matrix auto-melt ---------------------------------------
    # If both x and y reference non-existent columns and the DataFrame is a
    # numeric matrix (correlation matrix, distance matrix, etc.), melt the
    # matrix into long form. Detects two patterns:
    #   - Both x and y are non-existent column names -> generic matrix.
    #   - y is missing AND looks like an "index" alias.
    #   - x is missing AND looks like a "columns" alias.
    if chart_type == "heatmap":
        x_ref = _get_field(mapping, "x")
        y_ref = _get_field(mapping, "y")
        needs_melt = False
        if x_ref and y_ref:
            x_missing = x_ref not in df.columns
            y_missing = y_ref not in df.columns
            if x_missing and y_missing:
                needs_melt = True
            elif y_missing and y_ref.lower() in {"index", "row", "rows", "y"}:
                needs_melt = True
            elif x_missing and x_ref.lower() in {"columns", "column", "cols", "col", "x"}:
                needs_melt = True

        if needs_melt:
            try:
                # Capture the original index/column ordering BEFORE melting so
                # the heatmap can render rows and cols in their input order
                # (otherwise the heatmap's nominal axes default to alphabetical
                # sort and a correlation matrix becomes asymmetric).
                row_order = [str(v) for v in df.index]
                col_order = [str(c) for c in df.columns]

                melted = df.reset_index()
                idx_col = melted.columns[0]
                value_cols = [c for c in melted.columns if c != idx_col]
                melted = melted.melt(
                    id_vars=idx_col,
                    value_vars=value_cols,
                    var_name="_heatmap_x",
                    value_name="_heatmap_value",
                )
                melted = melted.rename(columns={idx_col: "_heatmap_y"})
                df = melted

                new_mapping = dict(mapping)
                new_mapping["x"] = "_heatmap_x"
                new_mapping["y"] = "_heatmap_y"
                # After auto-melt the value lives in _heatmap_value, regardless
                # of what the user originally passed (since matrix mode
                # implied the value field didn't exist as a column).
                new_mapping["value"] = "_heatmap_value"
                new_mapping.pop("z", None)
                if "x_sort" not in new_mapping:
                    new_mapping["x_sort"] = col_order
                if "y_sort" not in new_mapping:
                    new_mapping["y_sort"] = row_order
                # Preserve original labels as axis titles when sensible.
                # Treat missing OR empty-string user titles as "default
                # me" so callers don't accidentally stamp the
                # ``_heatmap_x`` / ``_heatmap_y`` placeholder names onto
                # the axes.
                if not new_mapping.get("x_title") and x_ref and x_ref.lower() not in {
                    "columns", "column", "cols", "col", "x",
                }:
                    new_mapping["x_title"] = x_ref
                if not new_mapping.get("y_title") and y_ref and y_ref.lower() not in {
                    "index", "row", "rows", "y",
                }:
                    new_mapping["y_title"] = y_ref
                # If x or y was a placeholder ("columns"/"index"), force
                # an empty title rather than the placeholder name. This
                # matches the matrix-style heatmap convention where
                # axis labels are redundant with the cell labels.
                if x_ref and x_ref.lower() in {
                    "columns", "column", "cols", "col", "x",
                }:
                    new_mapping["x_title"] = " "
                if y_ref and y_ref.lower() in {
                    "index", "row", "rows", "y",
                }:
                    new_mapping["y_title"] = " "
                mapping = new_mapping
                logger.info(
                    "[make_chart] auto-melted matrix DataFrame for heatmap: %s",
                    df.shape,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[make_chart] heatmap auto-melt failed: %s. "
                    "Proceeding with original data.",
                    exc,
                )

    # ---- Sanitize column names (Vega-Lite safety) -----------------------
    df, mapping = _sanitize_column_names(df, mapping)

    # ---- Auto-downsample large time series ------------------------------
    if chart_type in {"timeseries", "multi_line", "area"}:
        x_field = _get_field(mapping, "x")
        if x_field and x_field in df.columns:
            original_len = len(df)
            df, freq = _auto_downsample_timeseries(df, x_field)
            if freq:
                audit_trail.append(
                    f"Data auto-downsampled from {original_len} to {len(df)} rows "
                    f"(frequency: {freq}) to avoid Altair row limit."
                )

    # ---- Validate plot-ready DataFrame ----------------------------------
    try:
        warnings.extend(validate_plot_ready_df(df, chart_type, mapping))
        warnings.extend(_validate_encoding_data(df, mapping, chart_type))
        _validate_chart_data_integrity(df, mapping, chart_type)
    except ValidationError as exc:
        # ---- Y-axis 2-series auto-recovery (Principle #7 absorption) ----
        # When the y-scale flatness gate or level-disparity gate rejects
        # a 2-series multi_line / timeseries chart, the canonical fix is
        # routing the smaller-magnitude series to a dual right axis.
        # Inject ``mapping['dual_axis_series']=[<smallest>]`` +
        # ``y_title_right=<smallest>`` and recurse once with
        # ``_auto_recover_depth=1`` to prevent infinite loops.
        # 3+ series cases stay rejected -- the editorial choice between
        # 2-pack / dual / z-score / facet belongs to PRISM, not the
        # engine.
        recovered = _maybe_auto_recover_y_scale(
            exc, df, chart_type, mapping, depth=_auto_recover_depth,
        )
        if recovered is not None:
            new_mapping, recovery_msg = recovered
            audit_trail.append(recovery_msg)
            recovered_result = _make_chart(
                df=df, chart_type=chart_type, mapping=new_mapping,
                title=title, subtitle=subtitle, skin=skin, intent=intent,
                dimensions=dimensions, annotations=annotations,
                output_dir=output_dir,
                filename_prefix=filename_prefix,
                filename_suffix=filename_suffix,
                session_path=session_path,
                s3_manager=s3_manager, save_as=save_as,
                interactive=interactive, auto_beautify=auto_beautify,
                layers=layers, x_label=x_label, y_label=y_label,
                x_title=x_title, y_title=y_title,
                y_title_right=y_title_right,
                user_id=user_id, caption=caption,
                side_left=side_left, side_right=side_right,
                facet_cols=facet_cols,
                share_x=share_x, share_y=share_y, share_color=share_color,
                same_scale=same_scale,
                edge_only_ticks=edge_only_ticks,
                edge_only_axis_titles=edge_only_axis_titles,
                _auto_recover_depth=_auto_recover_depth + 1,
            )
            # Merge accumulated warnings + audit_trail (recovery
            # message + any soft warnings raised before the rejection)
            # ahead of what the recursive call surfaced.
            recovered_result.warnings = (
                warnings + list(recovered_result.warnings or [])
            )
            recovered_result.audit_trail = (
                audit_trail + list(recovered_result.audit_trail or [])
            )
            return recovered_result
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=str(exc), warnings=warnings,
            audit_trail=audit_trail,
        )

    # ---- Skin / dimensions ----------------------------------------------
    # Canvas size is engine-decided per chart_type. PRISM does not pass
    # dimensions; the kwarg remains on the signature for staging-side
    # power-user use (demos, fixture rendering) and is private-by-
    # convention (not taught in the skill). When not passed, route
    # through ``_auto_dimensions`` -- the same table the v2 ``Chart``
    # class consults.
    skin_config = get_skin(skin, intent)
    if dimensions is None:
        dimensions = _auto_dimensions(chart_type)
    if dimensions not in DIMENSION_PRESETS:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=(
                f"Unknown dimension preset {dimensions!r}. "
                f"Available: {list(DIMENSION_PRESETS.keys())}"
            ),
            warnings=warnings,
            audit_trail=audit_trail,
        )
    width, height = DIMENSION_PRESETS[dimensions]

    # ---- Pre-dispatch annotation absorption (Phase 1 of collision sweep)
    # ---- See dev/scratch/_collision_audit_2026-05-10_1955/inventory.md
    #
    # Three engine-side absorptions happen here BEFORE dispatch so the
    # bar builders + Callout layer see the cleaned state:
    #
    # (a) Class 9 -- thread chart_width into mapping for Callout dx clamp.
    #     Without this Callout.to_layer falls back to the 700px wide
    #     default; the threaded value lets the clamp respect the active
    #     dimension preset.
    #
    # (b) Class 11 -- grouped bar (color + stack=False) silently drops
    #     annotations because Vega-Lite column faceting doesn't support
    #     layered annotations. Surface a warning so the LLM knows; drop
    #     the annotations explicitly so render_annotations doesn't try.
    #
    # (c) Classes 1+4 -- compute bar value label suppression. Bar charts
    #     auto-emit numeric value labels above each bar. When a Callout /
    #     PointLabel / Arrow is anchored to the same bar (class 1), or
    #     when a labelled Band's y-range overlaps a stacked-bar total
    #     (class 4), the engine should suppress the redundant bar value
    #     label. Stash the suppression sets in mapping for the bar
    #     builders to consume.
    mapping["_chart_width_px"] = width

    if (
        chart_type in {"bar", "bar_horizontal"}
        and mapping.get("color")
        and mapping.get("stack") is False
        and annotations
    ):
        dropped_names = [
            type(a).__name__ for a in annotations if a is not None
        ]
        logger.warning(
            "[make_chart] Annotations not supported on grouped bar "
            "(stack=False with a color column); dropping %d annotation(s) "
            "(%s). Switch to stack=True or remove the color column to "
            "render annotations.",
            len(dropped_names), ", ".join(dropped_names),
        )
        warnings.append(
            f"Annotations dropped on grouped bar ({len(dropped_names)} "
            f"annotation(s): {', '.join(dropped_names)}). Vega-Lite column "
            f"faceting doesn't support layered annotations. Switch to "
            f"stack=True (stacked bars) or render the chart without color "
            f"to see the annotations."
        )
        annotations = []

    if chart_type in {"bar", "bar_horizontal"}:
        x_set_suppress, y_range_suppress = _compute_bar_value_suppression(
            df, mapping, annotations,
        )
        if x_set_suppress:
            mapping["_suppress_bar_value_at_x"] = x_set_suppress
            logger.info(
                "[make_chart] Suppressing bar value labels at %d x-position(s) "
                "due to anchored Callout / PointLabel / Arrow annotations.",
                len(x_set_suppress),
            )
        if y_range_suppress is not None:
            mapping["_suppress_bar_total_in_y_range"] = y_range_suppress
            logger.info(
                "[make_chart] Suppressing stacked-bar TOTAL value labels "
                "in y-range [%.3f, %.3f] (overlapped by labelled Band).",
                y_range_suppress[0], y_range_suppress[1],
            )

    # ---- Class 3 absorption: route HLine + horizontal-Band labels to the
    # right edge on bar charts (audit
    # `dev/scratch/_collision_audit_2026-05-10_1955/inventory.md` class 3,
    # subsuming class 2).
    #
    # Bar charts auto-emit numeric value labels above each bar; HLine and
    # horizontal Band labels default to roughly the plot center
    # horizontally. The two label streams crash together in the same
    # narrow y-band, creating a "label soup" region right where the data
    # is densest (e.g. 22/A1 BLOCKER, 22/I1 + 22/L1 MAJOR, 24/K1 MAJOR
    # repros from the audit). Route HLine + horizontal-Band labels to
    # the right edge of the bar zone so they form a clean per-rule
    # legend strip OUTSIDE the bar value-label region.
    #
    # Anchor x = the rightmost x category in df data order (NOT
    # alphabetical -- the bar builder preserves data order for the
    # axis). The HLine + Band downstream code reads
    # ``mapping['_anno_label_anchor_right_x']`` from to_layer and
    # switches to ``align='right'`` with ``dx=-5`` against that anchor.
    # Grouped bar (color + stack=False) is excluded since annotations
    # already get dropped there per class 11.
    #
    # Secondary suppression: routing labels to the rightmost bar's x
    # creates a new collision risk -- the rightmost bar's own value
    # label sits at the top of THAT bar, which is the same anchor x
    # as the routed labels. When the rightmost bar's y value falls
    # within 2%% of any routed HLine y (or inside any routed Band y
    # range), the routed label overlaps the bar value label
    # pixel-for-pixel. Suppress the bar value label at the rightmost
    # x so the routed legend strip reads cleanly.
    if (
        chart_type == "bar"
        and annotations
        and not (mapping.get("color") and mapping.get("stack") is False)
        and isinstance(mapping.get("x"), str)
        and mapping["x"] in df.columns
    ):
        x_field = mapping["x"]
        has_label_bearing_rule = any(
            (isinstance(a, HLine) and a.label)
            or (
                isinstance(a, Band)
                and a.y1 is not None and a.y2 is not None
                and a.label
            )
            for a in annotations
        )
        if has_label_bearing_rule and len(df) > 0:
            try:
                last_x = df[x_field].iloc[-1]
                mapping["_anno_label_anchor_right_x"] = last_x
                logger.info(
                    "[make_chart] Routing HLine + horizontal-Band labels "
                    "to right edge (class 3 absorption); anchor x=%r",
                    last_x,
                )

                # Secondary: check if the rightmost bar's y value
                # collides with any routed HLine y or labelled Band
                # y-range. If so, add last_x to the value-label
                # suppression set so the bar value label drops out and
                # the routed legend label survives alone.
                y_field = mapping.get("y") if isinstance(mapping.get("y"), str) else None
                if y_field and y_field in df.columns:
                    last_row = df[df[x_field] == last_x]
                    if len(last_row) > 0:
                        last_y_val = float(last_row[y_field].iloc[-1])
                        y_min_data = float(df[y_field].min())
                        y_max_data = float(df[y_field].max())
                        y_span = max(y_max_data - y_min_data, 1e-9)
                        tol = y_span * 0.02
                        collides = False
                        for ann in annotations:
                            if isinstance(ann, HLine) and ann.label:
                                if abs(float(ann.y) - last_y_val) <= tol:
                                    collides = True
                                    break
                            elif (
                                isinstance(ann, Band)
                                and ann.y1 is not None
                                and ann.y2 is not None
                                and ann.label
                            ):
                                y_lo = float(min(ann.y1, ann.y2))
                                y_hi = float(max(ann.y1, ann.y2))
                                if y_lo <= last_y_val <= y_hi:
                                    collides = True
                                    break
                        if collides:
                            existing = mapping.get("_suppress_bar_value_at_x") or set()
                            if not isinstance(existing, set):
                                existing = set(existing)
                            existing.add(last_x)
                            mapping["_suppress_bar_value_at_x"] = existing
                            logger.info(
                                "[make_chart] Class 3 secondary: also "
                                "suppressing rightmost bar value label "
                                "at x=%r (y=%.3f collides with routed "
                                "HLine/Band).",
                                last_x, last_y_val,
                            )
            except Exception:  # noqa: BLE001
                pass

    # ---- Colour-legend label validation (when legend will render) ------
    _legend_color_field = _get_field(mapping, "color")
    if (
        _legend_color_field
        and _legend_color_field in df.columns
        and _color_legend_will_render(
            chart_type, mapping, annotations, df=df,
        )
    ):
        try:
            _validate_legend_labels(
                df, _legend_color_field, width, mapping, composite_cell=False,
            )
        except ValidationError as exc:
            return ChartResult(
                chart_type=chart_type, skin=skin, success=False,
                error_message=str(exc), warnings=warnings,
                audit_trail=audit_trail,
            )

    # ---- Build the chart ------------------------------------------------
    try:
        chart = _dispatch_builder(
            chart_type, df, mapping, skin_config, width, height, layers,
            composite_cell=False,
        )
    except ValidationError as exc:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=str(exc), warnings=warnings,
            audit_trail=audit_trail,
        )
    except Exception as exc:  # noqa: BLE001
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=f"Chart build failed: {type(exc).__name__}: {exc}",
            warnings=warnings,
            audit_trail=audit_trail,
        )

    # ---- LastValueLabel on dual-axis: prohibited, drop with warning ----
    # LVL paints past the last data point and collides with the right-hand
    # y-axis scale. Dual-axis charts use the colour legend for series ID.
    annotations, lvl_stripped = _strip_dual_axis_lvl_annotations(
        annotations, mapping,
    )
    if lvl_stripped:
        logger.warning(
            "[make_chart] Suppressed %d LastValueLabel annotation(s) on a "
            "dual-axis chart -- LVL collides with the right y-axis. The "
            "colour legend renders instead.",
            lvl_stripped,
        )
        warnings.append(
            f"LastValueLabel suppressed on dual-axis chart "
            f"({lvl_stripped} stripped) -- end-of-line labels collide with "
            f"the right y-axis; the colour legend renders instead. For "
            f"end-of-line labels, build single-axis charts and combine "
            f"via ``make_2pack_vertical()``."
        )

    # ---- Auto-default LastValueLabel for multi_line / timeseries -------
    # Multi-line charts default to end-of-line labelling (FT/Bloomberg
    # house style) instead of a colour legend. The legend forces a
    # lookup-tax between hex swatch and series name; LVL paints the
    # series name directly at each line's end, in the line's colour.
    # The downstream legend-suppression branch inside
    # ``render_annotations`` turns the colour legend off automatically
    # once an LVL is present.
    #
    # ``mapping['legend'] = True`` is the internal QC-driven escape
    # hatch (post-render collision fallback); it is NOT part of the
    # PRISM-facing surface and is omitted from ``chart_context.md``.
    # ``_should_auto_inject_lvl`` also skips auto-injection on dual-axis
    # (LVL is stripped there anyway), when the caller has already added
    # their own ``LastValueLabel`` (explicit always wins), and on
    # non-line chart types.
    if _should_auto_inject_lvl(chart_type, mapping, annotations):
        annotations = list(annotations or [])
        annotations.append(LastValueLabel())

    # ---- Silent endpoint-annotation strip (LVL absorption per #7) -------
    # Whenever an LVL is in the annotation list (auto-injected or
    # explicit), any caller-supplied ``Callout`` / ``PointLabel`` /
    # ``PointHighlight`` placed at a series's latest data point is
    # redundant with the LVL's series-name label and produces the
    # right-edge stacking documented in
    # ``projects/altair/dev/fail_gallery.py``. The engine silently drops
    # them -- no ``warnings`` entry, no skill teaching required. PRISM
    # keeps writing the natural "highlight the latest value" pattern;
    # the engine absorbs the visual collision.
    annotations = _strip_endpoint_annotations_redundant_to_lvl(
        df, chart_type, mapping, annotations,
    )

    # ---- PlotText -> outside text panels (route BEFORE layer pass) -----
    # PlotText renders OUTSIDE the plot region only (per the 2026-05-10
    # outside-only rewire). Pull every PlotText out of the annotations
    # list here and convert it into the appropriate text-panel slot
    # (caption / side_left / side_right). Explicit panel kwargs win;
    # PlotTexts that target an occupied slot are rerouted to the next
    # available position (warning surfaced). The downstream
    # ``_apply_text_panels_to_spec`` call (~70 lines below) picks up
    # the resolved panel values without knowing PlotText was the source.
    if annotations:
        (
            annotations,
            caption,
            side_left,
            side_right,
            _plottext_warnings,
        ) = _route_plottext_to_panels(
            annotations,
            explicit_caption=caption,
            explicit_side_left=side_left,
            explicit_side_right=side_right,
        )
        warnings.extend(_plottext_warnings)

    # ---- LastValueLabel series-name validation ----------------------------
    # Validation runs BEFORE ``render_annotations`` so a long-name failure
    # is converted into a ChartResult(success=False) instead of bubbling
    # an exception out of make_chart. Canvas width for LVL text is handled
    # by Vega-Lite autosize at PNG export time -- explicit padding.right
    # was redundant and produced an empty white sidebar (2026-05-31).
    try:
        _validate_lvl_series_names(annotations, df, mapping)
    except ValidationError as exc:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=str(exc), warnings=warnings,
            audit_trail=audit_trail,
        )

    # ---- Annotations (layer first; configure must be applied AFTER ------
    # because altair rejects ``alt.layer(...)`` of charts that already
    # carry a top-level ``config``).
    if annotations:
        try:
            chart = render_annotations(
                chart, annotations, df, mapping, skin_config,
                chart_type=chart_type,
                chart_width=width, chart_height=height,
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Annotation layer failed (non-fatal): {exc}")

    # ---- Title / subtitle / skin config ---------------------------------
    chart_props: Dict[str, Any] = {}
    if title:
        try:
            title_lines = _validate_and_wrap_text(
                title, slot_kind="title", width_px=width,
                slot_label="make_chart() title",
                widening_hint=(
                    "use a wider dimension_preset (e.g. 'wide' or "
                    "'presentation')"
                ),
            )
            subtitle_lines = _validate_and_wrap_text(
                subtitle, slot_kind="subtitle", width_px=width,
                slot_label="make_chart() subtitle",
                widening_hint=(
                    "use a wider dimension_preset (e.g. 'wide' or "
                    "'presentation')"
                ),
            )
        except ValueError as exc:
            return ChartResult(
                chart_type=chart_type, skin=skin, success=False,
                error_message=str(exc), warnings=warnings,
                audit_trail=audit_trail,
            )
        # Always emit TitleParams with explicit anchor='start' so that
        # when the chart is later wrapped in an hconcat (side panels) the
        # title remains start-aligned to the chart's plot region instead
        # of drifting to the centre of its hconcat slot. ``frame='group'``
        # anchors the title to the chart group bounds (axes + plot area)
        # rather than the outer composition bounds. Pre-wrap via
        # ``_validate_and_wrap_text`` (font-size-aware); never ``limit``.
        if subtitle_lines:
            chart_props["title"] = _title_params_from_lines(
                title_lines,
                width_px=width,
                subtitle_lines=subtitle_lines,
                anchor="start",
            )
        else:
            chart_props["title"] = _title_params_from_lines(
                title_lines,
                width_px=width,
                anchor="start",
            )
    if chart_props:
        chart = chart.properties(**chart_props)

    chart = chart.configure(**skin_config.get("config", {}))

    # ---- Axis beautification -------------------------------------------
    spec = chart.to_dict()
    if auto_beautify:
        try:
            # `_build_bar` may have auto-flipped a vertical-bar request
            # into a horizontal one when category labels are too long
            # to render upright. The flip swaps x/y inside the spec but
            # leaves `mapping` / `chart_type` unchanged here -- the
            # downstream `get_axis_beautification` then computes its
            # x-axis config from the original NOMINAL field (which
            # naturally rotates -45 for long labels) and
            # `apply_beautification_to_spec` blindly applies that angle
            # to the NUMERIC value axis that now sits on x. Detect the
            # flip by comparing the rendered spec's x-field against
            # `mapping["x"]` and swap the mapping + chart_type so the
            # beautification matches the actual axes the user sees.
            eff_mapping = mapping
            eff_chart_type = chart_type
            if chart_type == "bar":
                spec_enc = (
                    spec.get("encoding")
                    or (spec.get("layer", [{}])[0].get("encoding") if spec.get("layer") else None)
                )
                if isinstance(spec_enc, dict):
                    spec_x_field = (
                        spec_enc.get("x", {}).get("field")
                        if isinstance(spec_enc.get("x"), dict) else None
                    )
                    if (
                        spec_x_field
                        and spec_x_field != mapping.get("x")
                        and spec_x_field == mapping.get("y")
                    ):
                        eff_mapping = dict(mapping)
                        eff_mapping["x"] = mapping.get("y")
                        eff_mapping["y"] = mapping.get("x")
                        eff_mapping["x_title"] = mapping.get("y_title")
                        eff_mapping["y_title"] = mapping.get("x_title")
                        eff_chart_type = "bar_horizontal"
            axis_configs = get_axis_beautification(
                df, eff_mapping, eff_chart_type, width, height
            )
            if axis_configs:
                spec = apply_beautification_to_spec(spec, axis_configs)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Axis beautification skipped (non-fatal): {exc}")

    # ---- Typography overrides (per dimension preset) -------------------
    # When dimensions is one of {compact, teams, thumbnail}, the skin's
    # default font sizes are too large for the smaller canvas. The
    # typography pass scales them down so labels remain legible without
    # requiring per-skin variants.
    if dimensions and dimensions in TYPOGRAPHY_OVERRIDES:
        try:
            spec = _apply_typography_overrides(spec, dimensions)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Typography overrides skipped (non-fatal): {exc}")

    # ---- Heatmap-specific config (suppress grid artifacts) -------------
    if chart_type == "heatmap":
        try:
            spec = _apply_heatmap_config(spec)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Heatmap config skipped (non-fatal): {exc}")

    # ---- Final pre-PNG spec validation ---------------------------------
    # Catches the silent-empty-chart failure mode where validation passed
    # upstream but data never propagated to the rendered spec. Soft fail
    # here -- the chart may still render (vl-convert is forgiving), but
    # we surface the issue as a warning so downstream consumers see it.
    try:
        _validate_spec_has_data(spec, chart_type, df, mapping)
    except ValidationError as exc:
        logger.warning("[make_chart] spec validation: %s", exc)
        warnings.append(f"Spec validation: {exc}")

    # ---- Text panels (caption / side_left / side_right) ---------------
    # Applied LAST so axis beautification, typography overrides, and
    # heatmap config all operate on the un-wrapped data chart spec.
    if caption is not None or side_left is not None or side_right is not None:
        try:
            spec = _apply_text_panels_to_spec(
                spec,
                chart_width=width, chart_height=height,
                caption=caption, side_left=side_left, side_right=side_right,
                skin_config=skin_config,
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Text-panel wrap failed (non-fatal): {exc}")

    # ---- Filename + PNG output ------------------------------------------
    filename_base = _generate_filename(
        title, chart_type, filename_prefix, filename_suffix
    )
    if save_as:
        # Passthrough: if save_as is already rooted at a canonical S3
        # prefix, honour it exactly. Mirrors _tbl_resolve_path() and
        # matches s3_manager.put() / save_artifact(output_path=...)
        # behavior so PRISM can pass either a leaf filename or a
        # fully-rooted path without producing double-nested paths.
        if save_as.startswith(_PASSTHROUGH_PREFIXES):
            png_path = save_as
        else:
            png_path = (
                f"{session_path}/{save_as}" if session_path else save_as
            )
    else:
        if session_path:
            png_path = f"{session_path}/{filename_base}.png"
        else:
            png_path = (
                os.path.join(output_dir, f"{filename_base}.png")
                if output_dir
                else f"{filename_base}.png"
            )

    png_save_failed = False
    png_error_message = ""
    download_url: Optional[str] = None
    png_bytes: bytes = b""
    try:
        png_bytes = _render_chart_to_png(spec, scale=2.0)
        s3_manager.put(png_bytes, png_path)
    except Exception as exc:  # noqa: BLE001
        png_save_failed = True
        png_error_message = str(exc)
        png_path = None
        warnings.append(f"PNG export failed: {png_error_message}")

    # ---- Presigned download URL ----------------------------------------
    if png_path and not png_save_failed:
        try:
            download_url = generate_presigned_download_url(png_path).presigned_url
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Failed to generate PNG download URL: {exc}")

    return ChartResult(
        png_path=png_path,
        download_url=download_url,
        vegalite_json=spec,
        chart_type=chart_type,
        skin=skin,
        success=not png_save_failed,
        error_message=(
            f"PNG export unavailable: {png_error_message}" if png_save_failed else None
        ),
        warnings=warnings,
        audit_trail=audit_trail,
        interactive=interactive,
    )


def _dispatch_builder(
    chart_type: str,
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    skin_config: Dict[str, Any],
    width: int,
    height: int,
    layers: Optional[List[Dict[str, Any]]],
    *,
    composite_cell: bool = False,
) -> alt.Chart:
    """Route ``chart_type`` to the appropriate ``_build_*`` function.

    ``multi_line`` itself routes between single-axis, dual-axis, and
    profile (ordinal x) modes inside ``_build_multi_line``.
    """
    if chart_type in {"multi_line", "timeseries"}:
        x_field = _get_field(mapping, "x")
        x_type_override = mapping.get("x_type")
        x_is_temporal = (
            x_field
            and x_field in df.columns
            and pd.api.types.is_datetime64_any_dtype(df[x_field])
        )
        if mapping.get("dual_axis_series"):
            return _build_multi_line(df, mapping, skin_config, width, height)
        if x_type_override == "ordinal" or (not x_type_override and not x_is_temporal):
            return _build_profile_line(df, mapping, skin_config, width, height)
        if chart_type == "timeseries":
            return _build_timeseries(df, mapping, skin_config, width, height)
        return _build_multi_line(df, mapping, skin_config, width, height)
    if chart_type == "scatter":
        return _build_scatter(df, mapping, skin_config, width, height, layers=layers)
    if chart_type == "scatter_multi":
        return _build_scatter_multi(
            df, mapping, skin_config, width, height, layers=layers
        )
    if chart_type == "bar":
        return _build_bar(df, mapping, skin_config, width, height)
    if chart_type == "bar_horizontal":
        return _build_bar_horizontal(df, mapping, skin_config, width, height)
    if chart_type == "area":
        return _build_area(df, mapping, skin_config, width, height)
    if chart_type == "heatmap":
        return _build_heatmap(
            df, mapping, skin_config, width, height,
            composite_cell=composite_cell,
        )
    if chart_type == "histogram":
        return _build_histogram(df, mapping, skin_config, width, height)
    if chart_type == "boxplot":
        return _build_boxplot(df, mapping, skin_config, width, height)
    if chart_type == "donut":
        return _build_donut(df, mapping, skin_config, width, height)
    if chart_type == "bullet":
        return _build_bullet(df, mapping, skin_config, width, height)
    if chart_type == "waterfall":
        return _build_waterfall(df, mapping, skin_config, width, height)
    raise ValidationError(f"No builder registered for chart_type {chart_type!r}.")


# ===========================================================================
# MODULE: COMPOSITE LAYOUTS
# ===========================================================================

LayoutType = Literal[
    "2_horizontal",
    "2_vertical",
    "3_triangle",
    "3_inverted",
    "3_horizontal",
    "3_vertical",
    "4_grid",
    "4_horizontal",
    "4_vertical",
    "6_grid",
]


# Per-layout, per-preset sub-chart dimensions. Composites scale individual
# charts down so they share the canvas without overflowing. Values in
# pixels. Layouts not listed fall back to ``4_grid`` defaults.
COMPOSITE_DIMENSIONS: Dict[str, Dict[str, Tuple[int, int]]] = {
    "2_horizontal": {
        "wide": (400, 300),
        "square": (350, 350),
        "compact": (300, 250),
        "teams": (260, 200),
    },
    "2_vertical": {
        "wide": (600, 250),
        "square": (450, 300),
        "compact": (400, 200),
        "teams": (380, 160),
    },
    "3_triangle": {
        "wide": (350, 250),
        "square": (300, 300),
        "compact": (280, 220),
        "teams": (240, 170),
    },
    "3_inverted": {
        "wide": (350, 250),
        "square": (300, 300),
        "compact": (280, 220),
        "teams": (240, 170),
    },
    "3_horizontal": {
        "wide": (240, 300),
        "compact": (220, 250),
        "teams": (200, 200),
    },
    "3_vertical": {
        "wide": (600, 200),
        "compact": (400, 180),
        "teams": (380, 140),
    },
    "4_grid": {
        "wide": (350, 250),
        "square": (300, 300),
        "compact": (280, 220),
        "teams": (240, 170),
    },
    "4_horizontal": {
        "wide": (200, 300),
        "compact": (180, 250),
        "teams": (160, 200),
    },
    "4_vertical": {
        "wide": (600, 180),
        "compact": (400, 160),
        "teams": (380, 130),
    },
    "6_grid": {
        "wide": (300, 220),
        "compact": (260, 200),
        "teams": (220, 160),
    },
}


def _get_expected_chart_count(layout: str) -> int:
    """Number of sub-charts required by a layout name (e.g. ``4_grid`` -> 4)."""
    head = layout.split("_", 1)[0]
    try:
        return int(head)
    except ValueError as exc:
        raise ValueError(f"Unrecognized layout {layout!r}") from exc


def _layout_grid_shape(layout: str, n_charts: int) -> Tuple[int, int]:
    """Return the (cols, rows) pixel grid shape used by a composite layout.

    Used to estimate the composite's outer pixel footprint when wrapping
    it in side / caption text panels. Best-effort: the actual rendered
    composite leaves a few pixels of intra-row spacing not modelled here.
    """
    if layout in ("2_horizontal",):
        return (2, 1)
    if layout in ("2_vertical",):
        return (1, 2)
    if layout in ("3_horizontal",):
        return (3, 1)
    if layout in ("3_vertical",):
        return (1, 3)
    if layout in ("3_triangle", "3_inverted"):
        return (2, 2)
    if layout in ("4_horizontal",):
        return (4, 1)
    if layout in ("4_vertical",):
        return (1, 4)
    if layout in ("4_grid",):
        return (2, 2)
    if layout in ("6_grid",):
        return (2, 3)
    return (max(1, n_charts), 1)


# Composite-global kwargs that live on the make_*pack_* call, NOT on a
# ChartSpec. Naming one of these on a ChartSpec is the most common drift, so
# the unknown-kwarg error calls them out explicitly rather than just listing
# the valid set.
_CHARTSPEC_COMPOSITE_GLOBAL_KWARGS = frozenset({
    "skin", "dimensions", "dimension_preset", "output_dir", "filename_prefix",
    "filename_suffix", "spacing", "interactive", "session_path", "s3_manager",
    "save_as", "user_id",
})


@dataclass(init=False)
class ChartSpec:
    """Specification for a single sub-chart inside a composite layout.

    Mirrors a subset of ``make_chart()``'s parameters but omits anything
    that's globally controlled by the composite (skin, dimensions,
    output paths). The composite engine builds each ``ChartSpec`` into
    an Altair chart and lays them out with ``alt.hconcat`` / ``vconcat``.

    Per-panel text panels (``caption`` / ``side_left`` / ``side_right``)
    accept the same string-or-dict shape as on ``make_chart``. Captions
    sit below their own sub-chart; side panels flank that sub-chart and
    remain inside the composite frame.

    Axis-title kwargs (``x_title`` / ``y_title`` / ``y_title_right``,
    plus ``x_label`` / ``y_label`` aliases) accept the same canonical-
    or-mapping pattern as ``make_chart``: pass at top level for
    ergonomics OR set on ``mapping``; ``mapping[...]`` wins if both
    are set.

    Unknown keyword arguments raise a typed ``ValidationError`` naming the
    bad kwarg, listing the valid set, and suggesting the nearest match --
    rather than the bare ``TypeError: __init__() got an unexpected keyword
    argument`` a plain dataclass emits when call-site code drifts.
    """

    df: pd.DataFrame
    chart_type: str
    mapping: Dict[str, Any]
    title: Optional[str] = None
    subtitle: Optional[str] = None
    annotations: Optional[List[Annotation]] = None
    layers: Optional[List[Dict[str, Any]]] = None
    caption: Union[str, Dict[str, Any], None] = None
    side_left: Union[str, Dict[str, Any], None] = None
    side_right: Union[str, Dict[str, Any], None] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    x_title: Optional[str] = None
    y_title: Optional[str] = None
    y_title_right: Optional[str] = None

    def __init__(
        self,
        df: pd.DataFrame,
        chart_type: str,
        mapping: Dict[str, Any],
        *,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        annotations: Optional[List[Annotation]] = None,
        layers: Optional[List[Dict[str, Any]]] = None,
        caption: Union[str, Dict[str, Any], None] = None,
        side_left: Union[str, Dict[str, Any], None] = None,
        side_right: Union[str, Dict[str, Any], None] = None,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
        x_title: Optional[str] = None,
        y_title: Optional[str] = None,
        y_title_right: Optional[str] = None,
        **extra: Any,
    ) -> None:
        if extra:
            self._raise_unknown_kwargs(list(extra))
        self.df = df
        self.chart_type = chart_type
        self.mapping = mapping
        self.title = title
        self.subtitle = subtitle
        self.annotations = annotations
        self.layers = layers
        self.caption = caption
        self.side_left = side_left
        self.side_right = side_right
        self.x_label = x_label
        self.y_label = y_label
        self.x_title = x_title
        self.y_title = y_title
        self.y_title_right = y_title_right
        self.__post_init__()

    @staticmethod
    def _raise_unknown_kwargs(unknown: List[str]) -> None:
        valid = [
            "df", "chart_type", "mapping", "title", "subtitle", "annotations",
            "layers", "caption", "side_left", "side_right", "x_label",
            "y_label", "x_title", "y_title", "y_title_right",
        ]
        bad = unknown[0]
        global_hint = ""
        if any(k in _CHARTSPEC_COMPOSITE_GLOBAL_KWARGS for k in unknown):
            offenders = [k for k in unknown if k in _CHARTSPEC_COMPOSITE_GLOBAL_KWARGS]
            global_hint = (
                f" Note: {offenders} are composite-global -- set them on the "
                f"make_*pack_* call (e.g. make_4pack_grid(..., "
                f"dimension_preset='wide')), not on a ChartSpec."
            )
        suggestion = difflib.get_close_matches(bad, valid, n=1, cutoff=0.6)
        did_you_mean = f" Did you mean '{suggestion[0]}'?" if suggestion else ""
        raise ValidationError(
            f"ChartSpec got unexpected keyword argument(s): {unknown}. "
            f"Valid ChartSpec kwargs: {valid}.{did_you_mean}{global_hint}"
        )

    def __post_init__(self) -> None:
        # Route top-level axis-title kwargs into ``mapping`` so the
        # downstream renderer doesn't have to know about the
        # convenience kwargs. Mirrors ``make_chart``'s behaviour;
        # mapping[...] wins when both are set.
        merged = dict(self.mapping or {})
        for kwarg_val, mapping_key in (
            (self.x_label, "x_title"),
            (self.y_label, "y_title"),
            (self.x_title, "x_title"),
            (self.y_title, "y_title"),
            (self.y_title_right, "y_title_right"),
        ):
            if kwarg_val is not None and mapping_key not in merged:
                merged[mapping_key] = kwarg_val
        self.mapping = merged


@dataclass
class CompositeResult:
    """Output of ``make_composite()`` and its convenience wrappers.

    Mirrors ``ChartResult`` for single-chart parity; check ``success``,
    ``error_message``, and ``chart_errors`` to surface partial failures.
    """

    png_path: Optional[str]
    layout: str
    n_charts: int
    success: bool = True
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    audit_trail: List[str] = field(default_factory=list)
    download_url: Optional[str] = None
    vegalite_json: Optional[Dict[str, Any]] = None
    skin: Optional[str] = None
    chart_errors: List[Dict[str, Any]] = field(default_factory=list)
    editor_html_path: Optional[str] = None
    editor_download_url: Optional[str] = None

    def __repr__(self) -> str:
        parts = [f"CompositeResult(success={self.success}, layout={self.layout}"]
        if self.png_path:
            parts.append(f"png_path={self.png_path}")
        if self.download_url:
            parts.append(f"download_url={self.download_url}")
        if self.error_message:
            parts.append(f"error={self.error_message}")
        return ", ".join(parts) + ")"


def _build_single_chart(
    spec: ChartSpec,
    skin_config: Dict[str, Any],
    width: int,
    height: int,
    *,
    force_x_label_angle: Optional[int] = None,
    reserve_caption_h: Optional[int] = None,
    reserve_side_left_w: Optional[int] = None,
    reserve_side_right_w: Optional[int] = None,
    title_fontsize_override: Optional[int] = None,
    subtitle_fontsize_override: Optional[int] = None,
    suppress_lvl: bool = False,
) -> alt.Chart:
    """Build a single Altair chart from a ``ChartSpec`` for composite use.

    Performs the same sequence as ``make_chart()`` minus the I/O
    (PNG render, S3 upload, presigned URL, studio HTML wrap):
      1. Auto-melt for multi_line/area
      2. Sanitize column names
      3. Validate plot-ready DF + encoding + integrity
      4. Dispatch to ``_build_*``
      5. Apply title/subtitle (per-sub-chart)
      6. Layer annotations (LVL auto-injected on multi_line by default)
      7. Strip ``config`` and ``$schema`` from the spec (they belong at
         the composite level, not per sub-chart -- Altair 4.x rejects
         them inside hconcat/vconcat).

    ``suppress_lvl=True`` is reserved for facet grids only; pack composites
    (``make_2pack_*``, ``make_4pack_grid``, etc.) leave it False so every
    multi_line cell gets end-of-line labels instead of a colour legend.

    Args:
        force_x_label_angle: When set, overrides the per-chart
            ``AxisConfig.label_angle`` for the x-axis. ``make_composite``
            uses this to harmonise tick rotation across sub-charts so a
            two-pack doesn't render one panel with horizontal labels and
            another with diagonal ones.

    Returns:
        An ``alt.Chart`` (or ``LayerChart``) ready to feed into
        ``alt.hconcat`` / ``alt.vconcat``.
    """
    # BUG-3 fix: deep-copy the input DataFrame so the builders' in-place
    # transforms (NaN interp on time series, ``_wf_y_*`` columns on
    # waterfalls, column renaming on dual-axis, etc.) don't mutate the
    # caller's ChartSpec. Without this, re-rendering the same ChartSpec
    # in a different composite layout would see a corrupted DataFrame.
    df = spec.df.copy()
    mapping = dict(spec.mapping)
    chart_type = spec.chart_type

    # Pre-chart transforms.
    if chart_type in {"multi_line", "area"}:
        df, mapping = _auto_melt_for_multiline(df, mapping)
    df, mapping = _sanitize_column_names(df, mapping)
    df = _normalize_intraday_x_column(df, mapping, chart_type)
    df = _coerce_string_x_to_datetime(df, mapping, chart_type)

    # Validation.
    validate_plot_ready_df(df, chart_type, mapping)
    _validate_encoding_data(df, mapping, chart_type)
    _validate_chart_data_integrity(df, mapping, chart_type)

    _legend_color_field = _get_field(mapping, "color")
    if (
        _legend_color_field
        and _legend_color_field in df.columns
        and _color_legend_will_render(
            chart_type, mapping, spec.annotations, suppress_lvl=suppress_lvl,
            df=df,
        )
    ):
        _validate_legend_labels(
            df,
            _legend_color_field,
            width,
            mapping,
            composite_cell=suppress_lvl,
        )

    # Build.
    chart = _dispatch_builder(
        chart_type, df, mapping, skin_config, width, height, spec.layers,
        composite_cell=True,
    )

    # Per-sub-chart title/subtitle. Length-validated + auto-wrapped so a
    # long ``ChartSpec.title`` doesn't blow past the panel boundary the
    # composite reserved for it. ValueError propagates to make_composite,
    # which collects it into ``chart_errors`` and renders survivors.
    #
    # The explicit ``fontSize`` / ``subtitleFontSize`` overrides are what
    # make the composite hierarchy read as a hierarchy: per-chart titles
    # are deliberately smaller than the composite super-title (set in
    # ``make_composite``) so the eye lands on the super-title first and
    # the per-panel titles second. Without these overrides Altair would
    # inherit the skin's 26px default, which sits within 2px of the
    # super-title and flattens the visual order.
    if spec.title:
        title_lines = _validate_and_wrap_text(
            spec.title, slot_kind="subchart_title", width_px=width,
            slot_label=f"ChartSpec.title ({spec.chart_type!r})",
            widening_hint=(
                "use a wider dimension_preset (e.g. 'wide')"
            ),
        )
        subtitle_lines = _validate_and_wrap_text(
            spec.subtitle, slot_kind="subchart_subtitle",
            width_px=width,
            slot_label=f"ChartSpec.subtitle ({spec.chart_type!r})",
            widening_hint=(
                "use a wider dimension_preset (e.g. 'wide')"
            ),
        )
        title_fs = (
            title_fontsize_override
            if title_fontsize_override
            else _SUBCHART_TITLE_FONT_SIZE
        )
        subtitle_fs = (
            subtitle_fontsize_override
            if subtitle_fontsize_override
            else _SUBCHART_SUBTITLE_FONT_SIZE
        )
        if subtitle_lines:
            chart = chart.properties(
                title=_title_params_from_lines(
                    title_lines,
                    width_px=width,
                    subtitle_lines=subtitle_lines,
                    anchor="start",
                    font_size=title_fs,
                    subtitle_font_size=subtitle_fs,
                )
            )
        else:
            chart = chart.properties(
                title=_title_params_from_lines(
                    title_lines,
                    width_px=width,
                    anchor="start",
                    font_size=title_fs,
                )
            )

    # Per-cell PlotText routing: pull PlotText annotations out and
    # promote them to per-cell text-panel slots BEFORE the layer pass.
    # ``ChartSpec.caption`` / ``side_left`` / ``side_right`` (set by
    # the composite caller) win against PlotText that targets the
    # same slot -- next-available fallback per
    # ``_route_plottext_to_panels`` semantics.
    cell_annotations = spec.annotations
    if suppress_lvl:
        cell_annotations = _strip_lvl_annotations(cell_annotations)
    cell_annotations, _lvl_stripped = _strip_dual_axis_lvl_annotations(
        cell_annotations, mapping,
    )
    if _lvl_stripped:
        logger.warning(
            "[_build_single_chart] Stripped %d LastValueLabel annotation(s) "
            "on dual-axis %r -- LVL collides with the right y-axis; colour "
            "legend renders instead.",
            _lvl_stripped, spec.title,
        )

    # Auto-default LastValueLabel for multi_line / timeseries (same as
    # standalone ``make_chart``). Facet grids pass ``suppress_lvl=True``;
    # pack composites leave it False so end-of-line labels replace the
    # colour legend in every cell.
    if not suppress_lvl and _should_auto_inject_lvl(
        chart_type, mapping, cell_annotations,
    ):
        cell_annotations = list(cell_annotations or [])
        cell_annotations.append(LastValueLabel())

    if not suppress_lvl:
        # Silent endpoint-annotation strip; mirrors the standalone branch
        # in ``make_chart``.
        cell_annotations = _strip_endpoint_annotations_redundant_to_lvl(
            df, chart_type, mapping, cell_annotations,
        )
        _validate_lvl_series_names(cell_annotations, df, mapping)

    cell_caption = spec.caption
    cell_side_left = spec.side_left
    cell_side_right = spec.side_right
    if cell_annotations:
        (
            cell_annotations,
            cell_caption,
            cell_side_left,
            cell_side_right,
            _cell_pt_warnings,
        ) = _route_plottext_to_panels(
            cell_annotations,
            explicit_caption=cell_caption,
            explicit_side_left=cell_side_left,
            explicit_side_right=cell_side_right,
        )
        for _w in _cell_pt_warnings:
            logger.warning(
                "[_build_single_chart] %r: %s", spec.title, _w,
            )

    # Annotations.
    if cell_annotations:
        try:
            chart = render_annotations(
                chart, cell_annotations, df, mapping, skin_config,
                chart_type=spec.chart_type,
                chart_width=width, chart_height=height,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[_build_single_chart] Annotation failed for %r: %s",
                spec.title,
                exc,
            )

    # Axis beautification (date formats, label rotation, y-domain) --
    # parity with the standalone ``make_chart`` path. Without this, a
    # composite sub-chart inherits Vega-Lite's default temporal axis
    # which produces full month names ("August / December / 2026")
    # instead of the house-style "mmm-yy" (e.g. "Apr-26").
    chart_spec_dict = chart.to_dict()
    try:
        # Detect a `_build_bar` auto-flip the same way `make_chart`
        # does -- composite cells use this builder too, so the same
        # B07 mismatch would otherwise apply numeric axis labels at
        # -45 here.
        eff_mapping_b = mapping
        eff_chart_type_b = chart_type
        if chart_type == "bar":
            spec_enc = (
                chart_spec_dict.get("encoding")
                or (
                    chart_spec_dict.get("layer", [{}])[0].get("encoding")
                    if chart_spec_dict.get("layer") else None
                )
            )
            if isinstance(spec_enc, dict):
                spec_x_field = (
                    spec_enc.get("x", {}).get("field")
                    if isinstance(spec_enc.get("x"), dict) else None
                )
                if (
                    spec_x_field
                    and spec_x_field != mapping.get("x")
                    and spec_x_field == mapping.get("y")
                ):
                    eff_mapping_b = dict(mapping)
                    eff_mapping_b["x"] = mapping.get("y")
                    eff_mapping_b["y"] = mapping.get("x")
                    eff_mapping_b["x_title"] = mapping.get("y_title")
                    eff_mapping_b["y_title"] = mapping.get("x_title")
                    eff_chart_type_b = "bar_horizontal"
        axis_configs = get_axis_beautification(
            df, eff_mapping_b, eff_chart_type_b, width, height
        )
        if axis_configs:
            # ``force_x_label_angle`` (the temporal-consensus angle from
            # ``_composite_consensus_x_angle``) is meant to harmonise
            # rotation across temporal panels only. Applying it to a
            # nominal x-axis (categorical bars, yield-curve tenors)
            # clobbers the per-panel angle that the bar builder
            # specifically picked to avoid overlap. Skip the override
            # when the panel's own x-axis isn't temporal.
            if force_x_label_angle is not None and "x" in axis_configs:
                x_field_for_panel = (
                    eff_mapping_b.get("x") if isinstance(eff_mapping_b.get("x"), str) else None
                )
                panel_x_is_temporal = bool(
                    x_field_for_panel
                    and x_field_for_panel in df.columns
                    and pd.api.types.is_datetime64_any_dtype(df[x_field_for_panel])
                )
                if panel_x_is_temporal:
                    axis_configs["x"].label_angle = force_x_label_angle
            chart_spec_dict = apply_beautification_to_spec(
                chart_spec_dict, axis_configs
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[_build_single_chart] Axis beautification skipped for %r: %s",
            spec.title,
            exc,
        )

    # Strip ``config`` and ``$schema`` -- they will be applied at the
    # composite level. Leaving them on each sub-chart causes Altair 4.x
    # to raise schema errors when nesting in hconcat/vconcat.
    chart_spec_dict.pop("config", None)
    chart_spec_dict.pop("$schema", None)
    saved_resolve = chart_spec_dict.get("resolve")

    # Resolve named-dataset references to inline values so the spec
    # round-trips cleanly through ``alt.LayerChart.from_dict``.
    #
    # Walk recursively through every nested layer / hconcat / vconcat:
    # annotations whose ``to_layer()`` returns a LayerChart of sub-charts
    # with DIFFERENT inline data per sub-layer (VLine = rule + label,
    # Arrow = body + head + label, Band(x1, x2) = rect + halo + label,
    # PointLabel halo + text) make altair serialize each sub-layer's
    # data as a SEPARATE named dataset. The wrapper carries no shared
    # data attribute, so a one-level inliner orphans those references
    # when ``datasets`` gets popped -- the annotation silently
    # disappears in the composite render. Recursion catches every
    # depth; cheap because each chart has at most a handful of layers.
    datasets = chart_spec_dict.pop("datasets", {})
    if datasets:
        def _inline_data_refs(node: Any) -> None:
            if isinstance(node, dict):
                d = node.get("data")
                if (
                    isinstance(d, dict)
                    and "name" in d
                    and "values" not in d
                ):
                    ds_name = d["name"]
                    if ds_name in datasets:
                        node["data"] = {"values": datasets[ds_name]}
                for v in node.values():
                    _inline_data_refs(v)
            elif isinstance(node, list):
                for item in node:
                    _inline_data_refs(item)

        _inline_data_refs(chart_spec_dict)

    # Per-sub-chart text panels (caption / side_left / side_right). Wraps
    # the data spec in hconcat/vconcat at the dict level so the
    # downstream reconstruction switch handles it via
    # ``alt.HConcatChart.from_dict`` / ``alt.VConcatChart.from_dict``.
    #
    # Uses the routed values (cell_caption / cell_side_left /
    # cell_side_right) which include any PlotText annotations that
    # promoted into these slots above.
    #
    # Reserve dimensions (forwarded by ``make_composite``) force every
    # sub-chart cell to reserve the SAME caption-row height and side-
    # panel widths. Without them, a 4-pack where one panel has a
    # caption and another has a side panel would render with
    # mismatched chart sizes and the chart plots would not align.
    has_own_text = (
        cell_caption is not None
        or cell_side_left is not None
        or cell_side_right is not None
    )
    has_reserve = (
        (reserve_caption_h or 0) > 0
        or (reserve_side_left_w or 0) > 0
        or (reserve_side_right_w or 0) > 0
    )
    if has_own_text or has_reserve:
        try:
            chart_spec_dict = _apply_text_panels_to_spec(
                chart_spec_dict,
                chart_width=width, chart_height=height,
                caption=cell_caption,
                side_left=cell_side_left,
                side_right=cell_side_right,
                skin_config=skin_config,
                reserve_caption_h=reserve_caption_h,
                reserve_side_left_w=reserve_side_left_w,
                reserve_side_right_w=reserve_side_right_w,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[_build_single_chart] text-panel wrap failed for %r: %s",
                spec.title, exc,
            )

    # Reconstruct using the right Altair class for the spec shape.
    if "layer" in chart_spec_dict:
        chart = alt.LayerChart.from_dict(chart_spec_dict)
    elif "hconcat" in chart_spec_dict:
        chart = alt.HConcatChart.from_dict(chart_spec_dict)
    elif "vconcat" in chart_spec_dict:
        chart = alt.VConcatChart.from_dict(chart_spec_dict)
    else:
        chart = alt.Chart.from_dict(chart_spec_dict)

    # Re-apply ``resolve`` config that may have been stripped during
    # the round-trip (dual-axis sub-charts need this so their
    # ``y='independent'`` resolution is preserved inside composites).
    if saved_resolve and hasattr(chart, "resolve_scale"):
        scale_resolve = saved_resolve.get("scale", {})
        axis_resolve = saved_resolve.get("axis", {})
        legend_resolve = saved_resolve.get("legend", {})
        if scale_resolve:
            chart = chart.resolve_scale(**scale_resolve)
        if axis_resolve:
            chart = chart.resolve_axis(**axis_resolve)
        if legend_resolve:
            chart = chart.resolve_legend(**legend_resolve)

    return chart


def _isolate(chart: alt.Chart) -> alt.Chart:
    """Apply per-panel resolve so Vega-Lite doesn't merge scales/legends.

    ``resolve_*`` on an outer concat only governs its DIRECT children. When
    a composite nests ``hconcat`` rows inside a ``vconcat`` (4-pack /
    6-pack), each row would otherwise inherit shared color/x/y scales for
    its own children, which is what produces the merged "all series"
    legend and the squashed shared y-axis.
    """
    return chart.resolve_scale(
        color="independent", y="independent", x="independent",
    ).resolve_legend(color="independent")


# ---------------------------------------------------------------------------
# Text panels: caption (below), side-left, side-right
# ---------------------------------------------------------------------------

# Default style for caption / side-panel text. Override per-call by
# passing a dict instead of a bare string.
#
# 2026-05-10 readability tuning (per user feedback on the new
# outside-only PlotText surface): bumped font_size 11 -> 12 (clearly
# larger), color #666 -> #555 (slightly darker, better contrast),
# padding 8 -> 5 (text starts closer to the chart edge -- combined
# with the hconcat spacing reduction in _wrap_with_text_panels /
# _apply_text_panels_to_spec the visible chart-to-text gap drops
# from ~12px to ~5px). Tighter visual coupling makes the panel
# feel like an integrated part of the chart instead of a detached
# annotation.
_TEXT_PANEL_DEFAULTS: Dict[str, Any] = {
    "font_size": 12,
    "color": "#555555",
    "italic": False,
    "align": "left",
    # Inner padding inside the text panel itself. The OUTER (chart-edge)
    # padding is killed asymmetrically by ``_build_text_panel`` so the
    # panel's chart-facing edge sits flush against the chart's border.
    "padding": 5,
    "width_pct": None,  # side panels: fraction of chart width (default 0.22)
}


def _normalize_text_panel(
    raw: Union[str, Dict[str, Any], None],
) -> Optional[Dict[str, Any]]:
    """Coerce a string-or-dict text-panel parameter into a normalized dict.

    Returns ``None`` for empty / missing input. The returned dict always
    carries every styling key (``font_size``, ``color``, ``italic``,
    ``align``, ``padding``, ``width_pct``) plus the ``text`` payload.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        if not raw.strip():
            return None
        cfg = dict(_TEXT_PANEL_DEFAULTS)
        cfg["text"] = raw
        return cfg
    if isinstance(raw, dict):
        text = raw.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return None
        cfg = dict(_TEXT_PANEL_DEFAULTS)
        for k in ("font_size", "color", "italic", "align", "padding", "width_pct"):
            if k in raw:
                cfg[k] = raw[k]
        cfg["text"] = text
        return cfg
    raise TypeError(
        f"Text-panel parameter must be str or dict, got {type(raw).__name__}"
    )


def _build_text_panel(
    cfg: Dict[str, Any],
    *,
    width: int,
    height: Optional[int],
    skin_config: Dict[str, Any],
    chart_edge: Optional[str] = None,
) -> alt.Chart:
    """Build a text-only Altair chart (one ``mark_text``) sized for a panel.

    Used for caption (below-chart, full chart width) and side panels
    (left / right, fraction of chart width). The text is pre-wrapped
    via ``_wrap_text_to_width`` so it fits the panel's content area.

    ``chart_edge`` controls asymmetric padding so the panel-side edge
    that abuts the chart has no outer gap (kills ~10px of dead space
    that Vega-Lite's default per-chart padding adds between concatenated
    sub-charts) AND collapses the inner text padding on that edge so
    the text sits flush against the chart:

      - ``"right"`` -- this panel sits to the LEFT of the chart, so its
        right edge abuts the chart; right outer padding -> 0 AND the
        text's right alignment uses ``padding_chart`` (1px) so the
        last character lands right against the chart's left edge.
      - ``"left"``  -- this panel sits to the RIGHT of the chart;
        left outer padding -> 0 AND the text's left alignment uses
        ``padding_chart`` (1px) so the first character lands right
        against the chart's right edge.
      - ``"top"``   -- caption below the chart; top outer padding -> 0
        AND the text top inset uses ``padding_chart`` (1px) so the
        caption's first line sits just below the chart's bottom edge.
      - ``None``    -- standalone, symmetric padding.

    Args:
        cfg: Normalized config dict (see ``_normalize_text_panel``).
        width: Total panel width in pixels.
        height: Total panel height in pixels. When ``None`` the height
            auto-derives from the wrapped line count + padding.
        skin_config: Active skin configuration dict (for font family).
        chart_edge: Which edge of the panel abuts the chart (see above).

    Returns:
        An ``alt.Chart`` ready to drop into ``alt.vconcat`` /
        ``alt.hconcat`` next to a data chart.
    """
    text = cfg["text"]
    font_size = int(cfg["font_size"])
    color = cfg["color"]
    italic = bool(cfg["italic"])
    align = cfg["align"]
    padding = int(cfg["padding"])

    # Asymmetric inner padding: tight on the chart-facing edge so the
    # text sits flush against the chart, normal padding on the other
    # edges so the panel doesn't feel cramped against the page edge.
    # See ``chart_edge`` semantics in the docstring.
    padding_chart = 1

    content_w = max(1, width - 2 * padding)
    wrapped = _wrap_text_to_width(text, content_w, font_size)
    n_lines = max(1, wrapped.count("\n") + 1)
    line_height = max(font_size + 2, int(font_size * 1.45))
    auto_h = n_lines * line_height + 2 * padding
    h = int(height) if height is not None else auto_h

    # X anchor: tight against the chart-facing edge when applicable,
    # else honour the requested align.
    if chart_edge == "left" and align == "left":
        # side_right panel: text should sit at the panel's LEFT edge
        # (which abuts the chart's right edge).
        x_px = padding_chart
    elif chart_edge == "right" and align == "right":
        # side_left panel: text should sit at the panel's RIGHT edge
        # (which abuts the chart's left edge).
        x_px = width - padding_chart
    elif align == "left":
        x_px = padding
    elif align == "right":
        x_px = width - padding
    else:
        x_px = width // 2

    # Y anchor: caption text should sit just below the chart for
    # ``chart_edge="top"`` (the caption-below-chart layout); side
    # panels just use the normal top inset.
    y_px = padding_chart if chart_edge == "top" else padding

    font_family = skin_config.get(
        "font_family", "Liberation Sans, Arial, sans-serif",
    )

    # Asymmetric outer padding kills the dead gap on the edge that
    # touches the chart. Vega-Lite default config padding is ~10px on
    # every edge of every concatenated sub-chart -- that's 20px of
    # combined dead space (text-panel right + chart left) before any
    # hconcat spacing kicks in.
    outer_pad: Dict[str, int] = {
        "left": padding, "right": padding, "top": padding, "bottom": padding,
    }
    if chart_edge == "right":
        outer_pad["right"] = 0
    elif chart_edge == "left":
        outer_pad["left"] = 0
    elif chart_edge == "top":
        outer_pad["top"] = 0

    panel = (
        alt.Chart(pd.DataFrame({"_": [0]}))
        .mark_text(
            align=align,
            baseline="top",
            fontSize=font_size,
            font=font_family,
            fontStyle="italic" if italic else "normal",
            color=color,
            lineBreak="\n",
            text=wrapped,
        )
        .encode(
            x=alt.value(x_px),
            y=alt.value(y_px),
        )
        .properties(width=width, height=h, padding=outer_pad)
    )
    return panel


def _resolve_side_width(
    cfg: Dict[str, Any], chart_width: int, default_pct: float = 0.22,
) -> int:
    """Compute a side panel's width in pixels.

    ``cfg["width_pct"]`` may be a fraction (0 < x <= 1) or an int >= 1
    interpreted as raw pixels. When ``None`` (the common case where the
    caller hasn't specified anything), the panel auto-fits to the
    wrapped text content -- short narratives produce a tight panel that
    sits flush against the chart, long narratives saturate the
    ``default_pct`` budget. This kills the dead horizontal whitespace
    that the old fixed-width default produced when the caption was
    short.

    Composite layouts use ``_scan_text_panel_reserves`` to pick the
    MAX fitted width across sibling cells, so chart plot regions still
    align even with heterogeneous caption lengths.
    """
    raw = cfg.get("width_pct")
    if raw is not None:
        val = float(raw)
        if val <= 1.0:
            if val < 0.05 or val > 0.50:
                clamped = max(0.05, min(0.50, val))
                logger.warning(
                    "[SidePanel] width_pct=%.2f outside soft range "
                    "[0.05, 0.50]; clamped to %.2f. Wider panels "
                    "produce a thin text column + squished chart.",
                    val, clamped,
                )
                val = clamped
            return max(40, int(chart_width * val))
        max_px = int(chart_width * 0.50)
        if val > max_px:
            logger.warning(
                "[SidePanel] width_pct=%dpx exceeds 50%% of chart "
                "width (%dpx); clamped to %dpx.",
                int(val), chart_width, max_px,
            )
            val = float(max_px)
        return max(40, int(val))
    return _autofit_side_width(cfg, chart_width, default_pct)


_SIDE_PANEL_MIN_READABLE_WIDTH_PX: int = 100
"""Minimum panel width for any side panel carrying real text content
(F7 fix from Phase 2 stress probe T14a -- 25/F1 BLOCKER). The previous
40px floor combined with the 22%% chart-width cap produced 60-65px-wide
panels in 2pack / 4pack cells (per-cell chart_width = 280-300px), which
wraps text at 7-8 chars per line and creates a single-character-wide
vertical column of text -- catastrophic readability collapse. Raising
the floor to 100px lets ~14 chars per line through and the text reads
as a real narrative panel even in narrow composite cells. Empty / single-
space placeholder panels keep the prior 40px floor (no readability
floor needed)."""


def _autofit_side_width(
    cfg: Dict[str, Any], chart_width: int, default_pct: float = 0.22,
) -> int:
    """Smallest width that contains the wrapped text, capped at default.

    Wrap the text to the default budget first (so a long caption fills
    the budget like before), then measure the longest line and shrink
    the panel down to that width plus the inner padding.

    F7 fix: enforce ``_SIDE_PANEL_MIN_READABLE_WIDTH_PX`` (100px) as
    the floor for panels carrying real text content, otherwise narrow
    composite cells (~300px wide) compute a tight cap (66px) that
    collapses text into a 7-char-wide column. Cap is also expanded
    to 50%% of chart_width in narrow cells so the floor can be met
    without breaking the cap-respects-chart-width invariant. Empty /
    single-space placeholder panels keep the 40px floor.
    """
    text = cfg.get("text", "")
    font_size = int(cfg.get("font_size", 11))
    padding = int(cfg.get("padding", 8))

    # F7: floor depends on whether real text is present. Placeholder
    # panels (blank cells in composite reserve rows) stay tight.
    is_real_text = bool(text and text.strip())
    floor = _SIDE_PANEL_MIN_READABLE_WIDTH_PX if is_real_text else 40

    # F7: in narrow composite cells the 22%% cap is below the readable
    # floor. Allow up to 50%% of chart_width so the floor wins.
    cap_w_px = max(floor, int(chart_width * default_pct), int(chart_width * 0.5))
    cap_w_px = min(cap_w_px, max(floor, int(chart_width * 0.5)))

    if not text:
        return floor

    content_w = max(1, cap_w_px - 2 * padding)
    wrapped = _wrap_text_to_width(text, content_w, font_size)
    char_w_px = max(1.0, font_size * 0.55)
    max_line_chars = max(len(ln) for ln in wrapped.split("\n"))
    # +1px slack so the rendered text never gets pixel-clipped on the
    # right edge by the auto-shrink.
    fitted_text_w = int(max_line_chars * char_w_px) + 1
    fitted_panel_w = fitted_text_w + 2 * padding
    return min(max(floor, fitted_panel_w), cap_w_px)


def _wrap_with_text_panels(
    chart: alt.Chart,
    *,
    chart_width: int,
    chart_height: int,
    caption: Union[str, Dict[str, Any], None] = None,
    side_left: Union[str, Dict[str, Any], None] = None,
    side_right: Union[str, Dict[str, Any], None] = None,
    skin_config: Dict[str, Any],
) -> alt.Chart:
    """Wrap a chart in optional caption (below) and/or side panels.

    Composition order:

        hconcat( side_left, vconcat(chart, caption), side_right )

    ``None`` panels are skipped. Returns the original chart unchanged
    when every panel input is ``None`` / empty.
    """
    cap_cfg = _normalize_text_panel(caption)
    left_cfg = _normalize_text_panel(side_left)
    right_cfg = _normalize_text_panel(side_right)

    if cap_cfg is None and left_cfg is None and right_cfg is None:
        return chart

    body: alt.Chart = chart
    if cap_cfg is not None:
        cap_panel = _build_text_panel(
            cap_cfg, width=chart_width, height=None,
            skin_config=skin_config, chart_edge="top",
        )
        body = alt.vconcat(body, cap_panel, spacing=6).resolve_scale(
            color="independent", x="independent", y="independent",
        ).resolve_legend(color="independent")

    if left_cfg is None and right_cfg is None:
        return body

    h_parts: List[alt.Chart] = []
    if left_cfg is not None:
        left_w = _resolve_side_width(left_cfg, chart_width)
        h_parts.append(_build_text_panel(
            left_cfg, width=left_w, height=chart_height,
            skin_config=skin_config, chart_edge="right",
        ))
    h_parts.append(body)
    if right_cfg is not None:
        right_w = _resolve_side_width(right_cfg, chart_width)
        h_parts.append(_build_text_panel(
            right_cfg, width=right_w, height=chart_height,
            skin_config=skin_config, chart_edge="left",
        ))
    return alt.hconcat(*h_parts, spacing=0).resolve_scale(
        color="independent", x="independent", y="independent",
    ).resolve_legend(color="independent")


def _wrap_composite_with_text_panels(
    composite: alt.Chart,
    *,
    composite_width: int,
    composite_height: int,
    caption: Union[str, Dict[str, Any], None] = None,
    narrative_left: Union[str, Dict[str, Any], None] = None,
    narrative_right: Union[str, Dict[str, Any], None] = None,
    skin_config: Dict[str, Any],
) -> alt.Chart:
    """Composite-level analogue of ``_wrap_with_text_panels``.

    Same wrap order; the ``caption`` sits below ALL sub-panels and
    ``narrative_left`` / ``narrative_right`` flank the entire pack.
    Defaults to a wider 22% side budget against the composite's full
    width (so a 4-pack at 1400px gets ~310px side panels).
    """
    return _wrap_with_text_panels(
        composite,
        chart_width=composite_width,
        chart_height=composite_height,
        caption=caption,
        side_left=narrative_left,
        side_right=narrative_right,
        skin_config=skin_config,
    )


_BLANK_PANEL_CFG: Dict[str, Any] = {
    **_TEXT_PANEL_DEFAULTS,
    "text": " ",  # single space renders nothing visible but takes the slot
}


def _estimate_caption_height(cfg: Dict[str, Any], panel_width: int) -> int:
    """Approximate the rendered height of a caption-style text panel.

    Used by ``make_composite`` to compute a uniform reserve height across
    sub-chart captions so 4-pack / 6-pack grids align (every cell gets
    the SAME caption-row height even when individual cells have shorter
    text or no caption at all).
    """
    text = cfg.get("text", "")
    fs = int(cfg.get("font_size", 11))
    pad = int(cfg.get("padding", 12))
    content_w = max(1, panel_width - 2 * pad)
    wrapped = _wrap_text_to_width(text, content_w, fs)
    n_lines = max(1, wrapped.count("\n") + 1)
    line_height = max(fs + 2, int(fs * 1.45))
    return n_lines * line_height + 2 * pad


def _scan_text_panel_reserves(
    charts: List["ChartSpec"],
    chart_width: int,
) -> Tuple[int, int, int]:
    """Return ``(max_caption_h, max_side_left_w, max_side_right_w)`` across
    a list of ``ChartSpec``s. Zero when no spec carries the corresponding
    text panel.

    These reserves drive uniform per-cell wrapping in composite layouts
    so the chart plot regions align even when individual sub-charts
    carry different combinations of caption / side panels.

    Treats PlotText annotations as text-panel sources too: each
    ChartSpec's annotations are previewed through
    ``_route_plottext_to_panels`` so a PlotText that promotes into
    side_right contributes to the right-panel reserve width even
    though the spec itself has ``side_right=None``. Without this the
    composite would forget to reserve the right-side slot and the
    PlotText panel would distort the per-cell width during the wrap.
    """
    max_cap_h = 0
    max_left_w = 0
    max_right_w = 0
    for spec in charts:
        # Preview PlotText routing to see which slots it would fill
        # in this cell. Discards the filtered annotation list -- we
        # only care about the resolved (caption / side_left /
        # side_right) values for reserve sizing.
        _ann, cell_cap, cell_left, cell_right, _w = _route_plottext_to_panels(
            getattr(spec, "annotations", None),
            explicit_caption=getattr(spec, "caption", None),
            explicit_side_left=getattr(spec, "side_left", None),
            explicit_side_right=getattr(spec, "side_right", None),
        )
        cap_cfg = _normalize_text_panel(cell_cap)
        if cap_cfg is not None:
            max_cap_h = max(max_cap_h, _estimate_caption_height(cap_cfg, chart_width))
        left_cfg = _normalize_text_panel(cell_left)
        if left_cfg is not None:
            max_left_w = max(max_left_w, _resolve_side_width(left_cfg, chart_width))
        right_cfg = _normalize_text_panel(cell_right)
        if right_cfg is not None:
            max_right_w = max(max_right_w, _resolve_side_width(right_cfg, chart_width))
    return max_cap_h, max_left_w, max_right_w


def _apply_text_panels_to_spec(
    spec: Dict[str, Any],
    *,
    chart_width: int,
    chart_height: int,
    caption: Union[str, Dict[str, Any], None] = None,
    side_left: Union[str, Dict[str, Any], None] = None,
    side_right: Union[str, Dict[str, Any], None] = None,
    skin_config: Dict[str, Any],
    reserve_caption_h: Optional[int] = None,
    reserve_side_left_w: Optional[int] = None,
    reserve_side_right_w: Optional[int] = None,
) -> Dict[str, Any]:
    """Spec-level wrap: glue text panels around an already-built chart spec.

    Used by ``make_chart`` AFTER axis beautification + typography
    overrides have run on the inner data spec. The inner spec moves
    into the wrapper's ``hconcat`` / ``vconcat`` list. ``$schema`` /
    ``config`` / ``datasets`` are hoisted to the wrapper (they only
    belong at the top level); ``title`` stays on the inner spec so it
    anchors to the chart's plot region rather than the wrapped
    composition.

    Reserve parameters force uniform cell dimensions across sub-charts
    in a composite. When ``reserve_caption_h`` is set and this spec
    has no ``caption``, an invisible placeholder of that height fills
    the caption slot so the sub-chart's outer height matches its
    siblings'. Same for ``reserve_side_left_w`` / ``reserve_side_right_w``
    on the horizontal axis. ``make_composite`` computes these reserves
    as the max across all ``ChartSpec``s and passes them through.

    When the user supplies a caption / side panel of their own, the
    rendered panel uses their text and style but its size is forced
    to the reserve so the grid stays uniform.
    """
    cap_cfg = _normalize_text_panel(caption)
    left_cfg = _normalize_text_panel(side_left)
    right_cfg = _normalize_text_panel(side_right)

    has_cap_reserve = (reserve_caption_h or 0) > 0
    has_left_reserve = (reserve_side_left_w or 0) > 0
    has_right_reserve = (reserve_side_right_w or 0) > 0

    needs_caption = cap_cfg is not None or has_cap_reserve
    needs_left = left_cfg is not None or has_left_reserve
    needs_right = right_cfg is not None or has_right_reserve

    if not (needs_caption or needs_left or needs_right):
        return spec

    inner = copy.deepcopy(spec)
    schema = inner.pop("$schema", None)
    config = inner.pop("config", None)
    # NOTE: do NOT pop ``title``. Hoisting the title to the outer
    # wrapper causes it to anchor against the WHOLE composition (left
    # edge = leftmost side-panel edge), which makes the title visually
    # drift left when ``side_left`` is set. Leaving the title on the
    # inner data chart keeps it aligned with the chart's plot region
    # regardless of which side panels are wrapped around it.
    datasets = inner.pop("datasets", None)
    # Strip ``padding`` from the inner sub-spec: Vega-Lite ignores
    # top-level padding on sub-views inside hconcat / vconcat (Altair
    # actually rejects it at the validator with the message
    # "Objects with 'padding' attribute cannot be used within
    # HConcatChart"). We bypass Altair by emitting raw spec dicts via
    # vl_convert, but the underlying behaviour is the same -- the
    # padding key has no effect here. Strip it so the spec stays
    # canonical and so future tightening attempts don't waste cycles
    # on this dead lever. The actual chart-to-panel gap is killed by
    # (a) the panel's chart-facing inner padding (``padding_chart=1``
    # in ``_build_text_panel``), (b) the panel's chart-facing outer
    # padding (``chart_edge`` -> 0 in ``_build_text_panel``), and
    # (c) hconcat ``spacing=0``. The remaining gap is Vega-Lite's
    # intrinsic axis-tick-label clearance (the rightmost tick label
    # like "18" extends past the bar's right edge to stay
    # readable) which is structural and not overridable from the
    # spec without clipping labels.
    inner.pop("padding", None)

    def _panel_spec(
        cfg: Dict[str, Any],
        width: int,
        height: Optional[int],
        chart_edge: Optional[str] = None,
    ) -> Dict[str, Any]:
        panel = _build_text_panel(
            cfg, width=width, height=height,
            skin_config=skin_config, chart_edge=chart_edge,
        )
        d = panel.to_dict()
        d.pop("$schema", None)
        d.pop("config", None)
        # ``padding`` is a top-level-only Vega-Lite property. When the
        # panel is nested inside a composite (4-pack / 6-pack), keeping
        # it triggers schema validation errors. The chart-edge
        # asymmetry is applied via panel-internal text offset instead
        # (see ``_apply_text_panels_to_spec`` callers; ``chart_edge``
        # currently only matters for the standalone wrap path).
        d.pop("padding", None)
        # Inline-resolve named datasets so the sub-spec round-trips
        # cleanly when nested inside another hconcat / vconcat. Vega-Lite
        # rejects ``datasets`` blocks below the top level.
        ds = d.pop("datasets", {})
        if ds:
            if (
                isinstance(d.get("data"), dict)
                and "name" in d["data"]
                and "values" not in d["data"]
            ):
                name = d["data"]["name"]
                if name in ds:
                    d["data"] = {"values": ds[name]}
        return d

    body: Dict[str, Any] = inner
    if needs_caption:
        cfg_to_use = cap_cfg if cap_cfg is not None else dict(_BLANK_PANEL_CFG)
        # Force the panel height to the reserve so every sibling cell
        # ends at the same y-coordinate.
        cap_h: Optional[int] = (
            int(reserve_caption_h) if has_cap_reserve else None
        )
        cap_spec = _panel_spec(
            cfg_to_use, chart_width, cap_h, chart_edge="top",
        )
        body = {"vconcat": [body, cap_spec], "spacing": 6}

    if needs_left or needs_right:
        h_parts: List[Dict[str, Any]] = []
        if needs_left:
            cfg_to_use = left_cfg if left_cfg is not None else dict(_BLANK_PANEL_CFG)
            left_w = (
                int(reserve_side_left_w)
                if has_left_reserve
                else _resolve_side_width(cfg_to_use, chart_width)
            )
            h_parts.append(
                _panel_spec(cfg_to_use, left_w, chart_height, chart_edge="right")
            )
        h_parts.append(body)
        if needs_right:
            cfg_to_use = right_cfg if right_cfg is not None else dict(_BLANK_PANEL_CFG)
            right_w = (
                int(reserve_side_right_w)
                if has_right_reserve
                else _resolve_side_width(cfg_to_use, chart_width)
            )
            h_parts.append(
                _panel_spec(cfg_to_use, right_w, chart_height, chart_edge="left")
            )
        wrapped: Dict[str, Any] = {"hconcat": h_parts, "spacing": 0}
    else:
        wrapped = body

    wrapped["resolve"] = {
        "scale": {"color": "independent", "x": "independent", "y": "independent"},
        "legend": {"color": "independent"},
    }
    if schema is not None:
        wrapped["$schema"] = schema
    if config is not None:
        wrapped["config"] = config
    if datasets is not None:
        wrapped["datasets"] = datasets
    return wrapped


def _composite_consensus_x_angle(
    charts: List["ChartSpec"],
    chart_width: int,
    chart_height: int,
) -> Optional[int]:
    """Pick a single x-axis label rotation to apply across composite sub-charts.

    Sub-charts in a 2/3/4/6-pack often have different time spans (e.g. a
    10-year CPI panel next to a 1-year equities panel). Run independently,
    each picks its own optimal label angle (0 for the wide span,
    -45 for the dense one), which produces a visually inconsistent
    composite.

    The fix: pre-compute each sub-chart's preferred angle and pick the
    most-rotated one as the consensus (so labels never clash). Sub-charts
    whose x-axis isn't temporal (categorical bars, profile yield curves)
    are excluded -- their rotation is dictated by data shape, not span.

    Returns ``None`` when no temporal sub-chart is present, so the caller
    falls back to per-chart angle selection.
    """
    angles: List[int] = []
    for spec in charts:
        try:
            df = spec.df.copy() if isinstance(spec.df, pd.DataFrame) else None
            if df is None:
                continue
            mapping = dict(spec.mapping)
            if spec.chart_type in {"multi_line", "area"}:
                df, mapping = _auto_melt_for_multiline(df, mapping)
            df, mapping = _sanitize_column_names(df, mapping)
            x_field = mapping.get("x") if isinstance(mapping.get("x"), str) else None
            if not x_field or x_field not in df.columns:
                continue
            if not pd.api.types.is_datetime64_any_dtype(df[x_field]):
                continue
            ax = get_axis_beautification(
                df, mapping, spec.chart_type, chart_width, chart_height,
            )
            x_cfg = ax.get("x")
            if x_cfg is None:
                continue
            angles.append(int(x_cfg.label_angle or 0))
        except Exception:  # noqa: BLE001
            continue
    if not angles:
        return None
    return max(angles, key=lambda a: abs(a))


# Map: original layout -> {survivor_count: downgraded_layout}.
# Survivor count of 1 always becomes ``None`` (single-chart fallback,
# handled by the caller).
#
# Orientation is preserved where the original expressed one
# (``4_horizontal`` -> ``3_horizontal`` -> ``2_horizontal``); grid
# layouts (``4_grid``, ``6_grid``) downgrade to ``N_grid`` for 4 then
# the same triangle / horizontal sequence below 4. ``3_triangle`` and
# ``3_inverted`` downgrade to ``2_horizontal`` (their bottom row is the
# only natural pair).
_LAYOUT_DOWNGRADE: Dict[str, Dict[int, Optional[str]]] = {
    "2_horizontal": {1: None},
    "2_vertical": {1: None},
    "3_triangle": {2: "2_horizontal", 1: None},
    "3_inverted": {2: "2_horizontal", 1: None},
    "3_horizontal": {2: "2_horizontal", 1: None},
    "3_vertical": {2: "2_vertical", 1: None},
    "4_grid": {3: "3_triangle", 2: "2_horizontal", 1: None},
    "4_horizontal": {3: "3_horizontal", 2: "2_horizontal", 1: None},
    "4_vertical": {3: "3_vertical", 2: "2_vertical", 1: None},
    "6_grid": {
        5: "4_grid",  # we only have 4 valid built; 5th cell not addressable
        4: "4_grid",
        3: "3_triangle",
        2: "2_horizontal",
        1: None,
    },
}


# Slot count per layout name. Used by the make_composite survivor
# trim path to bound ``built`` to the downgraded layout's expected size.
_LAYOUT_SLOT_COUNT: Dict[str, int] = {
    "2_horizontal": 2, "2_vertical": 2,
    "3_triangle": 3, "3_inverted": 3,
    "3_horizontal": 3, "3_vertical": 3,
    "4_grid": 4, "4_horizontal": 4, "4_vertical": 4,
    "6_grid": 6,
}


def _downgrade_layout_for_survivors(
    layout: str, n_survivors: int,
) -> Optional[str]:
    """Map a (layout, survivor count) to the layout that survivors fit.

    Returns ``None`` when survivor count == 1 (caller renders the lone
    survivor directly). Falls back to the original layout when the
    survivor count matches the layout's expected count or the table
    has no entry (which shouldn't happen for any layout the engine
    publishes today).
    """
    if n_survivors <= 0:
        return None
    if n_survivors == 1:
        return None
    table = _LAYOUT_DOWNGRADE.get(layout)
    if table is None:
        return layout
    if n_survivors in table:
        return table[n_survivors]
    return layout


def _compose_charts(
    charts: List[alt.Chart],
    layout: str,
    spacing: int = 20,
    has_dual_axis: bool = False,
) -> alt.Chart:
    """Lay out built sub-charts according to ``layout``.

    Composites always resolve color, x, and y scales independently so
    each sub-chart keeps its own palette and axis range -- otherwise
    Vega-Lite shares scales across panels and crushes small-range series.
    Inner concat groups (rows of a grid) get their own ``resolve_*`` too;
    outer-level ``resolve_*`` does not propagate into inner concats.
    """
    if layout == "2_horizontal":
        composed: alt.Chart = alt.hconcat(*charts, spacing=spacing)
    elif layout == "2_vertical":
        composed = alt.vconcat(*charts, spacing=spacing)
    elif layout == "3_triangle":
        bottom = _isolate(alt.hconcat(charts[1], charts[2], spacing=spacing))
        composed = alt.vconcat(charts[0], bottom, spacing=spacing)
    elif layout == "3_inverted":
        top = _isolate(alt.hconcat(charts[0], charts[1], spacing=spacing))
        composed = alt.vconcat(top, charts[2], spacing=spacing)
    elif layout == "3_horizontal":
        composed = alt.hconcat(*charts, spacing=spacing)
    elif layout == "3_vertical":
        composed = alt.vconcat(*charts, spacing=spacing)
    elif layout == "4_grid":
        top = _isolate(alt.hconcat(charts[0], charts[1], spacing=spacing))
        bot = _isolate(alt.hconcat(charts[2], charts[3], spacing=spacing))
        composed = alt.vconcat(top, bot, spacing=spacing)
    elif layout == "4_horizontal":
        composed = alt.hconcat(*charts, spacing=spacing)
    elif layout == "4_vertical":
        composed = alt.vconcat(*charts, spacing=spacing)
    elif layout == "6_grid":
        r1 = _isolate(alt.hconcat(charts[0], charts[1], spacing=spacing))
        r2 = _isolate(alt.hconcat(charts[2], charts[3], spacing=spacing))
        r3 = _isolate(alt.hconcat(charts[4], charts[5], spacing=spacing))
        composed = alt.vconcat(r1, r2, r3, spacing=spacing)
    else:
        raise ValueError(f"Unknown layout: {layout}")

    return _isolate(composed)


# ===========================================================================
# MODULE: FACET GRID (SMALL-MULTIPLES) -- driven by mapping['facet']
# ===========================================================================
#
# This block implements ``make_chart`` faceted mode: when the caller sets
# ``mapping['facet'] = '<column>'`` (plus an optional ``facet_cols=N`` and
# the sync booleans), ``make_chart`` dispatches into ``_render_facet_grid``
# which builds one alt.Chart per facet value and lays them out in an NxM
# grid. The layout uses the same ``alt.hconcat`` / ``alt.vconcat`` /
# ``_isolate`` machinery as ``make_composite`` so per-panel scales /
# legends stay independent by default.
#
# The sync defaults match today's composite philosophy: INDEPENDENT.
# Callers opt INTO sharing via ``share_y=True`` etc.
#
# See ``.cursor/rules/viz-platforms.mdc`` (RBR + targeted-gallery SOP)
# for the QC contract this code obeys.


def _resolve_facet_grid_shape(
    n_panels: int, facet_cols: Optional[int],
) -> Tuple[int, int]:
    """Resolve (rows, cols) given panel count and optional explicit cols.

    When ``facet_cols`` is not provided, fall back to a near-square
    layout favouring slightly-wider-than-tall (more cols than rows is
    the default page-portrait reading order).
    """
    if n_panels <= 0:
        raise ValidationError("Facet grid requires at least 1 panel.")
    if facet_cols is not None:
        if facet_cols <= 0:
            raise ValidationError(
                f"facet_cols must be positive, got {facet_cols}."
            )
        cols = min(facet_cols, n_panels)
    else:
        # Near-square default: cols = ceil(sqrt(n)). For 20 -> 5x4 (5 cols
        # 4 rows); for 9 -> 3x3; for 12 -> 4x3.
        cols = int(np.ceil(np.sqrt(n_panels)))
    rows = int(np.ceil(n_panels / cols))
    return (rows, cols)


def _resolve_facet_panel_dims(
    rows: int, cols: int,
    dimensions: Optional[str],
    spacing: int,
) -> Tuple[int, int]:
    """Resolve per-panel (width, height) from grid shape + preset.

    Facet panels are always SQUARE -- ``panel_w == panel_h`` regardless
    of grid shape. Asymmetric panels (e.g. 4x2 with very wide cells or
    4x4 with tall cells) read as inconsistent; small-multiples
    convention is uniform square cells. Computes the largest square
    that fits inside the per-cell width budget AND the per-cell height
    budget, then returns that square edge for both dimensions. Grids
    with fewer rows than cols (or vice-versa) intentionally leave
    canvas space unused -- readability of squares wins over filling
    every pixel.

    For ``dimensions='page_grid'`` (the default for facet mode), divide
    the usable US Letter portrait area (1200 x 1600 px) into rows*cols
    cells, accounting for inter-panel spacing. For any other named
    preset, treat its (w, h) as the per-cell BUDGET (the square edge
    is min of those two numbers). No preset -> compact-ish 280x280.
    """
    if dimensions == "page_grid" or dimensions is None:
        usable_w, usable_h = DIMENSION_PRESETS.get("page_grid", (1200, 1600))
    elif dimensions in DIMENSION_PRESETS:
        usable_w, usable_h = DIMENSION_PRESETS[dimensions]
    else:
        return (280, 280)

    # Subtract inter-panel spacing so total stays inside usable area.
    avail_w = usable_w - max(0, cols - 1) * spacing
    avail_h = usable_h - max(0, rows - 1) * spacing
    cell_w = max(140, avail_w // cols)
    cell_h = max(120, avail_h // rows)
    edge = int(min(cell_w, cell_h))
    return (edge, edge)


def _resolve_typography_for_panel_size(panel_w: int, panel_h: int) -> str:
    """Pick the typography-overrides preset best-suited to a panel size.

    Returns one of ``thumbnail`` / ``teams`` / ``compact`` / ``""`` (no
    override). Used by ``_render_facet_grid`` so the panel font sizes
    auto-shrink for tight grids without the caller specifying.

    Tuned for facet-grid use specifically: panels in the 200-400px
    range stay on ``compact`` (12-13pt axis labels) instead of dropping
    to ``teams`` (8pt) or ``thumbnail`` (7pt), because at letter-paper
    panel sizes the typography presets designed for genuinely tiny
    standalone canvases (Teams thumbnails, app embeds) shrink labels
    past readability.
    """
    if panel_w < 180 or panel_h < 160:
        return "thumbnail"
    if panel_w < 220 or panel_h < 200:
        return "teams"
    return "compact"


def _get_facet_panel_order(
    df: pd.DataFrame, facet_col: str,
    explicit_order: Optional[List[Any]] = None,
) -> List[Any]:
    """Resolve the panel id ordering.

    Default is first-appearance order in df (predictable; matches how
    PRISM tends to construct its DataFrames). An explicit
    ``explicit_order`` argument -- typically threaded from
    ``mapping['facet_order']`` at the ``_render_facet_grid`` call site
    -- takes precedence and validates that every requested id exists.
    """
    if explicit_order is not None:
        # Validate that every requested id exists in the data.
        present = set(df[facet_col].unique())
        missing = [v for v in explicit_order if v not in present]
        if missing:
            raise ValidationError(
                f"facet_order references panel ids not in df[{facet_col!r}]: "
                f"{missing}. Available: {sorted(present)}."
            )
        return list(explicit_order)
    # First-appearance order (preserves the user's natural ordering).
    seen: List[Any] = []
    seen_set: set = set()
    for v in df[facet_col].tolist():
        if v not in seen_set:
            seen.append(v)
            seen_set.add(v)
    return seen


def _split_df_by_facet(
    df: pd.DataFrame, facet_col: str, panel_order: List[Any],
) -> List[Tuple[Any, pd.DataFrame]]:
    """Yield (panel_id, sub_df) pairs in ``panel_order``."""
    out: List[Tuple[Any, pd.DataFrame]] = []
    for panel_id in panel_order:
        sub = df[df[facet_col] == panel_id].copy()
        out.append((panel_id, sub))
    return out


def _compute_shared_numeric_domain(
    df: pd.DataFrame, field: str, padding_frac: float = 0.05,
) -> Optional[List[float]]:
    """Compute a [lo, hi] numeric domain spanning the entire df.

    Pads by ``padding_frac`` of the range on each side so points don't
    sit flush against the panel edge. Returns ``None`` if the field
    isn't numeric or has no valid values.
    """
    if field not in df.columns:
        return None
    vals = pd.to_numeric(df[field], errors="coerce").dropna()
    if len(vals) == 0:
        return None
    lo, hi = float(vals.min()), float(vals.max())
    if lo == hi:
        # Pin a small synthetic range so Vega-Lite doesn't collapse.
        eps = max(abs(lo) * 0.05, 1e-6)
        return [lo - eps, hi + eps]
    span = hi - lo
    return [lo - span * padding_frac, hi + span * padding_frac]


def _compute_shared_temporal_domain(
    df: pd.DataFrame, field: str,
) -> Optional[List[str]]:
    """Compute an ISO-formatted temporal [lo, hi] domain spanning df.

    Returned as ISO strings so they round-trip cleanly through
    Vega-Lite's spec dict.
    """
    if field not in df.columns:
        return None
    if not pd.api.types.is_datetime64_any_dtype(df[field]):
        return None
    vals = df[field].dropna()
    if len(vals) == 0:
        return None
    return [vals.min().isoformat(), vals.max().isoformat()]


def _compute_shared_color_domain(
    df: pd.DataFrame, field: str,
) -> Optional[List[Any]]:
    """Compute a sorted union of the color column's unique values."""
    if field not in df.columns:
        return None
    uniq = df[field].dropna().unique().tolist()
    return sorted(uniq, key=lambda v: str(v))


def _inject_scale_domain_into_spec(
    spec: Dict[str, Any], encoding_key: str, domain: List[Any],
) -> None:
    """Patch ``encoding[<encoding_key>].scale.domain = domain`` in-place.

    Walks every layer / hconcat / vconcat / concat child so the domain
    propagates uniformly. ``domain`` is set verbatim; the caller is
    responsible for sensible bounds.
    """
    if not isinstance(spec, dict):
        return
    enc = spec.get("encoding")
    if isinstance(enc, dict) and encoding_key in enc:
        ek = enc[encoding_key]
        if isinstance(ek, dict):
            scale = ek.setdefault("scale", {})
            if isinstance(scale, dict):
                scale["domain"] = domain
    for child_key in ("layer", "hconcat", "vconcat", "concat"):
        children = spec.get(child_key)
        if isinstance(children, list):
            for child in children:
                _inject_scale_domain_into_spec(child, encoding_key, domain)


def _strip_axis_labels_from_spec(
    spec: Dict[str, Any], encoding_key: str,
) -> None:
    """Drop tick-label rendering from ``encoding[encoding_key].axis``.

    The tick MARKS still render (so panel boundaries stay aligned across
    the grid); only the label text is suppressed. Used to implement
    ``edge_only_ticks=True``: outer panels keep labels, inner panels
    pass through this helper.
    """
    if not isinstance(spec, dict):
        return
    enc = spec.get("encoding")
    if isinstance(enc, dict) and encoding_key in enc:
        ek = enc[encoding_key]
        if isinstance(ek, dict):
            axis = ek.setdefault("axis", {})
            if isinstance(axis, dict):
                axis["labels"] = False
    for child_key in ("layer", "hconcat", "vconcat", "concat"):
        children = spec.get(child_key)
        if isinstance(children, list):
            for child in children:
                _strip_axis_labels_from_spec(child, encoding_key)


def _strip_axis_title_from_spec(
    spec: Dict[str, Any], encoding_key: str,
) -> None:
    """Drop the axis title from ``encoding[encoding_key].axis``."""
    if not isinstance(spec, dict):
        return
    enc = spec.get("encoding")
    if isinstance(enc, dict) and encoding_key in enc:
        ek = enc[encoding_key]
        if isinstance(ek, dict):
            axis = ek.setdefault("axis", {})
            if isinstance(axis, dict):
                axis["title"] = None
            # Also strip the redundant top-level title= on the encoding
            # itself (Vega-Lite has BOTH places it can land).
            if "title" in ek:
                ek["title"] = None
    for child_key in ("layer", "hconcat", "vconcat", "concat"):
        children = spec.get(child_key)
        if isinstance(children, list):
            for child in children:
                _strip_axis_title_from_spec(child, encoding_key)


def _strip_legend_from_spec(spec: Dict[str, Any]) -> None:
    """Suppress the color/strokeDash legend from a panel spec.

    Used when ``share_color=True`` so the composite-level legend renders
    once instead of per-panel.
    """
    if not isinstance(spec, dict):
        return
    enc = spec.get("encoding")
    if isinstance(enc, dict):
        for ek_name in ("color", "strokeDash", "shape", "stroke"):
            ek = enc.get(ek_name)
            if isinstance(ek, dict):
                ek["legend"] = None
    for child_key in ("layer", "hconcat", "vconcat", "concat"):
        children = spec.get(child_key)
        if isinstance(children, list):
            for child in children:
                _strip_legend_from_spec(child)


def _build_facet_gradient_legend_panel(
    color_field: str,
    color_min: Any, color_max: Any,
    color_type: str,
    scheme: str,
    width: int,
    scale_spec: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Horizontal gradient color bar for facet+gradient mode.

    Builds a single composite-level legend showing the continuous color
    scale (e.g. dates from earliest to latest). Replaces the per-panel
    gradient legends that would otherwise pollute every facet cell.
    Renders as a 200-step rect grid stretched across the composite
    width with axis labels at evenly-spaced ticks. Height is fixed at
    52px so the legend bar reads as a "scale strip" rather than a
    full chart.
    """
    if color_min is None or color_max is None:
        return None

    n_steps = 200
    if color_type == "temporal":
        try:
            t_min = pd.Timestamp(color_min)
            t_max = pd.Timestamp(color_max)
        except Exception:  # noqa: BLE001
            return None
        if t_min >= t_max:
            return None
        steps = pd.date_range(t_min, t_max, periods=n_steps + 1)
        x1_vals = [v.isoformat() for v in steps[:-1]]
        x2_vals = [v.isoformat() for v in steps[1:]]
        midpoints = [
            (steps[i] + (steps[i + 1] - steps[i]) / 2).isoformat()
            for i in range(n_steps)
        ]
        encoding_type = "T"
    else:
        try:
            v_min = float(color_min)
            v_max = float(color_max)
        except Exception:  # noqa: BLE001
            return None
        if v_min >= v_max:
            return None
        edges = np.linspace(v_min, v_max, n_steps + 1)
        x1_vals = list(edges[:-1])
        x2_vals = list(edges[1:])
        midpoints = [(edges[i] + edges[i + 1]) / 2 for i in range(n_steps)]
        encoding_type = "Q"

    color_scale = scale_spec if scale_spec is not None else {"scheme": scheme}
    if _scatter_gradient_scale_uses_norm(scale_spec):
        color_values = [(i + 0.5) / n_steps for i in range(n_steps)]
        color_encoding_type = "Q"
    else:
        color_values = midpoints
        color_encoding_type = encoding_type

    spec: Dict[str, Any] = {
        "data": {
            "values": [
                {"_x1": x1_vals[i], "_x2": x2_vals[i], "_c": color_values[i]}
                for i in range(n_steps)
            ]
        },
        "mark": {"type": "rect", "stroke": None},
        "encoding": {
            "x": {
                "field": "_x1", "type": encoding_type,
                "axis": {
                    "title": color_field,
                    "labelFontSize": 24,
                    "titleFontSize": 22,
                    "labelFontWeight": "normal",
                    "titleFontWeight": "normal",
                    "tickCount": 5,
                    "grid": False,
                },
            },
            "x2": {"field": "_x2", "type": encoding_type},
            "color": {
                "field": "_c", "type": color_encoding_type,
                "scale": color_scale,
                "legend": None,
            },
        },
        "width": width,
        "height": 24,
    }
    return spec


def _build_facet_legend_panel(
    color_domain: List[Any],
    skin_config: Dict[str, Any],
    width: int,
) -> Optional[Dict[str, Any]]:
    """Build a stand-alone tiny chart whose only render is a color legend.

    Returns a Vega-Lite spec dict suitable for vconcat-ing under the
    facet grid as the single shared legend. Width-sized to match the
    composite grid width.
    """
    if not color_domain:
        return None
    # Build a one-row dataset with one entry per color domain value so
    # Altair renders a categorical legend.
    legend_df = pd.DataFrame({
        "_legend_label": [str(v) for v in color_domain],
        "_legend_y": [0] * len(color_domain),
    })
    legend = (
        alt.Chart(legend_df)
        .mark_point(size=80, filled=True)
        .encode(
            x=alt.X(
                "_legend_label:N",
                axis=alt.Axis(
                    title=None,
                    labelFontSize=10,
                    labelPadding=4,
                    domain=False,
                    ticks=False,
                ),
                sort=list(legend_df["_legend_label"]),
            ),
            y=alt.Y(
                "_legend_y:Q",
                axis=None,
                scale=alt.Scale(domain=[-0.5, 0.5]),
            ),
            color=alt.Color(
                "_legend_label:N",
                legend=None,
                sort=list(legend_df["_legend_label"]),
            ),
        )
        .properties(width=width, height=28)
    )
    return legend.to_dict()


def _compose_facet_grid(
    panel_specs: List[Dict[str, Any]],
    rows: int, cols: int, spacing: int,
) -> Dict[str, Any]:
    """Lay out a list of per-panel Vega-Lite spec dicts in an NxM grid.

    Pads trailing cells with invisible blank specs so the grid stays
    rectangular when ``len(panel_specs) < rows * cols``.

    Returns a top-level Vega-Lite spec with ``vconcat`` of ``hconcat``
    rows. The caller is responsible for adding a top-level title /
    config / schema.
    """
    n = len(panel_specs)
    n_cells = rows * cols

    # Use the first panel's width/height as the blank-cell footprint so
    # the rectangular grid stays aligned.
    blank_w = 280
    blank_h = 220
    if panel_specs:
        first = panel_specs[0]
        if isinstance(first.get("width"), int):
            blank_w = int(first["width"])
        if isinstance(first.get("height"), int):
            blank_h = int(first["height"])

    cells: List[Dict[str, Any]] = list(panel_specs)
    while len(cells) < n_cells:
        cells.append({
            "data": {"values": [{"_blank": 0}]},
            "mark": {"type": "point", "opacity": 0},
            "width": blank_w, "height": blank_h,
        })

    rows_specs: List[Dict[str, Any]] = []
    for r in range(rows):
        row_cells = cells[r * cols:(r + 1) * cols]
        # Each row is an hconcat with independent scales/legends.
        row_spec = {
            "hconcat": row_cells,
            "spacing": spacing,
            "resolve": {
                "scale": {
                    "color": "independent",
                    "x": "independent",
                    "y": "independent",
                },
                "legend": {"color": "independent"},
            },
        }
        rows_specs.append(row_spec)

    composed = {
        "vconcat": rows_specs,
        "spacing": spacing,
        "resolve": {
            "scale": {
                "color": "independent",
                "x": "independent",
                "y": "independent",
            },
            "legend": {"color": "independent"},
        },
    }
    return composed


def _strip_schema_and_config(spec: Dict[str, Any]) -> None:
    """Strip ``$schema`` and ``config`` from a per-panel spec, in place.

    Vega-Lite 4.x rejects these inside ``hconcat`` / ``vconcat`` -- they
    must live exactly once at the top level. ``_build_single_chart``
    already does this for ChartSpec-driven composites; the facet path
    builds panels through a slightly different code path (it goes via
    a synthesised ChartSpec-equivalent flow) so we re-strip defensively.
    """
    spec.pop("$schema", None)
    spec.pop("config", None)


def _inline_named_datasets_in_spec(spec: Dict[str, Any]) -> None:
    """Resolve ``data: {name: X}`` references against ``spec.datasets``.

    Vega-Lite only honours a ``datasets`` block at the TOP LEVEL of a
    spec; per-cell ``datasets`` inside ``hconcat`` / ``vconcat`` are
    silently ignored, so any cell whose ``data`` is a name reference
    renders empty. ``_build_single_chart`` already inlines-and-strips
    on its first to_dict round-trip, but Altair re-serializes named
    datasets when the rebuilt chart's ``.to_dict()`` is called again
    inside the facet path -- so the facet code does the same fix-up
    once more on each panel before composing.

    Walks every nested layer / hconcat / vconcat. Mutates ``spec`` in
    place: pops ``datasets`` and rewrites every ``data: {name: ...}``
    that names a known dataset to ``data: {values: [...]}``.
    """
    if not isinstance(spec, dict):
        return
    datasets = spec.pop("datasets", None)
    if not datasets:
        return

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            d = node.get("data")
            if (
                isinstance(d, dict)
                and "name" in d
                and "values" not in d
            ):
                ds_name = d["name"]
                if ds_name in datasets:
                    node["data"] = {"values": datasets[ds_name]}
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(spec)


def _render_facet_grid(
    df: pd.DataFrame,
    chart_type: str,
    mapping: Dict[str, Any],
    *,
    title: Optional[str],
    subtitle: Optional[str],
    skin: str,
    intent: str,
    dimensions: Optional[str],
    annotations: Optional[List[Annotation]],
    output_dir: str,
    filename_prefix: Optional[str],
    filename_suffix: Optional[str],
    session_path: Optional[str],
    s3_manager: Any,
    save_as: Optional[str],
    interactive: bool,
    auto_beautify: bool,
    layers: Optional[List[Dict[str, Any]]],
    user_id: Optional[str],
    facet_cols: Optional[int],
    share_x: bool,
    share_y: bool,
    share_color: bool,
    edge_only_ticks: bool,
    edge_only_axis_titles: bool,
) -> ChartResult:
    """Build a facet (small-multiples) grid and return a ChartResult.

    See ``make_chart`` for the public API. This function is the engine
    behind ``mapping['facet']`` mode.
    """
    warnings_list: List[str] = []

    # ---- Validate chart_type is allowed ---------------------------------
    if chart_type not in _FACET_VALID_CHART_TYPES:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=(
                f"chart_type {chart_type!r} does not support mapping['facet']. "
                f"Valid: {sorted(_FACET_VALID_CHART_TYPES)}. "
                f"For matrix-shaped data, drop facet and use chart_type="
                f"'heatmap'. For donut / boxplot / bullet / waterfall, "
                f"the natural expression is a single canvas."
            ),
        )

    facet_col = mapping.get("facet")
    if not facet_col or facet_col not in df.columns:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=(
                f"mapping['facet']={facet_col!r} is not a column in df. "
                f"Available columns: {list(df.columns)}."
            ),
        )

    # ---- Resolve panel order, count, grid shape -------------------------
    explicit_facet_order = mapping.get("facet_order")
    if explicit_facet_order is not None and not isinstance(
        explicit_facet_order, (list, tuple)
    ):
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=(
                f"mapping['facet_order'] must be a list of panel ids; "
                f"got {type(explicit_facet_order).__name__}."
            ),
        )
    try:
        panel_order = _get_facet_panel_order(
            df, facet_col,
            explicit_order=list(explicit_facet_order)
            if explicit_facet_order is not None else None,
        )
    except ValidationError as exc:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=str(exc),
        )
    n_panels = len(panel_order)

    if n_panels < _FACET_MIN_PANELS:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=(
                f"Facet grid requires at least {_FACET_MIN_PANELS} panels; "
                f"got {n_panels}. For fewer comparisons use "
                f"make_2pack_horizontal, make_2pack_vertical, "
                f"make_4pack_grid, or make_6pack_grid (composites "
                f"support up to 6 panels)."
            ),
        )

    if n_panels > _FACET_HARD_CAP:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=(
                f"Facet grid would render {n_panels} panels, exceeding the "
                f"hard cap of {_FACET_HARD_CAP} (6x6). At this size per-panel "
                f"readability collapses. Aggregate to group level (e.g. "
                f"region instead of country) or switch to chart_type="
                f"'heatmap' for a single dense canvas."
            ),
        )
    if n_panels >= _FACET_SOFT_WARN_THRESHOLD:
        warnings_list.append(
            f"Facet grid has {n_panels} panels (>= {_FACET_SOFT_WARN_THRESHOLD}); "
            f"per-panel readability is tight. Consider aggregating to a "
            f"smaller set of panels or using a heatmap."
        )

    rows, cols = _resolve_facet_grid_shape(n_panels, facet_cols)

    # ---- Resolve per-panel dimensions -----------------------------------
    spacing = _FACET_DEFAULT_SPACING
    panel_w, panel_h = _resolve_facet_panel_dims(rows, cols, dimensions, spacing)

    # ---- Drop facet from per-panel mapping (each panel is one panel id)
    panel_mapping = dict(mapping)
    panel_mapping.pop("facet", None)

    # Strip LVL annotations at the grid level; per-panel build also
    # passes ``suppress_lvl=True`` so auto-injection is off.
    annotations = _strip_lvl_annotations(annotations)

    # Histogram facets always share x (also enforced at make_chart dispatch).
    if chart_type == "histogram":
        share_x = True

    # ---- Compute shared scales (if requested) ---------------------------
    # Field resolution: x, y, color come from mapping. ``y`` may be a list
    # for auto-melt -- we run auto-melt locally so subsequent shared-scale
    # calcs see the long-form column.
    x_field = mapping.get("x")
    y_field = mapping.get("y")
    color_field = mapping.get("color")

    # Pre-melt the WHOLE df so shared scales see the same long-form
    # the per-panel build will. This mirrors make_chart's standard flow.
    if chart_type in {"multi_line", "area"} and isinstance(y_field, list):
        try:
            df, panel_mapping = _auto_melt_for_multiline(df, panel_mapping)
            # Refresh field handles after melt.
            x_field = panel_mapping.get("x")
            y_field = panel_mapping.get("y")
            color_field = panel_mapping.get("color")
        except ValidationError as exc:
            return ChartResult(
                chart_type=chart_type, skin=skin, success=False,
                error_message=f"Auto-melt failed: {exc}",
                warnings=warnings_list,
            )

    # Sanitize column names once on the parent df so panel splits inherit
    # the safe names.
    df, panel_mapping = _sanitize_column_names(df, panel_mapping)
    # Re-resolve fields against the sanitised mapping.
    x_field = panel_mapping.get("x")
    y_field = panel_mapping.get("y")
    color_field = panel_mapping.get("color")
    facet_col = panel_mapping.get("facet", facet_col)

    shared_y_domain: Optional[List[float]] = None
    shared_x_domain_temporal: Optional[List[str]] = None
    shared_x_domain_numeric: Optional[List[float]] = None
    shared_color_domain: Optional[List[Any]] = None

    if share_y and isinstance(y_field, str):
        shared_y_domain = _compute_shared_numeric_domain(df, y_field)
    if share_x and isinstance(x_field, str):
        if pd.api.types.is_datetime64_any_dtype(df.get(x_field, pd.Series([]))):
            shared_x_domain_temporal = _compute_shared_temporal_domain(df, x_field)
        else:
            shared_x_domain_numeric = _compute_shared_numeric_domain(df, x_field)
    if share_color and isinstance(color_field, str):
        shared_color_domain = _compute_shared_color_domain(df, color_field)

    # Facet histograms: one bin extent across all panels so x-axes align.
    if chart_type == "histogram" and share_x and isinstance(x_field, str):
        facet_hist_extent = _compute_shared_numeric_domain(
            df, x_field, padding_frac=0.02,
        )
        if facet_hist_extent:
            panel_mapping["_histogram_bin_extent"] = facet_hist_extent

    # ---- Build skin config ---------------------------------------------
    if skin not in AVAILABLE_SKINS:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=(
                f"Unknown skin {skin!r}. Available: {list(AVAILABLE_SKINS.keys())}"
            ),
            warnings=warnings_list,
        )
    skin_config = get_skin(skin, intent)

    # ---- Build each panel (uses _build_single_chart for parity) ---------
    panel_specs: List[Dict[str, Any]] = []
    panel_errors: List[Dict[str, Any]] = []

    for idx, panel_id in enumerate(panel_order):
        sub_df = df[df[facet_col] == panel_id].copy()
        if len(sub_df) == 0:
            panel_errors.append({
                "panel_index": idx, "panel_id": panel_id,
                "error": "empty sub-df",
            })
            continue

        # Build a synthesised ChartSpec for this panel. Per-panel title
        # is the panel id stringified (short -- "US", "Canada", etc.).
        sub_mapping = dict(panel_mapping)
        sub_mapping.pop("facet", None)
        if chart_type == "bar":
            sub_mapping["_facet_panel"] = True

        sub_spec = ChartSpec(
            df=sub_df,
            chart_type=chart_type,
            mapping=sub_mapping,
            title=str(panel_id),
            subtitle=None,
            annotations=annotations,
            layers=layers,
        )

        try:
            chart = _build_single_chart(
                sub_spec, skin_config, panel_w, panel_h,
                title_fontsize_override=26,
                suppress_lvl=True,
            )
        except Exception as exc:  # noqa: BLE001
            panel_errors.append({
                "panel_index": idx, "panel_id": panel_id,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            })
            warnings_list.append(
                f"Panel {idx + 1} ({panel_id!r}) failed: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        spec_dict = chart.to_dict()
        _strip_schema_and_config(spec_dict)
        _inline_named_datasets_in_spec(spec_dict)

        # ---- Strip y-axis title when it's redundant --------------------
        # Time-series / bar / area: every panel's y is the SAME metric
        # (the composite title carries it). Per-panel y-titles are
        # redundant clutter and steal horizontal pixels from the plot.
        #
        # Scatter / scatter_multi: x and y describe DIFFERENT variables
        # (e.g. CPI vs GDP) -- the y-title is needed so the reader knows
        # which axis is which. Keep it.
        if chart_type not in {"scatter", "scatter_multi"}:
            _strip_axis_title_from_spec(spec_dict, "y")

        # ---- Always strip per-panel legends in facet mode ---------------
        # Categorical legends repeat across panels (redundant); gradient
        # legends are self-evident from the data ordering. When
        # ``share_color=True`` and the color is categorical, a single
        # shared legend is rebuilt at the composite level (see below).
        # For gradient color, no legend is added.
        _strip_legend_from_spec(spec_dict)

        # ---- Apply shared-scale injections ------------------------------
        if shared_y_domain is not None:
            _inject_scale_domain_into_spec(spec_dict, "y", shared_y_domain)
        if shared_x_domain_temporal is not None:
            _inject_scale_domain_into_spec(
                spec_dict, "x", shared_x_domain_temporal,
            )
        elif shared_x_domain_numeric is not None:
            _inject_scale_domain_into_spec(
                spec_dict, "x", shared_x_domain_numeric,
            )
        if shared_color_domain is not None:
            _inject_scale_domain_into_spec(
                spec_dict, "color", shared_color_domain,
            )

        # ---- Apply edge-only chrome reductions --------------------------
        row_idx = idx // cols
        col_idx = idx % cols
        is_bottom_row = (row_idx == rows - 1) or (idx + cols >= n_panels)
        is_left_col = (col_idx == 0)

        if edge_only_ticks:
            if not is_bottom_row:
                _strip_axis_labels_from_spec(spec_dict, "x")
            if not is_left_col:
                _strip_axis_labels_from_spec(spec_dict, "y")

        if edge_only_axis_titles:
            if not is_bottom_row:
                _strip_axis_title_from_spec(spec_dict, "x")
            if not is_left_col:
                _strip_axis_title_from_spec(spec_dict, "y")

        # Force per-panel width/height onto the top-level spec so the
        # grid cells stay rectangular.
        spec_dict["width"] = panel_w
        spec_dict["height"] = panel_h

        panel_specs.append(spec_dict)

    if not panel_specs:
        return ChartResult(
            chart_type=chart_type, skin=skin, success=False,
            error_message=(
                f"All {n_panels} facet panels failed to build. "
                f"First error: {panel_errors[0] if panel_errors else 'unknown'}"
            ),
            warnings=warnings_list,
        )

    # ---- Compose the grid ----------------------------------------------
    composite_spec = _compose_facet_grid(panel_specs, rows, cols, spacing)

    # ---- Shared-color legend panel under the grid ----------------------
    # CATEGORICAL color (when share_color=True): horizontal strip with one
    #   labelled point per category.
    # GRADIENT color (temporal / numeric, always when set on a scatter):
    #   continuous gradient bar showing the date / value range.
    # No-color: nothing.
    composite_outer_w = cols * panel_w + max(0, cols - 1) * spacing
    color_is_gradient = False
    color_is_temporal = False
    if color_field and color_field in df.columns:
        c_series = df[color_field]
        color_is_temporal = pd.api.types.is_datetime64_any_dtype(c_series)
        color_is_numeric = (
            pd.api.types.is_numeric_dtype(c_series)
            and not pd.api.types.is_bool_dtype(c_series)
        )
        color_is_gradient = color_is_temporal or color_is_numeric

    if color_is_gradient and color_field:
        c_series = df[color_field]
        gradient_scheme = panel_mapping.get("color_scheme", "viridis")
        if color_is_temporal:
            c_min = c_series.min()
            c_max = c_series.max()
        else:
            c_vals = pd.to_numeric(c_series, errors="coerce").dropna()
            c_min = float(c_vals.min()) if len(c_vals) else None
            c_max = float(c_vals.max()) if len(c_vals) else None
        gradient_spec = _build_facet_gradient_legend_panel(
            color_field=color_field,
            color_min=c_min, color_max=c_max,
            color_type="temporal" if color_is_temporal else "quantitative",
            scheme=gradient_scheme,
            width=composite_outer_w,
            scale_spec=_scatter_gradient_scale_spec(panel_mapping),
        )
        if gradient_spec:
            _strip_schema_and_config(gradient_spec)
            composite_spec["vconcat"].append(gradient_spec)
    elif share_color and shared_color_domain:
        legend_spec = _build_facet_legend_panel(
            shared_color_domain, skin_config,
            width=composite_outer_w,
        )
        if legend_spec:
            _strip_schema_and_config(legend_spec)
            composite_spec["vconcat"].append(legend_spec)

    # ---- Top-level title / config / schema ------------------------------
    composite_spec["$schema"] = "https://vega.github.io/schema/vega-lite/v5.json"
    composite_spec["config"] = skin_config.get("config", {})

    composite_outer_h = rows * panel_h + max(0, rows - 1) * spacing

    if title or subtitle:
        try:
            title_lines = _validate_and_wrap_text(
                title, slot_kind="composite_super_title",
                width_px=composite_outer_w,
                slot_label="facet grid title",
                widening_hint=(
                    "use a smaller facet_cols or aggregate to fewer panels"
                ),
            )
            subtitle_lines = _validate_and_wrap_text(
                subtitle, slot_kind="composite_super_subtitle",
                width_px=composite_outer_w,
                slot_label="facet grid subtitle",
                widening_hint=(
                    "use a smaller facet_cols or aggregate to fewer panels"
                ),
            )
        except ValueError as exc:
            return ChartResult(
                chart_type=chart_type, skin=skin, success=False,
                error_message=str(exc), warnings=warnings_list,
            )
        title_block = _title_dict_from_lines(
            title_lines,
            width_px=composite_outer_w,
            subtitle_lines=subtitle_lines,
            anchor="start",
            fontSize=38,
            fontWeight="bold",
        )
        if subtitle_lines:
            title_block["subtitleFontSize"] = 22
        composite_spec["title"] = title_block

    # ---- Typography overrides (facet_grid preset: large labels, sparse ticks)
    typography_preset = "facet_grid"
    if auto_beautify:
        try:
            composite_spec = _apply_typography_overrides(
                composite_spec, typography_preset,
            )
        except Exception as exc:  # noqa: BLE001
            warnings_list.append(
                f"Typography overrides skipped (non-fatal): {exc}"
            )

    # ---- Filename + PNG output ------------------------------------------
    filename_base = _generate_filename(
        title, f"{chart_type}_facet", filename_prefix, filename_suffix,
    )
    if save_as:
        # Passthrough: if save_as is already rooted at a canonical S3
        # prefix, honour it exactly. Mirrors _tbl_resolve_path() and
        # matches s3_manager.put() / save_artifact(output_path=...)
        # behavior so PRISM can pass either a leaf filename or a
        # fully-rooted path without producing double-nested paths.
        if save_as.startswith(_PASSTHROUGH_PREFIXES):
            png_path = save_as
        else:
            png_path = (
                f"{session_path}/{save_as}" if session_path else save_as
            )
    else:
        if session_path:
            png_path = f"{session_path}/{filename_base}.png"
        else:
            png_path = (
                os.path.join(output_dir, f"{filename_base}.png")
                if output_dir
                else f"{filename_base}.png"
            )

    png_save_failed = False
    png_error_message = ""
    download_url: Optional[str] = None
    try:
        png_bytes = _render_chart_to_png(composite_spec, scale=2.0)
        s3_manager.put(png_bytes, png_path)
    except Exception as exc:  # noqa: BLE001
        png_save_failed = True
        png_error_message = str(exc)
        png_path = None
        warnings_list.append(f"PNG export failed: {png_error_message}")

    if png_path and not png_save_failed:
        try:
            download_url = generate_presigned_download_url(png_path).presigned_url
        except Exception as exc:  # noqa: BLE001
            warnings_list.append(f"Failed to generate PNG download URL: {exc}")

    return ChartResult(
        png_path=png_path,
        download_url=download_url,
        vegalite_json=composite_spec,
        chart_type=f"{chart_type}_facet",
        skin=skin,
        success=not png_save_failed,
        error_message=(
            f"PNG export unavailable: {png_error_message}" if png_save_failed
            else None
        ),
        warnings=warnings_list,
        interactive=False,
    )


def _resolve_composite_aliases(
    *,
    dimensions: Optional[str],
    dimension_preset: Optional[str],
    side_left: Union[str, Dict[str, Any], None],
    narrative_left: Union[str, Dict[str, Any], None],
    side_right: Union[str, Dict[str, Any], None],
    narrative_right: Union[str, Dict[str, Any], None],
) -> Tuple[
    Optional[str],
    Union[str, Dict[str, Any], None],
    Union[str, Dict[str, Any], None],
    List[str],
]:
    """Resolve composite kwarg aliases to single canonical values.

    The composite functions accept BOTH the make_chart-style canonical
    names (``dimensions``, ``side_left``, ``side_right``) AND their
    composite-specific legacy names (``dimension_preset``,
    ``narrative_left``, ``narrative_right``). Canonical wins when both
    are passed and a warning is emitted so the caller sees the conflict.
    """
    alias_warnings: List[str] = []
    if dimensions is not None and dimension_preset is not None:
        alias_warnings.append(
            "Both `dimensions=` and `dimension_preset=` were passed; "
            "`dimensions=` (canonical) wins. Drop `dimension_preset=`."
        )
    if side_left is not None and narrative_left is not None:
        alias_warnings.append(
            "Both `side_left=` and `narrative_left=` were passed; "
            "`side_left=` (canonical) wins. Drop `narrative_left=`."
        )
    if side_right is not None and narrative_right is not None:
        alias_warnings.append(
            "Both `side_right=` and `narrative_right=` were passed; "
            "`side_right=` (canonical) wins. Drop `narrative_right=`."
        )
    resolved_dim = dimensions if dimensions is not None else dimension_preset
    resolved_left = side_left if side_left is not None else narrative_left
    resolved_right = side_right if side_right is not None else narrative_right
    return resolved_dim, resolved_left, resolved_right, alias_warnings


def _summarize_chart_errors(
    chart_errors: List[Dict[str, Any]], n_charts: int
) -> str:
    """Roll per-sub-chart failures up into a self-sufficient top-level message.

    Composites collect each cell's failure in ``chart_errors[i]``; the
    top-level ``error_message`` used to be a generic
    ``"All sub-charts failed validation."`` that forced the caller to unpack
    ``chart_errors`` to learn the actual cause. This folds the per-cell
    causes into the headline string (deduping identical errors so a 4-pack
    that all hit the same gate reads as one line, not four).
    """
    if not chart_errors:
        return "All sub-charts failed validation."
    header = f"All {n_charts} sub-charts failed validation"
    distinct = {(ce.get("error_message") or "").strip() for ce in chart_errors}
    if len(distinct) == 1:
        only = next(iter(distinct))
        return f"{header} -- every cell raised the same error: {only}"
    lines = [
        f"  [{ce.get('chart_index')}] ({ce.get('chart_type')}) "
        f"{(ce.get('error_message') or '').strip()}"
        for ce in chart_errors
    ]
    return header + ":\n" + "\n".join(lines)


def make_composite(
    charts: List[ChartSpec],
    layout: LayoutType,
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    skin: str = "gs_clean",
    dimensions: Optional[DimensionPreset] = None,
    dimension_preset: DimensionPreset = "compact",
    output_dir: str = "",
    filename_prefix: Optional[str] = None,
    filename_suffix: Optional[str] = None,
    spacing: int = 20,
    interactive: bool = True,
    session_path: Optional[str] = None,
    s3_manager: Optional[Any] = None,
    save_as: Optional[str] = None,
    user_id: Optional[str] = None,
    caption: Union[str, Dict[str, Any], None] = None,
    side_left: Union[str, Dict[str, Any], None] = None,
    narrative_left: Union[str, Dict[str, Any], None] = None,
    side_right: Union[str, Dict[str, Any], None] = None,
    narrative_right: Union[str, Dict[str, Any], None] = None,
) -> CompositeResult:
    """Generic composite entry point used by all ``make_Npack_*`` wrappers.

    Builds each ``ChartSpec`` into an Altair chart, composes them via
    ``_compose_charts``, applies a top-level title/subtitle, renders to
    PNG via vl-convert, and (when ``session_path`` is set) uploads to
    S3 with a presigned URL. Per-sub-chart failures are collected in
    ``CompositeResult.chart_errors`` rather than aborting the whole
    composite; if at least 2 sub-charts succeed the layout is rendered
    with the survivors. With only 1 survivor the composite is downgraded
    to a single chart render.

    Composite-level text panels:
      ``caption`` sits below the entire pack (composite footer).
      ``side_left`` / ``side_right`` flank the whole pack (also
      accepted under the legacy aliases ``narrative_left`` /
      ``narrative_right``). Each accepts a string or a style dict
      (see ``make_chart``). Sub-chart-level text panels live on each
      ``ChartSpec`` instead.
    """
    warnings_list: List[str] = []
    dimension_preset, narrative_left, narrative_right, alias_warnings = (
        _resolve_composite_aliases(
            dimensions=dimensions,
            dimension_preset=dimension_preset,
            side_left=side_left,
            narrative_left=narrative_left,
            side_right=side_right,
            narrative_right=narrative_right,
        )
    )
    warnings_list.extend(alias_warnings)

    if layout not in (
        "2_horizontal", "2_vertical", "3_triangle", "3_inverted",
        "3_horizontal", "3_vertical", "4_grid", "4_horizontal",
        "4_vertical", "6_grid",
    ):
        return CompositeResult(
            png_path=None, layout=layout, n_charts=len(charts),
            success=False, error_message=f"Unknown layout: {layout}",
            skin=skin,
        )

    n_charts = len(charts)
    expected = _get_expected_chart_count(layout)
    if n_charts != expected:
        return CompositeResult(
            png_path=None, layout=layout, n_charts=n_charts,
            success=False,
            error_message=(
                f"Layout {layout!r} requires {expected} charts, got {n_charts}."
            ),
            skin=skin,
        )

    # Validate every cell is a ChartSpec BEFORE any spec-walking helper runs.
    # ``_composite_consensus_x_angle`` / ``_scan_text_panel_reserves`` read
    # ``spec.mapping`` / ``spec.df`` / ``spec.chart_type`` ahead of the per-cell
    # try/except, so a non-ChartSpec input (most commonly a ``CompositeResult``
    # from a nested ``make_*pack_*`` call) would otherwise surface as a raw
    # ``AttributeError`` from deep inside a helper instead of a typed,
    # actionable failure at the entry point.
    for i, spec in enumerate(charts):
        if not isinstance(spec, ChartSpec):
            got = type(spec).__name__
            nested_hint = (
                " Composites cannot be nested -- pass the underlying "
                "ChartSpecs to make_4pack_grid / make_6pack_grid instead of "
                "feeding one composite into another."
                if got == "CompositeResult" else ""
            )
            return CompositeResult(
                png_path=None, layout=layout, n_charts=n_charts,
                success=False,
                error_message=(
                    f"Composite cell {i + 1} is a {got}, but make_composite "
                    f"requires ChartSpec inputs. Build each panel with "
                    f"ChartSpec(df=..., chart_type=..., mapping=...)."
                    f"{nested_hint}"
                ),
                skin=skin,
            )

    skin_config = get_skin(skin, "explore")
    if s3_manager is None:
        raise ValueError(
            "make_composite() requires an s3_manager. PRISM injects one via "
            "the code sandbox; for local dev, instantiate "
            "ai_development.core.s3_bucket_manager.S3BucketManager and pass it "
            "explicitly."
        )

    layout_family = "_".join(layout.split("_", 2)[:2])
    layout_dims = COMPOSITE_DIMENSIONS.get(layout_family, COMPOSITE_DIMENSIONS["4_grid"])
    chart_width, chart_height = layout_dims.get(dimension_preset, (350, 280))

    # Pre-validate the composite super-title and super-subtitle so a
    # too-long string fails the whole composite fast (rather than
    # letting sub-chart building succeed and only blowing up when the
    # title is applied at the bottom of this function). The super-title
    # spans the widest row of the layout: ``cols * chart_width +
    # (cols - 1) * spacing``.
    super_title_lines: Optional[List[str]] = None
    super_subtitle_lines: Optional[List[str]] = None
    if title or subtitle:
        super_cols, _super_rows = _layout_grid_shape(layout, n_charts)
        super_title_width = (
            super_cols * chart_width + max(0, super_cols - 1) * spacing
        )
        try:
            super_title_lines = _validate_and_wrap_text(
                title, slot_kind="composite_super_title",
                width_px=super_title_width,
                slot_label="composite super-title",
                widening_hint=(
                    "use a wider dimension_preset (e.g. 'wide') so the "
                    "title row gets more horizontal pixels"
                ),
            )
            super_subtitle_lines = _validate_and_wrap_text(
                subtitle, slot_kind="composite_super_subtitle",
                width_px=super_title_width,
                slot_label="composite super-subtitle",
                widening_hint=(
                    "use a wider dimension_preset (e.g. 'wide')"
                ),
            )
        except ValueError as exc:
            return CompositeResult(
                png_path=None, layout=layout, n_charts=n_charts,
                success=False, error_message=str(exc),
                warnings=warnings_list, skin=skin,
            )

    # Pre-compute a consensus x-axis label rotation so every temporal
    # sub-chart shares the same tick angle. Without this, panels with
    # different time spans render with mismatched axes (one horizontal,
    # one diagonal) which looks unintentional.
    consensus_x_angle = _composite_consensus_x_angle(
        charts, chart_width, chart_height,
    )

    # Pre-compute uniform reserve dimensions for per-sub-chart text
    # panels. Without this, a 4-pack where one panel has a caption
    # and another has a side panel would render with mismatched outer
    # cell sizes, and the chart plot regions would not align across
    # the grid. The reserves equalize every cell to the maximum
    # caption-row height and side-panel widths observed across all
    # sub-charts; cells without a particular text panel get an
    # invisible placeholder of the corresponding size. Values are
    # ``None`` (no wrap triggered) when no sub-chart carries that
    # placement, so the no-text-panel composite path is unchanged.
    reserve_cap_h, reserve_left_w, reserve_right_w = _scan_text_panel_reserves(
        charts, chart_width,
    )
    reserve_cap_h_arg: Optional[int] = reserve_cap_h or None
    reserve_left_w_arg: Optional[int] = reserve_left_w or None
    reserve_right_w_arg: Optional[int] = reserve_right_w or None

    # Build each sub-chart, collecting errors.
    built: List[alt.Chart] = []
    chart_errors: List[Dict[str, Any]] = []
    for i, spec in enumerate(charts):
        chart_index = i + 1
        try:
            built.append(
                _build_single_chart(
                    spec, skin_config, chart_width, chart_height,
                    force_x_label_angle=consensus_x_angle,
                    reserve_caption_h=reserve_cap_h_arg,
                    reserve_side_left_w=reserve_left_w_arg,
                    reserve_side_right_w=reserve_right_w_arg,
                    suppress_lvl=False,
                )
            )
            logger.info(
                "[make_composite] Sub-chart %d/%d (%s) built.",
                chart_index, n_charts, spec.chart_type,
            )
        except Exception as exc:  # noqa: BLE001
            error_detail = {
                "chart_index": chart_index,
                "chart_type": spec.chart_type,
                "title": spec.title,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "df_shape": spec.df.shape if isinstance(spec.df, pd.DataFrame) else None,
            }
            chart_errors.append(error_detail)
            warnings_list.append(
                f"Sub-chart {chart_index} ({spec.chart_type}) failed: "
                f"{type(exc).__name__}: {exc}"
            )

    if not built:
        return CompositeResult(
            png_path=None, layout=layout, n_charts=n_charts,
            success=False,
            error_message=_summarize_chart_errors(chart_errors, n_charts),
            warnings=warnings_list, skin=skin, chart_errors=chart_errors,
        )

    # Survivors-only handling.
    #
    # Layout indexing in ``_compose_charts`` is positional (``charts[0]``,
    # ``charts[1]``, ...) and assumes the slot count matches the
    # original layout name. With partial survivors we have to downgrade
    # to a smaller layout that the survivor count can fill, otherwise
    # ``_compose_charts`` raises ``IndexError: list index out of range``
    # at ``charts[3]`` on a 4-grid with 3 survivors. Map by survivor
    # count, preserving horizontal-vs-vertical orientation where the
    # original layout expressed one. When the downgrade lands on a
    # smaller layout than survivor count (e.g. 5 of 6 -> 4_grid), trim
    # ``built`` to fit -- one extra survivor goes unrendered, but the
    # composite stays sound.
    composite_layout: Optional[str] = layout
    if len(built) < n_charts:
        composite_layout = _downgrade_layout_for_survivors(
            layout, len(built),
        )
        if composite_layout is None:
            warnings_list.append(
                f"Downgraded from {layout} composite to single chart "
                f"({len(built)} of {n_charts} sub-charts succeeded)."
            )
        else:
            slot_count = _LAYOUT_SLOT_COUNT.get(composite_layout, len(built))
            if slot_count < len(built):
                dropped = len(built) - slot_count
                built = built[:slot_count]
                warnings_list.append(
                    f"Removed {n_charts - len(built) - dropped} failed "
                    f"sub-chart(s) from composite ({layout} -> "
                    f"{composite_layout}) plus {dropped} successful "
                    f"sub-chart(s) trimmed to fit the downgraded "
                    f"layout's slot count."
                )
            else:
                warnings_list.append(
                    f"Removed {n_charts - len(built)} failed sub-chart(s) "
                    f"from composite ({layout} -> {composite_layout})."
                )

    has_dual_axis = any(
        isinstance(s, ChartSpec) and s.mapping.get("dual_axis_series")
        for s in charts
    )

    if composite_layout is None:
        composite = built[0]
    else:
        try:
            composite = _compose_charts(
                built, composite_layout, spacing=spacing,
                has_dual_axis=has_dual_axis,
            )
        except Exception as exc:  # noqa: BLE001
            return CompositeResult(
                png_path=None, layout=layout, n_charts=n_charts,
                success=False,
                error_message=f"Layout composition failed: {exc}",
                warnings=warnings_list, skin=skin, chart_errors=chart_errors,
            )

    # Top-level title. Uses the lines from the upfront-validated
    # super_title_lines / super_subtitle_lines so a wrapped title
    # renders as multi-line (Vega-Lite accepts a List[str] as a
    # multi-line title body) and a too-long title would have already
    # short-circuited above with CompositeResult(success=False).
    if super_title_lines:
        title_props = _title_dict_from_lines(
            super_title_lines,
            width_px=super_title_width,
            subtitle_lines=super_subtitle_lines,
            fontSize=32,
            font=skin_config.get(
                "font_family", "Liberation Sans, Arial, sans-serif",
            ),
            anchor="middle",
            offset=20,
        )
        if super_subtitle_lines:
            title_props["subtitleFontSize"] = 22
            title_props["subtitleColor"] = "#666666"
        composite = composite.properties(title=title_props)

    composite = composite.configure(**skin_config.get("config", {}))

    # Filename + render.
    filename_base = _generate_filename(
        title, f"{layout}_composite",
        filename_prefix, filename_suffix,
    )
    if save_as:
        # Passthrough: if save_as is already rooted at a canonical S3
        # prefix, honour it exactly (see make_chart for full rationale).
        if save_as.startswith(_PASSTHROUGH_PREFIXES):
            png_path = save_as
        else:
            png_path = (
                f"{session_path}/{save_as}" if session_path else save_as
            )
    elif session_path:
        png_path = f"{session_path}/{filename_base}.png"
    else:
        png_path = (
            os.path.join(output_dir, f"{filename_base}.png")
            if output_dir
            else f"{filename_base}.png"
        )

    spec_dict = composite.to_dict()

    # Composite-level text panels (caption / narrative_left / narrative_right).
    # Estimate the rendered composite's pixel footprint so the side
    # panels and caption sit at sensible widths. We approximate from the
    # per-sub-chart pixel size and the layout shape -- close enough for
    # font-budget purposes; Vega-Lite resolves the actual pixel layout
    # at render time.
    if (
        caption is not None
        or narrative_left is not None
        or narrative_right is not None
    ):
        n_cols, n_rows = _layout_grid_shape(layout, n_charts)
        composite_w = n_cols * chart_width + (n_cols - 1) * spacing
        composite_h = n_rows * chart_height + (n_rows - 1) * spacing
        try:
            spec_dict = _apply_text_panels_to_spec(
                spec_dict,
                chart_width=composite_w, chart_height=composite_h,
                caption=caption,
                side_left=narrative_left,
                side_right=narrative_right,
                skin_config=skin_config,
            )
        except Exception as exc:  # noqa: BLE001
            warnings_list.append(
                f"Composite text-panel wrap failed (non-fatal): {exc}"
            )

    download_url: Optional[str] = None
    png_save_failed = False
    png_error_message = ""
    try:
        png_bytes = _render_chart_to_png(spec_dict, scale=2.0)
        s3_manager.put(png_bytes, png_path)
    except Exception as exc:  # noqa: BLE001
        png_save_failed = True
        png_error_message = str(exc)
        png_path = None
        warnings_list.append(f"Composite PNG export failed: {png_error_message}")

    if png_path and not png_save_failed:
        try:
            download_url = generate_presigned_download_url(png_path).presigned_url
        except Exception as exc:  # noqa: BLE001
            warnings_list.append(f"Composite presigned URL failed: {exc}")

    return CompositeResult(
        png_path=png_path,
        layout=layout,
        n_charts=n_charts,
        success=not png_save_failed and not chart_errors,
        error_message=(
            f"PNG export unavailable: {png_error_message}"
            if png_save_failed
            else (
                f"{len(chart_errors)} sub-chart(s) failed to build"
                if chart_errors
                else None
            )
        ),
        warnings=warnings_list,
        download_url=download_url,
        vegalite_json=spec_dict,
        skin=skin,
        chart_errors=chart_errors,
    )


# ---------------------------------------------------------------------------
# Convenience wrappers for the common composite layouts
# ---------------------------------------------------------------------------

@_raise_on_failure
def make_2pack_horizontal(
    chart1: ChartSpec,
    chart2: ChartSpec,
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    skin: str = "gs_clean",
    dimensions: Optional[DimensionPreset] = None,
    dimension_preset: DimensionPreset = "compact",
    output_dir: str = "",
    filename_prefix: Optional[str] = None,
    filename_suffix: Optional[str] = None,
    spacing: int = 20,
    interactive: bool = True,
    session_path: Optional[str] = None,
    s3_manager: Optional[Any] = None,
    save_as: Optional[str] = None,
    user_id: Optional[str] = None,
    caption: Union[str, Dict[str, Any], None] = None,
    side_left: Union[str, Dict[str, Any], None] = None,
    narrative_left: Union[str, Dict[str, Any], None] = None,
    side_right: Union[str, Dict[str, Any], None] = None,
    narrative_right: Union[str, Dict[str, Any], None] = None,
) -> CompositeResult:
    """Two charts side-by-side. ``chart1`` is left, ``chart2`` is right."""
    return make_composite(
        [chart1, chart2],
        "2_horizontal",
        title=title, subtitle=subtitle, skin=skin,
        dimensions=dimensions, dimension_preset=dimension_preset,
        output_dir=output_dir,
        filename_prefix=filename_prefix, filename_suffix=filename_suffix,
        spacing=spacing, interactive=interactive,
        session_path=session_path, s3_manager=s3_manager,
        save_as=save_as, user_id=user_id,
        caption=caption,
        side_left=side_left, narrative_left=narrative_left,
        side_right=side_right, narrative_right=narrative_right,
    )


@_raise_on_failure
def make_2pack_vertical(
    chart1: ChartSpec,
    chart2: ChartSpec,
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    skin: str = "gs_clean",
    dimensions: Optional[DimensionPreset] = None,
    dimension_preset: DimensionPreset = "wide",
    output_dir: str = "",
    filename_prefix: Optional[str] = None,
    filename_suffix: Optional[str] = None,
    spacing: int = 20,
    interactive: bool = True,
    session_path: Optional[str] = None,
    s3_manager: Optional[Any] = None,
    save_as: Optional[str] = None,
    user_id: Optional[str] = None,
    caption: Union[str, Dict[str, Any], None] = None,
    side_left: Union[str, Dict[str, Any], None] = None,
    narrative_left: Union[str, Dict[str, Any], None] = None,
    side_right: Union[str, Dict[str, Any], None] = None,
    narrative_right: Union[str, Dict[str, Any], None] = None,
) -> CompositeResult:
    """Two charts stacked vertically. ``chart1`` is top, ``chart2`` is bottom."""
    return make_composite(
        [chart1, chart2],
        "2_vertical",
        title=title, subtitle=subtitle, skin=skin,
        dimensions=dimensions, dimension_preset=dimension_preset,
        output_dir=output_dir,
        filename_prefix=filename_prefix, filename_suffix=filename_suffix,
        spacing=spacing, interactive=interactive,
        session_path=session_path, s3_manager=s3_manager,
        save_as=save_as, user_id=user_id,
        caption=caption,
        side_left=side_left, narrative_left=narrative_left,
        side_right=side_right, narrative_right=narrative_right,
    )


@_raise_on_failure
def make_3pack_triangle(
    chart_top: ChartSpec,
    chart_bottom_left: ChartSpec,
    chart_bottom_right: ChartSpec,
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    skin: str = "gs_clean",
    dimensions: Optional[DimensionPreset] = None,
    dimension_preset: DimensionPreset = "compact",
    output_dir: str = "",
    filename_prefix: Optional[str] = None,
    filename_suffix: Optional[str] = None,
    spacing: int = 20,
    interactive: bool = True,
    session_path: Optional[str] = None,
    s3_manager: Optional[Any] = None,
    save_as: Optional[str] = None,
    user_id: Optional[str] = None,
    caption: Union[str, Dict[str, Any], None] = None,
    side_left: Union[str, Dict[str, Any], None] = None,
    narrative_left: Union[str, Dict[str, Any], None] = None,
    side_right: Union[str, Dict[str, Any], None] = None,
    narrative_right: Union[str, Dict[str, Any], None] = None,
) -> CompositeResult:
    """Three charts: one on top, two on bottom."""
    return make_composite(
        [chart_top, chart_bottom_left, chart_bottom_right],
        "3_triangle",
        title=title, subtitle=subtitle, skin=skin,
        dimensions=dimensions, dimension_preset=dimension_preset,
        output_dir=output_dir,
        filename_prefix=filename_prefix, filename_suffix=filename_suffix,
        spacing=spacing, interactive=interactive,
        session_path=session_path, s3_manager=s3_manager,
        save_as=save_as, user_id=user_id,
        caption=caption,
        side_left=side_left, narrative_left=narrative_left,
        side_right=side_right, narrative_right=narrative_right,
    )


@_raise_on_failure
def make_4pack_grid(
    chart_tl: ChartSpec,
    chart_tr: ChartSpec,
    chart_bl: ChartSpec,
    chart_br: ChartSpec,
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    skin: str = "gs_clean",
    dimensions: Optional[DimensionPreset] = None,
    dimension_preset: DimensionPreset = "compact",
    output_dir: str = "",
    filename_prefix: Optional[str] = None,
    filename_suffix: Optional[str] = None,
    spacing: int = 20,
    interactive: bool = True,
    session_path: Optional[str] = None,
    s3_manager: Optional[Any] = None,
    save_as: Optional[str] = None,
    user_id: Optional[str] = None,
    caption: Union[str, Dict[str, Any], None] = None,
    side_left: Union[str, Dict[str, Any], None] = None,
    narrative_left: Union[str, Dict[str, Any], None] = None,
    side_right: Union[str, Dict[str, Any], None] = None,
    narrative_right: Union[str, Dict[str, Any], None] = None,
) -> CompositeResult:
    """2x2 grid (top-left, top-right, bottom-left, bottom-right)."""
    return make_composite(
        [chart_tl, chart_tr, chart_bl, chart_br],
        "4_grid",
        title=title, subtitle=subtitle, skin=skin,
        dimensions=dimensions, dimension_preset=dimension_preset,
        output_dir=output_dir,
        filename_prefix=filename_prefix, filename_suffix=filename_suffix,
        spacing=spacing, interactive=interactive,
        session_path=session_path, s3_manager=s3_manager,
        save_as=save_as, user_id=user_id,
        caption=caption,
        side_left=side_left, narrative_left=narrative_left,
        side_right=side_right, narrative_right=narrative_right,
    )


@_raise_on_failure
def make_6pack_grid(
    chart_r1_l: Optional[ChartSpec] = None,
    chart_r1_r: Optional[ChartSpec] = None,
    chart_r2_l: Optional[ChartSpec] = None,
    chart_r2_r: Optional[ChartSpec] = None,
    chart_r3_l: Optional[ChartSpec] = None,
    chart_r3_r: Optional[ChartSpec] = None,
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    specs: Optional[List[ChartSpec]] = None,
    skin: str = "gs_clean",
    dimensions: Optional[DimensionPreset] = None,
    dimension_preset: DimensionPreset = "compact",
    output_dir: str = "",
    filename_prefix: Optional[str] = None,
    filename_suffix: Optional[str] = None,
    spacing: int = 20,
    interactive: bool = True,
    session_path: Optional[str] = None,
    s3_manager: Optional[Any] = None,
    save_as: Optional[str] = None,
    user_id: Optional[str] = None,
    caption: Union[str, Dict[str, Any], None] = None,
    side_left: Union[str, Dict[str, Any], None] = None,
    narrative_left: Union[str, Dict[str, Any], None] = None,
    side_right: Union[str, Dict[str, Any], None] = None,
    narrative_right: Union[str, Dict[str, Any], None] = None,
) -> CompositeResult:
    """3x2 grid (3 rows, 2 columns) of charts.

    Two calling conventions are supported:

      1. Positional ``ChartSpec`` per cell::

            make_6pack_grid(c1, c2, c3, c4, c5, c6, title="...")

      2. ``specs=[...]`` list-style (matches PRISM idiom)::

            make_6pack_grid(specs=[c1, c2, c3, c4, c5, c6], title="...")

    Pre-flight validation rejects empty DataFrames and y-fields with
    fewer than 2 valid values up-front (matches MD's COMPOSITE CHART
    ERROR pattern) so the failure surfaces with a meaningful message
    rather than after the layout has been built.
    """
    # Resolve the list-based calling pattern.
    if specs is not None:
        if len(specs) != 6:
            raise ValueError(
                f"specs must contain exactly 6 ChartSpec objects; got {len(specs)}"
            )
        chart_r1_l, chart_r1_r, chart_r2_l, chart_r2_r, chart_r3_l, chart_r3_r = specs

    charts = [chart_r1_l, chart_r1_r, chart_r2_l, chart_r2_r, chart_r3_l, chart_r3_r]
    if any(c is None for c in charts):
        raise ValueError(
            "make_6pack_grid: all 6 chart slots are required (positional or specs=)."
        )

    # Pre-flight validation -- fail fast with a useful message.
    chart_names = ["R1-Left", "R1-Right", "R2-Left", "R2-Right", "R3-Left", "R3-Right"]
    for spec, name in zip(charts, chart_names):
        if spec.df is None or len(spec.df) == 0:
            raise ValidationError(
                f"COMPOSITE CHART ERROR: Chart {name} ('{spec.title}') has empty "
                f"DataFrame. Cannot create 6-pack with empty charts."
            )
        y_field = spec.mapping.get("y")
        if (
            isinstance(y_field, str)
            and y_field in spec.df.columns
            and int(spec.df[y_field].notna().sum()) < 2
        ):
            valid_count = int(spec.df[y_field].notna().sum())
            raise ValidationError(
                f"COMPOSITE CHART ERROR: Chart {name} ('{spec.title}') has only "
                f"{valid_count} valid y-value(s). Need at least 2 points to render."
            )

    return make_composite(
        charts,
        "6_grid",
        title=title, subtitle=subtitle, skin=skin,
        dimensions=dimensions, dimension_preset=dimension_preset,
        output_dir=output_dir,
        filename_prefix=filename_prefix, filename_suffix=filename_suffix,
        spacing=spacing, interactive=interactive,
        session_path=session_path, s3_manager=s3_manager,
        save_as=save_as, user_id=user_id,
        caption=caption,
        side_left=side_left, narrative_left=narrative_left,
        side_right=side_right, narrative_right=narrative_right,
    )


# ===========================================================================
# MODULE: QUALITY GATE
# ===========================================================================

_QC_MAX_WORKERS = 8


def _qc_one(
    r: Any, s3_manager: Any,
) -> Dict[str, Any]:
    """QC a single result. Used as a worker by ``check_charts_quality``.

    Mirrors PRISM's ``_check_single`` inside ``check_charts_quality_parallel``:
    fail-open on infrastructure errors (S3 fetch, Gemini timeout); a
    real BAD verdict from ``check_chart_quality`` propagates through.
    """
    png_path = getattr(r, "png_path", None)
    success = getattr(r, "success", True)
    if not success or not png_path:
        err = getattr(r, "error_message", None)
        reason = (
            f"chart build failed: {err}" if err
            else "chart build failed: no png_path and no error_message on result"
        )
        return {
            "passed": False,
            "reason": reason,
            "png_path": png_path,
        }
    try:
        png_bytes = s3_manager.get(png_path)
        verdict = check_chart_quality(png_bytes)
        verdict.setdefault("png_path", png_path)
        return verdict
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[QualityGate] Quality check error (fail-open): %s -- %s",
            exc, png_path,
        )
        return {
            "passed": True,
            "reason": f"infra error (fail-open): {exc}",
            "png_path": png_path,
        }


def check_charts_quality(
    results: List[Any],
    s3_manager: Optional[Any] = None,
    max_workers: int = _QC_MAX_WORKERS,
) -> List[Dict[str, Any]]:
    """Run the chart-quality gate over a list of ``ChartResult`` /
    ``CompositeResult`` objects in parallel.

    For each result with a valid ``png_path``, fetches the PNG from S3
    and forwards it to ``check_chart_quality`` (PRISM: Gemini Flash;
    local: pass-through). Gemini calls are dispatched concurrently via
    ``ThreadPoolExecutor`` (default 8 workers, capped at chart count)
    so wall-clock time is one Gemini latency for up to 8 charts. This
    matches PRISM's ``check_charts_quality_parallel`` shape.

    Returns a list of ``{passed, reason, ...}`` dicts in the same order
    as ``results``.

    Fail-open: any infrastructure error (missing png, S3 failure,
    Gemini timeout) treats the chart as passing so a quality-gate
    outage doesn't suppress otherwise-fine charts.
    """
    if s3_manager is None:
        raise ValueError(
            "check_charts_quality() requires an s3_manager. PRISM injects one "
            "via the code sandbox; for local dev, instantiate "
            "ai_development.core.s3_bucket_manager.S3BucketManager and pass it "
            "explicitly."
        )

    n = len(results)
    if n == 0:
        return []

    out: List[Optional[Dict[str, Any]]] = [None] * n
    workers = max(1, min(max_workers, n))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(_qc_one, results[i], s3_manager): i for i in range(n)
        }
        for fut in concurrent.futures.as_completed(futures):
            idx = futures[fut]
            try:
                out[idx] = fut.result()
            except Exception as exc:  # noqa: BLE001 - belt-and-suspenders
                logger.warning(
                    "[QualityGate] worker %d crashed (fail-open): %s",
                    idx, exc,
                )
                out[idx] = {
                    "passed": True,
                    "reason": f"worker crash (fail-open): {exc}",
                    "png_path": getattr(results[idx], "png_path", None),
                }
    return [v if v is not None else {"passed": True, "reason": "no verdict"} for v in out]


# ===========================================================================
# MODULE: STATIC SPEC HELPERS (PNG export polish)
# ===========================================================================

def get_dimensions(preset: DimensionPreset) -> Tuple[int, int]:
    """Get the ``(width, height)`` tuple for a dimension preset name."""
    if preset not in DIMENSION_PRESETS:
        raise ValueError(
            f"Unknown dimension preset: {preset!r}. "
            f"Available: {list(DIMENSION_PRESETS.keys())}"
        )
    return DIMENSION_PRESETS[preset]


def list_dimension_presets() -> List[Dict[str, Any]]:
    """List all dimension presets with their pixel sizes."""
    return [
        {"name": name, "width": dims[0], "height": dims[1]}
        for name, dims in DIMENSION_PRESETS.items()
    ]


def _strip_param_expressions(obj: Dict[str, Any]) -> None:
    """Walk a Vega-Lite spec dict and remove ``{'expr': '...'}`` references
    on mark properties / scale domains so vl-convert can render the
    chart statically. Mutates in place.
    """
    if not isinstance(obj, dict):
        return

    obj.pop("params", None)

    if "mark" in obj and isinstance(obj["mark"], dict):
        mark = obj["mark"]
        for prop in (
            "strokeWidth", "opacity", "size", "cornerRadius",
            "innerRadius", "outerRadius", "padAngle", "fillOpacity",
        ):
            if isinstance(mark.get(prop), dict) and "expr" in mark[prop]:
                mark.pop(prop, None)

    if "encoding" in obj:
        for channel in ("x", "y", "color", "size"):
            enc = obj["encoding"].get(channel)
            if isinstance(enc, dict) and isinstance(enc.get("scale"), dict):
                scale = enc["scale"]
                for prop in ("domainMin", "domainMax"):
                    if isinstance(scale.get(prop), dict) and "expr" in scale[prop]:
                        scale.pop(prop, None)

    for key in ("hconcat", "vconcat", "concat", "layer"):
        if key in obj and isinstance(obj[key], list):
            for item in obj[key]:
                _strip_param_expressions(item)


def create_static_spec(
    spec: Dict[str, Any],
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    skin_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a static (non-interactive) version of a Vega-Lite spec for
    PNG rendering.

    Removes ``params`` definitions, replaces ``{'expr': ...}`` references
    on mark properties and scale domains with their default values, and
    -- when ``y_min`` / ``y_max`` are supplied -- pins the y-axis domain
    to those values. This is needed because ``vl-convert`` cannot
    resolve parameter expressions; without this, charts that include
    interactive sliders would render with unbound expression strings.

    Args:
        spec: The Vega-Lite spec dict (typically ``chart.to_dict()``).
        y_min / y_max: Optional explicit y-axis bounds to inject.
        skin_config: Used to source mark-property defaults (currently
            unused; kept for signature stability with PRISM's version).

    Returns:
        A new spec dict (deep-copied) with all expressions resolved.
    """
    static_spec = copy.deepcopy(spec)
    _strip_param_expressions(static_spec)

    if isinstance(static_spec.get("width"), dict) and "expr" in static_spec["width"]:
        static_spec["width"] = 600
    if isinstance(static_spec.get("height"), dict) and "expr" in static_spec["height"]:
        static_spec["height"] = 400

    # Optional: pin y-axis domain to (y_min, y_max).
    if y_min is not None and y_max is not None:
        def _set_y_domain(node: Dict[str, Any]) -> None:
            if not isinstance(node, dict):
                return
            if "encoding" in node and isinstance(node["encoding"], dict):
                y_enc = node["encoding"].get("y")
                if isinstance(y_enc, dict):
                    y_enc.setdefault("scale", {})
                    if isinstance(y_enc["scale"], dict):
                        y_enc["scale"]["domain"] = [y_min, y_max]
            for key in ("layer", "hconcat", "vconcat", "concat"):
                if key in node and isinstance(node[key], list):
                    for item in node[key]:
                        _set_y_domain(item)

        _set_y_domain(static_spec)

    return static_spec


def _inject_y_axis_domain(spec: Dict[str, Any]) -> None:
    """Inject Vega-Lite parameter-bound y-axis domain into a spec.

    Mutates in place. Adds ``scale.domainMin`` / ``scale.domainMax``
    expression bindings (``yDomainMin`` / ``yDomainMax`` parameter
    names) to every y-encoding in the spec, including layered
    sub-specs. This is the dynamic-scale-domain idiom used by the
    chart studio's "y range" interactive slider.

    The matching slider parameter is added at the top level by the
    studio wrap layer (``chart_functions_studio.wrap_interactive_prism``).
    """

    def _update_y_encoding(obj: Dict[str, Any]) -> None:
        if not isinstance(obj, dict):
            return
        if "encoding" in obj and "y" in obj["encoding"]:
            y_enc = obj["encoding"]["y"]
            if isinstance(y_enc, dict):
                y_enc.setdefault("scale", {})
                if isinstance(y_enc["scale"], dict):
                    y_enc["scale"]["domainMin"] = {"expr": "yDomainMin"}
                    y_enc["scale"]["domainMax"] = {"expr": "yDomainMax"}

    if "layer" in spec:
        for layer in spec["layer"]:
            _update_y_encoding(layer)
    else:
        _update_y_encoding(spec)


def clean_chart(obj: Dict[str, Any]) -> None:
    """Recursively clean a chart-or-concat spec for static PNG export.

    Mutates in place. Walks every level (``hconcat``, ``vconcat``,
    ``concat``, ``layer``) and:

      - Removes any ``params`` blocks (interactive sliders).
      - Drops mark-property expressions (``strokeWidth``, ``opacity``,
        ``size``, corner radii, ``innerRadius``, ``outerRadius``,
        ``padAngle``, ``fillOpacity``).
      - Drops scale-domain expressions (``domainMin`` / ``domainMax``).

    After this pass the spec is safe to feed to ``vl-convert`` for PNG
    rendering -- no unbound parameter expressions remain.
    """
    if not isinstance(obj, dict):
        return

    obj.pop("params", None)

    if "mark" in obj and isinstance(obj["mark"], dict):
        mark = obj["mark"]
        expr_props = {
            "strokeWidth", "opacity", "size", "cornerRadius",
            "innerRadius", "outerRadius", "padAngle", "fillOpacity",
        }
        for prop in expr_props:
            if isinstance(mark.get(prop), dict) and "expr" in mark[prop]:
                del mark[prop]

    if "encoding" in obj and isinstance(obj["encoding"], dict):
        for channel in ("x", "y", "color", "size"):
            enc = obj["encoding"].get(channel)
            if isinstance(enc, dict) and isinstance(enc.get("scale"), dict):
                scale = enc["scale"]
                for prop in ("domainMin", "domainMax"):
                    if isinstance(scale.get(prop), dict) and "expr" in scale[prop]:
                        del scale[prop]

    for key in ("hconcat", "vconcat", "concat", "layer"):
        if key in obj and isinstance(obj[key], list):
            for item in obj[key]:
                clean_chart(item)


def create_static_composite_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Create a static version of a composite spec for PNG export.

    Recurses into ``hconcat`` / ``vconcat`` / ``concat`` / ``layer``
    structures to strip interactive params at every level. Uses
    ``clean_chart`` for the recursive walk.
    """
    static_spec = copy.deepcopy(spec)
    static_spec.pop("params", None)

    if isinstance(static_spec.get("width"), dict) and "expr" in static_spec["width"]:
        static_spec["width"] = 600
    if isinstance(static_spec.get("height"), dict) and "expr" in static_spec["height"]:
        static_spec["height"] = 400
    if isinstance(static_spec.get("spacing"), dict) and "expr" in static_spec["spacing"]:
        static_spec["spacing"] = 20

    clean_chart(static_spec)
    return static_spec


# ===========================================================================
# MODULE: V2 API SURFACE (Chart class + render_grid)
# ===========================================================================
#
# Cleaner public surface that sits alongside the v1 surface
# (``make_chart``, ``ChartSpec``, ``make_2pack_*``,
# ``check_charts_quality``). Same rendering pipeline underneath -- the
# v2 functions translate flat kwargs into v1's ``mapping`` dict and
# delegate to ``make_chart`` / ``make_composite``. Chart output is
# byte-identical between the two APIs.
#
# Goals (vs v1):
#   * Single ``Chart`` class for both standalone and composite use
#     (replaces the ``make_chart`` + ``ChartSpec`` duality).
#   * Flat keyword arguments; no ``mapping={...}`` dict.
#   * One ``render_grid`` for composites (replaces 5 ``make_*pack_*``
#     wrappers).
#   * Auto QC + cleanup + URL printing absorbed into ``Chart.render`` /
#     ``render_grid`` -- the post-chart boilerplate disappears.
#   * ``s3_manager`` / ``session_path`` / ``user_id`` resolved from the
#     calling frame -- never threaded through call sites.
#
# Annotation primitives, ``ChartResult``, ``CompositeResult``,
# ``DataProfile``, ``profile_df`` are shared with v1 -- no duplication.

# --- Runtime context resolution -------------------------------------------
#
# PRISM injects ``s3_manager`` and ``SESSION_PATH`` (and optionally
# ``user_id``) as bindings in the script's execution namespace inside
# ``execute_analysis_script``. v1 forces the script to thread them
# through every ``make_chart`` / ``make_composite`` call. v2 walks the
# call stack at render time and picks them up automatically -- the
# script never has to mention them.
#
# Single resolution strategy, raises loudly on miss. There is no
# fallback chain.

_V2_SESSION_PATH_KEYS: Tuple[str, ...] = ("SESSION_PATH", "session_path")
_V2_USER_ID_KEYS: Tuple[str, ...] = ("user_id", "USER_ID")


@dataclass(frozen=True)
class _RuntimeContext:
    """Bundle of PRISM-injected runtime bindings consumed by v2."""

    s3_manager: Any
    session_path: str
    user_id: Optional[str]


def _resolve_runtime_context(start_depth: int = 2) -> _RuntimeContext:
    """Walk the call stack to find PRISM-injected runtime bindings.

    Searches each frame's ``f_locals`` then ``f_globals`` for the
    binding ``s3_manager``. When found, also pulls ``SESSION_PATH``
    (or lowercase ``session_path``) and ``user_id`` from the same
    frame so the three bindings come from the same logical scope.

    PRISM-side: every script ``execute_analysis_script`` runs has
    these injected into its exec namespace. The script's frame is
    typically two levels up from this function.

    Local-dev: demos / tests bind them in their own ``__main__`` /
    test scope before invoking ``Chart.render`` or ``render_grid``.

    Raises:
        RuntimeError: if no frame in the stack carries an
            ``s3_manager`` binding. The message points at the
            normal injection sites.
    """
    frame = sys._getframe(start_depth)
    while frame is not None:
        for ns in (frame.f_locals, frame.f_globals):
            s3 = ns.get("s3_manager")
            if s3 is not None:
                session_path = ""
                for key in _V2_SESSION_PATH_KEYS:
                    if key in ns and ns[key]:
                        session_path = ns[key]
                        break
                user_id: Optional[str] = None
                for key in _V2_USER_ID_KEYS:
                    if key in ns and ns[key]:
                        user_id = ns[key]
                        break
                return _RuntimeContext(
                    s3_manager=s3,
                    session_path=session_path,
                    user_id=user_id,
                )
        frame = frame.f_back
    raise RuntimeError(
        "chart_functions (v2): could not resolve `s3_manager` from any "
        "frame in the call stack. PRISM injects this into every "
        "execute_analysis_script namespace; for local dev, ensure "
        "`s3_manager = S3BucketManager(...)` is bound in the script's "
        "globals before calling Chart.render() or render_grid()."
    )


# --- Translation constants ------------------------------------------------

# Layout names accepted by ``render_grid``. The common geometric forms
# ('1x2', '2x2', '3x2', 'triangle') are the canonical names; v1's
# longer names ('2_horizontal', '4_grid', '6_grid', ...) are also
# accepted for ergonomic interop.
_V2_LAYOUT_ALIASES: Dict[str, str] = {
    # canonical short names
    "1x2": "2_horizontal",
    "2x1": "2_vertical",
    "2x2": "4_grid",
    "3x2": "6_grid",
    "triangle": "3_triangle",
    # v1 long names (passthrough)
    "2_horizontal": "2_horizontal",
    "2_vertical": "2_vertical",
    "3_triangle": "3_triangle",
    "3_inverted": "3_inverted",
    "3_horizontal": "3_horizontal",
    "3_vertical": "3_vertical",
    "4_grid": "4_grid",
    "4_horizontal": "4_horizontal",
    "4_vertical": "4_vertical",
    "6_grid": "6_grid",
}

# Keys that move into v1's ``mapping`` dict. Anything else stays as a
# top-level kwarg on ``make_chart``. The Chart class uses this to split
# its kwargs into the right buckets at render time.
_V2_MAPPING_KEYS: Tuple[str, ...] = (
    "x", "y", "color", "value", "theta",
    "x_title", "y_title", "y_title_right",
    "x_sort", "y_sort", "x_type",
    "dual_axis_series", "invert_right_axis",
    "stack", "trendline", "trendlines",
    "strokeDash", "strokeDashScale", "strokeDashLegend",
    "x_low", "x_high", "color_by", "label",
    "color_scheme",
)

# Sentinel for "kwarg not provided". We use this rather than ``None``
# because some mapping values legitimately default to None (e.g.
# ``stack`` -- ``None`` means "let the engine decide"). The Chart
# class only puts an explicitly-provided value into the v1 mapping.
_V2_UNSET = object()


# Per-chart-type dimension defaults. The engine picks the right canvas
# for each chart type so PRISM never has to think about it. Both v1's
# ``make_chart`` (when ``dimensions=None``) and v2's ``Chart`` class
# (when ``.with_dimensions()`` is not called) consult this table.
# Override path on v1: pass an explicit ``dimensions=`` (private-by-
# convention; not taught in the skill). Override on v2:
# ``Chart.with_dimensions(preset)``.
_AUTO_DIMENSIONS: Dict[str, str] = {
    "multi_line":      "wide",     # 700x350 - default standalone canvas
    "timeseries":      "wide",
    "area":            "wide",
    "bar":             "wide",     # vertical bars / categorical comparisons
    "histogram":       "wide",     # distributions read better wide
    "boxplot":         "wide",
    "waterfall":       "wide",     # decomposition needs horizontal room
    "bullet":          "wide",
    "scatter":         "wide",
    "scatter_multi":   "wide",
    "heatmap":         "wide",
    "donut":           "wide",
    "bar_horizontal":  "wide",
}


def _auto_dimensions(chart_type: str) -> str:
    """Return the engine-picked dimension preset for ``chart_type``.

    Single source of truth for "what canvas does this chart type want".
    Falls through to ``'wide'`` for any chart type without an explicit
    entry, matching the long-running engine default.
    """
    return _AUTO_DIMENSIONS.get(chart_type, "wide")


def _v2_resolve_layout(layout: str, n_charts: int) -> str:
    """Resolve a v2 layout name to v1's internal layout token.

    'auto' picks based on chart count: 2 -> 1x2, 3 -> triangle,
    4 -> 2x2, 6 -> 3x2. 1, 5, and >6 with 'auto' raise.
    """
    if layout == "auto":
        auto_map = {2: "1x2", 3: "triangle", 4: "2x2", 6: "3x2"}
        if n_charts not in auto_map:
            raise ValueError(
                f"render_grid(layout='auto') only resolves for "
                f"len(charts) in (2, 3, 4, 6); got {n_charts}. "
                f"Pass layout=... explicitly (e.g. '2x2') for "
                f"non-canonical counts."
            )
        return _V2_LAYOUT_ALIASES[auto_map[n_charts]]
    if layout in _V2_LAYOUT_ALIASES:
        return _V2_LAYOUT_ALIASES[layout]
    raise ValueError(
        f"render_grid: unknown layout {layout!r}. "
        f"Valid: {sorted(_V2_LAYOUT_ALIASES)} or 'auto'."
    )


# --- The Chart class ------------------------------------------------------

class Chart:
    """A single chart specification, renderable standalone or as a panel.

    Replaces v1's ``make_chart`` + ``ChartSpec`` duality with one
    class. Construction collects the spec; ``.render()`` produces a
    PNG and returns a ``ChartResult``. ``render_grid([c1, c2, ...])``
    consumes the same objects for composite layouts.

    All fields are keyword-only after the positional ``df`` and
    ``type``. Anything that was a key inside v1's ``mapping={...}``
    dict is now a flat kwarg.

    Quick reference (full guide in ``chart_context_v2.md``)::

        c = Chart(
            df, type='multi_line',
            x='date', y='value', color='series',
            y_title='CPI YoY (%)',
            title='Inflation Has Peaked',
            subtitle='Core CPI decelerating 6 months',
            annotations=[VLine(x='2022-03', label='Hike start'),
                         HLine(y=2.0, label='Fed target')],
        )
        result = c.render(save_as='charts/cpi.png')

    Per-chart-type kwargs are accepted but only emitted into the
    underlying v1 mapping dict when explicitly provided -- so the
    common multi_line / scatter / bar paths stay readable even though
    waterfall / bullet / heatmap kwargs all live on the same surface.
    """

    # The canonical set of mapping-bound kwargs (consulted by
    # ``_to_v1_mapping``). Module-level ``_V2_MAPPING_KEYS`` is the
    # source of truth; the class attribute exists so subclasses or
    # power users can override.
    _MAPPING_PARAMS = _V2_MAPPING_KEYS

    def __init__(
        self,
        df: pd.DataFrame,
        type: ChartType,
        *,
        # ----- Column references --------------------------------------
        x: Any = _V2_UNSET,
        y: Any = _V2_UNSET,
        color: Any = _V2_UNSET,
        value: Any = _V2_UNSET,
        theta: Any = _V2_UNSET,
        # ----- Display labels -----------------------------------------
        x_title: Any = _V2_UNSET,
        y_title: Any = _V2_UNSET,
        y_title_right: Any = _V2_UNSET,
        # ----- Axis behaviour -----------------------------------------
        x_sort: Any = _V2_UNSET,
        y_sort: Any = _V2_UNSET,
        x_type: Any = _V2_UNSET,
        # ----- Dual axis ----------------------------------------------
        dual_axis_series: Any = _V2_UNSET,
        invert_right_axis: Any = _V2_UNSET,
        # ----- Per-chart-type behaviour ------------------------------
        stack: Any = _V2_UNSET,
        trendline: Any = _V2_UNSET,
        trendlines: Any = _V2_UNSET,
        strokeDash: Any = _V2_UNSET,
        strokeDashScale: Any = _V2_UNSET,
        strokeDashLegend: Any = _V2_UNSET,
        x_low: Any = _V2_UNSET,
        x_high: Any = _V2_UNSET,
        color_by: Any = _V2_UNSET,
        label: Any = _V2_UNSET,
        type_col: Any = _V2_UNSET,  # waterfall: column naming bar type;
                                    # translates to mapping['type'] in v1
        color_scheme: Any = _V2_UNSET,
        # ----- Metadata -----------------------------------------------
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        # ----- Annotations / overlays / text panels -------------------
        annotations: Optional[List[Annotation]] = None,
        layers: Optional[List[Dict[str, Any]]] = None,
        caption: Union[str, Dict[str, Any], None] = None,
        side_left: Union[str, Dict[str, Any], None] = None,
        side_right: Union[str, Dict[str, Any], None] = None,
        # ----- Style --------------------------------------------------
        # NB: ``dimensions`` is intentionally NOT a public kwarg --
        # the engine picks per chart_type (see ``_auto_dimensions``).
        # Use ``Chart.with_dimensions(preset)`` if you really need to
        # override (escape hatch, not taught in the skill).
        skin: str = "gs_clean",
        intent: IntentType = "explore",
        auto_beautify: bool = True,
        # ----- Power-user escape hatch --------------------------------
        mapping_overrides: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Quick early-fail validation -- catches typos at construction
        # rather than at render(). All other validation runs inside
        # the v1 pipeline at render time.
        valid_types = {
            "multi_line", "timeseries", "scatter", "scatter_multi",
            "bar", "bar_horizontal", "area", "heatmap", "histogram",
            "boxplot", "donut", "bullet", "waterfall",
        }
        if type not in valid_types:
            raise ValueError(
                f"Chart: unknown type {type!r}. Valid: {sorted(valid_types)}."
            )
        if skin not in AVAILABLE_SKINS:
            raise ValueError(
                f"Chart: unknown skin {skin!r}. "
                f"Available: {list(AVAILABLE_SKINS.keys())}"
            )

        self._df = df
        self._type = type
        # Mapping-bound kwargs.
        self._x = x
        self._y = y
        self._color = color
        self._value = value
        self._theta = theta
        self._x_title = x_title
        self._y_title = y_title
        self._y_title_right = y_title_right
        self._x_sort = x_sort
        self._y_sort = y_sort
        self._x_type = x_type
        self._dual_axis_series = dual_axis_series
        self._invert_right_axis = invert_right_axis
        self._stack = stack
        self._trendline = trendline
        self._trendlines = trendlines
        self._strokeDash = strokeDash
        self._strokeDashScale = strokeDashScale
        self._strokeDashLegend = strokeDashLegend
        self._x_low = x_low
        self._x_high = x_high
        self._color_by = color_by
        self._label = label
        self._type_col = type_col
        self._color_scheme = color_scheme
        # Top-level kwargs.
        self._title = title
        self._subtitle = subtitle
        self._annotations: List[Annotation] = list(annotations) if annotations else []
        self._layers: List[Dict[str, Any]] = list(layers) if layers else []
        self._caption = caption
        self._side_left = side_left
        self._side_right = side_right
        self._skin = skin
        self._intent = intent
        # ``self._dimensions`` is the OVERRIDE slot. None means "let
        # the engine pick per chart_type" via ``_auto_dimensions``.
        # Set by ``.with_dimensions(preset)`` for power-user override.
        self._dimensions: Optional[DimensionPreset] = None
        self._auto_beautify = auto_beautify
        self._mapping_overrides = (
            dict(mapping_overrides) if mapping_overrides else {}
        )

    # ----- Fluent helpers ----------------------------------------------

    def annotate(self, *anns: Annotation) -> "Chart":
        """Append annotations in place, return self for chaining.

        Example::

            chart.annotate(VLine(x='2022-03'), HLine(y=2.0))
        """
        self._annotations.extend(anns)
        return self

    def layer(self, *layer_dicts: Dict[str, Any]) -> "Chart":
        """Append overlay layers (regression / rule / point), return self."""
        self._layers.extend(layer_dicts)
        return self

    def with_data(self, df: pd.DataFrame) -> "Chart":
        """Return a copy with ``df`` replaced.

        Useful for templates: build a Chart once, swap the data per
        render. Annotations / titles / mapping all carry over.
        """
        copy_chart = self._copy()
        copy_chart._df = df
        return copy_chart

    def with_title(
        self,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
    ) -> "Chart":
        """Return a copy with title / subtitle replaced."""
        copy_chart = self._copy()
        if title is not None:
            copy_chart._title = title
        if subtitle is not None:
            copy_chart._subtitle = subtitle
        return copy_chart

    def with_dimensions(self, preset: DimensionPreset) -> "Chart":
        """Power-user escape hatch: override the engine's auto-picked dimension preset.

        Not taught in the v2 skill -- the engine picks correctly per
        chart type for ~all real workflows. Reach for this only when
        a specific external constraint (slide aspect ratio, etc.)
        forces a non-default canvas, or during local QC.
        """
        if preset not in DIMENSION_PRESETS:
            raise ValueError(
                f"with_dimensions: unknown preset {preset!r}. "
                f"Available: {list(DIMENSION_PRESETS.keys())}"
            )
        copy_chart = self._copy()
        copy_chart._dimensions = preset
        return copy_chart

    def _copy(self) -> "Chart":
        """Internal: shallow-copy this Chart preserving all parameters."""
        new = Chart.__new__(Chart)
        new.__dict__.update(self.__dict__)
        new._annotations = list(self._annotations)
        new._layers = list(self._layers)
        new._mapping_overrides = dict(self._mapping_overrides)
        return new

    # ----- Translation to v1 -------------------------------------------

    def _to_v1_mapping(self) -> Dict[str, Any]:
        """Build the v1 ``mapping`` dict from this Chart's kwargs.

        Only includes keys that were explicitly provided (not _V2_UNSET).
        Translates v2's ``type_col`` to v1's ``mapping['type']``.
        Mapping overrides win.
        """
        mapping: Dict[str, Any] = {}
        for key in self._MAPPING_PARAMS:
            val = getattr(self, "_" + key, _V2_UNSET)
            if val is _V2_UNSET:
                continue
            mapping[key] = val
        # Waterfall: v2 ``type_col`` -> v1 ``mapping['type']``. Avoids
        # the kwarg-name collision with the chart ``type=...`` param.
        if self._type_col is not _V2_UNSET:
            mapping["type"] = self._type_col
        # Overrides take precedence.
        mapping.update(self._mapping_overrides)
        return mapping

    def to_v1_chartspec(self) -> "ChartSpec":
        """Build a v1 ``ChartSpec`` (used internally by ``render_grid``).

        Exposed publicly so power users can interop with v1 composite
        helpers if they need to. PRISM should not normally need this.
        """
        return ChartSpec(
            df=self._df,
            chart_type=self._type,
            mapping=self._to_v1_mapping(),
            title=self._title,
            subtitle=self._subtitle,
            annotations=self._annotations or None,
            layers=self._layers or None,
            caption=self._caption,
            side_left=self._side_left,
            side_right=self._side_right,
        )

    # ----- Rendering ----------------------------------------------------

    def _resolved_dimensions(self) -> str:
        """Return the dimension preset to use for this chart.

        Override (set via ``.with_dimensions()``) wins; otherwise the
        engine auto-picks per chart type.
        """
        return self._dimensions or _auto_dimensions(self._type)

    def preview(self) -> Dict[str, Any]:
        """Return the planned Vega-Lite spec without writing PNG / S3.

        Builds the chart through the v1 pipeline up to spec emission;
        returns the dict for inspection. Useful for debugging mapping
        translation, confirming auto-melt behaviour, or feeding the
        spec into a custom renderer.
        """
        ctx = _resolve_runtime_context()
        result = _make_chart(
            df=self._df,
            chart_type=self._type,
            mapping=self._to_v1_mapping(),
            title=self._title,
            subtitle=self._subtitle,
            skin=self._skin,
            intent=self._intent,
            dimensions=self._resolved_dimensions(),
            annotations=self._annotations or None,
            layers=self._layers or None,
            caption=self._caption,
            side_left=self._side_left,
            side_right=self._side_right,
            auto_beautify=self._auto_beautify,
            session_path=ctx.session_path,
            s3_manager=ctx.s3_manager,
            user_id=ctx.user_id,
        )
        return result.vegalite_json

    def render(
        self,
        save_as: Optional[str] = None,
        *,
        verbose: bool = True,
        filename_prefix: Optional[str] = None,
        filename_suffix: Optional[str] = None,
    ) -> ChartResult:
        """Build the chart, upload PNG + editor HTML, print URLs.

        This is the single I/O entry point. The boilerplate that PRISM
        used to write per chart (URL printing, warning surfacing) is
        absorbed here.

        Quality control is intentionally NOT run inline: PRISM's
        post-script sweep (``_check_charts_quality_injected`` in
        ``script_exec_tools.py``) parallel-QCs every session chart
        automatically after the script returns. Running QC inline per
        ``render()`` blocked each chart on a serial Gemini call,
        adding ~N x Gemini-latency to script wall time without
        catching anything the post-exec sweep wouldn't catch.

        Args:
            save_as: Fixed S3 path (relative to ``session_path``).
                Use for dashboard / report charts where a stable URL
                matters. Omit for one-off chats; the engine generates
                a timestamped slug.
            verbose: When True (default), prints the PNG URL on
                success; prints build-failure reason on failure.
                Set False inside batch loops where the caller will
                aggregate URLs itself.
            filename_prefix / filename_suffix: Optional slug components.

        Returns:
            ``ChartResult`` -- always returned, including on render
            failure. Check ``result.success``, ``result.error_message``,
            ``result.warnings``.
        """
        ctx = _resolve_runtime_context()
        result = _make_chart(
            df=self._df,
            chart_type=self._type,
            mapping=self._to_v1_mapping(),
            title=self._title,
            subtitle=self._subtitle,
            skin=self._skin,
            intent=self._intent,
            dimensions=self._resolved_dimensions(),
            annotations=self._annotations or None,
            layers=self._layers or None,
            caption=self._caption,
            side_left=self._side_left,
            side_right=self._side_right,
            save_as=save_as,
            filename_prefix=filename_prefix,
            filename_suffix=filename_suffix,
            auto_beautify=self._auto_beautify,
            session_path=ctx.session_path,
            s3_manager=ctx.s3_manager,
            user_id=ctx.user_id,
        )
        return _v2_post_render(
            result,
            verbose=verbose,
            label=self._title or self._type,
        )

    # ----- Introspection ------------------------------------------------

    def __repr__(self) -> str:
        parts = [
            f"Chart(type={self._type!r}",
            f"df.shape={self._df.shape if hasattr(self._df, 'shape') else None}",
        ]
        if self._title:
            parts.append(f"title={self._title!r}")
        if self._x is not _V2_UNSET and self._y is not _V2_UNSET:
            parts.append(f"x={self._x!r}, y={self._y!r}")
        if self._color is not _V2_UNSET:
            parts.append(f"color={self._color!r}")
        if self._dual_axis_series is not _V2_UNSET:
            parts.append(f"dual_axis_series={self._dual_axis_series!r}")
        if self._annotations:
            kinds = ",".join(type(a).__name__ for a in self._annotations)
            parts.append(f"annotations=[{kinds}]")
        return ", ".join(parts) + ")"


# --- render_grid ----------------------------------------------------------

def render_grid(
    charts: List[Chart],
    *,
    layout: str = "auto",
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    caption: Union[str, Dict[str, Any], None] = None,
    narrative_left: Union[str, Dict[str, Any], None] = None,
    narrative_right: Union[str, Dict[str, Any], None] = None,
    save_as: Optional[str] = None,
    skin: str = "gs_clean",
    spacing: int = 20,
    filename_prefix: Optional[str] = None,
    filename_suffix: Optional[str] = None,
    verbose: bool = True,
) -> CompositeResult:
    """Compose multiple ``Chart`` objects into a single grid layout.

    Replaces v1's five composite wrappers (``make_2pack_horizontal``,
    ``make_2pack_vertical``, ``make_3pack_triangle``, ``make_4pack_grid``,
    ``make_6pack_grid``) with one function. Layout is a string and is
    inferred from chart count when ``layout='auto'``.

    Per-panel canvas size is picked automatically by the engine
    (``compact`` for 4- and 6-grids and triangles, ``wide`` for the
    2x1 vertical pack). PRISM does not see a ``dimensions`` knob.

    Quality control is NOT run inline; PRISM's post-script sweep
    handles QC in parallel after the script returns (see ``Chart.render``
    docstring).

    Args:
        charts: List of ``Chart`` objects, one per panel. The order
            is row-major within the chosen layout.
        layout: Layout token. Canonical: ``'auto' | '1x2' | '2x1' |
            '2x2' | '3x2' | 'triangle'``. v1's longer names
            (``'2_horizontal'``, ``'4_grid'``, etc.) are also
            accepted. ``'auto'`` resolves by chart count: 2 -> 1x2,
            3 -> triangle, 4 -> 2x2, 6 -> 3x2.
        title / subtitle: Composite-level title and subtitle (the
            top of the whole pack). For per-panel titles, set
            ``title`` on each Chart.
        caption: Below-pack caption text or style dict.
        narrative_left / narrative_right: Side panels flanking the
            entire pack. (For per-panel side panels, set
            ``side_left`` / ``side_right`` on each Chart.)
        save_as: Fixed S3 path (relative to session_path).
        skin / spacing: Style knobs.
        filename_prefix / filename_suffix: Optional slug components.
        verbose: Print the PNG URL on success; print build-failure
            reasons on failure.

    Returns:
        ``CompositeResult`` -- always returned. ``result.chart_errors``
        carries per-panel build failures (the composite still renders
        with surviving panels as long as 2+ succeed).

    Example::

        c1 = Chart(us_df, type='multi_line', x='date', y='value',
                   color='series', y_title='CPI YoY %',
                   title='US')
        c2 = Chart(eu_df, type='multi_line', x='date', y='value',
                   color='series', y_title='CPI YoY %',
                   title='EU')
        result = render_grid([c1, c2], layout='1x2',
                             title='Inflation Has Peaked')
    """
    if not charts:
        raise ValueError("render_grid: charts list is empty.")
    if len(charts) == 1:
        # Single-chart "composite" is a code smell; degrade to a plain
        # chart render so the caller still gets a sensible result.
        return _v2_single_as_composite(
            charts[0],
            save_as=save_as,
            filename_prefix=filename_prefix,
            filename_suffix=filename_suffix,
            verbose=verbose,
        )

    v1_layout = _v2_resolve_layout(layout, len(charts))
    expected = _get_expected_chart_count(v1_layout)
    if expected != len(charts):
        raise ValueError(
            f"render_grid: layout {layout!r} (resolved to {v1_layout!r}) "
            f"requires {expected} charts; got {len(charts)}."
        )

    # Per-panel default dimension. Mirrors v1's per-wrapper defaults so
    # output is byte-identical: 2x1 vertical packs default to 'wide';
    # the rest default to 'compact'. PRISM does not get a knob for
    # this -- engine picks per layout shape.
    dimension_preset: DimensionPreset = (
        "wide" if v1_layout == "2_vertical" else "compact"
    )

    ctx = _resolve_runtime_context()
    specs = [c.to_v1_chartspec() for c in charts]

    result = make_composite(
        specs,
        v1_layout,
        title=title,
        subtitle=subtitle,
        skin=skin,
        dimension_preset=dimension_preset,
        spacing=spacing,
        save_as=save_as,
        filename_prefix=filename_prefix,
        filename_suffix=filename_suffix,
        session_path=ctx.session_path,
        s3_manager=ctx.s3_manager,
        user_id=ctx.user_id,
        caption=caption,
        narrative_left=narrative_left,
        narrative_right=narrative_right,
    )
    return _v2_post_render(
        result,
        verbose=verbose,
        label=title or f"{v1_layout} composite",
    )


def _v2_single_as_composite(
    chart: Chart,
    *,
    save_as: Optional[str],
    filename_prefix: Optional[str],
    filename_suffix: Optional[str],
    verbose: bool,
) -> CompositeResult:
    """Promote ``chart.render()`` output into a ``CompositeResult`` shape.

    Used when ``render_grid`` is called with a single Chart -- we
    delegate to a regular render but return the result wrapped so the
    caller doesn't need to branch on type.
    """
    cr = chart.render(
        save_as=save_as,
        verbose=verbose,
        filename_prefix=filename_prefix,
        filename_suffix=filename_suffix,
    )
    return CompositeResult(
        png_path=cr.png_path,
        layout="single",
        n_charts=1,
        success=cr.success,
        error_message=cr.error_message,
        warnings=cr.warnings,
        download_url=cr.download_url,
        vegalite_json=cr.vegalite_json,
        skin=cr.skin,
        chart_errors=[],
        editor_html_path=cr.editor_html_path,
        editor_download_url=cr.editor_download_url,
    )


# --- Post-render pipeline (URL printing only) -----------------------------

def _v2_post_render(
    result: Any,
    *,
    verbose: bool,
    label: str,
) -> Any:
    """Run the standard post-make_chart / make_composite pipeline.

    1. If render failed, print why (verbose) and return as-is.
    2. On success, print the PNG URL and any warnings.

    Quality control is NOT run here. PRISM's post-script sweep
    (``_check_charts_quality_injected`` in ``script_exec_tools.py``)
    parallel-QCs every session chart automatically after the script
    returns; running QC inline per render() blocked each chart on a
    serial Gemini round-trip and added ~N x Gemini-latency to script
    wall time without catching anything the post-exec sweep wouldn't.
    """
    if not verbose:
        return result
    if not getattr(result, "success", False):
        err = getattr(result, "error_message", None)
        if err:
            print(f"[Chart:{label}] FAIL build: {err}")
        for w in getattr(result, "warnings", []) or []:
            print(f"[Chart:{label}] WARN: {w}")
        return result
    png_url = getattr(result, "download_url", None)
    if png_url:
        print(f"[Chart:{label}] PNG: {png_url}")
    for w in getattr(result, "warnings", []) or []:
        print(f"[Chart:{label}] WARN: {w}")
    return result


# --- Batch helpers --------------------------------------------------------

def render_all(
    charts: List[Chart],
    *,
    save_prefix: Optional[str] = None,
    verbose: bool = True,
) -> List[ChartResult]:
    """Render N independent charts (NOT a composite).

    Use when you want N standalone PNGs, not a packed grid. Each
    Chart renders to its own PNG via the same pipeline; URLs print
    individually. QC happens automatically post-script (see
    ``Chart.render``).

    Args:
        save_prefix: When set, each chart saves to
            ``{save_prefix}/{i}_{title_slug}.png``. Omit for
            timestamped slugs.
    """
    out: List[ChartResult] = []
    for i, chart in enumerate(charts):
        save_as = None
        if save_prefix is not None:
            slug = (chart._title or chart._type).lower().replace(" ", "_")
            slug = "".join(ch for ch in slug if ch.isalnum() or ch == "_")
            save_as = f"{save_prefix}/{i:02d}_{slug}.png"
        out.append(chart.render(
            save_as=save_as,
            verbose=verbose,
        ))
    return out


# ===========================================================================
# MODULE: TABLE ENGINE -- make_table()
# ===========================================================================
#
# Pillow-based static-PNG table renderer. Same DIMENSION_PRESETS, GS_PRIMARY
# palette, and Liberation Sans font stack as the chart engine, so a table
# drops into the same UI cell a same-preset chart would.
#
# PRISM-facing surface (the only names documented in chart_context.md §13):
#   make_table(df=df OR rows=[...], *, ...) — render a single table to PNG
#   TableResult                            — dataclass returned by make_table
#
# PRISM-facing color modes — three strings, no degrees of freedom:
#   "rwg"  — diverging at zero, red(neg) ↔ white(0) ↔ green(pos)
#   "bw"   — sequential, white → navy. For values >= 0.
#   "rag"  — discrete buckets red/amber/green by author thresholds
#
# Two data-source paths (mutually exclusive):
#   df=<DataFrame>   — data-pulled tables (Haver / market / CSV / scraper)
#   rows=[...]       — hardcoded narrative tables (themes, trade ideas).
#                       Accepts list-of-dicts (column names from keys) or
#                       list-of-tuples (requires columns=[...] for headers).
#
# Color resolution priority (top wins per cell):
#   1. cell_colors[(r, c)]      4. heatmap_groups       7. highlight_columns
#   2. total_rows               5. column_color_modes   8. row_groups (handled separately)
#   3. subtotal_rows            6. row_colors[r]        9. row_bands

_TABLE_THEME: Dict[str, Any] = {
    "primary_color":     GS_PRIMARY["colors"][0],
    "secondary_color":   GS_PRIMARY["colors"][1],
    "accent_color":      GS_PRIMARY["colors"][4],
    "background_color":  "#FFFFFF",
    "row_band_color":    "#F7F7F7",
    "subtotal_band":     "#EFEFEF",
    "total_band":        GS_PRIMARY["colors"][0],
    "border_color":      "#1F1F1F",
    "muted_text":        "#5B5B5B",
    "header_text":       "#FFFFFF",
    "body_text":         "#000000",
    "positive_text":     "#0E7A28",
    "negative_text":     "#C00000",
    "title_font_size":   22,
    "subtitle_font_size": 13,
    "header_font_size":  14,
    "body_font_size":    13,
    "caption_font_size": 11,
}

_TABLE_PALETTES: Dict[str, Tuple] = {
    "bw":       ("sequential", GS_PRIMARY["colors"][2], 0.70),
    "wb":       ("sequential", GS_PRIMARY["colors"][2], 0.70),
    "wb_full":  ("sequential", GS_PRIMARY["colors"][0], 0.65),
    "wg":       ("sequential", "#3C9A4E", 0.65),
    "wr":       ("sequential", GS_PRIMARY["colors"][4], 0.55),
    "wo":       ("sequential", GS_PRIMARY["colors"][8], 0.65),
    "wgrey":    ("sequential", "#5B5B5B", 0.55),
    "rwg":      ("diverging", GS_PRIMARY["colors"][4], "#3C9A4E", 0.65),
    "rwb":      ("diverging", GS_PRIMARY["colors"][4], GS_PRIMARY["colors"][0], 0.65),
    "bwr":      ("diverging", GS_PRIMARY["colors"][0], GS_PRIMARY["colors"][4], 0.65),
    "owb":      ("diverging", GS_PRIMARY["colors"][8], GS_PRIMARY["colors"][0], 0.65),
}

# Content-driven table sizing constants. The table engine sizes its PNG
# to fit content exactly; PRISM never picks a canvas. These tunables
# govern only the wrap / compress behaviour for unusually-wide content
# and are private to this module. The "soft" hard-coded numbers reflect
# typical FT/Bloomberg article-body widths and reading-comfortable text
# column widths; they are not meant to be overridden by callers.
_TBL_SIDE_PAD = 12          # Left/right canvas margin (px)
_TBL_TEXT_COL_MAX = 280     # Cap text-col natural width before wrapping
_TBL_TEXT_COL_FLOOR = 160   # Lower bound when compressing text cols
_TBL_MAX_TABLE_W = 1400

# -------------------------------------------------------------------------
# Option-C canvas normalization constants for ``make_table()``.
#
# Display constraints for table PNGs: HTML report/email pipelines display
# table PNGs inside a bounded box (720px for reports, 600px for emails).
# When a content-driven canvas is forced into that box at preserved aspect
# ratio, text renders at native canvas scale -- tall portraits explode in
# height, wide ribbons collapse to microscopic text. These bounds clamp the
# native canvas so on-screen body text lands near ~11px at display width.
#
# _TBL_MAX_TABLE_H: hard ceiling on native canvas height (1080px -> ~800px
#   tall at 720px display width).
# _TBL_MAX_ASPECT_RATIO: max canvas_h / canvas_w; portraits above this shrink.
# _TBL_MIN_ASPECT_RATIO: min canvas_h / canvas_w; ribbons below this grow fonts.
# _TBL_TARGET_HTML_WIDTH_PX: display width make_table() targets (720 default;
#   override via target_html_width kwarg for email at 600).
# _TBL_TARGET_TEXT_PX_AT_DISPLAY: target on-screen body-text size in CSS px.
# _TBL_NORMALIZE_MAX_ITERATIONS: safety cap so a pathological table can't
#   bounce font sizes forever.
# -------------------------------------------------------------------------
_TBL_MAX_TABLE_H = 1080
_TBL_MAX_ASPECT_RATIO = 2.0
_TBL_MIN_ASPECT_RATIO = 0.30
_TBL_TARGET_HTML_WIDTH_PX = 720
_TBL_TARGET_TEXT_PX_AT_DISPLAY = 11.0
_TBL_NORMALIZE_MAX_ITERATIONS = 4

# Paper-legibility gate (make_table). The engine sizes the PNG to fit
# content exactly and NEVER truncates, so an over-wide table just shrinks
# to an unreadable micro-text PNG when fit to a page. This gate rejects a
# table whose body text, scaled to fill a portrait 8.5x11 page's usable
# width, would print below a legibility floor.
#
# canvas_w (px) -- NOT column count -- is the driver: numeric / datetime
# columns cannot compress (floor == natural width) and wrapping text
# columns floor at _TBL_TEXT_COL_FLOOR, so both decouple wideness from
# column count. The point-size a reader sees on paper is:
#       printed_pt = body_font_size * _TBL_LEGIBILITY_USABLE_IN * 72 / canvas_w
# evaluated on the FINAL (post-normalize) body font, because the aspect
# pass may have grown / shrunk it. There is no font escape hatch for a
# wide table: growing the font grows canvas_w too, leaving printed_pt
# unchanged.
#
#   _TBL_LEGIBILITY_USABLE_IN: usable page width after 1in margins
#       (portrait 8.5x11 -> 6.5in).
#   _TBL_MIN_LEGIBLE_PT: body-text point-size floor when fit to that width.
_TBL_LEGIBILITY_USABLE_IN = 6.5
_TBL_MIN_LEGIBLE_PT = 6.0
_TBL_FONT_TIER_FLOOR = 9   # do not shrink body font below this
_TBL_FONT_TIER_CEIL = 22   # do not grow body font above this
_TBL_CELL_PAD_X = 10        # Per-cell horizontal padding
_TBL_BODY_PAD_BOTTOM = 6    # Padding between last row and caption / edge

_TBL_FONT_SEARCH_PATHS: Dict[str, List[str]] = {
    "regular": [
        "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    "bold": [
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    "italic": [
        "/usr/share/fonts/liberation/LiberationSans-Italic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
        "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        "/Library/Fonts/Arial Italic.ttf",
    ],
}
_TBL_FONT_CACHE: Dict[Tuple[str, int], Any] = {}


def _tbl_load_font(weight: str, size: int):
    key = (weight, size)
    if key in _TBL_FONT_CACHE:
        return _TBL_FONT_CACHE[key]
    for path in _TBL_FONT_SEARCH_PATHS.get(weight, _TBL_FONT_SEARCH_PATHS["regular"]):
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, size=size)
                _TBL_FONT_CACHE[key] = font
                return font
            except OSError:
                continue
    font = ImageFont.load_default()
    _TBL_FONT_CACHE[key] = font
    return font


def _tbl_blend(c1: str, c2: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(
        int(round(r1 + (r2 - r1) * t)),
        int(round(g1 + (g2 - g1) * t)),
        int(round(b1 + (b2 - b1) * t)),
    )


def _tbl_readable_text_color(bg_hex: str) -> str:
    r, g, b = _hex_to_rgb(bg_hex)
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#000000" if luma > 140 else "#FFFFFF"


def _tbl_palette_seq(palette: str, value: float, vmin: float, vmax: float) -> Optional[str]:
    if vmax == vmin:
        return None
    t = max(0.0, min(1.0, (float(value) - vmin) / (vmax - vmin)))
    spec = _TABLE_PALETTES.get(palette, _TABLE_PALETTES["bw"])
    if spec[0] != "sequential":
        _, _, end_hex, max_i = spec
        return _tbl_blend("#FFFFFF", end_hex, t * max_i)
    _, end_hex, max_i = spec
    return _tbl_blend("#FFFFFF", end_hex, t * max_i + 0.05 if t > 0 else 0)


def _tbl_palette_div(palette: str, value: float, extent: float, center: float = 0.0) -> Optional[str]:
    if extent == 0:
        return None
    t = max(-1.0, min(1.0, (float(value) - center) / extent))
    spec = _TABLE_PALETTES.get(palette, _TABLE_PALETTES["rwg"])
    if spec[0] != "diverging":
        _, end_hex, max_i = spec
        if t >= 0:
            return _tbl_blend("#FFFFFF", end_hex, abs(t) * max_i)
        return _tbl_blend("#FFFFFF", "#5B5B5B", abs(t) * max_i)
    _, neg_hex, pos_hex, max_i = spec
    if t >= 0:
        return _tbl_blend("#FFFFFF", pos_hex, t * max_i)
    return _tbl_blend("#FFFFFF", neg_hex, abs(t) * max_i)


def _tbl_rag_color(value: float, thresholds: Any) -> Optional[str]:
    """Compute the RAG bucket colour for a numeric value.

    ``thresholds`` shapes (engine accepts all three for ergonomics):

      * Legacy 2-tuple ``(red_max, amber_max)`` — lower-is-bad.
        Below red_max → red, between → amber, above → green.
      * Dict ``{'red_below': X, 'amber_below': Y}`` — lower-is-bad
        with explicit naming (equivalent to the legacy 2-tuple).
      * Dict ``{'amber_above': X, 'red_above': Y}`` — higher-is-bad
        (inflation, unemployment, default rate, recession probability).
        Below amber_above → green, between → amber, above red_above
        → red.

    Returns ``None`` when the value is non-numeric / NaN, or when the
    threshold dict shape is incomplete.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None

    if isinstance(thresholds, (tuple, list)) and len(thresholds) == 2:
        red_max, amber_max = thresholds
        if v < red_max:
            return "#F4D6D6"
        if v < amber_max:
            return "#FCE9CC"
        return "#D8EED8"

    if isinstance(thresholds, dict):
        red_below = thresholds.get("red_below")
        amber_below = thresholds.get("amber_below")
        amber_above = thresholds.get("amber_above")
        red_above = thresholds.get("red_above")
        if red_below is not None and amber_below is not None:
            if v < float(red_below):
                return "#F4D6D6"
            if v < float(amber_below):
                return "#FCE9CC"
            return "#D8EED8"
        if amber_above is not None and red_above is not None:
            if v > float(red_above):
                return "#F4D6D6"
            if v > float(amber_above):
                return "#FCE9CC"
            return "#D8EED8"

    return None


@dataclass
class TableResult:
    """Result of a ``make_table`` call. Mirror of ``ChartResult`` for tables."""
    success: bool = False
    png_path: Optional[str] = None
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    n_rows: int = 0
    n_cols: int = 0
    truncated_rows: int = 0
    canvas_size: Optional[Tuple[int, int]] = None


def _tbl_smart_format(value: Any, hint: Optional[str] = None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if not isinstance(value, (int, float)):
        return str(value)
    v = float(value)
    if hint == "pct" or hint == "percent":
        return f"{v:.1f}%"
    if hint == "pct_signed":
        return f"{v:+.1f}%"
    if hint == "pct2":
        return f"{v:.2f}%"
    if hint == "pct2_signed":
        return f"{v:+.2f}%"
    if hint in ("bp", "bps"):
        return f"{int(round(v))}bp"
    if hint == "bp_signed":
        return f"{int(round(v)):+d}bp"
    if hint == "currency":
        sign = "-" if v < 0 else ""
        a = abs(v)
        if a >= 1e9:
            return f"{sign}${a/1e9:.2f}B"
        if a >= 1e6:
            return f"{sign}${a/1e6:.2f}M"
        if a >= 1e3:
            return f"{sign}${a/1e3:,.1f}k"
        return f"{sign}${a:,.2f}"
    if hint == "ratio":
        return f"{v:.2f}x"
    if hint == "int":
        return f"{int(round(v)):,}"
    a = abs(v)
    if a >= 1e9:
        return f"{v/1e9:.2f}B"
    if a >= 1e6:
        return f"{v/1e6:.2f}M"
    if a >= 1e3:
        return f"{v:,.1f}"
    if a >= 10 or a >= 1:
        return f"{v:.2f}"
    if a == 0:
        return "0.00"
    return f"{v:.3f}"


def _tbl_wrap_text(text: str, font, max_width_px: int) -> List[str]:
    if text is None:
        return [""]
    text = str(text)
    if not text:
        return [""]
    out: List[str] = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            out.append("")
            continue
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if font.getlength(candidate) <= max_width_px or not current:
                if font.getlength(word) > max_width_px and not current:
                    pieces = _tbl_hard_break(word, font, max_width_px)
                    out.extend(pieces[:-1])
                    current = pieces[-1]
                else:
                    current = candidate
            else:
                out.append(current)
                current = word
        if current:
            out.append(current)
    return out


def _tbl_hard_break(text: str, font, max_width_px: int) -> List[str]:
    pieces: List[str] = []
    current = ""
    for ch in text:
        if font.getlength(current + ch) > max_width_px and current:
            pieces.append(current)
            current = ch
        else:
            current += ch
    if current:
        pieces.append(current)
    return pieces or [text]


_TBL_RAG_THRESHOLD_KEYS = frozenset({
    "amber_above", "red_above", "amber_below", "red_below",
})
_TBL_VALID_MODE_VALUES = frozenset({
    "rwg", "bw", "rag", "highlight", "none", "heatmap",
    "diverging", "diverging_at_zero", "sequential",
})


def _tbl_normalize_mode(
    spec: Union[str, Dict[str, Any]],
    col_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalise a column_color_modes value to the internal {mode, ...} dict.

    Accepted spec shapes (per chart_context.md §13.4):
      str  -- one of {'rwg', 'bw', 'rag', 'highlight', 'none'}
      dict -- engine-internal full spec with required 'mode' key

    Reject loudly: dict shapes that PRISM naturally tries but are not
    the canonical form (e.g. dict carrying rag thresholds directly).
    These previously rendered SILENTLY UNCOLOURED -- the engine
    returned success=True but every cell in the column got no colour
    because the spec lacked a 'mode' key.
    """
    if isinstance(spec, dict):
        if "mode" in spec:
            return {**spec}
        col_hint = f"column_color_modes[{col_name!r}]" if col_name else "column_color_modes value"
        spec_keys = set(spec.keys())
        if spec_keys & _TBL_RAG_THRESHOLD_KEYS:
            raise ValidationError(
                f"{col_hint} looks like rag thresholds passed directly as "
                f"the colour-mode value: {spec!r}. The two are separate "
                f"kwargs: set the mode in `column_color_modes`, set the "
                f"thresholds in `rag_thresholds`. Canonical shape:\n"
                f"  column_color_modes={{'{col_name or '<col>'}': 'rag'}},\n"
                f"  rag_thresholds={{'{col_name or '<col>'}': {dict(spec)!r}}}\n"
                f"See chart_context.md §13.4."
            )
        raise ValidationError(
            f"{col_hint}={spec!r} is a dict without a 'mode' key. "
            f"column_color_modes values must be one of the strings "
            f"{sorted(_TBL_VALID_MODE_VALUES)} (per chart_context.md §13.4). "
            f"For full per-column control use an internal-shape dict "
            f"with an explicit 'mode' key."
        )
    s = str(spec)
    if s not in _TBL_VALID_MODE_VALUES:
        col_hint = f"column_color_modes[{col_name!r}]" if col_name else "column_color_modes value"
        raise ValidationError(
            f"{col_hint}={s!r} is not a recognised colour mode. Valid "
            f"PRISM-facing modes: 'rwg' / 'bw' / 'rag' / 'highlight' / "
            f"'none' (per chart_context.md §13.4)."
        )
    if s == "rwg":
        return {"mode": "diverging", "palette": "rwg", "center": 0.0}
    if s == "bw":
        return {"mode": "heatmap", "palette": "bw"}
    if s == "rag":
        return {"mode": "rag"}
    if s == "highlight":
        return {"mode": "highlight"}
    if s == "none":
        return {"mode": "none"}
    if s == "heatmap":
        return {"mode": "heatmap", "palette": "bw"}
    if s == "diverging" or s == "diverging_at_zero":
        return {"mode": "diverging", "palette": "rwg", "center": 0.0}
    return {"mode": s}


@dataclass
class _TableLayoutGeom:
    canvas_w: int
    canvas_h: int
    title_h: int
    title_lines: List[str]
    subtitle_lines: List[str]
    table_x: int
    table_w: int
    body_top_y: int
    header_h: int
    col_xs: List[int]
    col_widths: List[int]
    col_wraps: List[bool]
    row_heights: List[int]
    caption_y: int
    caption_h: int
    row_default_h: int
    group_band_h: int


def _tbl_measure_title(
    title: Optional[str], subtitle: Optional[str],
    inner_w: int, theme: Dict[str, Any],
) -> Tuple[int, List[str], List[str]]:
    """Return ``(band_height_px, wrapped_title_lines, wrapped_subtitle_lines)``.

    Title and subtitle are wrapped at word boundaries to fit ``inner_w``
    (the canvas inner width). Single words wider than ``inner_w`` fall
    back to character-level hard-break (matching caption behaviour).
    The band's height is computed from the line counts so titles that
    wrap to multiple lines grow the canvas top-to-bottom rather than
    clipping at the canvas's right edge.
    """
    if not title and not subtitle:
        return 0, [], []
    title_font = _tbl_load_font("bold", theme["title_font_size"])
    subtitle_font = _tbl_load_font("regular", theme["subtitle_font_size"])
    title_lines = _tbl_wrap_text(title, title_font, inner_w) if title else []
    subtitle_lines = (
        _tbl_wrap_text(subtitle, subtitle_font, inner_w) if subtitle else []
    )
    h = 6
    if title_lines:
        h += int(len(title_lines) * theme["title_font_size"] * 1.2)
    if subtitle_lines:
        h += int(len(subtitle_lines) * theme["subtitle_font_size"] * 1.4)
    h += 8
    return h, title_lines, subtitle_lines


def _tbl_measure_caption(caption: Optional[str], inner_w: int, theme: Dict[str, Any]) -> Tuple[int, List[str]]:
    """Return (caption_band_height, wrapped_caption_lines).

    Caption wraps to the inner table width (canvas_w - 2 * side_pad).
    Returns 0 / empty list when no caption is set.
    """
    if not caption:
        return 0, []
    cap_font = _tbl_load_font("italic", theme["caption_font_size"])
    lines = _tbl_wrap_text(caption, cap_font, inner_w)
    h = int(len(lines) * theme["caption_font_size"] * 1.4) + 12
    return h, lines


def _tbl_default_align(col: str, df: pd.DataFrame) -> str:
    if pd.api.types.is_numeric_dtype(df[col]):
        return "right"
    return "left"


def _tbl_is_text_col(
    df: pd.DataFrame, col: str,
    sparkline_columns: Dict[str, Any], minibar_columns: Dict[str, Any],
) -> bool:
    """Text columns wrap when wide; numeric / datetime / sparkline /
    minibar columns never wrap."""
    if col in sparkline_columns or col in minibar_columns:
        return False
    series = df[col]
    if pd.api.types.is_numeric_dtype(series):
        return False
    if pd.api.types.is_datetime64_any_dtype(series):
        return False
    return True


def _tbl_natural_widths(
    df: pd.DataFrame,
    column_formats: Dict[str, str],
    sparkline_columns: Dict[str, List], minibar_columns: Dict[str, str],
    theme: Dict[str, Any],
) -> Tuple[List[int], List[bool], List[int]]:
    """Compute the per-column natural width, wrap flag, and minimum
    floor (the smallest width that still keeps the header visible).

    Returns (widths, wraps, floors).
      ``widths[i]``  - natural rendered width in px (already clamped to
                       ``_TBL_TEXT_COL_MAX`` for wrapping text columns).
      ``wraps[i]``   - True when the column is a text column that has
                       been capped at ``_TBL_TEXT_COL_MAX`` and so its
                       cells must wrap to fit. Numeric / datetime /
                       sparkline / minibar columns always carry False.
      ``floors[i]``  - lowest acceptable width when the table needs to
                       compress to fit ``_TBL_MAX_TABLE_W``. Equal to
                       the column's natural width for non-wrapping
                       columns (they cannot be compressed without
                       truncation, which is forbidden) and to
                       max(header_w, ``_TBL_TEXT_COL_FLOOR``) for
                       wrapping text columns.
    """
    body_font = _tbl_load_font("regular", theme["body_font_size"])
    header_font = _tbl_load_font("bold", theme["header_font_size"])
    cell_pad_x = _TBL_CELL_PAD_X

    widths: List[int] = []
    wraps: List[bool] = []
    floors: List[int] = []
    for col in df.columns:
        header_w = int(header_font.getlength(str(col))) + 2 * cell_pad_x
        # Sparkline / minibar columns carry a graphical body (line + dot
        # or bar), so their natural body width is fixed. The HEADER, on
        # the other hand, is plain text and must fit -- otherwise the
        # header label silently overflows into the neighbouring column
        # (PIL ``draw.text`` does not clip). Width = max(graphical
        # default, header width).
        if col in sparkline_columns:
            w = max(120 + 2 * cell_pad_x, header_w)
            widths.append(w)
            wraps.append(False)
            floors.append(w)
            continue
        if col in minibar_columns:
            w = max(110 + 2 * cell_pad_x, header_w)
            widths.append(w)
            wraps.append(False)
            floors.append(w)
            continue
        body_max_w = 0
        for v in df[col].tolist():
            text = _tbl_smart_format(v, column_formats.get(col))
            tw = int(body_font.getlength(text)) + 2 * cell_pad_x
            if tw > body_max_w:
                body_max_w = tw
        natural = max(header_w, body_max_w, 60)
        is_text = _tbl_is_text_col(df, col, sparkline_columns, minibar_columns)
        if is_text and natural > _TBL_TEXT_COL_MAX:
            widths.append(max(header_w, _TBL_TEXT_COL_MAX))
            wraps.append(True)
            floors.append(max(header_w, _TBL_TEXT_COL_FLOOR))
        else:
            widths.append(natural)
            wraps.append(False)
            floors.append(natural)
    return widths, wraps, floors


def _tbl_compress_to_fit(
    widths: List[int], wraps: List[bool], floors: List[int],
    side_pad: int,
) -> List[int]:
    """If sum(widths) + 2*side_pad exceeds the soft ceiling, compress
    wrapping text columns toward their floors uniformly. If the ceiling
    cannot be honoured even at the floor, the overflow is accepted -
    the table just renders wider. No truncation."""
    inner_target = _TBL_MAX_TABLE_W - 2 * side_pad
    cur = sum(widths)
    if cur <= inner_target:
        return list(widths)
    overflow = cur - inner_target
    flex_idx = [i for i, wrapping in enumerate(wraps) if wrapping]
    if not flex_idx:
        return list(widths)
    out = list(widths)
    while overflow > 0:
        room = sum(out[i] - floors[i] for i in flex_idx)
        if room <= 0:
            break
        take = min(overflow, room)
        for i in flex_idx:
            slack = out[i] - floors[i]
            if slack <= 0:
                continue
            share = int(round(take * (slack / room)))
            share = min(share, slack)
            out[i] -= share
        overflow = sum(out) - inner_target
        if overflow <= 0 or sum(out[i] - floors[i] for i in flex_idx) <= 0:
            break
    return out


def _tbl_row_heights(
    df: pd.DataFrame,
    col_widths: List[int],
    col_wraps: List[bool],
    column_formats: Dict[str, str],
    theme: Dict[str, Any],
) -> List[int]:
    """Per-row height, growing to fit any wrapping cell content."""
    body_font = _tbl_load_font("regular", theme["body_font_size"])
    cell_pad_x = _TBL_CELL_PAD_X
    base_h = int(theme["body_font_size"] * 1.95)
    line_h = int(theme["body_font_size"] * 1.45)
    out: List[int] = []
    for _, row in df.iterrows():
        max_lines = 1
        for ci, col in enumerate(df.columns):
            if not col_wraps[ci]:
                continue
            avail = col_widths[ci] - 2 * cell_pad_x
            text = _tbl_smart_format(row[col], column_formats.get(col))
            lines = _tbl_wrap_text(text, body_font, max(20, avail))
            if len(lines) > max_lines:
                max_lines = len(lines)
        h = max(base_h, max_lines * line_h + 8)
        out.append(h)
    return out


def _tbl_normalize_theme_for_display(
    df: pd.DataFrame, title: Optional[str], subtitle: Optional[str],
    caption: Optional[str],
    base_theme: Dict[str, Any],
    header_levels: Optional[List[List[Tuple[str, int]]]],
    column_formats: Dict[str, str],
    sparkline_columns: Dict[str, List], minibar_columns: Dict[str, str],
    row_groups: Optional[List[Tuple[str, int]]],
    target_html_width: int,
) -> Tuple[Dict[str, Any], _TableLayoutGeom, List[str], List[str]]:
    """Adapt ``theme`` font sizes so the rendered canvas hits the target
    display-width text size and stays within bounded aspect ratio.

    Iteratively runs ``_tbl_layout()`` and inspects the resulting canvas:

    * If the canvas is too portrait (``canvas_h / canvas_w >
      _TBL_MAX_ASPECT_RATIO``), shrink fonts one tier and re-layout.
    * If the on-screen body text size at ``target_html_width`` would fall
      below ``_TBL_TARGET_TEXT_PX_AT_DISPLAY``, grow fonts one tier.
    * If the canvas exceeds ``_TBL_MAX_TABLE_H``, shrink fonts one tier.

    Caps iterations at ``_TBL_NORMALIZE_MAX_ITERATIONS``. Records every
    adjustment in the returned warnings list so PRISM can surface to the
    user that the rendered text size was auto-adjusted.

    Returns (adapted_theme, geom, caption_lines, warnings).
    """
    theme = dict(base_theme)
    warnings: List[str] = []
    last_geom: Optional[_TableLayoutGeom] = None
    last_caption_lines: List[str] = []

    for iteration in range(_TBL_NORMALIZE_MAX_ITERATIONS + 1):
        geom, caption_lines = _tbl_layout(
            df, title, subtitle, caption, theme,
            header_levels, column_formats,
            sparkline_columns, minibar_columns, row_groups,
        )
        last_geom, last_caption_lines = geom, caption_lines

        canvas_w = geom.canvas_w
        canvas_h = geom.canvas_h
        if canvas_w <= 0:
            break
        aspect = canvas_h / canvas_w  # >1 = portrait; <1 = landscape

        if iteration >= _TBL_NORMALIZE_MAX_ITERATIONS:
            break

        body_fs = theme["body_font_size"]
        header_fs = theme["header_font_size"]

        # Case 1: too portrait (tall).
        if aspect > _TBL_MAX_ASPECT_RATIO and body_fs > _TBL_FONT_TIER_FLOOR:
            new_body = max(_TBL_FONT_TIER_FLOOR, body_fs - 1)
            new_header = max(_TBL_FONT_TIER_FLOOR + 1, header_fs - 1)
            if new_body == body_fs and new_header == header_fs:
                break
            theme["body_font_size"] = new_body
            theme["header_font_size"] = new_header
            warnings.append(
                f"make_table canvas was too portrait "
                f"({canvas_w}x{canvas_h}, aspect={aspect:.2f}); "
                f"shrinking body font {body_fs}->{new_body} to fit display "
                f"width {target_html_width}px. Consider transposing or "
                f"splitting the table for a cleaner result."
            )
            continue

        # Case 2: too tall outright.
        if canvas_h > _TBL_MAX_TABLE_H and body_fs > _TBL_FONT_TIER_FLOOR:
            new_body = max(_TBL_FONT_TIER_FLOOR, body_fs - 1)
            new_header = max(_TBL_FONT_TIER_FLOOR + 1, header_fs - 1)
            if new_body == body_fs and new_header == header_fs:
                break
            theme["body_font_size"] = new_body
            theme["header_font_size"] = new_header
            warnings.append(
                f"make_table canvas height {canvas_h}px exceeded ceiling "
                f"{_TBL_MAX_TABLE_H}px; shrinking body font "
                f"{body_fs}->{new_body}."
            )
            continue

        # Case 3: rendered text size at display width too small.
        scale = target_html_width / canvas_w
        effective_text_px = body_fs * scale
        if (effective_text_px < _TBL_TARGET_TEXT_PX_AT_DISPLAY
                and aspect < _TBL_MIN_ASPECT_RATIO
                and body_fs < _TBL_FONT_TIER_CEIL):
            new_body = min(_TBL_FONT_TIER_CEIL, body_fs + 1)
            new_header = min(_TBL_FONT_TIER_CEIL + 2, header_fs + 1)
            if new_body == body_fs and new_header == header_fs:
                break
            theme["body_font_size"] = new_body
            theme["header_font_size"] = new_header
            warnings.append(
                f"make_table canvas was very wide / short "
                f"({canvas_w}x{canvas_h}, aspect={aspect:.2f}); "
                f"growing body font {body_fs}->{new_body} so text reads at "
                f"{_TBL_TARGET_TEXT_PX_AT_DISPLAY:.0f}px at display "
                f"width {target_html_width}px "
                f"(was ~{effective_text_px:.1f}px)."
            )
            continue

        # Canvas is within bounds.
        break

    return theme, last_geom, last_caption_lines, warnings


def _tbl_layout(
    df: pd.DataFrame, title: Optional[str], subtitle: Optional[str],
    caption: Optional[str],
    theme: Dict[str, Any],
    header_levels: Optional[List[List[Tuple[str, int]]]],
    column_formats: Dict[str, str],
    sparkline_columns: Dict[str, List], minibar_columns: Dict[str, str],
    row_groups: Optional[List[Tuple[str, int]]],
) -> Tuple[_TableLayoutGeom, List[str]]:
    """Compute a content-driven layout. Returns the geometry plus the
    pre-wrapped caption lines (so the draw step doesn't have to re-wrap).

    Width:  side_pad + Sum(col_widths) + side_pad
            (capped softly at ``_TBL_MAX_TABLE_W`` via wrap-column
             compression; if even the floor compression can't fit, the
             table renders wider rather than truncating any cell.)

    Height: title + header + Sum(row_heights) + group bands + caption
            + bottom padding. Always exact - no fixed canvas, so no
            bottom whitespace.
    """
    side_pad = _TBL_SIDE_PAD
    natural_w, wraps, floors = _tbl_natural_widths(
        df, column_formats, sparkline_columns, minibar_columns, theme,
    )
    col_widths = _tbl_compress_to_fit(natural_w, wraps, floors, side_pad)

    canvas_w = 2 * side_pad + sum(col_widths)
    inner_w = canvas_w - 2 * side_pad

    title_h, title_lines, subtitle_lines = _tbl_measure_title(
        title, subtitle, inner_w, theme,
    )
    caption_h, _caption_lines = _tbl_measure_caption(caption, inner_w, theme)

    n_super_levels = len(header_levels) if header_levels else 0
    header_row_h = int(theme["header_font_size"] * 1.7)
    header_h = header_row_h * (n_super_levels + 1)
    body_top_y = title_h + header_h + (8 if title_h else 0)

    row_default_h = int(theme["body_font_size"] * 1.95)
    group_band_h = int(theme["body_font_size"] * 1.85)

    row_heights = _tbl_row_heights(
        df, col_widths, wraps, column_formats, theme,
    )
    n_group_bands = len(row_groups or [])
    body_h = sum(row_heights) + n_group_bands * group_band_h
    canvas_h = body_top_y + body_h + caption_h + _TBL_BODY_PAD_BOTTOM

    col_xs = [side_pad]
    acc = side_pad
    for w in col_widths:
        acc += w
        col_xs.append(acc)

    geom = _TableLayoutGeom(
        canvas_w=canvas_w, canvas_h=canvas_h,
        title_h=title_h,
        title_lines=title_lines, subtitle_lines=subtitle_lines,
        table_x=side_pad,
        table_w=inner_w,
        body_top_y=body_top_y,
        header_h=header_h, col_xs=col_xs,
        col_widths=col_widths, col_wraps=wraps,
        row_heights=row_heights,
        caption_y=body_top_y + body_h, caption_h=caption_h,
        row_default_h=row_default_h, group_band_h=group_band_h,
    )
    return geom, _caption_lines


def _tbl_resolve_heatmap_group(
    r: int, c: int, df: pd.DataFrame,
    heatmap_groups: List[Dict[str, Any]],
) -> Optional[str]:
    col_name = df.columns[c]
    for grp in heatmap_groups:
        cols = grp.get("columns", [])
        if col_name not in cols:
            continue
        scope = grp.get("scope", "column")
        palette = grp.get("palette") or ("rwg" if grp.get("mode") == "diverging" else "bw")
        mode = grp.get("mode")
        if mode is None:
            mode = "diverging" if palette in ("rwg", "rwb", "bwr", "owb") else "sequential"
        center = float(grp.get("center", 0.0))
        v = df.iloc[r, c]
        try:
            vf = float(v) if pd.notna(v) else None
        except (TypeError, ValueError):
            vf = None
        if vf is None:
            return None
        if scope == "column":
            series = pd.to_numeric(df[col_name], errors="coerce").dropna()
            if not len(series):
                return None
            if mode == "sequential":
                return _tbl_palette_seq(palette, vf, float(series.min()), float(series.max()))
            extent = max(abs(float(series.min()) - center), abs(float(series.max()) - center))
            return _tbl_palette_div(palette, vf, extent, center=center)
        if scope == "row":
            row_vals = pd.to_numeric(df.iloc[r][cols], errors="coerce").dropna()
            if not len(row_vals):
                return None
            if mode == "sequential":
                return _tbl_palette_seq(palette, vf, float(row_vals.min()), float(row_vals.max()))
            extent = max(abs(float(row_vals.min()) - center), abs(float(row_vals.max()) - center))
            return _tbl_palette_div(palette, vf, extent, center=center)
        if scope == "group":
            block = pd.to_numeric(df[cols].stack(), errors="coerce").dropna()
            if not len(block):
                return None
            if mode == "sequential":
                return _tbl_palette_seq(palette, vf, float(block.min()), float(block.max()))
            extent = max(abs(float(block.min()) - center), abs(float(block.max()) - center))
            return _tbl_palette_div(palette, vf, extent, center=center)
    return None


def _tbl_resolve_column_mode(
    r: int, c: int, df: pd.DataFrame,
    column_color_modes: Dict[str, Dict[str, Any]],
    rag_thresholds: Dict[str, Any],
) -> Optional[str]:
    col_name = df.columns[c]
    spec = column_color_modes.get(col_name)
    if not spec:
        return None
    mode = spec.get("mode", "none")
    palette = spec.get("palette",
                        "bw" if mode in ("heatmap", "sequential") else "rwg")
    center = float(spec.get("center", 0.0))
    v = df.iloc[r, c]
    try:
        vf = float(v) if pd.notna(v) else None
    except (TypeError, ValueError):
        vf = None
    if mode == "rag":
        thr = spec.get("thresholds") or rag_thresholds.get(col_name)
        if thr is None or vf is None:
            return None
        return _tbl_rag_color(vf, thr)
    if mode == "highlight":
        return spec.get("color", "#E8F0F7")
    if vf is None:
        return None
    if mode in ("heatmap", "sequential"):
        series = pd.to_numeric(df[col_name], errors="coerce").dropna()
        if not len(series):
            return None
        return _tbl_palette_seq(palette, vf, float(series.min()), float(series.max()))
    if mode in ("diverging", "diverging_at_zero"):
        series = pd.to_numeric(df[col_name], errors="coerce").dropna()
        if not len(series):
            return None
        extent = max(abs(float(series.min()) - center), abs(float(series.max()) - center))
        return _tbl_palette_div(palette, vf, extent, center=center)
    return None


def _tbl_draw_title(draw, geom: _TableLayoutGeom, theme: Dict[str, Any]) -> None:
    """Draw the pre-wrapped title + subtitle lines stored on ``geom``.

    Layout already wrapped both to ``geom.table_w`` so the draw step
    only emits one line at a time.
    """
    if not geom.title_lines and not geom.subtitle_lines:
        return
    title_font = _tbl_load_font("bold", theme["title_font_size"])
    subtitle_font = _tbl_load_font("regular", theme["subtitle_font_size"])
    y = 6
    for line in geom.title_lines:
        draw.text((geom.table_x, y), line, fill="#000000", font=title_font)
        y += int(theme["title_font_size"] * 1.2)
    for line in geom.subtitle_lines:
        draw.text(
            (geom.table_x, y), line,
            fill=theme["muted_text"], font=subtitle_font,
        )
        y += int(theme["subtitle_font_size"] * 1.4)


def _tbl_draw_caption(draw, caption: Optional[str],
                       geom: _TableLayoutGeom, theme: Dict[str, Any]) -> None:
    if not caption:
        return
    cap_font = _tbl_load_font("italic", theme["caption_font_size"])
    lines = _tbl_wrap_text(caption, cap_font, geom.table_w)
    y = geom.caption_y + 6
    for line in lines:
        draw.text((geom.table_x, y), line, fill=theme["muted_text"], font=cap_font)
        y += int(theme["caption_font_size"] * 1.4)


def _tbl_draw_header(draw, df: pd.DataFrame, geom: _TableLayoutGeom,
                      theme: Dict[str, Any],
                      header_levels: Optional[List[List[Tuple[str, int]]]],
                      column_aligns: Dict[str, str]) -> None:
    header_font = _tbl_load_font("bold", theme["header_font_size"])
    header_row_h = int(theme["header_font_size"] * 1.7)
    band_y0 = geom.title_h
    band_y1 = band_y0 + geom.header_h
    draw.rectangle(
        [geom.table_x, band_y0, geom.table_x + geom.table_w, band_y1],
        fill=theme["primary_color"],
    )
    n_levels = (len(header_levels) if header_levels else 0)
    if header_levels:
        for level_idx, level in enumerate(header_levels):
            y0 = band_y0 + level_idx * header_row_h
            y1 = y0 + header_row_h
            col_cursor = 0
            for label, span in level:
                x0 = geom.col_xs[col_cursor]
                x1 = geom.col_xs[col_cursor + span]
                if col_cursor > 0:
                    draw.line([(x0, y0), (x0, y1 - 2)], fill="#FFFFFF", width=1)
                if label:
                    cx = (x0 + x1) // 2
                    cy = y0 + header_row_h // 2
                    tw = header_font.getlength(label)
                    draw.text(
                        (cx - tw / 2, cy - theme["header_font_size"] / 2 - 1),
                        label, fill=theme["header_text"], font=header_font,
                    )
                col_cursor += span
            draw.line(
                [(geom.table_x, y1 - 1), (geom.table_x + geom.table_w, y1 - 1)],
                fill="#FFFFFF", width=1,
            )
    y0 = band_y0 + n_levels * header_row_h
    cell_pad_x = _TBL_CELL_PAD_X
    for i, col in enumerate(df.columns):
        x0 = geom.col_xs[i]
        x1 = geom.col_xs[i + 1]
        align = column_aligns.get(col, _tbl_default_align(col, df))
        text = str(col)
        tw = header_font.getlength(text)
        if align == "right":
            tx = x1 - cell_pad_x - tw
        elif align == "center":
            tx = (x0 + x1) // 2 - tw / 2
        else:
            tx = x0 + cell_pad_x
        ty = y0 + header_row_h // 2 - theme["header_font_size"] / 2 - 1
        draw.text((tx, ty), text, fill=theme["header_text"], font=header_font)


def _tbl_draw_sparkline(draw, x: int, y: int, w: int, h: int,
                          series: Optional[Sequence[float]],
                          theme: Dict[str, Any]) -> None:
    if not series or len(series) < 2:
        return
    vals = [float(v) for v in series
            if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if len(vals) < 2:
        return
    vmin, vmax = min(vals), max(vals)
    if vmax == vmin:
        vmax = vmin + 1.0
    pts = []
    n = len(vals)
    for i, v in enumerate(vals):
        px = x + int(round(i * w / max(1, n - 1)))
        py = y + h - int(round((v - vmin) / (vmax - vmin) * h))
        pts.append((px, py))
    draw.line([(x, y + h), (x + w, y + h)], fill="#DDDDDD", width=1)
    draw.line(pts, fill=theme["primary_color"], width=2)
    draw.ellipse(
        [pts[-1][0] - 3, pts[-1][1] - 3, pts[-1][0] + 3, pts[-1][1] + 3],
        fill=theme["primary_color"],
    )


def _tbl_draw_minibar(draw, x: int, y: int, w: int, h: int,
                        value: Any, col_max: Any,
                        theme: Dict[str, Any]) -> None:
    if value is None or pd.isna(value) or col_max is None or pd.isna(col_max) or col_max == 0:
        return
    vf = float(value)
    cm = float(col_max)
    bar_h = max(8, h - 6)
    by = y + (h - bar_h) // 2
    draw.rectangle([x, by, x + w, by + bar_h], outline="#E0E0E0", fill="#FAFAFA", width=1)
    if vf >= 0:
        bw = int(round(min(1.0, vf / cm) * w))
        draw.rectangle([x, by, x + bw, by + bar_h], fill=theme["primary_color"])
    else:
        bw = int(round(min(1.0, abs(vf) / cm) * w))
        draw.rectangle([x + w - bw, by, x + w, by + bar_h], fill=theme["negative_text"])


def _tbl_draw_body(
    draw, df: pd.DataFrame, geom: _TableLayoutGeom, theme: Dict[str, Any],
    column_formats: Dict[str, str], column_aligns: Dict[str, str],
    column_color_modes: Dict[str, Dict[str, Any]],
    heatmap_groups: List[Dict[str, Any]],
    rag_thresholds: Dict[str, Any],
    row_bands: bool,
    row_groups: Optional[List[Tuple[str, int]]],
    row_indent: Optional[List[int]],
    row_colors: Dict[int, str],
    cell_colors: Dict[Tuple[int, int], str],
    cell_text_colors: Dict[Tuple[int, int], str],
    highlight_columns: List[str],
    sparkline_columns: Dict[str, List[List[float]]],
    minibar_columns: Dict[str, str],
    signed_columns: List[str],
    total_rows: List[int],
    subtotal_rows: List[int],
) -> None:
    """Draw every body row. Canvas is content-sized so there is no
    body-bottom check and no truncation; every row renders. Wrapping
    is driven by ``geom.col_wraps`` (engine-decided) and the per-row
    height (already computed by ``_tbl_layout``) is what gives wrapped
    cells the room they need."""
    body_font = _tbl_load_font("regular", theme["body_font_size"])
    body_bold = _tbl_load_font("bold", theme["body_font_size"])
    cell_pad_x = _TBL_CELL_PAD_X
    group_starts: Dict[int, str] = {}
    if row_groups:
        cursor = 0
        for label, count in row_groups:
            group_starts[cursor] = label
            cursor += count
    col_index = {c: i for i, c in enumerate(df.columns)}
    n_cols = len(df.columns)
    row_heights = geom.row_heights
    y = geom.body_top_y
    for r_idx, (_, row) in enumerate(df.iterrows()):
        rh = row_heights[r_idx] if r_idx < len(row_heights) else geom.row_default_h
        if r_idx in group_starts:
            draw.rectangle(
                [geom.table_x, y, geom.table_x + geom.table_w, y + geom.group_band_h],
                fill=theme["primary_color"],
            )
            label = group_starts[r_idx]
            draw.text(
                (geom.table_x + 12, y + geom.group_band_h // 2 - theme["body_font_size"] / 2 - 1),
                label, fill=theme["header_text"], font=body_bold,
            )
            y += geom.group_band_h
        is_total = r_idx in total_rows
        is_subtotal = r_idx in subtotal_rows
        if is_total:
            draw.rectangle(
                [geom.table_x, y, geom.table_x + geom.table_w, y + rh],
                fill=theme["total_band"],
            )
        elif is_subtotal:
            draw.rectangle(
                [geom.table_x, y, geom.table_x + geom.table_w, y + rh],
                fill=theme["subtotal_band"],
            )
        else:
            if row_bands and r_idx % 2 == 1:
                draw.rectangle(
                    [geom.table_x, y, geom.table_x + geom.table_w, y + rh],
                    fill=theme["row_band_color"],
                )
            row_tint = row_colors.get(r_idx)
            if row_tint:
                draw.rectangle(
                    [geom.table_x, y, geom.table_x + geom.table_w, y + rh],
                    fill=row_tint,
                )
            for hcol in highlight_columns:
                if hcol in col_index:
                    ci = col_index[hcol]
                    draw.rectangle(
                        [geom.col_xs[ci], y, geom.col_xs[ci + 1], y + rh],
                        fill="#E8F0F7",
                    )
        cell_bg: Dict[int, Optional[str]] = {}
        if not is_total:
            for ci in range(n_cols):
                color = _tbl_resolve_heatmap_group(r_idx, ci, df, heatmap_groups)
                if color is None:
                    color = _tbl_resolve_column_mode(
                        r_idx, ci, df, column_color_modes, rag_thresholds,
                    )
                cell_bg[ci] = color
                if color:
                    draw.rectangle(
                        [geom.col_xs[ci] + 1, y + 1, geom.col_xs[ci + 1] - 1, y + rh - 1],
                        fill=color,
                    )
        for (cell_r, cell_c), col_hex in cell_colors.items():
            if cell_r == r_idx and 0 <= cell_c < n_cols:
                draw.rectangle(
                    [geom.col_xs[cell_c] + 1, y + 1, geom.col_xs[cell_c + 1] - 1, y + rh - 1],
                    fill=col_hex,
                )
                cell_bg[cell_c] = col_hex
        for ci, col in enumerate(df.columns):
            x0 = geom.col_xs[ci]
            x1 = geom.col_xs[ci + 1]
            align = column_aligns.get(col, _tbl_default_align(col, df))
            font = body_bold if (is_total or is_subtotal) else body_font
            if col in sparkline_columns:
                series = sparkline_columns[col][r_idx] if r_idx < len(sparkline_columns[col]) else None
                _tbl_draw_sparkline(draw, x0 + 8, y + 6, x1 - x0 - 16, rh - 12, series, theme)
                continue
            if col in minibar_columns:
                src = minibar_columns[col]
                col_max = pd.to_numeric(df[src], errors="coerce").abs().max()
                _tbl_draw_minibar(draw, x0 + 8, y + 4, x1 - x0 - 16, rh - 8, row.get(src), col_max, theme)
                continue
            indent_px = 0
            if ci == 0 and row_indent and r_idx < len(row_indent):
                indent_px = row_indent[r_idx] * 16
            v = row[col]
            text_str = _tbl_smart_format(v, column_formats.get(col))
            text_color = cell_text_colors.get((r_idx, ci))
            if text_color is None:
                if is_total:
                    text_color = "#FFFFFF"
                elif col in signed_columns and isinstance(v, (int, float)) and not pd.isna(v):
                    if v > 0:
                        text_color = theme["positive_text"]
                    elif v < 0:
                        text_color = theme["negative_text"]
                    else:
                        text_color = theme["body_text"]
                else:
                    bg = cell_bg.get(ci)
                    if bg is not None:
                        text_color = _tbl_readable_text_color(bg)
                    else:
                        text_color = theme["body_text"]
            avail_w = x1 - x0 - 2 * cell_pad_x - indent_px
            if geom.col_wraps[ci]:
                lines = _tbl_wrap_text(text_str, font, max(20, avail_w))
                line_h = int(theme["body_font_size"] * 1.45)
                block_h = len(lines) * line_h
                ty = y + (rh - block_h) // 2 + 1
                for line in lines:
                    tw = font.getlength(line)
                    if align == "right":
                        tx = x1 - cell_pad_x - tw
                    elif align == "center":
                        tx = (x0 + x1) // 2 - tw / 2
                    else:
                        tx = x0 + cell_pad_x + indent_px
                    draw.text((tx, ty), line, fill=text_color, font=font)
                    ty += line_h
            else:
                tw = font.getlength(text_str)
                if align == "right":
                    tx = x1 - cell_pad_x - tw
                elif align == "center":
                    tx = (x0 + x1) // 2 - tw / 2
                else:
                    tx = x0 + cell_pad_x + indent_px
                ty = y + rh // 2 - theme["body_font_size"] / 2 - 1
                draw.text((tx, ty), text_str, fill=text_color, font=font)
        if not row_bands and r_idx > 0 and not is_total and not is_subtotal:
            draw.line(
                [(geom.table_x, y), (geom.table_x + geom.table_w, y)],
                fill="#E0E0E0", width=1,
            )
        y += rh


def _tbl_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return _compress_png(buf.getvalue())


_PASSTHROUGH_PREFIXES = (
    "sessions/", "users/", "threads/", "secondary/", "primary/",
    "development/", "context_cache/", "subprocess_logs/",
    "tickets/", "indexes/",
)


def _tbl_resolve_path(save_as: Optional[str], session_path: Optional[str],
                       df: pd.DataFrame, title: Optional[str]) -> str:
    if save_as:
        # Passthrough: if save_as is already rooted at a canonical S3
        # prefix, honour it exactly. This mirrors the convention used by
        # _resolve_session_path() in script_exec_tools.py and matches the
        # behaviour of s3_manager.put() / save_artifact(output_path=...).
        if save_as.startswith(_PASSTHROUGH_PREFIXES):
            return save_as
        rel = save_as
    else:
        slug = re.sub(r"[^A-Za-z0-9_-]+", "_", (title or "table").lower()).strip("_") or "table"
        rel = f"{slug}.png"
    if session_path:
        return f"{session_path.rstrip('/')}/{rel}"
    return rel


@_raise_on_failure
def make_table(
    df: Optional[pd.DataFrame] = None,
    *,
    rows: Optional[List[Union[Dict[str, Any], Tuple, List]]] = None,
    columns: Optional[List[str]] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    caption: Optional[str] = None,
    skin: str = "gs_clean",
    column_formats: Optional[Dict[str, str]] = None,
    column_aligns: Optional[Dict[str, str]] = None,
    header_levels: Optional[List[List[Tuple[str, int]]]] = None,
    row_groups: Optional[List[Tuple[str, int]]] = None,
    row_indent: Optional[List[int]] = None,
    row_bands: bool = True,
    row_colors: Optional[Dict[int, str]] = None,
    column_color_modes: Optional[Dict[str, Union[str, Dict[str, Any]]]] = None,
    heatmap_groups: Optional[List[Dict[str, Any]]] = None,
    rag_thresholds: Optional[Dict[str, Any]] = None,
    highlight_columns: Optional[List[str]] = None,
    cell_colors: Optional[Dict[Tuple[int, int], str]] = None,
    cell_text_colors: Optional[Dict[Tuple[int, int], str]] = None,
    sparkline_columns: Optional[Dict[str, List[List[float]]]] = None,
    minibar_columns: Optional[Dict[str, str]] = None,
    signed_columns: Optional[List[str]] = None,
    total_rows: Optional[List[int]] = None,
    subtotal_rows: Optional[List[int]] = None,
    show_index: bool = False,
    save_as: Optional[str] = None,
    session_path: Optional[str] = None,
    s3_manager: Optional[Any] = None,
    output_dir: str = "",
    user_id: Optional[str] = None,
    target_html_width: int = _TBL_TARGET_HTML_WIDTH_PX,
) -> TableResult:
    """Render a DataFrame as a content-sized PNG table.

    Two data-source paths (mutually exclusive — pass exactly one):
        df=<DataFrame>   data-pulled (Haver / market / CSV / scraper /
                          computed positions).
        rows=[...]       hardcoded narrative tables. Accepts list-of-dicts
                          (column names from keys; pass columns=[...] to
                          reorder) or list-of-tuples/lists (requires
                          columns=[...] to name the headers).

    Canvas is engine-decided. Width = sum of column widths (capped softly
    at ~1400px; wide text columns wrap to fit); height = sum of row
    heights (uncapped, grows to fit every row). The PNG is exactly the
    size the content needs — never preset-bound, never truncated, never
    surrounded by whitespace. PRISM never picks a dimension or canvas.

    PRISM-facing color modes (3 strings): "rwg" / "bw" / "rag".

    Color resolution priority (top wins per cell):
        1. cell_colors[(r, c)]      4. heatmap_groups       7. highlight_columns
        2. total_rows               5. column_color_modes   8. row_groups (handled separately)
        3. subtotal_rows            6. row_colors[r]        9. row_bands
    """
    warnings: List[str] = []

    # Resolve df from rows= when df= not passed.
    if df is None and rows is None:
        return TableResult(
            success=False,
            error_message="Pass either df= (DataFrame) or rows= (list of dicts/tuples)",
        )
    if df is not None and rows is not None:
        return TableResult(
            success=False,
            error_message="Pass either df= or rows=, not both",
        )
    if df is None:
        if not rows:
            return TableResult(
                success=False,
                error_message="rows= is empty; pass at least one row",
            )
        first = rows[0]
        if isinstance(first, dict):
            df = pd.DataFrame(rows)
            if columns is not None:
                missing = [c for c in columns if c not in df.columns]
                if missing:
                    return TableResult(
                        success=False,
                        error_message=f"columns= references keys not in rows: {missing}",
                    )
                df = df[columns]
        elif isinstance(first, (tuple, list)):
            if columns is None:
                return TableResult(
                    success=False,
                    error_message="rows= as list of tuples/lists requires columns=[...] to name the headers",
                )
            df = pd.DataFrame(rows, columns=columns)
        else:
            return TableResult(
                success=False,
                error_message=f"rows= entries must be dicts or tuples/lists, got {type(first).__name__}",
            )

    if df is None or len(df.columns) == 0:
        return TableResult(success=False, error_message="DataFrame has no columns")

    col_names = list(df.columns)
    if len(col_names) != len(set(col_names)):
        from collections import Counter

        dupes = sorted(
            name for name, count in Counter(col_names).items() if count > 1
        )
        return TableResult(
            success=False,
            error_message=(
                "Duplicate column names are not supported in make_table(): "
                f"{dupes}. Each column header must be unique -- rename the "
                "offending columns in the DataFrame (or pass distinct names "
                "via columns=[...] when using rows=) before calling "
                "make_table()."
            ),
        )

    df = df.copy()
    if show_index:
        df.insert(0, df.index.name or "index", df.index.values)
    df = df.reset_index(drop=True)

    column_formats = dict(column_formats or {})
    column_aligns = dict(column_aligns or {})
    rag_thresholds = dict(rag_thresholds or {})
    highlight_columns = list(highlight_columns or [])
    # Normalize cell_colors / cell_text_colors keys: accept (row, col_name) in
    # addition to (row, col_idx). Mirrors column_color_modes's {col_name: ...}
    # convention -- a column NAME is the natural key, an integer index is the
    # fallback. Previously, passing a name silently raised a low-information
    # TypeError from deep inside _tbl_draw_body.
    def _normalize_cell_keys(d):
        if not d:
            return {}
        out = {}
        col_to_idx = {c: i for i, c in enumerate(df.columns)}
        for k, v in d.items():
            if not (isinstance(k, tuple) and len(k) == 2):
                out[k] = v
                continue
            r, c = k
            if isinstance(c, str):
                if c not in col_to_idx:
                    warnings.append(
                        f"cell_colors/cell_text_colors key (r={r}, c={c!r}): "
                        f"column name not in df.columns; skipping"
                    )
                    continue
                c = col_to_idx[c]
            out[(r, c)] = v
        return out

    cell_colors = _normalize_cell_keys(cell_colors)
    cell_text_colors = _normalize_cell_keys(cell_text_colors)
    sparkline_columns = dict(sparkline_columns or {})
    minibar_columns = dict(minibar_columns or {})
    signed_columns = list(signed_columns or [])
    total_rows = list(total_rows or [])
    subtotal_rows = list(subtotal_rows or [])
    row_colors = dict(row_colors or {})
    # Detect heatmap_groups dict-keyed-by-mode shape BEFORE list() coercion
    # (which would discard the values, leaving only the mode keys).
    if isinstance(heatmap_groups, dict):
        return TableResult(
            success=False,
            error_message=(
                f"heatmap_groups={heatmap_groups!r} was passed as a "
                f"dict-keyed-by-mode. Canonical shape is list-of-dicts: "
                f"heatmap_groups=[{{'columns': [...], 'scope': 'column'/'row'/'group', "
                f"'mode': 'sequential'/'diverging'}}, ...] per chart_context.md §13.5."
            ),
            warnings=warnings,
        )
    heatmap_groups = list(heatmap_groups or [])

    raw_modes = column_color_modes or {}
    try:
        column_color_modes = {
            col: _tbl_normalize_mode(spec, col_name=col)
            for col, spec in raw_modes.items()
        }
    except ValidationError as exc:
        return TableResult(
            success=False,
            error_message=str(exc),
            warnings=warnings,
        )

    # Warn loudly when a column is set to 'rag' but no rag_thresholds entry
    # exists for it -- previously the cells rendered silently uncoloured
    # (per A2.d in the 2026-05-16 friction audit). The render still
    # succeeds so the table is usable, but PRISM gets a clear signal.
    for col, spec in column_color_modes.items():
        if spec.get("mode") != "rag":
            continue
        if "thresholds" in spec:
            continue
        if col in rag_thresholds:
            continue
        warnings.append(
            f"column_color_modes[{col!r}]='rag' set but no rag_thresholds[{col!r}] "
            f"provided -- cells will render uncoloured. Add e.g. "
            f"rag_thresholds={{{col!r}: {{'amber_above': X, 'red_above': Y}}}} "
            f"(higher-is-bad) or {{{col!r}: (red_max, amber_max)}} (lower-is-bad)."
        )

    theme = dict(_TABLE_THEME)

    # ---- Shape validation + defensive int() coercion at the boundary ----
    # The engine internals expect (label, span)-tuple form for both
    # header_levels rows and row_groups, with plain int counts (NOT
    # numpy scalars from .value_counts() / .groupby().size()). PRISM
    # naturally reaches for shorthand shapes -- the boundary either
    # coerces them or rejects with a typed error pointing at the
    # canonical form. Never let an unknown shape silently corrupt the
    # downstream geometry / colouring paths.
    if header_levels:
        normalised_levels: List[List[Tuple[str, int]]] = []
        for level_idx, level in enumerate(header_levels):
            if not isinstance(level, (list, tuple)):
                return TableResult(
                    success=False,
                    error_message=(
                        f"header_levels[{level_idx}] must be a list of "
                        f"(label, span) tuples; got {type(level).__name__}. "
                        f"Canonical shape: header_levels=[[(label, span), ...]] "
                        f"per chart_context.md §13.6.1."
                    ),
                )
            normalised_level: List[Tuple[str, int]] = []
            for entry_idx, entry in enumerate(level):
                if isinstance(entry, dict):
                    if "label" in entry and "span" in entry:
                        normalised_level.append((str(entry["label"]), int(entry["span"])))
                        continue
                    return TableResult(
                        success=False,
                        error_message=(
                            f"header_levels[{level_idx}][{entry_idx}]={entry!r} "
                            f"is a dict without both 'label' and 'span' keys. "
                            f"Canonical shape: header_levels=[[(label, span), ...]] "
                            f"per chart_context.md §13.6.1; the engine accepts "
                            f"dict form ONLY when both 'label' and 'span' are present."
                        ),
                    )
                if isinstance(entry, (tuple, list)) and len(entry) == 2:
                    label, span = entry
                    normalised_level.append((str(label), int(span)))
                    continue
                return TableResult(
                    success=False,
                    error_message=(
                        f"header_levels[{level_idx}][{entry_idx}]={entry!r} "
                        f"is not a (label, span) tuple. Canonical shape: "
                        f"header_levels=[[(label, span), ...]] per "
                        f"chart_context.md §13.6.1."
                    ),
                )
            normalised_levels.append(normalised_level)
        header_levels = normalised_levels
        for level_idx, level in enumerate(header_levels):
            total_span = sum(span for _, span in level)
            if total_span != len(df.columns):
                return TableResult(
                    success=False,
                    error_message=f"header_levels[{level_idx}] spans sum to "
                                  f"{total_span}, expected {len(df.columns)}",
                )

    if row_groups:
        normalised_groups: List[Tuple[str, int]] = []
        for grp_idx, grp in enumerate(row_groups):
            if not isinstance(grp, (tuple, list)) or len(grp) != 2:
                return TableResult(
                    success=False,
                    error_message=(
                        f"row_groups[{grp_idx}]={grp!r} is not a (label, count) "
                        f"tuple. Canonical shape: "
                        f"row_groups=[(label, n_rows), ...] per "
                        f"chart_context.md §13.6.2."
                    ),
                )
            label, count = grp
            normalised_groups.append((str(label), int(count)))
        row_groups = normalised_groups
        total = sum(c for _, c in row_groups)
        if total != len(df):
            return TableResult(
                success=False,
                error_message=f"row_groups counts sum to {total}, "
                              f"expected len(df)={len(df)}",
            )

    # heatmap_groups list elements: each must be a dict carrying at least
    # 'columns' (per chart_context.md §13.5). The outer dict-keyed-by-mode
    # case was already rejected above (before list() coercion).
    if heatmap_groups:
        normalised_hg: List[Dict[str, Any]] = []
        for hg_idx, hg in enumerate(heatmap_groups):
            if not isinstance(hg, dict):
                return TableResult(
                    success=False,
                    error_message=(
                        f"heatmap_groups[{hg_idx}]={hg!r} must be a dict "
                        f"with 'columns' (and optional 'scope', 'mode', 'palette'). "
                        f"See chart_context.md §13.5."
                    ),
                    warnings=warnings,
                )
            if "columns" not in hg:
                return TableResult(
                    success=False,
                    error_message=(
                        f"heatmap_groups[{hg_idx}] is missing required 'columns' key. "
                        f"See chart_context.md §13.5."
                    ),
                    warnings=warnings,
                )
            normalised_hg.append(dict(hg))
        heatmap_groups = normalised_hg

    # total_rows / subtotal_rows: coerce numpy scalars to plain int.
    total_rows = [int(r) for r in total_rows]
    subtotal_rows = [int(r) for r in subtotal_rows]

    # Option-C canvas normalization. _tbl_normalize_theme_for_display
    # adapts theme font sizes so the rendered canvas hits the target
    # display-width text size AND stays within bounded aspect ratio.
    # Falls through to a single _tbl_layout() call when the natural
    # canvas is already well-proportioned (the common case). See the
    # constants block above for the bounds.
    theme, geom, _caption_lines, normalize_warnings = (
        _tbl_normalize_theme_for_display(
            df, title, subtitle, caption, theme,
            header_levels, column_formats,
            sparkline_columns, minibar_columns, row_groups,
            target_html_width=target_html_width,
        )
    )
    warnings.extend(normalize_warnings)
    canvas = (geom.canvas_w, geom.canvas_h)

    # ---- Paper-legibility gate (width) --------------------------------
    # Reject a table too wide to read on a portrait 8.5x11 page BEFORE
    # rasterising it. The engine never truncates, so without this gate an
    # over-wide table renders as an illegible micro-text PNG that PRISM
    # would only discover by looking at the pixels. canvas_w is destiny:
    # column count is a poor proxy because numeric columns cannot compress
    # and text columns wrap to a fixed floor. See chart_context.md §13
    # "Width & legibility limits".
    printed_pt = (
        theme["body_font_size"] * _TBL_LEGIBILITY_USABLE_IN * 72 / geom.canvas_w
        if geom.canvas_w else 0.0
    )
    if printed_pt < _TBL_MIN_LEGIBLE_PT:
        return TableResult(
            success=False,
            error_message=(
                f"make_table(): this table is too wide to render legibly on a "
                f"portrait 8.5x11 page. The content-sized canvas is "
                f"{geom.canvas_w}px wide ({len(df.columns)} columns), which "
                f"prints body text at ~{printed_pt:.1f}pt across the "
                f"{_TBL_LEGIBILITY_USABLE_IN:.1f}in usable width -- below the "
                f"{_TBL_MIN_LEGIBLE_PT:.0f}pt legibility floor. make_table never "
                f"truncates, so an over-wide table would just shrink to an "
                f"unreadable PNG. Reduce the rendered width by ONE of: "
                f"(1) TRANSPOSE -- if there are many columns and few rows, swap "
                f"them (e.g. periods-as-rows instead of periods-as-columns); "
                f"(2) SPLIT into several tables by column group (e.g. one per "
                f"year / category) and render each separately; (3) DROP or "
                f"AGGREGATE columns -- show the most recent N periods or a "
                f"summary (latest + 3m + 12m change) instead of every period; "
                f"(4) SHORTEN long headers, which set a non-compressible width "
                f"floor on numeric columns. See chart_context.md §13 'Width & "
                f"legibility limits'."
            ),
            warnings=warnings,
            n_rows=len(df),
            n_cols=len(df.columns),
            canvas_size=canvas,
        )

    img = Image.new("RGB", canvas, theme["background_color"])
    draw = ImageDraw.Draw(img)

    _tbl_draw_title(draw, geom, theme)
    _tbl_draw_header(draw, df, geom, theme, header_levels, column_aligns)
    _tbl_draw_body(
        draw, df, geom, theme,
        column_formats, column_aligns, column_color_modes, heatmap_groups,
        rag_thresholds, row_bands, row_groups, row_indent, row_colors,
        cell_colors, cell_text_colors, highlight_columns,
        sparkline_columns, minibar_columns, signed_columns,
        total_rows, subtotal_rows,
    )

    _tbl_draw_caption(draw, caption, geom, theme)

    # Horizontal rules closing the body region top and bottom. The top
    # rule sits between the header band and the first data row; the
    # bottom rule sits between the last data row and the caption (or,
    # when there is no caption, between the body and the canvas bottom
    # pad). ``geom.caption_y == body_top_y + body_h`` regardless of
    # whether a caption was set, so it is the canonical "end of body"
    # coordinate. Without the bottom rule, an unbanded last row's
    # internal padding merged visually with the canvas's bottom pad,
    # producing ~15 px of perceived "white space at the bottom".
    draw.line(
        [(geom.table_x, geom.body_top_y - 1),
         (geom.table_x + geom.table_w, geom.body_top_y - 1)],
        fill="#1F1F1F", width=1,
    )
    draw.line(
        [(geom.table_x, geom.caption_y),
         (geom.table_x + geom.table_w, geom.caption_y)],
        fill="#1F1F1F", width=1,
    )

    buf = _tbl_png_bytes(img)
    out_path = _tbl_resolve_path(save_as, session_path, df, title)

    written_path: Optional[str] = None
    presigned_url: Optional[str] = None
    if s3_manager is not None:
        try:
            # s3_manager.put() returns None; the canonical path is out_path
            # itself. (Previously we assigned the return value to written_path,
            # which silently produced png_path=None on every successful table
            # render.)
            s3_manager.put(buf, out_path)
            written_path = out_path
        except Exception as e:  # noqa: BLE001
            return TableResult(
                success=False,
                error_message=f"s3_manager.put failed: {e}",
                warnings=warnings,
            )
        # Best-effort presigned URL for download convenience. Falls back to
        # the local-path shim when the manager exposes one (dev mode).
        try:
            presigned_url = generate_presigned_download_url(written_path).presigned_url
        except Exception:  # noqa: BLE001
            if hasattr(s3_manager, "local_path"):
                presigned_url = f"file://{s3_manager.local_path(out_path).resolve()}"
    else:
        local_root = Path(output_dir or "./session_output").expanduser().resolve()
        local_root.mkdir(parents=True, exist_ok=True)
        full = local_root / out_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(buf)
        written_path = str(full)
        presigned_url = f"file://{full}"

    return TableResult(
        success=True,
        png_path=written_path,
        download_url=presigned_url,
        warnings=warnings,
        n_rows=len(df),
        n_cols=len(df.columns),
        truncated_rows=0,
        canvas_size=canvas,
    )


_ENGINE_NAMESPACE_TABLES: Tuple[str, ...] = (
    "make_table",
    "TableResult",
)


# v2 namespace constant -- the names PRISM should auto-inject when
# the v2 skill (chart_context_v2.md) is loaded. See ``__all__`` for
# the full module export list (which carries both v1 and v2 names).
_ENGINE_NAMESPACE_V2: Tuple[str, ...] = (
    # Builders
    "Chart",
    "render_grid",
    "render_all",
    # Result types (shared with v1)
    "ChartResult",
    "CompositeResult",
    "DataProfile",
    # Pre-charting helper (shared with v1)
    "profile_df",
    # Annotations (shared with v1)
    "VLine",
    "HLine",
    "Segment",
    "Band",
    "Arrow",
    "PointLabel",
    "PointHighlight",
    "Callout",
    "LastValueLabel",
    "Trendline",
    "PlotText",
)


# ---------------------------------------------------------------------------
# Public entry-point gating (failures bubble up instead of being swallowed)
# ---------------------------------------------------------------------------
# PRISM's execute_analysis_script only surfaces a chart failure to the LLM
# when the script raises; a returned ``*Result(success=False)`` is discarded
# silently. ``make_chart`` is impl-split: ``_make_chart`` stays non-raising
# (the auto-recovery recursion + Chart.preview/render inspect its
# ``success`` flag), while the public ``make_chart`` name is the gated
# wrapper. ``make_table`` and the ``make_*pack_*`` helpers are gated in place
# via the ``@_raise_on_failure`` decorator on their defs. See
# ``_raise_on_failure`` for the routing rationale.
_make_chart.__name__ = "make_chart"
_make_chart.__qualname__ = "make_chart"
make_chart = _raise_on_failure(_make_chart)


# ===========================================================================
# MODULE: PUBLIC API SURFACE
# ===========================================================================

# Anything not listed here is internal and may change without notice.
__all__ = [
    # ---- Type aliases ----------------------------------------------
    "ChartType",
    "IntentType",
    "DimensionPreset",
    "LayoutType",
    # ---- Result / profile types (shared) --------------------------
    "ChartResult",
    "CompositeResult",
    "DataProfile",
    "ChartSpec",
    # ---- v1 entry points ------------------------------------------
    "make_chart",
    "make_composite",
    "make_2pack_horizontal",
    "make_2pack_vertical",
    "make_3pack_triangle",
    "make_4pack_grid",
    "make_6pack_grid",
    "check_charts_quality",
    "profile_df",
    # ---- v2 entry points ------------------------------------------
    "Chart",
    "render_grid",
    "render_all",
    # ---- Annotations (shared) -------------------------------------
    "Annotation",
    "VLine",
    "HLine",
    "Band",
    "Arrow",
    "PointLabel",
    "Trendline",
    # ---- Skins / dimensions ---------------------------------------
    "AVAILABLE_SKINS",
    "DIMENSION_PRESETS",
    "DATE_FORMAT_PRESETS",
    "COMPOSITE_DIMENSIONS",
    "get_skin",
    "get_dimensions",
    "list_skins",
    "list_dimension_presets",
    # ---- Validation / errors --------------------------------------
    "ValidationError",
    "YAxisLabelTooLongError",
    "LvlSeriesNameTooLongError",
    "LegendLabelTooLongError",
    "HeatmapRowLabelTooLongError",
    "validate_plot_ready_df",
    # ---- Static spec utilities ------------------------------------
    "create_static_spec",
    "create_static_composite_spec",
    "clean_chart",
    # ---- Phase B helpers exposed to PRISM -------------------------
    "TYPOGRAPHY_OVERRIDES",
    # ---- Phase C utility functions --------------------------------
    "prepare_timeseries_df",
    "process_data",
    "top_k_categories",
    "detect_scale_issues",
    "smart_label_format",
    "calculate_safe_axis_range",
    "generate_chart_filename",
    "check_for_outliers",
    "suggest_chart_type",
    "validate_data",
    # ---- Tables (PNG static-table engine; same DIMENSION_PRESETS as charts)
    "make_table",
    "TableResult",
    # ---- Engine namespace constants (PRISM-side injection consumer)
    "_ENGINE_NAMESPACE_V2",
    "_ENGINE_NAMESPACE_TABLES",
]


__version__ = "0.4.0"
