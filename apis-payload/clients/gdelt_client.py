#!/usr/bin/env python3
"""
GDELT Project API Explorer
===========================

Programmatic access to the GDELT Project's suite of real-time global media monitoring APIs.
GDELT monitors news coverage from across the world in 65+ languages, processes it through
machine translation, NLP, and deep learning pipelines, and exposes it through several APIs.

This client covers the four primary GDELT 2.0 APIs:

  DOC API    -- Full text search across 3 months of global news. Article lists, volume
                timelines, tone charts, word clouds, source country breakdowns. The primary
                workhorse for narrative monitoring and media tone analysis.

  TV API     -- Search 2M+ hours of television news (2009-present) from 163 stations.
                Clip galleries, station comparisons, volume timelines, trending topics,
                word clouds. Uses Internet Archive's Television News Archive.

  Context API -- Sentence-level search with contextual snippets (last 72 hours).
                 Returns the actual sentence matching your query plus surrounding context.
                 Useful for understanding HOW a topic is being discussed, not just that
                 it's being mentioned.

  GEO API    -- Geographic analysis of news coverage. Maps locations mentioned in articles
                matching your query. Useful for understanding the geographic footprint of
                a narrative.

API Details
-----------
Base URL:   https://api.gdeltproject.org/api/v2/
Auth:       None required (fully public)
Rate Limit: Not formally documented; be reasonable (1-2 req/sec)
Format:     JSON, CSV, HTML, RSS
Coverage:   DOC/GEO = rolling 3 months; Context = 72 hours; TV = July 2009 to present

GDELT Query Syntax
------------------
All APIs share a common query syntax within the QUERY parameter:

  "phrase"                   Exact phrase match
  (a OR b OR c)              Boolean OR (must be capitalized OR)
  -keyword                   Exclude keyword
  domain:cnn.com             Filter to domain
  domainis:un.org            Exact domain match
  sourcecountry:france       Filter by source country (or 2-char FIPS code)
  sourcelang:spanish         Filter by source language (or 3-char code)
  theme:TERROR               Filter by GKG theme
  tone<-5 / tone>5           Filter by article tone score
  toneabs>10                 Filter by absolute tone (high emotion)
  near20:"trump putin"       Proximity search (words within N words)
  repeat3:"recession"        Require word appears N+ times

PRISM Use Cases
---------------
- Narrative monitoring: track media tone around macro themes (recession, tariffs, Fed)
- Media volume tracking: timeline of coverage volume spikes = event detection
- Sentiment regime: tone distribution reveals whether coverage is fear-driven vs. neutral
- Cross-language narrative: what are EM local media saying vs. DM English press?
- TV narrative: what's dominating cable news? CNN vs Fox divergence on a topic
- Context extraction: get actual sentences about macro events for LLM consumption

Dependencies
------------
pip install requests

Dual-Mode CLI
-------------
Running without arguments launches the interactive menu.
Running with a subcommand runs non-interactively for scripting and automation.
"""

import argparse
import json
import sys
import time
import csv
import io
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

BASE_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"
BASE_TV = "https://api.gdeltproject.org/api/v2/tv/tv"
BASE_CONTEXT = "https://api.gdeltproject.org/api/v2/context/context"
BASE_GEO = "https://api.gdeltproject.org/api/v2/geo/geo"

# ── GKG Theme presets for macro analysis ─────────────────────────────────────
# These are curated theme keywords that map to PRISM's analytical domains.
# Full list: http://data.gdeltproject.org/api/v2/guides/LOOKUP-GKGTHEMES.TXT

MACRO_THEMES = {
    "recession": '(recession OR "economic downturn" OR "hard landing" OR "soft landing")',
    "inflation": '(inflation OR CPI OR "price pressures" OR disinflation OR deflation)',
    "fed": '("federal reserve" OR "interest rate" OR "rate cut" OR "rate hike" OR FOMC OR powell)',
    "tariffs": '(tariff OR tariffs OR "trade war" OR "import duties" OR "trade policy")',
    "labor": '("labor market" OR unemployment OR "job growth" OR "nonfarm payrolls" OR JOLTS)',
    "housing": '("housing market" OR "home prices" OR "mortgage rates" OR "housing starts")',
    "banking": '("banking crisis" OR "bank failure" OR "deposit flight" OR "bank run" OR "credit crunch")',
    "china": '(china OR beijing OR "chinese economy" OR yuan OR renminbi)',
    "geopolitical": '(geopolitical OR sanctions OR "military conflict" OR "diplomatic crisis")',
    "energy": '("oil prices" OR "crude oil" OR "natural gas" OR OPEC OR "energy crisis")',
    "fiscal": '("fiscal policy" OR "government spending" OR "debt ceiling" OR "budget deficit")',
    "crypto": '(bitcoin OR cryptocurrency OR "digital currency" OR ethereum OR "crypto crash")',
    "ai": '("artificial intelligence" OR "AI regulation" OR "generative AI" OR "tech layoffs")',
    "treasury": '("treasury yields" OR "bond market" OR "yield curve" OR "treasury auction")',
    "dollar": '("us dollar" OR "dollar strength" OR "currency war" OR DXY)',
    "emerging_markets": '("emerging markets" OR "EM crisis" OR "capital outflows" OR "frontier markets")',
}

# ── DOC API modes ────────────────────────────────────────────────────────────

DOC_MODES = {
    "artlist": "Article list -- URLs, titles, source info for matching articles",
    "artgallery": "Article gallery -- visual magazine-style layout (HTML only)",
    "timelinevol": "Volume timeline -- % of global coverage matching query over time",
    "timelinevolraw": "Raw volume timeline -- absolute article counts (not normalized)",
    "timelinevolinfo": "Volume timeline with top articles at each timestep",
    "timelinetone": "Tone timeline -- average sentiment of matching coverage over time",
    "timelinelang": "Language timeline -- coverage volume broken down by language",
    "timelinesourcecountry": "Source country timeline -- coverage by country of origin",
    "tonechart": "Tone chart -- histogram of sentiment distribution across all matches",
    "wordcloudimagewebtags": "Image web tags word cloud -- topics from reverse image search",
}

# ── TV API modes ─────────────────────────────────────────────────────────────

TV_MODES = {
    "clipgallery": "Clip gallery -- top matching TV clips with thumbnails and transcripts",
    "showchart": "Show chart -- which TV shows mention the topic most",
    "stationchart": "Station chart -- compare coverage across stations",
    "stationdetails": "Station details -- list all available TV stations",
    "timelinevol": "Volume timeline -- airtime mentioning the topic over time",
    "timelinevolheatmap": "Volume heatmap -- hourly breakdown (day x hour grid)",
    "timelinevolstream": "Streamgraph -- same as timeline but streamgraph display",
    "timelinevolnorm": "Normalized volume -- total monitored airtime per station",
    "trendingtopics": "Trending topics -- what's dominating TV news right now",
    "wordcloud": "Word cloud -- most frequent words in matching clips",
}

# ── Major TV stations ────────────────────────────────────────────────────────

