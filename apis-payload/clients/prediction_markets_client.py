#!/usr/bin/env python3
"""
Prediction Markets State-of-the-World Scraper
==============================================

Pulls event and market data from Kalshi and Polymarket public APIs (no auth required)
to construct a through-time state of the world: what events are priced, at what
probabilities, and how those probabilities have evolved.

The output is a temporally-ordered dataset that gives an AI consumer perfect
understanding of the exact set of geopolitical, economic, and policy events
that markets are pricing at any point in time.

APIs
----
Kalshi:      https://api.elections.kalshi.com/trade-api/v2  (public, ~30 req/s)
Polymarket:  https://gamma-api.polymarket.com               (public, no stated limit)
             https://clob.polymarket.com                    (public, price history)

No API keys required for any endpoint used here.
"""

import argparse
import csv
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

# ── Constants ─────────────────────────────────────────────────────────────────

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
POLY_GAMMA = "https://gamma-api.polymarket.com"
POLY_CLOB = "https://clob.polymarket.com"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

KALSHI_MACRO_CATEGORIES = [
    "economics",
    "politics",
    "world",
    "finance",
    "climate",
    "tech",
]

POLYMARKET_MACRO_TAGS = [
    "Politics",
    "Crypto",
    "Business",
    "Pop Culture",
    "Science",
    "Sports",
    "Global Elections",
]

MACRO_KEYWORDS = [
    "fed", "fomc", "rate", "inflation", "cpi", "gdp", "recession",
    "tariff", "trade", "china", "iran", "russia", "ukraine", "war",
    "oil", "opec", "nato", "nuclear", "sanctions", "ceasefire",
    "trump", "biden", "election", "congress", "debt ceiling",
    "treasury", "yield", "s&p", "nasdaq", "bitcoin", "crypto",
    "unemployment", "jobs", "nonfarm", "pmi", "ism",
    "default", "shutdown", "stimulus", "qe", "qt",
    "israel", "gaza", "hamas", "hezbollah", "taiwan",
    "ai", "regulation", "antitrust", "bank", "svb",
    "supreme court", "impeach", "indictment",
]

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/json",
    "User-Agent": "prediction-markets-scraper/1.0",
})

# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts_to_iso(ts):
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _now_ts():
    return int(datetime.now(tz=timezone.utc).timestamp())


def _days_ago_ts(days):
    return int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp())


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _sleep_rate_limit(source="kalshi"):
    time.sleep(0.15 if source == "kalshi" else 0.05)


def _safe_volume(v):
    if v is None:
        return 0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0


def _is_macro_relevant(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in MACRO_KEYWORDS)


def _save_json(data, filename):
    _ensure_data_dir()
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Saved {path} ({len(json.dumps(data, default=str)):,} bytes)")
    return path


def _save_csv(rows, filename, fieldnames=None):
    if not rows:
        print(f"  No data to save for {filename}")
        return None
    _ensure_data_dir()
    path = os.path.join(DATA_DIR, filename)
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  Saved {path} ({len(rows)} rows)")
    return path


# ── Kalshi API ────────────────────────────────────────────────────────────────

def kalshi_get(endpoint, params=None):
    url = f"{KALSHI_BASE}/{endpoint}"
    resp = SESSION.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def kalshi_get_series_list():
    """Get all series (recurring event templates) across macro categories."""
    all_series = []
    for cat in KALSHI_MACRO_CATEGORIES:
        try:
            data = kalshi_get("series", {"category": cat})
            series_list = data.get("series", [])
            for s in series_list:
                s["_category"] = cat
            all_series.extend(series_list)
            print(f"  Kalshi series [{cat}]: {len(series_list)}")
            _sleep_rate_limit("kalshi")
        except Exception as e:
            print(f"  Kalshi series [{cat}] error: {e}")
    return all_series


def kalshi_get_all_events(status="open", limit=200):
    """Paginate through all Kalshi events."""
    all_events = []
    cursor = None
    page = 0
    while True:
        params = {"limit": limit, "status": status, "with_nested_markets": "true"}
        if cursor:
            params["cursor"] = cursor
        data = kalshi_get("events", params)
        events = data.get("events", [])
        all_events.extend(events)
        page += 1
        print(f"  Kalshi events page {page}: {len(events)} events (total: {len(all_events)})")
        cursor = data.get("cursor")
        if not events or not cursor:
            break
        _sleep_rate_limit("kalshi")
    return all_events


def kalshi_get_markets(series_ticker=None, event_ticker=None, status="open", limit=200):
    """Get markets with optional filters."""
    all_markets = []
    cursor = None
    while True:
        params = {"limit": limit, "status": status}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if cursor:
            params["cursor"] = cursor
        data = kalshi_get("markets", params)
        markets = data.get("markets", [])
        all_markets.extend(markets)
        cursor = data.get("cursor")
        if not markets or not cursor:
            break
        _sleep_rate_limit("kalshi")
    return all_markets


def kalshi_get_candlesticks(ticker, period_minutes=1440, days_back=90):
    """Get daily candlesticks for a market."""
    start_ts = _days_ago_ts(days_back)
    end_ts = _now_ts()
    try:
        data = kalshi_get(f"markets/{ticker}/candlesticks", {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period_minutes,
        })
        return data.get("candlesticks", [])
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            try:
                data = kalshi_get(f"historical/markets/{ticker}/candlesticks", {
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "period_interval": period_minutes,
                })
                return data.get("candlesticks", [])
            except Exception:
                pass
        return []


def kalshi_extract_market_record(market, event=None):
    """Normalize a Kalshi market into a flat record."""
    yes_price = market.get("yes_bid_dollars") or market.get("last_price") or market.get("yes_ask")
    if yes_price is not None and isinstance(yes_price, (int, float)):
        if yes_price > 1:
            yes_price = yes_price / 100.0
    return {
        "source": "kalshi",
        "market_id": market.get("ticker", ""),
        "event_id": market.get("event_ticker", ""),
        "title": market.get("title", ""),
        "subtitle": market.get("subtitle", ""),
        "event_title": event.get("title", "") if event else "",
        "category": market.get("category", event.get("category", "") if event else ""),
        "status": market.get("status", ""),
        "yes_price": yes_price,
        "volume": market.get("volume") or market.get("volume_fp", 0),
        "open_interest": market.get("open_interest", 0),
        "close_time": market.get("close_time", ""),
        "expiration_time": market.get("expiration_time", ""),
        "result": market.get("result", ""),
        "last_price": market.get("last_price"),
        "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ── Polymarket API ────────────────────────────────────────────────────────────

def poly_gamma_get(endpoint, params=None):
    url = f"{POLY_GAMMA}/{endpoint}"
    resp = SESSION.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def poly_clob_get(endpoint, params=None):
    url = f"{POLY_CLOB}/{endpoint}"
    resp = SESSION.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def poly_get_tags():
    """Get all available tags/categories."""
    try:
        return poly_gamma_get("tags")
    except Exception as e:
        print(f"  Polymarket tags error: {e}")
        return []


def poly_get_all_events(active=True, limit=100, min_volume=10000):
    """Paginate through Polymarket events."""
    all_events = []
    offset = 0
    page = 0
    while True:
        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower(),
            "closed": "false" if active else "true",
            "order": "volume_24hr",
            "ascending": "false",
        }
        if min_volume:
            params["volume_min"] = min_volume
        try:
            events = poly_gamma_get("events", params)
        except Exception as e:
            print(f"  Polymarket events error at offset {offset}: {e}")
            break
        if not events:
            break
        if isinstance(events, dict):
            events = events.get("data", events.get("events", []))
        all_events.extend(events)
        page += 1
        print(f"  Polymarket events page {page}: {len(events)} events (total: {len(all_events)})")
        if len(events) < limit:
            break
        offset += limit
        _sleep_rate_limit("poly")
    return all_events


def poly_get_price_history(token_id, interval="1d", fidelity=1440):
    """Get price history for a Polymarket token."""
    try:
        data = poly_clob_get("prices-history", {
            "market": token_id,
            "interval": "max",
            "fidelity": fidelity,
        })
        return data.get("history", [])
    except Exception as e:
        return []


def _extract_poly_tags(event):
    tags = event.get("tags", [])
    if not tags:
        return ""
    if isinstance(tags[0], dict):
        return ", ".join(t.get("label", t.get("name", str(t))) for t in tags)
    return ", ".join(str(t) for t in tags)


