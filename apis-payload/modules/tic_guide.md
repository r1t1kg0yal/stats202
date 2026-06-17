# Treasury International Capital (TIC)

Script: `projects/apis/tic/tic.py`
Source: `https://ticdata.treasury.gov`
Auth: None required
Rate limit: ~0.3s between calls (polite usage)
Dependencies: `requests`
Update frequency: Monthly (mid-month release, ~2 month lag)


## Triggers

Use for: foreign holdings of U.S. securities (Treasuries, agencies, corporates, equities), cross-border capital flows, country-level portfolio investment, official vs private foreign demand, Major Foreign Holders headline data, month-over-month top movers, country deep dives (China/Japan/UK/Caymans etc.), capital flight and repatriation signals, "who is buying/selling Treasuries."

Not for: domestic auction results/bid-to-cover (TreasuryDirect), overnight funding rates (NY Fed), yield curves (Treasury Fiscal Data), futures positioning (CFTC), OTC swap flows (DTCC), bank-level foreign claims (BIS LBS), real-time FX flows (TIC is monthly with ~2mo lag).


## Data Catalog

### Source Files

| Key | File | Content | Frequency | Units |
|-----|------|---------|-----------|-------|
| `mfh` | `slt_table5.txt` | Major Foreign Holders of Treasury Securities | Monthly | $B |
| `holdings` | `slt_table1.txt` | Foreign holdings of U.S. long-term securities by country, type, issuer | Monthly | $M |
| `us_holdings` | `slt_table2.txt` | U.S. holdings of foreign long-term securities by country, type | Monthly | $M |
| `tsy_holdings` | `slt_table3.txt` | Foreign holdings of U.S. Treasury securities (LT + ST) by country | Monthly | $M |
| `flows` | `slt_table4.txt` | Gross U.S. purchases and sales of long-term securities by type and country | Monthly | $M |
| `mfh_history` | `mfhhis01.txt` | Historical Major Foreign Holders (extended series) | Monthly | $B |

### MFH Fields (slt_table5 -- pivot format)

| Field | Type | Description |
|-------|------|-------------|
| Country | string | Country name (top ~20 + "All Other", "Grand Total") |
| {YYYY-MM} | float | Holdings at end of month, billions of dollars |
| Grand Total | float | Sum of all foreign holdings |
| Of Which: Foreign Official | float | Official institutions (central banks, SWFs) |

### Holdings Fields (slt_table1 -- long format)

| Field | Type | Description |
|-------|------|-------------|
| `country` | string | Country name |
| `country_code` | string | TIC country code (99996 = Grand Total) |
| `date` | string | YYYY-MM |
| `for_lt_total_pos` | float | Total U.S. LT securities held ($M) |
| `for_lt_total_net` | float | Net U.S. sales ($M, positive = foreign buying) |
| `for_lt_total_valchg` | float | Valuation change ($M) |
| `for_lt_treas_pos` | float | U.S. Treasuries held ($M) |
| `for_lt_treas_net` | float | Net Treasury sales ($M) |
| `for_lt_agcy_pos` | float | U.S. Agency bonds held ($M) |
| `for_lt_corp_pos` | float | U.S. Corporate bonds held ($M) |
| `for_lt_eqty_pos` | float | U.S. Corporate equities held ($M) |

### Treasury Holdings Fields (slt_table3 -- long format)

| Field | Type | Description |
|-------|------|-------------|
| `for_treas_pos` | float | Total Treasury securities held ($M) |
| `for_treas_net` | float | Net U.S. sales ($M) |
| `for_lt_treas_pos` | float | Long-term Treasuries held ($M) |
| `for_lt_treas_net` | float | Long-term net sales ($M) |
| `for_lt_treas_valchg` | float | LT valuation change ($M) |
| `for_st_treas_pos` | float | Short-term Treasuries held ($M) |
| `for_st_treas_net` | float | Short-term net sales ($M) |

### Flows Fields (slt_table4 -- long format)

