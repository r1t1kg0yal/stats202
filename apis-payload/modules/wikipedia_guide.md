# Wikipedia Pageviews Data

Script: `projects/apis/wikipedia/wikipedia.py`
Base URL: `https://wikimedia.org/api/rest_v1/metrics/pageviews`
Docs: `https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/`
Auth: None required
Rate limit: ~200 req/s (script uses 0.5s sleep)
Coverage: English Wikipedia daily pageviews since ~2015, monthly going back further
Dependencies: `requests`


## Triggers

Use for: public attention/anxiety measurement on macro topics, composite fear gauge (z-score across crisis articles), viewership spike detection, cross-theme attention dashboards, article comparison, top-viewed articles on any date, long-run monthly history for regime comparison, aggregate Wikipedia traffic for normalization, arbitrary article lookups.

Not for: financial market data (use market APIs), structured economic data (use FRED), prediction market probabilities (use Kalshi/Polymarket), non-English Wikipedia, real-time pageviews (~24h lag), article text/NLP, social media sentiment (use GDELT), article edit history.


## Data Catalog

### Article Registry

7 curated themes, 36 articles total.

#### recession_growth (6)

Recession, Economic_growth, Great_Recession, Stagflation, Depression_(economics), Soft_landing_(economics)

#### inflation (5)

Inflation, Deflation, Hyperinflation, Consumer_price_index, Core_inflation

#### rates_fed (6)

Federal_Reserve, Interest_rate, Yield_curve, Quantitative_easing, Quantitative_tightening, Federal_funds_rate

#### markets (6)

Stock_market_crash, Bear_market, Bull_market, Volatility_(finance), Black_Monday_(1987), Dot-com_bubble

#### banking (5)

Bank_run, Bank_failure, Silicon_Valley_Bank, Credit_Suisse, Too_big_to_fail

#### geopolitical (5)

Tariff, Trade_war, Sanctions_(law), BRICS, Petrodollar_recycling

#### fiscal (3)

National_debt_of_the_United_States, Government_shutdown, Debt_ceiling

### Fear Gauge Methodology

Input: all articles from recession_growth + banking + markets themes (17 articles).

Pipeline:
1. Fetch 90-day lookback of daily pageviews per article
2. Compute trailing mean and std per article over full window
3. Compute recent 7-day mean per article
4. Per-article z-score: `(recent_7d_mean - trailing_mean) / trailing_std`
5. Composite z-score = simple average across scored articles

| Composite Z | Level | Meaning |
|-------------|-------|---------|
| > 1.0 | ELEVATED | Crisis-level public attention |
| > 0.5 | HIGH | Heightened anxiety |
| > -0.5 | NORMAL | Baseline attention |
| <= -0.5 | LOW | Below-average attention (complacency) |

### Spike Detection

Scans all 36 articles for abnormal viewership increases.

Pipeline:
1. Fetch 30-day lookback of daily pageviews per article
2. Compute trailing average over full window
3. Compute recent 7-day average
4. Ratio = recent_avg / trailing_avg
5. Report articles where ratio exceeds threshold (default: 2.0x)

### Pageview Item Fields

| Field | Description |
|-------|-------------|
| timestamp | YYYYMMDD00 format |
| views | Page view count |
| article | Article title |
| project | e.g. en.wikipedia.org |
| granularity | daily or monthly |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export.

### Single Article

```bash
# Pageviews for a specific article
python wikipedia.py article Recession --days 30
python wikipedia.py article Recession --days 60 --json
python wikipedia.py article Recession --days 30 --export csv
python wikipedia.py article Inflation --days 14 --json
python wikipedia.py article Tariff --days 90 --json
python wikipedia.py article Federal_Reserve --days 30 --json
python wikipedia.py article Bank_run --days 60 --json
python wikipedia.py article Stock_market_crash --days 30 --json
python wikipedia.py article Yield_curve --days 30 --json
python wikipedia.py article Quantitative_tightening --days 60 --json
python wikipedia.py article Trade_war --days 30 --json
python wikipedia.py article Debt_ceiling --days 14 --json

# Monthly granularity
python wikipedia.py article Recession --days 365 --granularity monthly --json
python wikipedia.py article Inflation --days 730 --granularity monthly --json
```

