#!/usr/bin/env python3
"""
echart_dashboard -- manifest-first dashboard composer and compiler.

The manifest is the source of truth -- a recyclable, LLM-editable JSON asset
that fully describes a dashboard. Two entry points render a manifest to HTML:

    compile_dashboard(spec)     JSON-first. Accepts a dict, a path to a JSON
                                file, or a JSON string. Recommended for LLMs.

    Dashboard(...).build(...)   Python builder sugar. Useful when composing
                                from DataFrames in notebooks / scripts.

Both paths converge on the same compiler pipeline:

    manifest  ->  validator  ->  spec resolver  ->  HTML renderer
                                  (spec -> option)    (dashboard_html.py)

Example: JSON-first (PRISM's preferred shape)
---------------------------------------------

    from echart_dashboard import compile_dashboard

    manifest = {
      "schema_version": 1,
      "id": "rates_monitor",
      "title": "Rates monitor",
      "theme": "gs_clean",
      "datasets": {
        "rates": {"source": [
          ["date", "us_2y", "us_10y", "2s10s"],
          ["2026-04-22", 4.12, 4.48, 36.0],
          ...
        ]}
      },
      "filters": [
        # dateRange in view-mode (default): sets the initial dataZoom
        # window on every targeted chart. Charts always render full
        # history; tables and KPIs that target this filter still get
        # real row-level filtering. Default label is "Initial range"
        # when none is supplied.
        {"id": "lookback", "type": "dateRange", "default": "6M",
         "targets": ["*"], "field": "date"}
      ],
      "layout": {
        "kind": "tabs",
        "tabs": [{
          "id": "overview", "label": "Overview",
          "rows": [[{
            "widget": "chart", "id": "curve", "w": 12,
            "spec": {
              "chart_type": "multi_line",
              "dataset": "rates",
              "mapping": {"x": "date", "y": ["us_2y", "us_10y"]},
              "title": "UST curve"
            }
          }]]
        }]
      }
    }

    r = compile_dashboard(manifest, session_path="sessions/demo")
    # r.manifest_path -> sessions/demo/dashboards/rates_monitor.json
    # r.html_path     -> sessions/demo/dashboards/rates_monitor.html

Example: Python builder
-----------------------

    from echart_dashboard import (
        Dashboard, ChartRef, KPIRef, GlobalFilter, Link,
    )

    db = (Dashboard(id="rates_monitor", title="Rates monitor")
          .add_dataset("rates", rates_df)
          .add_filter(GlobalFilter(id="lookback", type="dateRange",
                                    default="6M", targets=["*"]))
          .add_row([
              ChartRef(id="curve", w=12,
                        spec={"chart_type": "multi_line",
                              "dataset": "rates",
                              "mapping": {"x": "date",
                                          "y": ["us_2y", "us_10y"]}}),
          ]))
    r = db.build(session_path="sessions/demo")
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from rendering import render_dashboard_html
from config import MAX_DASHBOARD_DECIMALS, clamp_decimals

# =============================================================================
# MANIFEST SCHEMA + VALIDATOR
# =============================================================================

SCHEMA_VERSION = 1
# ``VALID_WIDGETS``, ``FILTER_TARGETABLE_WIDGETS`` and
# ``DATA_BOUND_WIDGETS`` are derived from the ``WIDGETS`` registry below;
# see the ``WIDGET REGISTRY`` section. Adding a widget kind = one entry
# in ``WIDGETS`` plus one validator function -- nothing else here changes.

VALID_TOOL_INPUT_KINDS = {"scalar", "sweep", "expression", "matrix"}
VALID_TOOL_INPUT_TYPES = {
    "number", "date", "text", "select", "radio", "toggle",
    "list_of_strings",
}
VALID_TOOL_OUTPUT_KINDS = {
    "stat", "scalar", "param", "kpi", "series",
    "table", "stat_grid", "distribution",
}
# Semantic kinds for the `note` widget (callouts for narrative writing).
# Each kind drives a distinct accent color + label so PRISM can flag
# load-bearing prose ("this is the thesis", "this is a risk", etc.)
# rather than relying on a flat markdown widget for everything.
#
# ``NOTE_KINDS`` is the single source of truth: ``kind`` -> human-
# readable label. The renderer in ``rendering.py`` imports this dict
# to build the in-card "Insight" / "Thesis" / ... badge. The
# validator-side ``VALID_NOTE_KINDS`` is derived from the keys.
NOTE_KINDS: Dict[str, str] = {
    "insight": "Insight",
    "thesis":  "Thesis",
    "watch":   "Watch",
    "risk":    "Risk",
    "context": "Context",
    "fact":    "Fact",
}
VALID_NOTE_KINDS = frozenset(NOTE_KINDS)
VALID_FILTERS = {"dateRange", "select", "multiSelect", "numberRange",
                  "toggle", "slider", "radio", "text", "number",
                  "rule"}
VALID_FILTER_OPS = {"==", "!=", ">", ">=", "<", "<=",
                     "contains", "startsWith", "endsWith",
                     "in", "not_in"}
VALID_SYNC = {"axis", "tooltip", "legend", "dataZoom"}
VALID_BRUSH_TYPES = {"rect", "polygon", "lineX", "lineY"}
VALID_REFRESH_FREQUENCIES = {"hourly", "daily", "weekly", "manual"}

# Supported column format tokens for table widgets.
# Examples: "number:2" (2 decimals), "percent:1", "currency:2",
# "bps:0", "integer", "date", "datetime", "text", "link".
VALID_TABLE_FORMATS = {
    "text", "number", "integer", "percent", "currency", "bps",
    "date", "datetime", "link", "signed", "delta",
}

# =============================================================================
# CHART-TYPE REGISTRY
# =============================================================================
#
# ``CHART_TYPES`` is the single source of truth for the set of chart
# kinds the dashboard accepts AND for cross-cutting flags about how
# each kind interacts with client-side filter state and the per-tile
# stat-strip popup. The corresponding builder function for each kind
# lives in ``echart_studio._BUILDER_DISPATCH``; the bijection between
# this dict's keys and that one's keys is pinned by
# ``test_chart_type_dispatch_covers_valid_chart_types`` in
# ``dev/tests.py``. Adding a new chart type means: (1) one entry
# here, (2) one entry in ``_BUILDER_DISPATCH`` pointing to the
# builder, (3) a documentation row in ``dashboards.md`` Section 3.1.
#
# Finance-flavoured additions:
#   waterfall  -- P&L attribution / decomposition
#   slope      -- two-period side-by-side comparison across categories
#   fan_cone   -- forecast / confidence-cone ribbon (median + bands)
#   marimekko  -- 2D categorical proportions (stacked bar with variable widths)


@dataclass(frozen=True)
class ChartTypeSpec:
    """Schema descriptor for a single chart type.

    Holds cross-cutting flags about how the chart behaves at the
    validator / orchestrator layer. The corresponding builder
    function lives in ``echart_studio._BUILDER_DISPATCH``.

    Fields
    ------
    kind : str
        The chart-type identifier as it appears in
        ``manifest.layout.rows[][].spec.chart_type``.
    rewire_strategy : Optional[str]
        How (if at all) the chart's series can be re-rendered
        client-side from a filtered dataset_ref WITHOUT re-invoking
        the Python builder.
            ``None``      -- pre-baked series.data; no client rewire.
                             Filter state still drives KPI / table
                             updates referencing the same
                             dataset_ref, but this chart's series
                             stay fixed.
            ``"reshape"`` -- wide-form dataset; the JS substitutes
                             the encode mapping after the row filter,
                             no builder call needed (line / bar /
                             area / multi_line in vanilla shapes).
                             Mapping-shape conditions in
                             ``_is_safe_for_rewire`` further gate
                             the actual auto-wire decision.
            ``"rebuild"`` -- the JS rebuilds the entire echarts
                             option from the filtered dataset
                             (scatter_studio, correlation_matrix).
                             Independent of mapping shape.
    stat_strip_eligible : bool
        Whether the per-tile Sigma toolbar button (current value /
        deltas at standard horizons / range / percentile rank) is
        rendered for this chart type. Only meaningful for time-
        series-flavoured charts. Suppressible per-widget via
        ``spec.stat_strip = false``.
    """
    kind: str
    rewire_strategy: Optional[str] = None  # None | "reshape" | "rebuild"
    stat_strip_eligible: bool = False


CHART_TYPES: Dict[str, ChartTypeSpec] = {
    "line":               ChartTypeSpec("line",
                            rewire_strategy="reshape",
                            stat_strip_eligible=True),
    "multi_line":         ChartTypeSpec("multi_line",
                            rewire_strategy="reshape",
                            stat_strip_eligible=True),
    "bar":                ChartTypeSpec("bar",
                            rewire_strategy="reshape"),
    "bar_horizontal":     ChartTypeSpec("bar_horizontal"),
    "scatter":            ChartTypeSpec("scatter"),
    "scatter_multi":      ChartTypeSpec("scatter_multi"),
    "scatter_studio":     ChartTypeSpec("scatter_studio",
                            rewire_strategy="rebuild"),
    "area":               ChartTypeSpec("area",
                            rewire_strategy="reshape",
                            stat_strip_eligible=True),
    "heatmap":            ChartTypeSpec("heatmap"),
    "correlation_matrix": ChartTypeSpec("correlation_matrix",
                            rewire_strategy="rebuild"),
    "pie":                ChartTypeSpec("pie"),
    "donut":              ChartTypeSpec("donut"),
    "boxplot":            ChartTypeSpec("boxplot"),
    "histogram":          ChartTypeSpec("histogram"),
    "bullet":             ChartTypeSpec("bullet"),
    "sankey":             ChartTypeSpec("sankey"),
    "treemap":            ChartTypeSpec("treemap"),
    "sunburst":           ChartTypeSpec("sunburst"),
    "graph":              ChartTypeSpec("graph"),
    "candlestick":        ChartTypeSpec("candlestick"),
    "radar":              ChartTypeSpec("radar"),
    "gauge":              ChartTypeSpec("gauge"),
    "calendar_heatmap":   ChartTypeSpec("calendar_heatmap"),
    "funnel":             ChartTypeSpec("funnel"),
    "parallel_coords":    ChartTypeSpec("parallel_coords"),
    "tree":               ChartTypeSpec("tree"),
    "waterfall":          ChartTypeSpec("waterfall"),
    "slope":              ChartTypeSpec("slope"),
    "fan_cone":           ChartTypeSpec("fan_cone"),
    "marimekko":          ChartTypeSpec("marimekko"),
}

VALID_CHART_TYPES = frozenset(CHART_TYPES)
RESHAPE_REWIREABLE_CHART_TYPES = frozenset(
    k for k, spec in CHART_TYPES.items()
    if spec.rewire_strategy == "reshape"
)
REBUILD_REWIREABLE_CHART_TYPES = frozenset(
    k for k, spec in CHART_TYPES.items()
    if spec.rewire_strategy == "rebuild"
)
STAT_STRIP_ELIGIBLE_CHART_TYPES = frozenset(
    k for k, spec in CHART_TYPES.items() if spec.stat_strip_eligible
)

# Aggregators recognised by the KPI / stat_grid runtime resolver.
# MUST mirror the ``resolveAgg`` switch in rendering.py's dashboard JS;
# any divergence produces silent ``--`` placeholders that don't fire a
# diagnostic. The JS implementation is pinned via TestKPIResolution.
VALID_KPI_AGGREGATORS = {
    "latest", "first", "sum", "mean", "min", "max", "count", "prev",
}


# =============================================================================
# TOOL-DEF LOADER  (used by widget: tool)
# =============================================================================
#
# A tool def is a JSON dict declaring inputs, outputs, and a JS compute
# string. The engine treats it as DATA -- domain-blind. Every tool def
# travels INLINE inside its dashboard manifest; there is no runtime
# registry or shared library on disk. Canonical reference templates
# live in staging at ``GS/viz/echarts/dev/tool_examples/<name>/``;
# PRISM cribs from them at authoring time and emits the def inline.
#
# Two equivalent compute shapes are accepted at the input layer:
#
#     "compute_js": "function compute(inputs){...}"          <- canonical
#     "compute":    {"kind": "js", "source": "function..."}  <- legacy nested
#
# Both normalise to the same internal representation
# (``compute = {"kind": "js", "source": "..."}``) so the validator,
# renderer, and JS runtime see one shape only. The flat ``compute_js``
# field is the canonical authoring form going forward; the nested
# ``compute.kind`` shape is retained for back-compat with manifests
# already on S3. PRISM-side authoring guidance lives in
# ``dashboards.md`` section 4.11.

def load_tool_def(ref: Any) -> Dict[str, Any]:
    """Resolve a tool_def reference to a fully-populated def dict.

    The only accepted shape is an inline dict. Strings are rejected
    with a message pointing at the inline-dict pattern; a registry
    lookup is intentionally not supported (every tool ships INLINE
    inside the manifest that uses it, so there is nowhere for the
    engine to "look up" a string ref).
    """
    if isinstance(ref, dict):
        return normalize_tool_def(ref)
    raise ValueError(
        f"tool_def must be an inline dict, got {type(ref).__name__}: "
        f"{ref!r}. The engine does not resolve string refs to a tool "
        f"library -- bake the def into the manifest. See "
        f"`dashboards.md` section 4.11 for the inline pattern; "
        f"canonical reference templates live at "
        f"`GS/viz/echarts/dev/tool_examples/<name>/` (staging-only) "
        f"for cribbing."
    )


def normalize_tool_def(d: Dict[str, Any]) -> Dict[str, Any]:
    """Fill defaults + rewrite the ``compute_js`` shortcut to the
    canonical ``compute = {"kind": "js", "source": ...}`` shape so
    downstream code (validator, renderer, JS runtime) sees one shape
    only. Returns a new dict; the input is not mutated.

    When both ``compute_js`` and a fully-shaped ``compute`` block are
    present, ``compute`` wins (the explicit nested form is more
    specific) and the shortcut is silently dropped, mirroring how
    ``dict.setdefault`` treats already-set keys.
    """
    d = dict(d)
    d.setdefault("inputs", [])
    d.setdefault("outputs", [])
    d.setdefault("display", {})
    if "compute_js" in d:
        flat = d.pop("compute_js")
        if "compute" not in d:
            d["compute"] = {"kind": "js", "source": flat}
    d.setdefault(
        "compute",
        {"kind": "js", "source": "function compute(){return {};}"},
    )
    return d


def _err(path: str, msg: str) -> str:
    return f"{path}: {msg}"


# DOM ids reserved by the rendering shell for the always-on header chrome
# (Methodology / Refresh / Share / Download dropdown / theme toggle / data-as-of
# pill / refresh-error pill). A manifest's ``header_actions[].id`` cannot
# collide with any of these -- the chrome is non-suppressible and an authored
# button with one of these ids would silently shadow the live chrome at runtime.
def _validate_tool_widget(w: Dict[str, Any], wbase: str,
                            errs: List[str],
                            dataset_names: Any) -> None:
    """Validate a `widget: tool` entry.

    Checks that:
      - `tool_def` is set and an inline dict (the engine rejects string refs).
      - the resolved def has a non-empty JS compute source and
        ``inputs`` / ``outputs`` lists. The compute source can be set
        via the canonical flat ``compute_js: "..."`` field OR the legacy
        nested ``compute: {kind: "js", source: "..."}`` shape; both are
        normalised to the same internal representation by
        ``load_tool_def`` before this validator runs.
      - every input id is unique and uses one of the known kinds + types.
      - every matrix input's ``rows_from.dataset`` references a known dataset.
      - per-input initial values (when given) parse to the declared type.
      - every output declares one of the supported kinds.
    """
    ref = w.get("tool_def")
    if ref is None:
        errs.append(_err(f"{wbase}.tool_def",
                            "tool widget requires 'tool_def'"))
        return
    try:
        tdef = load_tool_def(ref)
    except Exception as e:
        errs.append(_err(f"{wbase}.tool_def",
                            f"could not resolve tool def: {e}"))
        return

    if not isinstance(tdef.get("compute"), dict):
        errs.append(_err(f"{wbase}.tool_def.compute",
                            "tool def is missing a `compute` block"))
        return
    src = tdef["compute"].get("source")
    if not src or not isinstance(src, str):
        errs.append(_err(f"{wbase}.tool_def.compute.source",
                            "tool def compute.source is empty or missing"))

    seen_ids: set = set()
    for ii, inp in enumerate(tdef.get("inputs", []) or []):
        ipath = f"{wbase}.tool_def.inputs[{ii}]"
        if not isinstance(inp, dict):
            errs.append(_err(ipath, "must be a dict"))
            continue
        iid = inp.get("id")
        if not iid:
            errs.append(_err(f"{ipath}.id", "required"))
            continue
        if iid in seen_ids:
            errs.append(_err(f"{ipath}.id",
                                f"duplicate input id '{iid}'"))
        seen_ids.add(iid)
        kind = inp.get("kind", "scalar")
        if kind not in VALID_TOOL_INPUT_KINDS:
            errs.append(_err(f"{ipath}.kind",
                                f"'{kind}' not in "
                                f"{sorted(VALID_TOOL_INPUT_KINDS)}"))
        if kind == "scalar":
            ty = inp.get("type", "number")
            if ty not in VALID_TOOL_INPUT_TYPES:
                errs.append(_err(
                    f"{ipath}.type",
                    f"scalar type '{ty}' not in "
                    f"{sorted(VALID_TOOL_INPUT_TYPES)}"))
            if ty in ("select", "radio") and not inp.get("options"):
                errs.append(_err(
                    f"{ipath}.options",
                    "required for select/radio scalar"))
        elif kind == "matrix":
            rows_from = inp.get("rows_from")
            cols      = inp.get("cols")
            cols_from = inp.get("cols_from")
            if not rows_from and not isinstance(inp.get("rows"), list):
                errs.append(_err(
                    f"{ipath}.rows_from|rows",
                    "matrix input needs `rows_from` (dataset binding) "
                    "OR static `rows` list"))
            if not cols and not cols_from:
                errs.append(_err(
                    f"{ipath}.cols|cols_from",
                    "matrix input needs `cols` (static list) "
                    "OR `cols_from` (dynamic ref)"))
            if isinstance(rows_from, dict):
                ds = rows_from.get("dataset")
                if ds and dataset_names is not None and \
                   ds not in dataset_names:
                    errs.append(_err(
                        f"{ipath}.rows_from.dataset",
                        f"dataset '{ds}' not declared in "
                        f"manifest.datasets (available: "
                        f"{sorted(dataset_names)})"))
                if ds and not rows_from.get("key_col"):
                    errs.append(_err(
                        f"{ipath}.rows_from.key_col",
                        "required when `rows_from.dataset` is set"))
            cell = inp.get("cell")
            if not isinstance(cell, dict):
                errs.append(_err(
                    f"{ipath}.cell",
                    "matrix input needs `cell` dict (type, default, ...)"))
        # `sweep` and `expression` kinds: defer until Phase 4.

    seen_outs: set = set()
    for oi, out in enumerate(tdef.get("outputs", []) or []):
        opath = f"{wbase}.tool_def.outputs[{oi}]"
        if not isinstance(out, dict):
            errs.append(_err(opath, "must be a dict"))
            continue
        oid = out.get("id")
        if not oid:
            errs.append(_err(f"{opath}.id", "required"))
            continue
        if oid in seen_outs:
            errs.append(_err(f"{opath}.id",
                                f"duplicate output id '{oid}'"))
        seen_outs.add(oid)
        okind = out.get("kind")
        if okind not in VALID_TOOL_OUTPUT_KINDS:
            errs.append(_err(
                f"{opath}.kind",
                f"'{okind}' not in {sorted(VALID_TOOL_OUTPUT_KINDS)}"))


def _validate_filter_rule(rule: Any, base_path: str,
                            errs: List[str],
                            depth: int = 0) -> None:
    """Recursively validate a compound filter rule tree.

    Grammar (mirrors `show_when`):
        rule := {all: [rule, ...]}      AND
              | {any: [rule, ...]}      OR
              | {not: rule}             NOT
              | {field, op, value}      leaf comparison
              | {all/any/not + leaf-keys}  -- error: must be exactly one shape

    Leaf nodes use the standard filter ops (`VALID_FILTER_OPS`); `op`
    defaults to `"=="` when absent. `op="in"` / `"not_in"` expects
    `value` to be a list. Other ops expect a scalar.

    Stops at depth 12 to prevent runaway nesting blowing up the
    runtime evaluator's call stack on hand-authored manifests.
    """
    if depth > 12:
        errs.append(_err(base_path,
                            "rule nesting exceeds 12 levels deep"))
        return
    if not isinstance(rule, dict):
        errs.append(_err(base_path,
                            "rule node must be a dict"))
        return
    keys = set(rule.keys())
    boolean_ops = keys & {"all", "any", "not"}
    leaf_keys   = keys & {"field", "op", "value"}

    if boolean_ops and leaf_keys:
        errs.append(_err(
            base_path,
            f"rule node mixes boolean ops {sorted(boolean_ops)} with "
            f"leaf keys {sorted(leaf_keys)}; pick one shape"
        ))
        return

    if len(boolean_ops) > 1:
        errs.append(_err(
            base_path,
            f"rule node has multiple boolean ops {sorted(boolean_ops)}; "
            "use exactly one of 'all', 'any', 'not'"
        ))
        return

    unknown = keys - {"all", "any", "not", "field", "op", "value"}
    if unknown:
        errs.append(_err(
            base_path,
            f"unknown rule keys: {sorted(unknown)}; "
            "valid: 'all', 'any', 'not', 'field', 'op', 'value'"
        ))

    if "all" in rule or "any" in rule:
        op_key = "all" if "all" in rule else "any"
        kids = rule[op_key]
        if not isinstance(kids, list):
            errs.append(_err(f"{base_path}.{op_key}",
                                f"'{op_key}' must be a list of rule nodes"))
            return
        if not kids:
            errs.append(_err(f"{base_path}.{op_key}",
                                f"'{op_key}' must not be empty"))
            return
        for j, child in enumerate(kids):
            _validate_filter_rule(
                child, f"{base_path}.{op_key}[{j}]", errs, depth + 1
            )
    elif "not" in rule:
        _validate_filter_rule(
            rule["not"], f"{base_path}.not", errs, depth + 1
        )
    else:
        # Leaf: must have `field`. `op` defaults to "==", `value` required
        # unless op is is_null / is_not_null (not implemented in v1).
        field = rule.get("field")
        if not field or not isinstance(field, str):
            errs.append(_err(f"{base_path}.field",
                                "leaf rule requires a string 'field'"))
        op = rule.get("op", "==")
        if op not in VALID_FILTER_OPS:
            errs.append(_err(
                f"{base_path}.op",
                f"'{op}' not in {sorted(VALID_FILTER_OPS)}"
            ))
        if "value" not in rule:
            errs.append(_err(f"{base_path}.value",
                                "leaf rule requires a 'value'"))
        else:
            value = rule["value"]
            if op in ("in", "not_in"):
                if not isinstance(value, list) or len(value) == 0:
                    errs.append(_err(
                        f"{base_path}.value",
                        f"op='{op}' requires a non-empty list value"
                    ))
            else:
                if isinstance(value, list):
                    errs.append(_err(
                        f"{base_path}.value",
                        f"op='{op}' expects a scalar value, got list"
                    ))


# =============================================================================
# WIDGET REGISTRY
# =============================================================================
#
# Each widget kind has exactly one entry in ``WIDGETS`` below. The registry
# is the single source of truth for:
#
#   * which widget literals are valid                        (VALID_WIDGETS)
#   * which widgets a filter can target                      (FILTER_TARGETABLE_WIDGETS)
#   * which widgets consume a manifest dataset               (DATA_BOUND_WIDGETS)
#   * how to validate a widget dict                          (spec.validate)
#
# Adding a new widget kind = add one ``WidgetSpec`` entry below + one
# ``_validate_<kind>_widget`` function above + one render branch in
# ``rendering.py`` (``_render_widget``). VALID_WIDGETS,
# FILTER_TARGETABLE_WIDGETS and DATA_BOUND_WIDGETS auto-derive.
#
# The per-widget validators all share the signature:
#
#     _validate_<kind>_widget(w, wbase, errs, dataset_names) -> None
#
# Each appends error strings to ``errs`` for any structural issue with
# ``w`` (the widget dict). ``wbase`` is the dotted path prefix used to
# qualify error messages (e.g. ``"layout.rows[0][1]"``). ``dataset_names``
# is the set of declared ``manifest.datasets`` keys, used for cross-
# reference validation. Generic per-widget concerns that apply to every
# widget (``id`` uniqueness, ``w`` width clamp, ``show_when`` shape) live
# in the dispatch loop in ``_validate_rows`` below, NOT here.
#
# The ``data_bound`` and ``filter_targetable`` flags are independently
# settable: today they happen to coincide (every data-bound widget is
# also filter-targetable), but the abstraction permits future widgets
# that consume a dataset for display only (``filter_targetable=False``)
# or a non-data widget that filters can address (e.g. a future
# ``commentary`` widget whose copy varies by filter state).


def _validate_chart_widget(w: Dict[str, Any], wbase: str,
                            errs: List[str], dataset_names: Any) -> None:
    """Validate a ``widget: chart`` entry."""
    has_ref = bool(w.get("ref"))
    has_option = isinstance(w.get("option"), dict)
    has_option_inline = isinstance(w.get("option_inline"), dict)
    spec = w.get("spec")
    has_spec = isinstance(spec, dict)
    if not (has_ref or has_option or has_option_inline or has_spec):
        errs.append(_err(
            f"{wbase}",
            "chart widget requires one of 'spec' (high-level), "
            "'ref' (spec file path), or 'option' (inline ECharts dict)"
        ))
    if has_spec:
        ct = spec.get("chart_type")
        if not ct:
            errs.append(_err(f"{wbase}.spec.chart_type", "required"))
        elif ct not in VALID_CHART_TYPES:
            errs.append(_err(
                f"{wbase}.spec.chart_type",
                f"'{ct}' not in {sorted(VALID_CHART_TYPES)}"
            ))
        ds = spec.get("dataset")
        if not ds:
            errs.append(_err(f"{wbase}.spec.dataset", "required"))
        elif ds not in dataset_names:
            errs.append(_err(
                f"{wbase}.spec.dataset",
                f"'{ds}' not declared in manifest.datasets "
                f"(available: {sorted(dataset_names)})"
            ))
        if "mapping" not in spec:
            errs.append(_err(f"{wbase}.spec.mapping", "required"))
        elif not isinstance(spec["mapping"], dict):
            errs.append(_err(f"{wbase}.spec.mapping", "must be a dict"))
        palette = spec.get("palette")
        if palette:
            from config import PALETTES
            if palette not in PALETTES:
                errs.append(_err(
                    f"{wbase}.spec.palette",
                    f"unknown palette '{palette}'; "
                    f"valid: {sorted(PALETTES.keys())}"
                ))
        theme_override = spec.get("theme")
        if theme_override:
            from config import THEMES
            if theme_override not in THEMES:
                errs.append(_err(
                    f"{wbase}.spec.theme",
                    f"unknown theme '{theme_override}'; "
                    f"valid: {sorted(THEMES.keys())}"
                ))
        # Title / subtitle live at the widget level only. The tile header
        # chrome renders them; charts share the same uniform header
        # contract as KPIs / tables / markdown tiles. PNG export bakes
        # the widget title back into the option, so there is no PNG
        # reason to keep a spec-level title either.
        if "title" in spec:
            errs.append(_err(
                f"{wbase}.spec.title",
                "not allowed -- put the title at the widget "
                "level (sibling of 'spec'). The tile header "
                "renders it and PNG exports inject it "
                "automatically."
            ))
        if "subtitle" in spec:
            errs.append(_err(
                f"{wbase}.spec.subtitle",
                "not allowed -- put the subtitle at the "
                "widget level (sibling of 'spec'). It "
                "renders italic under the tile title."
            ))
        if "keep_title" in spec:
            errs.append(_err(
                f"{wbase}.spec.keep_title",
                "not allowed -- spec.title is rejected, so "
                "there is nothing to keep. Remove this key."
            ))
    dsr = w.get("dataset_ref")
    if dsr and dsr not in dataset_names:
        errs.append(_err(
            f"{wbase}.dataset_ref",
            f"dataset '{dsr}' not declared in manifest.datasets"
        ))
    click_popup = w.get("click_popup")
    if click_popup is not None and not isinstance(click_popup, (dict, bool)):
        errs.append(_err(
            f"{wbase}.click_popup",
            "must be a dict, or boolean false to suppress the "
            "default provenance popup; got "
            f"{type(click_popup).__name__}. Dict shape mirrors "
            "table 'row_click': title_field, subtitle_template, "
            "popup_fields, or detail.sections[]"
        ))


def _validate_kpi_widget(w: Dict[str, Any], wbase: str,
                          errs: List[str], dataset_names: Any) -> None:
    """Validate a ``widget: kpi`` entry."""
    for req in ("label",):
        if req not in w:
            errs.append(_err(f"{wbase}.{req}", f"required for kpi"))


def _validate_table_widget(w: Dict[str, Any], wbase: str,
                            errs: List[str], dataset_names: Any) -> None:
    """Validate a ``widget: table`` entry."""
    if not w.get("ref") and not w.get("dataset_ref"):
        errs.append(_err(
            f"{wbase}.ref|dataset_ref",
            "table widget requires 'ref' or 'dataset_ref'"
        ))
    cols_def = w.get("columns")
    if cols_def is not None:
        if not isinstance(cols_def, list):
            errs.append(_err(f"{wbase}.columns",
                              "must be a list of column dicts"))
        else:
            for ci, col in enumerate(cols_def):
                cbase = f"{wbase}.columns[{ci}]"
                if not isinstance(col, dict):
                    errs.append(_err(cbase, "must be a dict"))
                    continue
                if "field" not in col:
                    errs.append(_err(f"{cbase}.field", "required"))
                align = col.get("align")
                if align and align not in ("left", "center", "right"):
                    errs.append(_err(
                        f"{cbase}.align",
                        f"must be left|center|right, got {align!r}"
                    ))
                fmt = col.get("format")
                if isinstance(fmt, str):
                    token = fmt.split(":")[0]
                    if token not in VALID_TABLE_FORMATS:
                        errs.append(_err(
                            f"{cbase}.format",
                            f"unknown format '{fmt}'; token "
                            f"must be in {sorted(VALID_TABLE_FORMATS)}"
                        ))
                conditional = col.get("conditional")
                if conditional is not None:
                    if not isinstance(conditional, list):
                        errs.append(_err(
                            f"{cbase}.conditional",
                            "must be a list of rule dicts"
                        ))
                    else:
                        for ri, rule in enumerate(conditional):
                            rbase = f"{cbase}.conditional[{ri}]"
                            if not isinstance(rule, dict):
                                errs.append(_err(rbase, "must be a dict"))
                                continue
                            op = rule.get("op")
                            if op and op not in VALID_FILTER_OPS:
                                errs.append(_err(
                                    f"{rbase}.op",
                                    f"'{op}' not in {sorted(VALID_FILTER_OPS)}"
                                ))
                color_scale = col.get("color_scale")
                if color_scale is not None:
                    if not isinstance(color_scale, dict):
                        errs.append(_err(
                            f"{cbase}.color_scale",
                            "must be a dict with min/max/palette"
                        ))
                    else:
                        p = color_scale.get("palette")
                        if p:
                            from config import PALETTES
                            if p not in PALETTES:
                                errs.append(_err(
                                    f"{cbase}.color_scale.palette",
                                    f"unknown palette '{p}'"
                                ))
                in_cell = col.get("in_cell")
                if in_cell is not None:
                    if in_cell not in ("bar", "sparkline", "heat"):
                        errs.append(_err(
                            f"{cbase}.in_cell",
                            f"must be 'bar' / 'sparkline' / 'heat', "
                            f"got {in_cell!r}"))
                    if in_cell == "sparkline":
                        if not col.get("from_dataset") and not col.get("dataset"):
                            errs.append(_err(
                                f"{cbase}.from_dataset",
                                "in_cell=sparkline requires "
                                "'from_dataset' (sibling dataset to read history from)"))
                        if not col.get("row_key"):
                            errs.append(_err(
                                f"{cbase}.row_key",
                                "in_cell=sparkline requires 'row_key' "
                                "(column on this row used to look up history)"))
    row_click = w.get("row_click")
    if row_click is not None and not isinstance(row_click, (dict, bool)):
        errs.append(_err(
            f"{wbase}.row_click",
            "must be a dict, or boolean false to suppress the "
            "default provenance popup; got "
            f"{type(row_click).__name__}"
        ))


def _validate_pivot_widget(w: Dict[str, Any], wbase: str,
                            errs: List[str], dataset_names: Any) -> None:
    """Validate a ``widget: pivot`` entry."""
    if not w.get("dataset_ref"):
        errs.append(_err(f"{wbase}.dataset_ref",
                          "pivot widget requires 'dataset_ref'"))
    for k in ("row_dim_columns", "col_dim_columns", "value_columns"):
        v = w.get(k)
        if v is None:
            errs.append(_err(f"{wbase}.{k}", f"required for pivot widget"))
        elif not isinstance(v, list) or not v:
            errs.append(_err(
                f"{wbase}.{k}",
                "must be a non-empty list of column names"))
    agg_opts = w.get("agg_options",
                       ["mean", "sum", "median", "min", "max", "count"])
    if not isinstance(agg_opts, list):
        errs.append(_err(f"{wbase}.agg_options",
                          "must be a list of agg names"))
    cs = w.get("color_scale")
    if cs is not None:
        if isinstance(cs, str):
            if cs not in ("sequential", "diverging", "auto"):
                errs.append(_err(
                    f"{wbase}.color_scale",
                    f"must be 'sequential' / 'diverging' / "
                    f"'auto', got {cs!r}"))
        elif not isinstance(cs, dict):
            errs.append(_err(
                f"{wbase}.color_scale",
                "must be a string ('sequential' / 'diverging' "
                "/ 'auto') or a dict {min, max, palette}"))


def _validate_stat_grid_widget(w: Dict[str, Any], wbase: str,
                                 errs: List[str], dataset_names: Any) -> None:
    """Validate a ``widget: stat_grid`` entry."""
    stats = w.get("stats")
    if not isinstance(stats, list) or not stats:
        errs.append(_err(f"{wbase}.stats",
                          "required non-empty list of stat dicts"))
        return
    for si, st in enumerate(stats):
        if not isinstance(st, dict):
            errs.append(_err(f"{wbase}.stats[{si}]", "must be a dict"))
            continue
        if "label" not in st:
            errs.append(_err(f"{wbase}.stats[{si}].label", "required"))
        if "value" not in st and "source" not in st:
            errs.append(_err(
                f"{wbase}.stats[{si}]",
                "requires 'value' or 'source'"
            ))


def _validate_image_widget(w: Dict[str, Any], wbase: str,
                            errs: List[str], dataset_names: Any) -> None:
    """Validate a ``widget: image`` entry."""
    if not (w.get("src") or w.get("url")):
        errs.append(_err(f"{wbase}.src",
                          "image widget requires 'src' or 'url'"))


def _validate_markdown_widget(w: Dict[str, Any], wbase: str,
                                errs: List[str], dataset_names: Any) -> None:
    """Validate a ``widget: markdown`` entry.

    The merged markdown / note widget accepts:

      * ``content`` OR ``body`` -- markdown text (one is required;
        ``body`` is the legacy ``note``-widget field name kept for
        back-compat).
      * Optional ``kind`` ∈ ``VALID_NOTE_KINDS`` -- when set, the
        renderer emits a tinted card with a coloured left-edge stripe
        instead of transparent prose. Use ``insight`` / ``thesis`` /
        ``watch`` / ``risk`` / ``context`` / ``fact`` for load-bearing
        prose; omit ``kind`` for inline narrative.
      * Optional ``title`` / ``icon`` -- only meaningful when ``kind``
        is set (rendered in the note head bar).
    """
    if "content" not in w and "body" not in w:
        errs.append(_err(
            f"{wbase}.content",
            "required for markdown (or use 'body'); markdown widget "
            "needs the markdown text in either 'content' (canonical) "
            "or 'body' (legacy note alias)"))
    kind = w.get("kind")
    if kind is not None and kind not in VALID_NOTE_KINDS:
        errs.append(_err(
            f"{wbase}.kind",
            f"'{kind}' not in {sorted(VALID_NOTE_KINDS)}"
        ))


def _validate_note_widget(w: Dict[str, Any], wbase: str,
                            errs: List[str], dataset_names: Any) -> None:
    """Validate a ``widget: note`` entry.

    Alias for the merged ``widget: markdown`` schema. Kept as a
    distinct widget kind so persisted manifests written under the old
    two-widget contract still validate cleanly. The ``note`` literal
    implies an insight-card render even with no explicit ``kind``;
    new manifests should use ``widget: "markdown"`` with an explicit
    ``kind`` instead. Both go through the same renderer.
    """
    # ``note`` requires ``body`` (or ``content``) like markdown does.
    # Delegating to the markdown validator keeps the field-shape
    # contract in one place.
    _validate_markdown_widget(w, wbase, errs, dataset_names)


def _validate_divider_widget(w: Dict[str, Any], wbase: str,
                               errs: List[str], dataset_names: Any) -> None:
    """Validate a ``widget: divider`` entry. No required fields beyond
    the generic ones (``id``, ``w``) handled by the dispatch loop."""
    return


@dataclass(frozen=True)
class WidgetSpec:
    """Schema descriptor for a single widget kind.

    Holds the per-widget validator and the cross-cutting flags PRISM-
    facing infrastructure cares about. The ``WIDGETS`` table is the
    single source of truth -- everything that asks "what widgets
    exist?" or "is X data-bound?" derives from it.
    """
    kind: str
    validate: Any  # callable: (w, wbase, errs, dataset_names) -> None
    data_bound: bool = False
    filter_targetable: bool = False


WIDGETS: Dict[str, WidgetSpec] = {
    "chart":     WidgetSpec("chart",     _validate_chart_widget,
                              data_bound=True,  filter_targetable=True),
    "kpi":       WidgetSpec("kpi",       _validate_kpi_widget,
                              data_bound=True,  filter_targetable=True),
    "table":     WidgetSpec("table",     _validate_table_widget,
                              data_bound=True,  filter_targetable=True),
    "pivot":     WidgetSpec("pivot",     _validate_pivot_widget,
                              data_bound=True,  filter_targetable=True),
    "stat_grid": WidgetSpec("stat_grid", _validate_stat_grid_widget,
                              data_bound=True,  filter_targetable=True),
    "tool":      WidgetSpec("tool",      _validate_tool_widget,
                              data_bound=False, filter_targetable=False),
    "note":      WidgetSpec("note",      _validate_note_widget,
                              data_bound=False, filter_targetable=False),
    "markdown":  WidgetSpec("markdown",  _validate_markdown_widget,
                              data_bound=False, filter_targetable=False),
    "image":     WidgetSpec("image",     _validate_image_widget,
                              data_bound=False, filter_targetable=False),
    "divider":   WidgetSpec("divider",   _validate_divider_widget,
                              data_bound=False, filter_targetable=False),
}

VALID_WIDGETS = frozenset(WIDGETS)
FILTER_TARGETABLE_WIDGETS = frozenset(
    k for k, spec in WIDGETS.items() if spec.filter_targetable
)
DATA_BOUND_WIDGETS = frozenset(
    k for k, spec in WIDGETS.items() if spec.data_bound
)


RESERVED_HEADER_ACTION_IDS = frozenset({
    "methodology-btn",
    "refresh-btn",
    "refresh-btn-label",
    "refresh-err-btn",
    "share-btn",
    "share-btn-label",
    "download-btn",
    "download-btn-label",
    "download-menu",
    "export-all",
    "export-dashboard",
    "export-excel",
    "theme-toggle",
    "data-as-of",
    "data-as-of-val",
    "header-actions",
})


# =============================================================================
# MANIFEST VALIDATION -- SECTION VALIDATORS
# =============================================================================
#
# `validate_manifest` orchestrates a sequence of per-section validators.
# Each validator owns one logical area of the manifest schema and mutates
# nothing except `errs` (the running error list) and the shared
# `_ValidationCtx` (which collects cross-section state -- dataset names,
# filter ids, chart ids, filter-targetable widget ids -- needed by the
# later cross-reference passes).
#
# Order matters: section validators that BUILD ctx state must run before
# section validators that CONSUME it. The orchestrator below calls them
# in the correct order; rearranging them silently breaks cross-ref
# checks.


@dataclass
class _ValidationCtx:
    """Cross-section state shared between manifest section validators.

    Built up incrementally as each section validator runs. Later
    sections (filter target refs, depends_on refs, show_when filter
    refs, link members) consume the ids/names registered here.
    """
    require_persistence_metadata: bool = False
    dataset_names: set = field(default_factory=set)
    filter_ids: set = field(default_factory=set)
    chart_ids: set = field(default_factory=set)
    filter_target_ids: set = field(default_factory=set)


def _validate_schema_and_top_level(manifest: Dict[str, Any],
                                     errs: List[str],
                                     ctx: "_ValidationCtx") -> None:
    """schema_version, id, title, theme, palette."""
    sv = manifest.get("schema_version")
    if sv != SCHEMA_VERSION:
        errs.append(_err("schema_version",
                          f"expected {SCHEMA_VERSION}, got {sv!r}"))
    for key in ("id", "title"):
        if not manifest.get(key):
            errs.append(_err(key, "required field missing or empty"))
    theme = manifest.get("theme", "gs_clean")
    palette = manifest.get("palette")
    if theme:
        from config import THEMES
        if theme not in THEMES:
            errs.append(_err("theme",
                              f"unknown theme '{theme}'; "
                              f"valid: {sorted(THEMES.keys())}"))
    if palette:
        from config import PALETTES
        if palette not in PALETTES:
            errs.append(_err("palette",
                              f"unknown palette '{palette}'; "
                              f"valid: {sorted(PALETTES.keys())}"))


def _validate_metadata(manifest: Dict[str, Any],
                        errs: List[str],
                        ctx: "_ValidationCtx") -> None:
    """metadata block: required when require_persistence_metadata is True;
    optional fields are type-checked unconditionally."""
    metadata = manifest.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        errs.append(_err("metadata", "must be a dict"))
        metadata = None
    if metadata is None and ctx.require_persistence_metadata:
        # Empty / missing metadata block on the main entry path is the
        # bug-class this guard exists to catch. Surface a single
        # actionable error pointing at all three required fields.
        errs.append(_err(
            "metadata",
            "required block missing. Persistent dashboards must set "
            "metadata.kerberos, metadata.dashboard_id, and "
            "metadata.methodology -- these gate the always-on Refresh, "
            "Share, and Methodology buttons in the header chrome."))
    if not isinstance(metadata, dict):
        return
    for k in ("kerberos", "dashboard_id", "data_as_of",
                "generated_at", "version", "api_url", "status_url"):
        v = metadata.get(k)
        if v is not None and not isinstance(v, str):
            errs.append(_err(f"metadata.{k}",
                                f"must be a string, got {type(v).__name__}"))
    for k in ("sources", "tags"):
        v = metadata.get(k)
        if v is not None and not isinstance(v, list):
            errs.append(_err(f"metadata.{k}", "must be a list of strings"))
    # ``metadata.refresh_enabled`` was an escape hatch that hid the
    # browser Refresh button when set to ``False``; the field is
    # deprecated. The button is non-suppressible from the manifest
    # side now -- every persistent dashboard renders it. Old manifests
    # on S3 that still carry the field (with any value) validate fine;
    # the field is silently ignored at compile and render time. The
    # server-side ``refresh_enabled`` flag on the
    # ``dashboards_registry.json`` per-dashboard entry is a separate
    # field and continues to gate the hourly runner.
    rf = metadata.get("refresh_frequency")
    if rf is not None and rf not in VALID_REFRESH_FREQUENCIES:
        errs.append(_err("metadata.refresh_frequency",
                            f"'{rf}' not in "
                            f"{sorted(VALID_REFRESH_FREQUENCIES)}"))
    # methodology: markdown string OR {title?, body} dict.
    # Drives the header "Methodology" popup button.
    meth = metadata.get("methodology")
    if meth is not None:
        if isinstance(meth, str):
            if ctx.require_persistence_metadata and not meth.strip():
                errs.append(_err(
                    "metadata.methodology",
                    "required for persistent dashboards; got empty string"))
        elif isinstance(meth, dict):
            for k in ("title", "body", "text"):
                v = meth.get(k)
                if v is not None and not isinstance(v, str):
                    errs.append(_err(
                        f"metadata.methodology.{k}",
                        f"must be a string, got {type(v).__name__}"))
            if not (meth.get("body") or meth.get("text")):
                errs.append(_err(
                    "metadata.methodology",
                    "dict form requires a 'body' (or 'text') key"))
        else:
            errs.append(_err(
                "metadata.methodology",
                "must be a markdown string or "
                "{title?, body} dict"))
    # Required-presence checks for the three chrome gates.
    if ctx.require_persistence_metadata:
        for k, hint in (
            ("kerberos",
              "owner kerberos; gates the Refresh + Share buttons"),
            ("dashboard_id",
              "stable id under users/{kerberos}/dashboards/; gates "
              "the Refresh button and the share-toggle endpoint"),
            ("methodology",
              "markdown describing how the data is constructed; "
              "drives the Methodology popup. Use a plain string or "
              "{title, body} dict"),
        ):
            v = metadata.get(k)
            missing = (
                v is None
                or (isinstance(v, str) and not v.strip())
                or (isinstance(v, dict) and not (
                    v.get("body") or v.get("text")))
            )
            if missing:
                errs.append(_err(
                    f"metadata.{k}",
                    f"required for persistent dashboards -- {hint}"))


def _validate_header_actions(manifest: Dict[str, Any],
                               errs: List[str],
                               ctx: "_ValidationCtx") -> None:
    """header_actions: optional custom buttons / links in the header.

    Custom buttons are inserted to the LEFT of the always-on chrome
    (Methodology / Refresh / Share / Download / theme toggle). The
    chrome's DOM ids are reserved -- a custom action that re-uses one
    would silently shadow the live chrome at runtime.
    """
    header_actions = manifest.get("header_actions")
    if header_actions is None:
        return
    if not isinstance(header_actions, list):
        errs.append(_err("header_actions", "must be a list"))
        return
    for i, a in enumerate(header_actions):
        base = f"header_actions[{i}]"
        if not isinstance(a, dict):
            errs.append(_err(base, "must be a dict"))
            continue
        if not a.get("label"):
            errs.append(_err(f"{base}.label", "required"))
        aid = a.get("id")
        if aid is not None and aid in RESERVED_HEADER_ACTION_IDS:
            errs.append(_err(
                f"{base}.id",
                f"'{aid}' collides with a reserved chrome id "
                f"({sorted(RESERVED_HEADER_ACTION_IDS)}). "
                "Pick a different id; the chrome buttons "
                "(Methodology / Refresh / Share / Download / "
                "theme toggle) cannot be replaced via "
                "header_actions."))
        if not (a.get("href") or a.get("onclick")):
            errs.append(_err(
                base,
                "requires 'href' (URL) or 'onclick' (JS function name)",
            ))


def _validate_datasets(manifest: Dict[str, Any],
                        errs: List[str],
                        ctx: "_ValidationCtx") -> None:
    """datasets block: each entry must have a ``source`` list. Optional
    field_provenance and row_provenance shapes are sanity-checked.
    Builds ``ctx.dataset_names``."""
    datasets = manifest.get("datasets", {}) or {}
    if not isinstance(datasets, dict):
        errs.append(_err("datasets", "must be a dict of name -> dataset"))
        datasets = {}
    for name, ds in datasets.items():
        if not isinstance(ds, dict) or "source" not in ds:
            errs.append(_err(f"datasets.{name}", "must be a dict with 'source'"))
            continue
        if not isinstance(ds["source"], list):
            errs.append(_err(f"datasets.{name}.source", "must be a list"))

        # Optional per-column provenance: maps column name -> provenance dict
        # ({system, symbol, display_name, units, source_label, ...}). Light-
        # touch shape check only -- the inner keys are intentionally free-
        # form so PRISM can carry whatever the upstream data system emits
        # (haver_code, tsdb_symbol, fred_series, bloomberg_ticker, computed
        # recipe, etc.) without us needing to enumerate every system.
        fp = ds.get("field_provenance")
        if fp is not None:
            if not isinstance(fp, dict):
                errs.append(_err(
                    f"datasets.{name}.field_provenance",
                    "must be a dict mapping column name -> provenance dict "
                    "(e.g. {\"UST10Y\": {\"system\": \"market_data\", "
                    "\"symbol\": \"IR_USD_Treasury_10Y_Rate\", ...}})"
                ))
            else:
                for col, prov in fp.items():
                    if not isinstance(prov, dict):
                        errs.append(_err(
                            f"datasets.{name}.field_provenance.{col}",
                            "must be a dict; got "
                            f"{type(prov).__name__}"
                        ))
        # Optional per-row provenance overrides. ``row_provenance_field``
        # names a column whose cell value keys into ``row_provenance``,
        # which is a dict <row_key> -> {<column_name>: <provenance_dict>}.
        # Use this when an entity-keyed table mixes sources per row
        # (e.g. one bond pulled from Bloomberg, another from market_data).
        rpf = ds.get("row_provenance_field")
        if rpf is not None and not isinstance(rpf, str):
            errs.append(_err(
                f"datasets.{name}.row_provenance_field",
                "must be a string column name"
            ))
        rp = ds.get("row_provenance")
        if rp is not None:
            if not isinstance(rp, dict):
                errs.append(_err(
                    f"datasets.{name}.row_provenance",
                    "must be a dict <row_key> -> {<col>: <provenance_dict>}"
                ))
            else:
                for key, overrides in rp.items():
                    if not isinstance(overrides, dict):
                        errs.append(_err(
                            f"datasets.{name}.row_provenance.{key}",
                            "must be a dict <col> -> provenance dict"
                        ))
                        continue
                    for col, prov in overrides.items():
                        if not isinstance(prov, dict):
                            errs.append(_err(
                                f"datasets.{name}.row_provenance.{key}.{col}",
                                "must be a dict"
                            ))
    ctx.dataset_names = set(datasets.keys())


def _validate_filters(manifest: Dict[str, Any],
                       errs: List[str],
                       ctx: "_ValidationCtx") -> None:
    """filters block: per-filter shape (type, options, slider min/max,
    rule grammar, depends_on / options_from). Builds ``ctx.filter_ids``.

    Cross-references (depends_on -> real filter id; targets -> real
    widget id) are deferred to dedicated cross-ref passes that run
    AFTER ctx.filter_ids and ctx.filter_target_ids are populated.
    """
    filters = manifest.get("filters", []) or []
    if not isinstance(filters, list):
        errs.append(_err("filters", "must be a list"))
        return
    for i, f in enumerate(filters):
        base = f"filters[{i}]"
        if not isinstance(f, dict):
            errs.append(_err(base, "must be a dict"))
            continue
        fid = f.get("id")
        if not fid:
            errs.append(_err(f"{base}.id", "required"))
        elif fid in ctx.filter_ids:
            errs.append(_err(f"{base}.id", f"duplicate id '{fid}'"))
        else:
            ctx.filter_ids.add(fid)
        ft = f.get("type")
        if ft not in VALID_FILTERS:
            errs.append(_err(f"{base}.type",
                              f"'{ft}' not in {sorted(VALID_FILTERS)}"))
        if "targets" in f and not isinstance(f["targets"], list):
            errs.append(_err(f"{base}.targets",
                              "must be a list of chart ids or patterns"))
        if ft in ("select", "multiSelect", "radio"):
            if "options" not in f:
                errs.append(_err(f"{base}.options",
                                  f"required for type '{ft}'"))
            else:
                opts = f.get("options")
                if not isinstance(opts, list):
                    errs.append(_err(f"{base}.options",
                                      f"must be a list, got {type(opts).__name__}"))
                else:
                    for oi, o in enumerate(opts):
                        opath = f"{base}.options[{oi}]"
                        if isinstance(o, dict):
                            if "value" not in o:
                                errs.append(_err(
                                    opath,
                                    "dict option missing required 'value' "
                                    "key (use {\"value\": ..., \"label\": ...})"))
                            extras = set(o.keys()) - {"value", "label"}
                            if extras:
                                errs.append(_err(
                                    opath,
                                    f"dict option has unsupported keys "
                                    f"{sorted(extras)}; only "
                                    f"'value' and 'label' are allowed"))
                        elif not isinstance(o, (str, int, float, bool)):
                            errs.append(_err(
                                opath,
                                f"option must be a primitive (str/int/float/"
                                f"bool) or {{'value', 'label'}} dict, got "
                                f"{type(o).__name__}: {o!r}"))
        if ft == "slider":
            for k in ("min", "max"):
                if k not in f:
                    errs.append(_err(f"{base}.{k}",
                                       f"required for slider"))
        if ft in ("slider", "number", "text") and "field" not in f:
            errs.append(_err(f"{base}.field",
                              f"required for type '{ft}' "
                              "(column to filter against)"))
        if "op" in f and f["op"] not in VALID_FILTER_OPS:
            errs.append(_err(f"{base}.op",
                              f"'{f['op']}' not in {sorted(VALID_FILTER_OPS)}"))
        if ft == "rule":
            if "rule" not in f:
                errs.append(_err(f"{base}.rule",
                                   "required for type 'rule'"))
            else:
                _validate_filter_rule(f["rule"], f"{base}.rule", errs)
        # Cascading filters: depends_on + options_from
        depends = f.get("depends_on")
        if depends is not None:
            if not isinstance(depends, str) or not depends:
                errs.append(_err(f"{base}.depends_on",
                                  "must be a non-empty filter id string"))
            elif depends == fid:
                errs.append(_err(f"{base}.depends_on",
                                  "filter cannot depend on itself"))
            # Cross-ref to a real filter id is checked separately
            # in `_validate_filter_depends_on_refs` after every filter
            # has been registered.
        opts_from = f.get("options_from")
        if opts_from is not None:
            if not isinstance(opts_from, dict):
                errs.append(_err(f"{base}.options_from",
                                  "must be a dict {dataset, key, where?}"))
            else:
                if "dataset" not in opts_from:
                    errs.append(_err(f"{base}.options_from.dataset",
                                      "required"))
                if "key" not in opts_from:
                    errs.append(_err(f"{base}.options_from.key",
                                      "required"))


def _validate_layout(manifest: Dict[str, Any],
                      errs: List[str],
                      ctx: "_ValidationCtx") -> None:
    """layout structure: kind ∈ {grid, tabs}, cols, per-row width sums,
    per-widget validation via the WIDGETS registry. Builds
    ``ctx.chart_ids`` and ``ctx.filter_target_ids``.
    """
    layout = manifest.get("layout")
    if not isinstance(layout, dict):
        errs.append(_err("layout", "must be a dict"))
        layout = {}
    kind = layout.get("kind", "grid")
    if kind not in ("grid", "tabs"):
        errs.append(_err("layout.kind",
                          f"must be 'grid' or 'tabs', got '{kind}'"))
    cols = layout.get("cols", 12)
    if not isinstance(cols, int) or cols <= 0:
        errs.append(_err("layout.cols", f"must be a positive int, got {cols!r}"))
        cols = 12

    seen_ids: set = set()

    def _validate_rows(rows, path_prefix):
        if not isinstance(rows, list):
            errs.append(_err(path_prefix, "must be a list of rows"))
            return
        for ri, row in enumerate(rows):
            if not isinstance(row, list):
                errs.append(_err(f"{path_prefix}[{ri}]",
                                   "must be a list of widgets"))
                continue
            total_w = 0
            for wi, w in enumerate(row):
                wbase = f"{path_prefix}[{ri}][{wi}]"
                if not isinstance(w, dict):
                    errs.append(_err(wbase, "must be a dict"))
                    continue
                wt = w.get("widget")
                if wt not in VALID_WIDGETS:
                    errs.append(_err(f"{wbase}.widget",
                                       f"'{wt}' not in {sorted(VALID_WIDGETS)}"))
                wid = w.get("id")
                if not wid:
                    # Every widget needs a stable id: filter targets,
                    # link members, click_emit_filter, chart_ids, and
                    # the dashboard runtime DOM all key off it. The
                    # duplicate-id check below ran unconditionally
                    # before; the required-presence check was missing,
                    # letting widgets without an id silently validate.
                    errs.append(_err(f"{wbase}.id",
                                       "required; every widget needs "
                                       "a stable id (filter targets, "
                                       "link members, click_emit_filter, "
                                       "and the runtime DOM all key on "
                                       "it)"))
                elif wid in seen_ids:
                    errs.append(_err(f"{wbase}.id",
                                       f"duplicate widget id '{wid}'"))
                else:
                    seen_ids.add(wid)
                    if wt == "chart":
                        ctx.chart_ids.add(wid)
                    if wt in FILTER_TARGETABLE_WIDGETS:
                        ctx.filter_target_ids.add(wid)
                width = w.get("w", cols)
                if not isinstance(width, int) or width <= 0 or width > cols:
                    errs.append(_err(f"{wbase}.w",
                                       f"width must be 1..{cols}, got {width!r}"))
                else:
                    total_w += width
                # Generic widget knobs (apply to every widget type)
                show_when = w.get("show_when")
                if show_when is not None:
                    if not isinstance(show_when, dict):
                        errs.append(_err(
                            f"{wbase}.show_when",
                            "must be a dict with one of 'data' / 'filter' / "
                            "'all' / 'any' keys"))
                    else:
                        keys = set(show_when.keys())
                        valid = {"data", "filter", "value", "in", "op",
                                  "all", "any"}
                        unknown = keys - valid
                        if unknown:
                            errs.append(_err(
                                f"{wbase}.show_when",
                                f"unknown key(s) {sorted(unknown)}; "
                                f"valid: {sorted(valid)}"))
                        if "filter" in show_when:
                            fid = show_when.get("filter")
                            if not isinstance(fid, str) or not fid:
                                errs.append(_err(
                                    f"{wbase}.show_when.filter",
                                    "must be a non-empty filter id string"))
                # Per-widget validation via the WIDGETS registry. Each
                # widget kind owns one ``_validate_<kind>_widget`` function;
                # adding a new kind = one entry in WIDGETS + one validator
                # function (above), nothing else here changes.
                spec_entry = WIDGETS.get(wt)
                if spec_entry is not None:
                    spec_entry.validate(w, wbase, errs, ctx.dataset_names)
            if total_w > cols:
                errs.append(_err(f"{path_prefix}[{ri}]",
                                   f"widget widths sum to {total_w} > cols={cols}"))

    if kind == "tabs":
        tabs = layout.get("tabs", [])
        if not isinstance(tabs, list) or not tabs:
            errs.append(_err("layout.tabs",
                              "required non-empty list when kind='tabs'"))
            tabs = []
        tab_ids = set()
        for ti, tab in enumerate(tabs):
            base = f"layout.tabs[{ti}]"
            if not isinstance(tab, dict):
                errs.append(_err(base, "must be a dict"))
                continue
            tid = tab.get("id")
            if not tid:
                errs.append(_err(f"{base}.id", "required"))
            elif tid in tab_ids:
                errs.append(_err(f"{base}.id", f"duplicate tab id '{tid}'"))
            else:
                tab_ids.add(tid)
            if not tab.get("label"):
                errs.append(_err(f"{base}.label", "required"))
            _validate_rows(tab.get("rows", []), f"{base}.rows")
    else:
        rows = layout.get("rows", [])
        _validate_rows(rows, "layout.rows")


def _validate_filter_target_refs(manifest: Dict[str, Any],
                                    errs: List[str],
                                    ctx: "_ValidationCtx") -> None:
    """filter.targets[] -> data-bound widget ids cross-reference pass."""
    filters = manifest.get("filters", []) or []
    if not isinstance(filters, list):
        return
    for i, f in enumerate(filters):
        if not isinstance(f, dict):
            continue
        for tpat in f.get("targets", []) or []:
            if tpat == "*" or "*" in tpat:
                continue
            if tpat not in ctx.filter_target_ids:
                errs.append(_err(
                    f"filters[{i}].targets",
                    f"target '{tpat}' is not a data-bound widget id; "
                    f"available: {sorted(ctx.filter_target_ids)}"))


def _validate_filter_depends_on_refs(manifest: Dict[str, Any],
                                        errs: List[str],
                                        ctx: "_ValidationCtx") -> None:
    """filter.depends_on -> declared filter id cross-reference pass."""
    filters = manifest.get("filters", []) or []
    if not isinstance(filters, list):
        return
    for i, f in enumerate(filters):
        if not isinstance(f, dict):
            continue
        depends = f.get("depends_on")
        if depends and depends not in ctx.filter_ids:
            errs.append(_err(
                f"filters[{i}].depends_on",
                f"'{depends}' is not a declared filter id "
                f"(available: {sorted(ctx.filter_ids)})"))


def _validate_widget_show_when_filter_refs(manifest: Dict[str, Any],
                                              errs: List[str],
                                              ctx: "_ValidationCtx") -> None:
    """widget.show_when.{filter, all, any} -> declared filter id
    cross-reference pass."""
    layout = manifest.get("layout") or {}
    kind = layout.get("kind", "grid")

    def _walk_widget_show_when_filters(rows, path_prefix):
        if not isinstance(rows, list):
            return
        for ri, row in enumerate(rows):
            if not isinstance(row, list):
                continue
            for wi, w in enumerate(row):
                if not isinstance(w, dict):
                    continue
                cond = w.get("show_when")
                if not isinstance(cond, dict):
                    continue
                def _check(c, depth=0):
                    if depth > 8 or not isinstance(c, dict):
                        return
                    for sub in c.get("all", []) or []:
                        _check(sub, depth + 1)
                    for sub in c.get("any", []) or []:
                        _check(sub, depth + 1)
                    if "filter" in c:
                        fid_ref = c.get("filter")
                        if isinstance(fid_ref, str) and fid_ref not in ctx.filter_ids:
                            errs.append(_err(
                                f"{path_prefix}[{ri}][{wi}].show_when.filter",
                                f"'{fid_ref}' is not a declared filter id "
                                f"(available: {sorted(ctx.filter_ids)})"))
                _check(cond)

    if kind == "tabs":
        for ti, tab in enumerate(layout.get("tabs", []) or []):
            if isinstance(tab, dict):
                _walk_widget_show_when_filters(
                    tab.get("rows", []) or [],
                    f"layout.tabs[{ti}].rows")
    else:
        _walk_widget_show_when_filters(
            layout.get("rows", []) or [], "layout.rows")


def _validate_links(manifest: Dict[str, Any],
                     errs: List[str],
                     ctx: "_ValidationCtx") -> None:
    """links: per-link shape (group, members, sync, brush) with
    member ids cross-checked against ``ctx.chart_ids``."""
    links = manifest.get("links", []) or []
    if not isinstance(links, list):
        errs.append(_err("links", "must be a list"))
        return
    link_groups = set()
    for i, lk in enumerate(links):
        base = f"links[{i}]"
        if not isinstance(lk, dict):
            errs.append(_err(base, "must be a dict"))
            continue
        group = lk.get("group")
        if not group:
            errs.append(_err(f"{base}.group", "required"))
        elif group in link_groups:
            errs.append(_err(f"{base}.group", f"duplicate group '{group}'"))
        else:
            link_groups.add(group)
        members = lk.get("members", [])
        if not isinstance(members, list):
            errs.append(_err(f"{base}.members", "must be a list"))
            members = []
        for m in members:
            if m == "*" or (isinstance(m, str) and "*" in m):
                continue
            if m not in ctx.chart_ids:
                errs.append(_err(
                    f"{base}.members",
                    f"'{m}' is not a chart widget id; "
                    f"available: {sorted(ctx.chart_ids)}"))
        sync = lk.get("sync", [])
        if sync:
            if not isinstance(sync, list):
                errs.append(_err(f"{base}.sync", "must be a list"))
            else:
                for s in sync:
                    if s not in VALID_SYNC:
                        errs.append(_err(f"{base}.sync",
                                           f"'{s}' not in {sorted(VALID_SYNC)}"))
        brush = lk.get("brush")
        if brush:
            if not isinstance(brush, dict):
                errs.append(_err(f"{base}.brush", "must be a dict"))
            else:
                bt = brush.get("type", "rect")
                if bt not in VALID_BRUSH_TYPES:
                    errs.append(_err(f"{base}.brush.type",
                                       f"'{bt}' not in {sorted(VALID_BRUSH_TYPES)}"))


def validate_manifest(
    manifest: Dict[str, Any],
    require_persistence_metadata: bool = False,
) -> Tuple[bool, List[str]]:
    """Validate a manifest dict. Return (ok, error_list). PURE: never
    mutates the caller's manifest.

    Internally runs the canonical pre-validation pipeline on a private
    working copy of the mutation-prone substructures (``datasets``,
    ``filters``, ``layout``); the caller's manifest is left exactly as
    it was passed in. This means ``validate_manifest(m); compile_dashboard(m)``
    works with no shape-diagnostic loss, and a caller can repeatedly
    re-validate the same dict without state drift.

    Use :func:`prepare_manifest` when you DO want the augmentations
    applied to your manifest in place (filter ``scope`` inference,
    ``radio``/``select``/``multiSelect`` dict-default reduction to
    primitives, chart ``dataset_ref`` auto-wiring, computed-column
    materialisation). ``compile_dashboard`` and ``render_dashboard``
    do this implicitly on their working manifest before calling
    ``validate_manifest``.

    Missing required fields produce one error each; the validator
    does not short-circuit on first error.

    ``require_persistence_metadata`` (default ``False``) elevates the
    chrome-required metadata fields from optional to mandatory. When
    ``True``, the manifest MUST set ``metadata.kerberos``,
    ``metadata.dashboard_id``, and ``metadata.methodology`` -- the three
    fields that gate the always-on header chrome (Refresh, Share, and
    Methodology buttons respectively). ``compile_dashboard`` and
    ``Dashboard.build`` pass ``True`` by default; a missing field there
    means the resulting dashboard would silently render without those
    buttons, which is exactly the bug class this guard exists to
    prevent. Lower-level entry points (``render_dashboard``, direct
    ``validate_manifest`` calls in tests) keep the lenient default.
    """
    import copy as _copy
    errs: List[str] = []
    if not isinstance(manifest, dict):
        return False, [_err("(root)", "manifest must be a dict")]
    # Save mutation-prone substructures so validation is observably
    # pure. Three things the prep pipeline mutates and we must restore:
    #   1. datasets   -- shallow-copy the entry-mapping dict so
    #                    normalisation can rebind entries (DataFrame
    #                    bodies are NEVER deep-copied; entry slots are
    #                    just rebound on the working copy).
    #   2. filters    -- deep-copy the list because _augment_manifest
    #                    sets f["scope"] and rewrites f["default"] for
    #                    select/multiSelect/radio.
    #   3. layout     -- deep-copy because _augment_manifest sets
    #                    w["dataset_ref"] on chart widgets.
    _UNSET = object()
    _restore_datasets: Optional[Dict[str, Any]] = None
    _restore_filters: Any = _UNSET
    _restore_layout: Any = _UNSET
    original_datasets = manifest.get("datasets")
    if isinstance(original_datasets, dict):
        manifest["datasets"] = {k: v for k, v in original_datasets.items()}
        _restore_datasets = original_datasets
    if "filters" in manifest:
        _restore_filters = manifest["filters"]
        if isinstance(_restore_filters, list):
            manifest["filters"] = _copy.deepcopy(_restore_filters)
    if "layout" in manifest:
        _restore_layout = manifest["layout"]
        if isinstance(_restore_layout, dict):
            manifest["layout"] = _copy.deepcopy(_restore_layout)
    try:
        _normalize_manifest_datasets(manifest)
        # Evaluate compute blocks so the rest of the validator sees
        # the canonical, materialised dataset shape. Errors are
        # collected and reported as validation errors below.
        compute_errors_inner = _apply_computed_datasets(manifest)
        for ce in compute_errors_inner:
            errs.append(ce)
        _augment_manifest(manifest)
    except Exception:  # noqa: BLE001
        pass  # let validation report the issue

    # Orchestrate per-section validators. Order matters: sections that
    # POPULATE ctx state (datasets, filters, layout) must run before
    # sections that CONSUME it (filter-target / depends_on /
    # show_when-filter cross-refs, link members against chart_ids).
    ctx = _ValidationCtx(
        require_persistence_metadata=require_persistence_metadata,
    )
    try:
        _validate_schema_and_top_level(manifest, errs, ctx)
        _validate_metadata(manifest, errs, ctx)
        _validate_header_actions(manifest, errs, ctx)
        _validate_datasets(manifest, errs, ctx)
        _validate_filters(manifest, errs, ctx)
        _validate_layout(manifest, errs, ctx)
        _validate_filter_target_refs(manifest, errs, ctx)
        _validate_filter_depends_on_refs(manifest, errs, ctx)
        _validate_widget_show_when_filter_refs(manifest, errs, ctx)
        _validate_links(manifest, errs, ctx)
    finally:
        # Restore the caller's original substructures even if a section
        # validator raised. DataFrames remain available to downstream
        # callers (compile_dashboard's _capture_shape_info, in
        # particular); filters and layout return to their pre-
        # augmentation shape so the caller sees no scope /
        # default-reduction / dataset_ref mutations.
        if _restore_datasets is not None:
            manifest["datasets"] = _restore_datasets
        if _restore_filters is not _UNSET:
            manifest["filters"] = _restore_filters
        if _restore_layout is not _UNSET:
            manifest["layout"] = _restore_layout

    return (not errs), errs


# (Pre-section-validator monolithic ``validate_manifest`` body removed
# in the per-section refactor; the orchestrator + section validators
# above produce byte-identical (ok, errs) output. Section validators
# are individually testable now -- see ``dev/tests.py``.)


def load_manifest(path: Union[str, Path]) -> Dict[str, Any]:
    """Load a manifest JSON file and return the dict. No validation."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"manifest not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_manifest(manifest: Dict[str, Any], path: Union[str, Path]) -> Path:
    """Write a manifest dict to JSON. Returns Path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return p


def match_targets(targets: List[str], chart_ids: List[str]) -> List[str]:
    """Resolve a list of target patterns against actual chart ids.

    Supports '*' (match all) and simple 'prefix_*' / '*_suffix' patterns.
    """
    if not targets:
        return []
    out: List[str] = []
    for pat in targets:
        if pat == "*":
            out.extend(chart_ids)
        elif "*" in pat:
            rx = re.compile("^" + re.escape(pat).replace(r"\*", ".*") + "$")
            out.extend([c for c in chart_ids if rx.match(c)])
        else:
            if pat in chart_ids:
                out.append(pat)
    # dedupe preserving order
    seen = set(); uniq = []
    for c in out:
        if c in seen:
            continue
        seen.add(c); uniq.append(c)
    return uniq



# =============================================================================
# WIDGET BUILDERS
# =============================================================================


@dataclass
class ChartRef:
    """Reference to a chart inside a dashboard manifest.

    Three mutually-compatible shapes (prefer in listed order):

        spec={"chart_type": ..., "dataset": ..., "mapping": {...}, ...}
            High-level spec lowered at compile time. Preferred for LLMs.
        ref="echarts/chart.json"
            Path (relative to session or manifest dir) to a pre-built
            ECharts option JSON.
        option={...raw ECharts option dict...}
            Inline raw option. Useful for passthrough and tests.
    """
    id: str
    ref: Optional[str] = None                 # relative path to spec JSON
    option: Optional[Dict[str, Any]] = None    # inline raw ECharts option
    spec: Optional[Dict[str, Any]] = None      # high-level spec (compiled)
    dataset_ref: Optional[str] = None
    w: int = 12
    h_px: int = 320
    title: str = ""
    theme: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"widget": "chart", "id": self.id,
                               "w": self.w, "h_px": self.h_px,
                               "title": self.title}
        if self.ref: d["ref"] = self.ref
        if self.option is not None: d["option"] = self.option
        if self.spec is not None: d["spec"] = dict(self.spec)
        if self.dataset_ref: d["dataset_ref"] = self.dataset_ref
        if self.theme: d["theme"] = self.theme
        return d


@dataclass
class KPIRef:
    """A big-number tile.

    value OR source drives the displayed figure. delta + delta_source + prefix
    + suffix + decimals drive formatting. sparkline_source=<ds>.<col> adds a
    tiny inline chart.
    """
    id: str
    label: str
    value: Any = None
    source: Optional[str] = None
    sub: Optional[str] = None
    delta: Optional[float] = None
    delta_source: Optional[str] = None
    delta_label: Optional[str] = None
    delta_decimals: Optional[int] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    decimals: Optional[int] = None
    sparkline_source: Optional[str] = None
    w: int = 4

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"widget": "kpi", "id": self.id,
                               "label": self.label, "w": self.w}
        if self.value is not None: d["value"] = self.value
        if self.source: d["source"] = self.source
        if self.sub: d["sub"] = self.sub
        if self.delta is not None: d["delta"] = self.delta
        if self.delta_source: d["delta_source"] = self.delta_source
        if self.delta_label: d["delta_label"] = self.delta_label
        if self.delta_decimals is not None: d["delta_decimals"] = self.delta_decimals
        if self.prefix is not None: d["prefix"] = self.prefix
        if self.suffix is not None: d["suffix"] = self.suffix
        if self.decimals is not None: d["decimals"] = self.decimals
        if self.sparkline_source: d["sparkline_source"] = self.sparkline_source
        return d


@dataclass
class TableRef:
    id: str
    dataset_ref: Optional[str] = None
    ref: Optional[str] = None
    title: str = ""
    w: int = 12
    max_rows: int = 50

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"widget": "table", "id": self.id, "w": self.w,
                               "title": self.title, "max_rows": self.max_rows}
        if self.dataset_ref: d["dataset_ref"] = self.dataset_ref
        if self.ref: d["ref"] = self.ref
        return d


@dataclass
class MarkdownRef:
    id: str
    content: str
    w: int = 12

    def to_dict(self) -> Dict[str, Any]:
        return {"widget": "markdown", "id": self.id, "content": self.content, "w": self.w}


@dataclass
class NoteRef:
    """Semantic callout tile for narrative commentary.

    Distinct from a plain ``markdown`` widget in two ways:
      1. The ``kind`` (``insight`` / ``thesis`` / ``watch`` / ``risk``
         / ``context`` / ``fact``) drives a colored left-edge stripe
         and small kind label so the reader can tell at a glance
         which paragraphs are load-bearing.
      2. It always renders as a tinted card (instead of the markdown
         widget's transparent-prose styling) so it visually breaks
         from surrounding flat text.

    ``body`` is markdown using the same grammar as the ``markdown``
    widget. ``title`` is plain text. ``icon`` is an optional short
    glyph rendered to the left of the title.
    """
    id: str
    body: str
    kind: str = "insight"
    title: Optional[str] = None
    icon: Optional[str] = None
    w: int = 12

    def to_dict(self) -> Dict[str, Any]:
        if self.kind not in VALID_NOTE_KINDS:
            raise ValueError(
                f"NoteRef.kind '{self.kind}' not in "
                f"{sorted(VALID_NOTE_KINDS)}"
            )
        d: Dict[str, Any] = {
            "widget": "note", "id": self.id,
            "kind": self.kind, "body": self.body, "w": self.w,
        }
        if self.title is not None:
            d["title"] = self.title
        if self.icon is not None:
            d["icon"] = self.icon
        return d


@dataclass
class DividerRef:
    id: str = "divider"

    def to_dict(self) -> Dict[str, Any]:
        return {"widget": "divider", "id": self.id, "w": 12}


@dataclass
class GlobalFilter:
    id: str
    type: str
    label: Optional[str] = None
    default: Any = None
    options: Optional[List[Any]] = None
    targets: List[str] = field(default_factory=lambda: ["*"])
    field: Optional[str] = None  # dataset column name filtered

    def to_dict(self) -> Dict[str, Any]:
        if self.type not in VALID_FILTERS:
            raise ValueError(
                f"GlobalFilter.type '{self.type}' not in {sorted(VALID_FILTERS)}"
            )
        d: Dict[str, Any] = {"id": self.id, "type": self.type,
                               "targets": list(self.targets)}
        if self.label is not None: d["label"] = self.label
        if self.default is not None: d["default"] = self.default
        if self.options is not None: d["options"] = list(self.options)
        if self.field: d["field"] = self.field
        return d


@dataclass
class Link:
    group: str
    members: List[str] = field(default_factory=list)
    sync: List[str] = field(default_factory=list)
    brush: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        bad = [s for s in self.sync if s not in VALID_SYNC]
        if bad:
            raise ValueError(
                f"Link.sync contains invalid entries {bad}; valid: {sorted(VALID_SYNC)}"
            )
        if self.brush:
            bt = self.brush.get("type", "rect")
            if bt not in VALID_BRUSH_TYPES:
                raise ValueError(
                    f"Link.brush.type '{bt}' not in {sorted(VALID_BRUSH_TYPES)}"
                )
        d: Dict[str, Any] = {"group": self.group, "members": list(self.members)}
        if self.sync: d["sync"] = list(self.sync)
        if self.brush: d["brush"] = dict(self.brush)
        return d


# =============================================================================
# RESULT
# =============================================================================


@dataclass
class DashboardResult:
    manifest: Dict[str, Any]
    manifest_path: Optional[str]
    html_path: Optional[str]
    html: Optional[str]
    success: bool
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    download_url: Optional[str] = None
    # Structured chart-data diagnostics (separate from `warnings`, which
    # is kept as flat strings for backwards compat). PRISM should read
    # these directly when iterating on a manifest.
    diagnostics: List["Diagnostic"] = field(default_factory=list)


# =============================================================================
# DASHBOARD BUILDER
# =============================================================================


@dataclass
class Tab:
    """A tab in a tabs-layout dashboard. Built up via Dashboard.add_tab(id, label).

    Mutators return self so they can be chained. Rows live per-tab.
    """
    id: str
    label: str
    description: str = ""
    rows: List[List[Any]] = field(default_factory=list)

    def add_row(self, widgets: Sequence[Any]) -> "Tab":
        self.rows.append(list(widgets))
        return self


class Dashboard:
    """Builder for a manifest. `build(session_path)` produces manifest + HTML.

    Two layout modes:

        grid  (default)   .add_row([...])       rows become a single grid
        tabs              .add_tab(id, label)   each tab has its own .rows

    Calling add_tab() flips the dashboard into tabs mode; any previously added
    grid rows are migrated into a 'main' tab so nothing is lost.
    """

    def __init__(self, id: str, title: str, description: str = "",
                 theme: str = "gs_clean", palette: Optional[str] = None):
        from config import THEMES, PALETTES
        if theme not in THEMES:
            raise ValueError(
                f"Unknown theme '{theme}'. "
                f"Valid: {sorted(THEMES.keys())}"
            )
        if palette is not None and palette not in PALETTES:
            raise ValueError(
                f"Unknown palette '{palette}'. "
                f"Valid: {sorted(PALETTES.keys())}"
            )
        self.id = id
        self.title = title
        self.description = description
        self.theme = theme
        self.palette = palette
        self.datasets: Dict[str, Dict[str, Any]] = {}
        self.filters: List[GlobalFilter] = []
        self.rows: List[List[Any]] = []
        self.tabs: List[Tab] = []
        self.links: List[Link] = []
        self.cols: int = 12

    # ----- datasets -----

    def add_dataset(
        self,
        name: str,
        df_or_source: Any,
        *,
        field_types: Optional[Dict[str, str]] = None,
        field_provenance: Optional[Dict[str, Dict[str, Any]]] = None,
        row_provenance_field: Optional[str] = None,
        row_provenance: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    ) -> "Dashboard":
        """Add a shared dataset to the manifest.

        Accepts either a pandas DataFrame (converted to a [header, ...rows]
        array) or a raw list.

        The optional ``field_provenance`` / ``row_provenance_field`` /
        ``row_provenance`` arguments record the data lineage that flows into
        the dashboard's click popups (default + explicit) and source
        attribution footer. The compiler does NOT introspect ``df.attrs``;
        PRISM is expected to clean the upstream metadata into the canonical
        provenance shape and pass it explicitly here. See README 3.6 and the
        skill file for the contract.

        ``field_provenance`` shape: ``{column_name: {system, symbol,
        display_name?, units?, source_label?, ...}}``. Keys other than
        ``system`` and ``symbol`` are free-form so PRISM can carry whatever
        fits the upstream system (haver_code, tsdb_symbol, fred_series,
        bloomberg_ticker, computed recipe, etc.).
        """
        source = _dataset_source(df_or_source)
        self.datasets[name] = {"source": source}
        if field_types:
            self.datasets[name]["field_types"] = dict(field_types)
        if field_provenance:
            self.datasets[name]["field_provenance"] = dict(field_provenance)
        if row_provenance_field:
            self.datasets[name]["row_provenance_field"] = str(row_provenance_field)
        if row_provenance:
            self.datasets[name]["row_provenance"] = dict(row_provenance)
        return self

    def add_dataset_inline(self, name: str, rows: List[List[Any]]) -> "Dashboard":
        """Add a dataset from a pre-built [header, ...rows] list."""
        if not isinstance(rows, list) or not rows:
            raise ValueError("add_dataset_inline: rows must be a non-empty list")
        self.datasets[name] = {"source": list(rows)}
        return self

    # ----- filters -----

    def add_filter(self, f: GlobalFilter) -> "Dashboard":
        self.filters.append(f)
        return self

    # ----- layout -----

    def set_cols(self, cols: int) -> "Dashboard":
        self.cols = int(cols)
        return self

    def add_row(self, widgets: Sequence[Any]) -> "Dashboard":
        if self.tabs:
            # already in tabs mode -> route to the active (last) tab
            self.tabs[-1].rows.append(list(widgets))
        else:
            self.rows.append(list(widgets))
        return self

    def add_tab(self, id: str, label: str,
                 description: str = "") -> Tab:
        """Create and append a new tab, switching the dashboard into tabs mode.

        Returns the Tab so the caller can chain `.add_row([...])` on it.
        Any previously-added grid rows migrate into an auto-generated
        'overview' tab.
        """
        if not self.tabs and self.rows:
            migrated = Tab(id="overview", label="Overview",
                            rows=list(self.rows))
            self.tabs.append(migrated)
            self.rows = []
        tab = Tab(id=id, label=label, description=description)
        self.tabs.append(tab)
        return tab

    # ----- links -----

    def add_link(self, link: Link) -> "Dashboard":
        self.links.append(link)
        return self

    # ----- manifest assembly -----

    def _rows_to_dict(self, rows: List[List[Any]]) -> List[List[Dict[str, Any]]]:
        rows_out: List[List[Dict[str, Any]]] = []
        for row in rows:
            row_out = []
            for w in row:
                if hasattr(w, "to_dict"):
                    row_out.append(w.to_dict())
                elif isinstance(w, dict):
                    row_out.append(dict(w))
                else:
                    raise TypeError(
                        f"widget must have to_dict() or be dict, got {type(w)}"
                    )
            rows_out.append(row_out)
        return rows_out

    def to_manifest(self) -> Dict[str, Any]:
        manifest: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "theme": self.theme,
            "datasets": dict(self.datasets),
            "filters": [f.to_dict() for f in self.filters],
            "links": [lk.to_dict() for lk in self.links],
        }
        if self.tabs:
            manifest["layout"] = {
                "kind": "tabs",
                "cols": self.cols,
                "tabs": [
                    {"id": t.id, "label": t.label,
                      "description": t.description,
                      "rows": self._rows_to_dict(t.rows)}
                    for t in self.tabs
                ],
            }
        else:
            manifest["layout"] = {
                "kind": "grid",
                "cols": self.cols,
                "rows": self._rows_to_dict(self.rows),
            }
        if self.palette:
            manifest["palette"] = self.palette
        return manifest

    # ----- build -----

    def build(self, session_path: Optional[Union[str, Path]] = None,
              output_path: Optional[Union[str, Path]] = None,
              write_html: bool = True, write_json: bool = True,
              require_persistence_metadata: bool = True,
              strict: bool = False) -> DashboardResult:
        """Compile the manifest assembled by this builder.

        Thin wrapper around :func:`compile_dashboard`. Historically this
        method ran its OWN lowering pipeline that quietly skipped the
        ``chart_data_diagnostics`` pass, ``_apply_computed_datasets``,
        ``_apply_show_when_compile``, ``_resolve_stat_grid_sources``,
        the shape-diagnostics pre-pass, and the ALWAYS_BLOCKING /
        ``strict`` enforcement. The result was that builder-style
        dashboards could ship with column-mapping bugs the diagnostic
        layer would have caught for ``compile_dashboard()`` callers.
        Routing through ``compile_dashboard`` keeps the two surfaces
        on one code path; the diagnostics now flow back on the
        :class:`DashboardResult`.

        ``strict`` defaults to ``False`` here (vs ``True`` on
        ``compile_dashboard``) to preserve the historical lenient
        behaviour of ``Dashboard.build()`` -- callers that want to
        fail loudly on error-severity diagnostics should pass
        ``strict=True`` explicitly. ALWAYS_BLOCKING error codes still
        raise regardless, exactly as for ``compile_dashboard``.
        """
        return compile_dashboard(
            self.to_manifest(),
            session_path=session_path,
            output_path=output_path,
            write_html=write_html,
            write_json=write_json,
            strict=strict,
            require_persistence_metadata=require_persistence_metadata,
        )


# =============================================================================
# HELPERS
# =============================================================================


def df_to_source(df_or_source: Any) -> List[List[Any]]:
    """Convert a pandas DataFrame (or a list-shaped source) to the manifest
    dataset 'source' shape: [[header...], [row...], ...].

    Accepts:
        * pandas DataFrame  -- converted; datetime columns emit as ISO-8601
          strings (date-only when the column is calendar-day-aligned,
          ``"%Y-%m-%d %H:%M:%S"`` / ``isoformat(sep=' ')`` when any
          sub-day component is present); NaN / NaT becomes None.
        * list              -- returned as-is (assumed already in source shape).

    Raises TypeError on anything else. This is the canonical bridge between
    PRISM-side DataFrames and the manifest dataset contract; PRISM should
    use this (or pass a DataFrame directly and let compile_dashboard convert
    it) instead of hand-writing data rows into the JSON.
    """
    try:
        import pandas as pd
        from echart_studio import _format_datetime_series
        if isinstance(df_or_source, pd.DataFrame):
            df = df_or_source.copy()
            for c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    df[c] = _format_datetime_series(df[c])
            source: List[List[Any]] = [list(df.columns)]
            for _, row in df.iterrows():
                source.append([_scalarize(v) for v in row])
            return source
    except Exception:
        pass
    if isinstance(df_or_source, list):
        return list(df_or_source)
    raise TypeError(
        f"df_to_source: expected DataFrame or list, got {type(df_or_source).__name__}"
    )


# Internal alias kept for older internal callers (Dashboard.add_dataset).
_dataset_source = df_to_source


def _scalarize(v: Any) -> Any:
    try:
        import math
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    if hasattr(v, "item"):
        return v.item()
    return v


def _is_dataframe(obj: Any) -> bool:
    try:
        import pandas as pd
        return isinstance(obj, pd.DataFrame)
    except Exception:
        return False


def _normalize_manifest_datasets(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DataFrames in manifest.datasets.{name} / .source to source
    arrays IN PLACE and return the manifest.

    Accepted shapes per dataset entry:
        {"source": DataFrame}           -> converted to list-of-lists
        {"source": list_of_lists}       -> left alone
        DataFrame                       -> wrapped as {"source": [[...], ...]}
        list_of_lists                   -> wrapped as {"source": [...]}

    This runs BEFORE validate_manifest so that validation sees the canonical
    list-of-lists source shape in every case. PRISM code that builds a
    manifest in execute_analysis_script can simply pass DataFrames through
    with zero conversion boilerplate.
    """
    ds = manifest.get("datasets")
    if not isinstance(ds, dict):
        return manifest
    for name, entry in list(ds.items()):
        if _is_dataframe(entry):
            ds[name] = {"source": df_to_source(entry)}
            continue
        if isinstance(entry, list):
            ds[name] = {"source": df_to_source(entry)}
            continue
        if isinstance(entry, dict):
            src = entry.get("source")
            if _is_dataframe(src):
                entry["source"] = df_to_source(src)
    return manifest


# ---------------------------------------------------------------------------
# Computed / synthetic datasets
#
# A dataset entry can declare a ``compute`` block listing named expressions
# evaluated against a source dataset. The compiler resolves dependencies,
# evaluates each expression safely (AST-level whitelist; no eval/exec),
# materializes the result as a fresh dataset entry (replacing ``compute``
# with ``source``), and auto-populates ``field_provenance`` with
# ``system: computed`` + the recipe so the popup Sources footer surfaces
# the formula.
#
# Author shape:
#     "datasets": {
#         "rates": df_rates,
#         "spreads": {
#             "from": "rates",
#             "compute": {
#                 "us_2s10s_bp": "(us_10y - us_2y) * 100",
#                 "us_10y_z_252": "zscore(us_10y, 252)"
#             }
#         }
#     }
#
# Result shape (after _apply_computed_datasets runs):
#     "datasets": {
#         "rates": <unchanged>,
#         "spreads": {
#             "source": [[date, us_2s10s_bp, us_10y_z_252], [...], ...],
#             "field_provenance": {
#                 "us_2s10s_bp": {"system": "computed",
#                                   "recipe": "(us_10y - us_2y) * 100",
#                                   "computed_from": ["us_10y", "us_2y"]},
#                 ...
#             }
#         }
#     }
#
# A ``compute`` block can also be attached to a dataset that already has a
# ``source`` (the compute columns are appended to the existing dataset
# rather than emitted as a new dataset).
# ---------------------------------------------------------------------------


# Whitelisted function names + their numpy / pandas implementations.
# Each takes (series, *args) and returns a series of the same length.
# `series` is a list of numeric-or-None values; helpers return list shape
# so the compiler can stitch them back into the source list-of-lists.

def _compute_helpers():
    """Build the function whitelist lazily so numpy/pandas import only when
    a manifest actually uses ``compute`` blocks."""
    import math
    try:
        import numpy as np
        import pandas as pd
    except Exception:
        np = None
        pd = None

    def _to_series(x):
        if pd is None or np is None:
            raise RuntimeError(
                "compute: pandas + numpy must be installed to evaluate "
                "compute blocks"
            )
        if isinstance(x, pd.Series):
            return x
        if isinstance(x, (list, tuple)):
            return pd.Series(list(x), dtype="float64")
        return x

    def _f_log(x):  return _to_series(x).apply(
        lambda v: (math.log(v) if v is not None and v > 0 else None)
    )
    def _f_log10(x): return _to_series(x).apply(
        lambda v: (math.log10(v) if v is not None and v > 0 else None)
    )
    def _f_log2(x): return _to_series(x).apply(
        lambda v: (math.log2(v) if v is not None and v > 0 else None)
    )
    def _f_exp(x):  return _to_series(x).apply(
        lambda v: (math.exp(v) if v is not None else None)
    )
    def _f_sqrt(x): return _to_series(x).apply(
        lambda v: (math.sqrt(v) if v is not None and v >= 0 else None)
    )
    def _f_abs(x):  return _to_series(x).apply(
        lambda v: (abs(v) if v is not None else None)
    )
    def _f_sign(x): return _to_series(x).apply(
        lambda v: (0 if v == 0 else (1 if v > 0 else -1)) if v is not None else None
    )
    def _f_round(x, ndigits=0):
        n = int(ndigits) if ndigits is not None else 0
        return _to_series(x).apply(
            lambda v: (round(float(v), n) if v is not None else None)
        )

    def _f_mean(x):
        s = _to_series(x).astype("float64")
        m = s.mean(skipna=True)
        return pd.Series([m] * len(s))

    def _f_std(x):
        s = _to_series(x).astype("float64")
        v = s.std(skipna=True, ddof=1)
        return pd.Series([v] * len(s))

    def _f_min(x):
        s = _to_series(x).astype("float64")
        m = s.min(skipna=True)
        return pd.Series([m] * len(s))

    def _f_max(x):
        s = _to_series(x).astype("float64")
        m = s.max(skipna=True)
        return pd.Series([m] * len(s))

    def _f_sum(x):
        s = _to_series(x).astype("float64")
        m = s.sum(skipna=True)
        return pd.Series([m] * len(s))

    def _f_zscore(x, window=None):
        s = _to_series(x).astype("float64")
        if window is None:
            mu = s.mean(skipna=True); sd = s.std(skipna=True, ddof=1)
            if sd == 0 or pd.isna(sd):
                return pd.Series([None] * len(s))
            return (s - mu) / sd
        n = int(window)
        rm = s.rolling(window=n, min_periods=2).mean()
        rs = s.rolling(window=n, min_periods=2).std(ddof=1)
        z = (s - rm) / rs
        z = z.where((rs != 0) & rs.notna(), other=np.nan)
        return z

    def _f_rolling_mean(x, window):
        s = _to_series(x).astype("float64")
        n = int(window)
        return s.rolling(window=n, min_periods=1).mean()

    def _f_rolling_std(x, window):
        s = _to_series(x).astype("float64")
        n = int(window)
        return s.rolling(window=n, min_periods=2).std(ddof=1)

    def _f_pct_change(x, periods=1):
        s = _to_series(x).astype("float64")
        return s.pct_change(periods=int(periods)) * 100.0

    def _f_diff(x, periods=1):
        s = _to_series(x).astype("float64")
        return s.diff(periods=int(periods))

    def _f_shift(x, periods=1):
        s = _to_series(x).astype("float64")
        return s.shift(periods=int(periods))

    def _f_clip(x, lo=None, hi=None):
        s = _to_series(x).astype("float64")
        return s.clip(lower=lo, upper=hi)

    def _f_index100(x):
        s = _to_series(x).astype("float64")
        first = s.dropna().iloc[0] if s.dropna().shape[0] > 0 else None
        if first in (None, 0) or pd.isna(first):
            return pd.Series([None] * len(s))
        return (s / first) * 100.0

    def _f_rank_pct(x):
        s = _to_series(x).astype("float64")
        return s.rank(pct=True) * 100.0

    return {
        "log":   _f_log, "log10": _f_log10, "log2": _f_log2,
        "exp":   _f_exp, "sqrt":  _f_sqrt,
        "abs":   _f_abs, "sign":  _f_sign,
        "round": _f_round,
        "mean":  _f_mean, "std":  _f_std,
        "min":   _f_min, "max":  _f_max, "sum": _f_sum,
        "zscore": _f_zscore,
        "rolling_mean": _f_rolling_mean,
        "rolling_std":  _f_rolling_std,
        "pct_change":   _f_pct_change,
        "diff":         _f_diff,
        "shift":        _f_shift,
        "clip":         _f_clip,
        "index100":     _f_index100,
        "rank_pct":     _f_rank_pct,
    }


def _infer_computed_units(expr: str, refs: List[str],
                              datasets: Dict[str, Any]) -> Optional[str]:
    """Best-effort units inference for an auto-computed column.

    Heuristics, in priority order:
      1. ``zscore(...)`` -> ``z`` (rolling or full-series, both)
      2. ``pct_change`` / ``yoy_pct`` / ``rank_pct`` / ``index100`` ->
         ``percent``
      3. expression ends with ``* 100`` / ``*100`` / ``* 100.0`` AND
         every referenced column shares units = percent -> ``bp``
      4. all referenced columns share the same upstream units -> inherit
      5. otherwise None (no units set; runtime falls back to magnitude
         heuristic)
    """
    e = expr.strip()
    low = e.lower()
    if "zscore(" in low:
        return "z"
    if any(tok in low for tok in
           ("pct_change", "yoy_pct", "rank_pct", "index100")):
        return "percent"
    # `... * 100` (with optional whitespace, decimal) suffix
    import re
    if re.search(r"\*\s*100(?:\.0+)?\s*$", e):
        # If the inner refs are in percent units, the result is bp;
        # otherwise just leave the units ambiguous.
        if refs:
            ref_units = _gather_ref_units(refs, datasets)
            if ref_units and all(
                u in ("percent", "pct", "%") for u in ref_units
            ):
                return "bp"
    if refs:
        ref_units = _gather_ref_units(refs, datasets)
        if ref_units and len(set(ref_units)) == 1:
            return ref_units[0]
    return None


def _gather_ref_units(refs: List[str],
                          datasets: Dict[str, Any]) -> List[str]:
    """Collect the units of referenced columns across the manifest's
    datasets. Skips refs without explicit units."""
    out: List[str] = []
    for ref in refs:
        # Resolve qualified refs (`other_ds.col`) and bare refs by
        # walking every dataset's field_provenance.
        if "." in ref:
            ds_name, col = ref.split(".", 1)
            entry = datasets.get(ds_name) if isinstance(datasets, dict) else None
            if isinstance(entry, dict):
                fp = entry.get("field_provenance") or {}
                u = (fp.get(col) or {}).get("units")
                if u: out.append(u)
            continue
        for _, entry in (datasets or {}).items():
            if not isinstance(entry, dict):
                continue
            fp = entry.get("field_provenance") or {}
            u = (fp.get(ref) or {}).get("units")
            if u:
                out.append(u); break
    return out


def _safe_eval_expression(expr: str, columns: Dict[str, Any]) -> Any:
    """Evaluate ``expr`` against ``columns`` (dict of column_name -> Series).

    Whitelisted AST nodes only -- arithmetic, unary, names (column refs),
    constants, and calls to functions in :func:`_compute_helpers`. Any
    other node (Attribute, Subscript, Lambda, Comprehension, ...) raises
    ``ValueError`` so a malformed manifest can never execute arbitrary code.
    """
    import ast
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(
            f"compute expression {expr!r}: syntax error: {e}"
        )

    helpers = _compute_helpers()
    referenced_columns: List[str] = []

    def _walk(node):
        if isinstance(node, ast.Expression):
            return _walk(node.body)
        if isinstance(node, ast.BinOp):
            l = _walk(node.left); r = _walk(node.right); op = node.op
            if isinstance(op, ast.Add):    return l + r
            if isinstance(op, ast.Sub):    return l - r
            if isinstance(op, ast.Mult):   return l * r
            if isinstance(op, ast.Div):    return l / r
            if isinstance(op, ast.FloorDiv): return l // r
            if isinstance(op, ast.Mod):    return l % r
            if isinstance(op, ast.Pow):    return l ** r
            raise ValueError(
                f"compute: binary op {type(op).__name__} not supported "
                f"in {expr!r}"
            )
        if isinstance(node, ast.UnaryOp):
            v = _walk(node.operand)
            if isinstance(node.op, ast.UAdd):  return +v
            if isinstance(node.op, ast.USub):  return -v
            raise ValueError(
                f"compute: unary op {type(node.op).__name__} not supported"
            )
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(
                f"compute: constant {node.value!r} not allowed (only numbers)"
            )
        if isinstance(node, ast.Num):  # py<3.8 compat
            return node.n
        if isinstance(node, ast.Name):
            if node.id in columns:
                referenced_columns.append(node.id)
                return columns[node.id]
            raise ValueError(
                f"compute: name {node.id!r} not found "
                f"(available columns: {sorted(columns.keys())})"
            )
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError(
                    "compute: only top-level function calls allowed"
                )
            fn = node.func.id
            if fn not in helpers:
                raise ValueError(
                    f"compute: function {fn!r} not allowed "
                    f"(allowed: {sorted(helpers.keys())})"
                )
            args = [_walk(a) for a in node.args]
            kwargs = {kw.arg: _walk(kw.value) for kw in node.keywords}
            return helpers[fn](*args, **kwargs)
        raise ValueError(
            f"compute: AST node {type(node).__name__} not allowed in {expr!r}"
        )

    result = _walk(tree)
    return result, sorted(set(referenced_columns))


def _source_to_columns(source: List[List[Any]]) -> Dict[str, "pd.Series"]:
    """Convert a list-of-lists source to a {col: pd.Series} dict for
    expression evaluation. Header row is row 0; remaining rows are data.
    """
    import pandas as pd
    if not isinstance(source, list) or len(source) < 1:
        return {}
    header = list(source[0])
    rows = source[1:]
    cols = {h: [] for h in header}
    for row in rows:
        for i, h in enumerate(header):
            cols[h].append(row[i] if i < len(row) else None)
    out: Dict[str, pd.Series] = {}
    for name, col in cols.items():
        try:
            s = pd.Series(col)
            # Try to coerce to numeric; if every value is non-numeric
            # leave as object so downstream string handling still works.
            try:
                num = pd.to_numeric(s, errors="coerce")
                # If at least one non-null numeric value, prefer numeric
                if num.notna().any():
                    s = num
            except Exception:
                pass
            out[name] = s
        except Exception:
            out[name] = pd.Series(col)
    return out


def _columns_to_source(columns: Dict[str, "pd.Series"],
                          column_order: List[str]) -> List[List[Any]]:
    """Convert a {col: Series} dict back to list-of-lists source shape."""
    import pandas as pd
    from echart_studio import _format_datetime_value
    if not column_order:
        return [[]]
    n = max(len(columns[c]) for c in column_order)
    header = list(column_order)
    rows: List[List[Any]] = [header]
    for i in range(n):
        row: List[Any] = []
        for c in column_order:
            ser = columns[c]
            if i >= len(ser):
                row.append(None); continue
            v = ser.iloc[i]
            if v is None:
                row.append(None); continue
            try:
                if isinstance(v, float) and (v != v):  # NaN
                    row.append(None); continue
            except Exception:
                pass
            if hasattr(v, "item"):
                try:
                    row.append(v.item())
                    continue
                except Exception:
                    pass
            if isinstance(v, pd.Timestamp):
                row.append(_format_datetime_value(v))
                continue
            row.append(v)
        rows.append(row)
    return rows


def _apply_computed_datasets(manifest: Dict[str, Any]) -> List[str]:
    """Evaluate ``compute`` blocks on dataset entries.

    Runs AFTER :func:`_normalize_manifest_datasets` so every source has
    been coerced to list-of-lists. Mutates the manifest in place,
    replacing each ``compute`` block with a real ``source`` (and
    auto-populated ``field_provenance``). Resolves cross-dataset
    references (a compute block can read columns from its own source
    AND from any other dataset declared in the manifest, via
    ``"from": "<dataset_name>"``).

    Returns a list of error strings; empty list means success.
    """
    import pandas as pd
    ds = manifest.get("datasets")
    if not isinstance(ds, dict):
        return []

    errors: List[str] = []

    # Collect compute jobs in declared order. We expose a simple
    # one-pass evaluator -- a compute block can reference its own
    # source's columns OR another dataset's source columns, but a
    # compute block cannot reference another compute block's outputs.
    # That's a forward-compat constraint; cross-compute deps would need
    # a topological sort and we keep it simple for now.
    for name, entry in list(ds.items()):
        if not isinstance(entry, dict):
            continue
        compute = entry.get("compute")
        if not compute:
            continue
        if not isinstance(compute, dict):
            errors.append(_err(
                f"datasets.{name}.compute",
                "must be a dict of {output_column: expression_string}"))
            continue

        # Source columns: from the entry's own ``source`` if present,
        # otherwise from the dataset named by ``from``.
        source = entry.get("source")
        from_name = entry.get("from")
        if source is None and from_name is None:
            errors.append(_err(
                f"datasets.{name}",
                "compute block requires either an existing 'source' or "
                "a 'from': '<other_dataset_name>'"))
            continue
        if source is None:
            other = ds.get(from_name)
            if not isinstance(other, dict) or "source" not in other:
                errors.append(_err(
                    f"datasets.{name}.from",
                    f"references dataset '{from_name}' which has no source"))
                continue
            source = other["source"]
            # Inherit identity columns (date, label) from the source
            # dataset by copying its first column over by default.
            # Authors who want a different identity column can specify
            # ``identity_column`` explicitly.
        if not isinstance(source, list):
            errors.append(_err(
                f"datasets.{name}.source",
                "source must be a list-of-lists"))
            continue

        cols = _source_to_columns(source)
        # Allow the compute block to reference columns from any other
        # dataset in the manifest by prefixing with ``<ds>.<col>``. We
        # implement this lightly: pre-resolve any ``ds.col`` token
        # appearing in the expression to a synthesised column name in
        # ``cols``. Authors who don't use cross-dataset refs pay zero.
        for other_name, other_entry in ds.items():
            if other_name == name:
                continue
            if not isinstance(other_entry, dict):
                continue
            other_src = other_entry.get("source")
            if not isinstance(other_src, list):
                continue
            other_cols = _source_to_columns(other_src)
            for c, ser in other_cols.items():
                qualified = f"{other_name}.{c}"
                # Don't shadow a column in the home dataset.
                if qualified not in cols:
                    cols[qualified] = ser

        # Evaluate each compute expression in declared order. Each
        # output is added to `cols` so subsequent expressions can use
        # earlier ones (this gives us cheap dep resolution for the
        # 90% case: spread = a - b; spread_z = zscore(spread)).
        provenance_block = entry.get("field_provenance") or {}
        new_columns: List[str] = []
        for out_col, expr_raw in compute.items():
            if not isinstance(out_col, str):
                errors.append(_err(
                    f"datasets.{name}.compute",
                    f"output column name must be a string, got "
                    f"{type(out_col).__name__}"))
                continue
            if not isinstance(expr_raw, str):
                errors.append(_err(
                    f"datasets.{name}.compute.{out_col}",
                    f"expression must be a string, got "
                    f"{type(expr_raw).__name__}"))
                continue
            # Pre-process qualified names "ds.col" so the AST parser
            # treats them as a single name. We replace dots with a
            # safe sentinel and aliasing them in the columns dict.
            processed_expr = expr_raw
            qualified_aliases: Dict[str, str] = {}
            for q in [c for c in cols if "." in c]:
                # Construct a unique alias and substitute it where the
                # qualified name appears as a whole token in the
                # expression. We use word boundaries to avoid mangling
                # other identifiers.
                if q in processed_expr:
                    alias = q.replace(".", "__DOT__")
                    qualified_aliases[alias] = q
                    processed_expr = processed_expr.replace(q, alias)
            # Build a temporary cols dict that includes the aliases.
            eval_cols = dict(cols)
            for alias, real in qualified_aliases.items():
                eval_cols[alias] = cols[real]

            try:
                result, refs = _safe_eval_expression(
                    processed_expr, eval_cols
                )
            except (ValueError, ZeroDivisionError, Exception) as exc:  # noqa: BLE001
                errors.append(_err(
                    f"datasets.{name}.compute.{out_col}",
                    f"evaluation failed for {expr_raw!r}: {exc}"))
                continue

            # Map alias-references back to their qualified names for
            # provenance.computed_from
            mapped_refs: List[str] = []
            for r in refs:
                if r in qualified_aliases:
                    mapped_refs.append(qualified_aliases[r])
                elif r in cols:
                    mapped_refs.append(r)

            # If result is a scalar (e.g. mean of column) broadcast to
            # source length so the source list-of-lists stays well-formed.
            if not isinstance(result, pd.Series):
                # Scalar -- expand to series of source length
                source_len = max(0, len(source) - 1)
                result = pd.Series([result] * source_len)
            cols[out_col] = result
            new_columns.append(out_col)

            # Auto-fill provenance for the computed column if the author
            # didn't provide one already.
            if out_col not in provenance_block:
                inferred_units = _infer_computed_units(
                    expr_raw, mapped_refs, ds
                )
                prov: Dict[str, Any] = {
                    "system": "computed",
                    "recipe": expr_raw,
                    "computed_from": mapped_refs,
                    "display_name": out_col,
                }
                if inferred_units:
                    prov["units"] = inferred_units
                provenance_block[out_col] = prov

        if not new_columns:
            # No successful computes; leave entry alone but strip the
            # `compute` block so validation doesn't complain.
            entry.pop("compute", None)
            entry.pop("from", None)
            continue

        # Stitch the new columns onto the source (or build a fresh one
        # if there was no prior source).
        if source and len(source) > 0 and isinstance(source[0], list):
            existing_columns = list(source[0])
        else:
            existing_columns = []
        merged_columns = existing_columns + [
            c for c in new_columns if c not in existing_columns
        ]
        # Rebuild the source from `cols`, preserving the existing
        # column order and appending the new ones.
        # Filter to columns we actually have data for.
        emit_columns = [c for c in merged_columns if c in cols]
        new_source = _columns_to_source(cols, emit_columns)
        entry["source"] = new_source
        if provenance_block:
            entry["field_provenance"] = provenance_block
        entry.pop("compute", None)
        entry.pop("from", None)

    return errors


# ---------------------------------------------------------------------------
# Conditional widget visibility (`show_when`)
#
# Two evaluation contexts:
#   * data-condition (compile-time): widget is removed entirely when the
#     condition fails. The condition is a string like
#     ``"rates.latest.vix > 25"`` -- same dotted shape KPI sources use.
#     This is for "only render this risk panel when vol is elevated"
#     -style adaptive dashboards.
#   * filter-condition (runtime): widget is hidden via CSS display
#     when the named filter doesn't match the predicate. The widget is
#     emitted in the HTML and the JS runtime toggles it on filter change.
#
# Compound conditions: ``{"all": [<cond>, <cond>...]}`` (AND) and
# ``{"any": [<cond>, <cond>...]}`` (OR) are accepted at any level.
#
# A condition can mix data and filter clauses freely; the compile-time
# pass evaluates only the data clauses, leaving filter clauses for the
# runtime path. A widget is removed at compile time only when the
# data-only sub-condition resolves to False.
# ---------------------------------------------------------------------------

_SHOW_WHEN_OPS = {"==", "!=", ">", ">=", "<", "<=",
                   "contains", "startsWith", "endsWith"}


def _compare_op(a: Any, op: str, b: Any) -> bool:
    """Operator dispatch used by both compile-time data conditions and
    filter conditions. None propagates to False (a None on either side
    of any op is treated as failing).
    """
    if a is None or b is None:
        return False
    try:
        if op == "==":  return a == b
        if op == "!=":  return a != b
        if op == ">":   return float(a) >  float(b)
        if op == ">=":  return float(a) >= float(b)
        if op == "<":   return float(a) <  float(b)
        if op == "<=":  return float(a) <= float(b)
        if op == "contains":
            return str(b) in str(a)
        if op == "startsWith":
            return str(a).startswith(str(b))
        if op == "endsWith":
            return str(a).endswith(str(b))
    except (TypeError, ValueError):
        return False
    return False


def _parse_data_condition(s: str
                             ) -> Optional[Tuple[str, str, Any]]:
    """Parse a data-condition string of the form
    ``"<source_expr> <op> <value>"`` -- e.g. ``"rates.latest.vix > 25"``.
    Returns ``(source_expr, op, value)`` or None if the string can't be
    parsed cleanly.
    """
    if not isinstance(s, str):
        return None
    txt = s.strip()
    # Try the multi-char ops first so >= / <= / != / == aren't split
    # by their single-char prefix.
    for op in ("==", "!=", ">=", "<=", ">", "<"):
        idx = txt.find(op)
        if idx > 0:
            lhs = txt[:idx].strip()
            rhs = txt[idx + len(op):].strip()
            if not lhs or not rhs:
                continue
            # Try numeric, then string-with-quotes, then bare string
            try:
                rv: Any = float(rhs)
            except ValueError:
                if (rhs.startswith("'") and rhs.endswith("'")) or (
                    rhs.startswith('"') and rhs.endswith('"')):
                    rv = rhs[1:-1]
                else:
                    rv = rhs
            return lhs, op, rv
    # Word ops
    for word_op in (" contains ", " startsWith ", " endsWith "):
        idx = txt.find(word_op)
        if idx > 0:
            lhs = txt[:idx].strip()
            rhs = txt[idx + len(word_op):].strip()
            if rhs.startswith("'") and rhs.endswith("'"):
                rhs = rhs[1:-1]
            elif rhs.startswith('"') and rhs.endswith('"'):
                rhs = rhs[1:-1]
            return lhs, word_op.strip(), rhs
    return None


def _evaluate_show_when_compile(cond: Any, dfs: Dict[str, Any],
                                    *, _depth: int = 0
                                    ) -> Optional[bool]:
    """Evaluate the data-clauses of a show_when condition at compile time.

    Returns:
        * True   -- every data-clause is satisfied (or there are none)
        * False  -- at least one data-clause is unsatisfied
        * None   -- the condition cannot be fully resolved at compile
                    time (e.g. a filter clause is present); the widget
                    stays in the manifest and the runtime path takes over.

    Compound nodes (``all`` / ``any``) recurse with a small stack guard.
    """
    if cond is None:
        return True
    if _depth > 8:  # arbitrary depth cap; show_when is meant to be flat
        return None
    if not isinstance(cond, dict):
        return None

    if "all" in cond:
        results = [_evaluate_show_when_compile(c, dfs, _depth=_depth + 1)
                    for c in (cond.get("all") or [])]
        if any(r is False for r in results):
            return False
        if any(r is None for r in results):
            return None
        return True
    if "any" in cond:
        results = [_evaluate_show_when_compile(c, dfs, _depth=_depth + 1)
                    for c in (cond.get("any") or [])]
        if any(r is True for r in results):
            return True
        if any(r is None for r in results):
            return None
        return False if results else True

    # Filter clause: defer to runtime
    if "filter" in cond:
        return None

    # Data clause (compile-time)
    if "data" in cond:
        expr = cond.get("data")
        parsed = _parse_data_condition(expr) if isinstance(expr, str) else None
        if not parsed:
            # Misformed data clause: surface as failure so the author
            # notices something is off (rather than silently keeping
            # the widget visible).
            return False
        source_expr, op, rhs = parsed
        try:
            value, err = _resolve_kpi_value(source_expr, dfs)
        except Exception:  # noqa: BLE001
            value, err = None, "resolve failed"
        if err or value is None:
            return False
        return _compare_op(value, op, rhs)

    # Unknown clause shape
    return None


def _walk_widgets_in_layout(layout: Dict[str, Any]):
    """Yield (widget_dict, parent_row_list, index_in_row, container_dict)
    so callers can mutate widgets in place (most importantly: REMOVE
    widgets when a show_when fails)."""
    if not isinstance(layout, dict):
        return
    kind = layout.get("kind", "grid")
    if kind == "tabs":
        for t in layout.get("tabs", []) or []:
            for row in t.get("rows", []) or []:
                if not isinstance(row, list):
                    continue
                for i, w in enumerate(list(row)):
                    if isinstance(w, dict):
                        yield w, row, i, t
    else:
        for row in layout.get("rows", []) or []:
            if not isinstance(row, list):
                continue
            for i, w in enumerate(list(row)):
                if isinstance(w, dict):
                    yield w, row, i, layout


def _apply_show_when_compile(manifest: Dict[str, Any]) -> int:
    """Walk the manifest layout and remove every widget whose ``show_when``
    data-clause resolves to False at compile time. Returns the number of
    widgets removed (so callers can log it).

    Widgets with a runtime-only condition (filter clauses) are left in
    place; the JS runtime hides them via CSS on filter change.
    """
    layout = manifest.get("layout") or {}
    dfs = _materialize_datasets(manifest)
    rows_to_clean: List[List[Any]] = []
    removed = 0
    for w, row, _idx, _container in _walk_widgets_in_layout(layout):
        cond = w.get("show_when")
        if not cond:
            continue
        verdict = _evaluate_show_when_compile(cond, dfs)
        if verdict is False:
            # Replace with a sentinel; we'll filter rows after the walk
            # so we don't mutate the row mid-iteration in unsafe ways.
            row[row.index(w)] = None
            rows_to_clean.append(row)
            removed += 1
    for row in rows_to_clean:
        row[:] = [w for w in row if w is not None]
    return removed


def _augment_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Post-normalization, pre-validation enrichment that wires implicit
    contracts so PRISM-written manifests behave the way they look:

      1. chart widgets get ``dataset_ref`` auto-populated from
         ``spec.dataset`` when missing, so the runtime filter-application
         path (which keys off ``widget.dataset_ref``) reaches the chart.

      2. filters get a ``scope`` field inferred from their targets.
         If every resolved target lives in a single tab, ``scope`` is set
         to ``"tab:<id>"`` so the filter can render inside that tab
         (instead of squatting globally). If targets span tabs or include
         the wildcard ``"*"``, ``scope`` defaults to ``"global"``.

    Mutates the manifest in place and returns it.
    """
    layout = manifest.get("layout") or {}
    kind = layout.get("kind", "grid")

    widget_to_tab: Dict[str, Optional[str]] = {}
    tab_widget_ids: Dict[str, List[str]] = {}
    all_widgets: List[Dict[str, Any]] = []

    def _visit_rows(rows, tab_id: Optional[str]):
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                all_widgets.append(w)
                wid = w.get("id")
                if wid:
                    widget_to_tab[wid] = tab_id
                    if tab_id is not None:
                        tab_widget_ids.setdefault(tab_id, []).append(wid)

    if kind == "tabs":
        for t in layout.get("tabs", []) or []:
            if not isinstance(t, dict):
                continue
            _visit_rows(t.get("rows", []) or [], t.get("id"))
    else:
        _visit_rows(layout.get("rows", []) or [], None)

    filters = manifest.get("filters") or []

    # Set of widget ids that ANY filter targets. We only auto-populate
    # dataset_ref on widgets actually in the filter path so that charts
    # with pre-baked computed data (histograms, trendlines, bullets,
    # candlesticks, heatmaps, radar, gauge, sankey, treemap, funnel,
    # etc.) are not silently rewired and broken.
    targeted_ids: set = set()
    wildcard = False
    for f in filters:
        if not isinstance(f, dict):
            continue
        for t in f.get("targets") or []:
            if isinstance(t, str) and "*" in t:
                wildcard = True
            else:
                targeted_ids.add(t)

    # Chart types where the runtime rewire-on-filter path (dataset swap
    # + series encode substitution) can safely produce the right series
    # shape *without* access to the original builder. We only auto-wire
    # dataset_ref for widgets whose (chart_type, mapping) shape is in
    # this set. Anything else (computed series data, long-form with
    # color grouping, stacked bars, scatter with size/trendline, etc.)
    # keeps its pre-baked series.data and will not visually reshape on
    # filter change -- filter state still tracks and affects tables /
    # KPIs referencing the same dataset_ref.
    def _is_safe_for_rewire(chart_type: Optional[str],
                              mapping: Dict[str, Any]) -> bool:
        # rewire_strategy == "rebuild": the JS recomputes the entire
        # option from filtered dataset rows (scatter_studio rebuilds
        # series; correlation_matrix rebuilds the cell list from a
        # stable column whitelist). Independent of mapping shape.
        if chart_type in REBUILD_REWIREABLE_CHART_TYPES:
            return True
        # rewire_strategy == "reshape": wide-form dataset + encode
        # substitution. Mapping-shape conditions below further gate
        # which (chart_type, mapping) pairs are actually safe.
        if chart_type not in RESHAPE_REWIREABLE_CHART_TYPES:
            return False
        if mapping.get("color") or mapping.get("colour"):
            return False
        if mapping.get("trendline") or mapping.get("trendlines"):
            return False
        if mapping.get("stack") is True:
            return False
        if mapping.get("dual_axis_series") or mapping.get("axes"):
            # Dual-axis (legacy) and N-axis (canonical) multi_line still
            # use wide-form data so client-side filter reshape is safe.
            return chart_type == "multi_line"
        return True

    for w in all_widgets:
        if w.get("widget") != "chart":
            continue
        if w.get("dataset_ref"):
            continue
        wid = w.get("id")
        spec = w.get("spec")
        if not isinstance(spec, dict):
            continue
        ds_name = spec.get("dataset")
        if not ds_name:
            continue
        is_targeted = wildcard or (wid in targeted_ids)
        if not is_targeted:
            continue
        if not _is_safe_for_rewire(spec.get("chart_type"),
                                       spec.get("mapping") or {}):
            continue
        w["dataset_ref"] = ds_name

    for f in filters:
        if not isinstance(f, dict):
            continue
        if f.get("scope"):
            continue
        targets = f.get("targets") or []
        if not targets:
            f["scope"] = "global"
            continue
        has_wildcard = any(
            isinstance(t, str) and ("*" in t) for t in targets
        )
        if has_wildcard:
            f["scope"] = "global"
            continue
        resolved_tabs: set = set()
        for t in targets:
            tab = widget_to_tab.get(t)
            if tab is None:
                resolved_tabs.add("__none__")
                break
            resolved_tabs.add(tab)
        if len(resolved_tabs) == 1 and "__none__" not in resolved_tabs:
            f["scope"] = f"tab:{next(iter(resolved_tabs))}"
        else:
            f["scope"] = "global"

    # Reduce {value, label} dict defaults to their underlying value so the
    # JS runtime (which compares filterState[id] against row cells via
    # String() coercion) stays primitive-only. Options themselves keep
    # their original dict shape -- the renderer extracts value+label from
    # them in _option_value_label.
    def _strip_option_dict(v: Any) -> Any:
        if isinstance(v, dict) and "value" in v:
            return v["value"]
        return v

    for f in filters:
        if not isinstance(f, dict):
            continue
        if f.get("type") not in ("select", "multiSelect", "radio"):
            continue
        if "default" not in f:
            continue
        d = f["default"]
        if isinstance(d, list):
            f["default"] = [_strip_option_dict(x) for x in d]
        else:
            f["default"] = _strip_option_dict(d)

    return manifest


def prepare_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Canonical pre-validation augmentation pipeline. MUTATES IN PLACE.

    Runs (in order) the four side-effecting helpers that turn an
    LLM-friendly manifest dict into the canonical, validator-ready
    shape:

        1. ``_normalize_manifest_datasets``  -- DataFrames / list-of-lists
           / list-of-dicts all become ``{"source": [[h], [r], ...]}``.
        2. ``_apply_computed_datasets``      -- materialise every ``compute``
           block into a fresh ``source`` array (and stamp computed-column
           provenance). Errors are silently absorbed; failed compute blocks
           leave the column missing, which downstream
           ``chart_data_diagnostics`` reports as ``chart_mapping_column_missing``.
        3. ``_apply_show_when_compile``      -- drop widgets whose data-clause
           ``show_when`` resolves False before validation walks the layout.
        4. ``_augment_manifest``             -- infer filter ``scope``,
           strip ``{value, label}`` defaults to primitives, auto-wire
           ``widget.dataset_ref`` for filter-reachable charts.

    Returns the same manifest for chaining (``prepare_manifest(m); ...``).

    ``validate_manifest()`` runs an equivalent pipeline internally on a
    *private* working copy and never mutates the caller. This function
    is for callers who DO want the augmentations applied: typically
    ``compile_dashboard`` and ``render_dashboard`` on their own working
    manifest, or PRISM-side tooling that wants to inspect the
    canonical post-augment shape.

    The four helpers below remain in module-private form for callers
    that need finer-grained control (e.g. compile_dashboard captures
    the compute-error list separately to surface as a distinct failure
    mode); ``prepare_manifest`` is the canonical orchestrator.
    """
    _normalize_manifest_datasets(manifest)
    _apply_computed_datasets(manifest)
    _apply_show_when_compile(manifest)
    _augment_manifest(manifest)
    return manifest


def manifest_template(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Return a data-free copy of ``manifest`` suitable to save to disk
    as a reusable dashboard template.

    Dataset data rows are stripped; the header row (column names) is
    preserved when available so consumers know what schema each slot
    expects. Everything else (id, title, filters, layout, links, etc.)
    is deep-copied unchanged.

    Round-trips with :func:`populate_template`:

        tpl = manifest_template(m_with_dataframes)
        # ... later, at refresh time ...
        m_fresh = populate_template(tpl, {"rates": fresh_df, ...})
        compile_dashboard(m_fresh, ...)

    The template is pure JSON (no pandas), so ``json.dumps(tpl)`` works.
    """
    import copy
    if not isinstance(manifest, dict):
        raise TypeError(
            f"manifest_template: expected dict, got {type(manifest).__name__}"
        )

    # Normalize first so we always reason about the canonical
    # {name: {"source": [[header], [row], ...]}} shape.
    normalized = _normalize_manifest_datasets(copy.deepcopy(manifest))
    out = copy.deepcopy(normalized)

    ds = out.get("datasets")
    if not isinstance(ds, dict):
        return out
    for name, entry in list(ds.items()):
        header: List[Any] = []
        if isinstance(entry, dict):
            src = entry.get("source")
            if isinstance(src, list) and src and isinstance(src[0], list):
                header = list(src[0])
        ds[name] = {
            "source": [header] if header else [],
            "template": True,  # marker for populate_template sanity check
        }
    return out


def populate_template(template: Dict[str, Any],
                        datasets: Dict[str, Any],
                        *,
                        metadata: Optional[Dict[str, Any]] = None,
                        require_all_slots: bool = False) -> Dict[str, Any]:
    """Fill in a manifest template with fresh data and return a new
    manifest ready for :func:`compile_dashboard`.

    Parameters
    ----------
    template
        A manifest dict, typically produced by :func:`manifest_template`
        and re-loaded from disk via ``json.load``.
    datasets
        Mapping of dataset name -> DataFrame (or canonical list-of-lists
        source). Each entry replaces the corresponding slot in the
        template's ``datasets`` block. Names not already declared in the
        template are added.
    metadata
        Optional ``manifest.metadata`` merge (e.g. ``{"data_as_of": "..."}``).
        Existing metadata keys are preserved; passed keys override them.
    require_all_slots
        When True, raises ``KeyError`` if the template declares a dataset
        slot but no corresponding DataFrame was provided. Useful to guard
        refresh pipelines from silently missing data.

    Returns
    -------
    dict
        A new manifest ready to pass to ``compile_dashboard``. The input
        template is NOT mutated.
    """
    import copy
    if not isinstance(template, dict):
        raise TypeError(
            f"populate_template: template must be a dict, "
            f"got {type(template).__name__}"
        )
    if not isinstance(datasets, dict):
        raise TypeError(
            f"populate_template: datasets must be a dict of name -> "
            f"DataFrame, got {type(datasets).__name__}"
        )

    out = copy.deepcopy(template)
    out_ds = out.setdefault("datasets", {})

    if require_all_slots:
        missing = [
            name for name, entry in out_ds.items()
            if isinstance(entry, dict) and entry.get("template")
            and name not in datasets
        ]
        if missing:
            raise KeyError(
                f"populate_template: template declares dataset slot(s) "
                f"{sorted(missing)} but no data was provided for them"
            )

    for name, df in datasets.items():
        out_ds[name] = df  # compile_dashboard normalizes DataFrames -> source

    if metadata:
        md = out.setdefault("metadata", {})
        if not isinstance(md, dict):
            raise TypeError(
                f"populate_template: manifest.metadata must be a dict, "
                f"got {type(md).__name__}"
            )
        md.update(metadata)
    return out


def _source_to_dataframe(source: Any):
    """Materialize a manifest dataset source into a pandas DataFrame.

    Accepts either:
        [[header...], [row...], ...]     list-of-lists w/ header as row 0
        [{"col": val, ...}, ...]         list-of-dicts (column keys)

    Attempts lightweight date parsing: any column whose non-null values all
    parse as dates is converted to datetime.

    The ``pd.to_datetime(..., errors="coerce")`` probe is wrapped in
    ``warnings.catch_warnings`` so the dateutil-fallback ``UserWarning``
    pandas emits on string columns doesn't pollute compile_dashboard's
    output. The probe is just our heuristic and the user explicitly
    opted into best-effort parsing by passing a string column.
    """
    import pandas as pd
    import warnings
    if source is None:
        return pd.DataFrame()
    if not isinstance(source, list) or not source:
        return pd.DataFrame()
    first = source[0]
    if isinstance(first, dict):
        df = pd.DataFrame(source)
    elif isinstance(first, list):
        header = first
        rows = source[1:]
        df = pd.DataFrame(rows, columns=header)
    else:
        raise TypeError(
            f"dataset.source must be list-of-lists or list-of-dicts, "
            f"got first element of type {type(first).__name__}"
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        for col in df.columns:
            ser = df[col]
            if ser.dtype != object:
                continue
            non_null = ser.dropna()
            if non_null.empty:
                continue
            if not all(isinstance(v, str) for v in non_null):
                continue
            parsed = pd.to_datetime(non_null, errors="coerce")
            if parsed.notna().all():
                df[col] = pd.to_datetime(ser, errors="coerce")
    return df


def _spec_to_option(
    spec: Dict[str, Any],
    datasets: Dict[str, Dict[str, Any]],
    manifest_theme: str,
    manifest_palette: Optional[str],
) -> Dict[str, Any]:
    """Lower a high-level chart spec into an ECharts option dict.

    Looks up `spec.dataset` in manifest.datasets, reconstructs a DataFrame,
    and runs it through the same builder dispatch that make_echart() uses.
    Per-spec `theme` / `palette` override the manifest defaults.

    Raises ValueError on unknown dataset / chart_type, or missing mapping.
    """
    if not isinstance(spec, dict):
        raise TypeError(f"spec must be a dict, got {type(spec).__name__}")
    chart_type = spec.get("chart_type")
    if not chart_type:
        raise ValueError("spec.chart_type is required")
    ds_name = spec.get("dataset")
    if not ds_name:
        raise ValueError("spec.dataset is required")
    if ds_name not in datasets:
        raise ValueError(
            f"spec.dataset '{ds_name}' not declared in manifest.datasets "
            f"(available: {sorted(datasets.keys())})"
        )
    mapping = spec.get("mapping")
    if mapping is None:
        raise ValueError("spec.mapping is required")
    if not isinstance(mapping, dict):
        raise TypeError("spec.mapping must be a dict")

    # Lazy imports: keep the manifest module light and avoid import cycles
    from echart_studio import (
        _BUILDER_DISPATCH, _build_context, _apply_annotations,
        _install_default_axis_decimal_cap,
        _install_default_tooltip_decimal_cap,
    )

    if chart_type not in _BUILDER_DISPATCH:
        raise ValueError(
            f"spec.chart_type '{chart_type}' not in builder dispatch; "
            f"available: {sorted(_BUILDER_DISPATCH.keys())}"
        )

    source = datasets[ds_name].get("source")
    df = _source_to_dataframe(source)

    ctx = _build_context(
        chart_type=chart_type,
        theme=spec.get("theme") or manifest_theme,
        palette=spec.get("palette") or manifest_palette,
        dimensions=spec.get("dimensions", "wide"),
        title=None,
        subtitle=None,
    )

    # scatter_studio: ``spec.studio`` is sibling to ``spec.mapping`` for
    # readability (it describes the studio behavior, not column mappings),
    # but the builder takes a single ``mapping`` dict. Merge under
    # ``mapping["studio"]`` here so the builder sees both.
    mapping_for_builder = dict(mapping)
    if chart_type == "scatter_studio":
        if isinstance(spec.get("studio"), dict):
            existing = (mapping.get("studio")
                          if isinstance(mapping.get("studio"), dict) else {})
            merged = dict(existing)
            merged.update(spec["studio"])
            mapping_for_builder["studio"] = merged

    builder = _BUILDER_DISPATCH[chart_type]
    opt = builder(df, mapping_for_builder, ctx)

    spec_annotations = spec.get("annotations")
    mapping_annotations = mapping.get("annotations")
    combined: List[Dict[str, Any]] = []
    if mapping_annotations:
        combined.extend(list(mapping_annotations))
    if spec_annotations:
        combined.extend(list(spec_annotations))
    if combined:
        _apply_annotations(opt, combined)

    # Post-build cosmetic pass: humanize series / legend labels, apply
    # optional legend_position / legend_show overrides, and format
    # date-like x-axis tick labels. Each of these is a "polish layer"
    # applied uniformly across every chart type so individual builders
    # don't all need to grow the same cosmetic knobs.
    _apply_post_build_polish(opt, spec, mapping)

    # Cap value-axis tick precision at MAX_DASHBOARD_DECIMALS for any
    # axis the builder + polish + per-spec overrides left without an
    # explicit formatter. Idempotent and tolerant of axes already
    # carrying a custom formatter.
    _install_default_axis_decimal_cap(opt)
    # Cap tooltip-value precision at MAX_DASHBOARD_DECIMALS for any
    # tooltip the builder + per-spec overrides left without a custom
    # ``formatter`` or ``valueFormatter``. Idempotent.
    _install_default_tooltip_decimal_cap(opt)
    return opt


def _humanize_col(name: Any) -> str:
    """Turn a column/series identifier into a readable label.

    Rules:
      * snake_case -> Title Case with spaces
      * '_pct' -> '(%)'
      * preserves all-uppercase tokens (e.g. 'us_10y' -> 'US 10Y')
      * leaves non-string input untouched
    """
    if not isinstance(name, str) or not name:
        return name
    lowered = name.lower()
    if lowered.endswith("_pct"):
        lowered = lowered[:-4] + "_(%)"
    parts = [p for p in lowered.split("_") if p]

    def _tok(t: str) -> str:
        if t == "(%)":
            return "(%)"
        if t in {"us", "eu", "uk", "jp", "cn", "em", "dm", "hk"}:
            return t.upper()
        if len(t) <= 3 and any(ch.isdigit() for ch in t):
            return t.upper()
        if t in {"pnl", "mtd", "ytd", "yoy", "mom", "wow", "eps", "dxy",
                  "gdp", "cpi", "pmi", "ism", "nfp", "oas", "vix", "var",
                  "fx", "hy", "ig", "ir"}:
            return t.upper()
        return t.capitalize()
    return " ".join(_tok(p) for p in parts)


def _apply_post_build_polish(opt: Dict[str, Any],
                               spec: Dict[str, Any],
                               mapping: Dict[str, Any]) -> None:
    """Apply polish layers to an already-built chart option in place.

    Polish layers:
      * legend position/visibility (spec.legend_position, legend_show)
      * humanize series names unless mapping.humanize is False, or override
        via mapping.series_labels = {raw_name: display_name}
      * x-axis tick date formatting via mapping.x_date_format
    """
    # Legend visibility + position overrides. These are top-level knobs
    # that apply uniformly to every chart type.
    legend = opt.get("legend") or {}
    legend_show = spec.get("legend_show")
    if legend_show is not None:
        legend["show"] = bool(legend_show)
    pos = spec.get("legend_position") or mapping.get("legend_position")
    if pos:
        # reset any prior side settings so the assignment is crisp
        for k in ("left", "right", "top", "bottom", "orient"):
            legend.pop(k, None)
        pos = str(pos).lower()
        if pos == "top":
            legend["top"] = 8
            legend["left"] = "center"
            legend["orient"] = "horizontal"
        elif pos == "bottom":
            legend["bottom"] = 8
            legend["left"] = "center"
            legend["orient"] = "horizontal"
        elif pos == "left":
            legend["left"] = 8
            legend["top"] = "middle"
            legend["orient"] = "vertical"
        elif pos == "right":
            legend["right"] = 8
            legend["top"] = "middle"
            legend["orient"] = "vertical"
        elif pos == "none":
            legend["show"] = False
        # Plain (wrapping) legend is easier to read on dashboards than
        # the paginated default when many items don't fit on one line.
        legend["type"] = "plain"
        legend.setdefault("itemGap", 14)
        legend.setdefault("textStyle", {"fontSize": 12})
    if legend:
        opt["legend"] = legend

    # Humanize series names + legend entries. Caller can disable
    # globally with mapping.humanize = False or override per-series
    # with mapping.series_labels = {raw: display}.
    humanize = mapping.get("humanize")
    overrides = mapping.get("series_labels") or {}
    if humanize is None:
        humanize = True
    def _maybe_humanize(name: str) -> Optional[str]:
        if name in overrides:
            return overrides[name]
        if not humanize:
            return None
        if "_" in name:
            return _humanize_col(name)
        # single-word lowercase token: capitalize it (so axis labels
        # like "beta" render as "Beta"). Multi-case tokens like "SPX"
        # or "AAA" are left alone.
        if name.isalpha() and name.islower():
            return _humanize_col(name)
        return None

    rename: Dict[str, str] = {}
    for s in opt.get("series") or []:
        if not isinstance(s, dict):
            continue
        orig = s.get("name")
        if not isinstance(orig, str) or not orig:
            continue
        new = _maybe_humanize(orig)
        if new and new != orig:
            # Preserve the raw column name on the series so the
            # runtime (materializeOption) can still look up the right
            # dataset column when rewiring filter state. Without this,
            # a humanised name like "ECB" doesn't match the lowercase
            # dataset column "ecb" and ECharts falls back to positional
            # index, which is wrong for long-form datasets.
            s["_column"] = orig
            s["name"] = new
            rename[orig] = new

    if rename and isinstance(opt.get("legend"), dict):
        ld = opt["legend"].get("data")
        if isinstance(ld, list):
            opt["legend"]["data"] = [
                rename.get(n, n) if isinstance(n, str) else n
                for n in ld
            ]

    # Parallel coordinates axis names come from column names; humanize
    # them unless mapping.humanize is False.
    if isinstance(opt.get("parallelAxis"), list):
        for ax in opt["parallelAxis"]:
            if not isinstance(ax, dict):
                continue
            nm = ax.get("name")
            if not isinstance(nm, str):
                continue
            new = _maybe_humanize(nm)
            if new:
                ax["name"] = new

    # Pie / donut polish:
    #   * When the legend sits at the bottom, the slice-edge labels
    #     duplicate what's in the legend AND get truncated into the
    #     tile walls ("United States..."). Hide them and rely on the
    #     legend. Users can force them back with
    #     `mapping.show_slice_labels: True`.
    #   * Also recenter / slightly shrink the pie so the plot itself
    #     is vertically centered above the legend.
    show_slice = bool(mapping.get("show_slice_labels", False))
    for s in opt.get("series") or []:
        if not isinstance(s, dict):
            continue
        if s.get("type") != "pie":
            continue
        if pos in ("top", "bottom") and not show_slice:
            label = s.get("label") or {}
            label["show"] = False
            s["label"] = label
            # Also suppress label lines connecting to hidden labels.
            s["labelLine"] = {"show": False}
            if pos == "bottom":
                # Matches build_pie's 1-row-legend anchor. build_pie
                # always sets center so this setdefault is a no-op in
                # the normal path; it stays for the legacy case where
                # a caller constructs a pie option without going
                # through build_pie.
                s.setdefault("center", ["50%", "50%"])
            else:
                s.setdefault("center", ["50%", "58%"])
            # Give the pie a bit more breathing room now that labels
            # are gone.
            cur_r = s.get("radius")
            if isinstance(cur_r, list) and len(cur_r) == 2:
                # donut: keep the ring ratio, bump outer radius a touch
                s["radius"] = [cur_r[0], "78%"]
            else:
                s["radius"] = "72%"

    # X-axis date formatting. ECharts understands JS format functions;
    # we emit a string that the rendering layer's _reviveFns treats as
    # a live JS function so the tick label looks like "Apr 15" etc.
    x_fmt = mapping.get("x_date_format") or spec.get("x_date_format")
    if x_fmt:
        x_axis = opt.get("xAxis")
        axes: List[Dict[str, Any]]
        if isinstance(x_axis, list):
            axes = x_axis
        elif isinstance(x_axis, dict):
            axes = [x_axis]
        else:
            axes = []
        for ax in axes:
            al = ax.setdefault("axisLabel", {})
            if x_fmt == "auto":
                al["formatter"] = (
                    "function(v){"
                    " var d = new Date(v);"
                    " if (isNaN(d.getTime())) return v;"
                    " var m = ['Jan','Feb','Mar','Apr','May','Jun',"
                    "'Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];"
                    " return m + ' ' + d.getDate();"
                    "}"
                )
            else:
                al["formatter"] = str(x_fmt)

    # Axis range overrides. `y_min` / `y_max` / `x_min` / `x_max` on
    # mapping or spec get applied to the corresponding axis. Helpful
    # when auto-scale zooms the chart out to include 0 and squashes
    # the signal (e.g. rates around 5% plotted on a 0-9 axis).
    def _axis_range(axis_key: str, min_key: str, max_key: str):
        mn = mapping.get(min_key)
        mx = mapping.get(max_key)
        if mn is None and mx is None:
            mn = spec.get(min_key)
            mx = spec.get(max_key)
        if mn is None and mx is None:
            return
        axis = opt.get(axis_key)
        axes_: List[Dict[str, Any]]
        if isinstance(axis, list):
            axes_ = axis
        elif isinstance(axis, dict):
            axes_ = [axis]
        else:
            return
        for a in axes_:
            if mn is not None:
                a["min"] = mn
            if mx is not None:
                a["max"] = mx

    _axis_range("yAxis", "y_min", "y_max")
    _axis_range("xAxis", "x_min", "x_max")

    # `axis_format` / `y_format` / `x_format` shortcut for common
    # numeric label styles without writing raw ECharts functions.
    def _axis_number_format(axis_key: str, key: str):
        fmt = mapping.get(key) or spec.get(key)
        if not fmt:
            return
        axis = opt.get(axis_key)
        axes_: List[Dict[str, Any]] = (
            axis if isinstance(axis, list)
            else ([axis] if isinstance(axis, dict) else [])
        )
        fmt_str: Optional[str] = None
        if fmt == "percent":
            fmt_str = ("function(v){ return (v*100).toFixed(1) + '%'; }")
        elif fmt == "bp":
            fmt_str = ("function(v){ return v.toFixed(0) + ' bp'; }")
        elif fmt == "usd":
            fmt_str = ("function(v){ return '$' + v.toLocaleString(); }")
        elif fmt == "compact":
            fmt_str = (
                "function(v){"
                " var a = Math.abs(v);"
                " if (a >= 1e12) return (v/1e12).toFixed(1) + 'T';"
                " if (a >= 1e9)  return (v/1e9).toFixed(1) + 'B';"
                " if (a >= 1e6)  return (v/1e6).toFixed(1) + 'M';"
                " if (a >= 1e3)  return (v/1e3).toFixed(1) + 'K';"
                " return v.toString();"
                "}"
            )
        else:
            fmt_str = str(fmt)
        for a in axes_:
            al = a.setdefault("axisLabel", {})
            al["formatter"] = fmt_str

    _axis_number_format("yAxis", "y_format")
    _axis_number_format("xAxis", "x_format")

    # Axis cosmetic toggles.
    def _axis_cosmetics(axis_key: str):
        axis = opt.get(axis_key)
        if isinstance(axis, list):
            axes_ = axis
        elif isinstance(axis, dict):
            axes_ = [axis]
        else:
            return
        show_grid = spec.get("show_grid", mapping.get("show_grid"))
        show_axis_line = spec.get(
            "show_axis_line", mapping.get("show_axis_line"))
        show_axis_ticks = spec.get(
            "show_axis_ticks", mapping.get("show_axis_ticks"))
        for a in axes_:
            if show_grid is not None:
                a.setdefault("splitLine", {})["show"] = bool(show_grid)
            if show_axis_line is not None:
                a.setdefault("axisLine", {})["show"] = bool(show_axis_line)
            if show_axis_ticks is not None:
                a.setdefault("axisTick", {})["show"] = bool(show_axis_ticks)
    _axis_cosmetics("xAxis")
    _axis_cosmetics("yAxis")

    # `tooltip`: per-spec chart tooltip override. Accepts an ECharts
    # tooltip dict directly, or a sugared form:
    #   "tooltip": {
    #       "trigger": "axis" | "item" | "none",
    #       "decimals": 2,                      # format numeric values
    #       "formatter": "<fn string>",         # raw ECharts formatter
    #       "show": False,                      # hide tooltip entirely
    #   }
    tip_cfg = spec.get("tooltip")
    if tip_cfg is not None:
        tt = opt.get("tooltip") or {}
        if not isinstance(tt, dict):
            tt = {}
        if isinstance(tip_cfg, dict):
            if "show" in tip_cfg:
                tt["show"] = bool(tip_cfg["show"])
            if "trigger" in tip_cfg:
                tt["trigger"] = tip_cfg["trigger"]
            if "formatter" in tip_cfg:
                tt["formatter"] = tip_cfg["formatter"]
            if "decimals" in tip_cfg:
                d = clamp_decimals(tip_cfg["decimals"], default=2)
                tt["valueFormatter"] = (
                    "function(v){"
                    f" if (v == null) return '';"
                    f" var n = Number(v);"
                    f" if (isNaN(n)) return String(v);"
                    f" return n.toLocaleString(undefined,"
                    f" {{minimumFractionDigits: {d},"
                    f"   maximumFractionDigits: {d}}});"
                    "}"
                )
            # Pass through any unknown keys verbatim so callers can
            # reach ECharts-native tooltip options.
            for k, v in tip_cfg.items():
                if k in {"show", "trigger", "formatter", "decimals"}:
                    continue
                tt[k] = v
        opt["tooltip"] = tt

    # Per-series color overrides. `mapping.series_colors = {raw_col:
    # "#hex"}`. We look up by either the pre-humanise `_column` or the
    # final `name`, so callers can reference whichever is natural.
    series_colors = mapping.get("series_colors") or {}
    if isinstance(series_colors, dict) and series_colors:
        for s in opt.get("series") or []:
            if not isinstance(s, dict):
                continue
            col_key = s.get("_column") or s.get("name")
            if col_key in series_colors:
                s.setdefault("itemStyle", {})["color"] = \
                    series_colors[col_key]
                s.setdefault("lineStyle", {})["color"] = \
                    series_colors[col_key]

    # `grid_padding`: per-spec grid override. Accepts a dict with any
    # subset of {top, right, bottom, left} and merges into the option's
    # grid. Useful when a chart has an especially long y-axis title
    # or tick labels that need more breathing room. Auto-bumps
    # `right` when a dual-axis chart emits a right-side axis name so
    # the rotated label doesn't clip against the tile edge.
    pad = (spec.get("grid_padding") or mapping.get("grid_padding")
           or {})
    grid = opt.get("grid") or {}
    if isinstance(grid, list):
        grids = grid
    elif isinstance(grid, dict):
        grids = [grid]
    else:
        grids = []
    yaxes = opt.get("yAxis")
    has_right_axis_name = (
        isinstance(yaxes, list) and len(yaxes) >= 2
        and isinstance(yaxes[1], dict) and yaxes[1].get("name")
    )
    for g in grids:
        for k in ("top", "right", "bottom", "left"):
            if k in pad:
                g[k] = pad[k]
        if has_right_axis_name and "right" not in pad:
            # Ensure the rotated right-axis name has room even when
            # tick labels run to 4 or 5 digits on the right side.
            g["right"] = max(int(g.get("right", 24) or 24), 56)

    # Default in-chart zoom for time-axis charts. Every chart ships with
    # a draggable slider + scroll/pinch zoom so users can scrub the
    # x-axis directly inside the chart instead of relying on a global
    # "lookback" dropdown to chop the data. The slider sits below the
    # grid and is bumped up when the chart already has bottom padding
    # (legend at bottom, x-axis title, etc.) so it doesn't collide.
    #
    # Opt-out: ``spec.chart_zoom = False`` (or ``mapping.chart_zoom``)
    # disables the auto-injection. Builders that already wrote their
    # own ``dataZoom`` (candlestick) are left alone.
    chart_zoom_opt = spec.get("chart_zoom")
    if chart_zoom_opt is None:
        chart_zoom_opt = mapping.get("chart_zoom")
    _inject_default_chart_zoom(opt, chart_zoom_opt)


def _resolve_chart_zoom_opt(opt: Any) -> tuple:
    """Translate the author-facing ``chart_zoom`` value into
    ``(want_inside, want_slider)``.

    Accepts:
      * ``None`` / ``True``               -> ``(True, True)``  -- default
      * ``False``                         -> ``(False, False)`` -- full opt-out
      * ``{"slider": bool, "inside": bool}`` -- granular; missing keys
        default to True
      * anything else                     -> treated as truthy
    """
    if opt is False:
        return (False, False)
    if isinstance(opt, dict):
        return (bool(opt.get("inside", True)),
                bool(opt.get("slider", True)))
    return (True, True)


def _data_span_seconds(opt: Dict[str, Any]):
    """Best-effort estimate of the time-axis data span in seconds.

    Probes ``opt.dataset[*].source`` first (col 0 = x), then falls back
    to inline ``opt.series[*].data`` for charts without a dataset rewire
    (sparkline / KPI tile shape). Parses ECharts' usual time-string
    forms: ``"%Y-%m-%d"``, ``"%Y-%m-%d %H:%M:%S"``, ``"%Y-%m-%dT%H:%M:%S"``,
    with optional tz offset. Returns ``None`` if the span can't be
    determined (which the caller treats as "fall back to the default
    ``"Mon YYYY"`` formatter")."""
    import datetime as _dt

    def _parse(v) -> "Optional[float]":
        if isinstance(v, (int, float)):
            return float(v) / 1000.0
        if not isinstance(v, str) or not v:
            return None
        s = v.replace(" ", "T", 1)
        try:
            return _dt.datetime.fromisoformat(s).timestamp()
        except (ValueError, TypeError):
            return None

    first_x = last_x = None

    dataset = opt.get("dataset") or []
    if isinstance(dataset, dict):
        dataset = [dataset]
    for ds in dataset:
        if not isinstance(ds, dict):
            continue
        src = ds.get("source") or []
        if not isinstance(src, list) or len(src) < 2:
            continue
        body = src[1:]
        head = body[0]
        tail = body[-1]
        if isinstance(head, list) and head:
            first_x = first_x if first_x is not None else _parse(head[0])
        if isinstance(tail, list) and tail:
            last_x = last_x if last_x is not None else _parse(tail[0])
        if first_x is not None and last_x is not None:
            break

    if first_x is None or last_x is None:
        for s in opt.get("series") or []:
            if not isinstance(s, dict):
                continue
            data = s.get("data") or []
            if not isinstance(data, list) or not data:
                continue
            head = data[0]
            tail = data[-1]
            if isinstance(head, list) and head:
                first_x = first_x if first_x is not None else _parse(head[0])
            if isinstance(tail, list) and tail:
                last_x = last_x if last_x is not None else _parse(tail[0])
            if first_x is not None and last_x is not None:
                break

    if first_x is None or last_x is None:
        return None
    return abs(last_x - first_x)


def _slider_label_formatter_for_span(span_seconds) -> str:
    """Pick a JS labelFormatter for the dataZoom slider based on the
    data's actual time span.

    Buckets (chosen to keep slider tick labels readable across the
    full PRISM corpus -- 5y daily panels, 30y FRED series, 5d intraday
    event windows, 12h same-day intraday tracks):

      span <= 1 day        -> ``"HH:MM"``       (intraday)
      span <= 14 days      -> ``"Mon dd HH:MM"`` (multi-day intraday)
      span <= 1 year       -> ``"Mon dd"``      (daily within year)
      span > 1 year (or unknown) -> ``"Mon YYYY"`` (multi-year, current default)

    All formatters share the same NaN-guard prefix so the slider never
    crashes on a stray timestamp it can't parse.
    """
    DAY = 86400.0
    HH_MM = (
        "function(v){"
        " var d = new Date(v);"
        " if (isNaN(d.getTime())) return v;"
        " function p(n){return n<10?'0'+n:''+n;}"
        " return p(d.getHours())+':'+p(d.getMinutes());"
        "}"
    )
    DD_MMM_HH_MM = (
        "function(v){"
        " var d = new Date(v);"
        " if (isNaN(d.getTime())) return v;"
        " var m = ['Jan','Feb','Mar','Apr','May','Jun',"
        " 'Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];"
        " function p(n){return n<10?'0'+n:''+n;}"
        " return m+' '+d.getDate()+' '+p(d.getHours())+':'+p(d.getMinutes());"
        "}"
    )
    DD_MMM = (
        "function(v){"
        " var d = new Date(v);"
        " if (isNaN(d.getTime())) return v;"
        " var m = ['Jan','Feb','Mar','Apr','May','Jun',"
        " 'Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];"
        " return m+' '+d.getDate();"
        "}"
    )
    MMM_YYYY = (
        "function(v){"
        " var d = new Date(v);"
        " if (isNaN(d.getTime())) return v;"
        " var m = ['Jan','Feb','Mar','Apr','May','Jun',"
        " 'Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];"
        " return m + ' ' + d.getFullYear();"
        "}"
    )
    if span_seconds is None:
        return MMM_YYYY
    if span_seconds <= DAY:
        return HH_MM
    if span_seconds <= 14 * DAY:
        return DD_MMM_HH_MM
    if span_seconds <= 365 * DAY:
        return DD_MMM
    return MMM_YYYY


def _inject_default_chart_zoom(opt: Dict[str, Any],
                                  chart_zoom_opt: Any) -> None:
    """Inject inside + slider dataZoom for time-axis charts.

    Skip when:
      * ``chart_zoom_opt`` resolves to ``(False, False)`` -- full opt-out
      * ``opt`` already declares its own dataZoom (e.g. candlestick)
      * the chart has no time-typed xAxis (heatmaps, pies, polar shapes)
      * the chart uses a non-cartesian coordinate system (radar, polar)

    Granular control via ``chart_zoom`` value:

      * ``None`` / ``True``                 -- both inside + slider (default)
      * ``False``                           -- nothing injected
      * ``{"slider": bool, "inside": bool}`` -- pick exactly the components you want.
        Useful for: ``{"slider": False}`` on dashboards where vertical
        space is tight (slider claims ~28px), or ``{"inside": False}``
        on small tiles where the inside-pan would steal page-scroll.

    The slider's ``labelFormatter`` is auto-selected from the data span
    via :func:`_slider_label_formatter_for_span` -- the previous
    ``"Mon YYYY"`` default became useless when intraday data started
    rendering correctly post-strftime-fix (a 12h chart with both ends
    labelled "Apr 2026" tells the user nothing).

    The slider is sized to clear the grid bottom; we bump the grid's
    bottom padding when needed so the slider doesn't overlap the
    x-axis tick labels.
    """
    want_inside, want_slider = _resolve_chart_zoom_opt(chart_zoom_opt)
    if not want_inside and not want_slider:
        return
    if "dataZoom" in opt:
        return

    x_axis = opt.get("xAxis")
    if x_axis is None:
        return
    axes_list = x_axis if isinstance(x_axis, list) else [x_axis]
    time_axis_indices = [
        i for i, ax in enumerate(axes_list)
        if isinstance(ax, dict) and ax.get("type") == "time"
    ]
    if not time_axis_indices:
        return

    # Slider sits ~28px tall at bottom: 18px control + 10px breathing
    # room. Only bump grid padding when we're actually injecting it.
    slider_height = 18
    slider_bottom = 10
    slider_total = slider_height + slider_bottom + 14  # 14px clearance

    if want_slider:
        grid = opt.get("grid")
        if isinstance(grid, dict):
            grids = [grid]
        elif isinstance(grid, list):
            grids = grid
        else:
            grids = []
        for g in grids:
            if not isinstance(g, dict):
                continue
            cur = g.get("bottom")
            try:
                cur_n = int(cur) if cur is not None else 0
            except (TypeError, ValueError):
                cur_n = 0
            if cur_n < slider_total:
                g["bottom"] = slider_total

    span_s = _data_span_seconds(opt)
    label_formatter = _slider_label_formatter_for_span(span_s)

    dataZoom: List[Dict[str, Any]] = []
    if want_inside:
        dataZoom.append({
            "type": "inside",
            "xAxisIndex": time_axis_indices,
            "zoomLock": False,
            "moveOnMouseMove": True,
            "preventDefaultMouseMove": False,
        })
    if want_slider:
        dataZoom.append({
            "type": "slider",
            "xAxisIndex": time_axis_indices,
            "height": slider_height,
            "bottom": slider_bottom,
            "borderColor": "transparent",
            "fillerColor": "rgba(26,54,93,0.08)",
            "handleStyle": {"color": "#1a365d", "borderColor": "#1a365d"},
            "moveHandleStyle": {"color": "#1a365d", "opacity": 0.45},
            "selectedDataBackground": {
                "lineStyle": {"color": "#1a365d", "opacity": 0.45},
                "areaStyle": {"color": "#1a365d", "opacity": 0.10},
            },
            "dataBackground": {
                "lineStyle": {"color": "#94a3b8", "opacity": 0.45},
                "areaStyle": {"color": "#94a3b8", "opacity": 0.10},
            },
            "labelFormatter": label_formatter,
        })
    opt["dataZoom"] = dataZoom


def _format_placeholder_subtext(triage: Dict[str, Any],
                                 chart_type: Optional[str] = None,
                                 ) -> str:
    """Compose the ``(no data)`` subtext rendered inside a failed chart
    card.

    The card has ~ 140 chars of horizontal room before ECharts truncates
    the subtext, so we keep it dense + actionable: a short
    ``human_message`` from the translator, prefixed by the chart_type
    when known, and fall back to the raw exception when no translation
    is registered. PRISM's iteration loop will see the matching
    ``fix_hint`` in the Diagnostic stream so the placeholder stays
    visually clean.
    """
    if not triage:
        return ""
    short = triage.get("human_message")
    if short:
        prefix = f"{chart_type}: " if chart_type else ""
        text = f"{prefix}{short}"
    else:
        text = triage.get("exception_message") or ""
    if len(text) > 140:
        text = text[:137] + "..."
    return text


def _empty_placeholder_option(
    reason: Any,
    chart_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Minimal ECharts option used as a fallback when a chart's spec
    cannot be lowered to a real option (missing column, build error,
    etc.). The placeholder renders as a graphic-text annotation inside
    the otherwise-empty chart card, so the dashboard still loads and
    PRISM can see exactly which tile failed.

    ``reason`` accepts:
        - a ``BaseException`` (preferred): translated via
          :func:`_translate_builder_exception` so the subtext shows a
          plain-English ``human_message`` instead of "unhashable type:
          'list'" and similar Python tracebacks.
        - a string (legacy): rendered as-is, truncated to 140 chars.
    """
    if isinstance(reason, BaseException):
        triage = _translate_builder_exception(reason)
        subtext = _format_placeholder_subtext(triage, chart_type=chart_type)
    elif isinstance(reason, dict):
        subtext = _format_placeholder_subtext(reason, chart_type=chart_type)
    else:
        text = str(reason) if reason else ""
        subtext = text[:137] + "..." if len(text) > 140 else text
    return {
        "title": {"text": "(no data)", "left": "center", "top": "middle",
                   "textStyle": {"fontSize": 12, "fontWeight": "normal",
                                   "color": "#999"},
                   "subtext": subtext,
                   "subtextStyle": {"fontSize": 10, "color": "#bbb"}},
        "xAxis": {"show": False},
        "yAxis": {"show": False},
        "series": [],
    }


def _resolve_chart_specs(manifest: Dict[str, Any],
                          base_dir: Optional[Path],
                          diags: Optional[List["Diagnostic"]] = None
                          ) -> Dict[str, Dict[str, Any]]:
    """Resolve every chart widget in the manifest into an ECharts option dict.

    Resolution order per widget (first match wins):

        1. spec={...}       high-level -> lowered via builder dispatch
        2. option={...}     inline raw option
        3. option_inline    legacy alias for option
        4. ref="..."        load JSON from base_dir / ref or cwd / ref

    Widgets that don't match any of these are left with an empty series dict
    so the renderer still produces a card (blank chart) instead of failing.

    Per-chart resilience: when a spec fails to lower (missing columns,
    bad chart_type, etc.) we capture the failure as a Diagnostic into
    ``diags`` (when provided) and substitute a placeholder option so
    sibling charts still compile. PRISM-iteration callers should pass
    ``diags=[]`` and surface the accumulated list to the LLM.
    """
    specs: Dict[str, Dict[str, Any]] = {}
    datasets = manifest.get("datasets", {}) or {}
    manifest_theme = manifest.get("theme", "gs_clean")
    manifest_palette = manifest.get("palette")

    def _suppress_chart_title_if_widget_has_one(w, opt):
        """When the widget has its own title rendered in the tile
        header, clear the internal ECharts title to avoid the double
        "ACME daily OHLC / ACME daily OHLC" headline.

        Reaches the spec-built option (always blank title now that
        spec.title is rejected) and the raw ``option`` / ``ref`` /
        ``option_inline`` passthrough paths (which can still carry a
        title from hand-crafted ECharts options).
        """
        if not isinstance(opt, dict):
            return opt
        if not w.get("title"):
            return opt
        title = opt.get("title")
        if isinstance(title, dict):
            title["text"] = ""
        return opt

    def _record_build_failure(wid: str, wpath: str, exc: BaseException,
                                spec: Dict[str, Any]) -> None:
        """Emit a chart_build_failed diagnostic with the translated
        triage payload merged into the context. Chart spec is read for
        chart_type / dataset / mapping so PRISM gets the full repair
        scope without re-walking the manifest.
        """
        if diags is None:
            return
        triage = _translate_builder_exception(exc)
        chart_type = spec.get("chart_type") if isinstance(spec, dict) else None
        ds_name = spec.get("dataset") if isinstance(spec, dict) else None
        mapping = (spec.get("mapping") if isinstance(spec, dict)
                    and isinstance(spec.get("mapping"), dict) else {}) or {}
        # Capture the column refs the builder was about to consume so
        # PRISM can see *which* columns are in scope when triaging.
        mapping_cols = sorted({c for _, c in _walk_column_refs(
            mapping, chart_type)})
        ctx: Dict[str, Any] = {
            "chart_type": chart_type,
            "dataset": ds_name,
            "mapping_columns": mapping_cols,
        }
        ctx.update(triage)
        # Tight, single-line message that always names the chart_type +
        # the human-readable failure mode (when known) before the raw
        # Python exception. PRISM iteration prompts can pattern-match
        # on the first segment ("<chart_type> chart 'wid' failed").
        human = triage.get("human_message")
        if human:
            msg = (f"{chart_type or 'chart'} chart '{wid}' failed: {human} "
                    f"({triage['exception_type']}: "
                    f"{triage['exception_message']}).")
        else:
            msg = (f"{chart_type or 'chart'} chart '{wid}' failed "
                    f"({triage['exception_type']}: "
                    f"{triage['exception_message']}).")
        diags.append(Diagnostic(
            severity="error", code="chart_build_failed",
            widget_id=wid, path=f"{wpath}.spec",
            message=msg, context=ctx))

    def _existing_blocking_diag(wid: str) -> Optional["Diagnostic"]:
        """Return the first error-severity pre-build diagnostic already
        attached to this widget (if any). When ``chart_data_diagnostics``
        has flagged the widget, the build is guaranteed to crash with
        the same root cause -- skip the build to avoid emitting a
        redundant ``chart_build_failed`` next to the actionable
        diagnostic. The placeholder still renders, using the
        diagnostic's own ``human_message`` / ``message`` so the chart
        card and the diagnostic stream show the same triage text.
        """
        if not diags:
            return None
        for d in diags:
            if (d.widget_id == wid
                    and d.severity == "error"
                    and d.code != "chart_build_failed"):
                return d
        return None

    def visit(rows, path_prefix: str):
        for ri, row in enumerate(rows or []):
            for wi, w in enumerate(row):
                if w.get("widget") != "chart":
                    continue
                wid = w.get("id")
                if not wid:
                    continue
                wpath = f"{path_prefix}[{ri}][{wi}]"
                if isinstance(w.get("spec"), dict):
                    spec = w["spec"]
                    chart_type = spec.get("chart_type")
                    pre_blocking = _existing_blocking_diag(wid)
                    if pre_blocking is not None:
                        # Pre-build diagnostic already triaged this
                        # widget. Skip the build entirely; it would
                        # crash for the same reason and add a noisy
                        # second diagnostic.
                        triage_payload = dict(pre_blocking.context or {})
                        # Prefer a tight subtext: the explicit
                        # ``human_message`` if present, otherwise the
                        # full diagnostic message (already concise).
                        if "human_message" not in triage_payload:
                            triage_payload["human_message"] = (
                                pre_blocking.message
                            )
                        specs[wid] = _empty_placeholder_option(
                            triage_payload, chart_type=chart_type)
                        continue
                    try:
                        opt = _spec_to_option(
                            spec, datasets,
                            manifest_theme, manifest_palette,
                        )
                        specs[wid] = _suppress_chart_title_if_widget_has_one(
                            w, opt)
                    except (ValueError, TypeError, KeyError) as e:
                        _record_build_failure(wid, wpath, e, spec)
                        specs[wid] = _empty_placeholder_option(
                            e, chart_type=chart_type)
                    except Exception as e:  # noqa: BLE001
                        _record_build_failure(wid, wpath, e, spec)
                        specs[wid] = _empty_placeholder_option(
                            e, chart_type=chart_type)
                    continue
                if isinstance(w.get("option"), dict):
                    specs[wid] = _suppress_chart_title_if_widget_has_one(
                        w, w["option"]
                    )
                    continue
                if isinstance(w.get("option_inline"), dict):
                    specs[wid] = _suppress_chart_title_if_widget_has_one(
                        w, w["option_inline"]
                    )
                    continue
                ref = w.get("ref")
                if ref and base_dir:
                    candidate = (Path(base_dir) / ref)
                    if candidate.is_file():
                        specs[wid] = _suppress_chart_title_if_widget_has_one(
                            w,
                            json.loads(candidate.read_text(encoding="utf-8"))
                        )
                        continue
                if ref and Path(ref).is_file():
                    specs[wid] = _suppress_chart_title_if_widget_has_one(
                        w,
                        json.loads(Path(ref).read_text(encoding="utf-8"))
                    )

    layout = manifest.get("layout", {}) or {}
    if layout.get("kind") == "tabs":
        for ti, tab in enumerate(layout.get("tabs", []) or []):
            visit(tab.get("rows", []),
                  f"layout.tabs[{ti}].rows")
    else:
        visit(layout.get("rows", []), "layout.rows")
    return specs


# =============================================================================
# DATA DIAGNOSTICS
#
# Programmatic detection of chart/table/kpi widgets that will render as
# blank or broken because of empty datasets, missing columns, all-NaN
# series, etc. These are NOT validation errors -- the manifest is
# structurally valid, but the *data* won't produce a meaningful chart.
#
# Diagnostics are accumulated per widget so PRISM can see ALL data
# problems in one compile cycle (instead of fixing one and re-compiling
# to discover the next). Severity is informational, not blocking:
# compile_dashboard still emits HTML, with broken charts replaced by an
# empty-state placeholder.
# =============================================================================

# -----------------------------------------------------------------------------
# Data budget thresholds.
#
# Size limits are deterministic guardrails -- a dashboard that embeds
# 250k rows or 26 MB of data is broken regardless of whether every
# chart spec validates. Warnings are advisory; errors block compilation
# under ``strict=True``. PRISM is expected to keep datasets under
# these limits via top-N filtering, reduced lookback, or a lazy-load
# drill-down pattern (see DATA_SHAPES.md "Data budget limits").
# -----------------------------------------------------------------------------

# Single-dataset row counts. Daily-2y = 500, daily-10y = 2500, daily-20y
# = 5000 -- the warn threshold lets normal dashboards through and
# catches obvious history-pre-loading. The error threshold catches
# universe-scale embedding (the 248k-row drill-down case).
DATASET_ROWS_WARN = 10_000
DATASET_ROWS_ERROR = 50_000

# Single-dataset serialised JSON bytes. 2 MB is the cliff above which
# browser parse + render starts to feel sluggish even on a fast
# machine. 1 MB is the soft warning.
DATASET_BYTES_WARN = 1_048_576       # 1 MB
DATASET_BYTES_ERROR = 2_097_152      # 2 MB

# Total manifest serialised bytes. The HTML payload roughly tracks
# this; 5 MB+ HTML files take 1-2 seconds just to parse.
MANIFEST_BYTES_WARN = 3_145_728      # 3 MB
MANIFEST_BYTES_ERROR = 5_242_880     # 5 MB

# Table widget row counts. The table widget renders every row into the
# DOM regardless of `max_rows` (which only limits the visible
# viewport), so very large tables are slow to interact with.
TABLE_ROWS_WARN = 1_000
TABLE_ROWS_ERROR = 5_000

# -----------------------------------------------------------------------------
# Always-blocking error codes.
#
# These diagnostic codes flag load-bearing data-shape mistakes where the
# rendered chart / KPI / table / filter is GUARANTEED to be broken
# (placeholder card, '--' tile, empty cell, no-op filter). compile_dashboard
# fails on any of these regardless of the ``strict`` flag because persisting
# such an artifact ships a known-broken dashboard.
#
# The opt-in ``strict=False`` iteration mode still applies to cosmetic /
# advisory diagnostics and to error codes outside this set, so the
# inner-loop "fix everything in one round-trip" model is preserved for
# diagnostics where a placeholder is acceptable feedback. Authors who
# discover a NEW always-blocking case (a code where ``strict=False`` would
# silently ship broken output) should add the code here, not gate it
# behind ``strict``.
# -----------------------------------------------------------------------------
ALWAYS_BLOCKING_ERROR_CODES: frozenset = frozenset({
    # Chart spec data-binding failures: chart renders the
    # ``(no data)`` placeholder card.
    "chart_mapping_column_missing",
    "chart_mapping_required_missing",
    "chart_mapping_column_all_nan",
    "chart_dataset_empty",
    "chart_build_failed",
    # KPI source failures: tile renders ``--``.
    "kpi_no_value_no_source",
    "kpi_value_is_placeholder",
    "kpi_source_malformed",
    "kpi_source_dataset_unknown",
    "kpi_source_aggregator_unknown",
    "kpi_source_column_missing",
    "kpi_source_no_numeric_values",
    # stat_grid source failures: cell renders ``--``.
    "stat_grid_source_unresolvable",
    # Table column failures: column header renders but cells are empty.
    "table_column_field_missing",
    # Filter failures: filter is a no-op (silently filters nothing).
    "filter_field_missing_in_target",
})

# Mapping keys whose values are dataset column references (string or
# list of strings). Anything not in this set is treated as a config
# flag (e.g. legend_position, x_log, humanize) and not column-checked.
_COLUMN_REF_KEYS = {
    "x", "y", "value", "color", "colour", "size",
    "source", "target", "weight", "name", "category",
    "low", "high", "open", "close", "date",
    "strokeDash", "id", "parent", "labels",
    "dims", "path", "series", "node",
    # bullet chart: x is current value, x_low/x_high are the range
    "x_low", "x_high", "color_by", "label",
    # scatter_studio + correlation_matrix mapping keys
    "columns", "order_by", "label_column",
    "x_columns", "y_columns", "color_columns", "size_columns",
    "x_default", "y_default", "color_default", "size_default",
    # waterfall: optional column whose truthy cells render as
    # full-height totals rather than incremental deltas
    "is_total",
    # fan_cone: per-band {lower, upper, label?} structures resolve via
    # a custom walk in _walk_column_refs (so we don't add 'lower' /
    # 'upper' / 'bands' to the universal ref-set; band column names
    # come out of the dict items in the fan_cone branch).
}

# Required mapping keys per chart_type. Mirrors the builder's own
# raise-on-missing logic in echart_studio.py; we surface it as a
# diagnostic up-front so PRISM gets the available-columns context
# without parsing a Python traceback.
_REQUIRED_MAPPING_KEYS: Dict[str, Tuple[str, ...]] = {
    "line": ("x", "y"),
    "multi_line": ("x", "y"),
    "bar": ("x", "y"),
    "bar_horizontal": ("x", "y"),
    "scatter": ("x", "y"),
    "scatter_multi": ("x", "y"),
    "scatter_studio": (),  # all author keys are optional (defaults derived)
    "area": ("x", "y"),
    "heatmap": ("x", "y", "value"),
    "correlation_matrix": ("columns",),
    "pie": ("category", "value"),
    "donut": ("category", "value"),
    "histogram": ("x",),
    # bullet chart is "rates-RV style": for each row, draw the (low,
    # high) range and put a marker at the current value. The required
    # mapping keys mirror :func:`echart_studio.build_bullet`.
    "bullet": ("y", "x", "x_low", "x_high"),
    "sankey": ("source", "target", "value"),
    "candlestick": ("x", "open", "high", "low", "close"),
    "calendar_heatmap": ("date", "value"),
    "funnel": ("category", "value"),
    "gauge": ("value",),
    "radar": ("category", "value"),
    "graph": ("source", "target"),
    "boxplot": ("x", "y"),
    "parallel_coords": ("dims",),
    "tree": ("name", "parent"),
    # treemap/sunburst accept either {path, value} or {name, parent, value};
    # require_any_of handled below in _check_chart_widget.
    "treemap": (),
    "sunburst": (),
    # Waterfall: the bar-style decomposition. Authors give a category
    # column and a value column (signed deltas); the optional `is_total`
    # column flags any rows that should be drawn as full-height totals
    # rather than incremental deltas.
    "waterfall": ("x", "y"),
    # Slope: two snapshots joined by sloped lines per category.
    # `x` is the snapshot column (must have exactly two distinct
    # categorical values), `y` is the numeric value column, `color`
    # is the per-line category column.
    "slope": ("x", "y", "color"),
    # Fan / cone: a forecast ribbon. `x` is the time column, `y` is the
    # central path. `bands` is a list of {lower, upper, label?} pairs
    # (additional column names) layered as shaded bands. `bands` is
    # required (a fan with no band degenerates to a line).
    "fan_cone": ("x", "y", "bands"),
    # Marimekko: 2D categorical mosaic. `x` is the column-axis category,
    # `y` is the row-axis category, `value` is the cell magnitude.
    "marimekko": ("x", "y", "value"),
}

# chart_types whose required mapping is "either A-set OR B-set"
# (rather than a single hardcoded list). Each entry is a list of valid
# alternatives, where each alternative is itself a tuple of required
# keys. The diagnostic fires only when none of the alternatives are
# satisfied, with the union of required keys cited as context.
_REQUIRED_MAPPING_KEYS_ANY_OF: Dict[str, List[Tuple[str, ...]]] = {
    "treemap":  [("path", "value"), ("name", "parent", "value")],
    "sunburst": [("path", "value"), ("name", "parent", "value")],
}

# Mapping keys whose referenced column should be numeric, per chart_type.
# This used to be a single global set, but several chart_types put
# categorical data on what's traditionally a "numeric" axis -- e.g.
# bar_horizontal puts the category labels on `y` and the bar lengths
# on `x`; heatmap puts categories on both axes and the magnitude on
# `value`. The old global rule fired false-positive
# `chart_mapping_column_non_numeric` errors on these and blocked
# strict-mode compile of perfectly valid manifests. We now resolve
# the numeric mapping keys per chart_type via :func:`_numeric_keys_for`.

# Default rule for the majority of chart_types: y / value-shaped keys
# are numeric, x / category-shaped keys are not. Used as the fallback
# when a chart_type isn't in the override table below.
_NUMERIC_KEYS_DEFAULT: frozenset = frozenset({
    "y", "value", "size", "weight", "low", "high", "open", "close",
})

# Per-chart-type overrides. The set is the FULL list of numeric mapping
# keys for that chart_type (not additive over the default). Chart_types
# that match the default don't appear here.
_NUMERIC_KEYS_BY_CHART_TYPE: Dict[str, frozenset] = {
    # Horizontal bar: bar length is x, the category label is y
    "bar_horizontal": frozenset({"x", "size", "weight"}),
    # Heatmap: x and y are categorical buckets; value is the
    # magnitude shown via color. Same goes for correlation_matrix
    # (which is a heatmap of NxN correlation coefficients).
    "heatmap": frozenset({"value", "size", "weight"}),
    "correlation_matrix": frozenset({"value", "size", "weight"}),
    # Calendar heatmap: date and value; category-style date isn't
    # numeric but we don't enforce date-ness here.
    "calendar_heatmap": frozenset({"value"}),
    # Pie/donut/funnel/radar: the category is a label, value is
    # numeric.
    "pie":    frozenset({"value", "size", "weight"}),
    "donut":  frozenset({"value", "size", "weight"}),
    "funnel": frozenset({"value", "size", "weight"}),
    "radar":  frozenset({"value", "size", "weight"}),
    # Tree / treemap / sunburst: hierarchy is name+parent (categorical),
    # value is numeric.
    "tree":     frozenset({"value", "size", "weight"}),
    "treemap":  frozenset({"value", "size", "weight"}),
    "sunburst": frozenset({"value", "size", "weight"}),
    # Sankey: source and target are node labels; value is the flow
    # magnitude.
    "sankey": frozenset({"value", "size", "weight"}),
    # Graph: source and target are node ids; weight is the edge weight.
    "graph": frozenset({"value", "weight", "size"}),
    # Gauge: a single number on a scale.
    "gauge":  frozenset({"value", "low", "high"}),
    # Bullet (rates-RV style): x is the current value, x_low / x_high
    # the range bounds. y is the categorical row label (NOT numeric).
    "bullet": frozenset({"x", "x_low", "x_high", "value"}),
    # Histogram: x is binned, may or may not be numeric (we accept
    # both).
    "histogram": frozenset({"y", "value", "size", "weight"}),
    # Scatter studio: arbitrary column picker, every offered column
    # must be numeric. correlation_matrix uses the same `columns` key.
    "scatter_studio": frozenset({
        "columns", "x_columns", "y_columns", "size_columns",
        "x_default", "y_default", "size_default",
        "x", "y", "value", "size", "weight",
    }),
    # parallel_coords: dims is the list of dimension columns, all
    # numeric.
    "parallel_coords": frozenset({"dims", "value"}),
    # Waterfall: y is numeric (signed delta or total); x is category.
    "waterfall": frozenset({"y", "value", "size"}),
    # Slope: y is numeric; x is the snapshot label, color is the
    # per-line category.
    "slope": frozenset({"y", "value", "size"}),
    # Fan / cone: y is numeric central path; bands carry numeric pairs.
    # The validator only checks `y` here (band column-existence checks
    # run inside the builder's required-mapping logic via _walk_column_refs).
    "fan_cone": frozenset({"y", "value", "size"}),
    # Marimekko: value is numeric magnitude; x and y are categorical.
    "marimekko": frozenset({"value", "size", "weight"}),
}


def _numeric_keys_for(chart_type: Optional[str]) -> frozenset:
    """Return the set of mapping keys that must reference a numeric
    column for ``chart_type``. Falls back to the default ``y/value``
    set when the chart_type isn't in the override table."""
    if chart_type and chart_type in _NUMERIC_KEYS_BY_CHART_TYPE:
        return _NUMERIC_KEYS_BY_CHART_TYPE[chart_type]
    return _NUMERIC_KEYS_DEFAULT


@dataclass
class Diagnostic:
    """A structured chart-data finding from :func:`chart_data_diagnostics`.

    Designed to be both human- and LLM-readable. ``code`` is a stable
    short identifier; PRISM iteration prompts can pattern-match on
    ``code`` to fix specific failure modes. ``context`` carries the
    actionable data (e.g. ``available_columns``) needed to repair the
    manifest without another inspection round-trip.
    """
    severity: str           # "error" | "warning" | "info"
    code: str
    widget_id: Optional[str]
    path: str               # dotted manifest path, e.g. layout.rows[0][0]
    message: str
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity, "code": self.code,
            "widget_id": self.widget_id, "path": self.path,
            "message": self.message, "context": dict(self.context),
        }

    def __str__(self) -> str:
        """Single-line, dense, action-first rendering.

        Format::

            [severity] code [widget_id] @ path :: message | fix: <hint>

        ``fix_hint`` is the highest-leverage piece of context for an LLM
        iteration loop, so it's promoted out of the JSON context dump
        and rendered inline. The full structured context stays
        accessible via :meth:`to_dict` for callers that need it.
        """
        wid = f" [{self.widget_id}]" if self.widget_id else ""
        head = (f"[{self.severity}] {self.code}{wid} @ {self.path} :: "
                f"{self.message}")
        hint = (self.context or {}).get("fix_hint")
        if hint:
            return f"{head} | fix: {hint}"
        return head

    def format_verbose(self) -> str:
        """Multi-line rendering that includes the structured context.

        Useful for human-facing CLI output where vertical space is
        cheap. ``__str__`` stays single-line so log streams,
        ``warnings`` lists, and grep workflows remain compact.
        """
        lines = [str(self)]
        ctx = dict(self.context or {})
        ctx.pop("fix_hint", None)  # already inline in __str__
        if ctx:
            try:
                rendered = json.dumps(ctx, default=str, indent=2,
                                       sort_keys=True)
                for ln in rendered.splitlines():
                    lines.append(f"    {ln}")
            except (TypeError, ValueError):
                lines.append(f"    {ctx!r}")
        return "\n".join(lines)


def _series_is_numeric(ser) -> bool:
    """True iff a pandas Series can be coerced to numeric without
    every value going NaN. Strings like '1.23' count as numeric."""
    import pandas as pd
    if ser is None or len(ser) == 0:
        return False
    if pd.api.types.is_numeric_dtype(ser):
        return True
    coerced = pd.to_numeric(ser, errors="coerce")
    return coerced.notna().any()


def _all_nan(ser) -> bool:
    """True iff every value in the series is null / NaN / None."""
    import pandas as pd
    if ser is None:
        return True
    if len(ser) == 0:
        return True
    return bool(pd.isna(ser).all())


def _nan_fraction(ser) -> float:
    """Fraction (0..1) of NaN/None in the series."""
    import pandas as pd
    if ser is None or len(ser) == 0:
        return 1.0
    return float(pd.isna(ser).mean())


# -----------------------------------------------------------------------------
# Cell-type hygiene + builder exception translator.
#
# Two deeply related concerns the diagnostic system used to handle
# inconsistently:
#
# 1. *Before* building a chart we want to spot data hygiene problems
#    that the validator can't see (e.g. a column whose cells are
#    Python lists). The chart builders use those cells as dict keys
#    (heatmap, radar, graph categories, sankey nodes, etc.); any
#    unhashable cell crashes the builder with a cryptic stub like
#    "unhashable type: 'list'".
#
# 2. *After* a builder still raises -- because we couldn't anticipate
#    every edge case -- the placeholder text + diagnostic message
#    should translate the cryptic Python exception into something
#    PRISM can act on without reading a traceback.
#
# Both layers share a single source of truth: the translation table
# below names the cryptic substring, the human-readable replacement,
# and the actionable fix hint, so the diagnostic stream and the
# rendered placeholder card always show the same text.
# -----------------------------------------------------------------------------

_UNHASHABLE_CELL_TYPES: Tuple[type, ...] = (
    list, dict, set, frozenset, bytearray,
)


def _sample_repr(value: Any, max_len: int = 60) -> str:
    """Compact, repr-safe rendering of a sample cell for diagnostics."""
    try:
        s = repr(value)
    except Exception:  # noqa: BLE001
        s = f"<{type(value).__name__}>"
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def _detect_unhashable_cells(ser, sample_size: int = 200
                              ) -> Tuple[bool, List[str], str, int, int]:
    """Inspect a series for unhashable / non-scalar cells.

    Returns ``(has_unhashable, sample_reprs, dominant_type_name,
    bad_count, sampled_count)`` -- all five values populated even when
    nothing problematic is found (so the caller can include the
    sample-size context in any diagnostic).

    Only object-dtype series are scanned: numeric/datetime dtypes can't
    contain a Python list cell. The first ``sample_size`` non-null
    cells are inspected; the dominant type name is the most common
    offender so per-chart-type fix hints can be precise (e.g. "list-
    valued cells" vs "dict-valued cells").
    """
    import pandas as pd
    if ser is None or len(ser) == 0:
        return False, [], "", 0, 0
    if pd.api.types.is_numeric_dtype(ser):
        return False, [], "", 0, 0
    if pd.api.types.is_datetime64_any_dtype(ser):
        return False, [], "", 0, 0
    bad: List[Any] = []
    type_counts: Dict[str, int] = {}
    n_seen = 0
    for v in ser.dropna():
        if n_seen >= sample_size:
            break
        n_seen += 1
        if isinstance(v, _UNHASHABLE_CELL_TYPES):
            bad.append(v)
            tn = type(v).__name__
            type_counts[tn] = type_counts.get(tn, 0) + 1
    if not bad:
        return False, [], "", 0, n_seen
    dominant = max(type_counts, key=lambda k: type_counts[k])
    samples = [_sample_repr(b) for b in bad[:3]]
    return True, samples, dominant, len(bad), n_seen


# Translation table: each entry maps a substring of an exception's
# stringified message to a structured triage payload. Order matters --
# the first matching needle wins -- so put more specific patterns
# above more general ones.
#
# When PRISM sees "(no data) unhashable type: 'list'" in a chart card,
# the human_message replaces that subtext with something it can act on
# in the iteration loop ("category column has list-valued cells"); the
# fix_hint goes into Diagnostic.context["fix_hint"] so the same advice
# is one click away in the diagnostics stream. Updating this table
# automatically updates BOTH surfaces.
_BUILDER_EXCEPTION_TRANSLATIONS: List[Tuple[str, Dict[str, str]]] = [
    # Unhashable cell types ------------------------------------------------
    ("unhashable type: 'list'", {
        "human_message": "category column has list-valued cells",
        "fix_hint": (
            "A mapping column used as a category / group / node key "
            "(e.g. heatmap x/y, pie/radar/graph category, sankey "
            "source/target) has list-valued cells -- Python can't hash "
            "a list. Explode the column upstream "
            "(df.explode(col)) so each row carries one scalar, or "
            "aggregate (df[col].apply(','.join)) before charting."
        ),
    }),
    ("unhashable type: 'dict'", {
        "human_message": "category column has dict-valued cells",
        "fix_hint": (
            "A mapping column has dict-valued cells. Flatten the dicts "
            "(pd.json_normalize) and pick the scalar field that "
            "actually identifies the category before charting."
        ),
    }),
    ("unhashable type: 'set'", {
        "human_message": "category column has set-valued cells",
        "fix_hint": (
            "A mapping column has set-valued cells. Convert each cell "
            "to frozenset(sorted(s)) for stable hashing or to a "
            "comma-joined string before charting."
        ),
    }),
    ("unhashable type: 'bytearray'", {
        "human_message": "category column has bytearray cells",
        "fix_hint": (
            "Decode the bytearrays to str (.decode('utf-8')) or to "
            "bytes upstream before charting -- bytearray is the only "
            "bytes-like type Python won't hash."
        ),
    }),
    # Pandas list-cell-comparison fallout ---------------------------------
    ("Lengths must match to compare", {
        "human_message": "color/group column has list-valued cells",
        "fix_hint": (
            "A column referenced by mapping.color / mapping.series / "
            "mapping.strokeDash has list-valued cells. The builder "
            "filters rows per group with `df[df[col] == value]`, which "
            "pandas refuses on list cells. Explode the column "
            "(df.explode(col)) or pick a scalar grouping key."
        ),
    }),
    # Numeric coercion fallout --------------------------------------------
    ("could not convert string to float", {
        "human_message": "numeric column has non-numeric strings",
        "fix_hint": (
            "A column referenced by mapping.value / mapping.y holds "
            "non-numeric strings. Coerce upstream with "
            "pd.to_numeric(col, errors='coerce') and drop / fill the "
            "resulting NaNs, or repoint the mapping at a numeric column."
        ),
    }),
    ("Cannot convert non-finite values", {
        "human_message": "numeric column has NaN / inf where finite required",
        "fix_hint": (
            "The chart needs finite numeric values (no NaN, no Inf). "
            "Drop or fill the offending rows upstream "
            "(df = df.replace([np.inf, -np.inf], np.nan).dropna(...))."
        ),
    }),
    # Mapping-shape mistakes ----------------------------------------------
    ("mapping references columns not present in df", {
        "human_message": "mapping references column(s) not in dataset",
        "fix_hint": (
            "Check spec.mapping.* values against dataset columns. "
            "Common mistakes: passing a column name to a key that "
            "expects a list (e.g. mapping.path must be a list of "
            "column names, not a single string)."
        ),
    }),
]


def _translate_builder_exception(exc: BaseException) -> Dict[str, Any]:
    """Map a builder-thrown exception to a structured triage dict.

    Always returns ``exception_type`` and ``exception_message``; when
    the message matches a known cryptic pattern in
    :data:`_BUILDER_EXCEPTION_TRANSLATIONS` also returns
    ``human_message`` (short, placeholder-friendly) and ``fix_hint``
    (longer, diagnostic-friendly).

    Used by :func:`_record_build_failure` (pre-build diagnostic
    stream) and :func:`_empty_placeholder_option` (post-build chart
    card subtext) so the user sees the same actionable text in both
    places.
    """
    raw = str(exc)
    out: Dict[str, Any] = {
        "exception_type": type(exc).__name__,
        "exception_message": raw,
    }
    for needle, payload in _BUILDER_EXCEPTION_TRANSLATIONS:
        if needle in raw:
            out["human_message"] = payload["human_message"]
            out["fix_hint"] = payload["fix_hint"]
            break
    return out


# Per-chart-type EXCLUSIONS from the column-ref check. The default
# universe of column-ref keys is :data:`_COLUMN_REF_KEYS` -- broad
# enough to cover most chart types. Some chart types repurpose certain
# keys as labels / config (e.g. gauge.mapping.name is the gauge title,
# not a column). Keys listed here for a chart_type are NOT treated as
# column references when the validator walks that chart's mapping.
_NON_COLUMN_REF_KEYS_BY_CHART_TYPE: Dict[str, frozenset] = {
    # gauge: 'name' is the gauge label rendered inside the dial.
    # 'value' may be a literal number or a column.
    "gauge": frozenset({"name"}),
    # bullet: 'name' (when used) is a label, not a column.
    "bullet": frozenset({"name"}),
    # radar: 'name' is the radar series legend label, not a column.
    "radar": frozenset({"name"}),
}


def _walk_column_refs(
    mapping: Dict[str, Any],
    chart_type: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Return [(mapping_key, column_name), ...] for every column-reference
    in a chart mapping. Handles both string values and list-of-string
    values. Skips non-string non-list values (those are config flags).

    ``chart_type`` is consulted to filter out keys that are NOT column
    references for that chart_type even though they appear in the
    universal :data:`_COLUMN_REF_KEYS` set (e.g. ``gauge.mapping.name``
    is a label, not a column). Defaults to the full set when
    ``chart_type`` is None or unknown.
    """
    out: List[Tuple[str, str]] = []
    excluded = _NON_COLUMN_REF_KEYS_BY_CHART_TYPE.get(
        chart_type or "", frozenset()
    )
    for k, v in (mapping or {}).items():
        if k not in _COLUMN_REF_KEYS:
            continue
        if k in excluded:
            continue
        if isinstance(v, str):
            out.append((k, v))
        elif isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, str):
                    out.append((k, item))

    # fan_cone special case: 'bands' is a list of {lower, upper, label?}
    # dicts where 'lower' and 'upper' name dataset columns. We surface
    # those as column references so they get the standard column-existence
    # / NaN / numericity checks.
    if chart_type == "fan_cone":
        bands = (mapping or {}).get("bands")
        if isinstance(bands, (list, tuple)):
            for band in bands:
                if not isinstance(band, dict):
                    continue
                lo = band.get("lower")
                hi = band.get("upper")
                if isinstance(lo, str):
                    out.append(("lower", lo))
                if isinstance(hi, str):
                    out.append(("upper", hi))
    return out


def _did_you_mean(target: str, candidates: List[Any],
                    n: int = 3, cutoff: float = 0.6) -> List[str]:
    """Return up to ``n`` close-match suggestions for ``target`` from
    ``candidates``. Used to add typo hints to column-missing diagnostics
    so PRISM gets actionable repair guidance (e.g. ``us_2y`` -> ``usd_2y``)
    rather than just the available-columns dump.

    Includes a case-insensitive pass before falling back to difflib so
    'date' -> 'Date' and 'us_2y' -> 'US_2Y' still match even when the
    edit distance is large. Returns empty list when nothing close enough.

    Non-string candidates (e.g. MultiIndex column tuples) are filtered
    out before comparison so a malformed dataset doesn't crash the
    diagnostic emitter -- the dedicated shape diagnostic
    ``dataset_columns_multiindex`` already names that mistake.
    """
    if not target or not candidates:
        return []
    str_candidates = [c for c in candidates if isinstance(c, str)]
    if not str_candidates:
        return []
    target_lc = target.lower()
    case_hits = [c for c in str_candidates if c.lower() == target_lc]
    if case_hits:
        return case_hits[:n]
    return difflib.get_close_matches(target, str_candidates,
                                      n=n, cutoff=cutoff)


def _suggest_for_missing_column(
    column: str, available: List[str]
) -> Dict[str, Any]:
    """Bundle the ``did_you_mean`` + ``fix_hint`` keys for a missing-column
    diagnostic context. Returned dict can be merged into the existing
    context. Empty when no close match found -- caller still gets the
    available_columns list either way.
    """
    suggestions = _did_you_mean(column, list(available))
    out: Dict[str, Any] = {}
    if suggestions:
        out["did_you_mean"] = suggestions
        if len(suggestions) == 1:
            out["fix_hint"] = (
                f"Did you mean '{suggestions[0]}'? Replace '{column}' "
                f"with '{suggestions[0]}' (case/spelling)."
            )
        else:
            opts = " | ".join(f"'{s}'" for s in suggestions)
            out["fix_hint"] = (
                f"Closest matches: {opts}. Replace '{column}' with one "
                f"of these or pick from available_columns."
            )
    else:
        out["fix_hint"] = (
            f"'{column}' is not present. Pick a column from "
            f"available_columns, or repopulate the dataset to include it."
        )
    return out


def _materialize_datasets(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Build ``{dataset_name: pandas.DataFrame}`` once for diagnostic
    checks. Accepts every dataset shape that ``_normalize_manifest_datasets``
    normalises (DataFrame shorthand, list shorthand, ``{"source": ...}``
    wrapper) so callers can run diagnostics on raw PRISM-style manifests
    without pre-normalising.

    Datasets that fail to materialise (malformed source) yield an empty
    DataFrame; that empty state is flagged via ``chart_dataset_empty``
    only if a chart actually consumes the dataset.

    Pandas emits a noisy ``UserWarning`` when ``pd.to_datetime`` falls
    back to ``dateutil`` on string columns inside _source_to_dataframe.
    Silenced here so a diagnostics-only pass doesn't double-print
    warnings already surfaced during the render pipeline.
    """
    import pandas as pd
    import warnings
    datasets = manifest.get("datasets") or {}
    out: Dict[str, Any] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        for name, entry in datasets.items():
            try:
                if _is_dataframe(entry):
                    out[name] = entry
                elif isinstance(entry, list):
                    out[name] = _source_to_dataframe(entry)
                elif isinstance(entry, dict):
                    src = entry.get("source")
                    if _is_dataframe(src):
                        out[name] = src
                    else:
                        out[name] = _source_to_dataframe(src)
                else:
                    out[name] = pd.DataFrame()
            except (TypeError, ValueError):
                out[name] = pd.DataFrame()
    return out


# Chart types that interpret `value` as a slice / portion. Negative
# values silently render as 0 or as confusing reverse arcs / inverted
# blocks. Whitelisted explicitly so we don't false-positive on
# scatter/bar/line where negative values are legitimate.
_PORTION_CHART_TYPES = {"pie", "donut", "funnel", "sunburst", "treemap"}

# Chart types where a constant numeric y produces a degenerate flat
# line / single-bar-cluster -- worth surfacing because PRISM should
# either pick a different chart_type or apply a transformation.
_SERIES_CHART_TYPES = {"line", "multi_line", "area", "bar",
                         "bar_horizontal", "scatter", "scatter_multi",
                         "waterfall", "slope", "fan_cone", "marimekko"}


def _check_chart_widget(w: Dict[str, Any], path: str,
                          dfs: Dict[str, Any]) -> List[Diagnostic]:
    """All chart-widget data checks. Idempotent, no side effects."""
    out: List[Diagnostic] = []
    wid = w.get("id")
    spec = w.get("spec") if isinstance(w.get("spec"), dict) else None

    # Inline option / ref widgets bypass the spec pipeline -- their data
    # is already baked into the option JSON, so we can't usefully
    # introspect it from here. We don't emit diagnostics for those.
    if not spec:
        return out

    chart_type = spec.get("chart_type")
    ds_name = spec.get("dataset")
    mapping = spec.get("mapping") or {}

    # Dataset existence / emptiness ------------------------------------
    if ds_name and ds_name in dfs:
        df = dfs[ds_name]
        if df is None or len(df) == 0:
            out.append(Diagnostic(
                severity="error", code="chart_dataset_empty",
                widget_id=wid, path=f"{path}.spec.dataset",
                message=(f"chart '{wid}' references dataset '{ds_name}' "
                         f"which has 0 rows; chart will render blank."),
                context={"dataset": ds_name,
                           "available_datasets": sorted(dfs.keys()),
                           "fix_hint": (
                               "Repopulate the dataset before passing it "
                               "to the manifest -- check upstream loader, "
                               "filters, or join keys returning empty.")}))
            return out  # downstream column checks are noise on empty df
    elif ds_name:
        # Validator already flagged unknown datasets; skip duplicate.
        return out
    else:
        return out

    df = dfs[ds_name]
    available = list(df.columns)

    # Required mapping keys for this chart_type ------------------------
    required = _REQUIRED_MAPPING_KEYS.get(chart_type or "", ())
    for rk in required:
        if rk not in mapping or mapping[rk] in (None, "", [], ()):
            out.append(Diagnostic(
                severity="error", code="chart_mapping_required_missing",
                widget_id=wid, path=f"{path}.spec.mapping.{rk}",
                message=(f"chart_type '{chart_type}' requires "
                         f"mapping.{rk}; not provided."),
                context={"chart_type": chart_type, "missing_key": rk,
                           "required_keys": list(required),
                           "available_columns": available,
                           "fix_hint": (
                               f"Add 'mapping.{rk}' pointing to a column "
                               f"in available_columns. All required keys "
                               f"for chart_type='{chart_type}': "
                               f"{list(required)}.")}))

    # Either-or required-key sets (e.g. treemap/sunburst can be path+value
    # OR name+parent+value).
    any_of = _REQUIRED_MAPPING_KEYS_ANY_OF.get(chart_type or "")
    if any_of:
        def _has(keys):
            return all(
                k in mapping and mapping[k] not in (None, "", [], ())
                for k in keys
            )
        if not any(_has(alt) for alt in any_of):
            alt_repr = " | ".join(
                "{" + ",".join(alt) + "}" for alt in any_of
            )
            out.append(Diagnostic(
                severity="error",
                code="chart_mapping_required_missing",
                widget_id=wid, path=f"{path}.spec.mapping",
                message=(f"chart_type '{chart_type}' requires one of: "
                         + alt_repr + "; none provided."),
                context={"chart_type": chart_type,
                           "required_alternatives": [list(a) for a in any_of],
                           "available_columns": available,
                           "fix_hint": (
                               f"Pick ONE alternative and provide ALL its "
                               f"keys: {alt_repr}. Each key value must be "
                               f"a column in available_columns.")}))

    # Column existence / NaN coverage / numericity ---------------------
    refs = _walk_column_refs(mapping, chart_type)
    for key, col in refs:
        if col not in df.columns:
            ctx = {"mapping_key": key, "missing_column": col,
                    "dataset": ds_name,
                    "available_columns": available}
            ctx.update(_suggest_for_missing_column(col, available))
            out.append(Diagnostic(
                severity="error", code="chart_mapping_column_missing",
                widget_id=wid, path=f"{path}.spec.mapping.{key}",
                message=(f"mapping.{key}='{col}' is not a column in "
                         f"dataset '{ds_name}'."),
                context=ctx))
            continue
        ser = df[col]
        if _all_nan(ser):
            out.append(Diagnostic(
                severity="error", code="chart_mapping_column_all_nan",
                widget_id=wid, path=f"{path}.spec.mapping.{key}",
                message=(f"mapping.{key}='{col}' is all-NaN in dataset "
                         f"'{ds_name}'; chart will render blank."),
                context={"mapping_key": key, "column": col,
                           "dataset": ds_name, "row_count": len(df),
                           "fix_hint": (
                               "Repopulate the column upstream. Common "
                               "causes: API returning sentinels instead "
                               "of values, or a join missing rows.")}))
            continue
        nan_frac = _nan_fraction(ser)
        if nan_frac >= 0.5:
            out.append(Diagnostic(
                severity="warning",
                code="chart_mapping_column_mostly_nan",
                widget_id=wid, path=f"{path}.spec.mapping.{key}",
                message=(f"mapping.{key}='{col}' is "
                         f"{nan_frac*100:.0f}% NaN in dataset "
                         f"'{ds_name}'; chart may look empty."),
                context={"mapping_key": key, "column": col,
                           "dataset": ds_name,
                           "nan_fraction": round(nan_frac, 3),
                           "row_count": len(df)}))
        # Cell-type hygiene. Catches list/dict/set/frozenset/bytearray
        # cells -- the four scalar types Python's hash protocol rejects --
        # *before* they reach the builder. This is what stops the
        # "(no data) unhashable type: 'list'" placeholder bug: every
        # builder that uses the column as a dict key (heatmap.x_idx,
        # radar/graph categories, sankey nodes, ...) used to crash with
        # a cryptic TypeError; now we name the offending column, the
        # cell type, and the exact remediation pandas snippet.
        # Only fires on non-numeric mapping keys -- numeric keys get a
        # better diagnostic from the non-numeric check below.
        is_numeric_key = key in _numeric_keys_for(chart_type)
        if not is_numeric_key:
            has_bad, bad_samples, dom_type, bad_count, sampled = (
                _detect_unhashable_cells(ser)
            )
            if has_bad:
                if dom_type == "list":
                    fix_hint = (
                        f"Explode the column upstream "
                        f"(df.explode('{col}')) so each row carries "
                        f"one scalar, or aggregate to a string "
                        f"(df['{col}'] = "
                        f"df['{col}'].apply(','.join))."
                    )
                elif dom_type == "dict":
                    fix_hint = (
                        f"Flatten the dicts in '{col}' "
                        f"(pd.json_normalize) and pick the scalar "
                        f"field that identifies the category."
                    )
                else:
                    fix_hint = (
                        f"Convert each cell of '{col}' to a hashable "
                        f"scalar (str/int/...) before charting."
                    )
                out.append(Diagnostic(
                    severity="error",
                    code="chart_mapping_column_unhashable_cells",
                    widget_id=wid,
                    path=f"{path}.spec.mapping.{key}",
                    message=(
                        f"mapping.{key}='{col}' has {dom_type}-valued "
                        f"cells ({bad_count} of {sampled} sampled); "
                        f"chart_type '{chart_type}' uses this column "
                        f"as a category / group key, which requires "
                        f"hashable scalars."
                    ),
                    context={
                        "mapping_key": key, "column": col,
                        "dataset": ds_name, "chart_type": chart_type,
                        "cell_type": dom_type,
                        "bad_count": bad_count,
                        "sampled_count": sampled,
                        "sample_bad_values": bad_samples,
                        # Tight 1-line phrasing for the chart-card
                        # placeholder; the full message + fix_hint
                        # ride along in the Diagnostic stream.
                        "human_message": (
                            f"mapping.{key}='{col}' has "
                            f"{dom_type}-valued cells"
                        ),
                        "fix_hint": fix_hint,
                    }))
                continue  # skip non-numeric check; already triaged
        if (is_numeric_key
                and not _series_is_numeric(ser)):
            samples = [str(v) for v in ser.dropna().head(3).tolist()]
            out.append(Diagnostic(
                severity="error",
                code="chart_mapping_column_non_numeric",
                widget_id=wid, path=f"{path}.spec.mapping.{key}",
                message=(f"mapping.{key}='{col}' must be numeric for "
                         f"chart_type '{chart_type}'; column is "
                         f"non-numeric."),
                context={"mapping_key": key, "column": col,
                           "dataset": ds_name,
                           "chart_type": chart_type,
                           "sample_values": samples,
                           "fix_hint": (
                               f"Coerce '{col}' to numeric upstream "
                               f"(replace sentinels like {samples} with "
                               f"NaN, or remap to a numeric column).")}))

    # Single-row warning (most chart types degenerate at n=1) ----------
    if len(df) == 1 and chart_type in _SERIES_CHART_TYPES:
        out.append(Diagnostic(
            severity="warning", code="chart_dataset_single_row",
            widget_id=wid, path=f"{path}.spec.dataset",
            message=(f"chart '{wid}' has only 1 row in dataset "
                     f"'{ds_name}'; series-style charts need >=2."),
            context={"dataset": ds_name, "row_count": 1,
                       "fix_hint": (
                           "Add more rows to the dataset, or switch to a "
                           "single-value chart_type (kpi, gauge, bullet).")}))

    # Topology + degeneracy checks (run only when columns are present) -
    out.extend(_check_chart_degeneracy(wid, path, df, chart_type,
                                          mapping, ds_name))

    return out


def _check_chart_degeneracy(
    wid: Optional[str], path: str, df, chart_type: Optional[str],
    mapping: Dict[str, Any], ds_name: str,
) -> List[Diagnostic]:
    """Per-chart-type degeneracy checks: data is structurally fine
    (right columns, right types, not-all-NaN) but the *distribution*
    or *topology* makes the chart meaningless.

    Each check is gated on its mapping being valid (column exists,
    numeric where required) so we don't double-flag cases already
    raised upstream. Returns [] if every check passes.
    """
    import pandas as pd
    out: List[Diagnostic] = []
    if df is None or len(df) == 0 or not chart_type:
        return out

    def _col(key: str):
        v = mapping.get(key)
        if isinstance(v, str) and v in df.columns:
            return df[v], v
        return None, None

    # 1. Negative slice values for portion-style charts ----------------
    if chart_type in _PORTION_CHART_TYPES:
        ser, vname = _col("value")
        if ser is not None and _series_is_numeric(ser):
            coerced = pd.to_numeric(ser, errors="coerce")
            neg_mask = coerced < 0
            n_neg = int(neg_mask.sum())
            if n_neg > 0:
                samples = [
                    {"row": int(i), "value": float(coerced.iloc[i])}
                    for i in range(len(coerced))
                    if i < 5 and bool(neg_mask.iloc[i])
                ]
                out.append(Diagnostic(
                    severity="error",
                    code="chart_negative_values_in_portion",
                    widget_id=wid, path=f"{path}.spec.mapping.value",
                    message=(f"chart_type '{chart_type}' value column "
                             f"'{vname}' contains {n_neg} negative "
                             f"value(s); ECharts renders these as 0 or "
                             f"reversed arcs."),
                    context={
                        "chart_type": chart_type,
                        "column": vname, "dataset": ds_name,
                        "negative_count": n_neg, "row_count": len(df),
                        "negative_samples": samples,
                        "fix_hint": (
                            "Drop or absolute-value negative rows "
                            "before charting, or use a chart_type that "
                            "handles signed values (bar, bar_horizontal, "
                            "diverging colour palettes).")}))

    # 2. Constant numeric y for series charts --------------------------
    if chart_type in _SERIES_CHART_TYPES:
        for ykey in ("y",):
            v = mapping.get(ykey)
            cols = [v] if isinstance(v, str) else (
                list(v) if isinstance(v, (list, tuple)) else []
            )
            for ycol in cols:
                if not isinstance(ycol, str) or ycol not in df.columns:
                    continue
                ser = df[ycol]
                if not _series_is_numeric(ser):
                    continue
                coerced = pd.to_numeric(ser, errors="coerce").dropna()
                if len(coerced) < 2:
                    continue
                if coerced.nunique() == 1:
                    out.append(Diagnostic(
                        severity="warning",
                        code="chart_constant_values",
                        widget_id=wid,
                        path=f"{path}.spec.mapping.{ykey}",
                        message=(f"mapping.{ykey} column '{ycol}' has "
                                 f"a single unique value "
                                 f"({coerced.iloc[0]}) across "
                                 f"{len(coerced)} rows; chart will "
                                 f"render as a flat line."),
                        context={
                            "chart_type": chart_type, "column": ycol,
                            "dataset": ds_name,
                            "constant_value": float(coerced.iloc[0]),
                            "row_count": int(len(coerced)),
                            "fix_hint": (
                                "Pick a y column with variance, or "
                                "switch to a single-value chart_type "
                                "(kpi, gauge).")}))

    # 3. Sankey topology -- self-loops + disconnected ------------------
    if chart_type == "sankey":
        s_ser, sname = _col("source")
        t_ser, tname = _col("target")
        if s_ser is not None and t_ser is not None:
            n = len(df)
            self_loop_mask = (s_ser == t_ser)
            n_self = int(self_loop_mask.sum())
            if n_self > 0:
                pct = (n_self / n * 100) if n > 0 else 0.0
                samples = [
                    {"source": str(s_ser.iloc[i]),
                      "target": str(t_ser.iloc[i])}
                    for i in range(min(n, 5))
                    if bool(self_loop_mask.iloc[i])
                ]
                out.append(Diagnostic(
                    severity="error" if n_self == n else "warning",
                    code="chart_sankey_self_loops",
                    widget_id=wid, path=f"{path}.spec.mapping",
                    message=(f"sankey '{wid}' has {n_self}/{n} "
                             f"({pct:.0f}%) self-loop edges where "
                             f"source==target; sankey renders these as "
                             f"disconnected stubs."),
                    context={
                        "self_loop_count": n_self, "row_count": n,
                        "self_loop_pct": round(pct, 1),
                        "source_column": sname, "target_column": tname,
                        "samples": samples,
                        "fix_hint": (
                            "Filter rows where source!=target before "
                            "passing to the manifest, or model the data "
                            "as a graph (chart_type='graph').")}))
            sources = set(s_ser.dropna().astype(str).unique().tolist())
            targets = set(t_ser.dropna().astype(str).unique().tolist())
            if sources and targets and not (sources & targets):
                out.append(Diagnostic(
                    severity="warning",
                    code="chart_sankey_disconnected",
                    widget_id=wid, path=f"{path}.spec.mapping",
                    message=(f"sankey '{wid}' source/target sets share "
                             f"no nodes; the diagram is one bipartite "
                             f"step with no chained flow."),
                    context={
                        "source_unique": sorted(list(sources))[:8],
                        "target_unique": sorted(list(targets))[:8],
                        "fix_hint": (
                            "If you want a multi-step flow, the same "
                            "node names must appear on BOTH sides (a "
                            "target of step N becomes a source of step "
                            "N+1). For a one-step flow, this is fine -- "
                            "ignore the warning.")}))

    # 4. Candlestick OHLC inversion ------------------------------------
    if chart_type == "candlestick":
        o, _ = _col("open")
        h, _ = _col("high")
        l_ser, _ = _col("low")
        c, _ = _col("close")
        if all(s is not None for s in (o, h, l_ser, c)):
            o_n = pd.to_numeric(o, errors="coerce")
            h_n = pd.to_numeric(h, errors="coerce")
            l_n = pd.to_numeric(l_ser, errors="coerce")
            c_n = pd.to_numeric(c, errors="coerce")
            inv_hl = int((h_n < l_n).sum())
            inv_oh = int((o_n > h_n).sum())
            inv_ol = int((o_n < l_n).sum())
            inv_ch = int((c_n > h_n).sum())
            inv_cl = int((c_n < l_n).sum())
            problems = {"high<low": inv_hl, "open>high": inv_oh,
                          "open<low": inv_ol, "close>high": inv_ch,
                          "close<low": inv_cl}
            problems = {k: v for k, v in problems.items() if v > 0}
            if problems:
                out.append(Diagnostic(
                    severity="error",
                    code="chart_candlestick_inverted",
                    widget_id=wid, path=f"{path}.spec.mapping",
                    message=(f"candlestick '{wid}' has OHLC "
                             f"inversions: {problems}; ECharts will "
                             f"draw nonsense candles."),
                    context={
                        "row_count": len(df),
                        "inversions": problems,
                        "fix_hint": (
                            "Verify the open/high/low/close column "
                            "assignments; the most common cause is a "
                            "swap between mapping.high and mapping.low.")}))

    # 5. Tree orphan parents -------------------------------------------
    if chart_type == "tree":
        n_ser, nname = _col("name")
        p_ser, pname = _col("parent")
        if n_ser is not None and p_ser is not None:
            names_set = set(n_ser.dropna().astype(str).tolist())
            orphans: List[Tuple[int, str, str]] = []
            for i in range(len(p_ser)):
                p = p_ser.iloc[i]
                if p is None or (isinstance(p, float) and pd.isna(p)):
                    continue
                p_str = str(p)
                if p_str not in names_set:
                    orphans.append((i, str(n_ser.iloc[i]), p_str))
            if orphans:
                out.append(Diagnostic(
                    severity="error",
                    code="chart_tree_orphan_parents",
                    widget_id=wid, path=f"{path}.spec.mapping",
                    message=(f"tree '{wid}' has {len(orphans)} row(s) "
                             f"whose parent doesn't exist as a name; "
                             f"those nodes won't render."),
                    context={
                        "orphan_count": len(orphans),
                        "orphan_samples": [
                            {"row": r, "name": n, "parent": p}
                            for r, n, p in orphans[:5]
                        ],
                        "name_column": nname,
                        "parent_column": pname,
                        "fix_hint": (
                            "Every parent value must match a 'name' "
                            "value in the same dataset (the root row "
                            "uses null/None for its parent).")}))

    return out


def _check_table_widget(w: Dict[str, Any], path: str,
                          dfs: Dict[str, Any]) -> List[Diagnostic]:
    """Per-column field-existence + the all-columns-missing roll-up.

    When EVERY defined column is missing, the table will render a header
    row with empty cells -- worse than just one bad column. Flagged as
    a single `table_columns_all_missing` error so PRISM gets one
    actionable diagnostic instead of N near-identical ones.
    """
    out: List[Diagnostic] = []
    wid = w.get("id")
    ds_name = w.get("dataset_ref")
    if not ds_name or ds_name not in dfs:
        return out
    df = dfs[ds_name]
    if df is None or len(df) == 0:
        out.append(Diagnostic(
            severity="warning", code="table_dataset_empty",
            widget_id=wid, path=f"{path}.dataset_ref",
            message=(f"table '{wid}' references dataset '{ds_name}' "
                     f"which has 0 rows; table will render empty."),
            context={"dataset": ds_name,
                       "fix_hint": (
                           "Repopulate the dataset upstream, or filter "
                           "less aggressively before passing it to the "
                           "manifest.")}))
        return out

    cols = w.get("columns") or []
    if not isinstance(cols, list):
        return out
    available = list(df.columns)
    field_cols = [
        (ci, c.get("field"))
        for ci, c in enumerate(cols)
        if isinstance(c, dict) and c.get("field")
    ]
    missing_cols = [
        (ci, fld) for ci, fld in field_cols if fld not in df.columns
    ]
    # Aggregate roll-up first so it appears before the per-column noise
    if field_cols and len(missing_cols) == len(field_cols):
        out.append(Diagnostic(
            severity="error", code="table_columns_all_missing",
            widget_id=wid, path=f"{path}.columns",
            message=(f"table '{wid}' has {len(missing_cols)} defined "
                     f"columns and ALL of them are missing from dataset "
                     f"'{ds_name}'; the table will render an empty "
                     f"header row only."),
            context={
                "missing_columns": [fld for _, fld in missing_cols],
                "dataset": ds_name,
                "available_columns": available,
                "fix_hint": (
                    "Either redefine 'columns' to fields actually in "
                    "the dataset, or change 'dataset_ref' to a dataset "
                    "that has these columns.")}))
    for ci, fld in missing_cols:
        ctx = {"missing_column": fld, "dataset": ds_name,
                "available_columns": available}
        ctx.update(_suggest_for_missing_column(fld, available))
        out.append(Diagnostic(
            severity="error", code="table_column_field_missing",
            widget_id=wid, path=f"{path}.columns[{ci}].field",
            message=(f"table '{wid}' columns[{ci}].field='{fld}' is "
                     f"not a column in dataset '{ds_name}'."),
            context=ctx))
    return out


def _parse_kpi_source(
    src: str, kind: str
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Split a KPI / stat_grid source string into ``(ds, agg, col, error)``.

    ``kind`` selects the format expected by the JS runtime:

    * ``"value"`` (used by ``source`` / ``delta_source``) is
      ``dataset.aggregator.column`` -- exactly 3+ dot-separated parts.
      The column is the last segment and may contain dots itself.
      Mirrors ``resolveSource`` in rendering.py's dashboard JS.
    * ``"sparkline"`` (used by ``sparkline_source``) is
      ``dataset.column`` -- 2+ dot-separated parts. The column is the
      tail; no aggregator is applied (the sparkline plots all rows).

    On failure ``error`` is a short reason; on success it is None.
    """
    if not isinstance(src, str) or not src.strip():
        return None, None, None, "source must be a non-empty string"
    parts = src.split(".")
    if kind == "value":
        if len(parts) < 3:
            return None, None, None, (
                "value source needs 3+ parts "
                "'dataset.aggregator.column' "
                f"(got {len(parts)})"
            )
        return parts[0], parts[1], ".".join(parts[2:]), None
    if kind == "sparkline":
        if len(parts) < 2:
            return None, None, None, (
                "sparkline source needs 2+ parts "
                "'dataset.column' "
                f"(got {len(parts)})"
            )
        return parts[0], None, ".".join(parts[1:]), None
    raise ValueError(f"unknown kpi source kind: {kind}")


def _resolve_kpi_value(
    src: str, dfs: Dict[str, Any]
) -> Tuple[Optional[float], Optional[str]]:
    """Mirror of the JS ``resolveSource`` + ``resolveAgg``: return the
    numeric value the runtime would compute, or ``(None, reason)`` if
    the source cannot resolve.

    The JS runtime renders ``--`` whenever this would return None, so
    this is the single source of truth for the diagnostic check that
    decides whether a KPI tile will be broken in production.
    """
    ds_name, agg, col, err = _parse_kpi_source(src, "value")
    if err is not None:
        return None, err
    df = dfs.get(ds_name)
    if df is None:
        return None, f"dataset '{ds_name}' not declared"
    if col not in df.columns:
        return None, (f"column '{col}' not in dataset "
                       f"'{ds_name}'")
    if agg not in VALID_KPI_AGGREGATORS:
        return None, (f"aggregator '{agg}' not in "
                       f"{sorted(VALID_KPI_AGGREGATORS)}")
    import pandas as pd
    coerced = pd.to_numeric(df[col], errors="coerce")
    vals = coerced.dropna().tolist()
    if not vals:
        return None, (f"column '{col}' has no numeric values "
                       f"(after to_numeric coercion)")
    if agg == "latest":
        return float(vals[-1]), None
    if agg == "first":
        return float(vals[0]), None
    if agg == "sum":
        return float(sum(vals)), None
    if agg == "mean":
        return float(sum(vals) / len(vals)), None
    if agg == "min":
        return float(min(vals)), None
    if agg == "max":
        return float(max(vals)), None
    if agg == "count":
        return float(len(vals)), None
    if agg == "prev":
        return float(vals[-2] if len(vals) >= 2 else vals[-1]), None
    return None, f"aggregator '{agg}' has no implementation"


def _check_kpi_widget(w: Dict[str, Any], path: str,
                        dfs: Dict[str, Any]) -> List[Diagnostic]:
    """KPI source-binding diagnostics. A KPI tile renders ``--`` in the
    browser whenever ``value`` is missing AND ``source`` cannot resolve
    to a number. We flag every path that ends in ``--`` as an error
    severity diagnostic; that lets ``compile_dashboard(strict=True)``
    refuse to publish a dashboard with a broken headline number.

    Three independent sources can be set:

    * ``source`` (the displayed value) -- ``dataset.aggregator.column``
    * ``delta_source`` (vs-prev indicator) -- same format as ``source``
    * ``sparkline_source`` (inline mini-line) -- ``dataset.column``

    Failure modes covered:

    * Tile has neither ``value`` nor ``source`` -> ``kpi_no_value_no_source``
    * Source format is wrong shape -> ``kpi_source_malformed``
    * Source dataset is undeclared -> ``kpi_source_dataset_unknown``
    * Source column is not in dataset -> ``kpi_source_column_missing``
    * Source aggregator is unknown -> ``kpi_source_aggregator_unknown``
    * Source column has no numeric values -> ``kpi_source_no_numeric_values``
    * Source column is all-NaN -> ``kpi_source_no_numeric_values`` (subset)
    * Sparkline column has <2 numeric points -> ``kpi_sparkline_too_short``
    """
    import pandas as pd
    out: List[Diagnostic] = []
    wid = w.get("id")

    # ---- presence check: must have value OR source ------------------
    has_value = ("value" in w) and (w.get("value") is not None)
    has_source = bool(w.get("source"))
    if not has_value and not has_source:
        out.append(Diagnostic(
            severity="error", code="kpi_no_value_no_source",
            widget_id=wid, path=path,
            message=(f"kpi '{wid}' has neither 'value' nor 'source'; "
                     f"the tile will render '--' and the user will "
                     f"see a broken headline number."),
            context={"fix_hint": (
                "Set 'value' to a literal number (or string), or set "
                "'source' to 'dataset.aggregator.column' to pull the "
                "value from a dataset at runtime.")}))

    # ``value="--"`` (or any string sentinel) renders verbatim. Treat
    # the literal "--" sentinel as a hard error -- it's never what the
    # author wanted to display.
    if has_value and isinstance(w.get("value"), str) and \
            w["value"].strip() in ("--", "—", "n/a", "N/A"):
        out.append(Diagnostic(
            severity="error", code="kpi_value_is_placeholder",
            widget_id=wid, path=f"{path}.value",
            message=(f"kpi '{wid}' value={w['value']!r} is a "
                     f"placeholder string; the tile will literally "
                     f"display the placeholder."),
            context={"value": w["value"],
                       "fix_hint": (
                           "Pass a real number/string, or remove "
                           "'value' and bind 'source' instead.")}))

    # ---- per-source bind checks -------------------------------------
    # When ``value`` is set, the JS runtime uses it directly and skips
    # ``source`` resolution entirely (see ``renderKpis`` in
    # rendering.py). So a broken ``source`` on a KPI with an explicit
    # ``value`` is dead config -- we still validate ``delta_source``
    # and ``sparkline_source`` because those are independently
    # consumed regardless of ``value``.
    sources = [
        ("source", w.get("source"), "value"),
        ("delta_source", w.get("delta_source"), "value"),
        ("sparkline_source", w.get("sparkline_source"), "sparkline"),
    ]
    for key, src, kind in sources:
        if not src or not isinstance(src, str):
            continue
        # Skip the main ``source`` validation if ``value`` overrides it
        if key == "source" and has_value:
            continue

        ds_name, agg, col, parse_err = _parse_kpi_source(src, kind)
        if parse_err is not None:
            example = ("dataset.aggregator.column" if kind == "value"
                       else "dataset.column")
            out.append(Diagnostic(
                severity="error", code="kpi_source_malformed",
                widget_id=wid, path=f"{path}.{key}",
                message=(f"kpi '{wid}' {key}={src!r} is malformed: "
                         f"{parse_err}."),
                context={key: src, "expected_format": example,
                           "valid_aggregators": sorted(
                               VALID_KPI_AGGREGATORS),
                           "fix_hint": (
                               f"Rewrite as '{example}'.")}))
            continue

        if ds_name not in dfs:
            ds_suggestions = _did_you_mean(ds_name, sorted(dfs.keys()))
            ctx: Dict[str, Any] = {
                key: src, "dataset": ds_name,
                "available_datasets": sorted(dfs.keys()),
            }
            if ds_suggestions:
                ctx["did_you_mean"] = ds_suggestions
                ctx["fix_hint"] = (
                    f"Did you mean dataset '{ds_suggestions[0]}'? "
                    f"Replace '{ds_name}.' prefix or pick from "
                    f"available_datasets.")
            else:
                ctx["fix_hint"] = (
                    f"Declare dataset '{ds_name}' in manifest.datasets, "
                    f"or pick from available_datasets.")
            out.append(Diagnostic(
                severity="error", code="kpi_source_dataset_unknown",
                widget_id=wid, path=f"{path}.{key}",
                message=(f"kpi '{wid}' {key}={src!r} references "
                         f"unknown dataset '{ds_name}'."),
                context=ctx))
            continue

        df = dfs[ds_name]

        # value-format only: agg must be in the allow-list
        if kind == "value" and agg not in VALID_KPI_AGGREGATORS:
            agg_suggestions = _did_you_mean(
                agg, sorted(VALID_KPI_AGGREGATORS)
            )
            ctx = {key: src, "aggregator": agg,
                    "valid_aggregators": sorted(VALID_KPI_AGGREGATORS)}
            if agg_suggestions:
                ctx["did_you_mean"] = agg_suggestions
                ctx["fix_hint"] = (
                    f"Did you mean '{agg_suggestions[0]}'? "
                    f"Aggregator must be one of "
                    f"{sorted(VALID_KPI_AGGREGATORS)}.")
            else:
                ctx["fix_hint"] = (
                    f"Replace '{agg}' with one of "
                    f"{sorted(VALID_KPI_AGGREGATORS)}.")
            out.append(Diagnostic(
                severity="error", code="kpi_source_aggregator_unknown",
                widget_id=wid, path=f"{path}.{key}",
                message=(f"kpi '{wid}' {key}={src!r} uses unknown "
                         f"aggregator '{agg}'; the runtime will "
                         f"return null and the tile will render '--'."),
                context=ctx))
            continue

        if col not in df.columns:
            ctx = {key: src, "dataset": ds_name,
                    "missing_column": col,
                    "available_columns": list(df.columns)}
            ctx.update(_suggest_for_missing_column(
                col, list(df.columns)))
            out.append(Diagnostic(
                severity="error", code="kpi_source_column_missing",
                widget_id=wid, path=f"{path}.{key}",
                message=(f"kpi '{wid}' {key}={src!r} references "
                         f"column '{col}' which is not in dataset "
                         f"'{ds_name}'."),
                context=ctx))
            continue

        # Numeric-content check. JS resolveAgg keeps only ``typeof v
        # === 'number'`` rows; a string-only column resolves to null
        # and the tile shows ``--``. We coerce-then-count so a column
        # of strings like "1.23" still passes (matches the runtime
        # path in resolveAgg, which uses raw JS number values from
        # the JSON dataset).
        coerced = pd.to_numeric(df[col], errors="coerce")
        n_valid = int(coerced.notna().sum())
        if n_valid == 0:
            samples = [str(v) for v in df[col].head(3).tolist()]
            out.append(Diagnostic(
                severity="error",
                code="kpi_source_no_numeric_values",
                widget_id=wid, path=f"{path}.{key}",
                message=(f"kpi '{wid}' {key}={src!r} column "
                         f"'{col}' has 0 numeric values "
                         f"(out of {len(df)} rows); the tile will "
                         f"render '--'."),
                context={key: src, "dataset": ds_name,
                           "column": col, "row_count": len(df),
                           "sample_values": samples,
                           "fix_hint": (
                               f"Repopulate the column upstream with "
                               f"numeric values, or point at a "
                               f"different column. Got non-numeric "
                               f"samples: {samples}.")}))
            continue

        # Sparkline-specific: a 'line' of <2 points isn't a line.
        # Severity stays as warning -- the sparkline is purely
        # cosmetic, the headline number still resolves.
        if kind == "sparkline" and n_valid < 2:
            out.append(Diagnostic(
                severity="warning",
                code="kpi_sparkline_too_short",
                widget_id=wid, path=f"{path}.{key}",
                message=(f"kpi '{wid}' sparkline_source={src!r} "
                         f"has only {n_valid} numeric value(s); "
                         f"the sparkline will be empty or a dot."),
                context={key: src, "dataset": ds_name,
                           "column": col,
                           "valid_value_count": n_valid,
                           "row_count": len(df),
                           "fix_hint": (
                               "Sparklines need >=2 points. Either "
                               "drop sparkline_source on this KPI or "
                               "point at a column with more "
                               "history.")}))
    return out


def _check_stat_grid_widget(w: Dict[str, Any], path: str,
                              dfs: Dict[str, Any]) -> List[Diagnostic]:
    """Per-stat source-binding diagnostics for a ``stat_grid`` widget.

    The widget is server-rendered: every stat's ``value`` is baked into
    the HTML at compile time (no JS resolves anything). So a stat with
    ``source`` set but no ``value`` will silently render as ``--``
    unless the compiler resolves the source to a real number first
    (see :func:`_resolve_stat_grid_sources`). The diagnostic mirrors
    the KPI checks so authors get the same actionable hints.
    """
    out: List[Diagnostic] = []
    wid = w.get("id")
    stats = w.get("stats")
    if not isinstance(stats, list):
        return out
    for si, st in enumerate(stats):
        if not isinstance(st, dict):
            continue
        stat_path = f"{path}.stats[{si}]"
        has_value = ("value" in st) and (st.get("value") is not None)
        src = st.get("source")
        has_source = bool(src) and isinstance(src, str)
        if not has_value and not has_source:
            out.append(Diagnostic(
                severity="error", code="stat_grid_no_value_no_source",
                widget_id=wid, path=stat_path,
                message=(
                    f"stat_grid '{wid}' stats[{si}] (label="
                    f"{st.get('label')!r}) has neither 'value' nor "
                    f"'source'; the cell will render '--'."),
                context={"fix_hint": (
                    "Set 'value' to a literal, or set 'source' to "
                    "'dataset.aggregator.column' so the compiler "
                    "resolves it.")}))
            continue
        if has_value and isinstance(st.get("value"), str) and \
                st["value"].strip() in ("--", "—", "n/a", "N/A"):
            out.append(Diagnostic(
                severity="error", code="stat_grid_value_is_placeholder",
                widget_id=wid, path=f"{stat_path}.value",
                message=(
                    f"stat_grid '{wid}' stats[{si}] value="
                    f"{st['value']!r} is a placeholder string."),
                context={"value": st["value"]}))
        # Only validate ``source`` when there is no ``value``. If
        # the author has set both, ``value`` wins (the resolver
        # respects pre-existing values), so a broken ``source`` is
        # dead config -- not worth blocking compile.
        if has_value:
            continue
        if not has_source:
            continue
        # Reuse KPI resolver -- stat_grid sources have the same
        # ``dataset.aggregator.column`` shape.
        resolved, reason = _resolve_kpi_value(src, dfs)
        if resolved is None:
            out.append(Diagnostic(
                severity="error", code="stat_grid_source_unresolvable",
                widget_id=wid, path=f"{stat_path}.source",
                message=(
                    f"stat_grid '{wid}' stats[{si}] source={src!r} "
                    f"cannot resolve: {reason}; the cell will "
                    f"render '--'."),
                context={"source": src, "reason": reason,
                           "fix_hint": (
                               "Fix the source to point at a real "
                               "dataset/column with numeric values, "
                               "or set 'value' directly.")}))
    return out


def _resolve_stat_grid_sources(
    manifest: Dict[str, Any], dfs: Dict[str, Any],
) -> None:
    """Compile-time resolve every ``stat_grid`` stat that has a
    ``source`` but no ``value`` into a baked-in ``value``.

    Stat_grid widgets are server-rendered only -- the JS dashboard
    runtime never resolves their sources. So we have to do it here
    or the cell will render as ``--``. Resolution failures are
    surfaced via :func:`_check_stat_grid_widget`; this function does
    NOT raise on failure (it leaves ``value`` unset so the diagnostic
    can flag the right thing).

    Mutates the manifest in-place. Idempotent: stats that already
    have a ``value`` are left alone.
    """
    layout = manifest.get("layout") or {}

    def _visit(rows):
        for row in rows or []:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                if w.get("widget") != "stat_grid":
                    continue
                stats = w.get("stats")
                if not isinstance(stats, list):
                    continue
                for st in stats:
                    if not isinstance(st, dict):
                        continue
                    if "value" in st and st["value"] is not None:
                        continue
                    src = st.get("source")
                    if not isinstance(src, str):
                        continue
                    resolved, _reason = _resolve_kpi_value(src, dfs)
                    if resolved is not None:
                        # Apply prefix/suffix/decimals if specified;
                        # mirror the JS formatter's compact-vs-comma
                        # rules so server-rendered values match.
                        st["value"] = _format_kpi_number(resolved, st)

    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            if isinstance(tab, dict):
                _visit(tab.get("rows", []))
    else:
        _visit(layout.get("rows", []))


def _format_kpi_number(n: float, opts: Dict[str, Any]) -> str:
    """Mirror of the JS ``formatNumber`` helper for server-side
    KPI/stat_grid rendering. Produces the same display string as the
    browser would, given the same number + format options
    (``decimals`` / ``format`` / ``prefix`` / ``suffix``).

    ``decimals`` is clamped to ``MAX_DASHBOARD_DECIMALS`` so a
    server-rendered stat-grid value can never exceed the global cap.

    Only used by :func:`_resolve_stat_grid_sources` (KPI uses JS at
    runtime). Pinned to JS via ``TestKPIResolution``.
    """
    prefix = opts.get("prefix") or ""
    suffix = opts.get("suffix") or ""
    mode = opts.get("format") or "auto"
    raw_decimals = opts.get("decimals")
    decimals = (None if raw_decimals is None
                else clamp_decimals(raw_decimals, default=raw_decimals))
    abs_n = abs(n)

    def _comma(int_str: str) -> str:
        # Insert thousands separators on the integer portion, mirroring
        # the JS regex ``\B(?=(\d{3})+(?!\d))``.
        sign = ""
        if int_str.startswith("-"):
            sign = "-"
            int_str = int_str[1:]
        rev = int_str[::-1]
        chunks = [rev[i:i+3] for i in range(0, len(rev), 3)]
        return sign + ",".join(chunks)[::-1]

    if mode == "raw":
        return f"{prefix}{n}{suffix}"
    if mode == "percent":
        d = 2 if decimals is None else decimals
        return f"{prefix}{(n * 100):.{d}f}%{suffix}"
    if mode == "comma":
        d = 0 if decimals is None and abs_n >= 1000 else (
            2 if decimals is None else decimals)
        whole, _, frac = f"{n:.{d}f}".partition(".")
        whole = _comma(whole)
        out = whole if not frac else f"{whole}.{frac}"
        return f"{prefix}{out}{suffix}"
    if mode == "compact":
        d = 1 if decimals is None else decimals
        if abs_n >= 1e12:
            return f"{prefix}{n/1e12:.{d}f}T{suffix}"
        if abs_n >= 1e9:
            return f"{prefix}{n/1e9:.{d}f}B{suffix}"
        if abs_n >= 1e6:
            return f"{prefix}{n/1e6:.{d}f}M{suffix}"
        if abs_n >= 1e3:
            return f"{prefix}{n/1e3:.{d}f}K{suffix}"
        return f"{prefix}{n:.{d}f}{suffix}"
    # auto: comma below 1M, compact above
    if abs_n >= 1e12:
        d = 1 if decimals is None else decimals
        return f"{prefix}{n/1e12:.{d}f}T{suffix}"
    if abs_n >= 1e9:
        d = 1 if decimals is None else decimals
        return f"{prefix}{n/1e9:.{d}f}B{suffix}"
    if abs_n >= 1e6:
        d = 1 if decimals is None else decimals
        return f"{prefix}{n/1e6:.{d}f}M{suffix}"
    d = 0 if decimals is None and abs_n >= 1000 else (
        2 if decimals is None else decimals)
    whole, _, frac = f"{n:.{d}f}".partition(".")
    whole = _comma(whole)
    out = whole if not frac else f"{whole}.{frac}"
    return f"{prefix}{out}{suffix}"


def _check_filter(f: Dict[str, Any], idx: int, manifest: Dict[str, Any],
                    dfs: Dict[str, Any]) -> List[Diagnostic]:
    """Filter-level diagnostics. Three failure modes:

      1. ``filter_field_missing_in_target`` - filter.field is not a
         column in any of the target widgets' datasets.
      2. ``filter_default_not_in_options`` - filter.default is not in
         filter.options for select/multiSelect/radio types.
      3. ``filter_targets_no_match`` - none of the filter.targets
         patterns matches a real widget id.
    """
    out: List[Diagnostic] = []
    fid = f.get("id")
    fld = f.get("field")
    targets = f.get("targets") or []
    layout = manifest.get("layout") or {}

    # Build the universe of widget ids in the manifest so we can flag
    # filter targets that resolve to nothing.
    widget_ids: List[str] = []

    def _gather_ids(rows):
        for row in rows or []:
            for w in row:
                if isinstance(w, dict) and isinstance(w.get("id"), str):
                    widget_ids.append(w["id"])

    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            _gather_ids(tab.get("rows", []))
    else:
        _gather_ids(layout.get("rows", []))

    # 1. Default not in options for select-style filters
    ftype = f.get("type")
    default = f.get("default")
    options = f.get("options")
    if ftype in ("select", "multiSelect", "radio") and isinstance(
        options, list
    ):
        flat_opts: List[Any] = []
        for o in options:
            if isinstance(o, dict):
                if "value" in o:
                    flat_opts.append(o["value"])
            else:
                flat_opts.append(o)
        if default is not None:
            defaults = (default if (ftype == "multiSelect" and
                                       isinstance(default, list))
                         else [default])
            missing = [d for d in defaults if d not in flat_opts]
            if missing:
                out.append(Diagnostic(
                    severity="warning",
                    code="filter_default_not_in_options",
                    widget_id=fid,
                    path=f"filters[{idx}].default",
                    message=(f"filter '{fid}' default={default!r} is not "
                             f"in options; UI will reset to first "
                             f"option or render unselected."),
                    context={"default": default, "options": flat_opts,
                               "missing": missing,
                               "fix_hint": (
                                   f"Set 'default' to one of "
                                   f"{flat_opts}, or add the missing "
                                   f"value(s) {missing} to "
                                   f"'options'.")}))

    # 2. Targets resolve to nothing
    def _matches(wid: str, pat: str) -> bool:
        if pat == "*":
            return True
        if "*" in pat:
            if pat.endswith("*"):
                return wid.startswith(pat[:-1])
            if pat.startswith("*"):
                return wid.endswith(pat[1:])
        return wid == pat

    if targets:
        unmatched = [
            t for t in targets
            if t != "*" and not any(_matches(w, t) for w in widget_ids)
        ]
        if unmatched and len(unmatched) == len(
            [t for t in targets if t != "*"]
        ):
            # Every non-wildcard target was unmatched -> filter is dead.
            out.append(Diagnostic(
                severity="warning",
                code="filter_targets_no_match",
                widget_id=fid,
                path=f"filters[{idx}].targets",
                message=(f"filter '{fid}' targets={targets!r} match no "
                         f"widget ids; the filter will be a no-op."),
                context={"targets": targets,
                           "available_widget_ids": sorted(set(widget_ids)),
                           "fix_hint": (
                               "Replace targets with widget ids that "
                               "exist (or '*' for all). Patterns like "
                               "'foo*' / '*bar' are supported.")}))

    # 3. Field doesn't exist in target dataset
    if not fld or not targets:
        return out

    # Resolve target widget ids -> their dataset_ref / spec.dataset
    target_datasets: set = set()

    def _visit(rows):
        for row in rows or []:
            for w in row:
                if not isinstance(w, dict):
                    continue
                wid = w.get("id")
                if not isinstance(wid, str):
                    continue
                if not any(_matches(wid, t) for t in targets):
                    continue
                ds = w.get("dataset_ref")
                if not ds and isinstance(w.get("spec"), dict):
                    ds = w["spec"].get("dataset")
                if ds:
                    target_datasets.add(ds)

    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            _visit(tab.get("rows", []))
    else:
        _visit(layout.get("rows", []))

    for ds in target_datasets:
        df = dfs.get(ds)
        if df is None:
            continue
        if fld not in df.columns:
            ctx = {"field": fld, "dataset": ds,
                    "available_columns": list(df.columns)}
            ctx.update(_suggest_for_missing_column(fld, list(df.columns)))
            out.append(Diagnostic(
                severity="error",
                code="filter_field_missing_in_target",
                widget_id=fid,
                path=f"filters[{idx}].field",
                message=(f"filter '{fid}' field='{fld}' is not "
                         f"a column in target dataset '{ds}'; the "
                         f"filter will silently filter nothing."),
                context=ctx))
    return out


# -----------------------------------------------------------------------------
# DATA SHAPE DIAGNOSTICS
#
# Shape problems are visible only on the original DataFrame -- once
# _normalize_manifest_datasets() converts datasets to list-of-lists,
# the index, dtype, and df.attrs metadata are gone. So we snapshot
# the relevant shape attributes BEFORE normalize and feed the snapshot
# into chart_data_diagnostics() so it can emit precise "you forgot
# reset_index() on dataset X" / "dataset Y was a tuple" messages.
#
# The compiler does NOT auto-fix any of these; it names them clearly
# so PRISM can fix the producer in one round-trip.
# -----------------------------------------------------------------------------

# Patterns for column names that look like raw API codes. When such a
# column is referenced by a chart/table/kpi the compiler emits a
# warning suggesting humanisation -- the legend / tooltip / table
# header reads the column name verbatim.
_OPAQUE_CODE_PATTERNS = (
    re.compile(r"^[A-Z][A-Z0-9_]*@[A-Z][A-Z0-9_]*$"),   # GDP@USECON (Haver)
    re.compile(r"^IR_[A-Z]{3}_"),                        # IR_USD_Treasury_10Y_Rate
    re.compile(r"^FX_[A-Z]{3}_"),
    re.compile(r"^EQ_[A-Z]{3}_"),
    re.compile(r"^CR_[A-Z]{3}_"),
    re.compile(r"\s"),                                    # whitespace in name
    re.compile(r"[/%]"),                                  # path-y / unit-y chars
)


def _looks_like_opaque_code(name: str) -> bool:
    """True iff column name matches one of the known opaque-code patterns.

    Conservative: a snake_case ASCII name like 'core_cpi' or 'us_10y'
    never trips. A code like 'JCXFE@USECON' or 'IR_USD_Swap_10Y' does.
    Used to surface humanisation suggestions, not to block compile.
    """
    if not isinstance(name, str) or not name:
        return False
    for pat in _OPAQUE_CODE_PATTERNS:
        if pat.search(name):
            return True
    return False


def _capture_shape_info(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Snapshot DataFrame shape attributes BEFORE normalize destroys them.

    Returns ``{dataset_name: shape_info}`` where shape_info captures only
    what the shape diagnostics need (kind, DTI flag, index name, columns,
    MultiIndex flag, attrs metadata). Datasets that are already in list-
    of-lists form yield ``{kind: 'list'}`` and trip none of the shape
    checks.

    Safe to call on any manifest -- non-dict input returns ``{}``.
    """
    info: Dict[str, Dict[str, Any]] = {}
    if not isinstance(manifest, dict):
        return info
    datasets = manifest.get("datasets") or {}
    if not isinstance(datasets, dict):
        return info
    try:
        import pandas as pd
    except ImportError:
        return info
    for name, entry in datasets.items():
        if isinstance(entry, tuple):
            info[name] = {"kind": "tuple", "tuple_len": len(entry)}
            continue
        df = None
        if isinstance(entry, pd.DataFrame):
            df = entry
        elif isinstance(entry, dict):
            src = entry.get("source")
            if isinstance(src, tuple):
                info[name] = {"kind": "tuple", "tuple_len": len(src)}
                continue
            if isinstance(src, pd.DataFrame):
                df = src
        if df is None:
            info[name] = {"kind": "list"}
            continue
        info[name] = {
            "kind": "dataframe",
            "has_dti": isinstance(df.index, pd.DatetimeIndex),
            "index_name": df.index.name,
            "columns": list(df.columns),
            "multiindex_columns": isinstance(df.columns, pd.MultiIndex),
            "attrs_metadata": df.attrs.get("metadata"),
        }
    return info


def _columns_referenced_by_widgets(
    manifest: Dict[str, Any], ds_name: str,
) -> List[str]:
    """Collect every column name referenced by chart mappings, table
    column fields, KPI sources, and filter fields targeting the given
    dataset. Used to gate "looks like an opaque code" warnings to
    columns the dashboard actually consumes -- raw codes nobody plots
    aren't worth flagging.
    """
    refs: List[str] = []

    def _visit_rows(rows):
        for row in rows or []:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                wt = w.get("widget")
                if wt == "chart":
                    spec = w.get("spec")
                    if not isinstance(spec, dict):
                        continue
                    if spec.get("dataset") != ds_name:
                        continue
                    chart_type = spec.get("chart_type")
                    for _k, c in _walk_column_refs(
                        spec.get("mapping") or {}, chart_type
                    ):
                        refs.append(c)
                elif wt == "table":
                    if w.get("dataset_ref") != ds_name:
                        continue
                    for c in (w.get("columns") or []):
                        if isinstance(c, dict) and c.get("field"):
                            refs.append(c["field"])
                elif wt == "kpi":
                    for src_key in ("source", "delta_source",
                                       "sparkline_source"):
                        s = w.get(src_key)
                        if not isinstance(s, str) or "." not in s:
                            continue
                        parts = s.split(".")
                        if parts[0] != ds_name:
                            continue
                        # source/delta_source are <ds>.<agg>.<col>
                        # sparkline_source is <ds>.<col>
                        if src_key == "sparkline_source" and len(parts) >= 2:
                            refs.append(parts[1])
                        elif len(parts) >= 3:
                            refs.append(parts[2])

    layout = manifest.get("layout") or {}
    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            if isinstance(tab, dict):
                _visit_rows(tab.get("rows", []))
    else:
        _visit_rows(layout.get("rows", []))
    return list(set(refs))


def _check_dataset_shape(
    manifest: Dict[str, Any],
    shape_info: Dict[str, Dict[str, Any]],
) -> List[Diagnostic]:
    """Emit shape-mistake diagnostics from the pre-normalize snapshot.

    Catches the four most common "PRISM passed un-cleaned data" mistakes:
    tuple instead of DataFrame, MultiIndex columns, DatetimeIndex with
    no 'date' column, opaque codes used as column names. Each diagnostic
    carries a ``fix_hint`` with the literal pandas snippet to apply.
    """
    out: List[Diagnostic] = []
    for name, info in shape_info.items():
        kind = info.get("kind")
        if kind == "tuple":
            out.append(Diagnostic(
                severity="error", code="dataset_passed_as_tuple",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' is a tuple (likely the "
                         f"unpacked return of pull_market_data, which "
                         f"yields (eod_df, intraday_df)). The compiler "
                         f"requires a single DataFrame."),
                context={"dataset": name,
                           "tuple_len": info.get("tuple_len"),
                           "fix_hint": (
                               f"Unpack first, then pick the relevant "
                               f"DataFrame: eod_df, _ = "
                               f"pull_market_data(...); "
                               f"datasets={{'{name}': eod_df}}.")}))
            continue
        if kind != "dataframe":
            continue
        if info.get("multiindex_columns"):
            out.append(Diagnostic(
                severity="error", code="dataset_columns_multiindex",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' columns is a pandas MultiIndex; "
                         f"the compiler does not auto-flatten it."),
                context={"dataset": name,
                           "columns": [list(c) if isinstance(c, tuple) else c
                                          for c in info.get("columns") or []],
                           "fix_hint": (
                               "Flatten before passing: "
                               "df.columns = ['_'.join(str(x) for x in c) "
                               "for c in df.columns]")}))
            continue
        # DatetimeIndex with no 'date' column AND a chart that wants 'date'.
        if info.get("has_dti"):
            cols = info.get("columns") or []
            if "date" not in cols and _any_widget_uses_date(manifest, name):
                idx_name = info.get("index_name") or "(unnamed)"
                out.append(Diagnostic(
                    severity="error", code="dataset_dti_no_date_column",
                    widget_id=None, path=f"datasets.{name}",
                    message=(f"dataset '{name}' has a DatetimeIndex "
                             f"(name='{idx_name}') but no 'date' column. "
                             f"The compiler does not auto-reset_index(); "
                             f"a chart/filter on this dataset references "
                             f"'date' and will fail to bind."),
                    context={"dataset": name,
                               "index_name": idx_name,
                               "available_columns": cols,
                               "fix_hint": (
                                   f"Reset before passing: "
                                   f"df = df.reset_index()"
                                   + (f"  # 'date' column appears"
                                      if idx_name == "date" else
                                      "; then rename the index column "
                                      "to 'date' if needed"))}))
        # Opaque-code column names referenced by widgets.
        refs = set(_columns_referenced_by_widgets(manifest, name))
        for col in info.get("columns") or []:
            if not isinstance(col, str):
                continue
            if col not in refs:
                continue
            if not _looks_like_opaque_code(col):
                continue
            out.append(Diagnostic(
                severity="warning",
                code="dataset_column_looks_like_code",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' column '{col}' looks like a "
                         f"raw API code (Haver / coordinate / expression). "
                         f"It will appear verbatim in legends, tooltips, "
                         f"and table headers."),
                context={"dataset": name, "column": col,
                           "fix_hint": (
                               f"Rename to plain English before passing: "
                               f"df = df.rename(columns={{'{col}': "
                               f"'<plain_english_name>'}}). "
                               f"df.attrs['metadata'] usually carries a "
                               f"display_name for each pulled series.")}))
        # Pull-time metadata available but columns still match raw codes.
        meta = info.get("attrs_metadata")
        if isinstance(meta, list) and meta:
            cols_set = set(info.get("columns") or [])
            meta_keys = set()
            for m in meta:
                if not isinstance(m, dict):
                    continue
                for k in ("coordinate", "code", "expression"):
                    v = m.get(k)
                    if isinstance(v, str):
                        meta_keys.add(v)
            overlap = cols_set & meta_keys
            if overlap:
                out.append(Diagnostic(
                    severity="info",
                    code="dataset_metadata_attrs_unused",
                    widget_id=None, path=f"datasets.{name}",
                    message=(f"dataset '{name}' carries pull-time metadata "
                             f"in df.attrs['metadata'] but columns still "
                             f"use raw codes ({sorted(overlap)[:3]}...). "
                             f"Consider mapping coordinate -> plain "
                             f"English before passing."),
                    context={"dataset": name,
                               "raw_columns_in_metadata": sorted(overlap),
                               "fix_hint": (
                                   "rename = {m['coordinate']: "
                                   "<plain_english> for m in "
                                   "df.attrs['metadata']}; "
                                   "df = df.rename(columns=rename)")}))
    return out


def _any_widget_uses_date(manifest: Dict[str, Any], ds_name: str) -> bool:
    """True iff some widget in manifest references column 'date' on
    the named dataset (chart mapping, filter field, kpi source). Used
    to gate the dataset_dti_no_date_column diagnostic so we only fire
    it when the dashboard actually expects a date column.
    """
    def _visit(rows):
        for row in rows or []:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                if w.get("widget") == "chart":
                    spec = w.get("spec")
                    if isinstance(spec, dict) and spec.get("dataset") == ds_name:
                        chart_type = spec.get("chart_type")
                        for _k, c in _walk_column_refs(
                            spec.get("mapping") or {}, chart_type
                        ):
                            if c == "date":
                                return True
                if w.get("widget") in ("table", "kpi"):
                    if w.get("dataset_ref") == ds_name:
                        # tables / kpis don't usually use 'date' directly,
                        # but a date column is implied for time-series
                        # contexts; safe to skip here.
                        pass
        return False

    layout = manifest.get("layout") or {}
    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            if isinstance(tab, dict) and _visit(tab.get("rows", [])):
                return True
    else:
        if _visit(layout.get("rows", [])):
            return True
    # Filters can also imply a date column.
    for f in manifest.get("filters") or []:
        if not isinstance(f, dict):
            continue
        if f.get("type") == "dateRange" or f.get("field") == "date":
            # Check whether this filter targets the dataset.
            for t in f.get("targets") or []:
                # If target is '*' or a widget on this dataset, count it.
                if t == "*":
                    return True
                # Target is a widget id; we'd need the widget->dataset
                # map. Conservative: treat as "may target ds_name".
                return True
    return False


# -----------------------------------------------------------------------------
# DATA SIZE DIAGNOSTICS
#
# Run after normalize so we measure the actual list-of-lists payload,
# which is what the HTML embeds. Both row-count and serialised-byte
# limits fire so the failure mode is clearly named -- "this dataset
# has too many rows" reads differently from "this dataset is too
# heavy" (row counts are bounded but each row is a 200-char dict).
# -----------------------------------------------------------------------------

def _serialised_bytes(source: Any) -> int:
    """Length of ``json.dumps(source, default=str)`` in bytes. Mirrors
    the actual cost of embedding the dataset in the HTML payload.
    Returns 0 on non-serialisable input so a corrupted dataset doesn't
    blow up the size check.
    """
    try:
        return len(json.dumps(source, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def _row_count(source: Any) -> int:
    """Row count for a normalised list-of-lists source: len-1 because
    row 0 is the header. Returns 0 for malformed input.
    """
    if not isinstance(source, list) or not source:
        return 0
    return max(0, len(source) - 1)


def _check_dataset_size(
    manifest: Dict[str, Any],
    table_dataset_refs: set,
) -> List[Diagnostic]:
    """Emit size-budget diagnostics for every dataset in the manifest
    plus a manifest-level total. ``table_dataset_refs`` is the set of
    dataset names consumed by table widgets (used to apply the stricter
    table-rows thresholds).

    Pre-condition: manifest.datasets are normalised to list-of-lists.
    """
    out: List[Diagnostic] = []
    datasets = manifest.get("datasets") or {}
    if not isinstance(datasets, dict):
        return out

    total_bytes = 0
    for name, entry in datasets.items():
        source = entry.get("source") if isinstance(entry, dict) else entry
        rows = _row_count(source)
        sbytes = _serialised_bytes(source)
        total_bytes += sbytes

        if rows >= DATASET_ROWS_ERROR:
            out.append(Diagnostic(
                severity="error", code="dataset_rows_error",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' has {rows:,} rows "
                         f"(>= {DATASET_ROWS_ERROR:,}); embedding this "
                         f"in the dashboard HTML produces multi-MB "
                         f"payloads and slow first-render."),
                context={"dataset": name, "row_count": rows,
                           "threshold": DATASET_ROWS_ERROR,
                           "fix_hint": (
                               "Top-N filter at pull time (only the rows "
                               "the dashboard actually needs), reduce the "
                               "history window, or move the data behind "
                               "an API endpoint and lazy-load. See "
                               "DATA_SHAPES.md 'Data budget limits'.")}))
        elif rows >= DATASET_ROWS_WARN:
            out.append(Diagnostic(
                severity="warning", code="dataset_rows_warning",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' has {rows:,} rows "
                         f"(>= {DATASET_ROWS_WARN:,}); consider whether "
                         f"this much history is necessary."),
                context={"dataset": name, "row_count": rows,
                           "threshold": DATASET_ROWS_WARN,
                           "fix_hint": (
                               "Daily 10y is ~2,500 rows. Datasets above "
                               "10K usually mean the lookback is too long "
                               "or the universe wasn't filtered.")}))

        if sbytes >= DATASET_BYTES_ERROR:
            out.append(Diagnostic(
                severity="error", code="dataset_bytes_error",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' serialises to "
                         f"{sbytes:,} bytes "
                         f"(>= {DATASET_BYTES_ERROR:,}); the HTML "
                         f"payload will be sluggish to load."),
                context={"dataset": name, "bytes": sbytes,
                           "threshold": DATASET_BYTES_ERROR,
                           "fix_hint": (
                               "Drop columns that no widget reads, "
                               "shorten the history window, or split "
                               "into multiple smaller datasets keyed by "
                               "primary entity.")}))
        elif sbytes >= DATASET_BYTES_WARN:
            out.append(Diagnostic(
                severity="warning", code="dataset_bytes_warning",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' serialises to "
                         f"{sbytes:,} bytes "
                         f"(>= {DATASET_BYTES_WARN:,})."),
                context={"dataset": name, "bytes": sbytes,
                           "threshold": DATASET_BYTES_WARN}))

        # Stricter row caps for tables (the table widget renders every
        # row to the DOM regardless of max_rows).
        if name in table_dataset_refs:
            if rows >= TABLE_ROWS_ERROR:
                out.append(Diagnostic(
                    severity="error", code="table_rows_error",
                    widget_id=None, path=f"datasets.{name}",
                    message=(f"dataset '{name}' (consumed by a table "
                             f"widget) has {rows:,} rows "
                             f"(>= {TABLE_ROWS_ERROR:,}); the table "
                             f"will be unusable to scroll."),
                    context={"dataset": name, "row_count": rows,
                               "threshold": TABLE_ROWS_ERROR,
                               "fix_hint": (
                                   "Filter / aggregate the table dataset "
                                   "to a screened subset before passing. "
                                   "max_rows on the table widget only "
                                   "limits the visible viewport, not "
                                   "the embedded row count.")}))
            elif rows >= TABLE_ROWS_WARN:
                out.append(Diagnostic(
                    severity="warning", code="table_rows_warning",
                    widget_id=None, path=f"datasets.{name}",
                    message=(f"dataset '{name}' (consumed by a table "
                             f"widget) has {rows:,} rows "
                             f"(>= {TABLE_ROWS_WARN:,})."),
                    context={"dataset": name, "row_count": rows,
                               "threshold": TABLE_ROWS_WARN}))

    if total_bytes >= MANIFEST_BYTES_ERROR:
        out.append(Diagnostic(
            severity="error", code="manifest_bytes_error",
            widget_id=None, path="datasets",
            message=(f"manifest datasets total {total_bytes:,} bytes "
                     f"(>= {MANIFEST_BYTES_ERROR:,}); the compiled HTML "
                     f"will exceed practical browser-load thresholds."),
            context={"total_bytes": total_bytes,
                       "threshold": MANIFEST_BYTES_ERROR,
                       "fix_hint": (
                           "Trim the largest dataset (see per-dataset "
                           "diagnostics) or split this dashboard into "
                           "two narrower ones.")}))
    elif total_bytes >= MANIFEST_BYTES_WARN:
        out.append(Diagnostic(
            severity="warning", code="manifest_bytes_warning",
            widget_id=None, path="datasets",
            message=(f"manifest datasets total {total_bytes:,} bytes "
                     f"(>= {MANIFEST_BYTES_WARN:,})."),
            context={"total_bytes": total_bytes,
                       "threshold": MANIFEST_BYTES_WARN}))

    return out


