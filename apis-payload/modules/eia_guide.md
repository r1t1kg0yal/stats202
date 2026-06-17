# EIA Energy Data

Script: `projects/apis/eia/eia.py`
Base URL: `https://api.eia.gov/v2`
Auth: `EIA_API_KEY` env var (free at https://www.eia.gov/opendata/register.php)
Rate limit: ~0.15-0.2s between calls (polite usage)
Dependencies: `requests`


## Triggers

Use for: weekly petroleum status (WPSR), US crude/gasoline/distillate inventories, refinery utilization and crude inputs, natural gas storage (Lower-48), spot prices (WTI Cushing, Brent, Henry Hub), STEO short-term energy outlook forecasts, crude production/imports, API hierarchy browsing, generic EIA series history.

Not for: futures curves / forward structure (CME/ICE), OPEC production quotas (OPEC direct), pipeline flows / shipping (Kpler/Vortexa), LNG cargo tracking (Platts), electricity generation mix (use `electricity` module), refinery-specific margins (Nymex crack spreads), intraday commodity prices (exchange feeds), weather/degree-day data (NOAA), rig counts (Baker Hughes), strategic petroleum reserve policy (DOE announcements).


## Data Catalog

### SERIES_REGISTRY (14 Curated Series)

#### Petroleum -- Weekly (WPSR)

| Alias | EIA Series ID | Name | Unit | Freq | Route |
|-------|---------------|------|------|------|-------|
| `CRUDE_STOCKS` | `WCESTUS1` | US Crude Oil Stocks (excl. SPR) | thousand barrels | weekly | petroleum/sum/sndw |
| `GASOLINE_STOCKS` | `WGTSTUS1` | US Motor Gasoline Stocks | thousand barrels | weekly | petroleum/sum/sndw |
| `DISTILLATE_STOCKS` | `WDISTUS1` | US Distillate Fuel Oil Stocks | thousand barrels | weekly | petroleum/sum/sndw |
| `REFINERY_INPUTS` | `WCRFPUS2` | US Refinery Crude Inputs | thousand barrels/day | weekly | petroleum/sum/sndw |
| `REFINERY_UTIL` | `WPULEUS3` | US Refinery Utilization Rate | percent | weekly | petroleum/sum/sndw |
| `CRUDE_PRODUCTION` | `WCRFPUS2` | US Crude Production (weekly) | thousand barrels/day | weekly | petroleum/sum/sndw |
| `CRUDE_IMPORTS` | `WCEIMUS2` | US Crude Oil Imports | thousand barrels/day | weekly | petroleum/sum/sndw |
| `NET_IMPORTS` | `WTTNTUS2` | US Total Net Imports | thousand barrels/day | weekly | petroleum/sum/sndw |

#### Spot Prices -- Daily

| Alias | EIA Series ID | Name | Unit | Freq | Route |
|-------|---------------|------|------|------|-------|
| `WTI_SPOT` | `RWTC` | WTI Cushing Spot Price | $/barrel | daily | petroleum/pri/spt |
| `BRENT_SPOT` | `RBRTE` | Brent Spot Price | $/barrel | daily | petroleum/pri/spt |
| `HH_SPOT` | `RNGWHHD` | Henry Hub Natural Gas Spot | $/MMBtu | daily | natural-gas/pri/fut |

#### Natural Gas -- Weekly

| Alias | EIA Series ID | Name | Unit | Freq | Route |
|-------|---------------|------|------|------|-------|
| `NATGAS_STORAGE` | `NW2_EPG0_SWO_R48_BCF` | Lower-48 Working Gas in Storage | Bcf | weekly | natural-gas/stor/wkly |

#### STEO Forecasts -- Monthly

| Alias | EIA Series ID | Name | Unit | Freq | Route |
|-------|---------------|------|------|------|-------|
| `STEO_WTI` | `PAPR_WORLD` | STEO World Oil Price Forecast | $/barrel | monthly | steo |
| `STEO_CRUDE_PROD` | `COPR_US` | STEO US Crude Production Forecast | million barrels/day | monthly | steo |

### Grouped Constants

| Constant | Aliases |
|----------|---------|
| `WPSR_SERIES` | `CRUDE_STOCKS`, `GASOLINE_STOCKS`, `DISTILLATE_STOCKS`, `REFINERY_INPUTS`, `REFINERY_UTIL`, `CRUDE_PRODUCTION`, `CRUDE_IMPORTS`, `NET_IMPORTS` |
| `PRICE_SERIES` | `WTI_SPOT`, `BRENT_SPOT`, `HH_SPOT` |
| `VALID_PRICE_ALIASES` | `WTI_SPOT`, `BRENT_SPOT`, `HH_SPOT` |

### Return Fields -- Petroleum/WPSR/Prices Records

| Field | Type | Description |
|-------|------|-------------|
| `alias` | string | Series alias from SERIES_REGISTRY |
| `name` | string | Human-readable series name |
| `unit` | string | Unit of measurement |
| `period` | string | Observation date (YYYY-MM-DD) |
| `value` | float | Latest observed value |
| `prev` | float | Previous observation value |
| `change` | float | Week-over-week or day-over-day change |
| `pct_change` | float | Percent change (WPSR only) |

### Return Fields -- Inventory/Storage/History Records

| Field | Type | Description |
|-------|------|-------------|
| `period` | string | Observation date |
| `value` | float | Observed value |
| `change` | float | Change from prior period |

### Return Fields -- Refinery Records

| Field | Type | Description |
|-------|------|-------------|
| `period` | string | Observation date |
| `utilization_pct` | float | Refinery utilization rate (%) |
| `util_change` | float | Week-over-week utilization change (pp) |
| `crude_inputs_kbd` | float | Crude oil inputs (thousand barrels/day) |

### Return Fields -- STEO Records

| Field | Type | Description |
|-------|------|-------------|
| `period` | string | Forecast month (YYYY-MM) |
| `value` | float | Forecasted value |

### Return Fields -- Energy Snapshot Records

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Series name |
| `unit` | string | Unit of measurement |
| `period` | string | Observation date |
| `value` | float | Latest value |
| `change` | float | Change from prior observation |

### Return Fields -- Series Registry Records

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable name |
| `route` | string | EIA API route |
| `series` | string | EIA series ID |
| `unit` | string | Unit of measurement |
| `freq` | string | Frequency (daily, weekly, monthly) |

### Return Fields -- Browse Response

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Category name |
| `description` | string | Category description |
| `routes[]` | array | Child routes with id and name |
| `frequency[]` | array | Available frequencies |
| `facets[]` | array | Filterable facets |
| `data` | dict | Available data columns |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export (except `browse` which only supports `--json`).

### Petroleum -- Weekly Snapshot

```bash
# 6 key petroleum metrics: crude/gasoline/distillate stocks, refinery util, inputs, imports
python eia.py petroleum
python eia.py petroleum --json
python eia.py petroleum --export csv
python eia.py petroleum --export json
```

### Crude Oil Inventories

```bash
# Crude stocks (excl. SPR) with WoW change
python eia.py crude-stocks
python eia.py crude-stocks --weeks 52
python eia.py crude-stocks --weeks 104
python eia.py crude-stocks --weeks 26 --json
python eia.py crude-stocks --weeks 104 --export csv
```

### Natural Gas Storage

```bash
# Lower-48 working gas in storage with WoW change
python eia.py natgas-storage
python eia.py natgas-storage --weeks 52
python eia.py natgas-storage --weeks 104
python eia.py natgas-storage --weeks 26 --json
python eia.py natgas-storage --weeks 52 --export csv
```

### Spot Prices

```bash
# Latest WTI, Brent, Henry Hub with day-over-day change
python eia.py prices
python eia.py prices --json
python eia.py prices --export csv
```

### Price History

```bash
# Price history for a specific series over N days
# series choices: WTI_SPOT, BRENT_SPOT, HH_SPOT (default: WTI_SPOT)
python eia.py price-history
python eia.py price-history WTI_SPOT
python eia.py price-history WTI_SPOT --days 90
python eia.py price-history BRENT_SPOT --days 180
python eia.py price-history HH_SPOT --days 365
python eia.py price-history WTI_SPOT --days 90 --json
python eia.py price-history BRENT_SPOT --days 30 --export csv
```

### Refinery Data

```bash
# Utilization rate + crude inputs, merged by period
python eia.py refinery
python eia.py refinery --weeks 52
python eia.py refinery --weeks 104
python eia.py refinery --weeks 26 --json
python eia.py refinery --weeks 52 --export csv
```

### STEO Forecasts

```bash
# Short-Term Energy Outlook: WTI price + US crude production forecasts (up to 36 months)
python eia.py steo
python eia.py steo --json
python eia.py steo --export csv
python eia.py steo --export json
```

### Full WPSR

```bash
# All 8 WPSR series: latest + previous + WoW change + pct change
python eia.py wpsr
python eia.py wpsr --json
python eia.py wpsr --export csv
```

### Energy Snapshot Dashboard

```bash
# Combined dashboard: prices (WTI/Brent/HH), inventories (crude/gasoline/distillate),
# natgas storage, refinery utilization -- all with latest + change
python eia.py energy-snapshot
python eia.py energy-snapshot --json
python eia.py energy-snapshot --export csv
python eia.py energy-snapshot --export json
```

### Browse API Hierarchy

```bash
# Navigate EIA API tree: routes, frequencies, facets, data columns
python eia.py browse
python eia.py browse petroleum
python eia.py browse petroleum/pri/spt
python eia.py browse natural-gas/stor/wkly
python eia.py browse steo
python eia.py browse petroleum --json
```

### Series Registry

```bash
# List all 14 curated series with alias, EIA ID, name, freq, unit
python eia.py series
python eia.py series --json
python eia.py series --export csv
```

### Generic Series History

```bash
# Pull history for any alias in SERIES_REGISTRY
# series: any alias (default: CRUDE_STOCKS)
python eia.py history
python eia.py history CRUDE_STOCKS
python eia.py history CRUDE_STOCKS --periods 52
python eia.py history CRUDE_STOCKS --periods 104
python eia.py history GASOLINE_STOCKS --periods 52
python eia.py history REFINERY_UTIL --periods 26
python eia.py history NATGAS_STORAGE --periods 104
python eia.py history WTI_SPOT --periods 365
python eia.py history STEO_WTI --periods 36
python eia.py history CRUDE_STOCKS --periods 52 --json
python eia.py history NET_IMPORTS --periods 104 --export csv
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to CSV file | All commands except browse |
| `--export json` | Export to JSON file | All commands except browse |
| `--weeks N` | Number of weeks (default 52) | crude-stocks, natgas-storage, refinery |
| `--days N` | Number of days (default 90) | price-history |
| `--periods N` | Number of periods (default 52) | history |


## Python Recipes

### Petroleum Snapshot

```python
from eia import cmd_petroleum

# Latest 6 key petroleum metrics with WoW change
# Returns: list of dicts with alias, name, unit, period, value, prev, change
records = cmd_petroleum(as_json=True)
```

### Crude Oil Inventories

```python
from eia import cmd_crude_stocks

# N weeks of crude stocks (excl. SPR) with WoW change
# Returns: list of dicts with period, value, change
stocks = cmd_crude_stocks(weeks=52, as_json=True)
stocks = cmd_crude_stocks(weeks=104, as_json=True)
```

### Natural Gas Storage

```python
from eia import cmd_natgas_storage

# N weeks of Lower-48 working gas in storage with WoW change
# Returns: list of dicts with period, value, change
storage = cmd_natgas_storage(weeks=52, as_json=True)
storage = cmd_natgas_storage(weeks=104, as_json=True)
```

### Spot Prices

```python
from eia import cmd_prices, cmd_price_history

# Latest WTI, Brent, HH with day-over-day change
# Returns: list of dicts with alias, name, unit, period, value, change
prices = cmd_prices(as_json=True)

# Price history for a single series over N days
# alias: "WTI_SPOT" | "BRENT_SPOT" | "HH_SPOT" (default: "WTI_SPOT")
# Returns: list of dicts with period, value
wti = cmd_price_history(alias="WTI_SPOT", days=90, as_json=True)
brent = cmd_price_history(alias="BRENT_SPOT", days=180, as_json=True)
hh = cmd_price_history(alias="HH_SPOT", days=365, as_json=True)
```

### Refinery Data

```python
from eia import cmd_refinery

# N weeks of utilization + crude inputs merged by period
# Returns: list of dicts with period, utilization_pct, util_change, crude_inputs_kbd
refinery = cmd_refinery(weeks=52, as_json=True)
refinery = cmd_refinery(weeks=104, as_json=True)
```

### STEO Forecasts

```python
from eia import cmd_steo

# Short-Term Energy Outlook (up to 36 months)
# Returns: dict keyed by alias -> list of {period, value}
# Keys: STEO_WTI, STEO_CRUDE_PROD
steo = cmd_steo(as_json=True)
```

### Full WPSR

```python
from eia import cmd_wpsr

# All 8 WPSR series: latest + previous + WoW change + pct change
# Returns: list of dicts with alias, name, unit, period, value, prev, change, pct_change
wpsr = cmd_wpsr(as_json=True)
```

### Energy Snapshot Dashboard

```python
from eia import cmd_energy_snapshot

# Combined: prices, inventories, natgas storage, refinery util
# Returns: dict keyed by alias -> {name, unit, period, value, change}
# Keys: WTI_SPOT, BRENT_SPOT, HH_SPOT, CRUDE_STOCKS, GASOLINE_STOCKS,
#        DISTILLATE_STOCKS, NATGAS_STORAGE, REFINERY_UTIL
snapshot = cmd_energy_snapshot(as_json=True)
```

### Browse API Hierarchy

```python
from eia import cmd_browse

# Navigate EIA API tree
# Returns: dict with name, description, routes[], frequency[], facets[], data{}
root = cmd_browse(route="", as_json=True)
petroleum = cmd_browse(route="petroleum", as_json=True)
spot_prices = cmd_browse(route="petroleum/pri/spt", as_json=True)
natgas = cmd_browse(route="natural-gas/stor/wkly", as_json=True)
```

### Series Registry

```python
from eia import cmd_series

# List all 14 curated series
# Returns: dict keyed by alias -> {name, route, series, unit, freq}
registry = cmd_series(as_json=True)
```

### Generic Series History

```python
from eia import cmd_history

# Pull history for any alias in SERIES_REGISTRY
# alias: any key from SERIES_REGISTRY (default: "CRUDE_STOCKS")
# Returns: list of dicts with period, value, change
crude = cmd_history(alias="CRUDE_STOCKS", periods=52, as_json=True)
gasoline = cmd_history(alias="GASOLINE_STOCKS", periods=104, as_json=True)
util = cmd_history(alias="REFINERY_UTIL", periods=26, as_json=True)
steo_wti = cmd_history(alias="STEO_WTI", periods=36, as_json=True)
```


## Composite Recipes

### Morning Energy Check

```bash
python eia.py energy-snapshot --json
```

PRISM receives: latest WTI/Brent/HH spot prices with day-over-day change, crude/gasoline/distillate inventories with WoW change and build/draw direction, Lower-48 natgas storage with inject/withdraw direction, refinery utilization with WoW change.

### Weekly Petroleum Deep Dive

```bash
python eia.py wpsr --json
python eia.py crude-stocks --weeks 52 --json
python eia.py refinery --weeks 52 --json
```

PRISM receives: all 8 WPSR series with latest + previous + WoW change + pct change, 52-week crude stock history for seasonal comparison, 52-week refinery utilization and crude input history for throughput trends.

### Oil Price Assessment

```bash
python eia.py prices --json
python eia.py price-history WTI_SPOT --days 90 --json
python eia.py price-history BRENT_SPOT --days 90 --json
python eia.py steo --json
```

PRISM receives: latest WTI/Brent/HH spot levels, 90-day WTI and Brent price histories for recent trajectory, STEO world oil price forecast and US crude production forecast for forward view.

### Natural Gas Supply/Demand Check

```bash
python eia.py natgas-storage --weeks 52 --json
python eia.py price-history HH_SPOT --days 180 --json
```

PRISM receives: 52-week Lower-48 storage history with inject/withdraw WoW changes, 180-day Henry Hub spot price history for price-storage relationship.

### Inventory Regime Assessment

```bash
python eia.py crude-stocks --weeks 104 --json
python eia.py history GASOLINE_STOCKS --periods 104 --json
python eia.py history DISTILLATE_STOCKS --periods 104 --json
python eia.py natgas-storage --weeks 104 --json
```

PRISM receives: 2-year histories for crude, gasoline, distillate, and natgas storage for seasonal range comparison and deviation detection.

### Supply-Side Deep Dive

```bash
python eia.py history CRUDE_PRODUCTION --periods 52 --json
python eia.py history CRUDE_IMPORTS --periods 52 --json
python eia.py history NET_IMPORTS --periods 52 --json
python eia.py refinery --weeks 52 --json
```

PRISM receives: 52-week production, import, and net import histories, refinery utilization and throughput for domestic supply chain tracking.

### STEO Forward View

```bash
python eia.py steo --json
python eia.py prices --json
python eia.py crude-stocks --weeks 26 --json
```

PRISM receives: STEO price and production forecasts (up to 36 months forward), current spot prices for forecast vs actuals comparison, recent inventory trajectory for near-term context.


## Cross-Source Recipes

### Energy Prices + Macro Rates

```bash
python eia.py prices --json
python projects/apis/nyfed/nyfed.py rates --json
```

PRISM receives: latest energy spot prices + overnight funding rates. Commodity-rate co-movement.

### Oil Inventories + Positioning

```bash
python eia.py wpsr --json
python projects/apis/cftc/cftc.py energy --json
```

PRISM receives: WPSR physical inventory data + net speculative futures positioning. Physical vs financial alignment.

### Energy Snapshot + Treasury Flows

```bash
python eia.py energy-snapshot --json
python projects/apis/treasury/treasury.py get dts --json
```

PRISM receives: energy market levels + Treasury cash flows. Fiscal/energy cross-read.

### Natgas Storage + Electricity

```bash
python eia.py natgas-storage --weeks 52 --json
python projects/apis/electricity/electricity.py generation --json
```

PRISM receives: natural gas storage trajectory + electricity generation mix. Gas burn demand context.

### WTI Price + Tariffs

```bash
python eia.py price-history WTI_SPOT --days 180 --json
python projects/apis/tariffs/tariffs.py snapshot --json
```

PRISM receives: WTI price history + current tariff snapshot. Trade policy impact on energy flows.

### STEO Forecast + Fed Policy

```bash
python eia.py steo --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: EIA energy production/price forecasts + market-implied Fed path. Energy supply outlook vs monetary regime.

### Oil Supply + Global Credit

```bash
python eia.py history CRUDE_PRODUCTION --periods 52 --json
python projects/apis/bis/bis.py credit --json
```

PRISM receives: US crude production trajectory + BIS global credit aggregates. Capex/credit cycle context for production trends.


## Setup

1. Register for a free API key at https://www.eia.gov/opendata/register.php
2. `export EIA_API_KEY=your_key_here`
3. `pip install requests`
4. Test: `python eia.py prices`
5. Full test: `python eia.py energy-snapshot`


## Architecture

```
eia.py
  Constants       BASE_URL, MAX_ROWS (5000), SERIES_REGISTRY (14),
                  WPSR_SERIES (8), PRICE_SERIES (3), VALID_PRICE_ALIASES (3),
                  CATEGORY_ORDER, CATEGORY_NAMES
  HTTP            _request() with retries (3x), rate limit backoff (429 -> 5s*attempt),
                  _build_data_url() with facets, sort, pagination, date range
  Data Fetchers   _fetch_series, _fetch_series_paginated (offset-based, up to MAX_ROWS),
                  _fetch_multi_latest (2 obs per series, 0.15s spacing),
                  _fetch_browse (API tree navigation)
  Commands (12)   petroleum, crude-stocks, natgas-storage, prices, price-history,
                  refinery, steo, browse, series, history, wpsr, energy-snapshot
  Interactive     12-item menu -> interactive wrappers with prompts
  Argparse        12 subcommands, all with --json; all except browse with --export
```

API URL pattern:
```
{BASE_URL}/{route}/data?api_key={key}&frequency={freq}&data[]=value
    &facets[{facet_key}][]={series_id}
    &sort[0][column]=period&sort[0][direction]=desc
    &length={limit}&offset={offset}
    &start={start}&end={end}
```

API routes used:
```
petroleum/sum/sndw      -> WPSR weekly petroleum data (8 series)
petroleum/pri/spt       -> Petroleum spot prices (WTI, Brent)
natural-gas/stor/wkly   -> Weekly natural gas storage (Lower-48)
natural-gas/pri/fut     -> Natural gas spot prices (Henry Hub)
steo                    -> Short-Term Energy Outlook forecasts
{any route}             -> Browse hierarchy (routes, facets, frequencies)
```
