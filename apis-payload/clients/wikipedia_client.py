#!/usr/bin/env python3
"""
Wikipedia Pageviews -- Macro Attention / Fear Gauge

Single-script client for the Wikimedia Analytics Pageviews API. Tracks Wikipedia
article views as a proxy for public attention on macro-relevant topics: recessions,
inflation, banking crises, Fed policy, and geopolitical risk. Curated registry of
~30 articles organized by theme. No auth required.

Usage:
    python wikipedia.py                                    # interactive CLI
    python wikipedia.py article Recession --days 60        # views for Recession, 60 days
    python wikipedia.py compare Recession Inflation        # compare multiple articles
    python wikipedia.py theme recession_growth             # all articles in theme
    python wikipedia.py top --date 2024-01-15              # most-viewed on a day
    python wikipedia.py fear-gauge                         # composite fear index
    python wikipedia.py macro-dashboard                    # cross-theme snapshot
    python wikipedia.py spike-detect                       # find viewership spikes
    python wikipedia.py history Recession                  # long monthly history
    python wikipedia.py aggregate --days 30                # total Wikipedia traffic
    python wikipedia.py themes                             # list curated themes
    python wikipedia.py search "Yield curve"               # arbitrary article lookup
    python wikipedia.py export fear-gauge --export json    # export data
"""

import argparse
import csv
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta

import requests


# --- Configuration ------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "PRISM-WikipediaPageviews/1.0 (macro-analysis-bot)",
})

BASE_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews"

ARTICLE_REGISTRY = {
    "recession_growth": [
        "Recession", "Economic_growth", "Great_Recession",
        "Stagflation", "Depression_(economics)", "Soft_landing_(economics)",
    ],
    "inflation": [
        "Inflation", "Deflation", "Hyperinflation",
        "Consumer_price_index", "Core_inflation",
    ],
    "rates_fed": [
        "Federal_Reserve", "Interest_rate", "Yield_curve",
        "Quantitative_easing", "Quantitative_tightening", "Federal_funds_rate",
    ],
    "markets": [
        "Stock_market_crash", "Bear_market", "Bull_market",
        "Volatility_(finance)", "Black_Monday_(1987)", "Dot-com_bubble",
    ],
    "banking": [
        "Bank_run", "Bank_failure", "Silicon_Valley_Bank",
        "Credit_Suisse", "Too_big_to_fail",
    ],
    "geopolitical": [
        "Tariff", "Trade_war", "Sanctions_(law)",
        "BRICS", "Petrodollar_recycling",
    ],
    "fiscal": [
        "National_debt_of_the_United_States", "Government_shutdown",
        "Debt_ceiling",
    ],
}

THEME_NAMES = {
    "recession_growth": "RECESSION / GROWTH",
    "inflation":        "INFLATION",
    "rates_fed":        "RATES / FED",
    "markets":          "MARKETS",
    "banking":          "BANKING",
    "geopolitical":     "GEOPOLITICAL",
    "fiscal":           "FISCAL",
}

THEME_ORDER = list(ARTICLE_REGISTRY.keys())

