# DTCC Swap Data Repository

Script: `projects/apis/dtcc/dtcc.py`
Base URL: `https://kgc0418-tdw-data-0.s3.amazonaws.com`
Dashboard: `https://pddata.dtcc.com/ppd/cftcdashboard`
Auth: None (public S3 bucket)
Rate limit: None formal -- files are large ZIPs (~10-50MB); be respectful
Dependencies: `requests`


## Triggers

Use for: OTC swap flow across 5 asset classes (rates, credits, FX, equities, commodities), tenor distribution on the IRS curve, single-name vs index CDS volumes, FX NDF pair volumes, clearing rate by product type, SOFR transition tracking via underlier composition, cross-asset derivative flow comparison, event-window volume analysis.

Not for: listed futures/options (CME/ICE), directional positioning / net long-short (CFTC COT), real-time intraday flow (files are end-of-day cumulative), counterparty identity (anonymized), swap pricing / mark-to-market (flow data only), pre-2023 historical data (format changed with Part 43 rewrite), bilateral trades exempt from CFTC/SEC mandates.


## Data Catalog

### Asset Classes

| Alias | S3 Name | Display | What It Covers |
|-------|---------|---------|----------------|
| rates | RATES | Interest Rates | OIS swaps, fixed-float swaps, basis swaps, swaptions, caps/floors, FRAs |
| credits | CREDITS | Credits/CDS | Single-name CDS, index CDS (CDX, iTraxx), index tranches, total return swaps |
| fx | FOREX | Foreign Exchange | NDFs, FX forwards, FX options |
| equities | EQUITIES | Equities | Variance swaps, portfolio swaps, equity options |
| commodities | COMMODITIES | Commodities | Energy, metals, agriculture forwards and options |

### Data Sources

| Source | Coverage |
|--------|----------|
| cftc (default) | All 5 asset classes (CFTC-regulated swaps) |
| sec | Credits + equities only (securities-based swaps) |

### Product Types (derived from UPI FISN)

| Asset Class | Product Types |
|-------------|---------------|
| rates | OIS Swap, Fixed-Float Swap, Basis Swap, Option/Swaption, Forward/FRA, Cap/Floor |
| credits | Single Name CDS, Index CDS, Index Tranche, Credit Swap, Total Return Swap |
| fx | NDF, Forward/FRA, Option/Swaption |
| equities | Variance Swap, Portfolio Swap, Option/Swaption, Other |
| commodities | Forward/FRA, Option/Swaption, Other |

### Key Fields (Post-2023 CFTC Part 43)

| Field | Type | Description |
|-------|------|-------------|
| Notional amount-Leg 1/2 | float | Trade size in currency terms |
| Notional currency-Leg 1/2 | string | Currency denomination (USD, EUR, GBP, JPY, etc.) |
| Cleared | string | Y/N/I -- Y and I count as cleared |
| Execution Timestamp | string | When the trade was executed |
| Effective Date | string | Swap start date (used for tenor computation) |
| Expiration Date | string | Swap end date (used for tenor computation) |
| UPI FISN | string | Product classification string (parsed to derive product type) |
| UPI Underlier Name | string | Reference rate or entity (SOFR, CDX.NA.IG, etc.) |
| Fixed rate-Leg 1/2 | float | Fixed rate on IRS legs |
| Action type | string | New, Modify, Cancel, Correct |
| Price / Price notation | float/string | Trade price and notation type |
| Option Type / Strike Price | string/float | For swaptions, caps/floors, FX options |

### Tenor Buckets

| Bucket | Range |
|--------|-------|
| 0-3M | 0 to 3 months |
| 3-6M | 3 to 6 months |
| 6M-1Y | 6 months to 1 year |
| 1-2Y | 1 to 2 years |
| 2-3Y | 2 to 3 years |
| 3-5Y | 3 to 5 years |
| 5-7Y | 5 to 7 years |
| 7-10Y | 7 to 10 years |
| 10-15Y | 10 to 15 years |
| 15-20Y | 15 to 20 years |
| 20-30Y | 20 to 30 years |
| 30Y+ | Over 30 years |

