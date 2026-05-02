#!/usr/bin/env python3
"""
DTCC Swap Data Repository -- OTC Derivative Flow Client

Single-script client for DTCC Public Price Dissemination (PPD) data.
Downloads daily cumulative trade files from S3 for five OTC derivative asset
classes: interest rate swaps, credit default swaps, FX, equities, commodities.
No auth required -- data is publicly accessible.

Usage:
    python dtcc.py                                      # interactive CLI
    python dtcc.py latest                               # latest day, rates
    python dtcc.py latest --asset-class credits         # latest day, CDS
    python dtcc.py history --asset-class rates --days 5 # 5-day trend
    python dtcc.py rates                                # IRS tenor/rate analysis
    python dtcc.py credits                              # CDS single-name vs index
    python dtcc.py fx                                   # FX currency pair volumes
    python dtcc.py commodities                          # commodity underlier breakdown
    python dtcc.py volume --asset-class rates --days 20 # 20-day volume series
    python dtcc.py summary                              # cross-asset snapshot
    python dtcc.py search --underlier SOFR              # search by underlier
    python dtcc.py assets                               # list asset classes
    python dtcc.py cleared --asset-class rates          # clearing rate analysis
    python dtcc.py export --asset-class rates --days 1  # export raw CSV
"""

import argparse
import csv
import io
import json
import os
import sys
import time
import zipfile
from datetime import datetime, timedelta, date

import requests


# --- Configuration ------------------------------------------------------------

SESSION = requests.Session()
S3_BASE_URL = "https://kgc0418-tdw-data-0.s3.amazonaws.com"

ASSET_CLASSES = {
    "rates":       {"s3_name": "RATES",       "display": "Interest Rates",  "group": "rates"},
    "credits":     {"s3_name": "CREDITS",      "display": "Credits/CDS",    "group": "credit"},
    "fx":          {"s3_name": "FOREX",        "display": "Foreign Exchange","group": "fx"},
    "equities":    {"s3_name": "EQUITIES",     "display": "Equities",       "group": "equity"},
    "commodities": {"s3_name": "COMMODITIES",  "display": "Commodities",    "group": "commodity"},
}

ASSET_GROUPS = {
    "rates": ["rates"], "credit": ["credits"], "fx": ["fx"],
    "equity": ["equities"], "commodity": ["commodities"],
}

TENOR_ORDER = [
    "0-3M", "3-6M", "6M-1Y", "1-2Y", "2-3Y", "3-5Y", "5-7Y",
    "7-10Y", "10-15Y", "15-20Y", "20-30Y", "30Y+", "Unknown",
]

# Column names in current DTCC PPD format (post-2023 CFTC Part 43 rewrite)
COL_NOTIONAL_1 = "Notional amount-Leg 1"
COL_NOTIONAL_2 = "Notional amount-Leg 2"
COL_CCY_1 = "Notional currency-Leg 1"
COL_CCY_2 = "Notional currency-Leg 2"
COL_CLEARED = "Cleared"
COL_EXEC_TS = "Execution Timestamp"
COL_EFF_DATE = "Effective Date"
COL_EXP_DATE = "Expiration Date"
COL_ASSET_CLASS = "Asset Class"
COL_PRODUCT = "Product name"
COL_UPI_FISN = "UPI FISN"
COL_UPI_UNDERLIER = "UPI Underlier Name"
COL_UNDERLIER_1 = "Underlier ID-Leg 1"
COL_UNDERLIER_2 = "Underlier ID-Leg 2"
COL_FIXED_RATE_1 = "Fixed rate-Leg 1"
COL_FIXED_RATE_2 = "Fixed rate-Leg 2"
COL_PRICE = "Price"
COL_PRICE_NOTATION = "Price notation"
COL_SETTLE_CCY_1 = "Settlement currency-Leg 1"
COL_SETTLE_CCY_2 = "Settlement currency-Leg 2"
COL_ACTION = "Action type"
COL_OPTION_TYPE = "Option Type"
COL_STRIKE = "Strike Price"


# --- HTTP + Download ----------------------------------------------------------

def _most_recent_business_day():
    d = date.today()
    if d.weekday() >= 5:
        d -= timedelta(days=(d.weekday() - 4))
    return d

def _business_days_back(n, from_date=None):
    if from_date is None:
        from_date = _most_recent_business_day()
    days, d = [], from_date
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days

def _prev_business_day(d):
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

def _download_day(asset_class, date_obj, source="cftc"):
    info = ASSET_CLASSES.get(asset_class)
    if not info:
        print(f"  [unknown asset class: {asset_class}]")
        return None

    s3_name = info["s3_name"]
    src_upper = source.upper()
    src_lower = source.lower()
    ds = date_obj.strftime("%Y_%m_%d")
    url = f"{S3_BASE_URL}/{src_lower}/eod/{src_upper}_CUMULATIVE_{s3_name}_{ds}.zip"

    try:
        r = SESSION.get(url, timeout=60)
        if r.status_code != 200 or len(r.content) < 4 or r.content[:2] != b"PK":
            return None
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        csv_name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
        if not csv_name:
            return None
        raw = zf.read(csv_name).decode("utf-8", errors="replace")
        return list(csv.DictReader(io.StringIO(raw)))
    except zipfile.BadZipFile:
        return None
    except requests.exceptions.Timeout:
        print(f"  [timeout downloading {date_obj}]")
        return None
    except requests.exceptions.ConnectionError:
        print(f"  [connection error downloading {date_obj}]")
        return None
    except Exception as e:
        print(f"  [error downloading {date_obj}: {e}]")
        return None

