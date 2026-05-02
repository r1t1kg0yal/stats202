# Tool widget (form-driven compute)

Spoke fetched on demand from the dashboards hub. Covers `widget: tool` end-to-end — pricers, scenarios, calculators. For non-tool widgets fetch `widgets.md`; for chart specs fetch `charts.md`.

`widget: tool` is the **interactive** widget. Filters narrow rows; tools take user-supplied values, run a compute function, and route outputs to renderers. Use it for any tile where the user types/picks something and expects a number, table, or chart to update.

The engine is **domain-blind**. A tool def is a JSON dict declaring inputs + outputs + a JS compute string; the engine never knows what a "bond" or "Fed scenario" is.

---

## 1. Where tool defs live (inline only)

**Tool defs live INLINE in the manifest.** There is no runtime tool library, no shared registry, no file lookup at compile time. `tool_def` must be a dict. Every dashboard is fully self-contained: the def + JS compute fn travel with the manifest. PRISM authors a tool def the same way it authors a chart spec — emit the JSON, embed in the manifest, ship.

```json
{"widget": "tool", "id": "taylor", "w": 12,
  "title": "Taylor rule",
  "tool_def": {
    "name": "taylor_rule",
    "compute_js": "function compute(i){...}",
    "inputs":  [...],
    "outputs": [...]
  }}
```

The compiler validates the def, materialises any matrix-input row bindings against `manifest.datasets`, and embeds the full thing into the dashboard payload. Compute runs entirely in-browser; every keystroke triggers a recompute.

**Compute shape.** The canonical authoring form is the flat `compute_js: "function compute(...){...}"` field. The legacy nested shape `compute: {"kind": "js", "source": "..."}` is also accepted — both normalise to the same internal representation at compile time. The `kind` discriminator was a placeholder for a hypothetical Python compute backend that does not exist in v1 (§5); new defs should use `compute_js`.

---

## 2. Cribbing from canonical examples

PRISM doesn't author tool defs from a blank page. Reference templates live in **staging only** at `projects/echarts/dev/tool_examples/<name>/` — a `def.json` schema plus a `compute.js` paired sibling. They are NOT shipped with the payload (the engine has no concept of a tool registry; runtime accepts inline dicts only). Three are shipped today:

| Example | Demonstrates | Use it as a template for |
|---------|-------------|--------------------------|
| `bond_pricer` | scalars, radio mode toggle, Newton iteration, stat headline + cashflow table | YTM / price / yield-to-call solvers, any pricer with a discount-factor schedule |
| `option_bsm` | scalars, multi-output greeks, sweep into a series chart with `x_from: input.X` annotations | Black-Scholes / Bachelier / barrier pricers, payoff curves, any sensitivity sweep |
| `fed_scenario_swaps` | scalars + dynamic-rows matrix (paste-from-Excel), multi-scenario series output | Curve-shock dashboards, dividend schedules, any tool whose inputs are a 2D grid |

These folders are reference-only. The engine never reads them at compile time and they never travel with the payload to PRISM. They exist so that:

1. PRISM (and humans) can read `def.json` + `compute.js` to learn shapes.
2. Demo / test code can materialise a def via `from tool_examples_loader import read_example_tool_def; d = read_example_tool_def("bond_pricer")` (staging-side import; the helper lives at `dev/tool_examples_loader.py`) and inline the result.
3. Vetted, math-correct implementations of canonical tools have a single home in the staging repo.

When PRISM is asked for a tool that resembles one of the examples, the path is: read the example's def + compute, ADAPT to the asked-for shape, emit inline in the manifest. PRISM does NOT reference an example by name in `tool_def`; the engine rejects string refs.

If a custom tool earns shared shelf space, drop a `def.json` + `compute.js` under `dev/tool_examples/<new_name>/` so the next person authoring something similar can crib it. The on-disk files never become runtime assets.

---

## 3. Inline pattern, full example

```python
manifest["layout"]["rows"].append([{
    "widget": "tool", "id": "taylor", "w": 12,
    "title": "Taylor rule",
    "tool_def": {
        "name":       "taylor_rule",
        "compute_js": '''
            function compute(inputs) {
                var pi      = +inputs.inflation_pct  / 100;
                var pi_star = +inputs.target_pct     / 100;
                var r_star  = +inputs.neutral_rate_pct / 100;
                var y       = +inputs.output_gap_pct / 100;
                var phi_pi  = +inputs.phi_pi;
                var phi_y   = +inputs.phi_y;
                var implied = pi_star + r_star
                            + phi_pi * (pi - pi_star)
                            + phi_y * y;
                return {implied_rate: implied};
            }
        ''',
        "inputs": [
            {"id":"inflation_pct",   "kind":"scalar","type":"number","default":3.2},
            {"id":"target_pct",      "kind":"scalar","type":"number","default":2.0},
            {"id":"neutral_rate_pct","kind":"scalar","type":"number","default":0.5},
            {"id":"output_gap_pct",  "kind":"scalar","type":"number","default":-0.5},
            {"id":"phi_pi",          "kind":"scalar","type":"number","default":1.5},
            {"id":"phi_y",           "kind":"scalar","type":"number","default":0.5},
        ],
        "outputs": [
            {"id":"implied_rate","kind":"stat","label":"Implied rate",
              "format":"percent","decimals":2}
        ],
    }
}])
```

