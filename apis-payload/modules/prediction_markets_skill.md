# Prediction Markets (Kalshi + Polymarket)

Scripts:
- `projects/apis/prediction_markets/prediction_markets.py` (operational: briefings, time series, change detection)
- `projects/apis/prediction_markets/universe.py` (structural: landscape analysis, volume distributions)

Kalshi: `https://api.elections.kalshi.com/trade-api/v2` (public, ~30 req/s)
Polymarket: `https://gamma-api.polymarket.com` + `https://clob.polymarket.com` (public)
Auth: None required
Dependencies: `requests`


## Triggers

Use for: crowd-implied event probabilities (Fed cuts, geopolitical outcomes, elections), change detection (what repriced since last snapshot), probability time series (daily/hourly), volume-ranked state of the world, prediction market landscape structure, macro-filtered universe analysis, scenario calibration weights.

Not for: historical economic data series (FRED/Haver), financial market prices (GS Market Data), company fundamentals (EDGAR), banking data (FDIC), Treasury auctions (TreasuryDirect), resolved/settled markets with no active trading.


## Data Catalog

### Focus Presets

| Preset | Description |
|--------|-------------|
| `all` | Full state of the world (default) |
| `macro` | Fed, inflation, trade, energy, financial markets |
| `fed` | Federal Reserve / monetary policy |
| `iran` | Iran / Middle East conflict |
| `russia` | Russia / Ukraine conflict |
| `china` | China / Taiwan |
| `israel` | Israel / Gaza / Lebanon |
| `elections` | Elections worldwide |
| `trump` | Trump administration policy |
| `crypto` | Crypto / digital assets |
| `energy` | Energy / commodities |
| `markets` | Financial markets |
| `movers` | Biggest movers only (what changed) |

### Topic Buckets (Scraper)

Federal Reserve & Monetary Policy, Inflation & Economic Data, Geopolitics: Iran/Middle East, Geopolitics: Russia/Ukraine, Geopolitics: China/Taiwan, Trade & Tariffs, US Politics & Elections, US Policy: Trump Administration, Crypto & Digital Assets, Energy & Commodities, Technology & AI, Nuclear, Financial Markets.

### Topic Buckets (Universe -- 17 buckets)

Federal Reserve & Monetary Policy, Inflation & Economic Data, Trade & Tariffs, US Politics & Elections, US Policy: Executive Branch, Geopolitics: Iran & Middle East, Geopolitics: Russia & Ukraine, Geopolitics: China & Taiwan, Crypto & Digital Assets, Energy & Commodities, Financial Markets, Climate & Environment, Technology & AI, Global & Misc Geopolitics, Fiscal & Debt, Health & Pandemic, Other / Uncategorized.

### Macro Keyword Filter

Only events matching these keywords pass macro relevance filtering:

```
fed, fomc, rate, inflation, cpi, gdp, recession, tariff, trade, china,
iran, russia, ukraine, war, oil, opec, nato, nuclear, sanctions, ceasefire,
trump, biden, election, congress, debt ceiling, treasury, yield, s&p,
nasdaq, bitcoin, crypto, unemployment, jobs, nonfarm, pmi, ism, default,
shutdown, stimulus, qe, qt, israel, gaza, hamas, hezbollah, taiwan,
ai, regulation, antitrust, bank, supreme court, impeach, indictment
```

### Output Files

| Output | Location | Format |
|--------|----------|--------|
| Context snapshot | `briefings/CONTEXT.md` | Light markdown: probs + 1d deltas (~2-4K tokens) |
| Full briefing | `briefings/LATEST.md` | Full markdown with daily time series CSV per event (~40-50K tokens) |
| Briefing JSON | `briefings/briefing_{ts}.json` | JSON: full briefing with histories + movers |
| Event snapshot | `data/event_snapshot_{ts}.json` | JSON: event-level aggregation |
| Latest snapshot | `data/_latest_event_snapshot.json` | Most recent event snapshot (used for diffing) |
| Snapshots | `data/snapshot_{ts}.json` | Market-level raw snapshot |
| Histories | `data/histories_{ts}.json` | Price time series per market |
| Timeline | `data/timeline_{ts}.json` | Date-indexed event timeline |
| Universe cache | `data/_universe_cache.json` | Cached universe pull (both platforms) |