| Field | Type | Description |
|-------|------|-------------|
| `for_lt_total_sale` | float | U.S. LT securities sold to foreigners ($M) |
| `for_lt_total_pur` | float | U.S. LT securities purchased from foreigners ($M) |
| `for_lt_treas_sale` | float | Treasury bonds sold ($M) |
| `for_lt_treas_pur` | float | Treasury bonds purchased ($M) |
| `for_lt_agcy_sale` | float | Agency bonds sold ($M) |
| `for_lt_agcy_pur` | float | Agency bonds purchased ($M) |
| `for_lt_corp_sale` | float | Corporate bonds sold ($M) |
| `for_lt_corp_pur` | float | Corporate bonds purchased ($M) |
| `for_lt_eqty_sale` | float | Equities sold ($M) |
| `for_lt_eqty_pur` | float | Equities purchased ($M) |
| `us_lt_total_sale` | float | Foreign securities sold by U.S. ($M) |
| `us_lt_total_pur` | float | Foreign securities purchased by U.S. ($M) |

### Key Country Codes

| Code | Entity |
|------|--------|
| 99996 | Grand Total (all countries) |
| 99990 | Of which: Foreign Official |
| 99991 | Of which: Foreign Non-Official |
| 79995 | Total International/Regional Organizations |

### Country Aliases

The script resolves common aliases to TIC canonical names:

| Alias | Resolves To |
|-------|-------------|
| `china`, `prc`, `china mainland` | China, Mainland |
| `uk`, `britain` | United Kingdom |
| `south korea`, `korea` | Korea, South |
| `uae` | United Arab Emirates |
| `hk`, `hong kong` | Hong Kong |
| `ksa`, `saudi` | Saudi Arabia |
| `cayman`, `caymans` | Cayman Islands |
| `taiwan` | Taiwan |
| `swiss`, `switzerland` | Switzerland |
| `lux` | Luxembourg |
| `sg` | Singapore |
| `norway` | Norway |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export.

### Major Foreign Holders

```bash
# Full MFH table -- all countries with monthly holdings in $B
python tic.py mfh
python tic.py mfh --json
python tic.py mfh --export csv

# Top N holders only
python tic.py mfh --top 5
python tic.py mfh --top 10
python tic.py mfh --top 10 --json
python tic.py mfh --top 20 --export json
```

### Foreign Holdings of U.S. Long-Term Securities

```bash
# Grand total (all countries) -- default 13 months
python tic.py holdings
python tic.py holdings --json
python tic.py holdings --months 24 --export csv

# By country (supports aliases)
python tic.py holdings --country Japan
python tic.py holdings --country Japan --months 24
python tic.py holdings --country Japan --months 24 --json
python tic.py holdings --country China --months 12 --json
python tic.py holdings --country china --months 12
python tic.py holdings --country uk --months 12
python tic.py holdings --country "United Kingdom" --months 6
python tic.py holdings --country "Cayman Islands" --months 24
python tic.py holdings --country caymans --months 12 --json
python tic.py holdings --country Taiwan --months 12
python tic.py holdings --country saudi --months 12 --json
python tic.py holdings --country Luxembourg --months 24 --export csv
```

### Foreign Holdings of U.S. Treasuries

```bash
# Grand total -- Treasury-specific detail with LT/ST split
python tic.py tsy-holdings
python tic.py tsy-holdings --json
python tic.py tsy-holdings --months 24 --export csv

# By country
python tic.py tsy-holdings --country Japan --months 24
python tic.py tsy-holdings --country Japan --months 24 --json
python tic.py tsy-holdings --country China --json
python tic.py tsy-holdings --country china --months 12
python tic.py tsy-holdings --country saudi --months 12
python tic.py tsy-holdings --country uk --months 6 --json
python tic.py tsy-holdings --country "Cayman Islands" --months 24 --json
python tic.py tsy-holdings --country Taiwan --months 12 --export csv
```

### Gross Cross-Border Flows

```bash
# Grand total -- purchase/sale volumes for US and foreign securities
python tic.py flows
python tic.py flows --json
python tic.py flows --months 24 --export csv

# By country
python tic.py flows --country Japan --months 12
python tic.py flows --country Japan --months 24 --json
python tic.py flows --country China --json
python tic.py flows --country china --months 12
python tic.py flows --country uk --months 6 --json
python tic.py flows --country "Cayman Islands" --months 12
python tic.py flows --country Luxembourg --months 24 --json
```

### Top Movers (MoM Changes)

```bash
# Top 15 biggest month-over-month changes in Treasury holdings (default)
python tic.py top-changes
python tic.py top-changes --json
python tic.py top-changes --export csv

# Top N movers
python tic.py top-changes --top 5
python tic.py top-changes --top 10 --json
python tic.py top-changes --top 20
python tic.py top-changes --top 25 --export json
```

