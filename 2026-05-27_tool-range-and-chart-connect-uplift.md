# Session changelog: tool widget range inputs + chart connection fixes

**Date:** 2026-05-27  
**Scope:** `projects/echarts/echarts-payload/` (PRISM-bound drag-and-drop payload) + staging tests/examples/galleries  
**Motivation:** (1) Add slider UX to `widget: tool` for live inline chart driving. (2) Fix production failure mode where tool widgets showed stat labels and empty chart boxes but no rendered ECharts canvases (observed on GS Equity Valuation dashboard in PRISM).

---

## Summary

Two related uplifts to the **same subsystem** (`widget: tool`):

| Uplift | What changed | User-visible effect |
|--------|--------------|---------------------|
| **A — Range scalar inputs** | New scalar type `type: "range"` | Tool inputs render as `<input type="range">` + live value readout; dragging recomputes inline charts on every `input` event |
| **B — Chart connection fixes** | Output normalisation, stat DOM, bar charts, empty-state diagnostics | Secondary stats show values; `x_key`/`y_key`/`kind:"bar"` work; empty charts show diagnostic text instead of blank boxes |

No new widget kind was added. Both uplifts extend the existing `widget: tool` pipeline: validate → compile HTML/JS payload → `initTools()` → `compute(inputs)` → output renderers.

---

## Uplift A — Tool scalar `type: "range"`

### Problem

Tool widgets only offered `<input type="number">` for bounded numeric parameters (vol, sweep width, retention rate, etc.). Authors already set `min`/`max`/`step` on number inputs, but the UI remained a text box. Filter-bar sliders existed separately; tool inputs did not.

### Design decision

- **Option chosen:** explicit scalar type `"range"` (not auto-promotion of bounded `number` inputs).
- **Naming:** `"range"` (matches echart_studio knob convention), not `"slider"` (reserved for dashboard filter type `filters[].type: "slider"`).
- **Compute contract unchanged:** `inputs.<id>` is still a JavaScript `Number`, identical to `type: "number"`.
- **Recompute semantics:** recompute on every `input` event during drag (not deferred to `change` like filter sliders), so inline series charts update live.

### Code changes

#### `echarts-payload/echart_dashboard.py`

1. **`VALID_TOOL_INPUT_TYPES`** — added `"range"`:
   ```python
   VALID_TOOL_INPUT_TYPES = {
       "number", "range", "date", "text", "select", "radio", "toggle",
       "list_of_strings",
   }
   ```

2. **`_validate_tool_widget`** — for `kind == "scalar"` and `type == "range"`, require `min` and `max` (mirrors filter slider validation):
   ```python
   if ty == "range":
       for k in ("min", "max"):
           if k not in inp:
               errs.append(_err(f"{ipath}.{k}",
                                f"required for scalar type 'range'"))
   ```

#### `echarts-payload/rendering.py`

**CSS** (tool input panel):

- `.tool-input-row.tool-range .tool-range-row` — flex row for slider + readout
- `.tool-input-row.tool-range input[type=range]` — flex-grow, navy accent color
- `.tool-input-row.tool-range .tool-range-val` — tabular-nums readout (mirrors filter slider styling)
- Dark mode rule for `.tool-range-val`

**Python — `_render_tool_scalar_input()`**

New branch before the default `number` fallback:

```python
if typ == "range":
    mn = inp.get("min", 0)
    mx = inp.get("max", 100)
    step = inp.get("step", 1)
    val = default if default != "" else mn
    # emits:
    # <div class="tool-input-row tool-range" ...>
    #   <label>...</label>
    #   <div class="tool-range-row">
    #     <input type="range" id="tool-{wid}-in-{iid}" min=... max=... step=... value=.../>
    #     <span id="tool-{wid}-in-{iid}-val" class="tool-range-val">...</span>
    #   </div>
    # </div>
```

**JavaScript — tool runtime**

| Function | Change |
|----------|--------|
| `_toolWireScalarInputs` | Added `input[type=range]` to control selector; on `input`/`change`, calls `_toolUpdateRangeDisplay(el)` then `_toolOnScalarChange` |
| `_toolFormatRangeDisplay(val, inp)` | **New.** Formats slider readout using `inp.decimals` or inferred from `inp.step` |
| `_toolUpdateRangeDisplay(el)` | **New.** Updates `#tool-{wid}-in-{iid}-val` span during drag |
| `_toolReadScalarValue` | `typ === 'number' \|\| typ === 'range'` both read via `document.getElementById(nid).value` → `Number` |
| `initTools` | When seeding `initial_inputs` for `type === 'range'`, sets `el.value` and calls `_toolUpdateRangeDisplay(el)` |