def _table_dataset_refs(manifest: Dict[str, Any]) -> set:
    """Set of dataset names consumed by any table widget. Used by
    _check_dataset_size to apply the stricter table-rows thresholds.
    """
    refs: set = set()

    def _visit(rows):
        for row in rows or []:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                if w.get("widget") != "table":
                    continue
                ds = w.get("dataset_ref")
                if isinstance(ds, str):
                    refs.add(ds)

    layout = manifest.get("layout") or {}
    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            if isinstance(tab, dict):
                _visit(tab.get("rows", []))
    else:
        _visit(layout.get("rows", []))
    return refs


def chart_data_diagnostics(
    manifest: Dict[str, Any],
) -> List[Diagnostic]:
    """Inspect every chart/table/kpi/filter binding in ``manifest`` and
    return a list of :class:`Diagnostic` entries for empty datasets,
    missing columns, all-NaN series, missing required mapping keys,
    non-numeric value columns, filter-field/target mismatches, and
    dataset / manifest size budget violations.

    Shape diagnostics (DatetimeIndex with no 'date' column, MultiIndex
    columns, opaque-code names, tuple-instead-of-DataFrame, attrs
    metadata unused) require a snapshot of the original DataFrame
    shapes taken BEFORE :func:`_normalize_manifest_datasets` ran;
    :func:`compile_dashboard` and :func:`render_dashboard` capture
    that snapshot via :func:`_capture_shape_info` and call
    :func:`_check_dataset_shape` separately, so this function only
    needs to handle the post-normalize binding + size checks.

    Pure function: no side effects, no IO, manifest is not mutated.
    Safe to call at any time on any manifest (validator-checked or not).
    Returns an empty list when no problems are detected.
    """
    diags: List[Diagnostic] = []
    if not isinstance(manifest, dict):
        return diags

    dfs = _materialize_datasets(manifest)
    layout = manifest.get("layout") or {}

    def _walk(rows, path_prefix: str) -> None:
        for ri, row in enumerate(rows or []):
            if not isinstance(row, list):
                continue
            for wi, w in enumerate(row):
                if not isinstance(w, dict):
                    continue
                wpath = f"{path_prefix}[{ri}][{wi}]"
                wt = w.get("widget")
                if wt == "chart":
                    diags.extend(_check_chart_widget(w, wpath, dfs))
                elif wt == "table":
                    diags.extend(_check_table_widget(w, wpath, dfs))
                elif wt == "kpi":
                    diags.extend(_check_kpi_widget(w, wpath, dfs))
                elif wt == "stat_grid":
                    diags.extend(_check_stat_grid_widget(w, wpath, dfs))

    if layout.get("kind") == "tabs":
        for ti, tab in enumerate(layout.get("tabs", []) or []):
            if isinstance(tab, dict):
                _walk(tab.get("rows", []),
                      f"layout.tabs[{ti}].rows")
    else:
        _walk(layout.get("rows", []), "layout.rows")

    for fi, f in enumerate(manifest.get("filters") or []):
        if isinstance(f, dict):
            diags.extend(_check_filter(f, fi, manifest, dfs))

    diags.extend(_check_dataset_size(manifest, _table_dataset_refs(manifest)))

    return diags


