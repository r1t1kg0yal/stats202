# Eurostat (EU Statistical Office)

Sandbox name: `eurostat_client`
Base URL: `https://ec.europa.eu/eurostat/api/dissemination`
Auth: none (anonymous public service).
Transport: Bucket C — plain `requests` (no GS proxy).

`eurostat_client` wraps the JSON-stat dissemination API (~7,000 datasets):
it absorbs JSON-stat hypercube decoding into tidy rows, named dimension
filters (no positional keys, no dimension order), geo aliasing (including
Eurostat's `EL`-for-Greece and the per-dataset euro-area aggregate quirk),
value coercion, and dataset routing for current-account aggregates. It
ships a curated catalog of verified headline euro-macro filters plus TOC
search and per-dataset dimension discovery.

## Triggers

**Primary** — EU / euro-area / member-state official statistics: HICP
inflation (headline, core, any COICOP component), quarterly GDP growth and
levels, monthly unemployment, employment rates, labour cost / wage growth,
Maastricht (EDP) government debt and deficit, industrial production, retail
trade, producer prices, current account, household energy prices (gas /
electricity), population. Anything framed "euro area", "EU", "Eurostat",
"HICP", "Maastricht debt", or single-EU-country official prints.

**Not for** — OECD-standardised panels incl. non-EU members
(`oecd_client`); IMF forecasts (`imf_client`); US series (`fred_client`);
ECB policy rates / FX (not carried here — use `fred_client` for major FX
or `oecd_client` financial indicators); cross-border banking (`bis_client`).

### Format quirks (wrapper-absorbed unless noted)

- Geo codes are **ISO-2 with two Eurostat exceptions**: Greece is `EL`,
  United Kingdom `UK`. The wrapper resolves names and ISO-2 (`GR` → `EL`).
- **Euro-area aggregate codes differ per dataset** (`EA` in HICP, `EA21` in
  unemployment, `EA20` in national accounts). Pass `"euro area"` to
  `get_indicator` and the wrapper substitutes the right one; raw `get_data`
  callers must use the dataset's own code (check `describe_dataset`).
- Values are coerced to float; missing cells are dropped (not None-padded).
- `time` is `"2024"`, `"2024-05"`, `"2024-Q2"`, `"2024-S1"` (semester),
  `"2024-W05"`. `to_dataframe` adds a numeric time column.
- `last_n` counts **periods, not observations** — if the newest period is
  not yet reported for your geo, you get fewer (or zero) rows; widen it.
- Unfiltered dimensions return every code. Over-wide extractions fail with
  HTTP 413 EXTRACTION_TOO_BIG (~5M-row cap) — filter every dimension you
  don't need fanned out, and bound with `start=`/`last_n=`.

## Curated catalog (`get_indicator(name, geos, ...)`)

Verified filter combos, one clean series per geo. `list_catalog()` returns
this set programmatically.

| name | what it gives | freq |
|------|---------------|------|
| `hicp_yoy` | HICP all-items inflation % y/y | M |
| `hicp_core_yoy` | Core HICP (ex energy & food) % y/y | M |
| `hicp_index` | HICP index (2015=100) | M |
| `ppi_yoy` | Producer prices, domestic industry, % y/y | M |
| `gdp_growth` / `gdp_growth_yoy` | Real GDP % q/q, % y/y (SCA) | Q |
| `gdp_level` | Nominal GDP, million EUR (SCA) | Q |
| `industrial_production` | IP index B-D (2021=100, SCA) | M |
| `retail_trade` | Retail volume index G47 (2021=100, SCA) | M |
| `unemployment_rate` | Unemployment % active pop (SA); `sex=`/`age=` | M |
| `employment_rate` | Employment % of pop 20-64 (SA) | Q |
| `wage_growth` | Labour cost index, wages & salaries % y/y | Q |
| `gov_debt` | Maastricht govt debt, % of GDP | A |
| `gov_deficit` | Govt net lending(+)/borrowing(-), % of GDP | A |
| `current_account` | CA balance vs rest of world, mn EUR | Q |
| `gas_price_households` | Household gas, EUR/kWh incl. taxes | S |
| `electricity_price_households` | Household electricity, EUR/kWh incl. taxes | S |
| `population` | Population on 1 January | A |

The `filters` a catalog entry pins ARE its defaults — omitting a kwarg
keeps the pinned code (e.g. `unemployment_rate` defaults `age="TOTAL"`,
`sex="T"`, `s_adj="SA"`). Keyword overrides replace any of them and work
for ANY dimension of the underlying dataset: `sex="F"`, `age="Y_LT25"`,
`coicop="NRG"` (on the HICP names), `nrg_cons=`/`tax=` (on the energy
names).

## Friendly aliases PRISM can pass

| param | accepts |
|-------|---------|
| `geos` | Eurostat codes (`DE`, `EL`), names (`"Germany"`, `"Greece"`), `"euro area"` / `"EU"`; str or list (fans out) |
| `start`,`end` | `"2020"` (works for any frequency), `"2020-01"`, `"2020-Q1"` |
| `last_n` | last N time periods |

Rows are plain dicts sorted by (geo, time) — lists from separate calls
concatenate with `+` and feed `to_dataframe` together. Zero rows back
means the dimension codes were valid but no cells matched (wrong code
combo or the geo lacks that series); `EurostatError` means the request
itself was rejected (unknown dimension, bad code, HTTP 413 too-big).

## Domain semantics (the wrapper can't hide these)

- **EDP debt/deficit are the treaty numbers.** `gov_debt`/`gov_deficit` are
  the Maastricht definitions used for the 60%/3% rules — these differ from
  national-accounts debt concepts (and from IMF GGXWDG). Annual; notified
  April/October.
- **Energy prices are semi-annual** (`2024-S1`/`S2`) and band-specific: the
  catalog pins the mid consumption band (gas 20-200 GJ, electricity
  2500-5000 kWh) with taxes included; pass `nrg_cons=`/`tax=` to change.
- **`current_account` for a country is the country's own CA** (from
  `bop_c6_q`); for `"euro area"`/`"EU"` the wrapper switches to the
  aggregate dataset (`bop_eu6_q`, extra-area flows, NSA). Aggregate and
  country rows are not seasonally-adjusted the same way — don't mix in one
  chart without noting it.
