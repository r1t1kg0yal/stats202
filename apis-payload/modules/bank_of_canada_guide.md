# Bank of Canada (Valet)

Sandbox name: `bank_of_canada_client`
Base: `https://www.bankofcanada.ca/valet`
Auth: None
Transport: GS proxy via `session_and_auth` (Bucket A)
Universe: every Valet series and group is embedded (~15,600 series, ~2,400 groups, name -> label). Search the index offline to find the right series/group BEFORE any network call; pull observations live.

## Triggers

**Primary** — Canadian monetary and financial markets data: the Bank of Canada policy (overnight target) rate, CORRA, Government of Canada benchmark bond yields (2/3/5/7/10-year, long), daily/monthly/annual FX rates vs the Canadian dollar (USD/CAD, EUR/CAD, etc.), monetary aggregates (M1/M2/M2++), the Bank of Canada commodity price index (BCPI), and related rates/spreads.

**Not for** — Canadian CPI / GDP / labour / trade / housing (use `statcan_client`); US rates/FX (FRED / Treasury / NY Fed); cross-border banking (BIS).

## Two primitives: series and groups

- **series** — one time series addressed by name, e.g. `V39079` (overnight rate target), `AVG.INTWO` (CORRA), `FXUSDCAD`, `BD.CDN.10YR.DQ.YLD`.
- **group** — a named bundle of related series, e.g. `FX_RATES_DAILY` (all daily FX vs CAD), `bond_yields_benchmark` (all GoC benchmark tenors). One call returns every series in the group.

## Discovery Workflow (progressive disclosure)

```python
# 1. SEARCH the embedded index (offline; name or label; all tokens match)
bank_of_canada_client.search_series("benchmark 10 year")
bank_of_canada_client.search_groups("exchange rate")
bank_of_canada_client.list_groups(search="bond yield")

# 2. INSPECT a group's members / a series' metadata (live)
bank_of_canada_client.get_group_detail("bond_yields_benchmark")
# -> {label, description, series: {"BD.CDN.2YR.DQ.YLD": "2 year", ...}}
bank_of_canada_client.get_series_detail("FXUSDCAD")

# 3. GET observations (live)
bank_of_canada_client.get_observations("FXUSDCAD", recent=5)
bank_of_canada_client.get_observations(["V39079", "AVG.INTWO"], start_date="2026-01-01")
bank_of_canada_client.get_group_observations("FX_RATES_DAILY", recent=1)
bank_of_canada_client.latest("policy_rate")           # catalog fast path
```

## Curated catalog — Canadian rates / FX / monetary fast path

`bank_of_canada_client.list_catalog()` / `search_catalog(kw)`. `latest(alias)` returns the most-recent observation for series aliases.

| Alias | Series / Group | What |
|---|---|---|
| `policy_rate` | V39079 | Overnight rate target (the BoC policy rate, %) |
| `corra` | AVG.INTWO | Canadian Overnight Repo Rate Average, CORRA (%) |
| `goc_2y` / `goc_5y` / `goc_10y` / `goc_long` | BD.CDN.\*.DQ.YLD | GoC benchmark bond yields by tenor (%) |
| `usdcad` / `eurcad` / `gbpcad` / `jpycad` | FX\*CAD | Daily average FX rate vs CAD |
| `bcpi_total` / `bcpi_energy` | M.BCPI / M.ENER | Bank of Canada commodity price index (monthly) |
| `fx_daily` | group FX_RATES_DAILY | All daily FX rates vs CAD in one call |
| `benchmark_yields` | group bond_yields_benchmark | The full GoC benchmark curve in one call |

## Recipes

Catalog aliases work anywhere a name is accepted (`get_observations("corra", ...)`, `get_group_observations("benchmark_yields")`, `latest("policy_rate")`). Relative windows: `recent=N` (N observations), `recent_weeks`/`recent_months`/`recent_years` (calendar) — use one, mutually exclusive with `start_date`/`end_date`. `end_date` defaults to the latest available date when omitted.

```python
# Latest policy rate (catalog fast path) -> {value, date, series, label}
boc = bank_of_canada_client
pr = boc.latest("policy_rate")

# CORRA vs policy rate, last 30 obs, aligned in a wide DataFrame
rows = boc.get_observations(["corra", "policy_rate"], recent=30)
df = boc.observations_to_dataframe(rows)               # wide: one col per series, datetime index
df["spread_bps"] = (df["AVG.INTWO"] - df["V39079"]) * 100

# Full GoC benchmark curve as of the latest date (one group call)
curve = boc.get_group_observations("benchmark_yields", recent=1)
points = {s["label"]: list(s["observations"].values())[0] for s in curve}

# Long history by date range
goc10 = boc.get_observations("goc_10y", start_date="2020-01-01")
```

`observations_to_dataframe(rows)` returns a wide DataFrame (one column per series name, datetime index); pass `wide=False` for long form (name/label/date/value rows).

## Output schema (observations object)

`get_observations(...)` / `get_group_observations(...)` return `list[dict]`:

```python
{
    "name":         "FXUSDCAD",
    "label":        "USD/CAD",
    "description":  "Daily average exchange rate: ... US dollar in Canadian dollars ...",
    "observations": {"2026-05-29": 1.3798, "2026-05-28": 1.3809, ...},   # date -> float|None
}
```

`latest(...)` returns `{value, date, series, label}`. Dates are `YYYY-MM-DD`; values coerced to `float`.

## Decision table — which client for which Canadian question?

| Question | Client |
|---|---|
| BoC policy rate, CORRA, GoC bond yields, CAD FX, BCPI, monetary aggregates | `bank_of_canada_client` |
| Canadian CPI / GDP / jobs / trade / retail / housing | `statcan_client` |
| Canada vs other countries' policy rates / credit (cross-border) | `bis_client` |
| US rates / FX | `fred_client` / `treasury_client` / `newyorkfed_client` |

## Format quirks (the wrapper absorbs these)

| Quirk | What | Wrapper behavior |
|---|---|---|
| **`/json` suffix + format negotiation** | Every Valet route needs a format suffix | The wrapper always requests JSON; you pass names only. |
| **Observation cells are `{"v": "1.38"}`** | Each datapoint is a nested object with a string value | Flattened to `{date: float}`; values coerced. |
| **Relative windows** | `recent`, `recent_weeks`, `recent_months`, `recent_years` are alternatives to `start_date`/`end_date` | Pass any one; `recent=1` is the "latest value" idiom (used by `latest`). |
| **Series vs group** | Some catalog aliases are groups, not series | `latest(alias)` raises on a group alias and points you at `get_group_observations`. |
| **Many non-data series** | The 15,600 series include chart-only and note series (e.g. `MPR_*`, `FSR_*`, `SAN_*`) | Search by the canonical name/label; the catalog covers the headline macro series. |

## Full surface (`bank_of_canada_client.__all__`)

| Group | Primitives |
|---|---|
| Discovery (embedded) | `search_series`, `search_groups`, `list_groups`, `list_catalog`, `search_catalog` |
| On-demand detail (live) | `get_series_detail`, `get_group_detail` |
| Data (live) | `get_observations`, `get_group_observations`, `latest` |
| pandas | `observations_to_dataframe` |

`refresh_ontology(write_to=__file__)` re-harvests the embedded series/group index (offline tool — do not call from the sandbox).