### Country Profile

```bash
# Combined view: MFH + holdings + Treasury detail + flows for one country
python tic.py country Japan
python tic.py country Japan --json
python tic.py country Japan --months 24
python tic.py country Japan --months 24 --json
python tic.py country China --months 12
python tic.py country China --months 24 --json
python tic.py country "United Kingdom" --json
python tic.py country uk --months 6
python tic.py country saudi --json
python tic.py country "Cayman Islands" --months 24
python tic.py country Taiwan --months 12 --json
python tic.py country Luxembourg --months 24 --export csv
python tic.py country Singapore --json
python tic.py country Norway --months 12 --json
```

### Dashboard

```bash
# Full snapshot: MFH top 10, grand total, official/private split, composition, top movers
python tic.py snapshot
python tic.py snapshot --json
python tic.py snapshot --export csv
python tic.py snapshot --export json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to CSV file | All commands |
| `--export json` | Export to JSON file | All commands |
| `--top N` | Limit to top N entries | mfh, top-changes |
| `--country NAME` | Filter by country (supports aliases) | holdings, tsy-holdings, flows |
| `--months N` | Number of months of history (default 13) | holdings, tsy-holdings, flows, country |
| `name` | Country name (positional arg) | country |


## Python Recipes

### Major Foreign Holders

```python
from tic import cmd_mfh, cmd_top_changes

# Full MFH table
# Returns (as_json=True): list of {country, date, holdings_billions}
# Returns (as_json=False): list of {country, holdings: {date: value_bn}}
mfh = cmd_mfh(as_json=True)

# Top N holders only
mfh_top = cmd_mfh(top=10, as_json=True)
mfh_top5 = cmd_mfh(top=5, as_json=True)

# Export to file
cmd_mfh(top=20, export_fmt="csv")
cmd_mfh(export_fmt="json")

# Top movers -- biggest MoM changes
# Returns: list of {country, latest, prior, change, pct_change}
movers = cmd_top_changes(n=15, as_json=True)
movers = cmd_top_changes(n=10, as_json=True)
movers = cmd_top_changes(n=25, as_json=True)
```

### Foreign Holdings by Country

```python
from tic import cmd_holdings, cmd_tsy_holdings

# Japan's holdings of all US LT securities (last 24 months)
# Returns: list of dicts with country, country_code, date,
#   for_lt_total_pos, for_lt_treas_pos, for_lt_agcy_pos,
#   for_lt_corp_pos, for_lt_eqty_pos, and net/valchg fields
japan = cmd_holdings(country="Japan", months=24, as_json=True)
china = cmd_holdings(country="China", months=12, as_json=True)
uk = cmd_holdings(country="uk", months=12, as_json=True)
cayman = cmd_holdings(country="caymans", months=24, as_json=True)

# Grand total (all countries) -- omit country param
total = cmd_holdings(months=13, as_json=True)
total_2yr = cmd_holdings(months=24, as_json=True)

# China's Treasury holdings specifically (includes LT/ST split)
# Returns: list of dicts with for_treas_pos, for_treas_net,
#   for_lt_treas_pos, for_lt_treas_net, for_st_treas_pos, for_st_treas_net
china_tsy = cmd_tsy_holdings(country="China", months=12, as_json=True)
japan_tsy = cmd_tsy_holdings(country="Japan", months=24, as_json=True)
saudi_tsy = cmd_tsy_holdings(country="saudi", months=12, as_json=True)

# Grand total Treasury holdings
total_tsy = cmd_tsy_holdings(months=13, as_json=True)
```

### Cross-Border Flows

```python
from tic import cmd_flows

# Japan gross flows
# Returns: list of dicts with for_lt_total_sale, for_lt_total_pur,
#   for_lt_treas_sale, for_lt_treas_pur, for_lt_agcy_sale, for_lt_corp_sale,
#   for_lt_eqty_sale, us_lt_total_sale, us_lt_total_pur
japan_flows = cmd_flows(country="Japan", months=12, as_json=True)
china_flows = cmd_flows(country="China", months=24, as_json=True)

# Global flows
global_flows = cmd_flows(months=13, as_json=True)
global_flows_2yr = cmd_flows(months=24, as_json=True)
```

### Country Profile

```python
from tic import cmd_country

