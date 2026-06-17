# OFR -- Office of Financial Research

Script: `projects/apis/ofr/ofr.py`
Base URLs: `https://data.financialresearch.gov/v1` (STFM), `https://data.financialresearch.gov/hf/v1` (HFM)
Bonus: `https://www.financialresearch.gov/financial-stress-index/data/fsi.csv` (FSI)
Auth: None required
Rate limit: undocumented (polite ~0.15s spacing in client)
Dependencies: `requests`


## Triggers

Use for: short-term funding markets (Tri-Party / GCF / DVP repo rates and volumes), money market fund composition (Treasury / agency / repo / Fed RP usage), Treasury constant maturity yields and curve dynamics, NY Fed reference rates with full percentile distribution and underlying volume, primary dealer securities lending / borrowing / fails, hedge fund leverage and balance sheet (SEC Form PF aggregates by strategy and stress tests), CFTC Traders in Financial Futures positioning across rates / FX / equities, Senior Credit Officer Opinion Survey (SCOOS) on dealer financing terms to hedge funds, FICC sponsored repo volumes, and the OFR Financial Stress Index (33-variable daily global stress index with credit / equity-valuation / funding / safe-asset / volatility components and US / Other-AE / EM region decompositions).

Not for: real-time NY Fed repo / RRP operations or primary dealer outright net positions (use `nyfed.py`), Treasury auction details (use `treasurydirect.py`), DTCC swap volumes (use `dtcc.py`), CFTC Commitments of Traders for commodities (use `cftc.py`), bank-level financials (use `fdic.py`).


## API Surface Coverage

Three OFR data products in one client:

| API | Base URL | Datasets |
|-----|----------|----------|
| STFM | `data.financialresearch.gov/v1` | `fnyr`, `mmf`, `nypd`, `repo`, `tyld` |
| HFM  | `data.financialresearch.gov/hf/v1` | `fpf`, `tff`, `scoos`, `ficc` |
| FSI  | `financialresearch.gov/.../fsi.csv` | OFR Financial Stress Index (33 vars) |

Both STFM and HFM expose the same generic endpoints:

| Endpoint | Description |
|----------|-------------|
| `/metadata/mnemonics` | List all series identifiers (mnemonics) |
| `/metadata/query` | Get metadata for a mnemonic |
| `/metadata/search` | Search across mnemonics with `*`/`?` wildcards |
| `/series/timeseries` | Single-series time series |
| `/series/full` | Single-series time series + full metadata |
| `/series/multifull` | Multiple series in one call |
| `/series/dataset` | All series in a dataset |
| `/calc/spread` | Spread (X - Y) between two series |

The `categories` endpoint on HFM (`/categories?category=size`) is documented but currently broken (returns 500). The script does not use it.


## Datasets and Mnemonic Counts

| API | Key | Long Name | Frequency | Mnemonics |
|-----|-----|-----------|-----------|-----------|
| STFM | `fnyr` | NY Fed Reference Rates (SOFR/EFFR/OBFR/TGCR/BGCR + percentiles + UV) | Daily | 36 |
| STFM | `mmf` | OFR U.S. Money Market Fund Data Release | Monthly | 42 |
| STFM | `nypd` | NY Fed Primary Dealer Statistics (RP/RRP/SB/SL/Fails) | Weekly | 194 |
| STFM | `repo` | OFR U.S. Repo Markets Data Release (Tri-Party + GCF + DVP) | Daily | 164 |
| STFM | `tyld` | Treasury Constant Maturity Rates (1Mo--30Yr) | Daily | 12 |
| HFM  | `fpf` | Hedge Fund Aggregates from SEC Form PF | Quarterly | 329 |
| HFM  | `tff` | CFTC Traders in Financial Futures | Weekly | 153 |
| HFM  | `scoos` | Senior Credit Officer Opinion Survey on Dealer Financing | Quarterly | 13 |
| HFM  | `ficc` | FICC Sponsored Repo Service Volumes | Daily | 2 |

Total: ~945 mnemonics across 9 datasets, plus the FSI (~10 daily series in one CSV).


## Mnemonic Naming Convention

OFR mnemonics follow `<DATASET>-<NAME>[-<VINTAGE>]` where vintage is one of:

| Suffix | Meaning |
|--------|---------|
| `-A` | Single vintage (no preliminary/final distinction) |
| `-P` | Preliminary (latest, may be revised) |
| `-F` | Final (revised, ~1-month lag from preliminary) |

