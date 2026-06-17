# GDELT Project Global Media Monitoring

Script: `projects/apis/gdelt/gdelt.py`
Base URLs:
  - DOC: `https://api.gdeltproject.org/api/v2/doc/doc`
  - TV: `https://api.gdeltproject.org/api/v2/tv/tv`
  - Context: `https://api.gdeltproject.org/api/v2/context/context`
  - GEO: `https://api.gdeltproject.org/api/v2/geo/geo`
Auth: None required (fully public)
Rate limit: ~1-2 req/sec (not formally documented; be reasonable)
Coverage: DOC/GEO = rolling 3 months; Context = 72 hours; TV = July 2009 to present
Dependencies: `requests`


## Triggers

Use for: global news article search, media coverage volume timelines, media tone/sentiment analysis, language breakdown of coverage, source country breakdown, TV news clip search, TV station comparisons (CNN vs Fox vs MSNBC), TV trending topics, word clouds, sentence-level context extraction (last 72h), geographic footprint of narratives, macro theme narrative monitoring, event detection via volume spikes, cross-country narrative divergence, sentiment regime assessment (fear vs calm).

Not for: structured economic data (FRED, BLS, BEA), financial market prices or yields (Bloomberg, Refinitiv), social media sentiment (Twitter/X, Reddit), academic citation analysis, historical news archives beyond 3 months for DOC (use GDELT raw event files), real-time trade execution signals, company-level earnings or filings (SEC EDGAR), futures positioning (CFTC), repo/funding rates (NY Fed).


## Data Catalog

### GDELT Query Syntax

All four APIs share this query syntax in the `query` parameter:

| Syntax | Description | Example |
|--------|-------------|---------|
| `"phrase"` | Exact phrase match | `"federal reserve"` |
| `(a OR b OR c)` | Boolean OR (must capitalize OR) | `(recession OR downturn)` |
| `-keyword` | Exclude keyword | `-opinion` |
| `domain:X` | Filter to domain | `domain:reuters.com` |
| `domainis:X` | Exact domain match | `domainis:un.org` |
| `sourcecountry:X` | Source country (name or 2-char FIPS) | `sourcecountry:US` |
| `sourcelang:X` | Source language (name or 3-char code) | `sourcelang:spanish` |
| `theme:X` | GKG theme tag | `theme:TERROR` |
| `tone<N` | Articles with tone below N | `tone<-5` |
| `tone>N` | Articles with tone above N | `tone>5` |
| `toneabs>N` | Absolute tone > N (high emotion) | `toneabs>10` |
| `near20:"X Y"` | Proximity: words within N of each other | `near20:"trump putin"` |
| `repeat3:"X"` | Word appears N+ times in article | `repeat3:"recession"` |

### MACRO_THEMES (16 curated macro presets)

| Key | Query |
|-----|-------|
| `recession` | `(recession OR "economic downturn" OR "hard landing" OR "soft landing")` |
| `inflation` | `(inflation OR CPI OR "price pressures" OR disinflation OR deflation)` |
| `fed` | `("federal reserve" OR "interest rate" OR "rate cut" OR "rate hike" OR FOMC OR powell)` |
| `tariffs` | `(tariff OR tariffs OR "trade war" OR "import duties" OR "trade policy")` |
| `labor` | `("labor market" OR unemployment OR "job growth" OR "nonfarm payrolls" OR JOLTS)` |
| `housing` | `("housing market" OR "home prices" OR "mortgage rates" OR "housing starts")` |
| `banking` | `("banking crisis" OR "bank failure" OR "deposit flight" OR "bank run" OR "credit crunch")` |
| `china` | `(china OR beijing OR "chinese economy" OR yuan OR renminbi)` |
| `geopolitical` | `(geopolitical OR sanctions OR "military conflict" OR "diplomatic crisis")` |
| `energy` | `("oil prices" OR "crude oil" OR "natural gas" OR OPEC OR "energy crisis")` |
| `fiscal` | `("fiscal policy" OR "government spending" OR "debt ceiling" OR "budget deficit")` |
| `crypto` | `(bitcoin OR cryptocurrency OR "digital currency" OR ethereum OR "crypto crash")` |
| `ai` | `("artificial intelligence" OR "AI regulation" OR "generative AI" OR "tech layoffs")` |
| `treasury` | `("treasury yields" OR "bond market" OR "yield curve" OR "treasury auction")` |
| `dollar` | `("us dollar" OR "dollar strength" OR "currency war" OR DXY)` |
| `emerging_markets` | `("emerging markets" OR "EM crisis" OR "capital outflows" OR "frontier markets")` |

### DOC_MODES (10 output modes for DOC API)