### Summary Fields (per cmd_latest / cmd_summary)

| Field | Type | Description |
|-------|------|-------------|
| trade_count | int | Number of trades for the day |
| total_notional | float | Sum of Leg 1 notional across all trades |
| cleared_count | int | Number of cleared trades (Y or I) |
| cleared_pct | float | Clearing rate as percentage |
| by_product | dict | Breakdown by product type: {count, notional} |
| asset_class | string | Asset class alias |

### Rates Analysis Fields (per cmd_rates)

| Field | Type | Description |
|-------|------|-------------|
| by_tenor | dict | Notional and count per tenor bucket |
| rate_stats | dict | Fixed rate distribution: min, p25, median, p75, max |
| by_product | dict | Product type breakdown |
| top_underliers | dict | Top 15 reference rates by notional |

### Credits Analysis Fields (per cmd_credits)

| Field | Type | Description |
|-------|------|-------------|
| by_product | dict | Single-name vs index vs tranche breakdown |
| top_underliers | dict | Top 20 reference entities by notional |

### FX Analysis Fields (per cmd_fx)

| Field | Type | Description |
|-------|------|-------------|
| by_product | dict | NDF vs forward vs option breakdown |
| top_ccy_pairs | dict | Top 20 currency pairs by notional |

### Cleared Analysis Fields (per cmd_cleared)

| Field | Type | Description |
|-------|------|-------------|
| total_trades | int | Total trade count |
| total_cleared | int | Cleared count |
| overall_pct | float | Overall clearing rate |
| by_product | dict | Per-product: {total, cleared, pct} |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export.

### Latest Day Summary

```bash
# Latest day, default asset class (rates)
python dtcc.py latest
python dtcc.py latest --json

# Latest day for each asset class
python dtcc.py latest --asset-class rates --json
python dtcc.py latest --asset-class credits --json
python dtcc.py latest --asset-class fx --json
python dtcc.py latest --asset-class equities --json
python dtcc.py latest --asset-class commodities --json

# SEC source (credits and equities only)
python dtcc.py latest --asset-class credits --source sec --json
python dtcc.py latest --asset-class equities --source sec --json

# Export
python dtcc.py latest --asset-class rates --export csv
python dtcc.py latest --asset-class credits --export json
```

### Multi-Day History

```bash
# 5-day trend (default)
python dtcc.py history
python dtcc.py history --json

# Custom day counts
python dtcc.py history --asset-class rates --days 10 --json
python dtcc.py history --asset-class credits --days 5 --json
python dtcc.py history --asset-class fx --days 10 --json
python dtcc.py history --asset-class commodities --days 5 --json

# Export multi-day
python dtcc.py history --asset-class rates --days 10 --export csv
```

### Cross-Asset Summary

```bash
# All 5 asset classes in one call
python dtcc.py summary
python dtcc.py summary --json

# Specific date
python dtcc.py summary --date 2025-03-14 --json

# SEC source
python dtcc.py summary --source sec --json

# Export
python dtcc.py summary --export csv
```

### Interest Rate Swap Analysis

```bash
# Full IRS analysis: tenor, product types, rate stats, top underliers
python dtcc.py rates
python dtcc.py rates --json

# Specific date
python dtcc.py rates --date 2025-03-14 --json

# Export
python dtcc.py rates --export csv
python dtcc.py rates --export json
```

### Credit Default Swap Analysis

```bash
# Single-name vs index, top reference entities
python dtcc.py credits
python dtcc.py credits --json

# SEC-regulated securities-based CDS
python dtcc.py credits --source sec --json

# Specific date
python dtcc.py credits --date 2025-03-14 --json

# Export
python dtcc.py credits --export csv
```

### FX Derivative Analysis

```bash
# Currency pair volumes, NDF vs deliverable
python dtcc.py fx
python dtcc.py fx --json

# Specific date
python dtcc.py fx --date 2025-03-14 --json

# Export
python dtcc.py fx --export csv
```

### Commodity Swap Analysis

