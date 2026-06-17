# SEC EDGAR

Script: `projects/apis/sec_edgar/edgar_scraper.py`
Data API: `https://data.sec.gov`
Search API: `https://efts.sec.gov/LATEST/search-index`
Archives: `https://www.sec.gov/Archives/edgar/data`
Auth: User-Agent header only (no API key)
Rate limit: 10 req/sec
Dependencies: `requests`


## Triggers

Use for: company financials (XBRL structured data, 30+ metrics), filing history/download (10-K/10-Q/8-K/S-1/DEF 14A), full-text boolean search across 20M+ filings, cross-company financial screening (frames), company profiles, insider transactions (Form 4), institutional holdings (13F-HR), 10-K section extraction (risk factors/MD&A/business), peer comparison, sector screening.

Not for: banking system data (FDIC Call Reports), real-time market data (Bloomberg/GS), economic indicators (FRED/Haver), event probabilities (Kalshi/Polymarket), government fiscal data (Treasury Fiscal Data), non-US companies without SEC filings, private companies, OTC derivative volumes (DTCC), futures positioning (CFTC).


## Data Catalog

### Key Identifiers

| ID | Format | Example |
|----|--------|---------|
| CIK | 10-digit zero-padded | Apple=0000320193, NVDA=0001045810 |
| Ticker | Exchange symbol | Maps to CIK via company_tickers.json (~10,000 tickers) |
| SIC | 4-digit industry code | 7372=Software, 3674=Semiconductors, 6022=Banks |
| Accession | {filer}-{yy}-{seq} | 0000320193-24-000123. URL component for filing docs |

### Endpoints

| Endpoint | Returns |
|----------|---------|
| `data.sec.gov/submissions/CIK{cik}.json` | Profile metadata + up to 1000 filings |
| `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` | All XBRL facts (1-10MB, hundreds of line items) |
| `data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{tax}/{concept}.json` | One concept across all filings |
| `data.sec.gov/api/xbrl/frames/{tax}/{concept}/{unit}/{period}.json` | One concept for all filers (~2,000-6,000 companies) |
| `efts.sec.gov/LATEST/search-index` | Full-text hits + SIC/state/entity facets |
| `sec.gov/files/company_tickers.json` | Bulk ticker-to-CIK mapping |
| `sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}` | Raw filing document (HTML/TXT) |

### XBRL Income Statement Concepts

| Label | XBRL Tag | Unit |
|-------|----------|------|
| Revenue | `Revenues` | USD |
| CostOfRevenue | `CostOfRevenue` | USD |
| GrossProfit | `GrossProfit` | USD |
| ResearchAndDevelopment | `ResearchAndDevelopmentExpense` | USD |
| OperatingExpenses | `OperatingExpenses` | USD |
| OperatingIncome | `OperatingIncomeLoss` | USD |
| NetIncome | `NetIncomeLoss` | USD |
| EPS_Basic | `EarningsPerShareBasic` | USD/shares |
| EPS_Diluted | `EarningsPerShareDiluted` | USD/shares |

### XBRL Balance Sheet Concepts

| Label | XBRL Tag | Unit |
|-------|----------|------|
| TotalAssets | `Assets` | USD |
| CashAndEquivalents | `CashAndCashEquivalentsAtCarryingValue` | USD |
| ShortTermInvestments | `ShortTermInvestments` | USD |
| AccountsReceivable | `AccountsReceivableNetCurrent` | USD |
| Inventory | `InventoryNet` | USD |
| PropertyPlantEquipment | `PropertyPlantAndEquipmentNet` | USD |
| Goodwill | `Goodwill` | USD |
| IntangibleAssets | `IntangibleAssetsNetExcludingGoodwill` | USD |
| TotalLiabilities | `Liabilities` | USD |
| CurrentLiabilities | `LiabilitiesCurrent` | USD |
| LongTermDebt | `LongTermDebt` | USD |
| StockholdersEquity | `StockholdersEquity` | USD |
| CommonSharesOutstanding | `CommonStockSharesOutstanding` | shares |

### XBRL Cash Flow Concepts

| Label | XBRL Tag | Unit |
|-------|----------|------|
| OperatingCashFlow | `NetCashProvidedByOperatingActivities` | USD |
| CapitalExpenditure | `PaymentsToAcquirePropertyPlantAndEquipment` | USD |
| Depreciation | `DepreciationDepletionAndAmortization` | USD |
| DividendsPaid | `PaymentsOfDividends` | USD |
| ShareRepurchases | `PaymentsForRepurchaseOfCommonStock` | USD |

### Auto-Computed Derived Ratios

