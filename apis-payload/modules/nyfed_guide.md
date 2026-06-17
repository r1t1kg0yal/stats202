# NY Fed Markets Data

Script: `projects/apis/nyfed/nyfed.py`
Base URL: `https://markets.newyorkfed.org`
Auth: None required
Rate limit: ~0.2s between calls (polite usage)
Dependencies: `requests`


## Triggers

Use for: overnight reference rates (SOFR/EFFR/OBFR/TGCR/BGCR), SOMA balance sheet holdings (summary and CUSIP-level), treasury securities operations (outright purchases/sales/buybacks), agency MBS operations (purchases/sales/rolls/swaps), securities lending from SOMA, central bank liquidity swaps (FX swap lines), repo/reverse-repo operations, primary dealer positioning, funding stress assessment, QT runoff monitoring, weighted average maturity analysis, SOMA composition tracking.

Not for: yield curve / term rates (Treasury Fiscal Data), auction results (TreasuryDirect), OTC swap volumes (DTCC), futures positioning (CFTC), bank-level financials (FDIC), commercial paper / CD rates (FRED), intraday rates (these are T+1 daily).


## API Surface Coverage

All 10 public NY Fed Markets databases:

| Database | API Prefix | Commands |
|----------|-----------|----------|
| Reference Rates | `/api/rates/` | rates, sofr, effr, rate-history |
| SOMA Holdings (summary) | `/api/soma/summary` | soma, soma-history |
| SOMA Holdings (Treasury detail) | `/api/soma/tsy/` | soma-holdings, soma-cusip, soma-wam, soma-monthly |
| SOMA Holdings (Agency detail) | `/api/soma/agency/` | soma-agency |
| Treasury Securities Operations | `/api/tsy/` | tsy-ops, tsy-search |
| Agency MBS Operations | `/api/ambs/` | ambs-ops |
| Securities Lending | `/api/seclending/` | seclending |
| Central Bank Liquidity Swaps | `/api/fxs/` | fxswaps |
| Repo/Reverse Repo | `/api/rp/` | repo, rrp |
| Primary Dealer Statistics | `/api/pd/` | pd-positions, pd-snapshot, series |


## Data Catalog

### Reference Rate Types

| Key | Label | Type | Description |
|-----|-------|------|-------------|
| `sofr` | SOFR | Secured | Secured Overnight Financing Rate (~$2T/day) |
| `effr` | EFFR | Unsecured | Effective Federal Funds Rate (~$100B/day) |
| `obfr` | OBFR | Unsecured | Overnight Bank Funding Rate (~$200B/day) |
| `tgcr` | TGCR | Secured | Tri-Party General Collateral Rate (~$600B/day) |
| `bgcr` | BGCR | Secured | Broad General Collateral Rate (~$800B/day) |

### Rate Fields (per observation)

| Field | Type | Description |
|-------|------|-------------|
| `effectiveDate` | string | Publication date (T+1) |
| `type` | string | SOFR, EFFR, OBFR, TGCR, BGCR, SOFRAI |
| `percentRate` | float | Volume-weighted median rate |
| `percentPercentile1` | float | 1st percentile |
| `percentPercentile25` | float | 25th percentile |
| `percentPercentile75` | float | 75th percentile |
| `percentPercentile99` | float | 99th percentile |
| `volumeInBillions` | float | Transaction volume ($B) |
| `targetRateFrom` | float | Lower bound of target range (EFFR only) |
| `targetRateTo` | float | Upper bound of target range (EFFR only) |

### SOFR Averages Fields (type=SOFRAI)

| Field | Type | Description |
|-------|------|-------------|
| `average30day` | float | 30-day compounded SOFR average |
| `average90day` | float | 90-day compounded SOFR average |
| `average180day` | float | 180-day compounded SOFR average |
| `index` | float | Cumulative compounded return since 2018-04-02 |

### SOMA Summary Fields

| Field | Type | Description |
|-------|------|-------------|
| `asOfDate` | string | Weekly snapshot date (Wednesday) |
| `total` | int | Total SOMA holdings (par value, raw) |
| `notesbonds` | int | Treasury notes and bonds |
| `bills` | int | Treasury bills |
| `tips` | int | TIPS |
| `frn` | int | Floating Rate Notes |
| `mbs` | int | Agency MBS |
| `cmbs` | int | Commercial MBS |
| `agencies` | int | Agency debt |
| `tipsInflationCompensation` | int | Inflation compensation on TIPS |