```bash
# Underlier breakdown (energy, metals, agriculture)
python dtcc.py commodities
python dtcc.py commodities --json

# Specific date
python dtcc.py commodities --date 2025-03-14 --json

# Export
python dtcc.py commodities --export csv
```

### Volume Time Series

```bash
# 20-day notional volume series (default)
python dtcc.py volume
python dtcc.py volume --json

# Custom day counts per asset class
python dtcc.py volume --asset-class rates --days 20 --json
python dtcc.py volume --asset-class credits --days 10 --json
python dtcc.py volume --asset-class fx --days 10 --json
python dtcc.py volume --asset-class equities --days 10 --json
python dtcc.py volume --asset-class commodities --days 10 --json

# Export
python dtcc.py volume --asset-class rates --days 20 --export csv
```

### Search Trades

```bash
# Search by underlier
python dtcc.py search --asset-class rates --underlier SOFR --json
python dtcc.py search --asset-class rates --underlier LIBOR --json
python dtcc.py search --asset-class credits --underlier CDX --json
python dtcc.py search --asset-class credits --underlier iTraxx --json

# Search by currency
python dtcc.py search --asset-class fx --currency BRL --json
python dtcc.py search --asset-class fx --currency KRW --json
python dtcc.py search --asset-class fx --currency INR --json
python dtcc.py search --asset-class fx --currency TWD --json
python dtcc.py search --asset-class rates --currency EUR --json

# Search by product type
python dtcc.py search --asset-class rates --product OIS --json
python dtcc.py search --asset-class credits --product "Index CDS" --json

# Combined filters
python dtcc.py search --asset-class rates --underlier SOFR --product OIS --json

# Specific date
python dtcc.py search --asset-class rates --underlier SOFR --date 2025-03-14 --json

# Export
python dtcc.py search --asset-class rates --underlier SOFR --export csv
```

### Clearing Rate Analysis

```bash
# Clearing rates by product type
python dtcc.py cleared --asset-class rates --json
python dtcc.py cleared --asset-class credits --json
python dtcc.py cleared --asset-class fx --json
python dtcc.py cleared --asset-class equities --json
python dtcc.py cleared --asset-class commodities --json

# Specific date
python dtcc.py cleared --asset-class rates --date 2025-03-14 --json

# Export
python dtcc.py cleared --asset-class credits --export csv
```

### Asset Class Listing

```bash
# List all asset classes, product types, S3 URL format
python dtcc.py assets
python dtcc.py assets --json
```

### Raw Data Export

```bash
# Export raw trade-level data
python dtcc.py export --asset-class rates --days 1 --format csv
python dtcc.py export --asset-class credits --days 5 --format json
python dtcc.py export --asset-class fx --days 1 --format csv
python dtcc.py export --asset-class rates --days 10 --format csv
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands except export |
| `--export csv` | Export to CSV file | All commands except assets, export |
| `--export json` | Export to JSON file | All commands except assets, export |
| `--asset-class X` | Asset class: rates, credits, fx, equities, commodities | latest, history, volume, search, cleared, export |
| `--source X` | Data source: cftc (default), sec | All commands |
| `--days N` | Number of business days | history, volume, export |
| `--date YYYY-MM-DD` | Specific date | rates, credits, fx, commodities, summary, search, cleared |
| `--underlier X` | Filter by underlier name | search |
| `--currency X` | Filter by currency | search |
| `--product X` | Filter by product type | search |
| `--format X` | Export format: csv or json | export |


## Python Recipes

### Cross-Asset Overview

```python
from dtcc import cmd_summary, cmd_latest, cmd_assets

# All 5 asset classes in one call
# Returns: dict keyed by asset class -> {trade_count, total_notional, cleared_count, cleared_pct, by_product}
all_flows = cmd_summary(as_json=True)

# Specific date
all_flows = cmd_summary(date_str="2025-03-14", as_json=True)

