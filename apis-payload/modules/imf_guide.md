# IMF (International Monetary Fund)

Sandbox name: `imf_client`
Layer: cross-country macro — official forecasts (WEO), fiscal/debt (Fiscal Monitor, Global Debt Database), reserves (ARA), and the deep statistical tail (CPI, BOP, trade, GFS, FSI, exchange rates, policy rates) behind a keyed SDMX surface.
Auth: **none** for the Datamapper backbone; the SDMX 3.0 surface needs an Azure APIM subscription key. Transport: Bucket C (plain `requests`).
Design: catalog + thin getters. `get_data` returns tidy long rows; you write pandas on top. Entities and indicators accept friendly aliases ("US", "United States", "UK", "Korea", "Euro area", "real gdp growth", "inflation") resolved to codes internally; basket names ("G7", "G20", "BRICS") expand to member countries. Values are numeric-coerced. `imf_client.to_dataframe(rows, pivot=...)` for pandas.

## Surface (no key — the Datamapper backbone)

| Call | Returns |
|---|---|
| `imf_client.get_data(indicator, entities=None, start=None, end=None)` | tidy rows (schema below). `entities=None` = all economies; omit start/end for full history. |
| `imf_client.get_panel(indicators, entities=None, start=, end=)` | multiple indicators in one combined long-row set (each row keeps its `indicator`) |
| `imf_client.get_series(indicator, entity, start=, end=)` | one entity's `[{year, value}]` |
| `imf_client.latest(indicator, entity, include_forecast=True)` | most recent row (set `include_forecast=False` for latest ≤ current year) |
| `imf_client.compare(indicator, entities, year=None)` | cross-section `{indicator, unit, year, data:[{entity, entity_label, value}]}` sorted high→low; `year=None` = latest available year |
| `imf_client.members(basket)` | member ISO3 list for `"G7"` / `"G20"` / `"BRICS"` |
| `imf_client.list_datasets()` | the 13 Datamapper datasets + indicator counts |
| `imf_client.list_indicators(dataset=, keyword=)` / `search_indicators(kw)` | `[{code, label, unit, dataset}]` |
| `imf_client.get_indicator(code)` / `describe([indicator])` | indicator metadata / whole-client overview |
| `imf_client.list_countries(kw=)` / `list_groups(kw=)` | `{code: name}` (241 countries / 129 groups) |
| `imf_client.resolve_entity(name)` / `resolve_indicator(name)` | alias → code (raises with suggestions on miss) |
| `imf_client.refresh_catalog()` | live `/indicators`,`/countries`,`/groups` + `new_indicators` vs the embedded snapshot |
| `imf_client.to_dataframe(rows, pivot="entity"|"year"|None)` | pandas (long, or wide year×entity / entity×year) |

## Triggers

**Primary** — Cross-country comparisons; IMF **official forecasts** (WEO projections to ~T+5); government debt / fiscal balance / primary balance / revenue / expenditure (% of GDP); current account; GDP (level, growth, per-capita, PPP, world share); inflation (WEO annual); unemployment; reserves adequacy; household / corporate / public debt (Global Debt Database); regional outlooks. Anything framed "across countries", "vs other economies", "IMF projects", "in the WEO/Fiscal Monitor".

**Keyed (SDMX 3.0)** — Monthly CPI, Balance of Payments, bilateral trade matrix (IMTS), Government Finance Statistics, Financial Soundness Indicators (NPLs/capital adequacy), exchange rates, policy rates, commodity prices. See the SDMX section — needs a subscription key.

**Not for** (route elsewhere) — US high-frequency series (`fred_client`), cross-border banking / credit-to-GDP / DSR (`bis_client`), company financials / XBRL (`sec_edgar_client`).

## Decision table — IMF vs other clients

| Question | Use |
|---|---|
| Cross-country GDP/inflation/debt/fiscal, IMF forecasts, % of GDP comparisons | **`imf_client`** (Datamapper) |
| Monthly CPI / BOP / trade matrix / GFS / FSI / FX / policy rates | **`imf_client.sdmx`** (needs key) |
| US CPI MoM, payrolls, fed funds, IP, high-frequency US series | `fred_client` |
| Cross-border bank claims, credit-to-GDP gap, debt service ratio | `bis_client` |
| One company's financials / filings / XBRL frames | `sec_edgar_client` |

`imf_client.describe()` returns this routing programmatically (`ROUTING`).

## Datasets (no key, annual)

`list_indicators(dataset="WEO")` for the full per-dataset list. Source vintages are on each row via `get_indicator()`.

