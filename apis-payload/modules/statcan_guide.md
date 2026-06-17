# Statistics Canada (StatCan)

Sandbox name: `statcan_client`
Base: WDS `https://www150.statcan.gc.ca/t1/wds/rest` + SDMX `.../sdmx/statcan/rest`
Auth: None
Transport: GS proxy via `session_and_auth` (Bucket A)
Universe: the full active CODR universe — 5,070 active cubes (tables) across 31 subject domains, plus 622 subjects, 17 frequencies, 462 units of measure — all embedded. Per-cube dimensions/members are fetched on demand. Query the ontology BEFORE building a query.

## Triggers

**Primary** — Canadian macro / financial / economic data: CPI and core inflation (CPI-trim/median/common), GDP (monthly by industry, quarterly expenditure), labour force (unemployment/employment/participation/wages), international merchandise trade, government finance, income/wealth, retail and wholesale trade, manufacturing, construction and building permits, housing prices, business performance, national/financial accounts. Canada and provincial/CMA breakdowns.

**Not for** — Bank of Canada policy rate / CORRA / GoC bond yields / FX (use `bank_of_canada_client`); US data (FRED/Treasury); cross-border banking (BIS). StatCan is mostly monthly/quarterly with a release lag; daily series are rare.

## Universe at a Glance — the 11 macro/financial/economic subjects

`statcan_client.list_subjects(macro_only=True)` enumerates these at runtime. Every active cube is tagged with one or more 2-digit subject codes; `cubes_by_subject(code)` lists them.

| Code | Subject | Example headline tables |
|---|---|---|
| `36` | Economic accounts | GDP (36100434 monthly, 36100104 quarterly), financial/national accounts |
| `18` | Prices and price indexes | CPI (18100004), core inflation (18100256), NHPI (18100205) |
| `14` | Labour | Labour Force Survey (14100287), payroll/earnings (14100223) |
| `12` | International trade | Merchandise trade (12100011), trade by product/partner |
| `10` | Government | Federal/provincial revenue, expenditure, debt |
| `11` | Income, pensions, spending, wealth | Household income, wealth, savings |
| `33` | Business performance and ownership | Enterprise financials, business dynamics |
| `34` | Construction | Building permits (34100066), investment in construction |
| `16` | Manufacturing | Manufacturing sales/inventories/orders |
| `20` | Retail and wholesale | Retail trade (20100008), wholesale trade |
| `46` | Housing | Housing stats, dwellings |

The embedded index covers ALL active subjects (not just these 11). `get_cube_metadata(pid)` reaches any cube live, including archived ones outside the index.

## Discovery Workflow (progressive disclosure)

PRISM never memorises product IDs. Drill from subject → cube → dimensions → series → data, using the embedded ontology offline until the final data call.

```python
# 1. WHICH subjects exist?
statcan_client.list_subjects(macro_only=True)
# -> [{"code": "18", "name": "Prices and price indexes", "macro": True}, ...]

# 2. WHICH cubes are in a subject? (offline, from the embedded index)
statcan_client.cubes_by_subject("18", frequency=6)   # 6 = Monthly
# -> [{"pid": 18100004, "title": "Consumer Price Index, monthly...", ...}]

# 3. SEARCH cube titles (offline, accent/case-insensitive, all tokens match)
statcan_client.search_cubes("consumer price index", subject="18")
statcan_client.describe_cube(18100004)               # one-glance summary

# 4. WHAT dimensions/members does a cube have? (live DSD — progressive L3)
meta = statcan_client.get_cube_metadata(18100004)
# -> dimensions: [{position:1, name:"Geography", members:[{id:"2", name:"Canada"}...]},
#                 {position:2, name:"Products and product groups", members:[...359...]}]
statcan_client.get_dimension_members(18100004, "Geography")

# 5. GET data — by dimension filters (wrapper resolves to coordinates) ...
series = statcan_client.query(18100004, Geography="Canada",
                              Products="All-items", start="2024-01")
# ... or all provinces in one call (wildcard a dimension by omitting it):
statcan_client.query(18100004, Products="All-items", latest_n=12)
# ... or by stable vector id (the most precise pin):
statcan_client.get_vector("v41690973", latest_n=12)
statcan_client.latest("cpi")                          # catalog fast path
```

