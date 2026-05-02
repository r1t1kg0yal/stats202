#!/usr/bin/env python3
"""
EIA Electricity Grid -- Real-Time Demand & Generation Client

Single-script client for the EIA API v2 (api.eia.gov/v2). Tracks real-time and
historical U.S. electricity demand by balancing authority, generation by fuel
source, and interchange between grid regions. 14 curated balancing authorities
across 4 macro groups as industrial activity / economic nowcast signals.
Requires EIA_API_KEY env var (free at https://www.eia.gov/opendata/register.php).

Usage:
    python electricity.py                                          # interactive CLI
    python electricity.py demand --region PJM --hours 48           # hourly demand
    python electricity.py generation --region CISO                 # generation by fuel
    python electricity.py interchange --from PJM --to NYIS         # power flow
    python electricity.py regions                                  # list balancing auths
    python electricity.py snapshot                                 # Big 7 demand snapshot
    python electricity.py compare --regions PJM MISO ERCO          # compare regions
    python electricity.py fuel-mix --region ERCO                   # fuel % breakdown
    python electricity.py demand-history --region PJM --days 7     # daily demand totals
    python electricity.py peak --region CISO --days 3              # peak demand hour
    python electricity.py groups                                   # macro region groups
    python electricity.py group-snapshot --group industrial_belt   # group demand snapshot
    python electricity.py export --target demand --region PJM      # export to file
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests


# --- Configuration ------------------------------------------------------------

BASE_URL = "https://api.eia.gov/v2"
SESSION = requests.Session()
API_KEY = os.environ.get("EIA_API_KEY", "")

REGIONS = {
    "PJM":  {"name": "PJM Interconnection", "area": "Mid-Atlantic + Midwest", "states": "PA, NJ, DE, MD, VA, WV, OH, IN, IL, MI, KY, NC, TN, DC"},
    "MISO": {"name": "Midcontinent ISO", "area": "Central US", "states": "MN, WI, IA, MO, AR, MS, LA, IN, MI, MT, ND, SD"},
    "ERCO": {"name": "ERCOT (Texas)", "area": "Texas", "states": "TX"},
    "CISO": {"name": "California ISO", "area": "California", "states": "CA"},
    "ISNE": {"name": "ISO New England", "area": "New England", "states": "CT, ME, MA, NH, RI, VT"},
    "NYIS": {"name": "New York ISO", "area": "New York", "states": "NY"},
    "SWPP": {"name": "Southwest Power Pool", "area": "Central Plains", "states": "KS, OK, NE, parts of NM, TX, AR, LA, MO"},
    "SOCO": {"name": "Southern Company", "area": "Southeast", "states": "AL, GA, parts of MS, FL"},
    "TVA":  {"name": "Tennessee Valley Authority", "area": "Tennessee Valley", "states": "TN, AL, MS, KY, GA, NC, VA"},
    "BPAT": {"name": "Bonneville Power Admin", "area": "Pacific Northwest", "states": "WA, OR, ID, MT"},
    "WACM": {"name": "Western Area (Colorado/Missouri)", "area": "Western", "states": "CO, NE, WY, MT, SD, ND, MN, IA"},
    "FPL":  {"name": "Florida Power & Light", "area": "Florida", "states": "FL"},
    "DUK":  {"name": "Duke Energy Carolinas", "area": "Carolinas", "states": "NC, SC"},
    "AEC":  {"name": "PowerSouth Energy", "area": "Alabama", "states": "AL"},
}

FUEL_TYPES = {
    "COL": "Coal",
    "NG":  "Natural Gas",
    "NUC": "Nuclear",
    "SUN": "Solar",
    "WND": "Wind",
    "WAT": "Hydro",
    "OIL": "Petroleum",
    "OTH": "Other",
    "ALL": "All Sources",
}

MACRO_GROUPS = {
    "big_seven": {
        "label": "Big 7 RTOs/ISOs",
        "regions": ["PJM", "MISO", "ERCO", "CISO", "ISNE", "NYIS", "SWPP"],
    },
    "industrial_belt": {
        "label": "Industrial Belt (manufacturing proxy)",
        "regions": ["PJM", "MISO", "TVA"],
    },
    "sun_belt": {
        "label": "Sun Belt (growth proxy)",
        "regions": ["ERCO", "SOCO", "FPL"],
    },
    "tech_corridor": {
        "label": "Tech Corridor",
        "regions": ["CISO", "ISNE", "NYIS", "PJM"],
    },
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# --- HTTP Layer ---------------------------------------------------------------

def _request(endpoint, params=None, max_retries=3):
    url = f"{BASE_URL}{endpoint}"
    if params is None:
        params = {}
    params["api_key"] = API_KEY
    for attempt in range(max_retries):
        try:
            r = SESSION.get(url, params=params, timeout=30)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  [rate limited, waiting {wait}s...]")
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                print(f"  [API error {r.status_code}: {r.text[:200]}]")
                return None
            time.sleep(0.2)
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


# --- Data Fetchers ------------------------------------------------------------

def _time_range(hours):
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    return start.strftime("%Y-%m-%dT%H"), end.strftime("%Y-%m-%dT%H")


def _fetch_demand(region, hours=24):
    start, end = _time_range(hours)
    params = {
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": region,
        "facets[type][]": "D",
        "start": start,
        "end": end,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": str(min(hours, 5000)),
    }
    data = _request("/electricity/rto/region-data/data/", params)
    if not data:
        return []
    return data.get("response", {}).get("data", [])


def _fetch_generation(region, hours=24):
    start, end = _time_range(hours)
    params = {
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": region,
        "start": start,
        "end": end,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": str(min(hours * 10, 5000)),
    }
    data = _request("/electricity/rto/fuel-type-data/data/", params)
    if not data:
        return []
    return data.get("response", {}).get("data", [])


def _fetch_interchange(from_ba, to_ba, hours=24):
    start, end = _time_range(hours)
    params = {
        "frequency": "hourly",
        "data[0]": "value",
        "facets[fromba][]": from_ba,
        "facets[toba][]": to_ba,
        "start": start,
        "end": end,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": str(min(hours, 5000)),
    }
    data = _request("/electricity/rto/interchange-data/data/", params)
    if not data:
        return []
    return data.get("response", {}).get("data", [])


def _fetch_fuel_mix(region, hours=24):
    rows = _fetch_generation(region, hours)
    if not rows:
        return []
    latest_period = rows[0].get("period", "") if rows else ""
    return [r for r in rows if r.get("period") == latest_period]


# --- Parsing Helpers ----------------------------------------------------------

def _parse_period(period_str):
    if not period_str:
        return "N/A"
    try:
        if "T" in period_str:
            dt = datetime.strptime(period_str, "%Y-%m-%dT%H")
            return dt.strftime("%Y-%m-%d %H:00")
        return period_str
    except (ValueError, TypeError):
        return str(period_str)


def _truncate(text, length=40):
    if not text:
        return ""
    text = str(text).strip()
    return text[:length - 3] + "..." if len(text) > length else text


def _format_mwh(value):
    if value is None:
        return "N/A"
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


# --- Display Functions --------------------------------------------------------

def _display_demand_table(data, region, title=None):
    if not data:
        print(f"  [no demand data for {region}]")
        return
    label = title or f"HOURLY DEMAND: {region} ({REGIONS.get(region, {}).get('name', '')})"
    print(f"\n  {label}")
    print("  " + "=" * 55)
    print(f"  {'Period':<20} {'Demand (MWh)':>14} {'Region':>10}")
    print(f"  {'-'*20} {'-'*14} {'-'*10}")
    total = 0
    for row in data:
        period = _parse_period(row.get("period", ""))
        value = _safe_int(row.get("value"))
        total += value
        print(f"  {period:<20} {_format_mwh(value):>14} {region:>10}")
    if len(data) > 1:
        avg = total / len(data)
        print(f"  {'-'*20} {'-'*14} {'-'*10}")
        print(f"  {'Total':<20} {_format_mwh(total):>14}")
        print(f"  {'Avg/hour':<20} {_format_mwh(avg):>14}")
    print(f"\n  --- {len(data)} data points ---\n")


def _display_generation_table(data, region):
    if not data:
        print(f"  [no generation data for {region}]")
        return
    by_fuel = {}
    for row in data:
        ft = row.get("fueltype", row.get("type-name", "UNK"))
        val = _safe_int(row.get("value"))
        period = row.get("period", "")
        if ft not in by_fuel:
            by_fuel[ft] = {"total": 0, "count": 0, "latest_period": period}
        by_fuel[ft]["total"] += val
        by_fuel[ft]["count"] += 1

    print(f"\n  GENERATION BY FUEL TYPE: {region}")
    print("  " + "=" * 60)
    print(f"  {'Fuel Type':<12} {'Total MWh':>14} {'Hours':>6} {'Avg/hr':>12}")
    print(f"  {'-'*12} {'-'*14} {'-'*6} {'-'*12}")
    grand = 0
    for ft in sorted(by_fuel.keys()):
        info = by_fuel[ft]
        avg = info["total"] / info["count"] if info["count"] > 0 else 0
        grand += info["total"]
        name = FUEL_TYPES.get(ft, ft)[:12]
        print(f"  {name:<12} {_format_mwh(info['total']):>14} "
              f"{info['count']:>6} {_format_mwh(avg):>12}")
    print(f"  {'-'*12} {'-'*14} {'-'*6} {'-'*12}")
    print(f"  {'TOTAL':<12} {_format_mwh(grand):>14}")
    print()


def _display_fuel_mix(mix_data, region):
    if not mix_data:
        print(f"  [no fuel mix data for {region}]")
        return
    period = mix_data[0].get("period", "") if mix_data else ""
    total = sum(_safe_int(r.get("value")) for r in mix_data)
    print(f"\n  FUEL MIX: {region} -- {_parse_period(period)}")
    print("  " + "=" * 50)
    print(f"  {'Fuel Type':<16} {'MWh':>12} {'Share':>8}")
    print(f"  {'-'*16} {'-'*12} {'-'*8}")
    ranked = sorted(mix_data, key=lambda r: _safe_int(r.get("value")), reverse=True)
    for row in ranked:
        ft = row.get("fueltype", row.get("type-name", "UNK"))
        val = _safe_int(row.get("value"))
        pct = (val / total * 100) if total > 0 else 0
        name = FUEL_TYPES.get(ft, ft)
        print(f"  {name:<16} {_format_mwh(val):>12} {pct:>7.1f}%")
    print(f"  {'-'*16} {'-'*12} {'-'*8}")
    print(f"  {'TOTAL':<16} {_format_mwh(total):>12} {'100.0%':>8}")
    print()


def _display_interchange(data, from_ba, to_ba):
    if not data:
        print(f"  [no interchange data for {from_ba} -> {to_ba}]")
        return
    print(f"\n  INTERCHANGE: {from_ba} -> {to_ba}")
    print("  " + "=" * 50)
    print(f"  {'Period':<20} {'Flow (MWh)':>14}")
    print(f"  {'-'*20} {'-'*14}")
    total = 0
    for row in data:
        period = _parse_period(row.get("period", ""))
        value = _safe_int(row.get("value"))
        total += value
        sign = "+" if value >= 0 else ""
        print(f"  {period:<20} {sign}{_format_mwh(value):>13}")
    if len(data) > 1:
        avg = total / len(data)
        print(f"  {'-'*20} {'-'*14}")
        print(f"  {'Net Total':<20} {_format_mwh(total):>14}")
        print(f"  {'Avg/hour':<20} {_format_mwh(avg):>14}")
    print(f"\n  Positive = flow FROM {from_ba} TO {to_ba}")
    print(f"  --- {len(data)} data points ---\n")


def _display_snapshot(snapshot_data):
    if not snapshot_data:
        print("  [no snapshot data]")
        return
    print(f"\n  DEMAND SNAPSHOT -- Big 7 RTOs/ISOs")
    print("  " + "=" * 65)
    print(f"  {'Region':<8} {'Name':<30} {'Latest MWh':>14} {'Period':<18}")
    print(f"  {'-'*8} {'-'*30} {'-'*14} {'-'*18}")
    grand = 0
    for entry in snapshot_data:
        region = entry["region"]
        name = _truncate(REGIONS.get(region, {}).get("name", ""), 29)
        val = entry.get("value", 0)
        period = _parse_period(entry.get("period", ""))
        grand += val
        print(f"  {region:<8} {name:<30} {_format_mwh(val):>14} {period:<18}")
    print(f"  {'-'*8} {'-'*30} {'-'*14}")
    print(f"  {'TOTAL':<8} {'':<30} {_format_mwh(grand):>14}")
    print()


def _display_regions():
    print(f"\n  CURATED BALANCING AUTHORITIES ({len(REGIONS)} regions)")
    print("  " + "=" * 95)
    print(f"  {'Code':<6} {'Name':<32} {'Area':<24} {'States'}")
    print(f"  {'-'*6} {'-'*32} {'-'*24} {'-'*30}")
    for code, info in REGIONS.items():
        print(f"  {code:<6} {info['name']:<32} {info['area']:<24} {info['states']}")
    print()


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
            data = [data] if data else []
        _export_csv(data, path)


# --- Command Functions --------------------------------------------------------

def cmd_demand(region="PJM", hours=24, as_json=False, export_fmt=None):
    if not API_KEY:
        print("  [EIA_API_KEY not set -- export it as an env var]")
        return
    print(f"\n  Fetching {hours}h demand for {region}...")
    data = _fetch_demand(region, hours)
    if not data:
        print(f"  [no demand data for {region}]")
        return
    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return
    _display_demand_table(data, region)
    if export_fmt:
        rows = [{"period": _parse_period(r.get("period")),
                 "region": region, "demand_mwh": _safe_int(r.get("value"))}
                for r in data]
        _do_export(rows, f"eia_demand_{region}", export_fmt)


def cmd_generation(region="PJM", hours=24, as_json=False, export_fmt=None):
    if not API_KEY:
        print("  [EIA_API_KEY not set -- export it as an env var]")
        return
    print(f"\n  Fetching {hours}h generation for {region}...")
    data = _fetch_generation(region, hours)
    if not data:
        print(f"  [no generation data for {region}]")
        return
    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return
    _display_generation_table(data, region)
    if export_fmt:
        rows = [{"period": _parse_period(r.get("period")),
                 "region": region,
                 "fuel_type": FUEL_TYPES.get(r.get("fueltype", ""), r.get("fueltype", "")),
                 "mwh": _safe_int(r.get("value"))}
                for r in data]
        _do_export(rows, f"eia_generation_{region}", export_fmt)


def cmd_interchange(from_ba="PJM", to_ba="NYIS", hours=24,
                    as_json=False, export_fmt=None):
    if not API_KEY:
        print("  [EIA_API_KEY not set -- export it as an env var]")
        return
    print(f"\n  Fetching {hours}h interchange {from_ba} -> {to_ba}...")
    data = _fetch_interchange(from_ba, to_ba, hours)
    if not data:
        print(f"  [no interchange data for {from_ba} -> {to_ba}]")
        return
    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return
    _display_interchange(data, from_ba, to_ba)
    if export_fmt:
        rows = [{"period": _parse_period(r.get("period")),
                 "from": from_ba, "to": to_ba,
                 "flow_mwh": _safe_int(r.get("value"))}
                for r in data]
        _do_export(rows, f"eia_interchange_{from_ba}_{to_ba}", export_fmt)


def cmd_regions(as_json=False):
    if as_json:
        print(json.dumps(REGIONS, indent=2))
        return
    _display_regions()


def cmd_snapshot(as_json=False, export_fmt=None):
    if not API_KEY:
        print("  [EIA_API_KEY not set -- export it as an env var]")
        return
    regions = MACRO_GROUPS["big_seven"]["regions"]
    total = len(regions)
    print(f"\n  Building demand snapshot ({total} regions)...")
    snapshot = []
    for i, region in enumerate(regions, 1):
        print(f"  [{i}/{total}] Fetching {region}...", flush=True)
        rows = _fetch_demand(region, hours=2)
        if rows:
            latest = rows[0]
            snapshot.append({
                "region": region,
                "value": _safe_int(latest.get("value")),
                "period": latest.get("period", ""),
            })
        else:
            snapshot.append({"region": region, "value": 0, "period": "N/A"})
    if as_json:
        print(json.dumps(snapshot, indent=2, default=str))
        return
    _display_snapshot(snapshot)
    if export_fmt:
        _do_export(snapshot, "eia_snapshot", export_fmt)


def cmd_compare(regions=None, hours=24, as_json=False, export_fmt=None):
    if not API_KEY:
        print("  [EIA_API_KEY not set -- export it as an env var]")
        return
    if not regions or len(regions) < 2:
        print("  [need at least 2 regions to compare]")
        return
    total = len(regions)
    print(f"\n  Comparing {total} regions ({hours}h)...")
    all_data = {}
    for i, region in enumerate(regions, 1):
        print(f"  [{i}/{total}] Fetching {region}...", flush=True)
        rows = _fetch_demand(region, hours)
        all_data[region] = rows or []

    if as_json:
        print(json.dumps(all_data, indent=2, default=str))
        return

    all_periods = set()
    for rows in all_data.values():
        for row in rows:
            all_periods.add(row.get("period", ""))
    periods_sorted = sorted(all_periods, reverse=True)

    period_map = {}
    for region, rows in all_data.items():
        for row in rows:
            period_map[(region, row.get("period", ""))] = _safe_int(row.get("value"))

    header_labels = [r[:8] for r in regions]
    print(f"\n  DEMAND COMPARISON ({hours}h)")
    print("  " + "=" * (20 + 14 * len(regions)))
    print(f"  {'Period':<20}" + "".join(f" {lbl:>12}" for lbl in header_labels))
    print(f"  {'-'*20}" + (" " + "-" * 12) * len(regions))

    for period in periods_sorted[:hours]:
        row_str = f"  {_parse_period(period):<20}"
        for region in regions:
            val = period_map.get((region, period), 0)
            row_str += f" {_format_mwh(val):>12}"
        print(row_str)

    print()
    totals_row = f"  {'TOTAL':<20}"
    avg_row = f"  {'AVG':<20}"
    for region in regions:
        rows = all_data[region]
        total_val = sum(_safe_int(r.get("value")) for r in rows)
        avg_val = total_val / len(rows) if rows else 0
        totals_row += f" {_format_mwh(total_val):>12}"
        avg_row += f" {_format_mwh(avg_val):>12}"
    print(totals_row)
    print(avg_row)
    print()

    if export_fmt:
        flat = []
        for region, rows in all_data.items():
            for r in rows:
                flat.append({"period": _parse_period(r.get("period")),
                             "region": region,
                             "demand_mwh": _safe_int(r.get("value"))})
        _do_export(flat, "eia_compare", export_fmt)


def cmd_fuel_mix(region="PJM", hours=24, as_json=False, export_fmt=None):
    if not API_KEY:
        print("  [EIA_API_KEY not set -- export it as an env var]")
        return
    print(f"\n  Fetching fuel mix for {region}...")
    mix = _fetch_fuel_mix(region, hours)
    if not mix:
        print(f"  [no fuel mix data for {region}]")
        return
    if as_json:
        print(json.dumps(mix, indent=2, default=str))
        return
    _display_fuel_mix(mix, region)
    if export_fmt:
        total = sum(_safe_int(r.get("value")) for r in mix)
        rows = []
        for r in mix:
            ft = r.get("fueltype", r.get("type-name", "UNK"))
            val = _safe_int(r.get("value"))
            pct = (val / total * 100) if total > 0 else 0
            rows.append({"region": region, "fuel_type": FUEL_TYPES.get(ft, ft),
                         "mwh": val, "pct": round(pct, 1)})
        _do_export(rows, f"eia_fuel_mix_{region}", export_fmt)


def cmd_demand_history(region="PJM", days=7, as_json=False, export_fmt=None):
    if not API_KEY:
        print("  [EIA_API_KEY not set -- export it as an env var]")
        return
    hours = days * 24
    print(f"\n  Fetching {days}-day demand history for {region} ({hours}h)...")
    data = _fetch_demand(region, hours)
    if not data:
        print(f"  [no demand data for {region}]")
        return

    by_day = {}
    for row in data:
        period = row.get("period", "")
        day_key = period[:10] if period else "unknown"
        val = _safe_int(row.get("value"))
        if day_key not in by_day:
            by_day[day_key] = {"total": 0, "count": 0, "peak": 0, "peak_hour": ""}
        by_day[day_key]["total"] += val
        by_day[day_key]["count"] += 1
        if val > by_day[day_key]["peak"]:
            by_day[day_key]["peak"] = val
            by_day[day_key]["peak_hour"] = period

    daily = [{"date": d, **info} for d, info in sorted(by_day.items())]

    if as_json:
        print(json.dumps(daily, indent=2, default=str))
        return

    rname = REGIONS.get(region, {}).get("name", "")
    print(f"\n  DAILY DEMAND HISTORY: {region} ({rname})")
    print("  " + "=" * 65)
    print(f"  {'Date':<12} {'Total MWh':>14} {'Hours':>6} {'Peak MWh':>12} {'Avg/hr':>12}")
    print(f"  {'-'*12} {'-'*14} {'-'*6} {'-'*12} {'-'*12}")
    grand = 0
    for d in daily:
        avg = d["total"] / d["count"] if d["count"] > 0 else 0
        grand += d["total"]
        print(f"  {d['date']:<12} {_format_mwh(d['total']):>14} "
              f"{d['count']:>6} {_format_mwh(d['peak']):>12} {_format_mwh(avg):>12}")
    if len(daily) > 1:
        avg_daily = grand / len(daily)
        print(f"  {'-'*12} {'-'*14} {'-'*6} {'-'*12} {'-'*12}")
        print(f"  {'Period Total':<12} {_format_mwh(grand):>14}")
        print(f"  {'Daily Avg':<12} {_format_mwh(avg_daily):>14}")
    print()

    if export_fmt:
        _do_export(daily, f"eia_demand_history_{region}", export_fmt)


def cmd_peak(region="PJM", days=3, as_json=False, export_fmt=None):
    if not API_KEY:
        print("  [EIA_API_KEY not set -- export it as an env var]")
        return
    hours = days * 24
    print(f"\n  Finding peak demand for {region} over {days} days...")
    data = _fetch_demand(region, hours)
    if not data:
        print(f"  [no demand data for {region}]")
        return

    peak_row = max(data, key=lambda r: _safe_int(r.get("value")))
    peak_val = _safe_int(peak_row.get("value"))
    peak_period = peak_row.get("period", "")
    avg_val = sum(_safe_int(r.get("value")) for r in data) / len(data)

    result = {
        "region": region,
        "peak_mwh": peak_val,
        "peak_period": _parse_period(peak_period),
        "avg_mwh": round(avg_val),
        "peak_vs_avg_pct": round((peak_val / avg_val - 1) * 100, 1) if avg_val > 0 else 0,
        "hours_analyzed": len(data),
        "days": days,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return

    rname = REGIONS.get(region, {}).get("name", "")
    print(f"\n  PEAK DEMAND: {region} ({rname})")
    print("  " + "=" * 50)
    print(f"  Peak Hour:       {result['peak_period']}")
    print(f"  Peak Demand:     {_format_mwh(peak_val)} MWh")
    print(f"  Average Demand:  {_format_mwh(result['avg_mwh'])} MWh")
    print(f"  Peak vs Avg:     +{result['peak_vs_avg_pct']}%")
    print(f"  Hours Analyzed:  {result['hours_analyzed']}")
    print()

    if export_fmt:
        _do_export(result, f"eia_peak_{region}", export_fmt)


def cmd_groups(as_json=False):
    if as_json:
        print(json.dumps(MACRO_GROUPS, indent=2))
        return
    print(f"\n  MACRO REGION GROUPS ({len(MACRO_GROUPS)} groups)")
    print("  " + "=" * 65)
    for key, grp in MACRO_GROUPS.items():
        label = grp["label"]
        members = grp["regions"]
        print(f"\n  {label} [{key}]")
        print(f"  {'-' * len(label)}")
        for code in members:
            info = REGIONS.get(code, {})
            name = info.get("name", "")
            area = info.get("area", "")
            print(f"    {code:<6} {name:<30} {area}")
    print()


def cmd_group_snapshot(group="industrial_belt", as_json=False, export_fmt=None):
    if not API_KEY:
        print("  [EIA_API_KEY not set -- export it as an env var]")
        return
    grp = MACRO_GROUPS.get(group)
    if not grp:
        print(f"  [unknown group: {group}]")
        print(f"  Available: {', '.join(MACRO_GROUPS.keys())}")
        return
    regions = grp["regions"]
    total = len(regions)
    print(f"\n  Building snapshot for {grp['label']} ({total} regions)...")
    snapshot = []
    for i, region in enumerate(regions, 1):
        print(f"  [{i}/{total}] Fetching {region}...", flush=True)
        rows = _fetch_demand(region, hours=2)
        if rows:
            latest = rows[0]
            snapshot.append({
                "region": region,
                "value": _safe_int(latest.get("value")),
                "period": latest.get("period", ""),
            })
        else:
            snapshot.append({"region": region, "value": 0, "period": "N/A"})

    if as_json:
        print(json.dumps(snapshot, indent=2, default=str))
        return

    print(f"\n  DEMAND SNAPSHOT -- {grp['label']}")
    print("  " + "=" * 65)
    print(f"  {'Region':<8} {'Name':<30} {'Latest MWh':>14} {'Period':<18}")
    print(f"  {'-'*8} {'-'*30} {'-'*14} {'-'*18}")
    grand = 0
    for entry in snapshot:
        r = entry["region"]
        name = _truncate(REGIONS.get(r, {}).get("name", ""), 29)
        val = entry["value"]
        period = _parse_period(entry.get("period", ""))
        grand += val
        print(f"  {r:<8} {name:<30} {_format_mwh(val):>14} {period:<18}")
    print(f"  {'-'*8} {'-'*30} {'-'*14}")
    print(f"  {'TOTAL':<8} {'':<30} {_format_mwh(grand):>14}")
    print()

    if export_fmt:
        _do_export(snapshot, f"eia_group_{group}", export_fmt)


def cmd_export(target="demand", region="PJM", hours=24, days=7,
               from_ba="PJM", to_ba="NYIS", group="industrial_belt", fmt="csv"):
    if not API_KEY:
        print("  [EIA_API_KEY not set -- export it as an env var]")
        return
    dispatch = {
        "demand":         lambda: cmd_demand(region=region, hours=hours, export_fmt=fmt),
        "generation":     lambda: cmd_generation(region=region, hours=hours, export_fmt=fmt),
        "interchange":    lambda: cmd_interchange(from_ba=from_ba, to_ba=to_ba, hours=hours, export_fmt=fmt),
        "fuel-mix":       lambda: cmd_fuel_mix(region=region, hours=hours, export_fmt=fmt),
        "demand-history": lambda: cmd_demand_history(region=region, days=days, export_fmt=fmt),
        "snapshot":       lambda: cmd_snapshot(export_fmt=fmt),
        "group-snapshot": lambda: cmd_group_snapshot(group=group, export_fmt=fmt),
        "peak":           lambda: cmd_peak(region=region, days=days, export_fmt=fmt),
    }
    if target not in dispatch:
        print(f"  [unknown export target: {target}]")
        print(f"  Available: {', '.join(dispatch.keys())}")
        return
    dispatch[target]()


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   EIA Electricity Grid -- Demand & Generation Client
  =====================================================

   DEMAND
     1) demand           Hourly demand for a region
     2) demand-history   Daily demand totals over N days
     3) peak             Find peak demand hour

   GENERATION
     4) generation       Generation by fuel type
     5) fuel-mix         Fuel mix percentage breakdown

   GRID
     6) interchange      Power flow between two regions
     7) snapshot         Big 7 demand snapshot
     8) compare          Compare demand across regions

   REFERENCE
     9) regions          List balancing authorities
    10) groups           Macro region groups
    11) group-snapshot   Demand snapshot for a group

   DATA
    12) export           Export data to file

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
    return _prompt(f"{msg} ({'/'.join(str(c) for c in choices)})", default)


def _prompt_region(default="PJM"):
    print(f"  Regions: {', '.join(REGIONS.keys())}")
    return _prompt("Region code", default).upper()


def _i_demand():
    region = _prompt_region()
    hours = int(_prompt("Hours", "24"))
    cmd_demand(region=region, hours=hours)


def _i_demand_history():
    region = _prompt_region()
    days = int(_prompt("Days", "7"))
    cmd_demand_history(region=region, days=days)


def _i_peak():
    region = _prompt_region()
    days = int(_prompt("Days to search", "3"))
    cmd_peak(region=region, days=days)


def _i_generation():
    region = _prompt_region()
    hours = int(_prompt("Hours", "24"))
    cmd_generation(region=region, hours=hours)


def _i_fuel_mix():
    region = _prompt_region()
    hours = int(_prompt("Lookback hours", "24"))
    cmd_fuel_mix(region=region, hours=hours)


def _i_interchange():
    print(f"  Regions: {', '.join(REGIONS.keys())}")
    from_ba = _prompt("From region", "PJM").upper()
    to_ba = _prompt("To region", "NYIS").upper()
    hours = int(_prompt("Hours", "24"))
    cmd_interchange(from_ba=from_ba, to_ba=to_ba, hours=hours)


def _i_snapshot():
    cmd_snapshot()


def _i_compare():
    print(f"  Regions: {', '.join(REGIONS.keys())}")
    raw = _prompt("Regions (comma-separated)", "PJM,MISO,ERCO")
    regions = [r.strip().upper() for r in raw.split(",") if r.strip()]
    if len(regions) < 2:
        print("  [need at least 2 regions]")
        return
    hours = int(_prompt("Hours", "24"))
    cmd_compare(regions=regions, hours=hours)


def _i_regions():
    cmd_regions()


def _i_groups():
    cmd_groups()


def _i_group_snapshot():
    print(f"  Groups: {', '.join(MACRO_GROUPS.keys())}")
    group = _prompt("Group name", "industrial_belt")
    cmd_group_snapshot(group=group)


def _i_export():
    targets = ["demand", "generation", "interchange", "fuel-mix",
               "demand-history", "snapshot", "group-snapshot", "peak"]
    print(f"  Targets: {', '.join(targets)}")
    target = _prompt("Export target", "demand")
    fmt = _prompt_choice("Format", ["csv", "json"], "csv")
    region = _prompt_region()
    if target == "interchange":
        to_ba = _prompt("To region", "NYIS").upper()
        hours = int(_prompt("Hours", "24"))
        cmd_export(target=target, from_ba=region, to_ba=to_ba, hours=hours, fmt=fmt)
    elif target in ("demand-history", "peak"):
        days = int(_prompt("Days", "7"))
        cmd_export(target=target, region=region, days=days, fmt=fmt)
    elif target == "group-snapshot":
        print(f"  Groups: {', '.join(MACRO_GROUPS.keys())}")
        group = _prompt("Group", "industrial_belt")
        cmd_export(target=target, group=group, fmt=fmt)
    elif target == "snapshot":
        cmd_export(target=target, fmt=fmt)
    else:
        hours = int(_prompt("Hours", "24"))
        cmd_export(target=target, region=region, hours=hours, fmt=fmt)


COMMAND_MAP = {
    "1":  _i_demand,
    "2":  _i_demand_history,
    "3":  _i_peak,
    "4":  _i_generation,
    "5":  _i_fuel_mix,
    "6":  _i_interchange,
    "7":  _i_snapshot,
    "8":  _i_compare,
    "9":  _i_regions,
    "10": _i_groups,
    "11": _i_group_snapshot,
    "12": _i_export,
}


def interactive_loop():
    if not API_KEY:
        print("\n  WARNING: EIA_API_KEY not set.")
        print("  Get a free key at https://www.eia.gov/opendata/register.php")
        print("  Then: export EIA_API_KEY=your_key_here\n")
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

VALID_REGIONS = list(REGIONS.keys())
VALID_GROUPS = list(MACRO_GROUPS.keys())
EXPORT_TARGETS = ["demand", "generation", "interchange", "fuel-mix",
                  "demand-history", "snapshot", "group-snapshot", "peak"]


def build_argparse():
    p = argparse.ArgumentParser(
        prog="electricity.py",
        description="EIA Electricity Grid -- Real-Time Demand & Generation Client",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("demand", help="Hourly demand for a region")
    s.add_argument("--region", default="PJM")
    s.add_argument("--hours", type=int, default=24)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("generation", help="Generation by fuel type")
    s.add_argument("--region", default="PJM")
    s.add_argument("--hours", type=int, default=24)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("interchange", help="Power flow between regions")
    s.add_argument("--from", dest="from_ba", default="PJM")
    s.add_argument("--to", dest="to_ba", default="NYIS")
    s.add_argument("--hours", type=int, default=24)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("regions", help="List balancing authorities")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("snapshot", help="Big 7 demand snapshot")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("compare", help="Compare demand across regions")
    s.add_argument("--regions", nargs="+", default=["PJM", "MISO", "ERCO"])
    s.add_argument("--hours", type=int, default=24)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("fuel-mix", help="Fuel mix percentage breakdown")
    s.add_argument("--region", default="PJM")
    s.add_argument("--hours", type=int, default=24)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("demand-history", help="Daily demand over N days")
    s.add_argument("--region", default="PJM")
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("peak", help="Peak demand hour over N days")
    s.add_argument("--region", default="PJM")
    s.add_argument("--days", type=int, default=3)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("groups", help="Show macro region groups")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("group-snapshot", help="Demand snapshot for a group")
    s.add_argument("--group", choices=VALID_GROUPS, default="industrial_belt")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("export", help="Export data to file")
    s.add_argument("--target", choices=EXPORT_TARGETS, default="demand")
    s.add_argument("--region", default="PJM")
    s.add_argument("--hours", type=int, default=24)
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--from", dest="from_ba", default="PJM")
    s.add_argument("--to", dest="to_ba", default="NYIS")
    s.add_argument("--group", choices=VALID_GROUPS, default="industrial_belt")
    s.add_argument("--format", choices=["csv", "json"], default="csv")

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "demand":
        cmd_demand(region=args.region, hours=args.hours, as_json=j, export_fmt=exp)
    elif args.command == "generation":
        cmd_generation(region=args.region, hours=args.hours, as_json=j, export_fmt=exp)
    elif args.command == "interchange":
        cmd_interchange(from_ba=args.from_ba, to_ba=args.to_ba,
                        hours=args.hours, as_json=j, export_fmt=exp)
    elif args.command == "regions":
        cmd_regions(as_json=j)
    elif args.command == "snapshot":
        cmd_snapshot(as_json=j, export_fmt=exp)
    elif args.command == "compare":
        cmd_compare(regions=args.regions, hours=args.hours, as_json=j, export_fmt=exp)
    elif args.command == "fuel-mix":
        cmd_fuel_mix(region=args.region, hours=args.hours, as_json=j, export_fmt=exp)
    elif args.command == "demand-history":
        cmd_demand_history(region=args.region, days=args.days, as_json=j, export_fmt=exp)
    elif args.command == "peak":
        cmd_peak(region=args.region, days=args.days, as_json=j, export_fmt=exp)
    elif args.command == "groups":
        cmd_groups(as_json=j)
    elif args.command == "group-snapshot":
        cmd_group_snapshot(group=args.group, as_json=j, export_fmt=exp)
    elif args.command == "export":
        cmd_export(target=args.target, region=args.region, hours=args.hours,
                   days=args.days, from_ba=args.from_ba, to_ba=args.to_ba,
                   group=args.group, fmt=args.format)


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
