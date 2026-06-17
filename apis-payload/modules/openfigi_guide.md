# OpenFIGI -- Financial Instrument Identifier Mapping

Script: `projects/apis/openfigi/openfigi.py`
Base URL: `https://api.openfigi.com/v3`
Auth: Optional API key via `OPENFIGI_API_KEY` env var (higher rate limits with key; works without)
Rate limits: Without key: 10 jobs/request, 25 requests/minute. With key: 100 jobs/request, 25 requests/6s.
Dependencies: `requests`

27555b60-a631-4142-94c1-320133283cc1

## Triggers

Use for: identifier resolution (CUSIP/ISIN/SEDOL/FIGI/ticker cross-mapping), Treasury CUSIP -> Bloomberg ticker, batch portfolio mapping, mixed-identifier auto-detection, exchange listing discovery, FIGI hierarchy walking, issuer bond stacks, capital structure mapping, maturity wall analysis, sector-wide bond comparison, Treasury universe enumeration, preferred stock and loan facility discovery, options chain mapping, futures term structure, derivative overlay, MBS/agency securities, municipal bonds, FX/currency instruments, commodity instruments, index instruments, money market instruments, exchange-level universe scanning, full issuer universe across all asset classes.

Not for: price data or time series (market data APIs), company fundamentals (EDGAR), real-time instrument creation, historical identifier changes, OTC instruments without FIGI assignments, instruments already in the format your downstream system needs.


## Data Catalog

### Identifier Types (Most Used)

| ID Type | Description | Example | When Needed |
|---------|-------------|---------|-------------|
| `TICKER` | Ticker symbol | IBM, AAPL | Equity lookups, EDGAR cross-reference |
| `ID_CUSIP` | CUSIP (9-char) | 459200101 | Treasury/bond data from TreasuryDirect |
| `ID_ISIN` | ISIN (12-char) | US4592001014 | International cross-reference, BIS data |
| `ID_SEDOL` | SEDOL (7-char) | 2005973 | UK/European instruments |
| `ID_BB_GLOBAL` | Bloomberg FIGI | BBG000BLNNH6 | When you already have a FIGI |
| `COMPOSITE_ID_BB_GLOBAL` | Composite FIGI | BBG000BLNNH6 | Country-level aggregate |
| `ID_BB_GLOBAL_SHARE_CLASS_LEVEL` | Share Class FIGI | BBG001S5S399 | Global aggregate across all exchanges |

### Additional Identifier Types

| ID Type | Description |
|---------|-------------|
| `BASE_TICKER` | Base ticker (for options, bonds, pools: e.g. "IBM 7 10/30/25") |
| `ID_CUSIP_8_CHR` | CUSIP issuer-level (first 8 chars) |
| `ID_BB_UNIQUE` | Legacy Bloomberg unique ID |
| `ID_TRACE` | FINRA TRACE identifier |
| `ID_COMMON` | Common Code (9-digit) |
| `ID_WERTPAPIER` | WKN (German securities ID) |
| `ID_CINS` | CINS (international CUSIP) |
| `ID_EXCH_SYMBOL` | Exchange-specific symbol |
| `ID_FULL_EXCHANGE_SYMBOL` | Full exchange symbol (futures/options) |
| `ID_BB_SEC_NUM_DES` | Bloomberg security number description |
| `OCC_SYMBOL` | OCC option symbol (21-char) |
| `UNIQUE_ID_FUT_OPT` | Bloomberg future/option unique ID |
| `OPRA_SYMBOL` | OPRA option symbol |
| `TRADING_SYSTEM_IDENTIFIER` | Trading system ID |
| `ID_SHORT_CODE` | Short code (Asian fixed income) |
| `VENDOR_INDEX_CODE` | Index provider code |

### Response Fields

| Field | Description |
|-------|-------------|
| `figi` | FIGI for this specific listing |
| `compositeFIGI` | Country-level aggregate FIGI |
| `shareClassFIGI` | Global aggregate FIGI (all listings worldwide) |
| `ticker` | Ticker symbol |
| `name` | Instrument name |
| `exchCode` | Exchange code |
| `marketSector` | Equity, Corp, Govt, Comdty, Curncy, Index, M-Mkt, Mtge, Muni, Pfd |
| `securityType` | Specific security type (Common Stock, US GOVERNMENT, etc.) |
| `securityType2` | Broader type (Common Stock, Option, Note, Pool, etc.) |
| `securityDescription` | Short description |

### FIGI Hierarchy

