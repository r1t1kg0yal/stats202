# Bank of Japan (Time-Series Data Search)

Sandbox name: `boj_client`
Base URL: `https://www.stat-search.boj.or.jp/api/v1`
Auth: none (anonymous public service; avoid high-frequency hammering).
Transport: Bucket C — plain `requests` (no GS proxy).

`boj_client` wraps the BOJ Time-Series Data Search API (the full BOJ
statistical warehouse). It absorbs the per-frequency date grammar (both
directions), NEXTPOSITION pagination, the 250-code request cap, the
series-code-vs-search-screen-code trap, and the STATUS error envelope. It
ships an embedded registry of the ~50 databases plus a curated catalog of
verified headline series codes.

## Triggers

**Primary** — Japan official monetary/financial statistics from the source:
uncollateralized overnight call rate (the policy-relevant rate), USD/JPY
and other Tokyo-market FX, nominal/real effective exchange rates, monetary
base, money stock (M1/M2/M3), reserves, **TANKAN** business survey DIs,
Producer Price Index (CGPI) and Services PPI, loans and deposits, BOJ
accounts, flow of funds, Japan balance of payments, JGB market data.
Anything framed "BOJ", "TANKAN", "Japan money supply", "yen effective
exchange rate".

**Not for** — Japan CPI (that's Statistics Bureau/e-Stat, not BOJ; the
closest here is corporate goods PPI), Japan GDP (Cabinet Office; use
`oecd_client` or `imf_client`), cross-country panels (`oecd_client` /
`imf_client` / `ilo_client`), BIS-consolidated banking outside Japan
(`bis_client`).

### Format quirks (wrapper-absorbed unless noted)

- Series are identified by (database, series_code) pairs — `get_data`
  takes both. Search-screen "time-series data codes" with a `DB'` prefix
  (`IR01'MADR1Z@D`) are cleaned automatically.
- Dates are normalized on output to `"2024"`, `"2024-H1"`, `"2024-Q2"`,
  `"2024-05"`, `"2024-05-17"` per the series frequency; inputs accept the
  same friendly strings (daily/weekly series take month granularity for
  `start`/`end` — a per-API rule, so `start="2024-05"` is the finest).
- Missing values arrive as `None` and are KEPT (daily series carry None on
  weekends/holidays) — filter or let pandas handle NaN.
- One request must not mix frequencies across codes (API rule; raises
  cleanly).
- Pagination (250 codes / 60,000 datapoints per request) is automatic.

## Curated catalog (`get_indicator(name, start=, end=)`)

Verified codes. `list_catalog()` returns this set programmatically.

| name | what it gives | freq |
|------|---------------|------|
| `call_rate` | Uncollateralized overnight call rate, daily avg (policy-relevant) | D |
| `call_rate_monthly` | Same, monthly average | M |
| `basic_loan_rate` | Basic discount / loan rate (former ODR) | D |
| `usdjpy` | USD/JPY spot 9:00 JST, Tokyo | D |
| `usdjpy_monthly` | USD/JPY spot 17:00 JST, monthly average | M |
| `eurusd_tokyo` | EUR/USD 9:00 JST, Tokyo | D |
| `neer` / `reer` | Nominal / real effective exchange rate of the yen | M |
| `monetary_base` | Monetary base, avg outstanding (100 mn yen) | M |
| `monetary_base_yoy` | Monetary base, % y/y | M |
| `m2` / `m3` | Money stock M2 / M3, avg outstanding (100 mn yen) | M |
| `m2_yoy` / `m3_yoy` | Money stock M2 / M3, % y/y | M |
| `reserves` | Reserves, average outstanding (100 mn yen) | M |
| `tankan_large_mfg` | TANKAN business conditions DI, large manufacturers, actual | Q |
| `tankan_large_nonmfg` | TANKAN DI, large non-manufacturers, actual | Q |
| `cgpi` | Producer Price Index (formerly CGPI), all commodities (2020=100) | M |
| `export_price_index` / `import_price_index` | Export / import price index, yen basis (2020=100) | M |

## Domain semantics (the wrapper can't hide these)

- **TANKAN DIs are net-percent balances** ("favorable" minus
  "unfavorable"): +22 means a strong net-positive read. Quarterly; the
  survey also carries forecast rows per release (separate series codes —
  discover via `search_series("CO", ...)`).
- **Yen levels vs indices**: `usdjpy` is yen per dollar (higher = weaker
  yen); `neer`/`reer` are indices where HIGHER = stronger yen. Don't read
  them with the same sign convention.
- **Money aggregates are in 100 million yen** (oku-yen). Multiply by 1e8
  for yen, ~divide by 1.5e3 for USD bn at 150 — read `unit` per row.
- **BOJ renamed CGPI to "Producer Price Index"** in 2022 — series names say
  PPI, the database (PR01) and macro convention still say CGPI. Same thing.
- **Daily rate series carry None** on non-business days; the latest
  non-None row is the latest print.
- **Discontinued series stay in metadata** with names prefixed
  `(Discontinued)` — `search_series` excludes them unless
  `include_discontinued=True`.

