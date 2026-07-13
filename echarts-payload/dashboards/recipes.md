# Data archetypes and transforms

- **Context ID:** `echarts.recipes`
- **Owns:** `recipe.archetype`, `recipe.reshape`, `recipe.transform`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [charts.md](charts.md#chart-type-catalog-31) and [dashboards_hub.md](../dashboards_hub.md#cross-cutting-authoring-judgment).

This file maps analytical intent and data shape to an authoring pattern. It does not own builds, manifest edits, diagnosis, or persisted script-edit mechanics.

## Data archetypes

| # | Analytical shape | DataFrame shape | Primitive |
|---|---|---|---|
| 1 | Univariate time series | `(date, value)` | `line` |
| 2 | Fixed multi-series time series | `(date, v1, v2, ...)` | `multi_line`, `area` |
| 3 | Dynamic grouped time series | `(date, group, value)` | `multi_line` or `area` with `color` |
| 4 | One-metric cross-section | `(category, value)` | `bar`, `bar_horizontal`, `pie`, `donut`, `funnel` |
| 5 | Grouped cross-section | `(category, group, value)` | stacked/grouped `bar`, grouped `scatter` |
| 6 | Bivariate relationship | `(x, y, [group], [size])` | `scatter`, `scatter_multi` |
| 7 | Distribution | `(value)` | `histogram` |
| 8 | Distribution by group | `(group, value)` | `boxplot` |
| 9 | Current within range | `(category, low, high, current, ...)` | `bullet` |
| 10 | OHLC time series | `(date, open, close, low, high)` | `candlestick` |
| 11 | Daily scalar calendar | `(date, value)` | `calendar_heatmap` |
| 12 | Categorical matrix | `(x_category, y_category, value)` | `heatmap` |
| 13 | Wide co-movement panel | `(date, a, b, ...)` | `correlation_matrix` |
| 14 | Hierarchy | path or `(name, parent, value)` | `treemap`, `sunburst`, `tree` |
| 15 | Flow/network | `(source, target, value)` | `sankey`, `graph` |
| 16 | Multi-dimensional entities | wide dimensions or `(entity, dimension, value)` | `radar`, `parallel_coords` |
| 17 | Single scalar | one numeric value | `gauge` or dataset-backed `kpi` |
| 18 | Rich entity rows | `(id, attr1, attr2, ...)` | `table` |
| 19 | Latest snapshot from time series | any ordered time-series frame | `kpi` with `<ds>.latest.<col>` |
| 20 | Sparse events | `(date, label, ...)` | annotations on a chart |
| 21 | Schedule/agenda | `(date, time, event, ...)` | `table` |
| 22 | Exploratory bivariate panel | wide numeric panel | `scatter_studio` |
| 23 | Two snapshots by category | `(snapshot, category, value)` | `slope` |
| 24 | Central path with uncertainty | `(date, center, lower_*, upper_*)` | `fan_cone` |
| 25 | Signed attribution bridge | `(category, delta, is_total)` | `waterfall` |
| 26 | Two-dimensional proportional allocation | `(x_category, y_category, value)` | `marimekko` |

Choose the simplest primitive that answers the analytical question. Do not use a dual axis when normalization, small multiples, or a relationship chart makes the comparison more interpretable.

## Tidy-data contract

1. One row is one observation; one column is one variable.
2. Dates are columns, not an index.
3. Columns are stable plain-English identifiers.
4. Dataset names are domain nouns, not temporary variable names.
5. MultiIndex columns are flattened before persistence.
6. Numeric fields are explicitly coerced; invalid observations are handled before authoring.
7. Mixed frequencies are resampled according to stock/flow semantics before charting.
8. Every dataset carries enough history for the displayed horizon and enough provenance to identify source and derivation.

```python
frame = frame.reset_index()
frame.columns = [
    "_".join(str(part) for part in col if str(part))
    if isinstance(col, tuple) else str(col)
    for col in frame.columns
]
frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
frame = frame.dropna(subset=["date", "value"])
```

Frequency examples:

```python
month_end_stock = daily_stock.resample("ME").last()
monthly_flow = daily_flow.resample("ME").sum()
monthly_rate = daily_rate.resample("ME").mean()
quarter_end_stock = monthly_stock.resample("QE").last()
```

Resample from economic meaning, not appearance. Haver series stored on business-daily rows may still be monthly or quarterly concepts.

## Common chart compositions

### Long-form time series

```python
long = wide.melt(
    id_vars=["date"],
    var_name="series",
    value_name="value",
)
```

```json
{
  "widget": "chart",
  "id": "curve",
  "w": 6,
  "title": "Curve",
  "spec": {
    "chart_type": "multi_line",
    "dataset": "rates_long",
    "mapping": {
      "x": "date",
      "y": "value",
      "color": "series",
      "y_title": "Rate (%)"
    }
  }
}
```

Long form is best when group membership changes or the same widget/filter logic applies to all series. Keep visible line groups to four.

### Actual versus estimate

Use a semantic state column with `strokeDash`:

```json
{
  "chart_type": "multi_line",
  "dataset": "capex",
  "mapping": {
    "x": "date",
    "y": "capex_bn",
    "color": "company",
    "strokeDash": "state",
    "strokeDashScale": {
      "domain": ["actual", "estimate"],
      "range": [[1, 0], [8, 3]]
    }
  }
}
```

Do not encode actual/estimate only in color; color should preserve entity identity.

### Dual axis

Use only for two series with distinct units and one clear comparison:

```json
{
  "chart_type": "multi_line",
  "dataset": "macro_long",
  "mapping": {
    "x": "date",
    "y": "value",
    "color": "series",
    "dual_axis_series": ["ISM Manufacturing"],
    "y_title": "S&P 500",
    "y_title_right": "ISM index"
  }
}
```

Assert that the right-axis series name exactly matches a persisted value. For three or more distinct units, use `mapping.axes` or normalize to Index=100.

### Range and current

```json
{
  "chart_type": "bullet",
  "dataset": "rv",
  "mapping": {
    "y": "metric",
    "x": "current",
    "x_low": "low_5y",
    "x_high": "high_5y",
    "color_by": "zscore",
    "label": "percentile"
  }
}
```

Use for relative-value screens where current, historical range, and ranking matter together.

### Thesis and watch opening

Place a `thesis` and `watch` markdown card in a 6/6 row, then a 2-up chart row. The opening should state the load-bearing view and what would change it before presenting evidence. Values in prose must come from current data or be framed as analytical interpretation.

## Transform patterns

Transforms receive and return the complete dataset dictionary. Preserve source datasets and create named derived outputs.

### Change and year-over-year

```python
def derive_changes(datasets):
    rates = datasets["rates"].sort_values("date").copy()
    rates["us_10y_change_bp"] = rates["us_10y"].diff() * 100
    rates["us_10y_yoy_bp"] = rates["us_10y"].diff(252) * 100
    datasets["rates_changes"] = rates[
        ["date", "us_10y_change_bp", "us_10y_yoy_bp"]
    ]
    return datasets
```

Choose periods from native frequency. Do not apply 252 to monthly data or 12 to daily data.

### Index to 100

```python
def derive_indexed(datasets):
    frame = datasets["assets"].sort_values("date").copy()
    value_cols = ["spx", "dxy", "wti", "gold"]
    for col in value_cols:
        first = frame[col].dropna().iloc[0]
        frame[f"{col}_index100"] = frame[col] / first * 100
    datasets["assets_index100"] = frame[
        ["date", *[f"{col}_index100" for col in value_cols]]
    ]
    return datasets
```

Use when comparing trajectories across incompatible units.

### Composition

```python
def derive_composition(datasets):
    frame = datasets["funding"].copy()
    components = ["deposits", "wholesale", "equity"]
    total = frame[components].sum(axis=1)
    for col in components:
        frame[f"{col}_pct"] = frame[col] / total * 100
    datasets["funding_composition"] = frame[
        ["date", *[f"{col}_pct" for col in components]]
    ]
    return datasets
```

Validate denominator policy for zero/negative totals before division.

### Cross-dataset join

```python
def derive_funding(datasets):
    balance = datasets["balance_sheet"].set_index("date")
    deposits = datasets["deposits"].set_index("date")
    joined = balance.join(deposits, how="inner", rsuffix="_deposit")
    joined["loan_to_deposit_pct"] = (
        joined["loans"] / joined["total_deposits"] * 100
    )
    datasets["funding"] = joined.reset_index()
    return datasets
```

Choose `inner`, `left`, or `outer` from analytical meaning; report the resulting coverage and as-of alignment.

### Subset projection

```python
def derive_curve(datasets):
    datasets["curve"] = datasets["rates"][
        ["date", "us_2y", "us_5y", "us_10y", "us_30y"]
    ].copy()
    return datasets
```

Use to expose an intentional chart contract without duplicating a pull.

When one filter must target several widgets backed by different datasets, project group subsets with an identical schema so the same bare filter field exists on every target:

```python
def derive_group_subsets(datasets):
    source = datasets["comparisons"].copy()
    columns = ["as_of", "group", "lag_months", "series", "value"]
    for group, output in {
        "Manufacturing": "manufacturing",
        "Construction": "construction",
    }.items():
        datasets[output] = (
            source.loc[source["group"].eq(group), columns]
            .sort_values(["as_of", "lag_months", "series"])
            .reset_index(drop=True)
        )
    return datasets
```

Declare the shared filter with `field: "lag_months"` and exact target ids; never qualify the field with a dataset name.

### Long-form projection

```python
def derive_curve_long(datasets):
    curve = datasets["rates"][
        ["date", "us_2y", "us_5y", "us_10y", "us_30y"]
    ]
    datasets["curve_long"] = curve.melt(
        id_vars=["date"],
        var_name="tenor",
        value_name="yield_pct",
    )
    return datasets
```

### Rolling statistics

```python
def derive_rv(datasets):
    frame = datasets["rates"].sort_values("date").copy()
    spread = (frame["us_10y"] - frame["us_2y"]) * 100
    mean = spread.rolling(252, min_periods=60).mean()
    std = spread.rolling(252, min_periods=60).std()
    datasets["curve_rv"] = pd.DataFrame({
        "date": frame["date"],
        "spread_bp": spread,
        "zscore_1y": (spread - mean) / std,
    })
    return datasets
```

State the observation window in methodology and provenance.

### Rolling realized volatility

For daily rate levels expressed in percent, the canonical five-year realized-volatility contract is: sort by `date`; convert each tenor to daily basis-point changes with `diff() * 100`; compute a 1,260-observation rolling sample standard deviation with `ddof=1` and `min_periods=1260`; annualize by `sqrt(252)`. Output remains in annualized bp.

```python
def derive_realized_vol(datasets):
    frame = datasets["rates"].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame = frame.sort_values("date")
    tenors = ["us_2y", "us_10y", "us_30y"]
    out = pd.DataFrame({"date": frame["date"]})
    for column in tenors:
        changes_bp = pd.to_numeric(
            frame[column], errors="raise"
        ).diff() * 100.0
        out[f"{column}_rv_5y_bp"] = (
            changes_bp.rolling(
                window=1260, min_periods=1260
            ).std(ddof=1) * (252.0 ** 0.5)
        )
    datasets["rates_realized_vol"] = out[
        ["date", "us_2y_rv_5y_bp", "us_10y_rv_5y_bp",
         "us_30y_rv_5y_bp"]
    ]
    return datasets
```

If the supplied input is a price/total-return index rather than a rate level, the prompt must specify log or simple returns and units; do not reuse the rate-difference formula.

### Grouped TIPS relative-value statistics

Input `tips_history` is long-form with `date: datetime64[ns]`, `cusip: string`, `z_spread_bp: float64`, and issue descriptors needed by consumers. For each CUSIP, use observations from its latest date back five calendar years inclusive. The current value is the last non-null `z_spread_bp`; range is min/max; sample standard deviation uses `ddof=1`; percentile is `100 * count(history <= current) / count(history)`; z-score is `(current - mean) / std`. Emit one row per CUSIP:

`cusip`, `as_of`, `current_z_spread_bp`, `low_5y_bp`, `high_5y_bp`, `mean_5y_bp`, `std_5y_bp`, `percentile_5y_pct`, `zscore_5y`, plus explicitly carried issue descriptors such as `maturity_year`.

```python
def derive_tips_rv(datasets):
    history = datasets["tips_history"].copy()
    history["date"] = pd.to_datetime(history["date"], errors="raise")
    history["z_spread_bp"] = pd.to_numeric(
        history["z_spread_bp"], errors="raise"
    )
    rows = []
    for cusip, group in history.sort_values("date").groupby(
        "cusip", sort=True
    ):
        latest = group["date"].max()
        window = group.loc[
            group["date"].between(
                latest - pd.DateOffset(years=5), latest
            ),
            ["date", "z_spread_bp", "maturity_year"],
        ].dropna(subset=["z_spread_bp"])
        values = window["z_spread_bp"]
        if len(values) < 2:
            raise ValueError(
                f"{cusip}: need at least two non-null 5y observations"
            )
        current = float(values.iloc[-1])
        mean = float(values.mean())
        std = float(values.std(ddof=1))
        if std == 0.0:
            raise ValueError(f"{cusip}: 5y z_spread_bp std is zero")
        rows.append({
            "cusip": cusip,
            "as_of": window["date"].iloc[-1],
            "current_z_spread_bp": current,
            "low_5y_bp": float(values.min()),
            "high_5y_bp": float(values.max()),
            "mean_5y_bp": mean,
            "std_5y_bp": std,
            "percentile_5y_pct": float(values.le(current).mean() * 100),
            "zscore_5y": (current - mean) / std,
            "maturity_year": int(window["maturity_year"].iloc[-1]),
        })
    datasets["tips_rv"] = pd.DataFrame(rows)
    return datasets
```

Require at least two non-null observations and non-zero standard deviation per issue before emitting a z-score. State the calendar window, inclusive boundary, `ddof=1`, units, and output names in methodology and field provenance.

For formulas that stay within one dataset and need no grouped/window validation, use the grammar owned by [charts.md](charts.md#manifest-computed-columns). Keep joins, conditional logic, resampling, multi-step reshapes, and validated outputs in `TRANSFORMS`.

## Data budgets

Strict compilation enforces:

- single dataset warning at 10,000 rows and error at 50,000;
- single dataset warning at 1 MB and error at 2 MB;
- total manifest warning at 3 MB and error at 5 MB;
- table warning at 1,000 rows and error at 5,000.

Reduce data according to the analytical task: resample, pre-aggregate, select needed columns, or limit the requested universe. Do not truncate silently.

## Judgment checks

- Is the chart the right analytical form, not merely valid?
- Are comparisons in compatible units or deliberately normalized?
- Does the transformation preserve frequency and as-of meaning?
- Are formula, window, join policy, and upstream columns documented in provenance?
- Does every derived dataset update when its source pulls update?
- Is the output small enough for interactive use without discarding a user-visible requirement?