TV_STATIONS = {
    "national": ["CNN", "MSNBC", "FOXNEWS", "BBCNEWS", "CNBC", "BLOOMBERG", "CSPAN", "CSPAN2"],
    "broadcast": ["KNTV", "KGO", "KPIX", "WJLA", "WRC", "WTTG", "WCBS", "WNBC", "WABC"],
}


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _request(base_url, params, timeout=60, max_retries=3):
    """Make a GDELT API request with automatic retry on rate limits (429).
    Returns parsed JSON, raw CSV text, or None on error."""
    for attempt in range(max_retries):
        try:
            r = requests.get(base_url, params=params, timeout=timeout)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  [!] Rate limited (429). Waiting {wait}s before retry {attempt+1}/{max_retries}...")
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                print(f"  [!] HTTP {r.status_code}: {r.text[:500]}")
                return None
            content_type = r.headers.get("content-type", "")
            if "json" in content_type or params.get("format", "").lower() == "json":
                try:
                    return r.json()
                except Exception:
                    return r.text
            return r.text
        except requests.exceptions.Timeout:
            print("  [!] Request timed out (60s)")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"  [!] Connection error: {e}")
            return None
    print("  [!] Max retries exceeded on rate limit")
    return None


def _build_query(terms, operators=None):
    """Build a GDELT query string from search terms and optional operators.
    terms: the main search string (keywords, phrases, OR blocks)
    operators: dict of {operator: value} like {"sourcecountry": "US", "tone<": "-5"}
    """
    parts = [terms] if terms else []
    if operators:
        for op, val in operators.items():
            if val:
                parts.append(f"{op}:{val}" if ":" not in op and "<" not in op and ">" not in op else f"{op}{val}")
    return " ".join(parts)


# ── DOC API functions ────────────────────────────────────────────────────────

def doc_search(query, mode="artlist", format="json", timespan=None,
               start_dt=None, end_dt=None, sort=None, maxrecords=250,
               sourcelang=None, sourcecountry=None, domain=None, theme=None,
               tone_below=None, tone_above=None, trans=None):
    """Execute a GDELT DOC 2.0 API search.

    Args:
        query: Search terms (keywords, phrases, OR blocks)
        mode: Output mode (artlist, timelinevol, timelinetone, tonechart, etc.)
        format: Output format (json, csv, html)
        timespan: Time window (e.g. "3months", "7d", "24h", "60min")
        start_dt: Start datetime YYYYMMDDHHMMSS
        end_dt: End datetime YYYYMMDDHHMMSS
        sort: Sort order (DateDesc, DateAsc, ToneDesc, ToneAsc, HybridRel)
        maxrecords: Max articles to return (default 250, max 250)
        sourcelang: Filter by source language
        sourcecountry: Filter by source country
        domain: Filter by domain
        theme: Filter by GKG theme
        tone_below: Filter tone < value
        tone_above: Filter tone > value

    Returns:
        Parsed JSON dict/list or raw text depending on format
    """
    q_parts = [query] if query else []
    if sourcelang:
        q_parts.append(f"sourcelang:{sourcelang}")
    if sourcecountry:
        q_parts.append(f"sourcecountry:{sourcecountry}")
    if domain:
        q_parts.append(f"domain:{domain}")
    if theme:
        q_parts.append(f"theme:{theme}")
    if tone_below is not None:
        q_parts.append(f"tone<{tone_below}")
    if tone_above is not None:
        q_parts.append(f"tone>{tone_above}")

    params = {
        "query": " ".join(q_parts),
        "mode": mode,
        "format": format,
    }
    if timespan:
        params["timespan"] = timespan
    if start_dt:
        params["STARTDATETIME"] = start_dt
    if end_dt:
        params["ENDDATETIME"] = end_dt
    if sort:
        params["sort"] = sort
    if maxrecords:
        params["maxrecords"] = maxrecords
    if trans:
        params["trans"] = trans

    return _request(BASE_DOC, params)


def tv_search(query, mode="timelinevol", format="json", timespan=None,
              start_dt=None, end_dt=None, station=None, network=None,
              market=None, show=None, context=None, sort=None,
              datanorm=None, datacomb=None, last24=None, dateres=None,
              timelinesmooth=None):
    """Execute a GDELT TV 2.0 API search.

    Args:
        query: Search terms (keywords, phrases, OR blocks)
        mode: Output mode (clipgallery, timelinevol, stationchart, etc.)
        format: Output format (json, csv, html)
        timespan: Time window (e.g. "1y", "3months", "7d")
        start_dt: Start datetime YYYYMMDDHHMMSS
        end_dt: End datetime YYYYMMDDHHMMSS
        station: Filter by station ID (e.g. CNN, FOXNEWS, MSNBC)
        network: Filter by network (e.g. CBS, NBC, ABC)
        market: Filter by geographic market (e.g. "San Francisco")
        show: Filter by show name
        context: Additional context search (15s before/after clips)
        sort: Sort order (DateDesc, DateAsc)
        datanorm: Normalization mode for charts
        datacomb: Combine all stations into single series
        last24: Include last 24 hours (partial data)
        dateres: Date resolution (Hour, Day, Week, Month, Year)
        timelinesmooth: Smoothing window (integer days)
    """
    q_parts = [query] if query else []
    if station:
        q_parts.append(f"station:{station}")
    if network:
        q_parts.append(f"network:{network}")
    if market:
        q_parts.append(f'market:"{market}"')
    if show:
        q_parts.append(f'show:"{show}"')
    if context:
        q_parts.append(f'context:"{context}"')

    needs_station = mode.lower() in ("timelinevol", "timelinevolheatmap", "timelinevolstream",
                                      "timelinevolnorm", "stationchart", "wordcloud")
    if needs_station and not station and not network and not market:
        q_parts.append('market:"National"')

    params = {
        "query": " ".join(q_parts),
        "mode": mode,
        "format": format,
    }
    if timespan:
        params["timespan"] = timespan
    if start_dt:
        params["STARTDATETIME"] = start_dt
    if end_dt:
        params["ENDDATETIME"] = end_dt
    if sort:
        params["sort"] = sort
    if datanorm:
        params["datanorm"] = datanorm
    if datacomb:
        params["datacomb"] = datacomb
    if last24:
        params["last24"] = "yes"
    if dateres:
        params["dateres"] = dateres
    if timelinesmooth:
        params["timelinesmooth"] = timelinesmooth

    return _request(BASE_TV, params)


def context_search(query, format="json", timespan=None,
                   start_dt=None, end_dt=None, sort=None, maxrecords=75,
                   sourcelang=None, sourcecountry=None, domain=None):
    """Execute a GDELT Context 2.0 API search (sentence-level, last 72h).

    Returns matching sentences with surrounding context. All search terms
    must appear in the same sentence.
    """
    q_parts = [query] if query else []
    if sourcelang:
        q_parts.append(f"sourcelang:{sourcelang}")
    if sourcecountry:
        q_parts.append(f"sourcecountry:{sourcecountry}")
    if domain:
        q_parts.append(f"domain:{domain}")

    params = {
        "query": " ".join(q_parts),
        "mode": "artlist",
        "format": format,
    }
    if timespan:
        params["timespan"] = timespan
    if start_dt:
        params["STARTDATETIME"] = start_dt
    if end_dt:
        params["ENDDATETIME"] = end_dt
    if sort:
        params["sort"] = sort
    if maxrecords:
        params["maxrecords"] = maxrecords

    return _request(BASE_CONTEXT, params)