#### `echarts-payload/dashboards/widget_tool.md`

**§4.1 Scalar types table** — added row:

| `type` | UI | Notes |
|--------|----|-------|
| `range` | slider + value readout | `min` / `max` required; `step` / `decimals` / `suffix` optional. Compute receives a number identical to `type: "number"` |

#### `echarts-payload/dashboards/canonical_showcase.json`

Black-Scholes tool (`option_bsm` inline def):

- `vol`: `"type": "number"` → `"type": "range"`
- `sweep_pct`: `"type": "number"` → `"type": "range"`

Tab 7 markdown note updated to mention `range` in scalar type list and BSM range sliders.

#### `dev/tool_examples/option_bsm/def.json`

Staging reference template (not shipped to PRISM):

- `vol`: `"type": "range"`
- `sweep_pct`: `"type": "range"`

#### `dev/tests.py` — new tests in `TestToolWidget`

| Test | Asserts |
|------|---------|
| `test_tool_scalar_range_ok` | Manifest with `type: "range"` validates |
| `test_tool_scalar_range_missing_min` | Missing `min` fails validation |
| `test_compile_tool_range_emits_slider_html` | Compiled HTML contains `type="range"`, `tool-range-val`, `tool-bond-in-vol-val` |

#### `dev/_gallery_tool_range_input.py`

New mini-gallery script. Compiles two dashboards:

1. **A_linear_range** — single slope range input → inline line series
2. **B_bsm_vol_sweep** — canonical `option_bsm` with range sliders on vol + sweep_pct

Output: `dev/output/_recent/2026-05-27_1200_tool-range-input/`

---

## Uplift B — Tool chart connection fixes

### Problem (GS Equity Valuation screenshot)

Observed in PRISM: tool widget with many outputs showed:

- Top headline stats populated correctly
- Long vertical list of stat **labels** with no values (STEP 1 - P/B, STEP 1 - P/E, …)
- Empty white chart boxes where bar/line charts expected (`budget_bar`, growth paths)

Root causes traced in engine:

| # | Bug | Mechanism |
|---|-----|-----------|
| 1 | Secondary stats dead | When `display.headline_stats` is explicit, stats **not** in that list go to `other_outs` and were rendered as generic sections with only `.section-label` — no `.tool-stat-cell` DOM. `_toolRenderStat()` queries `.tool-stat-cell[data-output-id=...]` and silently no-ops. |
| 2 | `x_key` / `y_key` ignored | Docs/examples used `x_key`/`y_key`; runtime JS only read `out.x`/`out.y`. Series got `undefined` coordinates → empty charts. |
| 3 | `kind: "bar"` unsupported | `budget_bar`-style outputs used `kind: "bar"`, not in output renderer switch; fell through to generic host with no chart canvas. |
| 4 | Silent empty charts | `_toolRenderSeries` returned early on `!val` or `rows.length === 0` with no user-visible feedback. |
| 5 | `stat_grid` output kind unimplemented | Declared in `VALID_TOOL_OUTPUT_KINDS` but no JS renderer or compile-time HTML host. |
| 6 | String stat values | Narrative stats (text) were forced through numeric formatter. |

### Code changes

#### `echarts-payload/echart_dashboard.py`

**New function `_normalize_tool_output(out)`** — called for every output in `normalize_tool_def()`:

```python
def _normalize_tool_output(out: Dict[str, Any]) -> Dict[str, Any]:
    o = dict(out)
    kind = o.get("kind")
    if kind in ("bar", "bar_horizontal"):
        o["kind"] = "series"
        o.setdefault("chart_type", kind)
    elif kind == "scalar":
        o["kind"] = "stat"
    if o.get("x_key") and not o.get("x"):
        o["x"] = o["x_key"]
    if o.get("y_key") and not o.get("y"):
        o["y"] = o["y_key"]
    if o.get("color_key") and not o.get("color"):
        o["color"] = o["color_key"]
    return o
```

**`normalize_tool_def()`** — outputs list now mapped through `_normalize_tool_output` before validation/rendering. Original keys (`x_key`, etc.) are preserved; `x`/`y`/`color` are populated when missing.

#### `echarts-payload/rendering.py`

**CSS additions:**

- `.tool-chart-empty` — dashed border placeholder for missing chart data
- `.tool-output-stat-grid` — grid layout for stat_grid output kind
- `.tool-stat-section .tool-stat-cell` — styled secondary stat cards

**Python — `_render_tool_widget()` output HTML**

New branches in `other_outs` loop:

```python
elif okind == "stat_grid":
    # section-label + .tool-output-stat-grid-host

elif okind in ("stat", "param", "kpi", "scalar"):
    # .tool-stat-section containing .tool-stat-cell with label + value placeholder
    # (fixes secondary stats outside headline_stats)
```

Previously, non-table/non-series/non-distribution outputs fell into generic `else` with only `.tool-output-host` (no stat cell, no chart host).

**JavaScript — refactored / new helpers**

| Function | Purpose |
|----------|---------|
| `_toolShowChartEmpty(host, msg)` | **New.** Renders diagnostic message; disposes stale ECharts instance |
| `_toolClearChartHost(host)` | **New.** Clears empty placeholder before successful render |
| `_toolInitChart(host)` | **New.** Shared ECharts init (theme-aware, cached in `TOOL_CHARTS`) |
| `_toolRenderStatGrid(tile, out, val)` | **New.** Renders `[{label, value, ...}]` or `{stats: [...]}` into grid |
| `_toolFmtStat(out, val)` | Pass through string values when no numeric `format` |
| `_toolRenderSeries(...)` | **Rewritten** — see below |
| `_toolRenderDistribution(...)` | Uses empty-state helpers + `_toolInitChart` + `resize()` |

**`_toolRenderSeries` — full rewrite**

Key behavioral changes:

1. **Key resolution:** `xKey = out.x || out.x_key || 'x'` (same for y, color)
2. **`chart_type` support:**
   - `"line"` (default) — existing line / multi-line via `color` grouping
   - `"bar"` — categorical x-axis, numeric y-axis
   - `"bar_horizontal"` — categorical y-axis, numeric x-axis
3. **Empty states:** explicit messages naming output id and expected `{x, y}` shape
4. **Post-render:** `inst.resize()` after `setOption`
5. **Annotations:** vline `markLine` applied to `opt.series[0]` (works for bar + line)

**`_toolRenderOutputs` switch** — added:

```javascript
case 'stat_grid':
  _toolRenderStatGrid(tile, out, val);
  break;
```

(`stat`/`param`/`kpi`/`scalar` still route to `_toolRenderStat`, which now finds cells in both headline row and secondary stat sections.)

#### `echarts-payload/dashboards/widget_tool.md`

**§4.2 Output kinds table** — expanded:

- `stat` row notes secondary stat row when not in `headline_stats`; accepts text
- `series` row documents `chart_type`, bar kinds, `x_key`/`y_key` aliases
- New `stat_grid` row with return shape

**Series declaration paragraph** updated with normalisation rules for `bar` kind and key aliases.

#### `dev/tests.py` — new tests in `TestToolWidget`

| Test | Asserts |
|------|---------|
| `test_tool_output_bar_kind_normalizes_to_series` | `load_tool_def` maps `kind:"bar"` → `series` + `chart_type:"bar"` + `x`/`y` from keys |
| `test_tool_secondary_stats_get_stat_cells` | Explicit `headline_stats` leaves secondary stats with `tool-stat-section` DOM |
| `test_tool_series_x_key_y_key_renders_chart_host` | `kind:"bar"` + `x_key`/`y_key` emits `id="tool-bond-out-budget_bar"` and normalised `"chart_type": "bar"` in payload |

#### `dev/_gallery_tool_chart_connect.py`

New mini-gallery reproducing GS-equity-valuation layout pattern:

- 10 inputs (4× `range`, 6× `number`)
- 5 headline stats + 5 secondary stats + 1 narrative stat
- `budget_bar` output (`kind: "bar"`, `x_key`/`y_key`)
- `growth_path` output (`kind: "series"`, `x_key`/`y_key`)

Output: `dev/output/_recent/2026-05-27_1230_tool-chart-connect/valuation_repro.html`

---

## Complete file manifest

### PRISM-bound payload (drag-and-drop)

| File | Uplift A | Uplift B | Nature of edit |
|------|:--------:|:--------:|----------------|
| `echarts-payload/echart_dashboard.py` | ✓ | ✓ | Schema + validation + output normalisation |
| `echarts-payload/rendering.py` | ✓ | ✓ | CSS, Python HTML emit, embedded JS runtime |
| `echarts-payload/dashboards/widget_tool.md` | ✓ | ✓ | Authoring skill / PRISM L2 spoke |
| `echarts-payload/dashboards/canonical_showcase.json` | ✓ | — | BSM vol/sweep_pct → range; Tab 7 note |

### Staging only (does not ship to PRISM)