### SOMA CUSIP-Level Holdings Fields

| Field | Type | Description |
|-------|------|-------------|
| `asOfDate` | string | Snapshot date |
| `cusip` | string | CUSIP identifier |
| `maturityDate` | string | Maturity date |
| `issuer` | string | Issuer (Agency holdings only: FNMA, FHLMC, GNMA) |
| `coupon` | string | Coupon rate (blank for bills) |
| `parValue` | string | Par value in dollars |
| `percentOutstanding` | string | Fed's share of total outstanding |
| `changeFromPriorWeek` | string | Par value change from prior week |
| `securityType` | string | Bills, NotesBonds, FRN, TIPS, Agency Debts, MBS, CMBS |

### Treasury Securities Operations Fields

| Field | Type | Description |
|-------|------|-------------|
| `operationId` | string | Operation identifier |
| `operationDate` | string | Date of operation |
| `operationType` | string | Outright Bill Purchase, Outright Coupon Purchase, etc. |
| `operationDirection` | string | P=Purchase, S=Sale |
| `auctionMethod` | string | Multiple Price, Single Price |
| `totalParAmtSubmitted` | string | Total par submitted |
| `totalParAmtAccepted` | string | Total par accepted |
| `maturityRangeStart` | string | Maturity range start |
| `maturityRangeEnd` | string | Maturity range end |
| `settlementDate` | string | Settlement date |

### Agency MBS Operations Fields

| Field | Type | Description |
|-------|------|-------------|
| `operationId` | string | Operation identifier |
| `operationDate` | string | Date of operation |
| `operationType` | string | Outright TBA Purchase, Outright Specified Pool Sale, Dollar Roll, Coupon Swap |
| `operationDirection` | string | P=Purchase, S=Sale |
| `method` | string | Multiple Price |
| `totalSubmittedOrigFace` | string | Original face submitted |
| `totalAcceptedOrigFace` | string | Original face accepted |
| `totalSubmittedCurrFace` | string | Current face submitted |
| `totalAcceptedCurrFace` | string | Current face accepted |
| `settlementDate` | string | Settlement date |

### Securities Lending Fields

| Field | Type | Description |
|-------|------|-------------|
| `operationId` | string | Operation identifier |
| `operationDate` | string | Date of operation |
| `operationType` | string | Securities Lending or Extensions |
| `settlementDate` | string | Settlement date |
| `maturityDate` | string | Maturity date (overnight or term) |
| `totalParAmtSubmitted` | int | Par amount submitted |
| `totalParAmtAccepted` | int | Par amount accepted |
| `totalParAmtExtended` | int | Par amount extended (extensions only) |

### Repo Operation Fields

| Field | Type | Description |
|-------|------|-------------|
| `operationDate` | string | Date of operation |
| `operationType` | string | Repo type |
| `operationMethod` | string | Execution method |
| `term` | string | Overnight or term |
| `totalAmtSubmitted` | float | Total bid amount |
| `totalAmtAccepted` | float | Total accepted amount |
| `details[].securityType` | string | Collateral type |
| `details[].amtSubmitted` | float | Per-collateral submitted |
| `details[].amtAccepted` | float | Per-collateral accepted |
| `details[].minimumBidRate` | float | Minimum bid rate |

### ON RRP Fields

| Field | Type | Description |
|-------|------|-------------|
| `operationDate` | string | Date |
| `term` | string | Overnight |
| `totalAmtAccepted` | float | Cash absorbed by facility |
| `participatingCpty` | int | Number of counterparties |
| `percentOfferingRate` | float | Rate paid on ON RRP |
| `percentAwardRate` | float | Actual award rate |

### Primary Dealer Curated Series

| Key ID | Description |
|--------|-------------|
| `PDPOSGST-TOT` | Treasury Positions (ex-TIPS) |
| `PDPOSCS-TOT` | Corporate Securities Positions |
| `PDPOSMBS-TOT` | MBS Positions |
| `PDPOSFGS-TOT` | Agency/GSE Positions (ex-MBS) |

### QT Reinvestment Caps

| Asset | Monthly Cap |
|-------|-------------|
| Treasury | $25B/month |
| MBS | $35B/month |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export.