For repo: prefer `-P` for currency, `-F` for clean historical analysis.

### REPO mnemonic anatomy

`REPO-{SEGMENT}_{METRIC}_{TERM}-{VINTAGE}` plus collateral-typed variants `REPO-{SEGMENT}_{METRIC}_{COLLATERAL}-{VINTAGE}`.

| Component | Values | Notes |
|-----------|--------|-------|
| SEGMENT | `TRI`, `TRIV1`, `GCF`, `DVP` | TRIV1 = Tri-Party excluding Fed transactions |
| METRIC | `AR`, `OV`, `TV` | Avg Rate / Outstanding Vol / Transaction Vol |
| TERM | `OO`, `LE30`, `G30`, `TOT` | Overnight/Open / <=30 days / >30 days / Total |
| COLLATERAL | `T`, `AG`, `CORD`, `O` | Treasury / Agency / Corp Debt / Other |

Tri-Party only publishes `AR` and `TV` (no `OV`); DVP and GCF publish all three.

### NYPD mnemonic anatomy

`NYPD-PD_{ACTIVITY}_{COLLATERAL}_{TERM}-A` where ACTIVITY ∈ {`RP`, `RRP`, `SB`, `SL`, `AFtD`, `AFtR`}. Note: the broader `NYPD-PD_RP_TOT-A` and `NYPD-PD_RRP_TOT-A` aggregates stopped reporting in late 2021. Active series are SB / SL by collateral and AFtD / AFtR fails.


## Curated Catalogs in the Client