# =============================================================================
# PUBLIC FUNCTIONS
# =============================================================================


def render_dashboard(manifest: Dict[str, Any],
                      output_path: Optional[Union[str, Path]] = None,
                      chart_specs: Optional[Dict[str, Dict[str, Any]]] = None,
                      base_dir: Optional[Union[str, Path]] = None) -> DashboardResult:
    """Render an already-validated or in-memory manifest to HTML.

    If chart_specs is None, refs in the manifest are resolved relative to
    base_dir (or the output_path's parent directory). High-level `spec`
    widgets are lowered to ECharts options via the builder dispatch.

    DataFrames in manifest.datasets (via the .source field or as shorthand
    for the entry itself) are transparently converted to source arrays.

    Data diagnostics (empty datasets, missing columns, all-NaN series,
    etc.) are collected per widget and returned on
    :class:`DashboardResult.diagnostics`. Render does not fail because
    of diagnostics -- broken charts get an empty placeholder option so
    the rest of the dashboard still renders.
    """
    pre_shapes = _capture_shape_info(manifest)
    shape_diags = _check_dataset_shape(manifest, pre_shapes)
    _normalize_manifest_datasets(manifest)
    _augment_manifest(manifest)
    ok, errs = validate_manifest(manifest)
    if not ok:
        return DashboardResult(
            manifest=manifest, manifest_path=None,
            html_path=None, html=None, success=False,
            error_message="manifest validation failed",
            warnings=list(errs) + [str(d) for d in shape_diags],
            diagnostics=list(shape_diags),
        )
    diags: List[Diagnostic] = (list(shape_diags)
                                  + list(chart_data_diagnostics(manifest)))
    if chart_specs is None:
        base = Path(base_dir) if base_dir else (
            Path(output_path).parent if output_path else Path.cwd()
        )
        chart_specs = _resolve_chart_specs(manifest, base, diags=diags)
    html = render_dashboard_html(manifest, chart_specs,
                                  filename_base=manifest.get("id", "dashboard"))
    html_path: Optional[Path] = None
    if output_path:
        html_path = Path(output_path)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
    return DashboardResult(
        manifest=manifest, manifest_path=None,
        html_path=str(html_path) if html_path else None,
        html=html, success=True,
        warnings=[str(d) for d in diags],
        diagnostics=diags,
    )