```
Share Class FIGI (BBG001S5S399) -- global aggregate, one per share class
    |
    +-- Composite FIGI (BBG000BLNNH6) -- country-level aggregate
    |       |
    |       +-- FIGI (BBG000BLNNH6) -- specific exchange listing (NYSE)
    |       +-- FIGI (BBG000NHN466) -- specific exchange listing (LSE)
    |
    +-- Composite FIGI (BBG000NHN304) -- another country
            |
            +-- FIGI (...) -- listing on that country's exchange
```

### Mapping Job Filters

| Filter | Type | Description |
|--------|------|-------------|
| `exchCode` | String | Exchange code (cannot combine with micCode) |
| `micCode` | String | ISO MIC code (cannot combine with exchCode) |
| `currency` | String | Currency (e.g. USD, EUR, GBP) |
| `marketSecDes` | String | Market sector (Equity, Govt, Corp, etc.) |
| `securityType` | String | Specific security type |
| `securityType2` | String | Broader security type (Option, Future, Corp, Note, etc.) |
| `includeUnlistedEquities` | Boolean | Include unlisted equities |
| `strike` | [min, max] | Option strike range |
| `coupon` | [min, max] | Bond coupon range |
| `expiration` | [date, date] | Option/future expiration range (YYYY-MM-DD) |
| `maturity` | [date, date] | Bond/pool maturity range (YYYY-MM-DD) |
| `stateCode` | String | US state code (for municipal bonds) |

### Market Sectors

| Sector | Description | Script Commands |
|--------|-------------|-----------------|
| `Equity` | Stocks, ETFs | equity, global-listings, exchange-scan |
| `Corp` | Corporate bonds | issuer-bonds, capital-structure |
| `Govt` | Government bonds | treasury, treasury-universe |
| `Comdty` | Commodities | commodity |
| `Curncy` | FX / Currency | fx |
| `Index` | Indices | index |
| `M-Mkt` | Money Market | money-market |
| `Mtge` | Mortgage-backed | mbs |
| `Muni` | Municipal bonds | munis |
| `Pfd` | Preferred stock | preferred |

### Identifier Auto-Detection

The `portfolio` command auto-detects identifier types:

| Pattern | Detected Type | Example |
|---------|---------------|---------|
| Starts with "BBG", 12 chars | `ID_BB_GLOBAL` | BBG000B9XRY4 |
| 12 chars, starts with 2 letters | `ID_ISIN` | US4592001014 |
| 9 chars, alphanumeric | `ID_CUSIP` | 459200101 |
| 7 chars, alphanumeric | `ID_SEDOL` | 2005973 |
| 8 chars, alphanumeric | `ID_CUSIP_8_CHR` | 45920010 |
| Everything else | `TICKER` | AAPL, IBM |

### Curated Issuer Lists

| List | Tickers |
|------|---------|
| `banks` | JPM, BAC, C, GS, MS, WFC |
| `tech` | AAPL, MSFT, GOOG, AMZN, META, INTC |
| `energy` | XOM, CVX, COP, SLB, EOG |
| `pharma` | JNJ, PFE, MRK, ABBV, LLY |
| `telco` | T, VZ, TMUS |
| `auto` | F, GM, TSLA |

### Bond Ticker Parsing

| Raw Ticker | Coupon | Rate Type | Maturity | Suffix |
|------------|--------|-----------|----------|--------|
| `INTC 3.7 07/29/25` | 3.7% | fixed | 2025-07-29 | |
| `INTC F 05/11/27` | -- | floating | 2027-05-11 | |
| `INTC V3.22 03/01/25` | 3.22% | variable | 2025-03-01 | |
| `JPM 4.25 11/30/25 GMTN` | 4.25% | fixed | 2025-11-30 | GMTN |
| `INTC 0 02/01/04 144A` | 0% | zero | 2004-02-01 | 144A |

Suffixes: 144A (private placement), REGS (Regulation S), AI (accredited investor), GMTN (global MTN), * (defaulted).

### Enum Keys

Valid keys for `enums` command: `idType`, `exchCode`, `micCode`, `currency`, `marketSecDes`, `securityType`, `securityType2`, `stateCode`.


## CLI Recipes

All 33 commands support `--json` for structured output. Most support `--export csv|json` for file export.

### Single Identifier Mapping

```bash
python openfigi.py map TICKER IBM
python openfigi.py map TICKER IBM --json
python openfigi.py map ID_CUSIP 912810SZ9
python openfigi.py map ID_ISIN US4592001014
python openfigi.py map TICKER IBM --exch US --currency USD --sector Equity
```

