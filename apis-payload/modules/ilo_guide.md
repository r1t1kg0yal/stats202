# ILOSTAT (International Labour Organization)

Sandbox name: `ilo_client`
Base URL: `https://sdmx.ilo.org/rest`
Auth: none (anonymous public SDMX service).
Transport: Bucket C — plain `requests` (no GS proxy).

`ilo_client` is a thin SDMX-REST wrapper: it absorbs the SDMX key dimension
order, the "total" classification codes, country aliasing, CSV parsing, and
`OBS_VALUE` float coercion. It ships a curated catalog of headline
macro-labour indicators plus live discovery for the full ~1,200-dataflow
universe.

## Triggers

**Primary** — Cross-country labour-market statistics: unemployment rate,
employment-to-population ratio, labour force participation, employment by
sector/status, average earnings, hours worked, informality, NEET, working
poverty, time-related underemployment, labour underutilization (LU2/LU4),
labour income share of GDP, output per worker/hour, gender income gap. Both
nationally-reported series and ILO harmonized **modelled estimates** with
full country coverage.

**Not for** — US high-frequency macro/rates (FRED), US bank data (FDIC),
cross-border banking (BIS), Canadian official stats (StatCan), income/wealth
inequality shares + Gini (WID). For US labour specifically, FRED (BLS series)
is fresher; use ILO when you need a harmonized cross-country panel.

### Format quirks (wrapper-absorbed unless noted)

- Country codes are **ISO-3** (`USA`, `DEU`, `CHN`). The wrapper also accepts
  ISO-2, common names, and group names (`World`→`X01`, `BRICS`→`X85`) via
  `get_indicator`/`AREA_ALIASES`.
- `OBS_VALUE` is coerced to float by the wrapper.
- A selection with no data returns `[]` (SDMX 404), not an error.
- `TIME_PERIOD` is `"2024"` (annual), `"2024-M03"` (monthly), `"2024-Q1"`
  (quarterly). `to_dataframe` adds a numeric `time` column.
- Rates are in **percent** (7.0 = 7%), not fractions.

## Curated catalog (`get_indicator(name, areas, ...)`)

One clean series per country with total-sex / 15+-age defaults. Override with
`sex=`, `age=`, `currency=`, or raw classification kwargs.

| name | what it gives |
|------|---------------|
| `unemployment_rate` | Unemployment rate %, reported (some countries M/Q) |
| `unemployment_rate_modelled` | Unemployment rate %, ILO modelled (all countries) |
| `unemployment` | Number unemployed (thousands) |
| `employment_ratio` / `_modelled` | Employment-to-population ratio % |
| `employment` | Number employed (thousands) |
| `employment_by_sector` | Employment by 6 aggregate sectors (no total; pass `ECO="ECO_AGGREGATE_TOTAL"` for total economy) |
| `employment_by_status` | Employment: employees vs self-employed split |
| `employees` | Number of employees (thousands) |
| `labour_force_participation` / `_modelled` | LFPR % |
| `labour_force` | Labour force (thousands) |
| `working_age_population` | Working-age population (thousands) |
| `time_related_underemployment_rate` | Time-related underemployment %, modelled |
| `labour_underutilization_lu4` | Composite underutilization LU4 %, modelled |
| `combined_underutilization_lu2` | Underemployment+unemployment LU2 %, modelled |
| `informal_employment_rate` | Informal employment %, modelled |
| `neet_rate` | Youth NEET % |
| `working_poverty_rate` | Working poverty % (<US$3 PPP), SDG 1.1.1 |
| `child_labour_rate` | Children in child labour, % of children 5-17 (age bands via `AGE=AGE_CLDVERSION_Y05-11/Y12-14/Y15-17`) |
| `union_density` | Trade union density rate, % of employees |
| `collective_bargaining_coverage` | Collective bargaining coverage rate, % of employees |
| `fatal_injuries_rate` | Fatal occupational injuries per 100k workers, SDG 8.8.1 (`MIG=` for migrant split) |
| `mean_monthly_earnings` | Mean monthly earnings (currency=ppp\|lcu\|usd) |
| `mean_hourly_earnings` | Mean hourly earnings (currency=ppp\|lcu\|usd) |
| `mean_weekly_hours` | Mean weekly hours worked (total economy) |
| `labour_income_share` | Labour income share % of GDP, modelled (SDG 10.4.1) |
| `output_per_worker` | Output/worker, GDP const 2021 intl $ PPP |
| `output_per_hour` | Output/hour, GDP const 2021 intl $ PPP |
| `gdp_ppp` | GDP, millions const 2021 intl $ PPP |
| `gender_income_gap` | Women/men labour income ratio, modelled |
| `cpi` / `cpi_yoy` | CPI all-items (2017=100) / YoY % (FREQ M or A) |
| `exchange_rate` | Local currency units per US dollar |