def geo_search(query, mode="pointdata", format="geojson", timespan=None,
               start_dt=None, end_dt=None, sourcelang=None,
               sourcecountry=None, domain=None, theme=None):
    """Execute a GDELT GEO 2.0 API search (geographic event mapping)."""
    q_parts = [query] if query else []
    if sourcelang:
        q_parts.append(f"sourcelang:{sourcelang}")
    if sourcecountry:
        q_parts.append(f"sourcecountry:{sourcecountry}")
    if domain:
        q_parts.append(f"domain:{domain}")
    if theme:
        q_parts.append(f"theme:{theme}")

    params = {
        "query": " ".join(q_parts),
        "mode": mode,
        "format": format,
    }
    if timespan:
        params["timespan"] = timespan
    if start_dt:
        params["STARTDATETIME"] = start_dt
    if end_dt:
        params["ENDDATETIME"] = end_dt

    return _request(BASE_GEO, params)


# ── Display helpers ──────────────────────────────────────────────────────────

def _print_articles(data, max_show=25):
    """Display DOC/Context API article list results."""
    if not data:
        print("  (no data)")
        return

    articles = []
    if isinstance(data, dict):
        articles = data.get("articles", [])
    elif isinstance(data, list):
        articles = data
    else:
        print(f"  Unexpected response type: {type(data)}")
        print(f"  {str(data)[:500]}")
        return

    if not articles:
        print("  (no articles found)")
        return

    print(f"  Found {len(articles)} articles")
    print()

    for i, art in enumerate(articles[:max_show]):
        title = art.get("title", "(no title)")
        url = art.get("url", "")
        domain = art.get("domain", "")
        lang = art.get("language", "")
        country = art.get("sourcecountry", art.get("seendate", ""))
        tone = art.get("tone", "")
        date = art.get("seendate", "")

        print(f"  {i+1:3d}. {title[:90]}")
        detail_parts = []
        if domain:
            detail_parts.append(domain)
        if country:
            detail_parts.append(country)
        if lang:
            detail_parts.append(f"lang:{lang}")
        if tone:
            try:
                detail_parts.append(f"tone:{float(tone):+.1f}")
            except (ValueError, TypeError):
                detail_parts.append(f"tone:{tone}")
        if date:
            detail_parts.append(str(date)[:10])
        if detail_parts:
            print(f"       {' | '.join(detail_parts)}")
        if url:
            print(f"       {url[:100]}")

        excerpt = art.get("context", art.get("excerpt", ""))
        if excerpt:
            print(f"       >> {str(excerpt)[:150]}")
        print()


def _print_timeline(data):
    """Display timeline data (volume, tone, etc.)."""
    if not data:
        print("  (no data)")
        return

    timeline = []
    if isinstance(data, dict):
        timeline = data.get("timeline", [])
        if not timeline and "series" in data:
            timeline = data.get("series", [])
    elif isinstance(data, list):
        timeline = data

    if not timeline:
        print("  (no timeline data)")
        if isinstance(data, dict):
            print(f"  Keys: {list(data.keys())}")
        return

    for series in timeline:
        series_name = series.get("series", "unknown")
        datapoints = series.get("data", [])
        print(f"\n  Series: {series_name} ({len(datapoints)} points)")

        if not datapoints:
            continue

        vals = []
        for dp in datapoints:
            date = dp.get("date", "")
            value = dp.get("value", dp.get("norm", 0))
            vals.append((date, value))

        max_val = max(v for _, v in vals) if vals else 1
        if max_val == 0:
            max_val = 1

        for date_str, val in vals[:60]:
            bar_len = int((val / max_val) * 40) if max_val > 0 else 0
            bar = "#" * bar_len
            if isinstance(val, float):
                print(f"    {str(date_str)[:16]:16s}  {val:8.2f}  {bar}")
            else:
                print(f"    {str(date_str)[:16]:16s}  {val:8d}  {bar}")

        if len(vals) > 60:
            print(f"    ... ({len(vals) - 60} more datapoints)")


def _print_tone_chart(data):
    """Display tone chart histogram."""
    if not data:
        print("  (no data)")
        return

    tonechart = []
    if isinstance(data, dict):
        tonechart = data.get("tonechart", data.get("bins", []))
    elif isinstance(data, list):
        tonechart = data

    if not tonechart:
        print("  (no tone chart data)")
        return

    max_count = max(b.get("count", b.get("value", 0)) for b in tonechart) if tonechart else 1
    if max_count == 0:
        max_count = 1

    print(f"  {'Tone':>8s}  {'Count':>8s}  Distribution")
    print(f"  {'----':>8s}  {'-----':>8s}  ------------")
    for b in tonechart:
        tone = b.get("bin", b.get("tone", 0))
        count = b.get("count", b.get("value", 0))
        bar_len = int((count / max_count) * 50)
        bar = "#" * bar_len
        print(f"  {tone:8.1f}  {count:8d}  {bar}")


def _print_tv_clips(data, max_show=20):
    """Display TV clip gallery results."""
    if not data:
        print("  (no data)")
        return

    clips = []
    if isinstance(data, dict):
        clips = data.get("clips", [])
    elif isinstance(data, list):
        clips = data

    if not clips:
        print("  (no clips found)")
        return

    print(f"  Found {len(clips)} clips")
    print()

    for i, clip in enumerate(clips[:max_show]):
        show = clip.get("show", "(unknown show)")
        station = clip.get("station", "")
        date = clip.get("date", "")
        snippet = clip.get("snippet", "")
        url = clip.get("preview_url", clip.get("url", ""))

        print(f"  {i+1:3d}. [{station}] {show}")
        if date:
            print(f"       {date}")
        if snippet:
            print(f"       >> {snippet[:200]}")
        if url:
            print(f"       {url[:100]}")
        print()


def _print_trending(data):
    """Display TV trending topics."""
    if not data:
        print("  (no data)")
        return

    if isinstance(data, dict):
        for section, items in data.items():
            print(f"\n  {section}:")
            if isinstance(items, list):
                for item in items[:20]:
                    if isinstance(item, dict):
                        print(f"    - {item}")
                    else:
                        print(f"    - {item}")
            elif isinstance(items, dict):
                for k, v in items.items():
                    print(f"    {k}: {v}")
    elif isinstance(data, list):
        for item in data[:30]:
            print(f"    - {item}")