FEAR_THEMES = ["recession_growth", "banking", "markets"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# --- Date Helpers -------------------------------------------------------------

def _api_date(dt):
    """Format datetime as YYYYMMDD00 for the Wikimedia API."""
    return dt.strftime("%Y%m%d") + "00"


def _display_date(timestamp_str):
    """Convert API timestamp YYYYMMDD00 to YYYY-MM-DD."""
    return f"{timestamp_str[:4]}-{timestamp_str[4:6]}-{timestamp_str[6:8]}"


def _days_ago(n):
    return datetime.now() - timedelta(days=n)


def _parse_user_date(s):
    """Parse YYYY-MM-DD or YYYYMMDD from user input."""
    s = s.strip().replace("-", "")
    return datetime.strptime(s, "%Y%m%d")


# --- HTTP Layer ---------------------------------------------------------------

def _request(url):
    """GET with User-Agent and rate-limit sleep. Returns parsed JSON or None."""
    try:
        resp = SESSION.get(url, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        time.sleep(0.5)
        return resp.json()
    except requests.exceptions.Timeout:
        print("  [timeout]")
        return None
    except requests.exceptions.ConnectionError:
        print("  [connection error]")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"  [HTTP {e.response.status_code}]")
        return None
    except Exception as e:
        print(f"  [error: {str(e)[:60]}]")
        return None


# --- Domain Logic: Fetchers ---------------------------------------------------

def _fetch_article_views(article, start_dt, end_dt, granularity="daily",
                         project="en.wikipedia.org", access="all-access",
                         agent="all-agents"):
    url = (f"{BASE_URL}/per-article/{project}/{access}/{agent}/"
           f"{article}/{granularity}/{_api_date(start_dt)}/{_api_date(end_dt)}")
    data = _request(url)
    if not data or "items" not in data:
        return []
    return data["items"]


def _fetch_aggregate(start_dt, end_dt, granularity="daily",
                     project="en.wikipedia.org", access="all-access",
                     agent="all-agents"):
    url = (f"{BASE_URL}/aggregate/{project}/{access}/{agent}/"
           f"{granularity}/{_api_date(start_dt)}/{_api_date(end_dt)}")
    data = _request(url)
    if not data or "items" not in data:
        return []
    return data["items"]


def _fetch_top(year, month, day, project="en.wikipedia.org", access="all-access"):
    url = f"{BASE_URL}/top/{project}/{access}/{year}/{month:02d}/{day:02d}"
    data = _request(url)
    if not data or "items" not in data:
        return []
    items = data["items"]
    if items and "articles" in items[0]:
        return items[0]["articles"]
    return []


def _fetch_multi_articles(articles, start_dt, end_dt, granularity="daily",
                          quiet=False):
    """Fetch views for multiple articles with progress. Returns {article: [items]}."""
    results = {}
    total = len(articles)
    for idx, article in enumerate(articles, 1):
        if not quiet:
            label = article.replace("_", " ")
            print(f"  [{idx}/{total}] Fetching {label}...", flush=True)
        items = _fetch_article_views(article, start_dt, end_dt, granularity)
        results[article] = items
    return results


def _build_fear_gauge(lookback_days=90, recent_days=7):
    """
    Composite fear index: average z-score of recession/crash/banking articles'
    recent pageviews vs their trailing mean over the lookback window.
    """
    fear_articles = []
    for theme in FEAR_THEMES:
        fear_articles.extend(ARTICLE_REGISTRY[theme])

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=lookback_days)

    print(f"\n  Building fear gauge ({len(fear_articles)} articles, "
          f"{lookback_days}d lookback)...\n")
    article_data = _fetch_multi_articles(fear_articles, start_dt, end_dt)

    scores = []
    details = []

    for article in fear_articles:
        items = article_data.get(article, [])
        if len(items) < 14:
            details.append({"article": article, "status": "insufficient data"})
            continue

        views = [item["views"] for item in items]
        trailing_mean = sum(views) / len(views)
        variance = sum((v - trailing_mean) ** 2 for v in views) / len(views)
        trailing_std = math.sqrt(variance)

        recent_views = views[-recent_days:] if len(views) >= recent_days else views
        recent_mean = sum(recent_views) / len(recent_views)

        z = (recent_mean - trailing_mean) / trailing_std if trailing_std > 0 else 0.0

        scores.append(z)
        details.append({
            "article": article,
            "trailing_mean": round(trailing_mean, 1),
            "trailing_std": round(trailing_std, 1),
            "recent_mean": round(recent_mean, 1),
            "z_score": round(z, 2),
            "status": "ok",
        })

    composite = sum(scores) / len(scores) if scores else 0.0
    return {
        "composite_z": round(composite, 3),
        "article_count": len(fear_articles),
        "scored_count": len(scores),
        "lookback_days": lookback_days,
        "recent_days": recent_days,
        "details": details,
    }


def _detect_spikes(threshold=2.0, lookback_days=30, recent_days=7):
    """Find articles where recent 7d average exceeds threshold x trailing average."""
    all_articles = []
    article_theme = {}
    for theme, articles in ARTICLE_REGISTRY.items():
        for a in articles:
            all_articles.append(a)
            article_theme[a] = theme

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=lookback_days)

    print(f"\n  Scanning {len(all_articles)} articles for spikes "
          f"(>{threshold:.1f}x)...\n")
    article_data = _fetch_multi_articles(all_articles, start_dt, end_dt)

    spikes = []
    for article in all_articles:
        items = article_data.get(article, [])
        if len(items) < recent_days + 7:
            continue

        views = [item["views"] for item in items]
        trailing_avg = sum(views) / len(views)
        recent_views = views[-recent_days:]
        recent_avg = sum(recent_views) / len(recent_views)

        if trailing_avg <= 0:
            continue

        ratio = recent_avg / trailing_avg
        if ratio >= threshold:
            spikes.append({
                "article": article,
                "theme": article_theme[article],
                "trailing_avg": round(trailing_avg, 1),
                "recent_avg": round(recent_avg, 1),
                "ratio": round(ratio, 2),
            })

    spikes.sort(key=lambda x: x["ratio"], reverse=True)
    return spikes