| Mode | Description |
|------|-------------|
| `artlist` | Article list -- URLs, titles, source info for matching articles |
| `artgallery` | Article gallery -- visual magazine-style layout (HTML only) |
| `timelinevol` | Volume timeline -- % of global coverage matching query over time |
| `timelinevolraw` | Raw volume timeline -- absolute article counts (not normalized) |
| `timelinevolinfo` | Volume timeline with top articles at each timestep |
| `timelinetone` | Tone timeline -- average sentiment of matching coverage over time |
| `timelinelang` | Language timeline -- coverage volume broken down by language |
| `timelinesourcecountry` | Source country timeline -- coverage by country of origin |
| `tonechart` | Tone chart -- histogram of sentiment distribution across all matches |
| `wordcloudimagewebtags` | Image web tags word cloud -- topics from reverse image search |

### TV_MODES (10 output modes for TV API)

| Mode | Description |
|------|-------------|
| `clipgallery` | Clip gallery -- top matching TV clips with thumbnails and transcripts |
| `showchart` | Show chart -- which TV shows mention the topic most |
| `stationchart` | Station chart -- compare coverage across stations |
| `stationdetails` | Station details -- list all available TV stations |
| `timelinevol` | Volume timeline -- airtime mentioning the topic over time |
| `timelinevolheatmap` | Volume heatmap -- hourly breakdown (day x hour grid) |
| `timelinevolstream` | Streamgraph -- same as timeline but streamgraph display |
| `timelinevolnorm` | Normalized volume -- total monitored airtime per station |
| `trendingtopics` | Trending topics -- what's dominating TV news right now |
| `wordcloud` | Word cloud -- most frequent words in matching clips |

### TV_STATIONS

| Group | Stations |
|-------|----------|
| `national` | CNN, MSNBC, FOXNEWS, BBCNEWS, CNBC, BLOOMBERG, CSPAN, CSPAN2 |
| `broadcast` | KNTV, KGO, KPIX, WJLA, WRC, WTTG, WCBS, WNBC, WABC |

### DOC API Article Fields (artlist response)

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Article headline |
| `url` | string | Full article URL |
| `domain` | string | Source domain |
| `language` | string | Article language |
| `sourcecountry` | string | Country of source outlet |
| `seendate` | string | Date article was seen |
| `tone` | float | Sentiment score (negative=negative, positive=positive) |
| `excerpt` | string | Article excerpt/snippet |

### DOC API Timeline Fields (timelinevol/timelinetone response)

| Field | Type | Description |
|-------|------|-------------|
| `timeline[].series` | string | Series identifier |
| `timeline[].data[].date` | string | Timestamp |
| `timeline[].data[].value` | float | Volume (% or raw count) or tone score |
| `timeline[].data[].norm` | float | Normalized value (alternate key) |

### DOC API Tone Chart Fields (tonechart response)

| Field | Type | Description |
|-------|------|-------------|
| `tonechart[].bin` | float | Tone score bucket |
| `tonechart[].count` | int | Number of articles in this bucket |

### TV API Clip Fields (clipgallery response)

| Field | Type | Description |
|-------|------|-------------|
| `clips[].show` | string | TV show name |
| `clips[].station` | string | Station ID (CNN, FOXNEWS, etc.) |
| `clips[].date` | string | Air date/time |
| `clips[].snippet` | string | Transcript excerpt |
| `clips[].preview_url` | string | Internet Archive clip URL |

### Context API Response Fields

Same article structure as DOC artlist, plus `context` field containing the matched sentence with surrounding context.

### GEO API Response Fields

Returns GeoJSON (default) or JSON with location points mentioned in matching articles. Point features with coordinates and metadata.

### doc_search() Full Parameter Reference

| Arg | Type | Default | Description |
|-----|------|---------|-------------|
| `query` | str | required | Search terms (keywords, phrases, OR blocks, operators) |
| `mode` | str | `"artlist"` | Output mode (see DOC_MODES) |
| `format` | str | `"json"` | Output format: json, csv, html |
| `timespan` | str | None | Time window: `"24h"`, `"7d"`, `"1w"`, `"1months"`, `"3months"`, `"60min"` |
| `start_dt` | str | None | Start datetime `YYYYMMDDHHMMSS` |
| `end_dt` | str | None | End datetime `YYYYMMDDHHMMSS` |
| `sort` | str | None | `DateDesc`, `DateAsc`, `ToneDesc`, `ToneAsc`, `HybridRel` |
| `maxrecords` | int | 250 | Max articles (1-250) |
| `sourcelang` | str | None | Language filter (e.g. `"english"`, `"spanish"`) |
| `sourcecountry` | str | None | Country filter (e.g. `"US"`, `"france"`) |
| `domain` | str | None | Domain filter (e.g. `"reuters.com"`) |
| `theme` | str | None | GKG theme filter (e.g. `"TERROR"`) |
| `tone_below` | float | None | Filter tone < value |
| `tone_above` | float | None | Filter tone > value |
| `trans` | str | None | Translation parameter |