| Code | Dataset | n | Notes |
|---|---|---|---|
| WEO | World Economic Outlook | 15 | flagship; includes projections to ~T+5 |
| FM | Fiscal Monitor | 8 | fiscal balances + debt positions |
| GDD | Global Debt Database | 10 | household / corporate / public debt, % of GDP |
| ARA | Assessing Reserve Adequacy | 4 | reserves / ARA, /M2, /short-term-debt |
| FPP | Public Finances in Modern History | 8 | multi-century fiscal series (debt back to ~1800s) |
| CF | Capital Flows in Developing Economies | 18 | FDI / portfolio / other flows ($mn) |
| CL | Wang-Jahan Capital Openness Index | 18 | capital-account openness indices |
| AFRREO | Sub-Saharan Africa Regional Outlook | 26 | SSA-only regional cut |
| SPRLU | Export Diversification | 14 | diversification / quality indices |
| AIPI | AI Preparedness Index | 5 | one-off index (2024) |
| GD | Gender Development & Budgeting | 3 | indices |
| FR_FC | Fiscal Rules & Councils | 2 | indicator dummies |
| DEBT | Historical Public Debt (FAD) | 1 | gross public debt, % of GDP |

## Common indicators (code → alias)

| Code | Alias accepted | Unit |
|---|---|---|
| `NGDP_RPCH` | real gdp growth / gdp growth | % change |
| `NGDPD` | gdp / nominal gdp | $bn |
| `NGDPDPC` | gdp per capita | $/capita |
| `PPPGDP` / `PPPSH` | gdp ppp / world gdp share | int'l $bn / % of world |
| `PCPIPCH` / `PCPIEPCH` | inflation / end-of-period inflation | % change |
| `LUR` | unemployment | % |
| `LP` | population | millions |
| `BCA_NGDPD` / `BCA` | current account / current account usd | % of GDP / $bn |
| `GGXWDG_NGDP` | government debt / gross debt / public debt | % of GDP |
| `GGXCNL_NGDP` | fiscal balance / deficit | % of GDP |
| `GGXONLB_G01_GDP_PT` | primary balance | % of GDP |
| `HH_ALL` / `NFC_ALL` / `Privatedebt_all` | household / (nonfinancial) corporate / private debt | % of GDP |

This table is illustrative — `resolve_indicator` also accepts the **exact IMF labels** (e.g. "General government gross debt") and close paraphrases (hyphen/spacing-tolerant); on a miss it raises with suggestions. When unsure, `search_indicators(keyword)`. Likewise `resolve_entity` accepts ISO3 codes, group codes, and friendly names.

## Schemas

`get_data` / `get_panel` row: `indicator` (code), `indicator_label`, `unit`, `dataset`, `entity` (ISO3 or group code), `entity_label`, `year` (int), `value` (float|None), `is_projection` (bool — True when `year` > current calendar year; the WEO/FM forecast flag, so you never re-derive the cutoff).
`compare` → `{indicator, indicator_label, unit, year, data:[{entity, entity_label, value}]}` (data sorted high→low, None last).
`get_series` → `[{year, value}]`. `latest` → a full `get_data` row.

## Domain semantics (the wrapper can't hide these)

- **WEO/FM include forecasts.** Values with `is_projection=True` (year > current calendar year) are IMF **projections**, not actuals — the API does not flag the per-series boundary, so the flag is a calendar-year heuristic. `latest(..., include_forecast=False)` gives the latest non-projection year. Always say "IMF projects ..." for projection rows.
- **"Inflation" = period-average CPI** (`PCPIPCH`); end-of-period is `PCPIEPCH`. The alias "inflation" resolves to the average measure.
- **WEO aggregates use specific group codes**: `ADVEC` (advanced), `OEMDC` (emerging & developing), `EURO` (euro area), `MAE` (G7 aggregate), `WEOWORLD` (world). Not every group carries every indicator (e.g. `EME` has no WEO real-GDP-growth series) — `get_data` raises cleanly if a group/indicator pair is empty. **`"G7"`/`"G20"`/`"BRICS"` as entities expand to member countries** (a 7-country ranking); pass the group code (`MAE`) for the single aggregate series.
- **Longest histories live in different datasets.** WEO/FM debt (`GGXWDG_NGDP`) starts ~1980; for multi-century public debt use FPP (`"historical public debt"` → `d`, back to ~1800). For deep history of a series, search the dataset table first.
- **Annual only on the Datamapper.** For monthly/quarterly (CPI, BOP, FX, rates) use the keyed SDMX surface.
- **Units vary by indicator** — read `unit` per row; never assume % vs $bn. `% of GDP` and `$bn` indicators must not be summed together.
- **Coverage varies by dataset.** GDD/ARA/AFRREO/FPP cover subsets of the 241 economies; `get_data` raises (does not silently return empty) when an entity is absent.