| Ratio | Formula |
|-------|---------|
| Gross Margin % | Gross Profit / Revenue |
| Operating Margin % | Operating Income / Revenue |
| Net Margin % | Net Income / Revenue |
| R&D Intensity % | R&D Expense / Revenue |
| ROA % | Net Income / Total Assets |
| ROE % | Net Income / Stockholders' Equity |
| Debt/Equity | Long-Term Debt / Stockholders' Equity |
| Debt/Assets % | Long-Term Debt / Total Assets |
| Net Debt | Long-Term Debt - Cash |
| Revenue Growth YoY % | (Current Rev - Prior Rev) / Prior Rev |
| Net Income Growth YoY % | (Current NI - Prior NI) / Prior NI |

### Financial Presets

| Preset | Concepts |
|--------|----------|
| `default` | All 30+ metrics (income + balance sheet + cash flow) |
| `income` | Revenue through NetIncome + EPS |
| `balance_sheet` | Assets, liabilities, equity, debt |
| `cash_flow` | Operating CF, capex, depreciation, dividends, buybacks |

### XBRL Period Format

| Format | Meaning | Use For |
|--------|---------|---------|
| `CY2024` | Calendar year 2024 (annual) | Income statement, cash flow |
| `CY2024Q1` | Q1 2024 (quarterly) | Income statement, cash flow |
| `CY2024Q1I` | Instantaneous Q1 2024 | Balance sheet items (point-in-time) |

### Filing Types Reference

| Form | Frequency | Use Case |
|------|-----------|----------|
| 10-K | Annual | Full financials, risk factors, MD&A |
| 10-Q | 3x/year | Quarterly updates, interim financials |
| 8-K | Event-driven | Material events, earnings releases, M&A |
| DEF 14A | Annual | Executive compensation, governance |
| S-1 | One-time | IPO registration |
| 13F-HR | Quarterly | Institutional holdings |
| 4 | Event-driven | Insider transactions |
| SC 13D | Event-driven | Activist investor positions (>5%) |
| 20-F | Annual | Foreign company annual report |

### 10-K Section Extraction

| Section Key | Item | Content |
|-------------|------|---------|
| `risk_factors` | Item 1A | Risk disclosures, forward-looking uncertainties |
| `mda` | Item 7 | Management's Discussion and Analysis |
| `business` | Item 1 | Business description, products, markets |
| `quantitative_disclosures` | Item 7A | Market risk disclosures (rates, FX) |
| `financial_statements` | Item 8 | Financial statements and supplementary data |
| `legal_proceedings` | Item 3 | Pending litigation and legal matters |

### Full-Text Search Syntax

| Syntax | Example |
|--------|---------|
| Exact phrase | `"material weakness"` |
| Boolean AND | `"artificial intelligence" AND revenue` |
| Boolean OR | `tariff OR "trade war"` |
| Wildcard | `cybersecur*` |

### SIC Code Reference

| SIC | Industry |
|-----|----------|
| 3674 | Semiconductors |
| 7372 | Prepackaged Software |
| 7374 | Computer Processing |
| 2834 | Pharmaceuticals |
| 6021/6022 | Commercial Banks |
| 6282 | Investment Advice |
| 6798 | Real Estate Investment Trusts |
| 5961 | Catalog & Mail-Order Houses |
| 4911 | Electric Services |
| 1311 | Crude Petroleum & Natural Gas |

### Data Output Patterns

All saves go to `data/` adjacent to script, timestamped filenames.

| Command | Pattern |
|---------|---------|
| profile | `profile_{TICKER}_{ts}.json` |
| filings | `filings_{TICKER}_{ts}.json` |
| download | `{TICKER}_{FORM}_{date}.txt` |
| financials | `financials_{TICKER}_{ts}.json` |
| concept/screen | `frames_{concept}_{period}_{ts}.json` |
| search | `search_{query}_{ts}.json` |
| recent | `recent_{form}_{ts}.json` |
| deep-dive | `deep_dive_{TICKER}_{ts}.json` + section `.txt` files |
| peer-compare | `peer_compare_{TICKERS}_{ts}.json` |
| insider | `insider_{TICKER}_{ts}.json` |
| holdings | `institutional_{TICKER}_{ts}.json` |
| bulk | `bulk_pull_{ts}.json` |
| risk-factors | `{TICKER}_risk_factors_{date}.txt` |


## CLI Recipes

All commands support `--save` for JSON/text file persistence to `data/`.

### Company Lookup & Profile

```bash
# Resolve ticker/name/CIK to company matches
python edgar_scraper.py lookup AAPL
python edgar_scraper.py lookup NVDA
python edgar_scraper.py lookup 320193
python edgar_scraper.py lookup "Apple"
python edgar_scraper.py lookup "Goldman"

# Full company profile: SIC, addresses, exchanges, former names, last 10 filings
python edgar_scraper.py profile AAPL
python edgar_scraper.py profile MSFT --save
python edgar_scraper.py profile NVDA --save
python edgar_scraper.py profile 320193 --save
```