`list_catalog()` returns this set programmatically.

## Friendly aliases PRISM can pass

| param | accepts |
|-------|---------|
| `areas` | ISO-3 (`USA`), ISO-2 (`US`), names (`"Germany"`), groups (`"World"`, `"BRICS"`); str or list (OR-joined) |
| `sex` | `total` / `male` / `female` |
| `age` | `total` (15+) / `youth` (15-24) / `adult` (25+) / `working_age` (15-64) / `prime` (25-54) |
| `currency` | `ppp` / `lcu` / `usd` (earnings only) |
| `freq` | `A` annual / `M` monthly / `Q` quarterly |
| `start`,`end` | `"2015"`, `"2015-01"`, `"2015-Q1"` |
| `last_n` | last N observations per series |

## Domain semantics (the wrapper can't hide these)

- **Reported vs modelled.** Plain names (`unemployment_rate`) are
  nationally-reported — freshest, but coverage and comparability vary, and
  some countries publish monthly/quarterly (US, Canada report monthly). The
  `*_modelled` names are ILO modelled estimates: harmonized, comparable
  across all countries, **annual only**. Use modelled for any cross-country
  panel or demographic slice; use reported for the latest national print of
  one country. When the user names ILO for a US series, use ILO (not FRED).
- **Modelled-only indicators.** `labour_income_share`, `output_per_worker`,
  `output_per_hour`, `gdp_ppp`, `gender_income_gap`, and the `*_modelled`
  rates are modelled estimates with no reported counterpart — the absence of
  a `_modelled` suffix on the productivity/income-share names is expected.
- **Modelled series carry projections.** Modelled estimates extend ~2 years
  past the latest actual with nowcasts/projections. On modelled series the
  actual years carry `OBS_STATUS == "R"` and the projection years have a
  **blank** `OBS_STATUS`. Call `ilo_client.mark_forecasts(rows)` to add an
  `is_forecast` bool rather than hand-checking status.
