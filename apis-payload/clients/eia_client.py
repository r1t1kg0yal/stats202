#!/usr/bin/env python3
"""
EIA (Energy Information Administration) -- Energy Data Client

Single-script client for the EIA API v2 (api.eia.gov/v2).
Covers petroleum inventories, natural gas storage, spot prices, refinery data,
and STEO forecasts. 16 curated series across oil, gas, and macro-energy.

Requires EIA_API_KEY env var (free at https://www.eia.gov/opendata/register.php).

Usage:
    python eia.py                                   # interactive CLI
    python eia.py petroleum                         # weekly petroleum snapshot
    python eia.py crude-stocks --weeks 104          # 2-year crude inventory history
    python eia.py natgas-storage --weeks 52         # 1-year natgas storage
    python eia.py prices                            # latest WTI, Brent, HH
    python eia.py price-history WTI_SPOT --days 90  # WTI spot last 90 days
    python eia.py refinery --weeks 52               # refinery util + inputs
    python eia.py steo                              # short-term energy outlook
    python eia.py browse petroleum/pri/spt          # browse API hierarchy
    python eia.py series                            # list curated series
    python eia.py history CRUDE_STOCKS --periods 52 # generic series history
    python eia.py wpsr                              # full WPSR latest + WoW
    python eia.py energy-snapshot                   # combined energy dashboard
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests


# --- API Configuration --------------------------------------------------------

BASE_URL = "https://api.eia.gov/v2"
API_KEY = os.environ.get("EIA_API_KEY", "")
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

MAX_ROWS = 5000

if not API_KEY:
    print("  WARNING: EIA_API_KEY not set. All API calls will fail.")
    print("  Register free at https://www.eia.gov/opendata/register.php")


# --- Curated Series Registry --------------------------------------------------

SERIES_REGISTRY = {
    # Weekly Petroleum Status Report (WPSR) -- the Wednesday report
    "CRUDE_STOCKS":       {"route": "petroleum/sum/sndw", "series": "WCESTUS1",  "name": "US Crude Oil Stocks (excl. SPR)", "unit": "thousand barrels", "freq": "weekly", "facet_key": "series"},
    "GASOLINE_STOCKS":    {"route": "petroleum/sum/sndw", "series": "WGTSTUS1",  "name": "US Motor Gasoline Stocks", "unit": "thousand barrels", "freq": "weekly", "facet_key": "series"},
    "DISTILLATE_STOCKS":  {"route": "petroleum/sum/sndw", "series": "WDISTUS1",  "name": "US Distillate Fuel Oil Stocks", "unit": "thousand barrels", "freq": "weekly", "facet_key": "series"},
    "REFINERY_INPUTS":    {"route": "petroleum/sum/sndw", "series": "WCRFPUS2",  "name": "US Refinery Crude Inputs", "unit": "thousand barrels/day", "freq": "weekly", "facet_key": "series"},
    "REFINERY_UTIL":      {"route": "petroleum/sum/sndw", "series": "WPULEUS3",  "name": "US Refinery Utilization Rate", "unit": "percent", "freq": "weekly", "facet_key": "series"},
    "CRUDE_PRODUCTION":   {"route": "petroleum/sum/sndw", "series": "WCRFPUS2",  "name": "US Crude Production (weekly)", "unit": "thousand barrels/day", "freq": "weekly", "facet_key": "series"},
    "CRUDE_IMPORTS":      {"route": "petroleum/sum/sndw", "series": "WCEIMUS2",  "name": "US Crude Oil Imports", "unit": "thousand barrels/day", "freq": "weekly", "facet_key": "series"},
    "NET_IMPORTS":        {"route": "petroleum/sum/sndw", "series": "WTTNTUS2",  "name": "US Total Net Imports", "unit": "thousand barrels/day", "freq": "weekly", "facet_key": "series"},
    # Spot prices
    "WTI_SPOT":           {"route": "petroleum/pri/spt",  "series": "RWTC",      "name": "WTI Cushing Spot Price", "unit": "$/barrel", "freq": "daily", "facet_key": "series"},
    "BRENT_SPOT":         {"route": "petroleum/pri/spt",  "series": "RBRTE",     "name": "Brent Spot Price", "unit": "$/barrel", "freq": "daily", "facet_key": "series"},
    # Natural gas
    "NATGAS_STORAGE":     {"route": "natural-gas/stor/wkly", "series": "NW2_EPG0_SWO_R48_BCF", "name": "Lower-48 Working Gas in Storage", "unit": "Bcf", "freq": "weekly", "facet_key": "series"},
    "HH_SPOT":            {"route": "natural-gas/pri/fut", "series": "RNGWHHD",  "name": "Henry Hub Natural Gas Spot", "unit": "$/MMBtu", "freq": "daily", "facet_key": "series"},
    # STEO forecasts
    "STEO_WTI":           {"route": "steo", "series": "PAPR_WORLD", "name": "STEO World Oil Price Forecast", "unit": "$/barrel", "freq": "monthly", "facet_key": "seriesId"},
    "STEO_CRUDE_PROD":    {"route": "steo", "series": "COPR_US",    "name": "STEO US Crude Production Forecast", "unit": "million barrels/day", "freq": "monthly", "facet_key": "seriesId"},
}

WPSR_SERIES = [
    "CRUDE_STOCKS", "GASOLINE_STOCKS", "DISTILLATE_STOCKS",
    "REFINERY_INPUTS", "REFINERY_UTIL", "CRUDE_PRODUCTION",
    "CRUDE_IMPORTS", "NET_IMPORTS",
]

PRICE_SERIES = ["WTI_SPOT", "BRENT_SPOT", "HH_SPOT"]

CATEGORY_ORDER = ["petroleum", "natural-gas", "steo"]
CATEGORY_NAMES = {
    "petroleum":   "PETROLEUM",
    "natural-gas": "NATURAL GAS",
    "steo":        "STEO FORECASTS",
}


# --- HTTP + Parsing -----------------------------------------------------------

def _build_data_url(route, freq, series_id, facet_key="series",
                    start=None, end=None, limit=100, offset=0):
    parts = [
        f"api_key={API_KEY}",
        f"frequency={freq}",
        "data[]=value",
        f"facets[{facet_key}][]={series_id}",
        f"sort[0][column]=period",
        f"sort[0][direction]=desc",
        f"length={limit}",
        f"offset={offset}",
    ]
    if start:
        parts.append(f"start={start}")
    if end:
        parts.append(f"end={end}")
    return f"{BASE_URL}/{route}/data?{'&'.join(parts)}"


def _request(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  [rate limited, waiting {wait}s...]")
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                print(f"  [API error {r.status_code}: {r.text[:300]}]")
                return None
            return r.json()
        except requests.exceptions.Timeout:
            print(f"  [timeout, attempt {attempt + 1}/{max_retries}]")
        except requests.exceptions.ConnectionError:
            print(f"  [connection error, attempt {attempt + 1}/{max_retries}]")
            time.sleep(2)
        except Exception as e:
            print(f"  [error: {e}]")
            return None
    print("  [max retries reached]")
    return None


def _safe_float(val, default=None):
    if val is None:
        return default
    try:
        return float(str(val).strip().replace(",", ""))
    except (ValueError, TypeError):
        return default


def _parse_period(val):
    if not val:
        return ""
    return str(val)[:10]


# --- Data Fetchers ------------------------------------------------------------

def _fetch_series(alias, limit=100, start=None, end=None):
    info = SERIES_REGISTRY.get(alias)
    if not info:
        print(f"  Unknown series: {alias}")
        return []
    url = _build_data_url(
        info["route"], info["freq"], info["series"],
        facet_key=info["facet_key"], start=start, end=end, limit=limit,
    )
    data = _request(url)
    if not data:
        return []
    resp = data.get("response", {})
    rows = resp.get("data", [])
    return rows


def _fetch_series_paginated(alias, limit=5000, start=None, end=None):
    info = SERIES_REGISTRY.get(alias)
    if not info:
        print(f"  Unknown series: {alias}")
        return []

    all_rows = []
    offset = 0
    page_size = min(limit, MAX_ROWS)

    while len(all_rows) < limit:
        remaining = limit - len(all_rows)
        this_page = min(page_size, remaining)
        url = _build_data_url(
            info["route"], info["freq"], info["series"],
            facet_key=info["facet_key"], start=start, end=end,
            limit=this_page, offset=offset,
        )
        data = _request(url)
        if not data:
            break
        resp = data.get("response", {})
        rows = resp.get("data", [])
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < this_page:
            break
        offset += len(rows)
        time.sleep(0.2)

    return all_rows[:limit]


def _fetch_multi_latest(aliases):
    results = {}
    for idx, alias in enumerate(aliases):
        rows = _fetch_series(alias, limit=2)
        if rows:
            results[alias] = rows
        if idx < len(aliases) - 1:
            time.sleep(0.15)
    return results


def _fetch_browse(route=""):
    path = route.strip("/")
    url = f"{BASE_URL}/{path}?api_key={API_KEY}" if path else f"{BASE_URL}?api_key={API_KEY}"
    data = _request(url)
    if not data:
        return None
    return data.get("response", data)


# --- Display Helpers -----------------------------------------------------------

def _fmt_num(n, decimals=1, sign=False):
    if n is None:
        return "N/A"
    if sign:
        return f"{n:+,.{decimals}f}"
    return f"{n:,.{decimals}f}"


def _fmt_pct(p, sign=False):
    if p is None:
        return "N/A"
    if sign:
        return f"{p:+.1f}%"
    return f"{p:.1f}%"


def _fmt_price(p, sign=False):
    if p is None:
        return "N/A"
    if sign:
        return f"{p:+.2f}"
    return f"{p:.2f}"


def _prompt(msg, default=None):
    suffix = f" [{default}]" if default is not None else ""
    try:
        val = input(f"  {msg}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return str(default) if default is not None else ""
    return val if val else (str(default) if default is not None else "")


def _prompt_choice(msg, choices, default=None):
    choices_str = "/".join(str(c) for c in choices)
    return _prompt(f"{msg} ({choices_str})", default)


def _row_value(row):
    return _safe_float(row.get("value"))


def _row_period(row):
    return row.get("period", "")


# --- Export -------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


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
            data = list(data.values()) if data else []
        _export_csv(data, path)


def _prompt_export(data, prefix):
    choice = _prompt("Export? (json/csv/no)", "no")
    if choice in ("json", "csv"):
        _do_export(data, prefix, choice)


# --- Command Functions --------------------------------------------------------

def cmd_petroleum(as_json=False, export_fmt=None):
    print("\n  Fetching weekly petroleum status report snapshot...")
    aliases = ["CRUDE_STOCKS", "GASOLINE_STOCKS", "DISTILLATE_STOCKS",
               "REFINERY_UTIL", "REFINERY_INPUTS", "CRUDE_IMPORTS"]
    multi = _fetch_multi_latest(aliases)

    if not multi:
        print("  No data returned.")
        return

    records = []
    for alias in aliases:
        info = SERIES_REGISTRY[alias]
        rows = multi.get(alias, [])
        latest_val = _row_value(rows[0]) if rows else None
        latest_per = _row_period(rows[0]) if rows else "N/A"
        prev_val = _row_value(rows[1]) if len(rows) > 1 else None
        chg = (latest_val - prev_val) if latest_val is not None and prev_val is not None else None
        records.append({
            "alias": alias, "name": info["name"], "unit": info["unit"],
            "period": latest_per, "value": latest_val, "prev": prev_val, "change": chg,
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    print(f"\n  WEEKLY PETROLEUM STATUS REPORT SNAPSHOT")
    print("  " + "=" * 80)
    print(f"  {'Metric':<38} {'Latest':>12} {'Change':>10} {'Unit':<22} {'Period'}")
    print(f"  {'-'*38} {'-'*12} {'-'*10} {'-'*22} {'-'*10}")
    for r in records:
        val_str = _fmt_num(r["value"], decimals=0) if r["value"] is not None else "N/A"
        chg_str = _fmt_num(r["change"], decimals=0, sign=True) if r["change"] is not None else ""
        print(f"  {r['name']:<38} {val_str:>12} {chg_str:>10} {r['unit']:<22} {r['period']}")
    print()

    if export_fmt:
        _do_export(records, "eia_petroleum", export_fmt)
    return records


def cmd_crude_stocks(weeks=52, as_json=False, export_fmt=None):
    print(f"\n  Fetching crude oil inventory history ({weeks} weeks)...")
    rows = _fetch_series("CRUDE_STOCKS", limit=weeks)
    if not rows:
        print("  No data returned.")
        return

    records = []
    for i, row in enumerate(rows):
        val = _row_value(row)
        prev_val = _row_value(rows[i + 1]) if i + 1 < len(rows) else None
        chg = (val - prev_val) if val is not None and prev_val is not None else None
        records.append({
            "period": _row_period(row),
            "value": val,
            "change": chg,
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    info = SERIES_REGISTRY["CRUDE_STOCKS"]
    print(f"\n  {info['name']} -- Last {weeks} Weeks")
    print("  " + "=" * 55)
    print(f"  {'Period':<12} {'Stocks (k bbl)':>16} {'WoW Change':>14}")
    print(f"  {'-'*12} {'-'*16} {'-'*14}")
    for r in records[:min(weeks, 60)]:
        val_str = _fmt_num(r["value"], decimals=0) if r["value"] is not None else "N/A"
        chg_str = _fmt_num(r["change"], decimals=0, sign=True) if r["change"] is not None else ""
        print(f"  {r['period']:<12} {val_str:>16} {chg_str:>14}")
    if len(records) > 60:
        print(f"  ... ({len(records) - 60} more rows, use --export to get all)")
    print()

    if export_fmt:
        _do_export(records, "eia_crude_stocks", export_fmt)
    return records


def cmd_natgas_storage(weeks=52, as_json=False, export_fmt=None):
    print(f"\n  Fetching natural gas storage ({weeks} weeks)...")
    rows = _fetch_series("NATGAS_STORAGE", limit=weeks)
    if not rows:
        print("  No data returned.")
        return

    records = []
    for i, row in enumerate(rows):
        val = _row_value(row)
        prev_val = _row_value(rows[i + 1]) if i + 1 < len(rows) else None
        chg = (val - prev_val) if val is not None and prev_val is not None else None
        records.append({
            "period": _row_period(row),
            "value": val,
            "change": chg,
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    info = SERIES_REGISTRY["NATGAS_STORAGE"]
    print(f"\n  {info['name']} -- Last {weeks} Weeks")
    print("  " + "=" * 55)
    print(f"  {'Period':<12} {'Storage (Bcf)':>16} {'WoW Change':>14}")
    print(f"  {'-'*12} {'-'*16} {'-'*14}")
    for r in records[:min(weeks, 60)]:
        val_str = _fmt_num(r["value"], decimals=0) if r["value"] is not None else "N/A"
        chg_str = _fmt_num(r["change"], decimals=0, sign=True) if r["change"] is not None else ""
        print(f"  {r['period']:<12} {val_str:>16} {chg_str:>14}")
    if len(records) > 60:
        print(f"  ... ({len(records) - 60} more rows, use --export to get all)")
    print()

    if export_fmt:
        _do_export(records, "eia_natgas_storage", export_fmt)
    return records


def cmd_prices(as_json=False, export_fmt=None):
    print("\n  Fetching latest spot prices...")
    multi = _fetch_multi_latest(PRICE_SERIES)

    if not multi:
        print("  No data returned.")
        return

    records = []
    for alias in PRICE_SERIES:
        info = SERIES_REGISTRY[alias]
        rows = multi.get(alias, [])
        latest_val = _row_value(rows[0]) if rows else None
        latest_per = _row_period(rows[0]) if rows else "N/A"
        prev_val = _row_value(rows[1]) if len(rows) > 1 else None
        chg = (latest_val - prev_val) if latest_val is not None and prev_val is not None else None
        records.append({
            "alias": alias, "name": info["name"], "unit": info["unit"],
            "period": latest_per, "value": latest_val, "change": chg,
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    print(f"\n  SPOT PRICES -- Latest")
    print("  " + "=" * 70)
    print(f"  {'Name':<32} {'Price':>10} {'Change':>10} {'Unit':<14} {'Date'}")
    print(f"  {'-'*32} {'-'*10} {'-'*10} {'-'*14} {'-'*10}")
    for r in records:
        val_str = _fmt_price(r["value"]) if r["value"] is not None else "N/A"
        chg_str = _fmt_price(r["change"], sign=True) if r["change"] is not None else ""
        print(f"  {r['name']:<32} {val_str:>10} {chg_str:>10} {r['unit']:<14} {r['period']}")
    print()

    if export_fmt:
        _do_export(records, "eia_prices", export_fmt)
    return records


def cmd_price_history(alias=None, days=90, as_json=False, export_fmt=None):
    if alias is None:
        alias = "WTI_SPOT"
    alias = alias.upper()
    if alias not in SERIES_REGISTRY:
        print(f"  Unknown series '{alias}'. Use 'series' to see available aliases.")
        return

    info = SERIES_REGISTRY[alias]
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"\n  Fetching {info['name']} price history ({days} days)...")
    rows = _fetch_series(alias, limit=min(days, MAX_ROWS), start=start_date)

    if not rows:
        print("  No data returned.")
        return

    records = []
    for row in rows:
        records.append({
            "period": _row_period(row),
            "value": _row_value(row),
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    print(f"\n  {info['name']} -- Last {days} Days")
    print("  " + "=" * 40)
    print(f"  {'Date':<12} {'Price':>12} {info['unit']}")
    print(f"  {'-'*12} {'-'*12}")
    for r in records[:min(len(records), 60)]:
        val_str = _fmt_price(r["value"]) if r["value"] is not None else "N/A"
        print(f"  {r['period']:<12} {val_str:>12}")
    if len(records) > 60:
        print(f"  ... ({len(records) - 60} more rows, use --export to get all)")
    print()

    if export_fmt:
        _do_export(records, f"eia_price_{alias.lower()}", export_fmt)
    return records


def cmd_refinery(weeks=52, as_json=False, export_fmt=None):
    print(f"\n  Fetching refinery data ({weeks} weeks)...")
    util_rows = _fetch_series("REFINERY_UTIL", limit=weeks)
    time.sleep(0.15)
    input_rows = _fetch_series("REFINERY_INPUTS", limit=weeks)

    records = []
    util_map = {_row_period(r): _row_value(r) for r in (util_rows or [])}
    input_map = {_row_period(r): _row_value(r) for r in (input_rows or [])}
    all_periods = sorted(set(list(util_map.keys()) + list(input_map.keys())), reverse=True)

    for i, period in enumerate(all_periods[:weeks]):
        util_val = util_map.get(period)
        input_val = input_map.get(period)
        prev_period = all_periods[i + 1] if i + 1 < len(all_periods) else None
        util_chg = None
        if util_val is not None and prev_period and util_map.get(prev_period) is not None:
            util_chg = util_val - util_map[prev_period]
        records.append({
            "period": period,
            "utilization_pct": util_val,
            "util_change": util_chg,
            "crude_inputs_kbd": input_val,
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    if not records:
        print("  No data returned.")
        return

    print(f"\n  US REFINERY DATA -- Last {weeks} Weeks")
    print("  " + "=" * 65)
    print(f"  {'Period':<12} {'Util %':>8} {'Chg':>8} {'Crude Inputs (kbd)':>20}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*20}")
    for r in records[:min(len(records), 60)]:
        util_str = _fmt_pct(r["utilization_pct"]) if r["utilization_pct"] is not None else "N/A"
        chg_str = _fmt_pct(r["util_change"], sign=True) if r["util_change"] is not None else ""
        inp_str = _fmt_num(r["crude_inputs_kbd"], decimals=0) if r["crude_inputs_kbd"] is not None else "N/A"
        print(f"  {r['period']:<12} {util_str:>8} {chg_str:>8} {inp_str:>20}")
    if len(records) > 60:
        print(f"  ... ({len(records) - 60} more rows)")
    print()

    if export_fmt:
        _do_export(records, "eia_refinery", export_fmt)
    return records


def cmd_steo(as_json=False, export_fmt=None):
    print("\n  Fetching Short-Term Energy Outlook forecasts...")
    steo_aliases = [k for k in SERIES_REGISTRY if k.startswith("STEO_")]
    multi = {}
    for idx, alias in enumerate(steo_aliases):
        rows = _fetch_series(alias, limit=36)
        if rows:
            multi[alias] = rows
        if idx < len(steo_aliases) - 1:
            time.sleep(0.15)

    if not multi:
        print("  No data returned.")
        return

    if as_json:
        out = {}
        for alias, rows in multi.items():
            out[alias] = [{"period": _row_period(r), "value": _row_value(r)} for r in rows]
        print(json.dumps(out, indent=2, default=str))
        return out

    for alias, rows in multi.items():
        info = SERIES_REGISTRY[alias]
        print(f"\n  {info['name']} ({info['unit']})")
        print("  " + "=" * 40)
        print(f"  {'Period':<12} {'Value':>14}")
        print(f"  {'-'*12} {'-'*14}")
        for r in rows[:24]:
            val = _row_value(r)
            val_str = _fmt_num(val, decimals=2) if val is not None else "N/A"
            print(f"  {_row_period(r):<12} {val_str:>14}")
    print()

    if export_fmt:
        flat = []
        for alias, rows in multi.items():
            for r in rows:
                flat.append({"series": alias, "name": SERIES_REGISTRY[alias]["name"],
                             "period": _row_period(r), "value": _row_value(r)})
        _do_export(flat, "eia_steo", export_fmt)
    return multi


def cmd_browse(route="", as_json=False, export_fmt=None):
    path = route.strip("/") if route else ""
    display_path = path if path else "(root)"
    print(f"\n  Browsing: /v2/{display_path}")
    data = _fetch_browse(path)

    if not data:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return data

    name = data.get("name", data.get("id", display_path))
    desc = data.get("description", "")
    print(f"\n  {name}")
    if desc:
        print(f"  {desc}")
    print("  " + "=" * 60)

    routes = data.get("routes", [])
    if routes:
        print(f"\n  CHILD ROUTES:")
        print(f"  {'ID':<28} {'Name':<40}")
        print(f"  {'-'*28} {'-'*40}")
        for r in routes:
            rid = r.get("id", "?")
            rname = r.get("name", r.get("description", ""))
            print(f"  {rid:<28} {rname:<40}")

    freqs = data.get("frequency", [])
    if freqs:
        print(f"\n  FREQUENCIES:")
        for fr in freqs:
            fid = fr.get("id", fr) if isinstance(fr, dict) else fr
            fdesc = fr.get("description", "") if isinstance(fr, dict) else ""
            print(f"    {fid}  {fdesc}")

    facets = data.get("facets", [])
    if facets:
        print(f"\n  FACETS:")
        for fc in facets:
            fid = fc.get("id", fc) if isinstance(fc, dict) else fc
            fdesc = fc.get("description", "") if isinstance(fc, dict) else ""
            print(f"    {fid}  {fdesc}")

    data_cols = data.get("data", {})
    if isinstance(data_cols, dict) and data_cols:
        print(f"\n  DATA COLUMNS:")
        for k, v in data_cols.items():
            print(f"    {k}: {v}")

    print()
    return data


def cmd_series(as_json=False, export_fmt=None):
    if as_json:
        out = {}
        for alias, info in SERIES_REGISTRY.items():
            out[alias] = {
                "name": info["name"], "route": info["route"],
                "series": info["series"], "unit": info["unit"],
                "freq": info["freq"],
            }
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  Curated Series Registry ({len(SERIES_REGISTRY)} series)")
    print("  " + "=" * 90)

    current_route = None
    for alias, info in SERIES_REGISTRY.items():
        cat = info["route"].split("/")[0]
        if cat != current_route:
            current_route = cat
            label = CATEGORY_NAMES.get(cat, cat.upper())
            print(f"\n  {label}")
            print(f"  {'Alias':<20} {'Series ID':<26} {'Name':<40} {'Freq':<8} {'Unit'}")
            print(f"  {'-'*20} {'-'*26} {'-'*40} {'-'*8} {'-'*18}")
        print(f"  {alias:<20} {info['series']:<26} {info['name']:<40} {info['freq']:<8} {info['unit']}")

    print(f"\n  Usage: python eia.py history <ALIAS> --periods 52")
    print(f"  Example: python eia.py history CRUDE_STOCKS --periods 104\n")

    if export_fmt:
        flat = [{"alias": a, **{k: v for k, v in i.items() if k != "facet_key"}}
                for a, i in SERIES_REGISTRY.items()]
        _do_export(flat, "eia_series", export_fmt)
    return SERIES_REGISTRY


def cmd_history(alias=None, periods=52, as_json=False, export_fmt=None):
    if alias is None:
        alias = "CRUDE_STOCKS"
    alias = alias.upper()
    if alias not in SERIES_REGISTRY:
        print(f"  Unknown series '{alias}'. Use 'series' to see available aliases.")
        return

    info = SERIES_REGISTRY[alias]
    print(f"\n  Fetching {info['name']} ({periods} periods)...")
    rows = _fetch_series(alias, limit=periods)

    if not rows:
        print("  No data returned.")
        return

    records = []
    for i, row in enumerate(rows):
        val = _row_value(row)
        prev_val = _row_value(rows[i + 1]) if i + 1 < len(rows) else None
        chg = (val - prev_val) if val is not None and prev_val is not None else None
        records.append({
            "period": _row_period(row),
            "value": val,
            "change": chg,
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    print(f"\n  {info['name']} -- Last {periods} Periods ({info['unit']})")
    print("  " + "=" * 50)
    print(f"  {'Period':<12} {'Value':>14} {'Change':>12}")
    print(f"  {'-'*12} {'-'*14} {'-'*12}")
    for r in records[:min(len(records), 60)]:
        val_str = _fmt_num(r["value"], decimals=1) if r["value"] is not None else "N/A"
        chg_str = _fmt_num(r["change"], decimals=1, sign=True) if r["change"] is not None else ""
        print(f"  {r['period']:<12} {val_str:>14} {chg_str:>12}")
    if len(records) > 60:
        print(f"  ... ({len(records) - 60} more rows, use --export to get all)")
    print()

    if export_fmt:
        _do_export(records, f"eia_{alias.lower()}", export_fmt)
    return records


def cmd_wpsr(as_json=False, export_fmt=None):
    print("\n  Fetching full Weekly Petroleum Status Report...")
    multi = _fetch_multi_latest(WPSR_SERIES)

    if not multi:
        print("  No data returned.")
        return

    records = []
    for alias in WPSR_SERIES:
        info = SERIES_REGISTRY[alias]
        rows = multi.get(alias, [])
        latest_val = _row_value(rows[0]) if rows else None
        latest_per = _row_period(rows[0]) if rows else "N/A"
        prev_val = _row_value(rows[1]) if len(rows) > 1 else None
        chg = (latest_val - prev_val) if latest_val is not None and prev_val is not None else None
        pct_chg = None
        if chg is not None and prev_val and prev_val != 0:
            pct_chg = (chg / prev_val) * 100
        records.append({
            "alias": alias, "name": info["name"], "unit": info["unit"],
            "period": latest_per, "value": latest_val, "prev": prev_val,
            "change": chg, "pct_change": pct_chg,
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    report_date = records[0]["period"] if records else "unknown"
    print(f"\n  WEEKLY PETROLEUM STATUS REPORT (WPSR)")
    print(f"  Week ending: {report_date}")
    print("  " + "=" * 95)
    print(f"  {'Metric':<38} {'Latest':>14} {'WoW Chg':>12} {'% Chg':>8} {'Unit'}")
    print(f"  {'-'*38} {'-'*14} {'-'*12} {'-'*8} {'-'*22}")
    for r in records:
        val_str = _fmt_num(r["value"], decimals=0) if r["value"] is not None else "N/A"
        chg_str = _fmt_num(r["change"], decimals=0, sign=True) if r["change"] is not None else ""
        pct_str = _fmt_pct(r["pct_change"], sign=True) if r["pct_change"] is not None else ""
        print(f"  {r['name']:<38} {val_str:>14} {chg_str:>12} {pct_str:>8} {r['unit']}")
    print()

    if export_fmt:
        _do_export(records, "eia_wpsr", export_fmt)
    return records


def cmd_energy_snapshot(as_json=False, export_fmt=None):
    print("\n  Building energy snapshot...")
    snapshot_series = [
        "WTI_SPOT", "BRENT_SPOT", "HH_SPOT",
        "CRUDE_STOCKS", "GASOLINE_STOCKS", "DISTILLATE_STOCKS",
        "NATGAS_STORAGE", "REFINERY_UTIL",
    ]
    multi = _fetch_multi_latest(snapshot_series)

    if not multi:
        print("  No data returned.")
        return

    snapshot = {}
    for alias in snapshot_series:
        info = SERIES_REGISTRY[alias]
        rows = multi.get(alias, [])
        latest_val = _row_value(rows[0]) if rows else None
        latest_per = _row_period(rows[0]) if rows else "N/A"
        prev_val = _row_value(rows[1]) if len(rows) > 1 else None
        chg = (latest_val - prev_val) if latest_val is not None and prev_val is not None else None
        snapshot[alias] = {
            "name": info["name"], "unit": info["unit"],
            "period": latest_per, "value": latest_val, "change": chg,
        }

    if as_json:
        print(json.dumps(snapshot, indent=2, default=str))
        return snapshot

    print(f"\n  ENERGY MARKET SNAPSHOT")
    print("  " + "=" * 80)

    # Prices
    print(f"\n  PRICES")
    print(f"  {'-'*70}")
    for alias in ["WTI_SPOT", "BRENT_SPOT", "HH_SPOT"]:
        s = snapshot.get(alias, {})
        val_str = _fmt_price(s.get("value")) if s.get("value") is not None else "N/A"
        chg_str = _fmt_price(s.get("change"), sign=True) if s.get("change") is not None else ""
        print(f"  {s.get('name', alias):<36} {val_str:>10} {s.get('unit', ''):>12}   {chg_str:>8}  ({s.get('period', '')})")

    # Inventories
    print(f"\n  INVENTORIES")
    print(f"  {'-'*70}")
    for alias in ["CRUDE_STOCKS", "GASOLINE_STOCKS", "DISTILLATE_STOCKS"]:
        s = snapshot.get(alias, {})
        val = s.get("value")
        chg = s.get("change")
        val_str = _fmt_num(val, decimals=0) if val is not None else "N/A"
        chg_str = _fmt_num(chg, decimals=0, sign=True) if chg is not None else ""
        direction = ""
        if chg is not None:
            direction = "BUILD" if chg > 0 else "DRAW" if chg < 0 else "FLAT"
        print(f"  {s.get('name', alias):<36} {val_str:>12} k bbl   {chg_str:>10}  {direction:>6}  ({s.get('period', '')})")

    # Natural gas
    print(f"\n  NATURAL GAS STORAGE")
    print(f"  {'-'*70}")
    s = snapshot.get("NATGAS_STORAGE", {})
    val = s.get("value")
    chg = s.get("change")
    val_str = _fmt_num(val, decimals=0) if val is not None else "N/A"
    chg_str = _fmt_num(chg, decimals=0, sign=True) if chg is not None else ""
    inject = ""
    if chg is not None:
        inject = "INJECT" if chg > 0 else "WITHDRAW" if chg < 0 else "FLAT"
    print(f"  {s.get('name', 'Natgas Storage'):<36} {val_str:>12} Bcf     {chg_str:>10}  {inject:>8}  ({s.get('period', '')})")

    # Refinery
    print(f"\n  REFINERY")
    print(f"  {'-'*70}")
    s = snapshot.get("REFINERY_UTIL", {})
    val = s.get("value")
    chg = s.get("change")
    val_str = _fmt_pct(val) if val is not None else "N/A"
    chg_str = _fmt_pct(chg, sign=True) if chg is not None else ""
    print(f"  {s.get('name', 'Refinery Util'):<36} {val_str:>12}         {chg_str:>10}          ({s.get('period', '')})")

    print()

    if export_fmt:
        flat = [{"alias": k, **v} for k, v in snapshot.items()]
        _do_export(flat, "eia_snapshot", export_fmt)
    return snapshot


# --- Interactive CLI -----------------------------------------------------------

MENU = """
  =====================================================
   EIA Energy Information Administration -- API Client
  =====================================================

   PETROLEUM
     1) petroleum       Weekly petroleum status snapshot
     2) crude-stocks    Crude oil inventory history
     3) refinery        Refinery utilization & inputs
     4) wpsr            Full WPSR (all series + WoW)

   NATURAL GAS
     5) natgas-storage  Natural gas storage report

   PRICES
     6) prices          Spot prices snapshot (WTI/Brent/HH)
     7) price-history   Price history for a specific series

   FORECASTS
     8) steo            Short-term energy outlook

   DASHBOARDS
     9) energy-snapshot Combined energy market dashboard

   DATA
    10) browse          Browse API hierarchy
    11) series          List curated series registry
    12) history         Generic series history

   q) quit