### tv_search() Full Parameter Reference

| Arg | Type | Default | Description |
|-----|------|---------|-------------|
| `query` | str | required | Search terms |
| `mode` | str | `"timelinevol"` | Output mode (see TV_MODES) |
| `format` | str | `"json"` | Output format: json, csv, html |
| `timespan` | str | None | Time window: `"7d"`, `"1months"`, `"3months"`, `"1y"` |
| `start_dt` | str | None | Start datetime `YYYYMMDDHHMMSS` |
| `end_dt` | str | None | End datetime `YYYYMMDDHHMMSS` |
| `station` | str | None | Station ID: `CNN`, `FOXNEWS`, `MSNBC`, `CNBC`, `BLOOMBERG` |
| `network` | str | None | Network filter: `CBS`, `NBC`, `ABC` |
| `market` | str | None | Geographic market: `"San Francisco"`, `"National"` |
| `show` | str | None | Show name filter |
| `context` | str | None | Additional context search (15s before/after clips) |
| `sort` | str | None | `DateDesc`, `DateAsc` |
| `datanorm` | str | None | Normalization mode for charts |
| `datacomb` | str | None | Combine all stations into single series |
| `last24` | bool | None | Include last 24 hours (partial data) |
| `dateres` | str | None | Date resolution: `Hour`, `Day`, `Week`, `Month`, `Year` |
| `timelinesmooth` | int | None | Smoothing window (integer days) |

### context_search() Full Parameter Reference

| Arg | Type | Default | Description |
|-----|------|---------|-------------|
| `query` | str | required | Search terms (all terms must appear in same sentence) |
| `format` | str | `"json"` | Output format: json, csv |
| `timespan` | str | None | Time window (last 72h max) |
| `start_dt` | str | None | Start datetime `YYYYMMDDHHMMSS` |
| `end_dt` | str | None | End datetime `YYYYMMDDHHMMSS` |
| `sort` | str | None | `DateDesc`, `DateAsc` |
| `maxrecords` | int | 75 | Max sentences (1-75) |
| `sourcelang` | str | None | Language filter |
| `sourcecountry` | str | None | Country filter |
| `domain` | str | None | Domain filter |

### geo_search() Full Parameter Reference

| Arg | Type | Default | Description |
|-----|------|---------|-------------|
| `query` | str | required | Search terms |
| `mode` | str | `"pointdata"` | Output mode |
| `format` | str | `"geojson"` | Output format: geojson, json, csv |
| `timespan` | str | None | Time window |
| `start_dt` | str | None | Start datetime `YYYYMMDDHHMMSS` |
| `end_dt` | str | None | End datetime `YYYYMMDDHHMMSS` |
| `sourcelang` | str | None | Language filter |
| `sourcecountry` | str | None | Country filter |
| `domain` | str | None | Domain filter |
| `theme` | str | None | GKG theme filter |


## CLI Recipes

All commands support `--json` for raw JSON output and `--export json|csv` for file export.

### DOC API: Article Search

```bash
# Search articles by keyword
python gdelt.py doc-search --query "tariffs" --timespan 7d --maxrecords 25
python gdelt.py doc-search --query "tariffs" --timespan 7d --json

# Complex boolean query
python gdelt.py doc-search --query '"federal reserve" (rate OR hike OR cut)' --sort DateDesc
python gdelt.py doc-search --query '(recession OR "hard landing")' --timespan 3months --json

# Filter by source language
python gdelt.py doc-search --query "inflation" --sourcelang english --timespan 1w

# Filter by source country
python gdelt.py doc-search --query "tariffs" --sourcecountry US --timespan 7d

# Filter by domain
python gdelt.py doc-search --query "recession" --domain reuters.com --timespan 3months

# Filter by GKG theme
python gdelt.py doc-search --query "economy" --theme TAX_FNCACT --timespan 7d

# Sort options: DateDesc, DateAsc, ToneDesc, ToneAsc, HybridRel
python gdelt.py doc-search --query "inflation" --sort ToneDesc --maxrecords 50

# Date range (YYYYMMDDHHMMSS format)
python gdelt.py doc-search --query "tariffs" --start-dt 20260401000000 --end-dt 20260410000000

# Export to file
python gdelt.py doc-search --query "recession" --timespan 7d --export json
python gdelt.py doc-search --query "recession" --timespan 7d --export csv
```

### DOC API: Volume Timeline

