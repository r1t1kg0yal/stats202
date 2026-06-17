# CFTC Commitments of Traders (COT) -- Positioning Data

Script: `projects/apis/cftc/cftc.py`
Base URL: `https://publicreporting.cftc.gov/resource`
Auth: None required (public Socrata API)
Rate limit: No formal limit; ~0.3s between batch calls (polite usage)
Release schedule: Data as of Tuesday, published Friday 3:30pm ET
Dependencies: `requests`


## Triggers

Use for: futures positioning by trader category (leveraged funds, dealers, asset managers, managed money, producers), net speculative positions, crowding percentiles, weekly position changes, spec-vs-commercial divergence, cross-asset positioning heatmaps, rates/FX/commodity/equity positioning dashboards.

Not for: intraday or real-time positioning (COT is weekly Tuesday snapshot), options-specific Greeks or vol surfaces (COT aggregates futures + options), individual fund-level positions (aggregated by category), OTC swap positioning (DTCC SDR), non-US exchange data (CFTC covers US-regulated only), exchange-specific order flow or volume.


## Data Catalog

### Report Types

#### Traders in Financial Futures (TFF) -- Socrata ID: gpe5-46if
Used for: rates, FX, equity indices, VIX.

| Category | Who | Field Prefix |
|----------|-----|-------------|
| Dealer/Intermediary | Sell-side banks, swap dealers | `dealer_positions_*` |
| Asset Manager/Institutional | Pensions, endowments, insurance, SWFs | `asset_mgr_positions_*` |
| Leveraged Funds | Hedge funds, CTAs, prop desks | `lev_money_positions_*` |
| Other Reportable | Corporates, central banks, treasurers | `other_rept_positions_*` |

Net speculative position = Leveraged Funds long - short.

#### Disaggregated -- Socrata ID: 72hh-3qpy
Used for: energy, metals, agriculture.

| Category | Who | Field Prefix |
|----------|-----|-------------|
| Producer/Merchant | Oil companies, miners, farmers | `prod_merc_positions_*` |
| Swap Dealer | Banks facilitating OTC-to-futures hedges | `swap_positions_*` / `swap__positions_*` |
| Managed Money | CTAs, commodity hedge funds | `m_money_positions_*` |
| Other Reportable | Misc large traders | `other_rept_positions_*` |

Net speculative position = Managed Money long - short.

### Dataset IDs

| Key | Socrata ID | Description |
|-----|-----------|-------------|
| `tff_fut` | gpe5-46if | TFF futures-only |
| `tff_combo` | yw9f-hn96 | TFF futures + options combined |
| `disagg_fut` | 72hh-3qpy | Disaggregated futures-only |
| `disagg_combo` | kh3c-gbw2 | Disaggregated futures + options combined |
| `legacy_fut` | 6dca-aqww | Legacy futures-only |
| `legacy_combo` | jun7-fc8e | Legacy futures + options combined |

### Contract Registry

25 curated macro-relevant contracts across 6 asset groups:

#### Rates (TFF)
| Alias | Contract | CFTC Code |
|-------|----------|-----------|
| `UST_2Y` | UST 2-Year Note | 042601 |
| `UST_5Y` | UST 5-Year Note | 044601 |
| `UST_10Y` | UST 10-Year Note | 043602 |
| `UST_30Y` | UST 30-Year Bond | 020601 |
| `UST_ULTRA` | Ultra Bond | 020604 |
| `SOFR_3M` | SOFR 3-Month | 134741 |

#### FX (TFF)
| Alias | Contract | CFTC Code |
|-------|----------|-----------|
| `EUR_USD` | Euro FX | 099741 |
| `JPY_USD` | Japanese Yen | 097741 |
| `GBP_USD` | British Pound | 096742 |
| `AUD_USD` | Australian Dollar | 232741 |
| `CAD_USD` | Canadian Dollar | 090741 |
| `MXN_USD` | Mexican Peso | 095741 |
| `CHF_USD` | Swiss Franc | 092741 |
| `NZD_USD` | New Zealand Dollar | 112741 |

#### Equity Indices (TFF)
| Alias | Contract | CFTC Code |
|-------|----------|-----------|
| `SP500` | E-mini S&P 500 | 13874A |
| `NASDAQ` | E-mini Nasdaq 100 | 209742 |
| `VIX` | VIX Futures | 1170E1 |

#### Energy (Disaggregated)
| Alias | Contract | CFTC Code |
|-------|----------|-----------|
| `CRUDE_WTI` | Crude Oil WTI | 067651 |
| `NATGAS` | Natural Gas Henry Hub | 023651 |

