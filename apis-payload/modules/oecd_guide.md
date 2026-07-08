# OECD (Data Explorer / SDMX)

Sandbox name: `oecd_client`
Base URL: `https://sdmx.oecd.org/public/rest`
Auth: none (anonymous public SDMX service).
Transport: Bucket C — plain `requests` (no GS proxy).

`oecd_client` is a thin SDMX-REST wrapper over the OECD's ~1,500 dataflows:
it absorbs the flowRef grammar, the CDN caching quirk (structure responses
are always XML; data must be requested with a `format=csvfile` query param —
both handled internally), SDMX key dimension order, country aliasing, CSV
parsing, and `OBS_VALUE` float coercion. It ships a curated catalog of
verified headline macro keys — including the **Economic Outlook forecast
database** — plus live discovery for the full universe.

## Triggers

**Primary** — Cross-country OECD-standardised macro: CPI (headline + core),
quarterly real GDP growth, monthly unemployment / employment rates,
composite leading indicators (CLI), business + consumer confidence,
long/short/policy interest rates, share prices, real effective exchange
rates, house prices (real / nominal / price-to-income), productivity (GDP
per hour), and **OECD Economic Outlook projections** (GDP, inflation,
unemployment, government debt, fiscal balance, current account — history +
~2y forecasts). Anything framed "OECD countries", "advanced economies",
"OECD forecasts", "leading indicator", "price-to-income".

**Not for** — IMF/WEO forecasts and 190-country coverage (`imf_client`);
US high-frequency single-country series (`fred_client`); labour detail with
demographic splits beyond sex/age (`ilo_client`); EU-specific statistics
like HICP or Maastricht debt (`eurostat_client`); cross-border banking
(`bis_client`).

### Format quirks (wrapper-absorbed unless noted)

- Country codes are **ISO-3** (`USA`, `DEU`); the wrapper also accepts
  ISO-2 and common names. Aggregates: `OECD`, `EA20`, `EU27_2020`, `G7`,
  `G20` (availability varies by flow; not every flow carries aggregates).
- `OBS_VALUE` is coerced to float; empty selections return `[]`.
- `TIME_PERIOD` is `"2024"`, `"2024-05"`, `"2024-Q2"`. `to_dataframe` adds
  a numeric `time` column.
- Flow versions are omitted from requests, so every call rides the LATEST
  dataflow version (OECD bumps versions silently — each Economic Outlook
  edition is a version bump of the same `DSD_EO@DF_EO` flow).
- Rates are in percent; index series state their base in `BASE_PER`
  (mostly 2015=100). `UNIT_MULT` gives the power-of-10 multiplier on
  level series.

## Curated catalog (`get_indicator(name, areas, ...)`)

Verified keys, one clean series per area. `list_catalog()` returns this set
programmatically.

| name | what it gives | freq |
|------|---------------|------|
| `cpi_yoy` / `cpi_index` / `core_cpi_yoy` | Headline CPI % y/y, index (2015=100), core (ex food & energy) % y/y | M |
| `gdp_growth` / `gdp_growth_yoy` | Real GDP % q/q, % y/y (SA) | Q |
| `unemployment_rate` | Unemployment % of labour force (SA); `sex=`/`age=` | M |
| `employment_rate` | Employment % of pop 15-64 (SA); `sex=` | Q |
| `cli` | Composite Leading Indicator (amplitude-adj; 100 = trend) | M |
| `business_confidence` / `consumer_confidence` | BCI / CCI (100 = trend) | M |
| `long_term_rate` | 10y government bond yield, % p.a. | M |
| `short_term_rate` | 3-month interbank rate, % p.a. | M |
| `policy_rate` | Immediate/overnight rate (policy proxy), % p.a. | M |
| `share_prices` | Share price index (2015=100) | M |
| `reer` | Real effective exchange rate, CPI-based (2015=100) | M |
| `house_prices_real` / `house_prices_nominal` | House price indices (2015=100) | Q |
| `house_price_to_income` | Price-to-income ratio (2015=100) | Q |
| `gdp_per_hour` | GDP per hour worked, USD current PPP level | A |
| `gdp_per_hour_growth` | Labour productivity growth % y/y | A |
| `eo_gdp_growth` | **EO forecast**: real GDP growth % | A |
| `eo_inflation` | **EO forecast**: CPI inflation % | A |
| `eo_unemployment` | **EO forecast**: unemployment rate % | A |
| `eo_gov_debt` | **EO forecast**: general govt gross debt % of GDP | A |
| `eo_fiscal_balance` | **EO forecast**: govt net lending % of GDP | A |
| `eo_current_account` | **EO forecast**: current account % of GDP | A |