| Constant | Purpose |
|----------|---------|
| `FNYR_RATES` | 5 reference rates (SOFR/EFFR/OBFR/TGCR/BGCR) each with rate / percentiles / volume mnemonics |
| `TCMR_TENORS` | 12 Treasury constant maturity tenors (1Mo to 30Yr) |
| `REPO_OVERNIGHT_RATES` | 4 segments overnight rate mnemonics (TRIV1/TRI/GCF/DVP) |
| `REPO_TRANSACTION_VOLUMES` | 4 daily transaction volume mnemonics (TRIV1/TRI/GCF/DVP) |
| `REPO_OUTSTANDING_VOLUMES` | DVP + GCF outstanding (Tri-Party doesn't publish OV) |
| `MMF_COMPOSITION` | 14 MMF holdings categories |
| `NYPD_FINANCING` | 7 active SB / SL series by collateral |
| `NYPD_FAILS` | 12 fails-to-deliver / fails-to-receive series |
| `FPF_TOTALS` | 5 hedge fund aggregate balance-sheet items |
| `FPF_STRATEGIES` | 9 strategies (Credit / Equity / Event / FOF / Futures / Macro / Multi / Other / RV) |
| `FPF_STRESS_TESTS` | 6 stress scenarios (credit / FX / equity ±) at P5 and P50 |
| `TFF_GROUPS` | AI / LF / DI / OR (Asset Managers / Leveraged Funds / Dealers / Other Reportables) |
| `TFF_CONTRACTS` | 23 futures contracts (Treasury, Fed Funds, SOFR, equities, FX, VIX, Bitcoin) |
| `FICC_SERIES` | Sponsored Repo + Sponsored Reverse Repo |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export.

### Generic API access

```bash
python ofr.py datasets                                # list all 9 datasets + FSI
python ofr.py mnemonics --dataset repo                # 164 repo mnemonics
python ofr.py mnemonics --dataset fpf --query GAV     # filter mnemonics
python ofr.py search "Outstanding*"                   # 258 matches with wildcard
python ofr.py query FNYR-SOFR-A                       # series metadata
python ofr.py series FNYR-SOFR-A --start 2025-01-01
python ofr.py series REPO-GCF_AR_OO-P --periodicity W --how mean
python ofr.py multi FNYR-SOFR-A FNYR-EFFR-A REPO-GCF_AR_OO-P --start 2025-01-01
python ofr.py spread REPO-GCF_AR_OO-P FNYR-SOFR-A --start 2025-01-01
python ofr.py dataset-pull tyld --start 2024-01-01    # full Treasury yield curve
python ofr.py dataset-pull repo --start 2026-01-01 --periodicity W --how mean
```

### Reference rates (FNYR)

```bash
python ofr.py fnyr                                    # all 5 rates with percentiles + volume
python ofr.py fnyr --obs 60                           # 60-day history
python ofr.py fnyr --json                             # structured output
```

### Repo markets

```bash
python ofr.py repo-rates                              # Tri-Party + GCF + DVP overnight
python ofr.py repo-rates --obs 60                     # 60-day history
python ofr.py repo-volumes                            # daily TV across segments + OV (DVP/GCF)
python ofr.py repo-history --segment GCF --term OO --metric AR
python ofr.py repo-history --segment DVP --term TOT --metric OV --obs 90
python ofr.py repo-history --segment TRIV1 --term TOT --metric TV --vintage F
```

### Money market funds

```bash
python ofr.py mmf                                     # latest composition snapshot
python ofr.py mmf-history                             # 24-month history
python ofr.py mmf-history --obs 48                    # 4-year history
```

### Treasury yield curve

```bash
python ofr.py yields                                  # full curve latest + slope diagnostics
python ofr.py curve                                   # curve with 1d / 1w / 1m / 1y deltas
```

### Primary dealers

```bash
python ofr.py pd-financing                            # SB / SL activity by collateral
python ofr.py pd-fails                                # FtD / FtR by asset class
```

### Hedge funds (Form PF)

```bash
python ofr.py form-pf                                 # GAV / NAV / borrowing aggregates
python ofr.py form-pf-strategy                        # by-strategy decomposition
python ofr.py form-pf-stress                          # stress test results P5 / P50
```

### CFTC TFF

```bash
python ofr.py tff                                     # Leveraged Funds (default)
python ofr.py tff --group AI                          # Asset Managers
python ofr.py tff --group DI                          # Dealers
python ofr.py tff --group OR                          # Other Reportables
```

### SCOOS / FICC

```bash
python ofr.py scoos                                   # latest dealer survey
python ofr.py scoos --obs 12                          # 12-quarter history
python ofr.py ficc                                    # sponsored repo volumes
python ofr.py ficc --obs 60                           # 5-year history
```

### Financial Stress Index

```bash
python ofr.py fsi                                     # latest with components + regions
python ofr.py fsi-history --days 365                  # 1-year time series
python ofr.py fsi-history --days 60 --json
```

### Dashboards

```bash
python ofr.py funding-snapshot                        # rates + repo + MMF
python ofr.py stress-snapshot                         # FSI + curve + funding
python ofr.py hf-snapshot                             # cross-source hedge fund view
```

### Common flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | Structured JSON output | All commands |
| `--export csv` | Save to CSV file | All commands |
| `--export json` | Save to JSON file | All commands |
| `--obs N` | Number of recent observations | fnyr / repo-* / mmf-history / pd-* / form-pf / scoos / ficc |
| `--days N` | Number of days | fsi-history |
| `--start YYYY-MM-DD` | Start date | series / multi / spread / dataset-pull |
| `--end YYYY-MM-DD` | End date | series / multi / spread / dataset-pull |
| `--periodicity` | Resample (A/Q/M/W/D/B) | series / multi / spread / dataset-pull |
| `--how` | Aggregation (first/last/mean/median/sum) | series / spread / dataset-pull |
| `--remove-nulls` | Drop null values | series |
| `--dataset` | Restrict to one dataset | mnemonics / dataset-pull |
| `--query` | Filter substring | mnemonics |
| `--limit` | Max rows displayed | mnemonics / search |
| `--segment` | Repo segment (TRI/TRIV1/GCF/DVP) | repo-history |
| `--term` | Repo term (OO/LE30/G30/TOT) | repo-history |
| `--metric` | Repo metric (AR/OV/TV) | repo-history |
| `--vintage` | Vintage (P/F) | repo-history / dataset-pull |
| `--group` | TFF reporter group (AI/LF/DI/OR) | tff |


## Python Recipes

```python
from ofr import (
    cmd_datasets, cmd_mnemonics, cmd_search, cmd_query, cmd_series,
    cmd_multi, cmd_spread, cmd_dataset_pull,
    cmd_fnyr, cmd_repo_rates, cmd_repo_volumes, cmd_repo_history,
    cmd_mmf, cmd_mmf_history, cmd_yields, cmd_curve,
    cmd_pd_financing, cmd_pd_fails,
    cmd_form_pf, cmd_form_pf_strategy, cmd_form_pf_stress,
    cmd_tff, cmd_scoos, cmd_ficc,
    cmd_fsi, cmd_fsi_history,
    cmd_funding_snapshot, cmd_stress_snapshot, cmd_hf_snapshot,
)

# Reference rates
rates = cmd_fnyr(obs=60, as_json=True)

# Repo markets
repo_rates = cmd_repo_rates(obs=30, as_json=True)
repo_vols = cmd_repo_volumes(obs=30, as_json=True)
gcf_history = cmd_repo_history(segment="GCF", term="OO", metric="AR", obs=90,
                                as_json=True)

# MMF
mmf_now = cmd_mmf(as_json=True)
mmf_ts = cmd_mmf_history(obs=48, as_json=True)

# Treasury
yields = cmd_yields(as_json=True)
curve = cmd_curve(as_json=True)

# Primary dealers
sb_sl = cmd_pd_financing(obs=24, as_json=True)
fails = cmd_pd_fails(obs=24, as_json=True)

# Hedge funds
fpf = cmd_form_pf(obs=12, as_json=True)
strategies = cmd_form_pf_strategy(as_json=True)
stress = cmd_form_pf_stress(as_json=True)
tff_lf = cmd_tff(group="LF", as_json=True)
scoos = cmd_scoos(obs=8, as_json=True)
ficc = cmd_ficc(obs=24, as_json=True)

# Stress
fsi = cmd_fsi(as_json=True)
fsi_ts = cmd_fsi_history(days=365, as_json=True)

# Dashboards
funding = cmd_funding_snapshot(as_json=True)
stress_snap = cmd_stress_snapshot(as_json=True)
hf_snap = cmd_hf_snapshot(as_json=True)

# Low-level
datasets = cmd_datasets(as_json=True)
mnemonics = cmd_mnemonics(dataset="repo", as_json=True)
hits = cmd_search("Outstanding*", as_json=True)
metadata = cmd_query("FNYR-SOFR-A", as_json=True)
sofr_history = cmd_series("FNYR-SOFR-A", start_date="2024-01-01", as_json=True)
multi = cmd_multi(["FNYR-SOFR-A", "FNYR-EFFR-A"], start_date="2025-01-01",
                  as_json=True)
spread = cmd_spread("REPO-GCF_AR_OO-P", "FNYR-SOFR-A",
                    start_date="2024-01-01", as_json=True)
full_yld = cmd_dataset_pull("tyld", start_date="2025-01-01", as_json=True)
```


## Composite Recipes

### Morning funding pulse

```bash
python ofr.py funding-snapshot --json
```

### Repo market deep dive

```bash
python ofr.py repo-rates --obs 60 --json
python ofr.py repo-volumes --obs 60 --json
python ofr.py repo-history --segment DVP --term TOT --metric OV --obs 90 --json
python ofr.py repo-history --segment GCF --term OO --metric AR --obs 90 --json
python ofr.py spread REPO-GCF_AR_OO-P REPO-TRIV1_AR_OO-P --start $(date -v-3m +%Y-%m-%d) --json
python ofr.py spread REPO-DVP_AR_OO-P FNYR-SOFR-A --start $(date -v-3m +%Y-%m-%d) --json
```

### Money fund regime check

```bash
python ofr.py mmf --json
python ofr.py mmf-history --obs 36 --json
python ofr.py spread MMF-MMF_RP_T_TOT-M MMF-MMF_RP_AG_TOT-M --start 2023-01-01 --json
```

### Yield curve & rates complex

```bash
python ofr.py yields --json
python ofr.py curve --json
python ofr.py spread TYLD-TCMR-10Yr-A TYLD-TCMR-2Yr-A --start 2020-01-01 --json
python ofr.py spread TYLD-TCMR-10Yr-A TYLD-TCMR-3Mo-A --start 2020-01-01 --json
```

### Stress diagnostic

```bash
python ofr.py stress-snapshot --json
python ofr.py fsi-history --days 365 --json
python ofr.py funding-snapshot --json
```

### Hedge fund cross-check

```bash
python ofr.py hf-snapshot --json
python ofr.py form-pf --json
python ofr.py form-pf-strategy --json
python ofr.py form-pf-stress --json
python ofr.py tff --group LF --json
python ofr.py tff --group AI --json
python ofr.py scoos --obs 8 --json
python ofr.py ficc --obs 24 --json
```

### Dealer balance sheet stress

```bash
python ofr.py pd-financing --obs 24 --json
python ofr.py pd-fails --obs 24 --json
```

### Quarter-end / FOMC / Tax-day window

```bash
python ofr.py fnyr --obs 30 --json
python ofr.py repo-rates --obs 30 --json
python ofr.py repo-volumes --obs 30 --json
python ofr.py spread REPO-GCF_AR_OO-P FNYR-SOFR-A --start YYYY-MM-DD --end YYYY-MM-DD --json
```


## Cross-Source Recipes

### Funding stress: OFR + NY Fed operations

```bash
python ofr.py funding-snapshot --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

### Repo regime: rates + volumes + Fed operations

```bash
python ofr.py repo-rates --json
python ofr.py repo-volumes --json
python projects/apis/nyfed/nyfed.py rrp --count 10 --json
python projects/apis/dtcc/dtcc.py rates --json
```

### Hedge fund leverage cross-check (OFR + CFTC + DTCC)

```bash
python ofr.py hf-snapshot --json
python projects/apis/cftc/cftc.py macro-scan --json
python projects/apis/dtcc/dtcc.py rates --json
```

### Stress regime + macro narrative

```bash
python ofr.py stress-snapshot --json
python projects/apis/fred/fred.py macro-snapshot --json
python projects/apis/cftc/cftc.py crowding --years 3 --json
```

### Treasury curve consistency check (OFR vs FRED)

```bash
python ofr.py yields --json
python projects/apis/fred/fred.py compare DGS3MO DGS2 DGS10 DGS30
```

### Form PF + SCOOS leverage signal + FICC sponsored

```bash
python ofr.py form-pf-strategy --json
python ofr.py scoos --json
python ofr.py ficc --obs 24 --json
```


## Setup

1. No API key required.
2. `pip install requests`
3. Test: `python ofr.py datasets`
4. Full dashboard: `python ofr.py funding-snapshot`


## Architecture

```
ofr.py (29 commands, ~3200 lines)
  Constants
    STFM_BASE, HFM_BASE, FSI_CSV_URL
    STFM_DATASETS (5), HFM_DATASETS (4), ALL_DATASETS
    FNYR_RATES (5 rate types x 6 mnemonics each)
    TCMR_TENORS (12 yield curve tenors)
    REPO_SEGMENTS / TERMS / METRICS, REPO_OVERNIGHT_RATES,
      REPO_TRANSACTION_VOLUMES, REPO_OUTSTANDING_VOLUMES
    MMF_COMPOSITION (14 categories)
    NYPD_FINANCING (7), NYPD_FAILS (12)
    FPF_TOTALS, FPF_STRATEGIES (9), FPF_STRESS_TESTS (6)
    TFF_GROUPS (4), TFF_CONTRACTS (23)
    FICC_SERIES (2)

  HTTP            _request() with retry / 429 backoff / quiet flag
  Routing         _api_base / _api_base_for_mnemonic auto-routes STFM vs HFM

  Low-level       fetch_mnemonics, fetch_search, fetch_query,
                  fetch_timeseries, fetch_full, fetch_multifull,
                  fetch_dataset, fetch_spread, fetch_fsi_csv

  Generic cmds    datasets, mnemonics, search, query, series, multi,
                  spread, dataset-pull

  Curated cmds    fnyr, repo-rates, repo-volumes, repo-history,
                  mmf, mmf-history,
                  yields, curve,
                  pd-financing, pd-fails,
                  form-pf, form-pf-strategy, form-pf-stress,
                  tff, scoos, ficc,
                  fsi, fsi-history

  Dashboards      funding-snapshot, stress-snapshot, hf-snapshot

  Interactive     29-item menu -> interactive wrappers with prompts
  Argparse        29 subcommands, all with --json and --export
```

### Notes & Caveats

- **Repo mnemonics**: Tri-Party only publishes `AR` (rate) and `TV` (transaction volume); `OV` (outstanding) only available for DVP and GCF.
- **NYPD repo aggregates stale**: `NYPD-PD_RP_TOT-A` and `NYPD-PD_RRP_TOT-A` stopped publishing in late 2021. The `pd-financing` command focuses on the still-active SB/SL series. For real-time repo/RRP operations data, use `nyfed.py`.
- **Form PF strategy borrowing**: FOF and FUTURES strategies don't publish `BORROWING_SUM`. The script handles this by pulling borrowing series individually with quiet error handling.
- **HFM `categories` endpoint** is documented but currently broken on the live API (returns 500). Not implemented.
- **FSI source**: Pulled directly as CSV from `financialresearch.gov/financial-stress-index/data/fsi.csv` (not via the JSON API).
- **Quarterly data lag**: Form PF aggregates have a meaningful publication lag (typically published ~6 months after quarter end). Latest available may be 2 quarters behind.
- **Search wildcards**: `*` matches multiple chars, `?` matches one. Searching without a wildcard returns 0 -- always include `*` for substring matching.