### Core Concepts

| Concept | Meaning |
|---------|---------|
| Event | A question with one or more outcome markets |
| Market | A single tradable contract within an event |
| YES price | Implied probability (0.0-1.0). Price 0.72 = 72% crowd-implied chance |
| Volume | Total USD traded. Higher = more attention = higher signal quality |
| Open interest | Outstanding contracts. Current exposure, not cumulative |
| Salience | volume * |max probability change| -- ranks what changed |
| Focus preset | Topic filter applied to briefing rendering |


## Trading Engine

**Script**: `trading/pm_trading.py`
**Ontology**: `trading/pm_ontology.json`
**Skills**: `trading/skills/` (4 skills: fundamentals, dislocation, conditional, expression)

The trading engine maps PM events to macro fundamentals, detects cross-market dislocations, and audits conditional probability consistency. Requires `FRED_API_KEY` env var for full indicator coverage; NYFED and PM data work without keys.

```bash
python trading/pm_trading.py                                  # Interactive mode (full menu)
python trading/pm_trading.py fundamental --scan               # Fundamental scan: indicator-based probability estimates
python trading/pm_trading.py fundamental --category recession  # Scan one ontology category
python trading/pm_trading.py fundamental --event "fed rate"    # Single event analysis
python trading/pm_trading.py dislocation --scan               # PM vs real-market dislocation detection
python trading/pm_trading.py conditional --scan               # Multi-event conditional probability audit
python trading/pm_trading.py dashboard --top 10 --format json  # Aggregated signal dashboard
python trading/pm_trading.py ontology --list                  # Browse ontology categories
python trading/pm_trading.py ontology --coverage              # Coverage: which PM events map to which categories
```

Ontology categories: `fed_rate_decision`, `recession`, `inflation`, `employment`, `trade_tariffs`, `iran_conflict`, `russia_ukraine`, `china_taiwan`, `oil_energy`, `banking_stress`, `government_shutdown`, `debt_ceiling`, `elections`, `crypto`.


## CLI Recipes

### prediction_markets.py (Operational -- 12 commands)

All commands support `--format json|csv` where noted.

#### Autopilot & Rendering

```bash
# Full autopilot: scrape both sources, aggregate events, fetch daily time series,
# diff against previous run, produce volume-ranked briefing
python prediction_markets.py autopilot
python prediction_markets.py autopilot --focus all --max-histories 60 --days-back 90
python prediction_markets.py autopilot --focus macro
python prediction_markets.py autopilot --focus macro --max-histories 40
python prediction_markets.py autopilot --focus fed
python prediction_markets.py autopilot --focus iran --max-histories 30 --days-back 180
python prediction_markets.py autopilot --focus movers
python prediction_markets.py autopilot --min-volume 10000 --top-n 100 --format json

# Re-render existing briefing JSON to markdown with different focus
python prediction_markets.py render
python prediction_markets.py render --focus macro
python prediction_markets.py render --focus iran
python prediction_markets.py render --focus fed
python prediction_markets.py render --focus movers
python prediction_markets.py render --briefing-file briefings/briefing_20260412_1400.json --focus crypto
```

#### Data Collection

```bash
# Full scrape: events + price history + state-of-world + timeline
python prediction_markets.py full-pull
python prediction_markets.py full-pull --days-back 90 --max-histories 50
python prediction_markets.py full-pull --days-back 180 --max-histories 100 --min-volume 1000
python prediction_markets.py full-pull --format csv

# Quick snapshot: current probabilities only (no history)
python prediction_markets.py snapshot
python prediction_markets.py snapshot --min-volume 5000
python prediction_markets.py snapshot --min-volume 1000 --format csv
```