"""


def _i_petroleum():
    cmd_petroleum()

def _i_crude_stocks():
    weeks = _prompt("Number of weeks", "52")
    cmd_crude_stocks(weeks=int(weeks))

def _i_refinery():
    weeks = _prompt("Number of weeks", "52")
    cmd_refinery(weeks=int(weeks))

def _i_wpsr():
    cmd_wpsr()

def _i_natgas_storage():
    weeks = _prompt("Number of weeks", "52")
    cmd_natgas_storage(weeks=int(weeks))

def _i_prices():
    cmd_prices()

def _i_price_history():
    print(f"  Available: {', '.join(PRICE_SERIES)}")
    alias = _prompt("Series alias", "WTI_SPOT")
    days = _prompt("Number of days", "90")
    cmd_price_history(alias=alias, days=int(days))

def _i_steo():
    cmd_steo()

def _i_energy_snapshot():
    cmd_energy_snapshot()

def _i_browse():
    route = _prompt("API route (e.g. petroleum/pri/spt)", "")
    cmd_browse(route=route)

def _i_series():
    cmd_series()

def _i_history():
    print(f"  Available: {', '.join(SERIES_REGISTRY.keys())}")
    alias = _prompt("Series alias (e.g. CRUDE_STOCKS)")
    periods = _prompt("Number of periods", "52")
    cmd_history(alias=alias, periods=int(periods))


COMMAND_MAP = {
    "1":  _i_petroleum,
    "2":  _i_crude_stocks,
    "3":  _i_refinery,
    "4":  _i_wpsr,
    "5":  _i_natgas_storage,
    "6":  _i_prices,
    "7":  _i_price_history,
    "8":  _i_steo,
    "9":  _i_energy_snapshot,
    "10": _i_browse,
    "11": _i_series,
    "12": _i_history,
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

VALID_PRICE_ALIASES = ["WTI_SPOT", "BRENT_SPOT", "HH_SPOT"]


def build_argparse():
    p = argparse.ArgumentParser(
        prog="eia.py",
        description="EIA Energy Information Administration -- Energy Data Client",
    )
    sub = p.add_subparsers(dest="command")

    # petroleum
    s = sub.add_parser("petroleum", help="Weekly petroleum status snapshot")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # crude-stocks
    s = sub.add_parser("crude-stocks", help="Crude oil inventory history")
    s.add_argument("--weeks", type=int, default=52)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # natgas-storage
    s = sub.add_parser("natgas-storage", help="Natural gas storage report")
    s.add_argument("--weeks", type=int, default=52)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # prices
    s = sub.add_parser("prices", help="Spot prices snapshot")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # price-history
    s = sub.add_parser("price-history", help="Price history for a series")
    s.add_argument("series", nargs="?", default="WTI_SPOT",
                   help="Series alias (WTI_SPOT, BRENT_SPOT, HH_SPOT)")
    s.add_argument("--days", type=int, default=90)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # refinery
    s = sub.add_parser("refinery", help="Refinery utilization & crude inputs")
    s.add_argument("--weeks", type=int, default=52)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # steo
    s = sub.add_parser("steo", help="Short-term energy outlook forecasts")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # browse
    s = sub.add_parser("browse", help="Browse API hierarchy")
    s.add_argument("route", nargs="?", default="",
                   help="API route (e.g. petroleum/pri/spt)")
    s.add_argument("--json", action="store_true")

    # series
    s = sub.add_parser("series", help="List curated series registry")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # history
    s = sub.add_parser("history", help="Generic series history")
    s.add_argument("series", nargs="?", default="CRUDE_STOCKS",
                   help="Series alias (e.g. CRUDE_STOCKS)")
    s.add_argument("--periods", type=int, default=52)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # wpsr
    s = sub.add_parser("wpsr", help="Full WPSR (all series + WoW changes)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # energy-snapshot
    s = sub.add_parser("energy-snapshot", help="Combined energy market dashboard")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "petroleum":
        cmd_petroleum(as_json=j, export_fmt=exp)
    elif args.command == "crude-stocks":
        cmd_crude_stocks(weeks=args.weeks, as_json=j, export_fmt=exp)
    elif args.command == "natgas-storage":
        cmd_natgas_storage(weeks=args.weeks, as_json=j, export_fmt=exp)
    elif args.command == "prices":
        cmd_prices(as_json=j, export_fmt=exp)
    elif args.command == "price-history":
        cmd_price_history(alias=args.series, days=args.days, as_json=j, export_fmt=exp)
    elif args.command == "refinery":
        cmd_refinery(weeks=args.weeks, as_json=j, export_fmt=exp)
    elif args.command == "steo":
        cmd_steo(as_json=j, export_fmt=exp)
    elif args.command == "browse":
        cmd_browse(route=args.route, as_json=j)
    elif args.command == "series":
        cmd_series(as_json=j, export_fmt=exp)
    elif args.command == "history":
        cmd_history(alias=args.series, periods=args.periods, as_json=j, export_fmt=exp)
    elif args.command == "wpsr":
        cmd_wpsr(as_json=j, export_fmt=exp)
    elif args.command == "energy-snapshot":
        cmd_energy_snapshot(as_json=j, export_fmt=exp)


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