def _print_json(data, max_chars=5000):
    """Pretty-print JSON data, truncated."""
    if data is None:
        print("  (no data)")
        return
    if isinstance(data, str):
        print(data[:max_chars])
        return
    output = json.dumps(data, indent=2, default=str)
    print(output[:max_chars])
    if len(output) > max_chars:
        print(f"\n  ... truncated ({len(output):,} chars total)")


def _prompt(msg, default=""):
    suffix = f" [{default}]" if default else ""
    val = input(f"  {msg}{suffix}: ").strip()
    return val if val else default


def _prompt_export(data, prefix):
    """Prompt to export results."""
    if not data:
        return
    export = _prompt("Export? (json/csv/no)", "no")
    if export.lower() in ("no", "n", ""):
        return
    ts = time.strftime("%Y%m%d_%H%M%S")
    if export.lower() == "json":
        fname = f"{prefix}_{ts}.json"
        with open(fname, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"  Saved to {fname}")
    elif export.lower() == "csv":
        fname = f"{prefix}_{ts}.csv"
        if isinstance(data, dict):
            articles = data.get("articles", data.get("timeline", []))
        elif isinstance(data, list):
            articles = data
        else:
            print("  Cannot export this format to CSV")
            return
        if articles and isinstance(articles[0], dict):
            headers = list(articles[0].keys())
            with open(fname, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
                w.writeheader()
                w.writerows(articles)
            print(f"  Saved {len(articles)} records to {fname}")


# ── Interactive DOC commands ─────────────────────────────────────────────────

def cmd_doc_article_search():
    """Search global news articles (DOC API -- ArtList mode)."""
    print("\n== DOC: Article Search ==")
    query = _prompt("Search query (keywords, phrases, OR blocks)")
    if not query:
        return
    timespan = _prompt("Timespan (e.g. 24h, 7d, 1w, 3months)", "7d")
    sort = _prompt("Sort (DateDesc/DateAsc/ToneDesc/ToneAsc/HybridRel)", "HybridRel")
    maxrecords = int(_prompt("Max records (1-250)", "75"))
    sourcelang = _prompt("Source language filter (e.g. english, spanish, empty for all)")
    sourcecountry = _prompt("Source country filter (e.g. US, GB, empty for all)")
    domain = _prompt("Domain filter (e.g. reuters.com, empty for all)")

    data = doc_search(
        query, mode="artlist", format="json", timespan=timespan,
        sort=sort, maxrecords=maxrecords,
        sourcelang=sourcelang or None, sourcecountry=sourcecountry or None,
        domain=domain or None,
    )
    _print_articles(data)
    _prompt_export(data, "doc_articles")


def cmd_doc_volume_timeline():
    """Track coverage volume over time (DOC API -- TimelineVol mode)."""
    print("\n== DOC: Volume Timeline ==")
    query = _prompt("Search query")
    if not query:
        return
    timespan = _prompt("Timespan", "3months")
    raw = _prompt("Raw counts or normalized? (raw/norm)", "norm")
    mode = "timelinevolraw" if raw.lower() == "raw" else "timelinevol"

    data = doc_search(query, mode=mode, format="json", timespan=timespan)
    _print_timeline(data)
    _prompt_export(data, "doc_volume")


def cmd_doc_tone_timeline():
    """Track average sentiment over time (DOC API -- TimelineTone mode)."""
    print("\n== DOC: Tone Timeline ==")
    query = _prompt("Search query")
    if not query:
        return
    timespan = _prompt("Timespan", "3months")

    data = doc_search(query, mode="timelinetone", format="json", timespan=timespan)
    _print_timeline(data)
    _prompt_export(data, "doc_tone")


def cmd_doc_tone_chart():
    """Sentiment distribution histogram (DOC API -- ToneChart mode)."""
    print("\n== DOC: Tone Chart ==")
    query = _prompt("Search query")
    if not query:
        return
    timespan = _prompt("Timespan", "3months")

    data = doc_search(query, mode="tonechart", format="json", timespan=timespan)
    _print_tone_chart(data)
    _prompt_export(data, "doc_tonechart")


def cmd_doc_language_breakdown():
    """Coverage volume by language (DOC API -- TimelineLang mode)."""
    print("\n== DOC: Language Breakdown ==")
    query = _prompt("Search query")
    if not query:
        return
    timespan = _prompt("Timespan", "1w")

    data = doc_search(query, mode="timelinelang", format="json", timespan=timespan)
    _print_timeline(data)
    _prompt_export(data, "doc_language")


def cmd_doc_country_breakdown():
    """Coverage volume by source country (DOC API -- TimelineSourceCountry)."""
    print("\n== DOC: Source Country Breakdown ==")
    query = _prompt("Search query")
    if not query:
        return
    timespan = _prompt("Timespan", "1w")

    data = doc_search(query, mode="timelinesourcecountry", format="json", timespan=timespan)
    _print_timeline(data)
    _prompt_export(data, "doc_country")


# ── Interactive TV commands ──────────────────────────────────────────────────

def cmd_tv_clip_search():
    """Search TV news clips (TV API -- ClipGallery mode)."""
    print("\n== TV: Clip Search ==")
    query = _prompt("Search query")
    if not query:
        return
    station = _prompt("Station filter (CNN/FOXNEWS/MSNBC/CNBC/BLOOMBERG/empty for all)")
    timespan = _prompt("Timespan (e.g. 7d, 1months, 1y)", "7d")

    data = tv_search(
        query, mode="clipgallery", format="json", timespan=timespan,
        station=station or None,
    )
    _print_tv_clips(data)
    _prompt_export(data, "tv_clips")


def cmd_tv_volume_timeline():
    """Track TV coverage volume over time."""
    print("\n== TV: Volume Timeline ==")
    query = _prompt("Search query")
    if not query:
        return
    station = _prompt("Station filter (empty for national)")
    timespan = _prompt("Timespan", "3months")

    data = tv_search(
        query, mode="timelinevol", format="json", timespan=timespan,
        station=station or None, last24=True,
    )
    _print_timeline(data)
    _prompt_export(data, "tv_volume")


def cmd_tv_station_comparison():
    """Compare coverage across TV stations."""
    print("\n== TV: Station Comparison ==")
    query = _prompt("Search query")
    if not query:
        return
    timespan = _prompt("Timespan", "1months")

    data = tv_search(
        query, mode="stationchart", format="json", timespan=timespan,
    )
    _print_json(data)
    _prompt_export(data, "tv_stations")


def cmd_tv_trending():
    """Get currently trending topics on TV news."""
    print("\n== TV: Trending Topics ==")
    data = tv_search("", mode="trendingtopics", format="json")
    _print_trending(data)
    _prompt_export(data, "tv_trending")


def cmd_tv_word_cloud():
    """Word cloud of terms co-occurring with your query on TV."""
    print("\n== TV: Word Cloud ==")
    query = _prompt("Search query")
    if not query:
        return
    station = _prompt("Station filter (empty for all)")
    timespan = _prompt("Timespan", "1months")

    data = tv_search(
        query, mode="wordcloud", format="json", timespan=timespan,
        station=station or None,
    )
    _print_json(data)
    _prompt_export(data, "tv_wordcloud")


# ── Interactive Context commands ─────────────────────────────────────────────

def cmd_context_search():
    """Sentence-level search with snippets (Context API -- last 72h)."""
    print("\n== Context: Sentence Search ==")
    print("  (All terms must appear in same sentence. Searches last 72 hours.)")
    query = _prompt("Search query")
    if not query:
        return
    maxrecords = int(_prompt("Max records (1-75)", "50"))
    sort = _prompt("Sort (DateDesc/DateAsc)", "DateDesc")

    data = context_search(
        query, format="json", sort=sort, maxrecords=maxrecords,
    )
    _print_articles(data)
    _prompt_export(data, "context_sentences")


# ── Interactive GEO command ──────────────────────────────────────────────────

def cmd_geo_search():
    """Geographic analysis of news coverage (GEO API)."""
    print("\n== GEO: Geographic Coverage ==")
    query = _prompt("Search query")
    if not query:
        return
    timespan = _prompt("Timespan", "7d")
    format_choice = _prompt("Format (geojson/json/csv)", "json")

    data = geo_search(
        query, format=format_choice, timespan=timespan,
    )
    _print_json(data)
    _prompt_export(data, "geo_coverage")


# ── Recipe commands (pre-built macro queries) ────────────────────────────────

def cmd_recipe_narrative_monitor():
    """Monitor media narrative around a macro theme.
    Combines volume timeline + tone chart + top articles."""
    print("\n== Recipe: Narrative Monitor ==")
    print("  Available macro themes:")
    for i, (key, query) in enumerate(MACRO_THEMES.items()):
        print(f"    {i+1:2d}. {key:20s} -> {query[:60]}")
    print(f"    {len(MACRO_THEMES)+1:2d}. custom")

    choice = _prompt("Choose theme number or name", "1")
    if choice.isdigit():
        idx = int(choice) - 1
        keys = list(MACRO_THEMES.keys())
        if idx < len(keys):
            theme_key = keys[idx]
            query = MACRO_THEMES[theme_key]
        else:
            query = _prompt("Custom query")
            theme_key = "custom"
    elif choice in MACRO_THEMES:
        theme_key = choice
        query = MACRO_THEMES[choice]
    else:
        query = choice
        theme_key = "custom"

    if not query:
        return

    timespan = _prompt("Timespan", "3months")

    print(f"\n  Fetching narrative data for: {theme_key}")
    print(f"  Query: {query}")

    print("\n  --- Volume Timeline ---")
    vol_data = doc_search(query, mode="timelinevol", format="json", timespan=timespan)
    _print_timeline(vol_data)

    print("\n  --- Tone Timeline ---")
    tone_data = doc_search(query, mode="timelinetone", format="json", timespan=timespan)
    _print_timeline(tone_data)

    print("\n  --- Top Articles ---")
    art_data = doc_search(query, mode="artlist", format="json", timespan="7d",
                          sort="HybridRel", maxrecords=15)
    _print_articles(art_data, max_show=10)

    combined = {
        "theme": theme_key,
        "query": query,
        "volume_timeline": vol_data,
        "tone_timeline": tone_data,
        "top_articles": art_data,
    }
    _prompt_export(combined, f"narrative_{theme_key}")


def cmd_recipe_sentiment_regime():
    """Tone distribution for a topic -- reveals fear vs. calm media environment."""
    print("\n== Recipe: Sentiment Regime ==")
    query = _prompt("Search query (or macro theme name)")
    if query in MACRO_THEMES:
        query = MACRO_THEMES[query]
    if not query:
        return

    print("\n  --- Tone Chart (3 month) ---")
    data_3m = doc_search(query, mode="tonechart", format="json", timespan="3months")
    _print_tone_chart(data_3m)

    print("\n  --- Tone Chart (1 week) ---")
    data_1w = doc_search(query, mode="tonechart", format="json", timespan="1w")
    _print_tone_chart(data_1w)

    combined = {"query": query, "tone_3m": data_3m, "tone_1w": data_1w}
    _prompt_export(combined, "sentiment_regime")


def cmd_recipe_cross_country_narrative():
    """Compare how different countries' media cover a topic."""
    print("\n== Recipe: Cross-Country Narrative ==")
    query = _prompt("Search query (or macro theme name)")
    if query in MACRO_THEMES:
        query = MACRO_THEMES[query]
    if not query:
        return

    countries_str = _prompt("Countries (comma-separated FIPS codes)", "US,UK,CH,JA,GM,FR")
    countries = [c.strip() for c in countries_str.split(",")]
    timespan = _prompt("Timespan", "1months")

    results = {}
    for country in countries:
        print(f"\n  Fetching tone timeline for {country}...")
        data = doc_search(query, mode="timelinetone", format="json",
                          timespan=timespan, sourcecountry=country)
        results[country] = data
        if data:
            _print_timeline(data)

    _prompt_export(results, "cross_country")


def cmd_recipe_tv_narrative_divergence():
    """Compare CNN vs Fox vs MSNBC coverage of a topic."""
    print("\n== Recipe: TV Narrative Divergence ==")
    query = _prompt("Search query")
    if not query:
        return
    timespan = _prompt("Timespan", "3months")

    stations = ["CNN", "FOXNEWS", "MSNBC"]
    results = {}
    for st in stations:
        print(f"\n  Fetching {st} timeline...")
        data = tv_search(query, mode="timelinevol", format="json",
                         timespan=timespan, station=st, last24=True)
        results[st] = data
        if data:
            _print_timeline(data)

    _prompt_export(results, "tv_divergence")


def cmd_recipe_event_detection():
    """Detect media spikes -- find sudden coverage surges for macro topics."""
    print("\n== Recipe: Event Detection (Volume Spikes) ==")

    themes_to_check = _prompt(
        "Themes to scan (comma-separated, or 'all')",
        "recession,fed,tariffs,geopolitical,banking"
    )

    if themes_to_check.lower() == "all":
        check_list = list(MACRO_THEMES.keys())
    else:
        check_list = [t.strip() for t in themes_to_check.split(",")]

    print(f"\n  Scanning {len(check_list)} themes for recent volume spikes...")
    print(f"  (Comparing last 24h vs 7d baseline)")

    for theme_key in check_list:
        query = MACRO_THEMES.get(theme_key, theme_key)
        print(f"\n  {theme_key}: ", end="", flush=True)

        data_7d = doc_search(query, mode="timelinevolraw", format="json", timespan="7d")
        time.sleep(0.5)

        if not data_7d:
            print("(no data)")
            continue

        timeline = []
        if isinstance(data_7d, dict):
            for series in data_7d.get("timeline", []):
                timeline.extend(series.get("data", []))

        if len(timeline) < 2:
            print("(insufficient data)")
            continue

        recent = [dp.get("value", 0) for dp in timeline[-2:]]
        baseline = [dp.get("value", 0) for dp in timeline[:-2]]

        recent_avg = sum(recent) / len(recent) if recent else 0
        baseline_avg = sum(baseline) / len(baseline) if baseline else 0

        if baseline_avg > 0:
            ratio = recent_avg / baseline_avg
            indicator = "***SPIKE***" if ratio > 2.0 else "ELEVATED" if ratio > 1.5 else "normal"
            print(f"recent={recent_avg:.0f} baseline={baseline_avg:.0f} ratio={ratio:.2f}x  {indicator}")
        else:
            print(f"recent={recent_avg:.0f} (no baseline)")


def cmd_recipe_context_briefing():
    """Pull sentence-level context for a topic -- feeds directly into PRISM context."""
    print("\n== Recipe: Context Briefing ==")
    query = _prompt("Search query (or macro theme name)")
    if query in MACRO_THEMES:
        query = MACRO_THEMES[query]
    if not query:
        return

    maxrecords = int(_prompt("Max sentences", "50"))

    data = context_search(query, format="json", maxrecords=maxrecords, sort="DateDesc")
    _print_articles(data)
    _prompt_export(data, "context_briefing")


def cmd_recipe_multi_theme_dashboard():
    """Quick tone snapshot across all macro themes."""
    print("\n== Recipe: Multi-Theme Dashboard ==")
    timespan = _prompt("Timespan", "7d")

    print(f"\n  {'Theme':20s}  {'Articles':>8s}  Query")
    print(f"  {'─'*20}  {'─'*8}  {'─'*50}")

    results = {}
    for theme_key, query in MACRO_THEMES.items():
        data = doc_search(query, mode="artlist", format="json",
                          timespan=timespan, maxrecords=1, sort="HybridRel")
        count = 0
        if isinstance(data, dict):
            articles = data.get("articles", [])
            count = len(articles)
        elif isinstance(data, list):
            count = len(data)

        print(f"  {theme_key:20s}  {count:8d}  {query[:50]}")
        results[theme_key] = data
        time.sleep(0.3)

    _prompt_export(results, "multi_theme_dashboard")


# ── Raw query ────────────────────────────────────────────────────────────────

def cmd_raw_query():
    """Execute a fully custom GDELT API call."""
    print("\n== Raw API Query ==")
    api_choice = _prompt("API (doc/tv/context/geo)", "doc")

    base_map = {
        "doc": BASE_DOC,
        "tv": BASE_TV,
        "context": BASE_CONTEXT,
        "geo": BASE_GEO,
    }
    base = base_map.get(api_choice, BASE_DOC)

    query = _prompt("Full query string")
    mode = _prompt("Mode")
    format_choice = _prompt("Format (json/csv/html)", "json")

    params = {"query": query, "mode": mode, "format": format_choice}

    for key in ["timespan", "STARTDATETIME", "ENDDATETIME", "sort", "maxrecords",
                "datanorm", "datacomb", "last24", "dateres", "timelinesmooth"]:
        val = _prompt(f"  {key} (empty to skip)")
        if val:
            params[key] = val

    data = _request(base, params)
    _print_json(data)
    _prompt_export(data, f"raw_{api_choice}")


# ── Command registry ─────────────────────────────────────────────────────────

COMMAND_MAP = {
    # DOC API
    "1": cmd_doc_article_search,
    "2": cmd_doc_volume_timeline,
    "3": cmd_doc_tone_timeline,
    "4": cmd_doc_tone_chart,
    "5": cmd_doc_language_breakdown,
    "6": cmd_doc_country_breakdown,
    # TV API
    "10": cmd_tv_clip_search,
    "11": cmd_tv_volume_timeline,
    "12": cmd_tv_station_comparison,
    "13": cmd_tv_trending,
    "14": cmd_tv_word_cloud,
    # Context API
    "20": cmd_context_search,
    # GEO API
    "25": cmd_geo_search,
    # Recipes
    "30": cmd_recipe_narrative_monitor,
    "31": cmd_recipe_sentiment_regime,
    "32": cmd_recipe_cross_country_narrative,
    "33": cmd_recipe_tv_narrative_divergence,
    "34": cmd_recipe_event_detection,
    "35": cmd_recipe_context_briefing,
    "36": cmd_recipe_multi_theme_dashboard,
    # Tools
    "90": cmd_raw_query,
}


def interactive_loop():
    while True:
        print("\n" + "=" * 76)
        print("  GDELT Project API Explorer")
        print("=" * 76)
        print("\n  DOC API (global news, rolling 3 months):")
        print("    1.  Article search       - search articles by keyword/phrase/theme")
        print("    2.  Volume timeline      - coverage volume over time")
        print("    3.  Tone timeline        - average sentiment over time")
        print("    4.  Tone chart           - sentiment distribution histogram")
        print("    5.  Language breakdown    - coverage by source language")
        print("    6.  Country breakdown     - coverage by source country")
        print()
        print("  TV API (television news, 2009-present):")
        print("    10. Clip search          - search TV news clips with transcripts")
        print("    11. Volume timeline      - TV coverage volume over time")
        print("    12. Station comparison   - compare stations (CNN vs Fox vs MSNBC)")
        print("    13. Trending topics      - what's dominating TV news now")
        print("    14. Word cloud           - co-occurring terms on TV")
        print()
        print("  CONTEXT API (sentence-level, last 72h):")
        print("    20. Sentence search      - find sentences mentioning your query")
        print()
        print("  GEO API (geographic coverage):")
        print("    25. Geographic search    - map locations mentioned in coverage")
        print()
        print("  MACRO RECIPES:")
        print("    30. Narrative monitor    - volume + tone + articles for macro theme")
        print("    31. Sentiment regime     - tone distribution (fear vs calm)")
        print("    32. Cross-country        - how different countries cover a topic")
        print("    33. TV divergence        - CNN vs Fox vs MSNBC on a topic")
        print("    34. Event detection      - scan themes for volume spikes")
        print("    35. Context briefing     - sentence-level context for PRISM")
        print("    36. Multi-theme dash     - quick article count across all themes")
        print()
        print("  TOOLS:")
        print("    90. Raw query            - fully custom API call")
        print()
        print("    q.  Quit")

        choice = input("\n  Choice: ").strip()
        if choice.lower() in ("q", "quit", "exit"):
            print("  Bye.")
            break
        if choice in COMMAND_MAP:
            try:
                COMMAND_MAP[choice]()
            except KeyboardInterrupt:
                print("\n  (interrupted)")
            except Exception as e:
                print(f"  [!] Error: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("  Invalid choice.")


# ── Non-interactive CLI ──────────────────────────────────────────────────────

def build_argparse():
    parser = argparse.ArgumentParser(
        description="GDELT Project API Explorer -- global media monitoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python gdelt.py doc-search --query "tariffs" --timespan 7d --maxrecords 25
  python gdelt.py doc-search --query '"federal reserve" (rate OR hike OR cut)' --sort DateDesc
  python gdelt.py doc-volume --query "recession" --timespan 3months
  python gdelt.py doc-tone --query "inflation" --timespan 3months
  python gdelt.py doc-tonechart --query "china tariffs" --timespan 1months
  python gdelt.py doc-language --query "ukraine" --timespan 1w
  python gdelt.py doc-country --query "inflation" --timespan 1months
  python gdelt.py tv-clips --query "federal reserve" --station CNN --timespan 7d
  python gdelt.py tv-volume --query "recession" --timespan 1y
  python gdelt.py tv-stations --query "tariffs" --timespan 3months
  python gdelt.py tv-trending
  python gdelt.py context --query "recession unemployment" --maxrecords 50
  python gdelt.py narrative --theme recession --timespan 3months
  python gdelt.py event-detect --themes recession,fed,tariffs
  python gdelt.py multi-theme --timespan 7d
""")
    sub = parser.add_subparsers(dest="command")

    # DOC search
    p = sub.add_parser("doc-search", help="Search global news articles")
    p.add_argument("--query", "-q", required=True, help="Search query")
    p.add_argument("--timespan", default="7d")
    p.add_argument("--start-dt", default="")
    p.add_argument("--end-dt", default="")
    p.add_argument("--sort", default="HybridRel", choices=["DateDesc", "DateAsc", "ToneDesc", "ToneAsc", "HybridRel"])
    p.add_argument("--maxrecords", type=int, default=75)
    p.add_argument("--sourcelang", default="")
    p.add_argument("--sourcecountry", default="")
    p.add_argument("--domain", default="")
    p.add_argument("--theme", default="")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # DOC volume timeline
    p = sub.add_parser("doc-volume", help="Coverage volume timeline")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--timespan", default="3months")
    p.add_argument("--raw", action="store_true", help="Raw counts instead of normalized")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # DOC tone timeline
    p = sub.add_parser("doc-tone", help="Average sentiment timeline")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--timespan", default="3months")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # DOC tone chart
    p = sub.add_parser("doc-tonechart", help="Sentiment distribution histogram")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--timespan", default="3months")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # DOC language breakdown
    p = sub.add_parser("doc-language", help="Coverage by source language")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--timespan", default="1w")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # DOC country breakdown
    p = sub.add_parser("doc-country", help="Coverage by source country")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--timespan", default="1w")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # TV clips
    p = sub.add_parser("tv-clips", help="Search TV news clips")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--station", default="")
    p.add_argument("--network", default="")
    p.add_argument("--timespan", default="7d")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # TV volume
    p = sub.add_parser("tv-volume", help="TV coverage volume timeline")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--station", default="")
    p.add_argument("--timespan", default="3months")
    p.add_argument("--smooth", type=int, default=0)
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # TV station comparison
    p = sub.add_parser("tv-stations", help="Compare TV stations")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--timespan", default="1months")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # TV trending
    p = sub.add_parser("tv-trending", help="Trending topics on TV news")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # TV word cloud
    p = sub.add_parser("tv-wordcloud", help="Word cloud for TV topic")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--station", default="")
    p.add_argument("--timespan", default="1months")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # Context search
    p = sub.add_parser("context", help="Sentence-level search (last 72h)")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--maxrecords", type=int, default=50)
    p.add_argument("--sort", default="DateDesc", choices=["DateDesc", "DateAsc"])
    p.add_argument("--sourcelang", default="")
    p.add_argument("--sourcecountry", default="")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # GEO search
    p = sub.add_parser("geo", help="Geographic news coverage")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--timespan", default="7d")
    p.add_argument("--format", default="json", choices=["json", "geojson", "csv"])
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # Narrative monitor recipe
    p = sub.add_parser("narrative", help="Full narrative monitor (volume + tone + articles)")
    p.add_argument("--theme", required=True, help=f"Macro theme or custom query. Themes: {', '.join(MACRO_THEMES.keys())}")
    p.add_argument("--timespan", default="3months")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # Sentiment regime recipe
    p = sub.add_parser("sentiment", help="Sentiment regime analysis")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # Cross-country recipe
    p = sub.add_parser("cross-country", help="Cross-country narrative comparison")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--countries", default="US,UK,CH,JA,GM,FR")
    p.add_argument("--timespan", default="1months")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # TV divergence recipe
    p = sub.add_parser("tv-divergence", help="CNN vs Fox vs MSNBC comparison")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--timespan", default="3months")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    # Event detection recipe
    p = sub.add_parser("event-detect", help="Scan themes for volume spikes")
    p.add_argument("--themes", default="recession,fed,tariffs,geopolitical,banking")
    p.add_argument("--json", action="store_true")

    # Multi-theme dashboard
    p = sub.add_parser("multi-theme", help="Quick article count across all macro themes")
    p.add_argument("--timespan", default="7d")
    p.add_argument("--json", action="store_true")
    p.add_argument("--export", choices=["json", "csv"], default="")

    return parser


def _ni_output(data, args, prefix, display_fn=None):
    """Handle non-interactive output."""
    if not data:
        print("(no data)")
        return
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2, default=str))
        return
    if display_fn:
        display_fn(data)
    else:
        _print_json(data)

    export_fmt = getattr(args, "export", "")
    if export_fmt:
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = f"{prefix}_{ts}.{export_fmt}"
        with open(fname, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Exported to {fname}")


def run_noninteractive(args):
    cmd = args.command

    if cmd == "doc-search":
        data = doc_search(
            args.query, mode="artlist", format="json", timespan=args.timespan,
            start_dt=args.start_dt or None, end_dt=args.end_dt or None,
            sort=args.sort, maxrecords=args.maxrecords,
            sourcelang=args.sourcelang or None,
            sourcecountry=args.sourcecountry or None,
            domain=args.domain or None, theme=args.theme or None,
        )
        _ni_output(data, args, "doc_articles", _print_articles)

    elif cmd == "doc-volume":
        mode = "timelinevolraw" if args.raw else "timelinevol"
        data = doc_search(args.query, mode=mode, format="json", timespan=args.timespan)
        _ni_output(data, args, "doc_volume", _print_timeline)

    elif cmd == "doc-tone":
        data = doc_search(args.query, mode="timelinetone", format="json", timespan=args.timespan)
        _ni_output(data, args, "doc_tone", _print_timeline)

    elif cmd == "doc-tonechart":
        data = doc_search(args.query, mode="tonechart", format="json", timespan=args.timespan)
        _ni_output(data, args, "doc_tonechart", _print_tone_chart)

    elif cmd == "doc-language":
        data = doc_search(args.query, mode="timelinelang", format="json", timespan=args.timespan)
        _ni_output(data, args, "doc_language", _print_timeline)

    elif cmd == "doc-country":
        data = doc_search(args.query, mode="timelinesourcecountry", format="json", timespan=args.timespan)
        _ni_output(data, args, "doc_country", _print_timeline)

    elif cmd == "tv-clips":
        data = tv_search(
            args.query, mode="clipgallery", format="json", timespan=args.timespan,
            station=args.station or None, network=args.network or None,
        )
        _ni_output(data, args, "tv_clips", _print_tv_clips)

    elif cmd == "tv-volume":
        data = tv_search(
            args.query, mode="timelinevol", format="json", timespan=args.timespan,
            station=args.station or None, last24=True,
            timelinesmooth=args.smooth if args.smooth > 0 else None,
        )
        _ni_output(data, args, "tv_volume", _print_timeline)

    elif cmd == "tv-stations":
        data = tv_search(args.query, mode="stationchart", format="json", timespan=args.timespan)
        _ni_output(data, args, "tv_stations")

    elif cmd == "tv-trending":
        data = tv_search("", mode="trendingtopics", format="json")
        _ni_output(data, args, "tv_trending", _print_trending)

    elif cmd == "tv-wordcloud":
        data = tv_search(
            args.query, mode="wordcloud", format="json", timespan=args.timespan,
            station=args.station or None,
        )
        _ni_output(data, args, "tv_wordcloud")

    elif cmd == "context":
        data = context_search(
            args.query, format="json", maxrecords=args.maxrecords, sort=args.sort,
            sourcelang=args.sourcelang or None, sourcecountry=args.sourcecountry or None,
        )
        _ni_output(data, args, "context", _print_articles)

    elif cmd == "geo":
        data = geo_search(args.query, format=args.format, timespan=args.timespan)
        _ni_output(data, args, "geo")

    elif cmd == "narrative":
        query = MACRO_THEMES.get(args.theme, args.theme)
        theme_key = args.theme if args.theme in MACRO_THEMES else "custom"

        print(f"Narrative monitor: {theme_key}")
        print(f"Query: {query}")

        vol_data = doc_search(query, mode="timelinevol", format="json", timespan=args.timespan)
        tone_data = doc_search(query, mode="timelinetone", format="json", timespan=args.timespan)
        art_data = doc_search(query, mode="artlist", format="json", timespan="7d",
                              sort="HybridRel", maxrecords=15)

        combined = {
            "theme": theme_key, "query": query,
            "volume_timeline": vol_data, "tone_timeline": tone_data, "top_articles": art_data,
        }

        if getattr(args, "json", False):
            print(json.dumps(combined, indent=2, default=str))
        else:
            print("\n--- Volume Timeline ---")
            _print_timeline(vol_data)
            print("\n--- Tone Timeline ---")
            _print_timeline(tone_data)
            print("\n--- Top Articles ---")
            _print_articles(art_data, max_show=10)

        export_fmt = getattr(args, "export", "")
        if export_fmt:
            ts = time.strftime("%Y%m%d_%H%M%S")
            fname = f"narrative_{theme_key}_{ts}.{export_fmt}"
            with open(fname, "w") as f:
                json.dump(combined, f, indent=2, default=str)
            print(f"Exported to {fname}")

    elif cmd == "sentiment":
        query = MACRO_THEMES.get(args.query, args.query)
        data_3m = doc_search(query, mode="tonechart", format="json", timespan="3months")
        data_1w = doc_search(query, mode="tonechart", format="json", timespan="1w")
        combined = {"query": query, "tone_3m": data_3m, "tone_1w": data_1w}

        if getattr(args, "json", False):
            print(json.dumps(combined, indent=2, default=str))
        else:
            print("\n--- Tone Chart (3 month) ---")
            _print_tone_chart(data_3m)
            print("\n--- Tone Chart (1 week) ---")
            _print_tone_chart(data_1w)

    elif cmd == "cross-country":
        query = MACRO_THEMES.get(args.query, args.query)
        countries = [c.strip() for c in args.countries.split(",")]
        results = {}
        for country in countries:
            print(f"Fetching {country}...")
            data = doc_search(query, mode="timelinetone", format="json",
                              timespan=args.timespan, sourcecountry=country)
            results[country] = data
            if not getattr(args, "json", False) and data:
                _print_timeline(data)
            time.sleep(0.5)

        if getattr(args, "json", False):
            print(json.dumps(results, indent=2, default=str))

    elif cmd == "tv-divergence":
        stations = ["CNN", "FOXNEWS", "MSNBC"]
        results = {}
        for st in stations:
            print(f"Fetching {st}...")
            data = tv_search(args.query, mode="timelinevol", format="json",
                             timespan=args.timespan, station=st, last24=True)
            results[st] = data
            if not getattr(args, "json", False) and data:
                _print_timeline(data)
            time.sleep(0.5)

        if getattr(args, "json", False):
            print(json.dumps(results, indent=2, default=str))

    elif cmd == "event-detect":
        check_list = [t.strip() for t in args.themes.split(",")]
        results = {}
        for theme_key in check_list:
            query = MACRO_THEMES.get(theme_key, theme_key)
            data_7d = doc_search(query, mode="timelinevolraw", format="json", timespan="7d")
            time.sleep(0.5)

            if not data_7d:
                results[theme_key] = {"status": "no_data"}
                continue

            timeline = []
            if isinstance(data_7d, dict):
                for series in data_7d.get("timeline", []):
                    timeline.extend(series.get("data", []))

            if len(timeline) < 2:
                results[theme_key] = {"status": "insufficient_data"}
                continue

            recent = [dp.get("value", 0) for dp in timeline[-2:]]
            baseline = [dp.get("value", 0) for dp in timeline[:-2]]
            recent_avg = sum(recent) / len(recent) if recent else 0
            baseline_avg = sum(baseline) / len(baseline) if baseline else 0

            ratio = recent_avg / baseline_avg if baseline_avg > 0 else 0
            status = "spike" if ratio > 2.0 else "elevated" if ratio > 1.5 else "normal"
            results[theme_key] = {
                "recent_avg": recent_avg, "baseline_avg": baseline_avg,
                "ratio": ratio, "status": status,
            }

            if not getattr(args, "json", False):
                print(f"  {theme_key:20s}  recent={recent_avg:.0f}  baseline={baseline_avg:.0f}  ratio={ratio:.2f}x  {status}")

        if getattr(args, "json", False):
            print(json.dumps(results, indent=2, default=str))

    elif cmd == "multi-theme":
        results = {}
        for theme_key, query in MACRO_THEMES.items():
            data = doc_search(query, mode="artlist", format="json",
                              timespan=args.timespan, maxrecords=1, sort="HybridRel")
            count = 0
            if isinstance(data, dict):
                count = len(data.get("articles", []))
            elif isinstance(data, list):
                count = len(data)
            results[theme_key] = count
            if not getattr(args, "json", False):
                print(f"  {theme_key:20s}  {count}")
            time.sleep(0.3)

        if getattr(args, "json", False):
            print(json.dumps(results, indent=2, default=str))

    else:
        print(f"Unknown command: {cmd}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command:
        run_noninteractive(args)
    else:
        print("\n  GDELT Project API Explorer")
        print("  ==========================")
        print(f"  DOC API:     {BASE_DOC}")
        print(f"  TV API:      {BASE_TV}")
        print(f"  Context API: {BASE_CONTEXT}")
        print(f"  GEO API:     {BASE_GEO}")
        print(f"  Auth:        None required (fully public)")
        print(f"  Coverage:    DOC/GEO = rolling 3 months | Context = 72h | TV = 2009-present")
        interactive_loop()


if __name__ == "__main__":
    main()