#### Source-Specific Browsing

```bash
# Kalshi events
python prediction_markets.py kalshi-events
python prediction_markets.py kalshi-events --status open
python prediction_markets.py kalshi-events --status closed --format json

# Kalshi series by category
python prediction_markets.py kalshi-series

# Polymarket events
python prediction_markets.py polymarket-events
python prediction_markets.py polymarket-events --min-volume 5000
python prediction_markets.py polymarket-events --min-volume 1000 --format csv
```

#### Analysis

```bash
# Regenerate state-of-world from cached data
python prediction_markets.py state-of-world
python prediction_markets.py state-of-world --snapshot-file data/snapshot_20260412.json --histories-file data/histories_20260412.json

# Regenerate timeline from cached history data
python prediction_markets.py timeline
python prediction_markets.py timeline --histories-file data/histories_20260412.json

# Price history for a specific market
python prediction_markets.py price-history --source kalshi --market-id FEDRATECUT-26JUN
python prediction_markets.py price-history --source kalshi --market-id FEDRATECUT-26JUN --days-back 180
python prediction_markets.py price-history --source polymarket --market-id TOKEN_ID_HERE --days-back 90

# Search markets by keyword
python prediction_markets.py search --query "fed rate"
python prediction_markets.py search --query "fed rate" --source both
python prediction_markets.py search --query "iran" --source kalshi
python prediction_markets.py search --query "recession" --source polymarket
python prediction_markets.py search --query "tariff" --source both

# Time series deep dive (hourly or daily) with shock detection, regime shifts, volatility
python prediction_markets.py time-series --source kalshi --market-id FEDRATECUT-26JUN --granularity hourly --days-back 90
python prediction_markets.py time-series --source kalshi --market-id FEDRATECUT-26JUN --granularity daily --days-back 180
python prediction_markets.py time-series --source polymarket --market-id TOKEN_ID --granularity hourly
# From cached histories (daily only)
python prediction_markets.py time-series --query "iran" --histories-file data/histories_latest.json
python prediction_markets.py time-series --query "fed" --histories-file data/histories_latest.json --granularity daily
```

### universe.py (Structural -- 6 commands)

All commands support `--cache` to skip the ~30-second API pull and use locally cached data.

```bash
# Full universe overview: event/market counts, volumes, distributions,
# concentration metrics, Gini, category breakdowns for both platforms
python universe.py overview
python universe.py overview --cache

# Macro-filtered state: 17 topic buckets with per-bucket top markets,
# volume distribution, concentration
python universe.py macro
python universe.py macro --cache
python universe.py macro --cache --top-n 40
python universe.py macro --cache --top-n 100

# Deep dive on volume skew: Kalshi vs Polymarket vs combined Gini,
# percentiles, threshold tables, concentration curves
python universe.py distribution
python universe.py distribution --cache

# Top N markets by volume, split by platform, optionally macro-filtered
python universe.py top
python universe.py top --cache -n 50
python universe.py top --cache -n 100 --macro
python universe.py top --cache -n 25

# Category/tag breakdown by volume for each platform
python universe.py categories
python universe.py categories --cache

# Export full universe or macro-filtered subset as JSON
python universe.py export
python universe.py export --cache
python universe.py export --cache --macro
```


## Python Recipes

### prediction_markets.py