### Quick Lookups

```bash
python openfigi.py equity AAPL
python openfigi.py equity AAPL --exch US --json
python openfigi.py bond 912810SZ9
python openfigi.py bond US4592001014 --json
python openfigi.py cross-ref TICKER AAPL --json
python openfigi.py cross-ref ID_ISIN US0378331005 --json
```

### FIGI Hierarchy + Global Listings

```bash
# Reverse FIGI lookup -- walks listing -> composite -> share class
python openfigi.py figi-lookup BBG000B9XRY4
python openfigi.py figi-lookup BBG000B9XRY4 --json
python openfigi.py figi-lookup BBG001S5N8V8 --json

# All worldwide exchange listings for a ticker, grouped by composite
python openfigi.py global-listings AAPL
python openfigi.py global-listings MSFT --json
python openfigi.py global-listings TSLA --export csv
```

### Portfolio Auto-Detection

```bash
# Mixed identifiers -- auto-detects TICKER vs CUSIP vs ISIN vs SEDOL vs FIGI
python openfigi.py portfolio "AAPL,US4592001014,BBG000B9XRY4,912810SZ9"
python openfigi.py portfolio "AAPL,US4592001014,BBG000B9XRY4" --json
python openfigi.py portfolio mixed_ids.txt --json
python openfigi.py portfolio portfolio.txt --export csv
```

### Batch Resolution

```bash
python openfigi.py treasury 912810SZ9 912810TA3 912810TB1 --json
python openfigi.py batch tickers.txt --id-type TICKER
python openfigi.py batch bonds.txt --id-type ID_CUSIP --sector Govt --export csv
```

### Search & Discovery

```bash
python openfigi.py search "apple" --sector Equity --json
python openfigi.py search "treasury 10 year" --sector Govt --exch US --json
python openfigi.py filter --query "apple" --sector Equity
python openfigi.py filter --sector Govt --exch US --json
python openfigi.py enums exchCode
python openfigi.py enums securityType --json
python openfigi.py id-types --json
```

### Issuer Bond Analysis

```bash
python openfigi.py issuer-bonds INTC --maturity 2025-2035 --json
python openfigi.py issuer-bonds JPM --maturity 2025-2030 --sec-type GLOBAL --json
python openfigi.py capital-structure INTC --json
python openfigi.py capital-structure JPM --export csv
python openfigi.py maturity-profile INTC --start 2025 --end 2035 --json
python openfigi.py compare-issuers AAPL MSFT GOOG AMZN META INTC --json
python openfigi.py compare-issuers JPM BAC C GS MS WFC --export csv
python openfigi.py sector-scan --list banks --json
python openfigi.py sector-scan --list tech --json
python openfigi.py sector-scan --tickers NVDA AMD QCOM --json
```

### Issuer Full Universe

```bash
# Everything: equity + bonds + preferred + loans + options + futures
python openfigi.py issuer-universe INTC --json
python openfigi.py issuer-universe AAPL --json
python openfigi.py issuer-universe JPM --export csv
```

### Options Chain

```bash
# All options for next 2 years (default)
python openfigi.py options AAPL --json
python openfigi.py options SPY --json

# With expiry and strike filters
python openfigi.py options AAPL --expiry-start 2026-01-01 --expiry-end 2026-06-30 --json
python openfigi.py options AAPL --strike-min 150 --strike-max 250 --json
python openfigi.py options TSLA --expiry-start 2026-01-01 --expiry-end 2026-12-31 --strike-min 200 --strike-max 400 --json
python openfigi.py options SPY --expiry-start 2026-03-01 --expiry-end 2026-03-31 --export csv
```

### Futures Term Structure

```bash
# Equity index futures
python openfigi.py futures ES --json
python openfigi.py futures NQ --json
python openfigi.py futures YM --json

# Rates futures
python openfigi.py futures ZN --json
python openfigi.py futures TY --json
python openfigi.py futures ZB --json
python openfigi.py futures ED --json

# Commodity futures
python openfigi.py futures CL --json
python openfigi.py futures GC --json
python openfigi.py futures NG --json
python openfigi.py futures SI --json

# With expiry range
python openfigi.py futures ES --expiry-start 2026-01-01 --expiry-end 2027-12-31 --json
python openfigi.py futures CL --expiry-start 2026-01-01 --expiry-end 2028-12-31 --export csv
```