### Reference Rates

```bash
python nyfed.py rates
python nyfed.py sofr --obs 60
python nyfed.py effr --obs 30
python nyfed.py rate-history sofr --start 2025-01-01 --end 2026-04-01
python nyfed.py rate-history effr --start 2025-06-01
python nyfed.py rate-history tgcr --start 2025-01-01 --json
```

### SOMA Summary

```bash
python nyfed.py soma
python nyfed.py soma --json
python nyfed.py soma-history --weeks 52
python nyfed.py soma-history --weeks 104 --export csv
```

### SOMA Detailed (CUSIP-Level)

```bash
# All Treasury holdings (429 securities as of latest date)
python nyfed.py soma-holdings
python nyfed.py soma-holdings --json
python nyfed.py soma-holdings --type bills
python nyfed.py soma-holdings --type notesbonds
python nyfed.py soma-holdings --type tips
python nyfed.py soma-holdings --date 2025-12-31

# Agency/MBS holdings (9000+ securities)
python nyfed.py soma-agency
python nyfed.py soma-agency --json
python nyfed.py soma-agency --type mbs
python nyfed.py soma-agency --type "agency debts"

# Single CUSIP history (track Fed accumulation/runoff of specific bond)
python nyfed.py soma-cusip 912810QA9
python nyfed.py soma-cusip 912810QA9 --json
python nyfed.py soma-cusip 31359MEU3 --asset-class agency

# Weighted average maturity
python nyfed.py soma-wam
python nyfed.py soma-wam --type notesbonds
python nyfed.py soma-wam --type bills
python nyfed.py soma-wam --asset-class agency

# Monthly aggregated SOMA Treasury data
python nyfed.py soma-monthly
python nyfed.py soma-monthly --last 48 --json
python nyfed.py soma-monthly --last 12 --export csv
```

### Treasury Securities Operations

```bash
# Latest operations (purchases, sales, buybacks)
python nyfed.py tsy-ops
python nyfed.py tsy-ops --count 20
python nyfed.py tsy-ops --operation purchases
python nyfed.py tsy-ops --operation sales
python nyfed.py tsy-ops --include details --json

# Search by date range
python nyfed.py tsy-search --start 2025-01-01 --end 2026-04-01
python nyfed.py tsy-search --operation purchases --start 2025-06-01 --json
```

### Agency MBS Operations

```bash
python nyfed.py ambs-ops
python nyfed.py ambs-ops --count 20
python nyfed.py ambs-ops --operation purchases
python nyfed.py ambs-ops --operation sales
python nyfed.py ambs-ops --operation roll
python nyfed.py ambs-ops --operation swap
python nyfed.py ambs-ops --json
```

### Securities Lending

```bash
python nyfed.py seclending
python nyfed.py seclending --count 20
python nyfed.py seclending --operation seclending
python nyfed.py seclending --operation extensions
python nyfed.py seclending --include details --json
```

### Central Bank Liquidity Swaps

```bash
python nyfed.py fxswaps
python nyfed.py fxswaps --type usdollar
python nyfed.py fxswaps --type nonusdollar
python nyfed.py fxswaps --count 20 --json
```

### Repo Operations

```bash
python nyfed.py repo
python nyfed.py repo --count 10
python nyfed.py rrp
python nyfed.py rrp --count 30 --export csv
```

### Primary Dealers

```bash
python nyfed.py pd-positions
python nyfed.py pd-positions --count 24 --json
python nyfed.py pd-snapshot
python nyfed.py pd-snapshot --json
python nyfed.py series
python nyfed.py series --query treasury
```

### Dashboards