```python
import subprocess, json, glob

# Run autopilot and read the full briefing
subprocess.run(
    "python projects/apis/prediction_markets/prediction_markets.py autopilot --focus macro --max-histories 40",
    shell=True, capture_output=True)
with open("projects/apis/prediction_markets/briefings/LATEST.md") as f:
    full_briefing = f.read()

# Run macro-only autopilot
subprocess.run(
    "python projects/apis/prediction_markets/prediction_markets.py autopilot --focus fed",
    shell=True, capture_output=True)

# Read the light context snapshot (what get_context loads, ~2-4K tokens)
with open("projects/apis/prediction_markets/briefings/CONTEXT.md") as f:
    context = f.read()

# Read briefing JSON for programmatic analysis
briefing_dir = "projects/apis/prediction_markets/briefings"
latest_json = sorted(glob.glob(f"{briefing_dir}/briefing_*.json"))[-1]
with open(latest_json) as f:
    briefing = json.load(f)

# Extract daily time series for a topic from briefing JSON
for ek, hist in briefing.get("histories", {}).items():
    if "iran" in ek.lower() or "iran" in hist.get("market_title", "").lower():
        print(f"{hist['market_title']}: {hist['first_price']:.0%} -> {hist['last_price']:.0%}")
        for move in hist["biggest_moves"]:
            print(f"  {move['delta']:+.0%} on {move['date']}")

# Extract outcome distributions (e.g. Fed rate cuts)
for entry in briefing["what_the_world_is_pricing"]:
    if "fed" in entry["event"].lower() and entry["market_count"] > 3:
        for m in entry["top_markets"]:
            print(f"  {m['probability']:.0%}  {m['title']}")

# Search for a specific topic
result = subprocess.run(
    'python projects/apis/prediction_markets/prediction_markets.py search --query "tariff" --source both',
    shell=True, capture_output=True, text=True)
print(result.stdout)

# Hourly time series deep dive
result = subprocess.run(
    'python projects/apis/prediction_markets/prediction_markets.py time-series --source kalshi --market-id FEDRATECUT-26JUN --granularity hourly --days-back 90',
    shell=True, capture_output=True, text=True)
print(result.stdout)

# Read daily series from briefing JSON
for ek, hist in briefing.get("histories", {}).items():
    daily = hist.get("daily", [])
    if daily:
        print(f"{hist['market_title']}: {len(daily)} daily points")
        for pt in daily[-7:]:
            print(f"  {pt['date']}: {pt['price']:.2%}")
```

### universe.py

```python
import subprocess

# Full universe overview
subprocess.run("python projects/apis/prediction_markets/universe.py overview --cache",
    shell=True)

# Macro-filtered state
subprocess.run("python projects/apis/prediction_markets/universe.py macro --cache --top-n 30",
    shell=True)

# Export macro-filtered universe as JSON
subprocess.run("python projects/apis/prediction_markets/universe.py export --cache --macro",
    shell=True)
```

### universe.py (Programmatic Import)

```python
import sys
sys.path.insert(0, "projects/apis/prediction_markets")
from universe import (pull_universe, filter_macro, compute_stats,
                      compute_topic_breakdown, classify_topic)

# Load universe (from cache or fresh pull)
k_markets, p_markets = pull_universe(use_cache=True)
all_markets = k_markets + p_markets

# Filter to macro-relevant
macro = filter_macro(all_markets)

# Per-topic volume breakdown
for bucket in compute_topic_breakdown(macro):
    print(f"{bucket['topic']}: {bucket['markets']} mkts, ${bucket['total_volume']:,.0f}")

# Find all Iran-related markets with >$1M volume
iran = [m for m in macro
        if classify_topic(m) == "Geopolitics: Iran & Middle East"
        and m["volume"] > 1_000_000]
for m in sorted(iran, key=lambda x: -x["volume"]):
    print(f"  {m['yes_price']:.0%} | ${m['volume']:,.0f} | [{m['source'][:4]}] {m['title']}")

# Summary statistics
stats = compute_stats(macro)
print(f"Macro markets: {stats['count']:,}, Volume: ${stats['total_volume']:,.0f}, Gini: {stats['gini']:.3f}")
```

### Direct API Access

```python
import requests

# Kalshi: get all open events
kalshi = requests.get("https://api.elections.kalshi.com/trade-api/v2/events",
    params={"limit": 200, "status": "open", "with_nested_markets": "true"}).json()

# Polymarket: get active events sorted by 24h volume
poly = requests.get("https://gamma-api.polymarket.com/events",
    params={"limit": 100, "active": "true", "order": "volume_24hr",
            "ascending": "false"}).json()
```