### Derivatives Overlay

```bash
# All options + futures for a ticker in one view
python openfigi.py derivatives AAPL --json
python openfigi.py derivatives SPY --json
python openfigi.py derivatives ES --expiry-start 2026-01-01 --expiry-end 2027-12-31 --json
```

### MBS / Agency Securities

```bash
python openfigi.py mbs FNMA --json
python openfigi.py mbs GNMA --json
python openfigi.py mbs FHLMC --json
python openfigi.py mbs FNMA --maturity 2025-2035 --json
python openfigi.py mbs GNMA --maturity 2030-2040 --export csv
```

### Municipal Bonds

```bash
python openfigi.py munis "California" --json
python openfigi.py munis "New York" --state NY --json
python openfigi.py munis "general obligation" --state TX --json
python openfigi.py munis "revenue bond" --export csv
```

### FX / Currency

```bash
python openfigi.py fx EUR --json
python openfigi.py fx JPY --json
python openfigi.py fx "dollar" --json
python openfigi.py fx GBP --export csv
```

### Commodity Instruments

```bash
python openfigi.py commodity "crude oil" --json
python openfigi.py commodity "gold" --json
python openfigi.py commodity "natural gas" --json
python openfigi.py commodity "corn" --json
python openfigi.py commodity "copper" --export csv
```

### Index Instruments

```bash
python openfigi.py index "S&P 500" --json
python openfigi.py index "NASDAQ" --json
python openfigi.py index "MSCI" --json
python openfigi.py index "Russell" --json
python openfigi.py index "VIX" --json
```

### Money Market

```bash
python openfigi.py money-market "SOFR" --json
python openfigi.py money-market "commercial paper" --json
python openfigi.py money-market "certificate of deposit" --json
```

### Exchange Universe

```bash
# Scan all instruments on an exchange
python openfigi.py exchange-scan US --json
python openfigi.py exchange-scan LN --json
python openfigi.py exchange-scan JP --sector Equity --json
python openfigi.py exchange-scan HK --sector Equity --pages 5 --export csv
python openfigi.py exchange-scan US --sector Govt --json
```

### Treasury & Specialized

```bash
python openfigi.py treasury-universe --maturity 2025-2035 --type notes --json
python openfigi.py treasury-universe --maturity 2030-2031 --type all --export csv
python openfigi.py preferred JPM --json
python openfigi.py preferred BAC --export csv
python openfigi.py loans INTC --json
python openfigi.py loans GE --export csv
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All 33 commands |
| `--export csv` | Export to CSV file | Most commands |
| `--export json` | Export to JSON file | Most commands |
| `--exch CODE` | Exchange code filter | map, batch, equity, options |
| `--currency CUR` | Currency filter | map, batch |
| `--sector SEC` | Market sector filter | map, batch, search, filter, exchange-scan |
| `--sec-type TYPE` | Security type filter | map, search, filter, issuer-bonds, exchange-scan |
| `--pages N` | Max pages to fetch | search, filter, exchange-scan |
| `--maturity YYYY-YYYY` | Maturity range | issuer-bonds, treasury-universe, mbs |
| `--id-type TYPE` | Identifier type for batch | batch |
| `--start YYYY` | Start year | maturity-profile |
| `--end YYYY` | End year | maturity-profile |
| `--list NAME` | Curated issuer list | sector-scan |
| `--type TYPE` | notes/bonds/bills/all | treasury-universe |
| `--expiry-start DATE` | Expiry start YYYY-MM-DD | options, futures, derivatives |
| `--expiry-end DATE` | Expiry end YYYY-MM-DD | options, futures, derivatives |
| `--strike-min N` | Min strike price | options |
| `--strike-max N` | Max strike price | options |
| `--state CODE` | US state code | munis |


## Python Recipes

### Single Identifier Resolution

```python
from openfigi import cmd_map, cmd_equity, cmd_bond, cmd_cross_ref

result = cmd_map("TICKER", "IBM", as_json=True)
result = cmd_map("ID_CUSIP", "912810SZ9", as_json=True)
result = cmd_map("ID_ISIN", "US4592001014", as_json=True)
result = cmd_map("TICKER", "IBM", exch_code="US", sector="Equity", as_json=True)
eq = cmd_equity("AAPL", as_json=True)
eq = cmd_equity("AAPL", exch_code="US", as_json=True)
bond = cmd_bond("912810SZ9", as_json=True)
xref = cmd_cross_ref("TICKER", "AAPL", as_json=True)
```

### FIGI Hierarchy + Global Listings

```python
from openfigi import cmd_figi_lookup, cmd_global_listings