def _build_dashboard():
    """Cross-theme attention snapshot: avg views per article with trend direction."""
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=30)

    all_articles = []
    article_theme = {}
    for theme, articles in ARTICLE_REGISTRY.items():
        for a in articles:
            all_articles.append(a)
            article_theme[a] = theme

    print(f"\n  Building macro dashboard ({len(all_articles)} articles)...\n")
    article_data = _fetch_multi_articles(all_articles, start_dt, end_dt)

    theme_stats = {}
    for theme in THEME_ORDER:
        articles = ARTICLE_REGISTRY[theme]
        theme_views = []
        article_details = []

        for article in articles:
            items = article_data.get(article, [])
            if not items:
                article_details.append({
                    "article": article, "avg": 0, "trend": "n/a",
                })
                continue

            views = [item["views"] for item in items]
            avg = sum(views) / len(views)

            if len(views) >= 14:
                mid = len(views) // 2
                first_avg = sum(views[:mid]) / mid
                second_avg = sum(views[mid:]) / (len(views) - mid)
                if first_avg > 0:
                    pct = ((second_avg - first_avg) / first_avg) * 100
                else:
                    pct = 0
                trend = f"+{pct:.0f}%" if pct > 0 else f"{pct:.0f}%"
            else:
                trend = "n/a"

            theme_views.append(avg)
            article_details.append({
                "article": article,
                "avg": round(avg, 1),
                "trend": trend,
            })

        theme_avg = sum(theme_views) / len(theme_views) if theme_views else 0
        theme_stats[theme] = {
            "name": THEME_NAMES[theme],
            "avg_views": round(theme_avg, 1),
            "articles": article_details,
        }

    return theme_stats


# --- Display Functions --------------------------------------------------------

def _display_views_table(items, article_name):
    if not items:
        print(f"  No data for {article_name}.")
        return

    label = article_name.replace("_", " ")
    print(f"\n  PAGEVIEWS: {label}")
    print("  " + "=" * 50)
    print(f"  {'Date':<14} {'Views':>10}")
    print(f"  {'-'*14} {'-'*10}")

    total = 0
    for item in items:
        date_str = _display_date(item["timestamp"])
        views = item["views"]
        total += views
        print(f"  {date_str:<14} {views:>10,}")

    avg = total / len(items) if items else 0
    print(f"  {'-'*14} {'-'*10}")
    print(f"  {'Total':<14} {total:>10,}")
    print(f"  {'Daily avg':<14} {avg:>10,.0f}")
    print(f"\n  --- {len(items)} data points ---\n")


def _display_comparison(results, articles):
    print(f"\n  ARTICLE COMPARISON")
    print("  " + "=" * 70)

    header = f"  {'Date':<14}"
    for a in articles:
        label = a.replace("_", " ")[:15]
        header += f" {label:>15}"
    print(header)
    print(f"  {'-'*14}" + (" " + "-" * 15) * len(articles))

    all_dates = set()
    for a in articles:
        for item in results.get(a, []):
            all_dates.add(item["timestamp"])

    date_map = {}
    for a in articles:
        for item in results.get(a, []):
            date_map[(a, item["timestamp"])] = item["views"]

    for ts in sorted(all_dates):
        row = f"  {_display_date(ts):<14}"
        for a in articles:
            v = date_map.get((a, ts), 0)
            row += f" {v:>15,}"
        print(row)

    print()
    totals_row = f"  {'TOTAL':<14}"
    avg_row = f"  {'AVG':<14}"
    for a in articles:
        items = results.get(a, [])
        total = sum(i["views"] for i in items)
        avg = total / len(items) if items else 0
        totals_row += f" {total:>15,}"
        avg_row += f" {avg:>15,.0f}"
    print(totals_row)
    print(avg_row)
    print()


