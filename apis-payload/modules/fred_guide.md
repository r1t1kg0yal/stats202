# FRED (Federal Reserve Economic Data)

Script: `projects/apis/fred/fred.py`
Base URL: `https://api.stlouisfed.org/fred`
Auth: `FRED_API_KEY` env var (free at https://fred.stlouisfed.org/docs/api/api_key.html)
Rate limit: ~1.0s between calls
Dependencies: None (stdlib only -- urllib)


## Triggers

Use for: GDP, unemployment, payrolls, CPI, PCE, inflation expectations, Treasury yields, yield curve, Fed funds rate, credit spreads, money supply, Fed balance sheet, housing starts, consumer credit, trade balance, financial conditions, VIX, S&P 500, recession indicators, Sahm rule, any US macro time series.

Not for: intraday/tick data (no real-time), OTC swap volumes (DTCC), futures positioning (CFTC), cross-border banking (BIS), bank-level financials (FDIC), auction results (TreasuryDirect), overnight rate percentiles/volume (NY Fed), energy inventories (EIA), event probabilities (prediction markets), non-US country-specific data (BIS/OECD better).


## Curated Series Catalog

### Output & Growth

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| GDPC1 | Real GDP | Q | Bil. 2017$, SAAR |
| A191RL1Q225SBEA | Real GDP Growth Rate | Q | %, annualized |
| GDPPOT | Real Potential GDP | Q | Bil. 2017$ |
| GDPNOW | Atlanta Fed GDPNow | D | % |
| INDPRO | Industrial Production Index | M | Index 2017=100 |
| CPIAI | Capacity Utilization | M | % |
| RSAFS | Retail Sales (ex food svc) | M | Mil.$ |

### Labor Market

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| PAYEMS | Total Nonfarm Payrolls | M | Thousands |
| UNRATE | Unemployment Rate | M | % |
| U6RATE | U-6 Unemployment Rate | M | % |
| ICSA | Initial Jobless Claims | W | Number |
| CCSA | Continued Claims | W | Number |
| CES0500000003 | Avg Hourly Earnings (Private) | M | $/hr |
| JTSJOL | JOLTS Job Openings | M | Thousands |
| JTSQUR | JOLTS Quits Rate | M | % |
| CIVPART | Labor Force Participation Rate | M | % |
| EMRATIO | Employment-Population Ratio | M | % |
| AWHNONAG | Avg Weekly Hours (Nonfarm) | M | Hours |

### Prices & Inflation

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| CPIAUCSL | CPI All Items | M | Index 1982-84=100 |
| CPILFESL | Core CPI (ex Food & Energy) | M | Index 1982-84=100 |
| PCEPILFE | Core PCE Price Index | M | Index 2017=100 |
| PCEPI | PCE Price Index | M | Index 2017=100 |
| MEDCPIM158SFRBCLE | Median CPI (Cleveland Fed) | M | % chg |
| PPIFIS | PPI Final Demand | M | Index 2009=100 |
| T5YIE | 5Y Breakeven Inflation | D | % |
| T10YIE | 10Y Breakeven Inflation | D | % |
| T5YIFR | 5Y5Y Forward Inflation Exp. | D | % |
| MICH | UMich Inflation Expectations (1Y) | M | % |

### Interest Rates & Yields

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| FEDFUNDS | Effective Federal Funds Rate | M | % |
| DFEDTARU | Fed Funds Target Upper | D | % |
| DFEDTARL | Fed Funds Target Lower | D | % |
| DGS1MO | 1-Month Treasury Yield | D | % |
| DGS3MO | 3-Month Treasury Yield | D | % |
| DGS6MO | 6-Month Treasury Yield | D | % |
| DGS1 | 1-Year Treasury Yield | D | % |
| DGS2 | 2-Year Treasury Yield | D | % |
| DGS5 | 5-Year Treasury Yield | D | % |
| DGS7 | 7-Year Treasury Yield | D | % |
| DGS10 | 10-Year Treasury Yield | D | % |
| DGS20 | 20-Year Treasury Yield | D | % |
| DGS30 | 30-Year Treasury Yield | D | % |
| T10Y2Y | 10Y-2Y Treasury Spread | D | % |
| T10Y3M | 10Y-3M Treasury Spread | D | % |
| BAMLH0A0HYM2 | ICE BofA HY OAS | D | % |
| BAMLC0A0CM | ICE BofA IG OAS | D | % |
| MORTGAGE30US | 30-Year Mortgage Rate | W | % |
| TEDRATE | TED Spread | D | % |

### Monetary Policy & Money Supply

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| WALCL | Fed Total Assets | W | Mil.$ |
| RRPONTSYD | ON RRP Outstanding | D | Bil.$ |
| WTREGEN | Treasury General Account (TGA) | W | Mil.$ |
| TOTRESNS | Total Reserves | M | Bil.$ |
| BOGMBASE | Monetary Base | M | Bil.$ |
| M2SL | M2 Money Stock | M | Bil.$ |
| M1SL | M1 Money Stock | M | Bil.$ |
| MULT | M1 Money Multiplier | M | Ratio |

### Financial Conditions & Stress

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| NFCI | Chicago Fed NFCI | W | Index |
| ANFCI | Adjusted NFCI | W | Index |
| STLFSI4 | St. Louis Fed Financial Stress | W | Index |
| VIXCLS | CBOE VIX | D | Index |
| DTWEXBGS | Trade-Weighted USD (Broad) | D | Index |
| DCOILWTICO | WTI Crude Oil | D | $/barrel |
| GOLDAMGBD228NLBM | Gold Price (London Fix) | D | $/oz |
| SP500 | S&P 500 | D | Index |
| WILL5000INDFC | Wilshire 5000 Total Market | D | Index |

### Housing

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| HOUST | Housing Starts | M | Thousands, SAAR |
| PERMIT | Building Permits | M | Thousands, SAAR |
| CSUSHPINSA | Case-Shiller National HPI | M | Index Jan2000=100 |
| MSPUS | Median Home Sale Price | Q | $ |
| EXHOSLUSM495S | Existing Home Sales | M | Mil., SAAR |
| NHSLTOT | New Home Sales | M | Thousands, SAAR |
| RHORUSQ156N | Homeownership Rate | Q | % |

### Consumer & Bank Credit

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| TOTALSL | Total Consumer Credit | M | Bil.$ |
| REVOLSL | Revolving Consumer Credit | M | Bil.$ |
| DRALACBS | Delinquency Rate (All Loans) | Q | % |
| DRSFRMACBS | Delinquency Rate (Residential RE) | Q | % |
| BUSLOANS | C&I Loans (All Banks) | M | Bil.$ |
| DRTSCILM | Sr. Loan Officer Survey: Tightening | Q | % net |

### Trade & External

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| BOPGSTB | Trade Balance (Goods & Services) | M | Mil.$ |
| BOPGTB | Trade Balance (Goods Only) | M | Mil.$ |
| DEXUSEU | USD/EUR Exchange Rate | D | $/EUR |
| DEXJPUS | JPY/USD Exchange Rate | D | JPY/$ |
| DEXUSUK | USD/GBP Exchange Rate | D | $/GBP |
| DEXCHUS | CNY/USD Exchange Rate | D | CNY/$ |

### Government & Fiscal

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| GFDEBTN | Federal Debt Total Public | Q | Mil.$ |
| GFDEGDQ188S | Federal Debt as % of GDP | Q | % |
| MTSDS133FMS | Federal Surplus/Deficit | M | Mil.$ |
| FYFSD | Federal Surplus/Deficit (FY) | A | Mil.$ |
| A091RC1Q027SBEA | Federal Gov Current Expenditures | Q | Bil.$, SAAR |

### Recession Indicators

| Series ID | Name | Freq | Units |
|-----------|------|------|-------|
| SAHMREALTIME | Sahm Rule Recession Indicator | M | pp |
| RECPROUSM156N | Smoothed US Recession Probs | M | % |
| T10Y3M | 10Y-3M Spread (yield curve) | D | % |
| USSLIND | Leading Index | M | Index 2016=100 |
| UMCSENT | UMich Consumer Sentiment | M | Index |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export.

### Search & Discovery

```bash
# Search for series by keyword
python fred.py search "unemployment rate"
python fred.py search "inflation expectations" --limit 20
python fred.py search "credit spread" --json

# Show curated catalog (all themes)
python fred.py catalog
python fred.py catalog --theme rates
python fred.py catalog --theme inflation --json

# Series metadata
python fred.py metadata GDPC1
python fred.py metadata UNRATE --json
```

### Data Retrieval

```bash
# Single series (full history)
python fred.py get UNRATE
python fred.py get GDPC1 --start 2020-01-01
python fred.py get DGS10 --last 60

# Multiple series (separate outputs)
python fred.py get GDPC1,UNRATE,CPIAUCSL

# Multiple series (combined wide format)
python fred.py get GDPC1,UNRATE,PAYEMS --combine
python fred.py get DGS2,DGS10,DGS30 --combine --start 2023-01-01

# JSON output for programmatic consumption
python fred.py get UNRATE --json
python fred.py get GDPC1,PAYEMS --combine --json

# Export to file
python fred.py get CPIAUCSL --export csv
python fred.py get DGS2,DGS5,DGS10,DGS30 --combine --export csv
```

### Comparison

```bash
# Side-by-side latest values
python fred.py compare GDPC1 PAYEMS UNRATE CPIAUCSL
python fred.py compare DGS2 DGS10 DGS30 T10Y2Y
python fred.py compare FEDFUNDS DGS2 DGS10 BAMLH0A0HYM2 --json
```

### Releases & Navigation

```bash
# Recent release calendar
python fred.py releases
python fred.py releases --limit 50 --json

# Specific release detail (53 = GDP)
python fred.py release 53
python fred.py release 50     # Employment Situation
python fred.py release 10     # CPI
python fred.py release 21     # H.15 Interest Rates

# Browse category tree
python fred.py categories 0           # root
python fred.py categories 32991       # Money, Banking, & Finance
python fred.py categories 115         # National Accounts > GDP
```

### Dashboards

```bash
# Full macro snapshot (20 key indicators)
python fred.py macro-snapshot
python fred.py macro-snapshot --json
python fred.py macro-snapshot --export csv
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to CSV file | All commands |
| `--export json` | Export to JSON file | All commands |
| `--start YYYY-MM-DD` | Observation start date | get |
| `--end YYYY-MM-DD` | Observation end date | get |
| `--last N` | Last N observations only | get |
| `--combine` | Wide format for multi-series | get |
| `--limit N` | Max results | search, releases |
| `--theme NAME` | Filter catalog by theme | catalog |


## Python Recipes

### Data Retrieval

```python
from fred import cmd_get, cmd_compare, cmd_search, cmd_macro_snapshot

# Single series observations
data = cmd_get("UNRATE", start="2020-01-01", as_json=True)
# Returns: {"UNRATE": [{"date": "2020-01-01", "value": "3.6"}, ...]}

# Multiple series combined
data = cmd_get("GDPC1,PAYEMS,UNRATE", combine=True, as_json=True)

# Side-by-side comparison
comp = cmd_compare(["GDPC1", "PAYEMS", "UNRATE", "CPIAUCSL"], as_json=True)
# Returns: [{"series_id": "GDPC1", "name": "Real GDP", "date": ..., "value": ..., "change": ...}, ...]

# Full macro snapshot (20 indicators)
snap = cmd_macro_snapshot(as_json=True)
```

### Discovery

```python
from fred import cmd_search, cmd_catalog, cmd_metadata

# Search FRED
results = cmd_search("inflation expectations", limit=20, as_json=True)
# Returns: list of series dicts with id, title, frequency, units, popularity

# Curated catalog
cat = cmd_catalog(theme="rates", as_json=True)
# Returns: {theme: {label, series: [{id, name, freq, units}]}}

# Series metadata
meta = cmd_metadata("GDPC1", as_json=True)
# Returns: {id, title, frequency, units, seasonal_adjustment, observation_start, ...}
```

### Navigation

```python
from fred import cmd_releases, cmd_release, cmd_categories

# Recent releases
dates = cmd_releases(limit=30, as_json=True)

# Release detail with all series
rel = cmd_release(53, as_json=True)  # GDP release
# Returns: {"release": {name, link, ...}, "series": [{id, title, freq}, ...]}

# Category browsing
cats = cmd_categories(category_id=0, as_json=True)  # root
# Returns: {"category": {...}, "children": [{id, name}, ...]}
```


## Composite Recipes

### Morning Macro Check

```bash
python fred.py compare FEDFUNDS DGS2 DGS10 T10Y2Y BAMLH0A0HYM2 VIXCLS SP500 --json
```

PRISM receives: policy rate, front-end yield, long-end yield, curve slope, credit spreads, vol, equities. Single-call macro pulse.

### Recession Probability Assessment

```bash
python fred.py compare SAHMREALTIME RECPROUSM156N T10Y3M USSLIND UMCSENT ICSA --json
```

PRISM receives: Sahm rule trigger distance, smoothed recession probability, yield curve signal, leading index, consumer sentiment, claims trend.

### Inflation Decomposition

```bash
python fred.py get CPIAUCSL,CPILFESL,PCEPILFE,PCEPI,MEDCPIM158SFRBCLE --combine --start 2022-01-01 --json
python fred.py compare T5YIE T10YIE T5YIFR MICH --json
```

PRISM receives: headline vs core CPI vs PCE time series for decomposition, plus market-implied breakevens and survey expectations.

### Yield Curve Snapshot

```bash
python fred.py get DGS1MO,DGS3MO,DGS6MO,DGS1,DGS2,DGS5,DGS7,DGS10,DGS20,DGS30 --combine --last 5 --json
```

PRISM receives: full Treasury curve (10 points) last 5 days. Enough to plot current curve and recent shifts.

### Financial Conditions Dashboard

```bash
python fred.py compare NFCI ANFCI STLFSI4 VIXCLS BAMLH0A0HYM2 BAMLC0A0CM DTWEXBGS --json
```

PRISM receives: NFCI, adjusted NFCI, STL stress, VIX, HY OAS, IG OAS, dollar index. Complete financial conditions picture.

### Labor Market Deep Dive

```bash
python fred.py get PAYEMS,UNRATE,U6RATE,ICSA,CCSA,JTSJOL,JTSQUR,CIVPART,EMRATIO --combine --start 2023-01-01 --json
```

PRISM receives: payrolls, U-3, U-6, claims, JOLTS openings/quits, LFPR, E-pop ratio. Full labor market decomposition.

### Monetary Plumbing

```bash
python fred.py compare WALCL RRPONTSYD WTREGEN TOTRESNS M2SL BOGMBASE --json
```

PRISM receives: Fed balance sheet, ON RRP, TGA, reserves, M2, monetary base. Liquidity pipeline snapshot.


## Cross-Source Recipes

### FRED + NY Fed Funding

```bash
python fred.py compare FEDFUNDS DGS2 DGS10 T10Y2Y --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: FRED policy/term rates + NY Fed overnight rate complex with percentile distributions and RRP usage.

### FRED + CFTC Positioning

```bash
python fred.py get DGS2,DGS10,T10Y2Y --combine --last 30 --json
python projects/apis/cftc/cftc.py rates --json
```

PRISM receives: Treasury yield history + speculative positioning in rates futures. Yields vs bets.

### FRED + DTCC Swap Volumes

```bash
python fred.py compare FEDFUNDS DGS2 DGS10 BAMLH0A0HYM2 --json
python projects/apis/dtcc/dtcc.py rates --json
```

PRISM receives: benchmark rates + OIS/IRS swap flow data. Activity corroboration.

### FRED + BIS International Credit

```bash
python fred.py get TOTALSL,BUSLOANS,DRALACBS --combine --json
python projects/apis/bis/bis.py credit Q.US --start 2020 --json
```

PRISM receives: US consumer/bank credit from FRED + BIS total credit-to-GDP for international comparison.

### FRED + Treasury Fiscal Data

```bash
python fred.py compare GFDEBTN GFDEGDQ188S MTSDS133FMS --json
python projects/apis/treasury/treasury.py get dts --json
```

PRISM receives: FRED fiscal aggregates + Treasury Daily Treasury Statement for cash flow detail.


## Key Release IDs

| Release ID | Name | Key Series |
|------------|------|------------|
| 53 | Gross Domestic Product | GDPC1, A191RL1Q225SBEA |
| 50 | Employment Situation | PAYEMS, UNRATE |
| 10 | Consumer Price Index | CPIAUCSL, CPILFESL |
| 21 | H.15 Selected Interest Rates | DGS2, DGS10, FEDFUNDS |
| 46 | Personal Income and Outlays | PCEPI, PCEPILFE |
| 205 | JOLTS | JTSJOL, JTSQUR |
| 20 | H.4.1 Factors Affecting Reserve Balances | WALCL |
| 13 | G.17 Industrial Production and Capacity | INDPRO, CPIAI |
| 95 | Advance Monthly Sales for Retail and Food | RSAFS |
| 86 | Housing Starts | HOUST |
| 11 | New Residential Sales | NHSLTOT |
| 52 | Financial Accounts of the US (Z.1) | Flow of Funds |
| 22 | H.6 Money Stock Measures | M2SL |


## Setup

1. Get free API key: https://fred.stlouisfed.org/docs/api/api_key.html
2. `export FRED_API_KEY=your_key_here`
3. Test: `python fred.py catalog`
4. Full test: `python fred.py compare GDPC1 UNRATE CPIAUCSL DGS10`


## Architecture

```
fred.py
  Catalog        11 themes, ~110 curated series with metadata
  HTTP           _fetch_json() with rate limiting, retries (stdlib urllib)
  Data Fetchers  _fetch_observations, _fetch_series_meta, _fetch_search,
                 _fetch_releases, _fetch_release, _fetch_release_series,
                 _fetch_release_dates, _fetch_category, _fetch_category_children,
                 _fetch_category_series
  Commands (9)   search, get, compare, catalog, releases, release,
                 categories, metadata, macro-snapshot
  Interactive    9-item menu -> interactive wrappers with prompts
  Argparse       9 subcommands, all with --json and --export
```

API endpoints used:
```
fred/series/search          -> search by keyword
fred/series/observations    -> time series data
fred/series                 -> series metadata
fred/releases               -> all releases
fred/releases/dates         -> release calendar
fred/release                -> single release metadata
fred/release/series         -> series in a release
fred/category               -> category info
fred/category/children      -> child categories
fred/category/series        -> series in a category
```

## Extending the Catalog

To add new series, edit the `CATALOG` dict in `fred.py`. Each theme maps to a list of `(series_id, name, freq, units)` tuples. New themes can be added as new keys. Series added to the catalog automatically appear in:
- `catalog` command output
- `macro-snapshot` (if also added to `MACRO_SNAPSHOT_SERIES`)
- `compare` and `search` output annotations (marked with *)
