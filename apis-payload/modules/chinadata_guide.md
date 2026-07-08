# ChinaData.live (China official-statistics aggregator)

Sandbox name: `chinadata_client`
Base URL: `https://chinadata.live/api/v2`
Auth: none (no key; fair-use ~100 req/min).
Transport: Bucket C — plain `requests` (no GS proxy).

`chinadata_client` wraps the chinadata.live public JSON API: ~320 cleaned
datasets sourced from NBS / World Bank / GACC (GDP, CPI, population,
energy, technology, transport, ...) plus **monthly GACC customs trade**
by partner country and HS product. The wrapper absorbs country→slug
mapping, the response envelope, value coercion, and passes through the
API's QA metadata (suppressed values, flags) untouched.

## Triggers

**Primary** — China macro series (GDP, CPI, population, industrial /
energy / tech indicators) and especially **China trade**: monthly bilateral
exports/imports/balance with ~106 partners, HS-chapter composition of
bilateral trade, HS6/HS8 product-level trade with partner rankings
(e.g. lithium-ion battery exports by destination). Anything framed
"China's exports of X", "China-US trade balance", "China GDP/CPI series".

**Not for** — cross-country panels where China is one column
(`imf_client` / `oecd_client` / `ilo_client`); global trade matrices
(`imf_client` SDMX IMTS); US-side trade prints (Census via `fred_client`
or `usitc_client`). This is an independent aggregator of official data,
not the NBS itself — for load-bearing numbers cross-check against an
official source.

### Format quirks (wrapper-absorbed unless noted)

- Trade endpoints take URL slugs; the wrapper slugifies ANY country name
  (`"Germany"`→`germany`, `"Saudi Arabia"`→`saudi-arabia`) and maps the
  irregular aliases (`"US"`→`united-states`, `"UK"`, `"Korea"`/`"South
  Korea"`, `"UAE"`, ISO-2 majors). Dataset ids are kebab-case
  (`china-gdp`).
- Values are coerced to float (including multi-column datasets like
  `china-trade-monthly` whose numbers arrive as strings). Dataset dates
  are strings: `"2023"` (yearly), `"2023-05"` (monthly).
- **All trade values this client returns are FULL USD.** The upstream API
  mixes units (country endpoint in USD thousand, HS endpoints in full
  USD); the wrapper normalizes country-endpoint values ×1000 so
  everything is plain dollars. Non-trade dataset values follow each
  dataset's own `unit` field (many NBS series are "100 Million CNY") —
  always read `unit` before interpreting.
- **Suppressed prints stay `None`**: when the source sees an impossible
  negative monthly trade value it nulls the public value and keeps the raw
  number + QA flag in `suppressed_values` / `qa_flags`. Don't impute.
- A bad dataset id / country / HS code raises a clean not-found error —
  check `list_datasets()` / `search_datasets()`.

## Surface

| call | returns |
|------|---------|
| `list_datasets(category=, search=)` | dataset metadata rows (cached); categories: economy, energy, technology, transport, population, agriculture, manufacturing, ... |
| `search_datasets(q)` | server-side full-text search; rows carry `id`, `title`, `category`, `description`, `unit`, `frequency`, `tags` |
| `get_dataset(id)` | metadata + `data` = `[{date, value}]` (floats) |
| `get_series(id)` | just the data points |
| `list_trade_countries(search=)` | the exact ~106-partner trade universe: `slug`, `name`, coverage months (cached) — check here instead of guessing partners |
| `list_hs_codes(search=, flow=)` | the exact ~130 curated HS products: `hs_code`, `flow`, `commodity_name`, coverage (cached) — the `get_hs_trade` universe |
| `get_country_trade(country, full_breakdown=False, since=None)` | monthly bilateral trade + latest-month HS-chapter breakdowns; `since="2018"` trims |
| `get_hs_trade(hs_code, flow="export", period="all", limit=20, since=None)` | product/chapter trade: monthly totals + partner rankings |
| `get_hs_country_trade(hs_code, country, period=)` | bilateral product series (SPARSE curated coverage) |
| `to_dataframe(data)` | pandas from dataset dicts, point lists, or either trade `monthly` row shape |

## Schemas

`get_dataset` → `{id, title, category, description, source, unit,
frequency, tags, data: [{date: str, value: float}]}`.

`get_country_trade` → dict with:

| field | shape | notes |
|-------|-------|-------|
| `monthly` | `[{year, month, exports, imports, balance}]` | full USD; exports = China's exports TO the partner; `None` = suppressed |
| `export_breakdown` / `import_breakdown` | `[{hs_code, hs_label, val_month, val_ytd}]` | latest-month HS-chapter composition, full USD; `hs_label` = chapter name (from `HS_CHAPTERS`); `val_month` can be `None` |
| `coverage` | `{first_period, latest_period, row_count, scope}` | |
| `latest_period`, `source`, `source_url`, `qa_flags`, `known_limitations` | | QA metadata passthrough |
| `suppressed_values` | `[{year, month, direction, field, raw_value, qa_flags, action}]` | the raw prints behind each `None` |