```bash
# Normalized volume (% of global coverage)
python gdelt.py doc-volume --query "recession" --timespan 3months
python gdelt.py doc-volume --query "recession" --timespan 3months --json

# Raw article counts
python gdelt.py doc-volume --query "tariffs" --timespan 1months --raw
python gdelt.py doc-volume --query "tariffs" --timespan 1months --raw --json

# Export
python gdelt.py doc-volume --query "inflation" --timespan 3months --export csv
```

### DOC API: Tone Timeline

```bash
# Average sentiment over time
python gdelt.py doc-tone --query "inflation" --timespan 3months
python gdelt.py doc-tone --query "inflation" --timespan 3months --json

# Macro theme tone tracking
python gdelt.py doc-tone --query '("federal reserve" OR FOMC OR powell)' --timespan 3months --json

# Export
python gdelt.py doc-tone --query "recession" --timespan 3months --export csv
```

### DOC API: Tone Chart

```bash
# Sentiment distribution histogram
python gdelt.py doc-tonechart --query "china tariffs" --timespan 1months
python gdelt.py doc-tonechart --query "china tariffs" --timespan 3months --json

# Export
python gdelt.py doc-tonechart --query "recession" --timespan 3months --export json
```

### DOC API: Language Breakdown

```bash
# Coverage by source language
python gdelt.py doc-language --query "ukraine" --timespan 1w
python gdelt.py doc-language --query "tariffs" --timespan 1months --json

# Export
python gdelt.py doc-language --query "inflation" --timespan 1w --export csv
```

### DOC API: Country Breakdown

```bash
# Coverage by source country
python gdelt.py doc-country --query "inflation" --timespan 1months
python gdelt.py doc-country --query "recession" --timespan 1w --json

# Export
python gdelt.py doc-country --query "tariffs" --timespan 1months --export csv
```

### TV API: Clip Search

```bash
# Search TV clips by keyword
python gdelt.py tv-clips --query "federal reserve" --timespan 7d
python gdelt.py tv-clips --query "federal reserve" --timespan 7d --json

# Filter by station
python gdelt.py tv-clips --query "recession" --station CNN --timespan 7d
python gdelt.py tv-clips --query "tariffs" --station FOXNEWS --timespan 7d

# Filter by network
python gdelt.py tv-clips --query "inflation" --network CBS --timespan 7d

# Export
python gdelt.py tv-clips --query "recession" --station MSNBC --timespan 7d --export json
```

### TV API: Volume Timeline

```bash
# TV coverage volume over time
python gdelt.py tv-volume --query "recession" --timespan 3months
python gdelt.py tv-volume --query "recession" --timespan 1y --json

# Filter by station
python gdelt.py tv-volume --query "tariffs" --station CNN --timespan 3months

# Smoothing (days)
python gdelt.py tv-volume --query "inflation" --timespan 3months --smooth 5

# Export
python gdelt.py tv-volume --query "recession" --timespan 1y --export csv
```

### TV API: Station Comparison

```bash
# Compare coverage across all stations
python gdelt.py tv-stations --query "tariffs" --timespan 3months
python gdelt.py tv-stations --query "tariffs" --timespan 1months --json

# Export
python gdelt.py tv-stations --query "recession" --timespan 3months --export json
```

### TV API: Trending Topics

```bash
# What's dominating TV news right now
python gdelt.py tv-trending
python gdelt.py tv-trending --json

# Export
python gdelt.py tv-trending --export json
```

### TV API: Word Cloud

```bash
# Co-occurring terms on TV
python gdelt.py tv-wordcloud --query "federal reserve" --timespan 1months
python gdelt.py tv-wordcloud --query "tariffs" --station CNN --timespan 1months --json

# Export
python gdelt.py tv-wordcloud --query "recession" --timespan 1months --export json
```

### Context API: Sentence Search

```bash
# Sentence-level search (last 72h, all terms must co-occur in same sentence)
python gdelt.py context --query "recession unemployment" --maxrecords 50
python gdelt.py context --query "federal reserve rate cut" --maxrecords 50 --json

# Sort by date
python gdelt.py context --query "tariffs" --sort DateDesc --maxrecords 75

# Filter by language/country
python gdelt.py context --query "inflation" --sourcelang english --sourcecountry US

# Export
python gdelt.py context --query "recession" --maxrecords 50 --export json
```

### GEO API: Geographic Search

```bash
# Geographic coverage map
python gdelt.py geo --query "sanctions" --timespan 7d
python gdelt.py geo --query "military conflict" --timespan 7d --json

# GeoJSON output
python gdelt.py geo --query "tariffs" --format geojson --timespan 1months

# Export
python gdelt.py geo --query "sanctions" --timespan 7d --export json
```

### Recipe: Narrative Monitor