# Reverse FIGI lookup -- auto-detects listing vs composite vs share class
# Returns: {query, share_class_figi, composite_figi, listing_count, listings: [...]}
hierarchy = cmd_figi_lookup("BBG000B9XRY4", as_json=True)
hierarchy = cmd_figi_lookup("BBG001S5N8V8", as_json=True)

# All worldwide exchange listings, grouped by composite FIGI
# Returns: {ticker, total_listings, composites, share_class_figi, listings: [...]}
listings = cmd_global_listings("AAPL", as_json=True)
listings = cmd_global_listings("TSLA", as_json=True)
```

### Portfolio Auto-Detection

```python
from openfigi import cmd_portfolio

# Mixed identifiers -- auto-detects type per identifier
# Returns: list of {query_id, query_type, result} dicts
result = cmd_portfolio(identifiers=["AAPL", "US4592001014", "BBG000B9XRY4", "912810SZ9"], as_json=True)
result = cmd_portfolio(filepath="mixed_portfolio.txt", as_json=True)
```

### Batch Resolution

```python
from openfigi import cmd_batch, cmd_batch_file, cmd_treasury_cusips

batch = cmd_batch(["AAPL", "MSFT", "GOOG"], id_type="TICKER", as_json=True)
result = cmd_batch_file("tickers.txt", id_type="TICKER", as_json=True)
tsy = cmd_treasury_cusips(["912810SZ9", "912810TA3", "912810TB1"], as_json=True)
```

### Search & Discovery

```python
from openfigi import cmd_search, cmd_filter, cmd_enums, cmd_id_types

results = cmd_search("apple", sector="Equity", as_json=True)
data, total = cmd_filter(query="apple", sector="Equity", as_json=True)
exchanges = cmd_enums("exchCode", as_json=True)
types = cmd_id_types(as_json=True)
```

### Issuer Bond Analysis

```python
from openfigi import (cmd_issuer_bonds, cmd_capital_structure,
                      cmd_maturity_profile, cmd_compare_issuers,
                      cmd_sector_scan, cmd_preferred, cmd_loans)

bonds = cmd_issuer_bonds("INTC", as_json=True)
bonds = cmd_issuer_bonds("INTC", maturity_start="2025-01-01",
                         maturity_end="2035-12-31", as_json=True)
cap = cmd_capital_structure("INTC", as_json=True)
wall = cmd_maturity_profile("INTC", start_year=2025, end_year=2035, as_json=True)
comp = cmd_compare_issuers(["AAPL", "MSFT", "GOOG", "AMZN"], as_json=True)
scan = cmd_sector_scan(list_name="banks", as_json=True)
pfds = cmd_preferred("JPM", as_json=True)
loans = cmd_loans("INTC", as_json=True)
```

### Issuer Full Universe

```python
from openfigi import cmd_issuer_universe

# Everything: equity + bonds + preferred + loans + options count + futures count
# Returns: {ticker, name, equity_listings, bonds_outstanding, preferred_instruments,
#           loan_facilities, options_near_term, futures_active, equity: [...], bonds_sample: [...]}
universe = cmd_issuer_universe("INTC", as_json=True)
universe = cmd_issuer_universe("AAPL", as_json=True)
universe = cmd_issuer_universe("JPM", as_json=True)
```

### Options Chain

```python
from openfigi import cmd_options_chain

# All options for next 2 years (default range)
# Returns: list of option instrument dicts with securityType (Call/Put), exchange, FIGI
options = cmd_options_chain("AAPL", as_json=True)
options = cmd_options_chain("SPY", as_json=True)

# With expiry and strike filters
options = cmd_options_chain("AAPL", expiry_start="2026-01-01", expiry_end="2026-06-30", as_json=True)
options = cmd_options_chain("AAPL", strike_min=150, strike_max=250, as_json=True)
options = cmd_options_chain("TSLA", expiry_start="2026-01-01", expiry_end="2026-12-31",
                            strike_min=200, strike_max=400, as_json=True)
```

### Futures Term Structure

```python
from openfigi import cmd_futures

# Equity index futures (default: next 3 years)
# Returns: list of futures instrument dicts sorted by ticker/contract
futures = cmd_futures("ES", as_json=True)
futures = cmd_futures("NQ", as_json=True)