- **`OBS_STATUS`** also flags `B` = break in series (don't splice across it).
- **Earnings currency.** `ppp` (comparable), `lcu` (local currency, the raw
  national figure), `usd`. Not every country has every currency variant.
- **Groups vs members.** `X85` = BRICS as an aggregate entity. ILO also has
  `X85_COU` meaning the member countries individually — pass that to fan out.
- **15+ totals.** The wrapper picks `AGE_YTHADULT_YGE15` (15+) and `SEX_T`;
  pass `age=`/`sex=` to change.

## Decision table (vs adjacent clients)

| Question | Client |
|----------|--------|
| US labour, freshest monthly print | `fred_client` (BLS) |
| Cross-country harmonized labour panel | `ilo_client` `*_modelled` |
| Income / wealth inequality shares, Gini, DINA | `wid_client` |
| Canadian labour detail | `statcan_client` |
| Cross-border banking / credit / property | `bis_client` |
| Labour income share, output per worker | `ilo_client` |

## Schemas

`get_indicator` / `get_data` rows (SDMX-CSV columns):

| column | type | notes |
|--------|------|-------|
| `REF_AREA` | str | ISO-3 country or X-group |
| `FREQ` | str | A / M / Q |
| `MEASURE` | str | indicator measure code |
| `SEX`,`AGE`,`ECO`,`STE`,`CUR`,`COI`,`MIG` | str | classification codes (per dataflow); `AGE` uses child-labour bands (`AGE_CLDVERSION_*`) on `child_labour_rate`, `MIG` (migrant status) on `fatal_injuries_rate` |
| `TIME_PERIOD` | str | `2024`, `2024-M03`, `2024-Q1` |
| `OBS_VALUE` | float | the value (percent for rates) |
| `OBS_STATUS` | str | break/estimate/forecast flag |
| `UNIT_MEASURE`,`UNIT_MEASURE_TYPE`,`UNIT_MULT` | str | units |
| `SOURCE`,`NOTE_*` | str | source + free-text notes |

`list_catalog()` → `name`, `dataflow`, `desc`.
`list_dataflows(search=)` → `id`, `name`.
`get_dimensions(dataflow)` → ordered list of dimension ids.
`get_codelist(cl)` / `get_areas(groups_only=)` → `{code: name}`.
`code_label(code)` → human name for a classification code
(`"ECO_AGGREGATE_AGR"` → `"Agriculture"`); unknown codes pass through.
`to_dataframe(rows, wide=False, label=False)` → long frame (adds numeric
`time`); `wide=True` → index `time` × one column per series. Wide headers use
only the dimensions that VARY, so a single-indicator multi-country panel gets
clean `REF_AREA` columns. `label=True` adds `<DIM>_label` columns and uses
names in wide headers.
`mark_forecasts(rows)` → adds `is_forecast` bool (modelled projection years).

## Function reference

| call | key params |
|------|-----------|
| `get_indicator(name, areas, *, freq, start, end, last_n, sex, age, currency, **classif)` | `name` catalog key; `areas` str/list; classif kwargs (e.g. `ECO=`) override defaults, `=None` wildcards |
| `get_data(dataflow, key="", *, start, end, last_n, first_n, detail, version)` | raw SDMX key path; `key=""` returns whole flow |
| `build_key(dataflow, **dims)` | dim=value (or list for OR); unset dims wildcard |
| `get_dimensions(dataflow)` / `get_codelist(cl)` / `get_areas()` | discovery |

Defaults: `freq` per indicator (annual for modelled), `sex="SEX_T"`,
`age` 15+, earnings `currency="ppp"`.

## Python recipes

```python
# Headline: US unemployment, harmonized modelled, since 1991
rows = ilo_client.get_indicator("unemployment_rate_modelled", "USA", start="1991")
df = ilo_client.to_dataframe(rows)

# Cross-country panel, wide, for charting
rows = ilo_client.get_indicator(
    "labour_force_participation_modelled",
    ["US", "Germany", "Japan", "China", "BRICS"], start="2000")
wide = ilo_client.to_dataframe(rows, wide=True)

# Latest labour income share for the G7-ish set
rows = ilo_client.get_indicator(
    "labour_income_share", ["USA","DEU","FRA","GBR","ITA","JPN","CAN"], last_n=1)

# Female youth unemployment override
rows = ilo_client.get_indicator(
    "unemployment_rate_modelled", "ZA", sex="female", age="youth", start="2010")

# Monthly reported unemployment (latest prints)
rows = ilo_client.get_indicator("unemployment_rate", "CAN", freq="M", last_n=12)

# Sector breakdown: 6 clean sectors (no total), ranked + labelled
rows = ilo_client.get_indicator("employment_by_sector", "IND", last_n=1)
for r in sorted(rows, key=lambda x: -x["OBS_VALUE"])[:3]:
    print(ilo_client.code_label(r["ECO"]), r["OBS_VALUE"])

# Flag forecast years on a modelled series
rows = ilo_client.mark_forecasts(
    ilo_client.get_indicator("unemployment_rate_modelled", ["BRA", "US"], start="1995"))
```

## Beyond the catalog (full universe)

The catalog is ~30 of ~1,200 ILOSTAT indicators. Workflow for anything else
(discover → inspect dimensions → resolve codes → build key → pull):

```python
# e.g. public-sector employment (not in catalog)
flows = ilo_client.list_dataflows("public sector")   # -> [{'id','name'}, ...]
# pick e.g. 'DF_EES_PUBL_SEX_JBC_NB' (public sector employees by sex + contract)
dims  = ilo_client.get_dimensions("DF_EES_PUBL_SEX_JBC_NB")
#   -> ['REF_AREA','FREQ','MEASURE','SEX','JBC']
codes = ilo_client.get_codelist("CL_JBC")            # resolve a classification's codes
#   -> {'JBC_CONTRACT_TOTAL':'Total','JBC_CONTRACT_PERM':'Permanent', ...}
key   = ilo_client.build_key("DF_EES_PUBL_SEX_JBC_NB",
                             REF_AREA="FRA", FREQ="A", SEX="SEX_T")  # JBC wildcarded
rows  = ilo_client.get_data("DF_EES_PUBL_SEX_JBC_NB", key, last_n=1)
# coverage is partial -- many countries return [] for niche flows; check first
```

Always resolve classification codes with `get_codelist` before assuming them
(don't guess "total" codes). Dataflow ids are
`DF_<TOPIC><VARIANT>_<CLASSIFS>_<TYPE>` (e.g. `DF_UNE_DEAP_SEX_AGE_RT` =
unemployment, by sex and age, rate). The SDMX key is
`REF_AREA.FREQ.MEASURE.<classifications>`; omit a dimension to wildcard, OR
values with `+`. `get_areas(groups_only=True)` lists region/income/named
groups (`X##`); `X85_COU` fans a group into its member countries.