### Filing History & Download

```bash
# All filings (up to 1000)
python edgar_scraper.py filings AAPL
python edgar_scraper.py filings MSFT --save

# Filter by form type
python edgar_scraper.py filings AAPL --forms 10-K
python edgar_scraper.py filings AAPL --forms 10-K,10-Q
python edgar_scraper.py filings TSLA --forms 8-K --max 20
python edgar_scraper.py filings NVDA --forms 10-K,10-Q,8-K --max 50 --save
python edgar_scraper.py filings GOOG --forms DEF\ 14A --max 5
python edgar_scraper.py filings AAPL --forms S-1 --max 5
python edgar_scraper.py filings AAPL --forms 4 --max 30

# Download full filing text (HTML stripped to plain text)
python edgar_scraper.py download AAPL --form 10-K --count 1
python edgar_scraper.py download NVDA --form 10-K --count 3
python edgar_scraper.py download TSLA --form 10-Q --count 4
python edgar_scraper.py download GOOG --form 8-K --count 10
python edgar_scraper.py download META --form 10-K --count 1 --no-save

# Browse documents within a specific filing
python edgar_scraper.py browse AAPL
python edgar_scraper.py browse NVDA --accession 0001045810-25-000012
```

### XBRL Financials

```bash
# All 30+ metrics (default preset) + derived ratios
python edgar_scraper.py financials AAPL
python edgar_scraper.py financials NVDA --save
python edgar_scraper.py financials MSFT --save

# Income statement only
python edgar_scraper.py financials AAPL --preset income
python edgar_scraper.py financials GOOG --preset income --save

# Balance sheet only
python edgar_scraper.py financials AAPL --preset balance_sheet
python edgar_scraper.py financials TSLA --preset balance_sheet --save

# Cash flow only
python edgar_scraper.py financials AAPL --preset cash_flow
python edgar_scraper.py financials META --preset cash_flow --save

# By CIK
python edgar_scraper.py financials 320193 --preset default --save
```

### Cross-Company Screening

```bash
# Single concept across all filers for a period
python edgar_scraper.py concept Revenue --period CY2024
python edgar_scraper.py concept Revenue --period CY2024 --save
python edgar_scraper.py concept NetIncome --period CY2024
python edgar_scraper.py concept Assets --period CY2024Q4I
python edgar_scraper.py concept LongTermDebt --period CY2024Q4I --save
python edgar_scraper.py concept CashAndCashEquivalentsAtCarryingValue --period CY2024Q4I
python edgar_scraper.py concept EarningsPerShareDiluted --period CY2024
python edgar_scraper.py concept Revenues --period CY2024Q1

# Screen with preset concept keys
python edgar_scraper.py screen Revenue --period CY2024
python edgar_scraper.py screen Revenue --period CY2024 --save
python edgar_scraper.py screen NetIncome --period CY2024
python edgar_scraper.py screen TotalAssets --period CY2024Q4I
python edgar_scraper.py screen LongTermDebt --period CY2024Q4I --save
python edgar_scraper.py screen OperatingIncome --period CY2023
python edgar_scraper.py screen GrossProfit --period CY2024 --save

# Custom XBRL concept name
python edgar_scraper.py screen ResearchAndDevelopmentExpense --period CY2024
python edgar_scraper.py concept OperatingIncomeLoss --period CY2024Q2
```

### Full-Text Search

```bash
# Exact phrase search
python edgar_scraper.py search '"material weakness"' --forms 10-K --save
python edgar_scraper.py search '"going concern"' --forms 10-K,10-Q --save
python edgar_scraper.py search '"goodwill impairment"' --forms 10-K

# Boolean operators
python edgar_scraper.py search '"artificial intelligence" AND "revenue growth"' --forms 10-K
python edgar_scraper.py search '"credit agreement" AND "covenant"' --forms 10-K --save
python edgar_scraper.py search '"revolving credit" AND "amendment"' --forms 8-K
python edgar_scraper.py search 'tariff OR "trade war"' --forms 10-K,10-Q

# Wildcard
python edgar_scraper.py search "cybersecur*" --forms 8-K --max 100
python edgar_scraper.py search "cryptocur*" --forms 10-K --save

# Date-filtered search
python edgar_scraper.py search "tariff risk" --forms 10-K --start 2024-01-01 --end 2025-12-31
python edgar_scraper.py search '"supply chain"' --forms 10-K --start 2025-01-01 --save
python edgar_scraper.py search '"interest rate risk"' --forms 10-K,10-Q --start 2024-06-01 --end 2025-06-01

# Max results
python edgar_scraper.py search '"material weakness"' --forms 10-K --max 200 --save
python edgar_scraper.py search "bankruptcy" --forms 8-K --max 50 --start 2025-01-01
```

