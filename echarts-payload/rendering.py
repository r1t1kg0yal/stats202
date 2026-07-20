"""
rendering -- HTML templates + headless-Chrome PNG export for ai_development/dashboards.

Three concerns merged into one module:

    1. Single-chart editor HTML  (render_editor_html)
       Minimal-aesthetic interactive editor for one chart: knobs, spec-sheets,
       raw JSON escape hatch. Used by make_echart().

    2. Dashboard HTML            (render_dashboard_html)
       GS-branded self-contained dashboard: cards, tabs, grid, global filters,
       brush cross-filter, echarts.connect() link groups. Used by
       compile_dashboard(). Share and persisted-input clients live in
       dashboard_share.SHARE_CONTROLLER_JS and
       dashboard_user_input.USER_INPUT_CONTROLLER_JS (injected into
       DASHBOARD_APP_JS).

    3. PNG export                (save_chart_png, save_dashboard_pngs,
                                   save_dashboard_html_png, find_chrome)
       Server-side rasterization via headless Chrome. Zero Python deps; only
       requires a Chrome/Chromium binary (auto-detected on macOS, overridable
       via $CHROME_BIN).

Entry points
============

    render_editor_html(option, chart_id, chart_type, theme, palette,
                        dimension_preset, knob_defs, spec_sheets,
                        active_spec_sheet, user_id, filename_base) -> str

    render_dashboard_html(manifest, chart_specs, filename_base) -> str

    save_chart_png(option, path, ...) -> Path
    save_dashboard_pngs(manifest, chart_specs, dir, ...) -> List[Path]
    save_dashboard_html_png(html_path, png_path, ...) -> Path
    find_chrome() -> str

All PNG functions raise RuntimeError with an explicit message when the
Chrome dependency is not available -- there is no silent fallback.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from config import (
    THEMES, PALETTES, DIMENSION_PRESETS, TYPOGRAPHY_OVERRIDES,
    resolve_theme,
    GS_SKY, GS_NAVY, GS_NAVY_DEEP, GS_INK, GS_PAPER, GS_BG,
    GS_GREY_70, GS_GREY_40, GS_GREY_20, GS_GREY_10, GS_GREY_05,
    GS_POS, GS_NEG, GS_FONT_SANS, GS_FONT_SERIF,
    GS_DARK_BG, GS_DARK_SURFACE, GS_DARK_SURFACE_2, GS_DARK_SURFACE_HOV,
    GS_DARK_TEXT, GS_DARK_TEXT_DIM, GS_DARK_TEXT_FAINT,
    GS_DARK_BORDER, GS_DARK_BORDER_STR,
    MAX_DASHBOARD_DECIMALS,
)

from dashboard_share import SHARE_CONTROLLER_JS
from dashboard_user_input import USER_INPUT_CONTROLLER_JS


# =============================================================================
# SHARED HELPERS
# =============================================================================

def _html_escape(s: Any) -> str:
    """HTML-escape any value (cast to str first)."""
    return (str(s).replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


# Cached, base64-encoded Prism AI logo PNG. Resolved lazily on the first
# render. Empty string ("") is a valid cache value and means "no logo
# available in this environment" -- the dashboard then emits the GS brand
# mark in the header instead. Cached for the life of the process; the
# file/S3 read happens at most once.
_PRISM_LOGO_B64_CACHE: Optional[str] = None


def _get_prism_logo_b64() -> str:
    """Return a base64-encoded Prism AI logo PNG, or "" if unavailable.

    Source priority (first hit wins, all subsequent renders use the cache):

      1. PRISM runtime: ``core.s3_bucket_manager.s3_manager``.
         This import only resolves inside the deployed PRISM environment;
         the staging mirror exposes the same import path. When it resolves,
         we pull
         ``development/images/prism_logo.png`` from S3.
      2. ``$PRISM_LOGO_PATH`` env var pointing at a local PNG. Works in
         either environment; useful for previewing the prism mark in
         staging without pulling the full PRISM stack.
      3. ``projects/echarts/assets/prism_logo.png``. Drop a PNG here to
         test the prism mark locally.
      4. ``""`` -- the renderer interprets this as "use the GS brand
         mark" (the original staging behaviour).

    Returning "" rather than raising is intentional: the caller branches
    on truthiness to choose between the prism-mark and gs-mark spans.
    """
    global _PRISM_LOGO_B64_CACHE
    if _PRISM_LOGO_B64_CACHE is not None:
        return _PRISM_LOGO_B64_CACHE
    import base64

    try:
        from core.s3_bucket_manager import s3_manager  # type: ignore[import-not-found]
        logo_bytes = s3_manager.get("development/images/prism_logo.png")
        _PRISM_LOGO_B64_CACHE = base64.b64encode(logo_bytes).decode("utf-8")
        return _PRISM_LOGO_B64_CACHE
    except Exception:
        pass

    env_path = os.environ.get("PRISM_LOGO_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            _PRISM_LOGO_B64_CACHE = base64.b64encode(
                p.read_bytes()).decode("utf-8")
            return _PRISM_LOGO_B64_CACHE

    local_path = _here / "assets" / "prism_logo.png"
    if local_path.is_file():
        _PRISM_LOGO_B64_CACHE = base64.b64encode(
            local_path.read_bytes()).decode("utf-8")
        return _PRISM_LOGO_B64_CACHE

    _PRISM_LOGO_B64_CACHE = ""
    return _PRISM_LOGO_B64_CACHE


def _option_value_label(o: Any) -> Tuple[str, str]:
    """Normalise a filter option to a (value, label) pair of strings.

    Two option shapes are supported on `filters[].options`:

      * Primitive  -- ``"3M"``, ``42``, ``True``: value == label == ``str(o)``.
      * Dict       -- ``{"value": "sell", "label": "Looking to Sell"}``:
                      value comes from ``o["value"]``, label falls back to
                      ``o.get("label", o["value"])``.

    Anything else (list, set, dict without ``value``) is rejected here --
    ``validate_manifest`` catches the same shape earlier, so reaching this
    helper with a bad option is a programmer error, not user input.
    """
    if isinstance(o, dict):
        if "value" not in o:
            raise ValueError(
                f"filter option dict missing 'value' key: {o!r}")
        v = str(o["value"])
        l = str(o.get("label", o["value"]))
        return v, l
    if isinstance(o, (str, int, float, bool)):
        return str(o), str(o)
    raise ValueError(
        f"filter option must be a primitive or {{value,label}} dict, "
        f"got {type(o).__name__}: {o!r}")


def _default_value_for_compare(default: Any) -> Any:
    """Pull the underlying ``value`` out of a dict default so it compares
    against an option's value rather than against the whole dict.
    """
    if isinstance(default, dict) and "value" in default:
        return default["value"]
    return default


def _json_default(o: Any) -> Any:
    """json.dumps default handler that keeps numpy / pandas scalars as
    numbers instead of strings.

    The prior behaviour (``default=str``) turned ``numpy.int64(68)``
    into the string ``"68"``, which then fell through the KPI value
    format branch (``typeof v === 'number'``) and rendered without the
    configured prefix / suffix / decimals. We cast known scalar types
    to their plain Python counterparts here.
    """
    for attr in ("item",):
        f = getattr(o, attr, None)
        if callable(f):
            try:
                v = f()
            except Exception:  # noqa: BLE001
                v = None
            if isinstance(v, (bool, int, float)):
                return v
    try:
        import numpy as _np
        if isinstance(o, _np.integer):
            return int(o)
        if isinstance(o, _np.floating):
            return float(o)
        if isinstance(o, _np.bool_):
            return bool(o)
        if isinstance(o, _np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    try:
        import pandas as _pd
        if isinstance(o, _pd.Timestamp):
            return o.isoformat()
    except ImportError:
        pass
    return str(o)



# =============================================================================
# PART 1 -- SINGLE-CHART EDITOR HTML
# =============================================================================
# Minimal-aesthetic interactive editor: knob cards, spec sheets, data/code/
# metadata/export panels, raw JSON escape hatch.


HTML_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>__TITLE__</title>
__ECHARTS_SCRIPT__
<style>
/* bare-minimum layout; aesthetics intentionally austere per project
   convention. Typeface is the Goldman Sachs stack so the editor
   matches the rendered chart. */
html,body{margin:0;padding:0;font-family:__GS_FONT_SANS__;
  font-size:13px;background:#fff;color:__GS_INK__}
header,main,footer{padding:8px 12px}
header{border-bottom:2px solid __GS_NAVY__}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.wrap{display:flex;flex-wrap:wrap;gap:12px}
.chart-col{flex:1 1 600px;min-width:400px}
.side-col{flex:0 0 440px;min-width:320px;max-width:520px}
#chart{width:100%;height:480px}
.side-col{border-left:1px solid #ccc;padding-left:10px}
.tabs button{background:none;border:1px solid #ccc;padding:3px 8px;cursor:pointer;margin-right:2px}
.tabs button.active{background:#eee;font-weight:bold}
.tab{display:none;margin-top:6px}
.tab.active{display:block}
textarea.raw{width:100%;height:300px;font-family:monospace;font-size:11px}
table.data{border-collapse:collapse;font-size:11px}
table.data th,table.data td{border:1px solid #ccc;padding:2px 6px}
table.data th{background:#f4f4f4;cursor:pointer}
input[type=search]{padding:3px;width:200px}
details.card{border:1px solid #ccc;padding:8px;margin-bottom:8px}
details.card>summary{font-weight:bold;cursor:pointer;padding:2px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px}
.knob{display:flex;justify-content:space-between;align-items:center;margin:3px 0;gap:6px}
.knob label{flex:1 1 auto;overflow:hidden;text-overflow:ellipsis}
.knob input,.knob select{flex:0 0 140px}
.knob input[type=range]{flex:0 0 100px}
.knob input[type=checkbox]{flex:0 0 auto}
.knob input[type=color]{flex:0 0 40px;padding:0}
.knob .val{flex:0 0 50px;text-align:right;font-family:monospace;font-size:11px}
button{cursor:pointer}
.status{color:#888;font-size:11px;margin-left:12px}
.group-title{font-weight:bold;margin-top:10px}
hr{border:none;border-top:1px solid #ccc;margin:6px 0}
</style>
</head>
<body>
<header>
<div class="row">
<strong>__TITLE__</strong>
<span class="status" id="chart-meta">chart_id: __CHART_ID__ | type: __CHART_TYPE__</span>
</div>
<div class="row" style="margin-top:4px">
<label>spec sheet:
<select id="sheet-select"></select>
</label>
<button id="sheet-save">Save</button>
<button id="sheet-saveas">Save as</button>
<button id="sheet-delete">Delete</button>
<button id="sheet-download">Download</button>
<button id="sheet-upload">Upload</button>
<input type="file" id="sheet-upload-file" accept=".json" style="display:none"/>
<span class="status" id="sheet-status"></span>
</div>
</header>
<main>
<div class="wrap">
<div class="chart-col">
<div class="row">
<button id="btn-reset">Reset view</button>
<button id="btn-full">Fullscreen</button>
<button id="btn-png2x">PNG 2x</button>
<button id="btn-png4x">PNG 4x</button>
<button id="btn-svg">SVG</button>
<span class="status" id="chart-status"></span>
</div>
<div id="chart" style="width:100%;height:480px"></div>
</div>
<div class="side-col">
<div class="tabs">
<button class="active" data-tab="data">Data</button>
<button data-tab="code">Code</button>
<button data-tab="meta">Metadata</button>
<button data-tab="export">Export</button>
<button data-tab="raw">Raw</button>
</div>
<div id="tab-data" class="tab active"></div>
<div id="tab-code" class="tab"></div>
<div id="tab-meta" class="tab"></div>
<div id="tab-export" class="tab"></div>
<div id="tab-raw" class="tab"></div>
</div>
</div>
<hr/>
<div class="row">
<input id="knob-search" type="search" placeholder="search knobs..."/>
<span class="status" id="knob-count"></span>
<button id="btn-reset-knobs">Reset all knobs</button>
</div>
<div id="knob-cards" class="cards" style="margin-top:8px"></div>
</main>
<footer>
<span class="status">echart_studio v__VERSION__ | echarts@5 (CDN)</span>
</footer>
<script>
__PAYLOAD__
__APP__
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# JS app: apply functions + knob wiring + tabs + spec sheets
# ---------------------------------------------------------------------------

APP_JS = r"""
(function(){
  'use strict';

  // Global decimal-precision cap for the single-chart editor. Mirror of
  // config.MAX_DASHBOARD_DECIMALS injected by render_editor_html. See
  // the matching helper at the top of DASHBOARD_APP_JS for the full
  // policy doc -- both halves of the runtime route their toFixed
  // arguments through __capDec so author-supplied precision options
  // can never exceed the cap, and so raising the cap is a one-place
  // edit (config.MAX_DASHBOARD_DECIMALS).
  var __MAX_DEC = __MAX_DECIMALS__;
  function __capDec(d, fb){
    var cap = __MAX_DEC;
    var fbn = (fb == null) ? 0 : (+fb | 0);
    if (fbn < 0) fbn = 0; if (fbn > cap) fbn = cap;
    if (d == null) return fbn;
    var n = +d;
    if (isNaN(n)) return fbn;
    n = n | 0;
    if (n < 0) return 0;
    if (n > cap) return cap;
    return n;
  }

  // Last-line-of-defence tooltip decimal cap (mirror of the dashboard
  // runtime helper). Skipped when a custom ``formatter`` or
  // ``valueFormatter`` is already set so author-supplied tooltip
  // templates / runtime-installed formatters still win.
  function __ensureTooltipDecimalCap(opt){
    if (!opt || typeof opt !== 'object') return;
    var tt = opt.tooltip;
    if (!tt || typeof tt !== 'object') return;
    if (tt.formatter) return;
    if (tt.valueFormatter) return;
    var cap = __MAX_DEC;
    tt.valueFormatter = function(v){
      if (v == null) return '';
      if (typeof v === 'string') return v;
      if (Array.isArray(v)) {
        var out = [];
        for (var i = 0; i < v.length; i++){
          var x = v[i];
          if (x == null) { out.push(''); continue; }
          var nx = +x;
          if (isNaN(nx)) { out.push(String(x)); continue; }
          var sx = nx.toFixed(cap);
          if (sx.indexOf('.') >= 0) sx = sx.replace(/0+$/, '').replace(/\.$/, '');
          out.push(sx);
        }
        return out.join(', ');
      }
      var n = +v;
      if (isNaN(n)) return String(v);
      var s = n.toFixed(cap);
      if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
      return s;
    };
  }

  // Revive string-encoded JS functions into real functions before any
  // setOption call. The editor uses this for every mutation + reset path.
  function _isFnStr(s) {
    return typeof s === 'string' && /^\s*function\s*\(/.test(s);
  }
  function reviveFns(x) {
    if (x == null) return x;
    if (_isFnStr(x)) {
      try { return new Function('return (' + x + ')')(); }
      catch(e) { return x; }
    }
    if (Array.isArray(x)) {
      for (var i = 0; i < x.length; i++) x[i] = reviveFns(x[i]);
      return x;
    }
    if (typeof x === 'object') {
      for (var k in x) {
        if (Object.prototype.hasOwnProperty.call(x, k)) {
          x[k] = reviveFns(x[k]);
        }
      }
    }
    return x;
  }

  var state = {
    originalOption: JSON.parse(JSON.stringify(PAYLOAD.option)),
    option: JSON.parse(JSON.stringify(PAYLOAD.option)),
    chart: null,
    theme: PAYLOAD.theme,
    palette: PAYLOAD.palette,
    dimension: PAYLOAD.dimension,
    chartType: PAYLOAD.chartType,
    chartId: PAYLOAD.chartId,
    knobDefs: PAYLOAD.knobDefs,
    knobValues: {},
    sheets: PAYLOAD.sheets || {},
    activeSheet: PAYLOAD.activeSheet || '',
    sheetsKey: PAYLOAD.sheetsKey || 'echart_studio_sheets',
    prefKey: PAYLOAD.prefKey || ('echart_studio_prefs_' + PAYLOAD.chartType),
    paletteColors: PAYLOAD.paletteColors,
    paletteKind: PAYLOAD.paletteKind,
    themes: PAYLOAD.themes,
    palettes: PAYLOAD.palettes,
    dimensions: PAYLOAD.dimensions,
    typographyOverrides: PAYLOAD.typographyOverrides,
    version: PAYLOAD.version
  };

  // register themes
  try {
    Object.keys(state.themes || {}).forEach(function(tn){
      try { echarts.registerTheme(tn, state.themes[tn]); } catch(e){}
    });
  } catch(e){}

  // ------------------------------------------------------------------
  // APPLY FUNCTIONS
  // ------------------------------------------------------------------
  var APPLY = {};

  function getPath(obj, path){
    var parts = path.split('.'); var o = obj;
    for (var i=0;i<parts.length;i++){
      if (o == null) return undefined;
      var p = parts[i];
      var m = p.match(/^(.*)\[(\d+)\]$/);
      if (m){ o = o[m[1]]; if (o == null) return undefined; o = o[parseInt(m[2])]; }
      else { o = o[p]; }
    }
    return o;
  }
  function setPath(obj, path, val){
    var parts = path.split('.'); var o = obj;
    for (var i=0;i<parts.length-1;i++){
      var p = parts[i];
      var m = p.match(/^(.*)\[(\d+)\]$/);
      if (m){
        var arr = o[m[1]]; if (arr == null) { arr = []; o[m[1]] = arr; }
        var idx = parseInt(m[2]); if (arr[idx] == null) arr[idx] = {};
        o = arr[idx];
      } else {
        if (o[p] == null || typeof o[p] !== 'object' || Array.isArray(o[p])) o[p] = (typeof o[p] === 'object' && o[p] !== null) ? o[p] : {};
        o = o[p];
      }
    }
    var last = parts[parts.length-1];
    var mm = last.match(/^(.*)\[(\d+)\]$/);
    if (mm){ var arr2 = o[mm[1]] || (o[mm[1]] = []); arr2[parseInt(mm[2])] = val; }
    else { o[last] = val; }
  }

  // Title/subtitle
  APPLY.setTitleText = function(v){ setPath(state.option, 'title.text', v || ''); };
  APPLY.setSubtitleText = function(v){ setPath(state.option, 'title.subtext', v || ''); };

  // Legend position. All 'top*' positions sit at y=42 (row 2) so the
  // legend has its own row below the title/toolbox (row 1, y=0..30) and
  // never collides with either, regardless of chart width or the number
  // of legend entries.
  APPLY.setLegendPosition = function(v){
    var leg = state.option.legend || {}; state.option.legend = leg;
    ['top','bottom','left','right'].forEach(function(k){ delete leg[k]; });
    if (v === 'top') { leg.top = 42; leg.left = 'center'; }
    else if (v === 'bottom') { leg.bottom = 'bottom'; leg.left = 'center'; }
    else if (v === 'left') { leg.left = 'left'; leg.top = 'middle'; leg.orient = 'vertical'; }
    else if (v === 'right') { leg.right = 'right'; leg.top = 'middle'; leg.orient = 'vertical'; }
    else if (v === 'top-left') { leg.top = 42; leg.left = 'left'; }
    else if (v === 'top-right') { leg.top = 42; leg.right = 10; }
    else if (v === 'bottom-left') { leg.bottom = 'bottom'; leg.left = 'left'; }
    else if (v === 'bottom-right') { leg.bottom = 'bottom'; leg.right = 'right'; }
  };

  // Axis label / name sizes
  function forEachAxis(cb){
    ['xAxis','yAxis'].forEach(function(k){
      var ax = state.option[k]; if (!ax) return;
      if (Array.isArray(ax)) ax.forEach(cb); else cb(ax);
    });
  }
  APPLY.setAxisLabelSize = function(v){ forEachAxis(function(a){
    a.axisLabel = a.axisLabel || {}; a.axisLabel.fontSize = v;
  });};
  APPLY.setAxisNameSize = function(v){ forEachAxis(function(a){
    a.nameTextStyle = a.nameTextStyle || {}; a.nameTextStyle.fontSize = v;
  });};

  function xAxes(){ var a = state.option.xAxis; if (!a) return []; return Array.isArray(a)?a:[a]; }
  function yAxes(){ var a = state.option.yAxis; if (!a) return []; return Array.isArray(a)?a:[a]; }
  function onEachAxis(axisList, cb){ axisList.forEach(cb); }

  function applyBoundaryGap(axisList, v){
    axisList.forEach(function(a){
      if (v === 'default') delete a.boundaryGap;
      else if (v === 'true') a.boundaryGap = true;
      else if (v === 'false') a.boundaryGap = false;
    });
  }
  function tryNumber(v){ if (v === '' || v == null) return undefined; var n = Number(v); return isFinite(n) ? n : v; }
  function setMin(axisList, v){ axisList.forEach(function(a){ if (v === '' || v == null) delete a.min; else a.min = tryNumber(v); }); }
  function setMax(axisList, v){ axisList.forEach(function(a){ if (v === '' || v == null) delete a.max; else a.max = tryNumber(v); }); }
  APPLY.setXMin = function(v){ setMin(xAxes(), v); };
  APPLY.setXMax = function(v){ setMax(xAxes(), v); };
  APPLY.setYMin = function(v){ setMin(yAxes(), v); };
  APPLY.setYMax = function(v){ setMax(yAxes(), v); };
  APPLY.setXBoundaryGap = function(v){ applyBoundaryGap(xAxes(), v); };
  APPLY.setYBoundaryGap = function(v){ applyBoundaryGap(yAxes(), v); };
  APPLY.setXSplitLineColor = function(v){ xAxes().forEach(function(a){ a.splitLine = a.splitLine || {}; a.splitLine.lineStyle = a.splitLine.lineStyle || {}; a.splitLine.lineStyle.color = v; }); };
  APPLY.setYSplitLineColor = function(v){ yAxes().forEach(function(a){ a.splitLine = a.splitLine || {}; a.splitLine.lineStyle = a.splitLine.lineStyle || {}; a.splitLine.lineStyle.color = v; }); };
  APPLY.setXAxisLabelFormat = function(v){ xAxes().forEach(function(a){
    a.axisLabel = a.axisLabel || {};
    if (!v){ delete a.axisLabel.formatter; return; }
    a.axisLabel.formatter = v;
  });};
  APPLY.setYAxisLabelFormat = function(v){ yAxes().forEach(function(a){
    a.axisLabel = a.axisLabel || {};
    if (!v){ delete a.axisLabel.formatter; return; }
    a.axisLabel.formatter = v;
  });};

  // Toolbox feature toggles
  function toolboxFeat(){ state.option.toolbox = state.option.toolbox || {show:true, feature:{}}; state.option.toolbox.feature = state.option.toolbox.feature || {}; return state.option.toolbox.feature; }
  APPLY.setToolboxSaveAsImage = function(v){ var f = toolboxFeat(); if (v) f.saveAsImage = f.saveAsImage || {}; else delete f.saveAsImage; };
  APPLY.setToolboxDataZoom = function(v){ var f = toolboxFeat(); if (v) f.dataZoom = f.dataZoom || {}; else delete f.dataZoom; };
  APPLY.setToolboxRestore = function(v){ var f = toolboxFeat(); if (v) f.restore = f.restore || {}; else delete f.restore; };
  APPLY.setToolboxDataView = function(v){ var f = toolboxFeat(); if (v) f.dataView = f.dataView || {}; else delete f.dataView; };
  APPLY.setToolboxMagicType = function(v){ var f = toolboxFeat(); if (v) f.magicType = {type:['line','bar']}; else delete f.magicType; };
  APPLY.setToolboxBrush = function(v){ var f = toolboxFeat(); if (v) f.brush = {type:['rect','polygon','lineX','clear']}; else delete f.brush; };

  // DataZoom
  function dzFind(kind){
    var dz = state.option.dataZoom;
    if (!dz) return -1;
    if (!Array.isArray(dz)) dz = [dz];
    for (var i=0;i<dz.length;i++) if (dz[i] && dz[i].type === kind) return i;
    return -1;
  }
  function dzEnsure(){ if (!state.option.dataZoom) state.option.dataZoom = [];
    if (!Array.isArray(state.option.dataZoom)) state.option.dataZoom = [state.option.dataZoom]; }
  APPLY.setDataZoomShow = function(v){
    dzEnsure();
    var idx = dzFind('slider');
    if (v){ if (idx < 0) state.option.dataZoom.push({type:'slider'}); }
    else { if (idx >= 0) state.option.dataZoom.splice(idx,1); }
  };
  APPLY.setDataZoomInside = function(v){
    dzEnsure();
    var idx = dzFind('inside');
    if (v){ if (idx < 0) state.option.dataZoom.push({type:'inside'}); }
    else { if (idx >= 0) state.option.dataZoom.splice(idx,1); }
  };
  APPLY.setDataZoomStart = function(v){ dzEnsure(); state.option.dataZoom.forEach(function(d){ d.start = v; }); };
  APPLY.setDataZoomEnd = function(v){ dzEnsure(); state.option.dataZoom.forEach(function(d){ d.end = v; }); };
  APPLY.setDataZoomOrient = function(v){ dzEnsure(); state.option.dataZoom.forEach(function(d){ d.orient = v; }); };

  // Mark helpers
  function mainSeries(){
    var s = state.option.series; if (!s) return [];
    if (!Array.isArray(s)) return [s];
    return s;
  }
  function seriesOfType(t){ return mainSeries().filter(function(s){ return s.type === t; }); }

  // Line
  APPLY.setLineWidth = function(v){ seriesOfType('line').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.width = v; }); };
  APPLY.setLineSmooth = function(v){ seriesOfType('line').forEach(function(s){ s.smooth = !!v; }); };
  APPLY.setLineStep = function(v){ seriesOfType('line').forEach(function(s){ if (v === 'none') delete s.step; else s.step = v; }); };
  APPLY.setLineConnectNulls = function(v){ seriesOfType('line').forEach(function(s){ s.connectNulls = !!v; }); };
  APPLY.setLineShowSymbol = function(v){ seriesOfType('line').forEach(function(s){ s.showSymbol = !!v; }); };
  APPLY.setLineSymbolSize = function(v){ seriesOfType('line').forEach(function(s){ s.symbolSize = v; }); };
  APPLY.setLineAreaFill = function(v){ seriesOfType('line').forEach(function(s){ if (v){ s.areaStyle = s.areaStyle || {opacity:0.3}; } else delete s.areaStyle; }); };
  APPLY.setLineAreaOpacity = function(v){ seriesOfType('line').forEach(function(s){ if (s.areaStyle){ s.areaStyle.opacity = v; } }); };
  APPLY.setLineStack = function(v){ seriesOfType('line').forEach(function(s){ if (v) s.stack = 'total'; else delete s.stack; }); };
  APPLY.setLineStyleType = function(v){ seriesOfType('line').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.type = v; }); };

  // Bar
  APPLY.setBarWidth = function(v){ seriesOfType('bar').forEach(function(s){ if (v === '' || v == null) delete s.barWidth; else s.barWidth = v; }); };
  APPLY.setBarMaxWidth = function(v){ seriesOfType('bar').forEach(function(s){ if (v === '' || v == null) delete s.barMaxWidth; else s.barMaxWidth = v; }); };
  APPLY.setBarCategoryGap = function(v){ seriesOfType('bar').forEach(function(s){ s.barCategoryGap = v; }); };
  APPLY.setBarGap = function(v){ seriesOfType('bar').forEach(function(s){ s.barGap = v; }); };
  APPLY.setBarBorderRadius = function(v){ seriesOfType('bar').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderRadius = v; }); };
  APPLY.setBarOpacity = function(v){ seriesOfType('bar').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.opacity = v; }); };
  APPLY.setBarStack = function(v){ seriesOfType('bar').forEach(function(s){ if (v) s.stack = 'total'; else delete s.stack; }); };
  APPLY.setBarLabelShow = function(v){ seriesOfType('bar').forEach(function(s){ s.label = s.label || {}; s.label.show = !!v; }); };
  APPLY.setBarLabelPosition = function(v){ seriesOfType('bar').forEach(function(s){ s.label = s.label || {}; s.label.position = v; }); };

  // Scatter
  APPLY.setScatterSymbolSize = function(v){ seriesOfType('scatter').forEach(function(s){ s.symbolSize = v; }); };
  APPLY.setScatterSymbol = function(v){ seriesOfType('scatter').forEach(function(s){ s.symbol = v; }); };
  APPLY.setScatterOpacity = function(v){ seriesOfType('scatter').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.opacity = v; }); };
  APPLY.setScatterBorderWidth = function(v){ seriesOfType('scatter').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderWidth = v; }); };

  // Area (lines with areaStyle; we also cover pure area by piggybacking on setLineArea*)
  APPLY.setAreaOpacity = function(v){ seriesOfType('line').forEach(function(s){ if (s.areaStyle){ s.areaStyle.opacity = v; } }); };
  APPLY.setAreaStack = function(v){ seriesOfType('line').forEach(function(s){ if (v) s.stack = 'total'; else delete s.stack; }); };
  APPLY.setAreaLineWidth = function(v){ seriesOfType('line').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.width = v; }); };
  APPLY.setAreaSmooth = function(v){ seriesOfType('line').forEach(function(s){ s.smooth = !!v; }); };

  // Heatmap
  // ECharts heatmap doesn't evaluate label.color as a callback, so
  // auto-contrast routes through label.rich + a formatter that wraps
  // values in '{l|...}' (light bg -> dark text) or '{d|...}' based on
  // params.color luminance. setHeatmapAutoContrast(true) installs the
  // wrapping formatter; (false) strips the wrap so values render with
  // a single color (the built-in label.color or the ECharts default).
  function _heatmapValueDecimalsFor(s){
    // Heuristic: detect from the existing formatter string; default 1.
    // Cap at the global decimal limit so a user-supplied formatter that
    // accidentally encodes more precision than the runtime allows still
    // produces a label-block within bounds when we re-render it.
    var f = s && s.label && s.label.formatter;
    if (typeof f === 'function') f = f.toString();
    if (typeof f === 'string'){
      var m = f.match(/toFixed\(\s*(\d+)\s*\)/);
      if (m) return __capDec(+m[1], 1);
    }
    return __capDec(1, 1);
  }
  function _heatmapValueIndexFor(s){
    // Calendar heatmap data is [date, value] (idx 1); regular heatmap
    // is [xIdx, yIdx, value] (idx 2). Coordinate system flag is the
    // most reliable indicator.
    return s && s.coordinateSystem === 'calendar' ? 1 : 2;
  }
  function _heatmapMakeContrastFormatter(decimals, valueIdx){
    var dec = __capDec(decimals, 1);
    return function(p){
      var v = null; var d = p && p.data;
      if (d != null && d.value != null){
        v = Array.isArray(d.value) ? d.value[valueIdx] : d.value;
      } else if (Array.isArray(d)){
        v = d[valueIdx];
      } else if (d != null){ v = d; }
      if (v == null || isNaN(+v)) return '';
      var c = p && p.color; var r = 128, g = 128, b = 128;
      if (typeof c === 'string'){
        if (c.charAt(0) === '#'){
          if (c.length === 4){
            r = parseInt(c.charAt(1) + c.charAt(1), 16);
            g = parseInt(c.charAt(2) + c.charAt(2), 16);
            b = parseInt(c.charAt(3) + c.charAt(3), 16);
          } else if (c.length >= 7){
            r = parseInt(c.substr(1, 2), 16);
            g = parseInt(c.substr(3, 2), 16);
            b = parseInt(c.substr(5, 2), 16);
          }
        } else if (c.indexOf('rgb') === 0){
          var m = c.match(/[\d\.]+/g);
          if (m && m.length >= 3){ r = +m[0]; g = +m[1]; b = +m[2]; }
        }
      }
      function _L(x){ x /= 255; return x <= 0.03928 ? x / 12.92
        : Math.pow((x + 0.055) / 1.055, 2.4); }
      var L = 0.2126 * _L(r) + 0.7152 * _L(g) + 0.0722 * _L(b);
      var s = L > 0.5 ? 'l' : 'd';
      return '{' + s + '|' + (+v).toFixed(dec) + '}';
    };
  }
  function _heatmapMakePlainFormatter(decimals, valueIdx){
    var dec = __capDec(decimals, 1);
    return function(p){
      var v = null; var d = p && p.data;
      if (d != null && d.value != null){
        v = Array.isArray(d.value) ? d.value[valueIdx] : d.value;
      } else if (Array.isArray(d)){
        v = d[valueIdx];
      } else if (d != null){ v = d; }
      if (v == null || isNaN(+v)) return '';
      return (+v).toFixed(dec);
    };
  }
  APPLY.setHeatmapShowLabels = function(v){ seriesOfType('heatmap').forEach(function(s){ s.label = s.label || {}; s.label.show = !!v; }); };
  APPLY.setHeatmapAutoContrast = function(v){ seriesOfType('heatmap').forEach(function(s){
    s.label = s.label || {};
    var fontSize = +(s.label.fontSize || 11);
    var dec = _heatmapValueDecimalsFor(s);
    var vi  = _heatmapValueIndexFor(s);
    if (v){
      s.label.formatter = _heatmapMakeContrastFormatter(dec, vi);
      s.label.rich = {
        l: {color: '#111', fontSize: fontSize},
        d: {color: '#fff', fontSize: fontSize}
      };
      delete s.label.color;
    } else {
      s.label.formatter = _heatmapMakePlainFormatter(dec, vi);
      delete s.label.rich;
    }
  }); };
  APPLY.setHeatmapBorderWidth = function(v){ seriesOfType('heatmap').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderWidth = v; }); };

  // Pie
  APPLY.setPieInnerRadius = function(v){ seriesOfType('pie').forEach(function(s){ var r = s.radius || ['0%','75%']; if (!Array.isArray(r)) r = ['0%', r]; r[0] = v; s.radius = r; }); };
  APPLY.setPieOuterRadius = function(v){ seriesOfType('pie').forEach(function(s){ var r = s.radius || ['0%','75%']; if (!Array.isArray(r)) r = ['0%', r]; r[1] = v; s.radius = r; }); };
  APPLY.setPieRoseType = function(v){ seriesOfType('pie').forEach(function(s){ if (v === 'none') delete s.roseType; else s.roseType = v; }); };
  APPLY.setPieLabelShow = function(v){ seriesOfType('pie').forEach(function(s){ s.label = s.label || {}; s.label.show = !!v; }); };
  APPLY.setPieLabelPosition = function(v){ seriesOfType('pie').forEach(function(s){ s.label = s.label || {}; s.label.position = v; }); };
  APPLY.setPieLabelLine = function(v){ seriesOfType('pie').forEach(function(s){ s.labelLine = s.labelLine || {}; s.labelLine.show = !!v; }); };
  APPLY.setPieBorderRadius = function(v){ seriesOfType('pie').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderRadius = v; }); };

  // Boxplot
  APPLY.setBoxBorderWidth = function(v){ seriesOfType('boxplot').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderWidth = v; }); };
  APPLY.setBoxItemWidth = function(v){ seriesOfType('boxplot').forEach(function(s){ s.boxWidth = [Math.max(1,v/2), v]; }); };

  // Sankey
  APPLY.setSankeyNodeWidth = function(v){ seriesOfType('sankey').forEach(function(s){ s.nodeWidth = v; }); };
  APPLY.setSankeyNodeGap = function(v){ seriesOfType('sankey').forEach(function(s){ s.nodeGap = v; }); };
  APPLY.setSankeyOrient = function(v){ seriesOfType('sankey').forEach(function(s){ s.orient = v; }); };
  APPLY.setSankeyLinkOpacity = function(v){ seriesOfType('sankey').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.opacity = v; }); };
  APPLY.setSankeyLinkCurveness = function(v){ seriesOfType('sankey').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.curveness = v; }); };
  APPLY.setSankeyDraggable = function(v){ seriesOfType('sankey').forEach(function(s){ s.draggable = !!v; }); };

  // Treemap / sunburst
  APPLY.setTreemapLeafDepth = function(v){ seriesOfType('treemap').forEach(function(s){ s.leafDepth = v; }); };
  APPLY.setTreemapRoam = function(v){ seriesOfType('treemap').forEach(function(s){ s.roam = !!v; }); };
  APPLY.setTreemapNodeClick = function(v){ seriesOfType('treemap').forEach(function(s){ if (v === 'false') s.nodeClick = false; else s.nodeClick = v; }); };
  APPLY.setSunburstInnerRadius = function(v){ seriesOfType('sunburst').forEach(function(s){ var r = s.radius || ['0%','90%']; if (!Array.isArray(r)) r = ['0%', r]; r[0] = v; s.radius = r; }); };
  APPLY.setSunburstOuterRadius = function(v){ seriesOfType('sunburst').forEach(function(s){ var r = s.radius || ['0%','90%']; if (!Array.isArray(r)) r = ['0%', r]; r[1] = v; s.radius = r; }); };
  APPLY.setSunburstHighlightPolicy = function(v){ seriesOfType('sunburst').forEach(function(s){ s.emphasis = s.emphasis || {}; s.emphasis.focus = v === 'none' ? undefined : v; }); };

  // Graph
  APPLY.setGraphLayout = function(v){ seriesOfType('graph').forEach(function(s){ s.layout = v; }); };
  APPLY.setGraphRoam = function(v){ seriesOfType('graph').forEach(function(s){ s.roam = !!v; }); };
  APPLY.setGraphRepulsion = function(v){ seriesOfType('graph').forEach(function(s){ s.force = s.force || {}; s.force.repulsion = v; }); };
  APPLY.setGraphEdgeLength = function(v){ seriesOfType('graph').forEach(function(s){ s.force = s.force || {}; s.force.edgeLength = v; }); };
  APPLY.setGraphEdgeSymbol = function(v){ seriesOfType('graph').forEach(function(s){ if (v === 'none') s.edgeSymbol = ['none','none']; else s.edgeSymbol = ['none', v]; }); };
  APPLY.setGraphDraggable = function(v){ seriesOfType('graph').forEach(function(s){ s.draggable = !!v; }); };

  // Candlestick
  APPLY.setCandleBullColor = function(v){ seriesOfType('candlestick').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.color = v; }); };
  APPLY.setCandleBearColor = function(v){ seriesOfType('candlestick').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.color0 = v; }); };
  APPLY.setCandleBorderBull = function(v){ seriesOfType('candlestick').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderColor = v; }); };
  APPLY.setCandleBorderBear = function(v){ seriesOfType('candlestick').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderColor0 = v; }); };

  // Radar
  APPLY.setRadarShape = function(v){ state.option.radar = state.option.radar || {}; state.option.radar.shape = v; };
  APPLY.setRadarSplitNumber = function(v){ state.option.radar = state.option.radar || {}; state.option.radar.splitNumber = v; };
  APPLY.setRadarAreaOpacity = function(v){ seriesOfType('radar').forEach(function(s){ s.areaStyle = s.areaStyle || {}; s.areaStyle.opacity = v; }); };

  // Gauge
  APPLY.setGaugeMin = function(v){ seriesOfType('gauge').forEach(function(s){ s.min = v; }); };
  APPLY.setGaugeMax = function(v){ seriesOfType('gauge').forEach(function(s){ s.max = v; }); };
  APPLY.setGaugeSplitNumber = function(v){ seriesOfType('gauge').forEach(function(s){ s.splitNumber = v; }); };
  APPLY.setGaugeStartAngle = function(v){ seriesOfType('gauge').forEach(function(s){ s.startAngle = v; }); };
  APPLY.setGaugeEndAngle = function(v){ seriesOfType('gauge').forEach(function(s){ s.endAngle = v; }); };

  // Calendar
  APPLY.setCalendarOrient = function(v){ state.option.calendar = state.option.calendar || {}; state.option.calendar.orient = v; };
  APPLY.setCalendarCellSize = function(v){ state.option.calendar = state.option.calendar || {}; state.option.calendar.cellSize = ['auto', v]; };
  APPLY.setCalendarYearLabel = function(v){ state.option.calendar = state.option.calendar || {}; state.option.calendar.yearLabel = state.option.calendar.yearLabel || {}; state.option.calendar.yearLabel.show = !!v; };

  // Parallel coords
  APPLY.setParallelLineOpacity = function(v){ seriesOfType('parallel').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.opacity = v; }); };
  APPLY.setParallelLineWidth = function(v){ seriesOfType('parallel').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.width = v; }); };
  APPLY.setParallelLayoutHorizontal = function(v){ state.option.parallel = state.option.parallel || {}; state.option.parallel.layout = v ? 'horizontal' : 'vertical'; };

  // Funnel
  APPLY.setFunnelSort = function(v){ seriesOfType('funnel').forEach(function(s){ s.sort = v === 'none' ? undefined : v; }); };
  APPLY.setFunnelGap = function(v){ seriesOfType('funnel').forEach(function(s){ s.gap = v; }); };
  APPLY.setFunnelMin = function(v){ seriesOfType('funnel').forEach(function(s){ s.min = v; }); };
  APPLY.setFunnelMax = function(v){ seriesOfType('funnel').forEach(function(s){ s.max = v; }); };
  APPLY.setFunnelLabelShow = function(v){ seriesOfType('funnel').forEach(function(s){ s.label = s.label || {}; s.label.show = !!v; }); };

  // Tree
  APPLY.setTreeOrient = function(v){ seriesOfType('tree').forEach(function(s){ s.orient = v; s.layout = v === 'radial' ? 'radial' : 'orthogonal'; }); };
  APPLY.setTreeSymbolSize = function(v){ seriesOfType('tree').forEach(function(s){ s.symbolSize = v; }); };
  APPLY.setTreeRoam = function(v){ seriesOfType('tree').forEach(function(s){ s.roam = !!v; }); };

  // ------------------------------------------------------------------
  // KNOB RENDERING + WIRING
  // ------------------------------------------------------------------

  function applyKnob(def, val){
    state.knobValues[def.name] = val;
    if (def.apply){
      var fn = APPLY[def.apply];
      if (typeof fn === 'function') fn(val);
    } else if (def.path){
      setPath(state.option, def.path, val);
    }
  }

  function renderKnob(def){
    var row = document.createElement('div'); row.className = 'knob'; row.dataset.knob = def.name;
    var lab = document.createElement('label'); lab.textContent = def.label; lab.title = def.name;
    row.appendChild(lab);
    var val = state.knobValues[def.name];
    if (val === undefined) val = def.default;
    var input;
    if (def.type === 'range'){
      input = document.createElement('input'); input.type = 'range';
      input.min = def.min; input.max = def.max; input.step = def.step;
      input.value = val;
      var valSpan = document.createElement('span'); valSpan.className = 'val'; valSpan.textContent = val;
      input.addEventListener('input', function(){
        var v = Number(input.value); valSpan.textContent = v;
        applyKnob(def, v); render();
      });
      row.appendChild(input); row.appendChild(valSpan);
    } else if (def.type === 'number'){
      input = document.createElement('input'); input.type = 'number'; input.value = val;
      input.addEventListener('input', function(){ var v = Number(input.value); applyKnob(def, v); render(); });
      row.appendChild(input);
    } else if (def.type === 'select'){
      input = document.createElement('select');
      (def.options || []).forEach(function(o){ var op = document.createElement('option'); op.value = o; op.textContent = o; input.appendChild(op); });
      input.value = val;
      input.addEventListener('change', function(){ applyKnob(def, input.value); render(); });
      row.appendChild(input);
    } else if (def.type === 'checkbox'){
      input = document.createElement('input'); input.type = 'checkbox'; input.checked = !!val;
      input.addEventListener('change', function(){ applyKnob(def, input.checked); render(); });
      row.appendChild(input);
    } else if (def.type === 'color'){
      input = document.createElement('input'); input.type = 'color'; input.value = val || '#000000';
      input.addEventListener('input', function(){ applyKnob(def, input.value); render(); });
      row.appendChild(input);
    } else {
      input = document.createElement('input'); input.type = 'text'; input.value = val == null ? '' : val;
      input.addEventListener('change', function(){ applyKnob(def, input.value); render(); });
      row.appendChild(input);
    }
    return row;
  }

  function groupedKnobs(){
    var groups = {};
    (state.knobDefs || []).forEach(function(def){
      var g = def.group || 'Other';
      groups[g] = groups[g] || [];
      groups[g].push(def);
    });
    return groups;
  }

  function renderKnobCards(){
    var wrap = document.getElementById('knob-cards');
    wrap.innerHTML = '';
    // Presets card
    var presets = document.createElement('details'); presets.className = 'card'; presets.open = true;
    var psum = document.createElement('summary'); psum.textContent = 'Presets'; presets.appendChild(psum);
    presets.appendChild(makePresetRow('Theme', Object.keys(state.themes), state.theme, function(v){ state.theme = v; applyTheme(v); render(); rerenderKnobs(); }));
    var paletteNames = Object.keys(state.palettes);
    presets.appendChild(makePresetRow('Palette', paletteNames, state.palette, function(v){ state.palette = v; applyPalette(v); render(); }));
    presets.appendChild(makePresetRow('Dimensions', Object.keys(state.dimensions), state.dimension, function(v){ state.dimension = v; applyDimension(v); render(); rerenderKnobs(); }));
    wrap.appendChild(presets);

    // Essentials card
    var ess = document.createElement('details'); ess.className = 'card'; ess.open = true;
    var esum = document.createElement('summary'); esum.textContent = 'Essentials'; ess.appendChild(esum);
    (state.knobDefs || []).forEach(function(d){ if (d.essential || ESSENTIALS[d.name]) ess.appendChild(renderKnob(d)); });
    wrap.appendChild(ess);

    // Other groups
    var grouped = groupedKnobs();
    var order = ['Title','Typography','Layout','Grid','XAxis','YAxis','Legend','Tooltip','Toolbox','DataZoom','VisualMap','Interactivity','Mark','Colors'];
    var seen = {};
    order.forEach(function(g){
      if (!grouped[g]) return; seen[g] = true;
      var d = document.createElement('details'); d.className = 'card'; d.open = false;
      var sum = document.createElement('summary'); sum.textContent = g; d.appendChild(sum);
      grouped[g].forEach(function(def){ d.appendChild(renderKnob(def)); });
      wrap.appendChild(d);
    });
    Object.keys(grouped).forEach(function(g){
      if (seen[g]) return;
      var d = document.createElement('details'); d.className = 'card'; d.open = false;
      var sum = document.createElement('summary'); sum.textContent = g; d.appendChild(sum);
      grouped[g].forEach(function(def){ d.appendChild(renderKnob(def)); });
      wrap.appendChild(d);
    });

    // Session Prefs card
    var sp = document.createElement('details'); sp.className = 'card';
    var spSum = document.createElement('summary'); spSum.textContent = 'Session preferences'; sp.appendChild(spSum);
    var resetBtn = document.createElement('button'); resetBtn.textContent = 'Reset to theme defaults';
    resetBtn.addEventListener('click', function(){ resetToTheme(); });
    sp.appendChild(resetBtn);
    wrap.appendChild(sp);

    document.getElementById('knob-count').textContent = (state.knobDefs || []).length + ' knobs';
  }

  var ESSENTIALS = ESSENTIAL_NAMES;

  function makePresetRow(label, options, current, onChange){
    var row = document.createElement('div'); row.className = 'knob';
    var l = document.createElement('label'); l.textContent = label; row.appendChild(l);
    var sel = document.createElement('select');
    options.forEach(function(o){ var op = document.createElement('option'); op.value = o; op.textContent = o; sel.appendChild(op); });
    sel.value = current;
    sel.addEventListener('change', function(){ onChange(sel.value); });
    row.appendChild(sel); return row;
  }

  function applyTheme(name){
    state.theme = name;
    var theme = state.themes[name];
    if (theme && theme.color){ state.option.color = theme.color.slice(); }
    var kv = THEME_KNOB_VALUES[name] || {};
    Object.keys(kv).forEach(function(n){
      var def = KNOB_INDEX[n]; if (!def) return;
      applyKnob(def, kv[n]);
    });
  }

  function applyPalette(name){
    var p = state.palettes[name];
    if (!p) return;
    state.paletteColors = p.colors;
    state.paletteKind = p.kind;
    if (p.kind === 'categorical'){
      state.option.color = p.colors.slice();
    } else {
      // sequential/diverging -> visualMap ramp if present
      if (state.option.visualMap){
        var vm = state.option.visualMap;
        if (!Array.isArray(vm)) vm = [vm];
        vm.forEach(function(v){ v.inRange = {color: p.colors.slice()}; });
        state.option.visualMap = vm;
      }
    }
  }

  function applyDimension(name){
    var dim = state.dimensions[name]; if (!dim) return;
    var chartEl = document.getElementById('chart');
    chartEl.style.width = dim.width + 'px';
    chartEl.style.height = dim.height + 'px';
    state.chart && state.chart.resize();
    // typography override
    var to = state.typographyOverrides[name];
    if (to){
      Object.keys(to).forEach(function(k){
        var def = KNOB_INDEX[k]; if (!def) return;
        applyKnob(def, to[k]);
      });
    }
  }

  function resetToTheme(){
    state.option = JSON.parse(JSON.stringify(state.originalOption));
    state.knobValues = {};
    applyTheme(state.theme);
    render(); rerenderKnobs();
  }

  function rerenderKnobs(){
    renderKnobCards();
    filterKnobs(document.getElementById('knob-search').value || '');
  }

  function filterKnobs(q){
    q = q.toLowerCase();
    document.querySelectorAll('.knob').forEach(function(row){
      var label = row.querySelector('label');
      var name = row.dataset.knob || '';
      var text = (label ? label.textContent : '') + ' ' + name;
      row.style.display = (!q || text.toLowerCase().indexOf(q) >= 0) ? 'flex' : 'none';
    });
  }

  // Index knob defs by name
  var KNOB_INDEX = {};
  (state.knobDefs || []).forEach(function(d){ KNOB_INDEX[d.name] = d; });
  var THEME_KNOB_VALUES = PAYLOAD.themeKnobValues;

  // ------------------------------------------------------------------
  // CHART RENDERING
  // ------------------------------------------------------------------

  function render(){
    if (!state.chart){
      state.chart = echarts.init(document.getElementById('chart'), state.theme in state.themes ? state.theme : null);
    }
    try {
      // Pass through the reviver so renderItem/formatter/filter strings
      // become real functions. state.option is kept as-is so Raw/Code tab
      // still shows the serializable JSON.
      var live = reviveFns(JSON.parse(JSON.stringify(state.option)));
      __ensureTooltipDecimalCap(live);
      state.chart.setOption(live, true);
      document.getElementById('chart-status').textContent = 'ok';
    } catch (e){
      document.getElementById('chart-status').textContent = 'error: ' + (e && e.message || e);
    }
    refreshTabs();
  }

  function refreshTabs(){
    refreshCodeTab(); refreshDataTab(); refreshMetaTab(); refreshExportTab(); refreshRawTab();
  }

  function refreshCodeTab(){
    var el = document.getElementById('tab-code');
    el.innerHTML = '';
    var pre = document.createElement('pre');
    pre.textContent = JSON.stringify(state.option, null, 2);
    var copyBtn = document.createElement('button'); copyBtn.textContent = 'Copy JSON';
    copyBtn.addEventListener('click', function(){
      try { navigator.clipboard.writeText(pre.textContent); copyBtn.textContent = 'copied'; setTimeout(function(){copyBtn.textContent = 'Copy JSON';}, 800); } catch(e){}
    });
    el.appendChild(copyBtn); el.appendChild(pre);
  }

  function extractData(){
    var rows = [];
    (mainSeries() || []).forEach(function(s){
      if (s.data && Array.isArray(s.data)){
        s.data.forEach(function(d){ rows.push({series: s.name || s.type, data: d}); });
      }
    });
    return rows;
  }

  function refreshDataTab(){
    var el = document.getElementById('tab-data');
    el.innerHTML = '';
    var rows = extractData();
    var info = document.createElement('div'); info.textContent = rows.length + ' rows across ' + (mainSeries().length) + ' series';
    el.appendChild(info);
    if (rows.length === 0) return;
    var tbl = document.createElement('table'); tbl.className = 'data';
    var thead = document.createElement('thead'); var trh = document.createElement('tr');
    ['series','value'].forEach(function(h){ var th = document.createElement('th'); th.textContent = h; trh.appendChild(th); });
    thead.appendChild(trh); tbl.appendChild(thead);
    var tbody = document.createElement('tbody');
    rows.slice(0, 500).forEach(function(r){
      var tr = document.createElement('tr');
      var tds = document.createElement('td'); tds.textContent = r.series;
      var tdv = document.createElement('td'); tdv.textContent = JSON.stringify(r.data);
      tr.appendChild(tds); tr.appendChild(tdv); tbody.appendChild(tr);
    });
    tbl.appendChild(tbody); el.appendChild(tbl);
    if (rows.length > 500){
      var more = document.createElement('div'); more.textContent = '(showing first 500 of ' + rows.length + ' rows)';
      el.appendChild(more);
    }
  }

  function refreshMetaTab(){
    var el = document.getElementById('tab-meta');
    el.innerHTML = '';
    var k = ['chart_id','chart_type','theme','palette','dimension'];
    var v = [state.chartId, state.chartType, state.theme, state.palette, state.dimension];
    var dl = document.createElement('dl');
    for (var i=0;i<k.length;i++){
      var dt = document.createElement('dt'); dt.textContent = k[i];
      var dd = document.createElement('dd'); dd.textContent = v[i];
      dl.appendChild(dt); dl.appendChild(dd);
    }
    el.appendChild(dl);
    var series = document.createElement('div');
    series.textContent = 'series types: ' + mainSeries().map(function(s){ return s.type; }).join(', ');
    el.appendChild(series);
  }

  function refreshExportTab(){
    var el = document.getElementById('tab-export');
    el.innerHTML = '';
    var specs = [
      {label: 'PNG 1x', fn: function(){ downloadImage(1, 'png'); }},
      {label: 'PNG 2x', fn: function(){ downloadImage(2, 'png'); }},
      {label: 'PNG 4x', fn: function(){ downloadImage(4, 'png'); }},
      {label: 'SVG', fn: function(){ downloadSvg(); }},
      {label: 'Option JSON', fn: function(){ downloadText('option.json', JSON.stringify(state.option, null, 2)); }},
      {label: 'Spec Sheet JSON', fn: function(){ downloadText('spec_sheet.json', JSON.stringify(exportSheet(), null, 2)); }},
    ];
    specs.forEach(function(s){ var b = document.createElement('button'); b.textContent = s.label; b.addEventListener('click', s.fn); el.appendChild(b); });
  }

  function refreshRawTab(){
    var el = document.getElementById('tab-raw');
    el.innerHTML = '';
    var title = document.createElement('div'); title.textContent = 'Edit ECharts option as JSON. Changes apply on blur.';
    el.appendChild(title);
    var ta = document.createElement('textarea'); ta.className = 'raw';
    ta.value = JSON.stringify(state.option, null, 2);
    ta.addEventListener('blur', function(){
      try {
        var parsed = JSON.parse(ta.value);
        state.option = parsed; render();
        document.getElementById('chart-status').textContent = 'raw applied';
      } catch (e){
        document.getElementById('chart-status').textContent = 'invalid JSON';
      }
    });
    el.appendChild(ta);
  }

  // ------------------------------------------------------------------
  // EXPORT / IO
  // ------------------------------------------------------------------

  function downloadImage(pixelRatio, type){
    var url = state.chart.getDataURL({pixelRatio: pixelRatio, backgroundColor: state.option.backgroundColor || '#fff', type: type});
    var a = document.createElement('a'); a.href = url; a.download = (PAYLOAD.filename || 'chart') + '.' + type; a.click();
  }
  function downloadSvg(){
    var dom = document.getElementById('chart');
    var svg = dom.querySelector('svg');
    if (!svg) { alert('SVG renderer not active. Use PNG.'); return; }
    var xml = new XMLSerializer().serializeToString(svg);
    var blob = new Blob([xml], {type: 'image/svg+xml'});
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = (PAYLOAD.filename || 'chart') + '.svg'; a.click();
  }
  function downloadText(name, text){
    var blob = new Blob([text], {type: 'text/plain'});
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click();
  }

  // ------------------------------------------------------------------
  // SPEC SHEETS (localStorage)
  // ------------------------------------------------------------------

  function loadSheets(){
    try {
      var raw = localStorage.getItem(state.sheetsKey);
      if (raw){ state.sheets = Object.assign({}, state.sheets, JSON.parse(raw)); }
    } catch(e){}
  }
  function saveSheets(){
    try { localStorage.setItem(state.sheetsKey, JSON.stringify(state.sheets)); } catch(e){}
  }
  function refreshSheetDropdown(){
    var sel = document.getElementById('sheet-select');
    sel.innerHTML = '';
    var none = document.createElement('option'); none.value = ''; none.textContent = '(none)'; sel.appendChild(none);
    Object.keys(state.sheets).forEach(function(id){
      var op = document.createElement('option'); op.value = id; op.textContent = state.sheets[id].name || id; sel.appendChild(op);
    });
    sel.value = state.activeSheet || '';
  }
  function exportSheet(){
    return {
      schema_version: 1,
      spec_sheet_id: state.activeSheet || 'unnamed',
      name: state.activeSheet || 'unnamed',
      base_theme: state.theme, base_palette: state.palette,
      base_dimension_preset: state.dimension,
      overrides: Object.assign({}, state.knobValues),
      created_at: new Date().toISOString(), updated_at: new Date().toISOString()
    };
  }
  function applySheet(sheet){
    if (!sheet) return;
    if (sheet.base_theme){ state.theme = sheet.base_theme; applyTheme(sheet.base_theme); }
    if (sheet.base_palette){ state.palette = sheet.base_palette; applyPalette(sheet.base_palette); }
    if (sheet.base_dimension_preset){ state.dimension = sheet.base_dimension_preset; applyDimension(sheet.base_dimension_preset); }
    Object.keys(sheet.overrides || {}).forEach(function(n){
      var def = KNOB_INDEX[n]; if (!def) return;
      applyKnob(def, sheet.overrides[n]);
    });
    render(); rerenderKnobs();
  }

  // ------------------------------------------------------------------
  // WIRE UI
  // ------------------------------------------------------------------

  document.querySelectorAll('.tabs button').forEach(function(b){
    b.addEventListener('click', function(){
      document.querySelectorAll('.tabs button').forEach(function(x){ x.classList.remove('active'); });
      document.querySelectorAll('.tab').forEach(function(x){ x.classList.remove('active'); });
      b.classList.add('active');
      document.getElementById('tab-' + b.dataset.tab).classList.add('active');
    });
  });

  document.getElementById('btn-reset').addEventListener('click', function(){
    state.chart && state.chart.dispatchAction({type: 'restore'});
  });
  document.getElementById('btn-full').addEventListener('click', function(){
    var el = document.getElementById('chart');
    if (document.fullscreenElement) document.exitFullscreen(); else el.requestFullscreen();
  });
  document.getElementById('btn-png2x').addEventListener('click', function(){ downloadImage(2, 'png'); });
  document.getElementById('btn-png4x').addEventListener('click', function(){ downloadImage(4, 'png'); });
  document.getElementById('btn-svg').addEventListener('click', function(){ downloadSvg(); });

  document.getElementById('knob-search').addEventListener('input', function(e){ filterKnobs(e.target.value); });
  document.getElementById('btn-reset-knobs').addEventListener('click', function(){ resetToTheme(); });

  // sheet buttons
  document.getElementById('sheet-save').addEventListener('click', function(){
    var id = state.activeSheet || prompt('Name for this spec sheet:'); if (!id) return;
    var s = exportSheet(); s.spec_sheet_id = id; s.name = id;
    state.sheets[id] = s; state.activeSheet = id; saveSheets(); refreshSheetDropdown();
    document.getElementById('sheet-status').textContent = 'saved';
  });
  document.getElementById('sheet-saveas').addEventListener('click', function(){
    var id = prompt('New sheet name:'); if (!id) return;
    var s = exportSheet(); s.spec_sheet_id = id; s.name = id;
    state.sheets[id] = s; state.activeSheet = id; saveSheets(); refreshSheetDropdown();
  });
  document.getElementById('sheet-delete').addEventListener('click', function(){
    if (!state.activeSheet) return;
    delete state.sheets[state.activeSheet]; state.activeSheet = ''; saveSheets(); refreshSheetDropdown();
  });
  document.getElementById('sheet-download').addEventListener('click', function(){
    downloadText((state.activeSheet || 'spec_sheet') + '.json', JSON.stringify(exportSheet(), null, 2));
  });
  document.getElementById('sheet-upload').addEventListener('click', function(){
    document.getElementById('sheet-upload-file').click();
  });
  document.getElementById('sheet-upload-file').addEventListener('change', function(e){
    var f = e.target.files[0]; if (!f) return;
    var fr = new FileReader();
    fr.onload = function(){
      try {
        var s = JSON.parse(fr.result);
        var id = s.spec_sheet_id || s.name || ('sheet_' + Date.now());
        state.sheets[id] = s; state.activeSheet = id; saveSheets(); refreshSheetDropdown();
        applySheet(s);
      } catch(err){ alert('bad JSON'); }
    };
    fr.readAsText(f);
  });
  document.getElementById('sheet-select').addEventListener('change', function(e){
    state.activeSheet = e.target.value;
    if (state.activeSheet){ applySheet(state.sheets[state.activeSheet]); }
    else { resetToTheme(); }
  });

  // init
  loadSheets(); refreshSheetDropdown();
  renderKnobCards();
  filterKnobs('');
  render();
  if (state.activeSheet && state.sheets[state.activeSheet]) applySheet(state.sheets[state.activeSheet]);
})();
"""


def _essential_names_map() -> Dict[str, bool]:
    from echart_studio import ESSENTIAL_NAMES
    return {n: True for n in ESSENTIAL_NAMES}


def _themes_for_js() -> Dict[str, Any]:
    """Return a name -> ECharts theme object map for registerTheme."""
    return {name: theme["echarts"] for name, theme in THEMES.items()}


def _theme_knob_values_for_js() -> Dict[str, Dict[str, Any]]:
    return {name: dict(theme["knob_values"]) for name, theme in THEMES.items()}


def _palettes_for_js() -> Dict[str, Any]:
    return {name: {"colors": list(p["colors"]), "kind": p["kind"]}
            for name, p in PALETTES.items()}


def _dimensions_for_js() -> Dict[str, Any]:
    return {name: {"width": d["width"], "height": d["height"]}
            for name, d in DIMENSION_PRESETS.items()}


def render_editor_html(
    option: Dict[str, Any],
    chart_id: str,
    chart_type: str,
    theme: str,
    palette: str,
    dimension_preset: str,
    knob_defs: List[Dict[str, Any]],
    spec_sheets: Optional[Dict[str, Any]] = None,
    active_spec_sheet: Optional[str] = None,
    user_id: Optional[str] = None,
    filename_base: Optional[str] = None,
) -> str:
    """Render the single-chart editor HTML document."""
    from echart_studio import __version__ as VERSION

    title = option.get("title", {}).get("text", "") or filename_base or "chart"
    essential_map = _essential_names_map()
    # Also mark per-knob .essential flags
    for d in knob_defs:
        if d.get("essential"):
            essential_map[d["name"]] = True

    payload = {
        "option": option,
        "chartId": chart_id,
        "chartType": chart_type,
        "theme": theme,
        "palette": palette,
        "dimension": dimension_preset,
        "knobDefs": knob_defs,
        "themes": _themes_for_js(),
        "palettes": _palettes_for_js(),
        "dimensions": _dimensions_for_js(),
        "typographyOverrides": dict(TYPOGRAPHY_OVERRIDES),
        "themeKnobValues": _theme_knob_values_for_js(),
        "paletteColors": list(PALETTES[palette]["colors"]),
        "paletteKind": PALETTES[palette]["kind"],
        "sheets": spec_sheets or {},
        "activeSheet": active_spec_sheet or "",
        "sheetsKey": f"echart_studio_sheets_{user_id or 'anon'}",
        "prefKey": f"echart_studio_prefs_{user_id or 'anon'}_{chart_type}",
        "filename": filename_base or "chart",
        "version": VERSION,
    }
    payload_js = (
        "var PAYLOAD = " + json.dumps(payload, default=_json_default) + ";\n"
        "var ESSENTIAL_NAMES = " + json.dumps(essential_map) + ";\n"
    )
    app_js = APP_JS.replace(
        "__MAX_DECIMALS__", str(int(MAX_DASHBOARD_DECIMALS))
    )
    html = (HTML_SHELL
            .replace("__ECHARTS_SCRIPT__", f"<script>\n{_get_echarts_js()}\n</script>")
            .replace("__TITLE__", _html_escape(title))
            .replace("__CHART_ID__", chart_id)
            .replace("__CHART_TYPE__", chart_type)
            .replace("__VERSION__", VERSION)
            .replace("__PAYLOAD__", payload_js)
            .replace("__APP__", app_js)
            .replace("__GS_FONT_SANS__", GS_FONT_SANS)
            .replace("__GS_NAVY__", GS_NAVY)
            .replace("__GS_INK__", GS_INK)
            .replace("__GS_PAPER__", GS_PAPER))
    return html


# =============================================================================
# PART 2 -- DASHBOARD HTML
# =============================================================================
# GS-branded cards, tabs, grid layout, global filter bus, echarts.connect()
# link groups, brush cross-filter via shared dataset scopes.


DASHBOARD_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<script>
/* Browser-side telemetry beacon. Captures uncaught errors, unhandled
promise rejections, console.error / console.warn calls, and resource-
load failures, and POSTs them to /api/dashboard/telemetry/ via
navigator.sendBeacon. The endpoint append-writes JSONL to
users/{kerberos}/dashboards/{dashboard_id}/console_log.jsonl. PRISM
reads that file as the single best signal of what the user actually
saw in their browser. See dashboards/diagnose.md#structured-inspection. */
(function() {
    var BUFFER = [];
    var FLUSH_DELAY_MS = 2000;
    var MAX_BUFFER = 50;
    var endpoint = null;
    var flushTimer = null;

    function captureEvent(evt) {
        if (BUFFER.length >= MAX_BUFFER) return;
        BUFFER.push(Object.assign({
            ts: new Date().toISOString(),
            url: window.location.pathname,
            ua: navigator.userAgent.substring(0, 200)
        }, evt));
        scheduleFlush();
    }

    function scheduleFlush() {
        if (flushTimer) return;
        flushTimer = setTimeout(flush, FLUSH_DELAY_MS);
    }

    function flush() {
        flushTimer = null;
        if (!endpoint) return;
        if (!BUFFER.length) return;
        var events = BUFFER.splice(0, BUFFER.length);
        var payload = {
            kerberos: window.PRISM_DASHBOARD_OWNER || null,
            viewer: window.PRISM_VIEWER || null,
            dashboard_id: window.PRISM_DASHBOARD_ID || null,
            events: events
        };
        try {
            var blob = new Blob([JSON.stringify(payload)],
                {type: 'application/json'});
            if (navigator.sendBeacon) {
                if (!navigator.sendBeacon(endpoint, blob)) {
                    fetch(endpoint, {method: 'POST', body: blob, keepalive: true});
                }
            } else {
                fetch(endpoint, {method: 'POST', body: blob, keepalive: true});
            }
        } catch (e) {/* telemetry must never break the page */}
    }

    window.addEventListener('error', function(e) {
        captureEvent({
            kind: 'error',
            message: (e.message || '').substring(0, 500),
            source: e.filename || null,
            line: e.lineno || null,
            col: e.colno || null,
            stack: (e.error && e.error.stack || '').substring(0, 2000)
        });
    });

    window.addEventListener('unhandledrejection', function(e) {
        var reason = e.reason;
        captureEvent({
            kind: 'unhandled_rejection',
            message: ((reason && reason.message) ||
                      String(reason || '')).substring(0, 500),
            stack: (reason && reason.stack || '').substring(0, 2000)
        });
    });

    var __inCapture = false;
    ['error', 'warn'].forEach(function(level) {
        var orig = console[level];
        console[level] = function() {
            if (!__inCapture) {
                __inCapture = true;
                try {
                    var msg = Array.prototype.map.call(arguments, function(a) {
                        if (a instanceof Error) return a.message + "\\n" + a.stack;
                        if (typeof a === 'object') {
                            try {
                                return JSON.stringify(a);
                            } catch (e) {
                                return '[' + (a && a.constructor && a.constructor.name || 'Object') + ']';
                            }
                        }
                        return String(a);
                    }).join(' ').substring(0, 1000);
                    captureEvent({kind: 'console_' + level, message: msg});
                } catch (e) {/* never break */}
                __inCapture = false;
            }
            return orig.apply(console, arguments);
        };
    });

    window.addEventListener('error', function(e) {
        var t = e.target;
        if (t && t !== window && (t.src || t.href)) {
            captureEvent({
                kind: 'resource_404',
                tag: (t.tagName || '').toLowerCase(),
                url: (t.src || t.href || '').substring(0, 500)
            });
        }
    }, true);

    function bindEndpoint() {
        endpoint = window.PRISM_TELEMETRY_ENDPOINT || null;
        captureEvent({kind: 'page_view'});
        if (BUFFER.length) scheduleFlush();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindEndpoint);
    } else {
        bindEndpoint();
    }

    window.addEventListener('beforeunload', function() {
        if (endpoint) {
            flush();
            return;
        }
        if (!BUFFER.length) return;
        // Last-ditch: try the conventional path. If the URL is wrong, the
        // browser silently drops it -- same outcome as not firing at all.
        try {
            var fallback = '/api/dashboard/telemetry/';
            var payload = {
                kerberos: window.PRISM_DASHBOARD_OWNER || null,
                viewer: window.PRISM_VIEWER || null,
                dashboard_id: window.PRISM_DASHBOARD_ID || null,
                events: BUFFER.splice(0, BUFFER.length),
                unbound: true
            };
            var blob = new Blob([JSON.stringify(payload)],
                {type: 'application/json'});
            if (navigator.sendBeacon) navigator.sendBeacon(fallback, blob);
        } catch (e) {/* swallow */}
    });
})();
</script>
<script>
/* Apply persisted dark-mode preference before paint to avoid a
   light-mode flash. Falls back to the OS-level prefers-color-scheme
   when the user has never toggled the button. The same key is
   read/written by the toggle handler in DASHBOARD_APP_JS. */
(function(){
  try {
    var v = localStorage.getItem('echart_dashboard_theme_mode');
    var dark;
    if (v === 'dark') dark = true;
    else if (v === 'light') dark = false;
    else dark = !!(window.matchMedia &&
                    window.matchMedia('(prefers-color-scheme: dark)').matches);
    if (dark) document.documentElement.setAttribute('data-theme', 'dark');
  } catch(e){}
})();
</script>
__ECHARTS_SCRIPT__
<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
<style>
/* =============================================================
   Goldman Sachs canonical design tokens (synced with
   ai_development/dashboards/config.py). There is one style -- this one.
   ============================================================= */
:root {
  --gs-navy:       __GS_NAVY__;
  --gs-navy-deep:  __GS_NAVY_DEEP__;
  --gs-sky:        __GS_SKY__;
  --gs-ink:        __GS_INK__;
  --gs-paper:      __GS_PAPER__;
  --gs-bg:         __GS_BG__;
  --gs-grey-70:    __GS_GREY_70__;
  --gs-grey-40:    __GS_GREY_40__;
  --gs-grey-20:    __GS_GREY_20__;
  --gs-grey-10:    __GS_GREY_10__;
  --gs-grey-05:    __GS_GREY_05__;
  --gs-pos:        __GS_POS__;
  --gs-neg:        __GS_NEG__;
  --gs-font-sans:  __GS_FONT_SANS__;
  --gs-font-serif: __GS_FONT_SERIF__;

  /* semantic slots used by the chrome */
  --bg:            var(--gs-bg);
  --surface:       var(--gs-paper);
  --surface-2:     var(--gs-grey-05);
  --surface-hover: #F2F5FA;
  --text:          var(--gs-ink);
  --text-dim:      var(--gs-grey-70);
  --text-faint:    var(--gs-grey-40);
  --border:        var(--gs-grey-10);
  --border-strong: var(--gs-grey-20);
  --accent:        var(--gs-navy);
  --accent-2:      var(--gs-sky);
  --accent-soft:   rgba(115,153,198,0.16);
  --accent-ring:   rgba(0,47,108,0.14);
  --pos:           var(--gs-pos);
  --pos-soft:      rgba(46,125,50,0.12);
  --neg:           var(--gs-neg);
  --neg-soft:      rgba(179,38,30,0.10);

  /* surface geometry */
  --shadow-sm:  0 1px 2px rgba(10,18,40,0.04);
  --shadow:     0 1px 3px rgba(10,18,40,0.06),
                0 1px 2px rgba(10,18,40,0.04);
  --shadow-md:  0 4px 8px -2px rgba(10,18,40,0.08),
                0 2px 4px -2px rgba(10,18,40,0.05);
  --shadow-lg:  0 12px 24px -4px rgba(10,18,40,0.12),
                0 4px 8px -4px rgba(10,18,40,0.08);
  --radius:     6px;
  --radius-sm:  4px;
  --bounce:     cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease:       cubic-bezier(0.16, 1, 0.3, 1);
}

/* =============================================================
   Dark mode -- driven by data-theme="dark" on <html>. The brand
   tokens (gs-navy, gs-sky, gs-pos, gs-neg) stay constant; only the
   semantic slots flip so chrome inverts but brand identity is
   preserved. Activated by the theme-toggle button in the header
   (added at render time, never controlled by the manifest).
   ============================================================= */
:root[data-theme="dark"] {
  /* Re-aim the brand grey tokens at their dark-mode equivalents.
     Every place in the chrome uses these (either directly or via
     the semantic slots below), so flipping them here cascades
     through tile titles, badges, code blocks, table headers,
     borders, etc. without per-element rewrites.
     The brand colour tokens themselves (gs-navy, gs-sky, gs-pos,
     gs-neg) stay constant -- those are identity, not chrome. */
  --gs-ink:      __GS_DARK_TEXT__;
  --gs-grey-70:  __GS_DARK_TEXT_DIM__;
  --gs-grey-40:  __GS_DARK_TEXT_FAINT__;
  --gs-grey-20:  __GS_DARK_BORDER_STR__;
  --gs-grey-10:  __GS_DARK_BORDER__;
  --gs-grey-05:  __GS_DARK_SURFACE_2__;

  /* Semantic slots get their own explicit dark assignments so the
     intent stays readable, even though most resolve to the same
     value as the brand tokens above. */
  --bg:            __GS_DARK_BG__;
  --surface:       __GS_DARK_SURFACE__;
  --surface-2:     __GS_DARK_SURFACE_2__;
  --surface-hover: __GS_DARK_SURFACE_HOV__;
  --text:          __GS_DARK_TEXT__;
  --text-dim:      __GS_DARK_TEXT_DIM__;
  --text-faint:    __GS_DARK_TEXT_FAINT__;
  --border:        __GS_DARK_BORDER__;
  --border-strong: __GS_DARK_BORDER_STR__;
  /* shift accent slots from navy to sky -- navy on dark navy is
     unreadable; the brand box itself stays navy via --gs-navy. */
  --accent:        var(--gs-sky);
  --accent-2:      #9CB8DB;
  --accent-soft:   rgba(115,153,198,0.20);
  --accent-ring:   rgba(115,153,198,0.32);
  --pos-soft:      rgba(46,125,50,0.22);
  --neg-soft:      rgba(179,38,30,0.22);
  --shadow-sm:  0 1px 2px rgba(0,0,0,0.30);
  --shadow:     0 1px 3px rgba(0,0,0,0.40),
                0 1px 2px rgba(0,0,0,0.28);
  --shadow-md:  0 4px 8px -2px rgba(0,0,0,0.45),
                0 2px 4px -2px rgba(0,0,0,0.30);
  --shadow-lg:  0 12px 24px -4px rgba(0,0,0,0.55),
                0 4px 8px -4px rgba(0,0,0,0.40);
  color-scheme: dark;
}

/* ``color: var(--gs-navy)`` is used in many places as the chrome's
   "emphasis text" colour (KPI numbers, modal titles, strong inline
   text, slider readouts, stat-grid values, code-in-prose). The navy
   token cannot be redefined globally because it is also a brand
   background / border colour, so each emphasis-text site needs an
   explicit dark-mode override pointing at the sky-blue accent. */
:root[data-theme="dark"] .kpi-value,
:root[data-theme="dark"] .ed-modal-title,
:root[data-theme="dark"] .ed-modal-body h1,
:root[data-theme="dark"] .ed-modal-body h2,
:root[data-theme="dark"] .ed-modal-body strong,
:root[data-theme="dark"] .ed-modal-body a:hover,
:root[data-theme="dark"] .detail-stat-value,
:root[data-theme="dark"] .detail-markdown strong,
:root[data-theme="dark"] .stat-grid-tile .stat-value,
:root[data-theme="dark"] .filter-item.slider .slider-val,
:root[data-theme="dark"] .provenance-footer table.provenance-table code,
:root[data-theme="dark"] .detail-stat-src code {
  color: var(--gs-sky);
}

/* Borders / outlines that resolve to GS Navy disappear against the
   dark navy page; bump them to GS Sky so focus rings, dividers, and
   table-header underlines remain visible. */
:root[data-theme="dark"] .table-toolbar .table-search:focus,
:root[data-theme="dark"] .filter-item.text input[type="text"]:focus,
:root[data-theme="dark"] .filter-item.number input[type="number"]:focus,
:root[data-theme="dark"] .ed-modal-body table.md-table th,
:root[data-theme="dark"] .modal-detail-table th {
  border-color: var(--gs-sky);
}
:root[data-theme="dark"] .ed-modal-body table.md-table th {
  border-bottom-color: var(--gs-sky);
}
:root[data-theme="dark"] .gs-mark .gs-wordmark { color: var(--text); }
:root[data-theme="dark"] .prism-mark .prism-wordmark { color: var(--text); }
:root[data-theme="dark"] header.app-header {
  border-bottom-color: var(--gs-sky);
}
:root[data-theme="dark"] .header-titles h1 { color: var(--text); }
/* Header action buttons share a single visual treatment so the
   gallery doesn't look like every dashboard reskinned independently:
   white in light mode (the default .icon-btn rule), light-blue in
   dark mode. The theme toggle is excluded because its sun/moon glyph
   uses a `::after` cutout that must match the button background --
   it keeps the default dark-surface treatment. */
:root[data-theme="dark"] .header-actions .icon-btn:not(.theme-toggle) {
  background: var(--gs-sky); border-color: var(--gs-sky);
  color: __GS_DARK_BG__;
}
:root[data-theme="dark"]
    .header-actions .icon-btn:not(.theme-toggle):hover {
  background: #9CB8DB; border-color: #9CB8DB;
}
:root[data-theme="dark"] .badge { background: var(--gs-sky);
                                   color: __GS_DARK_BG__; }
:root[data-theme="dark"] .tab-btn.active {
  border-bottom-color: var(--gs-sky); background: var(--surface-2);
}
:root[data-theme="dark"] .tile-emphasis {
  border-color: var(--gs-sky);
  box-shadow: 0 0 0 1px var(--gs-sky), var(--shadow-md);
}
:root[data-theme="dark"] .tile-emphasis::before { background: var(--gs-sky); }
:root[data-theme="dark"] .tab-panel-header { border-left-color: var(--gs-sky); }
:root[data-theme="dark"] .markdown-tile th, :root[data-theme="dark"] .markdown-body th,
:root[data-theme="dark"] .markdown-tile table.md-table th,
:root[data-theme="dark"] .markdown-body table.md-table th {
  border-bottom-color: var(--gs-sky);
  background: var(--surface-2);
}
:root[data-theme="dark"] .kpi-tile { border-top-color: var(--gs-sky); }
:root[data-theme="dark"] .kpi-value { color: var(--gs-sky); }
:root[data-theme="dark"] .tile-pinned { background: var(--surface); }
:root[data-theme="dark"] footer.app-footer { background: var(--surface-2); }
:root[data-theme="dark"] .tile-btn.primary,
:root[data-theme="dark"] a.tile-btn.primary {
  background: var(--gs-sky); border-color: var(--gs-sky);
  color: __GS_DARK_BG__;
}
:root[data-theme="dark"] .tile-btn.primary:hover,
:root[data-theme="dark"] a.tile-btn.primary:hover {
  background: #9CB8DB; border-color: #9CB8DB;
}
:root[data-theme="dark"] .tile-btn.controls[data-active="true"] {
  background: var(--gs-sky); border-color: var(--gs-sky);
  color: __GS_DARK_BG__;
}
:root[data-theme="dark"] .tile-btn.controls[data-active="true"] .tile-btn-glyph {
  color: __GS_DARK_BG__;
}
:root[data-theme="dark"] .markdown-tile blockquote,
:root[data-theme="dark"] .markdown-body blockquote {
  background: rgba(115,153,198,0.10);
}
:root[data-theme="dark"] .markdown-tile pre,
:root[data-theme="dark"] .markdown-body pre,
:root[data-theme="dark"] .markdown-tile code,
:root[data-theme="dark"] .markdown-body code {
  background: var(--surface-2);
}
:root[data-theme="dark"] .filter-info:hover,
:root[data-theme="dark"] .tile-info:hover { color: var(--gs-sky); }

/* The theme toggle button itself -- a borderless icon-only square
   that sits flush with the rest of header-actions. The label is a
   pure CSS sun/moon glyph drawn with a single circle + accent
   crescent so we never rely on a font icon or emoji. */
.theme-toggle { padding: 6px 10px; min-width: 32px;
                  display: inline-flex; justify-content: center; }
.theme-toggle .toggle-glyph {
  display: inline-block; position: relative;
  width: 14px; height: 14px;
}
.theme-toggle .toggle-glyph::before {
  content: ""; display: block; position: absolute;
  inset: 0; border-radius: 50%;
  background: currentColor;
}
.theme-toggle .toggle-glyph::after {
  content: ""; display: block; position: absolute;
  inset: 0; border-radius: 50%;
  background: var(--surface);
  transform: translate(35%, -25%) scale(0.85);
  transition: transform 0.15s var(--ease),
              background-color 0.15s var(--ease);
}
:root[data-theme="dark"] .theme-toggle .toggle-glyph::after {
  background: var(--surface);
  transform: translate(35%, -25%) scale(0.85);
}
:root:not([data-theme="dark"]) .theme-toggle .toggle-glyph::after {
  transform: translate(120%, -120%) scale(0);
}

* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: var(--bg); color: var(--text);
  font-family: var(--gs-font-sans);
  font-size: 14px; line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-feature-settings: "ss01", "ss02", "kern", "liga", "tnum";
  transition: background-color 0.15s var(--ease),
              color 0.15s var(--ease);
}

.app { display: flex; flex-direction: column; min-height: 100vh; }

/* Header brand home link -- wraps either .prism-mark or .gs-mark and
   navigates to the PRISM profile home (/profile/). Keep link chrome
   invisible so the mark still reads as a brand, not a hyperlink. */
a.brand-home {
  display: inline-flex; align-items: center;
  text-decoration: none; color: inherit; cursor: pointer;
}
a.brand-home:hover,
a.brand-home:focus,
a.brand-home:visited {
  text-decoration: none; color: inherit;
}
a.brand-home:focus-visible {
  outline: 2px solid var(--gs-sky);
  outline-offset: 3px;
  border-radius: 2px;
}

/* GS brand mark -- a compact navy "blue-box" reminiscent of the
   historic Goldman Sachs logo. Pure CSS, no images. */
.gs-mark {
  display: inline-flex; align-items: center; gap: 10px;
  font-family: var(--gs-font-serif); letter-spacing: 0.01em;
}
.gs-mark .gs-box {
  width: 28px; height: 28px; background: var(--gs-navy);
  color: #fff; display: inline-flex; align-items: center;
  justify-content: center;
  font-family: var(--gs-font-serif); font-weight: 700;
  font-size: 13px; letter-spacing: 0.02em;
}
.gs-mark .gs-wordmark {
  font-family: var(--gs-font-serif); font-weight: 600;
  font-size: 13px; color: var(--gs-ink);
  letter-spacing: 0.03em; white-space: nowrap;
}

/* Prism AI brand mark -- shown in the header when a logo PNG is
   available (PRISM S3 fetch, $PRISM_LOGO_PATH override, or a file at
   projects/echarts/assets/prism_logo.png). When no logo can be sourced
   the renderer falls back to the .gs-mark span above, so these rules
   simply have nothing to style and stay inert. */
.prism-mark {
  display: inline-flex; align-items: center; gap: 12px;
}
.prism-mark img {
  height: 44px; width: auto; display: block;
}
.prism-mark .prism-wordmark {
  font-family: var(--gs-font-sans); font-weight: 600;
  font-size: 22px; color: var(--gs-ink);
  letter-spacing: 0.02em; white-space: nowrap;
}

header.app-header {
  background: var(--surface);
  border-bottom: 2px solid var(--gs-navy);
  padding: 16px 28px 14px 28px;
  position: sticky; top: 0; z-index: 10;
  display: block;
}
.header-titles { display: flex; flex-direction: column; gap: 4px;
                   padding-right: 32px; }
.header-titles h1 {
  font-family: var(--gs-font-serif);
  font-size: 22px; margin: 2px 0 0 0; font-weight: 600;
  letter-spacing: -0.005em; color: var(--gs-ink);
}
.header-titles .subtitle {
  color: var(--text-dim); font-size: 13px;
  max-width: 820px; font-family: var(--gs-font-sans);
}
.header-meta { color: var(--text-faint); font-size: 12px;
                 display: flex; align-items: center; gap: 10px;
                 font-variant-numeric: tabular-nums; flex-wrap: wrap; }
.header-meta .meta-dot {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; background: var(--gs-grey-05);
  border: 1px solid var(--border); border-radius: 3px;
  color: var(--text-dim); font-size: 11px;
}
.header-meta .meta-dot span { color: var(--gs-ink); font-weight: 600; }
/* live-flash heartbeat: dims the data-as-of pill for ~1.5s when the
   live-refresh poll loop swaps in fresh datasets. Subtle enough that
   it's not distracting; visible enough that a user with the dashboard
   on a second monitor sees that the numbers underneath the charts
   just updated. */
.header-meta .meta-dot.live-flash {
  animation: prism-live-flash 1500ms ease-in-out 1;
}
@keyframes prism-live-flash {
  0%   { background: var(--gs-grey-05); }
  35%  { background: rgba(115, 153, 198, 0.30); }  /* GS PMS 652 sky blue */
  100% { background: var(--gs-grey-05); }
}
.header-actions .icon-btn.refreshing {
  background: var(--gs-grey-05); color: var(--text-dim);
  cursor: wait; opacity: 0.9;
}
.header-actions .icon-btn.refresh-success {
  background: var(--pos); color: #fff; border-color: var(--pos);
}
.header-actions .icon-btn.refresh-error {
  background: var(--neg); color: #fff; border-color: var(--neg);
}
.header-actions .icon-btn.refresh-error:hover {
  background: var(--neg); color: #fff; border-color: var(--neg);
  filter: brightness(1.05);
}
/* Persistent "(i)" error pill rendered next to the Refresh button when
   the last refresh attempt failed. Stays visible after the Refresh
   button label resets so the user can re-open the error modal at any
   time, paste the contents into PRISM, and have the dashboard fixed. */
.header-actions .icon-btn.refresh-err-info {
  background: var(--neg); color: #fff; border-color: var(--neg);
  padding: 6px 9px; font-weight: 600; letter-spacing: 0.04em;
  font-size: 11px; text-transform: uppercase;
}
.header-actions .icon-btn.refresh-err-info:hover {
  background: var(--neg); color: #fff; border-color: var(--neg);
  filter: brightness(1.10);
}
/* Share button "currently sharing" state -- subtle accent so the
   author can glance at the header and see that the dashboard is
   public. The default Share button uses the standard icon-btn
   chrome; the .shared modifier swaps to the GS sky-blue accent. */
.header-actions .icon-btn.shared {
  background: var(--gs-blue, #7399C6); color: #fff;
  border-color: var(--gs-blue, #7399C6);
}
.header-actions .icon-btn.shared:hover {
  background: var(--gs-blue, #7399C6); color: #fff;
  border-color: var(--gs-blue, #7399C6);
  filter: brightness(1.05);
}
/* Refresh-error modal -- surfaces full error context (status,
   classification, errors[], timestamps, pid, log path, dashboard
   metadata) and a one-click "Copy for PRISM" markdown dump so the
   user can hand the failure straight to PRISM for a fix. */
.refresh-err-summary {
  display: grid; grid-template-columns: max-content 1fr;
  column-gap: 14px; row-gap: 6px;
  margin: 0 0 14px;
  font-family: var(--gs-font-sans); font-size: 12px;
}
.refresh-err-summary dt {
  color: var(--text-faint); text-transform: uppercase;
  letter-spacing: 0.06em; font-size: 10px; align-self: center;
}
.refresh-err-summary dd {
  margin: 0; color: var(--text);
  font-variant-numeric: tabular-nums;
  word-break: break-word;
}
.refresh-err-summary dd code {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo,
              Consolas, monospace;
  font-size: 11px;
}
.refresh-err-pill {
  display: inline-block; padding: 2px 9px; border-radius: 11px;
  font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.08em;
  font-family: var(--gs-font-sans);
}
.refresh-err-pill.kind-error,
.refresh-err-pill.kind-spawn_fail,
.refresh-err-pill.kind-network,
.refresh-err-pill.kind-timeout,
.refresh-err-pill.kind-runner_error {
  background: var(--neg); color: #fff;
}
.refresh-err-pill.kind-partial,
.refresh-err-pill.kind-runner_partial {
  background: var(--gs-amber, #B08D3F); color: #fff;
}
.refresh-err-section-h {
  font-family: var(--gs-font-sans); font-size: 11px; font-weight: 600;
  color: var(--gs-navy); text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 14px 0 6px;
}
.refresh-err-list {
  margin: 0 0 14px; padding: 0; list-style: none;
}
.refresh-err-list li {
  padding: 8px 10px; margin: 0 0 6px;
  background: var(--gs-grey-05); border: 1px solid var(--border);
  border-left: 3px solid var(--neg);
  border-radius: var(--radius-sm);
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo,
              Consolas, monospace;
  font-size: 11.5px; line-height: 1.45;
  white-space: pre-wrap; word-break: break-word;
  color: var(--text);
}
.refresh-err-list li.partial {
  border-left-color: var(--gs-amber, #B08D3F);
}
.refresh-err-list li .err-meta {
  display: block; font-family: var(--gs-font-sans); font-size: 10px;
  font-weight: 600; color: var(--text-faint);
  text-transform: uppercase; letter-spacing: 0.06em;
  margin: 0 0 4px;
}
.refresh-err-actions {
  display: flex; gap: 8px; flex-wrap: wrap;
  margin: 16px 0 4px; padding-top: 12px;
  border-top: 1px solid var(--border);
}
.refresh-err-actions button {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 6px 12px;
  cursor: pointer; color: var(--text); font-size: 12px;
  font-family: var(--gs-font-sans); font-weight: 500;
}
.refresh-err-actions button:hover {
  background: var(--surface-hover);
  border-color: var(--accent-2); color: var(--accent);
}
.refresh-err-actions button.primary {
  background: var(--gs-navy); color: #fff; border-color: var(--gs-navy);
}
.refresh-err-actions button.primary:hover {
  background: var(--gs-navy); color: #fff; border-color: var(--gs-navy);
  filter: brightness(1.10);
}
.refresh-err-copy-status {
  display: inline-flex; align-items: center;
  font-size: 11px; color: var(--pos);
  font-family: var(--gs-font-sans); font-weight: 600;
  margin-left: auto; opacity: 0;
  transition: opacity 0.15s var(--ease);
}
.refresh-err-copy-status.visible { opacity: 1; }
.refresh-err-tip {
  margin: 12px 0 0; padding: 10px 12px;
  background: rgba(115, 153, 198, 0.08);
  border-left: 3px solid var(--accent-2);
  border-radius: var(--radius-sm);
  font-size: 12px; color: var(--text-dim);
  font-family: var(--gs-font-sans); line-height: 1.55;
}
.refresh-err-tip strong { color: var(--text); }
.badge {
  padding: 3px 9px; font-size: 10px; border-radius: 2px;
  background: var(--gs-navy); color: #fff;
  font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
  font-family: var(--gs-font-sans);
}
.header-right {
  position: absolute;
  top: 12px;
  right: 28px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  pointer-events: auto;
}
.header-actions { display: flex; gap: 6px; align-items: center;
                    flex-wrap: wrap; justify-content: flex-end; }

/* Download dropdown. Single icon-btn that opens a click-anchored
   popover listing Full Dashboard / Panel / Charts / Excel. Replaces the three
   stand-alone Download* buttons that used to live in the chrome.
   Click-to-open + click-outside / Esc-to-close (no hover dropdown);
   accessibility-friendly because every menu item is a real <button>. */
.download-dd { position: relative; display: inline-flex; }
.download-dd .download-caret { font-size: 10px; line-height: 1;
                                  margin-left: 2px; opacity: 0.7; }
.download-dd[data-open="true"] #download-btn { background: var(--bg-soft, #f4f6fa); }
.download-menu {
  position: absolute; top: calc(100% + 4px); right: 0; z-index: 20;
  min-width: 140px; padding: 4px; margin: 0;
  list-style: none;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
}
.download-menu[hidden] { display: none; }
.download-menu li { padding: 0; margin: 0; }
.download-menu-item {
  display: block; width: 100%;
  padding: 7px 10px; border: 0; background: transparent;
  color: var(--text); font-size: 12px;
  font-family: var(--gs-font-sans); font-weight: 500;
  text-align: left; cursor: pointer; border-radius: 3px;
}
.download-menu-item:hover { background: var(--bg-soft, #f0f3f8); }
:root[data-theme="dark"] .download-menu {
  background: var(--surface);
  border-color: var(--border);
  box-shadow: 0 6px 18px rgba(0,0,0,0.4);
}
:root[data-theme="dark"] .download-menu-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.share-dd { position: relative; display: inline-flex; }
.share-dd .share-caret { font-size: 10px; line-height: 1; margin-left: 2px; opacity: 0.7; }
.share-dd[data-open="true"] #share-btn { background: var(--bg-soft, #f4f6fa); }
.share-menu {
  position: absolute; top: calc(100% + 4px); right: 0; z-index: 20;
  min-width: 280px; padding: 4px; margin: 0; list-style: none;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
}
.share-menu[hidden] { display: none; }
.share-menu li { padding: 0; margin: 0; }
.share-menu-item {
  display: flex; width: 100%; align-items: flex-start; gap: 10px;
  padding: 9px 12px; border: 0; background: transparent;
  color: var(--text); font-size: 12px;
  font-family: var(--gs-font-sans); text-align: left;
  cursor: pointer; border-radius: 3px;
}
.share-menu-item:hover { background: var(--bg-soft, #f0f3f8); }
.share-menu-item .share-menu-icon { font-size: 16px; line-height: 1; padding-top: 1px; }
.share-menu-item .share-menu-label { display: flex; flex-direction: column; gap: 2px; }
.share-menu-item .share-menu-label strong { font-weight: 600; }
.share-menu-item .share-menu-label .share-menu-sub {
  font-size: 11px; color: var(--text-dim); font-weight: 400;
}
.share-menu-item .share-menu-submenu-caret {
  margin-left: auto; padding-top: 2px; color: var(--text-faint);
}
.share-menu-item.danger:hover { color: var(--neg); }
.share-menu-item[data-active="true"] { background: var(--accent-soft); }
.share-menu-item[data-active="true"] .share-menu-label strong { color: var(--accent); }
.share-menu-divider {
  height: 1px; margin: 4px 8px !important;
  background: var(--border);
}
.share-menu-has-submenu { position: relative; }
.share-submenu {
  position: absolute; top: -4px; right: calc(100% + 4px); z-index: 21;
  min-width: 260px; padding: 4px; margin: 0; list-style: none;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: 0 6px 18px rgba(0,0,0,0.10);
}
.share-submenu[hidden] { display: none; }
.share-submenu-item {
  display: flex; width: 100%; align-items: center; gap: 10px;
  padding: 9px 10px; border: 0; background: transparent;
  color: var(--text); font-family: var(--gs-font-sans);
  text-align: left; cursor: pointer; border-radius: 3px;
}
.share-submenu-item:hover { background: var(--bg-soft, #f0f3f8); }
.share-submenu-item:disabled {
  cursor: not-allowed; opacity: 0.55; background: transparent;
}
.share-workspace-copy {
  display: flex; flex-direction: column; gap: 2px; min-width: 0;
}
.share-workspace-copy strong {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 12px; font-weight: 600;
}
.share-workspace-copy span {
  font-size: 10.5px; color: var(--text-dim); text-transform: capitalize;
}
.share-submenu-status {
  padding: 10px 12px !important; color: var(--text-dim);
  font-size: 11px; line-height: 1.45;
}
.share-modal-copy-row { display: flex; gap: 6px; margin: 12px 0 14px; }
.share-modal-input {
  width: 100%; min-width: 0; padding: 7px 9px;
  border: 1px solid var(--border); border-radius: 3px;
  background: var(--bg-soft); color: var(--text);
  font-family: var(--gs-font-sans); font-size: 12px;
}
.share-modal-input:focus {
  outline: none; border-color: var(--accent-2);
  box-shadow: 0 0 0 2px var(--accent-soft);
}
.share-modal-actions {
  display: flex; justify-content: flex-end; align-items: center;
  gap: 8px; margin-top: 14px;
}
.share-modal-btn {
  padding: 7px 13px; border: 1px solid var(--border);
  border-radius: 3px; background: transparent; color: var(--text);
  font-family: var(--gs-font-sans); font-size: 12px; cursor: pointer;
}
.share-modal-btn:hover { background: var(--surface-hover); }
.share-modal-btn.primary {
  background: var(--accent); border-color: var(--accent); color: #fff;
}
.share-modal-btn.danger {
  background: var(--neg); border-color: var(--neg); color: #fff;
}
.share-modal-btn:disabled { cursor: wait; opacity: 0.55; }
.share-modal-error {
  min-height: 16px; margin-top: 8px; color: var(--neg);
  font-size: 11px; line-height: 1.4;
}
.share-users-selected {
  display: flex; flex-wrap: wrap; gap: 6px; min-height: 30px;
  margin: 10px 0; padding: 8px;
  border: 1px solid var(--border); border-radius: 3px;
  background: var(--bg-soft);
}
.share-user-chip {
  display: inline-flex; align-items: center; gap: 5px;
  max-width: 100%; padding: 4px 7px;
  background: var(--accent-soft); color: var(--accent);
  border-radius: 12px; font-size: 11px;
}
.share-user-chip span {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.share-user-chip button {
  padding: 0; border: 0; background: transparent;
  color: inherit; cursor: pointer; font-size: 13px; line-height: 1;
}
.share-users-empty {
  align-self: center; color: var(--text-faint); font-size: 11px;
}
.share-users-results {
  max-height: 210px; overflow-y: auto;
  border: 1px solid var(--border); border-radius: 3px;
}
.share-users-results[hidden] { display: none; }
.share-user-result {
  display: flex; width: 100%; justify-content: space-between;
  gap: 12px; padding: 9px 10px; border: 0;
  border-bottom: 1px solid var(--border);
  background: var(--surface); color: var(--text);
  text-align: left; cursor: pointer;
}
.share-user-result:last-child { border-bottom: 0; }
.share-user-result:hover { background: var(--surface-hover); }
.share-user-result:disabled { cursor: default; opacity: 0.55; }
.share-user-result-copy {
  display: flex; flex-direction: column; gap: 2px; min-width: 0;
}
.share-user-result-copy strong { font-size: 12px; font-weight: 600; }
.share-user-result-copy span { font-size: 10.5px; color: var(--text-dim); }
.share-user-result-kerb {
  flex: 0 0 auto; color: var(--text-faint); font-size: 10.5px;
}
.share-toast {
  position: fixed; right: 22px; bottom: 22px; z-index: 10020;
  max-width: 360px; padding: 10px 14px;
  background: var(--gs-navy); color: #fff;
  border-radius: 4px; box-shadow: 0 8px 24px rgba(0,0,0,0.22);
  font-family: var(--gs-font-sans); font-size: 12px;
  opacity: 0; transform: translateY(8px);
  transition: opacity 0.15s var(--ease), transform 0.15s var(--ease);
}
.share-toast.visible { opacity: 1; transform: translateY(0); }
.share-toast.error { background: var(--neg); }

/* Share action in-flight: header button + modal/submenu primaries
   show a CSS spinner so the click feels acknowledged while the
   ACL / workspace POST is outstanding. */
@keyframes share-spin {
  to { transform: rotate(360deg); }
}
.share-spinner {
  display: inline-block; width: 11px; height: 11px;
  border: 1.5px solid currentColor; border-right-color: transparent;
  border-radius: 50%; vertical-align: -1px;
  animation: share-spin 0.7s linear infinite;
  flex: 0 0 auto;
}
.header-actions .icon-btn.share-busy {
  cursor: wait; opacity: 0.85;
  gap: 6px;
}
.header-actions .icon-btn.share-busy .share-btn-label-row {
  display: inline-flex; align-items: center; gap: 6px;
}
.header-actions .icon-btn.share-busy .share-caret { display: none; }
.share-modal-btn.share-busy,
.share-submenu-item.share-busy {
  display: inline-flex; align-items: center; gap: 7px;
  cursor: wait;
}
.share-menu-item.share-busy {
  cursor: wait; opacity: 0.7; pointer-events: none;
}
.share-menu-item.share-busy .share-menu-icon {
  display: inline-flex; align-items: center; justify-content: center;
}

:root[data-theme="dark"] .share-menu {
  background: var(--surface); border-color: var(--border);
  box-shadow: 0 6px 18px rgba(0,0,0,0.4);
}
:root[data-theme="dark"] .share-submenu {
  background: var(--surface); border-color: var(--border);
  box-shadow: 0 6px 18px rgba(0,0,0,0.4);
}
:root[data-theme="dark"] .share-menu-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
:root[data-theme="dark"] .share-submenu-item:hover,
:root[data-theme="dark"] .share-user-result:hover {
  background: rgba(255, 255, 255, 0.06);
}
.icon-btn {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 6px 12px;
  cursor: pointer; color: var(--text); font-size: 12px;
  font-family: var(--gs-font-sans); font-weight: 500;
  letter-spacing: 0.01em;
  display: inline-flex; align-items: center; gap: 6px;
  transition: background-color 0.12s var(--ease),
              border-color 0.12s var(--ease),
              color 0.12s var(--ease),
              transform 0.12s var(--bounce);
}
.icon-btn:hover {
  background: var(--surface-hover);
  border-color: var(--accent-2);
  color: var(--accent);
}
.icon-btn:active { transform: scale(0.97); }

nav.tab-bar {
  display: flex; gap: 0; padding: 0 28px;
  background: var(--surface); border-bottom: 1px solid var(--border);
  overflow-x: auto; scrollbar-width: thin;
}
.tab-btn {
  background: none; border: none;
  padding: 12px 18px; font-size: 12px; color: var(--text-dim);
  border-bottom: 2px solid transparent; cursor: pointer;
  transition: color 0.12s var(--ease),
              border-color 0.15s var(--ease),
              background-color 0.12s var(--ease);
  font-family: var(--gs-font-sans);
  white-space: nowrap;
  font-weight: 600;
  letter-spacing: 0.04em; text-transform: uppercase;
}
.tab-btn:hover { color: var(--accent); background: var(--surface-hover); }
.tab-btn.active {
  color: var(--accent); border-bottom-color: var(--gs-navy);
  background: var(--gs-grey-05);
}

.filter-bar {
  background: var(--surface); padding: 12px 28px;
  border-bottom: 1px solid var(--border);
  display: flex; gap: 18px; flex-wrap: wrap; align-items: center;
}
.filter-item {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--text-dim);
  font-family: var(--gs-font-sans);
}
.filter-item label {
  font-weight: 600; color: var(--text);
  letter-spacing: 0.04em; text-transform: uppercase; font-size: 11px;
  display: inline-flex; align-items: center; gap: 4px;
}
.filter-info {
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; color: var(--text-faint); cursor: pointer;
  text-transform: none; letter-spacing: 0; font-weight: 400;
  border-radius: 50%; user-select: none;
}
.filter-info:hover { color: var(--accent);
                      background: var(--surface-hover); }
.filter-info:focus { outline: 2px solid var(--accent-ring); outline-offset: 2px; }
.filter-item select, .filter-item input[type=text], .filter-item input[type=date],
.filter-item input[type=number] {
  padding: 6px 10px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--surface);
  font-size: 13px; color: var(--text); font-family: inherit;
  min-width: 120px;
  transition: border-color 0.15s var(--ease),
              box-shadow 0.15s var(--ease);
}
.filter-item select[multiple] {
  min-width: 160px; min-height: 68px;
  padding: 4px 8px;
}
.filter-item.slider input[type=range] { min-width: 140px; }
.filter-item select:focus, .filter-item input:focus {
  outline: none; border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}
.filter-item input[type=checkbox] {
  accent-color: var(--accent); width: 15px; height: 15px;
}
.filter-reset { margin-left: auto; }

.tab-filter-bar {
  display: inline-flex; gap: 14px; flex-wrap: wrap; align-items: center;
  padding: 8px 12px; margin-bottom: 14px;
  background: var(--gs-grey-05);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 12px;
}
.tab-filter-bar .filter-item { font-size: 12px; }
.tab-filter-bar .filter-item label { font-size: 10.5px; }
.tab-filter-bar .filter-item select,
.tab-filter-bar .filter-item input[type=text],
.tab-filter-bar .filter-item input[type=number],
.tab-filter-bar .filter-item input[type=date] {
  padding: 4px 8px; font-size: 12px;
}
.tab-filter-bar .filter-reset {
  margin-left: 0; padding: 4px 10px; font-size: 11px;
}

main.app-main { padding: 20px 28px 40px 28px; flex: 1 1 auto; }

.tab-panel {
  display: none;
  animation: fadeInUp 0.22s var(--ease);
}
.tab-panel.active { display: block; }
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.tab-panel-header {
  margin-bottom: 14px;
  display: flex; justify-content: space-between; align-items: baseline;
  border-left: 3px solid var(--gs-navy); padding-left: 10px;
}
.tab-panel-header h2 {
  font-family: var(--gs-font-serif);
  font-size: 13px; margin: 0; color: var(--text-dim);
  font-weight: 500; font-style: italic;
}

.grid { display: grid; grid-template-columns: repeat(__COLS__, 1fr); gap: 14px; }
.layout-group {
  display: block;
  margin: 0 0 20px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--surface-2) 56%, transparent);
}
.layout-group-heading {
  display: flex; align-items: baseline; gap: 12px;
  margin: 0 0 12px; padding: 0 2px 9px;
  border-bottom: 1px solid var(--border);
}
.layout-group-heading h2 {
  margin: 0; color: var(--gs-ink); font-size: 14px;
  font-family: var(--gs-font-sans); letter-spacing: 0.035em;
}
.layout-group-heading p {
  margin: 0; color: var(--text-dim); font-size: 12px;
  font-family: var(--gs-font-serif); font-style: italic;
}
.layout-group-collapsible > summary { cursor: pointer; list-style-position: outside; }
.layout-group-collapsible > summary .layout-group-heading {
  display: inline-flex; width: calc(100% - 22px); vertical-align: middle;
}

.tile {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: box-shadow 0.18s var(--ease),
              border-color 0.18s var(--ease);
  display: flex; flex-direction: column;
}
.tile:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--accent-2);
}
.tile-header {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px;
  background: var(--surface);
}
.tile-title-wrap {
  flex: 1 1 auto; min-width: 0;
  display: flex; flex-direction: column; gap: 2px;
}
.tile-title {
  font-family: var(--gs-font-sans);
  font-size: 12px; font-weight: 600; color: var(--gs-ink);
  letter-spacing: 0.04em; text-transform: uppercase;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  display: inline-flex; align-items: center; gap: 6px;
  min-width: 0;
}
.tile-subtitle {
  font-family: var(--gs-font-serif);
  font-size: 11px; color: var(--text-dim);
  font-style: italic; font-weight: 400;
  letter-spacing: 0.01em;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tile-info {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; font-size: 13px; color: var(--text-faint);
  cursor: pointer; border-radius: 50%; user-select: none;
  text-transform: none; letter-spacing: 0;
  transition: color 0.12s var(--ease),
              background-color 0.12s var(--ease);
}
.tile-info:hover { color: var(--accent); background: var(--surface-hover); }
.tile-info:focus { outline: 2px solid var(--accent-ring); outline-offset: 2px; }
.tile-info:hover { color: var(--accent); }
.tile-info-kpi { margin-left: 6px; vertical-align: middle; }
.tile-badge {
  display: inline-flex; align-items: center;
  padding: 1px 7px; border-radius: 999px;
  font-family: var(--gs-font-sans); font-size: 9px; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase;
  background: var(--gs-navy); color: white;
}
.tile-badge[data-color="gs-navy"] { background: var(--gs-navy); color: white; }
.tile-badge[data-color="sky"]     { background: var(--gs-sky);
                                      color: var(--gs-navy-deep); }
.tile-badge[data-color="pos"]     { background: var(--pos-soft);
                                      color: var(--pos); }
.tile-badge[data-color="neg"]     { background: var(--neg-soft);
                                      color: var(--neg); }
.tile-badge[data-color="muted"]   { background: var(--surface-2);
                                      color: var(--text-dim); }
.tile-actions { display: flex; gap: 2px; flex: 0 0 auto; }
.tile-btn, a.tile-btn {
  background: none; border: 1px solid transparent;
  border-radius: var(--radius-sm); padding: 3px 8px;
  cursor: pointer; color: var(--text-faint); font-size: 11px;
  font-family: var(--gs-font-sans); font-weight: 600;
  letter-spacing: 0.04em; text-decoration: none;
  transition: color 0.12s var(--ease),
              background-color 0.12s var(--ease),
              border-color 0.12s var(--ease);
}
.tile-btn:hover, a.tile-btn:hover { background: var(--surface-2);
                                      color: var(--accent);
                                      border-color: var(--accent-2); }
.tile-btn.primary, a.tile-btn.primary {
  background: var(--gs-navy); color: white;
  border-color: var(--gs-navy);
}
.tile-btn.primary:hover, a.tile-btn.primary:hover {
  background: var(--gs-navy-deep); color: white;
  border-color: var(--gs-navy-deep);
}
.tile-btn-custom { padding: 3px 10px; }
.tile-body { padding: 10px 14px; flex: 1 1 auto; position: relative; }

.tile-footer {
  padding: 6px 14px 8px; font-size: 11px; color: var(--text-faint);
  font-family: var(--gs-font-sans); border-top: 1px dashed var(--border);
  background: var(--surface);
  line-height: 1.45;
}
.tile-emphasis {
  border-color: var(--gs-navy);
  box-shadow: 0 0 0 1px var(--gs-navy), var(--shadow-md);
}
.tile-emphasis::before {
  content: ''; display: block; height: 3px; background: var(--gs-navy);
  margin: -1px -1px 0 -1px;
  border-top-left-radius: var(--radius-md);
  border-top-right-radius: var(--radius-md);
}
.tile-emphasis.kpi-tile { border-top-width: 3px;
                            border-top-color: var(--gs-sky); }
.tile-emphasis.kpi-tile::before { display: none; }
.tile-pinned {
  position: sticky; top: 12px; z-index: 5;
}

/* chart tile */
.chart-tile .tile-body { padding: 6px 8px 8px; }
.chart-div { width: 100%; min-height: 320px; }
.tile-hero {
  border-color: color-mix(in srgb, var(--accent) 34%, var(--border));
  box-shadow: var(--shadow-md);
}
.tile-hero .tile-header { padding: 13px 18px; }
.tile-hero .tile-title { font-size: 13px; letter-spacing: 0.055em; }
.tile-hero .tile-body { padding: 8px 12px 12px; }

/* chart controls drawer
   Lives between the tile header and the chart canvas. Closed by
   default; the gear button in the toolbar toggles data-open.
   Populated lazily by JS on first open so we can introspect the
   lowered ECharts option (chart type, series, axes) before deciding
   which knobs to render. */
.chart-controls {
  display: none;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  padding: 10px 14px 8px;
  font-family: var(--gs-font-sans);
  font-size: 11px;
  color: var(--text-dim);
}
.chart-controls[data-open="true"] { display: block; }
.chart-controls .cc-section {
  padding-bottom: 8px;
  margin-bottom: 8px;
  border-bottom: 1px dashed var(--border);
}
.chart-controls .cc-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}
.chart-controls .cc-section-title {
  font-size: 9px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--text-faint);
  margin-bottom: 6px;
}
.chart-controls .cc-row {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 6px 14px; padding: 2px 0;
}
.chart-controls .cc-row > .cc-label {
  font-size: 10px; font-weight: 600;
  color: var(--text-dim);
  text-transform: uppercase; letter-spacing: 0.06em;
  min-width: 80px;
}
.chart-controls .cc-series-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 6px 12px; align-items: center;
  padding: 2px 0;
}
.chart-controls .cc-series-row > .cc-series-name {
  font-size: 11px; font-weight: 600;
  color: var(--text);
  font-family: var(--gs-font-sans);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chart-controls .cc-series-row .cc-series-swatch {
  display: inline-block; width: 10px; height: 10px;
  border-radius: 2px; margin-right: 6px; vertical-align: middle;
}
.chart-controls select,
.chart-controls input[type=text],
.chart-controls input[type=date],
.chart-controls input[type=number] {
  font-family: var(--gs-font-sans);
  font-size: 11px; padding: 2px 6px;
  border: 1px solid var(--border); border-radius: 2px;
  background: var(--surface);
  color: var(--text);
  min-width: 100px;
}
.chart-controls select:focus,
.chart-controls input:focus {
  outline: 2px solid var(--accent-ring);
  outline-offset: 1px;
  border-color: var(--accent-2);
}
.chart-controls input[type=checkbox] { accent-color: var(--accent); }
.chart-controls .cc-actions {
  display: flex; gap: 4px; flex-wrap: wrap;
  padding-top: 4px;
}
.chart-controls .cc-action-btn {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 3px 9px;
  cursor: pointer;
  color: var(--text-dim);
  font-family: var(--gs-font-sans);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  transition: color 0.12s var(--ease),
              background-color 0.12s var(--ease),
              border-color 0.12s var(--ease);
}
.chart-controls .cc-action-btn:hover {
  background: var(--surface-2);
  color: var(--accent);
  border-color: var(--accent-2);
}
.tile-btn.controls { padding: 3px 6px; }
.tile-btn-glyph { display: inline-block; transform: scale(1.2);
                    line-height: 1; }
.tile-btn.controls[data-active="true"] {
  background: var(--gs-navy); color: white; border-color: var(--gs-navy);
}
.tile-btn.controls[data-active="true"] .tile-btn-glyph { color: white; }

/* studio stats strip (scatter_studio) */
.tile-stats-strip {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 4px 14px;
  padding: 6px 10px 4px;
  margin-top: 4px;
  font-family: var(--gs-font-sans);
  font-size: 11px;
  color: var(--text-dim);
  border-top: 1px solid var(--border);
}
.tile-stats-strip:empty { display: none; }
.tile-stats-strip .cc-stat { white-space: nowrap; }
.tile-stats-strip .cc-stat b { color: var(--text); font-weight: 600; }
.tile-stats-strip .cc-stats-empty { font-style: italic; }
.tile-stats-strip .cc-stats-groups {
  flex-basis: 100%; display: flex; flex-wrap: wrap;
  gap: 2px 12px; padding-top: 2px;
  font-size: 10.5px; color: var(--text-dim);
}
.tile-stats-strip .cc-stat-group { white-space: nowrap; }
.tile-stats-strip .cc-stats-swatch {
  display: inline-block; width: 9px; height: 9px;
  border-radius: 2px; margin-right: 4px; vertical-align: middle;
}

/* Pivot / crosstab widget. */
.pivot-tile { display: flex; flex-direction: column; }
.pivot-controls {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 8px; padding: 8px 14px;
  font-family: var(--gs-font-sans); font-size: 11.5px;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border);
  background: var(--gs-grey-05);
}
.pivot-controls label {
  display: inline-flex; align-items: center; gap: 6px;
  white-space: nowrap;
}
.pivot-controls select {
  font-family: inherit; font-size: 12px;
  padding: 3px 6px;
  border: 1px solid var(--border);
  border-radius: 3px; background: var(--paper);
}
.pivot-body {
  overflow: auto; padding: 6px 0 8px;
}
.pivot-body table {
  border-collapse: collapse;
  font-family: var(--gs-font-sans); font-size: 12px;
  width: 100%;
}
.pivot-body th, .pivot-body td {
  border-bottom: 1px solid var(--gs-grey-10);
  padding: 5px 10px;
  font-variant-numeric: tabular-nums;
}
.pivot-body thead th {
  font-weight: 600; color: var(--gs-navy);
  border-bottom: 1.5px solid var(--gs-navy);
  background: var(--paper);
  position: sticky; top: 0; z-index: 1;
  white-space: nowrap; text-align: right;
}
.pivot-body thead th.pivot-row-header { text-align: left; }
.pivot-body td.pivot-row-label {
  font-weight: 600; color: var(--text);
  text-align: left; white-space: nowrap;
}
.pivot-body td.pivot-cell { text-align: right; }
.pivot-body tr.pivot-total td,
.pivot-body tr.pivot-total td.pivot-row-label {
  border-top: 1.5px solid var(--gs-navy);
  font-weight: 600;
  background: var(--gs-grey-05);
}
.pivot-body th.pivot-total-col,
.pivot-body td.pivot-total-col {
  border-left: 1.5px solid var(--gs-navy);
  background: var(--gs-grey-05);
}

/* In-cell data bars / sparklines for table widgets. */
.in-cell-wrap {
  position: relative;
  display: inline-flex; align-items: center;
  gap: 8px; min-width: 60px; width: 100%;
  justify-content: flex-end;
}
.in-cell-bar {
  position: relative; height: 18px;
  flex: 1 1 auto; min-width: 24px; max-width: 100px;
  background: var(--gs-grey-05); border-radius: 2px;
  overflow: hidden;
}
.in-cell-bar-fill {
  position: absolute; top: 0; bottom: 0;
  border-radius: 2px;
}
.in-cell-text {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
  white-space: nowrap;
}
.in-cell-spark {
  display: inline-block; vertical-align: middle;
  flex: 0 0 auto;
}

/* Auto-computed stat strip -- opened via the per-tile Sigma button
   in the chart toolbar, rendered into the shared popup modal. The
   body is a metric x series table: metric labels down the left
   (Current / Delta horizons / Pctile / Range), one column per visible
   series. Reads top-to-bottom for a single series and left-to-right
   when comparing across series. */
.stat-strip-modal-body {
  font-family: var(--gs-font-sans);
  font-size: 12.5px;
  color: var(--text);
  line-height: 1.55;
  max-height: 60vh;
  overflow: auto;
}
.stat-strip-modal-body table.stat-strip-table {
  border-collapse: collapse;
  width: 100%;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
.stat-strip-modal-body table.stat-strip-table thead th {
  background: var(--gs-grey-05);
  color: var(--gs-navy);
  font-weight: 600;
  text-align: right;
  padding: 6px 10px;
  border-bottom: 1.5px solid var(--gs-navy);
  text-transform: uppercase;
  font-size: 10.5px;
  letter-spacing: 0.06em;
  white-space: nowrap;
}
.stat-strip-modal-body table.stat-strip-table thead th.ssm {
  text-align: left;
  background: var(--gs-grey-05);
  color: var(--text-dim);
  font-weight: 500;
}
.stat-strip-modal-body table.stat-strip-table tbody td {
  padding: 5px 10px;
  border-bottom: 1px solid var(--border);
  text-align: right;
  white-space: nowrap;
}
.stat-strip-modal-body table.stat-strip-table tbody td.ssm {
  text-align: left;
  color: var(--text-dim);
  font-size: 11.5px;
  font-weight: 500;
  white-space: nowrap;
}
.stat-strip-modal-body table.stat-strip-table tbody tr.ss-cur-row td { background: rgba(0,47,108,0.04); }
.stat-strip-modal-body table.stat-strip-table tbody tr:last-child td { border-bottom: none; }
.stat-strip-modal-body .css-cur { color: var(--text); font-weight: 600; }
.stat-strip-modal-body .css-pos { color: var(--gs-pos); font-weight: 600; }
.stat-strip-modal-body .css-neg { color: var(--gs-neg); font-weight: 600; }
.stat-strip-modal-body .ss-empty { color: var(--text-faint); }
.stat-strip-modal-body .modal-empty {
  font-style: italic;
  margin: 0;
  padding: 6px 0;
  color: var(--text-faint);
}
:root[data-theme="dark"] .stat-strip-modal-body table.stat-strip-table thead th { background: var(--surface-2); }
:root[data-theme="dark"] .stat-strip-modal-body table.stat-strip-table thead th.ssm { background: var(--surface-2); }
:root[data-theme="dark"] .stat-strip-modal-body table.stat-strip-table tbody tr.ss-cur-row td { background: rgba(115,153,198,0.08); }

/* Σ stat-strip toolbar button -- styled to match the existing
   tile-btn pattern (same weight + size as the other glyphs in the
   toolbar so the row reads as a single visual column). */
.tile-btn.stat-strip-btn .tile-btn-glyph {
  font-family: var(--gs-font-sans);
  font-weight: 500;
  font-size: 12px;
  line-height: 1;
  letter-spacing: 0;
  /* Match the muted color of the controls glyph; the active state
     comes from the tile-btn:hover rule above. */
  opacity: 0.85;
}
.tile-btn.stat-strip-btn:hover .tile-btn-glyph { opacity: 1; }


/* kpi tile */
.kpi-tile {
  padding: 16px 20px 18px 20px;
  display: flex; flex-direction: column; justify-content: center;
  min-height: 118px; gap: 0;
  border-top: 3px solid var(--gs-navy);
  /* Container query context (CC5 in 2026-05-11 audit): the KPI
     value font-size is now responsive to tile width via cqw units
     so a 12-KPI row at w:1 each (~80px tile) doesn't clip the value
     mid-digit. Container query support: Safari 16+, Chrome 105+,
     Firefox 110+. */
  container-type: inline-size;
  container-name: kpi;
}
.kpi-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 6px;
}
.kpi-header .tile-actions { margin-left: auto; }
.kpi-controls { margin: 8px -4px 4px -4px; padding: 8px 10px 6px; }
.kpi-controls .cc-section { padding-bottom: 6px; margin-bottom: 6px; }
.kpi-label {
  font-family: var(--gs-font-sans);
  font-size: 10px; color: var(--text-dim);
  text-transform: uppercase; letter-spacing: 0.09em;
  font-weight: 700;
  flex: 1 1 auto; min-width: 0;
  /* Wrap label cleanly at word boundaries when needed. Avoid
     `overflow-wrap: anywhere` which char-breaks "BITCOIN" into
     "BI/TC/OI/N" and similarly fragments underscore-joined
     ticker codes -- prefer the cleaner two-line word wrap. The
     letter-spacing + label-size shrink-with-container pair below
     keeps narrow-tile labels legible. */
  overflow-wrap: break-word;
  word-break: normal;
  line-height: 1.3;
  /* Shrink label font as the container narrows so a 70px tile
     doesn't have to wrap "BITCOIN" at all. clamp(min, fluid, max)
     where fluid is sized in container-query width units. */
  font-size: clamp(8px, 5cqw, 10px);
  letter-spacing: clamp(0.02em, 0.4cqw, 0.09em);
}
.kpi-value {
  font-family: var(--gs-font-serif);
  font-size: 32px; font-weight: 600; margin-top: 8px;
  line-height: 1.02; color: var(--gs-navy);
  font-feature-settings: "tnum";
  letter-spacing: -0.015em;
  /* Avoid mid-digit clipping at narrow tile widths: shrink the
     value font as the container narrows. clamp(min, fluid, max)
     with the fluid component sized in container-query width units
     (cqw = 1% of container width) so a ~80px tile renders the
     value at ~14px instead of clipping a 32px font. */
  font-size: clamp(14px, 11cqw, 32px);
  /* If the (shrunk) value still overflows, ellipsis instead of
     mid-digit clipping. */
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  min-width: 0; max-width: 100%;
}
.kpi-value.small { font-size: clamp(12px, 8cqw, 24px); }
.kpi-delta {
  font-family: var(--gs-font-sans);
  font-size: 11px; margin-top: 6px; font-weight: 600;
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 8px; border-radius: 2px; align-self: flex-start;
  letter-spacing: 0.02em;
}
.kpi-delta.pos { color: var(--pos); background: var(--pos-soft); }
.kpi-delta.neg { color: var(--neg); background: var(--neg-soft); }
.kpi-delta.flat { color: var(--text-dim); background: var(--surface-2); }
.kpi-sub { font-size: 11px; color: var(--text-faint); margin-top: 6px;
           font-family: var(--gs-font-sans); }
.kpi-sparkline { height: 32px; margin-top: 10px;
                  margin-left: -4px; margin-right: -4px; }

/* markdown tile + shared prose styling.
   Both `.markdown-tile` (transparent prose-on-page) and
   `.markdown-body` (used inside note tiles, drill-down sections,
   summary banner, popups) share the typography rules so prose
   reads identically wherever PRISM places it. */
.markdown-tile {
  background: transparent; border: none; box-shadow: none;
  padding: 0;
}
.markdown-tile .tile-body { padding: 12px 4px; }
.markdown-tile h1, .markdown-tile h2, .markdown-tile h3,
.markdown-tile h4, .markdown-tile h5,
.markdown-body h1, .markdown-body h2, .markdown-body h3,
.markdown-body h4, .markdown-body h5 {
  margin: 6px 0 6px 0; color: var(--text);
  font-family: var(--gs-font-serif); font-weight: 600;
  letter-spacing: -0.005em;
}
.markdown-tile h1, .markdown-body h1 { font-size: 20px; }
.markdown-tile h2, .markdown-body h2 { font-size: 15px; }
.markdown-tile h3, .markdown-body h3 {
  font-family: var(--gs-font-sans);
  font-size: 11px; color: var(--text-dim);
  text-transform: uppercase; letter-spacing: 0.09em; font-weight: 700;
}
.markdown-tile h4, .markdown-body h4 {
  font-family: var(--gs-font-sans);
  font-size: 12px; color: var(--text); font-weight: 700;
}
.markdown-tile h5, .markdown-body h5 {
  font-family: var(--gs-font-sans);
  font-size: 11px; color: var(--text-dim); font-weight: 700;
  font-style: italic;
}
.markdown-tile p, .markdown-body p {
  margin: 4px 0; color: var(--text-dim); line-height: 1.6;
  font-family: var(--gs-font-sans);
}
.markdown-tile a, .markdown-body a {
  color: var(--accent); text-decoration: underline;
  text-decoration-color: var(--accent-2);
  text-underline-offset: 3px;
}
.markdown-tile a:hover, .markdown-body a:hover {
  color: var(--gs-navy-deep);
}
.markdown-tile ul, .markdown-tile ol,
.markdown-body ul, .markdown-body ol {
  margin: 6px 0; padding-left: 22px; color: var(--text-dim);
  font-family: var(--gs-font-sans); line-height: 1.55;
}
.markdown-tile li, .markdown-body li { margin: 2px 0; }
.markdown-tile ul ul, .markdown-tile ul ol,
.markdown-tile ol ul, .markdown-tile ol ol,
.markdown-body ul ul, .markdown-body ul ol,
.markdown-body ol ul, .markdown-body ol ol {
  margin: 2px 0; padding-left: 18px;
}
.markdown-tile blockquote, .markdown-body blockquote {
  margin: 8px 0; padding: 6px 12px;
  border-left: 3px solid var(--accent-2);
  background: rgba(115,153,198,0.08);
  color: var(--text-dim); font-style: italic;
}
.markdown-tile blockquote p, .markdown-body blockquote p {
  margin: 2px 0; font-style: italic;
}
.markdown-tile pre, .markdown-body pre {
  margin: 6px 0; padding: 8px 12px;
  background: var(--gs-grey-05);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow-x: auto;
}
.markdown-tile pre code, .markdown-body pre code {
  background: none; padding: 0;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 12px; color: var(--text); line-height: 1.5;
}
.markdown-tile code, .markdown-body code {
  background: var(--gs-grey-05); padding: 1px 4px;
  border-radius: 3px;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 12px; color: var(--text);
}
.markdown-tile hr, .markdown-body hr {
  margin: 12px 0; border: none;
  border-top: 1px solid var(--border);
}
.markdown-tile del, .markdown-body del {
  color: var(--text-faint);
  text-decoration-thickness: 1.5px;
}
.markdown-tile table.md-table, .markdown-body table.md-table {
  border-collapse: collapse; margin: 8px 0;
  font-family: var(--gs-font-sans); font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.markdown-tile table.md-table th, .markdown-body table.md-table th {
  text-align: left; padding: 6px 10px;
  border-bottom: 1px solid var(--gs-navy);
  background: var(--gs-grey-05);
  text-transform: uppercase; font-size: 10px;
  letter-spacing: 0.08em; color: var(--gs-ink); font-weight: 700;
}
.markdown-tile table.md-table td, .markdown-body table.md-table td {
  padding: 6px 10px; border-bottom: 1px solid var(--border);
  color: var(--text);
}

/* note tile - semantic callout for narrative writing.
   Six kinds, each with its own accent stripe + label tint:
     insight   sky      "this is the lightbulb"
     thesis    navy     "this is the load-bearing claim"
     watch     amber    "this is what to monitor"
     risk      red      "this is the downside"
     context   muted    "this is background"
     fact      green    "this is established"
   The body is full markdown via the shared `.markdown-body`
   typography rules so prose matches the markdown widget. */
.note-tile {
  background: var(--surface); border: 1px solid var(--border);
  border-left: 4px solid var(--accent-2);
  border-radius: var(--radius);
  padding: 10px 14px 12px 14px;
  box-shadow: var(--shadow-sm);
}
.note-tile .note-head {
  display: flex; align-items: baseline; gap: 8px;
  margin-bottom: 4px;
}
.note-tile .note-icon {
  font-size: 14px; color: var(--accent-2);
}
.note-tile .note-kind {
  font-family: var(--gs-font-sans);
  font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--accent-2);
}
.note-tile .note-title {
  font-family: var(--gs-font-serif);
  font-size: 14px; font-weight: 600; color: var(--text);
  letter-spacing: -0.005em;
}
.note-tile .note-body { padding: 0; }
.note-tile .note-body > :first-child { margin-top: 0; }
.note-tile .note-body > :last-child { margin-bottom: 0; }
.note-tile .tile-footer { margin-top: 8px; }
.note-tile-insight {
  border-left-color: var(--accent-2);
  background: rgba(115,153,198,0.06);
}
.note-tile-insight .note-icon,
.note-tile-insight .note-kind { color: var(--accent-2); }
.note-tile-thesis {
  border-left-color: var(--accent);
  background: var(--accent-soft);
}
.note-tile-thesis .note-icon,
.note-tile-thesis .note-kind { color: var(--accent); }
.note-tile-watch {
  border-left-color: #dd6b20;
  background: rgba(221,107,32,0.07);
}
.note-tile-watch .note-icon,
.note-tile-watch .note-kind { color: #dd6b20; }
.note-tile-risk {
  border-left-color: var(--neg);
  background: var(--neg-soft);
}
.note-tile-risk .note-icon,
.note-tile-risk .note-kind { color: var(--neg); }
.note-tile-context {
  border-left-color: var(--gs-grey-40);
  background: var(--gs-grey-05);
}
.note-tile-context .note-icon,
.note-tile-context .note-kind { color: var(--text-dim); }
.note-tile-fact {
  border-left-color: var(--pos);
  background: var(--pos-soft);
}
.note-tile-fact .note-icon,
.note-tile-fact .note-kind { color: var(--pos); }

/* dashboard summary banner - markdown body rendered below the
   global filter bar, above the first row / tab bar. Used for the
   one-paragraph "today's read" / "executive summary" that sits at
   the top of the page so PRISM can frame the dashboard before any
   chart loads. Uses .markdown-body typography for parity with the
   markdown widget. */
.summary-banner {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--gs-navy);
  border-radius: var(--radius);
  padding: 12px 18px;
  margin: 14px 28px 0 28px;
}
.summary-banner > :first-child { margin-top: 0; }
.summary-banner > :last-child { margin-bottom: 0; }

/* divider tile */
.divider-tile {
  background: transparent; border: none; box-shadow: none;
  padding: 8px 0;
}
.divider-tile hr {
  border: none; border-top: 1px solid var(--gs-grey-20);
  margin: 0;
}

/* table tile */
.table-tile .tile-body { padding: 0; }
.data-grid-tile { min-width: 0; }
.data-grid-tile .tile-body { min-height: 240px; }
.table-virtual-scroll {
  overflow: auto; position: relative; overscroll-behavior: contain;
  scrollbar-gutter: stable;
}
.table-virtual-status {
  position: sticky; bottom: 0; padding: 7px 12px;
  border-top: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  color: var(--text-faint); font-size: 10px; text-align: center;
  font-family: var(--gs-font-sans);
}
.data-table {
  border-collapse: collapse; width: 100%; font-size: 12px;
  font-family: var(--gs-font-sans);
  font-variant-numeric: tabular-nums;
}
.data-table thead { background: var(--gs-grey-05);
                      position: sticky; top: 0;
                      border-bottom: 2px solid var(--gs-navy); }
.data-table th {
  padding: 8px 12px; text-align: left; font-weight: 700;
  color: var(--gs-ink); text-transform: uppercase;
  letter-spacing: 0.08em; font-size: 10px;
}
.data-table td {
  padding: 8px 12px; border-bottom: 1px solid var(--border);
  color: var(--text);
}
.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: var(--surface-hover); }
.data-table.compact th { padding: 5px 8px; font-size: 9px; }
.data-table.compact td { padding: 5px 8px; font-size: 11px; }
.data-table.clickable tbody tr { cursor: pointer; }
.data-table th.sortable { cursor: pointer; user-select: none; }
.data-table th.sortable:hover { background: var(--gs-grey-10); }
/* Drawer "Freeze first col" toggle. Pins col 1 to the left edge so
   wide tables stay readable when scrolled horizontally. We pair the
   sticky position with a solid background so the pinned cells aren't
   transparent over scrolled content. */
.data-table.freeze-first-col th:first-child,
.data-table.freeze-first-col td:first-child {
  position: sticky; left: 0; z-index: 1;
  background: var(--surface);
  box-shadow: 1px 0 0 var(--border);
}
.data-table.freeze-first-col thead th:first-child {
  background: var(--gs-grey-05);
}

/* Row highlight buckets (see row_highlight on table widgets).
   Subtle left-border accent + tinted background so the row pops
   without stomping the per-cell conditional colors. Note: the
   `--pos-soft` / `--neg-soft` variables are deliberately used
   directly here -- avoiding `color-mix(in srgb, ..., transparent)`
   so html2canvas (used by the Download dropdown's "Panel" item) can
   parse this rule. The visual difference is imperceptible because
   both vars are already very low-alpha rgba. */
.data-table tr.row-hl-pos td   { background: var(--pos-soft); }
.data-table tr.row-hl-pos td:first-child {
  box-shadow: inset 3px 0 0 var(--pos);
}
.data-table tr.row-hl-neg td   { background: var(--neg-soft); }
.data-table tr.row-hl-neg td:first-child {
  box-shadow: inset 3px 0 0 var(--neg);
}
.data-table tr.row-hl-warn td  { background: rgba(221, 107, 32, 0.08); }
.data-table tr.row-hl-warn td:first-child {
  box-shadow: inset 3px 0 0 #dd6b20;
}
.data-table tr.row-hl-info td  { background: rgba(49, 130, 206, 0.07); }
.data-table tr.row-hl-info td:first-child {
  box-shadow: inset 3px 0 0 var(--accent);
}
.data-table tr.row-hl-muted td { background: var(--gs-grey-05);
                                   color: var(--text-dim); }

.table-toolbar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; background: var(--gs-grey-05);
  border-bottom: 1px solid var(--border);
}
.table-toolbar .table-search {
  flex: 1; min-width: 120px; max-width: 320px;
  padding: 6px 10px; border: 1px solid var(--border);
  border-radius: 4px; font-size: 12px; font-family: var(--gs-font-sans);
  background: var(--surface);
}
.table-toolbar .table-search:focus { outline: none; border-color: var(--gs-navy); }
.table-toolbar .table-count {
  color: var(--text-faint); font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.table-toolbar .table-xlsx-btn {
  margin-left: auto;
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-dim); border-radius: 4px;
  padding: 5px 10px; font-size: 11px;
  font-family: var(--gs-font-sans); font-weight: 600;
  letter-spacing: 0.04em; cursor: pointer;
  transition: background 0.12s var(--ease), color 0.12s var(--ease),
              border-color 0.12s var(--ease);
}
.table-toolbar .table-xlsx-btn:hover {
  background: var(--gs-navy); color: #fff; border-color: var(--gs-navy);
}
.table-toolbar .table-xlsx-btn:focus {
  outline: 2px solid var(--accent-ring); outline-offset: 2px;
}
.table-empty {
  padding: 32px 16px; text-align: center; color: var(--text-faint);
  font-size: 12px; font-style: italic;
}

/* modal popup (row-click details) */
.ed-modal-backdrop {
  position: fixed; inset: 0; background: rgba(26, 54, 93, 0.45);
  display: none; align-items: center; justify-content: center;
  z-index: 9999;
}
.ed-modal {
  background: var(--surface); border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
  max-width: 640px; min-width: 360px;
  max-height: 86vh; overflow: auto;
  border-top: 4px solid var(--gs-navy);
}
.ed-modal.wide {
  max-width: 880px; min-width: 560px;
}
.ed-modal-header {
  padding: 14px 18px; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 14px;
}
.ed-modal-title-wrap { flex: 1 1 auto; min-width: 0; }
.ed-modal-title { font-weight: 600; font-size: 16px; color: var(--gs-navy);
                    font-family: var(--gs-font-serif); }
.ed-modal-subtitle {
  font-size: 12px; color: var(--text-dim); font-style: italic;
  margin-top: 2px; display: none;
}
.ed-modal-close {
  background: transparent; border: none; cursor: pointer;
  font-size: 16px; color: var(--text-faint); padding: 4px 8px;
}
.ed-modal-close:hover { color: var(--text); }
.ed-modal-body {
  padding: 16px 18px; font-size: 13px; line-height: 1.55;
  color: var(--text);
}
.ed-modal-body p { margin: 0 0 10px; }
.ed-modal-body p:last-child { margin-bottom: 0; }
.ed-modal-body h1, .ed-modal-body h2, .ed-modal-body h3,
.ed-modal-body h4, .ed-modal-body h5 {
  font-family: var(--gs-font-sans); color: var(--gs-navy);
  margin: 0 0 10px; font-weight: 600;
}
.ed-modal-body h1 { font-size: 16px; }
.ed-modal-body h2 { font-size: 14px; }
.ed-modal-body h3 { font-size: 13px; text-transform: uppercase;
                     letter-spacing: 0.04em; color: var(--text-faint); }
.ed-modal-body h4 { font-size: 13px; color: var(--text); }
.ed-modal-body h5 { font-size: 12px; color: var(--text-dim);
                     font-style: italic; }
.ed-modal-body ul, .ed-modal-body ol {
  margin: 6px 0 12px 18px; padding: 0;
}
.ed-modal-body li { margin-bottom: 4px; }
.ed-modal-body ul ul, .ed-modal-body ul ol,
.ed-modal-body ol ul, .ed-modal-body ol ol {
  margin: 4px 0 4px 18px;
}
.ed-modal-body blockquote {
  margin: 8px 0; padding: 6px 12px;
  border-left: 3px solid var(--accent-2);
  background: rgba(115,153,198,0.08);
  color: var(--text-dim); font-style: italic;
}
.ed-modal-body pre {
  margin: 8px 0; padding: 8px 12px;
  background: var(--gs-grey-05); border: 1px solid var(--border);
  border-radius: var(--radius-sm); overflow-x: auto;
}
.ed-modal-body pre code {
  background: none; padding: 0;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 12px; color: var(--text);
}
.ed-modal-body hr {
  margin: 12px 0; border: none;
  border-top: 1px solid var(--border);
}
.ed-modal-body del { color: var(--text-faint); }
.ed-modal-body table.md-table {
  border-collapse: collapse; margin: 8px 0;
  font-family: var(--gs-font-sans); font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.ed-modal-body table.md-table th {
  text-align: left; padding: 5px 10px;
  border-bottom: 1px solid var(--gs-navy);
  background: var(--gs-grey-05);
  text-transform: uppercase; font-size: 10px;
  letter-spacing: 0.08em; color: var(--gs-ink);
}
.ed-modal-body table.md-table td {
  padding: 5px 10px; border-bottom: 1px solid var(--border);
}
.ed-modal-body strong { color: var(--gs-navy); font-weight: 600; }
.ed-modal-body em { color: var(--text); }
.ed-modal-body code {
  background: var(--gs-grey-05); padding: 1px 6px;
  border-radius: 3px; font-family: ui-monospace, monospace;
  font-size: 12px;
}
.ed-modal-body a {
  color: var(--accent); text-decoration: underline;
  text-underline-offset: 2px;
}
.ed-modal-body a:hover { color: var(--gs-navy); }
.modal-detail-table {
  width: 100%; border-collapse: collapse; font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.modal-detail-table th {
  text-align: left; padding: 6px 12px 6px 0; width: 42%;
  color: var(--text-faint); font-weight: 500; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.modal-detail-table td {
  padding: 6px 0; color: var(--text);
  border-bottom: 1px solid var(--border);
}
.modal-detail-table tr:last-child td { border-bottom: none; }
.modal-extra {
  margin-top: 14px; padding-top: 14px;
  border-top: 1px solid var(--border); font-size: 12px;
  color: var(--text-faint);
}

/* View Data modal (chart controls -> View data) */
.view-data-table {
  width: 100%; border-collapse: collapse;
  font-size: 11px; font-variant-numeric: tabular-nums;
}
.view-data-table th, .view-data-table td {
  text-align: right; padding: 4px 10px; border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.view-data-table th {
  text-align: left; color: var(--text-faint); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em; font-size: 9.5px;
  background: var(--surface-2); position: sticky; top: 0;
}
.view-data-table td:first-child, .view-data-table th:first-child {
  text-align: left; font-weight: 500; color: var(--text);
}
.view-data-table tr:hover td { background: var(--surface-2); }
.view-data-meta {
  font-size: 11px; color: var(--text-faint);
  margin-bottom: 8px; font-family: var(--gs-font-sans);
}
.view-data-scroll { max-height: 60vh; overflow: auto;
                    border: 1px solid var(--border);
                    border-radius: var(--radius-sm); }

/* Rich row-click detail layout (row_click.detail.sections) */
.detail-section-title {
  font-family: var(--gs-font-sans); font-size: 10px;
  text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--text-faint); font-weight: 600;
  margin: 18px 0 8px;
}
.detail-section-title:first-child { margin-top: 4px; }
.detail-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 1px; background: var(--border);
  border-radius: 4px; overflow: hidden;
  margin-bottom: 6px;
}
.detail-stat {
  background: var(--surface); padding: 10px 12px;
  display: flex; flex-direction: column; gap: 2px;
}
.detail-stat-label {
  font-size: 10px; color: var(--text-faint);
  text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600;
}
.detail-stat-value {
  font-family: var(--gs-font-serif); font-size: 18px;
  color: var(--gs-navy); font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.detail-stat.pos .detail-stat-value { color: var(--pos); }
.detail-stat.neg .detail-stat-value { color: var(--neg); }
.detail-stat-sub { font-size: 10px; color: var(--text-dim); }
.detail-chart {
  width: 100%; margin: 4px 0 12px;
  border: 1px solid var(--border); border-radius: 4px;
  background: var(--surface);
}
.detail-chart-empty {
  padding: 24px; text-align: center; color: var(--text-faint);
  font-size: 12px; font-style: italic;
}
.detail-markdown {
  font-size: 13px; color: var(--text); line-height: 1.55;
  margin: 4px 0 12px;
}
.detail-markdown p { margin: 0 0 8px; }
.detail-markdown ul { margin: 4px 0 8px 16px; }
.detail-markdown strong { color: var(--gs-navy); }
.detail-markdown code {
  background: var(--gs-grey-05); padding: 1px 5px;
  border-radius: 3px; font-family: ui-monospace, monospace;
  font-size: 12px;
}
.detail-markdown a {
  color: var(--accent); text-decoration: underline;
  text-underline-offset: 2px;
}
.modal-detail-table.sub th {
  font-size: 10px; padding-top: 4px;
}
.modal-detail-table.sub td {
  font-size: 12px; padding: 4px 8px 4px 0;
}

/* provenance footer (driven by dataset.field_provenance) */
.provenance-footer {
  margin-top: 14px; padding-top: 12px;
  border-top: 1px dashed var(--border);
}
.provenance-footer .detail-section-title {
  margin: 0 0 6px;
}
.provenance-footer table.provenance-table {
  font-size: 11px; color: var(--text-dim);
}
.provenance-footer table.provenance-table th {
  width: 38%; font-size: 10px;
  color: var(--text-faint); font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.05em;
  padding: 4px 12px 4px 0;
}
.provenance-footer table.provenance-table td {
  padding: 4px 0; color: var(--text-dim);
}
.provenance-footer table.provenance-table code {
  background: var(--gs-grey-05); padding: 1px 5px;
  border-radius: 3px; font-family: ui-monospace, monospace;
  font-size: 10.5px; color: var(--gs-navy);
}
.provenance-footer .prov-system {
  font-family: var(--gs-font-sans);
  text-transform: uppercase; letter-spacing: 0.05em;
  font-size: 9.5px; color: var(--text-faint);
}
.provenance-footer .prov-units {
  font-style: italic; color: var(--text-faint);
}
.detail-stat-src {
  font-size: 10px; color: var(--text-faint);
  margin-top: 2px;
}
.detail-stat-src code {
  background: var(--gs-grey-05); padding: 1px 4px;
  border-radius: 3px; font-family: ui-monospace, monospace;
  font-size: 10px; color: var(--gs-navy);
}

/* filter widgets extensions */
.filter-item.slider { min-width: 200px; }
.filter-item.slider .slider-row {
  display: flex; align-items: center; gap: 8px;
}
.filter-item.slider input[type="range"] { flex: 1; }
.filter-item.slider .slider-val {
  min-width: 36px; text-align: right;
  font-variant-numeric: tabular-nums; color: var(--gs-navy);
  font-weight: 600; font-size: 12px;
}
.filter-item.radio-group .radio-row {
  display: flex; gap: 14px; align-items: center; flex-wrap: wrap;
}
.filter-item.radio-group label.radio-opt {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--text); font-weight: 400;
  text-transform: none; letter-spacing: 0; cursor: pointer;
}
.filter-item.rule {
  align-items: center;
  gap: 6px;
}
.filter-item.rule .filter-rule-toggle {
  display: inline-flex; align-items: center; gap: 6px;
  cursor: pointer;
  padding: 4px 10px;
  border: 1px solid var(--border, #ccd1da);
  border-radius: 4px;
  background: var(--surface, #fff);
  font-size: 0.82rem;
}
.filter-item.rule .filter-rule-toggle:hover {
  background: var(--surface-hover, #f5f7fa);
}
.filter-item.rule input[type="checkbox"] {
  margin: 0;
}
.filter-item.rule .filter-rule-label {
  font-weight: 600;
  color: var(--ink, #1a1a1a);
}
.filter-item.rule .filter-rule-summary {
  color: var(--text-secondary, #777);
  font-size: 0.78rem;
}
:root[data-theme="dark"] .filter-item.rule .filter-rule-toggle {
  background: var(--surface, #1f242e);
  border-color: var(--border, #2a2f3a);
  color: var(--text, #e8eaee);
}
:root[data-theme="dark"] .filter-item.rule .filter-rule-toggle:hover {
  background: var(--surface-hover, #232936);
}
.filter-item.text input[type="text"],
.filter-item.number input[type="number"] {
  padding: 6px 10px; border: 1px solid var(--border);
  border-radius: 4px; font-size: 12px;
  font-family: var(--gs-font-sans);
  background: var(--surface);
  min-width: 120px;
}
.filter-item.text input[type="text"]:focus,
.filter-item.number input[type="number"]:focus {
  outline: none; border-color: var(--gs-navy);
}

/* stat_grid widget */
.stat-grid-tile .tile-body { padding: 0; }
.stat-grid-tile .stat-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1px; background: var(--border);
}
.stat-grid-tile .stat-cell {
  background: var(--surface); padding: 12px 14px;
  display: flex; flex-direction: column; gap: 4px;
  cursor: default;
}
.stat-grid-tile .stat-label {
  font-size: 10px; color: var(--text-faint);
  text-transform: uppercase; letter-spacing: 0.08em; font-weight: 500;
  display: inline-flex; align-items: center; gap: 4px;
}
.stat-grid-tile .stat-info {
  font-size: 11px; color: var(--text-faint); cursor: pointer;
  text-transform: none; border-radius: 50%;
}
.stat-grid-tile .stat-info:hover { color: var(--accent);
                                     background: var(--surface-hover); }
.stat-grid-tile .stat-info:focus { outline: 2px solid var(--accent-ring);
                                     outline-offset: 2px; }
.stat-grid-tile .stat-value {
  font-size: 18px; color: var(--gs-navy); font-weight: 700;
  font-variant-numeric: tabular-nums;
  display: inline-flex; align-items: baseline; gap: 6px;
}
.stat-grid-tile .stat-trend {
  font-size: 12px;
}
.stat-grid-tile .stat-trend.pos  { color: var(--pos); }
.stat-grid-tile .stat-trend.neg  { color: var(--neg); }
.stat-grid-tile .stat-trend.flat { color: var(--text-faint); }
.stat-grid-tile .stat-sub {
  font-size: 10px; color: var(--text-faint);
}

/* image widget */
.image-tile .tile-body {
  padding: 0; display: flex; align-items: center; justify-content: center;
}
.image-tile img { max-width: 100%; max-height: 100%; display: block; }

.status { color: var(--text-faint); font-size: 11px;
          font-family: var(--gs-font-sans);
          font-variant-numeric: tabular-nums; }

footer.app-footer {
  padding: 14px 28px; border-top: 1px solid var(--border);
  background: var(--gs-grey-05); color: var(--text-faint);
  font-size: 11px; font-family: var(--gs-font-sans);
  letter-spacing: 0.02em;
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 8px;
}
footer.app-footer .gs-mark .gs-box {
  width: 22px; height: 22px; font-size: 11px;
}
footer.app-footer .gs-mark .gs-wordmark { font-size: 12px; }

/* responsive */
@media (max-width: 1024px) {
  .grid > .tile { grid-column: span 6; }
}
@media (max-width: 720px) {
  .grid > .tile { grid-column: span 12; }
  header.app-header { padding: 14px 16px; }
  nav.tab-bar { padding: 0 16px; }
  .filter-bar { padding: 10px 16px; }
  main.app-main { padding: 14px 16px; }
}
:root.dashboard-printing .tab-panel { display: block !important; }
@media print {
  @page { size: landscape; margin: 10mm; }
  :root, :root[data-theme="dark"] {
    --page-bg: #FFFFFF; --surface: #FFFFFF; --surface-2: #F7F9FB;
    --text: #1A1A1A; --text-dim: #595959; --text-faint: #595959;
    --border: #BFBFBF; --border-strong: #999999;
  }
  body { background: #FFFFFF !important; color: #1A1A1A !important; }
  .theme-toggle, .download-menu, .tile-actions, .chart-controls,
  .filter-bar, .tab-bar, footer.app-footer { display: none !important; }
  .tab-panel { display: block !important; break-before: page; }
  .tab-panel:first-of-type { break-before: auto; }
  .tile, .layout-group { break-inside: avoid; box-shadow: none !important; }
  .data-grid-tile { break-inside: auto; }
  .table-virtual-scroll {
    max-height: none !important; overflow: visible !important;
  }
  .table-virtual-status { display: none !important; }
  main.app-main { padding: 0; }
}

/* tool widget */
.tool-tile { padding: 0; }
.tool-tile .tile-header { padding: 14px 18px 8px 18px; }
.tool-tile .tool-body {
  display: flex; flex-direction: row; gap: 18px;
  padding: 8px 18px 16px 18px;
  align-items: stretch;
}
.tool-tile.tool-stacked .tool-body { flex-direction: column; }
.tool-tile .tool-input-panel {
  flex: 0 0 auto;
  display: flex; flex-direction: column; gap: 10px;
  border-right: 1px solid var(--border, #d8dde5);
  padding-right: 18px;
  min-width: 240px;
}
.tool-tile.tool-stacked .tool-input-panel {
  border-right: none;
  border-bottom: 1px solid var(--border, #d8dde5);
  padding-right: 0;
  padding-bottom: 14px;
}
.tool-tile .tool-output-panel {
  flex: 1 1 auto;
  display: flex; flex-direction: column; gap: 14px;
  min-width: 0;
}
.tool-input-row {
  display: flex; flex-direction: column; gap: 4px;
}
.tool-input-row.inline { flex-direction: row; align-items: center; gap: 10px; }
.tool-input-row label {
  font-size: 0.78rem; font-weight: 600;
  color: var(--text-secondary, #555);
  letter-spacing: 0.02em;
}
.tool-input-row input[type=number],
.tool-input-row input[type=date],
.tool-input-row input[type=text],
.tool-input-row select {
  padding: 6px 10px; font-size: 0.88rem;
  border: 1px solid var(--border, #ccd1da);
  border-radius: 4px;
  background: var(--surface, #fff);
  color: var(--ink, #1a1a1a);
  min-width: 140px;
  font-family: inherit;
}
.tool-input-row.tool-range .tool-range-row {
  display: flex; align-items: center; gap: 8px;
}
.tool-input-row.tool-range input[type=range] {
  flex: 1; min-width: 0; accent-color: var(--gs-navy, #002F6C);
}
.tool-input-row.tool-range .tool-range-val {
  min-width: 44px; text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--gs-navy, #002F6C);
  font-weight: 600; font-size: 0.82rem;
}
.tool-input-row input:focus, .tool-input-row select:focus {
  outline: none; border-color: var(--gs-navy, #002F6C);
  box-shadow: 0 0 0 2px rgba(0,47,108,0.12);
}
.tool-input-radio { display: flex; flex-direction: row; gap: 12px; }
.tool-input-radio label {
  font-size: 0.85rem; font-weight: 400; color: var(--ink, #1a1a1a);
  display: flex; align-items: center; gap: 4px;
  cursor: pointer;
}
.tool-input-row[data-hidden="true"] { display: none; }

.tool-input-matrix { display: flex; flex-direction: column; gap: 6px; }
.tool-matrix-header {
  display: flex; align-items: center; gap: 10px;
  justify-content: space-between;
}
.tool-matrix-header label {
  font-size: 0.78rem; font-weight: 600;
  color: var(--text-secondary, #555);
  letter-spacing: 0.02em;
}
.tool-matrix-actions { display: flex; gap: 6px; }
.tool-matrix-btn {
  font-size: 0.72rem;
  padding: 3px 9px;
  border: 1px solid var(--border, #ccd1da);
  background: var(--surface, #fff);
  color: var(--text-secondary, #555);
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
}
.tool-matrix-btn:hover { background: var(--surface-hover, #f5f7fa); }
.tool-matrix-grid-wrap {
  max-height: 320px; overflow-y: auto;
  border: 1px solid var(--border, #d8dde5);
  border-radius: 4px;
}
.tool-matrix-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.tool-matrix-table thead th {
  position: sticky; top: 0; z-index: 1;
  background: var(--surface-2, #f5f7fa);
  text-align: center; font-weight: 600;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border, #d8dde5);
  color: var(--text-secondary, #555);
}
.tool-matrix-table thead th:first-child { text-align: left; }
.tool-matrix-table tbody th {
  text-align: left; font-weight: 500;
  padding: 4px 8px;
  color: var(--ink, #1a1a1a);
  background: var(--surface, #fff);
  border-bottom: 1px solid var(--border, #eef0f4);
  white-space: nowrap;
}
.tool-matrix-table tbody td {
  padding: 2px 4px;
  border-bottom: 1px solid var(--border, #eef0f4);
  text-align: right;
}
.tool-matrix-table tbody td input[type=number] {
  width: 64px; padding: 3px 6px;
  font-size: 0.82rem;
  text-align: right;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 3px;
  font-family: inherit;
  color: var(--ink, #1a1a1a);
}
.tool-matrix-table tbody td input[type=number]:focus {
  outline: none; border-color: var(--gs-navy, #002F6C);
  background: var(--surface, #fff);
  box-shadow: 0 0 0 2px rgba(0,47,108,0.10);
}
.tool-matrix-table tbody td input[type=number].nonzero {
  background: rgba(115, 153, 198, 0.08);
  font-weight: 600;
}

.tool-matrix-paste-pane {
  border: 1px solid var(--border, #ccd1da);
  background: var(--surface-2, #f5f7fa);
  padding: 10px;
  border-radius: 4px;
  display: flex; flex-direction: column; gap: 6px;
}
.tool-matrix-paste-pane[hidden] { display: none !important; }
.tool-error[hidden] { display: none !important; }
.tool-input-row[data-hidden="true"] { display: none !important; }
.tool-matrix-paste-pane textarea {
  width: 100%; min-height: 80px;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 0.78rem;
  border: 1px solid var(--border, #ccd1da);
  border-radius: 3px;
  padding: 6px 8px;
  resize: vertical;
  background: var(--surface, #fff);
  color: var(--ink, #1a1a1a);
}
.tool-matrix-paste-actions {
  display: flex; gap: 6px; justify-content: flex-end;
}
.tool-matrix-paste-pane .pane-hint {
  font-size: 0.72rem; color: var(--text-secondary, #777);
}

.tool-output-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  padding: 10px;
  background: var(--surface-2, #f9fafc);
  border: 1px solid var(--border, #eef0f4);
  border-radius: 4px;
}
.tool-stat-cell {
  display: flex; flex-direction: column; gap: 2px;
  padding: 4px 8px;
}
.tool-stat-cell .label {
  font-size: 0.72rem; font-weight: 600;
  color: var(--text-secondary, #777);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.tool-stat-cell .value {
  font-size: 1.18rem; font-weight: 700;
  color: var(--ink, #1a1a1a);
  font-variant-numeric: tabular-nums;
}
.tool-output-section {
  display: flex; flex-direction: column; gap: 6px;
}
.tool-output-section .section-label {
  font-size: 0.78rem; font-weight: 600;
  color: var(--text-secondary, #555);
  letter-spacing: 0.02em;
}
.tool-output-table {
  width: 100%; border-collapse: collapse;
  font-size: 0.84rem;
}
.tool-output-table thead th {
  font-weight: 600;
  padding: 5px 10px;
  border-bottom: 1px solid var(--border, #d8dde5);
  background: var(--surface-2, #f5f7fa);
  color: var(--text-secondary, #555);
  text-align: right;
}
.tool-output-table thead th:first-child { text-align: left; }
.tool-output-table tbody td {
  padding: 4px 10px;
  border-bottom: 1px solid var(--border, #eef0f4);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.tool-output-table tbody td.first-col {
  text-align: left; font-weight: 500;
}
.tool-output-chart-host {
  width: 100%; min-height: 200px;
}
.tool-chart-empty {
  display: flex; align-items: center; justify-content: center;
  min-height: 180px; padding: 16px;
  border: 1px dashed var(--border, #ccd1da);
  border-radius: 4px;
  color: var(--text-secondary, #777);
  font-size: 0.82rem; text-align: center;
}
.tool-output-stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
}
.tool-output-stat-grid .tool-stat-cell {
  background: var(--surface-2, #f9fafc);
  border: 1px solid var(--border, #eef0f4);
  border-radius: 4px;
}
.tool-stat-section .tool-stat-cell {
  background: var(--surface-2, #f9fafc);
  border: 1px solid var(--border, #eef0f4);
  border-radius: 4px;
}
.tool-error {
  padding: 10px 14px;
  background: rgba(180, 30, 30, 0.06);
  border: 1px solid rgba(180, 30, 30, 0.3);
  color: #b41e1e;
  font-size: 0.82rem;
  border-radius: 4px;
  font-family: ui-monospace, Consolas, monospace;
  white-space: pre-wrap;
}

:root[data-theme="dark"] .tool-tile .tool-input-panel {
  border-right-color: var(--border, #2a2f3a);
}
:root[data-theme="dark"] .tool-input-row.tool-range .tool-range-val {
  color: var(--text, #e8eaed);
}
:root[data-theme="dark"] .tool-input-row input,
:root[data-theme="dark"] .tool-input-row select,
:root[data-theme="dark"] .tool-matrix-paste-pane textarea {
  background: var(--surface, #1f242e);
  border-color: var(--border, #2a2f3a);
  color: var(--text, #e8eaee);
}
:root[data-theme="dark"] .tool-matrix-table thead th {
  background: var(--surface-2, #161a22);
  border-bottom-color: var(--border, #2a2f3a);
}
:root[data-theme="dark"] .tool-matrix-table tbody th {
  background: var(--surface, #1f242e);
  color: var(--text, #e8eaee);
}
:root[data-theme="dark"] .tool-matrix-table tbody td input[type=number] {
  color: var(--text, #e8eaee);
}
:root[data-theme="dark"] .tool-matrix-table tbody td input[type=number].nonzero {
  background: rgba(115, 153, 198, 0.16);
}
:root[data-theme="dark"] .tool-output-stats {
  background: var(--surface-2, #161a22);
  border-color: var(--border, #2a2f3a);
}
:root[data-theme="dark"] .tool-output-table thead th {
  background: var(--surface-2, #161a22);
  border-bottom-color: var(--border, #2a2f3a);
}
:root[data-theme="dark"] .tool-matrix-btn {
  background: var(--surface, #1f242e);
  color: var(--text-secondary, #aaa);
  border-color: var(--border, #2a2f3a);
}

/* persisted user input widget */
.user-input-tile .tile-header {
  padding: 14px 18px 8px 18px;
}
.user-input-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 18px 16px 18px;
}
.user-input-description {
  color: var(--text-dim);
  font-size: 0.82rem;
  line-height: 1.4;
  padding: 0 18px 4px 18px;
}
.user-input-access {
  color: var(--text-faint);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.user-input-status {
  min-height: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-faint);
  font-size: 0.76rem;
}
.user-input-tile[data-user-input-state="dirty"] .user-input-status {
  color: #8A5A00;
}
.user-input-tile[data-user-input-state="saving"] .user-input-status {
  color: var(--gs-navy);
}
.user-input-tile[data-user-input-state="saved"] .user-input-status {
  color: var(--pos);
}
.user-input-tile[data-user-input-state="conflict"] .user-input-status,
.user-input-tile[data-user-input-state="unavailable"] .user-input-status {
  color: var(--neg);
}
.user-input-textarea {
  width: 100%;
  min-height: 110px;
  resize: vertical;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  line-height: 1.45;
}
.user-input-textarea:focus,
.user-input-checklist-text:focus,
.user-input-file-picker:focus {
  outline: none;
  border-color: var(--gs-navy);
  box-shadow: 0 0 0 2px rgba(0,47,108,0.12);
}
.user-input-textarea:disabled,
.user-input-checklist-text:disabled {
  background: var(--surface-2);
  color: var(--text-dim);
}
.user-input-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
.user-input-button,
.user-input-link-button {
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text);
  padding: 6px 10px;
  font: inherit;
  font-size: 0.78rem;
  cursor: pointer;
}
.user-input-button:hover,
.user-input-link-button:hover {
  background: var(--surface-2);
}
.user-input-button:disabled {
  cursor: default;
  opacity: 0.45;
}
.user-input-button.user-input-primary {
  background: var(--gs-navy);
  border-color: var(--gs-navy);
  color: #FFFFFF;
}
.user-input-button.user-input-compact {
  padding: 4px 7px;
  font-size: 0.7rem;
}
.user-input-link-button {
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  text-decoration: underline;
}
.user-input-checklist,
.user-input-file-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.user-input-checklist-row,
.user-input-file-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.user-input-checklist-text {
  flex: 1 1 auto;
  min-width: 0;
  padding: 7px 9px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
}
.user-input-file-row {
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}
.user-input-file-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.user-input-file-name {
  color: var(--gs-navy);
  font-size: 0.84rem;
  overflow-wrap: anywhere;
}
.user-input-file-meta,
.user-input-empty {
  color: var(--text-faint);
  font-size: 0.74rem;
}
.user-input-file-picker {
  flex: 1 1 260px;
  min-width: 0;
  color: var(--text-dim);
  font-size: 0.78rem;
}
:root[data-theme="dark"] .user-input-button.user-input-primary {
  background: var(--gs-sky);
  border-color: var(--gs-sky);
  color: #081526;
}

/* motion preferences */
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
</style>
</head>
<body>
<div class="app">
  <header class="app-header">
    <div class="header-titles">
      __HEADER_BRAND__
      <h1>__TITLE__</h1>
      <div class="subtitle">__DESCRIPTION__</div>
    </div>
    <div class="header-right">
      <div class="header-actions" id="header-actions">
        <button class="icon-btn" id="methodology-btn"
                title="View dashboard methodology" style="display:none">
          Methodology
        </button>
        <button class="icon-btn" id="refresh-btn"
                title="Refresh dashboard data" style="display:none">
          <span id="refresh-btn-label">Refresh</span>
        </button>
        <button class="icon-btn refresh-err-info" id="refresh-err-btn"
                title="Last refresh failed -- click for full error details + copy-for-PRISM"
                aria-label="Refresh error details"
                style="display:none">
          ! Error details
        </button>
        <div class="share-dd" id="share-dd" style="display:none">
          <button class="icon-btn" id="share-btn" type="button"
                  title="Share this dashboard"
                  aria-haspopup="menu" aria-expanded="false">
            <span id="share-btn-label">Share</span>
            <span class="share-caret" aria-hidden="true">&#x25BE;</span>
          </button>
          <ul class="share-menu" id="share-menu" role="menu"
              aria-label="Share options" hidden>
            <li role="none">
              <button type="button" role="menuitem"
                      class="share-menu-item" id="share-mode-public"
                      title="Anyone in Goldman can find this in the Community gallery.">
                <span class="share-menu-icon">&#x1F310;</span>
                <span class="share-menu-label">
                  <strong>Make public</strong>
                  <span class="share-menu-sub">Anyone can find this in the Community gallery</span>
                </span>
              </button>
            </li>
            <li role="none">
              <button type="button" role="menuitem"
                      class="share-menu-item" id="share-mode-link"
                      title="Anyone with the link can open this dashboard. Not listed in the gallery.">
                <span class="share-menu-icon">&#x1F517;</span>
                <span class="share-menu-label">
                  <strong>Share with link</strong>
                  <span class="share-menu-sub">Anyone with the link can view; not listed publicly</span>
                </span>
              </button>
            </li>
            <li role="none">
              <button type="button" role="menuitem"
                      class="share-menu-item" id="share-mode-users"
                      title="Share this dashboard with specific colleagues.">
                <span class="share-menu-icon">&#x1F464;</span>
                <span class="share-menu-label">
                  <strong>Share with people</strong>
                  <span class="share-menu-sub">Pick specific colleagues</span>
                </span>
              </button>
            </li>
            <li role="none">
              <button type="button" role="menuitem"
                      class="share-menu-item" id="share-mode-department"
                      title="Share this dashboard with your department.">
                <span class="share-menu-icon">&#x1F3E2;</span>
                <span class="share-menu-label">
                  <strong>Share with my department</strong>
                  <span class="share-menu-sub">Everyone in your department can view</span>
                </span>
              </button>
            </li>
            <li role="none" class="share-menu-has-submenu"
                id="share-workspace-host">
              <button type="button" role="menuitem"
                      class="share-menu-item" id="share-add-workspace"
                      title="Add this dashboard to a workspace you belong to."
                      aria-haspopup="menu" aria-expanded="false">
                <span class="share-menu-icon">&#x25A6;</span>
                <span class="share-menu-label">
                  <strong>Add to workspace</strong>
                  <span class="share-menu-sub">Share into a workspace pool</span>
                </span>
                <span class="share-menu-submenu-caret"
                      aria-hidden="true">&#x25C0;</span>
              </button>
              <ul class="share-submenu" id="share-workspace-submenu"
                  role="menu" aria-label="Your workspaces" hidden>
                <li class="share-submenu-status" role="none">
                  Open to load your workspaces
                </li>
              </ul>
            </li>
            <li class="share-menu-divider" role="separator"></li>
            <li role="none">
              <button type="button" role="menuitem"
                      class="share-menu-item danger" id="share-mode-private"
                      title="Make private. Existing share links stop working.">
                <span class="share-menu-icon">&#x1F512;</span>
                <span class="share-menu-label">
                  <strong>Stop sharing</strong>
                  <span class="share-menu-sub">Make private; existing links break</span>
                </span>
              </button>
            </li>
          </ul>
        </div>
        <div class="download-dd" id="download-dd">
          <button class="icon-btn" id="download-btn"
                  type="button"
                  title="Download dashboard contents"
                  aria-haspopup="menu" aria-expanded="false">
            <span id="download-btn-label">Download</span>
            <span class="download-caret" aria-hidden="true">&#x25BE;</span>
          </button>
          <ul class="download-menu" id="download-menu" role="menu"
              aria-label="Download options" hidden>
            <li role="none">
              <button type="button" role="menuitem"
                      class="download-menu-item" id="export-full-dashboard"
                      title="Download this interactive dashboard as one self-contained HTML file.">
                Full Dashboard
              </button>
            </li>
            <li role="none">
              <button type="button" role="menuitem"
                      class="download-menu-item" id="export-dashboard"
                      title="Download the entire panel as one PNG (full page).">
                Panel
              </button>
            </li>
            <li role="none">
              <button type="button" role="menuitem"
                      class="download-menu-item" id="export-all"
                      title="Download all charts as individual PNGs (2x).">
                Charts
              </button>
            </li>
            <li role="none">
              <button type="button" role="menuitem"
                      class="download-menu-item" id="export-chart-data"
                      title="Download the currently filtered data behind each chart as CSV.">
                Chart Data (CSV)
              </button>
            </li>
            <li role="none">
              <button type="button" role="menuitem"
                      class="download-menu-item" id="export-print"
                      title="Open the intentional light-mode print layout for PDF or paper.">
                PDF / Print
              </button>
            </li>
            <li role="none" id="download-menu-excel-li" hidden>
              <button type="button" role="menuitem"
                      class="download-menu-item" id="export-excel"
                      title="Download all tables as one Excel workbook.">
                Excel
              </button>
            </li>
          </ul>
        </div>
        <button class="icon-btn theme-toggle" id="theme-toggle"
                type="button"
                title="Toggle light / dark mode"
                aria-label="Toggle light or dark mode"
                aria-pressed="false">
          <span class="toggle-glyph" aria-hidden="true"></span>
        </button>
      </div>
      <div class="header-meta">
        <span class="meta-dot" id="now-pill" style="display:none">
          <span id="now-pill-val"></span>
        </span>
        <span class="meta-dot" id="refresh-pill" style="display:none">
          <span id="refresh-pill-val"></span>
        </span>
      </div>
    </div>
  </header>
  __TAB_BAR__
  __FILTER_BAR__
  __SUMMARY__
  <main class="app-main">
    __TAB_PANELS__
  </main>
  <footer class="app-footer">
    <span class="gs-mark">
      <span class="gs-box">GS</span>
      <span class="gs-wordmark">Goldman Sachs</span>
    </span>
    <span class="status">
      echart_dashboard v__VERSION__ &middot; ECharts@5 &middot; __TIMESTAMP__
    </span>
  </footer>
</div>
<script>
__PAYLOAD__
__APP__
</script>
</body>
</html>
"""


DASHBOARD_APP_JS = r"""
(function(){
  'use strict';
  var MANIFEST = PAYLOAD.manifest;
  var SPECS    = PAYLOAD.specs;       // id -> ECharts option dict
  var DATASETS = PAYLOAD.datasets;    // name -> {source: [...rows]}

  // Preserve the generated source before load-time rendering mutates the DOM.
  // The shell already inlines ECharts, manifest data, styles, and runtime JS,
  // so this exact snapshot is a complete offline dashboard without fetching
  // the serving URL (which would fail for file:// dashboards).
  var STATIC_DASHBOARD_HTML =
    '<!doctype html>\n' + document.documentElement.outerHTML;

  // Global decimal-precision cap. Mirror of config.MAX_DASHBOARD_DECIMALS;
  // injected by render_dashboard_html so the two halves can never drift.
  // Every formatter helper in this runtime (formatNumber, formatValue,
  // _pivotFmt, _stripFmtNumber, _ccFmt, heatmap label formatters, etc.)
  // funnels its decimals input through __capDec so author-supplied
  // precision options (table format suffixes like "number:5", widget
  // decimals=4, value_decimals=3) get silently coerced down to the cap.
  // Hard-coded toFixed() literals in this file are also bounded by the
  // cap. Raise the cap by editing config.MAX_DASHBOARD_DECIMALS in
  // staging; both sides regenerate next render.
  var __MAX_DEC = __MAX_DECIMALS__;
  function __capDec(d, fb){
    var cap = __MAX_DEC;
    var fbn = (fb == null) ? 0 : (+fb | 0);
    if (fbn < 0) fbn = 0; if (fbn > cap) fbn = cap;
    if (d == null) return fbn;
    var n = +d;
    if (isNaN(n)) return fbn;
    n = n | 0;
    if (n < 0) return 0;
    if (n > cap) return cap;
    return n;
  }

  // Last-line-of-defence tooltip decimal cap. Mirrors the compile-time
  // pass in echart_studio._install_default_tooltip_decimal_cap so a
  // chart that somehow reached the runtime without a tooltip
  // ``valueFormatter`` (hand-edited spec, non-standard build path,
  // legacy snapshot) still cannot leak raw 12-digit floats. Skipped
  // when a custom ``formatter`` or ``valueFormatter`` is already
  // present -- ECharts calls ``valueFormatter`` per-value only when
  // no per-tooltip ``formatter`` overrides the whole template.
  function __ensureTooltipDecimalCap(opt){
    if (!opt || typeof opt !== 'object') return;
    var tt = opt.tooltip;
    if (!tt || typeof tt !== 'object') return;
    if (tt.formatter) return;
    if (tt.valueFormatter) return;
    var cap = __MAX_DEC;
    tt.valueFormatter = function(v){
      if (v == null) return '';
      if (typeof v === 'string') return v;
      if (Array.isArray(v)) {
        var out = [];
        for (var i = 0; i < v.length; i++){
          var x = v[i];
          if (x == null) { out.push(''); continue; }
          var nx = +x;
          if (isNaN(nx)) { out.push(String(x)); continue; }
          var sx = nx.toFixed(cap);
          if (sx.indexOf('.') >= 0) sx = sx.replace(/0+$/, '').replace(/\.$/, '');
          out.push(sx);
        }
        return out.join(', ');
      }
      var n = +v;
      if (isNaN(n)) return String(v);
      var s = n.toFixed(cap);
      if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
      return s;
    };
  }

  // Revive string-encoded JS functions (renderItem, formatter, filter)
  // into real functions. Python emits them as strings because JSON cannot
  // carry code; ECharts needs real functions at setOption() time.
  function _isFnStr(s) {
    return typeof s === 'string' && /^\s*function\s*\(/.test(s);
  }
  function reviveFns(x) {
    if (x == null) return x;
    if (_isFnStr(x)) {
      try { return new Function('return (' + x + ')')(); }
      catch(e) { return x; }
    }
    if (Array.isArray(x)) {
      for (var i = 0; i < x.length; i++) x[i] = reviveFns(x[i]);
      return x;
    }
    if (typeof x === 'object') {
      for (var k in x) {
        if (Object.prototype.hasOwnProperty.call(x, k)) {
          x[k] = reviveFns(x[k]);
        }
      }
    }
    return x;
  }

  // register themes so echarts can use them
  try {
    Object.keys(PAYLOAD.themes || {}).forEach(function(tn){
      try { echarts.registerTheme(tn, PAYLOAD.themes[tn]); } catch(e){}
    });
  } catch(e){}
  try {
    Object.keys(PAYLOAD.maps || {}).forEach(function(mapName){
      var asset = PAYLOAD.maps[mapName];
      var geojson = asset && asset.geojson ? asset.geojson : asset;
      echarts.registerMap(mapName, geojson);
    });
  } catch(e){
    setTimeout(function(){ throw e; }, 0);
  }

  // ----- dark mode toggle ------------------------------------------------
  // The button in the header (.theme-toggle) flips data-theme on <html>,
  // which swaps every CSS var slot via the :root[data-theme="dark"]
  // block in the stylesheet, and re-inits every live ECharts instance
  // with the matching ``<theme>_dark`` variant. The preference is
  // persisted in localStorage and read back by the inline init script
  // in <head> so reloads don't flash light-mode first.
  //
  // The toggle is intentionally NOT exposed via the manifest -- every
  // dashboard shipped through this pipeline gets the same button in
  // the same place, and authors cannot suppress or relocate it.
  var THEME_STORAGE_KEY = 'echart_dashboard_theme_mode';
  var DARK_MODE = (function(){
    try {
      var v = localStorage.getItem(THEME_STORAGE_KEY);
      if (v === 'dark') return true;
      if (v === 'light') return false;
    } catch(e){}
    try {
      return !!(window.matchMedia &&
                 window.matchMedia('(prefers-color-scheme: dark)').matches);
    } catch(e){ return false; }
  })();

  function _applyDarkAttr(){
    if (DARK_MODE) document.documentElement.setAttribute('data-theme', 'dark');
    else document.documentElement.removeAttribute('data-theme');
    var btn = document.getElementById('theme-toggle');
    if (btn){
      btn.setAttribute('aria-pressed', DARK_MODE ? 'true' : 'false');
      btn.title = DARK_MODE ? 'Switch to light mode' : 'Switch to dark mode';
    }
  }
  // Sync the attribute now so the toggle button picks up its initial
  // pressed-state and tooltip even before the load handler runs.
  _applyDarkAttr();

  function setDarkMode(on, persist){
    var next = !!on;
    if (next === DARK_MODE) return;
    DARK_MODE = next;
    if (persist !== false){
      try { localStorage.setItem(THEME_STORAGE_KEY,
                                    DARK_MODE ? 'dark' : 'light'); } catch(e){}
    }
    _applyDarkAttr();
    // Charts capture their theme at init time, so dispose every live
    // instance and let the lazy/active path re-create them with the
    // new theme name. Tabs that haven't been opened yet stay
    // un-initialised and will use the new theme on first activation.
    var liveIds = Object.keys(CHARTS);
    liveIds.forEach(function(cid){
      var rec = CHARTS[cid];
      if (rec && rec.inst){
        try { rec.inst.dispose(); } catch(e){}
      }
      delete CHARTS[cid];
    });
    // Re-init only charts that are visible right now; charts in
    // hidden tabs will be initialised when their tab is activated.
    var panels = document.querySelectorAll('.tab-panel.active .chart-div');
    Array.prototype.forEach.call(panels, function(div){
      var id = (div.id || '').replace(/^chart-/, '');
      if (id) initChart(id);
    });
    if (typeof applyConnects === 'function') applyConnects();
    if (typeof renderKpis === 'function') renderKpis();
    if (typeof renderTables === 'function') renderTables();
  }
  window.setDarkMode = setDarkMode;
  var _printRestoreDark = false;
  var _printLiveIdsBefore = [];
  var _printClosedGroups = [];
  var _printGridStateBefore = {};
  var DASHBOARD_PRINTING = false;
  window.addEventListener('beforeprint', function(){
    _printRestoreDark = DARK_MODE;
    if (DARK_MODE) setDarkMode(false, false);
    _printLiveIdsBefore = Object.keys(CHARTS);
    _printClosedGroups = [];
    _printGridStateBefore = {};
    Object.keys(WIDGET_META).forEach(function(id){
      var widget = WIDGET_META[id];
      if (!widget || widget.widget !== 'data_grid') return;
      var state = tableState(id);
      _printGridStateBefore[id] = {
        visibleRows: state.visibleRows,
        scrollTop: state.scrollTop
      };
    });
    DASHBOARD_PRINTING = true;
    document.documentElement.classList.add('dashboard-printing');
    document.querySelectorAll('details.layout-group-collapsible').forEach(
      function(group){
        if (!group.open){
          _printClosedGroups.push(group);
          group.open = true;
        }
      }
    );
    // A virtual grid normally mounts one page at a time. Print the complete
    // filtered/sorted result up to the widget's validated max_rows cap.
    renderTables();
    // Print CSS exposes every tab, so every chart must have a real light-mode
    // canvas before the browser snapshots the page. Hidden tabs otherwise
    // print as empty tiles because their lazy charts were never mounted.
    document.querySelectorAll('.tab-panel .chart-div').forEach(function(div){
      var id = (div.id || '').replace(/^chart-/, '');
      if (id) initChart(id);
    });
    Object.keys(CHARTS).forEach(function(cid){
      try { CHARTS[cid].inst.resize(); } catch(e){}
    });
  });
  window.addEventListener('afterprint', function(){
    document.documentElement.classList.remove('dashboard-printing');
    _printClosedGroups.forEach(function(group){ group.open = false; });
    _printClosedGroups = [];
    // Dispose charts that existed only to populate hidden print tabs. They
    // will be initialized at the correct visible dimensions on first visit.
    Object.keys(CHARTS).forEach(function(cid){
      if (_printLiveIdsBefore.indexOf(cid) >= 0) return;
      try { CHARTS[cid].inst.dispose(); } catch(e){}
      delete CHARTS[cid];
    });
    _printLiveIdsBefore = [];
    DASHBOARD_PRINTING = false;
    Object.keys(_printGridStateBefore).forEach(function(id){
      var state = tableState(id);
      state.visibleRows = _printGridStateBefore[id].visibleRows;
    });
    renderTables();
    Object.keys(_printGridStateBefore).forEach(function(id){
      var state = tableState(id);
      var scrollTop = _printGridStateBefore[id].scrollTop || 0;
      state.scrollTop = scrollTop;
      var scroller = document.querySelector(
        '#table-' + id + ' .table-virtual-scroll'
      );
      if (scroller) scroller.scrollTop = scrollTop;
    });
    _printGridStateBefore = {};
    if (_printRestoreDark) setDarkMode(true, false);
    _printRestoreDark = false;
  });

  // ----- filter state + event bus -----
  var filterState = {};
  (MANIFEST.filters || []).forEach(function(f){
    if (f.type === 'rule'){
      // Default rule filters to enabled. Author can opt out by
      // setting `default: false` in the manifest.
      filterState[f.id] = f.default == null ? true : !!f.default;
    } else {
      filterState[f.id] = f.default != null ? f.default :
                            (f.type === 'multiSelect' ? [] : '');
    }
  });
  var listeners = {}; // filterId -> [chartId, ...]

  function subscribe(chartId, filterIds){
    filterIds.forEach(function(fid){
      listeners[fid] = listeners[fid] || [];
      if (listeners[fid].indexOf(chartId) < 0) listeners[fid].push(chartId);
    });
  }
  // ----- show_when (runtime conditional widget visibility) -----
  // Evaluates filter-clause conditions on every filter change and
  // toggles the widget tile via CSS display. Compile-time data-clauses
  // already removed widgets that fail; what remains is filter-clause
  // conditions only.
  var WIDGET_SHOW_WHEN = PAYLOAD.widgetShowWhen || {};

  // Mirror of the engine-side _to_bool. Returns true / false when x
  // matches the recognised boolean dialect (JS bool, 'true' / 'false'
  // string in any case, '1' / '0'); returns undefined otherwise so
  // callers know to fall back to JS's loose equality. Closes the
  // `true == 'true'` is false silent-failure mode that bites when
  // PRISM authors a show_when filter clause comparing a toggle filter
  // against the string 'true' (or vice versa).
  function _toBoolish(x){
    if (typeof x === 'boolean') return x;
    if (typeof x === 'string'){
      var s = x.trim().toLowerCase();
      if (s === 'true' || s === '1') return true;
      if (s === 'false' || s === '0') return false;
    }
    return undefined;
  }

  function _evalShowWhenCmp(a, op, b){
    if (a == null || b == null) return false;
    // Bool-aware == / !=. When BOTH sides parse as boolean dialect,
    // compare on the canonical bool form so 'true' == true. When
    // only one side is bool-dialect (e.g. comparing a toggle against
    // a non-bool literal 'foo'), fall through to JS loose equality.
    if (op === '==' || op === '!='){
      var ab = _toBoolish(a), bb = _toBoolish(b);
      var eq = (ab !== undefined && bb !== undefined)
                 ? (ab === bb)
                 : (a == b);
      return op === '==' ? eq : !eq;
    }
    if (op === '>')   return parseFloat(a) >  parseFloat(b);
    if (op === '>=')  return parseFloat(a) >= parseFloat(b);
    if (op === '<')   return parseFloat(a) <  parseFloat(b);
    if (op === '<=')  return parseFloat(a) <= parseFloat(b);
    if (op === 'contains')   return String(a).indexOf(String(b)) >= 0;
    if (op === 'startsWith') return String(a).indexOf(String(b)) === 0;
    if (op === 'endsWith'){
      var sa = String(a), sb = String(b);
      return sa.indexOf(sb, sa.length - sb.length) !== -1;
    }
    return false;
  }

  function _evalShowWhen(cond, depth){
    depth = depth || 0;
    if (cond == null) return true;
    if (depth > 8) return true;  // depth guard
    if (typeof cond !== 'object') return true;
    if (cond.all){
      for (var i = 0; i < cond.all.length; i++){
        if (!_evalShowWhen(cond.all[i], depth + 1)) return false;
      }
      return true;
    }
    if (cond.any){
      for (var j = 0; j < cond.any.length; j++){
        if (_evalShowWhen(cond.any[j], depth + 1)) return true;
      }
      return cond.any.length === 0;
    }
    // Filter clause -- the only runtime-evaluated form
    if (cond.filter){
      var fid = cond.filter;
      var v = filterState[fid];
      if (cond.in){
        if (Array.isArray(v)){
          for (var k = 0; k < v.length; k++){
            if (cond.in.indexOf(v[k]) >= 0) return true;
          }
          return false;
        }
        return cond.in.indexOf(v) >= 0;
      }
      var op = cond.op || '==';
      var rhs = cond.value;
      // multiSelect arrays vs scalars: an array filter matches if
      // ANY element satisfies the comparison -- reads naturally as
      // "show when the user has selected the matching value among
      // others". For non-array values, just compare.
      if (Array.isArray(v)){
        for (var m = 0; m < v.length; m++){
          if (_evalShowWhenCmp(v[m], op, rhs)) return true;
        }
        return false;
      }
      return _evalShowWhenCmp(v, op, rhs);
    }
    // Data clauses are resolved at compile time; if one survived to
    // runtime, treat as true (the compile-time pass would have
    // removed the widget if the condition were false).
    return true;
  }

  // ----- per-widget initial state -----
  // PRISM can declare opening defaults that bypass the "always start in
  // raw" default behaviour. The state shape mirrors what the per-tile
  // controls drawer mutates at runtime, so we just seed those state
  // objects before the first render.
  //
  //   widget.spec.initial_state = {
  //     transform: 'yoy_pct',
  //     smoothing: 5,
  //     y_scale: 'log',
  //     y_range: 'from_zero',
  //     shape: {lineStyleType: 'dashed', step: 'middle', width: 2,
  //             areaFill: true, stack: 'percent', markers: false},
  //     series: { 'col_a': {transform: 'log', visible: true} }
  //   }
  //   widget.initial_state = {                     // table
  //     search: 'foo', sort_by: 'col', sort_dir: 'desc',
  //     hidden_columns: ['col_z'], density: 'compact',
  //     freeze_first_col: true, decimals: 2
  //   }
  //   widget.initial_state = {                     // kpi
  //     compare_period: '1m', sparkline_visible: false,
  //     delta_visible: true, decimals: 1
  //   }
  function _initInitialState(){
    // Walk WIDGET_META for every widget's initial_state. Chart widgets
    // can declare initial_state on either spec.initial_state or
    // widget.initial_state (both work; the spec form keeps the state
    // close to the chart_type/mapping it modifies).
    Object.keys(WIDGET_META || {}).forEach(function(cid){
      var w = WIDGET_META[cid] || {};
      if (w.widget !== 'chart') return;
      var spec = w.spec || {};
      var init = spec.initial_state || w.initial_state;
      if (!init) return;
      var st = chartControlState[cid] = chartControlState[cid] || {series: {}};
        if (init.transform != null) st.transform = init.transform;
        if (init.smoothing != null) st.smoothing = init.smoothing;
        if (init.y_scale != null)  st.yScale = init.y_scale;
        if (init.y_range != null)  st.yRange = init.y_range;
        if (init.x_scale != null)  st.xScale = init.x_scale;
        if (init.shape != null){
          var ish = init.shape || {};
          st.shape = {
            lineStyleType: ish.lineStyleType || 'inherit',
            step:          ish.step || 'inherit',
            width:         ish.width || 'inherit',
            areaFill:      ish.areaFill,
            stack:         ish.stack || 'inherit',
            markers:       ish.markers
          };
        }
        if (init.series && typeof init.series === 'object'){
          Object.keys(init.series).forEach(function(seriesName){
            var s2 = init.series[seriesName] || {};
            st.series[seriesName] = st.series[seriesName] || {};
            if (s2.transform != null)
              st.series[seriesName].transform = s2.transform;
            if (s2.visible != null)
              st.series[seriesName].visible = !!s2.visible;
          });
        }
        // Bar / scatter / heatmap-specific knobs
        if (init.bar_sort != null)   st.barSort = init.bar_sort;
        if (init.bar_stack != null)  st.barStack = init.bar_stack;
        if (init.trendline != null)  st.trendline = init.trendline;
        if (init.color_scale != null) st.heatmapColorScale = init.color_scale;
        if (init.show_labels != null) st.heatmapLabels = !!init.show_labels;
        if (init.pie_sort != null)    st.pieSort = init.pie_sort;
        if (init.pie_other_threshold != null)
          st.pieOtherThreshold = init.pie_other_threshold;
        // correlation_matrix runtime seeds
        if (init.corr_transform != null) st.corrTransform = init.corr_transform;
        if (init.corr_window != null)    st.corrWindow    = init.corr_window;
        if (init.corr_method != null)    st.corrMethod    = init.corr_method;
    });
    // Walk widget meta for table / kpi initial_state
    Object.keys(WIDGET_META || {}).forEach(function(wid){
      var w = WIDGET_META[wid] || {};
      var init = w.initial_state;
      if (!init) return;
      if (_isTableWidget(w)){
        var ts = (typeof tableState === 'function')
          ? tableState(wid) : (TABLE_STATE[wid] = TABLE_STATE[wid] || {});
        if (init.search != null)         ts.search = init.search;
        if (init.sort_by != null)        ts.sortBy = init.sort_by;
        if (init.sort_dir != null)       ts.sortDir = init.sort_dir;
        if (init.hidden_columns != null) ts.hiddenColumns =
                                            init.hidden_columns.slice();
        if (init.density != null)        ts.density = init.density;
        if (init.freeze_first_col != null)
          ts.freezeFirstCol = !!init.freeze_first_col;
        if (init.decimals != null)       ts.decimals = init.decimals;
      } else if (w.widget === 'kpi'){
        var ks = (typeof _kpiState === 'function')
          ? _kpiState(wid) : (KPI_STATE[wid] = KPI_STATE[wid] || {});
        if (init.compare_period != null) ks.comparePeriod = init.compare_period;
        if (init.sparkline_visible != null)
          ks.sparklineVisible = !!init.sparkline_visible;
        if (init.delta_visible != null)
          ks.deltaVisible = !!init.delta_visible;
        if (init.decimals != null)       ks.decimals = init.decimals;
      }
    });
    // Re-render charts whose state we just seeded so the initial paint
    // reflects the requested state.
    if (typeof rerenderAllCharts === 'function'){
      rerenderAllCharts();
    } else {
      Object.keys(CHARTS || {}).forEach(function(cid){
        if (typeof rerenderChart === 'function') rerenderChart(cid);
      });
    }
    if (typeof renderTables === 'function') renderTables();
    if (typeof renderKpis === 'function') renderKpis();
  }
  window._initInitialState = _initInitialState;

  // ----- auto-computed stat strip -----
  // For supported chart types we walk the visible series and compute a
  // small line of context per series: current value, deltas at standard
  // horizons, range, percentile rank. Units are pulled from the
  // dataset's field_provenance; format choice (bp / pct+abs / pp /
  // arithmetic) follows the units lookup. Recomputes on every
  // rerenderChart() so the strip tracks transforms and filters.

  var _STRIP_SUPPORTED = {
    'line': true, 'multi_line': true, 'area': true
  };
  // Pre-defined horizons in days. Picked to read like a trader's
  // standard set; 1Y is approximated as 365d (the rolling-window logic
  // already smooths over leap years).
  var _STRIP_HORIZONS = [
    {label: '1d',  days: 1},
    {label: '5d',  days: 5},
    {label: '1m',  days: 30},
    {label: '3m',  days: 92},
    {label: 'YTD', kind: 'ytd'},
    {label: '1Y',  days: 365},
  ];

  function _stripUnitsFor(cid, seriesCol){
    var w = WIDGET_META[cid] || {};
    var spec = w.spec || {};
    var dsName = spec.dataset; if (!dsName) return null;
    var ds = DATASETS[dsName]; if (!ds) return null;
    var fp = ds.field_provenance;
    if (fp && fp[seriesCol] && fp[seriesCol].units){
      return String(fp[seriesCol].units).toLowerCase();
    }
    return null;
  }

  function _stripDeltaFormat(units){
    if (!units) return null;
    if (units === 'percent' || units === 'pct' || units === '%')
      return 'bp';
    if (units === 'bp' || units === 'basis_points' || units === 'basis points')
      return 'arith_bp';
    if (units === 'z' || units === 'zscore' || units === 'sigma'
        || units === 'std')
      return 'arith';
    if (units === 'index' || units === 'usd' || units === 'eur'
        || units === 'gbp' || units === 'jpy' || units.indexOf('$') >= 0)
      return 'pct_abs';
    if (units === 'pp' || units === 'percentage_points'
        || units === 'percentage points')
      return 'pp';
    if (units === 'ratio')
      return 'arith';
    return 'pct';
  }

  function _stripDeltaFormatHeuristic(values){
    // Used only when units are absent. Falls back to magnitude rules.
    var nums = values.filter(function(v){
      return typeof v === 'number' && !isNaN(v);
    });
    if (!nums.length) return 'pct';
    var lo = Math.min.apply(null, nums);
    var hi = Math.max.apply(null, nums);
    var any_neg = nums.some(function(v){ return v < 0; });
    var span = hi - lo;
    // Values that cross zero AND have small magnitude → arithmetic
    // (z-scores, spreads in z-units).
    if (any_neg && Math.max(Math.abs(lo), Math.abs(hi)) < 5)
      return 'arith';
    // Values in [0, 25] with tight band → looks like a yield in %
    if (lo >= 0 && hi <= 25 && span < 10)
      return 'bp';
    // 4-digit + values → index
    if (lo > 100 && hi > 100)
      return 'pct_abs';
    return 'pct';
  }

  function _stripFmtNumber(v, decimals){
    if (v == null || isNaN(v)) return '--';
    var d = decimals != null ? decimals
                                  : (Math.abs(v) >= 1000 ? 0
                                    : (Math.abs(v) >= 100 ? 1 : 2));
    return Number(v).toFixed(__capDec(d, 2));
  }

  function _stripFmtCurrent(v, deltaFormat){
    if (v == null || isNaN(v)) return '--';
    if (deltaFormat === 'bp')      return _stripFmtNumber(v, 2) + '%';
    if (deltaFormat === 'arith_bp') return _stripFmtNumber(v, 0) + 'bp';
    if (deltaFormat === 'pct_abs') {
      // Index / price: just the number, no unit (caller supplies $)
      return _stripFmtNumber(v, Math.abs(v) >= 100 ? 0 : 2);
    }
    if (deltaFormat === 'pp')      return _stripFmtNumber(v, 2) + '%';
    if (deltaFormat === 'arith')   return _stripFmtNumber(v, 2);
    return _stripFmtNumber(v, 2);
  }

  function _stripFmtDelta(delta, baseValue, deltaFormat){
    if (delta == null || isNaN(delta)) return null;
    if (deltaFormat === 'bp' || deltaFormat === 'arith_bp'){
      // 1bp = 0.01% on a yield. delta is in same units as `baseValue`.
      // If units = percent, multiply by 100 to get bp.
      var bp = (deltaFormat === 'bp') ? delta * 100 : delta;
      var sign = bp >= 0 ? '+' : '-';
      var v = Math.abs(bp);
      var s = v >= 100 ? v.toFixed(0) : v.toFixed(1);
      return {label: sign + s + 'bp', sign: bp};
    }
    if (deltaFormat === 'pct_abs'){
      var pct = (baseValue ? (delta / baseValue) * 100 : 0);
      var sign2 = pct >= 0 ? '+' : '-';
      return {
        label: sign2 + Math.abs(pct).toFixed(1) + '%',
        sign: delta
      };
    }
    if (deltaFormat === 'pp'){
      var sign3 = delta >= 0 ? '+' : '-';
      return {
        label: sign3 + Math.abs(delta).toFixed(2) + 'pp',
        sign: delta
      };
    }
    if (deltaFormat === 'arith'){
      var sign4 = delta >= 0 ? '+' : '-';
      return {
        label: sign4 + Math.abs(delta).toFixed(2),
        sign: delta
      };
    }
    // pct (default)
    var pct2 = (baseValue ? (delta / baseValue) * 100 : 0);
    var sign5 = pct2 >= 0 ? '+' : '-';
    return {
      label: sign5 + Math.abs(pct2).toFixed(1) + '%',
      sign: delta
    };
  }

  function _stripExtractSeries(opt){
    if (!opt || !opt.series) return [];
    var series = Array.isArray(opt.series) ? opt.series : [opt.series];
    var out = [];
    // Resolve the x-axis category data once (used when series.data is
    // a list of bare numeric values pinned to xAxis.data).
    var xAxes = Array.isArray(opt.xAxis) ? opt.xAxis : (opt.xAxis ? [opt.xAxis] : []);
    var xCats = (xAxes[0] && xAxes[0].data) || null;

    for (var i = 0; i < series.length; i++){
      var s = series[i];
      if (!s || s._band_internal) continue;
      if (!s.data || !s.data.length) continue;
      // Series datum can take any of three shapes:
      //   1. [x, y]                 -- standard time-axis form we emit
      //   2. {value: [x, y], ...}   -- ECharts wraps emitted data into
      //                                 this shape on inst.getOption()
      //                                 when the series carries
      //                                 itemStyle / label overrides
      //   3. y                       -- bare scalar pinned to xAxis.data
      //                                 when the chart uses category x
      //
      // Heatmap / parallel emit longer tuples; chart_type is gated
      // upstream so we don't have to defend against those here.
      var ts = [], vs = [];
      for (var j = 0; j < s.data.length; j++){
        var pt = s.data[j];
        if (pt == null) continue;
        if (Array.isArray(pt) && pt.length >= 2){
          ts.push(_ccParseT(pt[0]));
          vs.push((pt[1] == null || isNaN(+pt[1])) ? null : +pt[1]);
        } else if (typeof pt === 'object' && Array.isArray(pt.value)
                     && pt.value.length >= 2){
          ts.push(_ccParseT(pt.value[0]));
          vs.push((pt.value[1] == null || isNaN(+pt.value[1])) ? null : +pt.value[1]);
        } else if (typeof pt === 'object' && pt.value != null
                     && !isNaN(+pt.value)){
          // Bare scalar inside a dict wrapper. Pin to xAxis.data[j]
          // so deltas line up with the category labels.
          var tx = (xCats && xCats[j] != null) ? xCats[j] : j;
          ts.push(_ccParseT(tx));
          vs.push(+pt.value);
        } else if (typeof pt === 'number' && !isNaN(pt)){
          var ty = (xCats && xCats[j] != null) ? xCats[j] : j;
          ts.push(_ccParseT(ty));
          vs.push(pt);
        } else if (typeof pt === 'string' && pt !== '' && !isNaN(+pt)){
          var ts2 = (xCats && xCats[j] != null) ? xCats[j] : j;
          ts.push(_ccParseT(ts2));
          vs.push(+pt);
        }
      }
      if (!vs.some(function(x){ return x != null; })) continue;
      out.push({
        name: s.name || ('series ' + (i + 1)),
        column: s._column || s.name || null,
        ts: ts, values: vs,
      });
    }
    return out;
  }

  function _stripDeltaForHorizon(ts, vs, horizon){
    var n = vs.length; if (!n) return null;
    var lastIdx = n - 1;
    while (lastIdx >= 0 && vs[lastIdx] == null) lastIdx--;
    if (lastIdx < 0) return null;
    var current = vs[lastIdx];
    if (horizon.kind === 'ytd'){
      var lastT = ts[lastIdx];
      if (lastT == null || isNaN(lastT)) return null;
      var d = new Date(lastT);
      var yearStart = Date.UTC(d.getUTCFullYear(), 0, 1);
      var anchorIdx = -1;
      for (var i = 0; i < ts.length; i++){
        if (ts[i] != null && ts[i] >= yearStart && vs[i] != null){
          anchorIdx = i; break;
        }
      }
      if (anchorIdx < 0 || anchorIdx === lastIdx) return null;
      return {current: current, baseline: vs[anchorIdx]};
    }
    if (horizon.days){
      var msTarget = ts[lastIdx] - horizon.days * 86400000;
      var lo = 0, hi = lastIdx, best = -1;
      while (lo <= hi){
        var mid = (lo + hi) >> 1;
        if (ts[mid] != null && ts[mid] <= msTarget){
          best = mid; lo = mid + 1;
        } else hi = mid - 1;
      }
      if (best < 0 || vs[best] == null) return null;
      return {current: current, baseline: vs[best]};
    }
    return null;
  }

  function _stripPercentile(vs){
    var nums = [];
    var current = null;
    for (var i = 0; i < vs.length; i++){
      if (vs[i] != null){ nums.push(vs[i]); current = vs[i]; }
    }
    if (nums.length < 2 || current == null) return null;
    var sorted = nums.slice().sort(function(a, b){ return a - b; });
    var below = 0;
    for (var j = 0; j < sorted.length; j++){
      if (sorted[j] < current) below++;
      else if (sorted[j] === current) below += 0.5;
    }
    return Math.round((below / sorted.length) * 100);
  }

  function _stripRange(vs){
    var nums = [];
    for (var i = 0; i < vs.length; i++){
      if (vs[i] != null) nums.push(vs[i]);
    }
    if (!nums.length) return null;
    return {lo: Math.min.apply(null, nums),
              hi: Math.max.apply(null, nums)};
  }

  // _buildStatStripHtml returns the HTML body for the stat-strip
  // popup, or null when there is nothing to show. The popup is a
  // proper table -- metrics down the left, one column per visible
  // series -- so the eye can scan a metric row across series or a
  // series column down across metrics in O(1). Inline middot-separated
  // rows were too visually noisy.
  function _buildStatStripHtml(cid){
    var w = WIDGET_META[cid] || {};
    var spec = w.spec || {};
    var ct = spec.chart_type;
    if (!_STRIP_SUPPORTED[ct]) return null;
    var rec = CHARTS[cid]; if (!rec || !rec.inst) return null;
    // Pull series from the live ECharts option first (this captures
    // any drawer-applied transforms / smoothing). Fall back to the
    // compile-time spec when the live read returns nothing -- ECharts
    // can wrap series.data in ways the extractor doesn't see, and we
    // always have the original on PAYLOAD.specs[cid].
    var liveOpt = rec.inst.getOption();
    var seriesData = _stripExtractSeries(liveOpt);
    if (!seriesData.length){
      var baseOpt = (typeof SPECS !== 'undefined' && SPECS) ? SPECS[cid] : null;
      if (baseOpt) seriesData = _stripExtractSeries(baseOpt);
    }
    if (!seriesData.length) return null;
    var override = (spec.stat_strip && typeof spec.stat_strip === 'object')
                     ? spec.stat_strip : null;
    var horizons = (override && Array.isArray(override.horizons))
                     ? override.horizons.map(function(h){
                         var match = _STRIP_HORIZONS.find(
                           function(x){ return x.label === h; }
                         );
                         return match || null;
                       }).filter(Boolean)
                     : _STRIP_HORIZONS;
    var showRange = override ? (override.show_range !== false) : true;
    var showPctile = override ? (override.show_percentile !== false) : true;
    var forcedFormat = (override && override.delta_format) || null;

    // Pre-compute a flat per-series record for table assembly.
    var rows = [];
    seriesData.forEach(function(sd){
      var units = _stripUnitsFor(cid, sd.column);
      var deltaFormat = forcedFormat
                         || _stripDeltaFormat(units)
                         || _stripDeltaFormatHeuristic(sd.values);
      var lastIdx = sd.values.length - 1;
      while (lastIdx >= 0 && sd.values[lastIdx] == null) lastIdx--;
      if (lastIdx < 0) return;
      var current = sd.values[lastIdx];
      var entry = {
        name: sd.name || sd.column || '',
        deltaFormat: deltaFormat,
        currentLabel: _stripFmtCurrent(current, deltaFormat),
        deltas: {},   // horizon label -> {label, sign}
        pctile: null,
        rangeLabel: null,
      };
      horizons.forEach(function(h){
        var d = _stripDeltaForHorizon(sd.ts, sd.values, h);
        if (!d) return;
        var delta = d.current - d.baseline;
        var fmt = _stripFmtDelta(delta, d.baseline, deltaFormat);
        if (!fmt) return;
        entry.deltas[h.label] = fmt;
      });
      if (showPctile){
        var p = _stripPercentile(sd.values);
        if (p != null) entry.pctile = p;
      }
      if (showRange){
        var r = _stripRange(sd.values);
        if (r){
          entry.rangeLabel = _stripFmtCurrent(r.lo, deltaFormat) + ' \u2013 '
                              + _stripFmtCurrent(r.hi, deltaFormat);
        }
      }
      rows.push(entry);
    });
    if (!rows.length) return null;

    // Assemble the table: metric column header + one column per series.
    var html = '<table class="stat-strip-table">';
    html += '<thead><tr><th class="ssm">Metric</th>';
    rows.forEach(function(r){
      html += '<th>' + _he(r.name) + '</th>';
    });
    html += '</tr></thead><tbody>';
    function _addRow(label, cellFn, opts){
      opts = opts || {};
      html += '<tr' + (opts.cls ? ' class="' + opts.cls + '"' : '') + '>';
      html += '<td class="ssm">' + label + '</td>';
      rows.forEach(function(r){
        html += '<td>' + cellFn(r) + '</td>';
      });
      html += '</tr>';
    }
    // Current value -- bold so the eye lands on it first.
    _addRow('Current', function(r){
      return '<span class="css-cur">' + _he(r.currentLabel) + '</span>';
    }, {cls: 'ss-cur-row'});
    // One row per requested horizon. Empty cells for series where
    // the horizon is too short (e.g. Δ1Y on a 3-month series).
    horizons.forEach(function(h){
      _addRow('&Delta; ' + _he(h.label), function(r){
        var d = r.deltas[h.label];
        if (!d) return '<span class="ss-empty">--</span>';
        var cls = d.sign > 0 ? 'css-pos' : (d.sign < 0 ? 'css-neg' : '');
        return '<span class="' + cls + '">' + _he(d.label) + '</span>';
      });
    });
    if (showPctile){
      _addRow('Pctile (1Y)', function(r){
        return r.pctile == null
          ? '<span class="ss-empty">--</span>'
          : _he(String(r.pctile));
      });
    }
    if (showRange){
      _addRow('Range (1Y)', function(r){
        return r.rangeLabel == null
          ? '<span class="ss-empty">--</span>'
          : _he(r.rangeLabel);
      });
    }
    html += '</tbody></table>';
    return html;
  }
  window._buildStatStripHtml = _buildStatStripHtml;

  function _openStatStripModal(cid){
    var html = _buildStatStripHtml(cid);
    if (!html){
      // Edge cases: chart not yet initialised, no plottable series,
      // or chart_type isn't strip-eligible. Show a tiny help message
      // rather than failing silently so the click still feels live.
      var w = WIDGET_META[cid] || {};
      var ct = (w.spec || {}).chart_type;
      var msg;
      if (!_STRIP_SUPPORTED[ct]){
        msg = 'Stats are only computed for line / multi_line / area charts.';
      } else if (!CHARTS[cid] || !CHARTS[cid].inst){
        msg = 'Chart has not finished initialising yet -- try again in a moment.';
      } else {
        msg = 'No plottable series found on this chart.';
      }
      html = '<p class="modal-empty">' + msg + '</p>';
    }
    var w = WIDGET_META[cid] || {};
    var title = (w.title || w.id || 'Series stats') + ' \u00B7 stats';
    var subtitle = 'Current value, deltas at standard horizons, '
                    + '1Y range, percentile rank';
    var body = '<div class="stat-strip-modal-body">' + html + '</div>';
    if (typeof showModal === 'function'){
      showModal(title, body, {subtitle: subtitle, wide: false});
    }
  }
  window._openStatStripModal = _openStatStripModal;

  // Wire the toolbar Σ button on every chart tile. Delegated event
  // handler so it survives tab activation re-renders. We attach to
  // document because the chart toolbar is created server-side and
  // never replaced by the runtime.
  document.addEventListener('click', function(ev){
    var btn = ev.target && ev.target.closest
              && ev.target.closest('[data-stat-strip-toggle]');
    if (!btn) return;
    var tile = btn.closest('[data-tile-id]');
    if (!tile) return;
    var cid = tile.getAttribute('data-tile-id');
    if (!cid) return;
    ev.preventDefault();
    _openStatStripModal(cid);
  });

  // Stub kept so callers (initChart / rerenderChart wrapper) don't
  // break. The strip used to render inline on every rerender; now
  // it's modal-on-demand, so the no-op is correct.
  function _renderStatStrip(_cid){ /* no-op: strip is opened via the toolbar Σ button */ }
  window._renderStatStrip = _renderStatStrip;

  function _applyShowWhen(){
    Object.keys(WIDGET_SHOW_WHEN).forEach(function(wid){
      var cond = WIDGET_SHOW_WHEN[wid];
      var visible = _evalShowWhen(cond);
      var el = document.querySelector(
        '[data-tile-id="' + wid + '"]'
      ) || document.getElementById('kpi-' + wid)
        || document.getElementById('chart-' + wid);
      if (!el) return;
      // Walk up to the tile if we matched an inner element
      while (el && !el.classList.contains('tile')
                && !el.classList.contains('chart-tile')
                && !el.classList.contains('kpi-tile')) {
        el = el.parentElement;
      }
      if (!el) return;
      el.style.display = visible ? '' : 'none';
    });
  }
  window._applyShowWhen = _applyShowWhen;

  // ----- cascading filters (depends_on + options_from) -----
  // When an upstream filter changes, recompute every descendant in
  // manifest order. Each descendant keeps values that remain valid and
  // otherwise resets to options[0] (or [] for multiSelect). The queue is
  // bounded by `seen` so malformed cycles cannot spin in the browser;
  // validation rejects those cycles before compile.
  function _refreshDependentFilters(changedId){
    var filters = MANIFEST.filters || [];
    var queue = [changedId];
    var seen = {};
    while (queue.length){
      var parentId = queue.shift();
      filters.forEach(function(f){
        if (f.depends_on !== parentId || seen[f.id]) return;
        seen[f.id] = true;
        _rebuildFilterOptions(f);
        queue.push(f.id);
      });
    }
  }
  window._refreshDependentFilters = _refreshDependentFilters;

  function _rebuildFilterOptions(f){
    var spec = f.options_from;
    if (!spec || !spec.dataset || !spec.key) return;
    var ds = DATASETS[spec.dataset];
    if (!ds) return;
    var rows = (typeof _datasetRows === 'function')
      ? _datasetRows(spec.dataset)
      : _rowsFromSource(ds.source);
    // Apply the where clause if present. Variables of the form
    // ${filterId} are substituted with current filterState values.
    var where = spec.where;
    var filtered = rows;
    if (where && typeof where === 'string'){
      filtered = _filterRowsByWhere(rows, where);
    }
    var key = spec.key;
    var values = [];
    var seen = {};
    for (var i = 0; i < filtered.length; i++){
      var v = filtered[i][key];
      if (v == null) continue;
      var sk = String(v);
      if (!seen[sk]){
        seen[sk] = true;
        values.push(v);
      }
    }
    // Sort consistently (numeric if all numeric, else lexical)
    var allNumeric = values.every(function(x){
      return typeof x === 'number' || !isNaN(parseFloat(x));
    });
    if (allNumeric){
      values.sort(function(a, b){
        return parseFloat(a) - parseFloat(b);
      });
    } else {
      values.sort(function(a, b){
        return String(a).localeCompare(String(b));
      });
    }
    var current = filterState[f.id];
    function containsValue(candidate){
      return values.some(function(v){
        return String(v) === String(candidate);
      });
    }
    // Reset state before touching the DOM so cascade semantics are stable
    // even while a tab/filter control is not mounted.
    if (f.type === 'multiSelect'){
      var currentValues = Array.isArray(current) ? current : [current];
      filterState[f.id] = currentValues.filter(containsValue);
    } else if (!containsValue(current)){
      filterState[f.id] = values.length ? values[0] : '';
    }
    current = filterState[f.id];
    // Apply to the DOM
    var el = document.getElementById('filter-' + f.id);
    if (f.type === 'radio'){
      // Radios: replace the radio-group container if we can find it
      var group = document.querySelector(
        '.filter-radio[data-filter-id="' + f.id + '"]'
      );
      if (!group) return;
      group.innerHTML = '';
      values.forEach(function(v){
        var labelEl = document.createElement('label');
        labelEl.className = 'filter-radio-option';
        var input = document.createElement('input');
        input.type = 'radio';
        input.name = 'filter-' + f.id;
        input.value = v;
        if (String(v) === String(current)) input.checked = true;
        var span = document.createElement('span');
        span.textContent = v;
        labelEl.appendChild(input); labelEl.appendChild(span);
        group.appendChild(labelEl);
        input.addEventListener('change', function(){
          if (input.checked){
            filterState[f.id] = input.value;
            broadcast(f.id);
          }
        });
      });
    } else if (el && el.tagName === 'SELECT'){
      var prevValues = (f.type === 'multiSelect'
                          && Array.isArray(current)) ? current : [current];
      el.innerHTML = '';
      values.forEach(function(v){
        var opt = document.createElement('option');
        opt.value = v; opt.textContent = v;
        if (prevValues.some(function(pv){
          return String(pv) === String(v);
        })) opt.selected = true;
        el.appendChild(opt);
      });
      if (f.type !== 'multiSelect' && filterState[f.id] !== ''){
        el.value = filterState[f.id];
      }
    }
  }

  function _rowsFromSource(source){
    if (!Array.isArray(source) || !source.length) return [];
    var header = source[0];
    var out = [];
    for (var i = 1; i < source.length; i++){
      var row = source[i] || []; var obj = {};
      for (var j = 0; j < header.length; j++) obj[header[j]] = row[j];
      out.push(obj);
    }
    return out;
  }

  function _filterRowsByWhere(rows, where){
    // Substitute ${filterId} -> filterState[filterId]
    var resolved = where.replace(/\$\{([^}]+)\}/g, function(_m, fid){
      var v = filterState[fid];
      if (typeof v === 'string') return JSON.stringify(v);
      if (Array.isArray(v)) return JSON.stringify(v);
      return String(v);
    });
    // Parse a single binary expression: <colName> <op> <value>
    var ops = ['==', '!=', '>=', '<=', '>', '<'];
    for (var i = 0; i < ops.length; i++){
      var op = ops[i];
      var idx = resolved.indexOf(op);
      if (idx > 0){
        var lhs = resolved.slice(0, idx).trim();
        var rhs = resolved.slice(idx + op.length).trim();
        // Strip wrapping quotes from rhs
        if ((rhs.startsWith("'") && rhs.endsWith("'")) ||
            (rhs.startsWith('"') && rhs.endsWith('"'))){
          rhs = rhs.slice(1, -1);
        }
        return rows.filter(function(r){
          var a = r[lhs];
          if (op === '==') return String(a) == String(rhs);
          if (op === '!=') return String(a) != String(rhs);
          var na = parseFloat(a), nb = parseFloat(rhs);
          if (op === '>')  return na >  nb;
          if (op === '>=') return na >= nb;
          if (op === '<')  return na <  nb;
          if (op === '<=') return na <= nb;
          return true;
        });
      }
    }
    return rows;
  }

  function broadcast(filterId){
    var f = (MANIFEST.filters || []).find(function(x){
      return x && x.id === filterId;
    });
    // dateRange filters in their default view-mode don't reshape any
    // chart data -- they only move the in-chart dataZoom window.
    // Dispatch a dataZoom action instead of a full rerender so we
    // preserve series animations, tooltips, and any per-chart user
    // interactions (e.g. another dataZoom slider position on a chart
    // not subscribed to this filter).
    if (f && f.type === 'dateRange' && (f.mode || 'view') === 'view'){
      (listeners[filterId] || []).forEach(function(cid){
        _dispatchChartDateZoom(cid);
      });
    } else {
      (listeners[filterId] || []).forEach(function(cid){
        rerenderChart(cid);
      });
    }
    renderKpis();
    renderTables();
    if (typeof renderPivots === 'function') renderPivots();
    if (typeof renderStatGrids === 'function') renderStatGrids();
    // Cascading filters: a filter change may invalidate the options
    // of any filter whose `depends_on` references it. _refreshDependentFilters
    // walks the dependency graph and re-renders affected filter inputs.
    if (typeof _refreshDependentFilters === 'function'){
      _refreshDependentFilters(filterId);
    }
    _applyShowWhen();
    if (typeof _serializeUrlState === 'function') _serializeUrlState();
  }

  // Move every targeting chart's dataZoom to the current dateRange
  // filter value. No-op when the chart isn't initialised yet (lazy
  // tab) or has no dataZoom configured.
  function _dispatchChartDateZoom(cid){
    var rec = CHARTS[cid]; if (!rec || !rec.inst) return;
    var dr = _dateRangeForChart(cid);
    if (!dr) return;
    var range = resolveDateRange(dr.value);
    var t0 = range[0], t1 = range[1];
    try {
      var opt = rec.inst.getOption();
      var dz = opt && opt.dataZoom;
      if (!dz || !dz.length) return;
      // Dispatch one action per dataZoom index so multi-axis charts
      // (rare for time series, but possible for stacked composites)
      // all move together.
      for (var i = 0; i < dz.length; i++){
        rec.inst.dispatchAction({
          type: 'dataZoom',
          dataZoomIndex: i,
          startValue: t0,
          endValue: t1,
        });
      }
    } catch (e) {}
  }

  // ----- dataset management -----
  var currentDatasets = {};
  Object.keys(DATASETS || {}).forEach(function(name){
    currentDatasets[name] = JSON.parse(JSON.stringify(DATASETS[name].source || DATASETS[name]));
  });
  function resetDataset(name){
    var src = (DATASETS[name] && DATASETS[name].source) || DATASETS[name];
    currentDatasets[name] = JSON.parse(JSON.stringify(src));
  }

  // ----- widget meta registry -----
  var WIDGET_META = {};
  function collectWidgets(){
    function visit(rows){
      rows.forEach(function(row){ row.forEach(function(w){
        if (w.id) WIDGET_META[w.id] = w;
      }); });
    }
    var layout = MANIFEST.layout || {};
    if (layout.kind === 'tabs'){
      (layout.tabs || []).forEach(function(t){ visit(t.rows || []); });
    } else {
      visit(layout.rows || []);
    }
  }
  collectWidgets();

  function targetMatch(target, id){
    if (target === '*') return true;
    if (target.indexOf('*') < 0) return target === id;
    var rx = new RegExp('^' + target.replace(/\*/g,'.*') + '$');
    return rx.test(id);
  }
  function filtersForChart(chartId){
    var out = [];
    (MANIFEST.filters || []).forEach(function(f){
      if ((f.targets || []).some(function(t){ return targetMatch(t, chartId); })){
        out.push(f.id);
      }
    });
    return out;
  }

  // ----- apply global filters to a dataset -----
  function resolveDateRange(val){
    var now = Date.now();
    if (typeof val === 'string'){
      var m = val.match(/^(\d+)([DWMY])$/);
      if (m){
        var n = parseInt(m[1]);
        var ms = {D:86400e3, W:7*86400e3, M:30*86400e3, Y:365*86400e3}[m[2]];
        return [now - n*ms, now];
      }
      if (val === 'YTD'){
        var jan1 = new Date(new Date().getFullYear(), 0, 1).getTime();
        return [jan1, now];
      }
      if (val === 'All') return [0, now];
    }
    if (Array.isArray(val) && val.length === 2){
      return [Date.parse(val[0]), Date.parse(val[1])];
    }
    return [0, now];
  }

  // Generic cell-vs-value comparator used by slider/number/text + conditional
  // formatting rules on tables. op defaults to '==' (equality).
  function cmpOp(op, cell, val){
    if (cell == null) return false;
    if (op == null) op = '==';
    if (op === 'contains')   return String(cell).toLowerCase().indexOf(String(val).toLowerCase()) >= 0;
    if (op === 'startsWith') return String(cell).toLowerCase().indexOf(String(val).toLowerCase()) === 0;
    if (op === 'endsWith')   return String(cell).toLowerCase().lastIndexOf(String(val).toLowerCase()) === String(cell).length - String(val).length;
    var a = +cell, b = +val;
    if (isNaN(a) || isNaN(b)) {
      if (op === '==' ) return String(cell) === String(val);
      if (op === '!=' ) return String(cell) !== String(val);
      return false;
    }
    if (op === '==') return a === b;
    if (op === '!=') return a !== b;
    if (op === '>' ) return a >  b;
    if (op === '>=') return a >= b;
    if (op === '<' ) return a <  b;
    if (op === '<=') return a <= b;
    return false;
  }

  // Compound rule filter evaluator. Walks {all/any/not} trees and
  // evaluates leaf {field, op, value} clauses against a row.
  // Used by the `widget: rule` filter type to express composed
  // screening logic that can't be expressed as flat-ANDed filters.
  function _evalRuleLeaf(leaf, header, row){
    if (!leaf || typeof leaf !== 'object') return true;
    var field = leaf.field;
    var op = leaf.op || '==';
    var val = leaf.value;
    var idx = (typeof field === 'string') ? header.indexOf(field) : -1;
    if (idx < 0) return false;     // unknown field -> drop
    var cell = row[idx];
    if (op === 'in' || op === 'not_in'){
      if (!Array.isArray(val)) return false;
      var hit = false;
      for (var k = 0; k < val.length; k++){
        if (cell != null && String(cell) === String(val[k])) { hit = true; break; }
        var nc = +cell, nv = +val[k];
        if (!isNaN(nc) && !isNaN(nv) && nc === nv) { hit = true; break; }
      }
      return op === 'in' ? hit : !hit;
    }
    return cmpOp(op, cell, val);
  }

  function _evalRule(rule, header, row, depth){
    if (!rule || typeof rule !== 'object') return true;
    if (depth == null) depth = 0;
    if (depth > 16) return true;   // runaway-nesting guard, mirrors validator depth cap
    if (Array.isArray(rule.all)){
      for (var i = 0; i < rule.all.length; i++){
        if (!_evalRule(rule.all[i], header, row, depth + 1)) return false;
      }
      return true;
    }
    if (Array.isArray(rule.any)){
      for (var j = 0; j < rule.any.length; j++){
        if (_evalRule(rule.any[j], header, row, depth + 1)) return true;
      }
      return false;
    }
    if (rule.not){
      return !_evalRule(rule.not, header, row, depth + 1);
    }
    return _evalRuleLeaf(rule, header, row);
  }
  // Expose for debugging from the browser console.
  window._evalRule = _evalRule;

  // applyFilters: filter dataset rows by every applicable global filter.
  //
  // ``widgetType`` lets the caller signal whether this dataset is being
  // pulled for a chart, table, or KPI. Chart widgets get full data with
  // their visible window controlled by per-chart dataZoom controls
  // (slider / scroll / drag). Tables and KPIs still want real row
  // filtering -- "rows in the last 6M", "average over the lookback".
  // So we treat ``dateRange`` filters as view-only (skipped) when the
  // caller is a chart, and apply them normally elsewhere.
  function applyFilters(name, rows, widgetType, widgetId){
    var header = rows[0]; var body = rows.slice(1); var out = body;
    (MANIFEST.filters || []).forEach(function(f){
      var targets = f.targets || [];
      if (widgetId && targets.length &&
          !targets.some(function(pattern){ return targetMatch(pattern, widgetId); })){
        return;
      }
      var val = filterState[f.id];
      if (val === '' || val == null || (Array.isArray(val) && val.length === 0)) return;
      // Escape-hatch: if the filter declares `all_value` and the current
      // value matches it, treat this filter as a no-op. Lets radio/select
      // filters have an explicit "All / Any / None" option without having
      // to invent a null sentinel.
      if (f.all_value != null && String(val) === String(f.all_value)) return;
      var idx = f.field != null ? header.indexOf(f.field) : -1;
      if (f.type === 'dateRange'){
        // For chart targets, dateRange is a "view" filter -- it sets
        // the initial dataZoom window, not the underlying dataset.
        // Author can flip back to row-filtering with `mode: 'filter'`
        // on the filter declaration.
        if (widgetType === 'chart' && (f.mode || 'view') === 'view') return;
        if (idx < 0) idx = 0;
        var r = resolveDateRange(val);
        out = out.filter(function(row){
          var c = row[idx]; if (c == null) return false;
          var d = (typeof c === 'string') ? Date.parse(c) : +c;
          if (isNaN(d)) return true;
          return d >= r[0] && d <= r[1];
        });
      } else if ((f.type === 'select' || f.type === 'radio') && idx >= 0){
        out = out.filter(function(row){ return String(row[idx]) === String(val); });
      } else if (f.type === 'multiSelect' && idx >= 0){
        out = out.filter(function(row){ return val.indexOf(String(row[idx])) >= 0; });
      } else if (f.type === 'numberRange' && idx >= 0){
        var lo = val[0], hi = val[1];
        out = out.filter(function(row){ var n = +row[idx]; return !isNaN(n) && n>=lo && n<=hi; });
      } else if (f.type === 'toggle' && idx >= 0){
        if (val) out = out.filter(function(row){ return !!row[idx]; });
      } else if ((f.type === 'slider' || f.type === 'number' || f.type === 'text')
                   && idx >= 0){
        var op = f.op || (f.type === 'text' ? 'contains' : '>=');
        var transform = f.transform; // optional 'abs' | 'neg'
        out = out.filter(function(row){
          var cell = row[idx];
          if (transform === 'abs' && cell != null) cell = Math.abs(+cell);
          else if (transform === 'neg' && cell != null) cell = -(+cell);
          return cmpOp(op, cell, val);
        });
      } else if (f.type === 'rule'){
        // Compound rule filter: walk the {all/any/not + leaf} tree per row.
        // filterState[fid] holds the enable flag (boolean). When false,
        // the rule is bypassed and all rows pass. URL-state restore can
        // serialise booleans as the strings "true"/"false"; coerce both.
        if (val === false || val === 'false') return;
        if (!f.rule || typeof f.rule !== 'object') return;
        out = out.filter(function(row){
          return _evalRule(f.rule, header, row);
        });
      }
    });
    return [header].concat(out);
  }

  // Translate a ``dateRange`` filter value -> dataZoom start/end on
  // every time-axis dataZoom entry on the chart's option. Charts get
  // full data, so the filter only ever moves the visible window.
  // Returns true when at least one dataZoom entry was updated.
  function _dateRangeForChart(cid){
    var matches = [];
    (MANIFEST.filters || []).forEach(function(f){
      if (f.type !== 'dateRange') return;
      if ((f.mode || 'view') !== 'view') return;
      if (!(f.targets || []).some(function(t){ return targetMatch(t, cid); })) return;
      var val = filterState[f.id];
      if (val === '' || val == null) return;
      if (f.all_value != null && String(val) === String(f.all_value)) return;
      matches.push({filter: f, value: val});
    });
    if (!matches.length) return null;
    // If multiple dateRange filters target the same chart, the most
    // recent declaration wins. (This shouldn't happen in practice;
    // validator can later flag it.)
    return matches[matches.length - 1];
  }
  function _applyChartDateZoom(opt, dr){
    if (!opt || !dr) return;
    var dz = opt.dataZoom;
    if (!dz) return;
    var arr = Array.isArray(dz) ? dz : [dz];
    var range = resolveDateRange(dr.value);
    var t0 = range[0], t1 = range[1];
    arr.forEach(function(z){
      if (!z || typeof z !== 'object') return;
      // Setting startValue/endValue overrides start/end. ECharts
      // clamps out-of-range values to the data extent so undersized
      // datasets don't blow up.
      delete z.start; delete z.end;
      z.startValue = t0;
      z.endValue = t1;
    });
    if (!Array.isArray(opt.dataZoom)) opt.dataZoom = arr;
  }

  // =========================================================================
  // CHART CONTROLS  (gear-icon drawer)
  //
  // Per-chart, runtime-only knobs:
  //
  //   Time series (line / multi_line / area / bar with time axis):
  //     - Per-series transform  (raw / Δ / %Δ / YoY Δ / YoY % / index=100)
  //     - Smoothing  (off / 5 / 20 / 50 / 200)
  //     - Y-scale  (linear / log)
  //     - Y-range  (auto / from zero)
  //
  //   Bar (categorical):
  //     - Sort  (input / value desc / value asc / alphabetical)
  //     - Stack mode  (group / stack / 100% stack)
  //     - Y-scale  (linear / log)
  //
  //   Scatter:
  //     - Trendline  (off / linear)
  //     - X-scale  (linear / log)
  //     - Y-scale  (linear / log)
  //
  //   Heatmap:
  //     - Color scale  (sequential / diverging-around-zero)
  //     - Show cell labels  (on / off)
  //
  //   Pie / donut:
  //     - Sort  (input / largest first)
  //     - "Other" bucket  (off / <1% / <3% / <5%)
  //
  //   Universal:
  //     - View data  -> modal table
  //     - Copy CSV   -> clipboard
  //     - PNG export -> existing toolbar button
  //     - Reset      -> back to compile-time defaults
  //
  // State lives in chartControlState[cid] and is reapplied inside
  // materializeOption() on every rerender so the option produced by
  // setOption() always reflects the user's latest knob settings.
  // =========================================================================

  var chartControlState = {};

  function _ccGetState(cid){
    if (!chartControlState[cid]) chartControlState[cid] = {series: {}};
    if (!chartControlState[cid].series) chartControlState[cid].series = {};
    return chartControlState[cid];
  }

  // ---- per-series transforms ----

  function _ccParseT(d){
    return (typeof d === 'string') ? Date.parse(d) : +d;
  }
  function _ccChange(values){
    return values.map(function(v, i){
      if (i === 0) return null;
      if (v == null || values[i-1] == null) return null;
      var a = +v, b = +values[i-1];
      if (isNaN(a) || isNaN(b)) return null;
      return a - b;
    });
  }
  function _ccPctChange(values){
    return values.map(function(v, i){
      if (i === 0) return null;
      if (v == null || values[i-1] == null) return null;
      var a = +v, b = +values[i-1];
      if (isNaN(a) || isNaN(b) || b === 0) return null;
      return (a - b) / b * 100;
    });
  }
  function _ccFindYearAgo(times, i){
    var t = times[i]; if (t == null || isNaN(t)) return -1;
    var target = t - 365 * 86400000;
    var lo = 0, hi = i, best = -1;
    while (lo <= hi){
      var mid = (lo + hi) >> 1;
      var tm = times[mid];
      if (tm == null || isNaN(tm)){ hi = mid - 1; continue; }
      if (tm <= target){ best = mid; lo = mid + 1; }
      else { hi = mid - 1; }
    }
    return best;
  }
  function _ccYoyChange(times, values){
    return times.map(function(t, i){
      if (values[i] == null) return null;
      var j = _ccFindYearAgo(times, i);
      if (j < 0 || values[j] == null) return null;
      var a = +values[i], b = +values[j];
      if (isNaN(a) || isNaN(b)) return null;
      return a - b;
    });
  }
  function _ccYoyPct(times, values){
    return times.map(function(t, i){
      if (values[i] == null) return null;
      var j = _ccFindYearAgo(times, i);
      if (j < 0 || values[j] == null) return null;
      var a = +values[i], b = +values[j];
      if (isNaN(a) || isNaN(b) || b === 0) return null;
      return (a - b) / b * 100;
    });
  }
  function _ccIndex100(values){
    var anchor = null;
    for (var i = 0; i < values.length; i++){
      if (values[i] != null && !isNaN(+values[i]) && +values[i] !== 0){
        anchor = +values[i]; break;
      }
    }
    if (anchor == null) return values.slice();
    return values.map(function(v){
      if (v == null || isNaN(+v)) return null;
      return (+v / anchor) * 100;
    });
  }
  function _ccLog(values){
    return values.map(function(v){
      if (v == null || isNaN(+v) || +v <= 0) return null;
      return Math.log(+v);
    });
  }
  function _ccLogChange(values){
    return values.map(function(v, i){
      if (i === 0) return null;
      var a = values[i], b = values[i-1];
      if (a == null || b == null) return null;
      var na = +a, nb = +b;
      if (isNaN(na) || isNaN(nb) || na <= 0 || nb <= 0) return null;
      return Math.log(na) - Math.log(nb);
    });
  }
  function _ccYoyLog(times, values){
    return times.map(function(t, i){
      if (values[i] == null) return null;
      var j = _ccFindYearAgo(times, i);
      if (j < 0 || values[j] == null) return null;
      var a = +values[i], b = +values[j];
      if (isNaN(a) || isNaN(b) || a <= 0 || b <= 0) return null;
      return Math.log(a) - Math.log(b);
    });
  }
  function _ccZscore(values){
    var nums = [];
    for (var i = 0; i < values.length; i++){
      var v = values[i];
      if (v != null && !isNaN(+v)) nums.push(+v);
    }
    if (nums.length < 2) return values.map(function(){ return null; });
    var mean = 0;
    for (var k = 0; k < nums.length; k++) mean += nums[k];
    mean /= nums.length;
    var v2 = 0;
    for (var k2 = 0; k2 < nums.length; k2++){
      v2 += (nums[k2] - mean) * (nums[k2] - mean);
    }
    v2 /= (nums.length - 1);
    var sd = v2 > 0 ? Math.sqrt(v2) : 0;
    if (sd === 0) return values.map(function(){ return null; });
    return values.map(function(v){
      if (v == null || isNaN(+v)) return null;
      return (+v - mean) / sd;
    });
  }
  function _ccRollingZscore(values, window){
    window = Math.max(2, window | 0);
    var queue = []; var sum = 0; var sumSq = 0; var cnt = 0;
    var means = new Array(values.length);
    var stds  = new Array(values.length);
    for (var ix = 0; ix < values.length; ix++){
      means[ix] = null; stds[ix] = null;
      var vv = values[ix];
      if (vv != null && !isNaN(+vv)){
        var f = +vv; queue.push(f); sum += f; sumSq += f * f; cnt++;
      } else {
        queue.push(null);
      }
      if (queue.length > window){
        var rem = queue.shift();
        if (rem != null){ sum -= rem; sumSq -= rem * rem; cnt--; }
      }
      if (queue.length === window && cnt >= 2){
        var m = sum / cnt;
        var var2 = (sumSq - cnt * m * m) / (cnt - 1);
        if (var2 < 0) var2 = 0;
        means[ix] = m; stds[ix] = Math.sqrt(var2);
      }
    }
    var out = new Array(values.length);
    for (var iy = 0; iy < values.length; iy++){
      var v = values[iy], m2 = means[iy], s2 = stds[iy];
      if (v == null || m2 == null || s2 == null || s2 === 0){
        out[iy] = null; continue;
      }
      out[iy] = (+v - m2) / s2;
    }
    return out;
  }
  function _ccRankPct(values){
    var pairs = [];
    values.forEach(function(v, i){
      if (v != null && !isNaN(+v)) pairs.push({v: +v, i: i});
    });
    pairs.sort(function(a, b){ return a.v - b.v; });
    var out = new Array(values.length);
    for (var k = 0; k < values.length; k++) out[k] = null;
    var m = pairs.length;
    if (m === 0) return out;
    var i = 0;
    while (i < m){
      var j = i;
      while (j + 1 < m && pairs[j + 1].v === pairs[i].v) j++;
      var avgRank = (i + j) / 2.0;
      var pct = m > 1 ? (100 * avgRank / (m - 1)) : 50;
      for (var k2 = i; k2 <= j; k2++) out[pairs[k2].i] = pct;
      i = j + 1;
    }
    return out;
  }
  function _ccYtd(times, values){
    // Cumulative change vs. the first value of the same calendar year.
    // The transformed value at row i is (values[i] - anchor[year(i)]).
    var anchors = {};
    return times.map(function(t, i){
      var v = values[i];
      if (v == null || isNaN(+v) || t == null || isNaN(t)) return null;
      var d = new Date(+t); var yr = d.getUTCFullYear();
      if (anchors[yr] == null) anchors[yr] = +v;
      return +v - anchors[yr];
    });
  }
  function _ccDetectAnnualizationFactor(times){
    // Median gap between consecutive timestamps -> annualization factor.
    // Daily ~ 252 obs/yr, weekly ~ 52, monthly ~ 12, quarterly ~ 4,
    // semi-annual ~ 2, annual ~ 1. Falls back to 252 when uncertain.
    var gaps = [];
    for (var i = 1; i < times.length; i++){
      var a = times[i], b = times[i-1];
      if (a == null || b == null || isNaN(a) || isNaN(b)) continue;
      var dt = (a - b) / 86400000;
      if (dt > 0) gaps.push(dt);
    }
    if (!gaps.length) return 1;
    gaps.sort(function(x, y){ return x - y; });
    var med = gaps[gaps.length >> 1];
    if (med <= 1.5)   return 252;
    if (med <= 4)     return 252;
    if (med <= 10)    return 52;
    if (med <= 45)    return 12;
    if (med <= 120)   return 4;
    if (med <= 240)   return 2;
    return 1;
  }
  function _ccAnnualizedChange(times, values){
    var f = _ccDetectAnnualizationFactor(times);
    var diffs = _ccChange(values);
    return diffs.map(function(d){
      return (d == null || isNaN(+d)) ? null : +d * f;
    });
  }
  function _ccRollingMean(values, n){
    if (!n || n <= 1) return values.slice();
    var out = new Array(values.length);
    var sum = 0; var cnt = 0; var queue = [];
    for (var i = 0; i < values.length; i++){
      var v = values[i];
      var add = (v != null && !isNaN(+v)) ? +v : null;
      queue.push(add);
      if (add != null){ sum += add; cnt++; }
      if (queue.length > n){
        var rem = queue.shift();
        if (rem != null){ sum -= rem; cnt--; }
      }
      out[i] = (queue.length === n && cnt > 0) ? sum / cnt : null;
    }
    return out;
  }
  function _ccTransformValues(times, values, transform){
    if (transform && transform.indexOf('rolling_zscore_') === 0){
      var w = parseInt(transform.split('_').pop(), 10) || 252;
      return _ccRollingZscore(values, w);
    }
    switch (transform){
      case 'change':         return _ccChange(values);
      case 'pct_change':     return _ccPctChange(values);
      case 'log_change':     return _ccLogChange(values);
      case 'yoy_change':     return _ccYoyChange(times, values);
      case 'yoy_pct':        return _ccYoyPct(times, values);
      case 'yoy_log':        return _ccYoyLog(times, values);
      case 'annualized_change': return _ccAnnualizedChange(times, values);
      case 'log':            return _ccLog(values);
      case 'zscore':         return _ccZscore(values);
      case 'rank_pct':       return _ccRankPct(values);
      case 'ytd':            return _ccYtd(times, values);
      case 'index100':       return _ccIndex100(values);
      case 'raw': default:   return values.slice();
    }
  }
  function _ccTransformLabel(t){
    if (t && t.indexOf('rolling_zscore_') === 0){
      var w = parseInt(t.split('_').pop(), 10) || 252;
      return 'z (' + w + 'd)';
    }
    return ({
      raw:               '',
      change:            'Δ',
      pct_change:        '%Δ',
      log_change:        'log Δ',
      yoy_change:        'YoY Δ',
      yoy_pct:           'YoY %',
      yoy_log:           'YoY log Δ',
      annualized_change: 'ann. Δ',
      log:               'ln',
      zscore:            'z',
      rank_pct:          'pct rank',
      ytd:               'YTD Δ',
      index100:          'Index=100',
    })[t] || '';
  }
  function _ccTransformAxisLabel(transforms){
    // If every active series uses the same transform, label the y-axis
    // with that transform's units. Mixed transforms -> blank label.
    var seen = {};
    transforms.forEach(function(t){ seen[t || 'raw'] = 1; });
    var keys = Object.keys(seen);
    if (keys.length !== 1) return null;
    return _ccTransformLabel(keys[0]);
  }
  // Suffix applied to formatted values inside the tooltip when a
  // transform is active. ECharts tooltips are global; we just attach a
  // valueFormatter that respects the per-series transform via a map.
  function _ccTransformSuffix(t){
    if (t === 'pct_change' || t === 'yoy_pct') return '%';
    if (t === 'rank_pct') return '%';
    return '';
  }

  // ---- option mutation entry point ----
  //
  // Called from materializeOption AFTER applyFilters + after the
  // dataset rewire. The option already has its dataset.source filled
  // in. We mutate `opt.series[*]` in place and (for time-series
  // transforms) replace `series[i].data` with explicit pairs so the
  // transformed values are rendered.
  function applyChartControls(cid, opt){
    if (!opt) return opt;
    var w = WIDGET_META[cid];
    var ct = String(((w && w.spec) || {}).chart_type || '').toLowerCase();
    // scatter_studio must always run its apply pass on EVERY render
    // (even before the user touches the drawer) so the OLS line +
    // stats strip reflect the author's `regression_default`. For all
    // other chart types we early-return when no state exists since
    // the chart's compile-time defaults are already correct.
    var state = chartControlState[cid];
    if (!state){
      if (ct === 'scatter_studio'){
        state = _ccGetState(cid);
      } else {
        return opt;
      }
    }

    // --- time-series knobs (line / multi_line / area) ---
    if (ct === 'line' || ct === 'multi_line' || ct === 'area'){
      _ccApplyTimeSeries(cid, opt, state);
      _ccApplyLineShape(opt, state);
    }

    // --- bar knobs ---
    if (ct === 'bar' || ct === 'bar_horizontal'){
      _ccApplyBar(opt, state, ct === 'bar_horizontal');
    }

    // --- scatter knobs ---
    if (ct === 'scatter' || ct === 'scatter_multi'){
      _ccApplyScatter(opt, state);
    }

    // --- scatter studio (interactive X/Y picker + regression) ---
    if (ct === 'scatter_studio'){
      var statsBundle = _ccApplyStudio(cid, opt, state);
      // Stash the stats bundle on the state so the chart-render
      // callback can update the strip below the canvas after
      // setOption() completes.
      state._lastStudioStats = statsBundle;
    }

    // --- heatmap knobs (categorical X/Y/value) ---
    if (ct === 'heatmap'){
      _ccApplyHeatmap(opt, state);
    }

    // --- correlation_matrix knobs (Transform / Window / Method) ---
    if (ct === 'correlation_matrix'){
      _ccApplyCorrelationMatrix(cid, opt, state);
    }

    // --- pie knobs ---
    if (ct === 'pie' || ct === 'donut'){
      _ccApplyPie(opt, state);
    }

    // --- universal axis toggles (apply last so they aren't clobbered) ---
    if (state.yScale)  _ccApplyYScale(opt, state.yScale);
    if (state.yRange)  _ccApplyYRange(opt, state.yRange);
    if (state.xScale && (ct === 'scatter'
                          || ct === 'scatter_multi'
                          || ct === 'scatter_studio')){
      _ccApplyXScale(opt, state.xScale);
    }

    return opt;
  }

  // ---- helpers: time-series transform + smoothing ----

  function _ccApplyTimeSeries(cid, opt, state){
    // Two source paths:
    //   1) dataset rewired (chart has dataset_ref) -> opt.dataset.source
    //      is set; series have ``encode`` and no ``.data``.
    //   2) inline data path (chart wasn't auto-rewired) -> series each
    //      carry ``[[x, y], ...]`` directly. Per-series transform pulls
    //      pairs straight from s.data.
    // We support both so transforms work for any chart configuration.
    var smoothing = parseInt(state.smoothing || '0', 10) || 0;
    var hasDataset = !!(opt.dataset && opt.dataset.source
                          && opt.dataset.source.length >= 2);
    var header = hasDataset ? opt.dataset.source[0] : null;
    var body   = hasDataset ? opt.dataset.source.slice(1) : null;
    var xCol   = hasDataset
      ? ((opt.series && opt.series[0] && opt.series[0].encode)
          ? opt.series[0].encode.x : header[0])
      : null;
    var xIdx   = (hasDataset && header) ? header.indexOf(xCol) : 0;
    if (xIdx < 0) xIdx = 0;
    var datasetTimes = body ? body.map(function(r){
      return _ccParseT(r[xIdx]);
    }) : null;

    var anyTransform = false;
    var anySmooth    = smoothing > 1;
    var transforms   = [];

    (opt.series || []).forEach(function(s, i){
      if (!s || typeof s !== 'object') return;
      var t = s.type;
      if (t !== 'line' && t !== 'bar' && t !== 'area' && t !== 'scatter') return;

      var seriesKey = s._column || s.name || ('series_' + i);
      var sState = state.series[seriesKey] || {};
      var transform = sState.transform || 'raw';
      var visible = (sState.visible !== false);
      transforms.push(transform);

      // Hide series cleanly (ECharts respects empty data).
      if (!visible){
        s.data = [];
        delete s.encode;
        return;
      }

      // Collect pairs [[x, y], ...] from whichever source we have.
      var pairs = null;
      if (hasDataset){
        var yIdx = -1;
        if (s._column && header.indexOf(s._column) >= 0){
          yIdx = header.indexOf(s._column);
        } else if (s.name && header.indexOf(s.name) >= 0){
          yIdx = header.indexOf(s.name);
        } else {
          yIdx = Math.min(1 + i, header.length - 1);
        }
        if (yIdx <= 0) return;
        pairs = body.map(function(r){ return [r[xIdx], r[yIdx]]; });
      } else if (Array.isArray(s.data)){
        pairs = s.data.map(function(p){
          if (Array.isArray(p)) return [p[0], p[1]];
          if (p && typeof p === 'object'){
            // ECharts allows {value: [x,y], name: ...}
            var v = p.value;
            if (Array.isArray(v) && v.length >= 2) return [v[0], v[1]];
          }
          return null;
        }).filter(function(p){ return p != null; });
      }
      if (!pairs || !pairs.length) return;

      var times = pairs.map(function(p){ return _ccParseT(p[0]); });
      var values = pairs.map(function(p){ return p[1]; });

      if (transform !== 'raw'){
        values = _ccTransformValues(times, values, transform);
        anyTransform = true;
      }
      if (smoothing > 1){
        values = _ccRollingMean(values, smoothing);
      }

      if (transform !== 'raw' || smoothing > 1){
        s.data = pairs.map(function(p, j){
          var v = values[j];
          if (v == null || isNaN(+v)) return [p[0], null];
          return [p[0], +v];
        });
        delete s.encode;
        // Annotate series name with the transform tag so the legend
        // reads "US 10Y · YoY %" rather than just "US 10Y".
        var tag = _ccTransformLabel(transform);
        if (tag && s.name && s.name.indexOf(' \u00B7 ') < 0){
          s.name = s.name + ' \u00B7 ' + tag;
        }
      }
    });

    // Y-axis title hint when every visible series shares the same transform
    if (anyTransform){
      var axisTag = _ccTransformAxisLabel(transforms);
      if (axisTag){
        var yax = opt.yAxis;
        if (Array.isArray(yax) && yax.length) yax = yax[0];
        if (yax && typeof yax === 'object' && !yax._cc_orig_name){
          yax._cc_orig_name = yax.name || '';
          yax.name = axisTag;
        }
      }
    }

    if (anySmooth || anyTransform){
      // Force tooltip to format with sensible decimals; the percent
      // forms get a "%" suffix.
      var commonSuffix = _ccTransformSuffix(transforms[0] || 'raw');
      var tt = opt.tooltip || {};
      if (typeof tt === 'object'){
        tt.valueFormatter = (
          'function(v){ if (v == null || isNaN(+v)) return ""; '
          + 'var n = +v; var d = Math.abs(n) >= 100 ? 1 : 2; '
          + 'return n.toFixed(d) + "' + commonSuffix + '"; }');
        opt.tooltip = tt;
      }
    }
  }

  // ---- helpers: line/area shape (style / step / area / stack / width) ----
  //
  // Mutates every line/area series in opt to reflect the user's shape
  // selections. Each knob is applied independently so a user can layer
  // them (e.g. dashed + step + filled). Defaults are no-op: if the
  // state key is missing or 'inherit' the field on the series is left
  // untouched and the compile-time choice survives.
  function _ccApplyLineShape(opt, state){
    var shape = state.shape || null;
    if (!shape) return;
    var seriesArr = (opt.series || []).filter(function(s){
      return s && (s.type === 'line' || s.type === 'area');
    });
    if (!seriesArr.length) return;
    seriesArr.forEach(function(s){
      // ---- line style: solid | dotted | dashed ----
      if (shape.lineStyleType && shape.lineStyleType !== 'inherit'){
        s.lineStyle = s.lineStyle || {};
        s.lineStyle.type = shape.lineStyleType;
      }
      // ---- step: off | start | middle | end ----
      if (shape.step != null && shape.step !== 'inherit'){
        if (shape.step === 'off' || shape.step === 'none') delete s.step;
        else s.step = shape.step;
      }
      // ---- area fill: on | off ----
      if (shape.areaFill === 'on'){
        s.areaStyle = s.areaStyle || {opacity: 0.30};
      } else if (shape.areaFill === 'off'){
        delete s.areaStyle;
      }
      // ---- stack: group | stack | percent ----
      if (shape.stack && shape.stack !== 'inherit'){
        if (shape.stack === 'group') delete s.stack;
        else s.stack = 'total';
      }
      // ---- line width: 1 | 2 | 3 (px) ----
      if (shape.lineWidth != null && shape.lineWidth !== 'inherit'){
        s.lineStyle = s.lineStyle || {};
        s.lineStyle.width = +shape.lineWidth;
      }
      // ---- show point markers ----
      if (shape.showSymbol === 'on') s.showSymbol = true;
      else if (shape.showSymbol === 'off') s.showSymbol = false;
    });

    // 100% stack rescale -- only meaningful for line/area, mirrors the
    // bar `percent` behavior. Computes per-x totals across stacked
    // series and rewrites each series .data to its share of the total.
    if (shape.stack === 'percent' && seriesArr.length){
      var minLen = Infinity;
      seriesArr.forEach(function(s){
        var d = (s.data || []);
        if (d.length < minLen) minLen = d.length;
      });
      if (minLen === Infinity) minLen = 0;
      for (var i = 0; i < minLen; i++){
        var total = 0;
        seriesArr.forEach(function(s){
          var p = (s.data || [])[i];
          var v = Array.isArray(p) ? p[1] : p;
          if (v != null && !isNaN(+v)) total += +v;
        });
        if (total > 0){
          seriesArr.forEach(function(s){
            var p = (s.data || [])[i];
            if (Array.isArray(p)){
              var v2 = p[1];
              s.data[i] = [p[0], (v2 == null || isNaN(+v2))
                            ? null : (+v2 / total) * 100];
            } else if (p != null && !isNaN(+p)){
              s.data[i] = (+p / total) * 100;
            }
          });
        }
      }
      // Format the y axis as percent, clipped to 0..100.
      var yax = opt.yAxis;
      var yaxes = Array.isArray(yax) ? yax : (yax ? [yax] : []);
      yaxes.forEach(function(a){
        if (!a || typeof a !== 'object') return;
        var al = a.axisLabel || {};
        al.formatter = 'function(v){ return v.toFixed(0) + "%"; }';
        a.axisLabel = al;
        a.max = 100;
        if (a.min === undefined) a.min = 0;
      });
    }
  }

  // ---- helpers: bar sort / stack ----

  function _ccApplyBar(opt, state, horizontal){
    var sort = state.barSort;
    var stack = state.barStack;
    var catAxisKey = horizontal ? 'yAxis' : 'xAxis';
    var valAxisKey = horizontal ? 'xAxis' : 'yAxis';

    // Identify category axis (with .data) and series structure.
    // build_bar produces xAxis.data = categories, series[i].data = values.
    // build_bar_horizontal produces yAxis.data = categories.
    if (sort && sort !== 'input'){
      var catAxis = opt[catAxisKey];
      if (Array.isArray(catAxis) && catAxis.length) catAxis = catAxis[0];
      if (!catAxis || !Array.isArray(catAxis.data)) return;
      var cats = catAxis.data.slice();
      var n = cats.length;
      if (!n) return;

      // For each category index, sum across all bar series to get a
      // sortable value. Single-series falls out as the series value.
      var seriesArr = (opt.series || []).filter(function(s){
        return s && s.type === 'bar';
      });
      function valAt(i){
        var s = 0; var any = false;
        seriesArr.forEach(function(ser){
          var d = ser.data || [];
          var v = d[i];
          if (v != null && !isNaN(+v)){ s += +v; any = true; }
        });
        return any ? s : null;
      }

      // Build [(category, sumValue, originalIndex)] then sort.
      var pairs = cats.map(function(c, i){ return [c, valAt(i), i]; });
      if (sort === 'val_desc' || sort === 'val_asc'){
        pairs.sort(function(a, b){
          if (a[1] == null && b[1] == null) return 0;
          if (a[1] == null) return 1;
          if (b[1] == null) return -1;
          return sort === 'val_desc' ? b[1] - a[1] : a[1] - b[1];
        });
      } else if (sort === 'name'){
        pairs.sort(function(a, b){
          return String(a[0]).localeCompare(String(b[0]));
        });
      }

      // Apply the new permutation: reorder category list and each
      // series' data array in lockstep.
      var newOrder = pairs.map(function(p){ return p[2]; });
      catAxis.data = pairs.map(function(p){ return p[0]; });
      seriesArr.forEach(function(ser){
        if (Array.isArray(ser.data)){
          ser.data = newOrder.map(function(j){ return ser.data[j]; });
        }
      });
    }

    if (stack){
      // group | stack | percent (100% stacked)
      var seriesArr2 = (opt.series || []).filter(function(s){
        return s && s.type === 'bar';
      });
      seriesArr2.forEach(function(s){
        if (stack === 'group'){
          delete s.stack;
        } else {
          s.stack = 'total';
        }
      });
      if (stack === 'percent' && seriesArr2.length){
        // Compute per-category totals across all bar series, then
        // rescale every series value to a percentage of its total.
        var catAxis2 = opt[catAxisKey];
        if (Array.isArray(catAxis2) && catAxis2.length) catAxis2 = catAxis2[0];
        var n2 = (catAxis2 && Array.isArray(catAxis2.data))
          ? catAxis2.data.length
          : (seriesArr2[0].data || []).length;
        for (var i = 0; i < n2; i++){
          var total = 0;
          seriesArr2.forEach(function(s){
            var v = (s.data || [])[i];
            if (v != null && !isNaN(+v)) total += +v;
          });
          if (total > 0){
            seriesArr2.forEach(function(s){
              var v = (s.data || [])[i];
              s.data[i] = (v == null || isNaN(+v)) ? null : (+v / total) * 100;
            });
          }
        }
        // Format the value axis as percent and clip 0..100
        var valAx = opt[valAxisKey];
        var valAxes = Array.isArray(valAx) ? valAx : (valAx ? [valAx] : []);
        valAxes.forEach(function(a){
          if (!a || typeof a !== 'object') return;
          var al = a.axisLabel || {};
          al.formatter = 'function(v){ return v.toFixed(0) + "%"; }';
          a.axisLabel = al;
          a.max = 100;
          if (a.min === undefined) a.min = 0;
        });
      }
    }
  }

  // ---- helpers: scatter trendline + axis log ----

  function _ccApplyScatter(opt, state){
    var tline = state.scatterTrendline;
    if (!tline || tline === 'off') return;
    if (tline !== 'linear') return;
    // Compute OLS over every scatter series and inject a markLine.
    (opt.series || []).forEach(function(s){
      if (!s || s.type !== 'scatter') return;
      var pts = (s.data || []).map(function(p){
        if (Array.isArray(p)) return [+p[0], +p[1]];
        return null;
      }).filter(function(p){
        return p && !isNaN(p[0]) && !isNaN(p[1]);
      });
      if (pts.length < 2) return;
      var n = pts.length;
      var sx = 0, sy = 0, sxx = 0, sxy = 0;
      pts.forEach(function(p){
        sx += p[0]; sy += p[1]; sxx += p[0]*p[0]; sxy += p[0]*p[1];
      });
      var denom = n*sxx - sx*sx;
      if (denom === 0) return;
      var m = (n*sxy - sx*sy) / denom;
      var b = (sy - m*sx) / n;
      var xs = pts.map(function(p){ return p[0]; });
      var xmin = Math.min.apply(null, xs);
      var xmax = Math.max.apply(null, xs);
      s.markLine = s.markLine || {};
      s.markLine.symbol = ['none', 'none'];
      s.markLine.lineStyle = {color: '#1a365d', type: 'dashed', width: 1.5};
      s.markLine.label = {show: false};
      s.markLine.data = [[
        {coord: [xmin, m*xmin + b]},
        {coord: [xmax, m*xmax + b]},
      ]];
      s.markLine.silent = true;
    });
  }

  // =========================================================================
  // SCATTER STUDIO  (interactive X/Y picker + per-axis transforms +
  //                  regression stats strip)
  //
  // Compile-time builder embeds opt._studio with the column whitelists,
  // initial defaults, transform options, regression options. Runtime
  // state lives on chartControlState[cid].studio. _ccApplyStudio
  // resamples the dataset, applies per-axis transforms, optionally
  // groups by color, computes regression on the visible data, and
  // populates a stats strip below the canvas.
  // =========================================================================

  function _ccStudioCfg(cid){
    // Returns the spec-level studio config block embedded by
    // build_scatter_studio. Returns null when the chart isn't a studio.
    var base = SPECS[cid];
    if (!base) return null;
    return base._studio || null;
  }

  function _ccColumnTransform(values, times, name){
    // JS mirror of echart_studio._compute_transform. Operates on a
    // numeric column producing a same-length list with null for
    // undefined positions. Used by _ccApplyStudio per axis.
    if (!name || name === 'raw'){
      return values.map(function(v){
        if (v == null || isNaN(+v)) return null;
        return +v;
      });
    }
    if (name === 'log'){
      return values.map(function(v){
        if (v == null || isNaN(+v) || +v <= 0) return null;
        return Math.log(+v);
      });
    }
    if (name === 'rank_pct'){
      var pairs = [];
      values.forEach(function(v, i){
        if (v != null && !isNaN(+v)) pairs.push({v: +v, i: i});
      });
      pairs.sort(function(a, b){ return a.v - b.v; });
      var out = new Array(values.length);
      for (var k = 0; k < values.length; k++) out[k] = null;
      var m = pairs.length;
      if (m === 0) return out;
      var i = 0;
      while (i < m){
        var j = i;
        while (j + 1 < m && pairs[j + 1].v === pairs[i].v) j++;
        var avgRank = (i + j) / 2.0;
        var pct = m > 1 ? (100 * avgRank / (m - 1)) : 50;
        for (var k2 = i; k2 <= j; k2++) out[pairs[k2].i] = pct;
        i = j + 1;
      }
      return out;
    }
    if (name === 'zscore'){
      var nums = []; var anyNull = false;
      values.forEach(function(v){
        if (v != null && !isNaN(+v)) nums.push(+v);
        else anyNull = true;
      });
      if (nums.length < 2) return values.map(function(){ return null; });
      var mean = 0;
      for (var k3 = 0; k3 < nums.length; k3++) mean += nums[k3];
      mean /= nums.length;
      var v2 = 0;
      for (var k4 = 0; k4 < nums.length; k4++){
        v2 += (nums[k4] - mean) * (nums[k4] - mean);
      }
      v2 /= (nums.length - 1);
      var sd = v2 > 0 ? Math.sqrt(v2) : 0;
      if (sd === 0) return values.map(function(){ return null; });
      return values.map(function(v){
        if (v == null || isNaN(+v)) return null;
        return (+v - mean) / sd;
      });
    }
    if (name === 'change' || name === 'pct_change'){
      var out2 = [null];
      for (var i2 = 1; i2 < values.length; i2++){
        var a = values[i2]; var b = values[i2 - 1];
        if (a == null || b == null || isNaN(+a) || isNaN(+b)){
          out2.push(null); continue;
        }
        if (name === 'change'){ out2.push(+a - +b); }
        else if (+b === 0){ out2.push(null); }
        else { out2.push((+a - +b) / +b * 100); }
      }
      return out2;
    }
    if (name === 'yoy_change' || name === 'yoy_pct'){
      // Use the same helper as the time-series transform for parity.
      var ts = (times || []).map(function(t){ return _ccParseT(t); });
      var out3 = new Array(values.length);
      for (var i3 = 0; i3 < values.length; i3++) out3[i3] = null;
      for (var i4 = 0; i4 < values.length; i4++){
        if (values[i4] == null) continue;
        var j2 = _ccFindYearAgo(ts, i4);
        if (j2 < 0 || values[j2] == null) continue;
        var a2 = +values[i4]; var b2 = +values[j2];
        if (isNaN(a2) || isNaN(b2)) continue;
        if (name === 'yoy_change'){ out3[i4] = a2 - b2; }
        else if (b2 === 0){ continue; }
        else { out3[i4] = (a2 - b2) / b2 * 100; }
      }
      return out3;
    }
    if (name.indexOf('rolling_zscore_') === 0){
      var window = parseInt(name.split('_').pop(), 10) || 252;
      window = Math.max(2, window);
      var queue = []; var sum = 0; var sumSq = 0; var cnt = 0;
      var means = new Array(values.length);
      var stds  = new Array(values.length);
      for (var ix = 0; ix < values.length; ix++){
        means[ix] = null; stds[ix] = null;
        var vv = values[ix];
        if (vv != null && !isNaN(+vv)){
          var f = +vv; queue.push(f); sum += f; sumSq += f * f; cnt++;
        } else {
          queue.push(null);
        }
        if (queue.length > window){
          var rem = queue.shift();
          if (rem != null){ sum -= rem; sumSq -= rem * rem; cnt--; }
        }
        if (queue.length === window && cnt >= 2){
          var m2 = sum / cnt;
          var var2 = (sumSq - cnt * m2 * m2) / (cnt - 1);
          if (var2 < 0) var2 = 0;
          means[ix] = m2; stds[ix] = Math.sqrt(var2);
        }
      }
      var out4 = new Array(values.length);
      for (var iy = 0; iy < values.length; iy++){
        var v3 = values[iy], m3 = means[iy], s3 = stds[iy];
        if (v3 == null || m3 == null || s3 == null || s3 === 0){
          out4[iy] = null; continue;
        }
        out4[iy] = (+v3 - m3) / s3;
      }
      return out4;
    }
    if (name === 'index100'){
      var anchor = null;
      for (var ia = 0; ia < values.length; ia++){
        var va = values[ia];
        if (va != null && !isNaN(+va) && +va !== 0){ anchor = +va; break; }
      }
      if (anchor == null) return values.slice();
      return values.map(function(v){
        if (v == null || isNaN(+v)) return null;
        return (+v / anchor) * 100;
      });
    }
    return values.slice();
  }

  function _ccTransformAxisSuffix(name){
    if (!name || name === 'raw') return '';
    if (name.indexOf('rolling_zscore_') === 0){
      var w = parseInt(name.split('_').pop(), 10) || 252;
      return ' (z, ' + w + 'd)';
    }
    return ({
      log:        ' (ln)',
      change:     ' (\u0394)',
      pct_change: ' (%\u0394)',
      yoy_change: ' (YoY \u0394)',
      yoy_pct:    ' (YoY %)',
      zscore:     ' (z)',
      rank_pct:   ' (pct rank)',
      index100:   ' (index=100)'
    })[name] || '';
  }

  function _ccTransformLabelShort(name){
    if (!name || name === 'raw') return 'Raw';
    if (name.indexOf('rolling_zscore_') === 0){
      var w = parseInt(name.split('_').pop(), 10) || 252;
      return 'Rolling z (' + w + 'd)';
    }
    return ({
      log:        'log',
      change:     '\u0394',
      pct_change: '%\u0394',
      yoy_change: 'YoY \u0394',
      yoy_pct:    'YoY %',
      zscore:     'z-score',
      rank_pct:   'pct rank',
      index100:   'Index=100'
    })[name] || name;
  }

  function _ccRegStats(xs, ys){
    // OLS regression statistics. Returns {n, slope, intercept, r, r2,
    // rmse, se_slope, se_intercept, t_slope, p_slope}, or null when
    // n<2, or {n, degenerate:'x_zero_variance'} when Sxx==0.
    var pairs = [];
    for (var i = 0; i < xs.length; i++){
      var a = xs[i], b = ys[i];
      if (a == null || b == null || isNaN(+a) || isNaN(+b)) continue;
      pairs.push([+a, +b]);
    }
    var n = pairs.length;
    if (n < 2) return null;
    var mx = 0, my = 0;
    for (var k = 0; k < n; k++){ mx += pairs[k][0]; my += pairs[k][1]; }
    mx /= n; my /= n;
    var sxx = 0, syy = 0, sxy = 0;
    for (var k2 = 0; k2 < n; k2++){
      var dx = pairs[k2][0] - mx;
      var dy = pairs[k2][1] - my;
      sxx += dx * dx; syy += dy * dy; sxy += dx * dy;
    }
    if (sxx <= 0){
      return {n: n, slope: null, intercept: null, r: null,
              r2: null, rmse: null, p_slope: null,
              degenerate: 'x_zero_variance'};
    }
    var slope = sxy / sxx;
    var intercept = my - slope * mx;
    var r = (syy > 0) ? sxy / Math.sqrt(sxx * syy) : 0;
    var rss = 0;
    for (var k3 = 0; k3 < n; k3++){
      var pred = slope * pairs[k3][0] + intercept;
      var diff = pairs[k3][1] - pred;
      rss += diff * diff;
    }
    var df = Math.max(1, n - 2);
    var rmse = Math.sqrt(rss / df);
    var seSlope = rmse / Math.sqrt(sxx);
    var seIntercept = rmse * Math.sqrt(1 / n + (mx * mx) / sxx);
    var tSlope = (seSlope > 0) ? slope / seSlope : null;
    var pSlope = (tSlope == null) ? null
      : 2 * (1 - _ccPhi(Math.abs(tSlope)));
    return {n: n, slope: slope, intercept: intercept,
            r: r, r2: r * r, rmse: rmse,
            se_slope: seSlope, se_intercept: seIntercept,
            t_slope: tSlope, p_slope: pSlope};
  }

  function _ccPhi(x){
    // Standard-normal CDF via erf; sufficient precision for the
    // display strip's p-value.
    return 0.5 * (1 + _ccErf(x / Math.SQRT2));
  }
  function _ccErf(x){
    // Abramowitz & Stegun 7.1.26 approximation.
    var sign = x < 0 ? -1 : 1; x = Math.abs(x);
    var a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741,
        a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
    var t = 1.0 / (1.0 + p * x);
    var y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1)
              * t * Math.exp(-x * x);
    return sign * y;
  }

  function _ccPStars(p){
    if (p == null || isNaN(p)) return '';
    if (p < 0.001) return '***';
    if (p < 0.01)  return '**';
    if (p < 0.05)  return '*';
    if (p < 0.10)  return '\u00B7';
    return '';
  }

  function _ccFmt(v, d){
    if (v == null || isNaN(+v)) return '\u2014';
    var n = +v;
    var dec = (d != null) ? d : (Math.abs(n) >= 100 ? 1 : 2);
    return n.toFixed(__capDec(dec, 2));
  }

  function _ccApplyStudio(cid, opt, state){
    var cfg = _ccStudioCfg(cid);
    if (!cfg) return null;
    var st = state.studio = state.studio || {};

    // Resolve current selections (fall back to defaults).
    var xCol = st.xCol || cfg.x_default;
    var yCol = st.yCol || cfg.y_default;
    var colorCol = (st.colorCol === '' ? null : (st.colorCol || cfg.color_default));
    var sizeCol  = (st.sizeCol  === '' ? null : (st.sizeCol  || cfg.size_default));
    var xT = st.xTransform || cfg.x_transform_default || 'raw';
    var yT = st.yTransform || cfg.y_transform_default || 'raw';
    var winSel = st.window || cfg.window_default || 'all';
    var outSel = st.outliers || cfg.outlier_default || 'off';
    var regSel = st.regression || cfg.regression_default || 'off';

    // Pull rows from the (filtered) dataset.
    var w = WIDGET_META[cid];
    var ds = w && w.dataset_ref ? currentDatasets[w.dataset_ref] : null;
    if (!ds || !ds.length){
      // Compile-time inline data: fall back to opt.series[*].data.
      // The studio drawer is largely meaningless without a dataset_ref,
      // but at least don't crash.
      return null;
    }
    var filt = applyFilters(w.dataset_ref, ds, 'chart', cid);
    var header = filt[0];
    var body = filt.slice(1);

    var xIdx = header.indexOf(xCol);
    var yIdx = header.indexOf(yCol);
    var cIdx = colorCol ? header.indexOf(colorCol) : -1;
    var sIdx = sizeCol  ? header.indexOf(sizeCol)  : -1;
    var oIdx = cfg.order_by ? header.indexOf(cfg.order_by) : -1;
    var labelIdx = cfg.label_column ? header.indexOf(cfg.label_column) : -1;
    if (xIdx < 0 || yIdx < 0){
      return null;
    }

    // Sort by order_by if present (so order-aware transforms apply).
    var rows = body.slice();
    if (oIdx >= 0){
      rows.sort(function(a, b){
        var ta = _ccParseT(a[oIdx]); var tb = _ccParseT(b[oIdx]);
        if (isNaN(ta) && isNaN(tb)) return 0;
        if (isNaN(ta)) return 1;
        if (isNaN(tb)) return -1;
        return ta - tb;
      });
    }

    // Window slicing (only meaningful when order_by is a date col).
    if (oIdx >= 0 && winSel && winSel !== 'all'){
      var keepDays = null;
      if (/^\d+d$/.test(winSel))     keepDays = parseInt(winSel, 10);
      else if (/^\d+y$/.test(winSel)) keepDays = parseInt(winSel, 10) * 365;
      if (keepDays && rows.length){
        var lastT = _ccParseT(rows[rows.length - 1][oIdx]);
        if (!isNaN(lastT)){
          var cutoff = lastT - keepDays * 86400000;
          rows = rows.filter(function(r){
            var t = _ccParseT(r[oIdx]);
            return !isNaN(t) && t >= cutoff;
          });
        }
      }
    }

    var xRaw = rows.map(function(r){ return r[xIdx]; });
    var yRaw = rows.map(function(r){ return r[yIdx]; });
    var times = (oIdx >= 0)
      ? rows.map(function(r){ return r[oIdx]; })
      : null;
    var xT_vals = _ccColumnTransform(xRaw, times, xT);
    var yT_vals = _ccColumnTransform(yRaw, times, yT);

    // Outlier filter (after transform, before grouping/regression).
    if (outSel === 'iqr_3' || outSel === 'z_4'){
      var keep = _ccStudioOutlierMask(xT_vals, yT_vals, outSel);
      for (var i = 0; i < xT_vals.length; i++){
        if (!keep[i]){ xT_vals[i] = null; yT_vals[i] = null; }
      }
    }

    // Group rows by color column (if any).
    var groups = [];      // [{name, indices: [...]}, ...]
    if (cIdx >= 0){
      var gmap = {}; var order = [];
      for (var i = 0; i < rows.length; i++){
        var g = rows[i][cIdx];
        var gk = (g == null) ? '\u2014' : String(g);
        if (gmap[gk] == null){
          gmap[gk] = groups.length;
          groups.push({name: gk, indices: []});
          order.push(gk);
        }
        groups[gmap[gk]].indices.push(i);
      }
    } else {
      var allIdx = [];
      for (var ii = 0; ii < rows.length; ii++) allIdx.push(ii);
      groups = [{name: yCol || 'series', indices: allIdx}];
    }

    // Resolve a categorical palette for groups.
    var palette = (PAYLOAD.palettes &&
      ((PAYLOAD.palettes[MANIFEST.palette]
         && PAYLOAD.palettes[MANIFEST.palette].colors)
        || (PAYLOAD.palettes.gs_primary
             && PAYLOAD.palettes.gs_primary.colors))) || [];

    // Build series.
    var series = [];
    var legend = [];
    groups.forEach(function(grp, gi){
      var data = [];
      grp.indices.forEach(function(idx){
        var xv = xT_vals[idx]; var yv = yT_vals[idx];
        if (xv == null || yv == null) return;
        var pt = [xv, yv];
        if (sIdx >= 0){
          var sv = rows[idx][sIdx];
          pt.push(sv == null ? 1 : +sv);
        }
        // Tooltip / popup row reference: original row index from the
        // (filtered, post-window) array. Keep as a property so the
        // builder can find the source row.
        data.push({
          value: pt,
          _row: rows[idx],
          _label: (labelIdx >= 0) ? rows[idx][labelIdx] : null
        });
      });
      var entry = {
        type: 'scatter', name: grp.name, data: data,
        emphasis: {focus: 'series'}
      };
      if (sIdx >= 0){
        entry.symbolSize = function(val){
          return Math.sqrt(Math.abs(val[2] || 1)) * 4;
        };
      } else {
        entry.symbolSize = 10;
      }
      var color = palette[gi % (palette.length || 1)];
      if (color) entry.itemStyle = {color: color};
      series.push(entry);
      legend.push(grp.name);
    });

    // Regression (overall or per-group).
    var statsBundle = {n_total: 0, perGroup: [], overall: null,
                        x: xCol, y: yCol, xT: xT, yT: yT};
    var allX = [], allY = [];
    groups.forEach(function(grp){
      var gx = [], gy = [];
      grp.indices.forEach(function(idx){
        gx.push(xT_vals[idx]); gy.push(yT_vals[idx]);
        allX.push(xT_vals[idx]); allY.push(yT_vals[idx]);
      });
      var s = _ccRegStats(gx, gy);
      statsBundle.perGroup.push({name: grp.name, stats: s,
                                   color: (palette[statsBundle.perGroup.length % (palette.length || 1)])});
    });
    statsBundle.overall = _ccRegStats(allX, allY);
    statsBundle.n_total = statsBundle.overall ? statsBundle.overall.n : 0;

    // Inject regression markLines per the user's selection.
    if (regSel === 'ols' && statsBundle.overall
          && statsBundle.overall.slope != null){
      var os = statsBundle.overall;
      var xMin = Infinity, xMax = -Infinity;
      series.forEach(function(s){
        (s.data || []).forEach(function(p){
          var v = (p && p.value) || p;
          if (Array.isArray(v)){
            if (+v[0] < xMin) xMin = +v[0];
            if (+v[0] > xMax) xMax = +v[0];
          }
        });
      });
      if (isFinite(xMin) && isFinite(xMax) && series.length){
        // Attach the OLS line as its own series so it has a legend
        // entry the user can toggle.
        series.push({
          type: 'line', name: 'OLS', showSymbol: false,
          smooth: false, silent: true,
          lineStyle: {type: 'dashed', width: 1.5, color: '#1a365d'},
          data: [[xMin, os.slope * xMin + os.intercept],
                 [xMax, os.slope * xMax + os.intercept]],
          tooltip: {show: false},
          emphasis: {focus: 'none'}
        });
        legend.push('OLS');
      }
    } else if (regSel === 'ols_per_group'){
      // One markLine per group, colored to match.
      statsBundle.perGroup.forEach(function(pg, gi){
        var s = pg.stats;
        if (!s || s.slope == null) return;
        var sxs = []; var pts = (series[gi] && series[gi].data) || [];
        pts.forEach(function(p){
          var v = (p && p.value) || p;
          if (Array.isArray(v)) sxs.push(+v[0]);
        });
        if (!sxs.length) return;
        var lo = Math.min.apply(null, sxs);
        var hi = Math.max.apply(null, sxs);
        var color = (palette[gi % (palette.length || 1)]) || '#666';
        series.push({
          type: 'line', name: pg.name + ' OLS',
          showSymbol: false, smooth: false, silent: true,
          lineStyle: {type: 'dashed', width: 1.4, color: color},
          data: [[lo, s.slope * lo + s.intercept],
                 [hi, s.slope * hi + s.intercept]],
          tooltip: {show: false},
          emphasis: {focus: 'none'}
        });
      });
    }

    // Wire axis names + scales. nameLocation/nameGap mirror what the
    // Python builder set so the names render centered (not at the
    // ECharts-default 'end' which clips on tight grids).
    var xName = xCol + _ccTransformAxisSuffix(xT);
    var yName = yCol + _ccTransformAxisSuffix(yT);
    opt.xAxis = {type: 'value', name: xName, scale: true,
                  nameLocation: 'middle', nameGap: 28};
    opt.yAxis = {type: 'value', name: yName, scale: true,
                  nameLocation: 'middle', nameGap: 48};
    opt.tooltip = opt.tooltip || {};
    opt.tooltip.trigger = 'item';
    opt.tooltip.formatter = (
      'function(p){var v = (p.data && p.data.value) || p.data; '
      + 'if (!Array.isArray(v)) return ""; '
      + 'var lab = (p.data && p.data._label != null) '
      + '            ? (\"<b>\" + p.data._label + \"</b><br/>\") : \"\"; '
      + 'return lab + \"' + xName.replace(/"/g, '\\"') + ': \" + (+v[0]).toFixed(2) + \"<br/>\"'
      + ' + \"' + yName.replace(/"/g, '\\"') + ': \" + (+v[1]).toFixed(2); }'
    );
    opt.series = series;
    if (opt.legend){
      opt.legend.data = legend;
    }

    return statsBundle;
  }

  function _ccStudioOutlierMask(xs, ys, mode){
    var n = xs.length;
    var keep = new Array(n);
    for (var k = 0; k < n; k++) keep[k] = true;
    function pruneCol(vals){
      var nums = [];
      for (var i = 0; i < n; i++){
        if (vals[i] != null && !isNaN(+vals[i])) nums.push(+vals[i]);
      }
      if (nums.length < 4) return;
      nums.sort(function(a, b){ return a - b; });
      function quant(p){
        var idx = p * (nums.length - 1);
        var lo = Math.floor(idx), hi = Math.min(nums.length - 1, lo + 1);
        var f = idx - lo;
        return nums[lo] + (nums[hi] - nums[lo]) * f;
      }
      if (mode === 'iqr_3'){
        var q1 = quant(0.25), q3 = quant(0.75); var iqr = q3 - q1;
        var lo = q1 - 3 * iqr, hi = q3 + 3 * iqr;
        for (var i2 = 0; i2 < n; i2++){
          if (vals[i2] == null || isNaN(+vals[i2])) continue;
          var v = +vals[i2];
          if (v < lo || v > hi) keep[i2] = false;
        }
      } else if (mode === 'z_4'){
        var mean = 0;
        for (var k2 = 0; k2 < nums.length; k2++) mean += nums[k2];
        mean /= nums.length;
        var v2 = 0;
        for (var k3 = 0; k3 < nums.length; k3++){
          v2 += (nums[k3] - mean) * (nums[k3] - mean);
        }
        v2 /= Math.max(1, nums.length - 1);
        var sd = v2 > 0 ? Math.sqrt(v2) : 0;
        if (sd === 0) return;
        for (var i3 = 0; i3 < n; i3++){
          if (vals[i3] == null || isNaN(+vals[i3])) continue;
          var z = Math.abs((+vals[i3] - mean) / sd);
          if (z > 4) keep[i3] = false;
        }
      }
    }
    pruneCol(xs);
    pruneCol(ys);
    return keep;
  }

  function _ccRenderStatsStrip(cid, bundle){
    var el = document.getElementById('stats-' + cid);
    if (!el) return;
    if (!bundle){ el.innerHTML = ''; return; }
    var cfg = _ccStudioCfg(cid);
    if (!cfg || !cfg.show_stats){ el.innerHTML = ''; return; }
    var os = bundle.overall;
    if (!os){
      el.innerHTML = '<span class="cc-stats-empty">'
        + 'n &lt; 2 \u2014 regression unavailable</span>';
      return;
    }
    if (os.degenerate === 'x_zero_variance'){
      el.innerHTML = '<span class="cc-stats-empty">'
        + 'n=' + os.n + ' \u2014 zero x-variance, regression undefined</span>';
      return;
    }
    var stars = _ccPStars(os.p_slope);
    var fmt = function(v, d){ return _ccFmt(v, d); };
    var html = '<span class="cc-stat">n=<b>' + os.n + '</b></span>'
      + '<span class="cc-stat">r=<b>' + fmt(os.r, 2) + '</b>' + stars + '</span>'
      + '<span class="cc-stat">R\u00B2=<b>' + fmt(os.r2, 2) + '</b></span>'
      + '<span class="cc-stat">\u03B2=<b>' + fmt(os.slope, 2)
      + '</b> (SE ' + fmt(os.se_slope, 2) + ')</span>'
      + '<span class="cc-stat">\u03B1=<b>' + fmt(os.intercept, 2) + '</b></span>'
      + '<span class="cc-stat">RMSE=<b>' + fmt(os.rmse, 2) + '</b></span>'
      + '<span class="cc-stat">p=<b>' + (os.p_slope == null
          ? '\u2014' : (+os.p_slope).toExponential(2)) + '</b></span>';
    if ((bundle.perGroup || []).length > 1){
      var pgHtml = (bundle.perGroup || []).map(function(pg){
        var s = pg.stats;
        if (!s) return '';
        var sw = pg.color
          ? ('<span class="cc-stats-swatch" style="background:'
              + pg.color + '"></span>')
          : '';
        return '<span class="cc-stat-group">' + sw + (pg.name || '')
          + ': r=' + fmt(s.r, 2) + ', R\u00B2=' + fmt(s.r2, 2)
          + ', \u03B2=' + fmt(s.slope, 2)
          + ' (n=' + s.n + ')</span>';
      }).filter(function(x){ return !!x; }).join('');
      if (pgHtml) html += '<div class="cc-stats-groups">' + pgHtml + '</div>';
    }
    el.innerHTML = html;
  }

  // ---- helpers: heatmap color scale ----

  function _ccApplyHeatmap(opt, state){
    if (!state.heatmapScale) return;
    var vm = opt.visualMap;
    if (Array.isArray(vm)) vm = vm[0];
    if (!vm) return;
    if (state.heatmapScale === 'diverging'){
      vm.inRange = vm.inRange || {};
      vm.inRange.color = ['#8C1D40', '#f5f5f5', '#1a365d'];
    } else if (state.heatmapScale === 'sequential'){
      vm.inRange = vm.inRange || {};
      vm.inRange.color = ['#f0f5fb', '#7399C6', '#002F6C'];
    }
  }

  // ---- helpers: correlation_matrix recompute (Transform / Window / Method) ----
  //
  // Mirrors echart_studio._corr_apply_window + _corr (Python) +
  // _ccColumnTransform (JS, line/scatter shared). Reads the
  // ``_corr_runtime`` sidecar embedded by build_correlation_matrix
  // and produces a fresh ``[[xIdx, yIdx, r], ...]`` cell array on
  // every drawer change.

  function _ccCorrCfg(cid){
    var base = SPECS[cid];
    if (!base) return null;
    return base._corr_runtime || null;
  }

  function _ccCorrWindowDays(window){
    if (!window || window === 'all') return null;
    if (/^\d+d$/.test(window)){
      var n = parseInt(window.slice(0, -1), 10);
      return isFinite(n) && n > 0 ? n : null;
    }
    return null;
  }

  function _ccCorrWindowLabel(window){
    var n = _ccCorrWindowDays(window);
    if (n == null) return 'Full sample';
    return n + '-day rolling';
  }

  var _CC_MS_PER_DAY = 24 * 3600 * 1000;

  function _ccCorrApplyWindow(transformed, times, window){
    var n = _ccCorrWindowDays(window);
    if (n == null || !times || !times.length) return transformed;
    var lastT = null;
    for (var i = times.length - 1; i >= 0; i--){
      if (times[i] != null){ lastT = times[i]; break; }
    }
    if (lastT == null) return transformed;
    var cutoff = lastT - n * _CC_MS_PER_DAY;
    var out = {};
    for (var col in transformed){
      if (!Object.prototype.hasOwnProperty.call(transformed, col)) continue;
      var arr = transformed[col] || [];
      var mask = new Array(arr.length);
      for (var k = 0; k < arr.length; k++){
        var t = times[k];
        if (t == null || t < cutoff){ mask[k] = null; }
        else { mask[k] = arr[k]; }
      }
      out[col] = mask;
    }
    return out;
  }

  function _ccPearsonAligned(xs, ys){
    var n = xs.length;
    if (n < 2) return null;
    var mx = 0, my = 0;
    for (var i = 0; i < n; i++){ mx += xs[i]; my += ys[i]; }
    mx /= n; my /= n;
    var sxx = 0, syy = 0, sxy = 0;
    for (var j = 0; j < n; j++){
      var dx = xs[j] - mx, dy = ys[j] - my;
      sxx += dx * dx; syy += dy * dy; sxy += dx * dy;
    }
    if (sxx <= 0 || syy <= 0) return null;
    return sxy / Math.sqrt(sxx * syy);
  }

  function _ccCorrRanks(values){
    // Average-rank ties (mirror scipy 'average' / pandas
    // Series.rank(method='average')).
    var pairs = [];
    for (var i = 0; i < values.length; i++){
      pairs.push({v: +values[i], i: i});
    }
    pairs.sort(function(a, b){ return a.v - b.v; });
    var out = new Array(values.length);
    var k = 0;
    while (k < pairs.length){
      var j = k;
      while (j + 1 < pairs.length && pairs[j + 1].v === pairs[k].v) j++;
      var avgRank = (k + j) / 2.0 + 1;
      for (var m = k; m <= j; m++) out[pairs[m].i] = avgRank;
      k = j + 1;
    }
    return out;
  }

  function _ccCorr(xs, ys, method, minPeriods){
    if (!xs || !ys) return null;
    var len = Math.min(xs.length, ys.length);
    var ax = []; var ay = [];
    for (var i = 0; i < len; i++){
      var a = xs[i], b = ys[i];
      if (a == null || b == null || isNaN(+a) || isNaN(+b)) continue;
      ax.push(+a); ay.push(+b);
    }
    var mp = (minPeriods != null && minPeriods >= 1) ? minPeriods : 5;
    if (ax.length < mp) return null;
    if (method === 'spearman'){
      return _ccPearsonAligned(_ccCorrRanks(ax), _ccCorrRanks(ay));
    }
    return _ccPearsonAligned(ax, ay);
  }

  function _ccCorrSubtitle(method, transform, window, asOf){
    // "Pearson · %Δ · 63-day rolling · as of 2026-04-22"
    // Drops the transform piece when raw, the window piece when 'all'
    // and no time axis, and the as-of piece when no time axis.
    var parts = [];
    var m = (method || 'pearson').toLowerCase();
    parts.push(m === 'spearman' ? 'Spearman' : 'Pearson');
    var tLbl = _ccTransformLabelShort(transform || 'raw');
    if (transform && transform !== 'raw' && tLbl) parts.push(tLbl);
    if (asOf){
      parts.push(_ccCorrWindowLabel(window).toLowerCase());
      parts.push('as of ' + asOf);
    } else if (window && window !== 'all'){
      parts.push(_ccCorrWindowLabel(window).toLowerCase());
    }
    return parts.join(' \u00B7 ');
  }

  function _ccApplyCorrelationMatrix(cid, opt, state){
    var cfg = _ccCorrCfg(cid);
    if (!cfg || !opt || !opt.series || !opt.series[0]){
      // Compile-time first-paint already in opt; nothing to do.
      // No defensive fallback here -- a missing _corr_runtime is
      // an engine bug, not a runtime case to guard against.
      if (state && state.heatmapScale){
        _ccApplyHeatmap(opt, state);
      }
      return;
    }

    var transform = state.corrTransform || cfg.transform_default || 'raw';
    var window    = state.corrWindow    || cfg.window_default    || 'all';
    var method    = state.corrMethod    || cfg.method            || 'pearson';

    var cols   = cfg.columns || [];
    var times  = cfg.times || null;
    var values = cfg.values || {};
    var minPeriods = +cfg.min_periods || 5;
    var n      = cols.length;

    // Per-column transform across the FULL history (so rolling z /
    // YoY have their full lookback) then mask outside the window.
    var transformed = {};
    for (var i = 0; i < n; i++){
      var col = cols[i];
      transformed[col] = _ccColumnTransform(values[col] || [],
                                              times || [], transform);
    }
    var sliced = _ccCorrApplyWindow(transformed, times, window);

    // Recompute pairwise correlations.
    var cells = new Array(n * n);
    for (var ii = 0; ii < n; ii++){
      for (var jj = 0; jj < n; jj++){
        var r = _ccCorr(sliced[cols[ii]], sliced[cols[jj]],
                          method, minPeriods);
        var yIdx = (n - 1) - jj;
        cells[ii * n + jj] = {value: [ii, yIdx, r]};
      }
    }
    opt.series[0].data = cells;

    // Visual-map color scale (existing diverging/sequential toggle).
    if (state.heatmapScale){
      var vm = opt.visualMap;
      if (Array.isArray(vm)) vm = vm[0];
      if (vm){
        vm.inRange = vm.inRange || {};
        if (state.heatmapScale === 'diverging'){
          vm.inRange.color = ['#8C1D40', '#f5f5f5', '#1a365d'];
        } else if (state.heatmapScale === 'sequential'){
          vm.inRange.color = ['#f0f5fb', '#7399C6', '#002F6C'];
        }
      }
    }

    // Subtitle: pack method + transform + window + as_of into one
    // line so the user always knows what they're looking at. Skip
    // when the author pinned an explicit subtitle. We do NOT touch
    // opt.title.text -- the dashboard pipeline blanks it when the
    // widget tile owns the title, and re-stamping causes double
    // headlines.
    opt.title = opt.title || {};
    if (!cfg.subtitle_author){
      opt.title.subtext = _ccCorrSubtitle(method, transform, window,
                                              cfg.as_of);
    }

    // Tooltip formatter: single source of truth for runtime. Shows
    // the active transform's unit suffix when applicable (e.g. "%"
    // for pct_change / yoy_pct).
    var dec = (cfg.decimals != null && !isNaN(+cfg.decimals))
      ? +cfg.decimals : 2;
    var unitSuffix = _ccTransformSuffix(transform);
    var xs = cols.slice(); var ys = cols.slice().reverse();
    opt.tooltip = opt.tooltip || {};
    opt.tooltip.show = true;
    opt.tooltip.trigger = 'item';
    opt.tooltip.formatter = function(p){
      var v = (p.data && p.data.value) || p.data || [];
      var xi = v[0], yi = v[1], rv = v[2];
      var rn = ys[yi] || ''; var cn = xs[xi] || '';
      if (rv == null || isNaN(+rv)){
        return rn + ' x ' + cn + ': insufficient overlap';
      }
      var label = rn + ' x ' + cn + ': r=' + (+rv).toFixed(dec);
      if (unitSuffix) label += ' (' + unitSuffix + ')';
      return label;
    };
  }

  // ---- helpers: pie sort + other-bucket ----

  function _ccApplyPie(opt, state){
    (opt.series || []).forEach(function(s){
      if (!s || (s.type !== 'pie')) return;
      var data = (s.data || []).slice();
      if (state.pieSort === 'desc'){
        data.sort(function(a, b){
          var av = (a && a.value != null) ? +a.value : -Infinity;
          var bv = (b && b.value != null) ? +b.value : -Infinity;
          return bv - av;
        });
      }
      var thresh = parseFloat(state.pieOther) || 0;
      if (thresh > 0){
        var total = data.reduce(function(a, x){
          return a + (x && x.value != null ? +x.value : 0);
        }, 0);
        if (total > 0){
          var keep = []; var otherSum = 0;
          data.forEach(function(d){
            if (!d) return;
            var v = +d.value || 0;
            if (v / total < thresh){ otherSum += v; }
            else { keep.push(d); }
          });
          if (otherSum > 0){
            keep.push({name: 'Other', value: otherSum});
          }
          data = keep;
        }
      }
      s.data = data;
    });
  }

  // ---- helpers: axis scale / range ----

  function _ccApplyYScale(opt, mode){
    var yax = opt.yAxis;
    var axes = Array.isArray(yax) ? yax : (yax ? [yax] : []);
    axes.forEach(function(a){
      if (!a || typeof a !== 'object') return;
      if (a.type === 'category') return;          // log only on numeric
      a.type = (mode === 'log') ? 'log' : 'value';
    });
  }
  function _ccApplyXScale(opt, mode){
    var xax = opt.xAxis;
    var axes = Array.isArray(xax) ? xax : (xax ? [xax] : []);
    axes.forEach(function(a){
      if (!a || typeof a !== 'object') return;
      if (a.type === 'category' || a.type === 'time') return;
      a.type = (mode === 'log') ? 'log' : 'value';
    });
  }
  function _ccApplyYRange(opt, mode){
    var yax = opt.yAxis;
    var axes = Array.isArray(yax) ? yax : (yax ? [yax] : []);
    axes.forEach(function(a){
      if (!a || typeof a !== 'object') return;
      if (a.type === 'category') return;
      if (mode === 'zero'){
        a.scale = false;
        a.min  = 0;
      } else {
        a.scale = true;
        if (a.min === 0) delete a.min;
      }
    });
  }

  // =========================================================================
  // CONTROLS DRAWER UI  (DOM rendering + event wiring)
  // =========================================================================

  function _ccTransformOptions(){
    // Grouped by category for the controls drawer dropdown. The
    // <optgroup> rendering happens in _ccBuildSelect; flat code paths
    // (legend tags, axis label) read these via _ccTransformLabel.
    return [
      {group: 'Basic', value: 'raw',                label: 'Raw'},
      {group: 'Basic', value: 'change',             label: 'Δ (period)'},
      {group: 'Basic', value: 'pct_change',         label: '% Δ (period)'},
      {group: 'Basic', value: 'log_change',         label: 'log Δ (period)'},
      {group: 'Basic', value: 'yoy_change',         label: 'YoY Δ'},
      {group: 'Basic', value: 'yoy_pct',            label: 'YoY %'},
      {group: 'Basic', value: 'yoy_log',            label: 'YoY log Δ'},
      {group: 'Basic', value: 'annualized_change',  label: 'Annualized Δ'},
      {group: 'Advanced', value: 'log',             label: 'log'},
      {group: 'Advanced', value: 'zscore',          label: 'z-score'},
      {group: 'Advanced', value: 'rolling_zscore_252', label: 'Rolling z (252)'},
      {group: 'Advanced', value: 'rank_pct',        label: 'Pct rank'},
      {group: 'Advanced', value: 'ytd',             label: 'Year-to-date Δ'},
      {group: 'Advanced', value: 'index100',        label: 'Index = 100 (first)'},
    ];
  }
  function _ccSmoothingOptions(){
    return [
      {value: 'off', label: 'Off'},
      {value: '5',   label: '5'},
      {value: '20',  label: '20'},
      {value: '50',  label: '50'},
      {value: '200', label: '200'},
    ];
  }
  function _ccBarSortOptions(){
    return [
      {value: 'input',    label: 'Input order'},
      {value: 'val_desc', label: 'Value desc'},
      {value: 'val_asc',  label: 'Value asc'},
      {value: 'name',     label: 'Alphabetical'},
    ];
  }
  function _ccBarStackOptions(){
    return [
      {value: 'group',   label: 'Grouped'},
      {value: 'stack',   label: 'Stacked'},
      {value: 'percent', label: '100% stacked'},
    ];
  }
  function _ccPieOtherOptions(){
    return [
      {value: '0',     label: 'Off'},
      {value: '0.01',  label: '< 1%'},
      {value: '0.03',  label: '< 3%'},
      {value: '0.05',  label: '< 5%'},
    ];
  }

  function _ccBuildSelect(name, current, options){
    // Renders a <select> with optional <optgroup> sections. An option
    // entry may carry a `group` key; consecutive entries with the same
    // group land inside one <optgroup label="...">. Entries without a
    // group fall through as bare <option> elements.
    var html = '<select data-cc-control="' + name + '">';
    var openGroup = null;
    options.forEach(function(o){
      var grp = o.group || null;
      if (grp !== openGroup){
        if (openGroup !== null) html += '</optgroup>';
        if (grp !== null){
          html += '<optgroup label="' + _he(String(grp)) + '">';
        }
        openGroup = grp;
      }
      var sel = (String(o.value) === String(current)) ? ' selected' : '';
      html += '<option value="' + _he(String(o.value)) + '"' + sel + '>'
            + _he(o.label) + '</option>';
    });
    if (openGroup !== null) html += '</optgroup>';
    return html + '</select>';
  }
  // Lightweight HTML escaper (mirrors _he used elsewhere; kept local
  // here so the controls module is self-contained).
  function _he(s){
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function _ccPopulateDrawer(cid){
    // Top-level dispatcher. Routes to the chart / table / kpi
    // populator based on the widget kind in WIDGET_META, then runs
    // the matching wirer. The drawer DOM elements are emitted by the
    // Python tile renderer for every supported widget kind, so this
    // function only has to figure out *which* knobs to render.
    var drawer = document.getElementById('controls-' + cid);
    if (!drawer) return;
    if (drawer.getAttribute('data-populated') === 'true') return;
    var w = WIDGET_META[cid];
    var kind = w && w.widget;
    if (kind === 'table'){ _ccPopulateTableDrawer(cid, drawer); return; }
    if (kind === 'kpi'){   _ccPopulateKpiDrawer(cid, drawer);   return; }
    _ccPopulateChartDrawer(cid, drawer);
  }

  function _ccPopulateChartDrawer(cid, drawer){
    var w = WIDGET_META[cid];
    var spec = (w && w.spec) || {};
    var ct = String(spec.chart_type || '').toLowerCase();
    var state = _ccGetState(cid);

    var html = [];
    var hasSection = false;

    // --- Per-series transforms (time series only, no color long-form) ---
    var isTimeSeries = (ct === 'line' || ct === 'multi_line' || ct === 'area');
    var hasColorMapping = !!(spec.mapping && (spec.mapping.color || spec.mapping.colour));
    if (isTimeSeries && !hasColorMapping){
      // Read series list from SPECS (compile-time source of truth) -
      // ECharts strips unknown fields like ``_column`` from
      // ``inst.getOption()`` in some versions, which would break
      // key alignment between the drawer state and the transform
      // application path. SPECS preserves _column verbatim.
      var baseOpt = SPECS[cid];
      var seriesList = (baseOpt && baseOpt.series) || [];
      // Filter out non-line/scatter/bar series (e.g. annotation overlays)
      seriesList = seriesList.filter(function(s){
        var t = s && s.type;
        return t === 'line' || t === 'bar' || t === 'scatter' || t === 'area';
      });
      if (seriesList.length){
        // Resolve a palette so each series row can show a small color
        // swatch. We use the per-chart palette if set on the option,
        // otherwise the manifest palette, otherwise the first
        // categorical palette in PAYLOAD.
        var palette = (baseOpt && baseOpt.color) ||
          (PAYLOAD.palettes && (
            (PAYLOAD.palettes[MANIFEST.palette] && PAYLOAD.palettes[MANIFEST.palette].colors) ||
            (PAYLOAD.palettes.gs_primary && PAYLOAD.palettes.gs_primary.colors))
          ) || [];
        html.push('<div class="cc-section">');
        html.push('<div class="cc-section-title">Series</div>');
        seriesList.forEach(function(s, i){
          // strip transform tag if already appended
          var rawName = String(s.name || '').replace(/\s+\u00B7\s+.*$/, '');
          var key = s._column || rawName;
          var sState = state.series[key] || {};
          var color = (s.lineStyle && s.lineStyle.color)
            || (s.itemStyle && s.itemStyle.color)
            || palette[i % (palette.length || 1)]
            || '';
          html.push('<div class="cc-series-row" data-series-key="'
            + _he(key) + '">');
          html.push('<span class="cc-series-name">');
          if (color){
            html.push('<span class="cc-series-swatch" style="background:'
              + _he(color) + '"></span>');
          }
          html.push(_he(rawName) + '</span>');
          html.push(_ccBuildSelect(
            'series-transform', sState.transform || 'raw',
            _ccTransformOptions()));
          html.push('<label style="display:inline-flex;'
            + 'align-items:center;gap:4px;font-size:11px;">'
            + '<input type="checkbox" data-cc-control="series-visible"'
            + (sState.visible === false ? '' : ' checked') + '/>'
            + 'show</label>');
          html.push('</div>');
        });
        html.push('</div>');
        hasSection = true;
      }
    } else if (isTimeSeries && hasColorMapping){
      // Long-form: single chart-wide transform
      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Transform</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">All series</span>');
      html.push(_ccBuildSelect(
        'transform-all', state.transformAll || 'raw',
        _ccTransformOptions()));
      html.push('</div></div>');
      hasSection = true;
    }

    // --- Shape (line / area only) ---
    //   Mirrors Haver's chart-type strip (Line / Line dotted /
    //   Line dashed / Area / Step / Stacked / 100% stacked) but
    //   composable: each axis is its own dropdown, so a user can mix
    //   "dashed" + "step start" + "area fill" + "stacked" if they
    //   want. Keeps "inherit" as the default so the author's
    //   compile-time choice (e.g. dotted line) survives until the
    //   user explicitly overrides.
    if (isTimeSeries){
      var sh = state.shape || {};
      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Shape</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">Style</span>');
      html.push(_ccBuildSelect(
        'shape-line-style', sh.lineStyleType || 'inherit',
        [{value: 'inherit', label: 'Inherit'},
          {value: 'solid',   label: 'Solid'},
          {value: 'dotted',  label: 'Dotted'},
          {value: 'dashed',  label: 'Dashed'}]));
      html.push('<span class="cc-label">Step</span>');
      html.push(_ccBuildSelect(
        'shape-step', sh.step || 'inherit',
        [{value: 'inherit', label: 'Inherit'},
          {value: 'off',    label: 'Off'},
          {value: 'start',  label: 'Start'},
          {value: 'middle', label: 'Middle'},
          {value: 'end',    label: 'End'}]));
      html.push('<span class="cc-label">Width</span>');
      html.push(_ccBuildSelect(
        'shape-line-width', sh.lineWidth || 'inherit',
        [{value: 'inherit', label: 'Inherit'},
          {value: '1', label: '1 px'},
          {value: '2', label: '2 px'},
          {value: '3', label: '3 px'}]));
      html.push('</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">Area fill</span>');
      html.push(_ccBuildSelect(
        'shape-area-fill', sh.areaFill || 'inherit',
        [{value: 'inherit', label: 'Inherit'},
          {value: 'on',  label: 'On'},
          {value: 'off', label: 'Off'}]));
      html.push('<span class="cc-label">Stack</span>');
      html.push(_ccBuildSelect(
        'shape-stack', sh.stack || 'inherit',
        [{value: 'inherit', label: 'Inherit'},
          {value: 'group',   label: 'Grouped'},
          {value: 'stack',   label: 'Stacked'},
          {value: 'percent', label: '100% stacked'}]));
      html.push('<span class="cc-label">Markers</span>');
      html.push(_ccBuildSelect(
        'shape-show-symbol', sh.showSymbol || 'inherit',
        [{value: 'inherit', label: 'Inherit'},
          {value: 'on',  label: 'Show'},
          {value: 'off', label: 'Hide'}]));
      html.push('</div></div>');
      hasSection = true;
    }

    // --- Time series chart-level knobs ---
    if (isTimeSeries){
      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Chart</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">Smoothing</span>');
      html.push(_ccBuildSelect(
        'smoothing', state.smoothing || 'off',
        _ccSmoothingOptions()));
      html.push('<span class="cc-label">Y-scale</span>');
      html.push(_ccBuildSelect(
        'y-scale', state.yScale || 'linear',
        [{value: 'linear', label: 'Linear'},
          {value: 'log',    label: 'Log'}]));
      html.push('<span class="cc-label">Y-range</span>');
      html.push(_ccBuildSelect(
        'y-range', state.yRange || 'auto',
        [{value: 'auto', label: 'Auto'},
          {value: 'zero', label: 'From zero'}]));
      html.push('</div></div>');
      hasSection = true;
    }

    // --- Bar knobs ---
    if (ct === 'bar' || ct === 'bar_horizontal'){
      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Bar</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">Sort</span>');
      html.push(_ccBuildSelect(
        'bar-sort', state.barSort || 'input',
        _ccBarSortOptions()));
      html.push('<span class="cc-label">Stack</span>');
      html.push(_ccBuildSelect(
        'bar-stack', state.barStack || 'group',
        _ccBarStackOptions()));
      html.push('<span class="cc-label">Y-scale</span>');
      html.push(_ccBuildSelect(
        'y-scale', state.yScale || 'linear',
        [{value: 'linear', label: 'Linear'},
          {value: 'log',    label: 'Log'}]));
      html.push('</div></div>');
      hasSection = true;
    }

    // --- Scatter knobs ---
    if (ct === 'scatter' || ct === 'scatter_multi'){
      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Scatter</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">Trendline</span>');
      html.push(_ccBuildSelect(
        'scatter-trendline', state.scatterTrendline || 'off',
        [{value: 'off',    label: 'Off'},
          {value: 'linear', label: 'Linear (OLS)'}]));
      html.push('<span class="cc-label">X-scale</span>');
      html.push(_ccBuildSelect(
        'x-scale', state.xScale || 'linear',
        [{value: 'linear', label: 'Linear'},
          {value: 'log',    label: 'Log'}]));
      html.push('<span class="cc-label">Y-scale</span>');
      html.push(_ccBuildSelect(
        'y-scale', state.yScale || 'linear',
        [{value: 'linear', label: 'Linear'},
          {value: 'log',    label: 'Log'}]));
      html.push('</div></div>');
      hasSection = true;
    }

    // --- Scatter studio (interactive X/Y picker + regression) ---
    if (ct === 'scatter_studio'){
      var cfg = _ccStudioCfg(cid);
      if (cfg){
        var st = state.studio = state.studio || {};
        var xCol = st.xCol || cfg.x_default;
        var yCol = st.yCol || cfg.y_default;
        var colorCol = (st.colorCol === '')
          ? '' : (st.colorCol || cfg.color_default || '');
        var sizeCol = (st.sizeCol === '')
          ? '' : (st.sizeCol || cfg.size_default || '');
        var xT = st.xTransform || cfg.x_transform_default || 'raw';
        var yT = st.yTransform || cfg.y_transform_default || 'raw';
        var winSel = st.window || cfg.window_default || 'all';
        var outSel = st.outliers || cfg.outlier_default || 'off';
        var regSel = st.regression || cfg.regression_default || 'off';

        var transformOpts = (cfg.transforms || []).map(function(t){
          return {value: t, label: _ccTransformLabelShort(t)};
        });
        var colOpts = function(list){
          return (list || []).map(function(c){
            return {value: c, label: c};
          });
        };
        var nullableOpts = function(list){
          return [{value: '', label: '\u2014 none \u2014'}]
            .concat(colOpts(list));
        };

        html.push('<div class="cc-section">');
        html.push('<div class="cc-section-title">Studio</div>');

        // Row 1: X axis
        html.push('<div class="cc-row">');
        html.push('<span class="cc-label">X axis</span>');
        html.push(_ccBuildSelect('studio-x', xCol, colOpts(cfg.x_columns)));
        html.push('<span class="cc-label">Transform</span>');
        html.push(_ccBuildSelect('studio-x-transform', xT, transformOpts));
        html.push('</div>');

        // Row 2: Y axis
        html.push('<div class="cc-row">');
        html.push('<span class="cc-label">Y axis</span>');
        html.push(_ccBuildSelect('studio-y', yCol, colOpts(cfg.y_columns)));
        html.push('<span class="cc-label">Transform</span>');
        html.push(_ccBuildSelect('studio-y-transform', yT, transformOpts));
        html.push('</div>');

        // Row 3: Color + Size (only when columns are configured).
        if ((cfg.color_columns || []).length
              || (cfg.size_columns || []).length){
          html.push('<div class="cc-row">');
          if ((cfg.color_columns || []).length){
            html.push('<span class="cc-label">Color</span>');
            html.push(_ccBuildSelect('studio-color', colorCol,
                                        nullableOpts(cfg.color_columns)));
          }
          if ((cfg.size_columns || []).length){
            html.push('<span class="cc-label">Size</span>');
            html.push(_ccBuildSelect('studio-size', sizeCol,
                                        nullableOpts(cfg.size_columns)));
          }
          html.push('</div>');
        }

        // Row 4: Window (only when order_by is set) + Regression
        var hasOrder = !!cfg.order_by;
        var winChoices = (cfg.window_options || ['all'])
          .map(function(w){
            var lbl = w;
            if (w === 'all')   lbl = 'All';
            else if (/^\d+d$/.test(w)) lbl = w.replace('d', ' days');
            else if (/^\d+y$/.test(w)) lbl = w.replace('y', ' years');
            return {value: w, label: lbl};
          });
        var regChoices = (cfg.regression_options || ['off', 'ols'])
          .map(function(r){
            var lbl = ({off: 'Off', ols: 'OLS',
                         ols_per_group: 'OLS per color'})[r] || r;
            return {value: r, label: lbl};
          });
        var outChoices = (cfg.outlier_options || ['off'])
          .map(function(o){
            var lbl = ({off: 'Off',
                         iqr_3: 'IQR \u00D7 3',
                         z_4: '|z| > 4'})[o] || o;
            return {value: o, label: lbl};
          });
        html.push('<div class="cc-row">');
        if (hasOrder){
          html.push('<span class="cc-label">Window</span>');
          html.push(_ccBuildSelect('studio-window', winSel, winChoices));
        }
        html.push('<span class="cc-label">Outliers</span>');
        html.push(_ccBuildSelect('studio-outliers', outSel, outChoices));
        html.push('<span class="cc-label">Regression</span>');
        html.push(_ccBuildSelect('studio-regression', regSel, regChoices));
        html.push('</div>');

        // Row 5: X / Y scale
        html.push('<div class="cc-row">');
        html.push('<span class="cc-label">X-scale</span>');
        html.push(_ccBuildSelect(
          'x-scale', state.xScale || 'linear',
          [{value: 'linear', label: 'Linear'},
            {value: 'log',    label: 'Log'}]));
        html.push('<span class="cc-label">Y-scale</span>');
        html.push(_ccBuildSelect(
          'y-scale', state.yScale || 'linear',
          [{value: 'linear', label: 'Linear'},
            {value: 'log',    label: 'Log'}]));
        html.push('</div>');

        html.push('</div>');
        hasSection = true;
      }
    }

    // --- Heatmap knobs (categorical X/Y/value) ---
    if (ct === 'heatmap'){
      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Heatmap</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">Color scale</span>');
      html.push(_ccBuildSelect(
        'heatmap-scale', state.heatmapScale || 'sequential',
        [{value: 'sequential', label: 'Sequential'},
          {value: 'diverging',  label: 'Diverging (around 0)'}]));
      html.push('</div></div>');
      hasSection = true;
    }

    // --- Correlation matrix knobs (Transform / Window / Method) ---
    if (ct === 'correlation_matrix'){
      var corrCfg = _ccCorrCfg(cid) || {};
      var transformsList = corrCfg.transforms || ['raw'];
      var windowList     = corrCfg.window_options || ['all'];
      var hasTimeAxis    = !!(corrCfg.times && corrCfg.times.length
                              && corrCfg.as_of);

      // Transform: filter the curated list to ones that don't need
      // a time axis when we don't have one. Order-aware transforms
      // (change / pct_change / yoy_* / rolling_zscore_*) drop out
      // when ``times`` is null on the runtime sidecar.
      var orderAware = function(t){
        if (!t) return false;
        if (t === 'change' || t === 'pct_change') return true;
        if (t === 'yoy_change' || t === 'yoy_pct'
              || t === 'yoy_log') return true;
        if (t === 'ytd' || t === 'annualized_change') return true;
        if (t.indexOf('rolling_zscore_') === 0) return true;
        return false;
      };
      var transformOpts = transformsList
        .filter(function(t){ return hasTimeAxis || !orderAware(t); })
        .map(function(t){
          return {value: t, label: _ccTransformLabelShort(t)};
        });
      var curTransform = state.corrTransform
        || corrCfg.transform_default || 'raw';

      var windowLabel = function(w){
        if (w === 'all') return 'All';
        var m = /^(\d+)d$/.exec(w);
        if (!m) return w;
        var n = +m[1];
        var months = {21: '1m', 63: '3m', 126: '6m', 252: '1y',
                       504: '2y', 1260: '5y'}[n];
        return months ? (months + ' (' + n + 'd)') : (n + ' days');
      };
      var windowOpts = windowList.map(function(w){
        return {value: w, label: windowLabel(w)};
      });
      var curWindow = state.corrWindow
        || corrCfg.window_default || 'all';

      var curMethod = state.corrMethod || corrCfg.method || 'pearson';

      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Correlation</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">Transform</span>');
      html.push(_ccBuildSelect('corr-transform', curTransform,
                                  transformOpts));
      if (hasTimeAxis){
        html.push('<span class="cc-label">Window</span>');
        html.push(_ccBuildSelect('corr-window', curWindow, windowOpts));
      }
      html.push('<span class="cc-label">Method</span>');
      html.push(_ccBuildSelect('corr-method', curMethod, [
        {value: 'pearson',  label: 'Pearson'},
        {value: 'spearman', label: 'Spearman'}]));
      html.push('</div>');

      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">Color scale</span>');
      html.push(_ccBuildSelect(
        'heatmap-scale', state.heatmapScale || 'diverging',
        [{value: 'diverging',  label: 'Diverging (around 0)'},
          {value: 'sequential', label: 'Sequential'}]));
      html.push('</div></div>');
      hasSection = true;
    }

    // --- Pie knobs ---
    if (ct === 'pie' || ct === 'donut'){
      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Pie</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">Sort</span>');
      html.push(_ccBuildSelect(
        'pie-sort', state.pieSort || 'input',
        [{value: 'input', label: 'Input order'},
          {value: 'desc',  label: 'Largest first'}]));
      html.push('<span class="cc-label">"Other"</span>');
      html.push(_ccBuildSelect(
        'pie-other', state.pieOther || '0',
        _ccPieOtherOptions()));
      html.push('</div></div>');
      hasSection = true;
    }

    // --- Universal action bar ---
    //   Two rows of buttons:
    //     1. Inspect actions (View data / Copy CSV / Reset)
    //     2. Download trio  (PNG / CSV / XLSX) -- pulls the same
    //        post-transform rows that View data shows, so what gets
    //        downloaded matches exactly what the user sees on screen.
    html.push('<div class="cc-section">');
    html.push('<div class="cc-actions">');
    html.push('<button class="cc-action-btn" data-cc-action="view-data">View data</button>');
    html.push('<button class="cc-action-btn" data-cc-action="copy-csv">Copy CSV</button>');
    html.push('<button class="cc-action-btn" data-cc-action="reset">Reset chart</button>');
    html.push('</div>');
    html.push('<div class="cc-actions">');
    html.push('<button class="cc-action-btn" data-cc-action="download-png">Download PNG</button>');
    html.push('<button class="cc-action-btn" data-cc-action="download-csv">Download CSV</button>');
    html.push('<button class="cc-action-btn" data-cc-action="download-xlsx">Download XLSX</button>');
    html.push('</div></div>');

    drawer.innerHTML = html.join('');
    drawer.setAttribute('data-populated', 'true');
    _ccWireDrawer(cid, drawer);
  }

  function _ccWireDrawer(cid, drawer){
    var state = _ccGetState(cid);
    drawer.querySelectorAll('[data-cc-control]').forEach(function(el){
      var name = el.getAttribute('data-cc-control');
      el.addEventListener('change', function(){
        if (name === 'series-transform'){
          var key = el.closest('.cc-series-row').getAttribute('data-series-key');
          state.series[key] = state.series[key] || {};
          state.series[key].transform = el.value;
        } else if (name === 'series-visible'){
          var key2 = el.closest('.cc-series-row').getAttribute('data-series-key');
          state.series[key2] = state.series[key2] || {};
          state.series[key2].visible = el.checked;
        } else if (name === 'transform-all'){
          state.transformAll = el.value;
          // Propagate to every series so the transform pass sees it.
          // Read from SPECS (compile-time) not live opt, so _column
          // matches the keys used by _ccApplyTimeSeries.
          var baseOpt2 = SPECS[cid];
          ((baseOpt2 && baseOpt2.series) || []).forEach(function(s){
            var key3 = s._column ||
              (s.name || '').replace(/\s+\u00B7\s+.*$/, '');
            if (!key3) return;
            state.series[key3] = state.series[key3] || {};
            state.series[key3].transform = el.value;
          });
        }         else if (name === 'smoothing')           state.smoothing = el.value;
        else if (name === 'y-scale')               state.yScale = el.value;
        else if (name === 'y-range')               state.yRange = el.value;
        else if (name === 'x-scale')               state.xScale = el.value;
        else if (name === 'bar-sort')              state.barSort = el.value;
        else if (name === 'bar-stack')             state.barStack = el.value;
        else if (name === 'scatter-trendline')     state.scatterTrendline = el.value;
        else if (name === 'heatmap-scale')         state.heatmapScale = el.value;
        else if (name === 'corr-transform')        state.corrTransform = el.value;
        else if (name === 'corr-window')           state.corrWindow = el.value;
        else if (name === 'corr-method')           state.corrMethod = el.value;
        else if (name === 'pie-sort')              state.pieSort = el.value;
        else if (name === 'pie-other')             state.pieOther = el.value;
        else if (name === 'studio-x')              { state.studio = state.studio || {}; state.studio.xCol = el.value; }
        else if (name === 'studio-y')              { state.studio = state.studio || {}; state.studio.yCol = el.value; }
        else if (name === 'studio-color')          { state.studio = state.studio || {}; state.studio.colorCol = el.value; }
        else if (name === 'studio-size')           { state.studio = state.studio || {}; state.studio.sizeCol = el.value; }
        else if (name === 'studio-x-transform')    { state.studio = state.studio || {}; state.studio.xTransform = el.value; }
        else if (name === 'studio-y-transform')    { state.studio = state.studio || {}; state.studio.yTransform = el.value; }
        else if (name === 'studio-window')         { state.studio = state.studio || {}; state.studio.window = el.value; }
        else if (name === 'studio-outliers')       { state.studio = state.studio || {}; state.studio.outliers = el.value; }
        else if (name === 'studio-regression')     { state.studio = state.studio || {}; state.studio.regression = el.value; }
        else if (name === 'shape-line-style')      { state.shape = state.shape || {}; state.shape.lineStyleType = el.value; }
        else if (name === 'shape-step')            { state.shape = state.shape || {}; state.shape.step = el.value; }
        else if (name === 'shape-line-width')      { state.shape = state.shape || {}; state.shape.lineWidth = el.value; }
        else if (name === 'shape-area-fill')       { state.shape = state.shape || {}; state.shape.areaFill = el.value; }
        else if (name === 'shape-stack')           { state.shape = state.shape || {}; state.shape.stack = el.value; }
        else if (name === 'shape-show-symbol')     { state.shape = state.shape || {}; state.shape.showSymbol = el.value; }
        rerenderChart(cid);
      });
    });
    drawer.querySelectorAll('[data-cc-action]').forEach(function(btn){
      var act = btn.getAttribute('data-cc-action');
      btn.addEventListener('click', function(){
        if (act === 'view-data')          _ccViewData(cid);
        else if (act === 'copy-csv')      _ccCopyCsv(cid);
        else if (act === 'download-csv')  _ccDownloadCsv(cid);
        else if (act === 'download-png')  _ccDownloadPng(cid);
        else if (act === 'download-xlsx') _ccDownloadXlsx(cid);
        else if (act === 'reset')         _ccReset(cid);
      });
    });
  }

  // =========================================================================
  // TABLE CONTROLS DRAWER  (mirror of chart drawer, scoped to TABLE_STATE)
  // =========================================================================
  //
  // Knobs (only render the ones the table can support):
  //   - Search rows                      always
  //   - Sort by column ▾  + Asc/Desc     when w.sortable !== false
  //   - Hide columns (multi-checkbox)    always
  //   - Freeze first column ☐            always
  //   - Row height: regular / compact    always
  //   - Decimals: auto / 0 / 1 / 2 / 3   always (override numeric format)
  //   - Actions: View raw / Copy CSV / Download CSV / Download XLSX
  //              / Reset
  //
  // Runtime state lives on TABLE_STATE[cid] (same dict the existing
  // sort + search code uses). Toggling any knob calls renderTables()
  // which re-runs the table render path with the new state applied.
  function _ccPopulateTableDrawer(cid, drawer){
    var w = WIDGET_META[cid];
    if (!w) return;
    var ts = tableState(cid);
    var ds = w.dataset_ref ? currentDatasets[w.dataset_ref] : null;
    var header = (ds && ds.length) ? ds[0] : [];
    var cols = w.columns;
    if (!cols || !cols.length){
      cols = header.map(function(h){ return {field: h, label: h}; });
    }

    var html = [];

    // --- Search ---
    html.push('<div class="cc-section">');
    html.push('<div class="cc-section-title">Search</div>');
    html.push('<div class="cc-row">');
    html.push('<span class="cc-label">Filter rows</span>');
    html.push('<input type="text" data-cc-control="table-search" '
      + 'value="' + _he(ts.search || '') + '" placeholder="type to search..."/>');
    html.push('</div></div>');

    // --- Sort ---
    if (w.sortable !== false){
      var colOpts = [{value: '', label: 'No sort (input order)'}];
      cols.forEach(function(c, i){
        colOpts.push({value: String(i),
                       label: String(c.label != null ? c.label : c.field)});
      });
      var curSort = (ts.sortCol == null) ? '' : String(ts.sortCol);
      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Sort</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">By column</span>');
      html.push(_ccBuildSelect('table-sort-col', curSort, colOpts));
      html.push('<span class="cc-label">Direction</span>');
      html.push(_ccBuildSelect(
        'table-sort-dir', String(ts.sortDir || 1),
        [{value: '1',  label: 'Ascending'},
          {value: '-1', label: 'Descending'}]));
      html.push('</div></div>');
    }

    // --- Hide columns ---
    if (cols.length){
      ts.hidden = ts.hidden || {};
      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Columns</div>');
      html.push('<div class="cc-row" style="flex-direction:column;'
        + 'align-items:flex-start;gap:4px 14px;">');
      cols.forEach(function(c, i){
        var lbl = String(c.label != null ? c.label : c.field);
        var checked = ts.hidden[i] ? '' : ' checked';
        html.push('<label style="display:inline-flex;align-items:center;'
          + 'gap:6px;font-size:11px;font-weight:500;color:var(--text);">'
          + '<input type="checkbox" data-cc-control="table-col-visible" '
          + 'data-col-idx="' + i + '"' + checked + '/>'
          + _he(lbl) + '</label>');
      });
      html.push('</div></div>');
    }

    // --- Layout knobs ---
    html.push('<div class="cc-section">');
    html.push('<div class="cc-section-title">Layout</div>');
    html.push('<div class="cc-row">');
    html.push('<span class="cc-label">Density</span>');
    html.push(_ccBuildSelect(
      'table-density', ts.density || 'regular',
      [{value: 'regular', label: 'Regular'},
        {value: 'compact', label: 'Compact'}]));
    html.push('<span class="cc-label">Freeze first col</span>');
    html.push(_ccBuildSelect(
      'table-freeze', String(!!ts.freezeFirst),
      [{value: 'false', label: 'Off'},
        {value: 'true',  label: 'On'}]));
    html.push('<span class="cc-label">Decimals</span>');
    html.push(_ccBuildSelect(
      'table-decimals',
      ts.decimals == null ? 'auto' : String(ts.decimals),
      [{value: 'auto', label: 'Auto'},
        {value: '0',   label: '0'},
        {value: '1',   label: '1'},
        {value: '2',   label: '2'},
        {value: '3',   label: '3'},
        {value: '4',   label: '4'}]));
    html.push('</div></div>');

    // --- Actions ---
    html.push('<div class="cc-section">');
    html.push('<div class="cc-actions">');
    html.push('<button class="cc-action-btn" data-cc-action="table-view-raw">View raw</button>');
    html.push('<button class="cc-action-btn" data-cc-action="table-copy-csv">Copy CSV</button>');
    html.push('<button class="cc-action-btn" data-cc-action="table-reset">Reset table</button>');
    html.push('</div>');
    html.push('<div class="cc-actions">');
    html.push('<button class="cc-action-btn" data-cc-action="table-download-csv">Download CSV</button>');
    html.push('<button class="cc-action-btn" data-cc-action="table-download-xlsx">Download XLSX</button>');
    html.push('</div></div>');

    drawer.innerHTML = html.join('');
    drawer.setAttribute('data-populated', 'true');
    _ccWireTableDrawer(cid, drawer);
  }

  function _ccWireTableDrawer(cid, drawer){
    var ts = tableState(cid);
    drawer.querySelectorAll('[data-cc-control]').forEach(function(el){
      var name = el.getAttribute('data-cc-control');
      var fire = function(){
        if (name === 'table-search'){
          ts.search = el.value;
        } else if (name === 'table-sort-col'){
          ts.sortCol = el.value === '' ? null : Number(el.value);
        } else if (name === 'table-sort-dir'){
          ts.sortDir = Number(el.value) || 1;
        } else if (name === 'table-col-visible'){
          var idx = Number(el.getAttribute('data-col-idx'));
          ts.hidden = ts.hidden || {};
          ts.hidden[idx] = !el.checked;
        } else if (name === 'table-density'){
          ts.density = el.value;
        } else if (name === 'table-freeze'){
          ts.freezeFirst = (el.value === 'true');
        } else if (name === 'table-decimals'){
          ts.decimals = (el.value === 'auto') ? null : Number(el.value);
        }
        renderTables();
      };
      el.addEventListener(el.tagName === 'INPUT'
                            && el.type === 'text' ? 'input' : 'change', fire);
    });
    drawer.querySelectorAll('[data-cc-action]').forEach(function(btn){
      var act = btn.getAttribute('data-cc-action');
      btn.addEventListener('click', function(){
        if (act === 'table-view-raw')           _ccTableViewRaw(cid);
        else if (act === 'table-copy-csv')      _ccTableCopyCsv(cid);
        else if (act === 'table-download-csv')  _ccTableDownloadCsv(cid);
        else if (act === 'table-download-xlsx') _ccTableDownloadXlsx(cid);
        else if (act === 'table-reset')         _ccTableReset(cid);
      });
    });
  }

  function _ccTableRows(cid){
    var w = WIDGET_META[cid]; if (!_isTableWidget(w)) return null;
    var ds = w.dataset_ref ? currentDatasets[w.dataset_ref] : null;
    if (!ds || !ds.length) return null;
    return applyFilters(w.dataset_ref, ds, 'table', cid);
  }
  function _ccTableViewRaw(cid){
    var rows = _ccTableRows(cid);
    if (!rows || !rows.length){
      showModal('Raw data', '<p>No rows.</p>');
      return;
    }
    var w = WIDGET_META[cid] || {};
    var title = (w.title || w.id || 'Table') + ' - raw data';
    var meta = '<div class="view-data-meta">'
      + (rows.length - 1) + ' rows &middot; '
      + (rows[0] || []).length + ' columns'
      + '</div>';
    var head = (rows[0] || []).map(function(h){
      return '<th>' + _he(h) + '</th>';
    }).join('');
    var bodyRows = rows.slice(1, 1001).map(function(r){
      return '<tr>' + r.map(function(v){
        var t = (v == null) ? '' : (typeof v === 'number'
          ? v.toLocaleString(undefined, {maximumFractionDigits: __MAX_DEC})
          : String(v));
        return '<td>' + _he(t) + '</td>';
      }).join('') + '</tr>';
    }).join('');
    var trunc = rows.length > 1001
      ? '<div class="view-data-meta">Showing first 1000 of '
        + (rows.length - 1) + ' rows.</div>'
      : '';
    showModal(title,
      meta
      + '<div class="view-data-scroll"><table class="view-data-table">'
      + '<thead><tr>' + head + '</tr></thead>'
      + '<tbody>' + bodyRows + '</tbody></table></div>'
      + trunc,
      {wide: true});
  }
  function _ccTableCsvRows(cid){
    if (typeof _exportTableRowsForXlsx !== 'function') return null;
    return _exportTableRowsForXlsx(cid);
  }
  function _ccTableCopyCsv(cid){
    var rows = _ccTableCsvRows(cid);
    if (!rows || !rows.length){
      showModal('Copy CSV', '<p>No rows.</p>');
      return;
    }
    var csv = _ccRowsToCsv(rows);
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(csv).then(function(){
        _ccFlashAction(cid, 'table-copy-csv', 'Copied');
      }, function(){
        _ccFallbackCopy(csv);
        _ccFlashAction(cid, 'table-copy-csv', 'Copied');
      });
    } else {
      _ccFallbackCopy(csv);
      _ccFlashAction(cid, 'table-copy-csv', 'Copied');
    }
  }
  function _ccTableDownloadCsv(cid){
    var rows = _ccTableCsvRows(cid);
    if (!rows || !rows.length){
      showModal('Download CSV', '<p>No rows to download.</p>');
      return;
    }
    var csv = _ccRowsToCsv(rows);
    var blob = new Blob([csv], {type: 'text/csv;charset=utf-8'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = _ccChartFilenameStem(cid) + '.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function(){ URL.revokeObjectURL(url); }, 1200);
    _ccFlashAction(cid, 'table-download-csv', 'Saved');
  }
  function _ccTableDownloadXlsx(cid){
    if (typeof window.downloadOneTableXlsx === 'function'){
      window.downloadOneTableXlsx(cid);
      _ccFlashAction(cid, 'table-download-xlsx', 'Saved');
    }
  }
  function _ccTableReset(cid){
    TABLE_STATE[cid] = {sortCol: null, sortDir: 1, search: ''};
    var drawer = document.getElementById('controls-' + cid);
    if (drawer){
      drawer.setAttribute('data-populated', 'false');
      drawer.innerHTML = '';
      _ccPopulateTableDrawer(cid, drawer);
    }
    renderTables();
  }

  // =========================================================================
  // KPI CONTROLS DRAWER
  //
  // Knobs (only render those the KPI can support):
  //   - Compare period (when sparkline_source set):
  //       Auto / Prev / 1d / 1w / 1m / 3m / 6m / 1y / YTD
  //   - Show sparkline ☐
  //   - Show delta ☐
  //   - Decimals override (auto / 0..4)
  //   - Actions: View data / Copy CSV / Download CSV / Download XLSX
  //              / Reset
  //
  // State lives on KPI_STATE[cid]. The existing renderKpis() is
  // re-invoked on every change so the displayed value, delta, and
  // sparkline reflect the latest state.
  // =========================================================================

  var KPI_STATE = {};
  function _kpiState(cid){
    if (!KPI_STATE[cid]){
      KPI_STATE[cid] = {
        showSparkline: true,
        showDelta: true,
        comparePeriod: 'auto',
        decimals: null,
      };
    }
    return KPI_STATE[cid];
  }

  function _ccPopulateKpiDrawer(cid, drawer){
    var w = WIDGET_META[cid];
    if (!w) return;
    var st = _kpiState(cid);
    var hasSpark = !!w.sparkline_source;
    var html = [];

    if (hasSpark){
      html.push('<div class="cc-section">');
      html.push('<div class="cc-section-title">Compare</div>');
      html.push('<div class="cc-row">');
      html.push('<span class="cc-label">Period</span>');
      html.push(_ccBuildSelect(
        'kpi-compare', st.comparePeriod || 'auto',
        [{value: 'auto', label: 'Auto (delta_source)'},
          {value: 'prev', label: 'Previous point'},
          {value: '1d',   label: '1 day'},
          {value: '5d',   label: '5 days'},
          {value: '1w',   label: '1 week'},
          {value: '1m',   label: '1 month'},
          {value: '3m',   label: '3 months'},
          {value: '6m',   label: '6 months'},
          {value: '1y',   label: '1 year'},
          {value: 'ytd',  label: 'Year-to-date'}]));
      html.push('</div></div>');
    }

    html.push('<div class="cc-section">');
    html.push('<div class="cc-section-title">Display</div>');
    html.push('<div class="cc-row">');
    if (hasSpark){
      html.push('<label style="display:inline-flex;align-items:center;'
        + 'gap:4px;font-size:11px;color:var(--text);">'
        + '<input type="checkbox" data-cc-control="kpi-show-sparkline"'
        + (st.showSparkline === false ? '' : ' checked') + '/>'
        + 'Sparkline</label>');
    }
    html.push('<label style="display:inline-flex;align-items:center;'
      + 'gap:4px;font-size:11px;color:var(--text);">'
      + '<input type="checkbox" data-cc-control="kpi-show-delta"'
      + (st.showDelta === false ? '' : ' checked') + '/>'
      + 'Delta</label>');
    html.push('<span class="cc-label">Decimals</span>');
    html.push(_ccBuildSelect(
      'kpi-decimals',
      st.decimals == null ? 'auto' : String(st.decimals),
      [{value: 'auto', label: 'Auto (default)'},
        {value: '0',   label: '0'},
        {value: '1',   label: '1'},
        {value: '2',   label: '2'},
        {value: '3',   label: '3'},
        {value: '4',   label: '4'}]));
    html.push('</div></div>');

    html.push('<div class="cc-section">');
    html.push('<div class="cc-actions">');
    html.push('<button class="cc-action-btn" data-cc-action="kpi-view-data">View data</button>');
    html.push('<button class="cc-action-btn" data-cc-action="kpi-copy-csv">Copy CSV</button>');
    html.push('<button class="cc-action-btn" data-cc-action="kpi-reset">Reset KPI</button>');
    html.push('</div>');
    html.push('<div class="cc-actions">');
    html.push('<button class="cc-action-btn" data-cc-action="kpi-download-csv">Download CSV</button>');
    html.push('<button class="cc-action-btn" data-cc-action="kpi-download-xlsx">Download XLSX</button>');
    html.push('</div></div>');

    drawer.innerHTML = html.join('');
    drawer.setAttribute('data-populated', 'true');
    _ccWireKpiDrawer(cid, drawer);
  }

  function _ccWireKpiDrawer(cid, drawer){
    var st = _kpiState(cid);
    drawer.querySelectorAll('[data-cc-control]').forEach(function(el){
      var name = el.getAttribute('data-cc-control');
      var ev = (el.tagName === 'INPUT' && el.type === 'checkbox')
        ? 'change' : 'change';
      el.addEventListener(ev, function(){
        if (name === 'kpi-compare')               st.comparePeriod = el.value;
        else if (name === 'kpi-show-sparkline')   st.showSparkline = el.checked;
        else if (name === 'kpi-show-delta')       st.showDelta = el.checked;
        else if (name === 'kpi-decimals')         st.decimals = (el.value === 'auto')
                                                    ? null : Number(el.value);
        renderKpis();
      });
    });
    drawer.querySelectorAll('[data-cc-action]').forEach(function(btn){
      var act = btn.getAttribute('data-cc-action');
      btn.addEventListener('click', function(){
        if (act === 'kpi-view-data')          _ccKpiViewData(cid);
        else if (act === 'kpi-copy-csv')      _ccKpiCopyCsv(cid);
        else if (act === 'kpi-download-csv')  _ccKpiDownloadCsv(cid);
        else if (act === 'kpi-download-xlsx') _ccKpiDownloadXlsx(cid);
        else if (act === 'kpi-reset')         _ccKpiReset(cid);
      });
    });
  }

  function _ccKpiSparklineRows(cid){
    var w = WIDGET_META[cid]; if (!w || !w.sparkline_source) return null;
    var sp = String(w.sparkline_source).split('.');
    if (sp.length < 2) return null;
    var dsName = sp[0]; var col = sp.slice(1).join('.');
    var ds = currentDatasets[dsName]; if (!ds || !ds.length) return null;
    var header = ds[0];
    var idx = header.indexOf(col);
    if (idx < 0) return null;
    // Try to find a matching x/date column for context.
    var xIdx = -1;
    for (var i = 0; i < header.length; i++){
      var h = String(header[i]).toLowerCase();
      if (h === 'date' || h === 'time' || h === 'timestamp'
          || h === 'x' || h.indexOf('date') >= 0){
        xIdx = i; break;
      }
    }
    if (xIdx < 0 && idx > 0) xIdx = 0;
    var out = [[xIdx >= 0 ? header[xIdx] : 'i', col]];
    for (var j = 1; j < ds.length; j++){
      var row = ds[j];
      out.push([xIdx >= 0 ? row[xIdx] : (j - 1), row[idx]]);
    }
    return out;
  }
  function _ccKpiViewData(cid){
    var rows = _ccKpiSparklineRows(cid);
    if (!rows || rows.length < 2){
      showModal('KPI data', '<p>No backing time series for this KPI.</p>');
      return;
    }
    var w = WIDGET_META[cid] || {};
    var title = (w.label || w.title || w.id || 'KPI') + ' - data';
    _ccShowDataModal(cid, rows[0], rows.slice(1));
  }
  function _ccKpiCopyCsv(cid){
    var rows = _ccKpiSparklineRows(cid);
    if (!rows || rows.length < 2){
      showModal('Copy CSV', '<p>Nothing to copy.</p>');
      return;
    }
    var csv = _ccRowsToCsv(rows);
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(csv).then(function(){
        _ccFlashAction(cid, 'kpi-copy-csv', 'Copied');
      });
    } else {
      _ccFallbackCopy(csv);
      _ccFlashAction(cid, 'kpi-copy-csv', 'Copied');
    }
  }
  function _ccKpiDownloadCsv(cid){
    var rows = _ccKpiSparklineRows(cid);
    if (!rows || rows.length < 2){
      showModal('Download CSV', '<p>Nothing to download.</p>');
      return;
    }
    var csv = _ccRowsToCsv(rows);
    var blob = new Blob([csv], {type: 'text/csv;charset=utf-8'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = _ccChartFilenameStem(cid) + '.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function(){ URL.revokeObjectURL(url); }, 1200);
    _ccFlashAction(cid, 'kpi-download-csv', 'Saved');
  }
  function _ccKpiDownloadXlsx(cid){
    if (typeof XLSX === 'undefined'){
      alert('Excel export requires the SheetJS library.');
      return;
    }
    var rows = _ccKpiSparklineRows(cid);
    if (!rows || rows.length < 2){
      showModal('Download XLSX', '<p>Nothing to download.</p>');
      return;
    }
    var w = WIDGET_META[cid] || {};
    var wb = XLSX.utils.book_new();
    var ws = XLSX.utils.aoa_to_sheet(rows);
    var sheet = String(w.label || w.title || cid)
      .replace(/[\\\/\?\*\[\]:]/g, ' ').trim().slice(0, 31) || 'kpi';
    XLSX.utils.book_append_sheet(wb, ws, sheet);
    XLSX.writeFile(wb, _ccChartFilenameStem(cid) + '.xlsx');
    _ccFlashAction(cid, 'kpi-download-xlsx', 'Saved');
  }
  function _ccKpiReset(cid){
    KPI_STATE[cid] = {
      showSparkline: true, showDelta: true,
      comparePeriod: 'auto', decimals: null
    };
    var drawer = document.getElementById('controls-' + cid);
    if (drawer){
      drawer.setAttribute('data-populated', 'false');
      drawer.innerHTML = '';
      _ccPopulateKpiDrawer(cid, drawer);
    }
    renderKpis();
  }

  function _ccToggleDrawer(cid){
    var drawer = document.getElementById('controls-' + cid);
    if (!drawer) return;
    var open = drawer.getAttribute('data-open') === 'true';
    if (!open){
      _ccPopulateDrawer(cid);
      drawer.setAttribute('data-open', 'true');
    } else {
      drawer.setAttribute('data-open', 'false');
    }
    var btn = document.querySelector(
      '[data-tile-id="' + cid + '"] .tile-btn.controls');
    if (btn) btn.setAttribute('data-active', String(!open));
    // Resize chart since the tile height changed
    var rec = CHARTS[cid];
    if (rec && rec.inst){
      try { rec.inst.resize(); } catch(e){}
    }
  }

  // ---- universal actions: View Data / Copy CSV / Reset ----

  function _ccChartFiltered(cid){
    var w = WIDGET_META[cid];
    if (!w) return null;
    var spec = w.spec || {};
    var ct   = String(spec.chart_type || '').toLowerCase();
    if (ct === 'correlation_matrix'){
      // correlation_matrix has no dataset_ref -- materialise the
      // current NxN matrix straight from the live option so View
      // Data / Copy CSV / Download CSV/XLSX reflect the runtime
      // (post Transform/Window/Method) state.
      return _ccCorrMatrixRows(cid);
    }
    if (!w.dataset_ref) return null;
    var ds = currentDatasets[w.dataset_ref];
    if (!ds || !ds.length) return null;
    return applyFilters(w.dataset_ref, ds, 'chart', cid);
  }

  function _ccCorrMatrixRows(cid){
    // Returns rows shaped as [[header...], [row...], ...]. The first
    // column is the row label (a column name from cfg.columns); each
    // subsequent column is the correlation coefficient against the
    // matching column. Reads the live option (post-recompute) so the
    // exported numbers exactly match what the cells display.
    var rec = CHARTS[cid];
    var opt = rec && rec.inst && rec.inst.getOption();
    var cfg = _ccCorrCfg(cid);
    if (!opt || !opt.series || !opt.series[0] || !cfg) return null;
    var cols = (cfg.columns || []).slice();
    var n = cols.length;
    if (!n) return null;

    var grid = [];
    for (var i = 0; i < n; i++){
      grid.push(new Array(n));
      for (var j = 0; j < n; j++) grid[i][j] = null;
    }
    var data = opt.series[0].data || [];
    data.forEach(function(d){
      var v = (d && d.value) || d;
      if (!Array.isArray(v) || v.length < 3) return;
      var xi = v[0]; var yi = v[1]; var rv = v[2];
      // _ccApplyCorrelationMatrix stores cells as
      // [colIdx, (n-1)-rowIdx, r]. Invert yi to recover row index.
      var ri = (n - 1) - yi;
      if (ri < 0 || ri >= n || xi < 0 || xi >= n) return;
      grid[ri][xi] = rv;
    });

    var header = [''].concat(cols);
    var rows = [header];
    var dec = (cfg.decimals != null && !isNaN(+cfg.decimals))
      ? +cfg.decimals : 2;
    for (var ri2 = 0; ri2 < n; ri2++){
      var row = [cols[ri2]];
      for (var ci = 0; ci < n; ci++){
        var v = grid[ri2][ci];
        row.push((v == null || isNaN(+v)) ? null
                                              : +(+v).toFixed(dec));
      }
      rows.push(row);
    }
    return rows;
  }

  function _ccViewData(cid){
    var rows = _ccChartFiltered(cid);
    if (!rows){
      // Fallback to the chart's live option series .data
      var rec = CHARTS[cid];
      var liveOpt = rec && rec.inst && rec.inst.getOption();
      var srs = (liveOpt && liveOpt.series) || [];
      if (!srs.length){
        showModal('No data', '<p>No data available for this chart.</p>');
        return;
      }
      var maxLen = 0;
      srs.forEach(function(s){
        var d = (s && s.data) || [];
        if (d.length > maxLen) maxLen = d.length;
      });
      var hdr = ['x'].concat(srs.map(function(s){
        return (s && s.name) || '';
      }));
      var body = [];
      for (var i = 0; i < maxLen; i++){
        var row = [];
        var any = false;
        for (var j = 0; j < srs.length; j++){
          var d2 = (srs[j] && srs[j].data) || [];
          var p = d2[i];
          if (Array.isArray(p)){
            if (j === 0) row.push(p[0]);
            row.push(p[1]);
            any = true;
          } else if (p && typeof p === 'object'){
            if (j === 0) row.push(p.name || p.value && p.value[0]);
            row.push(p.value != null ? p.value : null);
            any = true;
          } else if (p != null){
            if (j === 0) row.push(i);
            row.push(p);
            any = true;
          }
        }
        if (any) body.push(row);
      }
      _ccShowDataModal(cid, hdr, body);
      return;
    }
    _ccShowDataModal(cid, rows[0], rows.slice(1));
  }

  function _ccShowDataModal(cid, header, body){
    var w = WIDGET_META[cid] || {};
    var title = (w.title || w.id || 'Chart') + ' - data';
    var meta = '<div class="view-data-meta">'
      + body.length + ' rows &middot; '
      + header.length + ' columns'
      + '</div>';
    var html = ['<div class="view-data-scroll"><table class="view-data-table">'];
    html.push('<thead><tr>');
    header.forEach(function(h){ html.push('<th>' + _he(h) + '</th>'); });
    html.push('</tr></thead><tbody>');
    var maxRows = Math.min(body.length, 1000);
    for (var i = 0; i < maxRows; i++){
      var r = body[i];
      html.push('<tr>');
      for (var j = 0; j < header.length; j++){
        var v = r[j];
        var cell = (v == null) ? '' :
          (typeof v === 'number' ?
            v.toLocaleString(undefined, {maximumFractionDigits: __MAX_DEC})
            : String(v));
        html.push('<td>' + _he(cell) + '</td>');
      }
      html.push('</tr>');
    }
    html.push('</tbody></table></div>');
    if (body.length > maxRows){
      html.push('<div class="view-data-meta">'
        + 'Showing first ' + maxRows + ' of ' + body.length + ' rows. '
        + 'Use Copy CSV for the full dataset.</div>');
    }
    showModal(title, meta + html.join(''), {wide: true});
  }

  function _ccRowsToCsv(rows){
    return rows.map(function(r){
      return r.map(function(v){
        if (v == null) return '';
        var s = String(v);
        if (s.indexOf(',') >= 0 || s.indexOf('"') >= 0 || s.indexOf('\n') >= 0){
          return '"' + s.replace(/"/g, '""') + '"';
        }
        return s;
      }).join(',');
    }).join('\n');
  }
  function _ccChartFilenameStem(cid){
    var w = WIDGET_META[cid] || {};
    var raw = w.title || w.id || cid;
    return String(raw).replace(/[^\w\-]+/g, '_');
  }
  function _ccCopyCsv(cid){
    var rows = _ccChartFiltered(cid);
    if (!rows || !rows.length){
      showModal('Copy CSV', '<p>No data to copy.</p>');
      return;
    }
    var csv = _ccRowsToCsv(rows);
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(csv).then(function(){
        _ccFlashAction(cid, 'copy-csv', 'Copied');
      }, function(){
        _ccFallbackCopy(csv);
        _ccFlashAction(cid, 'copy-csv', 'Copied');
      });
    } else {
      _ccFallbackCopy(csv);
      _ccFlashAction(cid, 'copy-csv', 'Copied');
    }
  }
  function _ccDownloadCsv(cid){
    var rows = _ccChartFiltered(cid);
    if (!rows || !rows.length){
      showModal('Download CSV', '<p>No data to download.</p>');
      return;
    }
    var csv = _ccRowsToCsv(rows);
    var blob = new Blob([csv], {type: 'text/csv;charset=utf-8'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = _ccChartFilenameStem(cid) + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function(){ URL.revokeObjectURL(url); }, 1200);
    _ccFlashAction(cid, 'download-csv', 'Saved');
  }
  function _ccDownloadPng(cid){
    if (typeof _downloadChartPngTitled === 'function'){
      try { _downloadChartPngTitled(cid, 2); }
      catch(e){ showModal('Download PNG', '<p>PNG export failed.</p>'); }
      _ccFlashAction(cid, 'download-png', 'Saved');
      return;
    }
    var rec = CHARTS[cid];
    if (!rec || !rec.inst){
      showModal('Download PNG', '<p>Chart not initialized.</p>');
      return;
    }
    var url = rec.inst.getDataURL({pixelRatio: 2,
                                      backgroundColor: chartExportBackground(cid),
                                      type: 'png'});
    var a = document.createElement('a');
    a.href = url; a.download = _ccChartFilenameStem(cid) + '.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    _ccFlashAction(cid, 'download-png', 'Saved');
  }
  function _ccDownloadXlsx(cid){
    if (typeof XLSX === 'undefined'){
      alert('Excel export requires the SheetJS library. Reload while ' +
            'online so the dashboard can fetch it.');
      return;
    }
    var rows = _ccChartFiltered(cid);
    if (!rows || !rows.length){
      showModal('Download XLSX', '<p>No data to download.</p>');
      return;
    }
    var w = WIDGET_META[cid] || {};
    var wb = XLSX.utils.book_new();
    var ws = XLSX.utils.aoa_to_sheet(rows);
    var sheet = String(w.title || cid).replace(/[\\\/\?\*\[\]:]/g, ' ').trim();
    if (!sheet) sheet = 'data';
    sheet = sheet.slice(0, 31);
    XLSX.utils.book_append_sheet(wb, ws, sheet);
    XLSX.writeFile(wb, _ccChartFilenameStem(cid) + '.xlsx');
    _ccFlashAction(cid, 'download-xlsx', 'Saved');
  }
  function _ccFallbackCopy(text){
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch(e){}
    document.body.removeChild(ta);
  }
  function _ccFlashAction(cid, action, label){
    var btn = document.querySelector(
      '#controls-' + cid + ' [data-cc-action="' + action + '"]');
    if (!btn) return;
    var orig = btn.textContent;
    btn.textContent = label;
    setTimeout(function(){ btn.textContent = orig; }, 1200);
  }

  function _ccReset(cid){
    chartControlState[cid] = {series: {}};
    var drawer = document.getElementById('controls-' + cid);
    if (drawer){
      drawer.setAttribute('data-populated', 'false');
      drawer.innerHTML = '';
      // Repopulate so dropdowns reflect reset state
      _ccPopulateDrawer(cid);
    }
    // Clear the studio stats strip too (will repopulate after rerender).
    var strip = document.getElementById('stats-' + cid);
    if (strip) strip.innerHTML = '';
    rerenderChart(cid);
  }

  // ----- rewire a chart spec to use a shared dataset -----
  function _filteredFieldIndex(header, name){
    return (typeof name === 'string') ? header.indexOf(name) : -1;
  }

  function _rebuildFilteredChartOption(opt, chartType, mapping, source){
    var header = source[0] || [];
    var body = source.slice(1);
    var template = (opt.series && opt.series[0])
      ? JSON.parse(JSON.stringify(opt.series[0])) : {};
    if (chartType === 'pie' || chartType === 'donut'){
      var ci = _filteredFieldIndex(header, mapping.category);
      var vi = _filteredFieldIndex(header, mapping.value);
      template.type = 'pie';
      template.data = body.filter(function(r){
        return ci >= 0 && vi >= 0 && r[ci] != null && r[vi] != null;
      }).map(function(r){ return {name: String(r[ci]), value: r[vi]}; });
      opt.series = [template];
      if (opt.legend) opt.legend.data = template.data.map(function(d){ return d.name; });
      delete opt.dataset;
      return true;
    }
    if (chartType === 'heatmap'){
      var xi = _filteredFieldIndex(header, mapping.x);
      var yi = _filteredFieldIndex(header, mapping.y);
      var zi = _filteredFieldIndex(header, mapping.value);
      var xs = [], ys = [];
      body.forEach(function(r){
        if (xi >= 0 && r[xi] != null && xs.indexOf(r[xi]) < 0) xs.push(r[xi]);
        if (yi >= 0 && r[yi] != null && ys.indexOf(r[yi]) < 0) ys.push(r[yi]);
      });
      var cells = [], vals = [];
      body.forEach(function(r){
        if (xi < 0 || yi < 0 || zi < 0 || r[xi] == null || r[yi] == null) return;
        cells.push([xs.indexOf(r[xi]), ys.indexOf(r[yi]), r[zi]]);
        var n = Number(r[zi]); if (Number.isFinite(n)) vals.push(n);
      });
      opt.xAxis = Object.assign({}, opt.xAxis || {}, {type: 'category', data: xs});
      opt.yAxis = Object.assign({}, opt.yAxis || {}, {type: 'category', data: ys});
      template.type = 'heatmap'; template.data = cells;
      opt.series = [template];
      var vm = Array.isArray(opt.visualMap) ? opt.visualMap[0] : opt.visualMap;
      if (vm && vals.length){
        vm.min = Math.min.apply(null, vals); vm.max = Math.max.apply(null, vals);
      }
      delete opt.dataset;
      return true;
    }
    if (chartType === 'geo_map'){
      var ri = _filteredFieldIndex(header, mapping.region);
      var gvi = _filteredFieldIndex(header, mapping.value);
      var mapAsset = (PAYLOAD.maps || {})[mapping.map] || {};
      var aliases = mapAsset.aliases || {};
      var mapValues = [];
      template.type = 'map';
      template.map = mapping.map;
      template.data = body.filter(function(r){
        return ri >= 0 && gvi >= 0 && r[ri] != null && r[gvi] != null;
      }).map(function(r){
        var region = String(r[ri]);
        var n = Number(r[gvi]);
        if (Number.isFinite(n)) mapValues.push(n);
        return {name: String(aliases[region] || region), value: r[gvi]};
      });
      opt.series = [template];
      var gvm = Array.isArray(opt.visualMap) ? opt.visualMap[0] : opt.visualMap;
      if (gvm && mapValues.length){
        gvm.min = Math.min.apply(null, mapValues);
        gvm.max = Math.max.apply(null, mapValues);
      }
      delete opt.dataset;
      return true;
    }
    var groupField = mapping.color || mapping.colour;
    if (groupField && ['line', 'multi_line', 'bar', 'area', 'scatter'].indexOf(chartType) >= 0){
      var xg = _filteredFieldIndex(header, mapping.x);
      var yg = _filteredFieldIndex(header, mapping.y);
      var gg = _filteredFieldIndex(header, groupField);
      var sg = chartType === 'scatter'
        ? _filteredFieldIndex(header, mapping.size) : -1;
      var groups = {};
      body.forEach(function(r){
        if (xg < 0 || yg < 0 || gg < 0 || r[gg] == null) return;
        var key = String(r[gg]);
        if (!groups[key]) groups[key] = [];
        var point = [r[xg], r[yg]];
        if (sg >= 0) point.push(r[sg]);
        groups[key].push(point);
      });
      var oldByName = {};
      (opt.series || []).forEach(function(s){ if (s.name != null) oldByName[String(s.name)] = s; });
      opt.series = Object.keys(groups).map(function(name){
        var s = JSON.parse(JSON.stringify(oldByName[name] || template));
        s.name = name;
        s.type = chartType === 'bar'
          ? 'bar' : (chartType === 'scatter' ? 'scatter' : 'line');
        s.data = groups[name]; delete s.encode;
        if (chartType === 'area') s.areaStyle = s.areaStyle || {};
        if (mapping.stack) s.stack = (typeof mapping.stack === 'string') ? mapping.stack : 'total';
        return s;
      });
      if (opt.legend) opt.legend.data = Object.keys(groups);
      delete opt.dataset;
      return true;
    }
    return false;
  }

  function materializeOption(cid){
    var w = WIDGET_META[cid]; var base = SPECS[cid];
    var opt = JSON.parse(JSON.stringify(base));
    // scatter_studio + correlation_matrix entirely rebuild their option
    // shape inside applyChartControls (studio) or are stable (corr).
    // The standard rewire path (encode + delete s.data) would clobber
    // the studio's series so we skip it for that chart_type.
    var ctMat = String(((w && w.spec) || {}).chart_type || '').toLowerCase();
    var skipRewire = (ctMat === 'scatter_studio');
    // Dataset rewire path: only when the widget was auto-wired with a
    // dataset_ref (filter targets / safe rewire shapes). Charts that
    // weren't rewired keep their inline ``series[*].data`` arrays.
    if (!skipRewire && w && w.dataset_ref && currentDatasets[w.dataset_ref]){
      // Chart widgets always render against the full dataset; the
      // global dateRange filter only moves the dataZoom window. Other
      // filter types (select / radio / numberRange / etc.) still
      // narrow the dataset normally.
      var filt = applyFilters(
        w.dataset_ref, currentDatasets[w.dataset_ref], 'chart', cid);
      var mapping = ((w.spec || {}).mapping || {});
      var rebuilt = _rebuildFilteredChartOption(opt, ctMat, mapping, filt);
      if (!rebuilt) opt.dataset = {source: filt};
      var header = filt[0] || [];
      if (!rebuilt) (opt.series || []).forEach(function(s, i){
        var t = s.type;
        var isRewireable = (t === 'line' || t === 'bar'
                            || t === 'scatter' || t === 'area');
        if (!isRewireable) return;
        if (s.encode) return;                // already fully specified
        // Resolve dataset columns from the declared mapping first. Popup
        // detail datasets often retain row-key/filter columns before the
        // plotted x field, so assuming column 0 is x silently empties a
        // time axis after the shared filter controller rewires the option.
        var mappedX = (typeof mapping.x === 'string'
                       && header.indexOf(mapping.x) >= 0)
          ? mapping.x : header[0];
        var mappedY = Array.isArray(mapping.y)
          ? mapping.y[i] : mapping.y;
        // Resolve the y dataset column. Priority:
        //   1. the declared mapping.y field for this series
        //   2. `_column` hint set at build time (raw, pre-humanise col)
        //   3. exact match of series name against header
        //   4. positional index
        var yIdx = -1;
        if (typeof mappedY === 'string' && header.indexOf(mappedY) >= 0) {
          yIdx = header.indexOf(mappedY);
        } else if (s._column && header.indexOf(s._column) >= 0) {
          yIdx = header.indexOf(s._column);
        } else if (s.name && header.indexOf(s.name) >= 0) {
          yIdx = header.indexOf(s.name);
        } else {
          yIdx = Math.min(1 + i, header.length - 1);
        }
        if (yIdx <= 0) yIdx = Math.min(1, header.length - 1);
        s.encode = {x: mappedX, y: header[yIdx]};
        s.name = s.name || header[yIdx];
        delete s.data;
      });
    }
    // Translate any targeting dateRange filter into the chart's
    // dataZoom window. Charts without time-axis dataZoom (no
    // injection happened at compile time) skip this naturally.
    var dr = _dateRangeForChart(cid);
    _applyChartDateZoom(opt, dr);
    // A manifest brush link is behavioral intent, but ECharts emits real
    // brush selections only when the linked chart option carries a brush
    // component. Materialize that mechanical config here so authors never
    // have to duplicate it inside each chart spec.
    var brushLink = (MANIFEST.links || []).find(function(link){
      return link.brush && (link.members || []).some(function(member){
        return targetMatch(member, cid);
      });
    });
    if (brushLink){
      var declaredBrush = brushLink.brush;
      var brushType = (typeof declaredBrush === 'string')
        ? declaredBrush : (declaredBrush.type || 'lineX');
      var brushAxis = (typeof declaredBrush === 'object'
                       && declaredBrush.xAxisIndex != null)
        ? declaredBrush.xAxisIndex : 'all';
      opt.brush = Object.assign({
        brushMode: 'single',
        xAxisIndex: brushAxis,
        throttleType: 'debounce',
        throttleDelay: 120
      }, opt.brush || {});
      opt.toolbox = opt.toolbox || {show: true, feature: {}};
      opt.toolbox.feature = opt.toolbox.feature || {};
      opt.toolbox.feature.brush = {
        type: [brushType, 'clear']
      };
    }
    // Stable name-based color assignment runs after every rebuild so
    // filtering and row-order changes never rotate series identities.
    applyStableSeriesColors(cid, opt);
    // Apply runtime per-chart controls (transforms, smoothing,
    // y-scale, sort, stack, trendline, ...). No-op when the user
    // hasn't touched the drawer yet. Runs whether or not the chart
    // has a dataset_ref so transforms work on inline-data charts.
    applyChartControls(cid, opt);
    // Last-line-of-defence: ensure the tooltip cannot render raw
    // floats with > MAX_DASHBOARD_DECIMALS digits, regardless of
    // whether the compile-time pass installed a valueFormatter or
    // a runtime control already attached one.
    __ensureTooltipDecimalCap(opt);
    return opt;
  }

  // ----- chart init/render -----
  var CHARTS = {};
  var SERIES_COLOR_SLOTS = Object.create(null);

  function chartThemeName(cid){
    // Strip any explicit ``_dark`` suffix authors may have set on
    // the manifest theme; the toggle button owns the dark/light
    // axis. In dark mode, prefer the ``<base>_dark`` variant when
    // it has been registered (every theme shipped from config.py
    // has one), otherwise fall back to the base theme.
    var w = cid ? (WIDGET_META[cid] || {}) : {};
    var spec = w.spec || {};
    var t = spec.theme || MANIFEST.theme || 'gs_clean';
    var base = (typeof t === 'string' && t.length > 5 &&
                  t.lastIndexOf('_dark') === t.length - 5)
                  ? t.slice(0, -5) : t;
    return DARK_MODE ? base + '_dark' : base;
  }

  function resolvedThemeForChart(cid){
    var name = chartThemeName(cid);
    var resolved = PAYLOAD.resolvedThemes && PAYLOAD.resolvedThemes[name];
    if (!resolved){
      throw new Error('Resolved theme contract missing for chart ' +
        String(cid == null ? '<dashboard>' : cid) + ': ' + name);
    }
    return resolved;
  }

  function semanticColor(role, cid){
    var resolved = resolvedThemeForChart(cid);
    if (!resolved.semantic || !(role in resolved.semantic)){
      throw new Error("Resolved theme '" + resolved.name +
        "' is missing semantic color role '" + role + "'");
    }
    return resolved.semantic[role];
  }

  function _seriesPalette(cid){
    var w = WIDGET_META[cid] || {};
    var spec = w.spec || {};
    if (spec.colors && typeof spec.colors === 'object'){
      var modeColors = DARK_MODE ? spec.colors.dark : spec.colors.light;
      if (Array.isArray(modeColors) && modeColors.length) return modeColors;
    }
    var paletteName = spec.palette || MANIFEST.palette;
    if (paletteName && paletteName !== 'gs_primary' &&
        PAYLOAD.palettes && PAYLOAD.palettes[paletteName]){
      return PAYLOAD.palettes[paletteName].colors || [];
    }
    return resolvedThemeForChart(cid).categorical;
  }

  function _namedSeriesColor(cid, keys){
    var w = WIDGET_META[cid] || {};
    var spec = w.spec || {};
    var named = spec.series_colors;
    if (!named || typeof named !== 'object') return null;
    var mode = DARK_MODE ? 'dark' : 'light';
    for (var i = 0; i < keys.length; i++){
      if (keys[i] == null) continue;
      var record = named[String(keys[i])];
      if (record && typeof record[mode] === 'string'){
        return record[mode];
      }
    }
    return null;
  }

  function _stableColorIndex(name, size){
    var text = String(name == null ? '' : name);
    var hash = 2166136261;
    for (var i = 0; i < text.length; i++){
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return size ? (hash >>> 0) % size : 0;
  }

  function _optionColorKeys(opt){
    var keys = [];
    if (!opt || !Array.isArray(opt.series)) return keys;
    opt.series.forEach(function(series, index){
      if (!series || series.type === 'heatmap' || series.type === 'map') return;
      if (series.type === 'pie' && Array.isArray(series.data)){
        series.data.forEach(function(item, itemIndex){
          if (!item || typeof item !== 'object') return;
          keys.push(String(
            item.name != null ? item.name : 'slice-' + itemIndex));
        });
        return;
      }
      keys.push(String(
        series.name || series._column || ('series-' + index)));
    });
    return keys;
  }

  function _seriesColorSlots(cid, opt, size){
    var record = SERIES_COLOR_SLOTS[cid];
    if (!record || record.size !== size){
      record = {size: size, slots: Object.create(null)};
      SERIES_COLOR_SLOTS[cid] = record;
    }
    var used = Object.create(null);
    Object.keys(record.slots).forEach(function(key){
      used[record.slots[key]] = true;
    });
    var baseKeys = _optionColorKeys(SPECS[cid]);
    var keys = baseKeys.concat(_optionColorKeys(opt)).filter(
      function(key, index, all){ return all.indexOf(key) === index; }
    ).sort();
    keys.forEach(function(key){
      if (Object.prototype.hasOwnProperty.call(record.slots, key)) return;
      var slot = _stableColorIndex(key, size);
      if (Object.keys(used).length < size){
        while (used[slot]) slot = (slot + 1) % size;
        used[slot] = true;
      }
      record.slots[key] = slot;
    });
    return record.slots;
  }

  function applyStableSeriesColors(cid, opt){
    var palette = _seriesPalette(cid);
    if (!palette.length || !opt || !Array.isArray(opt.series)) return;
    opt.color = palette.slice();
    var slots = _seriesColorSlots(cid, opt, palette.length);
    opt.series.forEach(function(series, index){
      if (!series || series.type === 'heatmap') return;
      if (series.type === 'map'){
        series.itemStyle = series.itemStyle || {};
        series.itemStyle.borderColor = semanticColor('surface', cid);
        return;
      }
      if (series.type === 'pie' && Array.isArray(series.data)){
        series.data.forEach(function(item, itemIndex){
          if (!item || typeof item !== 'object') return;
          item.itemStyle = item.itemStyle || {};
          var itemName = item.name != null ? item.name : 'slice-' + itemIndex;
          var itemKey = String(itemName);
          var itemExplicit = _namedSeriesColor(cid, [item.name, itemKey]);
          if (itemExplicit){
            item.itemStyle.color = itemExplicit;
          } else if (!item.itemStyle.color){
            var itemSlot = Object.prototype.hasOwnProperty.call(slots, itemKey)
              ? slots[itemKey] : _stableColorIndex(itemKey, palette.length);
            item.itemStyle.color = palette[itemSlot];
          }
        });
        return;
      }
      var name = series.name || series._column || ('series-' + index);
      var key = String(name);
      var slot = Object.prototype.hasOwnProperty.call(slots, key)
        ? slots[key] : _stableColorIndex(key, palette.length);
      var explicit = _namedSeriesColor(
        cid, [series.name, series._column, key]);
      var color = explicit || palette[slot];
      series.itemStyle = series.itemStyle || {};
      series.lineStyle = series.lineStyle || {};
      if (explicit){
        series.itemStyle.color = color;
        series.lineStyle.color = color;
      } else {
        if (!series.itemStyle.color) series.itemStyle.color = color;
        if (!series.lineStyle.color) series.lineStyle.color = color;
      }
    });
  }

  function chartExportBackground(cid){
    return resolvedThemeForChart(cid).export.background;
  }

  function _mountChartInstance(cid, el, option, detailDataset){
    var theme = chartThemeName(cid);
    if (!(theme in PAYLOAD.themes)){
      throw new Error("ECharts theme '" + theme + "' is not registered");
    }
    var inst = echarts.init(el, theme);
    CHARTS[cid] = {inst: inst, datasetRef: WIDGET_META[cid].dataset_ref};
    inst.setOption(reviveFns(option), true);
    subscribe(cid, filtersForChart(cid));
    wireBrush(cid, inst);
    wireChartClick(cid, inst);
    wireChartClickPopup(cid, inst);
    applyConnects();
    if (detailDataset){
      _DETAIL_CHARTS.push({inst: inst, cid: cid, dataset: detailDataset});
    }
    return inst;
  }

  function initChart(cid){
    var el = document.getElementById('chart-' + cid); if (!el) return;
    if (CHARTS[cid]) return;
    var inst = _mountChartInstance(cid, el, materializeOption(cid), null);
    // Studio charts: populate the stats strip on first render too.
    var w = WIDGET_META[cid] || {};
    var ct = String(((w && w.spec) || {}).chart_type || '').toLowerCase();
    if (ct === 'scatter_studio'){
      var st = chartControlState[cid];
      _ccRenderStatsStrip(cid, (st && st._lastStudioStats) || null);
    }
  }

  // ----- chart click -> filter emit -----
  //
  // If a widget declares `click_emit_filter`, clicking any data point
  // in the chart writes a value to the named filter and broadcasts so
  // all downstream widgets react. The config can be either a simple
  // filter id string, or an object:
  //   { filter_id: "region",            (required)
  //     value_from: "name" | "value" |  (default "name")
  //                 "seriesName",
  //     toggle: true }                  (default true; clicking the
  //                                       same value again clears it)
  // Pairs well with a `radio` or `select` filter whose `options`
  // include an `all_value`, so the user can reset via the reset btn
  // or by re-clicking the same point.
  function wireChartClick(cid, inst){
    var w = WIDGET_META[cid] || {};
    var cfg = w.click_emit_filter;
    if (!cfg) return;
    if (typeof cfg === 'string') cfg = {filter_id: cfg};
    if (!cfg.filter_id) return;
    var src = cfg.value_from || 'name';
    var toggle = cfg.toggle !== false;
    inst.on('click', function(params){
      var v = (src === 'value') ? params.value
            : (src === 'seriesName') ? params.seriesName
            : params.name;
      if (v == null) return;
      if (toggle && filterState[cfg.filter_id] === v){
        var f = (MANIFEST.filters || []).find(function(x){
          return x.id === cfg.filter_id;
        });
        filterState[cfg.filter_id] = (f && f.default != null)
          ? f.default
          : (f && f.type === 'multiSelect' ? [] : '');
      } else {
        filterState[cfg.filter_id] = v;
      }
      // Sync the control DOM (so the user sees it change too)
      try {
        var el = document.getElementById('filter-' + cfg.filter_id);
        if (el) {
          if (el.type === 'checkbox') el.checked = !!filterState[cfg.filter_id];
          else el.value = filterState[cfg.filter_id] == null
            ? '' : filterState[cfg.filter_id];
        } else {
          var radios = document.querySelectorAll('input[name="filter-' + cfg.filter_id + '"]');
          Array.prototype.forEach.call(radios, function(r){
            r.checked = (r.value === String(filterState[cfg.filter_id]));
          });
        }
      } catch (e) {}
      broadcast(cfg.filter_id);
    });
  }

  // ----- chart click -> detail popup -----
  //
  // If a chart widget declares `click_popup`, clicking any data point
  // resolves the corresponding row in the chart's dataset and opens
  // a modal with that row's details. Same configuration grammar as
  // table `row_click` -- simple `popup_fields` mode OR rich
  // `detail.sections[]` mode (stats / markdown / chart / table).
  //
  // When `click_popup` is NOT set but the chart's dataset carries
  // `field_provenance`, we synthesise a minimal default popup
  // (clicked row's mapped fields + provenance footer) so every
  // chart point becomes a click-to-trace surface for free. Set
  // `click_popup: false` to suppress the default explicitly.
  //
  // The row resolver maps ECharts click params -> dataset row across
  // chart types:
  //   line / area / multi_line / bar / scatter / candlestick / bullet
  //                            (no color)  -> rows[params.dataIndex]
  //                            (color set) -> filter color==seriesName,
  //                                             then dataIndex-th row
  //   scatter_multi                        -> grouped fallback (color)
  //   pie / donut / funnel / treemap /
  //   sunburst                             -> match category col ==
  //                                             params.name
  //   heatmap                              -> match (x_cat, y_cat)
  //                                             from params.value[0..1]
  //   calendar_heatmap                      -> match date col ==
  //                                              params.value[0]
  //   histogram / radar / gauge / sankey /
  //   graph / tree / parallel_coords /
  //   boxplot                              -> not row-resolvable;
  //                                              click is a no-op
  //
  // For grouped charts (mapping.color set), series names are
  // humanised by post-build polish but the raw column value is
  // preserved on `series._column`. We read that off the live ECharts
  // option so a humanised legend label like "Investment Grade" still
  // matches a raw cell value of "Investment Grade" (or its
  // pre-humanise form).
  function wireChartClickPopup(cid, inst){
    var w = WIDGET_META[cid] || {};
    var cp = w.click_popup;
    // Explicit opt-out: click_popup:false suppresses the default popup
    // even when the dataset has provenance.
    if (cp === false) return;
    var spec = w.spec || {};
    var dsName = w.dataset_ref || spec.dataset;
    if (!dsName) return;
    var ds = (DATASETS[dsName] && DATASETS[dsName].source) || DATASETS[dsName];
    if (!Array.isArray(ds) || ds.length < 2) return;
    var hasExplicit = (cp && typeof cp === 'object');
    var hasProv = _datasetHasProvenance(dsName);
    if (!hasExplicit && !hasProv && cp !== true) return;
    inst.on('click', function(params){
      if (!params || params.componentType !== 'series') return;
      // When the chart is rewireable, currentDatasets holds the
      // filter-stripped view that matches what's painted on screen;
      // otherwise the original DATASETS entry is what we have. We
      // pass 'chart' so dateRange filters stay view-only and the
      // dataIndex coming back from ECharts indexes the same rows
      // the chart actually rendered.
      var liveDs = currentDatasets[dsName] || ds;
      var filtered = w.dataset_ref
        ? applyFilters(w.dataset_ref, liveDs, 'chart', cid)
        : liveDs;
      var header = filtered[0];
      var rows = filtered.slice(1);
      var row = _resolveClickRow(w, params, inst, header, rows);
      if (!row) return;
      var rc = hasExplicit
        ? cp
        : _buildDefaultChartPopup(w, header, params);
      _openPopupModal(rc, header, row, null, w);
    });
  }

  function _resolveClickRow(w, params, inst, header, rows){
    var spec = w.spec || {};
    var ct = String(spec.chart_type || '').toLowerCase();
    var mapping = spec.mapping || {};

    // Aggregate / non-row chart types: histogram bins, radar/gauge
    // summaries, sankey/graph topology, derived structures. No row
    // identity to resolve.
    if (ct === 'histogram' || ct === 'radar' || ct === 'gauge'
        || ct === 'sankey' || ct === 'graph' || ct === 'tree'
        || ct === 'parallel_coords' || ct === 'boxplot') {
      return null;
    }

    // Category-keyed shapes: match by category cell == params.name.
    if (ct === 'pie' || ct === 'donut' || ct === 'funnel'
        || ct === 'treemap' || ct === 'sunburst') {
      var catCol = mapping.category || mapping.name;
      if (!catCol) return null;
      var ci = header.indexOf(catCol);
      if (ci < 0 || params.name == null) return null;
      for (var i = 0; i < rows.length; i++) {
        if (String(rows[i][ci]) === String(params.name)) return rows[i];
      }
      return null;
    }

    // Heatmap: ECharts emits params.value = [xIdx, yIdx, val] using
    // the same unique-ordered category lists the Python builder
    // produced. Reconstruct those lists from the dataset and match
    // back to the (x_cat, y_cat) row.
    if (ct === 'heatmap') {
      if (!Array.isArray(params.value)) return null;
      var xCol = mapping.x, yCol = mapping.y;
      var xi = header.indexOf(xCol), yi = header.indexOf(yCol);
      if (xi < 0 || yi < 0) return null;
      var xCats = [], yCats = [], seenX = {}, seenY = {};
      for (var i = 0; i < rows.length; i++) {
        var rxk = String(rows[i][xi]);
        var ryk = String(rows[i][yi]);
        if (!seenX[rxk]) { seenX[rxk] = 1; xCats.push(rows[i][xi]); }
        if (!seenY[ryk]) { seenY[ryk] = 1; yCats.push(rows[i][yi]); }
      }
      var xv = xCats[params.value[0]];
      var yv = yCats[params.value[1]];
      if (xv == null || yv == null) return null;
      for (var j = 0; j < rows.length; j++) {
        if (String(rows[j][xi]) === String(xv)
            && String(rows[j][yi]) === String(yv)) return rows[j];
      }
      return null;
    }

    if (ct === 'calendar_heatmap') {
      if (!Array.isArray(params.value)) return null;
      var dCol = mapping.date;
      var di = header.indexOf(dCol);
      if (di < 0) return null;
      for (var i = 0; i < rows.length; i++) {
        if (String(rows[i][di]) === String(params.value[0])) return rows[i];
      }
      return null;
    }

    // Default path: line / area / multi_line / bar / bar_horizontal /
    // scatter / scatter_multi / candlestick / bullet. dataIndex is
    // the position within the (color-grouped) series, so when a
    // color column is set we filter the dataset by series name first.
    var colorCol = mapping.color || mapping.colour;
    if (colorCol) {
      var cci = header.indexOf(colorCol);
      if (cci < 0) return null;
      var rawSeries = null;
      try {
        var opt = inst.getOption();
        var sArr = opt.series || [];
        var s = sArr[params.seriesIndex] || {};
        rawSeries = s._column || s.name || params.seriesName;
      } catch(e){ rawSeries = params.seriesName; }
      if (rawSeries == null) return null;
      var sub = [];
      for (var i = 0; i < rows.length; i++) {
        if (String(rows[i][cci]) === String(rawSeries)) sub.push(rows[i]);
      }
      var didx = params.dataIndex == null ? 0 : params.dataIndex;
      return sub[didx] || null;
    }
    if (params.dataIndex == null) return null;
    return rows[params.dataIndex] || null;
  }
  // rerenderChart(cid, opts?)
  //
  // Re-materializes a chart's option from its compile-time SPEC and
  // pushes it through setOption. Called by every non-dateRange filter
  // change, brush cross-filter, chart-control drawer change, and the
  // filter-reset button. By default we preserve the chart's current
  // in-chart dataZoom window across the rerender so the user's local
  // slider drag survives unrelated filter changes -- e.g. dragging
  // the slider on a rates chart and then flipping a region select
  // shouldn't snap the slider back to the dateRange filter's anchor.
  //
  // The dateRange dropdown path is already handled separately via
  // _dispatchChartDateZoom (see broadcast()), so the capture/restore
  // here doesn't fight that flow -- changing the dateRange dropdown
  // legitimately moves every targeted chart.
  //
  // Callers that DO want a clean reset (the global / per-tab filter
  // reset button) pass {preserveZoom: false}.
  function rerenderChart(cid, opts){
    var rec = CHARTS[cid]; if (!rec) return;
    var preserveZoom = !(opts && opts.preserveZoom === false);
    var savedZoom = null;
    if (preserveZoom){
      try {
        var prevOpt = rec.inst.getOption();
        var prevDz = prevOpt && prevOpt.dataZoom;
        if (prevDz && prevDz.length){
          savedZoom = prevDz.map(function(z){
            if (!z || typeof z !== 'object') return null;
            var win = {};
            if (z.startValue != null) win.startValue = z.startValue;
            if (z.endValue   != null) win.endValue   = z.endValue;
            if (win.startValue == null && z.start != null) win.start = z.start;
            if (win.endValue   == null && z.end   != null) win.end   = z.end;
            return win;
          });
        }
      } catch (e) { savedZoom = null; }
    }
    rec.inst.setOption(reviveFns(materializeOption(cid)), true);
    if (savedZoom){
      try {
        for (var i = 0; i < savedZoom.length; i++){
          var win = savedZoom[i];
          if (!win) continue;
          var hasAbs = ('startValue' in win) || ('endValue' in win);
          var hasPct = ('start' in win)      || ('end' in win);
          if (!hasAbs && !hasPct) continue;
          var act = {type: 'dataZoom', dataZoomIndex: i};
          if (hasAbs){
            if ('startValue' in win) act.startValue = win.startValue;
            if ('endValue'   in win) act.endValue   = win.endValue;
          } else {
            if ('start' in win) act.start = win.start;
            if ('end'   in win) act.end   = win.end;
          }
          rec.inst.dispatchAction(act);
        }
      } catch (e) {}
    }
    var st = chartControlState[cid];
    var w = WIDGET_META[cid] || {};
    var ct = String(((w && w.spec) || {}).chart_type || '').toLowerCase();
    if (ct === 'scatter_studio'){
      _ccRenderStatsStrip(cid, (st && st._lastStudioStats) || null);
    }
  }

  // ----- brush cross-filter -----
  var brushEventActive = false;
  var brushLastSelectionAt = 0;
  function wireBrush(cid, inst){
    var link = (MANIFEST.links || []).find(function(l){
      return l.brush && (l.members || []).some(function(m){ return targetMatch(m, cid); });
    });
    if (!link) return;
    inst.on('brushSelected', function(params){
      var sel = (params.batch && params.batch[0]) || {};
      var areas = sel.areas || [];
      // Connected peers emit trailing empty brushSelected events after the
      // real non-empty selection. They are propagation noise, not a user
      // clicking "clear"; accepting them immediately would undo the filter.
      if (!areas.length && Date.now() - brushLastSelectionAt < 400) return;
      // Connected ECharts instances rebroadcast brush actions to every
      // member. Without a transaction guard, each member re-enters the
      // other's handler and the browser can spin indefinitely.
      if (brushEventActive) return;
      brushEventActive = true;
      if (areas.length) brushLastSelectionAt = Date.now();
      try {
        applyBrush(cid, link, areas);
      } finally {
        // applyBrush also defers setOption to this turn; schedule the reset
        // after those rerenders so brush events emitted by setOption remain
        // inside the same guarded transaction.
        setTimeout(function(){ brushEventActive = false; }, 0);
      }
    });
  }
  function applyBrush(cid, link, areas){
    var members = (link.members || []).flatMap(function(p){
      return Object.keys(WIDGET_META).filter(function(k){
        return targetMatch(p, k) && WIDGET_META[k].widget === 'chart';
      });
    });
    var rerender = [];
    if (!areas.length){
      members.forEach(function(m){
        if (m === cid) return;
        var rec = CHARTS[m]; if (!rec || !rec.datasetRef) return;
        resetDataset(rec.datasetRef); rerender.push(m);
      });
      // brushSelected fires inside ECharts' action-dispatch transaction.
      // Calling setOption synchronously from that callback can make ECharts
      // dispose a component while its brush action still owns it. Defer all
      // linked rerenders until the dispatch stack has unwound.
      setTimeout(function(){
        rerender.forEach(function(m){ rerenderChart(m); });
      }, 0);
      return;
    }
    var xMin, xMax;
    areas.forEach(function(a){
      if (a.coordRange && a.coordRange.length >= 2){
        var cr = a.coordRange;
        var xr = Array.isArray(cr[0]) ? cr[0] : cr;
        if (xMin == null) xMin = xr[0]; else xMin = Math.min(xMin, xr[0]);
        if (xMax == null) xMax = xr[1]; else xMax = Math.max(xMax, xr[1]);
      }
    });
    members.forEach(function(m){
      if (m === cid) return;
      var rec = CHARTS[m]; if (!rec || !rec.datasetRef) return;
      var ds = DATASETS[rec.datasetRef]; if (!ds) return;
      var src = ds.source || ds;
      var header = src[0]; var body = src.slice(1);
      var filt = body.filter(function(r){
        var v = r[0]; var d = (typeof v === 'string') ? Date.parse(v) : +v;
        if (isNaN(d)) return true;
        return d >= xMin && d <= xMax;
      });
      currentDatasets[rec.datasetRef] = [header].concat(filt);
      rerender.push(m);
    });
    setTimeout(function(){
      rerender.forEach(function(m){ rerenderChart(m); });
    }, 0);
  }

  function applyConnects(){
    (MANIFEST.links || []).forEach(function(lk){
      if (!lk.sync) return;
      var group = lk.group;
      var members = (lk.members || []).flatMap(function(p){
        return Object.keys(CHARTS).filter(function(k){ return targetMatch(p, k); });
      });
      members.map(function(m){ return CHARTS[m] && CHARTS[m].inst; })
              .filter(Boolean).forEach(function(i){ i.group = group; });
      try { echarts.connect(group); } catch(e){}
    });
  }

  // ----- tabs -----
  function activateTab(tabId){
    document.querySelectorAll('.tab-btn').forEach(function(b){
      b.classList.toggle('active', b.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-panel').forEach(function(p){
      p.classList.toggle('active', p.id === 'tab-panel-' + tabId);
    });
    // lazy-init any chart tiles in the newly active tab
    var panel = document.getElementById('tab-panel-' + tabId);
    if (panel){
      panel.querySelectorAll('.chart-div').forEach(function(div){
        var id = (div.id || '').replace(/^chart-/, '');
        if (id && !CHARTS[id]) initChart(id);
        else if (id && CHARTS[id]){
          try { CHARTS[id].inst.resize(); } catch(e){}
        }
      });
      applyConnects();
      // Tool widgets in this tab: any chart-output may have been
      // init'd while its host had width 0 (hidden tab). Resize +
      // re-render so it picks up the now-visible width. Triggering
      // _toolRunCompute is the cheapest way to fully refresh the
      // output panel; cheap because the compute is JS in-browser.
      panel.querySelectorAll('[data-tool-id]').forEach(function(tile){
        var twid = tile.getAttribute('data-tool-id');
        if (typeof TOOL_CHARTS !== 'undefined') {
          Object.keys(TOOL_CHARTS).forEach(function(k){
            if (k.indexOf('tool-' + twid + '-out-') === 0) {
              try { TOOL_CHARTS[k].resize(); } catch(e){}
            }
          });
        }
        if (typeof _toolRunCompute === 'function') {
          try { _toolRunCompute(twid); } catch(e){}
        }
      });
    }
    try { localStorage.setItem('echart_dashboard_tab_' + MANIFEST.id, tabId); } catch(e){}
    if (typeof _serializeUrlState === 'function') _serializeUrlState();
  }

  document.querySelectorAll('.tab-btn').forEach(function(b){
    b.addEventListener('click', function(){ activateTab(b.dataset.tab); });
  });

  // ----- filter wiring -----
  function wireFilters(){
    (MANIFEST.filters || []).forEach(function(f){
      // Radio groups have no single DOM node for the filter itself --
      // there are N radio inputs sharing a common name. Everything
      // else is addressable by id.
      if (f.type === 'radio'){
        var inputs = document.querySelectorAll(
          'input[name="filter-' + f.id + '"]');
        if (!inputs.length) return;
        Array.prototype.forEach.call(inputs, function(r){
          r.addEventListener('change', function(){
            if (r.checked){
              filterState[f.id] = r.value;
              broadcast(f.id);
            }
          });
        });
        return;
      }
      var el = document.getElementById('filter-' + f.id); if (!el) return;
      if (f.type === 'multiSelect'){
        el.addEventListener('change', function(){
          filterState[f.id] = Array.from(el.selectedOptions).map(function(o){ return o.value; });
          broadcast(f.id);
        });
      } else if (f.type === 'toggle'){
        el.addEventListener('change', function(){ filterState[f.id] = el.checked; broadcast(f.id); });
      } else if (f.type === 'rule'){
        // Checkbox toggles the rule on/off; the rule itself is static
        // and embedded in the manifest. Default = enabled.
        el.addEventListener('change', function(){
          filterState[f.id] = el.checked;
          broadcast(f.id);
        });
      } else if (f.type === 'numberRange'){
        el.addEventListener('change', function(){
          var parts = el.value.split(',').map(function(s){ return Number(s.trim()); });
          if (parts.length === 2){ filterState[f.id] = parts; broadcast(f.id); }
        });
      } else if (f.type === 'slider'){
        var display = document.getElementById('filter-' + f.id + '-val');
        el.addEventListener('input', function(){
          var n = Number(el.value);
          filterState[f.id] = n;
          if (display) display.textContent = n;
        });
        el.addEventListener('change', function(){ broadcast(f.id); });
      } else if (f.type === 'number'){
        el.addEventListener('change', function(){
          var n = Number(el.value);
          filterState[f.id] = isNaN(n) ? '' : n;
          broadcast(f.id);
        });
      } else if (f.type === 'text'){
        // Debounce text input so broadcasts aren't firing per keystroke.
        var tId = null;
        el.addEventListener('input', function(){
          filterState[f.id] = el.value;
          if (tId) clearTimeout(tId);
          tId = setTimeout(function(){ broadcast(f.id); }, 180);
        });
      } else {
        // dateRange / select / date / default text -- all of these
        // use the native `change` event on the <select> or <input>.
        el.addEventListener('change', function(){
          filterState[f.id] = el.value; broadcast(f.id);
        });
      }
    });
    // Wire every reset button: both the global `#filter-reset` and any
    // per-tab inline reset buttons (marked with `data-filter-reset`).
    // An inline reset resets only the filters whose scope matches its
    // containing tab panel. Global reset clears everything.
    function resetFilters(targetsToReset){
      (MANIFEST.filters || []).forEach(function(f){
        if (targetsToReset && targetsToReset.indexOf(f.id) < 0) return;
        if (f.type === 'rule') {
          filterState[f.id] = f.default == null ? true : !!f.default;
        } else {
          filterState[f.id] = f.default != null ? f.default :
                              (f.type === 'multiSelect' ? [] : '');
        }
        if (f.type === 'radio'){
          var inputs = document.querySelectorAll('input[name="filter-' + f.id + '"]');
          Array.prototype.forEach.call(inputs, function(r){
            r.checked = r.value === String(filterState[f.id]);
          });
          return;
        }
        var el = document.getElementById('filter-' + f.id);
        if (!el) return;
        if (f.type === 'toggle' || f.type === 'rule') el.checked = !!filterState[f.id];
        else if (f.type === 'multiSelect')
          Array.from(el.options).forEach(function(o){ o.selected = (filterState[f.id] || []).indexOf(o.value) >= 0; });
        else if (f.type === 'slider'){
          el.value = filterState[f.id];
          var display = document.getElementById('filter-' + f.id + '-val');
          if (display) display.textContent = filterState[f.id];
        }
        else el.value = filterState[f.id] == null ? '' : filterState[f.id];
      });
      // Parent defaults may change the valid option set of dependent
      // controls. Rebuild them only after every filterState value has been
      // restored, so their DOM options and selected values agree with the
      // reset parent state.
      (MANIFEST.filters || []).forEach(function(f){
        if (f.depends_on && f.options_from) _rebuildFilterOptions(f);
      });
      Object.keys(currentDatasets).forEach(resetDataset);
      // Filter reset is one of the few legitimate paths where in-chart
      // dataZoom windows should snap back to the dateRange anchor --
      // the user is explicitly returning the dashboard to its default
      // state, so the slider should reset along with everything else.
      Object.keys(CHARTS).forEach(function(cid){
        rerenderChart(cid, {preserveZoom: false});
      });
      renderKpis(); renderTables();
    }

    document.querySelectorAll('[data-filter-reset]').forEach(function(btn){
      btn.addEventListener('click', function(){
        var panel = btn.closest('.tab-panel');
        var scopedIds = null;
        if (panel && btn.classList.contains('filter-reset') &&
            panel.classList.contains('tab-panel') && btn.closest('.tab-filter-bar')){
          var pid = (panel.id || '').replace(/^tab-panel-/, '');
          scopedIds = (MANIFEST.filters || [])
            .filter(function(f){ return String(f.scope || '') === 'tab:' + pid; })
            .map(function(f){ return f.id; });
        }
        resetFilters(scopedIds);
      });
    });
  }

  // ----- KPI widgets -----
  //
  // Default behavior: use comma-grouped digits for numbers < 1M
  // (so 2820 -> "2,820" not "3K"); compact K / M / B / T suffix only
  // kicks in at >= 1M. Callers can override via `format`:
  //    "compact"  -> always K/M/B/T abbreviation
  //    "comma"    -> always full digits w/ commas, no abbreviation
  //    "percent"  -> multiply by 100 + "%" suffix
  //    "raw"      -> Number(v).toString() no grouping
  // `decimals` controls fractional digits (defaults vary by magnitude).
  function _commaGroup(intStr){
    // insert thousands separators on the integer portion
    return intStr.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  function formatNumber(v, opts){
    opts = opts || {};
    if (v == null || isNaN(+v)) return String(v);
    var n = +v;
    var prefix = opts.prefix || '';
    var suffix = opts.suffix || '';
    var mode = opts.format || 'auto';
    var abs = Math.abs(n);
    var d = opts.decimals;
    function _apply(formatted){ return prefix + formatted + suffix; }
    if (mode === 'raw'){
      // 'raw' historically meant Number(v).toString() with no
      // formatting at all. Round through toFixed(__capDec) first so
      // even raw mode honours the global decimal cap when v has more
      // fractional digits than allowed (e.g. 0.123456 -> 0.12).
      var rd = __capDec(d, 2);
      return _apply(Number(n.toFixed(rd)).toString());
    }
    if (mode === 'percent'){
      if (d == null) d = 2;
      return _apply((n * 100).toFixed(__capDec(d, 2)) + '%');
    }
    if (mode === 'comma'){
      if (d == null) d = (abs >= 1000 ? 0 : 2);
      var parts = n.toFixed(__capDec(d, 2)).split('.');
      parts[0] = _commaGroup(parts[0]);
      return _apply(parts.join('.'));
    }
    if (mode === 'compact'){
      if (d == null) d = 1;
      var cd = __capDec(d, 1);
      var f;
      if (abs >= 1e12) f = (n/1e12).toFixed(cd) + 'T';
      else if (abs >= 1e9)  f = (n/1e9).toFixed(cd) + 'B';
      else if (abs >= 1e6)  f = (n/1e6).toFixed(cd) + 'M';
      else if (abs >= 1e3)  f = (n/1e3).toFixed(cd) + 'K';
      else                   f = n.toFixed(cd);
      return _apply(f);
    }
    // auto: commas below 1M, compact above
    if (abs >= 1e12) { if (d == null) d = 1;
      return _apply((n/1e12).toFixed(__capDec(d, 1)) + 'T'); }
    if (abs >= 1e9)  { if (d == null) d = 1;
      return _apply((n/1e9).toFixed(__capDec(d, 1)) + 'B'); }
    if (abs >= 1e6)  { if (d == null) d = 1;
      return _apply((n/1e6).toFixed(__capDec(d, 1)) + 'M'); }
    if (d == null) d = (abs >= 1000 ? 0 : 2);
    var parts2 = n.toFixed(__capDec(d, 2)).split('.');
    parts2[0] = _commaGroup(parts2[0]);
    return _apply(parts2.join('.'));
  }

  function resolveAgg(src, agg, col){
    var ds = currentDatasets[src]; if (!ds) return null;
    var header = ds[0]; var idx = header.indexOf(col);
    if (idx < 0) return null;
    var vals = ds.slice(1).map(function(r){ return r[idx]; })
                .filter(function(v){ return typeof v === 'number'; });
    if (!vals.length) return null;
    if (agg === 'latest') return vals[vals.length - 1];
    if (agg === 'first')  return vals[0];
    if (agg === 'sum')    return vals.reduce(function(a,b){ return a+b; }, 0);
    if (agg === 'mean')   return vals.reduce(function(a,b){ return a+b; }, 0) / vals.length;
    if (agg === 'min')    return Math.min.apply(null, vals);
    if (agg === 'max')    return Math.max.apply(null, vals);
    if (agg === 'count')  return vals.length;
    if (agg === 'prev'){
      return vals.length >= 2 ? vals[vals.length - 2] : vals[vals.length - 1];
    }
    return null;
  }
  function resolveSource(src){
    if (!src) return null;
    var parts = String(src).split('.');
    if (parts.length < 3) return null;
    return resolveAgg(parts[0], parts[1], parts.slice(2).join('.'));
  }

  // Compare-period delta: scan the sparkline-backed series for the
  // most recent value, then look back N days (or to first day of
  // year for 'ytd', or one row earlier for 'prev'). Returns
  // {delta, pct, label} or null when the lookup can't resolve a
  // comparison value.
  function _kpiPeriodDelta(w, period){
    if (!w.sparkline_source || !period) return null;
    var sp = String(w.sparkline_source).split('.');
    if (sp.length < 2) return null;
    var dsName = sp[0]; var col = sp.slice(1).join('.');
    var ds = currentDatasets[dsName] || DATASETS[dsName];
    if (ds && ds.source) ds = ds.source;
    if (!Array.isArray(ds) || ds.length < 2) return null;
    var header = ds[0]; var idx = header.indexOf(col);
    if (idx < 0) return null;
    // Find the most likely date column.
    var xIdx = -1;
    for (var i = 0; i < header.length; i++){
      var h = String(header[i]).toLowerCase();
      if (h === 'date' || h === 'time' || h === 'timestamp'
          || h.indexOf('date') >= 0){ xIdx = i; break; }
    }
    var rows = ds.slice(1);
    if (!rows.length) return null;
    var lastIdx = rows.length - 1;
    var lastRow = rows[lastIdx];
    var lastVal = lastRow[idx]; if (lastVal == null || isNaN(+lastVal)) return null;
    lastVal = +lastVal;

    if (period === 'prev'){
      var prevIdx = lastIdx - 1;
      while (prevIdx >= 0 && (rows[prevIdx][idx] == null
        || isNaN(+rows[prevIdx][idx]))) prevIdx--;
      if (prevIdx < 0) return null;
      var pv = +rows[prevIdx][idx];
      return {delta: lastVal - pv,
               pct: pv !== 0 ? (lastVal - pv) / Math.abs(pv) * 100 : null,
               label: 'vs prev'};
    }
    if (xIdx < 0) return null;
    var lastT = (typeof lastRow[xIdx] === 'string')
      ? Date.parse(lastRow[xIdx]) : +lastRow[xIdx];
    if (!isFinite(lastT)) return null;

    var DAY = 86400000;
    var target;
    if (period === 'ytd'){
      var d = new Date(lastT);
      target = Date.UTC(d.getUTCFullYear(), 0, 1);
    } else {
      var dayMap = {'1d': 1, '5d': 5, '1w': 7,
                     '1m': 30, '3m': 91, '6m': 182, '1y': 365};
      var ndays = dayMap[period];
      if (ndays == null) return null;
      target = lastT - ndays * DAY;
    }
    var bestIdx = -1;
    for (var k = lastIdx - 1; k >= 0; k--){
      var t = (typeof rows[k][xIdx] === 'string')
        ? Date.parse(rows[k][xIdx]) : +rows[k][xIdx];
      if (!isFinite(t)) continue;
      if (t <= target){ bestIdx = k; break; }
    }
    if (bestIdx < 0){
      // Use earliest available row when we don't have enough history.
      for (var k2 = 0; k2 <= lastIdx; k2++){
        if (rows[k2][idx] != null && !isNaN(+rows[k2][idx])){
          bestIdx = k2; break;
        }
      }
      if (bestIdx < 0) return null;
    }
    var bv = +rows[bestIdx][idx]; if (isNaN(bv)) return null;
    var labelMap = {'1d': 'vs 1d', '5d': 'vs 5d', '1w': 'vs 1w',
                     '1m': 'vs 1m', '3m': 'vs 3m', '6m': 'vs 6m',
                     '1y': 'vs 1y', 'ytd': 'YTD'};
    return {delta: lastVal - bv,
             pct: bv !== 0 ? (lastVal - bv) / Math.abs(bv) * 100 : null,
             label: labelMap[period] || ('vs ' + period)};
  }
  function renderKpis(){
    Object.keys(WIDGET_META).forEach(function(id){
      var w = WIDGET_META[id]; if (w.widget !== 'kpi') return;
      var el = document.getElementById('kpi-' + id); if (!el) return;
      var kst = (typeof KPI_STATE !== 'undefined') ? (KPI_STATE[id] || {}) : {};
      var value = w.value != null ? w.value : resolveSource(w.source);
      var formatted;
      if (typeof value === 'number'){
        formatted = formatNumber(value, {
          decimals: kst.decimals != null ? kst.decimals : w.decimals,
          format: w.format,
          prefix: w.prefix || '', suffix: w.suffix || ''
        });
      } else {
        formatted = value == null ? '--' : String(value);
      }
      var vNode = el.querySelector('.kpi-value');
      if (vNode) vNode.textContent = formatted;

      // delta: drawer's `comparePeriod` (when set + sparkline-backed)
      // takes priority. Falls back to declarative delta / delta_source
      // when the drawer is on 'auto' or no sparkline is available.
      var dNode = el.querySelector('.kpi-delta');
      if (dNode){
        var deltaVal = null;
        var pct = null;
        var deltaLabel = '';
        if (kst.comparePeriod && kst.comparePeriod !== 'auto'){
          var pd = _kpiPeriodDelta(w, kst.comparePeriod);
          if (pd){
            deltaVal = pd.delta; pct = pd.pct; deltaLabel = pd.label;
          }
        }
        if (deltaVal == null){
          deltaVal = w.delta;
          pct = w.delta_pct;
          deltaLabel = w.delta_label || '';
          var deltaSrc = w.delta_source;
          if (deltaVal == null && deltaSrc){
            var cur = (typeof value === 'number') ? value : resolveSource(w.source);
            var prev = resolveSource(deltaSrc);
            if (typeof cur === 'number' && typeof prev === 'number'){
              deltaVal = cur - prev;
              pct = prev !== 0 ? (deltaVal / Math.abs(prev)) * 100 : null;
            }
          }
        }
        var hide = (kst.showDelta === false);
        if (!hide && deltaVal != null){
          dNode.classList.remove('pos','neg','flat');
          var sign = deltaVal > 0 ? 'pos' : (deltaVal < 0 ? 'neg' : 'flat');
          dNode.classList.add(sign);
          var arrow = deltaVal > 0 ? '\u25B2' : (deltaVal < 0 ? '\u25BC' : '\u25B6');
          var txt = arrow + ' ' + formatNumber(Math.abs(deltaVal), {decimals: w.delta_decimals || 2});
          if (pct != null && !isNaN(pct)) txt += ' (' + (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%)';
          if (deltaLabel) txt += ' ' + deltaLabel;
          dNode.textContent = txt;
          dNode.style.display = 'inline-flex';
        } else {
          dNode.style.display = 'none';
        }
      }

      // sparkline
      var sNode = el.querySelector('.kpi-sparkline');
      if (sNode){
        var hideSpark = (kst.showSparkline === false);
        sNode.style.display = hideSpark ? 'none' : '';
      }
      if (sNode && w.sparkline_source && (kst.showSparkline !== false)){
        var sp2 = String(w.sparkline_source).split('.');
        if (sp2.length >= 2){
          var dsName2 = sp2[0], col2 = sp2.slice(1).join('.');
          var ds2 = currentDatasets[dsName2];
          if (ds2){
            var header2 = ds2[0]; var idx2 = header2.indexOf(col2);
            var rows2 = ds2.slice(1);
            if (idx2 >= 0){
              var data2 = rows2.map(function(r){ return r[idx2]; });
              if (!sNode._inst){
                sNode._inst = echarts.init(sNode);
              }
              sNode._inst.setOption({
                grid:{top:2,bottom:2,left:2,right:2,containLabel:false},
                xAxis:{type:'category',show:false,data:data2.map(function(_,i){return i;})},
                yAxis:{type:'value',show:false,scale:true},
                tooltip:{show:false},
                animation:false,
                series:[{type:'line',data:data2,symbol:'none',
                          smooth:true,lineStyle:{width:1.6},
                          areaStyle:{opacity:0.18}}]
              }, true);
            }
          }
        }
      }
    });
  }

  // ----- table widgets -----
  // Column formatters. Token is the prefix before ':' in the format string;
  // the suffix (if any) is decimals / precision. The precision suffix is
  // always coerced through __capDec so a column declared as "number:5"
  // renders the same as "number:2" -- the global cap wins.
  function formatValue(v, fmt){
    if (v == null || v === '') return '';
    if (fmt == null || fmt === 'text') return String(v);
    var parts = String(fmt).split(':');
    var kind = parts[0];
    var rawPrec = parts.length > 1 ? Number(parts[1]) : 2;
    var prec = __capDec(rawPrec, 2);
    var n = Number(v);
    if (kind === 'integer') {
      if (isNaN(n)) return String(v);
      return Math.round(n).toLocaleString();
    }
    if (kind === 'number')  {
      if (isNaN(n)) return String(v);
      return n.toLocaleString(undefined, {minimumFractionDigits: prec,
                                             maximumFractionDigits: prec});
    }
    if (kind === 'percent') {
      if (isNaN(n)) return String(v);
      // Accept both fractional (0.12) and percent (12) forms
      var pct = Math.abs(n) <= 1 ? n * 100 : n;
      return pct.toFixed(isNaN(rawPrec) ? __capDec(1, 1) : prec) + '%';
    }
    if (kind === 'currency') {
      if (isNaN(n)) return String(v);
      return '$' + n.toLocaleString(undefined, {minimumFractionDigits: prec,
                                                     maximumFractionDigits: prec});
    }
    if (kind === 'bps') {
      if (isNaN(n)) return String(v);
      return n.toFixed(isNaN(rawPrec) ? 0 : prec) + 'bp';
    }
    if (kind === 'signed') {
      if (isNaN(n)) return String(v);
      var sign = n > 0 ? '+' : '';
      return sign + n.toFixed(isNaN(rawPrec) ? __capDec(2, 2) : prec);
    }
    if (kind === 'delta') {
      if (isNaN(n)) return String(v);
      var arrow = n > 0 ? '\u25B2' : n < 0 ? '\u25BC' : '\u25AC';
      return arrow + ' ' + Math.abs(n).toFixed(isNaN(rawPrec) ? __capDec(2, 2) : prec);
    }
    if (kind === 'date') {
      var d = new Date(v);
      if (!isNaN(d.getTime())) return d.toISOString().slice(0, 10);
      return String(v);
    }
    if (kind === 'datetime') {
      var dt = new Date(v);
      if (!isNaN(dt.getTime())) return dt.toISOString().replace('T', ' ').slice(0, 19);
      return String(v);
    }
    if (kind === 'link') {
      var safe = String(v).replace(/"/g, '&quot;');
      return '<a href="' + safe + '" target="_blank">open</a>';
    }
    return String(v);
  }

  function _lerp(a, b, t){ return a + (b - a) * t; }
  function _hex2rgb(hex){
    hex = hex.replace('#', '');
    if (hex.length === 3) hex = hex.split('').map(function(c){ return c+c; }).join('');
    return [parseInt(hex.substr(0,2),16), parseInt(hex.substr(2,2),16), parseInt(hex.substr(4,2),16)];
  }
  function _rgb2hex(r, g, b){
    function hx(x){ return ('0' + Math.round(x).toString(16)).slice(-2); }
    return '#' + hx(r) + hx(g) + hx(b);
  }
  function interpolatePalette(stops, t){
    if (!stops || !stops.length) return null;
    if (stops.length === 1) return stops[0];
    var n = stops.length - 1;
    var pos = Math.max(0, Math.min(1, t)) * n;
    var lo = Math.floor(pos), hi = Math.min(n, lo + 1);
    var frac = pos - lo;
    var a = _hex2rgb(stops[lo]), b = _hex2rgb(stops[hi]);
    return _rgb2hex(_lerp(a[0], b[0], frac), _lerp(a[1], b[1], frac), _lerp(a[2], b[2], frac));
  }
  function colorForScale(v, scale){
    var n = Number(v);
    if (isNaN(n) || !scale) return null;
    var pal = scale.palette ? PAYLOAD.palettes[scale.palette] : null;
    var resolved = resolvedThemeForChart(null);
    var colors = pal && pal.colors;
    if (!colors) colors = scale.kind === 'diverging'
      ? resolved.diverging : resolved.sequential;
    if (!colors || !colors.length) return null;
    var lo = scale.min != null ? scale.min : 0;
    var hi = scale.max != null ? scale.max : 1;
    var span = hi - lo || 1;
    var t = (n - lo) / span;
    return interpolatePalette(colors, t);
  }
  function conditionalStyle(v, rules){
    if (!rules) return null;
    for (var i = 0; i < rules.length; i++){
      var r = rules[i];
      if (cmpOp(r.op || '==', v, r.value)){
        return r;
      }
    }
    return null;
  }
  // Table per-widget state: sort column index (null = original order),
  // sort direction (1 = asc, -1 = desc), search string. The drawer
  // adds: hidden{} (col-idx -> bool), density ('regular' | 'compact'),
  // freezeFirst (bool), decimals (null = use compile-time format).
  var TABLE_STATE = {};
  function _isTableWidget(w){
    return !!w && (w.widget === 'table' || w.widget === 'data_grid');
  }
  function tableState(id){
    if (!TABLE_STATE[id]){
      TABLE_STATE[id] = {
        sortCol: null, sortDir: 1, search: '',
        hidden: {}, density: null, freezeFirst: false, decimals: null,
        visibleRows: null, virtualKey: null, scrollTop: 0,
      };
    }
    return TABLE_STATE[id];
  }

  function _rowMatchesSearch(row, needle){
    if (!needle) return true;
    var n = String(needle).toLowerCase();
    for (var i = 0; i < row.length; i++){
      var c = row[i]; if (c == null) continue;
      if (String(c).toLowerCase().indexOf(n) >= 0) return true;
    }
    return false;
  }

  // ----- pivot widget -----
  // Per-pivot state: row dim, col dim, value column, agg name. Keyed
  // by widget id. Initialized from the manifest's *_default fields.
  var PIVOT_STATE = {};

  function _pivotState(wid){
    if (!PIVOT_STATE[wid]){
      var w = WIDGET_META[wid] || {};
      PIVOT_STATE[wid] = {
        row: w.row_default || (w.row_dim_columns || [])[0],
        col: w.col_default || (w.col_dim_columns || [])[0],
        val: w.value_default || (w.value_columns || [])[0],
        agg: w.agg_default || 'mean',
      };
    }
    return PIVOT_STATE[wid];
  }

  function _aggReduce(values, agg){
    var nums = values.filter(function(v){
      return v != null && !isNaN(v);
    }).map(Number);
    if (!nums.length) return null;
    if (agg === 'mean') return nums.reduce(function(a, b){ return a + b; }, 0) / nums.length;
    if (agg === 'sum')  return nums.reduce(function(a, b){ return a + b; }, 0);
    if (agg === 'min')  return Math.min.apply(null, nums);
    if (agg === 'max')  return Math.max.apply(null, nums);
    if (agg === 'count') return nums.length;
    if (agg === 'median'){
      var sorted = nums.slice().sort(function(a, b){ return a - b; });
      var m = Math.floor(sorted.length / 2);
      return sorted.length % 2 ? sorted[m] : (sorted[m-1] + sorted[m]) / 2;
    }
    return null;
  }

  function _pivotFmt(v, decimals){
    if (v == null || isNaN(v)) return '--';
    var d = (decimals == null) ? 2 : decimals;
    return Number(v).toFixed(__capDec(d, 2));
  }

  function _pivotColorScale(value, min, max, scale){
    if (value == null || isNaN(value)) return null;
    var cfg = (scale && typeof scale === 'object') ? scale : {};
    var kind = (typeof scale === 'string' ? scale : cfg.kind || cfg.type || 'auto');
    var lo = cfg.min != null ? Number(cfg.min) : Number(min);
    var hi = cfg.max != null ? Number(cfg.max) : Number(max);
    var resolved = resolvedThemeForChart(null);
    var palette = null;
    if (cfg.palette && PAYLOAD.palettes[cfg.palette]){
      palette = PAYLOAD.palettes[cfg.palette].colors;
    }
    var diverging = kind === 'diverging' ||
      (kind === 'auto' && lo < 0 && hi > 0);
    if (!palette) palette = diverging
      ? resolved.diverging : resolved.sequential;
    if (!palette || !palette.length) return null;
    var t;
    if (diverging){
      var absMax = Math.max(Math.abs(lo), Math.abs(hi)) || 1;
      t = (Number(value) + absMax) / (2 * absMax);
    } else {
      t = (Number(value) - lo) / ((hi - lo) || 1);
    }
    return interpolatePalette(palette, Math.max(0, Math.min(1, t)));
  }

  function _renderPivot(id){
    var w = WIDGET_META[id]; if (!w || w.widget !== 'pivot') return;
    var bodyEl = document.getElementById('pivot-' + id);
    var ctrlEl = document.getElementById('pivot-controls-' + id);
    if (!bodyEl || !ctrlEl) return;
    var ds = w.dataset_ref ? currentDatasets[w.dataset_ref] : null;
    if (!ds || !ds.length){
      bodyEl.innerHTML = '<div class="table-empty">No rows.</div>';
      return;
    }
    var st = _pivotState(id);
    // Render the controls bar (idempotent: rebuild every render so the
    // dropdowns stay in sync with state changes from URL state restore).
    var aggOpts = w.agg_options || ['mean', 'sum', 'median', 'min',
                                       'max', 'count'];
    function _ddl(label, options, current, role){
      var html = '<label>' + label;
      html += '<select data-pivot-id="' + id +
        '" data-pivot-role="' + role + '">';
      options.forEach(function(o){
        var sel = (String(o) === String(current)) ? ' selected' : '';
        html += '<option value="' + _he(o) + '"' + sel + '>' +
          _he(o) + '</option>';
      });
      html += '</select></label>';
      return html;
    }
    var ctrlHtml = '';
    ctrlHtml += _ddl('Rows: ', w.row_dim_columns || [], st.row, 'row');
    ctrlHtml += _ddl('Columns: ', w.col_dim_columns || [], st.col, 'col');
    ctrlHtml += _ddl('Values: ', w.value_columns || [], st.val, 'val');
    ctrlHtml += _ddl('Agg: ', aggOpts, st.agg, 'agg');
    ctrlEl.innerHTML = ctrlHtml;

    var header = ds[0];
    var allBody = applyFilters(w.dataset_ref, ds, 'pivot', id).slice(1);
    var rIdx = header.indexOf(st.row);
    var cIdx = header.indexOf(st.col);
    var vIdx = header.indexOf(st.val);
    if (rIdx < 0 || cIdx < 0 || vIdx < 0){
      bodyEl.innerHTML = '<div class="table-empty">Pivot column missing in dataset.</div>';
    } else {
      // Aggregate by (row, col)
      var rowVals = []; var rowSeen = {};
      var colVals = []; var colSeen = {};
      var bucket = {};
      for (var i = 0; i < allBody.length; i++){
        var r = allBody[i];
        var rv = r[rIdx], cv = r[cIdx], vv = r[vIdx];
        if (rv == null || cv == null) continue;
        var rk = String(rv), ck = String(cv);
        if (!rowSeen[rk]){ rowSeen[rk] = true; rowVals.push(rv); }
        if (!colSeen[ck]){ colSeen[ck] = true; colVals.push(cv); }
        var key = rk + '|' + ck;
        (bucket[key] = bucket[key] || []).push(vv);
      }
      // Sort rows / cols (numeric if all numeric, else lexical)
      function _sortVals(vs){
        var allNumeric = vs.every(function(x){
          return typeof x === 'number' || !isNaN(parseFloat(x));
        });
        if (allNumeric) vs.sort(function(a, b){ return parseFloat(a) - parseFloat(b); });
        else vs.sort(function(a, b){ return String(a).localeCompare(String(b)); });
        return vs;
      }
      _sortVals(rowVals); _sortVals(colVals);

      // Compute cell values
      var cells = {};
      var allNums = [];
      rowVals.forEach(function(rv){
        var rk = String(rv);
        cells[rk] = {};
        colVals.forEach(function(cv){
          var ck = String(cv);
          var val = _aggReduce(bucket[rk + '|' + ck] || [], st.agg);
          cells[rk][ck] = val;
          if (val != null && !isNaN(val)) allNums.push(val);
        });
      });
      // Row totals (re-aggregated across cols)
      var showTotals = w.show_totals !== false;
      var rowTotals = {};
      rowVals.forEach(function(rv){
        var rk = String(rv);
        var allRowVals = [];
        colVals.forEach(function(cv){
          var ck = String(cv);
          (bucket[rk + '|' + ck] || []).forEach(function(x){ allRowVals.push(x); });
        });
        rowTotals[rk] = _aggReduce(allRowVals, st.agg);
      });
      var colTotals = {};
      colVals.forEach(function(cv){
        var ck = String(cv);
        var allColVals = [];
        rowVals.forEach(function(rv){
          var rk = String(rv);
          (bucket[rk + '|' + ck] || []).forEach(function(x){ allColVals.push(x); });
        });
        colTotals[ck] = _aggReduce(allColVals, st.agg);
      });
      var grand = _aggReduce(
        [].concat.apply([], Object.keys(bucket).map(function(k){
          return bucket[k];
        })), st.agg
      );

      var minV = allNums.length ? Math.min.apply(null, allNums) : 0;
      var maxV = allNums.length ? Math.max.apply(null, allNums) : 0;
      var colorScale = w.color_scale || null;
      if (colorScale === 'auto'){
        colorScale = (minV < 0 && maxV > 0) ? 'diverging' : 'sequential';
      }
      var decimals = w.decimals != null ? w.decimals : 2;

      // Build HTML
      var html = '<table>';
      html += '<thead><tr>';
      html += '<th class="pivot-row-header">' + _he(st.row) +
              ' \\ ' + _he(st.col) + '</th>';
      colVals.forEach(function(cv){
        html += '<th>' + _he(cv) + '</th>';
      });
      if (showTotals){
        html += '<th class="pivot-total-col">Total (' + st.agg + ')</th>';
      }
      html += '</tr></thead><tbody>';
      rowVals.forEach(function(rv){
        var rk = String(rv);
        html += '<tr>';
        html += '<td class="pivot-row-label">' + _he(rv) + '</td>';
        colVals.forEach(function(cv){
          var ck = String(cv);
          var v = cells[rk][ck];
          var bg = (colorScale && v != null)
            ? _pivotColorScale(v, minV, maxV, colorScale) : null;
          var styleAttr = bg ? ' style="background:' + bg + '"' : '';
          html += '<td class="pivot-cell"' + styleAttr + '>' +
            _pivotFmt(v, decimals) + '</td>';
        });
        if (showTotals){
          html += '<td class="pivot-cell pivot-total-col">' +
            _pivotFmt(rowTotals[rk], decimals) + '</td>';
        }
        html += '</tr>';
      });
      if (showTotals){
        html += '<tr class="pivot-total">';
        html += '<td class="pivot-row-label">Total (' + st.agg + ')</td>';
        colVals.forEach(function(cv){
          var ck = String(cv);
          html += '<td class="pivot-cell">' +
            _pivotFmt(colTotals[ck], decimals) + '</td>';
        });
        if (showTotals){
          html += '<td class="pivot-cell pivot-total-col">' +
            _pivotFmt(grand, decimals) + '</td>';
        }
        html += '</tr>';
      }
      html += '</tbody></table>';
      bodyEl.innerHTML = html;
    }
    // Wire dropdowns
    ctrlEl.querySelectorAll('select').forEach(function(sel){
      sel.addEventListener('change', function(){
        var role = sel.getAttribute('data-pivot-role') || '';
        if (role === 'row') st.row = sel.value;
        if (role === 'col') st.col = sel.value;
        if (role === 'val') st.val = sel.value;
        if (role === 'agg') st.agg = sel.value;
        _renderPivot(id);
        if (typeof _serializeUrlState === 'function') _serializeUrlState();
      });
    });
  }

  function renderPivots(){
    Object.keys(WIDGET_META).forEach(function(id){
      var w = WIDGET_META[id];
      if (w && w.widget === 'pivot') _renderPivot(id);
    });
  }
  window.renderPivots = renderPivots;

  // ----- stat_grid client-render (HYBRID) -----
  //
  // The server BAKES stat values into the HTML at compile time
  // (graceful degradation for file://, JS-off, init errors). This
  // function OVERWRITES those server-baked values from currentDatasets
  // whenever it runs. Called from:
  //   - applyLiveData() — fresh cron-driven data lands; values update
  //     without a page reload
  //   - broadcast() (filter change) — wired for future filter-aware
  //     resolveSource; today resolveSource reads unfiltered data so the
  //     re-render is a no-op when only filters changed
  // The widget shape is preserved verbatim; only the `.stat-value`
  // span text is overwritten. Stats without a `source` (author-baked
  // value) are left alone.
  function renderStatGrids(){
    Object.keys(WIDGET_META).forEach(function(wid){
      var w = WIDGET_META[wid];
      if (!w || w.widget !== 'stat_grid') return;
      var container = document.getElementById('stat-grid-' + wid);
      if (!container) return;
      var stats = w.stats; if (!Array.isArray(stats)) return;
      var cells = container.querySelectorAll('.stat-cell');
      for (var i = 0; i < stats.length && i < cells.length; i++){
        var st = stats[i] || {};
        if (!st.source) continue;  // author-baked value: leave alone
        var resolved = resolveSource(st.source);
        var formatted;
        if (typeof resolved === 'number'){
          formatted = formatNumber(resolved, {
            decimals: st.decimals,
            format:   st.format,
            prefix:   st.prefix || '',
            suffix:   st.suffix || '',
          });
        } else if (resolved == null){
          // Source didn't resolve (column missing, empty dataset, etc.).
          // Leave the server-baked value in place rather than blanking
          // out — graceful degradation: stale-but-visible beats blank.
          continue;
        } else {
          formatted = String(resolved);
        }
        var vNode = cells[i].querySelector('.stat-value');
        if (!vNode) continue;
        // Preserve the trend arrow span (`.stat-trend`) when overwriting
        // the value text — it's a sibling element inside `.stat-value`
        // that the server emitted.
        var trendNode = vNode.querySelector('.stat-trend');
        var trendHTML = trendNode ? trendNode.outerHTML : '';
        vNode.innerHTML = trendHTML + formatted;
      }
    });
  }
  window.renderStatGrids = renderStatGrids;
  // First client-render pass: server values become client-resolved on
  // initial load too, so the value pipeline is exercised every time
  // the dashboard mounts (smoke-checks the resolveSource path).
  try { renderStatGrids(); } catch(e){ console.warn('[stat_grid] initial render failed:', e); }

  function renderTables(){
    Object.keys(WIDGET_META).forEach(function(id){
      var w = WIDGET_META[id]; if (!_isTableWidget(w)) return;
      var el = document.getElementById('table-' + id); if (!el) return;

      // The whole table is rebuilt via innerHTML below, which destroys
      // the search <input> and any focus/selection on it. Capture caret
      // state up-front so we can restore it after the rebuild and the
      // user can keep typing without their cursor being kicked out.
      var caret = null;
      var prevSearch = el.querySelector('.table-search');
      var prevScroller = el.querySelector('.table-virtual-scroll');
      if (prevScroller) tableState(id).scrollTop = prevScroller.scrollTop;
      if (prevSearch && document.activeElement === prevSearch){
        caret = {
          start: prevSearch.selectionStart,
          end:   prevSearch.selectionEnd,
          dir:   prevSearch.selectionDirection || 'none'
        };
      }

      var ds = w.dataset_ref ? currentDatasets[w.dataset_ref] : null;
      if (!ds || !ds.length) {
        el.innerHTML = '<div class="table-empty">' +
          (w.empty_message || 'No rows.') + '</div>';
        return;
      }
      var header = ds[0];
      var allBody = applyFilters(w.dataset_ref, ds, 'table', id).slice(1);
      var ts = tableState(id);

      // Search filter
      if (ts.search){
        allBody = allBody.filter(function(r){ return _rowMatchesSearch(r, ts.search); });
      }

      // Column config: if not supplied, auto-generate from header.
      var allCols = w.columns;
      if (!allCols || !allCols.length){
        allCols = header.map(function(h){ return {field: h, label: h}; });
      }
      // Drawer can hide columns by index (TABLE_STATE[id].hidden[i] = true).
      // We split into "all cols + visibility map" so sort indexes stay
      // stable even when columns are hidden, then filter to `cols`.
      ts.hidden = ts.hidden || {};
      var cols = allCols.filter(function(_, i){ return !ts.hidden[i]; });
      var visIdxMap = [];
      allCols.forEach(function(_, i){ if (!ts.hidden[i]) visIdxMap.push(i); });
      var colIndexes = cols.map(function(c){ return header.indexOf(c.field); });
      var colCompare = function(ci, dir){
        return function(a, b){
          var av = a[ci], bv = b[ci];
          if (av == null && bv == null) return 0;
          if (av == null) return 1;
          if (bv == null) return -1;
          var an = Number(av), bn = Number(bv);
          if (!isNaN(an) && !isNaN(bn)) return (an - bn) * dir;
          return String(av).localeCompare(String(bv)) * dir;
        };
      };
      // ts.sortCol is an index into allCols (drawer + header click both
      // use the full list). Translate to header column for comparison.
      if (ts.sortCol != null && allCols[ts.sortCol]){
        var srcIdx = header.indexOf(allCols[ts.sortCol].field);
        if (srcIdx >= 0){
          allBody = allBody.slice().sort(colCompare(srcIdx, ts.sortDir));
        }
      }

      var maxRows = w.max_rows || (w.widget === 'data_grid' ? 5000 : 100);
      var virtualized = w.virtualized === true || w.widget === 'data_grid';
      var pageSize = Math.max(20, Number(w.page_size || 100));
      var virtualKey = JSON.stringify(filterState) + '|' + ts.search + '|' +
        String(ts.sortCol) + '|' + String(ts.sortDir);
      if (ts.virtualKey !== virtualKey){
        ts.virtualKey = virtualKey;
        ts.visibleRows = pageSize;
        ts.scrollTop = 0;
      }
      var renderRows = virtualized
        ? Math.min(
            maxRows,
            DASHBOARD_PRINTING ? maxRows : (ts.visibleRows || pageSize)
          )
        : maxRows;
      var visible = allBody.slice(0, renderRows);
      var allRowsShown = allBody.length <= renderRows;

      // Per-table density / decimals overrides (drawer). Density on the
      // widget falls through if the user hasn't picked one; "compact"
      // wins. Decimals overrides any column.format that's a number/
      // integer/percent/currency/bps/signed/delta -- formatting falls
      // back to the column's own format when ts.decimals is null.
      var density = ts.density || (w.row_height === 'compact'
        ? 'compact' : 'regular');
      var decOverride = (ts.decimals == null) ? null : Number(ts.decimals);

      var html = '';
      var downloadable = w.downloadable !== false;
      if (w.searchable || downloadable){
        html += '<div class="table-toolbar">';
        if (w.searchable){
          html += '<input class="table-search" data-tid="' + id +
            '" placeholder="Search..." value="' + _he(ts.search) + '"/>';
        }
        if (w.searchable){
          html += '<span class="table-count">' + allBody.length +
            (allRowsShown ? '' : ' (showing ' + visible.length + ')') +
            ' rows</span>';
        }
        if (downloadable){
          html += '<button class="table-xlsx-btn" data-tid="' + id +
            '" title="Download this table as Excel">XLSX</button>';
        }
        html += '</div>';
      }
      // Default popup auto-fires when the table dataset carries
      // field_provenance and no explicit row_click is set; suppress
      // with `row_click: false`. The clickable visual cue mirrors
      // either explicit row_click dict or a default popup we'll wire.
      var rcExplicit = w.row_click && typeof w.row_click === 'object';
      var rcOptOut = w.row_click === false;
      var rcAuto = !rcExplicit && !rcOptOut
        && w.dataset_ref && _datasetHasProvenance(w.dataset_ref);
      var rowClickActive = !!(rcExplicit || rcAuto);
      if (virtualized){
        html += '<div class="table-virtual-scroll" data-virtual-table="' + id +
          '" style="max-height:' + Number(w.h_px || 560) + 'px">';
      }
      html += '<table class="data-table' +
              (density === 'compact' ? ' compact' : '') +
              (ts.freezeFirst ? ' freeze-first-col' : '') +
              (rowClickActive ? ' clickable' : '') +
              '"><thead><tr>';

      cols.forEach(function(c, vi){
        var ci = visIdxMap[vi]; // index into allCols (drawer-stable)
        var lbl = c.label != null ? c.label : c.field;
        var align = c.align || (c.format && /^(number|integer|percent|currency|bps|signed|delta)/.test(c.format) ? 'right' : 'left');
        var tip = c.tooltip ? ' title="' + _he(c.tooltip) + '"' : '';
        var sortable = c.sortable !== false && w.sortable !== false;
        var arrow = '';
        if (sortable && ts.sortCol === ci){
          arrow = ts.sortDir === 1 ? ' \u25B4' : ' \u25BE';
        }
        html += '<th style="text-align:' + align + '"' +
                (sortable ? ' class="sortable" data-col="' + ci + '" data-tid="' + id + '"' : '') +
                tip + '>' + _he(lbl) + arrow + '</th>';
      });
      html += '</tr></thead><tbody>';

      // Row highlighting: match a list of rules `{field, op, value,
      // class}` against each row. First matching rule wins. `class`
      // must be one of: 'pos', 'neg', 'muted', 'warn', 'info', or
      // a dashed bucket name. The row gets a `.row-hl-<class>` CSS
      // class (styles below).
      function _pickRowHL(row) {
        var rules = w.row_highlight || [];
        for (var i = 0; i < rules.length; i++){
          var r = rules[i];
          var fi = header.indexOf(r.field);
          if (fi < 0) continue;
          if (cmpOp(r.op || '==', row[fi], r.value)){
            return r.class || r.cls || r.className || 'info';
          }
        }
        return null;
      }

      // When the drawer's "Decimals" override is set, splice it into
      // the column format string -- e.g. "number:2" + override(0) ->
      // "number:0", "percent:1" + override(3) -> "percent:3", etc.
      // Non-numeric formats (text/date/datetime/link) are left alone.
      function _applyDecOverride(fmt){
        if (decOverride == null) return fmt;
        if (!fmt) return 'number:' + decOverride;
        var parts = String(fmt).split(':');
        var kind = parts[0];
        if (/^(number|integer|percent|currency|bps|signed|delta)$/.test(kind)){
          return kind + ':' + decOverride;
        }
        return fmt;
      }
      // Pre-compute column extents for in-cell bars / heatmaps so we
      // can normalize against the visible-row range without recomputing
      // per cell.
      var colExtent = {};
      cols.forEach(function(c, vi){
        if (c.in_cell !== 'bar' && c.in_cell !== 'heat') return;
        var hi = colIndexes[vi];
        if (hi < 0) return;
        var nums = [];
        for (var ri = 0; ri < visible.length; ri++){
          var x = visible[ri][hi];
          var n = (x == null || x === '') ? null : Number(x);
          if (n != null && !isNaN(n)) nums.push(n);
        }
        if (!nums.length) return;
        var mn = Math.min.apply(null, nums);
        var mx = Math.max.apply(null, nums);
        colExtent[vi] = {min: mn, max: mx,
                          absMax: Math.max(Math.abs(mn), Math.abs(mx))};
      });

      // Pre-build sparkline lookup tables (in-cell sparkline reads from
      // a sibling dataset, filtered by a column on this row).
      var sparkLookup = {};
      cols.forEach(function(c, vi){
        if (c.in_cell !== 'sparkline') return;
        var fromDs = c.from_dataset || c.dataset;
        var rowKey = c.row_key || c.field;
        var filterField = c.filter_field || rowKey;
        var valueCol = c.value || c.spark_field || rowKey;
        if (!fromDs || !rowKey || !valueCol) return;
        var src = currentDatasets[fromDs] || (DATASETS[fromDs] &&
          (DATASETS[fromDs].source || DATASETS[fromDs]));
        if (!src || !src.length) return;
        var srcHeader = src[0];
        var fIdx = srcHeader.indexOf(filterField);
        var vIdx = srcHeader.indexOf(valueCol);
        if (fIdx < 0 || vIdx < 0) return;
        var byKey = {};
        for (var r = 1; r < src.length; r++){
          var row = src[r] || [];
          var k = row[fIdx];
          if (k == null) continue;
          var kk = String(k);
          if (!byKey[kk]) byKey[kk] = [];
          var nv = (row[vIdx] == null || row[vIdx] === '')
            ? null : Number(row[vIdx]);
          byKey[kk].push(nv);
        }
        sparkLookup[vi] = {byKey: byKey, rowKeyIdx: header.indexOf(rowKey)};
      });

      function _inCellBarHtml(v, ext, c){
        if (v == null || isNaN(v) || !ext) return '';
        var nv = Number(v);
        var width = 0;
        var pos = (nv >= 0);
        // For data that crosses zero, anchor at 0 and render in two
        // directions. Otherwise normalize against [min, max].
        if (ext.min < 0 && ext.max > 0){
          var span = ext.absMax || 1;
          width = Math.min(100, Math.abs(nv) / span * 100);
        } else {
          var lo = ext.min, hi = ext.max;
          var range = hi - lo || 1;
          width = ((nv - lo) / range) * 100;
          width = Math.max(2, Math.min(100, width));
          pos = true;  // single-direction bars are always 'positive'
        }
        var fillColor = pos
          ? (c.bar_color_pos || 'rgba(47, 133, 90, 0.40)')
          : (c.bar_color_neg || 'rgba(197, 48, 48, 0.40)');
        var leftStyle = '';
        if (ext.min < 0 && ext.max > 0){
          // Anchor to a center line at 50%; positive grows right, negative grows left
          if (pos){
            leftStyle = 'left: 50%; width: ' + (width / 2) + '%;';
          } else {
            leftStyle = 'right: 50%; width: ' + (width / 2) + '%;';
          }
        } else {
          leftStyle = 'left: 0; width: ' + width + '%;';
        }
        return '<div class="in-cell-bar"><div class="in-cell-bar-fill"' +
          ' style="' + leftStyle + ' background:' + fillColor + '"></div></div>';
      }

      function _inCellSparklineHtml(row, c, vi){
        var look = sparkLookup[vi]; if (!look) return '';
        var rowKey = (look.rowKeyIdx >= 0) ? row[look.rowKeyIdx] : null;
        if (rowKey == null) return '';
        var arr = look.byKey[String(rowKey)];
        if (!arr || arr.length < 2) return '';
        var nums = arr.filter(function(n){
          return n != null && !isNaN(n);
        });
        if (nums.length < 2) return '';
        var mn = Math.min.apply(null, nums), mx = Math.max.apply(null, nums);
        var range = mx - mn || 1;
        var W = 80, H = 16;
        var pts = arr.map(function(n, i){
          if (n == null || isNaN(n)) return null;
          var x = (i / (arr.length - 1)) * W;
          var y = H - ((n - mn) / range) * H;
          return x.toFixed(1) + ',' + y.toFixed(1);
        }).filter(Boolean);
        var path = pts.join(' ');
        var color = c.spark_color || '#003359';
        var lastN = nums[nums.length - 1], firstN = nums[0];
        var lastColor = (lastN >= firstN)
          ? (c.spark_color_pos || '#2F855A')
          : (c.spark_color_neg || '#C53030');
        var lastX = ((arr.length - 1) / (arr.length - 1)) * W;
        var lastY = H - ((lastN - mn) / range) * H;
        return '<svg class="in-cell-spark" width="' + W +
          '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H +
          '" xmlns="http://www.w3.org/2000/svg">' +
          '<polyline points="' + path + '" fill="none" stroke="' +
          color + '" stroke-width="1.2" stroke-linejoin="round" ' +
          'stroke-linecap="round"></polyline>' +
          '<circle cx="' + lastX.toFixed(1) + '" cy="' + lastY.toFixed(1) +
          '" r="1.6" fill="' + lastColor + '"></circle></svg>';
      }

      visible.forEach(function(row, ri){
        var hlClass = _pickRowHL(row);
        var rowCls = hlClass ? ' class="row-hl-' + hlClass + '"' : '';
        html += '<tr' + rowCls + ' data-row-idx="' + ri + '" data-tid="' + id + '">';
        cols.forEach(function(c, vi){
          var hi = colIndexes[vi];
          var v = hi >= 0 ? row[hi] : null;
          var txt = formatValue(v, _applyDecOverride(c.format));
          var align = c.align || (c.format && /^(number|integer|percent|currency|bps|signed|delta)/.test(c.format) ? 'right' : 'left');
          var styleParts = ['text-align:' + align];
          // Conditional formatting
          var cs = conditionalStyle(v, c.conditional);
          if (cs){
            if (cs.background) styleParts.push('background:' + cs.background);
            if (cs.color)      styleParts.push('color:' + cs.color);
            if (cs.bold)       styleParts.push('font-weight:600');
          }
          // Color scale (continuous heatmap)
          if (c.color_scale){
            var bg = colorForScale(v, c.color_scale);
            if (bg){
              styleParts.push('background:' + bg);
              // Pick black or white text for contrast
              var rgb = _hex2rgb(bg);
              var lum = 0.299*rgb[0] + 0.587*rgb[1] + 0.114*rgb[2];
              styleParts.push('color:' + (lum > 128 ? '#1a1a1a' : '#ffffff'));
            }
          }
          var tip = c.tooltip ? ' title="' + _he(c.tooltip) + '"' : '';
          // In-cell visualizations
          var cellInner = txt;
          if (c.in_cell === 'bar'){
            var ext = colExtent[vi];
            var bar = _inCellBarHtml(v, ext, c);
            // Wrap value text + bar so the number stays readable
            cellInner = '<div class="in-cell-wrap">' + bar +
              '<span class="in-cell-text">' + txt + '</span></div>';
          } else if (c.in_cell === 'sparkline'){
            var spark = _inCellSparklineHtml(row, c, vi);
            // sparkline-only or sparkline + text
            if (c.show_text === false){
              cellInner = '<div class="in-cell-wrap">' + spark + '</div>';
            } else {
              cellInner = '<div class="in-cell-wrap">' +
                '<span class="in-cell-text">' + txt + '</span>' +
                spark + '</div>';
            }
          }
          html += '<td style="' + styleParts.join(';') + '"' + tip + '>' +
            cellInner + '</td>';
        });
        html += '</tr>';
      });
      html += '</tbody></table>';
      if (virtualized){
        html += '<div class="table-virtual-status">' +
          (allRowsShown
            ? 'All ' + visible.length + ' rows loaded'
            : 'Showing ' + visible.length + ' of ' +
              Math.min(allBody.length, maxRows) + ' rows; scroll to load more') +
          '</div></div>';
      }
      el.innerHTML = html;

      // Wire search
      var searchEl = el.querySelector('.table-search');
      if (searchEl){
        if (caret){
          searchEl.focus();
          try { searchEl.setSelectionRange(caret.start, caret.end, caret.dir); }
          catch(e){}
        }
        var tId = null;
        searchEl.addEventListener('input', function(){
          ts.search = searchEl.value;
          if (tId) clearTimeout(tId);
          tId = setTimeout(function(){ renderTables(); }, 160);
        });
      }
      // Wire per-table XLSX button
      var xlsxEl = el.querySelector('.table-xlsx-btn');
      if (xlsxEl){
        xlsxEl.addEventListener('click', function(){
          if (typeof window.downloadOneTableXlsx === 'function'){
            window.downloadOneTableXlsx(id);
          }
        });
      }
      var virtualEl = el.querySelector('.table-virtual-scroll');
      if (virtualEl){
        virtualEl.scrollTop = ts.scrollTop || 0;
        virtualEl.addEventListener('scroll', function(){
          ts.scrollTop = virtualEl.scrollTop;
          if (virtualEl.scrollTop + virtualEl.clientHeight >=
              virtualEl.scrollHeight - 80 && !allRowsShown){
            ts.visibleRows = Math.min(
              maxRows, (ts.visibleRows || pageSize) + pageSize);
            renderTables();
          }
        });
      }
      // Wire header-click sort
      el.querySelectorAll('th.sortable').forEach(function(th){
        th.addEventListener('click', function(){
          var ci = Number(th.dataset.col);
          if (ts.sortCol === ci) ts.sortDir = -ts.sortDir;
          else { ts.sortCol = ci; ts.sortDir = 1; }
          ts.visibleRows = pageSize;
          ts.scrollTop = 0;
          renderTables();
        });
      });
      // Wire row click -> popup modal. openRowModal picks the right
      // popup config (explicit row_click dict OR auto default
      // built from field_provenance).
      if (rowClickActive){
        el.querySelectorAll('tbody tr').forEach(function(tr){
          tr.addEventListener('click', function(){
            var idx = Number(tr.dataset.rowIdx);
            var row = visible[idx];
            openRowModal(w, header, row, cols);
          });
        });
      }
    });
  }

  function _he(s){
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  // ----- provenance: data lineage for click popups -----
  //
  // Datasets may carry `field_provenance` (per-column lineage) and
  // `row_provenance` (per-entity overrides keyed by the value of
  // `row_provenance_field`). Each provenance entry is a free-form
  // dict that should at minimum carry `system` (e.g. "haver",
  // "market_data", "plottool", "fred", "bloomberg", "computed",
  // "csv") and `symbol` (canonical identifier in that system),
  // plus optional `display_name`, `units`, `source_label`,
  // `recipe`, `as_of`, etc.
  //
  // PRISM is responsible for cleaning upstream metadata into this
  // shape -- the compiler does NOT introspect df.attrs or autoload
  // anything. See README 3.6.
  function _datasetWrapper(dsName){
    var ds = DATASETS[dsName];
    if (!ds || typeof ds !== 'object' || Array.isArray(ds)) return null;
    return ds;
  }
  function _datasetHasProvenance(dsName){
    var ds = _datasetWrapper(dsName);
    if (!ds) return false;
    var fp = ds.field_provenance;
    if (fp && typeof fp === 'object'){
      for (var k in fp){
        if (Object.prototype.hasOwnProperty.call(fp, k)) return true;
      }
    }
    return false;
  }
  function _rowKeyValueFor(dsName, header, row){
    var ds = _datasetWrapper(dsName);
    if (!ds) return null;
    var rpf = ds.row_provenance_field;
    if (!rpf) return null;
    var ki = header.indexOf(rpf);
    if (ki < 0) return null;
    return row[ki];
  }
  function _rowKeyValueForRowMap(dsName, rowMap){
    var ds = _datasetWrapper(dsName);
    if (!ds || !rowMap) return null;
    var rpf = ds.row_provenance_field;
    if (!rpf) return null;
    return rowMap[rpf];
  }
  // Resolve provenance for (dataset, column, optional row key).
  // Row override wins over the column default; missing is null.
  function _provenanceForCol(dsName, colName, rowKeyValue){
    var ds = _datasetWrapper(dsName);
    if (!ds || !colName) return null;
    var fp = ds.field_provenance || {};
    var rp = ds.row_provenance || {};
    var base = fp[colName] || null;
    var override = null;
    if (rowKeyValue != null){
      var perRow = rp[String(rowKeyValue)];
      if (perRow) override = perRow[colName] || null;
    }
    if (!base && !override) return null;
    var merged = {};
    if (base){
      for (var k in base){
        if (Object.prototype.hasOwnProperty.call(base, k)) merged[k] = base[k];
      }
    }
    if (override){
      for (var k2 in override){
        if (Object.prototype.hasOwnProperty.call(override, k2)) merged[k2] = override[k2];
      }
    }
    return merged;
  }
  // Pick the most specific symbol the provenance carries. Order
  // matters: caller-supplied `symbol` wins over system-specific
  // alt keys when both are present.
  function _provenancePrimarySymbol(p){
    if (!p) return null;
    return p.symbol || p.coordinate || p.expression
      || p.haver_code || p.tsdb_symbol || p.fred_series
      || p.bloomberg_ticker || p.refinitiv_ric || null;
  }
  // Compact one-liner for inline source attribution under a stat.
  // Format: "<symbol> &middot; <source_label or system>".
  function _provenanceInlineString(p){
    if (!p) return '';
    var sym = _provenancePrimarySymbol(p);
    var src = p.source_label || p.system || '';
    var bits = [];
    if (sym) bits.push('<code>' + _he(sym) + '</code>');
    if (src) bits.push(_he(src));
    return bits.join(' &middot; ');
  }
  // Render a single <tr> for the provenance footer table.
  function _provenanceFooterRowHTML(label, prov){
    var sym = _provenancePrimarySymbol(prov);
    var bits = [];
    if (sym) bits.push('<code>' + _he(sym) + '</code>');
    if (prov.system && prov.system !== prov.source_label){
      bits.push('<span class="prov-system">' + _he(prov.system) + '</span>');
    }
    if (prov.source_label) bits.push(_he(prov.source_label));
    if (prov.recipe) bits.push('<em>' + _he(prov.recipe) + '</em>');
    if (prov.units) bits.push('<span class="prov-units">' + _he(prov.units) + '</span>');
    var rowLabel = prov.display_name || label;
    return '<tr><th>' + _he(rowLabel) + '</th>'
      + '<td>' + bits.join(' &middot; ') + '</td></tr>';
  }
  // Render the provenance footer for a popup. `fields` is the list
  // of columns the popup body referenced (string field names or
  // `{field, label?}` dicts); when null, every dataset column with
  // provenance is shown. Returns '' when there's nothing to show or
  // the popup explicitly opted out via `rc.show_provenance: false`.
  function _renderProvenanceFooterFor(rc, header, row, w, fields){
    if (rc && rc.show_provenance === false) return '';
    if (!w) return '';
    var dsName = w.dataset_ref || (w.spec && w.spec.dataset);
    if (!dsName) return '';
    var ds = _datasetWrapper(dsName);
    if (!ds) return '';
    var rowKey = _rowKeyValueFor(dsName, header, row);
    var seen = {};
    var ordered = [];
    function addField(f){
      var fname = (typeof f === 'string') ? f : (f && f.field);
      if (!fname || seen[fname]) return;
      seen[fname] = 1;
      var label = (f && typeof f === 'object' && f.label != null)
        ? f.label : fname;
      var prov = _provenanceForCol(dsName, fname, rowKey);
      if (!prov) return;
      ordered.push({label: label, prov: prov});
    }
    if (fields && fields.length){
      fields.forEach(addField);
    } else {
      header.forEach(addField);
    }
    if (!ordered.length) return '';
    var rows = ordered.map(function(e){
      return _provenanceFooterRowHTML(e.label, e.prov);
    });
    return '<div class="provenance-footer">'
      + '<div class="detail-section-title">Sources</div>'
      + '<table class="modal-detail-table provenance-table">'
      + rows.join('')
      + '</table></div>';
  }
  // Build a synthetic popup config for charts that don't declare one
  // but whose dataset carries provenance. The auto popup picks the
  // mapped axes so a click on a multi-line / scatter / pie still
  // opens with the relevant context.
  function _buildDefaultChartPopup(w, header, params){
    var spec = (w && w.spec) || {};
    var m = spec.mapping || {};
    var fields = [];
    function add(f){
      if (!f) return;
      if (Array.isArray(f)){ f.forEach(add); return; }
      if (fields.indexOf(f) < 0 && header.indexOf(f) >= 0) fields.push(f);
    }
    if (m.x) add(m.x);
    if (m.date) add(m.date);
    if (m.category) add(m.category);
    if (m.name) add(m.name);
    if (m.y){
      if (Array.isArray(m.y)){
        var clicked = params && params.seriesName;
        if (clicked && m.y.indexOf(clicked) >= 0) add(clicked);
        else m.y.forEach(add);
      } else add(m.y);
    }
    if (m.value) add(m.value);
    if (m.color && fields.indexOf(m.color) < 0) add(m.color);
    if (!fields.length) fields = header.slice();
    var titleField = m.category || m.name || m.x || m.date || fields[0] || null;
    return {
      auto: true,
      title_field: titleField,
      popup_fields: fields,
    };
  }
  // Build a synthetic popup for tables with no row_click but whose
  // dataset carries provenance. Uses every column so the click opens
  // the full row + provenance footer.
  function _buildDefaultTablePopup(w, header, cols){
    var titleField = (cols && cols.length && cols[0] && cols[0].field)
      ? cols[0].field
      : (header && header.length ? header[0] : null);
    return {
      auto: true,
      title_field: titleField,
      popup_fields: header ? header.slice() : null,
    };
  }

  // ----- popup modal (table row_click + chart click_popup) -----
  //
  // Single source of truth for the click-popup modal. Both
  // table.row_click and chart.click_popup hand a config dict +
  // header + row to `_openPopupModal` and get back a populated
  // modal -- simple key/value table OR rich detail.sections[] layout.
  //
  // Two modes (apply identically to row_click and click_popup):
  //   A) Simple key/value table. Use `popup_fields` -- a list of
  //      field-name strings, OR `{field, label, format, prefix,
  //      suffix}` dicts when the caller wants per-row formatting
  //      without dropping into rich mode (chart click popups don't
  //      have a column config to inherit formats from).
  //      Default (no `popup_fields`) = every column in `header`.
  //   B) Rich detail layout. Use `detail.sections[]` with
  //      section `type: "stats" | "markdown" | "chart" | "table"`.
  //      Charts and sub-tables can be filtered by the clicked row's
  //      key value, so you can embed a per-entity time series,
  //      yield curve, etc.
  //
  // The provenance footer (driven by dataset `field_provenance`) is
  // auto-appended to both modes when present. Suppress per-popup
  // with `rc.show_provenance: false`.
  //
  // `cols` is the table widget's column config (per-column format
  // hints, used as a fallback when popup_fields entries are bare
  // field-name strings). Pass `null` for chart click popups.
  // `w` (optional) is the originating widget; needed to resolve the
  // dataset reference for the provenance footer.
  function openRowModal(w, header, row, cols){
    var rc = (w.row_click && typeof w.row_click === 'object')
      ? w.row_click
      : _buildDefaultTablePopup(w, header, cols);
    _openPopupModal(rc, header, row, cols, w);
  }
  function _openPopupModal(rc, header, row, cols, w){
    if (!rc || typeof rc !== 'object') return;
    var title = '';
    if (rc.title_field){
      var tIdx = header.indexOf(rc.title_field);
      if (tIdx >= 0) title = String(row[tIdx]);
    }
    if (!title && cols && cols.length){
      var firstIdx = header.indexOf(cols[0].field);
      if (firstIdx >= 0) title = String(row[firstIdx]);
    }
    // subtitle support: `subtitle_field` or `subtitle_template`
    // (string with `{field}` / `{field:format}` placeholders).
    var subtitle = null;
    if (rc.subtitle_field){
      var sIdx = header.indexOf(rc.subtitle_field);
      if (sIdx >= 0) subtitle = String(row[sIdx]);
    } else if (rc.subtitle_template){
      subtitle = _expandRowTemplate(rc.subtitle_template, header, row);
    }

    if (rc.detail && rc.detail.sections){
      openRichRowModal(rc, title, subtitle, header, row, cols, w);
      return;
    }

    // Simple mode: key/value table.
    // Each entry of `popup_fields` is either a plain field-name string
    // (we look up the format in `cols` if any), or a dict
    // {field, label?, format?, prefix?, suffix?}. Mixed lists are fine.
    var showFields = rc.popup_fields;
    if (!showFields || showFields === '*' ||
        (Array.isArray(showFields) && showFields.length === 1
          && showFields[0] === '*')){
      showFields = header.slice();
    }

    var body = '<table class="modal-detail-table">';
    showFields.forEach(function(item){
      var fname = (typeof item === 'string') ? item : (item && item.field);
      if (!fname) return;
      var hi = header.indexOf(fname);
      if (hi < 0) return;
      var val = row[hi];
      var label = (item && typeof item === 'object' && item.label != null)
        ? item.label : fname;
      var fmt = (item && typeof item === 'object') ? item.format : null;
      if (!fmt && cols){
        for (var i = 0; i < cols.length; i++){
          if (cols[i].field === fname){ fmt = cols[i].format; break; }
        }
      }
      var text = formatValue(val, fmt);
      if (item && typeof item === 'object'){
        if (item.prefix) text = item.prefix + text;
        if (item.suffix) text = text + item.suffix;
      }
      body += '<tr><th>' + _he(label) + '</th>' +
               '<td>' + text + '</td></tr>';
    });
    body += '</table>';

    if (rc.extra_content){
      body += '<div class="modal-extra">' + String(rc.extra_content) + '</div>';
    }

    // Auto-append provenance footer (suppressed by rc.show_provenance:false).
    var provHtml = _renderProvenanceFooterFor(rc, header, row, w, showFields);
    if (provHtml) body += provHtml;

    showModal(title || 'Details', body, {subtitle: subtitle, wide: false});
  }

  // Substitute `{field}` tokens in a template using the current row
  // values. `{field:format}` applies a value format (see formatValue).
  function _expandRowTemplate(tpl, header, row){
    return String(tpl).replace(/\{([^}:]+)(?::([^}]+))?\}/g, function(m, f, fmt){
      var i = header.indexOf(f.trim());
      if (i < 0) return m;
      return formatValue(row[i], fmt ? fmt.trim() : null);
    });
  }

  function openRichRowModal(rc, title, subtitle, header, row, cols, w){
    var detail = rc.detail || {};
    var sections = detail.sections || [];
    var rowMap = {};
    header.forEach(function(h, i){ rowMap[h] = row[i]; });

    // Give each chart section a stable dom id so we can init ECharts
    // after the modal HTML is in the DOM.
    var chartJobs = [];
    var parts = [];
    var sectionFields = [];  // accumulated for the provenance footer

    sections.forEach(function(sec, si){
      var sType = (sec.type || '').toLowerCase();
      if (sType === 'stats'){
        parts.push(_renderDetailStats(sec, rowMap, header, cols, w));
        (sec.fields || []).forEach(function(f){
          var fn = (typeof f === 'string') ? f : (f && f.field);
          if (fn) sectionFields.push(fn);
        });
      } else if (sType === 'markdown'){
        parts.push(_renderDetailMarkdown(sec, header, row));
      } else if (sType === 'chart'){
        var cid = 'detail-chart-' + si + '-' + (Math.random() * 1e6 | 0);
        var h = sec.height || sec.h_px || 260;
        parts.push(
          (sec.title ? '<div class="detail-section-title">'
             + _he(sec.title) + '</div>' : '') +
          '<div id="' + cid + '" class="detail-chart"'
          + ' style="height:' + h + 'px"></div>'
        );
        chartJobs.push({id: cid, sec: sec});
      } else if (sType === 'table'){
        parts.push(_renderDetailTable(sec, rowMap, header, row));
      } else if (sType === 'kv' || sType === 'kv_table'){
        parts.push(_renderDetailKV(sec, header, row, cols));
        (sec.fields || header).forEach(function(f){ sectionFields.push(f); });
      }
    });

    // Auto-append provenance footer using the union of fields the
    // rich modal references (stats + kv). Suppressed per-popup with
    // rc.show_provenance:false. Empty footer suppresses itself.
    var provHtml = _renderProvenanceFooterFor(rc, header, row, w,
                     sectionFields.length ? sectionFields : null);
    if (provHtml) parts.push(provHtml);

    showModal(title || 'Details', parts.join('\n'),
                {subtitle: subtitle, wide: detail.wide !== false});

    // Init embedded charts AFTER the DOM is live so ECharts can
    // measure their containers.
    setTimeout(function(){
      chartJobs.forEach(function(job){ _renderDetailChart(job.id, job.sec, rowMap); });
    }, 0);
  }

  function _renderDetailStats(sec, rowMap, header, cols, w){
    // `f.show_source: true` adds an inline subline beneath the stat
    // value rendering "<symbol> &middot; <source>" pulled from the
    // dataset's field_provenance. Cheaper than the full footer when
    // the caller wants per-stat attribution inline.
    var dsName = w ? (w.dataset_ref || (w.spec && w.spec.dataset)) : null;
    var rowKey = dsName ? _rowKeyValueForRowMap(dsName, rowMap) : null;
    var items = (sec.fields || []).map(function(f){
      if (typeof f === 'string') f = {field: f};
      var v = rowMap[f.field];
      var lbl = f.label != null ? f.label : f.field;
      var fmt = f.format;
      if (!fmt && cols){
        for (var i = 0; i < cols.length; i++){
          if (cols[i].field === f.field){ fmt = cols[i].format; break; }
        }
      }
      var text = formatValue(v, fmt);
      if (f.prefix) text = f.prefix + text;
      if (f.suffix) text = text + f.suffix;
      var cls = 'detail-stat';
      if (typeof v === 'number'){
        if (f.signed_color && v > 0) cls += ' pos';
        else if (f.signed_color && v < 0) cls += ' neg';
      }
      var subHtml = '';
      if (f.sub){
        subHtml = '<div class="detail-stat-sub">'
          + _he(_expandRowTemplate(f.sub, header,
              header.map(function(h){ return rowMap[h]; })))
          + '</div>';
      }
      if (f.show_source && dsName){
        var prov = _provenanceForCol(dsName, f.field, rowKey);
        if (prov){
          var srcLine = _provenanceInlineString(prov);
          if (srcLine){
            subHtml += '<div class="detail-stat-src">'
              + srcLine + '</div>';
          }
        }
      }
      return '<div class="' + cls + '">'
        + '<div class="detail-stat-label">' + _he(lbl) + '</div>'
        + '<div class="detail-stat-value">' + text + '</div>'
        + subHtml
        + '</div>';
    });
    var title = sec.title
      ? '<div class="detail-section-title">' + _he(sec.title) + '</div>'
      : '';
    return title + '<div class="detail-stats">' + items.join('') + '</div>';
  }

  function _renderDetailMarkdown(sec, header, row){
    var tpl = sec.template != null ? sec.template
               : (sec.content != null ? sec.content : '');
    var md = _expandRowTemplate(tpl, header, row);
    return '<div class="detail-markdown">' + _mdInlinePopup(md) + '</div>';
  }

  function _renderDetailKV(sec, header, row, cols){
    var fields = sec.fields || header;
    var body = '<table class="modal-detail-table">';
    fields.forEach(function(fname){
      var hi = header.indexOf(fname);
      if (hi < 0) return;
      var fmt = null;
      if (cols){
        for (var i = 0; i < cols.length; i++){
          if (cols[i].field === fname){ fmt = cols[i].format; break; }
        }
      }
      body += '<tr><th>' + _he(fname) + '</th>'
           + '<td>' + formatValue(row[hi], fmt) + '</td></tr>';
    });
    body += '</table>';
    var title = sec.title
      ? '<div class="detail-section-title">' + _he(sec.title) + '</div>'
      : '';
    return title + body;
  }

  function _renderDetailTable(sec, rowMap, header, row){
    // A sub-table driven by a filtered manifest dataset.
    // sec: {dataset, filter_field?, row_key?, columns?, max_rows?}
    var ds = DATASETS[sec.dataset];
    var src = ds && ds.source ? ds.source : ds;
    if (!Array.isArray(src) || src.length < 2) return '';
    var sHeader = src[0];
    var body = src.slice(1);
    if (sec.filter_field && sec.row_key){
      var key = rowMap[sec.row_key];
      var fi = sHeader.indexOf(sec.filter_field);
      if (fi >= 0) body = body.filter(function(r){ return r[fi] === key; });
    }
    var maxRows = sec.max_rows || 12;
    body = body.slice(0, maxRows);
    var colsCfg = sec.columns ||
      sHeader.map(function(h){ return {field: h, label: h}; });
    var cIdx = colsCfg.map(function(c){ return sHeader.indexOf(c.field); });
    var html = '<table class="modal-detail-table sub"><thead><tr>';
    colsCfg.forEach(function(c){
      html += '<th>' + _he(c.label || c.field) + '</th>';
    });
    html += '</tr></thead><tbody>';
    body.forEach(function(r){
      html += '<tr>';
      colsCfg.forEach(function(c, ci){
        var v = cIdx[ci] >= 0 ? r[cIdx[ci]] : null;
        html += '<td>' + formatValue(v, c.format) + '</td>';
      });
      html += '</tr>';
    });
    html += '</tbody></table>';
    var title = sec.title
      ? '<div class="detail-section-title">' + _he(sec.title) + '</div>'
      : '';
    return title + html;
  }

  function _renderDetailChart(elId, sec, rowMap){
    var el = document.getElementById(elId); if (!el) return;
    var ds = DATASETS[sec.dataset];
    var src = ds && ds.source ? ds.source : ds;
    if (!Array.isArray(src) || src.length < 2) return;
    var header = src[0];
    var body = src.slice(1);
    // Filter to the clicked row's key value if configured.
    if (sec.filter_field && sec.row_key){
      var key = rowMap[sec.row_key];
      var fi = header.indexOf(sec.filter_field);
      if (fi >= 0) body = body.filter(function(r){ return r[fi] === key; });
    }
    if (!body.length) {
      el.innerHTML = '<div class="detail-chart-empty">No data for this row.</div>';
      return;
    }
    var m = sec.mapping || {};
    var chartType = (sec.chart_type || 'line').toLowerCase();
    var xCol = m.x;
    var yCol = m.y;
    var xIdx = header.indexOf(xCol);
    // Build the option. We intentionally keep this small and purpose-
    // built (rather than calling into the main builder dispatch on
    // the server) so detail popups render fast and don't need a full
    // Python round-trip on each row click.
    var series = [];
    var colorCol = m.color || m.colour;
    if (colorCol && !Array.isArray(yCol)){
      var yi = header.indexOf(yCol);
      var gi = header.indexOf(colorCol);
      var groups = {};
      body.forEach(function(r){
        if (gi < 0 || r[gi] == null) return;
        var name = String(r[gi]);
        if (!groups[name]) groups[name] = [];
        groups[name].push([r[xIdx], r[yi]]);
      });
      Object.keys(groups).forEach(function(name){
        series.push({
          type: chartType === 'bar' ? 'bar' : 'line',
          name: name, showSymbol: false,
          smooth: !!m.smooth,
          stack: m.stack ? (typeof m.stack === 'string' ? m.stack : 'total') : undefined,
          areaStyle: chartType === 'area' ? {opacity: 0.25} : undefined,
          data: groups[name],
        });
      });
    } else if (Array.isArray(yCol)){
      // Wide-form: one line per y column.
      yCol.forEach(function(y){
        var yi = header.indexOf(y);
        series.push({
          type: chartType === 'bar' ? 'bar' : 'line',
          name: y, showSymbol: false, smooth: !!m.smooth,
          stack: m.stack ? (typeof m.stack === 'string' ? m.stack : 'total') : undefined,
          areaStyle: chartType === 'area' ? {opacity: 0.25} : undefined,
          data: body.map(function(r){ return [r[xIdx], r[yi]]; }),
        });
      });
    } else {
      var yi = header.indexOf(yCol);
      series.push({
        type: chartType === 'bar' ? 'bar' : 'line',
        name: yCol, showSymbol: false, smooth: !!m.smooth,
        stack: m.stack ? (typeof m.stack === 'string' ? m.stack : 'total') : undefined,
        areaStyle: chartType === 'area' ? {opacity: 0.25} : undefined,
        data: body.map(function(r){ return [r[xIdx], r[yi]]; }),
      });
    }
    var opt = {
      grid: {top: 24, right: 24, bottom: 40, left: 56, containLabel: true},
      tooltip: {trigger: 'axis'},
      legend: {show: series.length > 1, type: 'scroll', top: 0},
      xAxis: {type: _guessAxisTypeFromValues(body, xIdx)},
      yAxis: {type: 'value', scale: true,
               name: m.y_title || ''},
      series: series,
    };
    if (m.zoom){
      opt.dataZoom = [{type: 'inside'}, {type: 'slider', height: 16, bottom: 4}];
      opt.grid.bottom = 56;
    }
    // date formatting like the main charts
    if (opt.xAxis.type === 'time'){
      opt.xAxis.axisLabel = {formatter: function(v){
        var d = new Date(v);
        if (isNaN(d.getTime())) return v;
        var mo = ['Jan','Feb','Mar','Apr','May','Jun',
                  'Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];
        return mo + ' ' + d.getDate();
      }};
    }
    if (sec.annotations){
      _applyDetailAnnotations(opt, sec.annotations);
    }
    var cid = sec.id || elId;
    var detailDataset = '__detail__' + cid;
    var detailSource = [header].concat(body);
    DATASETS[detailDataset] = {source: detailSource};
    currentDatasets[detailDataset] = detailSource;
    WIDGET_META[cid] = {
      id: cid,
      widget: 'chart',
      title: sec.title || '',
      dataset_ref: detailDataset,
      click_emit_filter: sec.click_emit_filter,
      click_popup: sec.click_popup,
      spec: {
        chart_type: chartType,
        dataset: detailDataset,
        mapping: m,
        theme: sec.theme,
        palette: sec.palette,
        series_colors: sec.series_colors
      }
    };
    SPECS[cid] = opt;
    __ensureTooltipDecimalCap(opt);
    _mountChartInstance(cid, el, materializeOption(cid), detailDataset);
    // materializeOption() applies the current shared filter state during the
    // initial mount, so the popup's first frame matches inline charts,
    // tables, and KPIs without a second controller pass.
  }

  function _guessAxisTypeFromValues(rows, idx){
    if (!rows.length || idx < 0) return 'value';
    var v = rows[0][idx];
    if (typeof v === 'number') return 'value';
    if (typeof v === 'string') {
      var d = Date.parse(v);
      if (!isNaN(d)) return 'time';
      return 'category';
    }
    return 'value';
  }

  function _applyDetailAnnotations(opt, ann){
    var mlData = [], maData = [];
    (ann || []).forEach(function(a){
      if (!a || typeof a !== 'object') return;
      if (a.type === 'hline' && a.y != null){
        mlData.push({yAxis: a.y,
                      lineStyle: {color: a.color || '#718096',
                                    type: a.style || 'dashed'},
                      label: {formatter: a.label || ''}});
      } else if (a.type === 'vline' && a.x != null){
        mlData.push({xAxis: a.x,
                      lineStyle: {color: a.color || '#718096',
                                    type: a.style || 'dashed'},
                      label: {formatter: a.label || ''}});
      } else if (a.type === 'band' && a.y1 != null && a.y2 != null){
        maData.push([{yAxis: a.y1,
                       itemStyle: {color: a.color || 'rgba(26,54,93,0.08)',
                                     opacity: a.opacity || 0.2}},
                      {yAxis: a.y2}]);
      }
    });
    if (mlData.length || maData.length){
      var s0 = (opt.series || [])[0] || {};
      if (mlData.length) s0.markLine = {symbol: 'none', data: mlData};
      if (maData.length) s0.markArea = {data: maData};
    }
  }

  var _DETAIL_CHARTS = [];

  function showModal(title, bodyHtml, opts){
    opts = opts || {};
    var back = document.getElementById('ed-modal-backdrop');
    if (!back){
      back = document.createElement('div');
      back.id = 'ed-modal-backdrop';
      back.className = 'ed-modal-backdrop';
      back.innerHTML =
        '<div class="ed-modal">' +
          '<div class="ed-modal-header">' +
            '<div class="ed-modal-title-wrap">' +
              '<div class="ed-modal-title"></div>' +
              '<div class="ed-modal-subtitle"></div>' +
            '</div>' +
            '<button class="ed-modal-close" aria-label="close">\u2715</button>' +
          '</div>' +
          '<div class="ed-modal-body"></div>' +
        '</div>';
      document.body.appendChild(back);
      back.addEventListener('click', function(e){
        if (e.target === back) hideModal();
      });
      back.querySelector('.ed-modal-close').addEventListener('click', hideModal);
      document.addEventListener('keydown', function(e){
        if (e.key === 'Escape') hideModal();
      });
    }
    var modal = back.querySelector('.ed-modal');
    modal.classList.toggle('wide', !!opts.wide);
    back.querySelector('.ed-modal-title').textContent = title;
    var subEl = back.querySelector('.ed-modal-subtitle');
    if (opts.subtitle){
      subEl.textContent = opts.subtitle;
      subEl.style.display = 'block';
    } else {
      subEl.textContent = '';
      subEl.style.display = 'none';
    }
    back.querySelector('.ed-modal-body').innerHTML = bodyHtml;
    back.style.display = 'flex';
  }
  function hideModal(){
    var back = document.getElementById('ed-modal-backdrop');
    if (back) back.style.display = 'none';
    // Dispose embedded detail charts and remove their temporary
    // controller/dataset records so every popup starts cleanly.
    if (typeof _DETAIL_CHARTS !== 'undefined' && _DETAIL_CHARTS){
      _DETAIL_CHARTS.forEach(function(rec){
        var inst = rec && rec.inst ? rec.inst : rec;
        try { inst.dispose(); } catch(e){}
        if (rec && rec.cid){
          delete CHARTS[rec.cid];
          delete WIDGET_META[rec.cid];
          delete SPECS[rec.cid];
          delete chartControlState[rec.cid];
          delete SERIES_COLOR_SLOTS[rec.cid];
        }
        if (rec && rec.dataset){
          delete DATASETS[rec.dataset];
          delete currentDatasets[rec.dataset];
        }
      });
      _DETAIL_CHARTS.length = 0;
    }
  }

  // ----- click popup wiring (info icons) -----
  //
  // Every \u24D8 icon in the dashboard carries `data-popup-title` and
  // `data-popup-body` attributes (set server-side by
  // _popup_icon_html). Clicking the icon opens the shared modal with
  // markdown-rendered body content. ESC / overlay click / X button
  // all close the modal via existing hideModal wiring.
  //
  // Also: clicking inside a <label> normally toggles the associated
  // form control; we stopPropagation so the filter doesn't re-focus
  // underneath the open modal.
  function _mdInlinePopup(text){
    // Markdown renderer for popup bodies (info / methodology /
    // row drill-down / dashboard summary). Twin of the Python
    // `_render_md` in rendering.py - both must support the same
    // grammar so server-rendered tiles and client-rendered modals
    // read identically.
    //
    // Block grammar:
    //   # ... ##### headings (h1..h5)
    //   blank-line separated paragraphs
    //   - / * unordered list items, 1. ordered list items
    //     (nested via 2-space indent)
    //   > blockquote (multi-line; recursively parsed)
    //   ``` fenced code blocks ``` (with optional language tag)
    //   | a | b |  GFM tables (header + separator + body rows)
    //   --- / *** / ___ horizontal rules
    //
    // Inline grammar:
    //   **bold**  *italic*  ~~strike~~  `code`  [label](url)
    //
    // IMPORTANT ordering: line-level constructs (headings, bullets,
    // tables, code fences) are detected BEFORE inline transforms run.
    // Otherwise the italic regex eats things like consecutive bullet
    // markers across lines.
    if (text == null) return '';
    var escapeHTML = function(s){
      return String(s == null ? '' : s)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    };
    function inlineTransforms(raw){
      var phs = [];
      var staged = String(raw).replace(/\[([^\]]+)\]\(([^)]+)\)/g,
        function(_, lbl, url){
          phs.push('<a href="' + escapeHTML(url) + '" target="_blank"' +
                    ' rel="noopener">' + escapeHTML(lbl) + '</a>');
          return '\x00LINK' + (phs.length - 1) + '\x00';
        });
      var e = escapeHTML(staged);
      e = e.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      e = e.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
      e = e.replace(/~~([^~]+)~~/g, '<del>$1</del>');
      e = e.replace(/`([^`]+)`/g, '<code>$1</code>');
      for (var i = 0; i < phs.length; i++){
        e = e.replace('\x00LINK' + i + '\x00', phs[i]);
      }
      return e;
    }
    function splitTableRow(line){
      var s = String(line).trim();
      if (s.charAt(0) === '|') s = s.slice(1);
      if (s.charAt(s.length - 1) === '|') s = s.slice(0, -1);
      return s.split('|').map(function(c){ return c.trim(); });
    }
    function parseTableAligns(sep){
      return splitTableRow(sep).map(function(c){
        if (c.charAt(0) === ':' && c.charAt(c.length - 1) === ':') return 'center';
        if (c.charAt(c.length - 1) === ':') return 'right';
        if (c.charAt(0) === ':') return 'left';
        return null;
      });
    }
    var TABLE_SEP_RE = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/;
    var HR_RE = /^\s*([-*_])\s*\1\s*\1[\s\1]*$/;
    var lines = String(text).split(/\n/);
    var out = [];
    var para = [];
    var quoteBuf = [];
    var listStack = [];   // [{kind, indent}, ...]
    var liOpen = [];       // parallel to listStack: is the deepest <li> still open?
    function flushPara(){
      if (para.length){
        out.push('<p>' + para.join(' ') + '</p>');
        para = [];
      }
    }
    function flushQuote(){
      if (quoteBuf.length){
        var inner = _mdInlinePopup(quoteBuf.join('\n'));
        out.push('<blockquote>' + inner + '</blockquote>');
        quoteBuf = [];
      }
    }
    function closeTopList(){
      var top = listStack.pop();
      if (liOpen.pop()) out.push('</li>');
      out.push('</' + top.kind + '>');
    }
    function closeAllLists(){
      while (listStack.length) closeTopList();
    }
    function pushListItem(kind, indent, text){
      while (listStack.length && listStack[listStack.length - 1].indent > indent){
        closeTopList();
      }
      if (listStack.length && listStack[listStack.length - 1].indent === indent){
        var top = listStack[listStack.length - 1];
        if (top.kind !== kind){
          closeTopList();
        } else {
          if (liOpen[liOpen.length - 1]){
            out.push('</li>');
            liOpen[liOpen.length - 1] = false;
          }
        }
      }
      var topIndent = listStack.length ? listStack[listStack.length - 1].indent : -1;
      if (!listStack.length || topIndent < indent){
        listStack.push({kind: kind, indent: indent});
        liOpen.push(false);
        out.push('<' + kind + '>');
      }
      out.push('<li>' + inlineTransforms(text));
      liOpen[liOpen.length - 1] = true;
    }
    var i = 0, n = lines.length;
    while (i < n){
      var raw = lines[i];
      var stripped = raw.replace(/^\s+/, '');
      var indent = raw.length - stripped.length;
      var s = stripped.replace(/\s+$/, '');

      if (s.indexOf('```') === 0){
        var lang = s.slice(3).trim();
        flushPara(); flushQuote(); closeAllLists();
        var buf = []; i += 1;
        while (i < n){
          var fl = lines[i].replace(/^\s+/, '').replace(/\s+$/, '');
          if (fl.indexOf('```') === 0) break;
          buf.push(lines[i]); i += 1;
        }
        i += 1;
        var cls = lang ? ' class="lang-' + escapeHTML(lang) + '"' : '';
        out.push('<pre><code' + cls + '>' + escapeHTML(buf.join('\n')) + '</code></pre>');
        continue;
      }

      if (s.indexOf('|') !== -1 && i + 1 < n &&
          TABLE_SEP_RE.test(lines[i + 1].replace(/\s+$/, ''))){
        flushPara(); flushQuote(); closeAllLists();
        var hdr = splitTableRow(s);
        var aligns = parseTableAligns(lines[i + 1].replace(/\s+$/, ''));
        i += 2;
        var rows = [];
        while (i < n){
          var rs = lines[i].replace(/\s+$/, '');
          if (rs.indexOf('|') !== -1 && rs.trim()){
            rows.push(splitTableRow(rs)); i += 1;
          } else { break; }
        }
        var tbl = ['<table class="md-table"><thead><tr>'];
        hdr.forEach(function(h, j){
          var al = aligns[j];
          tbl.push('<th' + (al ? ' style="text-align:' + al + '"' : '') + '>' +
                    inlineTransforms(h) + '</th>');
        });
        tbl.push('</tr></thead><tbody>');
        rows.forEach(function(row){
          tbl.push('<tr>');
          row.forEach(function(c, j){
            var al = aligns[j];
            tbl.push('<td' + (al ? ' style="text-align:' + al + '"' : '') + '>' +
                      inlineTransforms(c) + '</td>');
          });
          tbl.push('</tr>');
        });
        tbl.push('</tbody></table>');
        out.push(tbl.join(''));
        continue;
      }

      if (HR_RE.test(s)){
        flushPara(); flushQuote(); closeAllLists();
        out.push('<hr/>');
        i += 1; continue;
      }

      if (s === ''){
        flushPara(); flushQuote(); closeAllLists();
        i += 1; continue;
      }

      var hMatch = /^(#{1,5})\s+(.*)$/.exec(s);
      if (hMatch){
        flushPara(); flushQuote(); closeAllLists();
        var lvl = Math.min(hMatch[1].length, 5);
        out.push('<h' + lvl + '>' + inlineTransforms(hMatch[2]) + '</h' + lvl + '>');
        i += 1; continue;
      }

      if (s.indexOf('> ') === 0){
        flushPara(); closeAllLists();
        quoteBuf.push(s.slice(2));
        i += 1; continue;
      }
      if (s === '>'){
        flushPara(); closeAllLists();
        quoteBuf.push('');
        i += 1; continue;
      }

      var olMatch = /^(\d+)\.\s+(.*)$/.exec(s);
      var ulMatch = /^[-*]\s+(.*)$/.exec(s);
      if (olMatch || ulMatch){
        flushPara(); flushQuote();
        var kind = olMatch ? 'ol' : 'ul';
        var liText = olMatch ? olMatch[2] : ulMatch[1];
        var snapped = (indent - (indent % 2));
        pushListItem(kind, snapped, liText);
        i += 1; continue;
      }

      flushQuote(); closeAllLists();
      para.push(inlineTransforms(stripped));
      i += 1;
    }
    flushPara(); flushQuote(); closeAllLists();
    return out.join('\n');
  }

  function wirePopupIcons(){
    document.querySelectorAll(
      '.tile-info, .filter-info, .stat-info'
    ).forEach(function(icon){
      if (icon._popupWired) return;
      icon._popupWired = true;
      icon.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        var title = icon.getAttribute('data-popup-title') || '';
        var body = icon.getAttribute('data-popup-body') || '';
        if (!body) return;
        showModal(title || 'Details', _mdInlinePopup(body));
      });
      icon.addEventListener('keydown', function(e){
        if (e.key === 'Enter' || e.key === ' '){
          e.preventDefault(); icon.click();
        }
      });
    });
  }
  wirePopupIcons();

  // ----- chart PNG export (with title baked in) -----
  //
  // The dashboard tile renders the chart's title in its header chrome
  // and the compiler suppresses the internal ECharts title to avoid
  // duplication on screen. That means a vanilla `chart.getDataURL()`
  // produces a PNG with no title, which is useless for embeds /
  // vision-model handoffs / decks.
  //
  // Strategy: temporarily inject a title (using GS type styles)
  // straight into the live chart, snapshot via getDataURL(), then
  // immediately revert. ECharts' setOption + getDataURL is fully
  // synchronous, so the whole sequence runs inside one event-loop
  // tick and the browser never paints the intermediate state -- no
  // visual flicker for the user.
  //
  // We tried an offscreen-instance variant first (clean isolation,
  // no live mutation). It rendered the title and axes correctly but
  // the dataset rows didn't draw -- ECharts doesn't reliably accept
  // a dataset payload via setOption when it was sourced from another
  // live instance's getOption(). Mutating-and-restoring is simpler
  // and bullet-proof.
  function _hasExistingChartTitle(t){
    if (!t) return false;
    if (Array.isArray(t)){
      return t.some(function(x){ return x && x.text; });
    }
    return !!t.text;
  }
  function _exportTitleBlock(w, cid){
    var resolved = resolvedThemeForChart(cid);
    var semantic = resolved.semantic;
    return {
      text: w && w.title ? String(w.title) : '',
      subtext: w && w.subtitle ? String(w.subtitle) : '',
      left: 16,
      top: 10,
      textStyle: {
        fontFamily: 'Goldman Sans, GS Sans, Helvetica Neue, Arial, sans-serif',
        fontSize: 14,
        fontWeight: 600,
        color: semantic.text
      },
      subtextStyle: {
        fontFamily: 'Goldman Sans, GS Sans, Helvetica Neue, Arial, sans-serif',
        fontSize: 11,
        color: semantic.text_dim,
        fontStyle: 'italic'
      }
    };
  }
  function _downloadChartPngTitled(id, scale){
    var c = CHARTS[id]; if (!c) return false;
    var w = WIDGET_META[id] || {};
    var inst = c.inst;
    var hasOwnTitle = false;
    try {
      hasOwnTitle = _hasExistingChartTitle(inst.getOption().title);
    } catch(e){}

    // Skip injection when the chart already shows its own title
    // (raw option / ref passthrough widgets) or there's nothing to
    // inject. Fall through to the plain getDataURL path.
    var canInject = (w.title || w.subtitle) && !hasOwnTitle;

    if (canInject){
      try {
        // Inject title (and small grid.top bump so the plot area
        // doesn't overlap the title text).
        var titlePx = 26 + (w.subtitle ? 18 : 0) + 10;
        inst.setOption({
          title: [_exportTitleBlock(w, id)],
          grid: {top: titlePx + 30}
        }, false);
      } catch(e){ canInject = false; }
    }

    var url = inst.getDataURL({
      pixelRatio: scale,
      backgroundColor: chartExportBackground(id),
      type: 'png'
    });

    if (canInject){
      // Restore: ECharts' setOption(opt, true) keeps prior title /
      // grid state across "notMerge" resets when the new option
      // doesn't restate them, so calling clear() first is the only
      // reliable way to wipe them. Then fully re-render from the
      // single source of truth (materializeOption) which is what
      // every other code path also uses to draw this chart.
      try {
        inst.clear();
        var fresh = (typeof reviveFns === 'function')
                       ? reviveFns(materializeOption(id))
                       : materializeOption(id);
        inst.setOption(fresh, true);
      } catch(e){}
    }

    var a = document.createElement('a');
    a.href = url; a.download = (id || 'chart') + '.png'; a.click();
    return true;
  }
  window.downloadChartPngTitled = _downloadChartPngTitled;

  // ----- per-tile controls -----
  function wireTileActions(){
    document.querySelectorAll('.tile').forEach(function(tile){
      var id = tile.dataset.tileId;
      // Chart controls drawer toggle (three-dots icon, rightmost).
      var cc = tile.querySelector('.tile-btn.controls');
      if (cc){
        cc.addEventListener('click', function(){
          if (id) _ccToggleDrawer(id);
        });
      }
    });
  }

  // ----- full-dashboard HTML -----
  //
  // Downloads the generated dashboard source captured before ECharts and the
  // widget runtimes mutate their host elements. Reopening the file therefore
  // follows the normal initialization path instead of serializing live canvas
  // internals that cannot be rehydrated safely.
  var exportFullDashboard = document.getElementById('export-full-dashboard');
  if (exportFullDashboard){
    exportFullDashboard.addEventListener('click', function(){
      var stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      var fname = (MANIFEST.id || 'dashboard')
        + '_full_dashboard_' + stamp + '.html';
      var blob = new Blob(
        [STATIC_DASHBOARD_HTML],
        {type: 'text/html;charset=utf-8'}
      );
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = fname;
      a.click();
      setTimeout(function(){ URL.revokeObjectURL(url); }, 1500);
    });
  }

  var exportAll = document.getElementById('export-all');
  if (exportAll){
    exportAll.addEventListener('click', function(){
      Object.keys(CHARTS).forEach(function(id){
        _downloadChartPngTitled(id, 2);
      });
    });
  }
  var exportChartData = document.getElementById('export-chart-data');
  if (exportChartData){
    exportChartData.addEventListener('click', function(){
      var ids = Object.keys(WIDGET_META).filter(function(id){
        return WIDGET_META[id] && WIDGET_META[id].widget === 'chart' &&
          !!_ccChartFiltered(id);
      });
      ids.forEach(function(id, index){
        setTimeout(function(){ _ccDownloadCsv(id); }, index * 180);
      });
    });
  }
  var exportPrint = document.getElementById('export-print');
  if (exportPrint){
    exportPrint.addEventListener('click', function(){ window.print(); });
  }

  // ----- whole-dashboard PNG (html2canvas, lazy-loaded) -----
  //
  // Captures the entire .app subtree (header, tabs, filter bar, active
  // tab panel, footer) to a single PNG. Designed for the "drop into a
  // vision model" workflow. The background follows the resolved light/
  // dark theme intentionally; scale=2 and full scrollHeight preserve detail.
  // fetched lazily on first click so dashboards that never click this
  // pay zero cost.
  function ensureHtml2Canvas(){
    if (window.html2canvas) return Promise.resolve();
    if (window.__h2cLoading__) return window.__h2cLoading__;
    window.__h2cLoading__ = new Promise(function(resolve, reject){
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';
      s.async = true;
      s.onload = function(){ resolve(); };
      s.onerror = function(){
        window.__h2cLoading__ = null;
        reject(new Error('Failed to load html2canvas'));
      };
      document.head.appendChild(s);
    });
    return window.__h2cLoading__;
  }

  var exportDash = document.getElementById('export-dashboard');
  if (exportDash){
    exportDash.addEventListener('click', function(){
      var btn = exportDash;
      var origLabel = btn.textContent;
      btn.textContent = 'Capturing...';
      btn.disabled = true;
      var stamp = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 19);
      var fname = (MANIFEST.id || 'dashboard') + '_' + stamp + '.png';
      ensureHtml2Canvas().then(function(){
        // Settle ECharts: every chart that has a pending render
        // resolves on its 'finished' event before we rasterize.
        var charts = Object.keys(CHARTS).map(function(k){ return CHARTS[k]; })
          .filter(Boolean);
        return Promise.all(charts.map(function(c){
          return new Promise(function(resolve){
            try {
              c.inst.on('finished', function once(){
                c.inst.off('finished', once); resolve();
              });
              setTimeout(resolve, 1200);
            } catch(e){ resolve(); }
          });
        })).then(function(){ return new Promise(function(r){
          requestAnimationFrame(function(){ requestAnimationFrame(r); });
        }); });
      }).then(function(){
        var target = document.querySelector('.app') || document.body;
        // Note on file:// origins: Chrome prints a one-time
        // "Unsafe attempt to load URL ... 'file:' URLs are treated as
        // unique security origins" warning when html2canvas clones
        // the document into a sandbox iframe. It is purely a console
        // warning -- html2canvas falls through to rendering against
        // the live document and toBlob() succeeds. The warning
        // disappears entirely if the dashboard is served from http
        // (e.g. `python -m http.server` in the dashboard folder).
        return window.html2canvas(target, {
          backgroundColor: chartExportBackground(null),
          scale: 2,
          useCORS: true,
          logging: false,
          windowWidth: target.scrollWidth,
          windowHeight: target.scrollHeight,
          width: target.scrollWidth,
          height: target.scrollHeight,
        });
      }).then(function(canvas){
        return new Promise(function(resolve){
          canvas.toBlob(function(blob){
            if (!blob){ resolve(); return; }
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url; a.download = fname; a.click();
            setTimeout(function(){ URL.revokeObjectURL(url); }, 1500);
            resolve();
          }, 'image/png');
        });
      }).catch(function(e){
        console.error('Dashboard PNG export failed:', e);
        alert('Dashboard PNG export failed. See console for details.');
      }).then(function(){
        btn.textContent = origLabel;
        btn.disabled = false;
      });
    });
  }

  // ----- data freshness badges -----
  //
  // Two pills in the header-meta strip:
  //
  //   #now-pill      "12 May 2026  02:03:47 ET"   (live; ticks every 1s)
  //   #refresh-pill  "Refreshed 02:00:35 ET"      (static until next poll)
  //
  // JS owns the rendering here intentionally:
  //   - The live clock CAN'T be server-baked (it ticks every second);
  //     this is the one exception to anti-pattern #4 ("date math in
  //     the browser is the bug"). We use Intl.DateTimeFormat with the
  //     ET timezone so the rendering is deterministic; no `new Date()
  //     .toISOString()` shenanigans.
  //   - The refresh pill IS read from `metadata.time.refresh_cycle_at`
  //     (canonical ISO emit; `+00:00` since the Phase 3 staging-side
  //     refactor; `parse_iso` accepts legacy Z-suffix entries too).
  //     applyLiveData() updates it on every successful poll.
  //
  // ET is hardcoded (trading-floor convention). If a non-NY user
  // friction shows up later, parametrize via metadata.display_tz.
  var MD = MANIFEST.metadata || {};

  // Format any Date object's wall-clock as an ET-broken-out parts dict.
  // Cached formatter -- creating Intl.DateTimeFormat is cheap but
  // creating it 50,000 times (once per tick over a day) is wasteful.
  var _ET_FMT = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
  function _toETParts(d){
    if (!(d instanceof Date) || isNaN(d.getTime())) return null;
    var parts = _ET_FMT.formatToParts(d).reduce(function(acc, p){
      if (p.type !== 'literal') acc[p.type] = p.value;
      return acc;
    }, {});
    // Intl emits "24" for midnight in hour12:false on some engines;
    // normalize to "00" so the pill never reads "24:03:47 ET".
    if (parts.hour === '24') parts.hour = '00';
    return parts;
  }

  function _formatNowPill(now){
    var p = _toETParts(now);
    if (!p) return '';
    return p.day + ' ' + p.month + ' ' + p.year + '  '
            + p.hour + ':' + p.minute + ':' + p.second + ' ET';
  }

  function _formatRefreshPill(refreshAtISO, now){
    if (!refreshAtISO) return null;
    // parse_iso parity in JS: handle Z / +00:00 / naive transparently.
    // new Date() accepts both Z and +00:00; naive is ambiguous but
    // rare on this path (all our emit sites are aware).
    var rd = new Date(refreshAtISO);
    if (isNaN(rd.getTime())) return null;
    var r = _toETParts(rd);
    var n = _toETParts(now);
    if (!r || !n) return null;
    var sameDay  = r.year === n.year && r.month === n.month && r.day === n.day;
    var sameYear = r.year === n.year;
    if (sameDay){
      return 'Refreshed ' + r.hour + ':' + r.minute + ':' + r.second + ' ET';
    }
    if (sameYear){
      return 'Refreshed ' + r.day + ' ' + r.month + '  ' + r.hour + ':' + r.minute + ' ET';
    }
    return 'Refreshed ' + r.day + ' ' + r.month + ' ' + r.year
            + '  ' + r.hour + ':' + r.minute + ' ET';
  }

  function updateNowPill(){
    var el  = document.getElementById('now-pill');
    var val = document.getElementById('now-pill-val');
    if (!el || !val) return;
    var s = _formatNowPill(new Date());
    if (!s){ el.style.display = 'none'; return; }
    val.textContent = s;
    el.style.display = 'inline-flex';
  }

  function updateRefreshPill(refreshAtISO){
    var el  = document.getElementById('refresh-pill');
    var val = document.getElementById('refresh-pill-val');
    if (!el || !val) return;
    var iso = refreshAtISO
              || (MD.time && MD.time.refresh_cycle_at)
              || (MD.time && MD.time.build_completed_at)
              || MD.generated_at
              || null;
    var s = _formatRefreshPill(iso, new Date());
    if (!s){ el.style.display = 'none'; return; }
    val.textContent = s;
    el.style.display = 'inline-flex';
  }

  // Initial paint + tick every second. The interval is cheap (one
  // textContent write); pause-when-hidden is handled by the browser
  // (background tabs throttle setInterval automatically).
  updateNowPill();
  updateRefreshPill();
  setInterval(updateNowPill, 1000);

  // ----- live data refresh (no page reload) -----
  //
  // On dashboard load, kick off a polling loop that GETs the data
  // endpoint at the configured cadence. If the server returns 200
  // (data changed since last_refreshed), apply the new datasets +
  // specs + metadata in place. If it returns 304, no-op.
  //
  // Cadence comes from ``manifest.metadata.live_refresh_seconds``
  // (engine-stamped from refresh_frequency when omitted; default 30s
  // for legacy HTML). 0 disables the auto poll. ETag is the registry's
  // ``last_refreshed`` (= ``metadata.time.refresh_cycle_at``), so most
  // polls return 304 with no body.
  //
  // Triggers that fire a 200 the next poll picks up:
  //   1. Hourly cron writes new manifest + bumps registry.last_refreshed
  //   2. User clicks [Refresh] in another tab on the same dashboard
  //   3. Background scheduled process writes new data + bumps registry
  // The user does not need to take any action.
  //
  // Structural change detection: ``payload.manifest_template_hash``
  // differs from the hash baked into the served HTML
  // (``window.PRISM_TEMPLATE_HASH`` injected by the dashboard-serving
  // views) -- the structure changed (new widget / tab / filter), so
  // an in-place data swap can't cover it; fall back to one clean
  // location.reload(). When the hash matches OR the global isn't
  // injected (e.g. file:// preview), apply in place.

  var LIVE_KERBEROS    = MD.kerberos || null;
  var LIVE_DASHBOARD_ID = MD.dashboard_id || MANIFEST.id || null;
  var LIVE_DATA_URL    = MD.data_url || '/api/dashboard/data/';
  // Default 30s (was 60). Explicit 0 still disables the poll loop;
  // Refresh-button success still force-polls via opts.force.
  var LIVE_REFRESH_SEC = (MD.live_refresh_seconds == null)
                             ? 30 : (+MD.live_refresh_seconds | 0);
  var LIVE_PRESENCE_URL = MD.presence_url || '/api/dashboard/presence/';
  var LAST_KNOWN_TEMPLATE_HASH = (typeof window.PRISM_TEMPLATE_HASH !== 'undefined')
                                       ? window.PRISM_TEMPLATE_HASH : null;
  var LAST_KNOWN_REFRESHED = (MD.time && MD.time.refresh_cycle_at)
                                 || MD.data_as_of || MD.generated_at || null;

  function _liveFlashPill(){
    // Flash the refresh pill specifically -- it's the one whose
    // displayed text actually changed. The now-pill ticks every
    // second so a flash on it would be visual noise.
    var pill = document.getElementById('refresh-pill');
    if (!pill) return;
    pill.classList.remove('live-flash');
    // Force a reflow so re-adding the class restarts the animation
    // even on rapid back-to-back updates.
    void pill.offsetWidth;
    pill.classList.add('live-flash');
    setTimeout(function(){ pill.classList.remove('live-flash'); }, 1600);
  }

  function applyLiveData(payload){
    if (!payload || typeof payload !== 'object') return;

    // Structural-change short-circuit: template hash drift means a
    // widget / tab / filter was added or removed, which we can't
    // reconcile in place. One clean reload, then live-refresh resumes
    // against the new structure.
    if (LAST_KNOWN_TEMPLATE_HASH &&
        payload.manifest_template_hash &&
        payload.manifest_template_hash !== LAST_KNOWN_TEMPLATE_HASH){
      console.log('[live] template hash changed; reloading for new structure');
      location.reload();
      return;
    }

    // 1. Swap datasets in place. Deep-copy each new source so PAYLOAD
    //    and currentDatasets stay independent (filter / chart-controls
    //    code mutates currentDatasets as it derives intermediate views).
    var newDs = payload.datasets || {};
    Object.keys(newDs).forEach(function(name){
      var entry = newDs[name];
      var src = (entry && entry.source) || entry;
      try {
        currentDatasets[name] = JSON.parse(JSON.stringify(src));
      } catch (e){
        console.warn('[live] dataset deepcopy failed for', name, e);
      }
      DATASETS[name] = entry;
    });
    // Drop datasets the new manifest no longer carries.
    Object.keys(currentDatasets).forEach(function(name){
      if (!(name in newDs)){
        delete currentDatasets[name];
        delete DATASETS[name];
      }
    });

    // 2. Swap chart specs (the lowered ECharts option dicts).
    var newSpecs = payload.specs || {};
    Object.keys(newSpecs).forEach(function(cid){
      SPECS[cid] = newSpecs[cid];
    });

    // 3. Re-render every initialized chart. ECharts setOption(opt, true)
    //    diffs series under the hood; canvases get reused. preserveZoom
    //    means the user's in-chart dataZoom slider survives.
    Object.keys(CHARTS).forEach(function(cid){
      try {
        if (typeof rerenderChart === 'function'){
          rerenderChart(cid, {preserveZoom: true});
        }
      } catch (e){
        console.warn('[live] rerenderChart failed for', cid, e);
      }
    });

    // 4. Re-render dataset-derived widget kinds. Each function reads
    //    from currentDatasets + WIDGET_META; we don't need to pass
    //    anything in.
    try { if (typeof renderKpis      === 'function') renderKpis(); } catch(e){}
    try { if (typeof renderTables    === 'function') renderTables(); } catch(e){}
    try { if (typeof renderPivots    === 'function') renderPivots(); } catch(e){}
    try { if (typeof renderStatGrids === 'function') renderStatGrids(); } catch(e){}
    try { if (typeof _applyShowWhen  === 'function') _applyShowWhen(); } catch(e){}

    // 5. Update header chrome from the new metadata block. The
    //    now-pill ticks on its own setInterval; only the refresh-pill
    //    needs to react to the new metadata.time.refresh_cycle_at.
    var md = payload.metadata || {};
    if (md.time)        MD.time        = md.time;
    if (md.data_as_of)  MD.data_as_of  = md.data_as_of;
    if (md.generated_at) MD.generated_at = md.generated_at;
    updateRefreshPill();

    // Methodology + summary (markdown content) live in shared popups;
    // stash the fresh value on MANIFEST.metadata so the next popup
    // click sees the latest body.
    if (md.methodology !== undefined){
      MANIFEST.metadata = MANIFEST.metadata || {};
      MANIFEST.metadata.methodology = md.methodology;
    }
    if (md.summary !== undefined){
      MANIFEST.metadata = MANIFEST.metadata || {};
      MANIFEST.metadata.summary = md.summary;
    }

    // 6. Visual heartbeat -- the data-as-of pill briefly dims so the
    //    user notices that the numbers underneath the charts just
    //    moved. Subtle, no modal.
    _liveFlashPill();

    // 7. Advance the ETag baseline so the next poll asks "anything new
    //    since THIS refresh?".
    LAST_KNOWN_REFRESHED = payload.last_refreshed
                               || (md.time && md.time.refresh_cycle_at)
                               || md.data_as_of || md.generated_at
                               || LAST_KNOWN_REFRESHED;
  }

  function pollLiveData(opts){
    opts = opts || {};
    if (!opts.force && LIVE_REFRESH_SEC <= 0){
      return Promise.resolve('disabled');
    }
    if (window.location.protocol === 'file:'){
      return Promise.resolve('file');
    }
    if (!LIVE_KERBEROS || !LIVE_DASHBOARD_ID){
      return Promise.resolve('no_id');
    }
    var baseline = LAST_KNOWN_REFRESHED;
    var url = LIVE_DATA_URL
              + '?dashboard_id=' + encodeURIComponent(LIVE_DASHBOARD_ID)
              + '&kerberos='     + encodeURIComponent(LIVE_KERBEROS);
    // If the page itself was loaded with ?share=<token> (link-mode viewer),
    // propagate the token to the live-data poll so the ACL passes on refresh.
    try {
      var shareTok = new URLSearchParams(window.location.search).get('share');
      if (shareTok) url += '&share=' + encodeURIComponent(shareTok);
    } catch(e) { /* URLSearchParams unavailable -- skip */ }
    var headers = {};
    if (LAST_KNOWN_REFRESHED && !opts.skipEtag){
      headers['If-None-Match'] = '"' + LAST_KNOWN_REFRESHED + '"';
    }
    return fetch(url, {method: 'GET', headers: headers})
      .then(function(r){
        if (r.status === 304) return {kind: 'noop'};
        if (!r.ok) return {kind: 'error', status: r.status};
        return r.json().then(function(j){ return {kind: 'body', body: j}; });
      })
      .then(function(res){
        if (!res) return 'error';
        if (res.kind === 'noop') return 'noop';
        if (res.kind === 'error') return 'error';
        var j = res.body;
        if (j && j.ok){
          applyLiveData(j);
          if (opts.expectNewerThan &&
              (j.last_refreshed === opts.expectNewerThan ||
               j.last_refreshed === baseline)){
            return 'stale';
          }
          return 'applied';
        }
        return 'error';
      })
      .catch(function(e){
        // Transient network blip -- log and let the next tick retry.
        console.warn('[live] poll error:', e);
        return 'error';
      });
  }

  function pollLiveDataAfterRefresh(){
    // Retry until registry last_refreshed advances (fixes one-shot 304
    // race right after runner success) or attempts exhaust.
    var baseline = LAST_KNOWN_REFRESHED;
    var attempts = 0;
    var maxAttempts = 10;
    function tryOnce(){
      attempts++;
      return pollLiveData({force: true, expectNewerThan: baseline})
        .then(function(result){
          if (result === 'applied') return result;
          if (attempts >= maxAttempts) return result;
          return new Promise(function(resolve){
            setTimeout(resolve, 400);
          }).then(tryOnce);
        });
    }
    return tryOnce();
  }

  function beatPresence(){
    if (window.location.protocol === 'file:') return;
    if (document.visibilityState && document.visibilityState !== 'visible'){
      return;
    }
    if (!LIVE_KERBEROS || !LIVE_DASHBOARD_ID) return;
    var viewer = (typeof window.PRISM_VIEWER !== 'undefined' && window.PRISM_VIEWER)
                   ? window.PRISM_VIEWER : LIVE_KERBEROS;
    fetch(LIVE_PRESENCE_URL, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        kerberos: LIVE_KERBEROS,
        dashboard_id: LIVE_DASHBOARD_ID,
        viewer: viewer
      }),
      keepalive: true
    }).catch(function(e){
      console.warn('[presence] heartbeat error:', e);
    });
  }

  if (LIVE_REFRESH_SEC > 0){
    setInterval(pollLiveData, LIVE_REFRESH_SEC * 1000);
    // Poll immediately when the tab becomes visible again, so a user
    // returning to a tab they'd backgrounded sees fresh data without
    // waiting up to LIVE_REFRESH_SEC for the next tick.
    document.addEventListener('visibilitychange', function(){
      if (document.visibilityState === 'visible'){
        pollLiveData();
        beatPresence();
      }
    });
  }

  // Open-tab presence: tell the server this dashboard is viewed so the
  // open-only light orchestrator can pull fresh data on a short cadence.
  if (window.location.protocol !== 'file:' && LIVE_KERBEROS && LIVE_DASHBOARD_ID){
    beatPresence();
    setInterval(beatPresence, 30000);
  }

  // ----- methodology popup -----
  //
  // Shown when manifest.metadata.methodology is set. Accepts either a
  // plain markdown string or a {title, body} dict. Renders into the
  // shared modal via _mdInlinePopup() (same engine used by every other
  // popup in the dashboard, so styling is automatically consistent).
  (function(){
    var btn = document.getElementById('methodology-btn');
    if (!btn) return;
    var m = MD.methodology;
    if (m == null || m === '') return;
    var title = 'Methodology';
    var body = '';
    if (typeof m === 'string'){ body = m; }
    else if (typeof m === 'object'){
      title = m.title || title;
      body = m.body || m.text || '';
    }
    if (!body) return;
    btn.style.display = 'inline-flex';
    btn.addEventListener('click', function(){
      showModal(title, _mdInlinePopup(body));
    });
  })();

  // ----- excel download (header) -----
  //
  // One workbook for the whole dashboard. Each `widget=table` widget
  // gets its own sheet. Rows reflect the current applyFilters() state
  // PLUS the per-table search string and sort order, so what's
  // exported is exactly what the user sees. Sheet names are taken
  // from the widget title (or id), truncated to Excel's 31-char limit
  // and uniquified if collisions occur.
  function _excelSheetName(raw, used){
    var name = String(raw || 'sheet').replace(/[\\\/\?\*\[\]:]/g, ' ').trim();
    if (!name) name = 'sheet';
    name = name.slice(0, 31);
    var base = name, n = 2;
    while (used[name]){
      var suf = ' (' + n + ')';
      name = base.slice(0, 31 - suf.length) + suf;
      n++;
    }
    used[name] = true;
    return name;
  }
  function _exportTableRowsForXlsx(id){
    var w = WIDGET_META[id]; if (!_isTableWidget(w)) return null;
    var ds = w.dataset_ref ? currentDatasets[w.dataset_ref] : null;
    if (!ds || !ds.length) return null;
    var header = ds[0];
    var body = applyFilters(w.dataset_ref, ds, 'table', id).slice(1);
    var ts = (typeof TABLE_STATE !== 'undefined' && TABLE_STATE[id])
              ? TABLE_STATE[id] : null;
    if (ts && ts.search){
      body = body.filter(function(r){ return _rowMatchesSearch(r, ts.search); });
    }
    var cols = w.columns;
    if (!cols || !cols.length){
      cols = header.map(function(h){ return {field: h, label: h}; });
    }
    var colIndexes = cols.map(function(c){ return header.indexOf(c.field); });
    if (ts && ts.sortCol != null && colIndexes[ts.sortCol] >= 0){
      var ci = colIndexes[ts.sortCol], dir = ts.sortDir;
      body = body.slice().sort(function(a, b){
        var av = a[ci], bv = b[ci];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        var an = Number(av), bn = Number(bv);
        if (!isNaN(an) && !isNaN(bn)) return (an - bn) * dir;
        return String(av).localeCompare(String(bv)) * dir;
      });
    }
    var outHeader = cols.map(function(c){ return c.label != null ? c.label : c.field; });
    var rows = body.map(function(row){
      return cols.map(function(c, i){
        var hi = colIndexes[i];
        return hi >= 0 ? row[hi] : null;
      });
    });
    return [outHeader].concat(rows);
  }
  function downloadAllTablesXlsx(){
    if (typeof XLSX === 'undefined'){
      alert('Excel export requires network access to load the SheetJS ' +
            'library. Please reload while online.');
      return;
    }
    var wb = XLSX.utils.book_new();
    var used = {};
    var added = 0;
    Object.keys(WIDGET_META).forEach(function(id){
      var w = WIDGET_META[id]; if (!_isTableWidget(w)) return;
      var aoa = _exportTableRowsForXlsx(id);
      if (!aoa) return;
      var ws = XLSX.utils.aoa_to_sheet(aoa);
      var nm = _excelSheetName(w.title || id, used);
      XLSX.utils.book_append_sheet(wb, ws, nm);
      added++;
    });
    if (!added){
      alert('No table widgets to export.');
      return;
    }
    var stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    XLSX.writeFile(wb, (MANIFEST.id || 'dashboard') + '_' + stamp + '.xlsx');
  }
  window.downloadAllTablesXlsx = downloadAllTablesXlsx;
  function downloadOneTableXlsx(id){
    if (typeof XLSX === 'undefined'){
      alert('Excel export requires network access to load the SheetJS ' +
            'library. Please reload while online.');
      return;
    }
    var w = WIDGET_META[id]; if (!_isTableWidget(w)) return;
    var aoa = _exportTableRowsForXlsx(id);
    if (!aoa){ alert('No rows to export.'); return; }
    var wb = XLSX.utils.book_new();
    var ws = XLSX.utils.aoa_to_sheet(aoa);
    var nm = _excelSheetName(w.title || id, {});
    XLSX.utils.book_append_sheet(wb, ws, nm);
    XLSX.writeFile(wb, (w.title ? String(w.title).replace(/[^\w\-]+/g, '_') : id) + '.xlsx');
  }
  window.downloadOneTableXlsx = downloadOneTableXlsx;
  (function(){
    var btn = document.getElementById('export-excel');
    if (!btn) return;
    var hasTable = Object.keys(WIDGET_META).some(function(k){
      return _isTableWidget(WIDGET_META[k]);
    });
    btn.addEventListener('click', downloadAllTablesXlsx);
    // The Excel menu item lives inside the Download dropdown -- show
    // it only when the dashboard contains at least one table widget.
    if (hasTable){
      var li = document.getElementById('download-menu-excel-li');
      if (li) li.hidden = false;
    }
  })();

  // ----- Download dropdown (Full Dashboard / Panel / Charts / Excel) -----
  //
  // Single dropdown anchored to the [Download] button in the chrome.
  // Click the button to toggle; click outside or press Esc to close.
  // Each menu item delegates to the existing handler that the
  // standalone export buttons used to wire (full dashboard: static HTML;
  // panel: html2canvas; charts: per-chart PNG; excel: SheetJS workbook). The Excel item
  // is shown/hidden by the block above based on whether the
  // dashboard contains any widget:table.
  (function(){
    var dd  = document.getElementById('download-dd');
    var btn = document.getElementById('download-btn');
    var menu = document.getElementById('download-menu');
    if (!dd || !btn || !menu) return;
    function open(){
      menu.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
      dd.setAttribute('data-open', 'true');
    }
    function close(){
      menu.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
      dd.removeAttribute('data-open');
    }
    function toggle(){
      if (menu.hidden) open(); else close();
    }
    btn.addEventListener('click', function(e){
      e.stopPropagation(); toggle();
    });
    document.addEventListener('click', function(e){
      if (menu.hidden) return;
      if (!dd.contains(e.target)) close();
    });
    document.addEventListener('keydown', function(e){
      if (e.key === 'Escape' && !menu.hidden) close();
    });
    // Each menu item closes the menu after firing its action. The
    // action itself is wired by the existing export-* listeners, so
    // we do not call them here -- we just close.
    Array.prototype.forEach.call(
      menu.querySelectorAll('.download-menu-item'),
      function(item){ item.addEventListener('click', close); }
    );
  })();

  // ----- header_actions: custom buttons/links in the header -----
  (function(){
    var host = document.getElementById('header-actions');
    var actions = MANIFEST.header_actions || [];
    if (!host || !actions.length) return;
    actions.forEach(function(a){
      var el;
      if (a.href){
        el = document.createElement('a');
        el.href = a.href;
        el.target = a.target || '_blank';
        if (a.target !== '_self') el.rel = 'noopener noreferrer';
      } else {
        el = document.createElement('button');
        el.type = 'button';
      }
      // Header buttons share a single visual treatment -- white in
      // light mode, light-blue in dark mode. The manifest cannot
      // override this (the previous `a.primary` knob was removed
      // because dashboards on the same gallery wall need to look
      // the same).
      el.className = 'icon-btn';
      if (a.id) el.id = a.id;
      if (a.title) el.title = a.title;
      el.innerHTML = (a.icon ? (a.icon + ' ') : '') + _he(a.label || '');
      if (a.onclick && typeof window[a.onclick] === 'function'){
        el.addEventListener('click', function(e){
          try { window[a.onclick](e, a); } catch(err){ console.warn(err); }
        });
      }
      host.insertBefore(el, host.firstChild);
    });
  })();

  // ----- theme toggle button -----
  // Wires the always-on light/dark mode toggle. Lives inside header-
  // actions and is rendered unconditionally by the shell template
  // (the manifest cannot suppress or relocate it).
  (function(){
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', function(){
      setDarkMode(!DARK_MODE);
    });
  })();

  // ----- refresh button + error surfacing -----
  //
  // Shown when metadata.kerberos + metadata.dashboard_id are set.
  // POSTs to metadata.api_url (default /api/dashboard/refresh/) and
  // polls metadata.status_url for completion.
  //
  // The refresh button is non-suppressible from the manifest side --
  // there is no opt-out flag. Every persistent dashboard renders it.
  // If a server-side refresh is genuinely impossible (registry
  // disabled, runner namespace gap, etc.) the click surfaces the
  // failure in the structured error modal below; that's the right UX,
  // not a missing button.
  //
  // Refresh failures must be RECOVERABLE FROM THE BROWSER. A console
  // warning is not enough; the user typically does not have a
  // developer console open and shouldn't need one. So every failure
  // mode (network, 4xx/5xx spawn-fail, runner-side error, runner-side
  // partial, polling timeout) populates a dashboard-scoped error
  // record and pops a modal that lays out:
  //
  //   - the failure kind (runner_error / runner_partial / timeout /
  //     network / spawn_fail) with a coloured pill
  //   - dashboard context (kerberos, dashboard_id, S3 folder)
  //   - timestamps (started / completed / elapsed) when present
  //   - server-side resources (pid, log path) when present
  //   - the full errors[] array verbatim, one card per entry
  //   - a "Copy markdown for PRISM" button that copies a
  //     self-contained markdown report covering everything above so
  //     the user can paste it straight into PRISM and have the
  //     dashboard fixed without context-stitching
  //   - a "Try again" button (re-POSTs the refresh) and, on partial,
  //     a "Reload anyway" button (because some scripts succeeded)
  //
  // The persistent "Error details" pill next to the Refresh button
  // remains visible after the refresh-button label resets, until a
  // subsequent refresh succeeds. This is the load-bearing UX
  // affordance: even if the user navigates away and comes back, they
  // can re-open the modal and copy the failure into PRISM.
  //
  // On dashboard load we also fire one GET against status_url -- if
  // the most recent refresh was an error/partial, the persistent pill
  // appears immediately so users with stale data have a one-click
  // path to get it fixed.
  (function(){
    var btn = document.getElementById('refresh-btn');
    var label = document.getElementById('refresh-btn-label');
    var errBtn = document.getElementById('refresh-err-btn');
    if (!btn || !label) return;
    var kerberos = MD.kerberos;
    var dashboardId = MD.dashboard_id || MANIFEST.id;
    if (!kerberos || !dashboardId){
      // Dev-visible breadcrumb. The validator on the Python side
      // (compile_dashboard with require_persistence_metadata=True)
      // already rejects manifests missing kerberos / dashboard_id, but
      // legacy dashboards built before that guard landed can still
      // render without these fields. Surface the silent-hide path so
      // we can diagnose "where did my Refresh button go?" without
      // needing to re-read the JS.
      var miss = [];
      if (!kerberos)    miss.push('metadata.kerberos');
      if (!dashboardId) miss.push('metadata.dashboard_id (or manifest.id)');
      console.warn(
        '[prism] Refresh button hidden: ' + miss.join(', ') + '. ' +
        'Persistent dashboards must set metadata.kerberos and ' +
        'metadata.dashboard_id; rebuild via compile_dashboard().');
      return;
    }
    var apiUrl = MD.api_url || '/api/dashboard/refresh/';
    var statusUrl = MD.status_url || '/api/dashboard/refresh/status/';
    btn.style.display = 'inline-flex';

    var KIND_LABEL = {
      runner_error:   'REFRESH FAILED',
      runner_partial: 'PARTIAL REFRESH',
      timeout:        'POLLING TIMEOUT',
      network:        'NETWORK ERROR',
      spawn_fail:     'SPAWN FAILED'
    };
    var KIND_HINT = {
      runner_error: 'The Django runner spawned, but pull_data.py or build.py raised before completing. ' +
                    'The dashboard.html below is stale. Paste this report into PRISM to identify the failing script and fix it.',
      runner_partial: 'Some refresh scripts succeeded and some failed. The dashboard reflects whatever artefacts were re-written; ' +
                      'others are stale. Paste this report into PRISM to identify which scripts to fix.',
      timeout: 'The refresh runner started but did not finish within the 3-minute polling window. ' +
               'It may still be running on the server. Paste this report into PRISM to investigate.',
      network: 'The browser could not reach the refresh API. The PRISM web server is offline, the URL is wrong, or ' +
               'CORS / auth blocked the request. Paste this report into PRISM (or copy to operations).',
      spawn_fail: 'The refresh API responded but rejected the request -- usually because the dashboard is not ' +
                  'registered in dashboards_registry.json, the user has no permissions, or the runner subprocess ' +
                  'failed to spawn. Paste this report into PRISM to triage.'
    };

    var LAST_ERROR = null;       // populated each time we hit a failure
    var modalContainer = null;
    var copyTimer = null;

    function pillHtml(kind){
      return '<span class="refresh-err-pill kind-' + kind + '">' +
             _he(KIND_LABEL[kind] || kind.toUpperCase()) + '</span>';
    }

    function fmtTs(t){
      if (!t) return '';
      try {
        var d = new Date(t);
        if (isNaN(d.getTime())) return String(t);
        return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
      } catch(e){ return String(t); }
    }

    function fmtElapsed(a, b){
      if (!a || !b) return '';
      try {
        var ms = (new Date(b)).getTime() - (new Date(a)).getTime();
        if (!isFinite(ms) || ms < 0) return '';
        var s = ms / 1000;
        if (s < 60) return s.toFixed(1) + 's';
        var m = Math.floor(s / 60), r = Math.round(s % 60);
        return m + 'm ' + r + 's';
      } catch(e){ return ''; }
    }

    // Errors come in two shapes: a list of strings, or a list of
    // dicts with at least a message. Normalise to objects so the
    // modal can render uniformly.
    function normalizeErrors(errors){
      if (!errors) return [];
      if (typeof errors === 'string') errors = [errors];
      if (!Array.isArray(errors)) errors = [errors];
      return errors.map(function(e){
        if (e == null) return {message: '(empty error)'};
        if (typeof e === 'string') return {message: e};
        if (typeof e === 'object'){
          var out = {};
          out.script         = e.script || e.script_name || e.path || '';
          out.classification = e.classification || e.code || e.type || e.kind || '';
          out.message        = e.message || e.error || e.detail ||
                               e.exception || JSON.stringify(e);
          out.traceback      = e.traceback || e.stacktrace || '';
          return out;
        }
        return {message: String(e)};
      });
    }

    // Self-contained markdown report. The user pastes this into PRISM
    // and PRISM has everything it needs to triage without round-trips.
    function buildPrismMarkdown(rec){
      var lines = [];
      lines.push('## Dashboard refresh failure');
      lines.push('');
      lines.push('| Field | Value |');
      lines.push('| --- | --- |');
      lines.push('| Failure kind | `' + (rec.kind || 'unknown') + '` (' +
                  (KIND_LABEL[rec.kind] || rec.kind || 'unknown') + ') |');
      lines.push('| Dashboard ID | `' + (rec.dashboard_id || '') + '` |');
      lines.push('| Kerberos | `' + (rec.kerberos || '') + '` |');
      if (rec.folder)
        lines.push('| Folder | `' + rec.folder + '` |');
      if (rec.status)
        lines.push('| `refresh_status.json` status | `' + rec.status + '` |');
      if (rec.http_code != null)
        lines.push('| HTTP status | `' + rec.http_code + '` |');
      if (rec.started_at)
        lines.push('| Started at | `' + rec.started_at + '` |');
      if (rec.completed_at)
        lines.push('| Completed at | `' + rec.completed_at + '` |');
      var elapsed = fmtElapsed(rec.started_at, rec.completed_at);
      if (elapsed)
        lines.push('| Elapsed | ' + elapsed + ' |');
      if (rec.pid != null)
        lines.push('| Runner PID | `' + rec.pid + '` |');
      if (rec.log_path)
        lines.push('| Server log | `' + rec.log_path + '` |');
      if (rec.auto_healed)
        lines.push('| Auto-healed | yes |');
      lines.push('| Captured at | `' + rec.captured_at + '` |');
      lines.push('| Page URL | ' + rec.page_url + ' |');
      lines.push('| User agent | ' + rec.user_agent + ' |');
      lines.push('');

      var errs = normalizeErrors(rec.errors);
      if (errs.length){
        lines.push('### Errors (`refresh_status.json.errors[]`)');
        lines.push('');
        errs.forEach(function(e, i){
          lines.push('**Error ' + (i + 1) + '**');
          if (e.script)         lines.push('- script: `' + e.script + '`');
          if (e.classification) lines.push('- classification: `' + e.classification + '`');
          lines.push('');
          lines.push('```');
          lines.push((e.message || '').toString());
          lines.push('```');
          if (e.traceback){
            lines.push('');
            lines.push('```');
            lines.push(String(e.traceback));
            lines.push('```');
          }
          lines.push('');
        });
      }

      if (rec.kind === 'network' && rec.exception){
        lines.push('### Browser-side exception');
        lines.push('');
        lines.push('```');
        lines.push(String(rec.exception));
        lines.push('```');
        lines.push('');
      }
      if (rec.kind === 'spawn_fail' && rec.spawn_error){
        lines.push('### Spawn-time error from `' + apiUrl + '`');
        lines.push('');
        lines.push('```');
        lines.push(String(rec.spawn_error));
        lines.push('```');
        lines.push('');
      }

      lines.push('### Raw response');
      lines.push('');
      lines.push('```json');
      try {
        lines.push(JSON.stringify(rec.raw, null, 2));
      } catch(e){
        lines.push('(could not serialise -- ' + e + ')');
      }
      lines.push('```');
      lines.push('');

      lines.push('### What PRISM should check');
      lines.push('');
      lines.push('1. `users/' + (rec.kerberos || '<kerberos>') + '/dashboards/' +
                  (rec.dashboard_id || '<id>') + '/scripts/pull_data.py` exists on S3 and runs cleanly.');
      lines.push('2. `users/' + (rec.kerberos || '<kerberos>') + '/dashboards/' +
                  (rec.dashboard_id || '<id>') + '/scripts/build.py` exists on S3 and runs cleanly.');
      lines.push('3. `users/' + (rec.kerberos || '<kerberos>') + '/dashboards/' +
                  (rec.dashboard_id || '<id>') + '/manifest_template.json` exists.');
      lines.push('4. `users/' + (rec.kerberos || '<kerberos>') + '/dashboards/' +
                  (rec.dashboard_id || '<id>') + '/data/*.csv` reflects the columns build.py expects.');
      lines.push('5. `users/' + (rec.kerberos || '<kerberos>') + '/dashboards/' +
                  (rec.dashboard_id || '<id>') + '/refresh_status.json` matches the snapshot above.');
      lines.push('6. The dashboard is registered in `users/' + (rec.kerberos || '<kerberos>') +
                  '/dashboards/dashboards_registry.json` with `refresh_enabled: true`.');
      return lines.join('\n');
    }

    function buildModalBody(rec){
      var errs = normalizeErrors(rec.errors);
      var elapsed = fmtElapsed(rec.started_at, rec.completed_at);
      var folder = rec.folder ||
                   ('users/' + rec.kerberos + '/dashboards/' + rec.dashboard_id + '/');
      var rows = [];
      rows.push(pillHtml(rec.kind));

      var summary = '<dl class="refresh-err-summary">';
      summary += '<dt>Dashboard</dt><dd><code>' + _he(rec.dashboard_id || '') + '</code></dd>';
      summary += '<dt>Kerberos</dt><dd><code>' + _he(rec.kerberos || '') + '</code></dd>';
      summary += '<dt>S3 folder</dt><dd><code>' + _he(folder) + '</code></dd>';
      if (rec.status)
        summary += '<dt>Status</dt><dd><code>' + _he(rec.status) + '</code></dd>';
      if (rec.http_code != null)
        summary += '<dt>HTTP</dt><dd><code>' + _he(String(rec.http_code)) + '</code></dd>';
      if (rec.started_at)
        summary += '<dt>Started</dt><dd>' + _he(fmtTs(rec.started_at)) + '</dd>';
      if (rec.completed_at)
        summary += '<dt>Completed</dt><dd>' + _he(fmtTs(rec.completed_at)) + '</dd>';
      if (elapsed)
        summary += '<dt>Elapsed</dt><dd>' + _he(elapsed) + '</dd>';
      if (rec.pid != null)
        summary += '<dt>Runner PID</dt><dd><code>' + _he(String(rec.pid)) + '</code></dd>';
      if (rec.log_path)
        summary += '<dt>Server log</dt><dd><code>' + _he(rec.log_path) + '</code></dd>';
      if (rec.auto_healed)
        summary += '<dt>Auto-healed</dt><dd>yes</dd>';
      summary += '</dl>';

      var listHtml = '';
      if (errs.length){
        listHtml += '<div class="refresh-err-section-h">' +
                    'Errors (' + errs.length + ')</div>';
        listHtml += '<ul class="refresh-err-list">';
        errs.forEach(function(e){
          var cls = (rec.kind === 'runner_partial') ? ' class="partial"' : '';
          var meta = [];
          if (e.script)         meta.push('script: ' + e.script);
          if (e.classification) meta.push('class: ' + e.classification);
          listHtml += '<li' + cls + '>';
          if (meta.length){
            listHtml += '<span class="err-meta">' +
                        _he(meta.join(' \u00B7 ')) + '</span>';
          }
          listHtml += _he((e.message || '').toString());
          if (e.traceback){
            listHtml += '\n\n' + _he(String(e.traceback));
          }
          listHtml += '</li>';
        });
        listHtml += '</ul>';
      } else {
        listHtml += '<div class="refresh-err-section-h">Errors</div>';
        listHtml += '<ul class="refresh-err-list"><li>' +
                    _he(rec.exception || rec.spawn_error || 'No structured errors returned.') +
                    '</li></ul>';
      }

      var tipHtml = '<div class="refresh-err-tip"><strong>What to do:</strong> ' +
                    _he(KIND_HINT[rec.kind] || '') +
                    '<br><br><strong>Fastest path to a fix:</strong> click ' +
                    '<em>Copy markdown for PRISM</em> and paste it into your PRISM session. ' +
                    'PRISM has all the context it needs to identify the failing script ' +
                    'and re-upload it to S3 -- you do not need to rebuild the dashboard ' +
                    'from scratch.</div>';

      var actionsHtml = '<div class="refresh-err-actions">';
      actionsHtml += '<button type="button" class="primary" id="refresh-err-copy">' +
                     'Copy markdown for PRISM</button>';
      actionsHtml += '<button type="button" id="refresh-err-retry">Try again</button>';
      if (rec.kind === 'runner_partial'){
        actionsHtml += '<button type="button" id="refresh-err-reload">' +
                       'Reload anyway (some scripts succeeded)</button>';
      }
      actionsHtml += '<span class="refresh-err-copy-status" id="refresh-err-copy-status">' +
                     'Copied -- paste into PRISM</span>';
      actionsHtml += '</div>';

      return rows.join('') + summary + listHtml + tipHtml + actionsHtml;
    }

    function showErrorModal(rec){
      var title = 'Dashboard refresh failed';
      if (rec.kind === 'runner_partial') title = 'Dashboard refresh: partial success';
      if (rec.kind === 'timeout')        title = 'Dashboard refresh timed out';
      if (rec.kind === 'network')        title = 'Dashboard refresh: network error';
      if (rec.kind === 'spawn_fail')     title = 'Dashboard refresh could not start';
      var subtitle = (rec.dashboard_id || '') +
                     (rec.kerberos ? '  \u00B7  ' + rec.kerberos : '');

      showModal(title, buildModalBody(rec), {wide: true, subtitle: subtitle});

      // Wire action buttons after innerHTML lands.
      var copyBtn   = document.getElementById('refresh-err-copy');
      var retryBtn  = document.getElementById('refresh-err-retry');
      var reloadBtn = document.getElementById('refresh-err-reload');
      var copyStatus = document.getElementById('refresh-err-copy-status');
      if (copyBtn){
        copyBtn.addEventListener('click', function(){
          var md = buildPrismMarkdown(rec);
          var done = function(){
            if (!copyStatus) return;
            copyStatus.classList.add('visible');
            if (copyTimer) clearTimeout(copyTimer);
            copyTimer = setTimeout(function(){
              copyStatus.classList.remove('visible');
            }, 3500);
          };
          if (navigator.clipboard && navigator.clipboard.writeText){
            navigator.clipboard.writeText(md).then(done, function(){
              fallbackCopy(md); done();
            });
          } else {
            fallbackCopy(md); done();
          }
        });
      }
      if (retryBtn){
        retryBtn.addEventListener('click', function(){
          hideModal(); doRefresh();
        });
      }
      if (reloadBtn){
        reloadBtn.addEventListener('click', function(){
          hideModal(); location.reload();
        });
      }
    }

    function fallbackCopy(text){
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed'; ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      } catch(e){ console.warn('[refresh] clipboard fallback failed:', e); }
    }

    function persistErrorPill(){
      if (!errBtn) return;
      errBtn.style.display = 'inline-flex';
    }
    function clearErrorPill(){
      if (!errBtn) return;
      errBtn.style.display = 'none';
    }

    function recordError(rec){
      rec.captured_at = new Date().toISOString();
      rec.page_url = window.location.href;
      rec.user_agent = navigator.userAgent;
      rec.kerberos = rec.kerberos || kerberos;
      rec.dashboard_id = rec.dashboard_id || dashboardId;
      LAST_ERROR = rec;
      window.LAST_REFRESH_ERROR = rec;   // for scripted access
      persistErrorPill();
    }

    function setLabel(cls, txt){
      btn.classList.remove('refreshing','refresh-success','refresh-error');
      if (cls) btn.classList.add(cls);
      label.textContent = txt;
    }
    function resetLabel(){ setLabel('', 'Refresh'); btn.disabled = false; }

    function pollStatus(){
      var polls = 0, maxPolls = 60; // 3s x 60 = 3 min
      var timer = setInterval(function(){
        polls++;
        if (polls > maxPolls){
          clearInterval(timer);
          setLabel('refresh-error', 'Timeout');
          recordError({
            kind: 'timeout',
            status: 'running',
            errors: ['Polling /api/dashboard/refresh/status/ timed out after ' +
                     (maxPolls * 3) + 's. The runner may still be in flight on ' +
                     'the server -- check the PID / log path before retrying.'],
            raw: {polled_for_seconds: polls * 3, max_polls: maxPolls}
          });
          showErrorModal(LAST_ERROR);
          setTimeout(resetLabel, 5000);
          return;
        }
        fetch(statusUrl + '?dashboard_id=' + encodeURIComponent(dashboardId))
          .then(function(r){ return r.json().then(function(j){ return [r.status, j]; }); })
          .then(function(pair){
            var code = pair[0], st = pair[1] || {};
            if (st.status === 'success'){
              clearInterval(timer);
              setLabel('refresh-success', 'Done');
              clearErrorPill();
              // No location.reload(): pull fresh data + apply in place
              // via the live-refresh loop. Filter state, dataZoom
              // sliders, table sort, dark mode all survive. Retry
              // briefly so a registry stamp lag does not 304 forever.
              pollLiveDataAfterRefresh();
              setTimeout(resetLabel, 1500);
            } else if (st.status === 'error'){
              clearInterval(timer);
              setLabel('refresh-error', 'Error');
              recordError({
                kind: 'runner_error', status: 'error', http_code: code,
                errors: st.errors || [], started_at: st.started_at,
                completed_at: st.completed_at, pid: st.pid,
                log_path: st.log_path || st.log,
                auto_healed: st.auto_healed, raw: st
              });
              showErrorModal(LAST_ERROR);
              setTimeout(resetLabel, 5000);
            } else if (st.status === 'partial'){
              clearInterval(timer);
              setLabel('refresh-error', 'Partial');
              recordError({
                kind: 'runner_partial', status: 'partial', http_code: code,
                errors: st.errors || [], started_at: st.started_at,
                completed_at: st.completed_at, pid: st.pid,
                log_path: st.log_path || st.log,
                auto_healed: st.auto_healed, raw: st
              });
              showErrorModal(LAST_ERROR);
              // No auto-reload: the user reads the modal first, then
              // chooses Reload-anyway. Reset the button label after a
              // beat so they can also re-attempt.
              setTimeout(resetLabel, 5000);
            }
            // still running -> keep polling
          })
          .catch(function(e){
            console.warn('[refresh] poll network error:', e);
            // Don't kill the timer on a single transient -- only on
            // sustained failure. The maxPolls cap above provides the
            // upper bound.
          });
      }, 3000);
    }

    function doRefresh(){
      if (window.location.protocol === 'file:'){
        alert('Refresh is not available when viewing the dashboard offline. ' +
              'Open the dashboard from the PRISM portal to refresh.');
        return;
      }
      btn.disabled = true; setLabel('refreshing', 'Refreshing...');
      // mode=light: pull + update manifest datasets only (no HTML
      // recompile). Django must forward this into refresh_runner
      // --mode light; staging harness already does.
      fetch(apiUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          kerberos: kerberos,
          dashboard_id: dashboardId,
          mode: 'light'
        })
      })
        .then(function(r){ return r.json().then(function(j){ return [r.status, j]; }); })
        .then(function(pair){
          var code = pair[0], result = pair[1] || {};
          if (code === 409){ pollStatus(); return; }
          if (result.status === 'refreshing'){ pollStatus(); return; }
          if (result.status === 'success' || result.status === 'partial'){
            // The synchronous-finish branch is rare in PRISM (the API
            // typically returns 200 + {status:"refreshing"} and the
            // runner finishes async), but if it does we still want the
            // partial UX to surface what failed.
            if (result.status === 'partial'){
              setLabel('refresh-error', 'Partial');
              recordError({
                kind: 'runner_partial', status: 'partial', http_code: code,
                errors: result.errors || [], started_at: result.started_at,
                completed_at: result.completed_at, pid: result.pid,
                log_path: result.log_path || result.log,
                auto_healed: result.auto_healed, raw: result
              });
              showErrorModal(LAST_ERROR);
              setTimeout(resetLabel, 5000);
              return;
            }
            setLabel('refresh-success', 'Done');
            clearErrorPill();
            // No location.reload(): the synchronous-finish branch lands
            // through the same in-place data swap path as the async
            // polled-status branch.
            pollLiveDataAfterRefresh();
            setTimeout(resetLabel, 1500);
          } else {
            // 4xx / 5xx / explicit {error: ...} body. The runner never
            // even ran -- usually because the dashboard is not in the
            // registry, the user is unauthenticated, or the spawn
            // itself failed.
            setLabel('refresh-error', 'Error');
            recordError({
              kind: 'spawn_fail', status: result.status || null,
              http_code: code,
              errors: result.errors || (result.error ? [result.error] : []),
              spawn_error: result.error || result.message || null,
              raw: result
            });
            showErrorModal(LAST_ERROR);
            setTimeout(resetLabel, 5000);
          }
        })
        .catch(function(err){
          // Network-level failure: the browser couldn't reach the API
          // at all. Distinct from spawn_fail (which means the API
          // responded with a rejection).
          setLabel('refresh-error', 'Error');
          recordError({
            kind: 'network',
            errors: ['fetch ' + apiUrl + ' failed: ' + (err && err.message ? err.message : err)],
            exception: (err && err.stack) ? err.stack : String(err),
            raw: {api_url: apiUrl, status_url: statusUrl}
          });
          showErrorModal(LAST_ERROR);
          setTimeout(resetLabel, 5000);
        });
    }

    btn.addEventListener('click', doRefresh);
    if (errBtn){
      errBtn.addEventListener('click', function(){
        if (LAST_ERROR) showErrorModal(LAST_ERROR);
      });
    }

    // On dashboard load, surface the most recent failure (if any) so
    // users coming back to a stale dashboard see the failure in the
    // header without having to click Refresh again. We don't auto-pop
    // the modal -- that would be too noisy on every reload -- we just
    // light up the persistent pill.
    if (window.location.protocol !== 'file:'){
      try {
        fetch(statusUrl + '?dashboard_id=' + encodeURIComponent(dashboardId), {
          method: 'GET'
        }).then(function(r){
          if (!r.ok) return null;
          return r.json();
        }).then(function(st){
          if (!st) return;
          if (st.status === 'error'){
            recordError({
              kind: 'runner_error', status: 'error',
              errors: st.errors || [], started_at: st.started_at,
              completed_at: st.completed_at, pid: st.pid,
              log_path: st.log_path || st.log,
              auto_healed: st.auto_healed, raw: st
            });
          } else if (st.status === 'partial'){
            recordError({
              kind: 'runner_partial', status: 'partial',
              errors: st.errors || [], started_at: st.started_at,
              completed_at: st.completed_at, pid: st.pid,
              log_path: st.log_path || st.log,
              auto_healed: st.auto_healed, raw: st
            });
          }
        }).catch(function(){ /* status endpoint optional */ });
      } catch(e){ /* swallow -- the manual refresh path still works */ }
    }
  })();

  // ----- URL state (shareable views) -----
  // Encode active tab + filter state + chart drawer state + table state
  // + kpi state into the URL hash. Shape:
  //   #t=overview&f.lookback=6M&f.scope=us&c.curve.transform=yoy_pct
  // Restored on load, written on every state mutation. Pure additive
  // layer -- localStorage tab persistence still works as a fallback
  // when no hash is present.
  var _URL_STATE_LOADING = false;

  function _serializeUrlState(){
    if (_URL_STATE_LOADING) return;
    var parts = [];
    // active tab
    var activeBtn = document.querySelector('.tab-btn.active');
    if (activeBtn && activeBtn.dataset.tab){
      parts.push('t=' + encodeURIComponent(activeBtn.dataset.tab));
    }
    // filters
    Object.keys(filterState).forEach(function(fid){
      var v = filterState[fid];
      if (v == null || v === '') return;
      if (Array.isArray(v) && v.length === 0) return;
      var s = Array.isArray(v) ? v.join(',') : String(v);
      parts.push('f.' + encodeURIComponent(fid) + '=' + encodeURIComponent(s));
    });
    // chart drawer state -- only the user-mutable knobs
    Object.keys(chartControlState || {}).forEach(function(cid){
      var st = chartControlState[cid] || {};
      if (st.transform) parts.push('c.' + cid + '.t=' + encodeURIComponent(st.transform));
      if (st.smoothing != null && st.smoothing !== 0)
        parts.push('c.' + cid + '.s=' + encodeURIComponent(st.smoothing));
      if (st.yScale && st.yScale !== 'linear')
        parts.push('c.' + cid + '.ys=' + encodeURIComponent(st.yScale));
      if (st.xScale && st.xScale !== 'linear')
        parts.push('c.' + cid + '.xs=' + encodeURIComponent(st.xScale));
    });
    // table sort + search -- keep concise, no hidden cols (often noise)
    Object.keys(TABLE_STATE || {}).forEach(function(tid){
      var ts = TABLE_STATE[tid] || {};
      if (ts.sortBy) parts.push('tb.' + tid + '.sb=' + encodeURIComponent(ts.sortBy));
      if (ts.sortDir) parts.push('tb.' + tid + '.sd=' + encodeURIComponent(ts.sortDir));
      if (ts.search) parts.push('tb.' + tid + '.q=' + encodeURIComponent(ts.search));
    });
    // KPI compare period
    Object.keys(KPI_STATE || {}).forEach(function(kid){
      var ks = KPI_STATE[kid] || {};
      if (ks.comparePeriod && ks.comparePeriod !== 'auto')
        parts.push('k.' + kid + '.cp=' + encodeURIComponent(ks.comparePeriod));
    });
    // Pivot dropdown selections
    Object.keys(PIVOT_STATE || {}).forEach(function(pid){
      var ps = PIVOT_STATE[pid] || {};
      if (ps.row) parts.push('p.' + pid + '.r=' + encodeURIComponent(ps.row));
      if (ps.col) parts.push('p.' + pid + '.c=' + encodeURIComponent(ps.col));
      if (ps.val) parts.push('p.' + pid + '.v=' + encodeURIComponent(ps.val));
      if (ps.agg) parts.push('p.' + pid + '.a=' + encodeURIComponent(ps.agg));
    });
    var hash = parts.length ? ('#' + parts.join('&')) : '';
    try {
      // replaceState avoids polluting the back-stack on every keystroke
      var url = window.location.pathname + window.location.search + hash;
      window.history.replaceState(null, '', url);
    } catch(e){}
  }
  window._serializeUrlState = _serializeUrlState;

  function _restoreUrlState(){
    var hash = String(window.location.hash || '');
    if (!hash || hash.length < 2) return;
    _URL_STATE_LOADING = true;
    try {
      var raw = hash.replace(/^#/, '');
      var pairs = raw.split('&');
      var pendingTab = null;
      var dirtyCharts = {};
      var dirtyTables = {};
      var dirtyKpis = {};
      pairs.forEach(function(p){
        var eq = p.indexOf('=');
        if (eq < 0) return;
        var k = decodeURIComponent(p.slice(0, eq));
        var v = decodeURIComponent(p.slice(eq + 1));
        if (k === 't'){ pendingTab = v; return; }
        if (k.indexOf('f.') === 0){
          var fid = k.slice(2);
          var f = (MANIFEST.filters || []).find(function(x){
            return x && x.id === fid;
          });
          if (!f) return;
          if (f.type === 'multiSelect'){
            filterState[fid] = v ? v.split(',') : [];
          } else if (f.type === 'numberRange'){
            var parts = v.split(',').map(function(s){ return Number(s.trim()); });
            filterState[fid] = parts.length === 2 ? parts : v;
          } else if (f.type === 'toggle' || f.type === 'rule'){
            filterState[fid] = v === 'true' || v === '1';
          } else if (f.type === 'slider' || f.type === 'number'){
            var n = Number(v);
            filterState[fid] = isNaN(n) ? '' : n;
          } else {
            filterState[fid] = v;
          }
          return;
        }
        if (k.indexOf('c.') === 0){
          var rest = k.slice(2);
          var lastDot = rest.lastIndexOf('.');
          if (lastDot < 0) return;
          var cid = rest.slice(0, lastDot);
          var prop = rest.slice(lastDot + 1);
          chartControlState[cid] = chartControlState[cid] || {series: {}};
          if (prop === 't')  chartControlState[cid].transform = v;
          if (prop === 's')  chartControlState[cid].smoothing = Number(v);
          if (prop === 'ys') chartControlState[cid].yScale = v;
          if (prop === 'xs') chartControlState[cid].xScale = v;
          dirtyCharts[cid] = true;
          return;
        }
        if (k.indexOf('tb.') === 0){
          var rest2 = k.slice(3);
          var lastDot2 = rest2.lastIndexOf('.');
          if (lastDot2 < 0) return;
          var tid = rest2.slice(0, lastDot2);
          var prop2 = rest2.slice(lastDot2 + 1);
          TABLE_STATE[tid] = TABLE_STATE[tid] || {};
          if (prop2 === 'sb') TABLE_STATE[tid].sortBy = v;
          if (prop2 === 'sd') TABLE_STATE[tid].sortDir = v;
          if (prop2 === 'q')  TABLE_STATE[tid].search = v;
          dirtyTables[tid] = true;
          return;
        }
        if (k.indexOf('k.') === 0){
          var rest3 = k.slice(2);
          var lastDot3 = rest3.lastIndexOf('.');
          if (lastDot3 < 0) return;
          var kid = rest3.slice(0, lastDot3);
          var prop3 = rest3.slice(lastDot3 + 1);
          KPI_STATE[kid] = KPI_STATE[kid] || {};
          if (prop3 === 'cp') KPI_STATE[kid].comparePeriod = v;
          dirtyKpis[kid] = true;
          return;
        }
        if (k.indexOf('p.') === 0){
          var rest4 = k.slice(2);
          var lastDot4 = rest4.lastIndexOf('.');
          if (lastDot4 < 0) return;
          var pid = rest4.slice(0, lastDot4);
          var prop4 = rest4.slice(lastDot4 + 1);
          PIVOT_STATE[pid] = PIVOT_STATE[pid] || {};
          if (prop4 === 'r') PIVOT_STATE[pid].row = v;
          if (prop4 === 'c') PIVOT_STATE[pid].col = v;
          if (prop4 === 'v') PIVOT_STATE[pid].val = v;
          if (prop4 === 'a') PIVOT_STATE[pid].agg = v;
          return;
        }
      });
      // Apply restored filter state to the inputs
      if (typeof wireFilters === 'function'){
        // wireFilters() is already wired up; we just need the inputs
        // to reflect the restored values. The reset path does that.
        (MANIFEST.filters || []).forEach(function(f){
          var v = filterState[f.id];
          if (v == null) return;
          if (f.type === 'radio'){
            var inputs = document.querySelectorAll(
              'input[name="filter-' + f.id + '"]'
            );
            Array.prototype.forEach.call(inputs, function(r){
              r.checked = String(r.value) === String(v);
            });
            return;
          }
          var el = document.getElementById('filter-' + f.id);
          if (!el) return;
          if (f.type === 'multiSelect' && Array.isArray(v)){
            Array.from(el.options).forEach(function(o){
              o.selected = v.indexOf(o.value) >= 0;
            });
          } else if (f.type === 'toggle' || f.type === 'rule'){
            el.checked = !!v;
          } else if (f.type === 'slider'){
            el.value = v;
            var disp = document.getElementById('filter-' + f.id + '-val');
            if (disp) disp.textContent = v;
          } else {
            el.value = v;
          }
        });
      }
      // Activate restored tab if applicable
      if (pendingTab && typeof activateTab === 'function'){
        activateTab(pendingTab);
      }
      // Re-render charts with restored drawer state
      Object.keys(dirtyCharts).forEach(function(cid){
        if (typeof rerenderChart === 'function') rerenderChart(cid);
      });
      // Re-render tables with restored sort/search
      if (typeof renderTables === 'function') renderTables();
      // Re-render KPIs with restored compare period
      if (typeof renderKpis === 'function') renderKpis();
      // Re-render pivots with restored dropdown state
      if (typeof renderPivots === 'function') renderPivots();
    } catch(e){
      console.warn('[urlstate] restore failed:', e);
    } finally {
      _URL_STATE_LOADING = false;
    }
  }
  window._restoreUrlState = _restoreUrlState;

  // Hook serializer + stat strip refresh to filter state, chart
  // controls, table state, kpi state, and tab activation. We piggyback
  // on broadcast() (already called on every filter change), and tab
  // clicks call activateTab. For the per-tile drawer state we patch
  // rerenderChart so any mutation that triggers a rerender also
  // triggers a hash write + strip refresh.
  if (typeof rerenderChart === 'function'){
    var _origRerender = rerenderChart;
    rerenderChart = function(cid){
      var r = _origRerender.apply(this, arguments);
      try { _renderStatStrip(cid); } catch(e){}
      _serializeUrlState();
      return r;
    };
  }
  // initChart fires once per chart on first activation -- hook the
  // strip there too so the initial paint has the right context line.
  if (typeof initChart === 'function'){
    var _origInit = initChart;
    initChart = function(cid){
      var r = _origInit.apply(this, arguments);
      try { _renderStatStrip(cid); } catch(e){}
      return r;
    };
  }

__SHARE_CONTROLLER__
__USER_INPUT_CONTROLLER__

  // ----- init -----
  window.addEventListener('load', function(){
    wireFilters(); wireTileActions();

    // figure initial tab
    var layout = MANIFEST.layout || {};
    var initialTab = null;
    if (layout.kind === 'tabs' && (layout.tabs || []).length){
      try {
        var saved = localStorage.getItem('echart_dashboard_tab_' + MANIFEST.id);
        if (saved && layout.tabs.some(function(t){ return t.id === saved; })) initialTab = saved;
      } catch(e){}
      initialTab = initialTab || layout.tabs[0].id;
      activateTab(initialTab);
    } else {
      // initialize every chart in the single default tab
      Object.keys(WIDGET_META).forEach(function(id){
        var w = WIDGET_META[id]; if (w.widget === 'chart') initChart(id);
      });
      applyConnects();
    }
    renderKpis(); renderTables();
    if (typeof renderPivots === 'function') renderPivots();
    // Cascading filters: populate downstream options from upstream defaults
    (MANIFEST.filters || []).forEach(function(f){
      if (f.depends_on && f.options_from && typeof _rebuildFilterOptions === 'function'){
        _rebuildFilterOptions(f);
      }
    });
    if (typeof _applyShowWhen === 'function') _applyShowWhen();
    if (typeof _initInitialState === 'function') _initInitialState();
    if (typeof _restoreUrlState === 'function') _restoreUrlState();
    if (typeof initTools === 'function') initTools();
    if (typeof initUserInputs === 'function') initUserInputs();
    window.addEventListener('resize', function(){
      Object.keys(CHARTS).forEach(function(k){
        try { CHARTS[k].inst.resize(); } catch(e){}
      });
      Object.keys(TOOL_CHARTS || {}).forEach(function(k){
        try { TOOL_CHARTS[k].resize(); } catch(e){}
      });
    });
    document.dispatchEvent(new CustomEvent('prism:dashboard:ready', {
      detail: { dashboard: window.DASHBOARD }
    }));
  });

  // ===========================================================================
  // TOOL WIDGET RUNTIME
  // ===========================================================================
  // Runs in-browser. For each `widget: tool` tile in the manifest:
  //   1. Initialize state from PAYLOAD.tools[wid] + initial_inputs.
  //   2. Render the matrix grid (rows × cols editable cells) into the
  //      input panel.
  //   3. Wire input change handlers on every scalar + matrix cell.
  //   4. On any input change: gather current input values, call the
  //      tool def's compute fn, route outputs to their renderers.
  //   5. Compute kind: only `js` is supported in v1. The compute source
  //      is wrapped in a Function() so it runs in the page sandbox.
  //
  // Output kinds routed today:
  //   - `stat` / `param` / `kpi`  -> headline stat cell value update
  //   - `series`                    -> ECharts multi_line / line chart
  //   - `table`                     -> HTML table rebuild
  //   - `distribution`              -> ECharts histogram
  //
  // No bind_from across tool widgets (Phase 6). No server-side compute
  // (compute.kind="python") in v1.

  var TOOLS = (PAYLOAD && PAYLOAD.tools) || {};
  var TOOL_FN_CACHE = {};   // wid -> compiled compute function
  var TOOL_CHARTS   = {};   // tool-output chart instances (keyed by wid+oid)
  var TOOL_STATE    = {};   // wid -> {inputs: {...}}

  function _toolCompileFn(wid, source){
    if (TOOL_FN_CACHE[wid]) return TOOL_FN_CACHE[wid];
    if (!source) return null;
    try {
      // The source string defines `function compute(inputs){...}`.
      // Wrap it so `compute` becomes the return value of the IIFE.
      var fn = new Function(
        '"use strict";\n' +
        source + '\n' +
        'return (typeof compute === "function") ? compute : null;'
      )();
      TOOL_FN_CACHE[wid] = fn;
      return fn;
    } catch (e) {
      console.error('[tool ' + wid + '] compile error:', e);
      return null;
    }
  }

  function _toolHumanFmt(val, decimals){
    if (val == null || isNaN(+val)) return '--';
    var n = +val;
    var d = (decimals == null) ? 2 : (+decimals | 0);
    if (d < 0) d = 0; if (d > __MAX_DEC) d = __MAX_DEC;
    var s = n.toFixed(d);
    // Comma-group integer side
    var parts = s.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return parts.join('.');
  }

  function _toolFmtCell(val, format){
    if (val == null || (typeof val === 'number' && isNaN(val))) return '';
    if (typeof val !== 'number' && isNaN(+val)) return String(val);
    if (typeof format !== 'string') return _toolHumanFmt(val, 2);
    var token = format.split(':')[0];
    var dec   = parseInt(format.split(':')[1], 10);
    if (isNaN(dec)) dec = 2;
    if (dec > __MAX_DEC) dec = __MAX_DEC;
    if (token === 'integer') return _toolHumanFmt(+val, 0);
    if (token === 'percent') return _toolHumanFmt(100 * +val, dec) + '%';
    if (token === 'bps')     return _toolHumanFmt(10000 * +val, dec) + ' bp';
    if (token === 'currency')return '$' + _toolHumanFmt(+val, dec);
    if (token === 'signed') {
      var n = +val; var sign = n > 0 ? '+' : (n < 0 ? '-' : '');
      return sign + _toolHumanFmt(Math.abs(n), dec);
    }
    return _toolHumanFmt(+val, dec);
  }

  function _toolFmtStat(out, val){
    if (val == null) return '--';
    if (typeof val === 'string' && !out.format) return val;
    if (typeof val === 'string' && isNaN(+val)) return val;
    var fmt = out.format || 'number';
    var dec = out.decimals;
    var s;
    if (fmt === 'percent') {
      s = _toolHumanFmt(100 * +val, dec == null ? 2 : dec) + '%';
    } else if (fmt === 'bps') {
      s = _toolHumanFmt(10000 * +val, dec == null ? 1 : dec) + ' bp';
    } else if (fmt === 'currency') {
      s = '$' + _toolHumanFmt(+val, dec == null ? 2 : dec);
    } else if (fmt === 'integer') {
      s = _toolHumanFmt(+val, 0);
    } else {
      s = _toolHumanFmt(+val, dec == null ? 4 : dec);
    }
    var prefix = out.prefix ? String(out.prefix) : '';
    var suffix = out.suffix ? String(out.suffix) : '';
    return prefix + s + suffix;
  }

  function _toolBuildMatrixGrid(tile, wid, inp){
    var iid = inp.id;
    var rows = inp.rows || [];
    var cols = inp.cols || [];
    var cell = inp.cell || {};
    var defVal = (cell.default != null) ? cell.default : 0;
    var step   = (cell.step    != null) ? cell.step    : 1;
    var dec    = (cell.decimals!= null) ? cell.decimals : 0;
    var minA   = (cell.min     != null) ? (' min="'  + cell.min + '"') : '';
    var maxA   = (cell.max     != null) ? (' max="'  + cell.max + '"') : '';
    var stepA  = ' step="' + step + '"';

    // Initial values: take from TOOL_STATE if present, else cell.default.
    var state = TOOL_STATE[wid].inputs[iid];
    if (!state) {
      state = {rows: rows, cols: cols, values: []};
      for (var ri = 0; ri < rows.length; ri++){
        var rowVals = [];
        for (var ci = 0; ci < cols.length; ci++) rowVals.push(defVal);
        state.values.push(rowVals);
      }
      TOOL_STATE[wid].inputs[iid] = state;
    }

    var headCells = ['<th></th>'];
    for (var ci = 0; ci < cols.length; ci++){
      var col = cols[ci];
      headCells.push('<th>' + _he(col.label || col.id) + '</th>');
    }
    var thead = '<thead><tr>' + headCells.join('') + '</tr></thead>';

    var rowsHtml = [];
    for (var ri = 0; ri < rows.length; ri++){
      var row = rows[ri];
      var parts = ['<tr data-row-key="' + _he(String(row.key)) + '">'];
      parts.push('<th title="' + _he(String(row.key)) + '">' +
                 _he(row.label || row.key) + '</th>');
      for (var cj = 0; cj < cols.length; cj++){
        var col2 = cols[cj];
        var v = state.values[ri][cj];
        parts.push(
          '<td><input type="number" data-row-idx="' + ri + '" ' +
          'data-col-idx="' + cj + '" data-col-id="' + _he(col2.id) + '" ' +
          'value="' + (v != null ? v : '') + '"' +
          stepA + minA + maxA + '/></td>'
        );
      }
      parts.push('</tr>');
      rowsHtml.push(parts.join(''));
    }
    var tbody = '<tbody>' + rowsHtml.join('') + '</tbody>';

    var wrap = tile.querySelector('[data-tool-matrix-grid="' + iid + '"]');
    if (!wrap) return;
    wrap.innerHTML = '<table class="tool-matrix-table">' + thead + tbody + '</table>';

    // Highlight non-zero cells.
    _toolMatrixApplyHighlight(wrap);

    // Wire input handlers per cell.
    var ins = wrap.querySelectorAll('input[type=number]');
    for (var k = 0; k < ins.length; k++){
      ins[k].addEventListener('input', function(ev){
        var el = ev.target;
        var ri = parseInt(el.getAttribute('data-row-idx'), 10);
        var ci = parseInt(el.getAttribute('data-col-idx'), 10);
        var raw = el.value;
        var v = (raw === '' ? null : (+raw));
        if (v != null && isNaN(v)) v = null;
        TOOL_STATE[wid].inputs[iid].values[ri][ci] = v == null ? 0 : v;
        if (v == null || v === 0) el.classList.remove('nonzero');
        else el.classList.add('nonzero');
        _toolRunCompute(wid);
      });
    }
  }

  function _toolMatrixApplyHighlight(wrap){
    var ins = wrap.querySelectorAll('input[type=number]');
    for (var i = 0; i < ins.length; i++){
      var v = +ins[i].value;
      if (!isNaN(v) && v !== 0) ins[i].classList.add('nonzero');
      else ins[i].classList.remove('nonzero');
    }
  }

  function _toolWirePasteHandlers(tile, wid){
    // For each matrix input with paste enabled, wire show/hide of the
    // paste pane and parse-on-apply.
    var btns = tile.querySelectorAll('[data-tool-matrix-paste]');
    btns.forEach(function(btn){
      var iid = btn.getAttribute('data-tool-matrix-paste');
      btn.addEventListener('click', function(){
        var pane = tile.querySelector('[data-tool-matrix-paste-pane="' + iid + '"]');
        if (!pane) return;
        var hidden = pane.hasAttribute('hidden');
        if (hidden) {
          pane.removeAttribute('hidden');
          var ta = pane.querySelector('textarea');
          if (ta) { ta.value = ''; ta.focus(); }
        } else {
          pane.setAttribute('hidden', '');
        }
      });
    });

    var cancels = tile.querySelectorAll('[data-tool-matrix-paste-cancel]');
    cancels.forEach(function(b){
      b.addEventListener('click', function(){
        var iid = b.getAttribute('data-tool-matrix-paste-cancel');
        var pane = tile.querySelector('[data-tool-matrix-paste-pane="' + iid + '"]');
        if (pane) pane.setAttribute('hidden', '');
      });
    });

    var applies = tile.querySelectorAll('[data-tool-matrix-paste-apply]');
    applies.forEach(function(b){
      b.addEventListener('click', function(){
        var iid = b.getAttribute('data-tool-matrix-paste-apply');
        var pane = tile.querySelector('[data-tool-matrix-paste-pane="' + iid + '"]');
        if (!pane) return;
        var ta = pane.querySelector('textarea');
        if (!ta) return;
        _toolApplyPasteToMatrix(tile, wid, iid, ta.value);
        pane.setAttribute('hidden', '');
      });
    });

    var clears = tile.querySelectorAll('[data-tool-matrix-clear]');
    clears.forEach(function(b){
      b.addEventListener('click', function(){
        var iid = b.getAttribute('data-tool-matrix-clear');
        var state = TOOL_STATE[wid] && TOOL_STATE[wid].inputs[iid];
        if (!state) return;
        for (var ri = 0; ri < state.values.length; ri++){
          for (var ci = 0; ci < state.values[ri].length; ci++){
            state.values[ri][ci] = 0;
          }
        }
        var wrap = tile.querySelector('[data-tool-matrix-grid="' + iid + '"]');
        if (!wrap) return;
        var ins = wrap.querySelectorAll('input[type=number]');
        for (var k = 0; k < ins.length; k++){
          ins[k].value = 0;
          ins[k].classList.remove('nonzero');
        }
        _toolRunCompute(wid);
      });
    });
  }

  function _toolApplyPasteToMatrix(tile, wid, iid, raw){
    if (typeof raw !== 'string') return;
    var lines = raw.split(/\r?\n/).filter(function(l){ return l.trim().length > 0; });
    var sep = (raw.indexOf('\t') >= 0) ? '\t' : (raw.indexOf(',') >= 0 ? ',' : /\s+/);
    var parsed = lines.map(function(line){
      var parts = (sep instanceof RegExp) ? line.split(sep) : line.split(sep);
      return parts.map(function(s){
        var v = parseFloat(String(s).trim());
        return isNaN(v) ? 0 : v;
      });
    });
    var state = TOOL_STATE[wid].inputs[iid];
    if (!state) return;
    var nrows = state.values.length;
    var ncols = state.values[0] ? state.values[0].length : 0;
    for (var ri = 0; ri < nrows; ri++){
      for (var ci = 0; ci < ncols; ci++){
        var v = (parsed[ri] && parsed[ri][ci] != null) ? parsed[ri][ci] : 0;
        state.values[ri][ci] = v;
      }
    }
    var wrap = tile.querySelector('[data-tool-matrix-grid="' + iid + '"]');
    if (wrap) {
      var ins = wrap.querySelectorAll('input[type=number]');
      for (var k = 0; k < ins.length; k++){
        var rii = parseInt(ins[k].getAttribute('data-row-idx'), 10);
        var cii = parseInt(ins[k].getAttribute('data-col-idx'), 10);
        ins[k].value = state.values[rii][cii];
      }
      _toolMatrixApplyHighlight(wrap);
    }
    _toolRunCompute(wid);
  }

  function _toolWireScalarInputs(tile, wid){
    var rows = tile.querySelectorAll('[data-tool-input-panel="true"] .tool-input-row');
    rows.forEach(function(row){
      var iid = row.getAttribute('data-input-id');
      if (!iid) return;
      // Number / date / text / select / toggle / range:
      var el = row.querySelector(
        'input[type=number], input[type=date], input[type=text], input[type=range], select, input[type=checkbox]'
      );
      if (el) {
        el.addEventListener('input', function(){
          if (el.type === 'range') _toolUpdateRangeDisplay(el);
          _toolOnScalarChange(tile, wid, iid);
        });
        el.addEventListener('change', function(){
          if (el.type === 'range') _toolUpdateRangeDisplay(el);
          _toolOnScalarChange(tile, wid, iid);
        });
        return;
      }
      // Radio:
      var radios = row.querySelectorAll('input[type=radio]');
      radios.forEach(function(r){
        r.addEventListener('change', function(){ _toolOnScalarChange(tile, wid, iid); });
      });
    });
  }

  function _toolFormatRangeDisplay(val, inp){
    if (val == null || val === '') return '';
    var n = +val;
    if (isNaN(n)) return String(val);
    var dec = inp && inp.decimals;
    if (dec == null || dec === '') {
      var step = inp && inp.step;
      if (step != null && step !== '') {
        var stepStr = String(step);
        var dot = stepStr.indexOf('.');
        dec = dot >= 0 ? (stepStr.length - dot - 1) : 0;
      } else {
        dec = 2;
      }
    }
    dec = (+dec | 0);
    if (dec < 0) dec = 0;
    if (dec > __MAX_DEC) dec = __MAX_DEC;
    return _toolHumanFmt(n, dec);
  }

  function _toolUpdateRangeDisplay(el){
    if (!el || el.type !== 'range') return;
    var disp = document.getElementById(el.id + '-val');
    if (!disp) return;
    var wid = el.closest('[data-tool-id]');
    wid = wid ? wid.getAttribute('data-tool-id') : null;
    var inp = null;
    if (wid && TOOLS[wid]){
      var iid = el.closest('.tool-input-row');
      iid = iid ? iid.getAttribute('data-input-id') : null;
      if (iid){
        inp = (TOOLS[wid].def.inputs || []).filter(function(x){
          return x.id === iid;
        })[0];
      }
    }
    disp.textContent = _toolFormatRangeDisplay(el.value, inp);
  }

  function _toolReadScalarValue(tile, inp){
    var iid = inp.id;
    var typ = inp.type || 'number';
    var nid = 'tool-' + tile.getAttribute('data-tool-id') + '-in-' + iid;
    if (typ === 'number' || typ === 'range'){
      var el = document.getElementById(nid);
      if (!el) return inp.default;
      var v = el.value;
      return (v === '' ? null : +v);
    }
    if (typ === 'select' || typ === 'date' || typ === 'text'){
      var el2 = document.getElementById(nid);
      return el2 ? el2.value : inp.default;
    }
    if (typ === 'toggle'){
      var el3 = document.getElementById(nid);
      return el3 ? !!el3.checked : !!inp.default;
    }
    if (typ === 'radio'){
      var rs = tile.querySelectorAll('input[name="' + nid + '"]');
      for (var i = 0; i < rs.length; i++){
        if (rs[i].checked) return rs[i].value;
      }
      return inp.default;
    }
    if (typ === 'list_of_strings'){
      // Not directly user-editable in v1; return def default.
      return inp.default;
    }
    return inp.default;
  }

  function _toolOnScalarChange(tile, wid, iid){
    // Update TOOL_STATE.inputs[iid] from DOM, run show_when on dependents,
    // then recompute.
    var entry = TOOLS[wid];
    if (!entry) return;
    var inp = (entry.def.inputs || []).filter(function(x){ return x.id === iid; })[0];
    if (inp) {
      TOOL_STATE[wid].inputs[iid] = _toolReadScalarValue(tile, inp);
    }
    _toolApplyInputShowWhen(tile, wid);
    _toolRunCompute(wid);
  }

  function _toolApplyInputShowWhen(tile, wid){
    var rows = tile.querySelectorAll('.tool-input-row[data-tool-show-when]');
    rows.forEach(function(row){
      var raw = row.getAttribute('data-tool-show-when');
      try {
        var cond = JSON.parse(raw);
        var hide = false;
        Object.keys(cond).forEach(function(k){
          var expected = cond[k];
          var actual = (TOOL_STATE[wid].inputs || {})[k];
          if (Array.isArray(expected)) {
            if (expected.indexOf(actual) < 0) hide = true;
          } else {
            if (String(actual) !== String(expected)) hide = true;
          }
        });
        if (hide) row.setAttribute('data-hidden', 'true');
        else      row.removeAttribute('data-hidden');
      } catch(e){}
    });
  }

  function _toolGatherInputs(tile, wid){
    var entry = TOOLS[wid];
    if (!entry) return {};
    var out = {};
    (entry.def.inputs || []).forEach(function(inp){
      if (inp.kind === 'matrix'){
        var st = TOOL_STATE[wid].inputs[inp.id];
        if (st) out[inp.id] = st;
      } else {
        var v = _toolReadScalarValue(tile, inp);
        out[inp.id] = v;
        TOOL_STATE[wid].inputs[inp.id] = v;
      }
    });
    return out;
  }

  function _toolRunCompute(wid){
    var entry = TOOLS[wid];
    if (!entry) return;
    var tile = document.querySelector('[data-tool-id="' + wid + '"]');
    if (!tile) return;
    var fn = _toolCompileFn(wid, (entry.def.compute || {}).source);
    if (!fn) return;
    var inputs = _toolGatherInputs(tile, wid);
    try {
      var outputs = fn(inputs) || {};
      _toolHideError(tile);
      _toolRenderOutputs(tile, wid, outputs);
    } catch (e) {
      _toolShowError(tile, e);
    }
  }

  function _toolShowError(tile, e){
    var box = tile.querySelector('.tool-error');
    if (!box) return;
    box.textContent = 'Compute error: ' + (e && e.message ? e.message : String(e));
    box.removeAttribute('hidden');
  }
  function _toolHideError(tile){
    var box = tile.querySelector('.tool-error');
    if (box) box.setAttribute('hidden', '');
  }

  function _toolRenderOutputs(tile, wid, outputs){
    var entry = TOOLS[wid];
    if (!entry) return;
    (entry.def.outputs || []).forEach(function(out){
      var oid = out.id;
      var val = outputs[oid];
      switch (out.kind){
        case 'stat':
        case 'param':
        case 'kpi':
          _toolRenderStat(tile, out, val);
          break;
        case 'table':
          _toolRenderTable(tile, out, val);
          break;
        case 'series':
          _toolRenderSeries(tile, wid, out, val, outputs);
          break;
        case 'distribution':
          _toolRenderDistribution(tile, wid, out, val);
          break;
        case 'stat_grid':
          _toolRenderStatGrid(tile, out, val);
          break;
        default: break;
      }
    });
  }

  function _toolRenderStat(tile, out, val){
    var cell = tile.querySelector(
      '.tool-stat-cell[data-output-id="' + out.id + '"] .value'
    );
    if (!cell) return;
    cell.textContent = _toolFmtStat(out, val);
  }

  function _toolRenderTable(tile, out, val){
    var section = tile.querySelector(
      '[data-output-id="' + out.id + '"][data-output-kind="table"] .tool-output-table-host'
    );
    if (!section) return;
    if (!val) { section.innerHTML = ''; return; }
    var cols, rows;
    if (Array.isArray(val)) {
      // val is the rows array directly; columns must come from def.
      cols = out.columns || [];
      rows = val;
    } else {
      cols = val.columns || out.columns || [];
      rows = val.rows || [];
    }
    var thead = ['<thead><tr>'];
    cols.forEach(function(c){
      thead.push('<th>' + _he(c.label || c.field) + '</th>');
    });
    thead.push('</tr></thead>');
    var tbody = ['<tbody>'];
    rows.forEach(function(r){
      var tr = ['<tr>'];
      cols.forEach(function(c, idx){
        var v = (r && typeof r === 'object' && !Array.isArray(r))
          ? r[c.field]
          : (Array.isArray(r) ? r[idx] : null);
        var cls = idx === 0 ? ' class="first-col"' : '';
        var s;
        if (idx === 0) s = (v == null ? '' : String(v));
        else s = _toolFmtCell(v, c.format);
        tr.push('<td' + cls + '>' + _he(s) + '</td>');
      });
      tr.push('</tr>');
      tbody.push(tr.join(''));
    });
    tbody.push('</tbody>');
    section.innerHTML =
      '<table class="tool-output-table">' + thead.join('') + tbody.join('') + '</table>';
  }

  function _toolShowChartEmpty(host, msg){
    if (!host) return;
    host.innerHTML = '<div class="tool-chart-empty">' + _he(msg) + '</div>';
    var inst = TOOL_CHARTS[host.id];
    if (inst){
      try { inst.dispose(); } catch(e){}
      delete TOOL_CHARTS[host.id];
    }
  }

  function _toolClearChartHost(host){
    if (!host) return;
    if (host.querySelector('.tool-chart-empty')) host.innerHTML = '';
  }

  function _toolInitChart(host){
    var inst = TOOL_CHARTS[host.id];
    if (!inst){
      var theme = MANIFEST.theme;
      try {
        inst = echarts.init(host, (DARK_MODE ? theme + '_dark' : theme), {renderer: 'canvas'});
      } catch (e) {
        inst = echarts.init(host, null, {renderer: 'canvas'});
      }
      TOOL_CHARTS[host.id] = inst;
    }
    return inst;
  }

  function _toolRenderStatGrid(tile, out, val){
    var host = tile.querySelector(
      '[data-output-id="' + out.id + '"] .tool-output-stat-grid-host'
    );
    if (!host) return;
    var stats = Array.isArray(val) ? val : ((val && val.stats) || []);
    if (!stats.length){
      host.innerHTML = '<div class="tool-chart-empty">No stats returned.</div>';
      return;
    }
    var cells = stats.map(function(st){
      var lbl = _he(st.label || st.id || '');
      var v = (st.value != null) ? _toolFmtStat(
        {format: st.format, decimals: st.decimals, prefix: st.prefix, suffix: st.suffix},
        st.value
      ) : '--';
      var sub = st.sub ? ('<div class="label" style="font-weight:400;text-transform:none">' +
                          _he(String(st.sub)) + '</div>') : '';
      return '<div class="tool-stat-cell"><div class="label">' + lbl +
             '</div><div class="value">' + _he(String(v)) + '</div>' + sub + '</div>';
    });
    host.innerHTML = '<div class="tool-output-stat-grid">' + cells.join('') + '</div>';
  }

  function _toolRenderSeries(tile, wid, out, val, allOutputs){
    var hostId = 'tool-' + wid + '-out-' + out.id;
    var host = document.getElementById(hostId);
    if (!host) return;
    if (val == null || val === ''){
      _toolShowChartEmpty(host, 'Compute returned no data for "' + out.id + '".');
      return;
    }
    var rows = Array.isArray(val) ? val : (val.rows || []);
    if (!rows.length){
      var xHint = out.x || out.x_key || 'x';
      var yHint = out.y || out.y_key || 'y';
      _toolShowChartEmpty(
        host,
        'No rows for "' + out.id + '". Expected array of {' + xHint + ', ' + yHint + '} objects.'
      );
      return;
    }
    _toolClearChartHost(host);

    var xKey = out.x || out.x_key || 'x';
    var yKey = out.y || out.y_key || 'y';
    var colorKey = out.color || out.color_key || null;
    var chartType = String(out.chart_type || 'line').toLowerCase();

    // y format
    var yFmt = function(v){
      if (out.y_format === 'percent') return _toolHumanFmt(+v, 2) + '%';
      if (out.y_format === 'bps')     return _toolHumanFmt(10000 * +v, 1) + 'bp';
      return _toolHumanFmt(+v, 2);
    };

    var seriesData = [];
    var opt;

    if (chartType === 'bar' || chartType === 'bar_horizontal'){
      var categories = rows.map(function(r){ return String(r[xKey]); });
      var values = rows.map(function(r){ return r[yKey]; });
      var barSeries = {
        name: out.label || out.id,
        type: 'bar',
        data: values,
        animation: false,
      };
      if (chartType === 'bar_horizontal'){
        opt = {
          grid: {left: 80, right: 24, top: 24, bottom: 24, containLabel: true},
          xAxis: {type: 'value', axisLabel: {formatter: yFmt}},
          yAxis: {type: 'category', data: categories, axisLabel: {hideOverlap: true}},
          tooltip: {trigger: 'axis', valueFormatter: yFmt},
          legend: {show: false},
          animation: false,
          series: [barSeries],
        };
      } else {
        opt = {
          grid: {left: 60, right: 24, top: 24, bottom: 36, containLabel: true},
          xAxis: {type: 'category', data: categories, axisLabel: {hideOverlap: true, rotate: categories.length > 8 ? 35 : 0}},
          yAxis: {type: 'value', axisLabel: {formatter: yFmt}},
          tooltip: {trigger: 'axis', valueFormatter: yFmt},
          legend: {show: false},
          animation: false,
          series: [barSeries],
        };
      }
    } else if (colorKey){
      var groups = {};
      rows.forEach(function(r){
        var c = String(r[colorKey]);
        if (!groups[c]) groups[c] = [];
        groups[c].push([r[xKey], r[yKey]]);
      });
      Object.keys(groups).forEach(function(k){
        seriesData.push({name: k, type: 'line', smooth: false, showSymbol: false,
                          step: 'end', data: groups[k]});
      });
      var xType = (out.x_format === 'date') ? 'time' : (
        (typeof rows[0][xKey] === 'number') ? 'value' : 'category'
      );
      opt = {
        grid: {left: 60, right: 24, top: 30, bottom: 36, containLabel: true},
        xAxis: {type: xType, axisLabel: {hideOverlap: true}},
        yAxis: {type: 'value', axisLabel: {formatter: yFmt}},
        tooltip: {trigger: 'axis', valueFormatter: yFmt},
        legend: (seriesData.length > 1)
          ? {top: 0, type: 'plain', textStyle: {fontSize: 11}}
          : {show: false},
        animation: false,
        series: seriesData,
      };
    } else {
      var data = rows.map(function(r){ return [r[xKey], r[yKey]]; });
      seriesData.push({name: out.label || out.id, type: 'line',
                        smooth: false, showSymbol: false, data: data});
      var xType2 = (out.x_format === 'date') ? 'time' : (
        (typeof rows[0][xKey] === 'number') ? 'value' : 'category'
      );
      opt = {
        grid: {left: 60, right: 24, top: 30, bottom: 36, containLabel: true},
        xAxis: {type: xType2, axisLabel: {hideOverlap: true}},
        yAxis: {type: 'value', axisLabel: {formatter: yFmt}},
        tooltip: {trigger: 'axis', valueFormatter: yFmt},
        legend: {show: false},
        animation: false,
        series: seriesData,
      };
    }

    // Annotations (vline x_from input.something) -> markLine on first series
    var markLines = [];
    var anns = out.annotations || [];
    anns.forEach(function(a){
      if (a.type !== 'vline') return;
      var x;
      if (a.x_from && typeof a.x_from === 'string'){
        var ref = a.x_from.split('.');
        if (ref[0] === 'input' && ref[1]){
          x = (TOOL_STATE[wid].inputs || {})[ref[1]];
        }
      } else if (a.x != null) {
        x = a.x;
      }
      if (x != null && x !== '') {
        markLines.push({xAxis: x, label: {formatter: a.label || ''}});
      }
    });
    if (markLines.length > 0 && opt.series && opt.series[0]) {
      opt.series[0].markLine = {symbol: 'none', silent: true,
                                  lineStyle: {type: 'dashed', color: '#888'},
                                  data: markLines};
    }

    var inst = _toolInitChart(host);
    inst.setOption(opt, true);
    try { inst.resize(); } catch(e){}
  }

  function _toolRenderDistribution(tile, wid, out, val){
    var hostId = 'tool-' + wid + '-out-' + out.id;
    var host = document.getElementById(hostId);
    if (!host) return;
    if (!val){
      _toolShowChartEmpty(host, 'Compute returned no data for "' + out.id + '".');
      return;
    }
    var rows = Array.isArray(val) ? val : (val.rows || []);
    if (!rows.length){
      _toolShowChartEmpty(host, 'No distribution rows for "' + out.id + '".');
      return;
    }
    _toolClearChartHost(host);
    var data = rows.map(function(r){ return [r.x, r.density]; });
    var opt = {
      grid: {left: 50, right: 16, top: 24, bottom: 30, containLabel: true},
      xAxis: {type: 'value'},
      yAxis: {type: 'value'},
      tooltip: {trigger: 'axis'},
      animation: false,
      series: [{type: 'line', step: 'middle', areaStyle: {opacity: 0.18},
                  showSymbol: false, smooth: false, data: data}]
    };
    var inst = _toolInitChart(host);
    inst.setOption(opt, true);
    try { inst.resize(); } catch(e){}
  }

  function _he(s){
    if (s == null) return '';
    return String(s).replace(/[&<>"]/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }

  function initTools(){
    Object.keys(TOOLS).forEach(function(wid){
      var entry = TOOLS[wid];
      if (!entry || entry._error){
        var t = document.querySelector('[data-tool-id="' + wid + '"]');
        if (t) _toolShowError(t, entry && entry._error || 'tool def could not be loaded');
        return;
      }
      TOOL_STATE[wid] = TOOL_STATE[wid] || {inputs: {}};
      // Seed scalar inputs from initial_inputs OR def defaults.
      (entry.def.inputs || []).forEach(function(inp){
        if (inp.kind === 'matrix'){
          // Init below in _toolBuildMatrixGrid which keys off TOOL_STATE.
          // initial_inputs may carry an override.
          if (entry.initial_inputs && entry.initial_inputs[inp.id]){
            TOOL_STATE[wid].inputs[inp.id] = entry.initial_inputs[inp.id];
          }
        } else {
          var v = (entry.initial_inputs && entry.initial_inputs[inp.id] !== undefined)
            ? entry.initial_inputs[inp.id] : inp.default;
          TOOL_STATE[wid].inputs[inp.id] = v;
          // Override DOM default with initial_inputs if provided.
          if (entry.initial_inputs && entry.initial_inputs[inp.id] !== undefined){
            var nid = 'tool-' + wid + '-in-' + inp.id;
            var el = document.getElementById(nid);
            if (el && (inp.type === 'number' || inp.type === 'date' ||
                        inp.type === 'text' || !inp.type)){
              el.value = v;
            } else if (el && inp.type === 'range'){
              el.value = v;
            } else if (el && inp.type === 'toggle'){
              el.checked = !!v;
            } else if (el && inp.type === 'select'){
              el.value = String(v);
            }
          }
          if (inp.type === 'range'){
            var rangeEl = document.getElementById(
              'tool-' + wid + '-in-' + inp.id
            );
            _toolUpdateRangeDisplay(rangeEl);
          }
        }
      });

      var tile = document.querySelector('[data-tool-id="' + wid + '"]');
      if (!tile) return;
      // Build matrix grids
      (entry.def.inputs || []).forEach(function(inp){
        if (inp.kind === 'matrix') _toolBuildMatrixGrid(tile, wid, inp);
      });
      _toolWireScalarInputs(tile, wid);
      _toolWirePasteHandlers(tile, wid);
      _toolApplyInputShowWhen(tile, wid);
      _toolRunCompute(wid);
    });
  }

  window.DASHBOARD = { manifest: MANIFEST, charts: CHARTS,
                        widgets: WIDGET_META,
                        filters: filterState, datasets: currentDatasets,
                        chartControlState: chartControlState,
                        tableState: TABLE_STATE,
                        kpiState: KPI_STATE,
                        pivotState: PIVOT_STATE,
                        specs: SPECS,
                        tools: TOOLS, toolState: TOOL_STATE,
                        toolCharts: TOOL_CHARTS,
                        userInputs: USER_INPUTS,
                        userInputState: USER_INPUT_STATE };
})();
"""
DASHBOARD_APP_JS = DASHBOARD_APP_JS.replace(
    "__SHARE_CONTROLLER__", SHARE_CONTROLLER_JS
)
DASHBOARD_APP_JS = DASHBOARD_APP_JS.replace(
    "__USER_INPUT_CONTROLLER__", USER_INPUT_CONTROLLER_JS
)



# ---------------------------------------------------------------------------
# PYTHON RENDERING
# ---------------------------------------------------------------------------




def _span_style(w: int, cols: int) -> str:
    return f"grid-column: span {max(1, min(w, cols))};"


def _count_rule_leaves(rule: Any) -> int:
    """Total number of leaf clauses in a compound rule tree."""
    if not isinstance(rule, dict):
        return 0
    if isinstance(rule.get("all"), list):
        return sum(_count_rule_leaves(c) for c in rule["all"])
    if isinstance(rule.get("any"), list):
        return sum(_count_rule_leaves(c) for c in rule["any"])
    if rule.get("not") is not None:
        return _count_rule_leaves(rule["not"])
    if "field" in rule:
        return 1
    return 0


def _rule_to_markdown(rule: Any, depth: int = 0) -> str:
    """Render a compound rule tree as nested-bullet markdown for the info popup."""
    if not isinstance(rule, dict):
        return ""
    indent = "  " * depth
    if isinstance(rule.get("all"), list):
        out = [f"{indent}- **AND** all of:"]
        for c in rule["all"]:
            out.append(_rule_to_markdown(c, depth + 1))
        return "\n".join(out)
    if isinstance(rule.get("any"), list):
        out = [f"{indent}- **OR** any of:"]
        for c in rule["any"]:
            out.append(_rule_to_markdown(c, depth + 1))
        return "\n".join(out)
    if rule.get("not") is not None:
        return (f"{indent}- **NOT**\n"
                + _rule_to_markdown(rule["not"], depth + 1))
    if "field" in rule:
        op = rule.get("op", "==")
        val = rule.get("value")
        if op in ("in", "not_in") and isinstance(val, list):
            val_repr = "[" + ", ".join(repr(v) for v in val) + "]"
        else:
            val_repr = repr(val)
        return f"{indent}- `{rule['field']}` `{op}` `{val_repr}`"
    return f"{indent}- _(empty rule node)_"


def _render_filter_controls(filters: List[Dict[str, Any]],
                              *, inline: bool = False,
                              show_reset: bool = True) -> str:
    """Render a list of filter controls as HTML.

    When ``inline=True`` the bar is emitted with the ``tab-filter-bar``
    class (flush with tab content, no full-width border) instead of the
    global ``filter-bar`` chrome. When no filters are supplied an empty
    string is returned so the container can be hidden entirely.
    """
    if not filters:
        return ""
    cls = "tab-filter-bar" if inline else "filter-bar"
    out = [f"<div class=\"{cls}\">"]

    def _label_html(label_text: str, description: Optional[str],
                      popup: Optional[Dict[str, Any]] = None) -> str:
        """Filter label with optional info icon. Hovering shows the
        description as a native tooltip; clicking opens a modal with
        the same text (or the richer ``popup`` body if provided)."""
        if description or popup:
            info = _popup_icon_html(
                info_text=description,
                popup=popup,
                fallback_title=label_text,
                cls="filter-info tile-info",
            )
        else:
            info = ""
        return f'<label>{_html_escape(label_text)}{info}</label>'

    for f in filters:
        fid = f["id"]
        ftype = f.get("type")
        default = f.get("default", "")
        # dateRange filters in their default view-mode set the initial
        # dataZoom window across every chart they target. Charts ship
        # with their own slider + scroll/pinch zoom so the global
        # dropdown is a "default view" knob, not a data filter. Make
        # the label honest about that even when the manifest didn't
        # set one (otherwise PRISM-emitted ids like "dt" or "fs_dt"
        # leak into the UI as cryptic labels).
        is_view_date = (
            ftype == "dateRange"
            and (f.get("mode") or "view") == "view"
        )
        if "label" in f and f["label"] is not None:
            label = f["label"]
        elif is_view_date:
            label = "Initial range"
        else:
            label = fid
        desc = f.get("description") or f.get("help") or f.get("info")
        if is_view_date and not desc:
            desc = (
                "Sets the initial visible window for every time-series "
                "chart on this dashboard. Each chart can also be zoomed "
                "or panned independently using its built-in slider, "
                "scroll wheel, or drag handles."
            )
        lbl = _label_html(label, desc, f.get("popup"))
        if ftype == "dateRange":
            options = ["1M", "3M", "6M", "YTD", "1Y", "2Y", "5Y", "All"]
            display_default = "All" if str(default) == "MAX" else str(default)
            opts_html = "".join(
                f"<option value=\"{o}\""
                f"{' selected' if display_default == o else ''}>{o}</option>"
                for o in options
            )
            extra_cls = " filter-view" if is_view_date else ""
            out.append(
                f"<div class=\"filter-item daterange{extra_cls}\">{lbl}"
                f"<select id=\"filter-{fid}\">{opts_html}</select></div>"
            )
        elif ftype in ("select", "multiSelect"):
            options = f.get("options", [])
            multi = " multiple" if ftype == "multiSelect" else ""
            default_set: set = set()
            if isinstance(default, list):
                default_set = set(
                    str(_default_value_for_compare(d)) for d in default)
            elif default:
                default_set = {str(_default_value_for_compare(default))}
            opt_pairs = [_option_value_label(o) for o in options]
            opts_html = "".join(
                f"<option value=\"{_html_escape(v)}\""
                f"{' selected' if v in default_set else ''}>"
                f"{_html_escape(l)}</option>"
                for v, l in opt_pairs
            )
            out.append(
                f"<div class=\"filter-item\">{lbl}"
                f"<select id=\"filter-{fid}\"{multi}>{opts_html}</select></div>"
            )
        elif ftype == "numberRange":
            out.append(
                f"<div class=\"filter-item\">{lbl}"
                f"<input id=\"filter-{fid}\" type=\"text\" "
                f"value=\"{_html_escape(str(default))}\" "
                f"placeholder=\"min,max\"/>"
                f"</div>"
            )
        elif ftype == "toggle":
            checked = " checked" if default else ""
            out.append(
                f"<div class=\"filter-item\">{lbl}"
                f"<input id=\"filter-{fid}\" type=\"checkbox\"{checked}/></div>"
            )
        elif ftype == "slider":
            mn = f.get("min", 0)
            mx = f.get("max", 100)
            step = f.get("step", 1)
            val = default if default != "" else mn
            out.append(
                f"<div class=\"filter-item slider\">{lbl}"
                f"<div class=\"slider-row\">"
                f"<input id=\"filter-{fid}\" type=\"range\" "
                f"min=\"{mn}\" max=\"{mx}\" step=\"{step}\" value=\"{val}\"/>"
                f"<span id=\"filter-{fid}-val\" class=\"slider-val\">{val}</span>"
                f"</div></div>"
            )
        elif ftype == "radio":
            options = f.get("options", [])
            default_v = str(_default_value_for_compare(default))
            radios: List[str] = []
            for o in options:
                v, l = _option_value_label(o)
                checked = " checked" if v == default_v else ""
                radios.append(
                    f"<label class=\"radio-opt\">"
                    f"<input type=\"radio\" name=\"filter-{fid}\" "
                    f"value=\"{_html_escape(v)}\"{checked}/>"
                    f"{_html_escape(l)}</label>"
                )
            out.append(
                f"<div class=\"filter-item radio-group\">{lbl}"
                f"<div class=\"radio-row\">{''.join(radios)}</div></div>"
            )
        elif ftype == "text":
            placeholder = f.get("placeholder", "Type to search...")
            out.append(
                f"<div class=\"filter-item text\">{lbl}"
                f"<input id=\"filter-{fid}\" type=\"text\" "
                f"value=\"{_html_escape(str(default))}\" "
                f"placeholder=\"{_html_escape(placeholder)}\"/></div>"
            )
        elif ftype == "number":
            mn = f.get("min", None)
            mx = f.get("max", None)
            step = f.get("step", "any")
            extra = ""
            if mn is not None:
                extra += f" min=\"{mn}\""
            if mx is not None:
                extra += f" max=\"{mx}\""
            extra += f" step=\"{step}\""
            out.append(
                f"<div class=\"filter-item number\">{lbl}"
                f"<input id=\"filter-{fid}\" type=\"number\""
                f"{extra} value=\"{_html_escape(str(default))}\"/></div>"
            )
        elif ftype == "rule":
            rule = f.get("rule") or {}
            count = _count_rule_leaves(rule)
            summary = f.get(
                "summary",
                f"{count} condition{'s' if count != 1 else ''}",
            )
            # `default` was harvested from `f.get("default", "")` at the
            # top of the loop, so we must look at the raw key here. The
            # rule filter defaults to ENABLED unless the manifest sets
            # `default: false` explicitly.
            raw_default = f.get("default")
            checked = "" if raw_default is False else " checked"
            # Reuse the existing filter-info popup mechanism for the
            # rule-tree dump (clickable info icon -> markdown modal).
            tree_md = _rule_to_markdown(rule)
            popup = {
                "title": f.get("label") or fid,
                "body": tree_md,
            }
            info_html = _popup_icon_html(
                info_text="Click to view the full rule tree",
                popup=popup,
                fallback_title=f.get("label") or fid,
                cls="filter-info tile-info filter-rule-info",
            )
            out.append(
                f'<div class="filter-item rule">'
                f'<label class="filter-rule-toggle">'
                f'<input type="checkbox" id="filter-{fid}"{checked}/>'
                f'<span class="filter-rule-label">'
                f'{_html_escape(f.get("label") or fid)}</span>'
                f'<span class="filter-rule-summary">'
                f'({_html_escape(summary)})</span>'
                f'{info_html}</label></div>'
            )
    if show_reset:
        reset_id = "filter-reset" if not inline else ""
        reset_attr = f" id=\"{reset_id}\"" if reset_id else ""
        out.append(
            f"<button class=\"icon-btn filter-reset\"{reset_attr}"
            f" data-filter-reset>Reset</button>"
        )
    out.append("</div>")
    return "\n".join(out)


def _table_toolbar_buttons(w: Dict[str, Any]) -> str:
    """Toolbar buttons for a table tile.

    Today the only entry is the controls drawer toggle (three-dots
    glyph) -- mirrors :func:`_chart_toolbar_buttons` so the markup
    and JS wiring stay the same as for chart tiles. Suppressed when
    ``table_controls`` is False on the widget.
    """
    if w.get("table_controls") is False:
        return ""
    controls_btn = (
        '<button class="tile-btn controls" title="Table controls" '
        'data-controls-toggle aria-label="Toggle table controls">'
        '<span class="tile-btn-glyph">&#x22EE;</span></button>'
    )
    return (
        "<div class=\"tile-actions\">"
        + controls_btn
        + "</div>"
    )


def _kpi_toolbar_buttons(w: Dict[str, Any]) -> str:
    """Toolbar buttons for a KPI tile.

    KPIs get the same three-dots affordance as charts and tables when
    they have anything to expose (delta source, sparkline, dataset
    binding for view/download). Suppressed when ``kpi_controls`` is
    False on the widget.
    """
    if w.get("kpi_controls") is False:
        return ""
    controls_btn = (
        '<button class="tile-btn controls" title="KPI controls" '
        'data-controls-toggle aria-label="Toggle KPI controls">'
        '<span class="tile-btn-glyph">&#x22EE;</span></button>'
    )
    return (
        "<div class=\"tile-actions\">"
        + controls_btn
        + "</div>"
    )


def _chart_toolbar_buttons(w: Dict[str, Any]) -> str:
    """Toolbar buttons for a chart tile.

    Layout (left -> right):

      1. any custom ``action_buttons`` the widget defines
      2. controls drawer toggle (three-dots glyph) -- rightmost

    Each ``action_buttons`` entry is a dict ``{label, onclick?, href?,
    icon?, title?}``. ``onclick`` names a global JS function (wired
    via ``window.<name>``); ``href`` opens a new tab. Unknown entries
    are skipped.

    Setting ``spec.chart_controls = False`` (or the same on the widget)
    suppresses the controls drawer toggle. Bulk PNG export is handled
    by the dashboard-level Download dropdown's "Charts" item.
    """
    extra: List[str] = []
    for btn in w.get("action_buttons") or []:
        if not isinstance(btn, dict):
            continue
        label = _html_escape(btn.get("label", ""))
        if not label and btn.get("icon"):
            label = _html_escape(btn["icon"])
        title = _html_escape(btn.get("title", btn.get("label", "")))
        cls = "tile-btn tile-btn-custom"
        if btn.get("primary"):
            cls += " primary"
        onclick = btn.get("onclick")
        href = btn.get("href")
        if href:
            target = ' target="_blank" rel="noopener"'
            extra.append(
                f'<a class="{cls}" href="{_html_escape(href)}"'
                f' title="{title}"{target}>{label}</a>'
            )
        elif onclick:
            js = (f'(window.{onclick} && window.{onclick}'
                   f'("{_html_escape(w.get("id", ""))}"))')
            extra.append(
                f'<button class="{cls}" title="{title}" '
                f'onclick=\'{js}\'>{label}</button>'
            )
        else:
            extra.append(
                f'<button class="{cls}" title="{title}" disabled>'
                f'{label}</button>'
            )
    # The stat-strip button opens the auto-computed context strip
    # (current value, deltas at standard horizons, range, percentile
    # rank) in a popup modal. We do NOT render the strip inline --
    # it was too cluttering when stacked above every chart. The
    # eligible chart types live in the central
    # ``STAT_STRIP_ELIGIBLE_CHART_TYPES`` set on the dashboard side
    # (line / multi_line / area today). The eligibility check is
    # purely client-side; we gate the button server-side so it
    # doesn't render on chart_types that wouldn't have stats anyway.
    from echart_dashboard import STAT_STRIP_ELIGIBLE_CHART_TYPES
    show_stat_strip = True
    spec = w.get("spec") if isinstance(w.get("spec"), dict) else {}
    if spec.get("stat_strip") is False:
        show_stat_strip = False
    if w.get("stat_strip") is False:
        show_stat_strip = False
    chart_type = (spec.get("chart_type") if isinstance(spec, dict) else None)
    if chart_type not in STAT_STRIP_ELIGIBLE_CHART_TYPES:
        show_stat_strip = False
    stat_strip_btn = (
        '<button class="tile-btn stat-strip-btn" '
        'title="Show stats: current / deltas / range / percentile" '
        'data-stat-strip-toggle aria-label="Open stats popup">'
        '<span class="tile-btn-glyph">&Sigma;</span></button>'
        if show_stat_strip else ""
    )
    # The "Controls" button toggles the per-chart controls drawer
    # below the title. The drawer is populated lazily in JS at chart
    # init time so it can introspect the lowered option (chart_type,
    # series, axes) and only render the knobs that apply to this
    # chart shape. The button is suppressed when ``chart_controls``
    # is explicitly disabled on the spec.
    show_controls = True
    if spec.get("chart_controls") is False:
        show_controls = False
    if w.get("chart_controls") is False:
        show_controls = False
    controls_btn = (
        '<button class="tile-btn controls" title="Chart controls" '
        'data-controls-toggle aria-label="Toggle chart controls">'
        '<span class="tile-btn-glyph">&#x22EE;</span></button>'
        if show_controls else ""
    )
    # Toolbar order: custom action_buttons, stats popup button,
    # then the controls drawer toggle (rightmost). The dashboard-level
    # Download dropdown's "Charts" item covers PNG export for the whole
    # dashboard; per-tile PNG download was redundant and removed.
    return (
        "<div class=\"tile-actions\">"
        + "".join(extra)
        + stat_strip_btn
        + controls_btn
        + "</div>"
    )


def _tile_title_html(w: Dict[str, Any]) -> str:
    """Compose the inner title text for a tile header, including an
    optional info icon, compact badge, and subtitle.

      * ``info``     -- short hover tooltip. Clicking the \u24D8 icon
                         also opens a modal with the same text (so long
                         blurbs are readable and dismissable).
      * ``popup``    -- {title, body} (body is markdown). Takes priority
                         over `info` as the modal content; `info` is
                         still used as the native hover tooltip.
      * ``badge``    -- short pill (e.g. "LIVE", "BETA"); pair with
                         ``badge_color`` to pick the hue.
      * ``subtitle`` -- secondary text rendered on the line below the
                         title, italic, small.
    """
    title = _html_escape(w.get("title", ""))
    info = w.get("info")
    popup = w.get("popup")
    badge = w.get("badge")
    subtitle = w.get("subtitle")
    parts = ['<div class="tile-title-wrap">']
    parts.append(f'<div class="tile-title">{title}')
    if info or popup:
        icon_html = _popup_icon_html(
            info_text=info,
            popup=popup,
            fallback_title=w.get("title"),
        )
        parts.append(icon_html)
    if badge:
        color = w.get("badge_color") or "gs-navy"
        parts.append(
            f'<span class="tile-badge" data-color="{_html_escape(color)}">'
            f'{_html_escape(str(badge))}</span>'
        )
    parts.append("</div>")
    if subtitle:
        parts.append(
            f'<div class="tile-subtitle">{_html_escape(str(subtitle))}</div>'
        )
    parts.append("</div>")
    return "".join(parts)


def _popup_icon_html(info_text: Optional[str] = None,
                      popup: Optional[Dict[str, Any]] = None,
                      fallback_title: Optional[str] = None,
                      cls: str = "tile-info") -> str:
    """Render a clickable \u24D8 icon that opens a modal popup.

    Click behaviour takes priority:
      1. ``popup = {title, body}`` -- modal with that content
      2. otherwise ``info`` -- modal with just that text
    Hover shows the ``info`` text natively via the ``title=`` attr.
    """
    hover_title = ""
    modal_title = ""
    modal_body = ""
    if isinstance(popup, dict):
        modal_title = str(popup.get("title", fallback_title or ""))
        modal_body = str(popup.get("body", info_text or ""))
        hover_title = modal_title or info_text or ""
    elif info_text:
        hover_title = str(info_text)
        modal_title = fallback_title or ""
        modal_body = str(info_text)
    title_attr = (f' title="{_html_escape(hover_title)}"'
                   if hover_title else "")
    return (
        f'<span class="{cls}" tabindex="0" role="button"'
        f' aria-label="More info"'
        f'{title_attr}'
        f' data-popup-title="{_html_escape(modal_title)}"'
        f' data-popup-body="{_html_escape(modal_body)}"'
        f'>\u24D8</span>'
    )


def _tile_class(w: Dict[str, Any], base: str) -> str:
    """Base CSS classes for any tile, honoring widget-level flags."""
    cls = base
    if w.get("emphasis") or w.get("emphasized"):
        cls += " tile-emphasis"
    if w.get("pinned"):
        cls += " tile-pinned"
    if w.get("hero"):
        cls += " tile-hero"
    return cls


def _tile_footer_html(w: Dict[str, Any]) -> str:
    foot = w.get("footer") or w.get("footnote")
    if not foot:
        return ""
    return f'<div class="tile-footer">{_html_escape(str(foot))}</div>'


# =============================================================================
# WIDGET RENDER REGISTRY
# =============================================================================
#
# Each widget kind has one ``_render_<kind>_widget(w, cols, wid, style)``
# function below. ``_RENDERERS`` is the dispatch table. Adding a new
# widget kind = one render function + one entry in ``_RENDERERS`` +
# (separately) one entry in ``echart_dashboard.WIDGETS`` for validation
# and one entry in ``dashboards/widgets.md#widget-kinds`` for the catalog.
#
# The ``_RENDERERS`` keys must match ``echart_dashboard.VALID_WIDGETS``
# byte-for-byte; a drift-prevention test in ``dev/tests.py`` asserts
# this. Today both dispatch tables cover the same set of widget kinds.


# Note kinds keyed by their human-readable label.
# ``NOTE_KINDS`` is owned by ``echart_dashboard`` (the schema /
# validator layer); we import it here lazily inside the renderer to
# avoid a module-load cycle (echart_dashboard imports from rendering
# at module load, so rendering cannot do the reverse at module-level).


def _render_chart_widget(w: Dict[str, Any], cols: int,
                          wid: str, style: str) -> str:
    # Layout-aware default height: 3-up chart tiles (w=cols//3) sit
    # at ~1/3 of the viewport width, so 360px keeps the aspect ratio
    # readable; 2-up tiles (w=cols//2) sit at ~1/2 viewport width and
    # need 400px to avoid the squashed-ribbon look (where slope-zero
    # white space dominates the canvas). The validator rejects any
    # other chart width, so widget-width falls into one of these two
    # buckets in practice. The same w-default (cols//2) is used here
    # as in the validator -- an omitted w is legal and tile-sized
    # for 2-up. Authors can still override with explicit h_px.
    wval = w.get("w", cols if w.get("hero") else cols // 2)
    default_h = (
        500 if w.get("hero")
        else 400 if isinstance(wval, int) and wval >= cols // 2
        else 360
    )
    height = int(w.get("h_px", default_h))
    cls = _tile_class(w, "tile chart-tile")
    # The controls drawer container is always emitted; the JS
    # populates it lazily on first toggle and the CSS hides it
    # by default. We tag it with the widget id so click handlers
    # can route directly. Suppressed when chart_controls is off
    # (skip the empty container so the layout is unchanged).
    spec_obj = w.get("spec") if isinstance(w.get("spec"), dict) else {}
    controls_off = (
        spec_obj.get("chart_controls") is False
        or w.get("chart_controls") is False
    )
    controls_div = (
        f"  <div class=\"chart-controls\" "
        f"id=\"controls-{_html_escape(wid)}\" "
        f"data-chart-id=\"{_html_escape(wid)}\" "
        f"data-open=\"false\" "
        f"data-populated=\"false\"></div>\n"
        if not controls_off else ""
    )
    # Studio charts get a stats strip below the canvas. The runtime
    # populates it from the bundle stashed by _ccApplyStudio after
    # every materializeOption() call. Hidden for non-studio charts
    # (the element is omitted entirely).
    is_studio = (spec_obj.get("chart_type") == "scatter_studio")
    studio_cfg = (
        isinstance(spec_obj.get("studio"), dict)
        and spec_obj["studio"]
    ) or {}
    show_stats_strip = (
        is_studio and studio_cfg.get("show_stats", True) is not False
    )
    stats_strip_div = (
        f"    <div class=\"tile-stats-strip\" "
        f"id=\"stats-{_html_escape(wid)}\"></div>\n"
        if show_stats_strip else ""
    )
    # Auto-computed stat strip for time-series chart types. We don't
    # render an inline strip (too cluttering); instead we emit a small
    # toolbar button that opens the strip in a popup modal. The marker
    # attribute below tags this tile as stat-strip-eligible so the JS
    # lazy-renders the modal body only when the user clicks. Suppress
    # with `stat_strip: false`.
    ss_off = (
        spec_obj.get("stat_strip") is False
        or w.get("stat_strip") is False
    )
    stat_strip_eligible_attr = (
        ' data-stat-strip-eligible="true"' if not ss_off else ""
    )
    return (
        f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
        f"style=\"{style}\">"
        f"  <div class=\"tile-header\">"
        f"    {_tile_title_html(w)}"
        f"    {_chart_toolbar_buttons(w)}"
        f"  </div>"
        f"{controls_div}"
        f"  <div class=\"tile-body\">"
        f"    <div id=\"chart-{_html_escape(wid)}\" class=\"chart-div\" "
        f"style=\"height:{height}px\"{stat_strip_eligible_attr}></div>"
        f"{stats_strip_div}"
        f"  </div>"
        f"  {_tile_footer_html(w)}"
        f"</div>"
    )


def _render_kpi_widget(w: Dict[str, Any], cols: int,
                        wid: str, style: str) -> str:
    label = w.get("label", "")
    val = w.get("value", "--")
    sub = w.get("sub", "")
    has_sparkline = bool(w.get("sparkline_source"))
    sub_html = (f'<div class="kpi-sub">{_html_escape(sub)}</div>'
                 if sub else "")
    sparkline_html = ('<div class="kpi-sparkline"></div>'
                       if has_sparkline else "")
    info_html = ""
    if w.get("info") or w.get("popup"):
        info_html = _popup_icon_html(
            info_text=w.get("info"),
            popup=w.get("popup"),
            fallback_title=w.get("label", w.get("title", "")),
            cls="tile-info tile-info-kpi",
        )
    cls = _tile_class(w, "tile kpi-tile")
    kpi_toolbar = _kpi_toolbar_buttons(w)
    controls_off = w.get("kpi_controls") is False
    controls_div = (
        f'<div class="chart-controls kpi-controls" '
        f'id="controls-{_html_escape(wid)}" '
        f'data-kpi-id="{_html_escape(wid)}" '
        f'data-open="false" data-populated="false"></div>'
        if not controls_off else ""
    )
    return (
        f"<div class=\"{cls}\" id=\"kpi-{_html_escape(wid)}\" "
        f"data-tile-id=\"{_html_escape(wid)}\" style=\"{style}\">"
        f"<div class=\"kpi-header\">"
        f"<div class=\"kpi-label\">{_html_escape(label)}{info_html}</div>"
        f"{kpi_toolbar}"
        f"</div>"
        f"{controls_div}"
        f"<div class=\"kpi-value\">{_html_escape(val)}</div>"
        f"<div class=\"kpi-delta\" style=\"display:none\"></div>"
        f"{sub_html}"
        f"{sparkline_html}"
        f"{_tile_footer_html(w)}"
        f"</div>"
    )


def _render_table_widget(w: Dict[str, Any], cols: int,
                          wid: str, style: str) -> str:
    cls = _tile_class(
        w,
        "tile table-tile data-grid-tile"
        if w.get("widget") == "data_grid" else "tile table-tile",
    )
    # Tables get the same controls drawer pattern as charts. Off by
    # default for legacy parity; opt out per widget via
    # `table_controls: false` (matches `chart_controls: false`).
    controls_off = w.get("table_controls") is False
    toolbar_html = (
        _table_toolbar_buttons(w) if not controls_off else ""
    )
    controls_div = (
        f"  <div class=\"chart-controls\" "
        f"id=\"controls-{_html_escape(wid)}\" "
        f"data-table-id=\"{_html_escape(wid)}\" "
        f"data-open=\"false\" "
        f"data-populated=\"false\"></div>\n"
        if not controls_off else ""
    )
    return (
        f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
        f"style=\"{style}\">"
        f"  <div class=\"tile-header\">"
        f"    {_tile_title_html(w)}"
        f"    {toolbar_html}"
        f"  </div>"
        f"{controls_div}"
        f"  <div class=\"tile-body\" id=\"table-{_html_escape(wid)}\"></div>"
        f"  {_tile_footer_html(w)}"
        f"</div>"
    )


def _render_pivot_widget(w: Dict[str, Any], cols: int,
                          wid: str, style: str) -> str:
    cls = _tile_class(w, "tile pivot-tile")
    return (
        f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
        f"data-pivot-id=\"{_html_escape(wid)}\" "
        f"style=\"{style}\">"
        f"  <div class=\"tile-header\">"
        f"    {_tile_title_html(w)}"
        f"  </div>"
        f"  <div class=\"pivot-controls\" "
        f"id=\"pivot-controls-{_html_escape(wid)}\"></div>"
        f"  <div class=\"tile-body pivot-body\" "
        f"id=\"pivot-{_html_escape(wid)}\"></div>"
        f"  {_tile_footer_html(w)}"
        f"</div>"
    )


def _render_markdown_widget(w: Dict[str, Any], cols: int,
                              wid: str, style: str) -> str:
    """Render a markdown widget. When ``kind`` is set, render as a
    semantic note card (tinted, coloured left-edge stripe, kind label
    in the head); otherwise render as transparent prose.

    The merged markdown/note widget accepts both ``content`` and
    ``body`` field names for the markdown text.
    """
    body_md = w.get("body") if w.get("body") is not None else w.get("content", "")
    body_html = _render_md(body_md or "")
    kind = w.get("kind")
    if kind:
        # Semantic callout: tinted card with a coloured left-edge
        # stripe keyed by `kind` so the reader can scan for "this is
        # the thesis" / "this is a risk" without reading prose.
        from echart_dashboard import NOTE_KINDS as _NOTE_KIND_LABELS
        kind_str = str(kind)
        title = w.get("title")
        icon = w.get("icon")
        cls = _tile_class(w, f"tile note-tile note-tile-{kind_str}")
        kind_label = _NOTE_KIND_LABELS.get(kind_str, kind_str.capitalize())
        head_parts: List[str] = []
        if icon:
            head_parts.append(
                f'<span class="note-icon">{_html_escape(str(icon))}</span>'
            )
        head_parts.append(
            f'<span class="note-kind">{_html_escape(kind_label)}</span>'
        )
        if title:
            head_parts.append(
                f'<span class="note-title">{_html_escape(str(title))}</span>'
            )
        head_html = (
            f'<div class="note-head">{"".join(head_parts)}</div>'
        )
        return (
            f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
            f"data-note-kind=\"{_html_escape(kind_str)}\" "
            f"style=\"{style}\">"
            f"{head_html}"
            f"<div class=\"note-body markdown-body\">{body_html}</div>"
            f"{_tile_footer_html(w)}"
            f"</div>"
        )
    # Plain markdown: transparent prose, no card chrome.
    cls = _tile_class(w, "tile markdown-tile")
    return (
        f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
        f"style=\"{style}\">"
        f"  <div class=\"tile-body markdown-body\">{body_html}</div>"
        f"  {_tile_footer_html(w)}"
        f"</div>"
    )


def _render_note_widget(w: Dict[str, Any], cols: int,
                          wid: str, style: str) -> str:
    """Render a note widget. Alias for the markdown widget with an
    implicit ``kind`` of ``"insight"`` when none is specified.

    Kept as a back-compat alias so persisted manifests written under
    the old two-widget contract still render cleanly. New manifests
    should use ``widget: "markdown"`` with an explicit ``kind`` (the
    structural surface is the same; one widget kind, one schema).
    """
    if w.get("kind") is None:
        w = dict(w)
        w["kind"] = "insight"
    return _render_markdown_widget(w, cols, wid, style)


def _render_divider_widget(w: Dict[str, Any], cols: int,
                             wid: str, style: str) -> str:
    return (
        f"<div class=\"tile divider-tile\" "
        f"data-tile-id=\"{_html_escape(wid)}\" "
        f"style=\"{_span_style(cols, cols)};grid-column:1/-1\">"
        f"<hr/></div>"
    )


def _render_stat_grid_widget(w: Dict[str, Any], cols: int,
                               wid: str, style: str) -> str:
    stats = w.get("stats", [])
    # CC1 in the 2026-05-11 audit: honor an explicit ``cols`` kwarg
    # on the widget. The CSS default is auto-fit minmax(140px, 1fr)
    # which optimizes for visual density. When the author provides a
    # specific column count (e.g. cols=6 for a 4x6 grid of 24 stats),
    # the widget should respect it. Inline style overrides the CSS.
    grid_cols = w.get("cols")
    grid_style = ""
    if isinstance(grid_cols, int) and grid_cols > 0:
        grid_style = (
            f' style="grid-template-columns: '
            f'repeat({int(grid_cols)}, minmax(0, 1fr));"'
        )
    cells: List[str] = []
    for st in stats:
        lbl = _html_escape(st.get("label", ""))
        val = _html_escape(st.get("value", "--"))
        sub = st.get("sub", "")
        sub_html = (f'<div class="stat-sub">{_html_escape(sub)}</div>'
                      if sub else "")
        info = st.get("info") or st.get("description")
        stat_popup = st.get("popup")
        info_html = (
            _popup_icon_html(
                info_text=info,
                popup=stat_popup,
                fallback_title=st.get("label", ""),
                cls="tile-info stat-info",
            )
            if info or stat_popup else ""
        )
        trend = st.get("trend")
        trend_cls = "pos" if trend and trend > 0 else (
            "neg" if trend and trend < 0 else "flat"
        )
        trend_arrow = (
            "\u25B2" if trend and trend > 0 else (
                "\u25BC" if trend and trend < 0 else ""
            )
        )
        trend_html = (
            f'<span class="stat-trend {trend_cls}">{trend_arrow}</span>'
            if trend is not None and trend != 0 else ""
        )
        cell_tip = (f' title="{_html_escape(str(info))}"'
                      if info else "")
        cells.append(
            f'<div class="stat-cell"'
            f' data-stat-id="{_html_escape(st.get("id", ""))}"'
            f'{cell_tip}>'
            f'<div class="stat-label">{lbl}{info_html}</div>'
            f'<div class="stat-value">{trend_html}{val}</div>'
            f'{sub_html}</div>'
        )
    cls = _tile_class(w, "tile stat-grid-tile")
    return (
        f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
        f"style=\"{style}\">"
        f"  <div class=\"tile-header\">"
        f"    {_tile_title_html(w)}"
        f"  </div>"
        f"  <div class=\"tile-body\">"
        f"    <div class=\"stat-grid\" "
        f"id=\"stat-grid-{_html_escape(wid)}\"{grid_style}>"
        f"{''.join(cells)}</div>"
        f"  </div>"
        f"  {_tile_footer_html(w)}"
        f"</div>"
    )


def _render_image_widget(w: Dict[str, Any], cols: int,
                           wid: str, style: str) -> str:
    title = w.get("title", "")
    src = w.get("src") or w.get("url") or ""
    alt = _html_escape(w.get("alt", title))
    link = w.get("link")
    img_html = (
        f'<img src="{_html_escape(src)}" alt="{alt}" '
        f'loading="lazy"/>'
    )
    if link:
        img_html = (
            f'<a href="{_html_escape(link)}" target="_blank" '
            f'rel="noopener noreferrer">{img_html}</a>'
        )
    header_html = (
        f"<div class=\"tile-header\">{_tile_title_html(w)}</div>"
        if title else ""
    )
    cls = _tile_class(w, "tile image-tile")
    return (
        f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
        f"style=\"{style}\">"
        f"{header_html}"
        f"<div class=\"tile-body\">{img_html}</div>"
        f"{_tile_footer_html(w)}"
        f"</div>"
    )


def _render_user_input_widget(w: Dict[str, Any], cols: int,
                              wid: str, style: str) -> str:
    mode = str(w.get("mode") or "")
    description = w.get("description")
    description_html = (
        f'<div class="user-input-description">'
        f'{_html_escape(str(description))}</div>'
        if description else ""
    )
    cls = _tile_class(w, "tile user-input-tile")
    return (
        f'<div class="{cls}" data-tile-id="{_html_escape(wid)}" '
        f'data-user-input-id="{_html_escape(wid)}" '
        f'data-user-input-mode="{_html_escape(mode)}" '
        f'data-user-input-state="idle" style="{style}">'
        f'  <div class="tile-header">'
        f'    {_tile_title_html(w)}'
        f'    <span class="user-input-access" '
        f'data-user-input-access hidden></span>'
        f'  </div>'
        f'  {description_html}'
        f'  <div class="user-input-body">'
        f'    <div data-user-input-content></div>'
        f'    <div class="user-input-status" '
        f'data-user-input-status aria-live="polite">Not loaded</div>'
        f'  </div>'
        f'  {_tile_footer_html(w)}'
        f'</div>'
    )


# Render dispatch table. Keys MUST match ``echart_dashboard.VALID_WIDGETS``;
# the validator-side registry (``echart_dashboard.WIDGETS``) is the
# canonical source for "what widget kinds exist". This mirror is the
# render side; ``test_render_registry_covers_valid_widgets`` in
# ``dev/tests.py`` asserts the two stay in sync.
_RENDERERS: Dict[str, Any] = {
    "chart":     _render_chart_widget,
    "kpi":       _render_kpi_widget,
    "table":     _render_table_widget,
    "data_grid": _render_table_widget,
    "pivot":     _render_pivot_widget,
    "markdown":  _render_markdown_widget,
    "note":      _render_note_widget,
    "divider":   _render_divider_widget,
    "stat_grid": _render_stat_grid_widget,
    "image":     _render_image_widget,
    "user_input": _render_user_input_widget,
    # `tool` is registered later in this module after _render_tool_widget
    # is defined; see the explicit assignment below the
    # _render_tool_widget definition.
}


def _render_widget(w: Dict[str, Any], cols: int) -> str:
    """Dispatch a widget dict to its renderer.

    All per-widget render logic lives in module-level
    ``_render_<kind>_widget`` functions; this dispatcher just looks up
    the kind in ``_RENDERERS``. Adding a new widget kind = one render
    function + one entry in ``_RENDERERS`` (and the matching entry in
    ``echart_dashboard.WIDGETS`` for validation).
    """
    wt = w.get("widget")
    width = w.get(
        "w",
        cols if wt != "chart" or w.get("hero") else cols // 2,
    )
    wid = w.get("id") or f"w_{id(w)}"
    style = _span_style(width, cols)
    renderer = _RENDERERS.get(wt)
    if renderer is None:
        return ""
    return renderer(w, cols, wid, style)


def _resolve_tool_for_render(w: Dict[str, Any],
                                manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Build the runtime payload entry for a tool widget.

    Resolves the `tool_def` ref (string or dict) to an inline def, then
    materialises every matrix input's `rows_from` against the manifest's
    datasets so the runtime gets a concrete row list. Returns a dict
    suitable for embedding as ``PAYLOAD.tools[wid]``.
    """
    from echart_dashboard import load_tool_def
    ref = w.get("tool_def")
    tdef = load_tool_def(ref) if ref is not None else {}
    inputs_init: Dict[str, Any] = w.get("inputs", {}) or {}

    datasets = manifest.get("datasets", {}) or {}

    def _materialise_matrix(inp: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(inp)
        rows_from = inp.get("rows_from")
        if isinstance(rows_from, dict):
            ds_name = rows_from.get("dataset")
            key_col = rows_from.get("key_col")
            label_col = rows_from.get("label_col")
            ds = datasets.get(ds_name)
            source = (ds.get("source") if isinstance(ds, dict) else ds)
            try:
                source_list = df_to_source(source) if source is not None else None
            except Exception:
                source_list = None
            rows: List[Dict[str, Any]] = []
            if source_list and len(source_list) > 1:
                header = source_list[0]
                if key_col in header:
                    ki = header.index(key_col)
                    li = header.index(label_col) if label_col in header else ki
                    for r in source_list[1:]:
                        if not isinstance(r, list) or ki >= len(r):
                            continue
                        key_v = r[ki]
                        if key_v is None:
                            continue
                        rows.append({
                            "key":   _scalarize(key_v),
                            "label": _scalarize(r[li]) if li < len(r) else _scalarize(key_v),
                        })
            out["rows"] = rows
        elif isinstance(inp.get("rows"), list):
            out["rows"] = list(inp["rows"])
        else:
            out["rows"] = []
        return out

    resolved_inputs: List[Dict[str, Any]] = []
    for inp in tdef.get("inputs", []) or []:
        if not isinstance(inp, dict):
            continue
        kind = inp.get("kind", "scalar")
        if kind == "matrix":
            resolved_inputs.append(_materialise_matrix(inp))
        else:
            resolved_inputs.append(dict(inp))

    return {
        "def": {
            "name":        tdef.get("name"),
            "title":       tdef.get("title", w.get("title")),
            "description": tdef.get("description"),
            "compute":     tdef.get("compute", {}),
            "inputs":      resolved_inputs,
            "outputs":     tdef.get("outputs", []),
            "display":     tdef.get("display", {}),
        },
        "initial_inputs": inputs_init,
    }


def _df_to_source_local(source: Any) -> List[List[Any]]:
    """Tiny shim around echart_dashboard.df_to_source for the render path."""
    from echart_dashboard import df_to_source as _f
    return _f(source)


# Re-bind locally so the local helper above can call it without circular
# import noise inside _resolve_tool_for_render.
df_to_source = _df_to_source_local  # type: ignore


def _scalarize(v: Any) -> Any:
    """Mirror of echart_dashboard._scalarize for compile-time JSON safety."""
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            pass
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    return v


def _render_tool_widget(w: Dict[str, Any], cols: int, wid: str, style: str) -> str:
    """Render a single tool widget tile.

    The tile body is split into an `input panel` (left) and an `output
    panel` (right) when the widget is wide enough; otherwise stacked.
    Each input is a row with a label + control; the matrix input renders
    as a sticky-headered editable table with a paste-from-Excel toggle.
    Outputs render placeholders that the runtime fills in on every
    compute pass.
    """
    cls = _tile_class(w, "tile tool-tile")
    width = int(w.get("w", cols))
    if width < 8:
        cls += " tool-stacked"

    # We need the resolved def to figure out input/output structure.
    # Resolution may fail (validator catches errors); fall back to an
    # empty shell so the renderer never raises.
    try:
        from echart_dashboard import load_tool_def
        ref = w.get("tool_def")
        tdef = load_tool_def(ref) if ref is not None else {}
    except Exception:
        tdef = {}

    inputs_html = []
    for inp in tdef.get("inputs", []) or []:
        if not isinstance(inp, dict):
            continue
        kind = inp.get("kind", "scalar")
        if kind == "matrix":
            inputs_html.append(_render_tool_matrix_input(inp, wid))
        else:
            inputs_html.append(_render_tool_scalar_input(inp, wid))
    inputs_panel_html = "".join(inputs_html)

    outputs_html = []
    headline_ids = (tdef.get("display", {}) or {}).get("headline_stats")
    headline_outs = []
    other_outs = []
    for out in tdef.get("outputs", []) or []:
        if not isinstance(out, dict):
            continue
        oid = out.get("id")
        if headline_ids and oid in headline_ids:
            headline_outs.append(out)
        else:
            other_outs.append(out)
    if not headline_ids:
        # default: every "stat" / "param" / "kpi" output goes in headline
        headline_outs = [o for o in (tdef.get("outputs") or [])
                         if o.get("kind") in ("stat", "param", "kpi")]
        other_outs   = [o for o in (tdef.get("outputs") or [])
                         if o.get("kind") not in ("stat", "param", "kpi")]

    if headline_outs:
        cells = []
        for out in headline_outs:
            cells.append(
                f'<div class="tool-stat-cell" data-output-id="{_html_escape(out.get("id",""))}">'
                f'<div class="label">{_html_escape(out.get("label", out.get("id","")))}</div>'
                f'<div class="value">--</div>'
                f'</div>'
            )
        outputs_html.append(
            f'<div class="tool-output-stats" data-output-stats="true">'
            f'{"".join(cells)}</div>'
        )

    for out in other_outs:
        oid = out.get("id", "")
        okind = out.get("kind")
        label = out.get("label", oid)
        if okind == "table":
            outputs_html.append(
                f'<div class="tool-output-section" data-output-id="{_html_escape(oid)}" data-output-kind="table">'
                f'<div class="section-label">{_html_escape(label)}</div>'
                f'<div class="tool-output-table-host"></div>'
                f'</div>'
            )
        elif okind == "series":
            outputs_html.append(
                f'<div class="tool-output-section" data-output-id="{_html_escape(oid)}" data-output-kind="series">'
                f'<div class="section-label">{_html_escape(label)}</div>'
                f'<div class="tool-output-chart-host" id="tool-{_html_escape(wid)}-out-{_html_escape(oid)}" style="height:280px"></div>'
                f'</div>'
            )
        elif okind == "distribution":
            outputs_html.append(
                f'<div class="tool-output-section" data-output-id="{_html_escape(oid)}" data-output-kind="distribution">'
                f'<div class="section-label">{_html_escape(label)}</div>'
                f'<div class="tool-output-chart-host" id="tool-{_html_escape(wid)}-out-{_html_escape(oid)}" style="height:240px"></div>'
                f'</div>'
            )
        elif okind == "stat_grid":
            outputs_html.append(
                f'<div class="tool-output-section" data-output-id="{_html_escape(oid)}" data-output-kind="stat_grid">'
                f'<div class="section-label">{_html_escape(label)}</div>'
                f'<div class="tool-output-stat-grid-host"></div>'
                f'</div>'
            )
        elif okind in ("stat", "param", "kpi", "scalar"):
            outputs_html.append(
                f'<div class="tool-output-section tool-stat-section" '
                f'data-output-id="{_html_escape(oid)}" data-output-kind="stat">'
                f'<div class="tool-stat-cell" data-output-id="{_html_escape(oid)}">'
                f'<div class="label">{_html_escape(label)}</div>'
                f'<div class="value">--</div>'
                f'</div>'
                f'</div>'
            )
        else:
            outputs_html.append(
                f'<div class="tool-output-section" data-output-id="{_html_escape(oid)}" data-output-kind="{_html_escape(str(okind))}">'
                f'<div class="section-label">{_html_escape(label)}</div>'
                f'<div class="tool-output-host"></div>'
                f'</div>'
            )

    error_div = f'<div class="tool-error" id="tool-{_html_escape(wid)}-error" hidden></div>'

    return (
        f'<div class="{cls}" data-tile-id="{_html_escape(wid)}" '
        f'data-tool-id="{_html_escape(wid)}" style="{style}">'
        f'  <div class="tile-header">'
        f'    {_tile_title_html(w)}'
        f'  </div>'
        f'  <div class="tool-body">'
        f'    <div class="tool-input-panel" data-tool-input-panel="true">'
        f'      {inputs_panel_html}'
        f'    </div>'
        f'    <div class="tool-output-panel" data-tool-output-panel="true">'
        f'      {error_div}'
        f'      {"".join(outputs_html)}'
        f'    </div>'
        f'  </div>'
        f'  {_tile_footer_html(w)}'
        f'</div>'
    )


# Register the tool renderer now that its function is defined.
# (The dispatch table above declares all other widget kinds inline;
# `tool` is appended here because its renderer's body is large enough
# that defining it inline would push the dispatch table down past the
# tool input helpers.)
_RENDERERS["tool"] = _render_tool_widget


def _render_tool_scalar_input(inp: Dict[str, Any], wid: str) -> str:
    iid = inp.get("id", "")
    label = inp.get("label", iid)
    typ = inp.get("type", "number")
    default = inp.get("default", "")
    show_when = inp.get("show_when")
    sw_attr = ""
    if isinstance(show_when, dict) and show_when:
        sw_attr = (' data-tool-show-when=' +
                    '"' + _html_escape(json.dumps(show_when, default=_json_default)) + '"')
    suffix = inp.get("suffix")
    suffix_html = (f'<span class="tool-input-suffix">{_html_escape(suffix)}</span>'
                   if suffix else "")
    nid = f'tool-{wid}-in-{iid}'

    if typ == "select":
        opts = []
        for o in inp.get("options", []) or []:
            if isinstance(o, dict):
                v = o.get("value")
                lbl = o.get("label", v)
            else:
                v = lbl = o
            sel = " selected" if str(v) == str(default) else ""
            opts.append(
                f'<option value="{_html_escape(str(v))}"{sel}>{_html_escape(str(lbl))}</option>'
            )
        return (
            f'<div class="tool-input-row" data-input-id="{_html_escape(iid)}"{sw_attr}>'
            f'<label>{_html_escape(label)}</label>'
            f'<select id="{nid}">{"".join(opts)}</select>'
            f'{suffix_html}'
            f'</div>'
        )
    if typ == "radio":
        opts = []
        for o in inp.get("options", []) or []:
            if isinstance(o, dict):
                v = o.get("value")
                lbl = o.get("label", v)
            else:
                v = lbl = o
            chk = " checked" if str(v) == str(default) else ""
            opts.append(
                f'<label><input type="radio" name="{nid}" '
                f'value="{_html_escape(str(v))}"{chk}/>'
                f'{_html_escape(str(lbl))}</label>'
            )
        return (
            f'<div class="tool-input-row" data-input-id="{_html_escape(iid)}" '
            f'data-input-type="radio" id="{nid}-row"{sw_attr}>'
            f'<label class="row-label">{_html_escape(label)}</label>'
            f'<div class="tool-input-radio">{"".join(opts)}</div>'
            f'</div>'
        )
    if typ == "toggle":
        chk = " checked" if default else ""
        return (
            f'<div class="tool-input-row inline" data-input-id="{_html_escape(iid)}"{sw_attr}>'
            f'<input type="checkbox" id="{nid}"{chk}/>'
            f'<label for="{nid}">{_html_escape(label)}</label>'
            f'</div>'
        )
    if typ == "date":
        return (
            f'<div class="tool-input-row" data-input-id="{_html_escape(iid)}"{sw_attr}>'
            f'<label>{_html_escape(label)}</label>'
            f'<input type="date" id="{nid}" value="{_html_escape(str(default))}"/>'
            f'</div>'
        )
    if typ == "text":
        return (
            f'<div class="tool-input-row" data-input-id="{_html_escape(iid)}"{sw_attr}>'
            f'<label>{_html_escape(label)}</label>'
            f'<input type="text" id="{nid}" value="{_html_escape(str(default))}"/>'
            f'</div>'
        )
    if typ == "range":
        mn = inp.get("min", 0)
        mx = inp.get("max", 100)
        step = inp.get("step", 1)
        val = default if default != "" else mn
        dec = inp.get("decimals")
        if dec is not None:
            try:
                disp_val = f"{float(val):.{int(dec)}f}"
            except (TypeError, ValueError):
                disp_val = str(val)
        else:
            disp_val = str(val)
        step_attr = f' step="{step}"'
        return (
            f'<div class="tool-input-row tool-range" data-input-id="{_html_escape(iid)}"{sw_attr}>'
            f'<label>{_html_escape(label)}</label>'
            f'<div class="tool-range-row">'
            f'<input type="range" id="{nid}" min="{mn}" max="{mx}"{step_attr} '
            f'value="{_html_escape(str(val))}"/>'
            f'<span id="{nid}-val" class="tool-range-val">{_html_escape(disp_val)}</span>'
            f'{suffix_html}'
            f'</div>'
            f'</div>'
        )
    # default: number
    step_attr = (f' step="{inp.get("step")}"' if inp.get("step") is not None else "")
    min_attr  = (f' min="{inp.get("min")}"'   if inp.get("min")  is not None else "")
    max_attr  = (f' max="{inp.get("max")}"'   if inp.get("max")  is not None else "")
    return (
        f'<div class="tool-input-row" data-input-id="{_html_escape(iid)}"{sw_attr}>'
        f'<label>{_html_escape(label)}</label>'
        f'<input type="number" id="{nid}" value="{_html_escape(str(default))}"'
        f'{step_attr}{min_attr}{max_attr}/>'
        f'</div>'
    )


def _render_tool_matrix_input(inp: Dict[str, Any], wid: str) -> str:
    iid = inp.get("id", "")
    label = inp.get("label", iid)
    paste_enabled = bool(inp.get("paste_enabled", True))
    actions = []
    if paste_enabled:
        actions.append(
            f'<button type="button" class="tool-matrix-btn" '
            f'data-tool-matrix-paste="{_html_escape(iid)}">Paste</button>'
        )
    actions.append(
        f'<button type="button" class="tool-matrix-btn" '
        f'data-tool-matrix-clear="{_html_escape(iid)}">Clear</button>'
    )
    actions_html = "".join(actions)

    paste_pane_html = ""
    if paste_enabled:
        paste_pane_html = (
            f'<div class="tool-matrix-paste-pane" '
            f'data-tool-matrix-paste-pane="{_html_escape(iid)}" hidden>'
            f'<div class="pane-hint">Paste tab- or comma-separated values from Excel '
            f'(rows = meetings, cols = scenarios). Empty cells become 0.</div>'
            f'<textarea data-tool-matrix-paste-area="{_html_escape(iid)}" '
            f'placeholder="0\\t25\\t-25&#10;0\\t25\\t-25&#10;..."></textarea>'
            f'<div class="tool-matrix-paste-actions">'
            f'<button type="button" class="tool-matrix-btn" '
            f'data-tool-matrix-paste-cancel="{_html_escape(iid)}">Cancel</button>'
            f'<button type="button" class="tool-matrix-btn" '
            f'data-tool-matrix-paste-apply="{_html_escape(iid)}">Apply</button>'
            f'</div>'
            f'</div>'
        )

    return (
        f'<div class="tool-input-matrix" data-input-id="{_html_escape(iid)}">'
        f'<div class="tool-matrix-header">'
        f'<label>{_html_escape(label)}</label>'
        f'<div class="tool-matrix-actions">{actions_html}</div>'
        f'</div>'
        f'{paste_pane_html}'
        f'<div class="tool-matrix-grid-wrap" '
        f'data-tool-matrix-grid="{_html_escape(iid)}">'
        f'<!-- runtime fills this -->'
        f'</div>'
        f'</div>'
    )


import re as _re

# Local-file echarts.js loader. The dashboard / editor HTML shells inline
# the entire echarts library (~1MB) instead of loading it from a CDN, so a
# rendered dashboard remains self-contained when downloaded as an
# attachment, opened via file://, or served directly from S3 via a
# presigned URL (which bypasses any Django static handler). The lookup uses
# prism_meta.REPO_ROOT and tries the current web/backend_django static path
# before the parent repo's legacy mysite path. The string is cached on first
# read so it doesn't get re-loaded for every rendered dashboard in a session.
_ECHARTS_JS_CACHE = None

def _get_echarts_js() -> str:
    global _ECHARTS_JS_CACHE
    if _ECHARTS_JS_CACHE is None:
        # Anchor to the portable prism_meta.REPO_ROOT SSOT (anchored to
        # __file__.) rather than os.getcwd(), which can drift mid-process if
        # any caller (notably pytickclient.__init__) does an unrestored chdir.
        # NOTE: the dirname-x3 fallback below is correct only by coincidental
        # depth parity (rendering.py sits at prism-main/prism-core/dashboards/);
        # prism_meta is the by-design anchor and should always resolve.
        try:
            from prism_meta import REPO_ROOT as _REPO_ROOT
        except Exception:
            _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidate_paths = [
            os.path.join(_REPO_ROOT, "web", "backend_django", "news", "static", "js", "echarts.js"),
            os.path.join(_REPO_ROOT, "mysite", "news", "static", "js", "echarts.js"),
        ]
        load_errors = []
        for js_path in candidate_paths:
            try:
                with open(js_path, "r", encoding="utf-8") as f:
                    source = f.read()
                    if not source.strip():
                        load_errors.append(f"{js_path}: file is empty")
                        continue
                    _ECHARTS_JS_CACHE = source
                    break
            except FileNotFoundError:
                load_errors.append(f"{js_path}: not found")
                continue
            except Exception as e:
                load_errors.append(
                    f"{js_path}: {type(e).__name__}: {e}"
                )
        if _ECHARTS_JS_CACHE is None:
            attempts = "\n".join(f"  - {item}" for item in load_errors)
            raise FileNotFoundError(
                "ECharts runtime asset could not be loaded; refusing to "
                "emit a syntactically valid but blank dashboard. Attempted:\n"
                f"{attempts}"
            )
    return _ECHARTS_JS_CACHE


# Inline markdown regexes. The grammar is intentionally bounded (no
# full CommonMark / GFM compiler): links, bold, italic, strikethrough,
# inline code. Block-level constructs (headings, lists, blockquotes,
# fenced code, tables, hr) are handled by `_render_md` below.
_RE_LINK = _re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_RE_BOLD = _re.compile(r"\*\*([^*]+)\*\*")
_RE_ITAL = _re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_RE_STRK = _re.compile(r"~~([^~]+)~~")
_RE_CODE = _re.compile(r"`([^`]+)`")

# Block-level regexes used by `_render_md`.
_RE_MD_HEADING = _re.compile(r"^(#{1,5})\s+(.*)$")
_RE_MD_OL_ITEM = _re.compile(r"^(\d+)\.\s+(.*)$")
_RE_MD_UL_ITEM = _re.compile(r"^[-*]\s+(.*)$")
_RE_MD_TABLE_SEP = _re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
_RE_MD_HR = _re.compile(r"^\s*([-*_])\s*\1\s*\1[\s\1]*$")


def _md_inline(text: str) -> str:
    """Escape the text then re-apply inline markdown for a safe
    subset: [label](url), **bold**, *italic*, ~~strike~~, `code`.
    URLs are passed through intact so we must be careful about
    escaping.
    """
    placeholders: List[str] = []
    def _stash_link(m):
        label, url = m.group(1), m.group(2)
        placeholders.append(
            f'<a href="{_html_escape(url)}" target="_blank"'
            f' rel="noopener noreferrer">{_html_escape(label)}</a>'
        )
        return f"\x00LINK{len(placeholders) - 1}\x00"

    staged = _RE_LINK.sub(_stash_link, text)
    escaped = _html_escape(staged)
    escaped = _RE_BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = _RE_ITAL.sub(r"<em>\1</em>", escaped)
    escaped = _RE_STRK.sub(r"<del>\1</del>", escaped)
    escaped = _RE_CODE.sub(r"<code>\1</code>", escaped)
    for i, ph in enumerate(placeholders):
        escaped = escaped.replace(f"\x00LINK{i}\x00", ph)
    return escaped


def _split_md_table_row(line: str) -> List[str]:
    """Split a markdown table row by `|`, trimming surrounding whitespace
    and dropping a leading/trailing empty cell when the row is fully
    bounded with `|` (e.g. `| a | b |`).
    """
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _parse_md_table_aligns(sep: str) -> List[Optional[str]]:
    """Parse a GFM separator row like `| :--- | ---: | :---: |` into a
    list of alignment hints (`left` / `right` / `center` / None).
    """
    cells = _split_md_table_row(sep)
    out: List[Optional[str]] = []
    for c in cells:
        c = c.strip()
        if c.startswith(":") and c.endswith(":"):
            out.append("center")
        elif c.endswith(":"):
            out.append("right")
        elif c.startswith(":"):
            out.append("left")
        else:
            out.append(None)
    return out


def _render_md(src: str) -> str:
    """Markdown renderer for prose-style dashboard content.

    Single source of truth for server-side prose rendering: markdown
    widget body, ``note`` widget body, and the dashboard summary
    banner. The JS twin ``_mdInlinePopup`` (defined in the dashboard
    shell script) mirrors this grammar for client-side popup bodies
    (info / methodology / row drill-down). Both must be upgraded
    together when extending the grammar.

    Block-level grammar:
      * ``# H1`` .. ``##### H5`` headings
      * blank-line separated paragraphs (lines within a paragraph are
        joined with a single space)
      * ``-`` / ``*`` unordered list items, ``1.`` ordered list items;
        nested via 2-space indent (each two leading spaces opens
        another list level)
      * ``> ...`` blockquotes (multi-line; consecutive ``>`` lines are
        collapsed and re-rendered through this same parser so quotes
        can carry their own headings, lists, and emphasis)
      * triple-backtick fenced code blocks (with optional language tag,
        rendered as ``<pre><code class="lang-<X>">``)
      * GFM-style tables: header row, ``| --- |`` separator (with
        optional ``:`` alignment hints), zero or more body rows
      * ``---`` / ``***`` / ``___`` on a line by itself for horizontal
        rules

    Inline grammar:
      ``**bold**``  ``*italic*``  ``~~strike~~``  ``` `code` ```
      ``[label](url)`` (always opens new tab)

    Anything that does not match is escaped as plain text.
    """
    lines = str(src).splitlines()
    n = len(lines)
    out: List[str] = []
    buf_para: List[str] = []
    quote_buf: List[str] = []
    # Parallel stacks: list_stack tracks (kind, indent) per open list,
    # li_open tracks whether the deepest <li> at that level is still
    # awaiting its closing tag. Keeping `<li>` open lets a nested
    # `<ul>` / `<ol>` live inside its parent `<li>`, which is the
    # only HTML-valid nesting shape.
    list_stack: List[Tuple[str, int]] = []
    li_open: List[bool] = []

    def flush_para():
        if buf_para:
            out.append(f"<p>{_md_inline(' '.join(buf_para))}</p>")
            buf_para.clear()

    def flush_quote():
        if quote_buf:
            inner = _render_md("\n".join(quote_buf))
            out.append(f"<blockquote>{inner}</blockquote>")
            quote_buf.clear()

    def close_top_list():
        kind, _ = list_stack.pop()
        if li_open.pop():
            out.append("</li>")
        out.append(f"</{kind}>")

    def close_all_lists():
        while list_stack:
            close_top_list()

    def push_list_item(kind: str, indent: int, text: str):
        # Step 1: pop all lists deeper than this indent (with their open
        # <li>, since the parent <li> at the shallower level is still
        # awaiting its close).
        while list_stack and list_stack[-1][1] > indent:
            close_top_list()
        # Step 2: at the same indent, close any open <li> sibling, and
        # if the kind switches (ul -> ol or vice versa) close that list
        # entirely so we can open a fresh one of the new kind.
        if list_stack and list_stack[-1][1] == indent:
            top_kind, _ = list_stack[-1]
            if top_kind != kind:
                close_top_list()
            else:
                if li_open[-1]:
                    out.append("</li>")
                    li_open[-1] = False
        # Step 3: if no list at this indent (either empty stack or
        # parent is shallower), open a new nested one INSIDE the
        # parent <li> (which we deliberately leave open).
        if not list_stack or list_stack[-1][1] < indent:
            list_stack.append((kind, indent))
            li_open.append(False)
            out.append(f"<{kind}>")
        # Step 4: open the new <li>; it stays open until either a
        # sibling closes it or a deeper list nests inside it.
        out.append(f"<li>{_md_inline(text)}")
        li_open[-1] = True

    i = 0
    while i < n:
        raw = lines[i]
        stripped = raw.lstrip()
        indent = len(raw) - len(stripped)
        s = stripped.rstrip()

        if s.startswith("```"):
            lang = s[3:].strip()
            flush_para(); flush_quote(); close_all_lists()
            buf: List[str] = []
            i += 1
            while i < n and not lines[i].lstrip().rstrip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            code = "\n".join(buf)
            cls = (f' class="lang-{_html_escape(lang)}"'
                   if lang else "")
            out.append(
                f"<pre><code{cls}>{_html_escape(code)}</code></pre>"
            )
            continue

        if "|" in s and i + 1 < n and \
           _RE_MD_TABLE_SEP.match(lines[i + 1].rstrip()):
            flush_para(); flush_quote(); close_all_lists()
            hdr = _split_md_table_row(s)
            aligns = _parse_md_table_aligns(lines[i + 1].rstrip())
            i += 2
            rows: List[List[str]] = []
            while i < n:
                rs = lines[i].rstrip()
                if "|" in rs and rs.strip():
                    rows.append(_split_md_table_row(rs))
                    i += 1
                else:
                    break
            tbl: List[str] = ['<table class="md-table">']
            tbl.append("<thead><tr>")
            for j, h in enumerate(hdr):
                al = aligns[j] if j < len(aligns) else None
                style = (f' style="text-align:{al}"' if al else "")
                tbl.append(f"<th{style}>{_md_inline(h)}</th>")
            tbl.append("</tr></thead><tbody>")
            for row in rows:
                tbl.append("<tr>")
                for j, c in enumerate(row):
                    al = aligns[j] if j < len(aligns) else None
                    style = (f' style="text-align:{al}"' if al else "")
                    tbl.append(f"<td{style}>{_md_inline(c)}</td>")
                tbl.append("</tr>")
            tbl.append("</tbody></table>")
            out.append("".join(tbl))
            continue

        if _RE_MD_HR.match(s):
            flush_para(); flush_quote(); close_all_lists()
            out.append("<hr/>")
            i += 1
            continue

        if s == "":
            flush_para(); flush_quote(); close_all_lists()
            i += 1
            continue

        h_match = _RE_MD_HEADING.match(s)
        if h_match:
            flush_para(); flush_quote(); close_all_lists()
            level = min(len(h_match.group(1)), 5)
            out.append(
                f"<h{level}>{_md_inline(h_match.group(2))}</h{level}>"
            )
            i += 1
            continue

        if s.startswith("> "):
            flush_para(); close_all_lists()
            quote_buf.append(s[2:])
            i += 1
            continue
        if s == ">":
            flush_para(); close_all_lists()
            quote_buf.append("")
            i += 1
            continue

        ol_match = _RE_MD_OL_ITEM.match(s)
        ul_match = _RE_MD_UL_ITEM.match(s)
        if ol_match or ul_match:
            flush_para(); flush_quote()
            kind = "ol" if ol_match else "ul"
            text = (ol_match.group(2) if ol_match
                    else ul_match.group(1))
            snapped = (indent // 2) * 2
            push_list_item(kind, snapped, text)
            i += 1
            continue

        flush_quote(); close_all_lists()
        buf_para.append(stripped)
        i += 1

    flush_para(); flush_quote(); close_all_lists()
    return "\n".join(out)


def _render_rows(
    rows: List[List[Dict[str, Any]]],
    cols: int,
    groups: Optional[List[Dict[str, Any]]] = None,
) -> str:
    def _grid(chunk: List[List[Dict[str, Any]]]) -> str:
        out = ["<div class=\"grid\">"]
        for row in chunk:
            for w in row:
                out.append(_render_widget(w, cols))
        out.append("</div>")
        return "\n".join(out)

    normalized = sorted(
        (
            g for g in (groups or [])
            if isinstance(g, dict)
            and isinstance(g.get("start_row"), int)
            and isinstance(g.get("end_row"), int)
            and 0 <= g["start_row"] <= g["end_row"] < len(rows)
        ),
        key=lambda g: g["start_row"],
    )
    if not normalized:
        return _grid(rows)

    out: List[str] = []
    cursor = 0
    for group in normalized:
        start, end = group["start_row"], group["end_row"]
        if start > cursor:
            out.append(_grid(rows[cursor:start]))
        title = _html_escape(group.get("title", ""))
        desc = _html_escape(group.get("description", ""))
        gid = _html_escape(group.get("id", f"group-{start}"))
        header = (
            f'<div class="layout-group-heading"><h2>{title}</h2>'
            + (f'<p>{desc}</p>' if desc else "")
            + "</div>"
        )
        body = _grid(rows[start:end + 1])
        if group.get("collapsible"):
            out.append(
                f'<details class="layout-group layout-group-collapsible" '
                f'id="layout-group-{gid}" open>'
                f'<summary>{header}</summary>{body}</details>'
            )
        else:
            out.append(
                f'<section class="layout-group" id="layout-group-{gid}">'
                f"{header}{body}</section>"
            )
        cursor = end + 1
    if cursor < len(rows):
        out.append(_grid(rows[cursor:]))
    return "\n".join(out)


def _collect_specs(manifest: Dict[str, Any],
                    chart_specs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    def visit_rows(rows):
        for row in rows:
            for w in row:
                if w.get("widget") != "chart":
                    continue
                wid = w.get("id") or f"chart_{len(out)}"
                if wid in chart_specs:
                    out[wid] = chart_specs[wid]
                elif isinstance(w.get("option"), dict):
                    out[wid] = w["option"]
                elif isinstance(w.get("option_inline"), dict):
                    out[wid] = w["option_inline"]
                else:
                    out[wid] = {"series": []}

    layout = manifest.get("layout", {})
    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            visit_rows(tab.get("rows", []) or [])
    else:
        visit_rows(layout.get("rows", []) or [])
    return out


def render_dashboard_html(
    manifest: Dict[str, Any],
    chart_specs: Dict[str, Dict[str, Any]],
    filename_base: Optional[str] = None,
) -> str:
    from echart_studio import __version__ as VERSION
    from datetime import datetime

    layout = manifest.get("layout", {})
    cols = int(layout.get("cols", 12))
    kind = layout.get("kind", "grid")

    # Split filters by scope: globals go in the top bar, "tab:<id>" filters
    # render inline inside their host tab panel. Filters without an
    # explicit scope default to global (_augment_manifest sets this).
    filters = manifest.get("filters", []) or []
    global_filters: List[Dict[str, Any]] = []
    per_tab_filters: Dict[str, List[Dict[str, Any]]] = {}
    for f in filters:
        scope = str(f.get("scope", "global"))
        if scope.startswith("tab:"):
            per_tab_filters.setdefault(scope[4:], []).append(f)
        else:
            global_filters.append(f)

    if kind == "tabs":
        tabs = layout.get("tabs", []) or []
        tab_btns: List[str] = []
        for t in tabs:
            tip = t.get("description", "")
            title_attr = (f' title="{_html_escape(tip)}"' if tip else "")
            tab_btns.append(
                f"<button class=\"tab-btn\""
                f" data-tab=\"{_html_escape(t['id'])}\"{title_attr}>"
                f"{_html_escape(t.get('label', t['id']))}</button>"
            )
        tab_bar_html = "<nav class=\"tab-bar\">" + "".join(tab_btns) + "</nav>"

        def _panel(t: Dict[str, Any]) -> str:
            tid = t["id"]
            header = (
                f"<div class=\"tab-panel-header\">"
                f"<h2>{_html_escape(t.get('description', ''))}</h2></div>"
                if t.get("description") else ""
            )
            inline_bar = _render_filter_controls(
                per_tab_filters.get(tid, []), inline=True,
                show_reset=bool(per_tab_filters.get(tid))
            )
            rows = _render_rows(
                t.get("rows", []) or [], cols, t.get("groups") or []
            )
            return (
                f"<section class=\"tab-panel\" "
                f"id=\"tab-panel-{_html_escape(tid)}\">"
                f"{header}{inline_bar}{rows}</section>"
            )
        panels_html = "\n".join(_panel(t) for t in tabs)
    else:
        tab_bar_html = ""
        panels_html = (
            "<section class=\"tab-panel active\" id=\"tab-panel-main\">"
            + _render_rows(
                layout.get("rows", []) or [],
                cols,
                layout.get("groups") or [],
            )
            + "</section>"
        )

    filter_bar_html = _render_filter_controls(global_filters, inline=False)

    # Optional dashboard-level summary banner. `metadata.summary` is a
    # short markdown blurb rendered below the filter bar and above the
    # first row / tab bar - the "today's read" header. Accepts either
    # a plain markdown string or a {title, body} dict where `title`
    # becomes a leading `<h2>` (so PRISM can label the banner without
    # the body needing its own `## Title` line).
    summary = (manifest.get("metadata") or {}).get("summary")
    if summary:
        if isinstance(summary, dict):
            s_title = summary.get("title")
            s_body = summary.get("body") or summary.get("text") or ""
        else:
            s_title = None
            s_body = str(summary)
        if s_body:
            head = (f"<h2>{_html_escape(str(s_title))}</h2>"
                    if s_title else "")
            summary_html = (
                f'<aside class="summary-banner markdown-body">'
                f'{head}{_render_md(s_body)}</aside>'
            )
        else:
            summary_html = ""
    else:
        summary_html = ""

    # Payload
    # The runtime JS reads DATASETS = PAYLOAD.datasets exclusively; nothing
    # in DASHBOARD_APP_JS references PAYLOAD.manifest.datasets. So the
    # canonical dataset copy lives in PAYLOAD.datasets and the manifest
    # copy in the payload is shipped without its datasets to avoid
    # serialising the rows twice (would otherwise ~double the HTML size
    # on data-heavy dashboards). The on-disk manifest.json written by
    # save_manifest() still includes datasets in full.
    specs = _collect_specs(manifest, chart_specs)
    datasets = manifest.get("datasets", {}) or {}
    manifest_for_payload = {
        k: v for k, v in manifest.items()
        if k not in ("datasets", "map_assets")
    }
    manifest_for_payload["datasets"] = {}

    # Extract runtime show_when conditions: {widget_id: condition_dict}
    # Compile-time data-clauses already removed widgets that fail; what
    # remains is filter-clause conditions the JS runtime evaluates on
    # every filter change.
    widget_show_when: Dict[str, Any] = {}
    def _collect_show_when(rows):
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                cond = w.get("show_when")
                wid = w.get("id")
                if cond and wid:
                    widget_show_when[wid] = cond

    if kind == "tabs":
        for t in layout.get("tabs", []) or []:
            _collect_show_when(t.get("rows") or [])
    else:
        _collect_show_when(layout.get("rows") or [])

    # Collect every tool widget: resolve its tool_def, materialise matrix
    # row bindings, attach initial input values. Runtime reads
    # PAYLOAD.tools[<wid>] for inputs panel rendering, compute dispatch,
    # and output routing.
    tools_payload: Dict[str, Any] = {}
    def _collect_tools(rows):
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                if w.get("widget") != "tool":
                    continue
                wid = w.get("id")
                if not wid:
                    continue
                try:
                    tools_payload[wid] = _resolve_tool_for_render(w, manifest)
                except Exception as e:
                    tools_payload[wid] = {
                        "def": {"name": "_error", "inputs": [], "outputs": [],
                                 "compute": {"kind": "js", "source": ""}},
                        "initial_inputs": {},
                        "_error": str(e),
                    }

    if kind == "tabs":
        for t in layout.get("tabs", []) or []:
            _collect_tools(t.get("rows") or [])
    else:
        _collect_tools(layout.get("rows") or [])

    user_inputs_payload: Dict[str, Any] = {}
    def _collect_user_inputs(rows):
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict) or w.get("widget") != "user_input":
                    continue
                wid = w.get("id")
                if not wid:
                    continue
                entry = {
                    "widget_id": wid,
                    "mode": w.get("mode"),
                    "seed": w.get("seed"),
                }
                if "placeholder" in w:
                    entry["placeholder"] = w.get("placeholder")
                if "rows" in w:
                    entry["rows"] = w.get("rows")
                user_inputs_payload[wid] = entry

    if kind == "tabs":
        for t in layout.get("tabs", []) or []:
            _collect_user_inputs(t.get("rows") or [])
    else:
        _collect_user_inputs(layout.get("rows") or [])

    payload = {
        "manifest": manifest_for_payload,
        "specs": specs,
        "datasets": datasets,
        "maps": manifest.get("map_assets", {}) or {},
        "themes": {n: t["echarts"] for n, t in THEMES.items()},
        "resolvedThemes": {
            n: resolve_theme(n, export_mode="screen")
            for n in THEMES
        },
        "palettes": {n: {"colors": list(p["colors"]), "kind": p["kind"]}
                      for n, p in PALETTES.items()},
        "widgetShowWhen": widget_show_when,
        "tools": tools_payload,
        "userInputs": user_inputs_payload,
    }
    payload_js = ("var PAYLOAD = "
                   + json.dumps(payload, default=_json_default)
                   + ";\n")

    title = manifest.get("title", "Dashboard")
    description = manifest.get("description", "")
    theme_name = manifest.get("theme", "gs_clean")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # GS brand tokens injected into CSS custom properties at render
    # time (keeps the stylesheet in lockstep with config.py).
    GS_TOKENS = {
        "__GS_NAVY__":       GS_NAVY,
        "__GS_NAVY_DEEP__":  GS_NAVY_DEEP,
        "__GS_SKY__":        GS_SKY,
        "__GS_INK__":        GS_INK,
        "__GS_PAPER__":      GS_PAPER,
        "__GS_BG__":         GS_BG,
        "__GS_GREY_70__":    GS_GREY_70,
        "__GS_GREY_40__":    GS_GREY_40,
        "__GS_GREY_20__":    GS_GREY_20,
        "__GS_GREY_10__":    GS_GREY_10,
        "__GS_GREY_05__":    GS_GREY_05,
        "__GS_POS__":        GS_POS,
        "__GS_NEG__":        GS_NEG,
        "__GS_FONT_SANS__":  GS_FONT_SANS,
        "__GS_FONT_SERIF__": GS_FONT_SERIF,
        "__GS_DARK_BG__":          GS_DARK_BG,
        "__GS_DARK_SURFACE__":     GS_DARK_SURFACE,
        "__GS_DARK_SURFACE_2__":   GS_DARK_SURFACE_2,
        "__GS_DARK_SURFACE_HOV__": GS_DARK_SURFACE_HOV,
        "__GS_DARK_TEXT__":        GS_DARK_TEXT,
        "__GS_DARK_TEXT_DIM__":    GS_DARK_TEXT_DIM,
        "__GS_DARK_TEXT_FAINT__":  GS_DARK_TEXT_FAINT,
        "__GS_DARK_BORDER__":      GS_DARK_BORDER,
        "__GS_DARK_BORDER_STR__":  GS_DARK_BORDER_STR,
    }

    # Header brand mark. When a Prism AI logo PNG is available
    # (PRISM S3 fetch, $PRISM_LOGO_PATH override, or assets/prism_logo.png)
    # we emit a .prism-mark span; otherwise we fall back to the original
    # .gs-mark span, which is still defined in DASHBOARD_SHELL's CSS.
    # Either mark is wrapped in a.brand-home -> /profile/ so a click
    # returns to the PRISM main page. The footer keeps the GS mark
    # (unlinked) in either case.
    prism_logo_b64 = _get_prism_logo_b64()
    if prism_logo_b64:
        brand_inner = (
            '<span class="prism-mark">'
            f'<img src="data:image/png;base64,{prism_logo_b64}" '
            'alt="Prism AI" '
            'onerror="this.style.display=\'none\'">'
            '<span class="prism-wordmark">Prism AI</span>'
            '</span>'
        )
    else:
        brand_inner = (
            '<span class="gs-mark">'
            '<span class="gs-box">GS</span>'
            '<span class="gs-wordmark">Goldman Sachs</span>'
            '</span>'
        )
    header_brand_html = (
        '<a class="brand-home" href="/profile/" '
        'title="Back to PRISM home" aria-label="Back to PRISM home">'
        f'{brand_inner}'
        '</a>'
    )

    app_js = DASHBOARD_APP_JS.replace(
        "__MAX_DECIMALS__", str(int(MAX_DASHBOARD_DECIMALS))
    )

    html = DASHBOARD_SHELL
    html = html.replace("__ECHARTS_SCRIPT__", f"<script>\n{_get_echarts_js()}\n</script>")
    for k, v in GS_TOKENS.items():
        html = html.replace(k, v)
    html = (html
            .replace("__TITLE__", _html_escape(title))
            .replace("__DESCRIPTION__", _html_escape(description))
            .replace("__THEME__", _html_escape(theme_name))
            .replace("__COLS__", str(cols))
            .replace("__TAB_BAR__", tab_bar_html)
            .replace("__FILTER_BAR__", filter_bar_html)
            .replace("__SUMMARY__", summary_html)
            .replace("__TAB_PANELS__", panels_html)
            .replace("__HEADER_BRAND__", header_brand_html)
            .replace("__TIMESTAMP__", _html_escape(ts))
            .replace("__VERSION__", VERSION)
            .replace("__PAYLOAD__", payload_js)
            .replace("__APP__", app_js))
    return html


# =============================================================================
# PART 3 -- PNG EXPORT (headless Chrome)
# =============================================================================
# Server-side PNG rendering via a tiny HTML harness + Chrome --screenshot.


_HARNESS = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>chart</title>
<style>
html,body{{margin:0;padding:0;width:{width}px;height:{height}px;
  background:{background};overflow:hidden;}}
#chart{{width:{width}px;height:{height}px;}}
</style>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
</head>
<body>
<div id="chart"></div>
<script>
(function(){{
  // Revive string-encoded functions (renderItem, formatter, filter) into
  // real JS functions. Python emits function bodies as strings because JSON
  // cannot carry code; ECharts needs real functions at setOption() time.
  function _isFnStr(s) {{
    return typeof s === 'string' && /^\\s*function\\s*\\(/.test(s);
  }}
  function _reviveFns(x) {{
    if (x == null) return x;
    if (_isFnStr(x)) {{
      try {{ return new Function('return (' + x + ')')(); }}
      catch(e) {{ return x; }}
    }}
    if (Array.isArray(x)) {{
      for (var i = 0; i < x.length; i++) x[i] = _reviveFns(x[i]);
      return x;
    }}
    if (typeof x === 'object') {{
      for (var k in x) {{
        if (Object.prototype.hasOwnProperty.call(x, k)) {{
          x[k] = _reviveFns(x[k]);
        }}
      }}
    }}
    return x;
  }}

  var OPTION = {option_json};
  var THEMES = {themes_json};
  var THEME_NAME = {theme_name_json};
  Object.keys(THEMES).forEach(function(k){{
    try {{ echarts.registerTheme(k, THEMES[k]); }} catch(e){{}}
  }});
  var inst = echarts.init(document.getElementById('chart'),
                            THEME_NAME in THEMES ? THEME_NAME : null,
                            {{renderer: 'canvas'}});
  // Strip interactive-only UI elements from the PNG output.
  delete OPTION.toolbox;
  delete OPTION.dataZoom;
  delete OPTION.brush;
  OPTION.animation = false;
  if (OPTION.series) {{
    (Array.isArray(OPTION.series) ? OPTION.series : [OPTION.series])
      .forEach(function(s){{ s.animation = false; }});
  }}
  OPTION = _reviveFns(OPTION);
  inst.setOption(OPTION, true);
  inst.on('finished', function(){{ document.title = 'rendered'; }});
}})();
</script>
</body>
</html>
"""


def find_chrome() -> str:
    """Locate the Chrome/Chromium binary. Raises RuntimeError if not found.

    Resolution order:
      1. $CHROME_BIN env var (absolute path)
      2. /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
      3. PATH lookup for google-chrome / chromium / chromium-browser / chrome
    """
    env = os.environ.get("CHROME_BIN")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return str(p)
        raise RuntimeError(
            f"CHROME_BIN={env!r} is set but the file does not exist."
        )
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path(mac).is_file():
        return mac
    for candidate in ("google-chrome", "chromium", "chromium-browser",
                       "chrome", "Chromium"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError(
        "PNG export needs a Chrome/Chromium binary. Install Google Chrome "
        "or set the CHROME_BIN environment variable to the binary path."
    )


def save_chart_png(
    option: Union[Dict[str, Any], str],
    output_path: Union[str, Path],
    *,
    width: int = 900,
    height: int = 520,
    theme: str = "gs_clean",
    scale: int = 2,
    background: Optional[str] = None,
    virtual_time_ms: int = 2500,
    timeout_s: float = 30.0,
    verbose: bool = False,
) -> Path:
    """Render a single ECharts option to PNG via headless Chrome.

    Parameters
    ----------
    option : dict | str
        ECharts option object (or JSON string).
    output_path : str | Path
        Destination PNG path. Parent directories are created.
    width, height : int
        Logical chart dimensions (CSS pixels). Final PNG dimensions will
        be `width * scale` x `height * scale`.
    theme : str
        Theme name to apply (one of the THEMES keys). Defaults to
        ``gs_clean``. The theme spec is embedded and registered inline.
    scale : int
        Device-pixel multiplier (2 = retina). 1, 2, 3 supported.
    background : str, optional
        Page background color. Defaults to the resolved theme background;
        use this for transparent exports by
        passing ``'rgba(0,0,0,0)'`` plus `--default-background-color=00000000`.
    virtual_time_ms : int
        How long to advance Chrome's virtual clock before the screenshot.
        Large charts with many series may need more.
    timeout_s : float
        Hard subprocess timeout.
    verbose : bool
        If True, prints the command line and the Chrome output.

    Returns
    -------
    Path
        Absolute path to the written PNG.
    """
    if isinstance(option, str):
        option = json.loads(option)
    if not isinstance(option, dict):
        raise TypeError(
            f"option must be a dict or JSON string, got {type(option).__name__}"
        )

    resolved = resolve_theme(theme, export_mode="screen")
    if background is None:
        background = resolved["export"]["background"]

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    themes_payload = {n: t.get("echarts", {}) for n, t in THEMES.items()}
    html = _HARNESS.format(
        width=int(width),
        height=int(height),
        background=background,
        option_json=json.dumps(option, default=str),
        themes_json=json.dumps(themes_payload, default=str),
        theme_name_json=json.dumps(theme),
    )

    chrome = find_chrome()
    tmp = Path(tempfile.mkdtemp(prefix="echarts_png_"))
    try:
        harness = tmp / "chart.html"
        harness.write_text(html, encoding="utf-8")
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--mute-audio",
            "--allow-file-access-from-files",
            f"--window-size={int(width)},{int(height)}",
            f"--force-device-scale-factor={int(scale)}",
            f"--virtual-time-budget={int(virtual_time_ms)}",
            "--run-all-compositor-stages-before-draw",
            f"--screenshot={output_path}",
            f"file://{harness}",
        ]
        if verbose:
            print("  [png_export] " + " ".join(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout_s)
        if verbose:
            if res.stdout:
                print(res.stdout.strip())
            if res.stderr:
                print(res.stderr.strip(), file=sys.stderr)
        if res.returncode != 0:
            raise RuntimeError(
                f"headless Chrome failed (exit {res.returncode}): "
                f"{(res.stderr or res.stdout).strip()}"
            )
        if not output_path.is_file():
            raise RuntimeError(
                f"Chrome did not write PNG to {output_path}. stderr: "
                f"{res.stderr.strip()}"
            )
        return output_path
    finally:
        try:
            for f in tmp.iterdir():
                try:
                    f.unlink()
                except OSError:
                    pass
            tmp.rmdir()
        except OSError:
            pass


def _cell_px(w_cols: int, container_px: int, cols: int, gap_px: int) -> int:
    """Approximate pixel width of a `w_cols`-wide cell in a `cols`-column grid.

    `container_px` is the total usable width after gutters.
    """
    w_cols = max(1, min(w_cols, cols))
    cell = (container_px - (cols - 1) * gap_px) / cols
    return int(round(cell * w_cols + (w_cols - 1) * gap_px))


def _has_existing_chart_title(t: Any) -> bool:
    if not t:
        return False
    if isinstance(t, list):
        return any(isinstance(x, dict) and x.get("text") for x in t)
    if isinstance(t, dict):
        return bool(t.get("text"))
    return False


def _stable_color_index(name: Any, size: int) -> int:
    value = 2166136261
    encoded = str(name if name is not None else "").encode("utf-16-le")
    for offset in range(0, len(encoded), 2):
        code_unit = encoded[offset] | (encoded[offset + 1] << 8)
        value ^= code_unit
        value = (value * 16777619) & 0xFFFFFFFF
    return value % size if size else 0


def _stable_color_slots(keys: Iterable[Any], size: int) -> Dict[str, int]:
    if size <= 0:
        return {}
    slots: Dict[str, int] = {}
    used: set[int] = set()
    for key in sorted({str(item) for item in keys}):
        slot = _stable_color_index(key, size)
        if len(used) < size:
            while slot in used:
                slot = (slot + 1) % size
            used.add(slot)
        slots[key] = slot
    return slots


def _apply_stable_series_colors(
    opt: Dict[str, Any],
    w: Dict[str, Any],
    theme: str,
) -> None:
    spec = w.get("spec") if isinstance(w.get("spec"), dict) else {}
    custom = spec.get("colors")
    named = (
        spec.get("series_colors")
        if isinstance(spec.get("series_colors"), dict) else {}
    )
    mode = "dark" if theme.endswith("_dark") else "light"
    if isinstance(custom, dict) and isinstance(custom.get(mode), list):
        colors = list(custom[mode])
    else:
        palette_name = spec.get("palette")
        if palette_name and palette_name != "gs_primary":
            colors = list(PALETTES[palette_name]["colors"])
        else:
            colors = list(resolve_theme(theme)["categorical"])
    if not colors:
        return

    def _named_color(*keys: Any) -> Optional[str]:
        for key in keys:
            if key is None:
                continue
            modes = named.get(str(key))
            if isinstance(modes, dict) and isinstance(modes.get(mode), str):
                return modes[mode]
        return None

    opt["color"] = colors
    series = opt.get("series")
    series_list = series if isinstance(series, list) else [series]
    keys: List[str] = []
    for index, item in enumerate(series_list):
        if not isinstance(item, dict) or item.get("type") in ("heatmap", "map"):
            continue
        if item.get("type") == "pie" and isinstance(item.get("data"), list):
            for item_index, datum in enumerate(item["data"]):
                if isinstance(datum, dict):
                    keys.append(str(datum.get("name", f"slice-{item_index}")))
            continue
        keys.append(str(
            item.get("name") or item.get("_column") or f"series-{index}"
        ))
    slots = _stable_color_slots(keys, len(colors))
    for index, item in enumerate(series_list):
        if not isinstance(item, dict) or item.get("type") == "heatmap":
            continue
        if item.get("type") == "map":
            item.setdefault("itemStyle", {})["borderColor"] = (
                resolve_theme(theme)["semantic"]["surface"]
            )
            continue
        if item.get("type") == "pie" and isinstance(item.get("data"), list):
            for item_index, datum in enumerate(item["data"]):
                if not isinstance(datum, dict):
                    continue
                style = datum.setdefault("itemStyle", {})
                key = str(datum.get("name", f"slice-{item_index}"))
                explicit = _named_color(datum.get("name"), key)
                if explicit is not None:
                    style["color"] = explicit
                elif "color" not in style:
                    style["color"] = colors[slots[key]]
            continue
        key = str(item.get("name") or item.get("_column") or f"series-{index}")
        color = _named_color(item.get("name"), item.get("_column"), key)
        if color is None:
            color = colors[slots[key]]
        item_style = item.setdefault("itemStyle", {})
        line_style = item.setdefault("lineStyle", {})
        if _named_color(item.get("name"), item.get("_column"), key) is not None:
            item_style["color"] = color
            line_style["color"] = color
        else:
            item_style.setdefault("color", color)
            line_style.setdefault("color", color)


def _inject_widget_title_into_option(
    opt: Dict[str, Any], w: Dict[str, Any], theme: str = "gs_clean"
) -> Tuple[Dict[str, Any], int]:
    """Bake the widget's tile title (and subtitle) into the chart option
    so PNG exports show what the user sees on the dashboard tile.

    The dashboard compiler clears ``opt.title.text`` to avoid double
    headlines on screen (the tile chrome already shows the title).
    That same stripping bites every PNG export -- in-browser via
    ``getDataURL()`` and headless-Chrome via ``save_chart_png``.
    This helper re-injects the title using GS type styles so the
    exported PNG has the title visually attached to the chart.

    Returns the (possibly mutated) option and the extra vertical
    pixels the title block consumes (so the caller can grow the
    canvas height accordingly and not squeeze the plot area).

    No-op when the option already carries its own title (raw
    ``option`` / ``ref`` passthrough widgets) -- in that case PNG
    export uses the chart's native title.
    """
    title = w.get("title") or ""
    subtitle = w.get("subtitle") or ""
    if not title and not subtitle:
        return opt, 0
    if _has_existing_chart_title(opt.get("title")):
        return opt, 0
    resolved = resolve_theme(theme, export_mode="screen")
    semantic = resolved["semantic"]
    title_block = {
        "text": str(title),
        "subtext": str(subtitle),
        "left": 16,
        "top": 10,
        "textStyle": {
            "fontFamily": ('Goldman Sans, GS Sans, '
                            'Helvetica Neue, Arial, sans-serif'),
            "fontSize": 14, "fontWeight": 600, "color": semantic["text"],
        },
        "subtextStyle": {
            "fontFamily": ('Goldman Sans, GS Sans, '
                            'Helvetica Neue, Arial, sans-serif'),
            "fontSize": 11, "color": semantic["text_dim"],
            "fontStyle": "italic",
        },
    }
    opt["title"] = [title_block]
    title_px = 26 + (18 if subtitle else 0) + 10
    grid = opt.get("grid")
    if isinstance(grid, list):
        for g in grid:
            if isinstance(g, dict):
                cur = g.get("top", 30)
                cur_n = cur if isinstance(cur, (int, float)) else 30
                g["top"] = int(cur_n) + title_px
    elif isinstance(grid, dict):
        cur = grid.get("top", 30)
        cur_n = cur if isinstance(cur, (int, float)) else 30
        grid["top"] = int(cur_n) + title_px
    return opt, title_px


def save_dashboard_pngs(
    manifest: Dict[str, Any],
    chart_specs: Dict[str, Dict[str, Any]],
    output_dir: Union[str, Path],
    *,
    theme: Optional[str] = None,
    scale: int = 2,
    container_px: int = 1400,
    gap_px: int = 14,
    min_width: int = 480,
    background: Optional[str] = None,
    virtual_time_ms: int = 2500,
    verbose: bool = False,
) -> List[Path]:
    """Render every chart widget in a dashboard as a separate PNG.

    Widget ``id`` becomes the filename stem. Widget pixel width is
    estimated from its grid span so the PNG matches the on-screen aspect.

    Parameters
    ----------
    manifest : dict
        The dashboard manifest (after validation).
    chart_specs : dict
        Mapping of chart widget id -> compiled ECharts option. This is
        exactly the output of ``_resolve_chart_specs()`` in
        ``echart_dashboard``.
    output_dir : str | Path
        Destination directory; created if missing.
    theme : str, optional
        Override theme; defaults to ``manifest['theme']`` or ``gs_clean``.
    scale : int
        Device-pixel multiplier.
    container_px : int
        Assumed dashboard container width (used to convert grid spans
        to pixel widths).
    gap_px : int
        Grid gap (matches dashboard CSS ``--gap``).
    min_width : int
        Floor for tiny tiles so PNGs remain legible.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    theme_name = theme or manifest.get("theme", "gs_clean")
    layout = manifest.get("layout", {}) or {}
    cols = int(layout.get("cols", 12))
    paths: List[Path] = []

    def visit(rows: List[List[Dict[str, Any]]]) -> None:
        for row in rows or []:
            for w in row or []:
                if w.get("widget") != "chart":
                    continue
                wid = w.get("id")
                opt = chart_specs.get(wid) or w.get("option")
                if not opt or not wid:
                    continue
                # Bake the tile title into the option so the PNG
                # actually shows what's on screen. _inject... is a
                # no-op when there's no widget title or the chart
                # already provides one (raw option / ref passthrough).
                opt = json.loads(json.dumps(opt))
                chart_theme = (
                    theme
                    or (
                        w.get("spec", {}).get("theme")
                        if isinstance(w.get("spec"), dict) else None
                    )
                    or theme_name
                )
                _apply_stable_series_colors(opt, w, chart_theme)
                opt, title_px = _inject_widget_title_into_option(
                    opt, w, chart_theme
                )
                w_cols = int(w.get(
                    "w", cols if w.get("hero") else cols // 2
                ))
                # Same layout-aware default as the HTML render path
                # (_render_chart_widget): 400 for 2-up tiles, 360 for
                # 3-up. Keeps the PNG export and the on-screen tile
                # at the same aspect ratio.
                _default_h = (
                    500 if w.get("hero")
                    else 400 if w_cols >= cols // 2
                    else 360
                )
                height = int(w.get("h_px", _default_h)) + title_px
                width = max(
                    min_width,
                    _cell_px(w_cols, container_px, cols, gap_px),
                )
                out = output_dir / f"{wid}.png"
                if verbose:
                    print(f"  rendering {wid}: {width}x{height} "
                          f"-> {out}")
                save_chart_png(
                    opt, out, width=width, height=height,
                    theme=chart_theme, scale=scale,
                    background=background,
                    virtual_time_ms=virtual_time_ms,
                )
                paths.append(out)

    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            visit(tab.get("rows", []))
    else:
        visit(layout.get("rows", []))
    return paths


def save_dashboard_html_png(
    html_path: Union[str, Path],
    output_path: Union[str, Path],
    *,
    width: int = 1400,
    height: int = 1200,
    scale: int = 2,
    virtual_time_ms: int = 4500,
    timeout_s: float = 45.0,
    verbose: bool = False,
) -> Path:
    """Screenshot a full dashboard HTML file (or any local HTML) to PNG.

    Unlike save_dashboard_pngs() which renders one PNG per chart widget,
    this captures the entire dashboard page as a single PNG -- useful for
    gallery thumbnails, email embeds, and report previews.

    Width is the browser viewport; height should be enough to fit the
    full dashboard (scroll height is NOT auto-detected; the PNG is
    clipped to the viewport).

    Raises RuntimeError on Chrome failure.
    """
    html_path = Path(html_path).resolve()
    if not html_path.is_file():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    chrome = find_chrome()
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-sandbox",
        f"--window-size={int(width)},{int(height)}",
        f"--force-device-scale-factor={int(scale)}",
        f"--virtual-time-budget={int(virtual_time_ms)}",
        "--run-all-compositor-stages-before-draw",
        f"--screenshot={output_path}",
        f"file://{html_path}",
    ]
    if verbose:
        print("  [png_export] " + " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout_s)
    if verbose:
        if res.stdout:
            print(res.stdout.strip())
        if res.stderr:
            print(res.stderr.strip(), file=sys.stderr)
    if res.returncode != 0:
        raise RuntimeError(
            f"headless Chrome failed (exit {res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}"
        )
    if not output_path.is_file():
        raise RuntimeError(
            f"Chrome did not write PNG to {output_path}. stderr: "
            f"{res.stderr.strip()}"
        )
    return output_path


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    "render_editor_html",
    "render_dashboard_html",
    "save_chart_png",
    "save_dashboard_pngs",
    "save_dashboard_html_png",
    "find_chrome",
]
