#!/usr/bin/env python3
"""
RSS/Atom Feed Aggregator -- Macro / Policy / Research Feed Client

Single-script aggregator for curated RSS/Atom feeds across Fed blogs, think tanks,
academic research, central bank communications, and macro analysis. Uses feedparser
for robust RSS/Atom parsing. No auth required.

Usage:
    python rss.py                                     # interactive CLI
    python rss.py latest                              # latest 20 entries across all feeds
    python rss.py latest --category fed --count 10    # latest 10 from Fed feeds
    python rss.py feed liberty_street                  # entries from Liberty Street Economics
    python rss.py pull                                 # pull all feeds, show summary
    python rss.py search "inflation"                   # search titles/summaries for keyword
    python rss.py category policy                      # all entries from policy category
    python rss.py feeds                                # list registered feeds
    python rss.py categories                           # list categories with counts
    python rss.py digest                               # daily digest, top entries per category
    python rss.py headlines --category fed             # compact headline view
    python rss.py export-digest --export json          # full digest export for PRISM
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser

try:
    import feedparser
except ImportError:
    print("feedparser is required. Install it with:")
    print("  pip install feedparser")
    sys.exit(1)

import requests


# --- Configuration ------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (PRISM RSS Aggregator)",
    "Accept": "application/xml, application/rss+xml, application/atom+xml, text/xml, */*",
})

FEED_TIMEOUT = 20

FEED_REGISTRY = {
    # Fed Blogs & Research
    "liberty_street":     {"url": "https://libertystreeteconomics.newyorkfed.org/feed/", "name": "Liberty Street Economics", "org": "NY Fed", "category": "fed"},
    "feds_notes":         {"url": "https://www.federalreserve.gov/feeds/feds_notes.xml", "name": "FEDS Notes", "org": "Fed Board", "category": "fed"},
    "chicago_fed":        {"url": "https://www.chicagofed.org/feeds/publications/chicago-fed-letter", "name": "Chicago Fed Letter", "org": "Chicago Fed", "category": "fed"},
    "stlouisfed":         {"url": "https://www.stlouisfed.org/on-the-economy/rss", "name": "On the Economy", "org": "St. Louis Fed", "category": "fed"},
    "sf_fed":             {"url": "https://www.frbsf.org/research-and-insights/publications/economic-letter/feed/", "name": "SF Fed Economic Letter", "org": "SF Fed", "category": "fed"},
    "richmond_fed":       {"url": "https://www.richmondfed.org/rss_feeds/research", "name": "Richmond Fed Research", "org": "Richmond Fed", "category": "fed"},

    # Think Tanks & Policy
    "brookings":          {"url": "https://www.brookings.edu/feed/", "name": "Brookings Institution", "org": "Brookings", "category": "policy"},
    "piie":               {"url": "https://www.piie.com/blogs/realtime-economics/feed", "name": "PIIE Realtime Economics", "org": "PIIE", "category": "policy"},
    "cato":               {"url": "https://www.cato.org/rss/recent-opeds", "name": "Cato Institute", "org": "Cato", "category": "policy"},
    "aei":                {"url": "https://www.aei.org/feed/", "name": "AEI", "org": "AEI", "category": "policy"},
    "heritage":           {"url": "https://www.heritage.org/rss", "name": "Heritage Foundation", "org": "Heritage", "category": "policy"},

    # Academic / Research
    "nber":               {"url": "https://www.nber.org/rss/new.xml", "name": "NBER New Working Papers", "org": "NBER", "category": "academic"},
    "voxeu":              {"url": "https://cepr.org/rss/columns/voxeu.xml", "name": "VoxEU / CEPR", "org": "CEPR", "category": "academic"},
    "imf_blog":           {"url": "https://www.imf.org/en/Blogs/rss", "name": "IMF Blog", "org": "IMF", "category": "academic"},

    # Central Bank Official
    "ecb_press":          {"url": "https://www.ecb.europa.eu/rss/press.html", "name": "ECB Press Releases", "org": "ECB", "category": "central_bank"},
    "boe_speeches":       {"url": "https://www.bankofengland.co.uk/rss/speeches", "name": "BoE Speeches", "org": "BoE", "category": "central_bank"},
    "bis_speeches":       {"url": "https://www.bis.org/doclist/cbspeeches.rss", "name": "BIS Central Bank Speeches", "org": "BIS", "category": "central_bank"},

    # Macro Data Releases / Analysis
    "calculated_risk":    {"url": "https://www.calculatedriskblog.com/feeds/posts/default", "name": "Calculated Risk", "org": "Calculated Risk", "category": "macro"},
    "econbrowser":        {"url": "https://econbrowser.com/feed", "name": "Econbrowser", "org": "Menzie Chinn / Jim Hamilton", "category": "macro"},
}

CATEGORY_ORDER = ["fed", "policy", "academic", "central_bank", "macro"]
CATEGORY_NAMES = {
    "fed":          "FED BLOGS & RESEARCH",
    "policy":       "THINK TANKS & POLICY",
    "academic":     "ACADEMIC / RESEARCH",
    "central_bank": "CENTRAL BANK OFFICIAL",
    "macro":        "MACRO DATA & ANALYSIS",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# --- HTML Stripping -----------------------------------------------------------

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self):
        return " ".join(self._parts)


def _strip_html(raw):
    if not raw:
        return ""
    stripper = _HTMLStripper()
    try:
        stripper.feed(raw)
        text = stripper.get_text()
    except Exception:
        text = re.sub(r"<[^>]+>", "", raw)
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text, length=120):
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) <= length:
        return text
    return text[:length - 3] + "..."


# --- Date Parsing -------------------------------------------------------------

def _parse_entry_date(entry):
    """Extract datetime from a feedparser entry. Returns datetime or None."""
    # feedparser gives published_parsed or updated_parsed as time.struct_time
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        st = entry.get(field)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue

    # try raw date strings
    for field in ("published", "updated", "created"):
        raw = entry.get(field, "")
        if not raw:
            continue
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
                    "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
    return None


def _fmt_date(dt):
    if not dt:
        return "no date"
    return dt.strftime("%Y-%m-%d")


def _fmt_date_short(dt):
    if not dt:
        return "n/a"
    return dt.strftime("%b %d")


def _age_str(dt):
    if not dt:
        return ""
    now = datetime.now(tz=timezone.utc)
    delta = now - dt
    days = delta.days
    if days < 0:
        return "future"
    if days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            return "just now"
        return f"{hours}h ago"
    if days == 1:
        return "1d ago"
    if days < 30:
        return f"{days}d ago"
    return f"{days // 30}mo ago"


# --- Feed Fetching & Parsing --------------------------------------------------

def _fetch_feed(feed_key):
    """Fetch and parse a single feed. Returns list of normalized entry dicts."""
    info = FEED_REGISTRY.get(feed_key)
    if not info:
        return [], f"unknown feed key: {feed_key}"

    try:
        resp = SESSION.get(info["url"], timeout=FEED_TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return [], "timeout"
    except requests.exceptions.ConnectionError:
        return [], "connection error"
    except requests.exceptions.HTTPError as e:
        return [], f"HTTP {e.response.status_code}"
    except Exception as e:
        return [], str(e)[:60]

    parsed = feedparser.parse(resp.text)
    if parsed.bozo and not parsed.entries:
        return [], "malformed feed"

    entries = []
    seen_links = set()
    for e in parsed.entries:
        link = e.get("link", "")
        if link in seen_links:
            continue
        if link:
            seen_links.add(link)

        dt = _parse_entry_date(e)
        summary_raw = e.get("summary", "") or e.get("description", "")

        entries.append({
            "title":     e.get("title", "(no title)"),
            "link":      link,
            "published": dt,
            "summary":   _strip_html(summary_raw),
            "author":    e.get("author", ""),
            "feed_key":  feed_key,
            "category":  info["category"],
            "feed_name": info["name"],
            "org":       info["org"],
        })

    return entries, None


def _fetch_multiple(feed_keys=None, quiet=False):
    """Fetch multiple feeds with progress. Returns (all_entries, errors_dict)."""
    if feed_keys is None:
        feed_keys = list(FEED_REGISTRY.keys())

    all_entries = []
    errors = {}
    total = len(feed_keys)

    for idx, key in enumerate(feed_keys, 1):
        info = FEED_REGISTRY.get(key, {})
        label = info.get("name", key)
        if not quiet:
            print(f"  [{idx}/{total}] {label}...", end=" ", flush=True)

        entries, err = _fetch_feed(key)
        if err:
            errors[key] = err
            if not quiet:
                print(f"ERROR: {err}")
        else:
            if not quiet:
                print(f"{len(entries)} entries")
            all_entries.extend(entries)

    return all_entries, errors


def _sort_entries(entries):
    """Sort entries by date descending, entries without dates go last."""
    def sort_key(e):
        dt = e.get("published")
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt
    return sorted(entries, key=sort_key, reverse=True)


def _dedup_entries(entries):
    """Deduplicate entries by link URL."""
    seen = set()
    out = []
    for e in entries:
        link = e.get("link", "")
        if not link:
            out.append(e)
            continue
        if link not in seen:
            seen.add(link)
            out.append(e)
    return out


def _feeds_for_category(cat):
    return [k for k, v in FEED_REGISTRY.items() if v["category"] == cat]


# --- Export Helpers -----------------------------------------------------------

def _ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _serialize_entry(entry):
    """Make an entry JSON/CSV-safe by converting datetime to string."""
    out = dict(entry)
    if out.get("published"):
        out["published"] = out["published"].isoformat()
    else:
        out["published"] = ""
    return out


def _export_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Exported: {path}")


def _export_csv(rows, path):
    if not rows:
        print("  No data to export.")
        return
    if isinstance(rows[0], dict):
        fieldnames = list(rows[0].keys())
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    else:
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerows(rows)
    print(f"  Exported: {path}")


def _do_export(data, prefix, fmt):
    path = os.path.join(SCRIPT_DIR, f"{prefix}_{_ts()}.{fmt}")
    if isinstance(data, list):
        data = [_serialize_entry(e) if isinstance(e, dict) and "published" in e else e for e in data]
    if fmt == "json":
        _export_json(data, path)
    elif fmt == "csv":
        if isinstance(data, dict):
            data = list(data.values()) if data else []
        _export_csv(data, path)


def _prompt_export(data, prefix):
    choice = _prompt("Export? (json/csv/no)", "no")
    if choice in ("json", "csv"):
        _do_export(data, prefix, choice)


# --- Display Helpers ----------------------------------------------------------

def _display_entries(entries, title="Entries", show_summary=True, limit=None):
    if not entries:
        print("  No entries found.")
        return

    if limit:
        entries = entries[:limit]

    print(f"\n  {title}")
    print("  " + "=" * 90)

    for i, e in enumerate(entries):
        dt_str = _fmt_date(e.get("published"))
        age = _age_str(e.get("published"))
        source = e.get("org", e.get("feed_name", ""))

        print(f"\n  [{i+1}] {e['title']}")
        print(f"      {dt_str} ({age})  |  {source}")
        if e.get("author"):
            print(f"      By: {e['author']}")
        if show_summary and e.get("summary"):
            print(f"      {_truncate(e['summary'], 140)}")
        if e.get("link"):
            print(f"      {e['link']}")

    print(f"\n  --- {len(entries)} entries ---\n")


def _display_headlines(entries, title="Headlines", limit=None):
    if not entries:
        print("  No entries found.")
        return

    if limit:
        entries = entries[:limit]

    print(f"\n  {title}")
    print("  " + "=" * 90)
    print(f"  {'Date':<12} {'Source':<22} Title")
    print(f"  {'-'*12} {'-'*22} {'-'*50}")

    for e in entries:
        dt_str = _fmt_date_short(e.get("published"))
        source = e.get("org", "")[:20]
        title_str = _truncate(e.get("title", ""), 60)
        print(f"  {dt_str:<12} {source:<22} {title_str}")

    print(f"\n  --- {len(entries)} headlines ---\n")


def _display_pull_summary(all_entries, errors, elapsed):
    """Show summary after pulling all feeds."""
    by_feed = {}
    for e in all_entries:
        key = e["feed_key"]
        by_feed.setdefault(key, []).append(e)

    print(f"\n  PULL SUMMARY")
    print("  " + "=" * 70)
    print(f"  {'Feed':<30} {'Entries':>8}  {'Latest':<12}")
    print(f"  {'-'*30} {'-'*8}  {'-'*12}")

    for cat in CATEGORY_ORDER:
        feeds = _feeds_for_category(cat)
        for key in feeds:
            info = FEED_REGISTRY[key]
            entries = by_feed.get(key, [])
            count = len(entries)
            if entries:
                dates = [e["published"] for e in entries if e.get("published")]
                latest = _fmt_date(max(dates)) if dates else "no dates"
            else:
                latest = "---"
            err = errors.get(key, "")
            suffix = f"  [{err}]" if err else ""
            print(f"  {info['name']:<30} {count:>8}  {latest:<12}{suffix}")

    total = len(all_entries)
    err_count = len(errors)
    print(f"\n  Total: {total} entries from {len(FEED_REGISTRY) - err_count} feeds "
          f"({err_count} errors) in {elapsed:.1f}s\n")


# --- Command Functions --------------------------------------------------------

def cmd_latest(category=None, count=20, as_json=False, export_fmt=None):
    if category:
        keys = _feeds_for_category(category)
        if not keys:
            print(f"  Unknown category: {category}")
            return
        label = CATEGORY_NAMES.get(category, category.upper())
        print(f"\n  Fetching latest from {label}...")
    else:
        keys = None
        print(f"\n  Fetching latest across all feeds...")

    entries, errors = _fetch_multiple(keys, quiet=False)
    entries = _dedup_entries(_sort_entries(entries))

    if as_json:
        print(json.dumps([_serialize_entry(e) for e in entries[:count]], indent=2))
        return

    _display_entries(entries, title=f"Latest Entries (top {count})", limit=count)

    if errors:
        print(f"  Feed errors: {', '.join(f'{k} ({v})' for k, v in errors.items())}\n")

    if export_fmt:
        _do_export(entries[:count], "rss_latest", export_fmt)


def cmd_feed(feed_key, count=20, as_json=False, export_fmt=None):
    if feed_key not in FEED_REGISTRY:
        print(f"  Unknown feed key: {feed_key}")
        print(f"  Available: {', '.join(sorted(FEED_REGISTRY.keys()))}")
        return

    info = FEED_REGISTRY[feed_key]
    print(f"\n  Fetching {info['name']} ({info['org']})...")

    entries, err = _fetch_feed(feed_key)
    if err:
        print(f"  Error: {err}")
        return

    entries = _sort_entries(entries)

    if as_json:
        print(json.dumps([_serialize_entry(e) for e in entries[:count]], indent=2))
        return

    _display_entries(entries, title=f"{info['name']} -- {info['org']}", limit=count)

    if export_fmt:
        _do_export(entries[:count], f"rss_{feed_key}", export_fmt)


def cmd_pull(as_json=False, export_fmt=None):
    print(f"\n  Pulling all {len(FEED_REGISTRY)} feeds...\n")
    t0 = time.time()
    entries, errors = _fetch_multiple(quiet=False)
    elapsed = time.time() - t0
    entries = _dedup_entries(_sort_entries(entries))

    if as_json:
        summary = {
            "total_entries": len(entries),
            "errors": errors,
            "elapsed_seconds": round(elapsed, 1),
            "by_feed": {},
        }
        for e in entries:
            summary["by_feed"].setdefault(e["feed_key"], 0)
            summary["by_feed"][e["feed_key"]] += 1
        print(json.dumps(summary, indent=2))
        return

    _display_pull_summary(entries, errors, elapsed)

    if export_fmt:
        _do_export(entries, "rss_pull", export_fmt)


def cmd_search(keyword=None, category=None, count=30, as_json=False, export_fmt=None):
    if not keyword:
        keyword = _prompt("Search keyword")
        if not keyword:
            return

    kw_lower = keyword.lower()
    if category:
        keys = _feeds_for_category(category)
    else:
        keys = None

    print(f"\n  Searching for '{keyword}' across {'all feeds' if not category else category}...")
    entries, errors = _fetch_multiple(keys, quiet=True)
    entries = _dedup_entries(_sort_entries(entries))

    matches = []
    for e in entries:
        title = (e.get("title") or "").lower()
        summary = (e.get("summary") or "").lower()
        if kw_lower in title or kw_lower in summary:
            matches.append(e)

    if as_json:
        print(json.dumps([_serialize_entry(e) for e in matches[:count]], indent=2))
        return

    _display_entries(matches, title=f"Search Results: '{keyword}' ({len(matches)} matches)", limit=count)

    if export_fmt:
        _do_export(matches[:count], f"rss_search_{keyword.replace(' ', '_')}", export_fmt)


def cmd_category(cat, count=30, as_json=False, export_fmt=None):
    if cat not in CATEGORY_NAMES:
        print(f"  Unknown category: {cat}")
        print(f"  Available: {', '.join(CATEGORY_ORDER)}")
        return

    keys = _feeds_for_category(cat)
    label = CATEGORY_NAMES[cat]
    print(f"\n  Fetching {label} ({len(keys)} feeds)...")

    entries, errors = _fetch_multiple(keys, quiet=False)
    entries = _dedup_entries(_sort_entries(entries))

    if as_json:
        print(json.dumps([_serialize_entry(e) for e in entries[:count]], indent=2))
        return

    _display_entries(entries, title=label, limit=count)

    if export_fmt:
        _do_export(entries[:count], f"rss_cat_{cat}", export_fmt)


def cmd_feeds(as_json=False):
    if as_json:
        print(json.dumps(FEED_REGISTRY, indent=2))
        return

    print(f"\n  REGISTERED FEEDS ({len(FEED_REGISTRY)})")
    print("  " + "=" * 80)

    for cat in CATEGORY_ORDER:
        label = CATEGORY_NAMES.get(cat, cat)
        feeds = [(k, v) for k, v in FEED_REGISTRY.items() if v["category"] == cat]
        print(f"\n  {label}")
        print(f"  {'-' * len(label)}")
        for key, info in feeds:
            print(f"    {key:<22} {info['name']:<30} ({info['org']})")
            print(f"    {' '*22} {info['url']}")

    print()


def cmd_categories(as_json=False):
    counts = {}
    for info in FEED_REGISTRY.values():
        counts.setdefault(info["category"], 0)
        counts[info["category"]] += 1

    if as_json:
        data = [{"category": c, "name": CATEGORY_NAMES.get(c, c), "feed_count": counts.get(c, 0)}
                for c in CATEGORY_ORDER]
        print(json.dumps(data, indent=2))
        return

    print(f"\n  CATEGORIES")
    print("  " + "=" * 50)
    print(f"  {'Category':<16} {'Name':<30} {'Feeds':>6}")
    print(f"  {'-'*16} {'-'*30} {'-'*6}")
    for cat in CATEGORY_ORDER:
        label = CATEGORY_NAMES.get(cat, cat)
        print(f"  {cat:<16} {label:<30} {counts.get(cat, 0):>6}")
    print(f"\n  Total: {len(FEED_REGISTRY)} feeds across {len(CATEGORY_ORDER)} categories\n")


def cmd_digest(entries_per_cat=3, as_json=False, export_fmt=None):
    print(f"\n  Building daily digest ({entries_per_cat} entries per category)...\n")

    all_entries = []
    errors = {}
    digest_data = {}

    for cat in CATEGORY_ORDER:
        keys = _feeds_for_category(cat)
        cat_entries, cat_errors = _fetch_multiple(keys, quiet=True)
        errors.update(cat_errors)
        cat_entries = _dedup_entries(_sort_entries(cat_entries))
        top = cat_entries[:entries_per_cat]
        all_entries.extend(top)
        digest_data[cat] = top

    if as_json:
        out = {}
        for cat, entries in digest_data.items():
            out[cat] = {
                "category_name": CATEGORY_NAMES.get(cat, cat),
                "entries": [_serialize_entry(e) for e in entries],
            }
        print(json.dumps(out, indent=2))
        return

    today = datetime.now().strftime("%A, %B %d, %Y")
    print(f"  ===================================================================")
    print(f"  DAILY DIGEST -- {today}")
    print(f"  ===================================================================")

    for cat in CATEGORY_ORDER:
        label = CATEGORY_NAMES.get(cat, cat)
        entries = digest_data.get(cat, [])
        print(f"\n  --- {label} ---")
        if not entries:
            print(f"      (no entries available)")
            continue
        for i, e in enumerate(entries):
            dt_str = _fmt_date(e.get("published"))
            age = _age_str(e.get("published"))
            print(f"\n    {i+1}. {e['title']}")
            print(f"       {e.get('org', '')} | {dt_str} ({age})")
            if e.get("author"):
                print(f"       By: {e['author']}")
            if e.get("summary"):
                print(f"       {_truncate(e['summary'], 160)}")
            if e.get("link"):
                print(f"       {e['link']}")

    print(f"\n  -------------------------------------------------------------------")
    total = sum(len(v) for v in digest_data.values())
    err_count = len(errors)
    print(f"  {total} entries across {len(CATEGORY_ORDER)} categories", end="")
    if err_count:
        print(f" ({err_count} feed errors)")
    else:
        print()
    print()

    if export_fmt:
        _do_export(all_entries, "rss_digest", export_fmt)


def cmd_headlines(category=None, count=40, as_json=False, export_fmt=None):
    if category:
        keys = _feeds_for_category(category)
        if not keys:
            print(f"  Unknown category: {category}")
            return
        label = CATEGORY_NAMES.get(category, category.upper())
    else:
        keys = None
        label = "ALL FEEDS"

    print(f"\n  Fetching headlines from {label}...")
    entries, errors = _fetch_multiple(keys, quiet=True)
    entries = _dedup_entries(_sort_entries(entries))

    if as_json:
        compact = [{"title": e["title"], "date": _fmt_date(e.get("published")),
                     "source": e.get("org", ""), "link": e.get("link", "")}
                    for e in entries[:count]]
        print(json.dumps(compact, indent=2))
        return

    _display_headlines(entries, title=f"Headlines -- {label}", limit=count)

    if export_fmt:
        _do_export(entries[:count], "rss_headlines", export_fmt)


def cmd_export_digest(export_fmt="json"):
    """Pull all feeds and export the full digest for PRISM consumption."""
    print(f"\n  Building full export digest...\n")
    t0 = time.time()
    entries, errors = _fetch_multiple(quiet=False)
    elapsed = time.time() - t0
    entries = _dedup_entries(_sort_entries(entries))

    by_category = {}
    for e in entries:
        cat = e["category"]
        by_category.setdefault(cat, []).append(_serialize_entry(e))

    digest = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_entries": len(entries),
        "feed_count": len(FEED_REGISTRY),
        "errors": errors,
        "elapsed_seconds": round(elapsed, 1),
        "categories": {},
    }

    for cat in CATEGORY_ORDER:
        cat_entries = by_category.get(cat, [])
        digest["categories"][cat] = {
            "name": CATEGORY_NAMES.get(cat, cat),
            "entry_count": len(cat_entries),
            "entries": cat_entries,
        }

    _do_export(digest, "rss_full_digest", export_fmt)
    print(f"\n  Full digest: {len(entries)} entries from "
          f"{len(FEED_REGISTRY) - len(errors)} feeds in {elapsed:.1f}s\n")


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   RSS/Atom Feed Aggregator -- Macro / Policy / Research
  =====================================================

   BROWSE
     1) latest         Latest entries across all feeds
     2) feed           Entries from a specific feed
     3) category       Entries from a category
     4) headlines      Compact headline view

   ANALYSIS
     5) search         Search across all feeds
     6) digest         Daily digest (top per category)

   DATA
     7) pull           Pull all feeds, show summary
     8) feeds          List registered feeds
     9) categories     List categories with counts
    10) export-digest  Export full digest (JSON)

   q) quit
"""