### Recent Filings

```bash
# Latest filings by form type
python edgar_scraper.py recent --form 10-K --days 7
python edgar_scraper.py recent --form 10-K --days 14 --save
python edgar_scraper.py recent --form 10-Q --days 7
python edgar_scraper.py recent --form 8-K --days 3
python edgar_scraper.py recent --form 8-K --days 1 --save
python edgar_scraper.py recent --form S-1 --days 30
python edgar_scraper.py recent --form 13F-HR --days 30 --save
python edgar_scraper.py recent --form 4 --days 7
python edgar_scraper.py recent --form "SC 13D" --days 30
```

### Deep Dive & Peer Comparison

```bash
# Full deep dive: profile + financials + ratios + 10-K section extraction
python edgar_scraper.py deep-dive AAPL
python edgar_scraper.py deep-dive NVDA
python edgar_scraper.py deep-dive TSLA
python edgar_scraper.py deep-dive MSFT --no-save

# Side-by-side financial comparison
python edgar_scraper.py peer-compare AAPL,MSFT,GOOG,META
python edgar_scraper.py peer-compare AAPL,MSFT,GOOG,META --save
python edgar_scraper.py peer-compare NVDA,AMD,INTC,AVGO,QCOM --save
python edgar_scraper.py peer-compare JPM,BAC,GS,MS,C
python edgar_scraper.py peer-compare XOM,CVX,COP,EOG
python edgar_scraper.py peer-compare LLY,JNJ,PFE,MRK,ABBV --save
```

### Risk Factors

```bash
# Extract risk factors section from latest 10-K
python edgar_scraper.py risk-factors AAPL
python edgar_scraper.py risk-factors TSLA
python edgar_scraper.py risk-factors NVDA
python edgar_scraper.py risk-factors META --no-save
```

### Insider & Institutional

```bash
# Form 4 insider transactions
python edgar_scraper.py insider AAPL --days 90
python edgar_scraper.py insider AAPL --days 180 --save
python edgar_scraper.py insider NVDA --days 30
python edgar_scraper.py insider TSLA --days 365 --save

# 13F-HR institutional holdings search
python edgar_scraper.py holdings AAPL
python edgar_scraper.py holdings NVDA --save
python edgar_scraper.py holdings TSLA --save
python edgar_scraper.py holdings MSFT
```

### Earnings Season

```bash
# Recent 10-K and 10-Q filing monitor
python edgar_scraper.py earnings-season --days 7
python edgar_scraper.py earnings-season --days 14
python edgar_scraper.py earnings-season --days 30 --save
```

### Bulk Operations

```bash
# Pull profiles + financials + filings for multiple tickers
python edgar_scraper.py bulk AAPL,MSFT,GOOG,AMZN,NVDA,TSLA --forms 10-K
python edgar_scraper.py bulk AAPL,MSFT,GOOG,META --forms 10-K,10-Q
python edgar_scraper.py bulk JPM,BAC,GS,MS,C --forms 10-K --max-each 5
python edgar_scraper.py bulk NVDA,AMD,INTC,AVGO,QCOM --forms 10-K,8-K --max-each 20

# Skip financials (filings only)
python edgar_scraper.py bulk AAPL,MSFT,GOOG --forms 10-K --no-financials

# Skip filings (financials only)
python edgar_scraper.py bulk AAPL,MSFT,GOOG --no-filings

# Minimal pull
python edgar_scraper.py bulk AAPL,MSFT --forms 10-K --max-each 3 --no-financials
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--save` | Save output to timestamped JSON/text in `data/` | profile, filings, financials, concept, search, recent, peer-compare, insider, holdings, screen, earnings-season |
| `--no-save` | Suppress auto-save | download, deep-dive, risk-factors |
| `--forms FORMS` | Comma-separated form type filter | filings, search |
| `--form FORM` | Single form type | download, recent |
| `--max N` | Max results/filings | filings, search |
| `--count N` | Number of filings to download | download |
| `--preset PRESET` | Financial data preset (default/income/balance_sheet/cash_flow) | financials |
| `--period PERIOD` | XBRL period (CY2024, CY2024Q1, CY2024Q1I) | concept, screen |
| `--start DATE` | Start date (YYYY-MM-DD) | search |
| `--end DATE` | End date (YYYY-MM-DD) | search |
| `--days N` | Look-back window in days | recent, insider, earnings-season |
| `--max-each N` | Max filings per company in bulk | bulk |
| `--no-financials` | Skip XBRL pull in bulk | bulk |
| `--no-filings` | Skip filing list in bulk | bulk |
| `--accession ACC` | Specific filing accession number | browse |