def _download_with_fallback(asset_class, date_obj, source="cftc", max_attempts=5):
    d = date_obj
    rows = _download_day(asset_class, d, source=source)
    attempts = 0
    while rows is None and attempts < max_attempts:
        d = _prev_business_day(d)
        print(f"  [no data, trying {d.strftime('%Y-%m-%d')}...]")
        rows = _download_day(asset_class, d, source=source)
        attempts += 1
    return rows, d


# --- Parsing Helpers ----------------------------------------------------------

def _safe_float(row, field, default=0.0):
    val = row.get(field, "")
    if not val or str(val).strip() == "":
        return default
    try:
        return float(str(val).strip().replace(",", "").replace("+", ""))
    except (ValueError, TypeError):
        return default

def _safe_str(row, field, default=""):
    val = row.get(field, default)
    return str(val).strip() if val else default

def _parse_date_field(val):
    if not val or not str(val).strip():
        return None
    val = str(val).strip()[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except (ValueError, TypeError):
            continue
    return None

def _compute_tenor_years(eff, end):
    eff_d, end_d = _parse_date_field(eff), _parse_date_field(end)
    if not eff_d or not end_d:
        return None
    delta = (end_d - eff_d).days
    return delta / 365.25 if delta > 0 else None

def _tenor_bucket(years):
    if years is None:
        return "Unknown"
    for limit, label in [(0.25, "0-3M"), (0.5, "3-6M"), (1.0, "6M-1Y"), (2.0, "1-2Y"),
                         (3.0, "2-3Y"), (5.0, "3-5Y"), (7.0, "5-7Y"), (10.0, "7-10Y"),
                         (15.0, "10-15Y"), (20.0, "15-20Y"), (30.0, "20-30Y")]:
        if years <= limit:
            return label
    return "30Y+"

def _is_cleared(row):
    return _safe_str(row, COL_CLEARED, "").upper() in ("Y", "I")

def _notional(row):
    val = _safe_float(row, COL_NOTIONAL_1)
    if val > 1e15:
        return 0.0
    return val

def _classify_product(row):
    """Derive product type from UPI FISN field."""
    fisn = _safe_str(row, COL_UPI_FISN, "").upper()
    if not fisn:
        return "Unknown"
    if "SWAP OIS" in fisn or "SW OIS" in fisn:
        return "OIS Swap"
    if "SWAP FXD FLT" in fisn or "SW FXD FLT" in fisn:
        return "Fixed-Float Swap"
    if "SWAP FLT FLT" in fisn or "SW FLT FLT" in fisn:
        return "Basis Swap"
    if "FWD NDF" in fisn:
        return "NDF"
    if "FWD PR" in fisn or "FWD" in fisn:
        return "Forward/FRA"
    if "O VAN" in fisn or "O P " in fisn or "O C " in fisn:
        return "Option/Swaption"
    if "CAP" in fisn or "FLR" in fisn or "FLOOR" in fisn:
        return "Cap/Floor"
    if "CR SW SN" in fisn:
        return "Single Name CDS"
    if "CR SW IDX" in fisn or "CR SW IX" in fisn:
        return "Index CDS"
    if "CR SW TRCH" in fisn:
        return "Index Tranche"
    if "CR SW" in fisn:
        return "Credit Swap"
    if "TRTN" in fisn:
        return "Total Return Swap"
    if "VAR" in fisn:
        return "Variance Swap"
    if "PORT" in fisn:
        return "Portfolio Swap"
    return "Other"

def _underlier_name(row):
    ul = _safe_str(row, COL_UPI_UNDERLIER, "")
    if ul:
        return ul
    return _safe_str(row, COL_UNDERLIER_1, "Unknown")


# --- Display Helpers ----------------------------------------------------------

def _fmt_notional(n):
    if n >= 1e12:
        return f"${n / 1e12:.1f}T"
    if n >= 1e9:
        return f"${n / 1e9:.1f}B"
    if n >= 1e6:
        return f"${n / 1e6:.1f}M"
    if n >= 1e3:
        return f"${n / 1e3:.0f}K"
    return f"${n:.0f}"

def _fmt_num(n, sign=False):
    return f"{n:+,}" if sign else f"{n:,}"

def _prompt(msg, default=None):
    suffix = f" [{default}]" if default is not None else ""
    try:
        val = input(f"  {msg}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return str(default) if default is not None else ""
    return val if val else (str(default) if default is not None else "")

def _prompt_choice(msg, choices, default=None):
    return _prompt(f"{msg} ({'/'.join(str(c) for c in choices)})", default)

def _prompt_asset_class(default="rates"):
    return _prompt_choice("Asset class", list(ASSET_CLASSES.keys()), default)

def _prompt_source(default="cftc"):
    return _prompt_choice("Data source", ["cftc", "sec"], default)


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
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    else:
        with open(path, "w", newline="") as f:
            csv.writer(f).writerows(rows)
    print(f"  Exported: {path}")

def _do_export(data, prefix, fmt):
    path = os.path.join(SCRIPT_DIR, f"{prefix}_{_ts()}.{fmt}")
    if fmt == "json":
        _export_json(data, path)
    elif fmt == "csv":
        if isinstance(data, dict):
            data = list(data.values()) if data else []
        _export_csv(data, path)


# --- Domain Logic -------------------------------------------------------------

def _summarize_day(rows, asset_class=None):
    if not rows:
        return None
    total_notional, by_product, cleared_count = 0.0, {}, 0
    for row in rows:
        n = _notional(row)
        total_notional += n
        prod = _classify_product(row)
        if prod not in by_product:
            by_product[prod] = {"count": 0, "notional": 0.0}
        by_product[prod]["count"] += 1
        by_product[prod]["notional"] += n
        if _is_cleared(row):
            cleared_count += 1
    return {
        "trade_count": len(rows), "total_notional": total_notional,
        "cleared_count": cleared_count,
        "cleared_pct": (cleared_count / len(rows) * 100) if rows else 0,
        "by_product": by_product, "asset_class": asset_class or "",
    }

def _volume_series(data_by_date):
    return [
        {"date": ds, "trade_count": len(rows),
         "total_notional": sum(_notional(r) for r in rows)}
        for ds, rows in sorted(data_by_date.items())
    ]

def _group_by_field(rows, extract_fn, top_n=None):
    groups = {}
    for row in rows:
        key = extract_fn(row)
        if key not in groups:
            groups[key] = {"count": 0, "notional": 0.0}
        groups[key]["count"] += 1
        groups[key]["notional"] += _notional(row)
    sorted_groups = dict(sorted(groups.items(), key=lambda x: x[1]["notional"], reverse=True))
    if top_n:
        sorted_groups = dict(list(sorted_groups.items())[:top_n])
    return sorted_groups

def _rates_analysis(rows):
    if not rows:
        return None
    by_tenor, rate_values = {}, []
    for row in rows:
        n = _notional(row)
        bucket = _tenor_bucket(_compute_tenor_years(
            _safe_str(row, COL_EFF_DATE), _safe_str(row, COL_EXP_DATE)))
        if bucket not in by_tenor:
            by_tenor[bucket] = {"count": 0, "notional": 0.0}
        by_tenor[bucket]["count"] += 1
        by_tenor[bucket]["notional"] += n
        rate = _safe_float(row, COL_FIXED_RATE_1)
        if 0 < rate < 0.20:
            rate_values.append(rate * 100)
        elif 0.20 <= rate < 20:
            rate_values.append(rate)

    rate_stats = None
    if rate_values:
        rate_values.sort()
        n = len(rate_values)
        rate_stats = {"count": n, "min": rate_values[0], "max": rate_values[-1],
                      "median": rate_values[n // 2], "p25": rate_values[n // 4],
                      "p75": rate_values[3 * n // 4]}
    return {
        "trade_count": len(rows),
        "total_notional": sum(_notional(r) for r in rows),
        "by_tenor": by_tenor, "rate_stats": rate_stats,
        "by_product": _group_by_field(rows, _classify_product),
        "top_underliers": _group_by_field(rows, _underlier_name, top_n=15),
    }

def _credits_analysis(rows):
    if not rows:
        return None
    return {
        "trade_count": len(rows),
        "total_notional": sum(_notional(r) for r in rows),
        "by_product": _group_by_field(rows, _classify_product),
        "top_underliers": _group_by_field(rows, _underlier_name, top_n=20),
    }

def _fx_analysis(rows):
    if not rows:
        return None
    def _ccy_pair(row):
        c1 = _safe_str(row, COL_CCY_1, "")
        c2 = _safe_str(row, COL_CCY_2, "")
        ul = _safe_str(row, COL_UPI_UNDERLIER, "")
        if ul and " " in ul:
            return ul
        return f"{c1}/{c2}" if c1 and c2 else (c1 or c2 or "Unknown")

    return {
        "trade_count": len(rows),
        "total_notional": sum(_notional(r) for r in rows),
        "by_product": _group_by_field(rows, _classify_product),
        "top_ccy_pairs": _group_by_field(rows, _ccy_pair, top_n=20),
    }

def _commodity_analysis(rows):
    if not rows:
        return None
    return {
        "trade_count": len(rows),
        "total_notional": sum(_notional(r) for r in rows),
        "by_product": _group_by_field(rows, _classify_product),
        "top_underliers": _group_by_field(rows, _underlier_name, top_n=20),
    }

def _cleared_analysis(rows):
    if not rows:
        return None
    total_cleared, by_product = 0, {}
    for row in rows:
        cleared = _is_cleared(row)
        prod = _classify_product(row)
        if prod not in by_product:
            by_product[prod] = {"total": 0, "cleared": 0}
        by_product[prod]["total"] += 1
        if cleared:
            by_product[prod]["cleared"] += 1
            total_cleared += 1
    for data in by_product.values():
        data["pct"] = (data["cleared"] / data["total"] * 100) if data["total"] > 0 else 0
    return {
        "total_trades": len(rows), "total_cleared": total_cleared,
        "overall_pct": (total_cleared / len(rows) * 100) if rows else 0,
        "by_product": dict(sorted(by_product.items(),
                                  key=lambda x: x[1]["total"], reverse=True)),
    }

def _search_trades(rows, underlier=None, currency=None, product=None):
    results = []
    for row in rows:
        match = True
        if underlier:
            term = underlier.upper()
            targets = [_safe_str(row, f, "").upper()
                       for f in (COL_UPI_UNDERLIER, COL_UNDERLIER_1, COL_UNDERLIER_2)]
            if not any(term in t for t in targets):
                match = False
        if currency:
            term = currency.upper()
            targets = [_safe_str(row, f, "").upper()
                       for f in (COL_CCY_1, COL_CCY_2, COL_SETTLE_CCY_1)]
            if not any(term in t for t in targets):
                match = False
        if product:
            if product.upper() not in _classify_product(row).upper():
                match = False
        if match:
            results.append(row)
    return results


# --- Display ------------------------------------------------------------------

def _display_breakdown(label, groups, total_notional, name_width=30):
    print(f"\n  {label}")
    print(f"  {'Name':<{name_width}} {'Count':>8} {'Notional':>14} {'Share':>7}")
    print(f"  {'-' * name_width} {'-' * 8} {'-' * 14} {'-' * 7}")
    for key, data in sorted(groups.items(), key=lambda x: x[1]["notional"], reverse=True):
        share = (data["notional"] / total_notional * 100) if total_notional > 0 else 0
        print(f"  {key[:name_width]:<{name_width}} {data['count']:>8,} "
              f"{_fmt_notional(data['notional']):>14} {share:>6.1f}%")

def _display_top(label, groups, name_width=30):
    print(f"\n  {label}")
    print(f"  {'Name':<{name_width}} {'Count':>8} {'Notional':>14}")
    print(f"  {'-' * name_width} {'-' * 8} {'-' * 14}")
    for key, data in groups.items():
        print(f"  {key[:name_width]:<{name_width}} {data['count']:>8,} "
              f"{_fmt_notional(data['notional']):>14}")

def _display_summary(summary, date_str=""):
    header = f"  {summary['asset_class'].upper()} SUMMARY"
    if date_str:
        header += f" -- {date_str}"
    print(f"\n{header}")
    print("  " + "=" * 60)
    print(f"  Trade Count:    {_fmt_num(summary['trade_count'])}")
    print(f"  Total Notional: {_fmt_notional(summary['total_notional'])}")
    print(f"  Cleared:        {summary['cleared_count']:,} ({summary['cleared_pct']:.1f}%)")
    if summary["by_product"]:
        _display_breakdown("BY PRODUCT TYPE", summary["by_product"],
                           summary["total_notional"])
    print()

def _display_volume_series(series, asset_class=""):
    print(f"\n  VOLUME TIME SERIES -- {asset_class.upper()}")
    print("  " + "=" * 55)
    print(f"  {'Date':<12} {'Trades':>8} {'Notional':>14}")
    print(f"  {'-' * 12} {'-' * 8} {'-' * 14}")
    for p in series:
        print(f"  {p['date']:<12} {p['trade_count']:>8,} "
              f"{_fmt_notional(p['total_notional']):>14}")
    if series:
        tt = sum(p["trade_count"] for p in series)
        tn = sum(p["total_notional"] for p in series)
        print(f"\n  Period: {len(series)} days, {_fmt_num(tt)} total trades")
        print(f"  Avg daily: {tt / len(series):,.0f} trades, "
              f"{_fmt_notional(tn / len(series))} notional")
    print()

def _display_rates(analysis):
    if not analysis:
        print("  [no data]")
        return
    print(f"\n  INTEREST RATE SWAP ANALYSIS")
    print("  " + "=" * 65)
    print(f"  Total Trades:   {_fmt_num(analysis['trade_count'])}")
    print(f"  Total Notional: {_fmt_notional(analysis['total_notional'])}")
    if analysis["by_product"]:
        _display_breakdown("BY PRODUCT TYPE", analysis["by_product"],
                           analysis["total_notional"])
    if analysis["by_tenor"]:
        total = analysis["total_notional"]
        print(f"\n  NOTIONAL BY TENOR")
        print(f"  {'Tenor':<10} {'Count':>8} {'Notional':>14} {'Share':>7}")
        print(f"  {'-' * 10} {'-' * 8} {'-' * 14} {'-' * 7}")
        for bucket in TENOR_ORDER:
            if bucket in analysis["by_tenor"]:
                data = analysis["by_tenor"][bucket]
                share = (data["notional"] / total * 100) if total > 0 else 0
                print(f"  {bucket:<10} {data['count']:>8,} "
                      f"{_fmt_notional(data['notional']):>14} {share:>6.1f}%")
    if analysis["rate_stats"]:
        rs = analysis["rate_stats"]
        print(f"\n  FIXED RATE DISTRIBUTION ({rs['count']} trades with rates)")
        print(f"  Min:    {rs['min']:.3f}%")
        print(f"  25th:   {rs['p25']:.3f}%")
        print(f"  Median: {rs['median']:.3f}%")
        print(f"  75th:   {rs['p75']:.3f}%")
        print(f"  Max:    {rs['max']:.3f}%")
    if analysis["top_underliers"]:
        _display_top("TOP UNDERLIERS", analysis["top_underliers"])
    print()

def _display_credits(analysis):
    if not analysis:
        print("  [no data]")
        return
    print(f"\n  CREDIT DEFAULT SWAP ANALYSIS")
    print("  " + "=" * 65)
    print(f"  Total Trades:   {_fmt_num(analysis['trade_count'])}")
    print(f"  Total Notional: {_fmt_notional(analysis['total_notional'])}")
    if analysis["by_product"]:
        _display_breakdown("BY TYPE (Single-Name vs Index vs Other)",
                           analysis["by_product"], analysis["total_notional"])
    if analysis["top_underliers"]:
        _display_top("TOP REFERENCE ENTITIES", analysis["top_underliers"], name_width=35)
    print()

def _display_fx(analysis):
    if not analysis:
        print("  [no data]")
        return
    print(f"\n  FX DERIVATIVE ANALYSIS")
    print("  " + "=" * 65)
    print(f"  Total Trades:   {_fmt_num(analysis['trade_count'])}")
    print(f"  Total Notional: {_fmt_notional(analysis['total_notional'])}")
    if analysis["by_product"]:
        _display_breakdown("BY TYPE (NDF vs Deliverable vs Options)",
                           analysis["by_product"], analysis["total_notional"])
    if analysis["top_ccy_pairs"]:
        _display_top("TOP CURRENCY PAIRS", analysis["top_ccy_pairs"], name_width=15)
    print()

def _display_commodities(analysis):
    if not analysis:
        print("  [no data]")
        return
    print(f"\n  COMMODITY SWAP ANALYSIS")
    print("  " + "=" * 65)
    print(f"  Total Trades:   {_fmt_num(analysis['trade_count'])}")
    print(f"  Total Notional: {_fmt_notional(analysis['total_notional'])}")
    if analysis["by_product"]:
        _display_breakdown("BY TYPE", analysis["by_product"], analysis["total_notional"])
    if analysis["top_underliers"]:
        _display_top("TOP UNDERLIERS", analysis["top_underliers"], name_width=35)
    print()

def _display_cleared(analysis, asset_class=""):
    if not analysis:
        print("  [no data]")
        return
    print(f"\n  CLEARING ANALYSIS -- {asset_class.upper()}")
    print("  " + "=" * 60)
    print(f"  Total Trades:  {analysis['total_trades']:,}")
    print(f"  Cleared:       {analysis['total_cleared']:,} ({analysis['overall_pct']:.1f}%)")
    if analysis["by_product"]:
        print(f"\n  {'Product':<25} {'Total':>8} {'Cleared':>8} {'Rate':>7}")
        print(f"  {'-' * 25} {'-' * 8} {'-' * 8} {'-' * 7}")
        for prod, data in analysis["by_product"].items():
            print(f"  {prod[:25]:<25} {data['total']:>8,} "
                  f"{data['cleared']:>8,} {data['pct']:>6.1f}%")
    print()

def _display_search_results(results, max_display=50):
    if not results:
        print("  [no matching trades]")
        return
    print(f"\n  SEARCH RESULTS ({len(results)} trades)")
    print("  " + "=" * 85)
    display = results[:max_display]
    print(f"  {'Timestamp':<22} {'Product':<20} {'Underlier':<20} "
          f"{'Notional':>14} {'Clr':>4}")
    print(f"  {'-' * 22} {'-' * 20} {'-' * 20} {'-' * 14} {'-' * 4}")
    for row in display:
        ts = _safe_str(row, COL_EXEC_TS, "")[:19]
        prod = _classify_product(row)[:20]
        ul = _underlier_name(row)[:20]
        clr = "Y" if _is_cleared(row) else "N"
        print(f"  {ts:<22} {prod:<20} {ul:<20} "
              f"{_fmt_notional(_notional(row)):>14} {clr:>4}")
    if len(results) > max_display:
        print(f"\n  ... showing {max_display} of {len(results)} results")
    total = sum(_notional(r) for r in results)
    print(f"\n  Total Notional: {_fmt_notional(total)}")
    print()


# --- Commands -----------------------------------------------------------------

def _resolve_date(date_str):
    d = _parse_date_field(date_str) if date_str else _most_recent_business_day()
    return d if d else _most_recent_business_day()

def cmd_latest(asset_class="rates", source="cftc", as_json=False, export_fmt=None):
    d = _most_recent_business_day()
    print(f"\n  Downloading {ASSET_CLASSES[asset_class]['display']} for {d}...")
    rows, d = _download_with_fallback(asset_class, d, source=source)
    if rows is None:
        print("  [no data available for recent dates]")
        return None
    summary = _summarize_day(rows, asset_class)
    if as_json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        _display_summary(summary, d.strftime("%Y-%m-%d"))
    if export_fmt:
        _do_export(rows, f"dtcc_{asset_class}_latest", export_fmt)
    return summary

def cmd_history(asset_class="rates", days=5, source="cftc",
                as_json=False, export_fmt=None):
    bdays = _business_days_back(days)
    ac_display = ASSET_CLASSES[asset_class]["display"]
    print(f"\n  Downloading {days} days of {ac_display}...")
    data_by_date = {}
    for i, d in enumerate(reversed(bdays), 1):
        ds = d.strftime("%Y-%m-%d")
        print(f"  [{i}/{days}] Downloading {ds} {asset_class}...")
        rows = _download_day(asset_class, d, source=source)
        if rows is not None:
            data_by_date[ds] = rows
    if not data_by_date:
        print("  [no data available]")
        return None
    print(f"\n  {ac_display} -- {len(data_by_date)} days with data")
    print("  " + "=" * 55)
    print(f"  {'Date':<12} {'Trades':>8} {'Notional':>14} {'Cleared %':>10}")
    print(f"  {'-' * 12} {'-' * 8} {'-' * 14} {'-' * 10}")
    all_summaries = []
    for ds in sorted(data_by_date.keys()):
        s = _summarize_day(data_by_date[ds], asset_class)
        all_summaries.append({"date": ds, **s})
        print(f"  {ds:<12} {s['trade_count']:>8,} "
              f"{_fmt_notional(s['total_notional']):>14} {s['cleared_pct']:>9.1f}%")
    print()
    if as_json:
        print(json.dumps(all_summaries, indent=2, default=str))
    if export_fmt:
        flat = []
        for ds, rows in data_by_date.items():
            for row in rows:
                row["_download_date"] = ds
                flat.append(row)
        _do_export(flat, f"dtcc_{asset_class}_history", export_fmt)
    return all_summaries

def cmd_rates(date_str=None, source="cftc", as_json=False, export_fmt=None):
    d = _resolve_date(date_str)
    print(f"\n  Downloading rates for {d}...")
    rows, d = _download_with_fallback("rates", d, source=source)
    if rows is None:
        print("  [no rates data available]")
        return None
    analysis = _rates_analysis(rows)
    if as_json:
        print(json.dumps(analysis, indent=2, default=str))
    else:
        _display_rates(analysis)
    if export_fmt:
        _do_export(rows, f"dtcc_rates_{d.strftime('%Y-%m-%d')}", export_fmt)
    return analysis

def cmd_credits(date_str=None, source="cftc", as_json=False, export_fmt=None):
    d = _resolve_date(date_str)
    print(f"\n  Downloading credits for {d}...")
    rows, d = _download_with_fallback("credits", d, source=source)
    if rows is None:
        print("  [no credits data available]")
        return None
    analysis = _credits_analysis(rows)
    if as_json:
        print(json.dumps(analysis, indent=2, default=str))
    else:
        _display_credits(analysis)
    if export_fmt:
        _do_export(rows, f"dtcc_credits_{d.strftime('%Y-%m-%d')}", export_fmt)
    return analysis

def cmd_fx(date_str=None, source="cftc", as_json=False, export_fmt=None):
    d = _resolve_date(date_str)
    print(f"\n  Downloading FX for {d}...")
    rows, d = _download_with_fallback("fx", d, source=source)
    if rows is None:
        print("  [no FX data available]")
        return None
    analysis = _fx_analysis(rows)
    if as_json:
        print(json.dumps(analysis, indent=2, default=str))
    else:
        _display_fx(analysis)
    if export_fmt:
        _do_export(rows, f"dtcc_fx_{d.strftime('%Y-%m-%d')}", export_fmt)
    return analysis

def cmd_commodities(date_str=None, source="cftc", as_json=False, export_fmt=None):
    d = _resolve_date(date_str)
    print(f"\n  Downloading commodities for {d}...")
    rows, d = _download_with_fallback("commodities", d, source=source)
    if rows is None:
        print("  [no commodities data available]")
        return None
    analysis = _commodity_analysis(rows)
    if as_json:
        print(json.dumps(analysis, indent=2, default=str))
    else:
        _display_commodities(analysis)
    if export_fmt:
        _do_export(rows, f"dtcc_commodities_{d.strftime('%Y-%m-%d')}", export_fmt)
    return analysis

def cmd_volume(asset_class="rates", days=20, source="cftc",
               as_json=False, export_fmt=None):
    bdays = _business_days_back(days)
    ac_display = ASSET_CLASSES[asset_class]["display"]
    print(f"\n  Building {days}-day volume series for {ac_display}...")
    data_by_date = {}
    for i, d in enumerate(reversed(bdays), 1):
        ds = d.strftime("%Y-%m-%d")
        print(f"  [{i}/{days}] Downloading {ds} {asset_class}...")
        rows = _download_day(asset_class, d, source=source)
        if rows is not None:
            data_by_date[ds] = rows
    if not data_by_date:
        print("  [no data available]")
        return None
    series = _volume_series(data_by_date)
    if as_json:
        print(json.dumps(series, indent=2, default=str))
    else:
        _display_volume_series(series, asset_class)
    if export_fmt:
        _do_export(series, f"dtcc_{asset_class}_volume", export_fmt)
    return series

def cmd_summary(date_str=None, source="cftc", as_json=False, export_fmt=None):
    d = _resolve_date(date_str)
    actual_date = d.strftime("%Y-%m-%d")
    print(f"\n  Cross-Asset Summary for {actual_date}")
    print("  " + "=" * 60)
    all_summaries = {}
    for ac in ASSET_CLASSES:
        print(f"  Downloading {ac}...")
        rows = _download_day(ac, d, source=source)
        if rows is not None:
            all_summaries[ac] = _summarize_day(rows, ac)
    if not all_summaries:
        d = _prev_business_day(d)
        actual_date = d.strftime("%Y-%m-%d")
        print(f"  [no data, trying {actual_date}...]")
        for ac in ASSET_CLASSES:
            rows = _download_day(ac, d, source=source)
            if rows is not None:
                all_summaries[ac] = _summarize_day(rows, ac)
    if not all_summaries:
        print("  [no data available]")
        return None
    if as_json:
        print(json.dumps(all_summaries, indent=2, default=str))
    else:
        print(f"\n  CROSS-ASSET OTC DERIVATIVE FLOWS -- {actual_date}")
        print("  " + "=" * 65)
        print(f"  {'Asset Class':<18} {'Trades':>8} {'Notional':>14} {'Cleared':>8}")
        print(f"  {'-' * 18} {'-' * 8} {'-' * 14} {'-' * 8}")
        grand_trades, grand_notional = 0, 0.0
        for ac, s in all_summaries.items():
            display = ASSET_CLASSES[ac]["display"]
            grand_trades += s["trade_count"]
            grand_notional += s["total_notional"]
            print(f"  {display:<18} {s['trade_count']:>8,} "
                  f"{_fmt_notional(s['total_notional']):>14} {s['cleared_pct']:>7.1f}%")
        print(f"  {'-' * 18} {'-' * 8} {'-' * 14} {'-' * 8}")
        print(f"  {'TOTAL':<18} {grand_trades:>8,} {_fmt_notional(grand_notional):>14}")
        print()
    if export_fmt:
        flat = [{"asset_class": ac, "trade_count": s["trade_count"],
                 "total_notional": s["total_notional"],
                 "cleared_pct": round(s["cleared_pct"], 1)}
                for ac, s in all_summaries.items()]
        _do_export(flat, "dtcc_summary", export_fmt)
    return all_summaries

def cmd_search(asset_class="rates", underlier=None, currency=None,
               product=None, date_str=None, source="cftc",
               as_json=False, export_fmt=None):
    d = _resolve_date(date_str)
    filters = []
    if underlier:
        filters.append(f"underlier={underlier}")
    if currency:
        filters.append(f"currency={currency}")
    if product:
        filters.append(f"product={product}")
    desc = ", ".join(filters) if filters else "no filter"
    print(f"\n  Searching {asset_class} trades for {d} ({desc})...")
    rows, d = _download_with_fallback(asset_class, d, source=source)
    if rows is None:
        print("  [no data available]")
        return None
    results = _search_trades(rows, underlier=underlier, currency=currency,
                             product=product)
    if as_json:
        print(json.dumps(results[:100], indent=2, default=str))
    else:
        _display_search_results(results)
    if export_fmt:
        _do_export(results, f"dtcc_search_{asset_class}", export_fmt)
    return results

def cmd_assets(as_json=False):
    if as_json:
        print(json.dumps(ASSET_CLASSES, indent=2))
        return ASSET_CLASSES
    print("\n  DTCC PPD -- Available Asset Classes")
    print("  " + "=" * 55)
    print(f"\n  {'Alias':<14} {'S3 Name':<14} {'Display':<22}")
    print(f"  {'-' * 14} {'-' * 14} {'-' * 22}")
    for alias, info in ASSET_CLASSES.items():
        print(f"  {alias:<14} {info['s3_name']:<14} {info['display']:<22}")
    print(f"\n  Data sources: CFTC (default), SEC")
    print(f"  SEC covers: credits, equities only (securities-based swaps)")
    print(f"\n  URL: {{base}}/{{source}}/eod/{{SOURCE}}_CUMULATIVE_{{CLASS}}_{{YYYY_MM_DD}}.zip")
    print(f"  Base: {S3_BASE_URL}")
    print(f"\n  PRODUCT TYPES (derived from UPI FISN)")
    type_map = {
        "rates":       "OIS Swap, Fixed-Float Swap, Basis Swap, Option/Swaption, Forward/FRA, Cap/Floor",
        "credits":     "Single Name CDS, Index CDS, Index Tranche, Credit Swap, Total Return Swap",
        "fx":          "NDF, Forward/FRA, Option/Swaption",
        "equities":    "Other, Variance Swap, Portfolio Swap, Option/Swaption",
        "commodities": "Other, Option/Swaption, Forward/FRA",
    }
    for ac, types in type_map.items():
        print(f"    {ac:<14} {types}")
    print()
    return ASSET_CLASSES

def cmd_cleared(asset_class="rates", date_str=None, source="cftc",
                as_json=False, export_fmt=None):
    d = _resolve_date(date_str)
    print(f"\n  Downloading {asset_class} for clearing analysis...")
    rows, d = _download_with_fallback(asset_class, d, source=source)
    if rows is None:
        print("  [no data available]")
        return None
    analysis = _cleared_analysis(rows)
    if as_json:
        print(json.dumps(analysis, indent=2, default=str))
    else:
        _display_cleared(analysis, asset_class)
    if export_fmt:
        flat = [{"product": prod, **data}
                for prod, data in analysis["by_product"].items()]
        _do_export(flat, f"dtcc_{asset_class}_cleared", export_fmt)
    return analysis

def cmd_export(asset_class="rates", days=1, source="cftc", fmt="csv"):
    bdays = _business_days_back(days)
    print(f"\n  Exporting {days} day(s) of {ASSET_CLASSES[asset_class]['display']}...")
    all_rows = []
    for i, d in enumerate(reversed(bdays), 1):
        ds = d.strftime("%Y-%m-%d")
        print(f"  [{i}/{days}] Downloading {ds}...")
        rows = _download_day(asset_class, d, source=source)
        if rows is not None:
            for row in rows:
                row["_download_date"] = ds
            all_rows.extend(rows)
    if not all_rows:
        print("  [no data to export]")
        return
    print(f"  {len(all_rows)} total records")
    _do_export(all_rows, f"dtcc_{asset_class}_raw", fmt)


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   DTCC Swap Data Repository -- OTC Flow Client
  =====================================================

   OVERVIEW
     1) latest         Latest day summary for an asset class
     2) history        Multi-day volume/count trends
     3) summary        Cross-asset summary for a date

   ASSET-SPECIFIC
     4) rates          Interest rate swap analysis
     5) credits        Credit default swap analysis
     6) fx             FX derivative analysis
     7) commodities    Commodity swap analysis

   ANALYTICS
     8) volume         Notional volume time series
     9) cleared        Clearing rate analysis
    10) search         Search trades by underlier/currency

   DATA
    11) assets         List available asset classes
    12) export         Export raw data

   q) quit