The `compute_js` value is a Python triple-quoted string that the JSON serialiser carries verbatim into the dashboard payload. The runtime wraps it in `new Function(...)` and runs it on every input change.

---

## 4. Tool def shape

| Field | Purpose |
|-------|---------|
| `name` / `version` / `title` / `description` | Identification + UI copy |
| `compute_js` | `"function compute(inputs){...}"` — canonical flat shape (preferred) |
| `compute` | `{kind: "js", source: "function compute(inputs){...}"}` — legacy nested shape; both forms normalise to the same internal representation |
| `inputs` | List of input declarations (§4.1) |
| `outputs` | List of output declarations (§4.2) |
| `display.input_panel_w` | Hint for input panel width (informational; layout is auto) |
| `display.headline_stats` | Ordered list of output ids that go in the headline stat row |

### 4.1 Input kinds

Four kinds. Every input is a row in the input panel.

| Kind | Use | Schema |
|------|-----|--------|
| `scalar` | One value (number / date / text / select / radio / toggle) | `{id, kind:"scalar", type, default, label, step?, min?, max?, decimals?, options?, suffix?, show_when?}` |
| `sweep` | Auto-generated range (Phase 4 — not in v1) | reserved |
| `expression` | Function of other inputs (Phase 4 — not in v1) | reserved |
| `matrix` | User-typed / Excel-pasted grid | `{id, kind:"matrix", label, rows_from?, rows?, cols?, cols_from?, cell, paste_enabled?}` |

**Scalar types:**

| `type` | UI | Notes |
|--------|----|-------|
| `number` | numeric input | `step` / `min` / `max` honored |
| `date` | date picker | ISO `YYYY-MM-DD` value |
| `text` | text input | free-form string |
| `select` | dropdown | requires `options`: list of primitives or `{value, label}` |
| `radio` | radio group | same `options` shape |
| `toggle` | checkbox | boolean; `default: true/false` |

`show_when` on a scalar input takes `{<other_input_id>: <expected_value>}` and hides the row when the dependency mismatches. Used for conditional inputs (e.g. a price field that only shows when `input_mode === "price"`). Multiple keys = AND.

**Matrix:**

| Field | Purpose |
|-------|---------|
| `rows_from` | `{dataset, key_col, label_col?}` — rows resolved at compile time from a manifest dataset (e.g. FOMC dates) |
| `rows` | Static row list `[{key, label}, ...]` (used if `rows_from` not set) |
| `cols` | Static col list `[{id, label}, ...]` |
| `cols_from` | Dynamic col binding (Phase 4 — defer) |
| `cell` | `{type:"number", default, step, suffix, decimals, min, max}` — uniform cell type |
| `paste_enabled` | If `true` (default), shows a Paste button that opens a TSV/CSV textarea. Empty cells become 0; rows pad/truncate to grid shape |

Matrix rows are STATIC at compile time when `rows_from.dataset` is given (the dataset's rows become the matrix rows once). Refresh re-runs the build with the latest dataset; the matrix structure refreshes with it.

### 4.2 Output kinds

| Kind | Routes to | Compute fn returns |
|------|-----------|--------------------|
| `stat` / `param` / `kpi` | Headline stat cell | scalar number |
| `table` | HTML table inside the tile | `{columns:[{field,label,align?,format?}], rows:[{...}]}` OR bare row-array (columns from def) |
| `series` | ECharts line / multi-line | `[{x_key, y_key, color_key?}, ...]` long-form OR `{rows:[...]}` |
| `distribution` | ECharts histogram-style line | `[{x, density}, ...]` |

Series outputs declare `x` / `y` / `color?` keys plus `x_format` (`date` / `number`) / `y_format` (`percent` / `bps` / `number`). Annotations of type `vline` accept `x_from: "input.<id>"` to track a scalar input live.

Stat outputs declare `format` (`number` / `percent` / `bps` / `currency` / `integer`), `decimals`, `prefix`, `suffix`. Numeric precision is clamped to the global decimal cap (see hub).

### 4.3 Compute function

A JS function that takes `inputs` and returns `outputs`:

```js
function compute(inputs) {
  // inputs.<scalar_id>     -> the scalar value
  // inputs.<matrix_id>     -> {rows:[{key,label}], cols:[{id,label}], values:[[...]]}
  // returns: {<output_id>: <scalar | array | {rows:[]} | {columns:[],rows:[]}>}
}
```

Pure JS, no DOM access, no network. Errors are caught and shown in the tile's error box. Heavier compute (large simulations, calibration) would land as a separate `compute_python` field with a server-side endpoint — Phase 4+; v1 has only `compute_js`.

---

## 5. What v1 doesn't do (deliberately deferred)

| Feature | Defer to | Why |
|---------|----------|-----|
| `sweep` / `expression` input kinds | Phase 4 | Cross-product evaluator + cycle detection; matrix subsumes user-authored sweeps for v1 |
| `compute_python` (server-side compute) | Phase 4 | Server endpoint + auth + serialisation; v1 cases all fit in JS. Today only `compute_js` (canonical) and `compute: {kind: "js", source: "..."}` (legacy nested) are accepted |
| `bind_from` (cross-widget output → input wiring) | Phase 6 | Sync semantics + cycle detection; not needed for single-tool dashboards |
| Multi-operation defs (`calibrate` / `simulate`) | Phase 5 | Stochastic-model use cases only; defer until first concrete need |