## Python Recipes

### Company Lookup & Profile

```python
from edgar_scraper import cmd_company_lookup, cmd_company_profile

# Resolve ticker/name/CIK to matches
# Returns: list of {cik, ticker, title}
matches = cmd_company_lookup(query="AAPL")
matches = cmd_company_lookup(query="Goldman")
matches = cmd_company_lookup(query="320193")

# Full company profile
# Returns: dict with cik, name, sic, sicDescription, exchanges, addresses, formerNames
profile = cmd_company_profile(ticker="AAPL", save=False)
profile = cmd_company_profile(ticker="MSFT", save=True)
```

### Filing History & Download

```python
from edgar_scraper import cmd_filing_history, cmd_filing_download, cmd_browse_filing_index

# Filing history with optional form filter and max
# Returns: {company, submissions, filings}
result = cmd_filing_history(ticker="AAPL", form_filter=None, max_filings=None, save=False)
result = cmd_filing_history(ticker="AAPL", form_filter="10-K", max_filings=10, save=True)
result = cmd_filing_history(ticker="NVDA", form_filter="10-K,10-Q,8-K", max_filings=50, save=True)

# Download full filing text (HTML stripped)
# Returns: list of {filing, file, chars, words}
downloaded = cmd_filing_download(ticker="AAPL", form_type="10-K", count=1, save=True)
downloaded = cmd_filing_download(ticker="NVDA", form_type="10-K", count=3, save=True)
downloaded = cmd_filing_download(ticker="TSLA", form_type="8-K", count=10, save=False)

# Browse filing index
# Returns: {company, accession, documents}
docs = cmd_browse_filing_index(ticker="AAPL", accession="0000320193-24-000123")
```

### XBRL Financials

```python
from edgar_scraper import cmd_company_financials

# All 30+ metrics with derived ratios
# Returns: {company, facts, key_financials, derived}
data = cmd_company_financials(ticker="AAPL", preset="default", save=False)
data = cmd_company_financials(ticker="NVDA", preset="default", save=True)

# Income statement only
data = cmd_company_financials(ticker="AAPL", preset="income", save=False)

# Balance sheet only
data = cmd_company_financials(ticker="AAPL", preset="balance_sheet", save=False)

# Cash flow only
data = cmd_company_financials(ticker="AAPL", preset="cash_flow", save=False)

# Access structured data from return value
key_fins = data["key_financials"]    # dict: label -> list of {val, end, form, filed}
derived = data["derived"]            # dict: gross_margin_pct, roe_pct, revenue_growth_pct, ...
```

### Cross-Company Screening

```python
from edgar_scraper import cmd_concept_lookup, cmd_sector_screen

# Single concept across all filers
# Returns: frames JSON with data[] list of {accn, cik, entityName, val, end}
frames = cmd_concept_lookup(concept_key="Revenue", period="CY2024", save=False)
frames = cmd_concept_lookup(concept_key="NetIncome", period="CY2024", save=True)
frames = cmd_concept_lookup(concept_key="TotalAssets", period="CY2024Q4I", save=False)

# Custom XBRL tag
frames = cmd_concept_lookup(concept_key="OperatingIncomeLoss", period="CY2024", save=False)

# Sector screen (same as concept but with min/max/SIC filtering)
# Returns: list of {accn, cik, entityName, val, end}
results = cmd_sector_screen(concept_key="Revenue", period="CY2024", save=False)
results = cmd_sector_screen(concept_key="LongTermDebt", period="CY2024Q4I",
                            min_val=1e9, save=True)
```

### Full-Text Search

```python
from edgar_scraper import cmd_full_text_search

# Boolean search with facets
# Returns: {total, hits, aggregations}
# Note: pass explicit None for forms/start_date/end_date to avoid interactive prompts
result = cmd_full_text_search(query='"material weakness"', forms="10-K",
                              start_date=None, end_date=None, max_results=50, save=False)
result = cmd_full_text_search(query='"artificial intelligence" AND revenue',
                              forms="10-K", start_date="2024-01-01",
                              end_date="2025-12-31", max_results=100, save=True)
result = cmd_full_text_search(query="tariff risk", forms="10-K,10-Q",
                              start_date="2025-01-01", end_date=None,
                              max_results=200, save=True)

# Access results
hits = result["hits"]            # list of {entity, cik, form, file_date, accession, sic, ...}
total = result["total"]          # total match count
aggs = result["aggregations"]    # {sic_filter: [...], biz_states_filter: [...]}
```

### Deep Dive & Analyst Recipes