### Compare Articles

```bash
# Side-by-side comparison
python wikipedia.py compare Recession Inflation --days 30
python wikipedia.py compare Recession Inflation Tariff --days 60 --json
python wikipedia.py compare Recession Inflation Tariff Federal_Reserve --days 30 --json
python wikipedia.py compare Bank_run Silicon_Valley_Bank Credit_Suisse --days 90 --json
python wikipedia.py compare Stock_market_crash Bear_market Volatility_(finance) --days 30 --json
python wikipedia.py compare Tariff Trade_war Sanctions_(law) --days 60 --json
python wikipedia.py compare Quantitative_easing Quantitative_tightening --days 90 --json
python wikipedia.py compare Recession Stagflation Soft_landing_(economics) --days 30 --json
python wikipedia.py compare Recession Inflation --days 30 --export csv
```

### Theme

```bash
# All articles in a curated theme
python wikipedia.py theme recession_growth --days 30
python wikipedia.py theme recession_growth --days 30 --json
python wikipedia.py theme inflation --days 14 --json
python wikipedia.py theme rates_fed --days 30 --json
python wikipedia.py theme markets --days 30 --json
python wikipedia.py theme banking --days 60 --json
python wikipedia.py theme geopolitical --days 30 --json
python wikipedia.py theme fiscal --days 14 --json
python wikipedia.py theme recession_growth --days 30 --export csv
```

### Fear Gauge

```bash
# Composite fear index
python wikipedia.py fear-gauge
python wikipedia.py fear-gauge --json
python wikipedia.py fear-gauge --lookback 90 --recent 7 --json
python wikipedia.py fear-gauge --lookback 60 --recent 14 --json
python wikipedia.py fear-gauge --lookback 120 --recent 7 --json
python wikipedia.py fear-gauge --export json
```

### Dashboard & Spikes

```bash
# Full cross-theme attention snapshot
python wikipedia.py macro-dashboard
python wikipedia.py macro-dashboard --json
python wikipedia.py macro-dashboard --export json

# Find viewership spikes
python wikipedia.py spike-detect
python wikipedia.py spike-detect --json
python wikipedia.py spike-detect --threshold 2.0 --lookback 30 --recent 7 --json
python wikipedia.py spike-detect --threshold 1.5 --json
python wikipedia.py spike-detect --threshold 3.0 --json
python wikipedia.py spike-detect --threshold 1.5 --lookback 14 --recent 3 --json
python wikipedia.py spike-detect --export csv
```

### History & Aggregate

```bash
# Long monthly history for an article
python wikipedia.py history Recession --months 24
python wikipedia.py history Recession --months 36 --json
python wikipedia.py history Bank_run --months 36 --json
python wikipedia.py history Tariff --months 24 --json
python wikipedia.py history Inflation --months 48 --json
python wikipedia.py history Stock_market_crash --months 36 --json
python wikipedia.py history Federal_Reserve --months 24 --json
python wikipedia.py history Recession --months 24 --export csv

# Total English Wikipedia daily traffic
python wikipedia.py aggregate --days 30
python wikipedia.py aggregate --days 90 --json
python wikipedia.py aggregate --days 30 --granularity daily --json
python wikipedia.py aggregate --days 365 --granularity monthly --json
python wikipedia.py aggregate --days 30 --export csv
```

### Top Articles & Search

```bash
# Most-viewed Wikipedia articles on a specific day
python wikipedia.py top
python wikipedia.py top --date 2024-03-11
python wikipedia.py top --date 2024-03-11 --json
python wikipedia.py top --export json

# List all curated themes and articles
python wikipedia.py themes
python wikipedia.py themes --json

# Look up any arbitrary article (case-sensitive title)
python wikipedia.py search "Yield curve" --days 30
python wikipedia.py search "Yield curve" --days 30 --json
python wikipedia.py search "Silicon Valley Bank" --days 90 --json
python wikipedia.py search "Quantitative easing" --days 60 --json
python wikipedia.py search "Credit default swap" --days 30 --json
python wikipedia.py search "Inverted yield curve" --days 30 --json
```