## Composite Recipes

### Morning Macro Briefing

```bash
python prediction_markets.py autopilot --focus macro --max-histories 40
```

PRISM receives: volume-ranked macro events with current probabilities, 1d deltas, daily time series CSV per event (90 data points each), biggest single-day moves, outcome distributions, topic-clustered view, salience-ranked movers since last snapshot.

### Fed Policy Deep Dive

```bash
python prediction_markets.py autopilot --focus fed --max-histories 20
python prediction_markets.py search --query "fed rate" --source both
```

PRISM receives: all Fed-related events with probabilities + daily trajectories, searchable list of all Fed markets across both platforms with prices and volume.

### Geopolitical Surveillance

```bash
python prediction_markets.py autopilot --focus iran --max-histories 30
python prediction_markets.py search --query "iran" --source both
python prediction_markets.py search --query "israel" --source both
```

PRISM receives: Iran/Middle East events with trajectory data, full searchable market list for both Iran and Israel topics.

### Change Detection (What Repriced?)

```bash
python prediction_markets.py autopilot --focus movers
```

PRISM receives: salience-ranked movers (volume * |max probability change|). High salience = big move in a market people care about. New events flagged with [NEW].

### Specific Market Time Series

```bash
python prediction_markets.py time-series --source kalshi --market-id FEDRATECUT-26JUN --granularity hourly --days-back 90
```

PRISM receives: raw CSV (timestamp, price) + KEY STATS + VOLATILITY PROFILE + SHOCKS (sigma-scored) + REGIME SHIFTS (sustained level changes) + BIGGEST MOVES. ~12K tokens per market.

### Landscape Structure

```bash
python universe.py overview --cache
python universe.py macro --cache --top-n 40
```

PRISM receives: full universe metrics (event/market counts, volumes, Gini, zero-volume %, concentration curves) for Kalshi and Polymarket separately, then macro-filtered view across 17 topic buckets with top markets per bucket.

### Event-Window Probability Tracking

```bash
# Before event (run autopilot to capture baseline)
python prediction_markets.py autopilot --focus macro

# After event (run again, diff happens automatically)
python prediction_markets.py autopilot --focus macro
```

PRISM receives: both snapshots with automatic diffing -- probability deltas, new events, salience ranking of what moved between the two runs.


## Cross-Source Recipes

### Prediction Markets + Fed Funds Pricing