```python
from edgar_scraper import (cmd_deep_dive, cmd_peer_compare, cmd_risk_factors,
                           cmd_insider_activity, cmd_institutional_holdings,
                           cmd_earnings_season, cmd_recent_filings)

# Full deep dive: profile + financials + ratios + 10-K sections
# Returns: {profile, key_financials, derived, filings}
dive = cmd_deep_dive(ticker="NVDA", save=True)

# Side-by-side peer comparison
# Returns: dict keyed by ticker -> {company, derived}
peers = cmd_peer_compare(tickers_str="AAPL,MSFT,GOOG,META", save=True)
peers = cmd_peer_compare(tickers_str="NVDA,AMD,INTC,AVGO,QCOM", save=False)

# Risk factors extraction from latest 10-K
# Returns: string (full risk factors text)
risk_text = cmd_risk_factors(ticker="TSLA", save=True)

# Insider transactions (Form 4)
# Returns: list of filing dicts
insiders = cmd_insider_activity(ticker="AAPL", days=90, save=False)
insiders = cmd_insider_activity(ticker="NVDA", days=180, save=True)

# Institutional holdings (13F-HR search)
# Returns: {total, hits}
holdings = cmd_institutional_holdings(ticker="NVDA", save=True)

# Earnings season monitor
# Returns: True
cmd_earnings_season(days=14, save=False)

# Recent filings by form type
# Returns: {total, hits}
recent = cmd_recent_filings(form_type="8-K", days=3, save=False)
recent = cmd_recent_filings(form_type="10-K", days=14, save=True)
```

### Bulk Operations

```python
from edgar_scraper import cmd_bulk_company_pull

# Pull profiles + financials + filings for multiple tickers
# Returns: dict keyed by ticker -> {company, profile, filings, key_financials, derived_ratios}
results = cmd_bulk_company_pull(tickers_str="AAPL,MSFT,GOOG,NVDA,META",
                                forms="10-K", include_financials=True,
                                include_filings=True, max_filings_each=10)

# Financials only (skip filings)
results = cmd_bulk_company_pull(tickers_str="JPM,BAC,GS,MS,C",
                                forms=None, include_financials=True,
                                include_filings=False)
```

### Low-Level API Access

```python
from edgar_scraper import (resolve_company, get_submissions, extract_company_profile,
                           extract_filings, get_company_facts, get_company_concept,
                           get_frames, extract_key_financials, compute_derived_metrics,
                           full_text_search, parse_efts_results, parse_efts_aggregations,
                           download_filing_text, extract_10k_section, strip_html,
                           build_filing_url)

# Ticker to CIK resolution
matches = resolve_company("AAPL")  # [{cik, ticker, title}]
cik = matches[0]["cik"]

# Raw submissions + profile extraction
subs = get_submissions(cik)
profile = extract_company_profile(subs)
filings = extract_filings(subs, form_filter=["10-K"], max_filings=5)

# XBRL company facts (all data, 1-10MB)
facts = get_company_facts(cik)
key_fins = extract_key_financials(facts)                   # annual 10-K data
key_fins_q = extract_key_financials(facts, include_quarterly=True)  # include 10-Q
derived = compute_derived_metrics(key_fins)

# Single concept for one company
concept_data = get_company_concept(cik, "us-gaap", "Revenues")

# Cross-company frames
frames = get_frames("us-gaap", "Revenues", "USD", "CY2024")
companies = frames["data"]  # list of {accn, cik, entityName, loc, end, val}

# Full-text search with aggregations
data = full_text_search('"material weakness"', forms="10-K",
                        start_date="2024-01-01", end_date="2025-12-31",
                        offset=0, size=100)
hits, total = parse_efts_results(data)
aggs = parse_efts_aggregations(data)

# Download and extract 10-K sections
filing = filings[0]
text = download_filing_text(cik, filing["accessionNumber"], filing["primaryDocument"])
risk_factors = extract_10k_section(text, "risk_factors")
mda = extract_10k_section(text, "mda")
business = extract_10k_section(text, "business")

# Build filing URL
url = build_filing_url(cik, filing["accessionNumber"], filing["primaryDocument"])
```


## Composite Recipes

### Company Deep Dive

```bash
python edgar_scraper.py deep-dive NVDA
```

PRISM receives: company profile (SIC, exchanges, addresses, former names), 30+ XBRL financial metrics across all annual filings, 11 derived ratios (margins, ROE, ROA, growth rates, leverage), last 20 filings (10-K/10-Q/8-K), extracted 10-K sections (risk factors, MD&A, business description) as separate text files.

### Peer Financial Comparison

```bash
python edgar_scraper.py peer-compare AAPL,MSFT,GOOG,META --save
```

PRISM receives: side-by-side comparison table with Revenue, NetIncome, Gross/Operating/Net margins, ROE, ROA, Revenue Growth YoY, R&D intensity, Debt/Equity for each peer.

### Fundamental Analysis (Single Company)