#### Metals (Disaggregated)
| Alias | Contract | CFTC Code |
|-------|----------|-----------|
| `GOLD` | Gold | 088691 |
| `SILVER` | Silver | 084691 |
| `COPPER` | Copper | 085692 |

#### Agriculture (Disaggregated)
| Alias | Contract | CFTC Code |
|-------|----------|-----------|
| `CORN` | Corn | 002602 |
| `SOYBEANS` | Soybeans | 005602 |
| `WHEAT_SRW` | Wheat SRW | 001602 |

### TFF Fields (per observation)

Speculative (Leveraged Funds):

| Field | Type | Description |
|-------|------|-------------|
| `lev_money_positions_long` | int | Leveraged fund longs |
| `lev_money_positions_short` | int | Leveraged fund shorts |
| `lev_money_positions_spread` | int | Leveraged fund spreads |
| `change_in_lev_money_long` | int | Week-over-week change in longs |
| `change_in_lev_money_short` | int | Week-over-week change in shorts |

Dealer:

| Field | Type | Description |
|-------|------|-------------|
| `dealer_positions_long_all` | int | Dealer longs |
| `dealer_positions_short_all` | int | Dealer shorts |
| `dealer_positions_spread_all` | int | Dealer spreads |

Asset Manager:

| Field | Type | Description |
|-------|------|-------------|
| `asset_mgr_positions_long` | int | Asset manager longs |
| `asset_mgr_positions_short` | int | Asset manager shorts |

Common:

| Field | Type | Description |
|-------|------|-------------|
| `open_interest_all` | int | Total open interest |
| `report_date_as_yyyy_mm_dd` | string | Report date (Tuesday snapshot) |
| `cftc_contract_market_code` | string | Contract identifier |
| `market_and_exchange_names` | string | Full contract name |
| `contract_market_name` | string | Short contract name |

### Disaggregated Fields (per observation)

Speculative (Managed Money):

| Field | Type | Description |
|-------|------|-------------|
| `m_money_positions_long_all` | int | Managed money longs |
| `m_money_positions_short_all` | int | Managed money shorts |
| `m_money_positions_spread` | int | Managed money spreads |
| `change_in_m_money_long_all` | int | Week-over-week change in longs |
| `change_in_m_money_short_all` | int | Week-over-week change in shorts |

Commercial (Producer/Merchant):

| Field | Type | Description |
|-------|------|-------------|
| `prod_merc_positions_long` | int | Producer/merchant longs |
| `prod_merc_positions_short` | int | Producer/merchant shorts |

Swap Dealer:

| Field | Type | Description |
|-------|------|-------------|
| `swap_positions_long_all` | int | Swap dealer longs |
| `swap__positions_short_all` | int | Swap dealer shorts (note: double underscore) |


## CLI Recipes

All commands support `--json` for structured output. Most support `--export csv|json` for file export.

### Positioning

```bash
# Latest week, all 25 contracts
python cftc.py latest
python cftc.py latest --json
python cftc.py latest --export csv

# Latest week, filtered by asset group
# group choices: rates, fx, equity, energy, metals, ags
python cftc.py latest --group rates
python cftc.py latest --group fx --json
python cftc.py latest --group equity --export json
python cftc.py latest --group energy --json
python cftc.py latest --group metals
python cftc.py latest --group ags --json

# Time series for a single contract
# contract: any alias from Contract Registry (e.g. UST_10Y, GOLD, EUR_USD)
python cftc.py history UST_10Y
python cftc.py history UST_10Y --weeks 104
python cftc.py history UST_10Y --weeks 104 --json
python cftc.py history GOLD --weeks 52 --export csv
python cftc.py history EUR_USD --weeks 26 --json
python cftc.py history SOFR_3M --weeks 156 --export json
python cftc.py history CRUDE_WTI --weeks 52
python cftc.py history SP500 --weeks 104 --json

# Weekly position changes, sorted by magnitude
python cftc.py changes
python cftc.py changes --json
python cftc.py changes --group rates
python cftc.py changes --group fx --json
python cftc.py changes --group energy

# Percentile rank vs N-year history (crowding indicators)
python cftc.py crowding
python cftc.py crowding --years 3
python cftc.py crowding --years 1 --json
python cftc.py crowding --group rates --years 3
python cftc.py crowding --group fx --years 3 --json
python cftc.py crowding --group energy --years 5 --export csv
python cftc.py crowding --years 3 --export json
```

### Analysis