def _display_fear_gauge(gauge):
    z = gauge["composite_z"]
    if z > 1.0:
        level = "ELEVATED"
    elif z > 0.5:
        level = "HIGH"
    elif z > -0.5:
        level = "NORMAL"
    else:
        level = "LOW"

    print(f"\n  FEAR / ATTENTION GAUGE")
    print("  " + "=" * 60)
    print(f"  Composite Z-Score:  {z:+.3f}  ({level})")
    print(f"  Articles scored:    {gauge['scored_count']}/{gauge['article_count']}")
    print(f"  Lookback:           {gauge['lookback_days']}d trailing, "
          f"{gauge['recent_days']}d recent")
    print()

    bar_len = 40
    mid = bar_len // 2
    bar_pos = max(-3, min(3, z))
    marker = int((bar_pos + 3) / 6 * bar_len)
    marker = max(0, min(bar_len - 1, marker))
    bar = list("." * bar_len)
    bar[mid] = "|"
    bar[marker] = "#"
    print(f"  LOW [{''.join(bar)}] HIGH")
    print()

    print(f"  {'Article':<35} {'Z-Score':>8} {'Recent':>8} {'Trailing':>10}")
    print(f"  {'-'*35} {'-'*8} {'-'*8} {'-'*10}")

    sorted_details = sorted(
        gauge["details"],
        key=lambda x: x.get("z_score", -999),
        reverse=True,
    )
    for d in sorted_details:
        label = d["article"].replace("_", " ")[:33]
        if d["status"] != "ok":
            print(f"  {label:<35} {'---':>8} {'---':>8} "
                  f"{'---':>10}  [{d['status']}]")
        else:
            print(f"  {label:<35} {d['z_score']:>+8.2f} "
                  f"{d['recent_mean']:>8,.0f} {d['trailing_mean']:>10,.0f}")
    print()


def _display_dashboard(theme_stats):
    print(f"\n  MACRO ATTENTION DASHBOARD")
    print("  " + "=" * 70)
    print(f"  Period: last 30 days\n")

    for theme in THEME_ORDER:
        stats = theme_stats.get(theme, {})
        name = stats.get("name", theme)
        avg = stats.get("avg_views", 0)

        print(f"  {name}")
        print(f"  {'-' * len(name)}")
        for a in stats.get("articles", []):
            label = a["article"].replace("_", " ")[:30]
            avg_v = a["avg"]
            trend = a["trend"]
            print(f"    {label:<32} {avg_v:>8,.0f} views/day  {trend:>8}")
        print(f"    {'Theme average:':<32} {avg:>8,.0f} views/day")
        print()


def _display_top(articles, date_str):
    if not articles:
        print(f"  No data for {date_str}.")
        return

    print(f"\n  TOP ARTICLES: {date_str}")
    print("  " + "=" * 60)
    print(f"  {'Rank':>6} {'Views':>12}  Article")
    print(f"  {'-'*6} {'-'*12}  {'-'*40}")

    for i, a in enumerate(articles[:50], 1):
        name = a.get("article", "?").replace("_", " ")
        views = a.get("views", 0)
        print(f"  {i:>6} {views:>12,}  {name}")

    print(f"\n  --- showing top {min(50, len(articles))} ---\n")


def _display_spikes(spikes):
    if not spikes:
        print("\n  No spikes detected.\n")
        return

    print(f"\n  VIEWERSHIP SPIKES")
    print("  " + "=" * 70)
    print(f"  {'Article':<30} {'Theme':<18} {'Ratio':>6} "
          f"{'Recent':>10} {'Trailing':>10}")
    print(f"  {'-'*30} {'-'*18} {'-'*6} {'-'*10} {'-'*10}")

    for s in spikes:
        label = s["article"].replace("_", " ")[:28]
        theme = s["theme"][:16]
        print(f"  {label:<30} {theme:<18} {s['ratio']:>5.1f}x "
              f"{s['recent_avg']:>10,.0f} {s['trailing_avg']:>10,.0f}")

    print(f"\n  --- {len(spikes)} articles with elevated attention ---\n")


# --- Export Helpers -----------------------------------------------------------

def _ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


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
    if fmt == "json":
        _export_json(data, path)
    elif fmt == "csv":
        if isinstance(data, dict):
            flat = []
            for key, val in data.items():
                if isinstance(val, list):
                    flat.extend(val)
                elif isinstance(val, dict):
                    val["_key"] = key
                    flat.append(val)
            data = flat if flat else [data]
        _export_csv(data, path)


# --- Command Functions --------------------------------------------------------

def cmd_article(article=None, days=30, granularity="daily",
                as_json=False, export_fmt=None):
    if not article:
        return

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    label = article.replace("_", " ")

    print(f"\n  Fetching {granularity} views for {label} ({days} days)...")
    items = _fetch_article_views(article, start_dt, end_dt, granularity)

    if as_json:
        print(json.dumps(items, indent=2))
        return

    _display_views_table(items, article)

    if export_fmt:
        rows = [{"date": _display_date(i["timestamp"]), "views": i["views"],
                 "article": article} for i in items]
        _do_export(rows, f"wiki_{article}", export_fmt)