`query(...)` resolves named dimension filters against the live cube metadata, validating every member (raises `StatCanError` with up to 8 valid-member suggestions on a miss) and wildcarding any dimension you omit. If a wildcard resolves to more than 300 series it raises and points you at `get_full_table_url(pid)` (whole-cube zip download).

## Curated catalog — Canada macro fast path

`statcan_client.list_catalog()` / `search_catalog(kw)`. `latest(alias)` returns the most-recent observation. Aliases with a fixed `vector` resolve instantly; aliases with only a `pid` need `get_cube_metadata` + `query` to pick the slice.

| Alias | Vector / PID | Series |
|---|---|---|
| `cpi` | v41690973 | CPI all-items, Canada (NSA, 2002=100) |
| `cpi_common` / `cpi_median` / `cpi_trim` | v108785713/714/715 | BoC core inflation measures, Canada (YoY %) |
| `gdp_monthly` | v65201210 | Real GDP at basic prices, all industries (chained $) |
| `gdp_quarterly` | pid 36100104 | GDP, expenditure-based, quarterly |
| `unemployment_rate` | v2062815 | Unemployment rate, Canada, 15+, both sexes (SA, %) |
| `employment` / `participation_rate` | v2062811 / v2062816 | LFS employment / participation (SA) |
| `trade_balance` | pid 12100011 | Merchandise trade balance |
| `retail_sales` | pid 20100008 | Retail trade sales by industry |
| `building_permits` | pid 34100066 | Building permits by structure type |
| `new_housing_price_index` | v111955442 | New Housing Price Index, Canada |
| `population` | v1 | Population estimates, quarterly |

## Recipes

Catalog aliases work anywhere a vector is accepted (`get_vector("cpi", ...)`, `latest("cpi")`). `latest_n=N` means the N most-recent observations **per series** (for a monthly series, N months). `get_vector` and `query` also take `start=`/`end=` (any period granularity); `latest(...)` returns `{value, period, vector, title, frequency}`.

```python
# Headline CPI + year-over-year inflation (CPI is an index; compute YoY)
s = statcan_client.get_vector("cpi", latest_n=13)[0]["observations"]
months = sorted(s)
yoy = (s[months[-1]] / s[months[-13]] - 1) * 100      # latest vs 12 months prior

# Rank a wildcard slice (all geographies, latest month) with pandas
rows = statcan_client.query(18100004, Products="All-items", latest_n=1)
df = statcan_client.series_to_dataframe(rows)          # long: Geography, period, value
ranked = df.sort_values("value", ascending=False)

# pid-only catalog entry (no fixed vector) -> drill metadata, then pin
# every dimension so the query resolves to one series (wildcards multiply)
meta = statcan_client.get_cube_metadata(12100011)      # inspect dimensions/members
bal = statcan_client.query(
    12100011, Geography="Canada", Trade="Trade Balance",
    Basis="Balance of payments", latest_n=60,
    **{"Seasonal adjustment": "Seasonally adjusted",
       "Principal trading partners": "All countries"})

# Align multiple series into one period-indexed wide frame
df = statcan_client.fetch_aligned([
    {"name": "cpi", "vector": "v41690973"},
    {"name": "unemp", "vector": "v2062815"},
], start="2020")
```

A wildcard `query` returns one series per member combination, each with its resolved `dimensions` — filter the `Canada` aggregate out of a by-province slice on your side. `series_to_dataframe(rows)` (long) / `(rows, wide=True)` (one column per series) and `get_cube_metadata(pid)["dimensions"]` give coverage.

## Decision table — which client for which Canadian question?

| Question | Client |
|---|---|
| Canadian CPI / core inflation / GDP / jobs / trade / retail / housing prices | `statcan_client` |
| Bank of Canada policy (overnight target) rate, CORRA | `bank_of_canada_client` |
| GoC benchmark bond yields, CAD FX rates, BCPI commodity index | `bank_of_canada_client` |
| Canada vs other countries' credit/property/policy rates (cross-border) | `bis_client` |
| US equivalents | `fred_client` / `treasury_client` |