```bash
# Full cross-asset table with crowding bars (all 25, 3Y history)
python cftc.py heatmap
python cftc.py heatmap --json
python cftc.py heatmap --export csv

# Contracts at positioning extremes
python cftc.py extremes
python cftc.py extremes --threshold 15
python cftc.py extremes --threshold 10 --years 3
python cftc.py extremes --threshold 10 --years 5 --json
python cftc.py extremes --threshold 20 --years 1

# Speculative vs commercial divergence
python cftc.py divergence
python cftc.py divergence --json
python cftc.py divergence --group rates
python cftc.py divergence --group fx --json
python cftc.py divergence --group energy
python cftc.py divergence --group metals --json
```

### Dashboards

```bash
# Rates positioning dashboard (6 contracts + crowding + divergence)
python cftc.py rates
python cftc.py rates --json
python cftc.py rates --export csv

# FX positioning dashboard (8 contracts + crowding + divergence)
python cftc.py fx
python cftc.py fx --json
python cftc.py fx --export csv

# Commodities dashboard (energy + metals + ags, 8 contracts)
python cftc.py commodities
python cftc.py commodities --json
python cftc.py commodities --export json

# Full cross-asset scan (all 25 contracts + crowding + divergence + signals)
python cftc.py macro-scan
python cftc.py macro-scan --json
python cftc.py macro-scan --export csv
```

### Data

```bash
# Search contracts by name across CFTC database
python cftc.py search "crude"
python cftc.py search "treasury"
python cftc.py search "gold" --json
python cftc.py search "euro"
python cftc.py search "natural gas"

# List curated contract registry
python cftc.py contracts
python cftc.py contracts --group rates
python cftc.py contracts --group fx
python cftc.py contracts --group energy

# Export raw data
python cftc.py export
python cftc.py export --contract UST_10Y --weeks 104 --format csv
python cftc.py export --contract GOLD --weeks 52 --format json
python cftc.py export --contract EUR_USD --weeks 156 --format csv
python cftc.py export --format json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to CSV file | latest, history, crowding, heatmap, rates, fx, commodities, macro-scan |
| `--export json` | Export to JSON file | latest, history, crowding, heatmap, rates, fx, commodities, macro-scan |
| `--group GROUP` | Filter by asset group (rates/fx/equity/energy/metals/ags) | latest, changes, crowding, divergence, contracts |
| `--weeks N` | Number of weeks of history (default 52) | history, export |
| `--years N` | History period in years (default 3) | crowding, extremes |
| `--threshold N` | Percentile threshold for extremes (default 15) | extremes |
| `--contract ALIAS` | Contract alias for single-contract export | export |
| `--format FMT` | Export format (csv/json, default csv) | export |


## Python Recipes

### Positioning

```python
from cftc import cmd_latest, cmd_history, cmd_changes

# Latest week, all 25 contracts
# Returns: dict keyed by alias -> {alias, name, group, report, date, oi, net_spec,
#          chg_spec, pct_oi, net_comm, chg_comm, pctile, label}
latest = cmd_latest(as_json=True)

# Latest week, filtered by group
# group: "rates" | "fx" | "equity" | "energy" | "metals" | "ags"
rates_pos = cmd_latest(group="rates", as_json=True)
fx_pos = cmd_latest(group="fx", as_json=True)

# Time series for one contract
# Returns: list of {date, oi, net_spec, chg_spec, net_comm, pct_oi} ordered by date desc
hist = cmd_history(alias="UST_10Y", weeks=104, as_json=True)
hist = cmd_history(alias="GOLD", weeks=52, as_json=True)
hist = cmd_history(alias="EUR_USD", weeks=156, as_json=True)
hist = cmd_history(alias="SOFR_3M", weeks=52, as_json=True)

# Weekly changes, sorted by magnitude
# Returns: list of summary dicts sorted by abs(chg_spec) desc
changes = cmd_changes(as_json=True)
changes = cmd_changes(group="rates", as_json=True)
```

### Analysis

```python
from cftc import cmd_crowding, cmd_heatmap, cmd_extremes, cmd_divergence

# Crowding percentiles vs N-year history
# Returns: dict keyed by alias -> {alias, name, ..., pctile, label}
# label: "EXTREME LONG" (>=90), "LONG" (>=75), "EXTREME SHORT" (<=10), "SHORT" (<=25)
crowding = cmd_crowding(years=3, as_json=True)
crowding = cmd_crowding(group="rates", years=3, as_json=True)
crowding = cmd_crowding(group="fx", years=5, as_json=True)

# Full heatmap (all 25, 3Y crowding)
# Returns: dict keyed by alias -> summary with pctile and label
heatmap = cmd_heatmap(as_json=True)

# Contracts at percentile extremes
# Returns: dict of contracts where pctile <= threshold or >= (100-threshold)
extremes = cmd_extremes(threshold=15, years=3, as_json=True)
extremes = cmd_extremes(threshold=10, years=5, as_json=True)