# Combined view: MFH + holdings + Treasury detail + flows
# Returns: {country, mfh: {country, holdings: {...}},
#   holdings: [...], tsy_holdings: [...], flows: [...]}
japan_profile = cmd_country("Japan", months=12, as_json=True)
china_profile = cmd_country("China", months=24, as_json=True)
uk_profile = cmd_country("uk", months=12, as_json=True)
cayman_profile = cmd_country("Cayman Islands", months=24, as_json=True)
```

### Snapshot Dashboard

```python
from tic import cmd_snapshot

# Dashboard data: MFH top holders, grand total, official/private split
# Returns: {mfh_latest: [{country, holdings_bn}], grand_total_bn,
#   foreign_official_bn, latest_date}
snap = cmd_snapshot(as_json=True)
```

### Internal Helpers

```python
from tic import _resolve_country, _filter_country, _filter_grand_total
from tic import _download, _parse_mfh, _parse_long_table
from tic import TIC_FILES, COUNTRY_ALIASES

# Resolve alias to canonical name
_resolve_country("china")       # -> "China, Mainland"
_resolve_country("uk")          # -> "United Kingdom"
_resolve_country("ksa")         # -> "Saudi Arabia"
_resolve_country("caymans")     # -> "Cayman Islands"

# Download raw TIC file
raw = _download(TIC_FILES["mfh"])           # slt_table5.txt
raw = _download(TIC_FILES["holdings"])      # slt_table1.txt
raw = _download(TIC_FILES["tsy_holdings"])  # slt_table3.txt
raw = _download(TIC_FILES["flows"])         # slt_table4.txt

# Parse into structured data
rows, dates = _parse_mfh(raw)               # pivot: [{country, holdings: {date: val}}]
rows, cols = _parse_long_table(raw)         # long: [{country, country_code, date, ...fields}]

# Filter helpers
japan_rows = _filter_country(rows, "Japan")
total_rows = _filter_grand_total(rows)
```


## Composite Recipes

### Foreign Demand Assessment

```bash
python tic.py mfh --json
python tic.py top-changes --json
```

PRISM receives: full MFH table with current holdings for all countries, month-over-month changes sorted by magnitude showing which countries are accumulating or reducing Treasury exposure, net buying/selling counts.

### Country Deep Dive

```bash
python tic.py country China --months 24 --json
python tic.py tsy-holdings --country China --months 24 --json
python tic.py flows --country China --months 24 --json
```

PRISM receives: 2 years of China's total holdings (Treasuries + agencies + corporates + equities), Treasury-specific detail with LT/ST split and net sales, and gross flow data showing actual purchase/sale volumes.

### Official vs Private Foreign Demand

```bash
python tic.py mfh --json
python tic.py snapshot --json
```

PRISM receives: total foreign official vs foreign private holdings of Treasuries with percentages, composition breakdown (Treasuries vs agencies vs corporates vs equities), top 10 holders with MoM changes, biggest movers.

### Asia Treasury Demand Monitor

```bash
python tic.py country Japan --months 12 --json
python tic.py country China --months 12 --json
python tic.py country Taiwan --months 12 --json
python tic.py country "Korea, South" --months 12 --json
python tic.py country Singapore --months 12 --json
```

PRISM receives: individual Asian holder profiles with MFH + holdings + Treasury detail + flows for each country.

### Offshore Center Monitor

```bash
python tic.py country "Cayman Islands" --months 24 --json
python tic.py country Luxembourg --months 24 --json
python tic.py country "United Kingdom" --months 24 --json
python tic.py country "Hong Kong" --months 24 --json
```

PRISM receives: holdings trajectories for major offshore/custodial centers where beneficial ownership differs from reported holder.

### Capital Flight / Repatriation Signals

```bash
python tic.py flows --months 12 --json
python tic.py holdings --months 12 --json
python tic.py top-changes --json
```

PRISM receives: gross cross-border flow volumes (sales vs purchases), total foreign position in U.S. securities, and concentration of changes.

### Composition Shift Tracker

```bash
python tic.py holdings --months 24 --json
python tic.py tsy-holdings --months 24 --json
```

PRISM receives: 2 years of total foreign holdings with Treasuries/agencies/corporates/equities breakdown, plus Treasury-specific LT vs ST split. Shows whether foreigners are rotating between asset types.


## Cross-Source Recipes

### TIC + Auction Demand

```bash
python tic.py mfh --json
python tic.py top-changes --json
python projects/apis/treasurydirect/treasurydirect.py api auctions --days 30
```

PRISM receives: foreign holdings trajectory + recent auction metrics. Shows whether foreign demand at auctions aligns with TIC holdings trends.

### TIC + Overnight Funding

```bash
python tic.py snapshot --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: foreign holdings and flows + current rate complex and RRP usage.

