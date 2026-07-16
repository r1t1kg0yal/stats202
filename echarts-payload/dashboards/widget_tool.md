# Tool widgets

- **Context ID:** `echarts.tool_widget`
- **Owns:** `tool.definition`, `tool.input_kind`, `tool.output_kind`, `tool.compute`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards_hub.md](../dashboards_hub.md#manifest-skeleton) and [template_crud.md](template_crud.md#widget-operations) for edits.

`widget: "tool"` is a form-driven in-browser calculator. Use it when the viewer supplies values and expects stats, a table, a distribution, or a series to recompute.

## Tool definition

Tool definitions live inline in the manifest; `tool_def` is a dictionary, never a file/string reference. The canonical compute form is `compute_js`.

```json
{
  "widget": "tool",
  "id": "taylor",
  "w": 12,
  "title": "Taylor rule",
  "tool_def": {
    "name": "taylor_rule",
    "description": "Policy-rate scenario calculator",
    "compute_js": "function compute(inputs) { return {implied_rate: 0}; }",
    "inputs": [],
    "outputs": []
  }
}
```

The accepted alternate form is `compute: {"kind": "js", "source": "function compute(inputs){...}"}`. Author definitions with `compute_js`.

The definition exists only in `manifest_template.json`. `build.py` must not author or interpolate it. Edit an existing tool with typed manifest operations while preserving the complete current `tool_def`.

### Pure calculator dashboard

When every output is computed only from viewer inputs, use the legal tool-only path in [build.md](build.md#tool-only-build): `PULLS = {}`, `datasets = {}`, and `TRANSFORMS = []`. Do not create a placeholder dataset. A matrix `rows_from` or any sibling data-bound widget makes the build data-dependent and requires the normal pipeline.

## Compute safety

`compute_js` is literal JavaScript. It receives current values in `inputs` and returns an object keyed by output ids.

The Python compiler validates the declaration and static source contract but never executes or translates arbitrary `compute_js`. Every tool panel therefore has `coverage="runtime_unverified"`, `data_state="RUNTIME_UNVERIFIED"`, and at least `REVIEW_REQUIRED`. Inspect `review.panel(id)` and acknowledge that exact unverified-runtime boundary; this accepts the coverage limit, not the output's correctness. Then build, execute representative/default/edge inputs in the browser, and withhold delivery until those browser checks pass.

```js
function compute(inputs) {
  var inflation = +inputs.inflation_pct / 100;
  var target = +inputs.target_pct / 100;
  var neutral = +inputs.neutral_rate_pct / 100;
  var outputGap = +inputs.output_gap_pct / 100;
  return {
    implied_rate:
      neutral + inflation
      + (+inputs.phi_pi) * (inflation - target)
      + (+inputs.phi_y) * outputGap
  };
}
```

Rules:

- Put Python-supplied defaults in `inputs[].default`, not inside JS source.
- Never interpolate Python `None`, booleans, timestamps, decimals, NaN, or infinities into JS.
- Return every declared output key.
- Use pure deterministic JS: no DOM, network, or hidden global state.
- Keep large simulations/server-side models outside the tool widget.
- Validation blocks Python-literal leakage and missing output keys.

## Input kinds

The closed input-kind enum is:

`scalar`, `sweep`, `expression`, `matrix`

| Kind | Schema and use |
|---|---|
| `scalar` | `{id, kind:"scalar", type, default, label?, step?, min?, max?, decimals?, options?, suffix?, show_when?}` |
| `matrix` | `{id, kind:"matrix", rows_from? or rows?, cols?, cols_from?, cell, paste_enabled?}` |
| `sweep` | Reserved declarative range input; do not author without an engine-supported concrete schema |
| `expression` | Reserved derived-input kind; do not author without an engine-supported concrete schema |

### Scalar types

Accepted scalar `type` values:

`number`, `range`, `date`, `text`, `select`, `radio`, `toggle`, `list_of_strings`

| Type | Contract |
|---|---|
| `number` / `range` | Numeric input; `step`, `min`, `max` apply |
| `date` | ISO `YYYY-MM-DD` |
| `text` | Free-form string |
| `select` / `radio` | `options` is primitives or `{value, label}` objects |
| `toggle` | Boolean |
| `list_of_strings` | String list input |

Scalar `show_when` takes `{other_input_id: expected_value}`; multiple keys are ANDed.

### Matrix inputs

| Field | Purpose |
|---|---|
| `rows_from` | `{dataset, key_col, label_col?}`; rows bind from a manifest dataset during compile |
| `rows` | Static `[{key, label}, ...]` when not dataset-bound |
| `cols` | Static `[{id, label}, ...]` |
| `cols_from` | Dynamic column binding when supported by the authored use case |
| `cell` | Uniform cell contract such as `{type:"number", default, step, suffix, decimals, min, max}` |
| `paste_enabled` | Enables TSV/CSV paste; default true |

Dataset-bound row structure is refreshed on each dashboard build.

Inside `compute_js`, a matrix input value is exactly `{rows, cols, values}`: `rows` and `cols` are the authored descriptor lists and `values` is a row-major two-dimensional array, so cell `[r][c]` corresponds to `rows[r]` and `cols[c]`. Paste guidance belongs in a visible markdown widget beside the tool, not in an invented matrix hint key.

## Output kinds

The closed output-kind enum is:

`stat`, `scalar`, `param`, `kpi`, `series`, `table`, `stat_grid`, `distribution`

| Kind | Compute return | Rendering |
|---|---|---|
| `stat` / `scalar` / `param` / `kpi` | Number or scalar | Headline stat cell |
| `stat_grid` | Object/list matching declared stat items | Dense stat grid |
| `table` | Bare row list or `{columns:[...], rows:[...]}` | Table |
| `series` | Long-form row list or `{rows:[...]}` | ECharts line/multi-line |
| `distribution` | `[{x, density}, ...]` or declared equivalent | Distribution chart |

Stat-like outputs accept `format` (`number`, `percent`, `bps`, `currency`, `integer`), `decimals`, `prefix`, and `suffix`.

Use these complete declaration/return shapes:

```python
# Table
{"id": "cashflows", "kind": "table", "label": "Cashflows",
 "columns": [
     {"field": "period", "label": "#", "format": "integer"},
     {"field": "cashflow", "label": "Cashflow", "format": "number:2"},
 ]}
# compute return: cashflows: [{period: 1, cashflow: 2.25}, ...]
# or cashflows: {columns: [...], rows: [...]}

# Stat grid
{"id": "greeks", "kind": "stat_grid", "label": "Greeks"}
# compute return: greeks: [
#   {id: "delta", label: "Delta", value: 0.52,
#    format: "number", decimals: 4, suffix: ""}
# ]

# Series with input-tracking vline
{"id": "payoff", "kind": "series", "label": "P&L",
 "x": "spot", "y": "pnl", "x_format": "number",
 "y_format": "number", "chart_type": "line",
 "annotations": [
     {"type": "vline", "x_from": "input.spot", "label": "Spot"},
 ]}
# compute return: payoff: [{spot: 80.0, pnl: -4.2}, ...]
```

Table columns are declaration objects with `field`, optional `label`, `format`, and `align`; returned object rows may be dictionaries or arrays aligned to columns. Stat-grid returned items carry their own `id`/`label`/`value` and optional stat formatting. Series output declares x/y/color field names, optional `chart_type`, `x_format` (`date` or `number`), and `y_format` (`percent`, `bps`, or `number`). `percent` displays returned percent points; `bps` expects decimal-rate values and converts by 10,000. A vline annotation may use `x_from: "input.<id>"` to follow a scalar input.

## Deterministic calculator contracts

### Fixed-coupon bond

Inputs are `face` (currency), `coupon_pct` (annual percent), `freq` in `{1,2,4,12}`, `settlement` and `maturity` ISO dates, `input_mode` in `{"price","yield"}`, `price` per face, and `ytm_pct` annual nominal percent compounded `freq` times. Set `T = (maturity - settlement) / 365.25`, `N = max(1, round(T * freq))`, periodic coupon `c = face * coupon_pct / 100 / freq`, and cashflow `CF_i = c + face` only at `i=N`. Price is `sum(CF_i / (1 + ytm/freq)^i)`. In price mode solve decimal YTM with bounded Newton iteration (80 iterations, absolute price tolerance `1e-10`, yield bound `[-0.5, 5]`); in yield mode calculate price directly. For a price/YTM solver, return stat-grid items `price` and `ytm_pct = 100 * ytm`, plus table rows `{period, yrs, cashflow, df, pv}`. Declare only outputs the requested calculator renders; do not add duration, convexity, or DV01 merely because they can be derived.

### Black-Scholes-Merton

Inputs are `kind` (`call`/`put`), positive `spot`, positive `strike`, `tte` in years, `vol`, `rate`, and `div` in percent. Convert the last three to decimals. With continuous dividend yield, `d1 = [ln(S/K) + (r-q+0.5*sigma^2)T] / (sigma*sqrt(T))`, `d2 = d1 - sigma*sqrt(T)`. Call price is `S*exp(-qT)N(d1) - K*exp(-rT)N(d2)`; put price is `K*exp(-rT)N(-d2) - S*exp(-qT)N(-d1)`. Define the normal CDF exactly:

```js
function normCDF(x) {
  var ax = Math.abs(x);
  var t = 1 / (1 + 0.2316419 * ax);
  var pdf = 0.3989422804014327 * Math.exp(-0.5 * ax * ax);
  var upper = 1 - pdf * t * (
    0.319381530 + t * (-0.356563782 + t * (
      1.781477937 + t * (-1.821255978 + t * 1.330274429)
    ))
  );
  return x >= 0 ? upper : 1 - upper;
}
```

Return price plus delta, gamma, vega per one vol-percentage-point (`raw vega / 100`), theta per calendar day (`annual theta / 365`), and rho per one rate-percentage-point (`raw rho / 100`). For the series output, evaluate current model value at 41 evenly spaced spots from `0.8*S` through `1.2*S` and return `{spot, pnl: swept_price - current_price}`; annotate current spot and strike with `x_from`.

## Data-backed literal defaults

When verified persisted data seeds a tool, read the current CSV during authoring, sort by the declared date field, validate the required latest-row values, and bake Python scalars into complete literal `inputs[].default` values before the manifest operation:

```python
latest = wages.sort_values("date").iloc[-1]
defaults = {
    "ahe_mom_pct": float(latest["ahe_mom_pct"]),
    "ahe_yoy_pct": float(latest["ahe_yoy_pct"]),
    "cpi_yoy_pct": float(latest["cpi_yoy_pct"]),
}
updated_inputs = copy.deepcopy(current_tool_def["inputs"])
for item in updated_inputs:
    if item["id"] in defaults:
        item["default"] = defaults[item["id"]]
# patch: {"tool_def": {"inputs": updated_inputs}} — deep-merge keeps compute_js/outputs
```

These are author-time defaults, not live bindings. To append methodology without losing inherited text: describe/inspect; deep-merge `patch_metadata` with the complete new `methodology` string (or concatenate onto the current value and patch that key).

## Scalar calculator pattern

```python
{
    "widget": "tool",
    "id": "taylor",
    "w": 12,
    "title": "Taylor rule",
    "tool_def": {
        "name": "taylor_rule",
        "compute_js": """
function compute(i) {
  var pi = +i.inflation_pct / 100;
  var target = +i.target_pct / 100;
  var neutral = +i.neutral_rate_pct / 100;
  var gap = +i.output_gap_pct / 100;
  return {
    implied_rate:
      neutral + pi
      + (+i.phi_pi) * (pi - target)
      + (+i.phi_y) * gap
  };
}
""",
        "inputs": [
            {"id": "inflation_pct", "kind": "scalar",
             "type": "number", "default": 3.2, "label": "Inflation", "suffix": "%"},
            {"id": "target_pct", "kind": "scalar",
             "type": "number", "default": 2.0, "label": "Target", "suffix": "%"},
            {"id": "neutral_rate_pct", "kind": "scalar",
             "type": "number", "default": 0.5, "label": "Neutral", "suffix": "%"},
            {"id": "output_gap_pct", "kind": "scalar",
             "type": "number", "default": -0.5, "label": "Output gap", "suffix": "%"},
            {"id": "phi_pi", "kind": "scalar",
             "type": "number", "default": 1.5},
            {"id": "phi_y", "kind": "scalar",
             "type": "number", "default": 0.5},
        ],
        "outputs": [{
            "id": "implied_rate",
            "kind": "stat",
            "label": "Implied rate",
            "format": "percent",
            "decimals": 2,
        }],
    },
}
```

## Matrix scenario pattern

```python
{
    "widget": "tool",
    "id": "fed_scenarios",
    "w": 12,
    "title": "Fed path scenarios",
    "tool_def": {
        "name": "fed_path_scenarios",
        "compute_js": """
function compute(i) {
  var rows = i.path.rows;
  var cols = i.path.cols;
  var values = i.path.values;
  var output = [];
  for (var c = 0; c < cols.length; c++) {
    var level = +i.starting_rate;
    for (var r = 0; r < rows.length; r++) {
      level += (+values[r][c]) / 100;
      output.push({
        date: rows[r].key,
        scenario: cols[c].label,
        rate: level
      });
    }
  }
  return {paths: output};
}
""",
        "inputs": [
            {"id": "starting_rate", "kind": "scalar",
             "type": "number", "default": 4.5, "suffix": "%"},
            {
                "id": "path",
                "kind": "matrix",
                "rows_from": {
                    "dataset": "fomc_dates",
                    "key_col": "date",
                    "label_col": "label",
                },
                "cols": [
                    {"id": "base", "label": "Base"},
                    {"id": "hawk", "label": "Hawkish"},
                    {"id": "dove", "label": "Dovish"},
                ],
                "cell": {
                    "type": "number", "default": 0,
                    "step": 25, "suffix": "bp",
                },
                "paste_enabled": True,
            },
        ],
        "outputs": [{
            "id": "paths",
            "kind": "series",
            "x": "date",
            "y": "rate",
            "color": "scenario",
            "x_format": "date",
            "y_format": "percent",
        }],
    },
}
```

## Editing a tool

Use `describe_dashboard` (or inspect for heal/triage) to identify the stable widget id. Deep-merge into `tool_def` and replace only list-valued keys that change (`inputs` replaces; `compute_js` / `outputs` are preserved):

```python
updated_inputs = copy.deepcopy(current_tool_def["inputs"])
target = next(item for item in updated_inputs if item["id"] == "phi_pi")
target["default"] = 1.7

apply_manifest_operations(
    before,  # describe_dashboard / inspect_dashboard state
    [{
        "op": "update_widget",
        "selector": {"id": "taylor"},
        "patch": {"tool_def": {"inputs": updated_inputs}},
    }],
)
```

Do not rebuild the containing tab or widget from memory. A manifest root replacement can destroy the only persisted copy of the tool definition.

## Choice checks

- Use a filter when a viewer is narrowing existing rows.
- Use a tool when viewer inputs drive a new calculation.
- Use a chart drawer when the interaction is a supported transform/view choice on one chart.
- Keep the model explainable in the methodology and output labels.
- Verify all declared outputs with representative and edge-case inputs in the browser before delivery; Python review never claims runtime execution.