# Single asset class latest day
# Returns: {trade_count, total_notional, cleared_count, cleared_pct, by_product, asset_class}
rates_today = cmd_latest(asset_class="rates", as_json=True)
credits_today = cmd_latest(asset_class="credits", as_json=True)
fx_today = cmd_latest(asset_class="fx", as_json=True)
equities_today = cmd_latest(asset_class="equities", as_json=True)
commodities_today = cmd_latest(asset_class="commodities", as_json=True)

# SEC source
sec_credits = cmd_latest(asset_class="credits", source="sec", as_json=True)

# List asset classes and product types
classes = cmd_assets(as_json=True)
```

### Interest Rate Swap Analysis

```python
from dtcc import cmd_rates, cmd_search

# Full IRS analysis: tenor distribution, rate stats, product types, top underliers
# Returns: {trade_count, total_notional, by_tenor, rate_stats, by_product, top_underliers}
rates = cmd_rates(as_json=True)
rates = cmd_rates(date_str="2025-03-14", as_json=True)

# SOFR-specific trades
# Returns: list of raw trade dicts (up to 100)
sofr_trades = cmd_search(asset_class="rates", underlier="SOFR", as_json=True)

# OIS-specific trades
ois_trades = cmd_search(asset_class="rates", product="OIS", as_json=True)

# Combined filter: SOFR OIS
sofr_ois = cmd_search(asset_class="rates", underlier="SOFR", product="OIS", as_json=True)
```

### Credit Default Swap Analysis

```python
from dtcc import cmd_credits, cmd_search, cmd_cleared

# CDS breakdown: single-name vs index, top reference entities
# Returns: {trade_count, total_notional, by_product, top_underliers}
cds = cmd_credits(as_json=True)
cds = cmd_credits(date_str="2025-03-14", as_json=True)

# SEC-regulated CDS
sec_cds = cmd_credits(source="sec", as_json=True)

# CDX index trades
cdx = cmd_search(asset_class="credits", underlier="CDX", as_json=True)

# iTraxx index trades
itraxx = cmd_search(asset_class="credits", underlier="iTraxx", as_json=True)

# Clearing rates for credit products
# Returns: {total_trades, total_cleared, overall_pct, by_product: {total, cleared, pct}}
clearing = cmd_cleared(asset_class="credits", as_json=True)
```

### FX Derivative Analysis

```python
from dtcc import cmd_fx, cmd_search

# FX overview: currency pairs, NDF vs deliverable, product mix
# Returns: {trade_count, total_notional, by_product, top_ccy_pairs}
fx = cmd_fx(as_json=True)
fx = cmd_fx(date_str="2025-03-14", as_json=True)

# EM NDF drilldown by currency
brl = cmd_search(asset_class="fx", currency="BRL", as_json=True)
krw = cmd_search(asset_class="fx", currency="KRW", as_json=True)
inr = cmd_search(asset_class="fx", currency="INR", as_json=True)
twd = cmd_search(asset_class="fx", currency="TWD", as_json=True)
clp = cmd_search(asset_class="fx", currency="CLP", as_json=True)
```

### Commodity & Equity Analysis

```python
from dtcc import cmd_commodities, cmd_latest

# Commodity underlier breakdown
# Returns: {trade_count, total_notional, by_product, top_underliers}
commod = cmd_commodities(as_json=True)

# Equities via latest
eq = cmd_latest(asset_class="equities", as_json=True)
```

### Multi-Day Trends

```python
from dtcc import cmd_history, cmd_volume

# Multi-day summary with daily counts and notional
# Returns: list of {date, trade_count, total_notional, cleared_count, cleared_pct, by_product}
hist = cmd_history(asset_class="rates", days=10, as_json=True)
hist = cmd_history(asset_class="credits", days=5, as_json=True)

# Volume time series (notional only, lighter output)
# Returns: list of {date, trade_count, total_notional}
vol = cmd_volume(asset_class="rates", days=20, as_json=True)
vol = cmd_volume(asset_class="credits", days=10, as_json=True)
vol = cmd_volume(asset_class="fx", days=10, as_json=True)
```

### Clearing & Export

```python
from dtcc import cmd_cleared, cmd_export