# Spec vs commercial divergence
# Returns: dict keyed by alias -> {net_spec, net_comm, chg_spec, chg_comm, ...}
div = cmd_divergence(as_json=True)
div = cmd_divergence(group="rates", as_json=True)
```

### Dashboards

```python
from cftc import cmd_dashboard, cmd_macro_scan

# Asset class dashboards (crowding + divergence + signals)
# Returns: dict keyed by alias -> summary with pctile, label, divergence
rates = cmd_dashboard(groups=["rates"], as_json=True)
fx = cmd_dashboard(groups=["fx"], as_json=True)
commodities = cmd_dashboard(groups=["energy", "metals", "ags"], as_json=True)

# Full cross-asset scan (all 25)
scan = cmd_macro_scan(as_json=True)
```

### Data

```python
from cftc import cmd_search, cmd_contracts, cmd_export_data

# Search contracts across CFTC database
cmd_search(query="crude", as_json=True)
cmd_search(query="treasury", as_json=True)

# List curated registry (display only, no return)
cmd_contracts()
cmd_contracts(group="rates")

# Export raw data to file
cmd_export_data(alias="UST_10Y", weeks=104, fmt="csv")
cmd_export_data(alias="GOLD", weeks=52, fmt="json")
cmd_export_data(fmt="csv")  # all contracts, latest
```

### Direct API

```python
import requests

BASE = "https://publicreporting.cftc.gov/resource"
TFF = "gpe5-46if"
DISAGG = "72hh-3qpy"

# Latest 10Y Treasury positioning
r = requests.get(f"{BASE}/{TFF}.json", params={
    "$where": "cftc_contract_market_code='043602'",
    "$order": "report_date_as_yyyy_mm_dd DESC",
    "$limit": 1,
})
row = r.json()[0]
net_spec = int(row["lev_money_positions_long"]) - int(row["lev_money_positions_short"])

# Multiple contracts in one call
codes = "('042601','044601','043602','020601')"
r = requests.get(f"{BASE}/{TFF}.json", params={
    "$where": f"cftc_contract_market_code IN {codes}",
    "$order": "report_date_as_yyyy_mm_dd DESC",
    "$limit": 20,
})

# Disaggregated: crude oil managed money
r = requests.get(f"{BASE}/{DISAGG}.json", params={
    "$where": "cftc_contract_market_code='067651'",
    "$order": "report_date_as_yyyy_mm_dd DESC",
    "$limit": 1,
})
row = r.json()[0]
net_mm = int(row["m_money_positions_long_all"]) - int(row["m_money_positions_short_all"])
```


## Composite Recipes

### Weekly Positioning Review (Friday after 3:30pm ET)

```bash
python cftc.py latest --json
python cftc.py changes --json
python cftc.py extremes --threshold 15 --json
```

PRISM receives: net spec position for all 25 contracts with open interest, weekly changes sorted by magnitude with direction labels, contracts at percentile extremes (below 15th or above 85th on 3Y history).

### Crowding / Mean Reversion Scan

```bash
python cftc.py crowding --years 3 --json
```

PRISM receives: 3-year percentile rank for each of 25 contracts, crowding labels (EXTREME LONG/SHORT at 90/10 %ile), net spec levels, weekly changes, pct of OI.

### Rates Positioning Deep Dive

```bash
python cftc.py rates --json
python cftc.py history UST_10Y --weeks 104 --json
python cftc.py history SOFR_3M --weeks 104 --json
python cftc.py divergence --group rates --json
```

PRISM receives: 6 rates contracts (2Y/5Y/10Y/30Y/Ultra/SOFR) with crowding + divergence + signals, 2-year history for 10Y and SOFR with weekly net spec and OI, spec-vs-dealer divergence for all rates tenors.

### FX Positioning Map

```bash
python cftc.py fx --json
python cftc.py history EUR_USD --weeks 104 --json
python cftc.py history JPY_USD --weeks 104 --json
```

PRISM receives: 8 FX contracts with crowding + divergence + signals, 2-year history for EUR and JPY as G10 bellwethers.

### Commodities Positioning Review

```bash
python cftc.py commodities --json
python cftc.py history CRUDE_WTI --weeks 52 --json
python cftc.py history GOLD --weeks 52 --json
```

PRISM receives: energy + metals + ags dashboard (8 contracts) with crowding + divergence, 1-year WTI and gold histories with managed money net positioning.

### Full Cross-Asset Regime Read

```bash
python cftc.py macro-scan --json
```

PRISM receives: all 25 contracts with net spec, crowding percentile, weekly changes, divergence flags, and key signals. Full positioning regime snapshot.

### Pre-Trade Positioning Check

```bash
python cftc.py history <CONTRACT> --weeks 104 --json
python cftc.py crowding --group <GROUP> --json
```

PRISM receives: 2-year history for the target contract (net spec range, current percentile, mean), crowding context for the full asset group.

### Event-Window Positioning Shift

```bash
python cftc.py history <CONTRACT> --weeks 12 --json
python cftc.py changes --group <GROUP> --json
python cftc.py extremes --threshold 15 --years 3 --json
```

PRISM receives: 3-month history for the target contract showing positioning evolution around the event, weekly changes for the asset group, extreme readings that may have formed during the event window.


## Cross-Source Recipes

### Positioning + OIS Swap Flow

```bash
python cftc.py rates --json
python projects/apis/dtcc/dtcc.py latest irs --json
```

PRISM receives: rates positioning (COT) + OIS swap volumes (DTCC). Derivative hedging activity vs futures positioning.

### Positioning + Actual Overnight Rates

```bash
python cftc.py rates --json
python projects/apis/nyfed/nyfed.py rates --json
```

PRISM receives: net speculative SOFR/Treasury futures positioning + actual overnight rates (SOFR/EFFR). Directional bets vs funding conditions.

### Positioning + Fed Probability

```bash
python cftc.py history SOFR_3M --weeks 26 --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: SOFR futures positioning trajectory + market-implied cut/hike probabilities. Calibrates implied pricing vs positioning.