def _prompt(msg, default=None):
    suffix = f" [{default}]" if default is not None else ""
    try:
        val = input(f"  {msg}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return str(default) if default is not None else ""
    return val if val else (str(default) if default is not None else "")


def _prompt_choice(msg, choices, default=None):
    choices_str = "/".join(choices)
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {msg} ({choices_str}){suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default or choices[0]
    if val and val in choices:
        return val
    return default or choices[0]


def _i_latest():
    cats = ["all"] + CATEGORY_ORDER
    cat = _prompt_choice("Category", cats, "all")
    count = _prompt("Number of entries", "20")
    cmd_latest(category=cat if cat != "all" else None, count=int(count))


def _i_feed():
    print(f"  Available feeds:")
    for cat in CATEGORY_ORDER:
        feeds = [(k, v) for k, v in FEED_REGISTRY.items() if v["category"] == cat]
        names = ", ".join(k for k, _ in feeds)
        print(f"    {cat}: {names}")
    key = _prompt("Feed key")
    count = _prompt("Number of entries", "20")
    cmd_feed(feed_key=key, count=int(count))


def _i_category():
    print(f"  Categories: {', '.join(CATEGORY_ORDER)}")
    cat = _prompt("Category")
    count = _prompt("Number of entries", "30")
    cmd_category(cat=cat, count=int(count))


def _i_headlines():
    cats = ["all"] + CATEGORY_ORDER
    cat = _prompt_choice("Category", cats, "all")
    count = _prompt("Number of headlines", "40")
    cmd_headlines(category=cat if cat != "all" else None, count=int(count))


def _i_search():
    keyword = _prompt("Search keyword")
    cats = ["all"] + CATEGORY_ORDER
    cat = _prompt_choice("Category filter", cats, "all")
    cmd_search(keyword=keyword, category=cat if cat != "all" else None)


def _i_digest():
    n = _prompt("Entries per category", "3")
    cmd_digest(entries_per_cat=int(n))


def _i_pull():
    cmd_pull()


def _i_feeds():
    cmd_feeds()


def _i_categories():
    cmd_categories()


def _i_export_digest():
    fmt = _prompt_choice("Format", ["json", "csv"], "json")
    cmd_export_digest(export_fmt=fmt)


COMMAND_MAP = {
    "1":  _i_latest,
    "2":  _i_feed,
    "3":  _i_category,
    "4":  _i_headlines,
    "5":  _i_search,
    "6":  _i_digest,
    "7":  _i_pull,
    "8":  _i_feeds,
    "9":  _i_categories,
    "10": _i_export_digest,
}


def interactive_loop():
    print(MENU)
    while True:
        choice = _prompt("\n  Command").strip().lower()
        if choice in ("q", "quit", "exit"):
            break
        if choice in COMMAND_MAP:
            try:
                COMMAND_MAP[choice]()
            except KeyboardInterrupt:
                print("\n  [interrupted]")
            except Exception as e:
                print(f"  [error: {e}]")
        else:
            print(f"  Unknown command: {choice}")
            print("  Enter 1-10 or q to quit")


# --- Argparse -----------------------------------------------------------------

VALID_CATEGORIES = CATEGORY_ORDER + ["all"]


def build_argparse():
    p = argparse.ArgumentParser(
        prog="rss.py",
        description="RSS/Atom Feed Aggregator -- Macro / Policy / Research Feed Client",
    )
    sub = p.add_subparsers(dest="command")

    # latest
    s = sub.add_parser("latest", help="Latest entries across all feeds")
    s.add_argument("--category", choices=VALID_CATEGORIES, default="all")
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # feed
    s = sub.add_parser("feed", help="Entries from a specific feed")
    s.add_argument("feed_key", help="Feed registry key (e.g. liberty_street)")
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # pull
    s = sub.add_parser("pull", help="Pull all feeds, show summary")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # search
    s = sub.add_parser("search", help="Search across all feeds")
    s.add_argument("keyword", help="Search keyword")
    s.add_argument("--category", choices=VALID_CATEGORIES, default="all")
    s.add_argument("--count", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # category
    s = sub.add_parser("category", help="Entries from a specific category")
    s.add_argument("cat", choices=CATEGORY_ORDER, help="Category key")
    s.add_argument("--count", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # feeds
    s = sub.add_parser("feeds", help="List registered feeds")
    s.add_argument("--json", action="store_true")

    # categories
    s = sub.add_parser("categories", help="List categories with feed counts")
    s.add_argument("--json", action="store_true")

    # digest
    s = sub.add_parser("digest", help="Daily digest (top entries per category)")
    s.add_argument("--count", type=int, default=3, help="Entries per category")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # headlines
    s = sub.add_parser("headlines", help="Compact headline view")
    s.add_argument("--category", choices=VALID_CATEGORIES, default="all")
    s.add_argument("--count", type=int, default=40)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # export-digest
    s = sub.add_parser("export-digest", help="Export full digest for PRISM")
    s.add_argument("--export", choices=["csv", "json"], default="json")

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)
    cnt = getattr(args, "count", 20)

    cat = getattr(args, "category", "all")
    cat = cat if cat != "all" else None

    if args.command == "latest":
        cmd_latest(category=cat, count=cnt, as_json=j, export_fmt=exp)
    elif args.command == "feed":
        cmd_feed(feed_key=args.feed_key, count=cnt, as_json=j, export_fmt=exp)
    elif args.command == "pull":
        cmd_pull(as_json=j, export_fmt=exp)
    elif args.command == "search":
        cmd_search(keyword=args.keyword, category=cat, count=cnt, as_json=j, export_fmt=exp)
    elif args.command == "category":
        cmd_category(cat=args.cat, count=cnt, as_json=j, export_fmt=exp)
    elif args.command == "feeds":
        cmd_feeds(as_json=j)
    elif args.command == "categories":
        cmd_categories(as_json=j)
    elif args.command == "digest":
        cmd_digest(entries_per_cat=cnt, as_json=j, export_fmt=exp)
    elif args.command == "headlines":
        cmd_headlines(category=cat, count=cnt, as_json=j, export_fmt=exp)
    elif args.command == "export-digest":
        cmd_export_digest(export_fmt=exp or "json")


# --- Main ---------------------------------------------------------------------

def main():
    parser = build_argparse()
    args = parser.parse_args()

    if args.command:
        run_noninteractive(args)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
