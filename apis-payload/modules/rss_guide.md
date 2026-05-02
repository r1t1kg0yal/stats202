# RSS/Atom Feed Aggregator -- Macro / Policy / Research

Script: `projects/apis/rss/rss.py`
Sources: 20 curated RSS/Atom feeds across 5 categories
Auth: None required
Rate limit: Sequential fetch with 20s timeout per feed
Dependencies: `feedparser`, `requests`


## Triggers

Use for: Fed regional bank research blogs, think tank policy commentary, NBER working paper releases, central bank speeches and press releases, macro analysis blogs, cross-category keyword search across all feeds, daily digests, headline scanning, PRISM context ingestion via export-digest.

Not for: actual data series (FRED, BLS, BEA), market prices or yields (Bloomberg, Refinitiv), futures positioning (CFTC), official policy statements / minutes text (Fed Board website), repo/rate data (NY Fed Markets API), PDF full-text extraction (use paper2md), real-time news (Reuters, Bloomberg terminals), social media / fintwit sentiment.


## Data Catalog

### Feed Registry

#### Fed Blogs & Research (6 feeds)

| Key | Name | Org | URL |
|-----|------|-----|-----|
| `liberty_street` | Liberty Street Economics | NY Fed | `https://libertystreeteconomics.newyorkfed.org/feed/` |
| `feds_notes` | FEDS Notes | Fed Board | `https://www.federalreserve.gov/feeds/feds_notes.xml` |
| `chicago_fed` | Chicago Fed Letter | Chicago Fed | `https://www.chicagofed.org/feeds/publications/chicago-fed-letter` |
| `stlouisfed` | On the Economy | St. Louis Fed | `https://www.stlouisfed.org/on-the-economy/rss` |
| `sf_fed` | SF Fed Economic Letter | SF Fed | `https://www.frbsf.org/research-and-insights/publications/economic-letter/feed/` |
| `richmond_fed` | Richmond Fed Research | Richmond Fed | `https://www.richmondfed.org/rss_feeds/research` |

#### Think Tanks & Policy (5 feeds)

| Key | Name | Org | URL |
|-----|------|-----|-----|
| `brookings` | Brookings Institution | Brookings | `https://www.brookings.edu/feed/` |
| `piie` | PIIE Realtime Economics | PIIE | `https://www.piie.com/blogs/realtime-economics/feed` |
| `cato` | Cato Institute | Cato | `https://www.cato.org/rss/recent-opeds` |
| `aei` | AEI | AEI | `https://www.aei.org/feed/` |
| `heritage` | Heritage Foundation | Heritage | `https://www.heritage.org/rss` |

#### Academic / Research (3 feeds)

| Key | Name | Org | URL |
|-----|------|-----|-----|
| `nber` | NBER New Working Papers | NBER | `https://www.nber.org/rss/new.xml` |
| `voxeu` | VoxEU / CEPR | CEPR | `https://cepr.org/rss/columns/voxeu.xml` |
| `imf_blog` | IMF Blog | IMF | `https://www.imf.org/en/Blogs/rss` |

#### Central Bank Official (3 feeds)

| Key | Name | Org | URL |
|-----|------|-----|-----|
| `ecb_press` | ECB Press Releases | ECB | `https://www.ecb.europa.eu/rss/press.html` |
| `boe_speeches` | BoE Speeches | BoE | `https://www.bankofengland.co.uk/rss/speeches` |
| `bis_speeches` | BIS Central Bank Speeches | BIS | `https://www.bis.org/doclist/cbspeeches.rss` |

#### Macro Data & Analysis (2 feeds)

| Key | Name | Org | URL |
|-----|------|-----|-----|
| `calculated_risk` | Calculated Risk | Calculated Risk | `https://www.calculatedriskblog.com/feeds/posts/default` |
| `econbrowser` | Econbrowser | Menzie Chinn / Jim Hamilton | `https://econbrowser.com/feed` |

### Categories