```bash
# Full narrative monitor: volume timeline + tone timeline + top articles
# Uses MACRO_THEMES keys or custom query
python gdelt.py narrative --theme recession --timespan 3months
python gdelt.py narrative --theme fed --timespan 3months --json
python gdelt.py narrative --theme tariffs --timespan 1months
python gdelt.py narrative --theme inflation --timespan 3months --json

# Custom query as theme
python gdelt.py narrative --theme '"debt ceiling" OR "government shutdown"' --timespan 3months --json

# Export
python gdelt.py narrative --theme recession --timespan 3months --export json
```

### Recipe: Sentiment Regime

```bash
# Tone distribution comparison: 3-month vs 1-week
# Accepts MACRO_THEMES key or custom query
python gdelt.py sentiment --query recession --json
python gdelt.py sentiment --query inflation --json
python gdelt.py sentiment --query '(tariffs OR "trade war")' --json

# Export
python gdelt.py sentiment --query recession --export json
```

### Recipe: Cross-Country Narrative

```bash
# Compare tone timelines across countries (FIPS codes)
python gdelt.py cross-country --query recession --countries US,UK,CH,JA,GM,FR --timespan 1months
python gdelt.py cross-country --query inflation --countries US,UK,CH,JA --timespan 1months --json

# Custom country set
python gdelt.py cross-country --query tariffs --countries US,CH,JA,GM --timespan 3months --json

# Export
python gdelt.py cross-country --query recession --countries US,UK --timespan 1months --export json
```

### Recipe: TV Divergence

```bash
# CNN vs Fox vs MSNBC volume comparison
python gdelt.py tv-divergence --query "federal reserve" --timespan 3months
python gdelt.py tv-divergence --query "immigration" --timespan 1months --json
python gdelt.py tv-divergence --query "tariffs" --timespan 3months --json

# Export
python gdelt.py tv-divergence --query "recession" --timespan 3months --export json
```

### Recipe: Event Detection

```bash
# Scan macro themes for recent volume spikes (compares last 24h vs 7d baseline)
python gdelt.py event-detect --themes recession,fed,tariffs,geopolitical,banking
python gdelt.py event-detect --themes recession,fed,tariffs,geopolitical,banking --json

# Scan all 16 themes
python gdelt.py event-detect --themes recession,inflation,fed,tariffs,labor,housing,banking,china,geopolitical,energy,fiscal,crypto,ai,treasury,dollar,emerging_markets

# Subset
python gdelt.py event-detect --themes fed,tariffs,china --json
```

### Recipe: Multi-Theme Dashboard

```bash
# Quick article count across all 16 macro themes
python gdelt.py multi-theme --timespan 7d
python gdelt.py multi-theme --timespan 24h --json
python gdelt.py multi-theme --timespan 1months --json

# Export
python gdelt.py multi-theme --timespan 7d --export json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | Raw JSON output for programmatic consumption | All commands |
| `--export json` | Export to JSON file | All commands with --export |
| `--export csv` | Export to CSV file | All commands with --export |
| `--query TEXT` / `-q TEXT` | Search query | All except tv-trending, event-detect, multi-theme |
| `--timespan X` | Time window (24h, 7d, 1w, 1months, 3months, 1y) | Most commands |
| `--start-dt YYYYMMDDHHMMSS` | Exact start datetime | doc-search |
| `--end-dt YYYYMMDDHHMMSS` | Exact end datetime | doc-search |
| `--sort X` | Sort order | doc-search, context |
| `--maxrecords N` | Max results (1-250 DOC, 1-75 Context) | doc-search, context |
| `--sourcelang X` | Source language filter | doc-search, context |
| `--sourcecountry X` | Source country filter | doc-search, context |
| `--domain X` | Domain filter | doc-search |
| `--theme X` | GKG theme filter | doc-search, narrative |
| `--raw` | Raw counts instead of normalized | doc-volume |
| `--station X` | TV station ID (CNN, FOXNEWS, MSNBC, etc.) | tv-clips, tv-volume, tv-wordcloud |
| `--network X` | TV network filter (CBS, NBC, ABC) | tv-clips |
| `--smooth N` | Smoothing window in days | tv-volume |
| `--countries X` | Comma-separated FIPS codes | cross-country |
| `--themes X` | Comma-separated theme keys | event-detect |
| `--format X` | Output format (json, geojson, csv) | geo |


## Python Recipes

### DOC API: Article Search

```python
from gdelt import doc_search

# Search articles by keyword (returns dict with "articles" list)
data = doc_search("tariffs", mode="artlist", format="json", timespan="7d",
                  sort="HybridRel", maxrecords=75)

# Boolean query
data = doc_search('(recession OR "hard landing")', mode="artlist", format="json",
                  timespan="3months", sort="DateDesc", maxrecords=100)