### Export

```bash
# Export data from any command
python wikipedia.py export fear-gauge --export json
python wikipedia.py export article --article Recession --export csv
python wikipedia.py export macro-dashboard --export json
python wikipedia.py export spike-detect --export csv
python wikipedia.py export theme --theme recession_growth --export json
python wikipedia.py export compare --articles Recession Inflation --export csv
python wikipedia.py export history --article Recession --export json
python wikipedia.py export aggregate --export csv
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output | All commands |
| `--export csv\|json` | Export to file | Most commands |
| `--days N` | Lookback window in days (default: 30) | article, compare, theme, aggregate, search |
| `--months N` | Months of monthly data (default: 24) | history |
| `--granularity daily\|monthly` | Time granularity | article, aggregate |
| `--lookback N` | Trailing window days (default: 90/30) | fear-gauge, spike-detect |
| `--recent N` | Recent window days (default: 7) | fear-gauge, spike-detect |
| `--threshold X` | Spike ratio threshold (default: 2.0) | spike-detect |
| `--date YYYY-MM-DD` | Date for top articles (default: yesterday) | top |


## Python Recipes

### Core Fetchers

```python
from wikipedia import (
    _fetch_article_views, _fetch_multi_articles, _fetch_top,
    _fetch_aggregate, ARTICLE_REGISTRY, FEAR_THEMES, THEME_ORDER
)
from datetime import datetime, timedelta

end = datetime.now()
start = end - timedelta(days=30)

# Single article views
# Returns: list of {timestamp, views, article, project, granularity, access, agent}
items = _fetch_article_views("Recession", start, end)
items = _fetch_article_views("Recession", start, end, granularity="monthly")
items = _fetch_article_views("Inflation", start, end)
items = _fetch_article_views("Tariff", start, end)

# Multiple articles
# Returns: {article_name: [items]}
results = _fetch_multi_articles(["Recession", "Inflation", "Tariff"], start, end)
results = _fetch_multi_articles(ARTICLE_REGISTRY["banking"], start, end)

# Top articles on a day
# Returns: list of {article, views, rank}
top = _fetch_top(2024, 3, 11)

# Aggregate traffic
# Returns: list of {timestamp, views}
agg = _fetch_aggregate(start, end, granularity="daily")
```

### Fear Gauge

```python
from wikipedia import _build_fear_gauge

# Composite fear index
# Returns: {composite_z, article_count, scored_count, lookback_days, recent_days,
#           details: [{article, trailing_mean, trailing_std, recent_mean, z_score, status}]}
gauge = _build_fear_gauge(lookback_days=90, recent_days=7)
gauge = _build_fear_gauge(lookback_days=60, recent_days=14)

z = gauge["composite_z"]
for d in sorted(gauge["details"], key=lambda x: x.get("z_score", -999), reverse=True):
    if d["status"] == "ok":
        print(f"  {d['z_score']:+.2f}  {d['article']}")
```

### Spike Detection

```python
from wikipedia import _detect_spikes

# Find spiking articles
# Returns: list of {article, theme, trailing_avg, recent_avg, ratio} sorted by ratio desc
spikes = _detect_spikes(threshold=2.0, lookback_days=30, recent_days=7)
spikes = _detect_spikes(threshold=1.5)
spikes = _detect_spikes(threshold=3.0, lookback_days=14, recent_days=3)

for s in spikes:
    print(f"  {s['ratio']:.1f}x  [{s['theme']}]  {s['article']}")
```

### Dashboard

```python
from wikipedia import _build_dashboard, THEME_ORDER

# Cross-theme attention snapshot
# Returns: {theme: {name, avg_views, articles: [{article, avg, trend}]}}
stats = _build_dashboard()

for theme in THEME_ORDER:
    data = stats[theme]
    print(f"{data['name']}: {data['avg_views']:,.0f} avg views/day")
    for a in data["articles"]:
        print(f"  {a['article']}: {a['avg']:,.0f} ({a['trend']})")