"""

def _i_latest():
    ac = _prompt_asset_class()
    src = _prompt_source()
    cmd_latest(asset_class=ac, source=src)

def _i_history():
    ac = _prompt_asset_class()
    days = _prompt("Number of business days", "5")
    src = _prompt_source()
    cmd_history(asset_class=ac, days=int(days), source=src)

def _i_summary():
    ds = _prompt("Date (YYYY-MM-DD, blank for latest)", "")
    src = _prompt_source()
    cmd_summary(date_str=ds or None, source=src)

def _i_rates():
    ds = _prompt("Date (YYYY-MM-DD, blank for latest)", "")
    src = _prompt_source()
    cmd_rates(date_str=ds or None, source=src)

def _i_credits():
    ds = _prompt("Date (YYYY-MM-DD, blank for latest)", "")
    src = _prompt_source()
    cmd_credits(date_str=ds or None, source=src)

def _i_fx():
    ds = _prompt("Date (YYYY-MM-DD, blank for latest)", "")
    src = _prompt_source()
    cmd_fx(date_str=ds or None, source=src)

def _i_commodities():
    ds = _prompt("Date (YYYY-MM-DD, blank for latest)", "")
    src = _prompt_source()
    cmd_commodities(date_str=ds or None, source=src)

def _i_volume():
    ac = _prompt_asset_class()
    days = _prompt("Number of business days", "20")
    src = _prompt_source()
    cmd_volume(asset_class=ac, days=int(days), source=src)

def _i_cleared():
    ac = _prompt_asset_class()
    ds = _prompt("Date (YYYY-MM-DD, blank for latest)", "")
    src = _prompt_source()
    cmd_cleared(asset_class=ac, date_str=ds or None, source=src)

def _i_search():
    ac = _prompt_asset_class()
    print("  Filter by: underlier, currency, or product type")
    underlier = _prompt("Underlier name (blank to skip)", "")
    currency = _prompt("Currency (blank to skip)", "")
    product = _prompt("Product type (blank to skip)", "")
    src = _prompt_source()
    cmd_search(asset_class=ac, underlier=underlier or None,
               currency=currency or None, product=product or None,
               source=src)

def _i_assets():
    cmd_assets()

def _i_export():
    ac = _prompt_asset_class()
    days = _prompt("Number of business days", "1")
    src = _prompt_source()
    fmt = _prompt_choice("Format", ["csv", "json"], "csv")
    cmd_export(asset_class=ac, days=int(days), source=src, fmt=fmt)

COMMAND_MAP = {
    "1": _i_latest, "2": _i_history, "3": _i_summary,
    "4": _i_rates, "5": _i_credits, "6": _i_fx, "7": _i_commodities,
    "8": _i_volume, "9": _i_cleared, "10": _i_search,
    "11": _i_assets, "12": _i_export,
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

VALID_ASSET_CLASSES = list(ASSET_CLASSES.keys())
VALID_SOURCES = ["cftc", "sec"]

def build_argparse():
    p = argparse.ArgumentParser(
        prog="dtcc.py",
        description="DTCC Swap Data Repository -- OTC Derivative Flow Client",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("latest", help="Latest day summary")
    s.add_argument("--asset-class", choices=VALID_ASSET_CLASSES, default="rates")
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("history", help="Multi-day trends")
    s.add_argument("--asset-class", choices=VALID_ASSET_CLASSES, default="rates")
    s.add_argument("--days", type=int, default=5)
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("rates", help="Interest rate swap analysis")
    s.add_argument("--date", help="Date YYYY-MM-DD")
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("credits", help="Credit default swap analysis")
    s.add_argument("--date", help="Date YYYY-MM-DD")
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("fx", help="FX derivative analysis")
    s.add_argument("--date", help="Date YYYY-MM-DD")
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("commodities", help="Commodity swap analysis")
    s.add_argument("--date", help="Date YYYY-MM-DD")
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("volume", help="Notional volume time series")
    s.add_argument("--asset-class", choices=VALID_ASSET_CLASSES, default="rates")
    s.add_argument("--days", type=int, default=20)
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("summary", help="Cross-asset summary")
    s.add_argument("--date", help="Date YYYY-MM-DD")
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("search", help="Search trades")
    s.add_argument("--asset-class", choices=VALID_ASSET_CLASSES, default="rates")
    s.add_argument("--underlier", help="Underlier name filter")
    s.add_argument("--currency", help="Currency filter")
    s.add_argument("--product", help="Product type filter")
    s.add_argument("--date", help="Date YYYY-MM-DD")
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("assets", help="List asset classes")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("cleared", help="Clearing rate analysis")
    s.add_argument("--asset-class", choices=VALID_ASSET_CLASSES, default="rates")
    s.add_argument("--date", help="Date YYYY-MM-DD")
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("export", help="Export raw data")
    s.add_argument("--asset-class", choices=VALID_ASSET_CLASSES, default="rates")
    s.add_argument("--days", type=int, default=1)
    s.add_argument("--source", choices=VALID_SOURCES, default="cftc")
    s.add_argument("--format", choices=["csv", "json"], default="csv")

    return p

def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)
    ac = getattr(args, "asset_class", "rates")
    src = getattr(args, "source", "cftc")
    dt = getattr(args, "date", None)

    if args.command == "latest":
        cmd_latest(asset_class=ac, source=src, as_json=j, export_fmt=exp)
    elif args.command == "history":
        cmd_history(asset_class=ac, days=args.days, source=src, as_json=j, export_fmt=exp)
    elif args.command == "rates":
        cmd_rates(date_str=dt, source=src, as_json=j, export_fmt=exp)
    elif args.command == "credits":
        cmd_credits(date_str=dt, source=src, as_json=j, export_fmt=exp)
    elif args.command == "fx":
        cmd_fx(date_str=dt, source=src, as_json=j, export_fmt=exp)
    elif args.command == "commodities":
        cmd_commodities(date_str=dt, source=src, as_json=j, export_fmt=exp)
    elif args.command == "volume":
        cmd_volume(asset_class=ac, days=args.days, source=src, as_json=j, export_fmt=exp)
    elif args.command == "summary":
        cmd_summary(date_str=dt, source=src, as_json=j, export_fmt=exp)
    elif args.command == "search":
        cmd_search(asset_class=ac, underlier=args.underlier, currency=args.currency,
                   product=args.product, date_str=dt, source=src,
                   as_json=j, export_fmt=exp)
    elif args.command == "assets":
        cmd_assets(as_json=j)
    elif args.command == "cleared":
        cmd_cleared(asset_class=ac, date_str=dt, source=src, as_json=j, export_fmt=exp)
    elif args.command == "export":
        cmd_export(asset_class=ac, days=args.days, source=src, fmt=args.format)


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