```bash
python prediction_markets.py autopilot --focus fed
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: crowd-implied Fed cut/hike probabilities + actual overnight rate complex. Calibrates prediction market pricing against realized funding conditions.

### Prediction Markets + Macro Data Trajectory

```bash
python prediction_markets.py autopilot --focus macro --max-histories 40
python projects/apis/fred/fred.py series CPIAUCSL --obs 24 --json
python projects/apis/fred/fred.py series UNRATE --obs 24 --json
```

PRISM receives: crowd-implied recession/inflation/Fed probabilities + actual CPI and unemployment trajectories. Compare what the crowd expects vs what the data says.

### Prediction Markets + Treasury Supply

```bash
python prediction_markets.py search --query "debt ceiling" --source both
python projects/apis/treasury/treasury.py get dts --json
```

PRISM receives: debt ceiling market probabilities + TGA cash flows. Fiscal risk pricing vs actual fiscal dynamics.

### Prediction Markets + Rates Positioning

```bash
python prediction_markets.py autopilot --focus fed
python projects/apis/cftc/cftc.py rates --json
```

PRISM receives: crowd-implied rate cut probabilities + net speculative SOFR futures positioning. Directional bets vs prediction market consensus.

### Prediction Markets + Cross-Border Flows

```bash
python prediction_markets.py search --query "china" --source both
python prediction_markets.py search --query "tariff" --source both
python projects/apis/bis/bis.py lbs --json
```

PRISM receives: China/tariff event probabilities + BIS cross-border banking statistics. Geopolitical risk pricing vs actual capital flow data.

### Prediction Markets + Energy

```bash
python prediction_markets.py autopilot --focus energy
python projects/apis/electricity/electricity.py dashboard --json
```

PRISM receives: energy/commodity event probabilities + real-time electricity generation mix and demand. Energy market sentiment vs physical market reality.


## Setup

1. No API key required
2. `pip install requests`
3. Test scraper: `python prediction_markets.py search --query "fed" --source both`
4. Test universe: `python universe.py overview --cache` (after first run caches data)
5. Full test: `python prediction_markets.py autopilot --focus macro --max-histories 20`


## Architecture

```
prediction_markets.py (operational, 12 commands)
  Constants       KALSHI_BASE, POLY_GAMMA, POLY_CLOB, KALSHI_MACRO_CATEGORIES,
                  POLYMARKET_MACRO_TAGS, MACRO_KEYWORDS (60+), FOCUS_PRESETS (13)
  Kalshi API      kalshi_get(), kalshi_get_all_events(), kalshi_get_markets(),
                  kalshi_get_series_list(), kalshi_get_candlesticks(),
                  kalshi_extract_market_record()
  Polymarket API  poly_gamma_get(), poly_clob_get(), poly_get_all_events(),
                  poly_get_price_history(), poly_extract_market_record()
  Unified         build_unified_market_snapshot(), fetch_price_histories(),
                  build_state_of_world(), build_timeline(), aggregate_to_events(),
                  diff_event_snapshots(), build_volume_briefing()
  Time Series     _extract_series(), render_market_time_series(),
                  render_multi_market_time_series(), detect_shocks(),
                  detect_regime_shifts(), compute_volatility_profile()
  Autopilot       _cmd_autopilot() 6-step pipeline:
                    [1] Fetch Kalshi events (paginated)
                    [2] Fetch Polymarket events (paginated)
                    [3] Build snapshot + aggregate to events + macro filter
                    [4] Fetch time series for top N events (daily candlesticks)
                    [5] Diff against previous snapshot (change detection + salience)
                    [6] Build briefing + render markdown
  Rendering       render_markdown_briefing(), _render_event_block(),
                  _render_daily_csv()
  Commands (12)   autopilot, render, full-pull, snapshot, kalshi-events,
                  kalshi-series, polymarket-events, state-of-world, timeline,
                  price-history, search, time-series
  Interactive     12-item numbered menu
  Argparse        12 subcommands with --focus, --format, --days-back, etc.

universe.py (structural, 6 commands)
  Constants       KALSHI_MACRO_CATEGORIES, POLYMARKET_MACRO_TAGS,
                  MACRO_KEYWORDS (refined), MACRO_EXCLUSIONS, MEME_MARKET_PATTERNS,
                  MACRO_TOPIC_BUCKETS (17)
  API Pulls       pull_kalshi_events(), pull_polymarket_events()
  Normalization   normalize_kalshi(), normalize_polymarket()
  Filtering       _is_macro_relevant() 3-pass filter, filter_macro(), classify_topic()
  Statistics      compute_stats() (count, volume, Gini, concentration, thresholds),
                  compute_category_breakdown(), compute_topic_breakdown()
  Pipeline        pull_universe() -> normalize -> cache
  Commands (6)    overview, macro, distribution, top, categories, export
  Interactive     6-item numbered menu
  Argparse        6 subcommands, all with --cache
```

API endpoints:
```
Kalshi:
  GET  /trade-api/v2/events                    -> paginated events with nested markets
  GET  /trade-api/v2/markets                   -> market listing with filters
  GET  /trade-api/v2/series                    -> series by category
  GET  /trade-api/v2/markets/{ticker}/candlesticks -> OHLCV (1min/60min/1440min)

Polymarket:
  GET  gamma-api.polymarket.com/events         -> paginated events
  GET  gamma-api.polymarket.com/markets        -> individual markets
  GET  clob.polymarket.com/prices-history      -> token price history (configurable fidelity)
```