```bash
python nyfed.py funding-snapshot
python nyfed.py funding-snapshot --json
python nyfed.py qt-monitor
python nyfed.py qt-monitor --weeks 52 --json
python nyfed.py operations-summary
python nyfed.py operations-summary --json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to CSV file | All commands |
| `--export json` | Export to JSON file | All commands |
| `--obs N` | Number of observations | sofr, effr |
| `--weeks N` | Number of weeks | soma-history, qt-monitor |
| `--count N` | Number of items | tsy-ops, ambs-ops, seclending, fxswaps, repo, rrp, pd-positions |
| `--start YYYY-MM-DD` | Start date | rate-history, tsy-search |
| `--end YYYY-MM-DD` | End date | rate-history, tsy-search |
| `--query TEXT` | Keyword filter | series |
| `--date YYYY-MM-DD` | As-of date | soma-holdings, soma-agency, soma-wam |
| `--type TYPE` | Filter by sub-type | soma-holdings, soma-agency, soma-wam, fxswaps |
| `--operation TYPE` | Operation filter | tsy-ops, tsy-search, ambs-ops, seclending |
| `--include summary\|details` | Detail level | tsy-ops, tsy-search, ambs-ops, seclending |
| `--asset-class tsy\|agency` | Asset class | soma-cusip, soma-wam |
| `--last N` | Last N months | soma-monthly |


## Python Recipes

### Reference Rates

```python
from nyfed import cmd_rates, cmd_sofr, cmd_effr, cmd_rate_history

rates = cmd_rates(as_json=True)
sofr = cmd_sofr(obs=60, as_json=True)
effr = cmd_effr(obs=30, as_json=True)
history = cmd_rate_history(rate_key="sofr", start_date="2025-01-01",
                           end_date="2026-04-01", as_json=True)
```

### SOMA Summary

```python
from nyfed import cmd_soma, cmd_soma_history, cmd_qt_monitor

soma = cmd_soma(as_json=True)
soma_ts = cmd_soma_history(weeks=52, as_json=True)
qt = cmd_qt_monitor(weeks=26, as_json=True)
```

### SOMA Detailed Holdings

```python
from nyfed import (cmd_soma_holdings, cmd_soma_agency, cmd_soma_cusip,
                    cmd_soma_wam, cmd_soma_monthly)

# 429 CUSIP-level Treasury holdings with par, % outstanding, weekly changes
tsy_holdings = cmd_soma_holdings(as_json=True)

# Filter by type
bills = cmd_soma_holdings(holding_type="bills", as_json=True)
notes_bonds = cmd_soma_holdings(holding_type="notesbonds", as_json=True)

# 9000+ Agency/MBS holdings
agency = cmd_soma_agency(as_json=True)
agency_mbs = cmd_soma_agency(holding_type="mbs", as_json=True)

# Track single CUSIP across all SOMA snapshots (full history since 2003)
cusip_history = cmd_soma_cusip("912810QA9", as_json=True)

# Weighted average maturity
wam = cmd_soma_wam(holding_type="all", as_json=True)

# Monthly aggregated Treasury SOMA data
monthly = cmd_soma_monthly(last_n=24, as_json=True)
```

### Treasury & Agency Operations

```python
from nyfed import (cmd_tsy_ops, cmd_tsy_ops_search, cmd_ambs_ops,
                    cmd_seclending_ops, cmd_fxswaps)

# Treasury operations: outright bill/coupon purchases, sales
tsy = cmd_tsy_ops(operation="all", n=20, as_json=True)

# Search Treasury operations by date range
tsy_search = cmd_tsy_ops_search(operation="purchases",
                                 start_date="2025-01-01", as_json=True)

# Agency MBS: purchases, sales, dollar rolls, coupon swaps
ambs = cmd_ambs_ops(operation="all", n=20, as_json=True)

# Securities lending (daily, overnight, ~$35-40B/day)
seclend = cmd_seclending_ops(operation="all", n=10, as_json=True)

# Central bank liquidity swaps (dormant outside stress)
fxs = cmd_fxswaps(n=10, as_json=True)
```

### Repo & RRP

```python
from nyfed import cmd_repo, cmd_rrp

repo_ops = cmd_repo(n=10, as_json=True)
rrp_ops = cmd_rrp(n=10, as_json=True)
```

### Primary Dealers

```python
from nyfed import cmd_pd_positions, cmd_pd_snapshot, cmd_series

pd = cmd_pd_positions(n_recent=24, as_json=True)
pd_all = cmd_pd_snapshot(as_json=True)
all_series = cmd_series(as_json=True)
```

### Dashboards

```python
from nyfed import cmd_funding_snapshot, cmd_qt_monitor, cmd_operations_summary

# All rates + spread + RRP + stress assessment
snapshot = cmd_funding_snapshot(as_json=True)

# SOMA runoff pace, cap utilization, cumulative
qt = cmd_qt_monitor(weeks=52, as_json=True)