def poly_extract_market_record(market, event=None):
    """Normalize a Polymarket market into a flat record."""
    outcomes = market.get("outcomes", "[]")
    prices = market.get("outcomePrices", "[]")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            outcomes = []
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except Exception:
            prices = []

    yes_price = None
    if prices:
        try:
            yes_price = float(prices[0])
        except (ValueError, IndexError):
            pass

    clob_token_ids = market.get("clobTokenIds", "[]")
    if isinstance(clob_token_ids, str):
        try:
            clob_token_ids = json.loads(clob_token_ids)
        except Exception:
            clob_token_ids = []

    return {
        "source": "polymarket",
        "market_id": market.get("id", ""),
        "event_id": event.get("id", "") if event else "",
        "title": market.get("question", market.get("title", "")),
        "subtitle": "",
        "event_title": event.get("title", "") if event else "",
        "category": _extract_poly_tags(event) if event else "",
        "status": "active" if market.get("active") else "closed",
        "yes_price": yes_price,
        "volume": market.get("volume", 0),
        "open_interest": market.get("openInterest", 0),
        "close_time": market.get("endDate", ""),
        "expiration_time": market.get("endDate", ""),
        "result": market.get("resolutionSource", ""),
        "last_price": yes_price,
        "clob_token_ids": clob_token_ids,
        "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ── Unified Timeline Builder ─────────────────────────────────────────────────

def build_unified_market_snapshot(kalshi_events, poly_events):
    """Merge Kalshi and Polymarket data into a single unified market list,
    filtered to macro-relevant events."""
    records = []

    for event in kalshi_events:
        markets = event.get("markets", [])
        for m in markets:
            rec = kalshi_extract_market_record(m, event)
            if _is_macro_relevant(rec["title"]) or _is_macro_relevant(rec["event_title"]):
                records.append(rec)
        if not markets:
            title = event.get("title", "")
            if _is_macro_relevant(title):
                records.append({
                    "source": "kalshi",
                    "market_id": event.get("event_ticker", ""),
                    "event_id": event.get("event_ticker", ""),
                    "title": title,
                    "subtitle": event.get("subtitle", ""),
                    "event_title": title,
                    "category": event.get("category", ""),
                    "status": "open",
                    "yes_price": None,
                    "volume": 0,
                    "open_interest": 0,
                    "close_time": "",
                    "expiration_time": "",
                    "result": "",
                    "last_price": None,
                    "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
                })

    for event in poly_events:
        markets = event.get("markets", [])
        if not markets:
            continue
        for m in markets:
            rec = poly_extract_market_record(m, event)
            if _is_macro_relevant(rec["title"]) or _is_macro_relevant(rec["event_title"]):
                records.append(rec)

    records.sort(key=lambda r: _safe_volume(r.get("volume")), reverse=True)
    return records


def fetch_price_histories(records, max_markets=50, days_back=90):
    """Fetch time series for the top N markets by volume."""
    histories = {}
    count = 0
    for rec in records:
        if count >= max_markets:
            break
        mid = rec["market_id"]
        source = rec["source"]
        if mid in histories:
            continue

        print(f"  [{count+1}/{max_markets}] Fetching history: {rec['title'][:70]}...")

        if source == "kalshi":
            candles = kalshi_get_candlesticks(mid, period_minutes=1440, days_back=days_back)
            if candles:
                histories[mid] = {
                    "source": "kalshi",
                    "market_id": mid,
                    "title": rec["title"],
                    "event_title": rec.get("event_title", ""),
                    "category": rec.get("category", ""),
                    "series": [
                        {
                            "timestamp": _ts_to_iso(c.get("end_period_ts") or c.get("open_ts")),
                            "open": c.get("open"),
                            "high": c.get("high"),
                            "low": c.get("low"),
                            "close": c.get("close"),
                            "volume": c.get("volume"),
                            "yes_price": c.get("yes_price") or c.get("close"),
                        }
                        for c in candles
                    ],
                }
                count += 1

        elif source == "polymarket":
            token_ids = rec.get("clob_token_ids", [])
            if token_ids:
                history = poly_get_price_history(token_ids[0])
                if history:
                    histories[mid] = {
                        "source": "polymarket",
                        "market_id": mid,
                        "title": rec["title"],
                        "event_title": rec.get("event_title", ""),
                        "category": rec.get("category", ""),
                        "series": [
                            {
                                "timestamp": _ts_to_iso(h.get("t")),
                                "yes_price": h.get("p"),
                            }
                            for h in history
                        ],
                    }
                    count += 1

        _sleep_rate_limit(source)

    return histories


def build_state_of_world(records, histories):
    """Construct a structured state-of-the-world document from market data."""
    now = datetime.now(tz=timezone.utc)

    theme_buckets = {
        "Federal Reserve & Monetary Policy": [],
        "Inflation & Economic Data": [],
        "Geopolitics: Iran": [],
        "Geopolitics: Russia/Ukraine": [],
        "Geopolitics: China/Taiwan": [],
        "Geopolitics: Israel/Middle East": [],
        "Trade & Tariffs": [],
        "US Politics & Elections": [],
        "US Policy: Trump Administration": [],
        "Crypto & Digital Assets": [],
        "Energy & Commodities": [],
        "Technology & AI": [],
        "Nuclear": [],
        "Financial Markets": [],
        "Other Macro": [],
    }

    theme_keywords = {
        "Federal Reserve & Monetary Policy": ["fed ", "fed?", "fomc", "rate cut", "rate hike", "interest rate", "powell", "monetary", "fed chair", "fed rate"],
        "Inflation & Economic Data": ["inflation", "cpi", "ppi", "gdp", "recession", "unemployment", "jobs report", "nonfarm", "pmi", "ism ", "consumer price", "producer price", "payroll"],
        "Geopolitics: Iran": ["iran", "tehran", "strait of hormuz", "kharg island", "pahlavi", "araghchi"],
        "Geopolitics: Russia/Ukraine": ["russia", "ukraine", "putin", "zelensky", "crimea", "nato", "moscow", "kyiv"],
        "Geopolitics: China/Taiwan": ["china", "taiwan", "xi jinping", "beijing", "chinese"],
        "Geopolitics: Israel/Middle East": ["israel", "gaza", "hamas", "hezbollah", "netanyahu", "west bank"],
        "Trade & Tariffs": ["tariff", "trade war", "trade deal", "wto", "import duty", "export ban", "trade deficit", "reciprocal tariff", "refund tariff"],
        "US Politics & Elections": ["presidential", "election", "congress", "senate", "house speaker", "supreme court", "impeach", "indictment", "governor", "democrat", "republican", "nomination"],
        "US Policy: Trump Administration": ["trump", "biden", "executive order", "doge", "musk", "white house", "vance", "cabinet"],
        "Crypto & Digital Assets": ["bitcoin", "crypto", "ethereum", "stablecoin", "defi", "btc ", "eth "],
        "Energy & Commodities": ["oil", "opec", "crude", "natural gas", "energy price", "commodity", "gold price", "wti", "brent"],
        "Technology & AI": ["artificial intelligence", "openai", "anthropic", "google ai", "ai model", "agi", "chatgpt", "llm"],
        "Nuclear": ["nuclear", "nuclear weapon", "enrichment", "warhead"],
        "Financial Markets": ["s&p", "nasdaq", "dow jones", "vix", "yield", "treasury", "bond market", "stock market", "market crash"],
    }

    for rec in records:
        title_lower = (rec["title"] + " " + rec.get("event_title", "")).lower()
        placed = False
        for theme, keywords in theme_keywords.items():
            if any(kw in title_lower for kw in keywords):
                theme_buckets[theme].append(rec)
                placed = True
                break
        if not placed:
            theme_buckets["Other Macro"].append(rec)

    state = {
        "generated_at": now.isoformat(),
        "description": (
            "State of the world as implied by prediction market pricing. "
            "Each section groups markets by macro theme. Probabilities are "
            "YES prices (0-1 scale where 1.0 = 100% certain). Markets are "
            "ranked by volume within each theme."
        ),
        "summary_stats": {
            "total_markets_tracked": len(records),
            "markets_with_history": len(histories),
            "sources": {
                "kalshi": len([r for r in records if r["source"] == "kalshi"]),
                "polymarket": len([r for r in records if r["source"] == "polymarket"]),
            },
        },
        "themes": {},
    }

    for theme, bucket in theme_buckets.items():
        if not bucket:
            continue
        bucket.sort(key=lambda r: _safe_volume(r.get("volume")), reverse=True)
        theme_data = {
            "market_count": len(bucket),
            "total_volume": sum(_safe_volume(r.get("volume")) for r in bucket),
            "markets": [],
        }
        for rec in bucket[:25]:
            mid = rec["market_id"]
            market_entry = {
                "source": rec["source"],
                "title": rec["title"],
                "event": rec.get("event_title", ""),
                "probability": rec.get("yes_price"),
                "volume": rec.get("volume"),
                "status": rec.get("status", ""),
                "closes": rec.get("close_time", ""),
            }
            if mid in histories:
                series = histories[mid].get("series", [])
                if len(series) >= 2:
                    recent = series[-1].get("yes_price") or series[-1].get("close")
                    older = series[0].get("yes_price") or series[0].get("close")
                    if recent is not None and older is not None:
                        try:
                            market_entry["price_change_period"] = round(float(recent) - float(older), 4)
                        except (ValueError, TypeError):
                            pass
                    week_ago_idx = max(0, len(series) - 7)
                    week_price = series[week_ago_idx].get("yes_price") or series[week_ago_idx].get("close")
                    if recent is not None and week_price is not None:
                        try:
                            market_entry["price_change_7d"] = round(float(recent) - float(week_price), 4)
                        except (ValueError, TypeError):
                            pass
            theme_data["markets"].append(market_entry)
        state["themes"][theme] = theme_data

    return state


def build_timeline(histories):
    """Build a date-indexed timeline showing how the world state evolved."""
    date_events = {}
    for mid, hist in histories.items():
        series = hist.get("series", [])
        title = hist.get("title", mid)
        for i, point in enumerate(series):
            ts = point.get("timestamp", "")
            if not ts:
                continue
            date_key = ts[:10]  # YYYY-MM-DD
            if date_key not in date_events:
                date_events[date_key] = []

            price = point.get("yes_price") or point.get("close")
            prev_price = None
            if i > 0:
                prev_price = series[i - 1].get("yes_price") or series[i - 1].get("close")

            change = None
            if price is not None and prev_price is not None:
                try:
                    change = round(float(price) - float(prev_price), 4)
                except (ValueError, TypeError):
                    pass

            if change is not None and abs(change) < 0.01:
                continue

            date_events[date_key].append({
                "market": title,
                "source": hist.get("source", ""),
                "category": hist.get("category", ""),
                "price": price,
                "change": change,
            })

    timeline = []
    for date_key in sorted(date_events.keys()):
        day_data = date_events[date_key]
        day_data.sort(key=lambda x: abs(x.get("change") or 0), reverse=True)
        timeline.append({
            "date": date_key,
            "significant_moves": len(day_data),
            "markets": day_data[:20],
        })

    return timeline


# ── Time Series Engine ────────────────────────────────────────────────────────

def _extract_series(history_dict, truncate_to_date=True):
    """Extract (timestamps, prices) from a market history dict. Prices on 0-1 scale.
    If truncate_to_date=True, timestamps are YYYY-MM-DD; otherwise full ISO."""
    series = history_dict.get("series", [])
    timestamps, prices = [], []
    for pt in series:
        ts = pt.get("timestamp")
        p = pt.get("yes_price")
        if ts is None or p is None:
            continue
        try:
            p = float(p)
        except (ValueError, TypeError):
            continue
        timestamps.append(ts[:10] if truncate_to_date else ts)
        prices.append(p)
    return timestamps, prices


def _extract_daily_series(history_dict):
    """Extract (dates, prices) from a market history dict. Prices on 0-1 scale."""
    return _extract_series(history_dict, truncate_to_date=True)


# ── Shock Detection & Regime Analysis ─────────────────────────────────────────

def _compute_daily_changes(prices):
    """Return list of (index, change) for each day-over-day move."""
    return [(i, prices[i] - prices[i - 1]) for i in range(1, len(prices))]


def _std(values):
    if len(values) < 2:
        return 0.0
    mu = sum(values) / len(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / (len(values) - 1))


def detect_shocks(dates, prices, sigma_thresholds=(3.0, 5.0)):
    """Detect statistically significant moves using both full-sample and trailing volatility.

    Returns a list of shock dicts sorted by sigma (descending), each containing:
      date, prev_date, price_before, price_after, change_pp,
      z_full (z-score vs full-sample vol), z_trail (z-score vs trailing 20d vol),
      sigma (max of the two), daily_vol_pp (full-sample daily vol)
    """
    if len(prices) < 5:
        return [], 0.0

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    full_std = _std(changes)
    full_mean = sum(changes) / len(changes)

    if full_std < 0.0005:
        return [], full_std

    trail_window = min(20, max(5, len(changes) // 3))
    min_sigma = min(sigma_thresholds)

    shocks = []
    for i, chg in enumerate(changes):
        z_full = (chg - full_mean) / full_std if full_std > 0 else 0.0

        trail_start = max(0, i - trail_window)
        trail_slice = changes[trail_start:i]
        if len(trail_slice) >= 3:
            trail_std = _std(trail_slice)
            trail_mean = sum(trail_slice) / len(trail_slice)
            z_trail = (chg - trail_mean) / trail_std if trail_std > 0.0005 else z_full
        else:
            z_trail = z_full

        sigma = max(abs(z_full), abs(z_trail))

        if sigma >= min_sigma:
            shocks.append({
                "date": dates[i + 1],
                "prev_date": dates[i],
                "price_before": prices[i],
                "price_after": prices[i + 1],
                "change": chg,
                "change_pp": chg * 100,
                "z_full": z_full,
                "z_trail": z_trail,
                "sigma": sigma,
            })

    shocks.sort(key=lambda s: s["sigma"], reverse=True)
    return shocks, full_std


def detect_regime_shifts(dates, prices, min_shift_pp=10.0, window=5):
    """Detect sustained level changes by comparing rolling windows.

    A regime shift is flagged when the mean price over `window` days after a point
    differs from the mean over `window` days before by >= min_shift_pp percentage points,
    AND the new level holds (the post-window mean stays separated from pre-window mean).
    """
    n = len(prices)
    if n < window * 3:
        return []

    shifts = []
    i = window
    while i < n - window:
        pre_mean = sum(prices[i - window:i]) / window
        post_mean = sum(prices[i:i + window]) / window
        shift_pp = (post_mean - pre_mean) * 100

        if abs(shift_pp) >= min_shift_pp:
            hold_end = min(i + window * 2, n)
            if hold_end > i + window:
                hold_mean = sum(prices[i + window:hold_end]) / (hold_end - i - window)
                hold_ok = abs((hold_mean - pre_mean) * 100) >= min_shift_pp * 0.5
            else:
                hold_ok = True

            if hold_ok:
                peak_in_window = max(prices[i:i + window]) if shift_pp > 0 else min(prices[i:i + window])
                shifts.append({
                    "start_date": dates[i],
                    "end_date": dates[min(i + window - 1, n - 1)],
                    "pre_level": pre_mean,
                    "post_level": post_mean,
                    "shift_pp": shift_pp,
                    "peak_in_window": peak_in_window,
                    "direction": "UP" if shift_pp > 0 else "DOWN",
                })
                i += window
                continue
        i += 1

    merged = []
    for s in shifts:
        if merged and s["start_date"] <= merged[-1]["end_date"]:
            prev = merged[-1]
            if (s["shift_pp"] > 0) == (prev["shift_pp"] > 0):
                prev["end_date"] = s["end_date"]
                prev["post_level"] = s["post_level"]
                prev["shift_pp"] = (s["post_level"] - prev["pre_level"]) * 100
                continue
        merged.append(s)

    return merged


def compute_volatility_profile(dates, prices, window=10):
    """Compute rolling realized volatility (annualized-ish, in pp) for context.

    Returns (vol_mean_pp, vol_current_pp, vol_max_pp, vol_max_date).
    """
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    if len(changes) < window:
        std = _std(changes) if len(changes) >= 2 else 0.0
        return std * 100, std * 100, std * 100, dates[-1] if dates else ""

    rolling_vols = []
    for i in range(window, len(changes) + 1):
        rv = _std(changes[i - window:i])
        rolling_vols.append((i, rv))

    vols = [v for _, v in rolling_vols]
    vol_mean = sum(vols) / len(vols)
    vol_current = vols[-1]
    vol_max_idx = max(range(len(vols)), key=lambda j: vols[j])
    vol_max = vols[vol_max_idx]
    vol_max_date_idx = rolling_vols[vol_max_idx][0]
    vol_max_date = dates[vol_max_date_idx] if vol_max_date_idx < len(dates) else dates[-1]

    return vol_mean * 100, vol_current * 100, vol_max * 100, vol_max_date


def render_market_time_series(history_dict, granularity="daily"):
    """Produce a full LLM-readable context block for one market time series.
    Raw CSV data + statistical analytics (shocks, regime shifts, volatility)."""
    is_hourly = granularity == "hourly"
    timestamps, prices = _extract_series(history_dict, truncate_to_date=not is_hourly)
    if not timestamps:
        title = history_dict.get("title", "?")
        return f"[{title}] -- no time series data available"

    title = history_dict.get("title", "Unknown Market")
    source = history_dict.get("source", "?")
    market_id = history_dict.get("market_id", "?")
    n = len(timestamps)

    first_t, last_t = timestamps[0], timestamps[-1]
    first_p, last_p = prices[0], prices[-1]
    p_min, p_max = min(prices), max(prices)
    min_idx = prices.index(p_min)
    max_idx = prices.index(p_max)
    net_change = last_p - first_p
    mean_p = sum(prices) / len(prices)

    daily_dates, daily_prices = _extract_daily_series(history_dict)
    shocks, daily_vol = detect_shocks(daily_dates, daily_prices, sigma_thresholds=(3.0, 5.0))
    regimes = detect_regime_shifts(daily_dates, daily_prices, min_shift_pp=10.0)
    vol_mean, vol_current, vol_max, vol_max_date = compute_volatility_profile(daily_dates, daily_prices)

    parts = []
    parts.append(f"=== {title} ===")
    parts.append(f"Source: {source} | ID: {market_id}")
    parts.append(f"Period: {first_t} to {last_t} ({n} {granularity} points)")
    parts.append(f"Current: {last_p*100:.1f}% | Start: {first_p*100:.1f}% | Net: {net_change*100:+.1f}pp")
    parts.append("")

    parts.append(f"TIME SERIES ({granularity}, {n} points):")
    parts.append("timestamp,price")
    for t, p in zip(timestamps, prices):
        parts.append(f"{t},{p:.4f}")
    parts.append("")

    parts.append("KEY STATS:")
    parts.append(f"  First:  {first_t}  {first_p*100:5.1f}%    Last:  {last_t}  {last_p*100:5.1f}%")
    parts.append(f"  Min:    {timestamps[min_idx]}  {p_min*100:5.1f}%    Max:   {timestamps[max_idx]}  {p_max*100:5.1f}%")
    parts.append(f"  Mean:   {mean_p*100:5.1f}%    Net change: {net_change*100:+.1f}pp over {n} points")

    parts.append("")
    parts.append("VOLATILITY PROFILE:")
    parts.append(f"  Daily vol (full sample): {daily_vol*100:.2f}pp")
    parts.append(f"  Rolling 10d vol:  mean={vol_mean:.2f}pp  current={vol_current:.2f}pp  peak={vol_max:.2f}pp ({vol_max_date})")
    if vol_current > vol_mean * 1.5 and vol_mean > 0:
        parts.append(f"  ** ELEVATED VOLATILITY: current vol is {vol_current/vol_mean:.1f}x the average **")
    elif vol_mean > 0 and vol_current < vol_mean * 0.5:
        parts.append(f"  ** SUPPRESSED VOLATILITY: current vol is {vol_current/vol_mean:.1f}x the average **")

    if shocks:
        s5 = [s for s in shocks if s["sigma"] >= 5.0]
        s3 = [s for s in shocks if 3.0 <= s["sigma"] < 5.0]
        parts.append("")
        parts.append(f"SHOCKS DETECTED: {len(s5)} events >= 5-sigma, {len(s3)} events >= 3-sigma")
        parts.append(f"  (baseline daily vol: {daily_vol*100:.2f}pp)")
        for s in shocks[:15]:
            tier = "5-SIGMA+" if s["sigma"] >= 5.0 else "3-SIGMA+"
            parts.append(
                f"  [{tier}] {s['date']}: {s['change_pp']:+.1f}pp "
                f"({s['price_before']*100:.0f}% -> {s['price_after']*100:.0f}%) "
                f"z_full={s['z_full']:+.1f} z_trail={s['z_trail']:+.1f} "
                f"({s['sigma']:.1f}x)"
            )
    else:
        parts.append("")
        parts.append(f"SHOCKS: none detected (daily vol: {daily_vol*100:.2f}pp, no moves >= 3-sigma)")

    if regimes:
        parts.append("")
        parts.append(f"REGIME SHIFTS ({len(regimes)}):")
        for r in regimes:
            parts.append(
                f"  {r['direction']} {r['start_date']} to {r['end_date']}: "
                f"{r['shift_pp']:+.1f}pp "
                f"(level {r['pre_level']*100:.0f}% -> {r['post_level']*100:.0f}%)"
            )

    daily_moves = []
    for i in range(1, len(daily_prices)):
        delta = daily_prices[i] - daily_prices[i - 1]
        if abs(delta) >= 0.01:
            daily_moves.append((daily_dates[i], daily_prices[i - 1], daily_prices[i], delta))
    daily_moves.sort(key=lambda x: abs(x[3]), reverse=True)

    if daily_moves:
        parts.append("")
        parts.append(f"BIGGEST DAILY MOVES (top {min(10, len(daily_moves))}):")
        for d, prev, curr, delta in daily_moves[:10]:
            sigma_tag = ""
            for s in shocks:
                if s["date"] == d:
                    sigma_tag = f"  [{s['sigma']:.1f}x]"
                    break
            parts.append(f"  {d}: {delta*100:+5.1f}pp  ({prev*100:.0f}% -> {curr*100:.0f}%){sigma_tag}")

    return '\n'.join(parts)


def render_multi_market_time_series(histories, max_markets=None, granularity="daily"):
    """Render raw time series for multiple markets from a histories dict."""
    blocks = []
    items = list(histories.items())
    if max_markets:
        items = items[:max_markets]
    for mid, hist in items:
        blocks.append(render_market_time_series(hist, granularity=granularity))
    sep = "\n\n" + "=" * 80 + "\n\n"
    return sep.join(blocks)


def _cmd_time_series(source=None, market_id=None, days_back=90, granularity="hourly",
                     histories_file=None, query=None):
    """Fetch a market time series and output raw data with analytics.
    Default granularity is hourly for live fetches, daily for cached data."""

    if histories_file:
        path = histories_file
        if not os.path.isabs(path):
            path = os.path.join(DATA_DIR, path)
        if not os.path.exists(path):
            print(f"  File not found: {path}")
            return
        with open(path) as f:
            histories = json.load(f)

        if market_id and market_id in histories:
            print(render_market_time_series(histories[market_id], granularity="daily"))
            return

        if query:
            q = query.lower()
            matches = {k: v for k, v in histories.items()
                       if q in v.get("title", "").lower() or q in v.get("event_title", "").lower()}
            if not matches:
                print(f"  No markets matching '{query}' in {path}")
                return
            print(f"  Found {len(matches)} matching markets:\n")
            print(render_multi_market_time_series(matches, max_markets=10))
            return

        print(f"  {len(histories)} markets in file. Rendering all:\n")
        print(render_multi_market_time_series(histories, max_markets=20))
        return

    if not source or not market_id:
        _latest = _find_latest_file("histories_")
        if _latest:
            print(f"  Using cached histories: {_latest}")
            with open(os.path.join(DATA_DIR, _latest)) as f:
                histories = json.load(f)
            if query:
                q = query.lower()
                histories = {k: v for k, v in histories.items()
                             if q in v.get("title", "").lower() or q in v.get("event_title", "").lower()}
                if not histories:
                    print(f"  No markets matching '{query}'")
                    return
            print(f"  Rendering {min(20, len(histories))} markets:\n")
            print(render_multi_market_time_series(histories, max_markets=20))
        else:
            print("  No source/market-id provided and no cached histories found.")
            print("  Run 'full-pull' first or provide --source and --market-id.")
        return

    period = 60 if granularity == "hourly" else 1440
    fidelity = 60 if granularity == "hourly" else 1440

    print(f"\n=== Time Series: {source} / {market_id} ({days_back}d, {granularity}) ===\n")
    if source == "kalshi":
        candles = kalshi_get_candlesticks(market_id, period_minutes=period, days_back=days_back)
        if not candles:
            print("  No data returned.")
            return
        hist = {
            "source": "kalshi", "market_id": market_id,
            "title": market_id, "event_title": "",
            "series": [
                {"timestamp": _ts_to_iso(c.get("end_period_ts") or c.get("open_ts")),
                 "yes_price": c.get("yes_price") or c.get("close")}
                for c in candles
            ],
        }
    elif source == "polymarket":
        history = poly_get_price_history(market_id, fidelity=fidelity)
        if not history:
            print("  No price history returned.")
            return
        hist = {
            "source": "polymarket", "market_id": market_id,
            "title": market_id, "event_title": "",
            "series": [
                {"timestamp": _ts_to_iso(h.get("t")), "yes_price": h.get("p")}
                for h in history
            ],
        }
    else:
        print(f"  Unknown source: {source}")
        return

    output = render_market_time_series(hist, granularity=granularity)
    print(output)

    out_file = os.path.join(DATA_DIR, f"time_series_{market_id[:40]}_{time.strftime('%Y%m%d_%H%M%S')}.txt")
    _ensure_data_dir()
    with open(out_file, "w") as f:
        f.write(output)
    print(f"\n  Saved to {out_file}")


def _find_latest_file(prefix):
    """Find the most recently modified file in DATA_DIR matching prefix."""
    _ensure_data_dir()
    candidates = [f for f in os.listdir(DATA_DIR) if f.startswith(prefix) and f.endswith(".json")]
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0]


# ── Non-interactive CLI ───────────────────────────────────────────────────────

def build_argparse():
    parser = argparse.ArgumentParser(
        description="Prediction Markets State-of-the-World Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # full-pull
    p_full = sub.add_parser("full-pull", help="Full scrape: events + price history + state-of-world")
    p_full.add_argument("--days-back", type=int, default=90, help="Days of price history (default: 90)")
    p_full.add_argument("--max-histories", type=int, default=50, help="Max markets to fetch history for (default: 50)")
    p_full.add_argument("--min-volume", type=int, default=5000, help="Min volume filter for Polymarket (default: 5000)")
    p_full.add_argument("--format", choices=["json", "csv"], default="json")

    # snapshot
    p_snap = sub.add_parser("snapshot", help="Quick snapshot of current market probabilities (no history)")
    p_snap.add_argument("--min-volume", type=int, default=5000)
    p_snap.add_argument("--format", choices=["json", "csv"], default="json")

    # kalshi-events
    p_ke = sub.add_parser("kalshi-events", help="List all Kalshi events")
    p_ke.add_argument("--status", default="open", choices=["open", "closed", "settled", "all"])
    p_ke.add_argument("--format", choices=["json", "csv"], default="json")

    # kalshi-series
    sub.add_parser("kalshi-series", help="List all Kalshi series by category")

    # polymarket-events
    p_pe = sub.add_parser("polymarket-events", help="List all Polymarket events")
    p_pe.add_argument("--min-volume", type=int, default=5000)
    p_pe.add_argument("--format", choices=["json", "csv"], default="json")

    # state-of-world (from cached data)
    p_sow = sub.add_parser("state-of-world", help="Generate state-of-world from cached scrape data")
    p_sow.add_argument("--snapshot-file", help="Path to snapshot JSON")
    p_sow.add_argument("--histories-file", help="Path to histories JSON")

    # price-history
    p_ph = sub.add_parser("price-history", help="Get price history for a specific market")
    p_ph.add_argument("--source", required=True, choices=["kalshi", "polymarket"])
    p_ph.add_argument("--market-id", required=True, help="Market ticker (Kalshi) or token ID (Polymarket)")
    p_ph.add_argument("--days-back", type=int, default=90)

    # search
    p_search = sub.add_parser("search", help="Search markets by keyword")
    p_search.add_argument("--query", required=True, help="Search query")
    p_search.add_argument("--source", choices=["kalshi", "polymarket", "both"], default="both")

    # timeline
    p_tl = sub.add_parser("timeline", help="Build event timeline from cached history data")
    p_tl.add_argument("--histories-file", help="Path to histories JSON")

    # autopilot
    p_ap = sub.add_parser("autopilot", help="Volume-driven state-of-world with change detection + time series")
    p_ap.add_argument("--min-volume", type=int, default=5000, help="Min volume for Polymarket events (default: 5000)")
    p_ap.add_argument("--top-n", type=int, default=75, help="Top N events to include in briefing (default: 75)")
    p_ap.add_argument("--max-histories", type=int, default=60, help="Max events to fetch history for (default: 60)")
    p_ap.add_argument("--days-back", type=int, default=90, help="Days of history (default: 90)")
    p_ap.add_argument("--focus", choices=list(FOCUS_PRESETS.keys()), default="all",
                       help="Focus preset: " + ", ".join(f"{k}={v['description']}" for k, v in FOCUS_PRESETS.items()))
    p_ap.add_argument("--format", choices=["json", "csv"], default="json")

    # render
    p_render = sub.add_parser("render", help="Render latest briefing JSON to markdown for AI consumption")
    p_render.add_argument("--briefing-file", help="Path to briefing JSON (default: latest)")
    p_render.add_argument("--focus", choices=list(FOCUS_PRESETS.keys()), default="all",
                           help="Focus preset filter")

    # time-series
    p_ts = sub.add_parser("time-series", help="Fetch raw time series data with analytics (hourly or daily)")
    p_ts.add_argument("--source", choices=["kalshi", "polymarket"], help="Market source")
    p_ts.add_argument("--market-id", help="Market ticker (Kalshi) or token ID (Polymarket)")
    p_ts.add_argument("--days-back", type=int, default=90, help="Days of history (default: 90)")
    p_ts.add_argument("--granularity", choices=["hourly", "daily"], default="hourly",
                       help="Time series resolution (default: hourly for live fetch)")
    p_ts.add_argument("--histories-file", help="Path to cached histories JSON")
    p_ts.add_argument("--query", help="Search title filter when using cached histories")

    return parser


def run_noninteractive(args):
    cmd = args.command

    if cmd == "full-pull":
        _cmd_full_pull(args.days_back, args.max_histories, args.min_volume, args.format)
    elif cmd == "snapshot":
        _cmd_snapshot(args.min_volume, args.format)
    elif cmd == "kalshi-events":
        _cmd_kalshi_events(args.status, args.format)
    elif cmd == "kalshi-series":
        _cmd_kalshi_series()
    elif cmd == "polymarket-events":
        _cmd_polymarket_events(args.min_volume, args.format)
    elif cmd == "state-of-world":
        _cmd_state_of_world(args.snapshot_file, args.histories_file)
    elif cmd == "price-history":
        _cmd_price_history(args.source, args.market_id, args.days_back)
    elif cmd == "search":
        _cmd_search(args.query, args.source)
    elif cmd == "timeline":
        _cmd_timeline(args.histories_file)
    elif cmd == "autopilot":
        _cmd_autopilot(args.min_volume, args.top_n, args.format,
                       focus=args.focus, max_histories=args.max_histories,
                       days_back=args.days_back)
    elif cmd == "render":
        _cmd_render_briefing(args.briefing_file, focus=args.focus)
    elif cmd == "time-series":
        _cmd_time_series(source=args.source, market_id=args.market_id,
                         days_back=args.days_back, granularity=args.granularity,
                         histories_file=args.histories_file, query=args.query)


# ── Command Implementations ───────────────────────────────────────────────────

def _cmd_full_pull(days_back=90, max_histories=50, min_volume=5000, fmt="json"):
    print("\n=== Full Pull: Prediction Markets State-of-the-World ===\n")
    ts = time.strftime("%Y%m%d_%H%M%S")

    print("[1/5] Fetching Kalshi events...")
    kalshi_events = kalshi_get_all_events(status="open")
    print(f"  Total Kalshi events: {len(kalshi_events)}")

    print("\n[2/5] Fetching Polymarket events...")
    poly_events = poly_get_all_events(active=True, min_volume=min_volume)
    print(f"  Total Polymarket events: {len(poly_events)}")

    print("\n[3/5] Building unified macro snapshot...")
    records = build_unified_market_snapshot(kalshi_events, poly_events)
    print(f"  Macro-relevant markets: {len(records)}")
    snap_file = f"snapshot_{ts}.json"
    _save_json(records, snap_file)

    print(f"\n[4/5] Fetching price histories (top {max_histories} markets, {days_back} days)...")
    histories = fetch_price_histories(records, max_markets=max_histories, days_back=days_back)
    print(f"  Markets with history: {len(histories)}")
    hist_file = f"histories_{ts}.json"
    _save_json(histories, hist_file)

    print("\n[5/5] Building state-of-the-world and timeline...")
    state = build_state_of_world(records, histories)
    _save_json(state, f"state_of_world_{ts}.json")

    timeline = build_timeline(histories)
    _save_json(timeline, f"timeline_{ts}.json")

    if fmt == "csv":
        _save_csv(records, f"snapshot_{ts}.csv")

    print(f"\n  Done. {len(records)} markets tracked, {len(histories)} with history, {len(timeline)} timeline days.")
    return state, timeline


def _cmd_snapshot(min_volume=5000, fmt="json"):
    print("\n=== Quick Snapshot: Current Market Probabilities ===\n")
    ts = time.strftime("%Y%m%d_%H%M%S")

    print("[1/3] Fetching Kalshi events...")
    kalshi_events = kalshi_get_all_events(status="open")

    print("[2/3] Fetching Polymarket events...")
    poly_events = poly_get_all_events(active=True, min_volume=min_volume)

    print("[3/3] Building snapshot...")
    records = build_unified_market_snapshot(kalshi_events, poly_events)

    _save_json(records, f"snapshot_{ts}.json")
    if fmt == "csv":
        _save_csv(records, f"snapshot_{ts}.csv")

    print(f"\n  {len(records)} macro-relevant markets captured.")
    _print_snapshot_summary(records)


def _cmd_kalshi_events(status="open", fmt="json"):
    print(f"\n=== Kalshi Events (status={status}) ===\n")
    events = kalshi_get_all_events(status=status)
    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_json(events, f"kalshi_events_{ts}.json")
    print(f"\n  Total: {len(events)} events")
    for e in events[:20]:
        title = e.get("title", "?")
        cat = e.get("category", "?")
        print(f"  [{cat}] {title}")


def _cmd_kalshi_series():
    print("\n=== Kalshi Series by Category ===\n")
    series = kalshi_get_series_list()
    for s in series:
        cat = s.get("_category", "?")
        ticker = s.get("ticker", "?")
        title = s.get("title", "?")
        freq = s.get("frequency", "")
        print(f"  [{cat}] {ticker}: {title} ({freq})")
    print(f"\n  Total: {len(series)} series")


def _cmd_polymarket_events(min_volume=5000, fmt="json"):
    print(f"\n=== Polymarket Events (min_volume={min_volume}) ===\n")
    events = poly_get_all_events(active=True, min_volume=min_volume)
    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_json(events, f"polymarket_events_{ts}.json")
    print(f"\n  Total: {len(events)} events")
    for e in events[:20]:
        title = e.get("title", "?")
        tags = ", ".join(e.get("tags", []))
        print(f"  [{tags}] {title}")


def _cmd_state_of_world(snapshot_file=None, histories_file=None):
    snap_path = snapshot_file
    hist_path = histories_file
    if not snap_path or not hist_path:
        _ensure_data_dir()
        files = sorted(os.listdir(DATA_DIR), reverse=True)
        if not snap_path:
            snap_candidates = [f for f in files if f.startswith("snapshot_") and f.endswith(".json")]
            if snap_candidates:
                snap_path = os.path.join(DATA_DIR, snap_candidates[0])
        if not hist_path:
            hist_candidates = [f for f in files if f.startswith("histories_") and f.endswith(".json")]
            if hist_candidates:
                hist_path = os.path.join(DATA_DIR, hist_candidates[0])

    if not snap_path or not hist_path:
        print("No cached data found. Run 'full-pull' first.")
        return

    print(f"\nLoading snapshot: {snap_path}")
    with open(snap_path) as f:
        records = json.load(f)
    print(f"Loading histories: {hist_path}")
    with open(hist_path) as f:
        histories = json.load(f)

    state = build_state_of_world(records, histories)
    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_json(state, f"state_of_world_{ts}.json")
    _print_state_summary(state)


def _cmd_price_history(source, market_id, days_back=90):
    print(f"\n=== Price History: {source} / {market_id} ({days_back}d) ===\n")
    hist = None
    if source == "kalshi":
        candles = kalshi_get_candlesticks(market_id, days_back=days_back)
        for c in candles[-30:]:
            ts_str = _ts_to_iso(c.get("end_period_ts") or c.get("open_ts"))
            price = c.get("yes_price") or c.get("close")
            vol = c.get("volume", 0)
            print(f"  {ts_str[:10]}  price={price}  vol={vol}")
        if candles:
            hist = {
                "source": "kalshi", "market_id": market_id,
                "title": market_id, "event_title": "",
                "series": [
                    {"timestamp": _ts_to_iso(c.get("end_period_ts") or c.get("open_ts")),
                     "yes_price": c.get("yes_price") or c.get("close")}
                    for c in candles
                ],
            }
    elif source == "polymarket":
        history = poly_get_price_history(market_id)
        for h in history[-30:]:
            ts_str = _ts_to_iso(h.get("t"))
            print(f"  {ts_str[:10]}  price={h.get('p')}")
        if history:
            hist = {
                "source": "polymarket", "market_id": market_id,
                "title": market_id, "event_title": "",
                "series": [
                    {"timestamp": _ts_to_iso(h.get("t")), "yes_price": h.get("p")}
                    for h in history
                ],
            }
    if hist:
        print("\n" + render_market_time_series(hist, granularity="daily"))


def _cmd_search(query, source="both"):
    print(f"\n=== Search: '{query}' (source={source}) ===\n")
    results = []

    if source in ("kalshi", "both"):
        print("  Searching Kalshi...")
        events = kalshi_get_all_events(status="open")
        for e in events:
            if query.lower() in (e.get("title", "") + " " + e.get("subtitle", "")).lower():
                markets = e.get("markets", [])
                for m in markets:
                    rec = kalshi_extract_market_record(m, e)
                    results.append(rec)
                if not markets:
                    results.append({
                        "source": "kalshi",
                        "title": e.get("title", ""),
                        "yes_price": None,
                        "volume": 0,
                    })

    if source in ("polymarket", "both"):
        print("  Searching Polymarket...")
        try:
            search_results = poly_gamma_get("public-search", {"query": query, "limit": 50})
            events = search_results if isinstance(search_results, list) else search_results.get("events", [])
            for e in events:
                for m in e.get("markets", []):
                    rec = poly_extract_market_record(m, e)
                    results.append(rec)
        except Exception as e:
            print(f"  Polymarket search error: {e}")

    results.sort(key=lambda r: _safe_volume(r.get("volume")), reverse=True)
    print(f"\n  Found {len(results)} markets:")
    for r in results[:30]:
        prob = f"{r.get('yes_price', '?')}" if r.get("yes_price") is not None else "?"
        vol = r.get("volume", 0)
        print(f"  [{r['source']:12s}] prob={prob:>6s}  vol={vol:>10}  {r['title'][:80]}")


def _cmd_timeline(histories_file=None):
    hist_path = histories_file
    if not hist_path:
        _ensure_data_dir()
        files = sorted(os.listdir(DATA_DIR), reverse=True)
        hist_candidates = [f for f in files if f.startswith("histories_") and f.endswith(".json")]
        if hist_candidates:
            hist_path = os.path.join(DATA_DIR, hist_candidates[0])
    if not hist_path:
        print("No cached history data found. Run 'full-pull' first.")
        return

    print(f"\nLoading histories: {hist_path}")
    with open(hist_path) as f:
        histories = json.load(f)

    timeline = build_timeline(histories)
    ts = time.strftime("%Y%m%d_%H%M%S")
    _save_json(timeline, f"timeline_{ts}.json")

    print(f"\n  Timeline: {len(timeline)} days with significant moves\n")
    for day in timeline[-14:]:
        moves = day.get("significant_moves", 0)
        date = day.get("date", "?")
        top = day.get("markets", [])[:3]
        print(f"  {date}  ({moves} moves)")
        for m in top:
            chg = m.get("change")
            chg_str = f"{chg:+.2%}" if chg is not None else "?"
            print(f"    {chg_str:>8s}  {m['market'][:70]}")


# ── Autopilot: Volume-Driven Event Aggregation & Change Detection ─────────────

BRIEFING_DIR = os.path.join(SCRIPT_DIR, "briefings")
LATEST_LINK = os.path.join(DATA_DIR, "_latest_event_snapshot.json")


def _ensure_briefing_dir():
    os.makedirs(BRIEFING_DIR, exist_ok=True)


def aggregate_to_events(records):
    """Aggregate individual markets up to the event level.
    This is the core transformation: instead of 19K individual markets,
    produce ~2K events ranked by total volume."""
    events = {}
    for rec in records:
        eid = rec.get("event_id") or rec.get("market_id")
        source = rec["source"]
        key = f"{source}::{eid}"

        if key not in events:
            events[key] = {
                "event_key": key,
                "event_id": eid,
                "source": source,
                "event_title": rec.get("event_title") or rec.get("title", ""),
                "category": rec.get("category", ""),
                "total_volume": 0,
                "market_count": 0,
                "markets": [],
                "earliest_close": None,
            }

        evt = events[key]
        vol = _safe_volume(rec.get("volume"))
        evt["total_volume"] += vol
        evt["market_count"] += 1

        price = None
        try:
            price = float(rec["yes_price"]) if rec.get("yes_price") is not None else None
        except (ValueError, TypeError):
            pass

        evt["markets"].append({
            "market_id": rec["market_id"],
            "title": rec.get("title", ""),
            "yes_price": price,
            "volume": vol,
            "close_time": rec.get("close_time", ""),
            "status": rec.get("status", ""),
            "clob_token_ids": rec.get("clob_token_ids", []),
        })

        ct = rec.get("close_time", "")
        if ct and (evt["earliest_close"] is None or ct < evt["earliest_close"]):
            evt["earliest_close"] = ct

    result = list(events.values())

    for evt in result:
        evt["markets"].sort(key=lambda m: m["volume"], reverse=True)
        top = evt["markets"][0] if evt["markets"] else {}
        evt["top_market_title"] = top.get("title", "")
        evt["top_market_price"] = top.get("yes_price")
        evt["top_market_volume"] = top.get("volume", 0)

        priced = [(m["title"], m["yes_price"], m["volume"])
                  for m in evt["markets"]
                  if m["yes_price"] is not None and m["yes_price"] > 0]
        if priced:
            leading = max(priced, key=lambda x: x[1])
            evt["leading_outcome"] = leading[0]
            evt["leading_probability"] = leading[1]
        else:
            evt["leading_outcome"] = evt["top_market_title"]
            evt["leading_probability"] = None

    result.sort(key=lambda e: e["total_volume"], reverse=True)
    return result


def load_previous_event_snapshot():
    """Load the most recent event-level snapshot for diffing."""
    if os.path.exists(LATEST_LINK):
        try:
            with open(LATEST_LINK) as f:
                return json.load(f)
        except Exception:
            pass

    _ensure_data_dir()
    files = sorted(
        [f for f in os.listdir(DATA_DIR)
         if f.startswith("event_snapshot_") and f.endswith(".json")],
        reverse=True,
    )
    if files:
        try:
            with open(os.path.join(DATA_DIR, files[0])) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def diff_event_snapshots(current_events, previous_snapshot):
    """Compare current event aggregation to previous snapshot.
    Returns events annotated with deltas and a ranked list of movers by salience."""
    if not previous_snapshot:
        return current_events, []

    prev_lookup = {}
    prev_events = previous_snapshot.get("events", [])
    for evt in prev_events:
        prev_lookup[evt["event_key"]] = evt

    movers = []
    for evt in current_events:
        prev = prev_lookup.get(evt["event_key"])
        if not prev:
            evt["is_new"] = True
            evt["delta_leading_prob"] = None
            evt["delta_volume"] = evt["total_volume"]
            if evt["total_volume"] > 100_000:
                movers.append(evt)
            continue

        evt["is_new"] = False
        curr_prob = evt.get("leading_probability")
        prev_prob = prev.get("leading_probability")
        if curr_prob is not None and prev_prob is not None:
            evt["delta_leading_prob"] = round(curr_prob - prev_prob, 4)
        else:
            evt["delta_leading_prob"] = None

        evt["delta_volume"] = evt["total_volume"] - prev.get("total_volume", 0)

        prev_market_prices = {}
        for m in prev.get("markets", []):
            prev_market_prices[m["market_id"]] = m.get("yes_price")

        max_abs_delta = 0
        for m in evt["markets"]:
            pp = prev_market_prices.get(m["market_id"])
            cp = m.get("yes_price")
            if pp is not None and cp is not None:
                delta = abs(cp - pp)
                m["delta_price"] = round(cp - pp, 4)
                max_abs_delta = max(max_abs_delta, delta)
            else:
                m["delta_price"] = None

        evt["max_abs_market_delta"] = max_abs_delta
        evt["salience"] = evt["total_volume"] * max_abs_delta

        if max_abs_delta >= 0.01 and evt["total_volume"] > 50_000:
            movers.append(evt)

    movers.sort(key=lambda e: e.get("salience", 0), reverse=True)
    return current_events, movers


def build_volume_briefing(events, movers, previous_ts=None):
    """Produce a deterministic, volume-ranked briefing.
    Top N events by volume IS the state of the world.
    Movers ranked by salience IS what changed."""
    now = datetime.now(tz=timezone.utc)

    top_n = 100
    vol_threshold = 100_000

    top_events = [e for e in events if e["total_volume"] >= vol_threshold][:top_n]

    total_vol = sum(e["total_volume"] for e in top_events)
    total_mkts = sum(e["market_count"] for e in top_events)

    briefing = {
        "generated_at": now.isoformat(),
        "previous_snapshot_at": previous_ts,
        "method": "volume-ranked event aggregation, no keyword heuristics",
        "stats": {
            "total_events_in_universe": len(events),
            "events_above_volume_threshold": len(top_events),
            "total_markets_in_top_events": total_mkts,
            "total_volume_in_top_events": total_vol,
            "volume_threshold_usd": vol_threshold,
        },
        "what_the_world_is_pricing": [],
        "what_changed": [],
    }

    for rank, evt in enumerate(top_events, 1):
        entry = {
            "rank": rank,
            "event_key": evt["event_key"],
            "event_id": evt["event_id"],
            "event": evt["event_title"],
            "source": evt["source"],
            "total_volume_usd": round(evt["total_volume"]),
            "volume_share_pct": round(evt["total_volume"] / total_vol * 100, 2) if total_vol > 0 else 0,
            "market_count": evt["market_count"],
            "leading_outcome": evt["leading_outcome"],
            "leading_probability": evt["leading_probability"],
            "earliest_close": evt["earliest_close"],
        }
        if evt.get("delta_leading_prob") is not None:
            entry["delta_leading_prob"] = evt["delta_leading_prob"]
        if evt.get("is_new"):
            entry["is_new"] = True

        top_mkts = []
        for m in evt["markets"][:5]:
            me = {
                "title": m["title"],
                "probability": m["yes_price"],
                "volume": round(m["volume"]),
            }
            if m.get("delta_price") is not None:
                me["delta"] = m["delta_price"]
            top_mkts.append(me)
        entry["top_markets"] = top_mkts

        briefing["what_the_world_is_pricing"].append(entry)

    for evt in movers[:50]:
        mover_entry = {
            "event": evt["event_title"],
            "source": evt["source"],
            "total_volume_usd": round(evt["total_volume"]),
            "salience_score": round(evt.get("salience", 0)),
            "max_market_delta": evt.get("max_abs_market_delta", 0),
            "is_new": evt.get("is_new", False),
        }
        moved_markets = []
        for m in evt["markets"]:
            dp = m.get("delta_price")
            if dp is not None and abs(dp) >= 0.01:
                moved_markets.append({
                    "title": m["title"],
                    "probability": m["yes_price"],
                    "delta": dp,
                    "volume": round(m["volume"]),
                })
        moved_markets.sort(key=lambda x: abs(x.get("delta", 0)), reverse=True)
        mover_entry["moved_markets"] = moved_markets[:10]
        briefing["what_changed"].append(mover_entry)

    return briefing


def save_event_snapshot(events):
    """Save event-level snapshot and update the _latest pointer."""
    _ensure_data_dir()
    ts = time.strftime("%Y%m%d_%H%M%S")
    snapshot = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "events": [
            {
                "event_key": e["event_key"],
                "event_id": e["event_id"],
                "source": e["source"],
                "event_title": e["event_title"],
                "category": e["category"],
                "total_volume": e["total_volume"],
                "market_count": e["market_count"],
                "leading_outcome": e["leading_outcome"],
                "leading_probability": e["leading_probability"],
                "top_market_title": e["top_market_title"],
                "top_market_price": e["top_market_price"],
                "earliest_close": e["earliest_close"],
                "markets": [
                    {
                        "market_id": m["market_id"],
                        "title": m["title"],
                        "yes_price": m["yes_price"],
                        "volume": m["volume"],
                    }
                    for m in e["markets"]
                ],
            }
            for e in events
            if e["total_volume"] > 0
        ],
    }
    fname = f"event_snapshot_{ts}.json"
    path = _save_json(snapshot, fname)

    with open(LATEST_LINK, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    return snapshot


FOCUS_PRESETS = {
    "all":       {"description": "Full state of the world", "topics": None},
    "iran":      {"description": "Iran / Middle East conflict", "topics": ["Iran / Middle East Conflict"]},
    "fed":       {"description": "Federal Reserve / monetary policy", "topics": ["Federal Reserve / Monetary Policy"]},
    "russia":    {"description": "Russia / Ukraine conflict", "topics": ["Russia / Ukraine"]},
    "china":     {"description": "China / Taiwan", "topics": ["China / Taiwan"]},
    "israel":    {"description": "Israel / Gaza / Lebanon", "topics": ["Israel / Gaza / Lebanon"]},
    "elections": {"description": "Elections worldwide", "topics": ["US Politics / Elections"]},
    "trump":     {"description": "Trump administration policy", "topics": ["Trump Administration / Policy"]},
    "crypto":    {"description": "Crypto / digital assets", "topics": ["Crypto / Digital Assets"]},
    "energy":    {"description": "Energy / commodities", "topics": ["Energy / Commodities"]},
    "markets":   {"description": "Financial markets", "topics": ["Financial Markets"]},
    "movers":    {"description": "Biggest movers only (what changed)", "topics": None, "movers_only": True},
    "macro":     {"description": "Macro-only: Fed, inflation, trade, energy, markets",
                  "topics": ["Federal Reserve / Monetary Policy", "Inflation / Economic Data",
                             "Trade / Tariffs", "Energy / Commodities", "Financial Markets"]},
}


def fetch_event_histories(agg_events, max_events=60, days_back=90):
    """Fetch time series for the leading market in each top event.
    Returns {event_key: {weekly_series, daily_series, biggest_moves}}."""
    event_histories = {}
    count = 0

    for evt in agg_events:
        if count >= max_events:
            break
        if evt["total_volume"] < 100_000:
            continue

        top_mkt = evt["markets"][0] if evt["markets"] else None
        if not top_mkt:
            continue

        mid = top_mkt["market_id"]
        source = evt["source"]
        title = top_mkt["title"]

        print(f"  [{count+1}/{max_events}] {title[:65]}...")

        raw_series = []
        if source == "kalshi":
            candles = kalshi_get_candlesticks(mid, period_minutes=1440, days_back=days_back)
            for c in candles:
                ts_val = c.get("end_period_ts") or c.get("open_ts")
                price = c.get("yes_price") or c.get("close")
                if ts_val and price is not None:
                    try:
                        raw_series.append((_ts_to_iso(ts_val)[:10], float(price)))
                    except (ValueError, TypeError):
                        pass
        elif source == "polymarket":
            token_ids = top_mkt.get("clob_token_ids", [])
            if token_ids:
                history = poly_get_price_history(token_ids[0], fidelity=1440)
                for h in history:
                    ts_val = h.get("t")
                    price = h.get("p")
                    if ts_val and price is not None:
                        try:
                            raw_series.append((_ts_to_iso(ts_val)[:10], float(price)))
                        except (ValueError, TypeError):
                            pass

        if not raw_series:
            _sleep_rate_limit(source)
            continue

        raw_series.sort(key=lambda x: x[0])
        seen_dates = set()
        daily = []
        for date, price in raw_series:
            if date not in seen_dates:
                seen_dates.add(date)
                daily.append((date, price))

        weekly = _downsample_weekly(daily)

        biggest_moves = _find_biggest_moves(daily, top_n=5)

        event_histories[evt["event_key"]] = {
            "market_id": mid,
            "market_title": title,
            "daily": daily,
            "weekly": weekly,
            "biggest_moves": biggest_moves,
            "first_date": daily[0][0] if daily else None,
            "last_date": daily[-1][0] if daily else None,
            "first_price": daily[0][1] if daily else None,
            "last_price": daily[-1][1] if daily else None,
            "total_change": round(daily[-1][1] - daily[0][1], 4) if len(daily) >= 2 else None,
        }
        count += 1
        _sleep_rate_limit(source)

    return event_histories


def _downsample_weekly(daily):
    """Take daily (date, price) and return weekly samples (one per week)."""
    if not daily:
        return []
    weekly = [daily[0]]
    for date, price in daily:
        last_date = weekly[-1][0]
        try:
            d1 = datetime.strptime(last_date, "%Y-%m-%d")
            d2 = datetime.strptime(date, "%Y-%m-%d")
            if (d2 - d1).days >= 7:
                weekly.append((date, price))
        except ValueError:
            pass
    if daily[-1][0] != weekly[-1][0]:
        weekly.append(daily[-1])
    return weekly


def _find_biggest_moves(daily, top_n=5):
    """Find the N biggest single-day probability moves."""
    moves = []
    for i in range(1, len(daily)):
        prev_date, prev_price = daily[i - 1]
        curr_date, curr_price = daily[i]
        delta = round(curr_price - prev_price, 4)
        if abs(delta) >= 0.01:
            moves.append({"date": curr_date, "from": prev_price, "to": curr_price, "delta": delta})
    moves.sort(key=lambda m: abs(m["delta"]), reverse=True)
    return moves[:top_n]


def _cmd_autopilot(min_volume=5000, top_n=75, fmt="json", focus="all", max_histories=60, days_back=90):
    """The main autopilot command. Scrapes both sources, aggregates to events,
    fetches time series, diffs against previous run, produces a volume-ranked briefing."""
    print("\n=== Autopilot: Volume-Driven State of the World ===\n")
    if focus != "all":
        preset = FOCUS_PRESETS.get(focus, {})
        print(f"  Focus: {focus} -- {preset.get('description', '')}")
    ts = time.strftime("%Y%m%d_%H%M%S")

    print("[1/6] Fetching Kalshi events...")
    kalshi_events = kalshi_get_all_events(status="open")
    print(f"  {len(kalshi_events)} Kalshi events")

    print("\n[2/6] Fetching Polymarket events...")
    poly_events = poly_get_all_events(active=True, min_volume=min_volume)
    print(f"  {len(poly_events)} Polymarket events")

    print("\n[3/6] Building market-level snapshot & aggregating to events...")
    records = build_unified_market_snapshot(kalshi_events, poly_events)
    print(f"  {len(records)} macro-relevant markets")
    agg_events = aggregate_to_events(records)
    print(f"  {len(agg_events)} unique events")
    vol_events = [e for e in agg_events if e["total_volume"] >= 100_000]
    print(f"  {len(vol_events)} events above $100K volume")

    print(f"\n[4/6] Fetching time series for top {max_histories} events ({days_back}d)...")
    event_histories = fetch_event_histories(agg_events, max_events=max_histories, days_back=days_back)
    print(f"  {len(event_histories)} events with history")

    print("\n[5/6] Diffing against previous snapshot...")
    prev_snapshot = load_previous_event_snapshot()
    prev_ts = prev_snapshot.get("generated_at") if prev_snapshot else None
    if prev_ts:
        print(f"  Previous snapshot: {prev_ts}")
    else:
        print("  No previous snapshot found (first run)")
    agg_events, movers = diff_event_snapshots(agg_events, prev_snapshot)
    print(f"  {len(movers)} events with significant moves")

    print("\n[6/6] Building briefing, rendering markdown, saving...")
    briefing = build_volume_briefing(agg_events, movers, prev_ts)
    briefing["histories"] = _serialize_histories_for_briefing(event_histories)
    _save_json(briefing, f"briefing_{ts}.json")
    _ensure_briefing_dir()
    briefing_path = os.path.join(BRIEFING_DIR, f"briefing_{ts}.json")
    with open(briefing_path, "w") as f:
        json.dump(briefing, f, indent=2, default=str)

    save_event_snapshot(agg_events)

    md = render_markdown_briefing(briefing, focus=focus)
    _ensure_briefing_dir()
    md_path = os.path.join(BRIEFING_DIR, f"state_of_world_{ts}.md")
    with open(md_path, "w") as f:
        f.write(md)
    latest_md = os.path.join(BRIEFING_DIR, "LATEST.md")
    with open(latest_md, "w") as f:
        f.write(md)
    print(f"  Full briefing: {md_path} ({len(md):,} chars)")
    print(f"  Updated: {latest_md}")

    ctx = render_context_snapshot(briefing)
    ctx_path = os.path.join(BRIEFING_DIR, "CONTEXT.md")
    with open(ctx_path, "w") as f:
        f.write(ctx)
    print(f"  Context snapshot: {ctx_path} ({len(ctx):,} chars)")

    print(f"\n  Done.")
    _print_autopilot_summary(briefing)
    return briefing


def _serialize_histories_for_briefing(event_histories):
    """Convert event_histories into a JSON-serializable dict keyed by event_key."""
    out = {}
    for ek, hist in event_histories.items():
        out[ek] = {
            "market_id": hist["market_id"],
            "market_title": hist["market_title"],
            "first_date": hist["first_date"],
            "last_date": hist["last_date"],
            "first_price": hist["first_price"],
            "last_price": hist["last_price"],
            "total_change": hist["total_change"],
            "daily": [{"date": d, "price": p} for d, p in hist["daily"]],
            "weekly": [{"date": d, "price": p} for d, p in hist["weekly"]],
            "biggest_moves": hist["biggest_moves"],
        }
    return out


def _print_autopilot_summary(briefing):
    stats = briefing["stats"]
    prev = briefing.get("previous_snapshot_at")
    print(f"\n{'='*78}")
    print(f"  STATE OF THE WORLD  ({briefing['generated_at'][:19]})")
    if prev:
        print(f"  Changes since:      {prev[:19]}")
    print(f"  Events tracked:     {stats['events_above_volume_threshold']}")
    print(f"  Total volume:       ${stats['total_volume_in_top_events']:,.0f}")
    print(f"{'='*78}")

    print(f"\n  TOP EVENTS BY VOLUME (what the world is pricing)")
    print(f"  {'#':>3}  {'Vol':>9}  {'Prob':>5}  {'Delta':>6}  Event")
    print(f"  {'---':>3}  {'---------':>9}  {'-----':>5}  {'------':>6}  {'-----'}")
    for entry in briefing["what_the_world_is_pricing"][:40]:
        r = entry["rank"]
        vol_s = _fmt_vol(entry["total_volume_usd"])
        prob = entry.get("leading_probability")
        prob_s = _fmt_prob(prob)
        delta = entry.get("delta_leading_prob")
        if delta is not None:
            try:
                delta_s = f"{float(delta):+.1%}"
            except (ValueError, TypeError):
                delta_s = ""
        elif entry.get("is_new"):
            delta_s = "  NEW"
        else:
            delta_s = ""
        title = entry["event"][:55]
        print(f"  {r:>3}  {vol_s:>9}  {prob_s:>5}  {delta_s:>6}  {title}")

    what_changed = briefing.get("what_changed", [])
    if what_changed:
        print(f"\n  WHAT CHANGED (ranked by salience = volume * |delta|)")
        print(f"  {'Salience':>10}  {'MaxDelta':>8}  Event")
        print(f"  {'----------':>10}  {'--------':>8}  {'-----'}")
        for entry in what_changed[:25]:
            sal = _fmt_vol(entry["salience_score"])
            md = entry.get("max_market_delta", 0)
            try:
                md_s = f"{float(md):+.1%}"
            except (ValueError, TypeError):
                md_s = "?"
            new_tag = " [NEW]" if entry.get("is_new") else ""
            title = entry["event"][:55]
            print(f"  {sal:>10}  {md_s:>8}  {title}{new_tag}")
            for mm in entry.get("moved_markets", [])[:3]:
                dp = mm.get("delta", 0)
                try:
                    dp_s = f"{float(dp):+.1%}"
                except (ValueError, TypeError):
                    dp_s = "?"
                ps = _fmt_prob(mm.get("probability"))
                print(f"  {'':>10}  {'':>8}    {dp_s:>6} -> {ps:>4}  {mm['title'][:50]}")
    else:
        print("\n  No significant changes detected (first run or no movers).")


# ── Markdown Briefing Renderer ─────────────────────────────────────────────────

TOPIC_CLUSTERS = [
    {
        "name": "Iran / Middle East Conflict",
        "keywords": ["iran", "tehran", "kharg", "pahlavi", "hormuz", "araghchi"],
    },
    {
        "name": "Israel / Gaza / Lebanon",
        "keywords": ["israel", "hamas", "gaza", "hezbollah", "netanyahu", "west bank", "golan"],
    },
    {
        "name": "Russia / Ukraine",
        "keywords": ["russia", "ukraine", "putin", "zelensky", "crimea", "nato", "moscow", "kyiv", "kostyantynivka"],
    },
    {
        "name": "China / Taiwan",
        "keywords": ["china", "taiwan", "xi jinping", "beijing", "chinese"],
    },
    {
        "name": "Federal Reserve / Monetary Policy",
        "keywords": ["fed ", "fed?", "fomc", "interest rate", "rate cut", "rate hike", "fed chair", "fed rate", "fed decision", "monetary"],
    },
    {
        "name": "Inflation / Economic Data",
        "keywords": ["inflation", "cpi", "ppi", "gdp", "recession", "unemployment", "jobs report", "nonfarm", "pmi", "ism ", "consumer price", "payroll"],
    },
    {
        "name": "Trade / Tariffs",
        "keywords": ["tariff", "trade war", "trade deal", "refund tariff", "import duty"],
    },
    {
        "name": "US Politics / Elections",
        "keywords": ["presidential", "election", "nominee", "nomination", "congress", "senate", "supreme court", "governor", "parliamentary"],
    },
    {
        "name": "Trump Administration / Policy",
        "keywords": ["trump", "greenland", "doge", "musk", "vance", "white house", "executive order", "attorney general", "cabinet"],
    },
    {
        "name": "Crypto / Digital Assets",
        "keywords": ["bitcoin", "crypto", "ethereum", "btc", "microstrategy", "stablecoin"],
    },
    {
        "name": "Energy / Commodities",
        "keywords": ["oil", "crude", "wti", "brent", "opec", "natural gas", "gold price", "commodity"],
    },
    {
        "name": "Financial Markets",
        "keywords": ["s&p", "nasdaq", "dow", "stock market", "vix", "treasury", "yield", "bond"],
    },
    {
        "name": "Technology / AI",
        "keywords": ["openai", "anthropic", "deepseek", "ai model", "agi", "chatgpt", "ai-generated"],
    },
]


def _cluster_events_by_topic(events):
    """Assign each event to a topic cluster based on keyword matching.
    Returns {topic_name: [events]} and a list of unclustered events."""
    clusters = {tc["name"]: [] for tc in TOPIC_CLUSTERS}
    unclustered = []

    for evt in events:
        title_lower = evt["event"].lower()
        placed = False
        for tc in TOPIC_CLUSTERS:
            if any(kw in title_lower for kw in tc["keywords"]):
                clusters[tc["name"]].append(evt)
                placed = True
                break
        if not placed:
            unclustered.append(evt)

    clusters = {k: v for k, v in clusters.items() if v}
    return clusters, unclustered


def _md_prob(p):
    if p is None:
        return "n/a"
    try:
        return f"{float(p):.0%}"
    except (ValueError, TypeError):
        return "n/a"


def _md_vol(v):
    try:
        fv = float(v)
    except (ValueError, TypeError):
        return "$0"
    if fv >= 1_000_000:
        return f"${fv/1_000_000:.1f}M"
    if fv >= 1_000:
        return f"${fv/1_000:.0f}K"
    return f"${fv:.0f}"


def _md_delta(d):
    if d is None:
        return ""
    try:
        fd = float(d)
    except (ValueError, TypeError):
        return ""
    if abs(fd) < 0.001:
        return ""
    return f"{fd:+.1%}"


def _render_daily_csv(daily):
    """Render daily series as indented CSV lines for markdown briefing.
    daily can be list of (date,price) tuples or list of {date,price} dicts."""
    if not daily:
        return []
    lines = []
    for pt in daily:
        if isinstance(pt, dict):
            d, p = pt["date"], pt["price"]
        else:
            d, p = pt[0], pt[1]
        try:
            lines.append(f"  {d},{float(p):.4f}")
        except (ValueError, TypeError):
            lines.append(f"  {d},?")
    return lines


def _render_biggest_moves(moves):
    """Render biggest moves list into compact string."""
    if not moves:
        return ""
    parts = []
    for m in moves:
        try:
            ds = f"{float(m['delta']):+.0%}"
        except (ValueError, TypeError):
            ds = "?"
        parts.append(f"{ds} on {m['date'][5:]}")
    return " | ".join(parts)


def render_context_snapshot(briefing):
    """Render a minimal context snapshot for PRISM's get_context injection.
    Just current probabilities + 1d deltas + volume. ~2-4K tokens.
    All deeper analysis (time series, distributions, biggest moves) lives
    in code execution via the full briefing JSON."""
    lines = []
    w = lines.append
    gen_at = briefing["generated_at"][:19].replace("T", " ")
    prev_at = briefing.get("previous_snapshot_at")
    stats = briefing["stats"]

    w("# Prediction Markets Snapshot")
    w(f"As of {gen_at} UTC | Kalshi + Polymarket | {stats['events_above_volume_threshold']} events | {_md_vol(stats['total_volume_in_top_events'])} total volume")
    if prev_at:
        w(f"Deltas vs. {prev_at[:19].replace('T', ' ')} UTC")
    w("")

    what_changed = briefing.get("what_changed", [])
    if what_changed:
        w("## Movers")
        for entry in what_changed[:15]:
            new_tag = " [NEW]" if entry.get("is_new") else ""
            moved = entry.get("moved_markets", [])
            top_move = moved[0] if moved else None
            if top_move:
                dp = _md_delta(top_move.get("delta"))
                prob = _md_prob(top_move.get("probability"))
                w(f"- {dp} -> {prob} | {_md_vol(entry['total_volume_usd'])} | {entry['event']}{new_tag}")
            else:
                w(f"- {_md_vol(entry['total_volume_usd'])} | {entry['event']}{new_tag}")
        w("")

    pricing = briefing["what_the_world_is_pricing"]
    clusters, unclustered = _cluster_events_by_topic(pricing)

    sorted_topics = sorted(
        clusters.items(),
        key=lambda kv: sum(e["total_volume_usd"] for e in kv[1]),
        reverse=True,
    )

    w("## Current Probabilities")
    w("")
    for topic_name, topic_events in sorted_topics:
        topic_events.sort(key=lambda e: e["total_volume_usd"], reverse=True)
        topic_vol = sum(e["total_volume_usd"] for e in topic_events)
        w(f"**{topic_name}** ({_md_vol(topic_vol)})")
        for evt in topic_events:
            prob = _md_prob(evt.get("leading_probability"))
            delta = _md_delta(evt.get("delta_leading_prob"))
            vol = _md_vol(evt["total_volume_usd"])
            title = evt["event"]
            if len(title) > 65:
                title = title[:62] + "..."
            delta_str = f" ({delta})" if delta else ""
            w(f"- {prob}{delta_str} | {vol} | {title}")
        w("")

    if unclustered:
        w(f"**Other** ({_md_vol(sum(e['total_volume_usd'] for e in unclustered))})")
        for evt in unclustered[:10]:
            prob = _md_prob(evt.get("leading_probability"))
            delta = _md_delta(evt.get("delta_leading_prob"))
            vol = _md_vol(evt["total_volume_usd"])
            title = evt["event"]
            if len(title) > 65:
                title = title[:62] + "..."
            delta_str = f" ({delta})" if delta else ""
            w(f"- {prob}{delta_str} | {vol} | {title}")
        w("")

    w("---")
    w("For time series, distributions, biggest moves, and deep analysis: use code execution against the full briefing JSON or run the scraper commands directly.")

    return "\n".join(lines)


def render_markdown_briefing(briefing, focus="all"):
    """Render the briefing JSON into a structured markdown document
    optimized for LLM consumption. Includes through-time trajectories."""
    lines = []
    w = lines.append
    preset = FOCUS_PRESETS.get(focus, FOCUS_PRESETS["all"])
    focus_topics = preset.get("topics")
    movers_only = preset.get("movers_only", False)

    histories = briefing.get("histories", {})

    gen_at = briefing["generated_at"][:19].replace("T", " ")
    prev_at = briefing.get("previous_snapshot_at")
    stats = briefing["stats"]

    w("# Prediction Markets: State of the World")
    w("")
    w(f"Generated: {gen_at} UTC")
    if prev_at:
        w(f"Changes since: {prev_at[:19].replace('T', ' ')} UTC")
    if focus != "all":
        w(f"Focus: {focus} -- {preset.get('description', '')}")
    w(f"Sources: Kalshi + Polymarket (public APIs, no auth)")
    w(f"Events tracked: {stats['events_above_volume_threshold']} (above ${stats['volume_threshold_usd']:,} volume)")
    w(f"Total volume: {_md_vol(stats['total_volume_in_top_events'])}")
    w(f"Events with time series: {len(histories)}")
    w("")
    w("**How to read this document:**")
    w("- Volume = total USD traded. Higher volume = more market attention = higher signal.")
    w("- Probability = implied YES price (0-100%). Market at 80% = crowd prices 80% chance.")
    w("- Daily series = full daily probability time series (date,price CSV) for each event.")
    w("- Biggest moves = single-day probability jumps, indicating event-driven repricing.")
    w("- Focus parameter controls which topics are included. Current: " + focus)
    w("")

    # -- What changed section
    what_changed = briefing.get("what_changed", [])
    if what_changed:
        if focus_topics:
            filtered_changed = []
            for entry in what_changed:
                evt_title = entry.get("event", "").lower()
                for tc in TOPIC_CLUSTERS:
                    if tc["name"] in focus_topics:
                        if any(kw in evt_title for kw in tc["keywords"]):
                            filtered_changed.append(entry)
                            break
            what_changed = filtered_changed if filtered_changed else what_changed[:10]

        w("---")
        w("")
        w("## What Changed Since Last Snapshot")
        w("")
        w("Ranked by salience = volume * |largest probability move|.")
        w("")
        for entry in what_changed[:25]:
            sal = _md_vol(entry["salience_score"])
            new_tag = " **[NEW]**" if entry.get("is_new") else ""
            w(f"**{entry['event']}**{new_tag}")
            w(f"- Source: {entry['source']} | Volume: {_md_vol(entry['total_volume_usd'])} | Salience: {sal}")
            moved = entry.get("moved_markets", [])
            if moved:
                for mm in moved[:5]:
                    dp = _md_delta(mm.get("delta"))
                    prob = _md_prob(mm.get("probability"))
                    vol = _md_vol(mm.get("volume", 0))
                    w(f"  - {dp} -> {prob} ({vol}) {mm['title'][:80]}")
            w("")

    if movers_only:
        return "\n".join(lines)

    # -- Topic-clustered view with time series
    w("---")
    w("")
    w("## State of the World by Topic")
    w("")

    pricing = briefing["what_the_world_is_pricing"]
    clusters, unclustered = _cluster_events_by_topic(pricing)

    sorted_topics = sorted(
        clusters.items(),
        key=lambda kv: sum(e["total_volume_usd"] for e in kv[1]),
        reverse=True,
    )

    if focus_topics:
        sorted_topics = [(name, evts) for name, evts in sorted_topics if name in focus_topics]
        unclustered = []

    for topic_name, topic_events in sorted_topics:
        topic_vol = sum(e["total_volume_usd"] for e in topic_events)
        w(f"### {topic_name}")
        w(f"Topic volume: {_md_vol(topic_vol)} | {len(topic_events)} events")
        w("")

        topic_events.sort(key=lambda e: e["total_volume_usd"], reverse=True)

        for evt in topic_events:
            _render_event_block(w, evt, histories)

    if unclustered:
        w("### Other Events")
        unc_vol = sum(e["total_volume_usd"] for e in unclustered)
        w(f"Topic volume: {_md_vol(unc_vol)} | {len(unclustered)} events")
        w("")
        for evt in unclustered[:15]:
            _render_event_block(w, evt, histories)

    # -- Flat table
    w("---")
    w("")
    w("## Volume-Ranked Event Table")
    w("")
    table_events = pricing
    if focus_topics:
        focus_set = set()
        for name, evts in clusters.items():
            if name in focus_topics:
                for e in evts:
                    focus_set.add(e["event"])
        table_events = [e for e in pricing if e["event"] in focus_set]

    w("| # | Volume | Prob | Chg | Recent 7d (daily) | Event | Closes |")
    w("|---|--------|------|-----|-------------------|-------|--------|")
    for i, entry in enumerate(table_events, 1):
        vol = _md_vol(entry["total_volume_usd"])
        prob = _md_prob(entry.get("leading_probability"))
        delta = _md_delta(entry.get("delta_leading_prob"))
        close = entry.get("earliest_close", "")[:10]
        title = entry["event"]
        if len(title) > 50:
            title = title[:47] + "..."

        ek = entry.get("event_key") or f"{entry['source']}::{entry.get('event_id', '')}"
        hist = histories.get(ek, {})
        trajectory = ""
        daily = hist.get("daily", [])
        if daily:
            tc = hist.get("total_change")
            tc_s = f"{float(tc):+.0%}" if tc is not None else ""
            recent = daily[-7:] if len(daily) > 7 else daily
            traj_parts = [f"{float(p['price']):.0%}" for p in recent]
            trajectory = "->".join(traj_parts) + (f" ({tc_s} total)" if tc_s else "")

        w(f"| {i} | {vol} | {prob} | {delta} | {trajectory} | {title} | {close} |")

    w("")
    return "\n".join(lines)


def _render_event_block(w, evt, histories):
    """Render a single event block with outcomes + daily time series CSV."""
    vol = _md_vol(evt["total_volume_usd"])
    lp = _md_prob(evt.get("leading_probability"))
    delta_lp = _md_delta(evt.get("delta_leading_prob"))
    close = evt.get("earliest_close", "")
    close_str = close[:10] if close else ""
    new_tag = " **[NEW]**" if evt.get("is_new") else ""

    lead = evt.get("leading_outcome", "")
    if lead and len(lead) > 80:
        lead = lead[:77] + "..."

    w(f"**{evt['event']}**{new_tag}")
    w(f"- Volume: {vol} | Leading: {lp}{(' ' + delta_lp) if delta_lp else ''} | Closes: {close_str}")
    if lead:
        w(f"- Most likely: {lead}")

    ek = evt.get("event_key") or f"{evt['source']}::{evt.get('event_id', '')}"
    hist = histories.get(ek, {})
    if hist:
        daily = hist.get("daily", [])
        if daily:
            tc = hist.get("total_change")
            tc_s = f", net {float(tc):+.0%}" if tc is not None else ""
            first_d = daily[0]["date"] if isinstance(daily[0], dict) else daily[0][0]
            last_d = daily[-1]["date"] if isinstance(daily[-1], dict) else daily[-1][0]
            w(f"- Daily series ({first_d} to {last_d}, {len(daily)}pts{tc_s}):")
            for line in _render_daily_csv(daily):
                w(line)
        moves = hist.get("biggest_moves", [])
        if moves:
            w(f"- Biggest moves: {_render_biggest_moves(moves)}")

    mkts = evt.get("top_markets", [])
    if len(mkts) > 1:
        w("- Outcomes:")
        for m in mkts:
            mp = _md_prob(m.get("probability"))
            md = _md_delta(m.get("delta"))
            mv = _md_vol(m.get("volume", 0))
            title = m["title"]
            if len(title) > 75:
                title = title[:72] + "..."
            w(f"  - {mp}{(' ' + md) if md else ''} ({mv}) {title}")

    w("")


def _cmd_render_briefing(briefing_file=None, focus="all"):
    """Render a briefing JSON to markdown."""
    if not briefing_file:
        _ensure_data_dir()
        files = sorted(
            [f for f in os.listdir(DATA_DIR)
             if f.startswith("briefing_") and f.endswith(".json")],
            reverse=True,
        )
        if not files:
            _ensure_briefing_dir()
            files = sorted(
                [f for f in os.listdir(BRIEFING_DIR)
                 if f.startswith("briefing_") and f.endswith(".json")],
                reverse=True,
            )
            if files:
                briefing_file = os.path.join(BRIEFING_DIR, files[0])
        else:
            briefing_file = os.path.join(DATA_DIR, files[0])

    if not briefing_file:
        print("No briefing found. Run 'autopilot' first.")
        return

    print(f"  Loading: {briefing_file}")
    with open(briefing_file) as f:
        briefing = json.load(f)

    md = render_markdown_briefing(briefing, focus=focus)

    _ensure_briefing_dir()
    ts = time.strftime("%Y%m%d_%H%M%S")
    suffix = f"_{focus}" if focus != "all" else ""
    md_path = os.path.join(BRIEFING_DIR, f"state_of_world_{ts}{suffix}.md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"  Saved: {md_path} ({len(md):,} chars)")

    latest_md = os.path.join(BRIEFING_DIR, "LATEST.md")
    with open(latest_md, "w") as f:
        f.write(md)
    print(f"  Updated: {latest_md}")

    return md_path


# ── Display Helpers ───────────────────────────────────────────────────────────

def _fmt_prob(p):
    if p is None:
        return "  ?"
    try:
        return f"{float(p):.0%}"
    except (ValueError, TypeError):
        return "  ?"


def _fmt_vol(v):
    try:
        fv = float(v)
    except (ValueError, TypeError):
        return "0"
    if fv >= 1_000_000:
        return f"{fv/1_000_000:.1f}M"
    if fv >= 1_000:
        return f"{fv/1_000:.0f}K"
    return f"{fv:.0f}"


def _print_snapshot_summary(records):
    print("\n  --- Top 30 by Volume ---")
    for r in records[:30]:
        prob_str = _fmt_prob(r.get("yes_price"))
        vol_str = _fmt_vol(r.get("volume", 0))
        print(f"  [{r['source']:12s}] {prob_str:>5s}  vol={vol_str:>8s}  {r['title'][:70]}")


def _print_state_summary(state):
    print(f"\n=== State of the World ({state['generated_at'][:10]}) ===\n")
    stats = state.get("summary_stats", {})
    print(f"  Markets tracked: {stats.get('total_markets_tracked', 0)}")
    print(f"  With history:    {stats.get('markets_with_history', 0)}")
    sources = stats.get("sources", {})
    print(f"  Kalshi:          {sources.get('kalshi', 0)}")
    print(f"  Polymarket:      {sources.get('polymarket', 0)}")

    for theme, data in state.get("themes", {}).items():
        mc = data.get("market_count", 0)
        tv = data.get("total_volume", 0)
        print(f"\n  {theme} ({mc} markets, vol={tv:,.0f})")
        for m in data.get("markets", [])[:5]:
            prob_str = _fmt_prob(m.get("probability"))
            chg7 = m.get("price_change_7d")
            try:
                chg_str = f" 7d:{float(chg7):+.1%}" if chg7 is not None else ""
            except (ValueError, TypeError):
                chg_str = ""
            print(f"    {prob_str:>5s}{chg_str:>12s}  {m['title'][:65]}")


# ── Interactive CLI ───────────────────────────────────────────────────────────

def interactive_loop():
    MENU = """
  Commands:
    1) autopilot       Volume-driven state-of-world with change detection + markdown
    2) render          Re-render latest briefing JSON to markdown
    3) full-pull       Full scrape: events + history + state-of-world + timeline
    4) snapshot        Quick snapshot of current probabilities (no history)
    5) kalshi-events   Browse Kalshi events
    6) kalshi-series   Browse Kalshi series by category
    7) poly-events     Browse Polymarket events
    8) state-of-world  Regenerate state-of-world from cached data (keyword themes)
    9) timeline        Regenerate timeline from cached data
   10) price-history   Get price history for a specific market
   11) search          Search markets by keyword
   12) time-series     Fetch raw time series data (hourly/daily) with analytics
    q) quit
"""
    while True:
        print(MENU)
        choice = input("  > ").strip().lower()

        if choice in ("q", "quit", "exit"):
            break

        elif choice in ("1", "autopilot"):
            print("  Focus presets: " + ", ".join(FOCUS_PRESETS.keys()))
            focus = input("  Focus [all]: ").strip().lower() or "all"
            if focus not in FOCUS_PRESETS:
                print(f"  Unknown focus '{focus}', using 'all'")
                focus = "all"
            max_h = _ask_int("  Max events for history", 60)
            days = _ask_int("  Days of history", 90)
            _cmd_autopilot(focus=focus, max_histories=max_h, days_back=days)

        elif choice in ("2", "render"):
            _cmd_render_briefing()

        elif choice in ("3", "full-pull"):
            days = _ask_int("  Days of history", 90)
            max_h = _ask_int("  Max markets for history", 50)
            min_v = _ask_int("  Min volume (Polymarket)", 5000)
            _cmd_full_pull(days_back=days, max_histories=max_h, min_volume=min_v)

        elif choice in ("4", "snapshot"):
            min_v = _ask_int("  Min volume (Polymarket)", 5000)
            _cmd_snapshot(min_volume=min_v)

        elif choice in ("5", "kalshi-events"):
            status = input("  Status [open/closed/settled/all] (default: open): ").strip() or "open"
            _cmd_kalshi_events(status=status)

        elif choice in ("6", "kalshi-series"):
            _cmd_kalshi_series()

        elif choice in ("7", "poly-events"):
            min_v = _ask_int("  Min volume", 5000)
            _cmd_polymarket_events(min_volume=min_v)

        elif choice in ("8", "state-of-world"):
            _cmd_state_of_world()

        elif choice in ("9", "timeline"):
            _cmd_timeline()

        elif choice in ("10", "price-history"):
            source = input("  Source [kalshi/polymarket]: ").strip().lower()
            if source not in ("kalshi", "polymarket"):
                print("  Invalid source.")
                continue
            mid = input("  Market ID / ticker: ").strip()
            days = _ask_int("  Days back", 90)
            _cmd_price_history(source, mid, days)

        elif choice in ("11", "search"):
            query = input("  Search query: ").strip()
            if not query:
                continue
            src = input("  Source [kalshi/polymarket/both] (default: both): ").strip() or "both"
            _cmd_search(query, src)

        elif choice in ("12", "time-series"):
            print("  Modes: (a) live fetch by source+id  (b) from cached histories  (c) search cached")
            mode = input("  Mode [a/b/c] (default: c): ").strip().lower() or "c"
            if mode == "a":
                source = input("  Source [kalshi/polymarket]: ").strip().lower()
                mid = input("  Market ID / ticker / token: ").strip()
                days = _ask_int("  Days back", 90)
                gran = input("  Granularity [hourly/daily] (default: hourly): ").strip().lower() or "hourly"
                if gran not in ("hourly", "daily"):
                    gran = "hourly"
                _cmd_time_series(source=source, market_id=mid, days_back=days, granularity=gran)
            elif mode == "b":
                hf = input("  Histories file (blank for latest): ").strip() or None
                _cmd_time_series(histories_file=hf or _find_latest_file("histories_"))
            else:
                query = input("  Title search query: ").strip()
                if not query:
                    print("  No query provided.")
                    continue
                hf = _find_latest_file("histories_")
                if hf:
                    _cmd_time_series(histories_file=hf, query=query)
                else:
                    print("  No cached histories found. Run full-pull first.")

        else:
            print(f"  Unknown command: {choice}")


def _ask_int(prompt, default):
    val = input(f"{prompt} (default: {default}): ").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command:
        run_noninteractive(args)
    else:
        print("\n  Prediction Markets State-of-the-World Scraper")
        print("  =============================================")
        print(f"  Kalshi:      {KALSHI_BASE}")
        print(f"  Polymarket:  {POLY_GAMMA}")
        print(f"  No API keys required - all endpoints are public.")
        print(f"  Data dir:    {DATA_DIR}")
        interactive_loop()


if __name__ == "__main__":
    main()