| File | Purpose |
|------|---------|
| `dev/tests.py` | 6 new unit tests (3 per uplift) |
| `dev/tool_examples/option_bsm/def.json` | Reference template: vol/sweep_pct as range |
| `dev/_gallery_tool_range_input.py` | Range input mini-gallery |
| `dev/_gallery_tool_chart_connect.py` | Chart connection repro gallery |
| `dev/output/_recent/2026-05-27_1200_tool-range-input/` | Compiled gallery artifacts |
| `dev/output/_recent/2026-05-27_1230_tool-chart-connect/` | Compiled gallery artifacts |

### Not changed

- `dashboards_hub.md` — tool input kinds table still lists 4 input kinds at kind level (`scalar`/`sweep`/`expression`/`matrix`); scalar **types** are documented in `widget_tool.md` spoke
- `VALID_TOOL_OUTPUT_KINDS` set membership — no new kinds added; `bar` normalised to `series` at compile time instead
- `kind: "sweep"` input — still Phase 4 / not implemented
- `bind_from` cross-widget wiring — still Phase 6
- Filter bar `type: "slider"` — unchanged (separate code path from tool range inputs)
- No new `widget:` catalog entry

---

## Authoring contract (post-uplift)

### Range input (Uplift A)

```json
{
  "id": "vol",
  "kind": "scalar",
  "type": "range",
  "label": "Vol (%)",
  "default": 20,
  "min": 0.01,
  "max": 500,
  "step": 1,
  "decimals": 2
}
```

### Chart outputs (Uplift B)

**Bar chart (normalised from `kind: "bar"`):**

```json
{
  "id": "budget_bar",
  "kind": "bar",
  "label": "Growth budget",
  "x_key": "label",
  "y_key": "value"
}
```

Compute must return:

```javascript
budget_bar: [
  {label: "Organic g", value: 8.0},
  {label: "Retained", value: 2.1},
  {label: "Buyback", value: 6.0}
]
```

**Line/series chart:**

```json
{
  "id": "growth_path",
  "kind": "series",
  "x_key": "year",
  "y_key": "price",
  "x_format": "number",
  "y_format": "currency"
}
```

**Headline vs secondary stats:**

```json
"display": {
  "headline_stats": ["step2_implied_g", "step2_actual_g", "step2_gap"]
}
```

Any `kind: "stat"` output **not** listed in `headline_stats` now renders as a secondary stat card with live value (previously: label-only ghost).

---

## Runtime data flow (unchanged shape, fixed wiring)

```
manifest.tool_def
       │
       ▼
normalize_tool_def()          ← NEW: _normalize_tool_output per output
       │
       ▼
validate_manifest()
       │
       ▼
compile_dashboard() → HTML + PAYLOAD.tools[wid]
       │
       ▼
initTools()
  ├─ seed TOOL_STATE
  ├─ _toolWireScalarInputs()   ← range: input event → recompute
  └─ _toolRunCompute(wid)
         │
         ├─ compute(inputs) → {output_id: value, ...}
         └─ _toolRenderOutputs()
                ├─ stat/param/kpi/scalar → _toolRenderStat
                ├─ stat_grid           → _toolRenderStatGrid  (NEW)
                ├─ series (+ bar)      → _toolRenderSeries    (REWRITTEN)
                ├─ distribution        → _toolRenderDistribution
                └─ table               → _toolRenderTable
```

---

## Test results

All **31** tests in `TestToolWidget` pass after both uplifts:

```bash
cd projects/echarts && python3 dev/tests.py TestToolWidget
# Ran 31 tests — OK
```

New tests added this session: **6** (3 range + 3 chart-connect).

---

## PRISM promotion

Copy updated payload files from `projects/echarts/echarts-payload/` to PRISM `ai_development/dashboards/` + `context/modules/static/tools/dashboards/widget_tool.md`.

Existing dashboards authored with `x_key`/`y_key` or `kind:"bar"` will start working without manifest edits (normalisation is compile-time). Dashboards with secondary stats outside `headline_stats` will populate values on next compile.

If charts still show dashed empty-state text after promotion, the compute function is returning no rows for that output id — the engine now surfaces that explicitly instead of a blank box.

---

## Known limitations (unchanged by this session)

- Tool series renderer supports `line`, `bar`, `bar_horizontal` only — not full chart catalog (pie, scatter, etc.)
- No compile-time requirement that every tool widget must declare a chart output (validation warning not added)
- Heavy compute on every range drag tick — no debounce knob yet (`recompute_on: "change"` not implemented)
- Local staging galleries warn if `ai_development/mysite/news/static/js/echarts.js` mirror missing — charts need inlined echarts in compiled HTML or PRISM runtime path