```bash
python edgar_scraper.py profile AAPL --save
python edgar_scraper.py financials AAPL --preset default --save
python edgar_scraper.py financials AAPL --preset income --save
python edgar_scraper.py financials AAPL --preset balance_sheet --save
python edgar_scraper.py financials AAPL --preset cash_flow --save
python edgar_scraper.py insider AAPL --days 180 --save
python edgar_scraper.py holdings AAPL --save
```

PRISM receives: full company metadata, all XBRL financials with derived ratios across each preset slice, 6-month insider transaction history, institutional ownership from 13F-HR filings.

### Risk Factor Monitoring (Thematic)

```bash
python edgar_scraper.py search '"tariff risk"' --forms 10-K --start 2024-01-01 --save
python edgar_scraper.py search '"material weakness"' --forms 10-K --start 2024-01-01 --save
python edgar_scraper.py search '"going concern"' --forms 10-K,10-Q --start 2025-01-01 --save
```

PRISM receives: hit counts per query, SIC industry distribution of matches (which industries mention this most), state distribution, entity list with filing dates and accession numbers.

### Risk Factor Comparison (Company-Level)

```bash
python edgar_scraper.py risk-factors TSLA
python edgar_scraper.py risk-factors NVDA
python edgar_scraper.py risk-factors AAPL
```

PRISM receives: full risk factors text (Item 1A) from latest 10-K for each company, typically 10,000-30,000 words each.

### Earnings Season Dashboard

```bash
python edgar_scraper.py earnings-season --days 14 --save
python edgar_scraper.py recent --form 8-K --days 3 --save
python edgar_scraper.py recent --form 10-K --days 7 --save
```

PRISM receives: all 10-K and 10-Q filings in last 14 days, all 8-K material events in last 3 days, all 10-K filings in last 7 days with entity names and filing dates.

### Credit / Debt Analysis

```bash
python edgar_scraper.py financials TICKER --preset balance_sheet --save
python edgar_scraper.py financials TICKER --preset cash_flow --save
python edgar_scraper.py download TICKER --form 10-K --count 1
python edgar_scraper.py search '"credit agreement" AND "covenant"' --forms 10-K --save
python edgar_scraper.py search '"revolving credit" AND "amendment"' --forms 8-K --save
```

PRISM receives: balance sheet with debt/equity/liabilities, cash flow with OCF/capex/dividends/buybacks, full 10-K text for debt maturity schedule, covenant language matches across all filers.

### Insider & Institutional Review

```bash
python edgar_scraper.py insider AAPL --days 180 --save
python edgar_scraper.py holdings AAPL --save
python edgar_scraper.py filings AAPL --forms 4 --max 50 --save
python edgar_scraper.py search '"SC 13D"' --forms "SC 13D" --start $(date -v-6m +%Y-%m-%d) --save
```

PRISM receives: 6-month insider transaction history (Form 4), institutional holders from 13F-HR, full Form 4 filing list, recent activist positions (SC 13D).

### Sector-Wide Screen

```bash
python edgar_scraper.py screen Revenue --period CY2024 --save
python edgar_scraper.py screen NetIncome --period CY2024 --save
python edgar_scraper.py screen LongTermDebt --period CY2024Q4I --save
```

PRISM receives: Revenue for all ~3,000+ filers in CY2024 sorted by magnitude, NetIncome for all filers, LongTermDebt (point-in-time) for all filers. Each entry includes entityName, CIK, value.

### Bulk Coverage Universe

```bash
python edgar_scraper.py bulk AAPL,MSFT,GOOG,AMZN,NVDA,TSLA,META --forms 10-K
python edgar_scraper.py peer-compare AAPL,MSFT,GOOG,AMZN,NVDA,TSLA,META --save
```

PRISM receives: profiles, financials, derived ratios, and filing lists for 7 companies in single JSON, plus side-by-side comparison table.

### Event-Window Filing Search

```bash
# Around a specific event (e.g. tariff announcement, rate decision)
python edgar_scraper.py search '"tariff"' --forms 8-K --start YYYY-MM-DD --end YYYY-MM-DD --save
python edgar_scraper.py search '"tariff"' --forms 10-K --start YYYY-MM-DD --end YYYY-MM-DD --save
python edgar_scraper.py recent --form 8-K --days 3 --save
```

PRISM receives: all 8-K and 10-K filings mentioning the event term within the window, plus very recent material event filings for context.


## Cross-Source Recipes

### EDGAR + FDIC (Bank Fundamentals)

```bash
python edgar_scraper.py financials JPM --preset default --save
python projects/apis/fdic/fdic.py recipe bank-stress --json
```

PRISM receives: bank holding company XBRL financials + bank subsidiary-level Call Report data from FDIC. SEC shows consolidated picture; FDIC shows bank-level capital/NII/provisions.