# Clearing rates across asset classes
rates_clearing = cmd_cleared(asset_class="rates", as_json=True)
credits_clearing = cmd_cleared(asset_class="credits", as_json=True)
fx_clearing = cmd_cleared(asset_class="fx", as_json=True)

# Raw data export to file
cmd_export(asset_class="rates", days=1, fmt="csv")
cmd_export(asset_class="credits", days=5, fmt="json")

# History with export
cmd_history(asset_class="rates", days=10, export_fmt="json")
```


## Composite Recipes

### Daily Cross-Asset Flow Pulse

```bash
python dtcc.py summary --json
```

PRISM receives: all 5 asset classes with trade count, total notional, clearing rate per class. Identifies which class is unusually active.

### Rate Curve Positioning

```bash
python dtcc.py rates --json
python dtcc.py search --asset-class rates --underlier SOFR --json
python dtcc.py volume --asset-class rates --days 20 --json
```

PRISM receives: tenor distribution across 12 buckets (0-3M through 30Y+), product type mix (OIS vs fixed-float vs basis), fixed rate distribution (median, p25/p75), top underliers with SOFR share, 20-day volume trend for context.

### Credit Risk Appetite

```bash
python dtcc.py credits --json
python dtcc.py search --asset-class credits --underlier CDX --json
python dtcc.py cleared --asset-class credits --json
```

PRISM receives: single-name vs index CDS ratio with top 20 reference entities, CDX-specific trade details, clearing rates by credit product type.

### EM FX NDF Barometer

```bash
python dtcc.py fx --json
python dtcc.py search --asset-class fx --currency KRW --json
python dtcc.py search --asset-class fx --currency BRL --json
python dtcc.py search --asset-class fx --currency INR --json
python dtcc.py volume --asset-class fx --days 10 --json
```

PRISM receives: top currency pairs by notional, NDF vs deliverable ratio, EM-specific trade details for KRW/BRL/INR, 10-day FX volume trend.

### Clearing Mandate Compliance

```bash
python dtcc.py cleared --asset-class rates --json
python dtcc.py cleared --asset-class credits --json
python dtcc.py cleared --asset-class fx --json
```

PRISM receives: per-product clearing rates across three major asset classes. Standard products should show 90%+ clearing; low-clearing pockets indicate bespoke/structured risk.

### Event-Window Volume Analysis

```bash
python dtcc.py volume --asset-class rates --days 20 --json
python dtcc.py volume --asset-class credits --days 20 --json
python dtcc.py history --asset-class rates --days 10 --json
python dtcc.py history --asset-class credits --days 10 --json
python dtcc.py history --asset-class fx --days 10 --json
```

PRISM receives: 20-day notional volume series for rates and credits, 10-day history with trade counts and clearing rates for rates/credits/FX. Spikes should map to known events (FOMC, CPI, NFP, roll dates).

### SOFR Transition Tracker

```bash
python dtcc.py search --asset-class rates --underlier SOFR --json
python dtcc.py search --asset-class rates --underlier LIBOR --json
python dtcc.py search --asset-class rates --underlier "FED FUNDS" --json
python dtcc.py rates --json
```

PRISM receives: SOFR-specific trades, any remaining LIBOR/Fed Funds activity, full rates analysis with top underliers showing reference rate composition.

### Full Drill-Down (Single Asset Class)

```bash
python dtcc.py latest --asset-class rates --json
python dtcc.py rates --json
python dtcc.py cleared --asset-class rates --json
python dtcc.py history --asset-class rates --days 5 --json
```

PRISM receives: day summary with product breakdown, full IRS analysis with tenor/rate stats/underliers, clearing rates by product, 5-day historical context.

### Raw Data Pull for Offline Analysis

```bash
python dtcc.py export --asset-class rates --days 5 --format csv
python dtcc.py export --asset-class credits --days 5 --format csv
```

PRISM receives: full trade-level CSV files for rates and credits covering 5 business days.


## Cross-Source Recipes

### OTC Swap Flow + Overnight Funding Rates

```bash
python dtcc.py rates --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: IRS tenor distribution and rate stats + all 5 overnight reference rates with SOFR-EFFR spread. Shows OTC hedging activity alongside the funding rate picture.