| Key | Label | Feed Count |
|-----|-------|------------|
| `fed` | FED BLOGS & RESEARCH | 6 |
| `policy` | THINK TANKS & POLICY | 5 |
| `academic` | ACADEMIC / RESEARCH | 3 |
| `central_bank` | CENTRAL BANK OFFICIAL | 3 |
| `macro` | MACRO DATA & ANALYSIS | 2 |

### Entry Fields (per normalized entry)

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Entry headline |
| `link` | string | URL to full article |
| `published` | string | ISO 8601 datetime (UTC), empty if unavailable |
| `summary` | string | HTML-stripped excerpt (truncated in display, full in JSON) |
| `author` | string | Author name if provided |
| `feed_key` | string | Registry key (e.g. `liberty_street`) |
| `category` | string | Category key (e.g. `fed`, `policy`) |
| `feed_name` | string | Display name (e.g. `Liberty Street Economics`) |
| `org` | string | Organization (e.g. `NY Fed`) |

### Pull Summary Fields (from `pull --json`)

| Field | Type | Description |
|-------|------|-------------|
| `total_entries` | int | Total entries across all feeds |
| `errors` | dict | Feed key -> error message for failed feeds |
| `elapsed_seconds` | float | Wall-clock fetch time |
| `by_feed` | dict | Feed key -> entry count |

### Export Digest Fields (from `export-digest`)

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | string | ISO 8601 generation timestamp |
| `total_entries` | int | Total entries |
| `feed_count` | int | Number of registered feeds (20) |
| `errors` | dict | Feed key -> error message |
| `elapsed_seconds` | float | Fetch time |
| `categories` | dict | Category key -> `{name, entry_count, entries[]}` |

### Headline Fields (from `headlines --json`)

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Entry headline |
| `date` | string | YYYY-MM-DD formatted date |
| `source` | string | Organization name |
| `link` | string | URL |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export (where noted).

### Browse -- Latest Entries

```bash
# Latest 20 entries across all feeds
python rss.py latest
python rss.py latest --json

# Latest from a specific category
python rss.py latest --category fed
python rss.py latest --category fed --count 10
python rss.py latest --category policy --json
python rss.py latest --category academic --count 5 --json

# Latest with export
python rss.py latest --count 50 --export csv
python rss.py latest --category central_bank --export json
```

### Browse -- Single Feed

```bash
# Entries from a specific feed by registry key
python rss.py feed liberty_street
python rss.py feed liberty_street --json
python rss.py feed liberty_street --count 10

python rss.py feed nber
python rss.py feed nber --count 50 --json

python rss.py feed ecb_press --json
python rss.py feed calculated_risk --count 15 --export csv

# All valid feed_key values:
# liberty_street, feds_notes, chicago_fed, stlouisfed, sf_fed, richmond_fed,
# brookings, piie, cato, aei, heritage,
# nber, voxeu, imf_blog,
# ecb_press, boe_speeches, bis_speeches,
# calculated_risk, econbrowser
```

### Browse -- Category

```bash
# All entries from a category
# cat choices: fed, policy, academic, central_bank, macro
python rss.py category fed
python rss.py category policy --count 20 --json
python rss.py category academic --json
python rss.py category central_bank --count 10
python rss.py category macro --export csv
```

### Browse -- Headlines

```bash
# Compact headline view (date | source | title)
python rss.py headlines
python rss.py headlines --json
python rss.py headlines --category fed --count 20
python rss.py headlines --category policy --json
python rss.py headlines --count 100 --export csv
```

### Analysis -- Search

```bash
# Keyword search across titles and summaries
python rss.py search "inflation"
python rss.py search "inflation" --json
python rss.py search "inflation" --category fed --count 10
python rss.py search "tariff" --json
python rss.py search "labor market" --category academic --json
python rss.py search "quantitative tightening" --count 50 --export json
python rss.py search "rate cut" --category policy --json
```

### Analysis -- Digest

```bash
# Daily digest: top N entries per category
python rss.py digest
python rss.py digest --json
python rss.py digest --count 5 --json
python rss.py digest --count 10 --export json
```

### Data -- Pull All

```bash
# Pull all 20 feeds, show per-feed summary table
python rss.py pull
python rss.py pull --json
python rss.py pull --export csv
```