## Decision table (vs adjacent clients)

| Question | Client |
|----------|--------|
| BOJ rates, FX, money, TANKAN, Japan flow of funds / BOP | `boj_client` |
| Japan CPI, GDP, labour | `oecd_client` / `imf_client` / `ilo_client` |
| Japan in a cross-country panel | `oecd_client` / `imf_client` |
| USD/JPY intraday or long daily history for charting | `boj_client` (Tokyo fixings) or `fred_client` (NY) |
| BIS-reported Japanese bank claims abroad | `bis_client` |

## Schemas

`get_indicator` / `get_data` / `get_layer` rows (one per series × date):

| column | type | notes |
|--------|------|-------|
| `series_code` | str | BOJ series code (no DB prefix) |
| `name` | str | English series name |
| `unit` | str | e.g. "percent per annum", "100 million yen" |
| `frequency` | str | full label: `DAILY`, `MONTHLY`, `QUARTERLY`, ... |
| `category` | str | statistical category |
| `date` | str | normalized: `2024`, `2024-H1`, `2024-Q2`, `2024-05`, `2024-05-17` |
| `value` | float \| None | None = missing (weekends, unpublished) |

Rows are plain dicts — lists from separate calls concatenate with `+`
and feed `to_dataframe` together.

`get_metadata(db)` / `search_series(db, keyword, frequency=, include_discontinued=)`
→ rows with `series_code`, `name`, `unit`, `frequency`, `start`, `end`,
`last_update`, `layers`.
`list_databases(search=)` → `{db, desc}` for the ~50 databases.
`list_catalog()` → `name`, `db`, `codes`, `desc`.
`to_dataframe(rows, wide=False)` → long frame (adds numeric `time`);
`wide=True` → index `time` × one column per series (headers = series names).

## Function reference

| call | key params |
|------|-----------|
| `get_indicator(name, *, start, end, drop_missing=False)` | catalog accessor; `drop_missing=True` removes the None rows daily series carry on non-business days |
| `get_panel(names, *, start, end, drop_missing=False)` | several catalog indicators combined; rows tagged `indicator` — the one-call path for level+YoY pairs or FX panels |
| `get_data(db, codes, *, start, end)` | explicit codes (str or list, one frequency per call); auto-paginates |
| `get_layer(db, frequency, layer, *, start, end)` | pull a whole tree branch; `frequency` abbrev (`CY`/`FY`/`CH`/`FH`/`Q`/`M`/`W`/`D`); `layer` list or "1,1,1" ("*" wildcard) |
| `get_metadata(db)` / `search_series(db, kw, ...)` | discovery within a database |
| `list_databases(search=)` | which database holds what |

## Python recipes

```python
# Policy rate normalisation: call rate since 2022 (drop weekend Nones)
cr = boj_client.get_indicator("call_rate", start="2022-01", drop_missing=True)

# Yen: USD/JPY vs real effective rate in one call. Use the MONTHLY dollar
# rate when pairing with the monthly REER (don't mix daily + monthly).
# Note opposite sign conventions: usdjpy up = weaker yen, reer up = stronger.
fx = boj_client.to_dataframe(
    boj_client.get_panel(["usdjpy_monthly", "reer"], start="2020-01"),
    wide=True)

# TANKAN: manufacturers vs non-manufacturers, last 3 years
tk = boj_client.to_dataframe(
    boj_client.get_panel(["tankan_large_mfg", "tankan_large_nonmfg"],
                         start="2023-Q1"),
    wide=True)

# Monetary base level + YoY in one call
mb = boj_client.get_panel(["monetary_base", "monetary_base_yoy"],
                          start="2015-01")

# Money stock GROWTH = the *_yoy names (don't re-derive from levels)
ms = boj_client.get_panel(["m2_yoy", "m3_yoy"], start="2021-01")

# YoY from an index series the catalog gives as a level (e.g. PPI)
ppi = boj_client.to_dataframe(
    boj_client.get_indicator("cgpi", start="2020-01"), wide=True)
ppi_yoy = ppi.pct_change(12) * 100      # monthly index -> % y/y

# Discover then pull. When several hits match, prefer the exact
# "[<index name>] All ..." row (shortest name, no parenthetical qualifier).
hits = boj_client.search_series("PR02", "all items", frequency="MONTHLY")
rows = boj_client.get_data("PR02", hits[0]["series_code"], start="2022-01")
```

## Beyond the catalog (full warehouse)

Workflow: find the database → search its series → pull.

```python
boj_client.list_databases("price")        # -> PR01 CGPI/PPI, PR02 SPPI, ...
meta = boj_client.search_series("PR02", "all items")   # resolve exact codes
rows = boj_client.get_data("PR02", meta[0]["series_code"], start="2024-01")

# Or walk a layer tree (flow of funds, balance of payments):
bp = boj_client.get_layer("BP01", "M", [1, 1, 1], start="2025-01")
```

A layer selection matching >1,250 series errors on the BOJ side — narrow
the layers (specify more levels) rather than wildcarding a whole large
database. PR01 alone carries ~31,000 series; always `search_series` first,
never wildcard-pull it.