- **HICP euro-area series use the changing-composition aggregate** (`EA`);
  national accounts use fixed-composition `EA20`. Historic aggregates are
  backwards-extended.
- **US/JP appear in a few datasets** (`une_rt_m` carries `US`, `JP`) but
  Eurostat is not a global source — cross-check with the country's own
  statistical office for anything load-bearing.
- **`unemployment_rate` age bands**: `TOTAL`, `Y_LT25` (youth), `Y25-74`.
- **HICP has no seasonal-adjustment dimension** (HICP is unadjusted by
  construction) — don't look for an `s_adj` filter on `prc_hicp_*`.
- **`last_n=1` on annual EDP data can misalign countries** if one geo has
  not yet reported the newest year — pull `last_n=2` and reduce with
  `latest_per_geo(rows)` when ranking.
- **Units ride on the rows**: datasets with a `unit` dimension carry
  `unit` + `unit_label` columns on every row (e.g. energy prices
  `KWH`/"Kilowatt-hour") — read them instead of assuming.

## Decision table (vs adjacent clients)

| Question | Client |
|----------|--------|
| HICP, Maastricht debt/deficit, EU energy prices, EU member detail | `eurostat_client` |
| Cross-country panel incl. US/Japan/EM | `oecd_client` or `imf_client` |
| IMF forecasts / % of GDP debt comparisons | `imf_client` |
| Euro-area labour with sector/status splits | `ilo_client` |
| US anything | `fred_client` |

## Schemas

`get_indicator` / `get_data` rows (one per observation):

| column | type | notes |
|--------|------|-------|
| `<dim>` | str | code per dataset dimension (`geo`, `coicop`, `unit`, `s_adj`, `nace_r2`, ...) |
| `<dim>_label` | str | human label for every dimension code |
| `time` | str | period string (`2024-05`, `2024-Q2`, `2024-S1`) |
| `value` | float | the observation |