# Filter by source country
data = doc_search("inflation", mode="artlist", format="json", timespan="7d",
                  sourcecountry="US", maxrecords=50)

# Filter by language
data = doc_search("tariffs", mode="artlist", format="json", timespan="7d",
                  sourcelang="english")

# Filter by domain
data = doc_search("recession", mode="artlist", format="json", timespan="3months",
                  domain="reuters.com")

# Filter by GKG theme
data = doc_search("economy", mode="artlist", format="json", timespan="7d",
                  theme="TAX_FNCACT")

# Filter by tone
data = doc_search("china", mode="artlist", format="json", timespan="7d",
                  tone_below=-5)  # only negative articles
data = doc_search("china", mode="artlist", format="json", timespan="7d",
                  tone_above=5)   # only positive articles

# Date range (YYYYMMDDHHMMSS)
data = doc_search("tariffs", mode="artlist", format="json",
                  start_dt="20260401000000", end_dt="20260410000000")
```

### DOC API: Volume and Tone Timelines

```python
from gdelt import doc_search

# Normalized volume timeline (% of global coverage)
vol = doc_search("recession", mode="timelinevol", format="json", timespan="3months")

# Raw article counts
vol_raw = doc_search("recession", mode="timelinevolraw", format="json", timespan="3months")

# Tone (sentiment) timeline
tone = doc_search("inflation", mode="timelinetone", format="json", timespan="3months")

# Language breakdown timeline
lang = doc_search("ukraine", mode="timelinelang", format="json", timespan="1w")

# Source country breakdown timeline
country = doc_search("tariffs", mode="timelinesourcecountry", format="json", timespan="1months")

# Tone chart (histogram)
tonechart = doc_search("recession", mode="tonechart", format="json", timespan="3months")
```

### TV API: Clips and Timelines

```python
from gdelt import tv_search

# Search TV clips
clips = tv_search("federal reserve", mode="clipgallery", format="json", timespan="7d")

# Filter by station
clips = tv_search("tariffs", mode="clipgallery", format="json", timespan="7d",
                   station="CNN")

# Volume timeline
vol = tv_search("recession", mode="timelinevol", format="json", timespan="3months",
                last24=True)

# Volume timeline for specific station
vol = tv_search("tariffs", mode="timelinevol", format="json", timespan="3months",
                station="FOXNEWS", last24=True)

# Volume with smoothing
vol = tv_search("inflation", mode="timelinevol", format="json", timespan="3months",
                timelinesmooth=5)

# Station comparison chart
stations = tv_search("tariffs", mode="stationchart", format="json", timespan="1months")

# Word cloud
wc = tv_search("federal reserve", mode="wordcloud", format="json", timespan="1months")

# Station-specific word cloud
wc = tv_search("tariffs", mode="wordcloud", format="json", timespan="1months",
               station="CNN")

# Trending topics (no query needed)
trending = tv_search("", mode="trendingtopics", format="json")

# Heatmap (hourly x daily grid)
heatmap = tv_search("recession", mode="timelinevolheatmap", format="json",
                    timespan="1months")

# Date resolution control
vol = tv_search("tariffs", mode="timelinevol", format="json", timespan="1y",
                dateres="Month")
```

### Context API: Sentence Search

```python
from gdelt import context_search

# Sentence-level search (last 72h, all terms must appear in same sentence)
data = context_search("recession unemployment", format="json", maxrecords=50,
                      sort="DateDesc")

# With language filter
data = context_search("federal reserve rate cut", format="json", maxrecords=75,
                      sourcelang="english")

# With country filter
data = context_search("tariffs", format="json", maxrecords=50,
                      sourcecountry="US")

# With domain filter
data = context_search("inflation", format="json", maxrecords=50,
                      domain="reuters.com")
```

### GEO API: Geographic Search

```python
from gdelt import geo_search

# Geographic footprint of a narrative
data = geo_search("sanctions", format="json", timespan="7d")

# GeoJSON format
data = geo_search("military conflict", format="geojson", timespan="7d")

# With filters
data = geo_search("tariffs", format="json", timespan="1months",
                  sourcecountry="US")

# With theme filter
data = geo_search("economy", format="json", timespan="7d", theme="TERROR")
```

### Using MACRO_THEMES

```python
from gdelt import doc_search, MACRO_THEMES

# Use a curated macro theme query
query = MACRO_THEMES["recession"]
data = doc_search(query, mode="timelinevol", format="json", timespan="3months")

# Iterate all themes
for theme_key, query in MACRO_THEMES.items():
    data = doc_search(query, mode="artlist", format="json", timespan="7d",
                      maxrecords=1)
    articles = data.get("articles", []) if isinstance(data, dict) else []
    print(f"{theme_key}: {len(articles)} articles")