### Data -- List Feeds & Categories

```bash
# List all registered feeds with URLs
python rss.py feeds
python rss.py feeds --json

# List categories with feed counts
python rss.py categories
python rss.py categories --json
```

### Data -- Export Full Digest

```bash
# Full digest export (all feeds, all entries, grouped by category)
python rss.py export-digest
python rss.py export-digest --export json
python rss.py export-digest --export csv
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to CSV file | latest, feed, pull, search, category, digest, headlines, export-digest |
| `--export json` | Export to JSON file | latest, feed, pull, search, category, digest, headlines, export-digest |
| `--count N` | Number of entries to return | latest (20), feed (20), search (30), category (30), headlines (40), digest (3 per cat) |
| `--category KEY` | Filter by category (`fed`/`policy`/`academic`/`central_bank`/`macro`/`all`) | latest, search, headlines |
| `feed_key` | Positional: registry key for single-feed fetch | feed |
| `keyword` | Positional: search term | search |
| `cat` | Positional: category key | category |


## Python Recipes

### Browse -- Latest & Single Feed

```python
from rss import cmd_latest, cmd_feed

# Latest entries across all feeds (default 20)
# Returns: list of entry dicts with title, link, published, summary, author, feed_key, category, feed_name, org
cmd_latest(as_json=True)
cmd_latest(category="fed", count=10, as_json=True)
cmd_latest(category="policy", count=5, as_json=True)

# Latest from a single feed
# Returns: list of entry dicts for that feed only
cmd_feed(feed_key="liberty_street", as_json=True)
cmd_feed(feed_key="nber", count=50, as_json=True)
cmd_feed(feed_key="ecb_press", count=10, as_json=True)
```

### Browse -- Category & Headlines

```python
from rss import cmd_category, cmd_headlines

# All entries from a category
# cat choices: "fed", "policy", "academic", "central_bank", "macro"
# Returns: list of entry dicts sorted by date descending
cmd_category(cat="fed", as_json=True)
cmd_category(cat="academic", count=20, as_json=True)

# Compact headline data
# Returns: list of {title, date, source, link} dicts
cmd_headlines(as_json=True)
cmd_headlines(category="fed", count=20, as_json=True)
```

### Analysis -- Search

```python
from rss import cmd_search

# Keyword search across titles and summaries
# Returns: list of matching entry dicts sorted by date
cmd_search(keyword="inflation", as_json=True)
cmd_search(keyword="tariff", category="policy", count=10, as_json=True)
cmd_search(keyword="labor market", category="academic", as_json=True)
```

### Analysis -- Digest

```python
from rss import cmd_digest

# Top N entries per category
# Returns: dict keyed by category -> {category_name, entries[]}
cmd_digest(as_json=True)
cmd_digest(entries_per_cat=5, as_json=True)
```

### Data -- Pull & Registry

```python
from rss import cmd_pull, cmd_feeds, cmd_categories

# Pull all feeds, returns summary
# Returns: {total_entries, errors, elapsed_seconds, by_feed}
cmd_pull(as_json=True)

# Feed registry as JSON
# Returns: full FEED_REGISTRY dict (key -> {url, name, org, category})
cmd_feeds(as_json=True)

# Categories with counts
# Returns: list of {category, name, feed_count}
cmd_categories(as_json=True)
```

### Data -- Export Digest

```python
from rss import cmd_export_digest

# Full structured export for PRISM ingestion
# Writes file: rss_full_digest_YYYYMMDD_HHMMSS.json
# Returns: {generated_at, total_entries, feed_count, errors, elapsed_seconds,
#           categories: {cat -> {name, entry_count, entries[]}}}
cmd_export_digest(export_fmt="json")
cmd_export_digest(export_fmt="csv")
```

### Direct Feed Access

```python
from rss import _fetch_feed, _fetch_multiple, _sort_entries, _dedup_entries, FEED_REGISTRY

# Fetch a single feed (returns raw entry list + error)
entries, err = _fetch_feed("liberty_street")