def cmd_compare(articles=None, days=30, as_json=False, export_fmt=None):
    if not articles or len(articles) < 2:
        print("  [need at least 2 articles to compare]")
        return

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)

    print(f"\n  Comparing {len(articles)} articles ({days} days)...")
    results = _fetch_multi_articles(articles, start_dt, end_dt)

    if as_json:
        out = {}
        for a in articles:
            out[a] = results.get(a, [])
        print(json.dumps(out, indent=2))
        return

    _display_comparison(results, articles)

    if export_fmt:
        rows = []
        for a in articles:
            for item in results.get(a, []):
                rows.append({"article": a,
                             "date": _display_date(item["timestamp"]),
                             "views": item["views"]})
        _do_export(rows, "wiki_compare", export_fmt)


def cmd_theme(theme=None, days=30, as_json=False, export_fmt=None):
    if not theme or theme not in ARTICLE_REGISTRY:
        print(f"  [unknown theme: {theme}]")
        print(f"  Available: {', '.join(THEME_ORDER)}")
        return

    articles = ARTICLE_REGISTRY[theme]
    name = THEME_NAMES[theme]
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)

    print(f"\n  Fetching {name} ({len(articles)} articles, {days} days)...\n")
    results = _fetch_multi_articles(articles, start_dt, end_dt)

    if as_json:
        out = {}
        for a in articles:
            out[a] = results.get(a, [])
        print(json.dumps(out, indent=2))
        return

    _display_comparison(results, articles)

    if export_fmt:
        rows = []
        for a in articles:
            for item in results.get(a, []):
                rows.append({"theme": theme, "article": a,
                             "date": _display_date(item["timestamp"]),
                             "views": item["views"]})
        _do_export(rows, f"wiki_theme_{theme}", export_fmt)


def cmd_top(date_str=None, as_json=False, export_fmt=None):
    if not date_str:
        dt = datetime.now() - timedelta(days=1)
    else:
        dt = _parse_user_date(date_str)

    year, month, day = dt.year, dt.month, dt.day
    display = f"{year}-{month:02d}-{day:02d}"

    print(f"\n  Fetching top articles for {display}...")
    articles = _fetch_top(year, month, day)

    if as_json:
        print(json.dumps(articles[:50], indent=2))
        return

    _display_top(articles, display)

    if export_fmt:
        rows = [{"rank": i + 1, "article": a.get("article", ""),
                 "views": a.get("views", 0)}
                for i, a in enumerate(articles[:50])]
        _do_export(rows, f"wiki_top_{display}", export_fmt)


def cmd_fear_gauge(lookback=90, recent=7, as_json=False, export_fmt=None):
    gauge = _build_fear_gauge(lookback_days=lookback, recent_days=recent)

    if as_json:
        print(json.dumps(gauge, indent=2))
        return

    _display_fear_gauge(gauge)

    if export_fmt:
        _do_export(gauge, "wiki_fear_gauge", export_fmt)


def cmd_macro_dashboard(as_json=False, export_fmt=None):
    stats = _build_dashboard()

    if as_json:
        print(json.dumps(stats, indent=2))
        return

    _display_dashboard(stats)

    if export_fmt:
        rows = []
        for theme, data in stats.items():
            for a in data.get("articles", []):
                rows.append({"theme": theme, "article": a["article"],
                             "avg_views": a["avg"], "trend": a["trend"]})
        _do_export(rows, "wiki_dashboard", export_fmt)


def cmd_spike_detect(threshold=2.0, lookback=30, recent=7,
                     as_json=False, export_fmt=None):
    spikes = _detect_spikes(threshold=threshold, lookback_days=lookback,
                            recent_days=recent)

    if as_json:
        print(json.dumps(spikes, indent=2))
        return

    _display_spikes(spikes)

    if export_fmt:
        _do_export(spikes, "wiki_spikes", export_fmt)


def cmd_history(article=None, months=24, as_json=False, export_fmt=None):
    if not article:
        return

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=months * 31)
    label = article.replace("_", " ")

    print(f"\n  Fetching monthly history for {label} (~{months} months)...")
    items = _fetch_article_views(article, start_dt, end_dt, granularity="monthly")

    if as_json:
        print(json.dumps(items, indent=2))
        return

    _display_views_table(items, article)

    if export_fmt:
        rows = [{"date": _display_date(i["timestamp"]), "views": i["views"],
                 "article": article} for i in items]
        _do_export(rows, f"wiki_history_{article}", export_fmt)