def _clone_manifest_for_compile(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Return an independently-owned working copy of ``manifest`` for
    compile_dashboard's mutation pipeline.

    compile_dashboard runs the full augmentation pipeline (dataset
    normalisation, computed columns, compile-time show_when filtering,
    filter scope inference + dataset_ref auto-wire, stat_grid value
    baking) on its working dict. Each step mutates one of the three
    mutation-prone substructures:

        * ``datasets``  -- entry rebinding and inner-dict mutation
                           (``entry["source"] = df_to_source(df)``)
        * ``filters``   -- per-element scope + default rewrites
        * ``layout``    -- widget removal, ``dataset_ref`` auto-wire,
                           stat_grid value baking

    To keep the function pure on the caller's dict, every other top-
    level key is deep-copied and the three above are independently
    owned at the level the pipeline writes to. DataFrame bodies in
    ``datasets`` entries are SHARED by reference -- they are never
    mutated, only rebound to a normalised source-list form -- so
    cloning a manifest with a multi-million-row DataFrame stays cheap.
    """
    import copy as _copy
    out: Dict[str, Any] = {}
    for k, v in manifest.items():
        if k == "datasets":
            continue
        out[k] = _copy.deepcopy(v)
    src_datasets = manifest.get("datasets")
    if isinstance(src_datasets, dict):
        copied_datasets: Dict[str, Any] = {}
        for name, entry in src_datasets.items():
            if isinstance(entry, dict):
                # Independently-owned inner dict so
                # _normalize_manifest_datasets / _apply_computed_datasets
                # can rebind entry["source"] / entry["compute"] without
                # touching the caller. DataFrame bodies inside entry
                # (e.g. entry["source"] when it is a DataFrame) are
                # shared by reference; df_to_source(df) does not mutate
                # df, it returns a fresh list-of-lists.
                copied_datasets[name] = {k: v for k, v in entry.items()}
            else:
                # DataFrame / list / scalar entry: rebound at the outer
                # dict level by _normalize_manifest_datasets, never
                # mutated in place.
                copied_datasets[name] = entry
        out["datasets"] = copied_datasets
    elif src_datasets is not None:
        out["datasets"] = src_datasets
    return out


def compile_dashboard(
    manifest: Union[Dict[str, Any], str, Path],
    session_path: Optional[Union[str, Path]] = None,
    output_path: Optional[Union[str, Path]] = None,
    write_html: bool = True,
    write_json: bool = True,
    save_pngs: bool = False,
    png_dir: Optional[Union[str, Path]] = None,
    png_scale: int = 2,
    strict: bool = True,
    require_persistence_metadata: bool = True,
) -> DashboardResult:
    """JSON-first entry point. Compile a manifest to a dashboard.

    Accepts any of:
        * a manifest dict
        * a JSON string containing the manifest
        * a filesystem path (str or Path) to a manifest JSON file

    PURE on the caller's manifest dict: the augmentation pipeline runs
    on a private working copy (see ``_clone_manifest_for_compile``).
    The returned ``DashboardResult.manifest`` is the post-augment
    working copy; the caller's input dict is untouched.

    Side effects (when write_html/write_json):
        * session_path  -> session_path/dashboards/{id}.json + {id}.html
        * output_path   -> output_path + .json + .html (suffixes forced)
        * neither       -> returns result with html attribute only, no IO

    Unlike render_dashboard(), this function always re-validates and always
    runs the spec resolver, and it writes the *canonical* manifest JSON
    alongside the HTML. This is the function PRISM should call.

    High-level `spec` widgets are lowered to ECharts option JSON at compile
    time; the written manifest mirrors the input exactly (specs are NOT
    inlined into the manifest, they're resolved only for the HTML payload).

    ``strict`` (default ``True``) raises :class:`ValueError` when any
    error-severity diagnostic fires (size budget breach, dataset shape
    mistake, missing column, KPI source that would render as ``--``,
    etc.). This is the safe production behaviour: a broken headline
    number is a broken dashboard, full stop. The opt-in
    ``strict=False`` keeps the inner-loop iteration model -- compile
    still produces HTML, broken charts get placeholders, every
    diagnostic shows up on the result -- so PRISM can fix everything
    in one round-trip rather than discovering one bug per recompile.

    ``strict`` was flipped from ``False`` to ``True`` after the
    discovery that production was shipping dashboards with KPI tiles
    rendering ``--`` because the diagnostic layer was either silent
    or non-blocking. The new default is "fail loud, fix it"; PRISM's
    iteration runner explicitly opts into the resilient mode.

    Note: a small allow-list of load-bearing error codes
    (:data:`ALWAYS_BLOCKING_ERROR_CODES`) ALWAYS fail compile,
    regardless of ``strict``. These are codes where the rendered
    artifact is guaranteed broken (chart placeholder, KPI ``--``,
    empty table cell, no-op filter); persisting such an artifact
    ships a known-broken dashboard. ``strict=False`` cannot suppress
    them. Authors can still iterate freely on cosmetic / advisory
    diagnostics in non-strict mode -- only the load-bearing set is
    elevated.
    """
    if isinstance(manifest, (str, Path)):
        base_dir: Optional[Path] = None
        text = str(manifest).strip()
        if text.startswith("{"):
            manifest_dict = json.loads(text)
        else:
            p = Path(manifest)
            try:
                is_file = p.is_file()
            except OSError:
                is_file = False
            if is_file:
                manifest_dict = load_manifest(p)
                base_dir = p.parent
            else:
                raise FileNotFoundError(
                    f"compile_dashboard: '{manifest}' is neither a valid file "
                    f"path nor a JSON string"
                )
    elif isinstance(manifest, dict):
        manifest_dict = _clone_manifest_for_compile(manifest)
        base_dir = None
    else:
        raise TypeError(
            f"compile_dashboard: manifest must be dict, str, or Path; "
            f"got {type(manifest).__name__}"
        )

    pre_shapes = _capture_shape_info(manifest_dict)
    # Shape diagnostics run from the snapshot; any tuple/MultiIndex
    # dataset would also fail validation downstream, but the shape
    # diagnostic names the exact fix so we want it in the result even
    # when validation later rejects the manifest.
    shape_diags = _check_dataset_shape(manifest_dict, pre_shapes)
    _normalize_manifest_datasets(manifest_dict)
    compute_errors = _apply_computed_datasets(manifest_dict)
    # Compile-time show_when: drop widgets whose data-condition fails
    # before validation walks the layout (a removed widget shouldn't
    # contribute diagnostics, target counts, etc.).
    _apply_show_when_compile(manifest_dict)
    _augment_manifest(manifest_dict)

    # compile_dashboard is the user-facing build path; the four
    # always-on chrome buttons (Methodology / Refresh / Share /
    # Download dropdown) must all be functional, which means the
    # gating metadata fields must all be present. validate_manifest
    # rejects manifests that would silently render with chrome buttons
    # missing. ``require_persistence_metadata`` defaults to True for
    # this reason; tests / dev fixtures that exercise the renderer with
    # bare-minimum manifests can opt out via the kwarg.
    ok, errs = validate_manifest(
        manifest_dict,
        require_persistence_metadata=require_persistence_metadata)
    if not ok or compute_errors:
        # Structural validation failed. Run chart_data_diagnostics NOW
        # (rather than short-circuiting as the legacy path did) so
        # PRISM sees EVERY bug in one pass -- validate errors AND
        # data-binding errors together. Without this, PRISM needs one
        # round-trip to fix metadata and a second to fix chart mappings
        # that were visible at the first compile but silently dropped.
        #
        # The return path is preserved (strict OR non-strict) because
        # validate failures are the "malformed manifest" class that
        # callers expect to observe via DashboardResult.success /
        # .warnings / .diagnostics. CDD errors in the post-validate
        # path (below) still raise under strict=True. End-state
        # contract: on any call, PRISM's ONE-SHOT view of errors is
        # (a) r.warnings + r.diagnostics if r was returned, or
        # (b) the ValueError message if it was raised. Either way,
        # every error is visible in a single call.
        cdd_diags_pre: List[Diagnostic]
        try:
            cdd_diags_pre = list(chart_data_diagnostics(manifest_dict))
        except Exception as cdd_exc:  # noqa: BLE001
            # Structural damage severe enough to crash CDD itself --
            # surface the crash as a synthetic diagnostic so the error
            # surface stays programmatic; validate errors still go
            # through.
            cdd_diags_pre = [Diagnostic(
                severity="error",
                code="chart_data_diagnostics_raised",
                widget_id=None,
                path="(root)",
                message=(f"chart_data_diagnostics could not run on "
                         f"this manifest: "
                         f"{type(cdd_exc).__name__}: {cdd_exc}"),
            )]
        agg_warnings = (list(errs)
                         + list(compute_errors)
                         + [str(d) for d in shape_diags]
                         + [str(d) for d in cdd_diags_pre])
        agg_diags = list(shape_diags) + list(cdd_diags_pre)
        return DashboardResult(
            manifest=manifest_dict, manifest_path=None,
            html_path=None, html=None, success=False,
            error_message=(
                "manifest validation failed" if not ok
                else "compute block evaluation failed"
            ),
            warnings=agg_warnings,
            diagnostics=agg_diags,
        )

    manifest_path: Optional[Path] = None
    html_path: Optional[Path] = None
    if output_path:
        html_path = Path(output_path)
        if html_path.suffix.lower() != ".html":
            html_path = html_path.with_suffix(".html")
        manifest_path = html_path.with_suffix(".json")
        base_dir = base_dir or html_path.parent
    elif session_path:
        sp = Path(session_path) / "dashboards"
        sp.mkdir(parents=True, exist_ok=True)
        dashboard_id = manifest_dict.get("id", "dashboard")
        manifest_path = sp / f"{dashboard_id}.json"
        html_path = sp / f"{dashboard_id}.html"
        base_dir = base_dir or Path(session_path)

    # Compile-time resolve stat_grid sources into baked ``value``s
    # BEFORE diagnostics + before manifest is persisted. stat_grid is
    # server-rendered only (the JS dashboard runtime never resolves
    # stat sources), so a stat with ``source`` set but no ``value``
    # would silently render ``--`` in the browser unless we resolve
    # it here. Sources that fail to resolve are left untouched and
    # surface via ``stat_grid_source_unresolvable`` in diagnostics.
    _resolve_stat_grid_sources(
        manifest_dict, _materialize_datasets(manifest_dict)
    )

    if manifest_path and write_json:
        save_manifest(manifest_dict, manifest_path)

    diags: List[Diagnostic] = (list(shape_diags)
                                  + list(chart_data_diagnostics(manifest_dict)))

    # Always-blocking error codes fire regardless of the ``strict`` flag --
    # see ALWAYS_BLOCKING_ERROR_CODES near the data-budget constants for
    # the rationale. ``strict=False`` iteration mode is preserved for
    # error codes outside this set; codes inside it would silently ship
    # a broken dashboard and so always raise.
    always_blocking = [
        d for d in diags
        if d.severity == "error"
        and d.code in ALWAYS_BLOCKING_ERROR_CODES
    ]
    if always_blocking:
        # No truncation: every always-blocking error goes into the
        # message so PRISM can batch-fix them in one recompile.
        body = "\n".join(f"  - {e}" for e in always_blocking)
        raise ValueError(
            f"compile_dashboard: {len(always_blocking)} always-blocking "
            f"error-severity diagnostic(s) (these fail regardless of the "
            f"`strict` flag because the rendered artifact would be "
            f"broken):\n{body}"
        )

    if strict:
        errors = [d for d in diags if d.severity == "error"]
        if errors:
            body = "\n".join(f"  - {e}" for e in errors)
            raise ValueError(
                f"compile_dashboard(strict=True): "
                f"{len(errors)} error-severity diagnostic(s):\n"
                f"{body}"
            )
    chart_specs = _resolve_chart_specs(
        manifest_dict, base_dir, diags=diags,
    )

    # Post-build re-check: ``_resolve_chart_specs`` adds ``chart_build_failed``
    # diagnostics when a builder raises (typically because a validation gap
    # in chart_data_diagnostics let a bad spec through to the builder).
    # ``chart_build_failed`` is always-blocking because the chart card
    # renders as the ``(no data)`` placeholder -- a broken artifact, just
    # discovered later in the pipeline.
    pre_block_ids = {id(d) for d in always_blocking}
    new_blocking = [
        d for d in diags
        if d.severity == "error"
        and d.code in ALWAYS_BLOCKING_ERROR_CODES
        and id(d) not in pre_block_ids
    ]
    if new_blocking:
        body = "\n".join(f"  - {e}" for e in new_blocking)
        raise ValueError(
            f"compile_dashboard: {len(new_blocking)} always-blocking "
            f"error-severity diagnostic(s) emerged during spec resolution "
            f"(builder exception(s); the rendered chart card would show "
            f"the `(no data)` placeholder):\n{body}"
        )

    html = render_dashboard_html(
        manifest_dict, chart_specs,
        filename_base=manifest_dict.get("id", "dashboard"),
    )

    if html_path and write_html:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

    warnings: List[str] = [str(d) for d in diags]
    if save_pngs:
        # pick a dir: explicit override, or alongside the html file
        resolved_png_dir: Optional[Path] = None
        if png_dir is not None:
            resolved_png_dir = Path(png_dir)
        elif html_path is not None:
            resolved_png_dir = html_path.parent / (html_path.stem + "_pngs")
        elif session_path is not None:
            resolved_png_dir = Path(session_path) / "pngs"
        if resolved_png_dir is None:
            warnings.append(
                "save_pngs=True but no png_dir/html_path/session_path "
                "provided; skipping PNG export."
            )
        else:
            try:
                from rendering import save_dashboard_pngs
                save_dashboard_pngs(
                    manifest_dict, chart_specs, resolved_png_dir,
                    scale=int(png_scale),
                )
            except Exception as e:  # noqa: BLE001
                warnings.append(f"PNG export failed: {e}")

    return DashboardResult(
        manifest=manifest_dict,
        manifest_path=str(manifest_path) if manifest_path else None,
        html_path=str(html_path) if html_path else None,
        html=html, success=True, warnings=warnings,
        diagnostics=diags,
    )


__all__ = [
    "Dashboard", "DashboardResult", "Tab",
    "ChartRef", "KPIRef", "TableRef", "MarkdownRef", "NoteRef", "DividerRef",
    "GlobalFilter", "Link",
    "compile_dashboard", "render_dashboard",
    "load_manifest", "validate_manifest", "save_manifest",
    "prepare_manifest",
    "load_tool_def", "normalize_tool_def",
    "df_to_source", "manifest_template", "populate_template",
    "Diagnostic", "chart_data_diagnostics",
    "SCHEMA_VERSION", "VALID_WIDGETS", "VALID_FILTERS",
    "VALID_CHART_TYPES", "VALID_FILTER_OPS", "VALID_SYNC",
    "VALID_BRUSH_TYPES", "VALID_TABLE_FORMATS",
    "VALID_REFRESH_FREQUENCIES", "VALID_NOTE_KINDS",
    "VALID_KPI_AGGREGATORS",
    "DATASET_ROWS_WARN", "DATASET_ROWS_ERROR",
    "DATASET_BYTES_WARN", "DATASET_BYTES_ERROR",
    "MANIFEST_BYTES_WARN", "MANIFEST_BYTES_ERROR",
    "TABLE_ROWS_WARN", "TABLE_ROWS_ERROR",
    "ALWAYS_BLOCKING_ERROR_CODES",
]