# Fetch multiple feeds
all_entries, errors = _fetch_multiple(feed_keys=["nber", "voxeu", "imf_blog"], quiet=True)

# Fetch all feeds
all_entries, errors = _fetch_multiple(quiet=True)

# Sort and dedup
entries = _dedup_entries(_sort_entries(all_entries))

# Access registry directly
for key, info in FEED_REGISTRY.items():
    print(key, info["name"], info["category"], info["url"])
```


## Composite Recipes

### Morning Research Scan

```bash
python rss.py digest --count 3 --json
```

PRISM receives: top 3 entries per category (15 total across 5 categories), with title, date, source, summary, and link. Covers overnight Fed research, policy commentary, academic papers, central bank communications, and macro analysis.

### Full Feed Health Check

```bash
python rss.py pull --json
python rss.py categories --json
```

PRISM receives: per-feed entry counts, error report for any failed feeds, total entry count, fetch elapsed time, category breakdown. Monitors feed availability and staleness.

### Fed Research Deep Dive

```bash
python rss.py category fed --count 30 --json
python rss.py feed liberty_street --count 20 --json
python rss.py feed feds_notes --count 20 --json
python rss.py feed sf_fed --count 20 --json
```

PRISM receives: full Fed research output across all 6 regional banks and the Board, plus deep pulls from the three highest-signal feeds (Liberty Street, FEDS Notes, SF Fed Economic Letter).

### Topic Surveillance

```bash
python rss.py search "inflation" --json
python rss.py search "inflation" --category fed --json
python rss.py search "inflation" --category academic --json
python rss.py search "inflation" --category policy --json
```

PRISM receives: all recent mentions of a keyword across the full feed universe, then broken down by category. Shows which institutions are publishing on the topic and when.

### Think Tank Policy Sweep

```bash
python rss.py category policy --count 20 --json
python rss.py search "fiscal" --category policy --json
python rss.py search "regulation" --category policy --json
```

PRISM receives: recent policy commentary from Brookings, PIIE, Cato, AEI, Heritage, plus targeted searches for fiscal and regulatory topics within the policy category.

### Central Bank Communications Monitor

```bash
python rss.py category central_bank --count 20 --json
python rss.py feed ecb_press --count 15 --json
python rss.py feed boe_speeches --count 15 --json
python rss.py feed bis_speeches --count 15 --json
```

PRISM receives: all recent central bank official communications, then per-institution deep pulls from ECB, BoE, and BIS.

### Academic Paper Watch

```bash
python rss.py feed nber --count 30 --json
python rss.py feed voxeu --count 20 --json
python rss.py search "monetary policy" --category academic --json
```

PRISM receives: latest NBER working papers, VoxEU columns, plus targeted academic search for monetary policy research.

### PRISM Full Ingestion

```bash
python rss.py export-digest --export json
```

PRISM receives: full structured digest file with all entries from all 20 feeds, grouped by category, with metadata (generation timestamp, error report, entry counts). Primary ingestion pathway for PRISM context system.

### Headline Scan by Sector

```bash
python rss.py headlines --category fed --count 30 --json
python rss.py headlines --category policy --count 30 --json
python rss.py headlines --category academic --count 30 --json
python rss.py headlines --category central_bank --count 30 --json
python rss.py headlines --category macro --count 30 --json
```

PRISM receives: compact headline data (title, date, source, link) for each category. Lightweight alternative to full entry pulls for scanning volume.


## Cross-Source Recipes

### Research + Rates Context

```bash
python rss.py search "SOFR" --json
python rss.py search "federal funds" --json
python projects/apis/nyfed/nyfed.py rates --json
```

PRISM receives: research commentary mentioning SOFR or fed funds + actual current rate levels. Pairs institutional analysis with live data.

### Fed Research + FOMC Expectations

```bash
python rss.py category fed --count 20 --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: latest Fed research blog output + market-implied policy expectations. Shows what the Fed system is publishing alongside what markets are pricing.

### Policy Commentary + Tariff Data

```bash
python rss.py search "tariff" --category policy --json
python rss.py search "trade" --category policy --json
python projects/apis/tariffs/tariffs.py latest --json
```