def cmd_aggregate(days=30, granularity="daily", as_json=False, export_fmt=None):
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)

    print(f"\n  Fetching aggregate Wikipedia traffic ({days} days, {granularity})...")
    items = _fetch_aggregate(start_dt, end_dt, granularity)

    if as_json:
        print(json.dumps(items, indent=2))
        return

    if not items:
        print("  [no aggregate data returned]")
        return

    print(f"\n  AGGREGATE WIKIPEDIA TRAFFIC")
    print("  " + "=" * 50)
    print(f"  {'Date':<14} {'Views':>16}")
    print(f"  {'-'*14} {'-'*16}")

    total = 0
    for item in items:
        date_str = _display_date(item["timestamp"])
        views = item["views"]
        total += views
        print(f"  {date_str:<14} {views:>16,}")

    avg = total / len(items) if items else 0
    print(f"  {'-'*14} {'-'*16}")
    print(f"  {'Total':<14} {total:>16,}")
    print(f"  {'Daily avg':<14} {avg:>16,.0f}")
    print(f"\n  --- {len(items)} data points ---\n")

    if export_fmt:
        rows = [{"date": _display_date(i["timestamp"]), "views": i["views"]}
                for i in items]
        _do_export(rows, "wiki_aggregate", export_fmt)


def cmd_themes(as_json=False):
    if as_json:
        print(json.dumps(ARTICLE_REGISTRY, indent=2))
        return

    total = sum(len(v) for v in ARTICLE_REGISTRY.values())
    print(f"\n  CURATED THEMES ({len(ARTICLE_REGISTRY)} themes, {total} articles)")
    print("  " + "=" * 60)

    for theme in THEME_ORDER:
        name = THEME_NAMES[theme]
        articles = ARTICLE_REGISTRY[theme]
        print(f"\n  {name} [{theme}]")
        print(f"  {'-' * len(name)}")
        for a in articles:
            print(f"    {a.replace('_', ' ')}")

    print()


def cmd_search(article=None, days=30, as_json=False, export_fmt=None):
    if not article:
        return

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    search_term = article.replace(" ", "_")
    label = search_term.replace("_", " ")

    print(f"\n  Looking up '{label}' ({days} days)...")
    items = _fetch_article_views(search_term, start_dt, end_dt)

    if as_json:
        print(json.dumps(items, indent=2))
        return

    if not items:
        print(f"  [no data for '{label}' -- check title, it is case-sensitive]")
        return

    _display_views_table(items, search_term)

    if export_fmt:
        rows = [{"date": _display_date(i["timestamp"]), "views": i["views"],
                 "article": search_term} for i in items]
        _do_export(rows, f"wiki_search_{search_term}", export_fmt)


def cmd_export(sub_command=None, export_fmt="json", **kwargs):
    """Re-run a command with export flag. Delegates to the target cmd_* function."""
    dispatch = {
        "article": cmd_article,
        "compare": cmd_compare,
        "theme": cmd_theme,
        "top": cmd_top,
        "fear-gauge": cmd_fear_gauge,
        "macro-dashboard": cmd_macro_dashboard,
        "spike-detect": cmd_spike_detect,
        "history": cmd_history,
        "aggregate": cmd_aggregate,
        "search": cmd_search,
    }

    fn = dispatch.get(sub_command)
    if not fn:
        print(f"  [unknown export target: {sub_command}]")
        print(f"  Available: {', '.join(sorted(dispatch.keys()))}")
        return

    fn(export_fmt=export_fmt, **kwargs)


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   Wikipedia Pageviews -- Macro Attention / Fear Gauge
  =====================================================

   BROWSE
     1) article         Pageviews for a specific article
     2) compare         Compare multiple articles
     3) theme           All articles in a curated theme
     4) top             Most-viewed articles on a day

   ANALYSIS
     5) fear-gauge      Composite fear index
     6) macro-dashboard Full cross-theme snapshot
     7) spike-detect    Find viewership spikes

   DATA
     8) history         Long monthly history
     9) aggregate       Total Wikipedia traffic
    10) themes          List curated themes
    11) search          Lookup any article
    12) export          Export data

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