# Rates futures
futures = cmd_futures("ZN", as_json=True)
futures = cmd_futures("TY", as_json=True)

# Commodity futures with custom range
futures = cmd_futures("CL", expiry_start="2026-01-01", expiry_end="2028-12-31", as_json=True)
futures = cmd_futures("GC", as_json=True)
```

### Derivatives Overlay

```python
from openfigi import cmd_derivatives

# Combined options + futures for a ticker
# Returns: {ticker, options_count, calls, puts, futures_count, options_sample: [...], futures: [...]}
deriv = cmd_derivatives("AAPL", as_json=True)
deriv = cmd_derivatives("SPY", as_json=True)
deriv = cmd_derivatives("ES", expiry_start="2026-01-01", expiry_end="2027-12-31", as_json=True)
```

### Asset-Class Universes

```python
from openfigi import cmd_mbs, cmd_munis, cmd_fx, cmd_commodity, cmd_index_instruments, cmd_money_market

# MBS / Agency securities (keyword search or BASE_TICKER with maturity range)
mbs = cmd_mbs("FNMA", as_json=True)
mbs = cmd_mbs("GNMA", maturity_start="2025-01-01", maturity_end="2035-12-31", as_json=True)

# Municipal bonds (with optional state filter)
munis = cmd_munis("California", as_json=True)
munis = cmd_munis("general obligation", state_code="NY", as_json=True)

# FX / Currency
fx = cmd_fx("EUR", as_json=True)
fx = cmd_fx("JPY", as_json=True)

# Commodities
comdty = cmd_commodity("crude oil", as_json=True)
comdty = cmd_commodity("gold", as_json=True)

# Indices
idx = cmd_index_instruments("S&P 500", as_json=True)
idx = cmd_index_instruments("VIX", as_json=True)

# Money market
mm = cmd_money_market("SOFR", as_json=True)
mm = cmd_money_market("commercial paper", as_json=True)
```

### Exchange Universe

```python
from openfigi import cmd_exchange_scan

# Instruments on a specific exchange (returns sample + total count)
# Returns: (data_list, total_count)
data, total = cmd_exchange_scan("US", as_json=True)
data, total = cmd_exchange_scan("LN", sector="Equity", as_json=True)
data, total = cmd_exchange_scan("JP", sector="Equity", as_json=True)
```

### Treasury Universe

```python
from openfigi import cmd_treasury_universe

tsy = cmd_treasury_universe(maturity_start="2025-01-01",
                            maturity_end="2035-12-31",
                            instrument_type="notes", as_json=True)
```

### Core API Functions

```python
from openfigi import api_map, api_map_single, api_search, api_filter, api_enum_values

jobs = [{"idType": "TICKER", "idValue": "IBM"},
        {"idType": "TICKER", "idValue": "AAPL", "exchCode": "US"}]
results = api_map(jobs)

result = api_map_single("TICKER", "IBM", exchCode="US", marketSecDes="Equity")
instruments = api_search("apple", max_pages=3, marketSecDes="Equity")
instruments, total = api_filter(query="apple", max_pages=3, marketSecDes="Equity")
exchanges = api_enum_values("exchCode")

# Options via raw API
options = api_map([{"idType": "BASE_TICKER", "idValue": "AAPL",
                    "securityType2": "Option",
                    "expiration": ["2026-01-01", "2026-12-31"],
                    "strike": [150, 250]}])

# Futures via raw API
futures = api_map([{"idType": "BASE_TICKER", "idValue": "ES",
                    "securityType2": "Future",
                    "expiration": ["2026-01-01", "2028-12-31"]}])