# All open market operations in one call
ops = cmd_operations_summary(as_json=True)
```


## Composite Recipes

### Morning Funding Check

```bash
python nyfed.py funding-snapshot --json
```

### Reserve Regime Assessment

```bash
python nyfed.py rrp --count 10 --json
python nyfed.py rates --json
python nyfed.py rate-history sofr --start $(date -v-3m +%Y-%m-%d) --json
python nyfed.py rate-history effr --start $(date -v-3m +%Y-%m-%d) --json
python nyfed.py qt-monitor --weeks 26 --json
```

### QT Pace and Balance Sheet Trajectory

```bash
python nyfed.py qt-monitor --weeks 52 --json
python nyfed.py soma-history --weeks 104 --json
python nyfed.py soma-monthly --last 24 --json
```

### SOMA Composition Deep Dive

```bash
python nyfed.py soma-holdings --json
python nyfed.py soma-agency --type mbs --json
python nyfed.py soma-wam --json
python nyfed.py soma-monthly --last 48 --json
```

### Treasury Buyback / Operations Monitoring

```bash
python nyfed.py tsy-ops --count 20 --json
python nyfed.py tsy-search --operation purchases --start $(date -v-6m +%Y-%m-%d) --json
python nyfed.py tsy-search --operation sales --start $(date -v-6m +%Y-%m-%d) --json
```

### MBS Portfolio Management

```bash
python nyfed.py ambs-ops --count 20 --json
python nyfed.py soma-agency --type mbs --json
python nyfed.py seclending --count 20 --json
```

### Full Operations Overview

```bash
python nyfed.py operations-summary --json
```

### Rate Complex Deep Dive

```bash
python nyfed.py rates --json
python nyfed.py sofr --obs 60 --json
python nyfed.py effr --obs 60 --json
python nyfed.py rate-history tgcr --start $(date -v-6m +%Y-%m-%d) --json
python nyfed.py rate-history bgcr --start $(date -v-6m +%Y-%m-%d) --json
```

### Primary Dealer Positioning Review

```bash
python nyfed.py pd-positions --count 24 --json
python nyfed.py pd-snapshot --json
python nyfed.py series --query treasury --json
```

### Event-Window Analysis (Quarter-End, FOMC, Tax Date)

```bash
python nyfed.py rate-history sofr --start YYYY-MM-DD --end YYYY-MM-DD --json
python nyfed.py rate-history effr --start YYYY-MM-DD --end YYYY-MM-DD --json
python nyfed.py rates --json
python nyfed.py rrp --count 10 --json
python nyfed.py seclending --count 10 --json
```

### Securities Lending Demand

```bash
python nyfed.py seclending --count 30 --json
python nyfed.py seclending --operation extensions --count 10 --json
```


## Cross-Source Recipes

### Funding + OIS Swap Flow

```bash
python nyfed.py funding-snapshot --json
python projects/apis/dtcc/dtcc.py latest irs --json
```

### Rates + SOFR Positioning

```bash
python nyfed.py rates --json
python projects/apis/cftc/cftc.py rates --json
```

### Funding + Treasury Supply

```bash
python nyfed.py funding-snapshot --json
python projects/apis/treasury/treasury.py get dts --json
```

### RRP + Auction Absorption

```bash
python nyfed.py rrp --count 10 --json
python nyfed.py pd-positions --count 12 --json
python projects/apis/treasurydirect/treasurydirect.py api auctions --days 30
```

### Funding + Fed Probability

```bash
python nyfed.py funding-snapshot --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

### QT + Bank Health

```bash
python nyfed.py qt-monitor --weeks 26 --json
python projects/apis/fdic/fdic.py recipe bank-stress --json
```

### SOMA Holdings + SEC 13F