```

### Command Functions

```python
from wikipedia import (
    cmd_article, cmd_compare, cmd_theme, cmd_top,
    cmd_fear_gauge, cmd_macro_dashboard, cmd_spike_detect,
    cmd_history, cmd_aggregate, cmd_themes, cmd_search
)

# All cmd_* functions accept as_json=True for JSON output
cmd_article(article="Recession", days=60, as_json=True)
cmd_article(article="Tariff", days=30, as_json=True)
cmd_compare(articles=["Recession", "Inflation", "Tariff"], days=30, as_json=True)
cmd_theme(theme="recession_growth", days=30, as_json=True)
cmd_theme(theme="banking", days=14, as_json=True)
cmd_top(date_str="2024-03-11", as_json=True)
cmd_fear_gauge(lookback=90, recent=7, as_json=True)
cmd_macro_dashboard(as_json=True)
cmd_spike_detect(threshold=2.0, as_json=True)
cmd_spike_detect(threshold=1.5, lookback=14, recent=3, as_json=True)
cmd_history(article="Recession", months=24, as_json=True)
cmd_aggregate(days=30, as_json=True)
cmd_themes(as_json=True)
cmd_search(article="Yield curve", days=30, as_json=True)

# With export
cmd_article(article="Recession", days=30, export_fmt="csv")
cmd_fear_gauge(export_fmt="json")
cmd_macro_dashboard(export_fmt="json")
```

### Subprocess

```python
import subprocess, json

result = subprocess.run(
    "python projects/apis/wikipedia/wikipedia.py fear-gauge --json",
    shell=True, capture_output=True, text=True)
gauge = json.loads(result.stdout)

result = subprocess.run(
    "python projects/apis/wikipedia/wikipedia.py compare Recession Inflation Tariff --days 60 --json",
    shell=True, capture_output=True, text=True)
data = json.loads(result.stdout)

result = subprocess.run(
    "python projects/apis/wikipedia/wikipedia.py macro-dashboard --json",
    shell=True, capture_output=True, text=True)
dashboard = json.loads(result.stdout)
```


## Composite Recipes

### Attention Snapshot

```bash
python wikipedia.py fear-gauge --json
python wikipedia.py macro-dashboard --json
python wikipedia.py spike-detect --threshold 1.5 --json
```

PRISM receives: composite z-score with per-article breakdown across 17 crisis articles, all 7 themes with per-theme average views and half-over-half trend, articles with recent/trailing ratio above 1.5x.

### Competing Narrative Analysis

```bash
python wikipedia.py compare Recession Inflation Tariff Federal_Reserve --days 60 --json
python wikipedia.py theme recession_growth --days 30 --json
python wikipedia.py theme geopolitical --days 30 --json
```

PRISM receives: 60-day daily views for key narrative articles (head-to-head comparison), full recession and geopolitical theme breakdowns showing which macro story dominates public attention.

### Event Detection

```bash
python wikipedia.py spike-detect --threshold 2.0 --lookback 30 --recent 7 --json
python wikipedia.py article {SPIKING_ARTICLE} --days 30 --json
python wikipedia.py theme {THEME_OF_SPIKE} --days 14 --json
```

PRISM receives: spiking articles with ratio, daily series for spiking article (shows spike onset date), theme context (whether spike is isolated or theme-wide).

### Historical Calibration

```bash
python wikipedia.py history Recession --months 36 --json
python wikipedia.py history Bank_run --months 36 --json
python wikipedia.py history Tariff --months 24 --json
python wikipedia.py history Stock_market_crash --months 36 --json
python wikipedia.py aggregate --days 90 --json
```

PRISM receives: 3-year monthly histories for key crisis articles (SVB Mar 2023, COVID Mar 2020, tariff 2018-19/2025 benchmarks), aggregate traffic for normalization.

### Full Fear Assessment

```bash
python wikipedia.py fear-gauge --lookback 90 --recent 7 --json
python wikipedia.py fear-gauge --lookback 90 --recent 14 --json
python wikipedia.py spike-detect --threshold 1.5 --json
python wikipedia.py theme banking --days 14 --json
python wikipedia.py theme recession_growth --days 14 --json
python wikipedia.py theme geopolitical --days 14 --json
```

PRISM receives: fear gauge at 7d and 14d recent windows (trend direction), spiking articles, per-theme detail for the three highest-signal themes.

### Banking Stress Check

```bash
python wikipedia.py theme banking --days 30 --json
python wikipedia.py compare Bank_run Bank_failure Silicon_Valley_Bank --days 60 --json
python wikipedia.py history Bank_run --months 24 --json
```

PRISM receives: full banking theme with daily views and trend, head-to-head banking article comparison, monthly Bank_run history for calibration against SVB episode peak.


## Cross-Source Recipes

### Attention + Prediction Markets

```bash
python wikipedia.py fear-gauge --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset recession --json
```

PRISM receives: public fear z-score + market-implied recession probability. Divergence between public panic and sophisticated pricing.

### Attention + Media Narrative

```bash
python wikipedia.py macro-dashboard --json
python projects/apis/gdelt/gdelt.py events --theme recession --json
```

PRISM receives: public attention levels (demand side) + media coverage intensity (supply side). When public exceeds media, narrative has penetrated mainstream.

### Attention + Positioning

```bash
python wikipedia.py fear-gauge --json
python wikipedia.py theme recession_growth --days 14 --json
python projects/apis/cftc/cftc.py rates --json
```

PRISM receives: public fear level + recession theme detail + speculative positioning. Public anxiety vs professional bets.

### Attention + Funding Stress

```bash
python wikipedia.py theme banking --days 30 --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: banking theme attention (Bank_run, SVB, Credit_Suisse) + actual overnight funding rates and RRP. Public banking fear vs observed stress indicators.