### TIC + Fed Balance Sheet

```bash
python tic.py mfh --json
python projects/apis/nyfed/nyfed.py soma --json
python projects/apis/nyfed/nyfed.py qt-monitor --weeks 26 --json
```

PRISM receives: foreign official + private Treasury demand alongside Fed SOMA runoff. Key for the marginal buyer question: as Fed unwinds, who absorbs?

### TIC + BIS Cross-Border Banking

```bash
python tic.py holdings --json
python projects/apis/bis/bis.py lbs --reporter US --position L --start 2015
```

PRISM receives: portfolio investment flows (TIC) + banking claims/liabilities (BIS LBS). Full cross-border financial picture -- securities vs banking channels.

### TIC + CFTC Positioning

```bash
python tic.py top-changes --json
python projects/apis/cftc/cftc.py rates --json
python projects/apis/cftc/cftc.py fx --json
```

PRISM receives: actual foreign holdings changes + speculative futures positioning in rates and FX. Cross-references physical demand with derivatives bets.

### TIC + Treasury Supply

```bash
python tic.py mfh --json
python projects/apis/treasury/treasury.py get debt_to_penny --json
python projects/apis/treasury/treasury.py get mspd_table_1 --json
```

PRISM receives: foreign demand (TIC) + outstanding debt and composition (Fiscal Data). Demand vs supply framing.

### TIC + Prediction Markets

```bash
python tic.py top-changes --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: foreign Treasury demand shifts + market-implied rate path probabilities. Links flow data to policy expectations.

### TIC + DTCC Swap Flows

```bash
python tic.py flows --country Japan --months 6 --json
python projects/apis/dtcc/dtcc.py latest irs --json
```

PRISM receives: Japan's gross cross-border securities flows + OIS swap volumes. Shows whether hedging activity accompanies physical investment flows.

### TIC + GDELT Narrative

```bash
python tic.py top-changes --json
python projects/apis/gdelt/gdelt.py narrative --theme treasury --timespan 1months --json
python projects/apis/gdelt/gdelt.py doc-search --query '"foreign holdings" OR "China selling Treasuries"' --timespan 1months --json
```

PRISM receives: actual TIC data + media narrative around foreign Treasury demand. Calibrates media narrative vs actual flow data.


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python tic.py mfh --top 5`
4. Full test: `python tic.py snapshot`


## Architecture

```
tic.py
  Constants       BASE_URL, TIC_FILES (6 data files), COUNTRY_ALIASES (16 aliases),
                  SESSION, REQUEST_DELAY
  HTTP            _download() with retries, rate limit handling
  Parsers         _parse_mfh (pivot table -> [{country, holdings: {date: val}}]),
                  _parse_long_table (long-form -> [{country, country_code, date, ...fields}])
  Filters         _filter_country (fuzzy + alias resolution),
                  _filter_grand_total (code 99996)
  Commands (7)    mfh, holdings, tsy-holdings, flows, top-changes, country, snapshot
  Interactive     7-item menu -> interactive wrappers with prompts
  Argparse        7 subcommands, all with --json and --export
```

Data source:
```
https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/
  slt_table5.txt     MFH pivot -- Country rows, date columns ($B)
  slt_table1.txt     Long-form -- foreign holdings of US LT secs by country ($M)
  slt_table2.txt     Long-form -- US holdings of foreign LT secs by country ($M)
  slt_table3.txt     Long-form -- foreign holdings of US Treasuries by country ($M)
  slt_table4.txt     Long-form -- gross purchases/sales by type and country ($M)
  mfhhis01.txt       Extended historical MFH series ($B)
```

Units:
- MFH (table 5, mfhhis01): billions of dollars
- All other tables (1-4): millions of dollars
- Dates: YYYY-MM format
- Net sales: positive = foreigners buying / increasing position