### Positioning + Treasury Supply

```bash
python cftc.py rates --json
python projects/apis/treasury/treasury.py get dts --json
```

PRISM receives: duration positioning (COT) + Treasury issuance flows. Net duration supply/demand balance.

### Positioning + Funding Stress

```bash
python cftc.py rates --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: rates/SOFR positioning + full funding rate complex (SOFR/EFFR/OBFR + RRP + repo). Positioning vs plumbing stress.

### Positioning + Auction Absorption

```bash
python cftc.py latest --group rates --json
python projects/apis/nyfed/nyfed.py pd-positions --count 12 --json
python projects/apis/treasurydirect/treasurydirect.py api auctions --days 30
```

PRISM receives: spec positioning + primary dealer inventory + recent auction results. Supply absorption mechanics.

### FX Positioning + BIS Cross-Border Flows

```bash
python cftc.py fx --json
python projects/apis/bis/bis.py lbs --json
```

PRISM receives: FX futures positioning + cross-border banking flows. Capital flow + FX positioning composite for EM analysis.

### Commodity Positioning + Inventory

```bash
python cftc.py commodities --json
python projects/apis/electricity/electricity.py petroleum inventories --json
```

PRISM receives: energy/metals/ags positioning + physical inventory data. Fundamental supply vs speculative positioning.

### Full Macro Positioning + Prediction Markets

```bash
python cftc.py macro-scan --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset macro --json
```

PRISM receives: full 25-contract positioning regime + macro probability surface. Probability-weighted positioning analysis.


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python cftc.py latest --group rates`
4. Full test: `python cftc.py macro-scan`


## Architecture

```
cftc.py
  Constants       BASE_URL, DATASETS (6), CONTRACT_REGISTRY (25), FIELD_MAP (tff/disagg),
                  GROUP_ORDER, GROUP_NAMES
  HTTP            _request() with retries, rate limit handling
  Parsing         _safe_int(), _safe_float(), _parse_date()
  Positioning     _net_spec(), _net_comm(), _chg_net_spec(), _chg_net_comm(),
                  _get_oi(), _pct_oi(), _percentile_rank(), _crowding_label()
  Display         _build_summaries() -> _display_table() (latest/crowding/divergence/changes),
                  _display_signals() for extreme readings
  Data Fetchers   _fetch_latest(), _fetch_history(), _fetch_multi_history()
  Commands (14)   latest, history, changes, crowding, heatmap, extremes, divergence,
                  rates, fx, commodities, macro-scan, search, contracts, export
  Interactive     14-item menu -> interactive wrappers with prompts
  Argparse        14 subcommands, all with --json and --export
```

API endpoints:
```
/resource/gpe5-46if.json    -> TFF futures-only (rates, FX, equity)
/resource/yw9f-hn96.json    -> TFF futures + options combined
/resource/72hh-3qpy.json    -> Disaggregated futures-only (energy, metals, ags)
/resource/kh3c-gbw2.json    -> Disaggregated futures + options combined
/resource/6dca-aqww.json    -> Legacy futures-only
/resource/jun7-fc8e.json    -> Legacy futures + options combined
```