def _pick_article():
    print("  Curated articles (or type any title):")
    all_articles = []
    for theme in THEME_ORDER:
        for a in ARTICLE_REGISTRY[theme]:
            all_articles.append(a)
    col = 0
    for a in all_articles:
        if col == 0:
            print("    ", end="")
        print(f"{a.replace('_', ' '):<35}", end="")
        col += 1
        if col >= 3:
            print()
            col = 0
    if col > 0:
        print()
    val = _prompt("Article title")
    return val.replace(" ", "_") if val else None


def _i_article():
    article = _pick_article()
    if not article:
        return
    days = int(_prompt("Days", "30"))
    cmd_article(article=article, days=days)


def _i_compare():
    print("  Enter article titles separated by commas:")
    raw = _prompt("Articles")
    if not raw:
        return
    articles = [a.strip().replace(" ", "_") for a in raw.split(",") if a.strip()]
    if len(articles) < 2:
        print("  [need at least 2 articles]")
        return
    days = int(_prompt("Days", "30"))
    cmd_compare(articles=articles, days=days)


def _i_theme():
    print(f"  Themes: {', '.join(THEME_ORDER)}")
    theme = _prompt("Theme")
    if not theme:
        return
    days = int(_prompt("Days", "30"))
    cmd_theme(theme=theme, days=days)


def _i_top():
    date_str = _prompt("Date (YYYY-MM-DD)", "yesterday")
    if date_str == "yesterday":
        date_str = None
    cmd_top(date_str=date_str)


def _i_fear_gauge():
    lookback = int(_prompt("Lookback days", "90"))
    recent = int(_prompt("Recent window days", "7"))
    cmd_fear_gauge(lookback=lookback, recent=recent)


def _i_macro_dashboard():
    cmd_macro_dashboard()


def _i_spike_detect():
    threshold = float(_prompt("Spike threshold multiplier", "2.0"))
    cmd_spike_detect(threshold=threshold)


def _i_history():
    article = _pick_article()
    if not article:
        return
    months = int(_prompt("Months of history", "24"))
    cmd_history(article=article, months=months)


def _i_aggregate():
    days = int(_prompt("Days", "30"))
    gran = _prompt_choice("Granularity", ["daily", "monthly"], "daily")
    cmd_aggregate(days=days, granularity=gran)


def _i_themes():
    cmd_themes()


def _i_search():
    article = _prompt("Article title (exact, case-sensitive)")
    if not article:
        return
    days = int(_prompt("Days", "30"))
    cmd_search(article=article, days=days)


def _i_export():
    targets = ["article", "compare", "theme", "top", "fear-gauge",
               "macro-dashboard", "spike-detect", "history", "aggregate", "search"]
    print(f"  Targets: {', '.join(targets)}")
    target = _prompt("Command to export")
    fmt = _prompt_choice("Format", ["json", "csv"], "json")

    if target == "article":
        article = _pick_article()
        if article:
            cmd_article(article=article, export_fmt=fmt)
    elif target == "compare":
        raw = _prompt("Articles (comma-separated)")
        articles = [a.strip().replace(" ", "_") for a in raw.split(",")
                    if a.strip()]
        cmd_compare(articles=articles, export_fmt=fmt)
    elif target == "theme":
        theme = _prompt("Theme")
        cmd_theme(theme=theme, export_fmt=fmt)
    elif target == "top":
        cmd_top(export_fmt=fmt)
    elif target == "fear-gauge":
        cmd_fear_gauge(export_fmt=fmt)
    elif target == "macro-dashboard":
        cmd_macro_dashboard(export_fmt=fmt)
    elif target == "spike-detect":
        cmd_spike_detect(export_fmt=fmt)
    elif target == "history":
        article = _pick_article()
        if article:
            cmd_history(article=article, export_fmt=fmt)
    elif target == "aggregate":
        cmd_aggregate(export_fmt=fmt)
    elif target == "search":
        article = _prompt("Article title")
        if article:
            cmd_search(article=article, export_fmt=fmt)
    else:
        print(f"  [unknown export target: {target}]")