### EDGAR + FRED (Cyclical Company + Macro)

```bash
python edgar_scraper.py financials CAT --preset default --save
python projects/apis/fred/fred.py series GDP,UNRATE,INDPRO --obs 60
```

PRISM receives: company financials + macro context (GDP growth, unemployment, industrial production). Revenue cyclicality vs macro cycle.

### EDGAR + NY Fed (Financial Sector + Funding)

```bash
python edgar_scraper.py peer-compare JPM,BAC,GS,MS,C --save
python projects/apis/nyfed/nyfed.py funding-snapshot --json
python projects/apis/nyfed/nyfed.py rates --json
```

PRISM receives: bank financials side-by-side + current funding conditions (SOFR/EFFR rates, RRP, repo operations). NII sensitivity to rate environment.

### EDGAR + Prediction Markets (M&A / Event)

```bash
python edgar_scraper.py search '"material agreement"' --forms 8-K --start $(date -v-30d +%Y-%m-%d) --save
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: recent material agreement 8-K filings + market-implied event probabilities. M&A completion odds, regulatory approval likelihood.

### EDGAR + Treasury (Rate-Sensitive Issuers)

```bash
python edgar_scraper.py financials TICKER --preset balance_sheet --save
python edgar_scraper.py search '"interest rate risk"' --forms 10-K --start 2024-01-01 --save
python projects/apis/treasury/treasury.py get rates --json
```

PRISM receives: company debt levels + interest rate risk language from 10-K filings + current Treasury rate environment. Refinancing risk assessment.

### EDGAR + BIS (Multinational Exposure)

```bash
python edgar_scraper.py deep-dive TICKER
python projects/apis/bis/bis.py lbs --json
```

PRISM receives: company profile/financials/10-K narrative + BIS cross-border banking statistics. Geographic revenue mix vs cross-border capital flows.

### EDGAR + Tariffs (Trade Exposure)

```bash
python edgar_scraper.py search '"tariff" OR "trade war"' --forms 10-K --start 2024-01-01 --save
python edgar_scraper.py risk-factors TICKER
python projects/apis/tariffs/tariffs.py overview --json
```

PRISM receives: companies mentioning tariff risk in 10-K + specific company risk factors text + current tariff rate landscape. Supply chain and margin exposure.

### EDGAR + Electricity (Utility Fundamentals)

```bash
python edgar_scraper.py peer-compare NEE,DUK,SO,D,AEP --save
python projects/apis/electricity/electricity.py generation --json
```

PRISM receives: utility company financials side-by-side + actual electricity generation/demand data. Revenue drivers vs production volumes.


## Setup

1. No API key required (User-Agent header set automatically)
2. `pip install requests`
3. Test: `python edgar_scraper.py lookup AAPL`
4. Full test: `python edgar_scraper.py deep-dive AAPL`


## Architecture

```
edgar_scraper.py
  Constants       SIC_INDUSTRIES (80+), FORM_TYPES_CORE/EXTENDED, XBRL_INCOME_STATEMENT,
                  XBRL_BALANCE_SHEET, XBRL_CASH_FLOW, XBRL_PRESETS (4)
  HTTP            _session (User-Agent), _rate_limit (10 req/sec), _get (retries + 403/429 handling)
  Ticker/CIK      _load_tickers (~10K), resolve_company, _resolve_one
  Profile         get_submissions, extract_company_profile, extract_filings
  Filing Docs     get_filing_index, download_filing_text, _HTMLStripper, extract_10k_section
  XBRL            get_company_facts, get_company_concept, get_frames,
                  extract_key_financials, compute_derived_metrics
  Search          full_text_search, parse_efts_results, parse_efts_aggregations
  Persistence     _save_json, _save_text, _save_csv -> data/ directory
  Core Cmds (10)  lookup, profile, filings, download, financials, concept,
                  search, recent, browse, bulk
  Recipes (7)     deep-dive, peer-compare, risk-factors, insider, holdings,
                  screen, earnings-season
  Interactive     interactive_loop -> 17-item menu with core + recipes + tools
  Argparse        17 subcommands, all with --save or --no-save
```

API endpoints:
```
/submissions/CIK{cik}.json                            -> company profile + filing history
/api/xbrl/companyfacts/CIK{cik}.json                  -> all XBRL facts (1-10MB)
/api/xbrl/companyconcept/CIK{cik}/{tax}/{concept}.json -> single concept per company
/api/xbrl/frames/{tax}/{concept}/{unit}/{period}.json  -> cross-company (2K-6K filers)
efts.sec.gov/LATEST/search-index                       -> full-text search + facets
sec.gov/files/company_tickers.json                     -> bulk ticker-to-CIK mapping
sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}          -> raw filing documents
```