The wrapper already absorbs (you do not handle any of these): friendly entity/indicator aliases (incl. `US`/`UK`/`Korea`), basket expansion, numeric coercion, the `is_projection` flag, the multi-entity filter (the API only filters one entity server-side; the wrapper fetches-and-filters for >1), `compare(year=None)` → latest year, and the unknown-indicator quirk (the API returns its country catalog at HTTP 200 for a bad code — the wrapper detects this and raises).

## SDMX 3.0 — keyed escape hatch (deep datasets)

`imf_client.sdmx.*` reaches `api.imf.org/external/sdmx/3.0` for datasets the Datamapper omits. **Requires** an Azure APIM subscription key in `IMF_API_PRIMARY_KEY` (free at https://datamarketplace.imf.org/). Without a key these methods raise `ImfError` — never a silent fallback.

| Call | Returns |
|---|---|
| `imf_client.sdmx.catalog([keyword])` | curated dataflows: `dataflow, agency, version, freq, name, note` (offline) |
| `imf_client.sdmx.has_key()` | whether a key is configured |
| `imf_client.sdmx.build_path(dataflow, key="*")` | the wire path (offline preview) |
| `imf_client.sdmx.key_grammar()` | how to construct the dot-joined series key |
| `imf_client.sdmx.data(dataflow, key, start=, end=)` | tidy rows (one col per dimension + `TIME_PERIOD`, `value`) — **key required** |
| `imf_client.sdmx.dataflows()` | live dataflow list — **key required** |

**Dataflows**: `CPI` (monthly inflation), `BOP`/`BOP_AGG` (balance of payments), `IMTS` (trade matrix; replaces DOTS), `GFS_COFOG` (govt finance), `FSI` (financial soundness), `ER` (exchange rates), `MFS_IR` (policy rates), `PCPS` (commodity prices), `CDIS`/`CPIS` (investment surveys), `WEO`/`FM` (prefer the no-key Datamapper).

**Key grammar**: the wire path is `/data/dataflow/{agency}/{flow}/{version}/{key}` (slash form; the comma form 404s). `{key}` = dimension values joined by `.`, `*` wildcards a dimension, `+` ORs values. SDMX keys use **ISO3** country codes (`USA`, not the `US` alias the Datamapper accepts) — call `imf_client.resolve_entity("US")` → `"USA"` to convert a friendly name to the ISO3 a key needs. `start`/`end` take SDMX period strings or ints (`"2024"`, `2024`, `"2024-01"`). Use `key_grammar()` + (keyed) `dataflows()` to discover the exact dimensions for a flow before composing a precise key. Example: `imf_client.sdmx.data("CPI", "USA.CPI._T.IX.M", start="2024")`. Pass an explicit `"AGENCY,FLOW,VERSION"` to override the catalog. The on-wire SDMX-JSON parser is verified against the documented format but not a live keyed call — confirm shapes on first keyed use.

## Recipes

```python
import pandas as pd
imf = imf_client

# 1. Cross-country growth + inflation panel (WEO)
g = imf.to_dataframe(imf.get_data("real gdp growth", ["US","China","Euro area","India","Japan"],
                                  start=2020, end=2027), pivot="entity")

# 2. G7 government debt snapshot (sorted), latest year ("G7" expands to members)
debt = imf.compare("government debt", ["G7"])      # year=None -> latest available

# 3. Actuals vs projections (read the is_projection flag)
rows = imf.get_data("inflation", "Brazil", start=2015)
actuals = [r for r in rows if not r["is_projection"]]
proj    = [r for r in rows if r["is_projection"]]

# 4. Multi-indicator panel in one call (household + corporate debt)
panel = imf.to_dataframe(
    imf.get_panel(["household debt", "corporate debt"], ["US","China","Korea"], start=2010))
# long rows: pivot/melt as needed, e.g. panel.pivot_table(index=["year"], columns=["entity","indicator"], values="value")

# 5. Group aggregates over time (advanced vs emerging vs world)
agg = imf.to_dataframe(imf.get_data("real gdp growth", ["ADVEC","OEMDC","WEOWORLD"], start=2015), pivot="entity")

# 6. Discover what exists before pulling
fiscal = imf.search_indicators("balance")           # indicators across datasets
print(imf.list_groups(keyword="g-7"))               # group codes

# 7. Deep monthly data (SDMX, key required) — falls cleanly to ImfError if no key
if imf.sdmx.has_key():
    cpi = imf.to_dataframe(imf.sdmx.data("CPI", "USA.CPI._T.IX.M", start="2024"))
```

## Coverage gaps

The Datamapper carries headline annual indicators only; sub-annual frequency and the full statistical detail (monthly CPI, BOP components, bilateral trade, GFS, FSI, FX, policy rates) require the keyed SDMX surface. The legacy `dataservices.imf.org` JSON/XML service was retired in Sept 2025 and is not supported.