## Friendly aliases PRISM can pass

| param | accepts |
|-------|---------|
| `areas` | ISO-3 (`USA`), ISO-2 (`US`), names (`"Germany"`), aggregates (`"OECD"`, `"euro area"`, `"G7"`, `"G20"`); str or list (OR-joined). All OECD members + major partners are aliased; unknown tokens pass through unchanged, so exact SDMX codes always work |
| `sex` | `total` / `male` / `female` (labour indicators only; omitted = total; a list fans out both in one call) |
| `age` | `total` (15+) / `youth` (15-24) / `adult` (25+) / `working_age` (15-64) (unemployment only; omitted = 15+; a list fans out, e.g. `age=["youth","total"]`) |
| `start`,`end` | `"2015"` (works for any frequency), `"2015-01"`, `"2015-Q1"` |
| `last_n` | last N observations per series |

Rows come back sorted by (area, time). `[]` means the selection is valid
but has no data (typically: that area isn't covered by that flow);
`OECDError` means the request itself failed.

## Domain semantics (the wrapper can't hide these)

- **Economic Outlook rows include forecasts.** The `eo_*` indicators return
  the current EO edition: history plus ~2 forward years. Each `eo_*` row
  carries `is_forecast` (True = year beyond the current calendar year, the
  OECD projection window). Say "OECD projects ..." for those rows.
- **CLI/BCI/CCI read relative to 100** (long-term trend). CLI above 100 and
  rising = expansion ahead of trend; below 100 and falling = slowdown.
  These are amplitude-adjusted, designed for turning points, not levels.
- **`policy_rate` (IRSTCI) is the immediate/overnight rate**, an
  interbank-market proxy for the policy stance — not the official target
  rate announcement (for US specifics use FRED).
- **Coverage varies by flow.** OECD members are complete; accession /
  partner economies (CHN, IND, BRA, ZAF, IDN) appear in some flows (EO,
  prices) but not others (IALFS labour). An empty `[]` for a valid key
  means that area isn't in the flow.
- **House-price ratios are indexed** (2015=100), not absolute ratios — use
  them for over/under-valuation vs own history, not cross-country levels.
- **Monthly unemployment lags** the national print by ~1 month (OECD
  harmonises); FRED is fresher for the US number itself.

## Decision table (vs adjacent clients)

| Question | Client |
|----------|--------|
| OECD-standardised cross-country macro panel, CLI, house prices, EO forecasts | `oecd_client` |
| IMF forecasts, 190+ economies, debt datasets | `imf_client` |
| US single-country, freshest prints | `fred_client` |
| EU HICP, Maastricht debt/deficit, EU energy prices | `eurostat_client` |
| Labour with deep demographic/sector splits | `ilo_client` |
| Cross-border banking, credit gaps, BIS property prices | `bis_client` |

## Schemas

`get_indicator` / `get_data` rows (SDMX-CSV columns; per-flow dimension
columns vary):

| column | type | notes |
|--------|------|-------|
| `REF_AREA` | str | ISO-3 country or aggregate |
| `FREQ` | str | A / Q / M |
| `MEASURE` | str | flow-specific measure code (e.g. `LI`, `IRLT`, `UNR`) |
| flow dims | str | e.g. `UNIT_MEASURE`, `TRANSFORMATION`, `ADJUSTMENT`, `SEX`, `AGE`, `TRANSACTION` (per flow) |
| `TIME_PERIOD` | str | `2024`, `2024-05`, `2024-Q2` |
| `OBS_VALUE` | float | the value |
| `OBS_STATUS` | str | `A` normal, `P` provisional, `E` estimate |
| `UNIT_MULT`, `BASE_PER`, `DECIMALS` | str | unit scale / index base |

`list_catalog()` → `name`, `flow`, `desc`.
`list_dataflows(search=)` → `agency`, `id`, `version`, `name`, `flow_ref`
(~1,500 flows; pass `flow_ref` straight to `get_data`/`get_dimensions`).
`get_dimensions(flow_ref)` → ordered dimension ids (the SDMX key order).
`get_codelist(flow_ref, dimension)` → `{code: name}`.
`build_key(flow_ref, **dims)` → dot-key (unset dims wildcard; lists OR with `+`).
`to_dataframe(rows, wide=False)` → long frame (adds numeric `time`);
`wide=True` → index `time` × one column per series (headers use only the
dimensions that VARY, so a multi-country panel gets clean `REF_AREA`
columns).

## Function reference

| call | key params |
|------|-----------|
| `get_indicator(name, areas, *, start, end, last_n, sex, age)` | `name` catalog key; `areas` str/list |
| `get_panel(names, areas, *, start, end, last_n)` | several catalog indicators in one long-row set; each row tagged `indicator`, so `wide=True` pivots to one column per (indicator, area) |
| `get_data(flow_ref, key="all", *, start, end, last_n, first_n)` | raw SDMX pull; `flow_ref`="AGENCY,FLOW_ID"; ALWAYS bound `key="all"` with `start`/`last_n` |
| `build_key(flow_ref, **dims)` / `get_dimensions` / `get_codelist` | key assembly + discovery; dim names in `build_key` must be the exact ids `get_dimensions` returns |
| `list_dataflows(search=)` / `list_catalog()` | universe / catalog |

## Python recipes

```python
# G7 member CPI panel, wide for charting (G7 = these 7 countries)
G7 = ["USA","DEU","FRA","GBR","ITA","JPN","CAN"]
rows = oecd_client.get_indicator("cpi_yoy", G7, start="2020-01")
wide = oecd_client.to_dataframe(rows, wide=True)

# Economic Outlook projections: is_forecast flag splits history from forecast
eo = oecd_client.get_panel(
    ["eo_gdp_growth", "eo_inflation", "eo_gov_debt"], "USA", start="2020")
hist = [r for r in eo if not r["is_forecast"]]
proj = [r for r in eo if r["is_forecast"]]   # "OECD projects ..."

# q/q + y/y GDP growth in one frame (multi-indicator panel)
gdp = oecd_client.to_dataframe(
    oecd_client.get_panel(["gdp_growth", "gdp_growth_yoy"],
                          ["USA", "euro area"], start="2023-Q1"),
    wide=True)   # columns: (indicator | area)

# Youth vs total unemployment in ONE call (age list fans out)
cmp = oecd_client.to_dataframe(
    oecd_client.get_indicator("unemployment_rate", "ES",
                              age=["youth", "total"], start="2024-01"),
    wide=True)   # one column per AGE code

# CLI turning points, several economies
cli = oecd_client.to_dataframe(
    oecd_client.get_indicator("cli", ["US","China","Germany"], start="2024-01"),
    wide=True)

# House-price-to-income vs own history (indexed 2015=100 -> compare to
# each country's own long-run mean, not across countries)
hp = oecd_client.to_dataframe(
    oecd_client.get_indicator("house_price_to_income",
                              ["USA","CAN","NZL","DEU"], start="2005"),
    wide=True)
stretch = (hp.iloc[-1] / hp.mean() - 1) * 100   # % above own 20y average
```

## Beyond the catalog (full universe)

The catalog covers ~24 of ~1,500 OECD dataflows. Workflow for anything else
(discover → inspect dimensions → resolve codes → build key → pull):

```python
flows = oecd_client.list_dataflows("productivity")   # rows carry flow_ref
# For INDUSTRY-level productivity pick 'DSD_PDB@DF_PDB_ISIC4_I4'
# ("Productivity by industry") -- NOT DF_PDB / DF_PDB_GR (economy-wide).
ref   = next(f["flow_ref"] for f in flows if "ISIC4" in f["id"])
dims  = oecd_client.get_dimensions(ref)              # SDMX key order
# The industry split lives in the ACTIVITY dimension on OECD flows
acts  = oecd_client.get_codelist(ref, "ACTIVITY")    # ISIC industry codes
key   = oecd_client.build_key(ref, REF_AREA="KOR", FREQ="A")
rows  = oecd_client.get_data(ref, key, start="2015")
```

flowRef is `"AGENCY,FLOW_ID"` (e.g. `"OECD.ECO.MAD,DSD_EO@DF_EO"` — agency
strings contain dots, the comma separates agency from flow);
`list_dataflows` hands it to you pre-assembled as `flow_ref`. Omit a
dimension in `build_key` to wildcard; OR values with a list. ALWAYS bound
wildcard-heavy pulls with `start=`/`last_n=` — big flows (QNA, PDB) carry
100k+ rows. Resolve codes with `get_codelist` before assuming them; OECD
code conventions differ per flow family (`_T` totals, `_Z` not-applicable).
Sector/industry breakdowns almost always live in an `ACTIVITY` dimension;
demographic splits in `SEX`/`AGE`; the measure concept in `MEASURE` or
`TRANSACTION` (national accounts).