### Attention + Legislation

```bash
python wikipedia.py spike-detect --threshold 2.0 --json
python projects/apis/congress/congress.py search "tariff" --json
```

PRISM receives: spiking articles + active legislation. Legislative events trigger article spikes -- spike confirms public awareness.

### Attention + Consumer Data

```bash
python wikipedia.py fear-gauge --json
python wikipedia.py history Recession --months 12 --json
python projects/apis/fred/fred_client.py series UMCSENT --json
```

PRISM receives: fear gauge + 12-month recession article history + Michigan consumer sentiment. Wikipedia traffic leads consumer confidence by 4-6 weeks.

### Attention + Sanctions

```bash
python wikipedia.py theme geopolitical --days 30 --json
python projects/apis/ofac/ofac.py geo-focus --json
```

PRISM receives: geopolitical theme attention (Tariff, Trade_war, Sanctions) + SDN designation distribution. Public awareness vs actual sanctions activity.

### Attention + Energy

```bash
python wikipedia.py compare Tariff Trade_war --days 30 --json
python projects/apis/eia/eia.py petroleum --json
```

PRISM receives: trade/tariff public attention + petroleum supply data. Public trade fear vs physical commodity flows.


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python wikipedia.py themes` (no API calls)
4. API test: `python wikipedia.py article Recession --days 7`


## Architecture

```
wikipedia.py
  Constants       BASE_URL, ARTICLE_REGISTRY (7 themes, 36 articles),
                  THEME_NAMES, THEME_ORDER, FEAR_THEMES (3)
  HTTP            SESSION with User-Agent, _request() with 0.5s sleep
  Date Helpers    _api_date, _display_date, _days_ago, _parse_user_date
  Data Fetchers   _fetch_article_views, _fetch_multi_articles, _fetch_top,
                  _fetch_aggregate
  Analytics       _build_fear_gauge (z-score composite),
                  _detect_spikes (ratio threshold),
                  _build_dashboard (theme averages + trend)
  Commands (13)   article, compare, theme, top, fear-gauge, macro-dashboard,
                  spike-detect, history, aggregate, themes, search, export
  Interactive     12-item menu -> interactive wrappers with prompts
  Argparse        13 subcommands, all with --json and --export
```

API endpoints:
```
/per-article/{project}/{access}/{agent}/{article}/{granularity}/{start}/{end}
/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}
/top/{project}/{access}/{year}/{month}/{day}
```