`statcan_client` owns the Canadian real economy; `bank_of_canada_client` owns Canadian rates/FX/monetary; they are complementary.

## Output schema (series object)

`query(...)` / `get_vector(...)` return `list[dict]`:

```python
{
    "vector":       "41690973",        # stable series id (None for some query rows)
    "pid":          18100004,
    "coordinate":   "2.2.0.0.0.0.0.0.0.0",
    "dimensions":   {"Geography": "Canada", "Products and product groups": "All-items"},
    "title":        "Consumer Price Index, monthly, not seasonally adjusted",
    "frequency":    "Monthly",
    "scalar_factor": "units",
    "observations": {"2024-01": 158.3, "2024-02": 158.8, ...},   # period -> float|None
}
```

Periods are normalised strings by frequency: `"2024"` (annual), `"2024-Q1"` (quarterly), `"2024-06"` (monthly), `"2024-06-15"` (daily). Values are coerced to `float`.

`get_cube_metadata(pid)` returns `{pid, title, frequency, nb_series, start, end, dimensions:[{position, name, members:[{id, name, parent}]}]}`.

## Format quirks (the wrapper absorbs these; PRISM should know the rest)

| Quirk | What | Wrapper behavior |
|---|---|---|
| **Periods are mislabelled in SDMX-JSON** | StatCan's SDMX `TIME_PERIOD` ids are computed wrong (2024-02 returned as "2025") | The wrapper derives every period from the reliable ISO `start` + frequency. PRISM always gets correct period labels. Use `query`/`get_vector` (WDS-backed); they never expose the bug. |
| **Vectors are stable, coordinates positional** | A vector (`v41690973`) never changes; a coordinate is the 10-position dot key of member ids | Pin a known series with `get_vector`; let `query(pid, Dim=...)` build coordinates from member names/ids for you. |
| **Member ids are numeric, names verbose** | Geography "Canada" = id `2` in CPI but id `1` in 18100256; "Products and product groups" not "Products" | Pass names or ids; partial dimension names resolve when unique (`Products` -> `Products and product groups`). |
| **Scalar factor + decimals** | A value may be published in units / thousands / millions (see `scalar_factor`) | Surfaced in each series; values are returned as published (apply the scalar for true magnitude). |
| **Archived cubes** | ~3,140 cubes are discontinued and excluded from the embedded active index | `get_cube_metadata(pid)` still reaches them live; `get_cube(pid)` returns None for non-active. |
| **Whole-cube pulls are large** | CPI alone is 2,139 series; querying every member combination is huge | A wildcard query over the 300-series cap raises with a pointer to `get_full_table_url(pid)` (zipped CSV/SDMX download). |

## Frequency codes

`get_frequency(code)`. Common: `1`=Daily, `6`=Monthly, `7`=Bimonthly, `9`=Quarterly, `11`=Semi-annual, `12`=Annual. `cubes_by_subject(code, frequency=6)` filters to monthly tables.

## Full surface (`statcan_client.__all__`)

| Group | Primitives |
|---|---|
| Discovery (embedded) | `list_subjects`, `get_subject`, `cubes_by_subject`, `search_cubes`, `get_cube`, `describe_cube`, `list_catalog`, `search_catalog` |
| Code sets | `get_frequency`, `get_uom`, `get_scalar_factor`, `list_frequencies` |
| On-demand structure (live) | `get_cube_metadata`, `get_dimensions`, `get_dimension_members`, `get_series_info` |
| Data (live) | `get_vector`, `query`, `get_data`, `build_coordinate`, `latest`, `get_data_sdmx`, `get_full_table_url` |
| pandas | `series_to_dataframe`, `fetch_aligned` |

`get_data_sdmx(dataflow, key, ...)` is the raw SDMX REST interface (the StatCan SDMX user-guide path: `DF_<pid>` dataflow + dot-separated key, wildcard by omission, OR with `+`); the wrapper corrects periods, but for reliable per-series identity prefer `query`/`get_vector`. `refresh_ontology(write_to=__file__)` re-harvests the embedded universe (offline tool — do not call from the sandbox).