PRISM receives: think tank commentary on tariffs/trade + actual tariff rate data. Policy analysis paired with the underlying data.

### Academic Research + NBER Data

```bash
python rss.py feed nber --count 30 --json
python rss.py search "recession" --category academic --json
```

PRISM receives: latest NBER working papers and recession-related academic research for monitoring the research frontier.

### Central Bank Comms + BIS Statistics

```bash
python rss.py category central_bank --count 20 --json
python projects/apis/bis/bis.py stats credit-to-gdp --json
```

PRISM receives: central bank speeches and press releases + BIS credit/GDP data. Pairs official communications with underlying statistical trends.

### Morning Macro Briefing

```bash
python rss.py digest --count 3 --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
python projects/apis/treasury/treasury.py get dts --json
```

PRISM receives: daily research digest across all categories + overnight funding conditions + Treasury cash flows. Full morning context package.

### Inflation Narrative Tracking

```bash
python rss.py search "inflation" --json
python rss.py search "CPI" --json
python rss.py search "PCE" --json
python projects/apis/nyfed/nyfed.py rates --json
```

PRISM receives: all recent inflation/CPI/PCE commentary across all feeds + current rate levels. Maps the institutional narrative around inflation against funding market conditions.

### Fiscal Policy Monitor

```bash
python rss.py search "fiscal" --json
python rss.py search "deficit" --category policy --json
python projects/apis/treasury/treasury.py get dts --json
python projects/apis/sec_edgar/sec_edgar.py search "government debt" --json
```

PRISM receives: fiscal policy commentary from all sources + think tank deficit analysis + Treasury cash flows + SEC filings mentioning government debt.


## Setup

1. No API key required
2. `pip install feedparser requests`
3. Test: `python rss.py feeds`
4. Full test: `python rss.py pull`


## Architecture

```
rss.py
  Config          SESSION (requests), FEED_TIMEOUT (20s), FEED_REGISTRY (20 feeds),
                  CATEGORY_ORDER (5), CATEGORY_NAMES
  HTML            _HTMLStripper, _strip_html(), _truncate()
  Date Parsing    _parse_entry_date(), _fmt_date(), _fmt_date_short(), _age_str()
  Feed Fetching   _fetch_feed(), _fetch_multiple() with progress,
                  _sort_entries(), _dedup_entries(), _feeds_for_category()
  Export          _serialize_entry(), _export_json(), _export_csv(), _do_export()
  Display         _display_entries(), _display_headlines(), _display_pull_summary()
  Commands (10)   latest, feed, pull, search, category, feeds, categories,
                  digest, headlines, export-digest
  Interactive     10-item menu -> interactive wrappers with prompts
  Argparse        10 subcommands, all with --json, most with --export and --count
```

Feed sources (all public RSS/Atom, no auth):
```
libertystreeteconomics.newyorkfed.org    -> NY Fed blog
federalreserve.gov/feeds/                -> Fed Board FEDS Notes
chicagofed.org/feeds/                    -> Chicago Fed Letter
stlouisfed.org/on-the-economy/rss        -> St. Louis Fed blog
frbsf.org/.../economic-letter/feed/      -> SF Fed Economic Letter
richmondfed.org/rss_feeds/               -> Richmond Fed Research
brookings.edu/feed/                      -> Brookings Institution
piie.com/blogs/realtime-economics/feed   -> PIIE Realtime Economics
cato.org/rss/                            -> Cato Institute
aei.org/feed/                            -> AEI
heritage.org/rss                         -> Heritage Foundation
nber.org/rss/new.xml                     -> NBER Working Papers
cepr.org/rss/columns/voxeu.xml           -> VoxEU / CEPR
imf.org/en/Blogs/rss                     -> IMF Blog
ecb.europa.eu/rss/press.html             -> ECB Press Releases
bankofengland.co.uk/rss/speeches         -> BoE Speeches
bis.org/doclist/cbspeeches.rss           -> BIS Central Bank Speeches
calculatedriskblog.com/feeds/            -> Calculated Risk
econbrowser.com/feed                     -> Econbrowser
```