`list_catalog()` → `name`, `dataset`, `desc`.
`search_datasets(keyword)` → `code`, `title`, `data_start`, `data_end`,
`last_update` (full TOC, cached).
`describe_dataset(dataset, **partial_filters)` → `{dim: {code: label}}` —
the discovery tool; call it before composing raw `get_data` filters.
`to_dataframe(rows, wide=False, label=False)` → long frame (varying dims +
`time` + numeric `time_num` + `value`); `wide=True` → `time` × one column
per series (headers from varying dims; `label=True` uses human labels).

## Function reference

| call | key params |
|------|-----------|
| `get_indicator(name, geos, *, start, end, last_n, **overrides)` | catalog accessor; overrides replace catalog filters |
| `get_panel(names, geos, *, start, end, last_n)` | several catalog indicators in one long-row set; rows tagged `indicator`, so `wide=True` pivots to one column per (indicator, geo) |
| `latest_per_geo(rows)` | newest row per geo (and per indicator) — use for cross-country rankings on annual data instead of `last_n=1` |
| `get_data(dataset, *, start, end, last_n, **filters)` | raw pull; NAMED dimension filters, exact codes (geo goes through aliases); lists fan out |
| `describe_dataset(dataset, **filters)` | dims + valid codes + labels (latest period probe) |
| `get_constraints(dataset)` | POPULATED codes per dimension + TIME_PERIOD coverage, a few KB for ANY dataset size (codes only, no labels) |
| `search_datasets(keyword)` | TOC full-text search |

## Python recipes

```python
# Headline vs core inflation in one frame (multi-indicator panel).
# Wide headers are "<indicator> | <varying dims>" -- select by name, not
# positional iloc.
panel = eurostat_client.to_dataframe(
    eurostat_client.get_panel(["hicp_yoy", "hicp_core_yoy"], "euro area",
                              start="2022-01"),
    wide=True)
head = [c for c in panel.columns if c.startswith("hicp_yoy")][0]
core = [c for c in panel.columns if c.startswith("hicp_core_yoy")][0]
spread = panel[core].iloc[-1] - panel[head].iloc[-1]

# Maastricht debt ranking: pull 2 periods, reduce to each geo's latest
# (countries report the newest EDP year with different lags)
rows = eurostat_client.get_indicator(
    "gov_debt", ["IT","EL","FR","ES","BE","PT","DE","NL","AT"], last_n=2)
debt = sorted(eurostat_client.latest_per_geo(rows),
              key=lambda r: -r["value"])

# Youth unemployment, Spain vs euro area
y = eurostat_client.get_indicator(
    "unemployment_rate", ["Spain", "euro area"], age="Y_LT25", start="2023-01")

# Raw dataset: energy-component HICP for France
nrg = eurostat_client.get_data(
    "prc_hicp_manr", coicop="NRG", unit="RCH_A", geo="France", start="2024-01")

# Household electricity prices across the big-4
el = eurostat_client.get_indicator(
    "electricity_price_households", ["DE","FR","IT","ES"], start="2022")
```

## Beyond the catalog (full universe)

~7,000 datasets. Workflow (find dataset → discover dims → pull):

```python
hits = eurostat_client.search_datasets("house price")      # TOC search
# pick e.g. 'prc_hpi_q' (house price index, quarterly)
dims = eurostat_client.describe_dataset("prc_hpi_q", geo="DE")
#   -> {'freq': {...}, 'purchase': {'TOTAL': 'Total', ...}, 'unit': {...}, ...}
rows = eurostat_client.get_data(
    "prc_hpi_q", purchase="TOTAL", unit="I15_Q", geo="DE", start="2015-Q1")

# For a BIG dataset (bop, nama detail) probe the populated codes instead —
# get_constraints is a few KB regardless of dataset size and also tells
# you the TIME_PERIOD coverage:
c = eurostat_client.get_constraints("bop_eu6_q")
#   -> {'geo': ['EU27_2020','EA20',...], 'partner': [...], 'bop_item': [...],
#       'TIME_PERIOD': ['1999-Q1', ..., '2026-Q1'], ...}
```

Always discover before composing raw filters — dimension names and code
vocabularies vary per dataset family (`indic_bt`, `nace_r2`, `coicop`,
`siec`, `lcstruct`, ...) and guessing codes silently returns zero rows
(valid dims, no matching cells). `describe_dataset` gives labels but needs
narrowing filters on very large datasets (HTTP 413 otherwise);
`get_constraints` always works and gives the exact populated code lists.