# All 16 keys: recession, inflation, fed, tariffs, labor, housing, banking,
# china, geopolitical, energy, fiscal, crypto, ai, treasury, dollar, emerging_markets
```

### Using _build_query Helper

```python
from gdelt import _build_query, doc_search

# Programmatically construct queries with operators
q = _build_query("tariffs", {"sourcecountry": "US", "sourcelang": "english"})
data = doc_search(q, mode="artlist", format="json", timespan="7d")
```


## Composite Recipes

### Narrative Monitor (volume + tone + top articles)

```bash
python gdelt.py narrative --theme recession --timespan 3months --json
```

PRISM receives: normalized volume timeline (% of global coverage over 3 months), average tone timeline (sentiment trend), top 15 articles sorted by hybrid relevance from the last 7 days. Three API calls in one command.

### Sentiment Regime Assessment

```bash
python gdelt.py sentiment --query recession --json
```

PRISM receives: tone chart histogram over 3 months and tone chart histogram over 1 week. Comparing the two distributions reveals whether the media environment is shifting toward fear (left-skewed) or calm (centered/right-skewed).

### Cross-Country Narrative Divergence

```bash
python gdelt.py cross-country --query inflation --countries US,UK,CH,JA,GM,FR --timespan 1months --json
```

PRISM receives: tone timelines for each country (6 separate series). Shows how US media covers inflation sentiment vs. UK, China, Japan, Germany, France. Reveals narrative divergence across economies.

### TV Partisan Divergence

```bash
python gdelt.py tv-divergence --query "immigration" --timespan 3months --json
```

PRISM receives: volume timelines for CNN, FOXNEWS, MSNBC on a single topic. Reveals which network is amplifying the topic and when divergence/convergence occurs.

### Event Detection Scan

```bash
python gdelt.py event-detect --themes recession,fed,tariffs,geopolitical,banking --json
```

PRISM receives: for each theme, recent_avg (last 2 timesteps), baseline_avg (prior 5 timesteps), ratio, and status (spike/elevated/normal). A ratio > 2.0x flags a volume spike. Quick scan for macro events breaking into the news cycle.

### Multi-Theme Dashboard

```bash
python gdelt.py multi-theme --timespan 7d --json
```

PRISM receives: dict of {theme_key: article_count} across all 16 macro themes for the specified timespan. Quick pulse check on which macro narratives are active.

### Context Briefing for PRISM

```bash
python gdelt.py context --query "federal reserve rate cut" --maxrecords 75 --json
```

PRISM receives: up to 75 sentences from the last 72 hours where all query terms co-occur in the same sentence, with surrounding context. Direct feed for LLM consumption.

### Full Macro Surveillance Sweep

```bash
# Run in sequence for complete macro narrative state
python gdelt.py event-detect --themes recession,inflation,fed,tariffs,labor,housing,banking,china,geopolitical,energy,fiscal,crypto,ai,treasury,dollar,emerging_markets --json
python gdelt.py multi-theme --timespan 7d --json
python gdelt.py narrative --theme fed --timespan 3months --json
python gdelt.py sentiment --query recession --json
python gdelt.py tv-trending --json
```

PRISM receives: spike detection across all themes, article counts across all themes, full narrative breakdown for Fed, recession sentiment regime, and current TV trending topics.

### Theme Deep Dive

```bash
python gdelt.py narrative --theme tariffs --timespan 3months --json
python gdelt.py sentiment --query tariffs --json
python gdelt.py cross-country --query tariffs --countries US,CH,JA,GM --timespan 1months --json
python gdelt.py tv-divergence --query tariffs --timespan 3months --json
python gdelt.py context --query "tariffs trade war" --maxrecords 75 --json
python gdelt.py geo --query "tariffs" --timespan 7d --json
```

PRISM receives: complete narrative + sentiment + cross-country + TV partisan + sentence context + geographic footprint for a single macro theme. Six API pipelines for total narrative coverage.


## Cross-Source Recipes

### Media Narrative + Fed Policy Probability

```bash
python gdelt.py narrative --theme fed --timespan 3months --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: media volume/tone trajectory for Fed narrative + market-implied rate cut/hike probabilities. Shows whether media tone is leading or lagging rate expectations.

### Media Volume Spikes + Funding Stress