### OTC Swap Flow + SOFR Positioning

```bash
python dtcc.py search --asset-class rates --underlier SOFR --json
python projects/apis/nyfed/nyfed.py sofr --obs 60 --json
```

PRISM receives: SOFR-referenced OTC swap trades + 60-day SOFR rate history with percentile distributions. OTC flow vs underlying rate dynamics.

### Swap Volumes + Futures Positioning

```bash
python dtcc.py summary --json
python projects/apis/cftc/cftc.py rates --json
```

PRISM receives: OTC swap volumes across 5 asset classes + CFTC COT net speculative positioning in rates futures. OTC hedging vs exchange-traded directional bets.

### CDS Flow + Bank Health

```bash
python dtcc.py credits --json
python projects/apis/fdic/fdic.py recipe bank-stress --json
```

PRISM receives: single-name vs index CDS ratio with top reference entities + bank-level stress indicators. Credit hedging intensity vs banking sector fundamentals.

### Commodity Swaps + Physical Market

```bash
python dtcc.py commodities --json
python projects/apis/eia/eia.py summary --json
```

PRISM receives: commodity derivative volumes by underlier + EIA physical energy data. Financial vs physical market correlation.

### OTC Flow + Event Probability

```bash
python dtcc.py summary --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: cross-asset OTC flow snapshot + market-implied event probabilities. Whether hedging activity matches implied probability pricing.

### Rate Curve + Treasury Supply

```bash
python dtcc.py rates --json
python projects/apis/treasury/treasury.py get dts --json
```

PRISM receives: IRS tenor distribution (where duration hedging concentrates) + TGA cash flows. Supply absorption and duration management around issuance.

### EM FX NDF + Cross-Border Flows

```bash
python dtcc.py fx --json
python projects/apis/bis/bis.py lbs --json
```

PRISM receives: FX NDF volumes by currency pair + BIS locational banking statistics for cross-border capital flows. NDF hedging intensity vs banking channel exposure.

### CDS Flow + Rate Regime

```bash
python dtcc.py credits --json
python dtcc.py rates --json
python projects/apis/nyfed/nyfed.py rates --json
```

PRISM receives: credit risk hedging (CDS) + rate hedging (IRS) + overnight funding rates. Simultaneous spikes in rates and credit = macro catalyst.


## Setup

1. No API key required -- data is on a public S3 bucket
2. `pip install requests`
3. Test: `python dtcc.py assets` (lists asset classes, no download)
4. First real test: `python dtcc.py latest --asset-class rates` (downloads one day ~10-50MB)


## Architecture

```
dtcc.py
  Constants       S3_BASE_URL, ASSET_CLASSES (5), TENOR_ORDER (13 buckets),
                  COL_* column name constants (16)
  HTTP            _download_day(), _download_with_fallback(), SESSION
  Date Helpers    _most_recent_business_day, _business_days_back, _prev_business_day
  Parsing         _safe_float, _safe_str, _parse_date_field, _compute_tenor_years,
                  _tenor_bucket, _is_cleared, _notional, _classify_product, _underlier_name
  Analysis        _summarize_day, _volume_series, _group_by_field, _rates_analysis,
                  _credits_analysis, _fx_analysis, _commodity_analysis, _cleared_analysis,
                  _search_trades
  Commands (12)   latest, history, rates, credits, fx, commodities,
                  volume, summary, search, assets, cleared, export
  Interactive     12-item menu -> interactive wrappers with prompts
  Argparse        12 subcommands, all with --json and --export
```

S3 URL pattern:
```
{base}/{source}/eod/{SOURCE}_CUMULATIVE_{CLASS}_{YYYY_MM_DD}.zip
```

Example:
```
https://kgc0418-tdw-data-0.s3.amazonaws.com/cftc/eod/CFTC_CUMULATIVE_RATES_2025_04_11.zip
```
