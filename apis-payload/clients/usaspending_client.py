#!/usr/bin/env python3
"""
USASpending.gov -- Federal Spending & Fiscal Pulse Client

Single-script client for the USASpending.gov API (api.usaspending.gov/api/v2).
Tracks every federal dollar: contracts, grants, loans, direct payments.
17 curated macro-relevant agencies across 9 groups for fiscal impulse analysis.
No auth required.

Usage:
    python usaspending.py                              # interactive CLI
    python usaspending.py agencies                     # list top-tier agencies
    python usaspending.py agency treasury              # deep dive on Treasury
    python usaspending.py spending --fy 2024           # spending over time
    python usaspending.py by-agency --fy 2024          # top agencies by spending
    python usaspending.py by-geography --fy 2024       # spending by state
    python usaspending.py fiscal-snapshot              # macro fiscal pulse
    python usaspending.py awards "infrastructure"      # search awards by keyword
    python usaspending.py budget                       # budgetary resources over time
    python usaspending.py overview                     # current FY status
    python usaspending.py search "defense contract"    # free-text award search
    python usaspending.py groups                       # list curated agency groups
    python usaspending.py export agencies --format csv # export any command's data
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

import requests


# --- API Configuration --------------------------------------------------------

BASE_URL = "https://api.usaspending.gov/api/v2"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

AGENCY_REGISTRY = {
    "treasury":       {"code": "015", "name": "Department of the Treasury", "group": "fiscal"},
    "defense":        {"code": "097", "name": "Department of Defense", "group": "defense"},
    "hhs":            {"code": "075", "name": "Department of Health and Human Services", "group": "social"},
    "ssa":            {"code": "028", "name": "Social Security Administration", "group": "social"},
    "education":      {"code": "091", "name": "Department of Education", "group": "social"},
    "veterans":       {"code": "036", "name": "Department of Veterans Affairs", "group": "social"},
    "agriculture":    {"code": "012", "name": "Department of Agriculture", "group": "economy"},
    "transportation": {"code": "069", "name": "Department of Transportation", "group": "infrastructure"},
    "energy":         {"code": "089", "name": "Department of Energy", "group": "infrastructure"},
    "hud":            {"code": "086", "name": "Department of Housing and Urban Development", "group": "housing"},
    "labor":          {"code": "016", "name": "Department of Labor", "group": "labor"},
    "commerce":       {"code": "013", "name": "Department of Commerce", "group": "economy"},
    "interior":       {"code": "014", "name": "Department of the Interior", "group": "resources"},
    "homeland":       {"code": "070", "name": "Department of Homeland Security", "group": "defense"},
    "justice":        {"code": "015", "name": "Department of Justice", "group": "governance"},
    "state":          {"code": "019", "name": "Department of State", "group": "governance"},
    "sba":            {"code": "073", "name": "Small Business Administration", "group": "economy"},
}

GROUP_ORDER = ["fiscal", "defense", "social", "economy", "infrastructure",
               "housing", "labor", "resources", "governance"]

GROUP_NAMES = {
    "fiscal":         "FISCAL",
    "defense":        "DEFENSE",
    "social":         "SOCIAL PROGRAMS",
    "economy":        "ECONOMY",
    "infrastructure": "INFRASTRUCTURE",
    "housing":        "HOUSING",
    "labor":          "LABOR",
    "resources":      "NATURAL RESOURCES",
    "governance":     "GOVERNANCE",
}

AWARD_TYPE_CODES = {
    "contracts":       ["A", "B", "C", "D"],
    "grants":          ["02", "03", "04", "05"],
    "direct_payments": ["06", "10"],
    "loans":           ["07", "08"],
    "insurance":       ["09"],
    "other":           ["11"],
    "all": ["A", "B", "C", "D", "02", "03", "04", "05",
            "06", "07", "08", "09", "10", "11"],
}

VALID_AWARD_TYPES = list(AWARD_TYPE_CODES.keys())

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# --- Fiscal Year Helpers ------------------------------------------------------

def _current_fy():
    now = datetime.now()
    return now.year + 1 if now.month >= 10 else now.year


def _fy_dates(fy):
    return f"{fy - 1}-10-01", f"{fy}-09-30"


# --- HTTP ---------------------------------------------------------------------

def _get(endpoint, params=None, max_retries=3):
    url = f"{BASE_URL}/{endpoint}"
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
            time.sleep(0.3)
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


def _post(endpoint, payload, max_retries=3):
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(max_retries):
        try:
            r = SESSION.post(url, json=payload, timeout=30)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  [rate limited, waiting {wait}s...]")
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                print(f"  [API error {r.status_code}: {r.text[:200]}]")
                return None
            time.sleep(0.3)
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


# --- Formatting ---------------------------------------------------------------

def _fmt_dollars(val):
    if val is None:
        return "$0"
    val = float(val)
    neg = val < 0
    av = abs(val)
    if av >= 1e12:
        s = f"${av / 1e12:.1f}T"
    elif av >= 1e9:
        s = f"${av / 1e9:.1f}B"
    elif av >= 1e6:
        s = f"${av / 1e6:.1f}M"
    elif av >= 1e3:
        s = f"${av / 1e3:.1f}K"
    else:
        s = f"${av:,.0f}"
    return f"-{s}" if neg else s


def _fmt_pct(val, sign=True):
    if val is None:
        return "N/A"
    if sign:
        return f"{val:+.1f}%"
    return f"{val:.1f}%"


def _safe_float(data, key, default=0.0):
    val = data.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _truncate(text, length=80):
    if not text:
        return ""
    text = str(text).replace("\n", " ").strip()
    return text[:length - 3] + "..." if len(text) > length else text


# --- Data Fetchers ------------------------------------------------------------

def _fetch_toptier_agencies():
    data = _get("references/toptier_agencies/")
    if not data:
        return []
    return data.get("results", data) if isinstance(data, dict) else data


def _fetch_agency_detail(toptier_code):
    return _get(f"agency/{toptier_code}/")


def _fetch_budgetary_resources(toptier_code):
    return _get(f"agency/{toptier_code}/budgetary_resources/")


def _fetch_total_budgetary_resources():
    return _get("references/total_budgetary_resources/")


def _fetch_last_updated():
    return _get("awards/last_updated/")


def _fetch_spending_over_time(fy=None, group_by="fiscal_year", award_types=None):
    if fy is None:
        fy = _current_fy()
    if award_types is None:
        award_types = AWARD_TYPE_CODES["all"]
    start, end = _fy_dates(fy)
    payload = {
        "group": group_by,
        "filters": {
            "time_period": [{"start_date": start, "end_date": end}],
            "award_type_codes": award_types,
        },
    }
    return _post("search/spending_over_time/", payload)


def _fetch_spending_over_time_range(fy_start, fy_end, group_by="fiscal_year",
                                    award_types=None):
    if award_types is None:
        award_types = AWARD_TYPE_CODES["all"]
    start, _ = _fy_dates(fy_start)
    _, end = _fy_dates(fy_end)
    payload = {
        "group": group_by,
        "filters": {
            "time_period": [{"start_date": start, "end_date": end}],
            "award_type_codes": award_types,
        },
    }
    return _post("search/spending_over_time/", payload)


def _fetch_spending_by_agency(fy=None, limit=10, page=1, award_types=None):
    if fy is None:
        fy = _current_fy()
    if award_types is None:
        award_types = AWARD_TYPE_CODES["all"]
    start, end = _fy_dates(fy)
    payload = {
        "filters": {
            "time_period": [{"start_date": start, "end_date": end}],
            "award_type_codes": award_types,
        },
        "category": "awarding_agency",
        "limit": limit,
        "page": page,
    }
    return _post("search/spending_by_category/awarding_agency/", payload)


def _fetch_spending_by_geography(fy=None, geo_layer="state",
                                 scope="place_of_performance", award_types=None):
    if fy is None:
        fy = _current_fy()
    if award_types is None:
        award_types = AWARD_TYPE_CODES["all"]
    start, end = _fy_dates(fy)
    payload = {
        "scope": scope,
        "geo_layer": geo_layer,
        "filters": {
            "time_period": [{"start_date": start, "end_date": end}],
            "award_type_codes": award_types,
        },
    }
    return _post("search/spending_by_geography/", payload)


def _fetch_spending_by_award(keyword=None, fy=None, award_types=None,
                             limit=25, page=1):
    if fy is None:
        fy = _current_fy()
    if award_types is None:
        award_types = AWARD_TYPE_CODES["all"]
    start, end = _fy_dates(fy)
    filters = {
        "time_period": [{"start_date": start, "end_date": end}],
        "award_type_codes": award_types,
    }
    if keyword:
        filters["keywords"] = [keyword]
    payload = {
        "filters": filters,
        "fields": ["Award ID", "Recipient Name", "Award Amount",
                   "Awarding Agency", "Award Type", "Description",
                   "Start Date", "End Date"],
        "limit": limit,
        "page": page,
        "sort": "Award Amount",
        "order": "desc",
    }
    return _post("search/spending_by_award/", payload)


def _fetch_federal_spending(fy=None):
    if fy is None:
        fy = _current_fy()
    payload = {
        "type": "agency",
        "filters": {"fy": str(fy)},
    }
    return _post("spending/", payload)


# --- Display ------------------------------------------------------------------

def _display_agencies_table(agencies):
    print(f"\n  Top-Tier Federal Agencies")
    print("  " + "=" * 78)
    print(f"  {'#':<4} {'Agency':<42} {'Abbr':<8} {'Budget Auth':>18}")
    print(f"  {'-'*4} {'-'*42} {'-'*8} {'-'*18}")
    for i, a in enumerate(agencies[:30], 1):
        name = _truncate(a.get("agency_name", ""), 41)
        abbr = (a.get("abbreviation", "") or "")[:7]
        ba = _fmt_dollars(a.get("current_total_budget_authority_amount", 0))
        print(f"  {i:<4} {name:<42} {abbr:<8} {ba:>18}")
    total = len(agencies)
    if total > 30:
        print(f"\n  ... showing top 30 of {total} agencies")
    print(f"\n  Total agencies listed: {total}")


def _display_agency_detail(data, alias=None):
    label = f" ({alias})" if alias else ""
    print(f"\n  {data.get('name', 'Unknown Agency')}{label}")
    print("  " + "=" * 70)
    for key, lbl in [("toptier_code", "Toptier Code"),
                     ("abbreviation", "Abbreviation"),
                     ("agency_id", "Agency ID")]:
        val = data.get(key)
        if val:
            print(f"  {lbl + ':':<28} {val}")
    print()
    for key, lbl in [("budget_authority_amount", "Budget Authority"),
                     ("current_total_budget_authority_amount", "Current Budget Auth"),
                     ("obligated_amount", "Obligations"),
                     ("outlay_amount", "Outlays")]:
        val = data.get(key)
        if val is not None:
            print(f"  {lbl + ':':<28} {_fmt_dollars(val)}")
    pct = data.get("percentage_of_total_budget_authority")
    if pct is not None:
        print(f"  {'Pct of Total Budget:':<28} {pct:.2f}%")
    if data.get("mission"):
        print(f"\n  Mission: {_truncate(data['mission'], 120)}")


def _display_budgetary_resources(data, alias=None):
    if not data:
        print("  [no budgetary resources data]")
        return
    years = data.get("agency_data_by_year", [])
    if not years:
        print("  [no yearly data]")
        return
    print(f"\n  Budgetary Resources: {alias or 'Agency'}")
    print("  " + "=" * 62)
    print(f"  {'FY':<6} {'Budget Auth':>18} {'Obligations':>18} {'Outlays':>18}")
    print(f"  {'-'*6} {'-'*18} {'-'*18} {'-'*18}")
    for yr in sorted(years, key=lambda x: x.get("fiscal_year", 0), reverse=True)[:8]:
        print(f"  {yr.get('fiscal_year', ''):<6} "
              f"{_fmt_dollars(yr.get('agency_budgetary_resources', 0)):>18} "
              f"{_fmt_dollars(yr.get('agency_total_obligated', 0)):>18} "
              f"{_fmt_dollars(yr.get('agency_total_outlayed', 0)):>18}")


def _display_spending_over_time(data, title="Spending Over Time"):
    if not data:
        print("  [no spending data]")
        return
    results = data.get("results", [])
    if not results:
        print("  [no time series results]")
        return
    print(f"\n  {title}")
    print("  " + "=" * 55)
    print(f"  {'Period':<20} {'Obligations':>16} {'Outlays':>16}")
    print(f"  {'-'*20} {'-'*16} {'-'*16}")
    for r in sorted(results, key=lambda x: (
        x.get("time_period", {}).get("fiscal_year", 0),
        x.get("time_period", {}).get("month", 0))):
        tp = r.get("time_period", {})
        fy = tp.get("fiscal_year", "")
        month = tp.get("month")
        label = f"FY{fy} M{month:02d}" if month else f"FY{fy}"
        oblig = _fmt_dollars(r.get("aggregated_amount", 0))
        outlays = _fmt_dollars(r.get("aggregated_outlay_amount", 0))
        print(f"  {label:<20} {oblig:>16} {outlays:>16}")


def _agency_amount(r):
    return r.get("amount", r.get("aggregated_amount", 0))


def _display_by_agency(data, fy=None):
    if not data:
        print("  [no agency spending data]")
        return
    results = data.get("results", [])
    if not results:
        print("  [no results]")
        return
    fy_label = f" (FY{fy})" if fy else ""
    print(f"\n  Top Agencies by Spending{fy_label}")
    print("  " + "=" * 68)
    print(f"  {'#':<4} {'Agency':<42} {'Amount':>18}")
    print(f"  {'-'*4} {'-'*42} {'-'*18}")
    for i, r in enumerate(results, 1):
        name = _truncate(r.get("name", "Unknown"), 41)
        amt = _fmt_dollars(_agency_amount(r))
        print(f"  {i:<4} {name:<42} {amt:>18}")


def _display_geography(data, fy=None):
    if not data:
        print("  [no geography data]")
        return
    results = data.get("results", [])
    if not results:
        print("  [no geography results]")
        return

    ranked = sorted(results, key=lambda x: abs(float(
        x.get("aggregated_amount", 0) or 0)), reverse=True)
    fy_label = f" (FY{fy})" if fy else ""
    print(f"\n  Spending by State{fy_label}")
    print("  " + "=" * 58)
    print(f"  {'#':<4} {'State':<25} {'Code':<6} {'Amount':>18}")
    print(f"  {'-'*4} {'-'*25} {'-'*6} {'-'*18}")
    for i, r in enumerate(ranked[:30], 1):
        name = r.get("display_name", r.get("shape_code", "Unknown"))
        code = r.get("shape_code", "")
        amt = _fmt_dollars(r.get("aggregated_amount", 0))
        print(f"  {i:<4} {name:<25} {code:<6} {amt:>18}")
    remaining = len(results) - 30
    if remaining > 0:
        print(f"\n  ... and {remaining} more states/territories")


def _display_awards(data):
    if not data:
        print("  [no award data]")
        return
    results = data.get("results", [])
    if not results:
        print("  [no awards found]")
        return

    total = data.get("page_metadata", {}).get("total", len(results))
    print(f"\n  Awards ({total} total, showing {len(results)})")
    print("  " + "=" * 78)
    for i, a in enumerate(results[:20], 1):
        award_id = a.get("Award ID", "N/A")
        recipient = _truncate(a.get("Recipient Name", "Unknown"), 45)
        amount = _fmt_dollars(a.get("Award Amount", 0))
        agency = _truncate(a.get("Awarding Agency", ""), 35)
        atype = a.get("Award Type", "")
        desc = _truncate(a.get("Description", ""), 70)
        print(f"\n  {i}) {award_id}")
        print(f"     Recipient:  {recipient}")
        print(f"     Amount:     {amount}")
        print(f"     Agency:     {agency}")
        print(f"     Type:       {atype}")
        if desc:
            print(f"     Desc:       {desc}")


def _display_total_budget(data):
    if not data:
        print("  [no budget data]")
        return
    results = data.get("results", [])
    if not results:
        print("  [no budget results]")
        return
    print(f"\n  Total Federal Budgetary Resources")
    print("  " + "=" * 50)
    print(f"  {'FY':<6} {'Period':>8} {'Total Budget':>22}")
    print(f"  {'-'*6} {'-'*8} {'-'*22}")
    seen = set()
    for r in sorted(results, key=lambda x: (
        x.get("fiscal_year", 0), x.get("fiscal_period", 0)), reverse=True):
        fy = r.get("fiscal_year", "")
        period = r.get("fiscal_period", "")
        total = _fmt_dollars(r.get("total_budgetary_resources", 0))
        key = (fy, period)
        if key not in seen:
            seen.add(key)
            print(f"  {fy:<6} {period:>8} {total:>22}")
        if len(seen) >= 15:
            break


def _display_fiscal_snapshot(snapshot):
    if not snapshot:
        print("  [could not build fiscal snapshot]")
        return
    fy = snapshot["fy"]
    print(f"\n  FISCAL PULSE SNAPSHOT -- FY{fy}")
    print("  " + "=" * 70)
    print(f"  Data last updated: {snapshot.get('last_updated', 'N/A')}")

    total = snapshot.get("total_budget", {})
    if total:
        print(f"\n  AGGREGATE BUDGET")
        print(f"  {'Total Budget Authority:':<35} {_fmt_dollars(total.get('budget_authority', 0))}")
        if total.get("period"):
            print(f"  {'As of fiscal period:':<35} {total['period']}")

    yoy = snapshot.get("yoy_change")
    if yoy is not None:
        direction = "UP" if yoy > 0 else "DOWN" if yoy < 0 else "FLAT"
        print(f"\n  Year-over-Year Change in Budget Authority")
        print(f"  {'Change:':<35} {_fmt_pct(yoy)} ({direction})")
        prev_ba = snapshot.get("prev_budget_authority")
        if prev_ba:
            print(f"  FY{fy-1} Budget Auth:                  {_fmt_dollars(prev_ba)}")
            print(f"  FY{fy} Budget Auth:                  {_fmt_dollars(total.get('budget_authority', 0))}")

    agencies = snapshot.get("top_agencies", [])
    if agencies:
        print(f"\n  TOP 10 AGENCIES BY AWARD SPENDING")
        print(f"  {'#':<4} {'Agency':<42} {'Amount':>18}")
        print(f"  {'-'*4} {'-'*42} {'-'*18}")
        for i, a in enumerate(agencies, 1):
            name = _truncate(a.get("name", "Unknown"), 41)
            amt = _fmt_dollars(_agency_amount(a))
            print(f"  {i:<4} {name:<42} {amt:>18}")

    groups = snapshot.get("group_totals", {})
    if groups:
        print(f"\n  CURATED AGENCY GROUPS")
        print(f"  {'Group':<22} {'Agencies':>8}  {'Members'}")
        print(f"  {'-'*22} {'-'*8}  {'-'*35}")
        for grp in GROUP_ORDER:
            if grp in groups:
                info = groups[grp]
                members = ", ".join(info["aliases"][:4])
                if len(info["aliases"]) > 4:
                    members += "..."
                print(f"  {GROUP_NAMES.get(grp, grp.upper()):<22} {info['count']:>8}  {members}")


# --- Snapshot Builder ---------------------------------------------------------

def _build_fiscal_snapshot(fy=None):
    if fy is None:
        fy = _current_fy()
    snapshot = {"fy": fy}

    print(f"  Building fiscal snapshot for FY{fy}...")

    print(f"  [1/4] Fetching last update date...")
    updated = _fetch_last_updated()
    if updated:
        snapshot["last_updated"] = updated.get("last_updated", "N/A")

    print(f"  [2/4] Fetching total budgetary resources...")
    budget_data = _fetch_total_budgetary_resources()
    if budget_data:
        results = budget_data.get("results", [])
        fy_results = [r for r in results if r.get("fiscal_year") == fy]
        if fy_results:
            latest = max(fy_results, key=lambda x: x.get("fiscal_period", 0))
            snapshot["total_budget"] = {
                "budget_authority": latest.get("total_budgetary_resources", 0),
                "period": latest.get("fiscal_period"),
            }

        prev_fy = fy - 1
        prev_results = [r for r in results if r.get("fiscal_year") == prev_fy]
        if prev_results and fy_results:
            prev_latest = max(prev_results, key=lambda x: x.get("fiscal_period", 0))
            curr_val = float(latest.get("total_budgetary_resources", 0) or 0)
            prev_val = float(prev_latest.get("total_budgetary_resources", 0) or 0)
            snapshot["prev_budget_authority"] = prev_val
            if prev_val > 0:
                snapshot["yoy_change"] = (curr_val - prev_val) / prev_val * 100

    print(f"  [3/4] Fetching top agencies by spending...")
    agency_data = _fetch_spending_by_agency(fy=fy, limit=10)
    if agency_data:
        snapshot["top_agencies"] = agency_data.get("results", [])

    print(f"  [4/4] Building group breakdown...")
    group_totals = {}
    for alias, info in AGENCY_REGISTRY.items():
        grp = info["group"]
        if grp not in group_totals:
            group_totals[grp] = {"count": 0, "aliases": []}
        group_totals[grp]["count"] += 1
        group_totals[grp]["aliases"].append(alias)
    snapshot["group_totals"] = group_totals

    return snapshot


# --- Export -------------------------------------------------------------------

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


# --- Commands -----------------------------------------------------------------

def cmd_agencies(as_json=False, export_fmt=None):
    print("\n  Fetching top-tier agencies...")
    agencies = _fetch_toptier_agencies()
    if not agencies:
        print("  [no agencies returned]")
        return

    if as_json:
        print(json.dumps(agencies, indent=2, default=str))
        return

    ranked = sorted(
        agencies,
        key=lambda x: abs(float(x.get("current_total_budget_authority_amount", 0) or 0)),
        reverse=True,
    )
    _display_agencies_table(ranked)

    if export_fmt:
        flat = [{
            "agency_name": a.get("agency_name", ""),
            "abbreviation": a.get("abbreviation", ""),
            "toptier_code": a.get("toptier_code", ""),
            "budget_authority": a.get("current_total_budget_authority_amount", 0),
            "active_fq": a.get("active_fq", ""),
            "active_fy": a.get("active_fy", ""),
        } for a in ranked]
        _do_export(flat, "usaspending_agencies", export_fmt)


def cmd_agency(alias=None, toptier_code=None, as_json=False, export_fmt=None):
    if alias:
        entry = AGENCY_REGISTRY.get(alias.lower())
        if not entry:
            print(f"  [unknown alias '{alias}' -- use 'groups' to see aliases]")
            return
        toptier_code = entry["code"]
    if not toptier_code:
        print("  [provide an agency alias or toptier code]")
        return

    print(f"  Fetching agency detail for code {toptier_code}...")
    detail = _fetch_agency_detail(toptier_code)
    if not detail:
        print("  [no agency data returned]")
        return

    if as_json:
        budget = _fetch_budgetary_resources(toptier_code)
        combined = {"detail": detail, "budgetary_resources": budget}
        print(json.dumps(combined, indent=2, default=str))
        return

    _display_agency_detail(detail, alias)

    print(f"\n  Fetching budgetary resources...")
    budget = _fetch_budgetary_resources(toptier_code)
    if budget:
        _display_budgetary_resources(budget, alias)

    if export_fmt:
        _do_export(detail, f"usaspending_agency_{toptier_code}", export_fmt)


def cmd_spending(fy=None, group_by="fiscal_year", award_type="all",
                 as_json=False, export_fmt=None):
    if fy is None:
        fy = _current_fy()
    codes = AWARD_TYPE_CODES.get(award_type, AWARD_TYPE_CODES["all"])

    if group_by == "month":
        print(f"  Fetching monthly spending for FY{fy}...")
        data = _fetch_spending_over_time(fy=fy, group_by="month", award_types=codes)
    else:
        fy_start = max(fy - 4, 2017)
        print(f"  Fetching spending FY{fy_start}-FY{fy}...")
        data = _fetch_spending_over_time_range(fy_start, fy,
                                               group_by="fiscal_year",
                                               award_types=codes)
    if not data:
        print("  [no spending data returned]")
        return

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return

    title = f"Monthly Spending FY{fy}" if group_by == "month" else "Spending Over Time"
    _display_spending_over_time(data, title=title)

    if export_fmt:
        rows = []
        for r in data.get("results", []):
            tp = r.get("time_period", {})
            rows.append({
                "fiscal_year": tp.get("fiscal_year", ""),
                "month": tp.get("month", ""),
                "obligations": r.get("aggregated_amount", 0),
                "outlays": r.get("aggregated_outlay_amount", 0),
            })
        _do_export(rows, "usaspending_spending", export_fmt)


def cmd_by_agency(fy=None, limit=10, award_type="all",
                  as_json=False, export_fmt=None):
    if fy is None:
        fy = _current_fy()
    codes = AWARD_TYPE_CODES.get(award_type, AWARD_TYPE_CODES["all"])
    print(f"  Fetching top {limit} agencies by spending for FY{fy}...")
    data = _fetch_spending_by_agency(fy=fy, limit=limit, award_types=codes)
    if not data:
        print("  [no data returned]")
        return

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return

    _display_by_agency(data, fy=fy)

    if export_fmt:
        rows = [{
            "rank": i,
            "agency": r.get("name", ""),
            "amount": _agency_amount(r),
            "id": r.get("id", ""),
        } for i, r in enumerate(data.get("results", []), 1)]
        _do_export(rows, f"usaspending_by_agency_fy{fy}", export_fmt)


def cmd_by_geography(fy=None, geo_layer="state", award_type="all",
                     as_json=False, export_fmt=None):
    if fy is None:
        fy = _current_fy()
    codes = AWARD_TYPE_CODES.get(award_type, AWARD_TYPE_CODES["all"])
    print(f"  Fetching spending by {geo_layer} for FY{fy}...")
    data = _fetch_spending_by_geography(fy=fy, geo_layer=geo_layer,
                                        award_types=codes)
    if not data:
        print("  [no geography data returned]")
        return

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return

    _display_geography(data, fy=fy)

    if export_fmt:
        rows = [{
            "rank": i,
            "state": r.get("display_name", r.get("shape_code", "")),
            "code": r.get("shape_code", ""),
            "amount": r.get("aggregated_amount", 0),
            "per_capita": r.get("per_capita", ""),
            "population": r.get("population", ""),
        } for i, r in enumerate(
            sorted(data.get("results", []),
                   key=lambda x: abs(float(x.get("aggregated_amount", 0) or 0)),
                   reverse=True), 1)]
        _do_export(rows, f"usaspending_geography_fy{fy}", export_fmt)


def cmd_fiscal_snapshot(fy=None, as_json=False, export_fmt=None):
    if fy is None:
        fy = _current_fy()
    snapshot = _build_fiscal_snapshot(fy=fy)

    if as_json:
        print(json.dumps(snapshot, indent=2, default=str))
        return

    _display_fiscal_snapshot(snapshot)

    if export_fmt:
        _do_export(snapshot, f"usaspending_snapshot_fy{fy}", export_fmt)


def cmd_awards(keyword=None, fy=None, award_type="all", limit=25,
               as_json=False, export_fmt=None):
    if fy is None:
        fy = _current_fy()
    codes = AWARD_TYPE_CODES.get(award_type, AWARD_TYPE_CODES["all"])
    label = f" matching '{keyword}'" if keyword else ""
    print(f"  Searching awards{label} in FY{fy}...")
    data = _fetch_spending_by_award(keyword=keyword, fy=fy,
                                    award_types=codes, limit=limit)
    if not data:
        print("  [no data returned]")
        return

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return

    _display_awards(data)

    if export_fmt:
        _do_export(data.get("results", []), "usaspending_awards", export_fmt)


def cmd_budget(as_json=False, export_fmt=None):
    print("  Fetching total budgetary resources...")
    data = _fetch_total_budgetary_resources()
    if not data:
        print("  [no data returned]")
        return

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return

    _display_total_budget(data)

    if export_fmt:
        rows = [{
            "fiscal_year": r.get("fiscal_year", ""),
            "fiscal_period": r.get("fiscal_period", ""),
            "total_budgetary_resources": r.get("total_budgetary_resources", 0),
        } for r in data.get("results", [])]
        _do_export(rows, "usaspending_budget", export_fmt)


def cmd_overview(fy=None, as_json=False, export_fmt=None):
    if fy is None:
        fy = _current_fy()
    print(f"  Fetching FY{fy} overview...")
    overview = {"fy": fy}

    print(f"  [1/3] Budget authority...")
    budget_data = _fetch_total_budgetary_resources()
    if budget_data:
        results = budget_data.get("results", [])
        fy_results = [r for r in results if r.get("fiscal_year") == fy]
        if fy_results:
            latest = max(fy_results, key=lambda x: x.get("fiscal_period", 0))
            overview["total_budget_authority"] = latest.get(
                "total_budgetary_resources", 0)
            overview["fiscal_period"] = latest.get("fiscal_period")

    print(f"  [2/3] Top agencies...")
    agency_data = _fetch_spending_by_agency(fy=fy, limit=5)
    if agency_data:
        overview["top_5_agencies"] = agency_data.get("results", [])

    print(f"  [3/3] Last update...")
    updated = _fetch_last_updated()
    if updated:
        overview["last_updated"] = updated.get("last_updated", "")

    if as_json:
        print(json.dumps(overview, indent=2, default=str))
        return

    print(f"\n  FY{fy} OVERVIEW")
    print("  " + "=" * 58)
    if "last_updated" in overview:
        print(f"  Data last updated: {overview['last_updated']}")
    if "total_budget_authority" in overview:
        print(f"  Total Budget Authority: {_fmt_dollars(overview['total_budget_authority'])}")
        print(f"  As of fiscal period:    {overview.get('fiscal_period', 'N/A')}")

    agencies = overview.get("top_5_agencies", [])
    if agencies:
        print(f"\n  Top 5 Agencies by Award Spending")
        print(f"  {'#':<4} {'Agency':<42} {'Amount':>14}")
        print(f"  {'-'*4} {'-'*42} {'-'*14}")
        for i, a in enumerate(agencies, 1):
            name = _truncate(a.get("name", ""), 41)
            amt = _fmt_dollars(_agency_amount(a))
            print(f"  {i:<4} {name:<42} {amt:>14}")

    if export_fmt:
        _do_export(overview, f"usaspending_overview_fy{fy}", export_fmt)


def cmd_search(keyword=None, fy=None, award_type="all", limit=25,
               as_json=False, export_fmt=None):
    if not keyword:
        print("  [provide a search keyword]")
        return
    cmd_awards(keyword=keyword, fy=fy, award_type=award_type,
               limit=limit, as_json=as_json, export_fmt=export_fmt)


def cmd_groups(as_json=False):
    if as_json:
        groups = {}
        for grp in GROUP_ORDER:
            agencies = {a: info for a, info in AGENCY_REGISTRY.items()
                        if info["group"] == grp}
            groups[grp] = agencies
        print(json.dumps(groups, indent=2, default=str))
        return

    print(f"\n  Curated Agency Groups ({len(AGENCY_REGISTRY)} agencies, "
          f"{len(GROUP_ORDER)} groups)")
    print("  " + "=" * 70)
    for grp in GROUP_ORDER:
        aliases = [(a, info) for a, info in AGENCY_REGISTRY.items()
                   if info["group"] == grp]
        if not aliases:
            continue
        print(f"\n  {GROUP_NAMES.get(grp, grp.upper())}")
        print(f"  {'Alias':<16} {'Code':>5}  {'Agency Name'}")
        print(f"  {'-'*16} {'-'*5}  {'-'*45}")
        for alias, info in aliases:
            print(f"  {alias:<16} {info['code']:>5}  {info['name']}")

    print(f"\n  Total: {len(AGENCY_REGISTRY)} agencies across {len(GROUP_ORDER)} groups")
    print(f"  Usage: python usaspending.py agency treasury")
    print(f"  Usage: python usaspending.py by-agency --fy 2024\n")


def cmd_export(target="agencies", fy=None, fmt="csv"):
    if fy is None:
        fy = _current_fy()
    dispatch = {
        "agencies":        lambda: cmd_agencies(export_fmt=fmt),
        "spending":        lambda: cmd_spending(fy=fy, export_fmt=fmt),
        "by-agency":       lambda: cmd_by_agency(fy=fy, export_fmt=fmt),
        "by-geography":    lambda: cmd_by_geography(fy=fy, export_fmt=fmt),
        "budget":          lambda: cmd_budget(export_fmt=fmt),
        "overview":        lambda: cmd_overview(fy=fy, export_fmt=fmt),
        "fiscal-snapshot": lambda: cmd_fiscal_snapshot(fy=fy, export_fmt=fmt),
    }
    if target not in dispatch:
        print(f"  [unknown export target '{target}']")
        print(f"  Available: {', '.join(dispatch.keys())}")
        return
    dispatch[target]()


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   USASpending.gov -- Federal Spending & Fiscal Pulse
  =====================================================

   AGENCIES
     1) agencies          List top-tier agencies
     2) agency            Deep dive on a specific agency
     3) groups            Curated agency groups

   SPENDING
     4) spending          Spending over time
     5) by-agency         Top agencies by spending
     6) by-geography      Spending by state

   MACRO
     7) fiscal-snapshot   Macro fiscal pulse
     8) budget            Total budgetary resources
     9) overview          Current FY status

   AWARDS
    10) awards            Search awards by keyword
    11) search            Free-text award search

   DATA
    12) export            Export any command's data

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
    choices_str = "/".join(str(c) for c in choices)
    return _prompt(f"{msg} ({choices_str})", default)


def _i_agencies():
    cmd_agencies()


def _i_agency():
    print(f"  Aliases: {', '.join(AGENCY_REGISTRY.keys())}")
    alias = _prompt("Agency alias or toptier code")
    if alias.lower() in AGENCY_REGISTRY:
        cmd_agency(alias=alias.lower())
    else:
        cmd_agency(toptier_code=alias)


def _i_groups():
    cmd_groups()


def _i_spending():
    fy = _prompt("Fiscal year", str(_current_fy()))
    group_by = _prompt_choice("Group by", ["fiscal_year", "month"], "fiscal_year")
    atype = _prompt_choice("Award type", VALID_AWARD_TYPES, "all")
    cmd_spending(fy=int(fy), group_by=group_by, award_type=atype)


def _i_by_agency():
    fy = _prompt("Fiscal year", str(_current_fy()))
    limit = _prompt("Number of agencies", "10")
    atype = _prompt_choice("Award type", VALID_AWARD_TYPES, "all")
    cmd_by_agency(fy=int(fy), limit=int(limit), award_type=atype)


def _i_by_geography():
    fy = _prompt("Fiscal year", str(_current_fy()))
    layer = _prompt_choice("Geography", ["state", "county", "district"], "state")
    atype = _prompt_choice("Award type", VALID_AWARD_TYPES, "all")
    cmd_by_geography(fy=int(fy), geo_layer=layer, award_type=atype)


def _i_fiscal_snapshot():
    fy = _prompt("Fiscal year", str(_current_fy()))
    cmd_fiscal_snapshot(fy=int(fy))


def _i_budget():
    cmd_budget()


def _i_overview():
    fy = _prompt("Fiscal year", str(_current_fy()))
    cmd_overview(fy=int(fy))


def _i_awards():
    keyword = _prompt("Keyword (or blank for all)")
    fy = _prompt("Fiscal year", str(_current_fy()))
    atype = _prompt_choice("Award type", VALID_AWARD_TYPES, "all")
    keyword = keyword if keyword else None
    cmd_awards(keyword=keyword, fy=int(fy), award_type=atype)


def _i_search():
    keyword = _prompt("Search term")
    if not keyword:
        print("  [search requires a keyword]")
        return
    fy = _prompt("Fiscal year", str(_current_fy()))
    cmd_search(keyword=keyword, fy=int(fy))


def _i_export():
    targets = ["agencies", "spending", "by-agency", "by-geography",
               "budget", "overview", "fiscal-snapshot"]
    print(f"  Targets: {', '.join(targets)}")
    target = _prompt("Export target", "agencies")
    fmt = _prompt_choice("Format", ["csv", "json"], "csv")
    fy = _prompt("Fiscal year", str(_current_fy()))
    cmd_export(target=target, fy=int(fy), fmt=fmt)


COMMAND_MAP = {
    "1":  _i_agencies,
    "2":  _i_agency,
    "3":  _i_groups,
    "4":  _i_spending,
    "5":  _i_by_agency,
    "6":  _i_by_geography,
    "7":  _i_fiscal_snapshot,
    "8":  _i_budget,
    "9":  _i_overview,
    "10": _i_awards,
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

EXPORT_TARGETS = ["agencies", "spending", "by-agency", "by-geography",
                  "budget", "overview", "fiscal-snapshot"]


def build_argparse():
    p = argparse.ArgumentParser(
        prog="usaspending.py",
        description="USASpending.gov -- Federal Spending & Fiscal Pulse Client",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("agencies", help="List top-tier agencies")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("agency", help="Deep dive on a specific agency")
    s.add_argument("alias", help="Agency alias (e.g. treasury) or toptier code")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("spending", help="Spending over time")
    s.add_argument("--fy", type=int, default=None)
    s.add_argument("--group-by", choices=["fiscal_year", "month"],
                   default="fiscal_year")
    s.add_argument("--award-type", choices=VALID_AWARD_TYPES, default="all")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("by-agency", help="Top agencies by spending")
    s.add_argument("--fy", type=int, default=None)
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--award-type", choices=VALID_AWARD_TYPES, default="all")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("by-geography", help="Spending by state/county/district")
    s.add_argument("--fy", type=int, default=None)
    s.add_argument("--geo-layer", choices=["state", "county", "district"],
                   default="state")
    s.add_argument("--award-type", choices=VALID_AWARD_TYPES, default="all")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("fiscal-snapshot", help="Macro fiscal pulse snapshot")
    s.add_argument("--fy", type=int, default=None)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("awards", help="Search awards by keyword")
    s.add_argument("keyword", nargs="?", default=None, help="Search keyword")
    s.add_argument("--fy", type=int, default=None)
    s.add_argument("--award-type", choices=VALID_AWARD_TYPES, default="all")
    s.add_argument("--limit", type=int, default=25)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("budget", help="Total budgetary resources over time")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("overview", help="Current FY status")
    s.add_argument("--fy", type=int, default=None)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("search", help="Free-text award search")
    s.add_argument("keyword", help="Search term")
    s.add_argument("--fy", type=int, default=None)
    s.add_argument("--award-type", choices=VALID_AWARD_TYPES, default="all")
    s.add_argument("--limit", type=int, default=25)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("groups", help="List curated agency groups")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("export", help="Export data from any command")
    s.add_argument("target", choices=EXPORT_TARGETS)
    s.add_argument("--fy", type=int, default=None)
    s.add_argument("--format", choices=["csv", "json"], default="csv")

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)
    fy = getattr(args, "fy", None)

    if args.command == "agencies":
        cmd_agencies(as_json=j, export_fmt=exp)
    elif args.command == "agency":
        alias = args.alias
        if alias.lower() in AGENCY_REGISTRY:
            cmd_agency(alias=alias.lower(), as_json=j, export_fmt=exp)
        else:
            cmd_agency(toptier_code=alias, as_json=j, export_fmt=exp)
    elif args.command == "spending":
        cmd_spending(fy=fy, group_by=args.group_by,
                     award_type=args.award_type, as_json=j, export_fmt=exp)
    elif args.command == "by-agency":
        cmd_by_agency(fy=fy, limit=args.limit,
                      award_type=args.award_type, as_json=j, export_fmt=exp)
    elif args.command == "by-geography":
        cmd_by_geography(fy=fy, geo_layer=args.geo_layer,
                         award_type=args.award_type, as_json=j, export_fmt=exp)
    elif args.command == "fiscal-snapshot":
        cmd_fiscal_snapshot(fy=fy, as_json=j, export_fmt=exp)
    elif args.command == "awards":
        cmd_awards(keyword=args.keyword, fy=fy,
                   award_type=args.award_type, limit=args.limit,
                   as_json=j, export_fmt=exp)
    elif args.command == "budget":
        cmd_budget(as_json=j, export_fmt=exp)
    elif args.command == "overview":
        cmd_overview(fy=fy, as_json=j, export_fmt=exp)
    elif args.command == "search":
        cmd_search(keyword=args.keyword, fy=fy,
                   award_type=args.award_type, limit=args.limit,
                   as_json=j, export_fmt=exp)
    elif args.command == "groups":
        cmd_groups(as_json=j)
    elif args.command == "export":
        cmd_export(target=args.target, fy=fy, fmt=args.format)


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