```


## Composite Recipes

### Treasury Auction Cross-Reference

```bash
python openfigi.py treasury 912810SZ9 912810TA3 912810TB1 --json
```

PRISM receives: Bloomberg ticker (e.g. "T 4.5 11/15/33"), FIGI, composite FIGI, security type, and name for each CUSIP. Links TreasuryDirect auction data to Bloomberg identifiers.

### EDGAR Filing -> Instrument Identifier

```bash
python openfigi.py equity AAPL --json
python openfigi.py cross-ref TICKER AAPL --json
```

PRISM receives: composite FIGI, share class FIGI, all exchange listings globally. Links EDGAR filings to Bloomberg identifier system.

### Full Identifier Resolution Pipeline

```bash
python openfigi.py figi-lookup BBG000B9XRY4 --json
python openfigi.py global-listings AAPL --json
python openfigi.py issuer-bonds IBM --maturity 2025-2035 --json
```

PRISM receives: FIGI hierarchy (listing -> composite -> share class), every global exchange listing, full corporate bond stack with parsed coupon/maturity.

### Mixed Portfolio Resolution

```bash
python openfigi.py portfolio "AAPL,US4592001014,BBG000B9XRY4,912810SZ9,2005973" --json
```

PRISM receives: auto-detected identifier types + resolved FIGIs for a mixed bag of tickers, ISINs, CUSIPs, SEDOLs, and FIGIs. Single call resolves any portfolio regardless of identifier format.

### Issuer Credit Profile

```bash
python openfigi.py capital-structure INTC --json
python openfigi.py maturity-profile INTC --start 2025 --end 2035 --json
```

PRISM receives: equity listing count, total bonds outstanding, preferred count, loan facility count, maturity wall with per-year bond count and average coupon.

### Complete Issuer Footprint

```bash
python openfigi.py issuer-universe AAPL --json
```

PRISM receives: equity listings, corporate bonds, preferred stock, loan facilities, near-term options count, and futures count. Single-call complete instrument footprint across all asset classes.

### Sector Bond Comparison

```bash
python openfigi.py sector-scan --list banks --json
python openfigi.py sector-scan --list tech --json
```

PRISM receives: per-issuer bond count, average coupon, coupon range, maturity range.

### Treasury Curve Reference Points

```bash
python openfigi.py treasury-universe --maturity 2025-2035 --type notes --json
```

PRISM receives: every outstanding Treasury note and bond with coupon, maturity date, and FIGI.

### Options Chain for Derivatives Analysis

```bash
python openfigi.py options AAPL --expiry-start 2026-01-01 --expiry-end 2026-06-30 --strike-min 150 --strike-max 250 --json
```

PRISM receives: all matching option instruments with calls/puts breakdown, exchange, FIGI, and security descriptions. For options flow analysis, implied vol surface construction, or hedging instrument discovery.

### Futures Curve Construction

```bash
python openfigi.py futures ES --json
python openfigi.py futures CL --expiry-start 2026-01-01 --expiry-end 2028-12-31 --json
```

PRISM receives: all futures contracts for the base ticker with expiration embedded in ticker. For building term structure curves, roll analysis, and calendar spread identification.

### Derivatives Overlay

```bash
python openfigi.py derivatives AAPL --json
```

PRISM receives: combined options count (calls/puts split) + futures contracts for a single underlying. Quick assessment of derivatives universe depth.

### MBS Universe Mapping

```bash
python openfigi.py mbs FNMA --maturity 2025-2035 --json
```

PRISM receives: FNMA/GNMA/FHLMC mortgage pool identifiers with maturity ranges. For prepayment analysis context and MBS universe sizing.

### Municipal Bond Discovery

```bash
python openfigi.py munis "general obligation" --state CA --json
```

PRISM receives: municipal bond instruments filtered by state and type. For muni credit analysis and state-level fiscal assessment.

### Exchange Universe Sizing

```bash
python openfigi.py exchange-scan US --sector Equity --json
python openfigi.py exchange-scan LN --json
```

PRISM receives: total instrument count + type/sector breakdown for an exchange. For market structure analysis and cross-exchange comparison.

### FX / Commodity / Index Discovery

```bash
python openfigi.py fx EUR --json
python openfigi.py commodity "crude oil" --json
python openfigi.py index "VIX" --json
python openfigi.py money-market "SOFR" --json
```

PRISM receives: instrument-level identifiers for any asset class. For cross-asset analysis, linking reference rates to instruments, or discovering tradable proxies.


## Cross-Source Recipes

### CUSIP Resolution + Treasury Auction Data

```bash
python openfigi.py treasury 912810SZ9 912810TA3 --json
python projects/apis/treasurydirect/treasurydirect.py api auctions --days 30
```

PRISM receives: Bloomberg tickers for auction CUSIPs + recent auction results. Links identifiers to supply data.

### Equity Resolution + SEC Filings

```bash
python openfigi.py equity AAPL --json
python projects/apis/sec_edgar/sec_edgar.py company-facts --ticker AAPL --json
```

PRISM receives: full FIGI set (FIGI, composite, share class) + company fundamentals. Cross-system instrument linkage.

### Bond Stack + Credit Spreads

```bash
python openfigi.py issuer-bonds INTC --maturity 2025-2035 --json
python projects/apis/nyfed/nyfed.py rates --json
```

PRISM receives: issuer bond universe with coupon/maturity + current risk-free reference rates. Basis for credit spread estimation.

### Capital Structure + Bank Health

```bash
python openfigi.py capital-structure JPM --json
python projects/apis/fdic/fdic.py recipe bank-stress --json
```

PRISM receives: full capital stack (equity + bonds + pfds + loans) + bank-level stress indicators. Capital adequacy context.

### Treasury Universe + Funding Conditions

```bash
python openfigi.py treasury-universe --maturity 2025-2030 --type notes --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: outstanding Treasury supply by maturity + overnight rate complex. Supply vs funding conditions.