COMMAND_MAP = {
    "1":  _i_article,
    "2":  _i_compare,
    "3":  _i_theme,
    "4":  _i_top,
    "5":  _i_fear_gauge,
    "6":  _i_macro_dashboard,
    "7":  _i_spike_detect,
    "8":  _i_history,
    "9":  _i_aggregate,
    "10": _i_themes,
    "11": _i_search,
    "12": _i_export,
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
            print("  Enter 1-12 or q to quit")


# --- Argparse -----------------------------------------------------------------

def build_argparse():
    p = argparse.ArgumentParser(
        prog="wikipedia.py",
        description="Wikipedia Pageviews -- Macro Attention / Fear Gauge",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("article", help="Pageviews for a specific article")
    s.add_argument("article", help="Article title (e.g. Recession)")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--granularity", choices=["daily", "monthly"], default="daily")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("compare", help="Compare multiple articles")
    s.add_argument("articles", nargs="+", help="Article titles")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("theme", help="All articles in a curated theme")
    s.add_argument("theme", choices=THEME_ORDER)
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("top", help="Most-viewed articles on a day")
    s.add_argument("--date", help="Date as YYYY-MM-DD (default: yesterday)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("fear-gauge", help="Composite fear index")
    s.add_argument("--lookback", type=int, default=90)
    s.add_argument("--recent", type=int, default=7)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("macro-dashboard", help="Cross-theme attention snapshot")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("spike-detect", help="Find viewership spikes")
    s.add_argument("--threshold", type=float, default=2.0)
    s.add_argument("--lookback", type=int, default=30)
    s.add_argument("--recent", type=int, default=7)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("history", help="Long monthly history for an article")
    s.add_argument("article", help="Article title")
    s.add_argument("--months", type=int, default=24)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("aggregate", help="Total Wikipedia traffic")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--granularity", choices=["daily", "monthly"], default="daily")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("themes", help="List curated themes and articles")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("search", help="Lookup any arbitrary article")
    s.add_argument("article", help="Article title (case-sensitive)")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("export", help="Export data for any command")
    s.add_argument("target", help="Command to export (e.g. fear-gauge)")
    s.add_argument("--export", choices=["csv", "json"], default="json")
    s.add_argument("--article", help="Article for article/history/search")
    s.add_argument("--articles", nargs="+", help="Articles for compare")
    s.add_argument("--theme", choices=THEME_ORDER)
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--date", help="Date for top")

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "article":
        cmd_article(article=args.article, days=args.days,
                    granularity=args.granularity, as_json=j, export_fmt=exp)

    elif args.command == "compare":
        cmd_compare(articles=args.articles, days=args.days,
                    as_json=j, export_fmt=exp)

    elif args.command == "theme":
        cmd_theme(theme=args.theme, days=args.days, as_json=j, export_fmt=exp)

    elif args.command == "top":
        cmd_top(date_str=args.date, as_json=j, export_fmt=exp)

    elif args.command == "fear-gauge":
        cmd_fear_gauge(lookback=args.lookback, recent=args.recent,
                       as_json=j, export_fmt=exp)

    elif args.command == "macro-dashboard":
        cmd_macro_dashboard(as_json=j, export_fmt=exp)

    elif args.command == "spike-detect":
        cmd_spike_detect(threshold=args.threshold, lookback=args.lookback,
                         recent=args.recent, as_json=j, export_fmt=exp)

    elif args.command == "history":
        cmd_history(article=args.article, months=args.months,
                    as_json=j, export_fmt=exp)

    elif args.command == "aggregate":
        cmd_aggregate(days=args.days, granularity=args.granularity,
                      as_json=j, export_fmt=exp)

    elif args.command == "themes":
        cmd_themes(as_json=j)

    elif args.command == "search":
        cmd_search(article=args.article, days=args.days,
                   as_json=j, export_fmt=exp)

    elif args.command == "export":
        target = args.target
        fmt = args.export or "json"
        if target in ("article", "history", "search") and args.article:
            dispatch = {"article": cmd_article, "history": cmd_history,
                        "search": cmd_search}
            dispatch[target](article=args.article, days=args.days, export_fmt=fmt)
        elif target == "compare" and args.articles:
            cmd_compare(articles=args.articles, days=args.days, export_fmt=fmt)
        elif target == "theme" and args.theme:
            cmd_theme(theme=args.theme, days=args.days, export_fmt=fmt)
        elif target == "top":
            cmd_top(date_str=args.date, export_fmt=fmt)
        elif target == "fear-gauge":
            cmd_fear_gauge(export_fmt=fmt)
        elif target == "macro-dashboard":
            cmd_macro_dashboard(export_fmt=fmt)
        elif target == "spike-detect":
            cmd_spike_detect(export_fmt=fmt)
        elif target == "aggregate":
            cmd_aggregate(days=args.days, export_fmt=fmt)
        else:
            print(f"  [missing required args for export target '{target}']")


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