`get_hs_trade` → dict with:

| field | shape | notes |
|-------|-------|-------|
| `commodity` | str | product name (e.g. "Lithium-ion accumulators") |
| `monthly` | `[{month: "2018-01", year, month_num, value_usd, <flow>, partner_count}]` | product totals; `exports`/`imports` aliases `value_usd` — use `value_usd` as the value column in DataFrames |
| `years` | `[{year, value_usd, partner_count}]` | annual totals |
| `top_partners` | `[{partner_code, partner_name, value_usd, share, month_count}]` | cumulative over `period`; the "biggest buyers" list |
| `latest_partners` | same shape | latest month only |
| `growth_countries` | `[{country_name, value_usd, yoy_growth, share_ytd, ...}]` | YoY movers |
| `available_flows`, `available_periods`, `coverage` | | check `available_flows` before querying imports |

`to_dataframe` on either trade `monthly` shape adds `period` ("2026-05")
and numeric `time`; on `{date, value}` points adds numeric `time`.

## Domain semantics (the wrapper can't hide these)

- **Direction convention**: in `get_country_trade`, `exports` are China's
  exports TO that partner (China's perspective, GACC data). The China-US
  "trade balance" here is China's surplus.
- **Product coverage varies by flow**: many HS6/HS8 products are
  export-only in the public snapshot — `list_hs_codes()` shows each
  product's flow up front (`~110` export, `~20` import products), and the
  response's `available_flows` confirms it.
- **`get_hs_country_trade` is a curated subset** ("opportunity pages") —
  most product × country pairs 404 cleanly. For bilateral composition use
  `get_country_trade(...)["export_breakdown"]`; for a product's
  destinations use `get_hs_trade(...)["top_partners"]`.
- **HS chapter vs product**: 2-digit codes (`85`) hit chapter pages, 6/8
  digit codes hit curated product pages. Partner rankings are capped at
  the top 20 publicly.
- **GACC data starts 2018-01** for country pages; dataset series vary
  (GDP back to 1960 via World Bank splice).
- **GDP and most NBS macro series are nominal** (current prices) unless
  the dataset title/description says otherwise — a CAGR on `china-gdp`
  is nominal growth in CNY.
- **January/February distortions**: Chinese New Year shifts make Jan/Feb
  YoY reads unreliable — GACC itself often publishes Jan-Feb combined;
  compare Jan+Feb sums, not single months.

## Decision table (vs adjacent clients)

| Question | Client |
|----------|--------|
| China bilateral / product trade detail (monthly GACC) | `chinadata_client` |
| China GDP/CPI/population single series | `chinadata_client` (or `imf_client` for comparability) |
| China in a cross-country panel | `imf_client` / `oecd_client` / `ilo_client` |
| Global bilateral trade matrix | `imf_client` SDMX (IMTS) |
| US-reported side of US-China trade | `usitc_client` / `fred_client` |

## Python recipes

```python
# China GDP: CAGR over the last decade (mind the unit field)
gdp = chinadata_client.get_dataset("china-gdp")   # unit: 100 Million CNY
df = chinadata_client.to_dataframe(gdp)
d10 = df[df["time"] >= df["time"].max() - 10]
cagr = (d10["value"].iloc[-1] / d10["value"].iloc[0]) ** (1 / 10) - 1

# China-US monthly trade balance since 2018 (values are full USD)
tr = chinadata_client.get_country_trade("US", since="2018")
m = chinadata_client.to_dataframe(tr["monthly"])
m["balance_usd_bn"] = m["balance"] / 1e9

# Multi-partner export comparison (rerouting check)
import pandas as pd
panel = pd.concat({
    c: chinadata_client.to_dataframe(
        chinadata_client.get_country_trade(c, since="2018")["monthly"]
    ).set_index("period")["exports"]
    for c in ["US", "Vietnam", "Mexico"]
}, axis=1)

# What does China export to Germany? (latest-month HS chapters)
de = chinadata_client.get_country_trade("Germany")
top = sorted(de["export_breakdown"], key=lambda r: -(r["val_month"] or 0))[:5]
for r in top:
    print(r["hs_label"], f"{r['val_month']/1e9:.1f}bn")   # labels attached

# What products/partners does the trade universe cover?
cn = chinadata_client
partners = cn.list_trade_countries()              # 106 partners with slugs
products = cn.list_hs_codes("battery")            # find HS codes by name
#   -> [{'hs_code': '850760', 'flow': 'export',
#        'commodity_name': 'Lithium-ion accumulators', ...}]

# Lithium-ion battery exports: trend + destinations
hs = chinadata_client.get_hs_trade("850760")      # flow="export", period="all"
monthly = chinadata_client.to_dataframe(hs["monthly"])
buyers = hs["top_partners"]                       # cumulative; share sums to 1

# Discover what exists. When several hits match, pick by title/description
# fit and PREFER a series whose `frequency`/`unit` matches the question
# (macro indicator datasets over trade-page stubs).
cats = chinadata_client.list_datasets(category="energy")
hits = chinadata_client.search_datasets("semiconductor")
```