```bash
python nyfed.py soma-holdings --json
python projects/apis/sec_edgar/sec_edgar.py search-13f --cik 0000070858
```


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python nyfed.py rates`
4. Full test: `python nyfed.py operations-summary`


## Architecture

```
nyfed.py (24 commands, ~2600 lines)
  Constants       BASE_URL, RATE_TYPES (5), PD_KEY_SERIES (4), QT_CAPS,
                  TSY_OPERATIONS, AMBS_OPERATIONS, SECLENDING_OPERATIONS,
                  FXS_TYPES, SOMA_TSY_TYPES, SOMA_AGENCY_TYPES

  HTTP            _request() with retries, rate limit handling

  Data Fetchers
    Rates         _fetch_all_rates_latest, _fetch_rate_last, _fetch_rate_search
    SOMA Summary  _fetch_soma_summary, _fetch_soma_latest_date
    SOMA Detail   _fetch_soma_tsy_holdings, _fetch_soma_tsy_holdingtype,
                  _fetch_soma_tsy_cusip, _fetch_soma_tsy_wam,
                  _fetch_soma_tsy_monthly, _fetch_soma_tsy_release_log,
                  _fetch_soma_agency_holdings, _fetch_soma_agency_holdingtype,
                  _fetch_soma_agency_cusip, _fetch_soma_agency_wam,
                  _fetch_soma_agency_release_log
    Repo          _fetch_repo_results, _fetch_rrp_results, _fetch_repo_search
    Primary Dlr   _fetch_pd_series_list, _fetch_pd_series, _fetch_pd_latest,
                  _fetch_pd_asof
    Tsy Ops       _fetch_tsy_ops, _fetch_tsy_ops_search
    AMBS Ops      _fetch_ambs_ops, _fetch_ambs_ops_search
    Sec Lending   _fetch_seclending_ops, _fetch_seclending_search
    FX Swaps      _fetch_fxswaps, _fetch_fxswaps_search

  Commands (24)   rates, sofr, effr, rate-history,
                  soma, soma-history,
                  soma-holdings, soma-agency, soma-cusip, soma-wam, soma-monthly,
                  tsy-ops, tsy-search,
                  ambs-ops,
                  seclending,
                  fxswaps,
                  repo, rrp,
                  pd-positions, pd-snapshot, series,
                  funding-snapshot, qt-monitor, operations-summary

  Interactive     24-item menu -> interactive wrappers with prompts
  Argparse        24 subcommands, all with --json and --export
```

### API Endpoints

```
RATES
/api/rates/all/latest.json
/api/rates/{secured|unsecured}/{type}/last/{N}.json
/api/rates/{secured|unsecured}/{type}/search.json?startDate=&endDate=

SOMA SUMMARY
/api/soma/summary.json
/api/soma/asofdates/latest.json
/api/soma/asofdates/list.json

SOMA TREASURY DETAIL
/api/soma/tsy/get/asof/{date}.json
/api/soma/tsy/get/{holdingtype}/asof/{date}.json
/api/soma/tsy/get/cusip/{cusip}.json
/api/soma/tsy/wam/{holdingtype}/asof/{date}.json
/api/soma/tsy/get/monthly.json
/api/soma/tsy/get/release_log.json

SOMA AGENCY DETAIL
/api/soma/agency/get/asof/{date}.json
/api/soma/agency/get/{holdingtype}/asof/{date}.json
/api/soma/agency/get/cusip/{cusip}.json
/api/soma/agency/wam/agency%20debts/asof/{date}.json
/api/soma/agency/get/release_log.json

TREASURY SECURITIES OPERATIONS
/api/tsy/{op}/results/{include}/last/{N}.json
/api/tsy/{op}/results/{include}/search.json?startDate=&endDate=
  op: all, purchases, sales
  include: summary, details

AGENCY MBS OPERATIONS
/api/ambs/{op}/results/{include}/last/{N}.json
/api/ambs/{op}/results/{include}/search.json?startDate=&endDate=
  op: all, purchases, sales, roll, swap
  include: summary, details

SECURITIES LENDING
/api/seclending/{op}/results/{include}/last/{N}.json
/api/seclending/{op}/results/{include}/search.json?startDate=&endDate=
  op: all, seclending, extensions
  include: summary, details

CENTRAL BANK LIQUIDITY SWAPS
/api/fxs/{type}/last/{N}.json
/api/fxs/{type}/search.json?startDate=&endDate=
  type: all, usdollar, nonusdollar

REPO / REVERSE REPO
/api/rp/repo/all/results/last/{N}.json
/api/rp/reverserepo/all/results/last/{N}.json
/api/rp/results/search.json?startDate=&endDate=

PRIMARY DEALER
/api/pd/list/timeseries.json
/api/pd/get/{keyid}.json
/api/pd/latest.json
/api/pd/get/asof/{date}.json
```