```bash
python gdelt.py event-detect --themes banking,fed,recession --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: media spike detection for financial stress themes + actual overnight rate complex and RRP usage. Cross-validates whether media fear is reflected in funding conditions.

### Tariff Narrative + Trade Data

```bash
python gdelt.py narrative --theme tariffs --timespan 3months --json
python projects/apis/tariffs/tariffs.py dashboard --json
```

PRISM receives: media volume and tone around tariff coverage + actual tariff rate data and trade policy changes. Shows whether media narrative is proportional to actual policy shifts.

### Geopolitical Narrative + Energy Prices

```bash
python gdelt.py narrative --theme geopolitical --timespan 3months --json
python gdelt.py narrative --theme energy --timespan 3months --json
```

PRISM receives: parallel narrative timelines for geopolitical risk and energy markets. Volume and tone co-movement reveals narrative coupling.

### TV Trending + Market Context

```bash
python gdelt.py tv-trending --json
python projects/apis/nyfed/nyfed.py rates --json
python projects/apis/treasury/treasury.py get dts --json
```

PRISM receives: what's dominating TV news right now + current overnight rate snapshot + Treasury cash flows. Context for whether TV narrative is market-relevant.

### Cross-Country Inflation Narrative + FRED Data

```bash
python gdelt.py cross-country --query inflation --countries US,UK,GM,JA --timespan 1months --json
python projects/apis/fred/fred.py cpi --json
```

PRISM receives: how each country's media covers inflation + actual US CPI data from FRED. Reveals whether local media tone reflects actual inflation dynamics.

### Banking Stress Narrative + FDIC Data

```bash
python gdelt.py narrative --theme banking --timespan 3months --json
python gdelt.py context --query "bank failure deposit flight" --maxrecords 75 --json
python projects/apis/fdic/fdic.py recipe bank-stress --json
```

PRISM receives: banking narrative volume/tone + actual sentence-level context + FDIC bank stress indicators. Three-layer validation: media volume, media content, actual data.

### Treasury Narrative + Auction Results

```bash
python gdelt.py narrative --theme treasury --timespan 3months --json
python projects/apis/treasurydirect/treasurydirect.py api auctions --days 30
python projects/apis/nyfed/nyfed.py pd-positions --count 12 --json
```

PRISM receives: media coverage of treasury/bond market + recent auction results + primary dealer positioning. Supply absorption narrative vs. reality.

### EM Stress Narrative + BIS Cross-Border Flows

```bash
python gdelt.py narrative --theme emerging_markets --timespan 3months --json
python gdelt.py cross-country --query "capital outflows" --countries BR,MX,IN,TH,ZA --timespan 1months --json
python projects/apis/bis/bis.py lbs --json
```

PRISM receives: EM media narrative + cross-country coverage comparison + BIS locational banking statistics for cross-border capital flows.

### Dollar Narrative + Currency Data

```bash
python gdelt.py narrative --theme dollar --timespan 3months --json
python gdelt.py cross-country --query '"us dollar" OR "dollar strength"' --countries US,JA,CH,GM --timespan 1months --json
```

PRISM receives: dollar media narrative volume/tone + how different countries' media cover dollar strength. Reveals narrative asymmetries around FX moves.


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python gdelt.py doc-search --query "tariffs" --timespan 7d --maxrecords 5`
4. Full test: `python gdelt.py narrative --theme recession --timespan 3months`


## Architecture

```
gdelt.py
  Constants       BASE_DOC, BASE_TV, BASE_CONTEXT, BASE_GEO,
                  MACRO_THEMES (16), DOC_MODES (10), TV_MODES (10),
                  TV_STATIONS {national: 8, broadcast: 9}
  HTTP            _request() with retry on 429, _build_query()
  Core APIs (4)   doc_search(), tv_search(), context_search(), geo_search()
  Display (6)     _print_articles, _print_timeline, _print_tone_chart,
                  _print_tv_clips, _print_trending, _print_json
  Interactive
    DOC (6)       article-search, volume-timeline, tone-timeline,
                  tone-chart, language-breakdown, country-breakdown
    TV (5)        clip-search, volume-timeline, station-comparison,
                  trending, word-cloud
    Context (1)   sentence-search
    GEO (1)       geographic-search
    Recipes (7)   narrative-monitor, sentiment-regime, cross-country,
                  tv-divergence, event-detection, context-briefing,
                  multi-theme-dashboard
    Tools (1)     raw-query
  Argparse (19)   doc-search, doc-volume, doc-tone, doc-tonechart,
                  doc-language, doc-country, tv-clips, tv-volume,
                  tv-stations, tv-trending, tv-wordcloud, context, geo,
                  narrative, sentiment, cross-country, tv-divergence,
                  event-detect, multi-theme
  CLI             21-item interactive menu -> argparse (19 subcommands)
```

API endpoints:
```
/api/v2/doc/doc        -> DOC API (articles, timelines, tone, language, country)
/api/v2/tv/tv          -> TV API (clips, volumes, stations, trending, wordcloud)
/api/v2/context/context -> Context API (sentence-level search, last 72h)
/api/v2/geo/geo        -> GEO API (geographic point data)
```