### Sector Scan + Positioning

```bash
python openfigi.py sector-scan --list banks --json
python projects/apis/nyfed/nyfed.py pd-positions --count 24 --json
```

PRISM receives: bank bond stack sizes + primary dealer net positions. Credit supply vs dealer inventory.

### Options + Earnings Calendar

```bash
python openfigi.py options AAPL --expiry-start 2026-04-01 --expiry-end 2026-05-31 --json
python projects/apis/sec_edgar/sec_edgar.py filings --ticker AAPL --type 10-Q --json
```

PRISM receives: options chain around earnings + filing dates. For event-driven derivatives analysis.

### Futures Curve + FOMC Dates

```bash
python openfigi.py futures ED --json
python openfigi.py futures ZN --json
```

PRISM receives: Eurodollar/Treasury futures term structure. For rate expectations extraction and FOMC meeting pricing.

### MBS Universe + Prepayment Context

```bash
python openfigi.py mbs FNMA --maturity 2025-2035 --json
python projects/apis/nyfed/nyfed.py rates --json
```

PRISM receives: agency MBS pool identifiers + current rate environment. For prepayment speed estimation context.


## Setup

1. `pip install requests`
2. Optional: `export OPENFIGI_API_KEY=your_key` (higher rate limits)
3. Test: `python openfigi.py equity AAPL`
4. Full test: `python openfigi.py capital-structure INTC`


## Architecture

```
openfigi.py
  Constants       BASE_URL, ID_TYPES (25+), ENUM_KEYS, MARKET_SECTORS, ISSUER_LISTS (6)
  Auto-Detect     _detect_id_type() -- ISIN/CUSIP/SEDOL/FIGI/ticker classification
  Ticker Parser   _parse_bond_ticker(), _parse_maturity_year(), _fmt_coupon()
  HTTP            _post(), _get() with rate limiting, retries, 429 handling
  Core API        api_map(), api_map_single(), api_search(), api_filter(), api_enum_values()
  Display         _display_instruments(), _display_bond_table(), _display_mapping_result()
  Sector Search   _search_sector() -- generic sector-filtered search (used by 6 asset-class commands)
  Analytical      _fetch_issuer_bonds() with mega-issuer maturity chunking + FIGI dedup
  Commands (33):
    Mapping (4):      map, batch, batch-file, portfolio
    Search (2):       search, filter
    Lookups (6):      equity, bond, treasury-cusips, cross-ref, figi-lookup, global-listings
    Credit (9):       issuer-bonds, capital-structure, maturity-profile, compare-issuers,
                      treasury-universe, sector-scan, preferred, loans, issuer-universe
    Derivatives (3):  options, futures, derivatives
    Asset Class (6):  mbs, munis, fx, commodity, index, money-market
    Exchange (1):     exchange-scan
    Reference (2):    enums, id-types
  Interactive     33-item menu -> interactive wrappers with prompts
  Argparse        33 subcommands, all with --json and --export
```

API endpoints:
```
POST /v3/mapping          -> batch identifier resolution (primary endpoint)
POST /v3/search           -> keyword search (paginated via next cursor)
POST /v3/filter           -> filtered search (alphabetical by FIGI, with total)
GET  /v3/mapping/values/  -> enum value reference (idType, exchCode, etc.)
```

Rate limit management:
```
cmd_*() -> api_*() -> _post()/_get() -> _rate_wait() -> SESSION.post/get()
                                         |
                                         +-- Tracks _last_request_time
                                         +-- Enforces min interval between requests
                                         +-- Handles 429 with ratelimit-reset header
                                         +-- Chunks batches into MAX_JOBS per request

Overflow handling (>15k results):
  Bonds:     chunks by 1-year maturity windows
  Options:   chunks by quarterly expiration windows
  Futures:   chunks by 1-year expiration windows
  MBS:       chunks by 1-year maturity windows
  All:       deduplicates by FIGI after reassembly
```
